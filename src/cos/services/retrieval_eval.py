"""Retrieval benchmark orchestration service."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.ingestion.embedder import EmbeddingResult, VoyageTransportConfig, embed
from cos.retrieval.benchmark import (
    BenchmarkQuery,
    BenchmarkReport,
    ClassSummary,
    FixtureDoc,
    CorpusError,
    QueryResult,
    SINGLE_LINEAGE_CLASSES,
    aggregate_by_class,
    load_fixture_docs,
    load_queries,
    resolve_corpus_version,
    score_query,
)
from cos.retrieval.citations import CitedResults, narrow_to_lineage
from cos.retrieval.search import hybrid_search
from cos.store.db import store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord


class RetrievalEvalService:
    def __init__(self, config: CosConfig, pool: AsyncConnectionPool) -> None:
        self._config = config
        self._pool = pool

    async def run_benchmark(
        self,
        corpus_path: Path,
        include_stress_fuzz: bool = False,
    ) -> BenchmarkReport:
        queries = load_queries(corpus_path, include_stress_fuzz)
        fixture_docs = load_fixture_docs(corpus_path)
        corpus_version = resolve_corpus_version(corpus_path)
        run_timestamp = datetime.now(timezone.utc).isoformat()

        async with self._pool.connection() as conn:
            await self._seed_fixtures(conn, corpus_path / "generated", fixture_docs)

        results: list[QueryResult] = []
        async with self._pool.connection() as conn:
            for query in queries:
                result = await self._run_query(conn, query)
                results.append(result)

        async with self._pool.connection() as conn:
            await self._cleanup_fixtures(conn, fixture_docs)

        per_class = aggregate_by_class(results)
        return _build_report(run_timestamp, corpus_version, results, per_class)

    async def _seed_fixtures(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        generated_dir: Path,
        docs: list[FixtureDoc],
    ) -> None:
        for doc in docs:
            content_path = generated_dir / doc.filename
            if not content_path.exists():
                raise CorpusError(f"Fixture document not found: {content_path}")

            content = content_path.read_text(encoding="utf-8")
            sha256 = hashlib.sha256(content.encode()).hexdigest()
            source_path = doc.source_locator

            embedding_results = await embed(
                [content],
                provider=self._config.embedding.provider,
                model=self._config.embedding.model,
                api_key=(
                    self._config.embedding.api_key.get_secret_value()
                    if self._config.embedding.api_key
                    else ""
                ),
                transport=VoyageTransportConfig(
                    ca_bundle_path=self._config.embedding.ca_bundle_path,
                    proxy_url=self._config.embedding.proxy_url,
                    trust_env=self._config.embedding.trust_env,
                ),
            )

            chunks = [
                ChunkRecord(
                    content=content,
                    chunk_index=0,
                    token_count=len(content.split()),
                )
            ]
            embeddings = [
                EmbeddingRecord(
                    vector=embedding_results[0].vector,
                    model=self._config.embedding.model,
                    provider=self._config.embedding.provider,
                )
            ]

            await store_document_canonical(
                conn,
                source_path=source_path,
                sha256=sha256,
                byte_size=len(content.encode()),
                source_type=doc.source_type,
                source_locator=doc.source_locator,
                source_alias=doc.source_alias,
                chunks=chunks,
                embeddings=embeddings,
            )

    async def _run_query(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        query: BenchmarkQuery,
    ) -> QueryResult:
        t0 = time.monotonic()
        cited = await hybrid_search(
            query.query,
            conn,
            self._config,
            role_pack=None,
            min_score=self._config.retrieval.min_score,
            max_chunks_per_source=self._config.retrieval.max_chunks_per_source,
        )
        latency_ms = (time.monotonic() - t0) * 1000.0

        if cited and query.query_class in SINGLE_LINEAGE_CLASSES:
            cited = narrow_to_lineage(cited)

        return score_query(query, cited, latency_ms)

    async def _cleanup_fixtures(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        docs: list[FixtureDoc],
    ) -> None:
        locators = [doc.source_locator for doc in docs]
        # Remove all document rows whose source_path matches a fixture locator.
        # Cascades through chunks and embeddings.
        await conn.execute(
            "DELETE FROM documents WHERE source_path = ANY(%s)",
            (locators,),
        )
        # Remove the source registry entries.
        await conn.execute(
            "DELETE FROM sources WHERE source_locator = ANY(%s)",
            (locators,),
        )


def _build_report(
    run_timestamp: str,
    corpus_version: str,
    results: list[QueryResult],
    per_class: list[ClassSummary],
) -> BenchmarkReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    answerable = [
        r
        for r in results
        if r.answerability_verdict not in ("correct_no_answer", "false_answer")
    ]
    overall_recall = (
        sum(1 for r in answerable if r.passed) / len(answerable) if answerable else 0.0
    )

    all_actual = [loc for r in results for loc in r.actual_lineage]
    all_expected_sets = [set(r.expected_lineage) for r in results if r.actual_lineage]
    if all_expected_sets and all_actual:
        precision_values = []
        for r in results:
            if r.actual_lineage:
                expected_set = set(r.expected_lineage)
                hits = sum(1 for loc in r.actual_lineage if loc in expected_set)
                precision_values.append(hits / len(r.actual_lineage))
        overall_precision = (
            sum(precision_values) / len(precision_values) if precision_values else 0.0
        )
    else:
        overall_precision = 0.0

    avg_latency = sum(r.latency_ms for r in results) / total if results else 0.0

    return BenchmarkReport(
        run_timestamp=run_timestamp,
        corpus_version=corpus_version,
        per_query=results,
        per_class=per_class,
        overall_recall=overall_recall,
        overall_citation_precision=overall_precision,
        overall_pass_rate=passed / total if total else 0.0,
        total_queries=total,
        passed_queries=passed,
        avg_latency_ms=avg_latency,
    )


def report_to_dict(report: BenchmarkReport) -> dict:  # type: ignore[type-arg]
    return {
        "run_timestamp": report.run_timestamp,
        "corpus_version": report.corpus_version,
        "summary": {
            "total_queries": report.total_queries,
            "passed_queries": report.passed_queries,
            "overall_pass_rate": report.overall_pass_rate,
            "overall_recall": report.overall_recall,
            "overall_citation_precision": report.overall_citation_precision,
            "avg_latency_ms": report.avg_latency_ms,
        },
        "per_class": [
            {
                "query_class": s.query_class,
                "total": s.total,
                "passed": s.passed,
                "recall": s.recall,
                "citation_precision": s.citation_precision,
                "avg_latency_ms": s.avg_latency_ms,
            }
            for s in report.per_class
        ],
        "per_query": [
            {
                "query_id": r.query_id,
                "query_class": r.query_class,
                "pass": r.passed,
                "latency_ms": r.latency_ms,
                "expected_lineage": r.expected_lineage,
                "actual_lineage": r.actual_lineage,
                "answerability_verdict": r.answerability_verdict,
            }
            for r in report.per_query
        ],
    }


def format_human_summary(report: BenchmarkReport) -> str:
    lines = [
        "Retrieval Benchmark Summary",
        f"  Run:          {report.run_timestamp}",
        f"  Corpus:       {report.corpus_version}",
        f"  Queries:      {report.passed_queries}/{report.total_queries} passed "
        f"({report.overall_pass_rate:.0%})",
        f"  Recall:       {report.overall_recall:.0%}",
        f"  Precision:    {report.overall_citation_precision:.0%}",
        f"  Avg latency:  {report.avg_latency_ms:.0f} ms",
        "",
        "  Per-class breakdown:",
    ]
    for s in report.per_class:
        status = "✓" if s.passed == s.total else "✗"
        lines.append(
            f"    {status} {s.query_class:<30} "
            f"{s.passed}/{s.total}  "
            f"recall={s.recall:.0%}  "
            f"precision={s.citation_precision:.0%}  "
            f"avg {s.avg_latency_ms:.0f}ms"
        )
    return "\n".join(lines)
