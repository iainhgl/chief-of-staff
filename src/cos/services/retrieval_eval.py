"""Retrieval benchmark orchestration service."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig
from cos.ingestion.embedder import embed
from cos.retrieval.benchmark import (
    BENCHMARK_SCHEMA_VERSION,
    BenchmarkCitation,
    BenchmarkQuery,
    BenchmarkReport,
    ClassSummary,
    CorpusError,
    FixtureDoc,
    QueryResult,
    aggregate_by_class,
    attribute_failure,
    citation_precision_for_result,
    load_fixture_docs,
    load_queries,
    recall_satisfied,
    resolve_corpus_version,
    score_query,
)
from cos.retrieval.citations import (
    narrow_to_lineage,
    select_document_first_anchors,
    select_synthesis_evidence,
)
from cos.retrieval.context_expansion import expand_bounded_context
from cos.retrieval.search import hybrid_search_with_trace
from cos.retrieval.strategy import QueryStrategy, select_query_strategy_for_class
from cos.store.db import store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord

_BENCHMARK_PROVIDER = "benchmark"
_BENCHMARK_MODEL = "benchmark-static"
_BENCHMARK_SOURCE_PREFIX = "benchmark"


@dataclass(frozen=True)
class SeededFixture:
    source_path: str
    source_type: str
    source_locator: str
    source_alias: str
    citation: BenchmarkCitation


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
        benchmark_config = _benchmark_config(self._config)
        seeded_fixtures: dict[str, SeededFixture] = {}
        results: list[QueryResult] = []
        try:
            async with self._pool.connection() as conn:
                seeded = await self._seed_fixtures(
                    conn,
                    corpus_path / "generated",
                    fixture_docs,
                    benchmark_config,
                )
            seeded_fixtures = {fixture.source_locator: fixture for fixture in seeded}

            async with self._pool.connection() as conn:
                for query in queries:
                    expected_citations = _resolve_expected_citations(
                        query,
                        seeded_fixtures,
                    )
                    result = await self._run_query(
                        conn,
                        query,
                        benchmark_config,
                        expected_citations=expected_citations,
                    )
                    results.append(result)
        finally:
            async with self._pool.connection() as conn:
                await self._cleanup_fixtures(conn, fixture_docs)

        per_class = aggregate_by_class(results)
        retrieval_settings = _retrieval_settings_from_config(benchmark_config)
        return _build_report(
            run_timestamp, corpus_version, results, per_class, retrieval_settings
        )

    async def _seed_fixtures(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        generated_dir: Path,
        docs: list[FixtureDoc],
        benchmark_config: CosConfig,
    ) -> list[SeededFixture]:
        seeded: list[SeededFixture] = []
        for doc in docs:
            content_path = generated_dir / doc.filename
            if not content_path.exists():
                raise CorpusError(f"Fixture document not found: {content_path}")

            content = content_path.read_text(encoding="utf-8")
            source_path = _benchmark_source_path(doc)
            source_type = _benchmark_source_type(doc.source_type)

            if doc.chunk_count > 1:
                chunks, embeddings = await _make_multi_chunks(
                    content, doc.chunk_count, benchmark_config
                )
                citation_chunk_index = doc.citation_chunk_index
            else:
                chunks = [
                    ChunkRecord(
                        content=content,
                        chunk_index=0,
                        token_count=len(content.split()),
                    )
                ]
                embeddings = [
                    EmbeddingRecord(
                        vector=(
                            await embed(
                                [content],
                                provider=benchmark_config.embedding.provider,
                                model=benchmark_config.embedding.model,
                                api_key="",
                            )
                        )[0].vector,
                        model=benchmark_config.embedding.model,
                        provider=benchmark_config.embedding.provider,
                    )
                ]
                citation_chunk_index = 0

            await store_document_canonical(
                conn,
                source_path=source_path,
                sha256=_content_sha256(content),
                byte_size=len(content.encode()),
                source_type=source_type,
                source_locator=doc.source_locator,
                source_alias=doc.source_alias,
                chunks=chunks,
                embeddings=embeddings,
            )
            seeded.append(
                SeededFixture(
                    source_path=source_path,
                    source_type=source_type,
                    source_locator=doc.source_locator,
                    source_alias=doc.source_alias,
                    citation=await _resolve_seeded_citation(
                        conn, source_path, doc, chunk_index=citation_chunk_index
                    ),
                )
            )
        return seeded

    async def _run_query(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        query: BenchmarkQuery,
        benchmark_config: CosConfig,
        expected_citations: list[BenchmarkCitation],
    ) -> QueryResult:
        t0 = time.monotonic()
        cited, stats = await hybrid_search_with_trace(
            query.query,
            conn,
            benchmark_config,
            role_pack=None,
            min_score=benchmark_config.retrieval.min_score,
            max_chunks_per_source=benchmark_config.retrieval.max_chunks_per_source,
        )
        latency_ms = (time.monotonic() - t0) * 1000.0

        document_candidate_count = len(
            {c.document_version_id or c.source_locator for c in cited}
        )

        strategy = select_query_strategy_for_class(query.query_class)

        pre_lineage_cited = list(cited)
        post_lineage_count: int | None = None
        expansion_mode = "none"
        expanded_context_count: int | None = None

        if strategy == QueryStrategy.BOUNDED:
            anchors = select_document_first_anchors(cited)
            post_lineage_count = len(anchors)
            expanded = await expand_bounded_context(conn, anchors)
            evidence = select_synthesis_evidence(expanded.evidence_chunks)
            post_evidence_selection_count = len(evidence)
            expansion_mode = "bounded"
            expanded_context_count = len(expanded.synthesis_chunks)
        elif strategy == QueryStrategy.MULTI_SOURCE:
            evidence = select_synthesis_evidence(
                cited,
                require_multi_source=True,
            )
            post_evidence_selection_count = len(evidence)
        else:  # DEFAULT
            cited = narrow_to_lineage(cited)
            post_lineage_count = len(cited)
            evidence = select_synthesis_evidence(cited)
            post_evidence_selection_count = len(evidence)

        candidate_counts: dict[str, Any] = {
            "keyword": stats.keyword_candidate_count,
            "semantic": stats.semantic_candidate_count,
            "merged": stats.merged_candidate_count,
            "post_threshold": stats.post_threshold_count,
            "post_pruning": stats.post_pruning_count,
            "final": stats.final_candidate_count,
            "document_candidates": document_candidate_count,
            "post_lineage": post_lineage_count,
            "post_evidence_selection": post_evidence_selection_count,
            "expansion_mode": expansion_mode,
            "expanded_context": expanded_context_count,
        }

        result = score_query(
            query,
            evidence,
            latency_ms,
            expected_citations=expected_citations,
            trace_id=str(uuid.uuid4()),
            query_mode=query.query_class,
            candidate_counts=candidate_counts,
            synthesis_mode="not_run",
        )

        post_lineage_result = score_query(
            query,
            cited if strategy == QueryStrategy.DEFAULT else pre_lineage_cited,
            latency_ms,
            expected_citations=expected_citations,
        )
        pre_lineage_result = (
            score_query(
                query,
                pre_lineage_cited,
                latency_ms,
                expected_citations=expected_citations,
            )
            if post_lineage_count is not None and strategy == QueryStrategy.DEFAULT
            else None
        )

        if not result.passed:
            # For BOUNDED: anchor recall vs expansion result (context_expansion stage)
            anchors_passed = (
                recall_satisfied(
                    score_query(
                        query,
                        (
                            select_document_first_anchors(pre_lineage_cited)
                            if pre_lineage_cited
                            else []
                        ),
                        latency_ms,
                        expected_citations=expected_citations,
                    )
                )
                if strategy == QueryStrategy.BOUNDED and pre_lineage_cited
                else False
            )
            result.failure_stage = attribute_failure(
                result.answerability_verdict,
                candidate_counts,
                lineage_narrowing_lost_support=(
                    pre_lineage_result is not None
                    and recall_satisfied(pre_lineage_result)
                    and not recall_satisfied(post_lineage_result)
                ),
                evidence_selection_lost_support=(
                    recall_satisfied(post_lineage_result)
                    and not recall_satisfied(result)
                    and strategy != QueryStrategy.BOUNDED
                ),
                context_expansion_lost_support=(
                    strategy == QueryStrategy.BOUNDED
                    and anchors_passed
                    and not recall_satisfied(result)
                ),
            )

        return result

    async def _cleanup_fixtures(
        self,
        conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
        docs: list[FixtureDoc],
    ) -> None:
        source_paths = [_benchmark_source_path(doc) for doc in docs]
        benchmark_source_types = [
            _benchmark_source_type(doc.source_type) for doc in docs
        ]
        locators = [doc.source_locator for doc in docs]
        await conn.execute(
            "DELETE FROM documents WHERE source_path = ANY(%s)",
            (source_paths,),
        )
        await conn.execute(
            """
            DELETE FROM sources
            WHERE source_type = ANY(%s)
              AND source_locator = ANY(%s)
            """,
            (benchmark_source_types, locators),
        )
        await conn.execute(
            """
            DELETE FROM content_blobs cb
            WHERE NOT EXISTS (
                SELECT 1 FROM document_versions dv WHERE dv.content_blob_id = cb.id
            )
              AND NOT EXISTS (
                SELECT 1 FROM source_versions sv WHERE sv.content_blob_id = cb.id
            )
            """
        )


def _build_report(
    run_timestamp: str,
    corpus_version: str,
    results: list[QueryResult],
    per_class: list[ClassSummary],
    retrieval_settings: dict[str, Any] | None = None,
) -> BenchmarkReport:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    answerable = [
        r
        for r in results
        if r.answerability_verdict not in ("correct_no_answer", "false_answer")
    ]
    overall_recall = (
        sum(1 for r in answerable if recall_satisfied(r)) / len(answerable)
        if answerable
        else 0.0
    )

    precision_values = [
        precision
        for r in results
        if (precision := citation_precision_for_result(r)) is not None
    ]
    overall_precision = (
        sum(precision_values) / len(precision_values) if precision_values else 0.0
    )

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
        retrieval_settings=retrieval_settings if retrieval_settings is not None else {},
        schema_version=BENCHMARK_SCHEMA_VERSION,
    )


def report_to_dict(report: BenchmarkReport) -> dict:  # type: ignore[type-arg]
    return {
        "schema_version": report.schema_version,
        "run_timestamp": report.run_timestamp,
        "corpus_version": report.corpus_version,
        "retrieval_settings": report.retrieval_settings,
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
                "expected_citations": [
                    _citation_to_dict(citation) for citation in r.expected_citations
                ],
                "actual_citations": [
                    _citation_to_dict(citation) for citation in r.actual_citations
                ],
                "answerability_verdict": r.answerability_verdict,
                "trace_id": r.trace_id,
                "query_mode": r.query_mode,
                "candidate_counts": r.candidate_counts,
                "failure_stage": r.failure_stage,
                "synthesis_mode": r.synthesis_mode,
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


def _benchmark_config(config: CosConfig) -> CosConfig:
    return config.model_copy(
        update={
            "embedding": config.embedding.model_copy(
                update={
                    "provider": _BENCHMARK_PROVIDER,
                    "model": _BENCHMARK_MODEL,
                    "api_key": None,
                    "ca_bundle_path": None,
                    "proxy_url": None,
                    "trust_env": False,
                }
            )
        }
    )


def _retrieval_settings_from_config(config: CosConfig) -> dict[str, Any]:
    return {
        "min_score": config.retrieval.min_score,
        "max_chunks_per_source": config.retrieval.max_chunks_per_source,
        "embedding_provider": config.embedding.provider,
        "embedding_model": config.embedding.model,
    }


def _benchmark_source_type(source_type: str) -> str:
    return f"{_BENCHMARK_SOURCE_PREFIX}:{source_type}"


def _benchmark_source_path(doc: FixtureDoc) -> str:
    return (
        f"{_BENCHMARK_SOURCE_PREFIX}://{doc.source_type}/"
        f"{doc.source_locator.replace('://', '/')}"
    )


def _content_sha256(content: str) -> str:
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _make_multi_chunks(
    content: str,
    chunk_count: int,
    benchmark_config: CosConfig,
) -> tuple[list[ChunkRecord], list[EmbeddingRecord]]:
    """Split content into chunk_count roughly equal chunks and embed each."""
    lines = content.splitlines(keepends=True)
    total_lines = len(lines)
    chunk_size = max(1, total_lines // chunk_count)

    chunks: list[ChunkRecord] = []
    embeddings: list[EmbeddingRecord] = []
    for i in range(chunk_count):
        start = i * chunk_size
        end = start + chunk_size if i < chunk_count - 1 else total_lines
        chunk_content = "".join(lines[start:end]).strip()
        if not chunk_content:
            continue
        chunks.append(
            ChunkRecord(
                content=chunk_content,
                chunk_index=i,
                token_count=len(chunk_content.split()),
            )
        )
        result = await embed(
            [chunk_content],
            provider=benchmark_config.embedding.provider,
            model=benchmark_config.embedding.model,
            api_key="",
        )
        embeddings.append(
            EmbeddingRecord(
                vector=result[0].vector,
                model=benchmark_config.embedding.model,
                provider=benchmark_config.embedding.provider,
            )
        )

    if len(chunks) != chunk_count:
        raise CorpusError(
            f"Seeded {len(chunks)} chunks, expected {chunk_count} for benchmark fixture"
        )
    return chunks, embeddings


async def _resolve_seeded_citation(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    source_path: str,
    doc: FixtureDoc,
    *,
    chunk_index: int = 0,
) -> BenchmarkCitation:
    result = await conn.execute(
        """
        SELECT dv.id::text
        FROM documents d
        JOIN document_versions dv
          ON dv.document_id = d.id
         AND dv.version = d.current_version
        WHERE d.source_path = %s
        """,
        (source_path,),
    )
    row = await result.fetchone()
    if row is None:
        raise RuntimeError(
            f"Failed to resolve seeded fixture version for {source_path}"
        )
    return BenchmarkCitation(
        source_alias=doc.source_alias,
        source_locator=doc.source_locator,
        document_version_id=row[0],
        chunk_index=chunk_index,
    )


def _resolve_expected_citations(
    query: BenchmarkQuery,
    seeded_fixtures: dict[str, SeededFixture],
) -> list[BenchmarkCitation]:
    expected_citations: list[BenchmarkCitation] = []
    for locator in query.expected_lineage:
        fixture = seeded_fixtures.get(locator)
        if fixture is None:
            raise CorpusError(
                f"Expected lineage {locator!r} for query {query.id!r} "
                "does not map to a seeded fixture document"
            )
        expected_citations.append(fixture.citation)
    return expected_citations


def _citation_to_dict(citation: BenchmarkCitation) -> dict[str, str | int]:
    return {
        "source_alias": citation.source_alias,
        "source_locator": citation.source_locator,
        "document_version_id": citation.document_version_id,
        "chunk_index": citation.chunk_index,
    }
