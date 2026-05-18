"""Retrieval benchmark corpus models, loading, and scoring rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cos.retrieval.citations import CitedResults

BENCHMARK_SCHEMA_VERSION = "7.2"

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
    expected_citations: list["BenchmarkCitation"] = field(default_factory=list)
    actual_citations: list["BenchmarkCitation"] = field(default_factory=list)
    # Observability fields added in Story 7.2 — all optional with safe defaults
    trace_id: str = ""
    query_mode: str = ""
    candidate_counts: dict[str, Any] = field(default_factory=dict)
    failure_stage: str | None = None
    synthesis_mode: str = "not_run"


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
    # Run-level metadata added in Story 7.2 — all optional with safe defaults
    retrieval_settings: dict[str, Any] = field(default_factory=dict)
    schema_version: str = BENCHMARK_SCHEMA_VERSION


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkCitation:
    source_alias: str
    source_locator: str
    document_version_id: str
    chunk_index: int


def load_queries(
    corpus_path: Path,
    include_stress_fuzz: bool = False,
) -> list[BenchmarkQuery]:
    """Load gold queries and optional stress/fuzz queries from corpus manifests."""
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
    expected_citations: list[BenchmarkCitation] | None = None,
    *,
    trace_id: str = "",
    query_mode: str = "",
    candidate_counts: dict[str, Any] | None = None,
    failure_stage: str | None = None,
    synthesis_mode: str = "not_run",
) -> QueryResult:
    actual_citations = _dedupe_citations(
        [
            BenchmarkCitation(
                source_alias=c.source_alias,
                source_locator=c.source_locator,
                document_version_id=c.document_version_id,
                chunk_index=c.chunk_index,
            )
            for c in citations
        ]
    )
    resolved_expected = (
        list(expected_citations)
        if expected_citations is not None
        else _expected_citations_from_lineage(query.expected_lineage)
    )
    actual_lineage = list(dict.fromkeys(c.source_locator for c in actual_citations))

    if query.answerable:
        has_expected = _has_expected_support(actual_citations, resolved_expected)
        has_only_expected = _only_expected_citations(
            actual_citations, resolved_expected
        )
        passed = has_expected and has_only_expected
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
        expected_citations=resolved_expected,
        actual_citations=actual_citations,
        trace_id=trace_id,
        query_mode=query_mode,
        candidate_counts=candidate_counts if candidate_counts is not None else {},
        failure_stage=failure_stage,
        synthesis_mode=synthesis_mode,
    )


def attribute_failure(
    verdict: str,
    candidate_counts: dict[str, Any],
) -> str | None:
    """Return the retrieval stage most likely responsible for a failed query.

    Returns None when the verdict indicates a pass.  For failures, walks the
    candidate-count chain from the earliest stage inward to identify where
    evidence was lost.
    """
    if verdict in ("correct_answer", "correct_no_answer"):
        return None
    if verdict == "false_answer":
        return "candidate_selection"
    # missed_answer: walk the pipeline stages
    if candidate_counts.get("merged", 0) == 0:
        return "candidate_selection"
    if candidate_counts.get("post_threshold", 0) == 0:
        return "threshold_filtering"
    post_lineage = candidate_counts.get("post_lineage")
    if post_lineage is not None and post_lineage == 0:
        return "lineage_narrowing"
    return "citation_precision"


def _citation_precision_for_result(result: QueryResult) -> float | None:
    actual_citations = _actual_citations_for_result(result)
    expected_citations = _expected_citations_for_result(result)
    if not actual_citations:
        return None
    hits = sum(
        1
        for actual in actual_citations
        if any(_citation_matches(actual, expected) for expected in expected_citations)
    )
    return hits / len(actual_citations)


def _recall_for_result(result: QueryResult) -> bool:
    return _has_expected_support(
        _actual_citations_for_result(result),
        _expected_citations_for_result(result),
    )


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
            sum(1 for r in answerable if _recall_for_result(r)) / len(answerable)
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
    """Derive a short version tag from corpus file paths and contents."""
    manifest_files = sorted(
        p for p in corpus_path.rglob("*") if p.is_file() and "__pycache__" not in str(p)
    )
    h = hashlib.sha256()
    for p in manifest_files:
        h.update(str(p.relative_to(corpus_path)).encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:12]


def _expected_citations_from_lineage(
    expected_lineage: list[str],
) -> list[BenchmarkCitation]:
    return [
        BenchmarkCitation(
            source_alias="",
            source_locator=locator,
            document_version_id="",
            chunk_index=-1,
        )
        for locator in expected_lineage
    ]


def _actual_citations_from_lineage(
    actual_lineage: list[str],
) -> list[BenchmarkCitation]:
    return [
        BenchmarkCitation(
            source_alias="",
            source_locator=locator,
            document_version_id="",
            chunk_index=-1,
        )
        for locator in actual_lineage
    ]


def _expected_citations_for_result(result: QueryResult) -> list[BenchmarkCitation]:
    if result.expected_citations:
        return result.expected_citations
    return _expected_citations_from_lineage(result.expected_lineage)


def _actual_citations_for_result(result: QueryResult) -> list[BenchmarkCitation]:
    if result.actual_citations:
        return result.actual_citations
    return _actual_citations_from_lineage(result.actual_lineage)


def _dedupe_citations(citations: list[BenchmarkCitation]) -> list[BenchmarkCitation]:
    return list(dict.fromkeys(citations))


def _has_expected_support(
    actual_citations: list[BenchmarkCitation],
    expected_citations: list[BenchmarkCitation],
) -> bool:
    return any(
        any(_citation_matches(actual, expected) for expected in expected_citations)
        for actual in actual_citations
    )


def _only_expected_citations(
    actual_citations: list[BenchmarkCitation],
    expected_citations: list[BenchmarkCitation],
) -> bool:
    return all(
        any(_citation_matches(actual, expected) for expected in expected_citations)
        for actual in actual_citations
    )


def _citation_matches(actual: BenchmarkCitation, expected: BenchmarkCitation) -> bool:
    if actual.source_locator != expected.source_locator:
        return False
    if expected.source_alias and actual.source_alias != expected.source_alias:
        return False
    if (
        expected.document_version_id
        and actual.document_version_id != expected.document_version_id
    ):
        return False
    if expected.chunk_index >= 0 and actual.chunk_index != expected.chunk_index:
        return False
    return True


def citation_precision_for_result(result: QueryResult) -> float | None:
    return _citation_precision_for_result(result)


def recall_satisfied(result: QueryResult) -> bool:
    return _recall_for_result(result)
