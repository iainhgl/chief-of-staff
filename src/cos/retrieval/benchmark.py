"""Retrieval benchmark corpus models, loading, and scoring rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from cos.retrieval.citations import CitedResults

VALID_QUERY_CLASSES = frozenset(
    {
        "direct_fact",
        "exact_phrase",
        "date_timeline",
        "single_doc_interpretation",
        "cross_doc_synthesis",
        "briefing",
        "no_answer",
    }
)

# Query classes where lineage is narrowed to the best-ranked source (Story 6.14).
SINGLE_LINEAGE_CLASSES = frozenset(
    {
        "direct_fact",
        "exact_phrase",
        "date_timeline",
        "single_doc_interpretation",
    }
)


@dataclass
class BenchmarkQuery:
    id: str
    query: str
    query_class: str
    answerable: bool
    expected_lineage: list[str]
    notes: str = ""


@dataclass
class FixtureDoc:
    filename: str
    source_locator: str
    source_alias: str
    source_type: str


@dataclass
class QueryResult:
    query_id: str
    query_class: str
    passed: bool
    latency_ms: float
    expected_lineage: list[str]
    actual_lineage: list[str]
    # "correct_answer" | "missed_answer" | "correct_no_answer" | "false_answer"
    answerability_verdict: str


@dataclass
class ClassSummary:
    query_class: str
    total: int
    passed: int
    recall: float
    citation_precision: float
    avg_latency_ms: float


@dataclass
class BenchmarkReport:
    run_timestamp: str
    corpus_version: str
    per_query: list[QueryResult]
    per_class: list[ClassSummary]
    overall_recall: float
    overall_citation_precision: float
    overall_pass_rate: float
    total_queries: int
    passed_queries: int
    avg_latency_ms: float


class CorpusError(ValueError):
    pass


def load_queries(
    corpus_path: Path,
    include_stress_fuzz: bool = False,
) -> list[BenchmarkQuery]:
    """Load and validate benchmark queries from gold (and optionally stress_fuzz) manifests."""
    gold_dir = corpus_path / "gold"
    if not gold_dir.is_dir():
        raise CorpusError(f"Gold benchmark directory not found: {gold_dir}")

    manifest_files = sorted(gold_dir.glob("*.yaml"))
    if not manifest_files:
        raise CorpusError(f"No YAML manifests found in {gold_dir}")

    if include_stress_fuzz:
        fuzz_dir = corpus_path / "stress_fuzz"
        if fuzz_dir.is_dir():
            manifest_files = manifest_files + sorted(fuzz_dir.glob("*.yaml"))

    queries: list[BenchmarkQuery] = []
    seen_ids: set[str] = set()
    for manifest_path in manifest_files:
        queries.extend(_load_manifest(manifest_path, seen_ids))
    return queries


def load_fixture_docs(corpus_path: Path) -> list[FixtureDoc]:
    """Load fixture document metadata from generated/manifest.yaml."""
    manifest_path = corpus_path / "generated" / "manifest.yaml"
    if not manifest_path.exists():
        raise CorpusError(f"Generated manifest not found: {manifest_path}")

    with manifest_path.open() as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "documents" not in data:
        raise CorpusError("generated/manifest.yaml must have a 'documents' list")

    docs = []
    for item in data["documents"]:
        if not isinstance(item, dict):
            raise CorpusError(f"Document entry must be a dict: {item!r}")
        for key in ("filename", "source_locator", "source_alias", "source_type"):
            if key not in item:
                raise CorpusError(f"Document entry missing '{key}': {item!r}")
        docs.append(
            FixtureDoc(
                filename=item["filename"],
                source_locator=item["source_locator"],
                source_alias=item["source_alias"],
                source_type=item["source_type"],
            )
        )
    return docs


def _load_manifest(path: Path, seen_ids: set[str]) -> list[BenchmarkQuery]:
    with path.open() as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict) or "queries" not in data:
        raise CorpusError(f"Manifest must have a 'queries' list: {path}")

    queries = []
    for item in data["queries"]:
        if not isinstance(item, dict):
            raise CorpusError(f"Query entry must be a dict in {path}: {item!r}")
        for key in ("id", "query", "query_class", "answerable", "expected_lineage"):
            if key not in item:
                raise CorpusError(f"Query entry missing '{key}' in {path}: {item!r}")

        qid = item["id"]
        if not isinstance(qid, str) or not qid:
            raise CorpusError(f"Query id must be a non-empty string in {path}")
        if qid in seen_ids:
            raise CorpusError(f"Duplicate query id '{qid}' in {path}")
        seen_ids.add(qid)

        qclass = item["query_class"]
        if qclass not in VALID_QUERY_CLASSES:
            raise CorpusError(
                f"Unknown query_class '{qclass}' in {path}. "
                f"Valid classes: {sorted(VALID_QUERY_CLASSES)}"
            )

        answerable = item["answerable"]
        if not isinstance(answerable, bool):
            raise CorpusError(
                f"'answerable' must be a bool in {path} for query {qid!r}"
            )

        expected = item["expected_lineage"]
        if not isinstance(expected, list):
            raise CorpusError(
                f"'expected_lineage' must be a list in {path} for query {qid!r}"
            )

        if answerable and not expected:
            raise CorpusError(
                f"Query {qid!r} is answerable but has no expected_lineage in {path}"
            )

        queries.append(
            BenchmarkQuery(
                id=qid,
                query=item["query"],
                query_class=qclass,
                answerable=answerable,
                expected_lineage=list(expected),
                notes=item.get("notes", "") or "",
            )
        )
    return queries


def score_query(
    query: BenchmarkQuery,
    citations: CitedResults,
    latency_ms: float,
) -> QueryResult:
    actual_lineage = list(dict.fromkeys(c.source_locator for c in citations))

    if query.answerable:
        expected_set = set(query.expected_lineage)
        has_expected = any(loc in expected_set for loc in actual_lineage)
        passed = has_expected
        verdict = "correct_answer" if passed else "missed_answer"
    else:
        passed = len(citations) == 0
        verdict = "correct_no_answer" if passed else "false_answer"

    return QueryResult(
        query_id=query.id,
        query_class=query.query_class,
        passed=passed,
        latency_ms=latency_ms,
        expected_lineage=list(query.expected_lineage),
        actual_lineage=actual_lineage,
        answerability_verdict=verdict,
    )


def _citation_precision_for_result(result: QueryResult) -> float | None:
    if not result.actual_lineage:
        return None
    expected_set = set(result.expected_lineage)
    hits = sum(1 for loc in result.actual_lineage if loc in expected_set)
    return hits / len(result.actual_lineage)


def aggregate_by_class(results: list[QueryResult]) -> list[ClassSummary]:
    by_class: dict[str, list[QueryResult]] = {}
    for r in results:
        by_class.setdefault(r.query_class, []).append(r)

    summaries = []
    for cls in sorted(by_class):
        class_results = by_class[cls]
        passed = sum(1 for r in class_results if r.passed)
        total = len(class_results)

        answerable = [
            r
            for r in class_results
            if r.answerability_verdict not in ("correct_no_answer", "false_answer")
        ]
        recall = (
            sum(1 for r in answerable if r.passed) / len(answerable)
            if answerable
            else 0.0
        )

        precision_values = [
            p
            for r in class_results
            if (p := _citation_precision_for_result(r)) is not None
        ]
        citation_precision = (
            sum(precision_values) / len(precision_values) if precision_values else 0.0
        )

        avg_latency = sum(r.latency_ms for r in class_results) / total

        summaries.append(
            ClassSummary(
                query_class=cls,
                total=total,
                passed=passed,
                recall=recall,
                citation_precision=citation_precision,
                avg_latency_ms=avg_latency,
            )
        )
    return summaries


def resolve_corpus_version(corpus_path: Path) -> str:
    """Derive a short version tag from the set of manifest files in the corpus."""
    manifest_files = sorted(
        p
        for p in corpus_path.rglob("*.yaml")
        if "__pycache__" not in str(p)
    )
    h = hashlib.sha256()
    for p in manifest_files:
        h.update(p.name.encode())
        h.update(str(p.stat().st_mtime).encode())
    return h.hexdigest()[:12]
