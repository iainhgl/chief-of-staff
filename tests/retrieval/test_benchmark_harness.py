"""DB-backed tests for the retrieval benchmark harness."""

from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.retrieval.benchmark import (
    SINGLE_LINEAGE_CLASSES,
    VALID_QUERY_CLASSES,
    BenchmarkCitation,
    BenchmarkQuery,
    CorpusError,
    QueryResult,
    aggregate_by_class,
    attribute_failure,
    load_fixture_docs,
    load_queries,
    resolve_corpus_version,
    score_query,
)
from cos.retrieval.citations import CitedChunk
from cos.retrieval.search import hybrid_search
from cos.store.db import store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord

_CORPUS_PATH = Path(__file__).parents[1] / "fixtures" / "retrieval_eval"
_FIXED_VECTOR = [float(i) / 100 for i in range(1024)]
_FAKE_SHA = "deadbeef" * 8


def _make_chunk(
    source_locator: str,
    source_alias: str,
    score: float = 0.9,
    content: str = "sample content",
    chunk_index: int = 0,
) -> CitedChunk:
    return CitedChunk(
        content=content,
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_alias,
        source_locator=source_locator,
        document_version_id="",
        chunk_index=chunk_index,
        score=score,
    )


# ── Corpus loading tests ─────────────────────────────────────────────────────


def test_load_queries_returns_all_gold_cases() -> None:
    queries = load_queries(_CORPUS_PATH)
    ids = {q.id for q in queries}
    # gold/core-queries.yaml must be loaded
    assert "gold-df-001" in ids
    assert "gold-ep-001" in ids
    assert "gold-dt-001" in ids
    assert "gold-sdi-001" in ids
    assert "gold-cds-001" in ids
    assert "gold-br-001" in ids
    assert "gold-na-001" in ids


def test_load_queries_with_stress_fuzz_includes_fuzz_cases() -> None:
    queries = load_queries(_CORPUS_PATH, include_stress_fuzz=True)
    ids = {q.id for q in queries}
    assert "fuzz-df-001" in ids
    assert "fuzz-na-001" in ids


def test_load_queries_without_stress_fuzz_excludes_fuzz() -> None:
    queries = load_queries(_CORPUS_PATH, include_stress_fuzz=False)
    ids = {q.id for q in queries}
    assert "fuzz-df-001" not in ids


def test_load_queries_all_have_valid_query_class() -> None:
    queries = load_queries(_CORPUS_PATH, include_stress_fuzz=True)
    for q in queries:
        assert q.query_class in VALID_QUERY_CLASSES, (
            f"{q.id} has invalid class {q.query_class!r}"
        )


def test_load_queries_answerable_cases_have_expected_lineage() -> None:
    queries = load_queries(_CORPUS_PATH, include_stress_fuzz=True)
    for q in queries:
        if q.answerable:
            assert q.expected_lineage, (
                f"{q.id} is answerable but has no expected_lineage"
            )


def test_load_queries_no_answer_cases_have_empty_lineage() -> None:
    queries = load_queries(_CORPUS_PATH, include_stress_fuzz=True)
    for q in queries:
        if not q.answerable:
            assert q.expected_lineage == [], (
                f"{q.id} is not answerable but has expected_lineage "
                f"{q.expected_lineage!r}"
            )


def test_load_fixture_docs_returns_five_docs() -> None:
    docs = load_fixture_docs(_CORPUS_PATH)
    assert len(docs) == 5
    locators = {d.source_locator for d in docs}
    assert "local://local-leave-policy" in locators
    assert "gmail://msg-leave-policy-001" in locators
    assert "calendar://event-q1-review-001" in locators
    assert "mcp://note-retention-q4-2024" in locators
    assert "local://local-succession-plan" in locators


def test_corpus_schema_malformed_manifest_raises_corpus_error(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    bad_manifest = gold_dir / "bad.yaml"
    bad_manifest.write_text("not_a_dict: true\n")
    with pytest.raises(CorpusError, match="queries"):
        load_queries(tmp_path)


def test_corpus_schema_unknown_query_class_raises_corpus_error(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    bad_manifest = gold_dir / "bad.yaml"
    bad_manifest.write_text(
        "queries:\n"
        "  - id: q1\n"
        "    query: test\n"
        "    query_class: invalid_class\n"
        "    answerable: true\n"
        "    expected_lineage:\n"
        "      - loc://a\n"
    )
    with pytest.raises(CorpusError, match="query_class"):
        load_queries(tmp_path)


def test_corpus_schema_missing_expected_lineage_for_answerable_raises(
    tmp_path: Path,
) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    bad_manifest = gold_dir / "bad.yaml"
    bad_manifest.write_text(
        "queries:\n"
        "  - id: q1\n"
        "    query: test\n"
        "    query_class: direct_fact\n"
        "    answerable: true\n"
        "    expected_lineage: []\n"
    )
    with pytest.raises(CorpusError, match="answerable but has no expected_lineage"):
        load_queries(tmp_path)


def test_corpus_schema_duplicate_id_raises_corpus_error(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    manifest = gold_dir / "dup.yaml"
    manifest.write_text(
        "queries:\n"
        "  - id: q1\n"
        "    query: first\n"
        "    query_class: direct_fact\n"
        "    answerable: true\n"
        "    expected_lineage: [loc://a]\n"
        "  - id: q1\n"
        "    query: second\n"
        "    query_class: direct_fact\n"
        "    answerable: true\n"
        "    expected_lineage: [loc://a]\n"
    )
    with pytest.raises(CorpusError, match="Duplicate query id"):
        load_queries(tmp_path)


def test_fixture_manifest_missing_field_raises_corpus_error(tmp_path: Path) -> None:
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    (gen_dir / "manifest.yaml").write_text(
        "documents:\n  - filename: foo.md\n    source_locator: loc://foo\n"
    )
    with pytest.raises(CorpusError, match="missing"):
        load_fixture_docs(tmp_path)


# ── Scoring unit tests ───────────────────────────────────────────────────────


def test_score_query_answerable_correct_returns_passed() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://a"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(query, [chunk], latency_ms=50.0)
    assert result.passed
    assert result.answerability_verdict == "correct_answer"
    assert result.actual_lineage == ["loc://a"]


def test_score_query_answerable_wrong_lineage_returns_missed() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://expected"],
    )
    chunk = _make_chunk("loc://other", "loc://other")
    result = score_query(query, [chunk], latency_ms=50.0)
    assert not result.passed
    assert result.answerability_verdict == "missed_answer"


def test_score_query_no_answer_empty_citations_returns_correct() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="pension rate",
        query_class="no_answer",
        answerable=False,
        expected_lineage=[],
    )
    result = score_query(query, [], latency_ms=10.0)
    assert result.passed
    assert result.answerability_verdict == "correct_no_answer"


def test_score_query_no_answer_with_citations_returns_false_answer() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="pension rate",
        query_class="no_answer",
        answerable=False,
        expected_lineage=[],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(query, [chunk], latency_ms=10.0)
    assert not result.passed
    assert result.answerability_verdict == "false_answer"


def test_score_query_cross_doc_synthesis_any_expected_lineage_passes() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="compare email vs file",
        query_class="cross_doc_synthesis",
        answerable=True,
        expected_lineage=["loc://a", "loc://b"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(query, [chunk], latency_ms=30.0)
    assert result.passed


def test_score_query_fails_when_unexpected_citation_is_present() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="compare email vs file",
        query_class="cross_doc_synthesis",
        answerable=True,
        expected_lineage=["loc://a", "loc://b"],
    )
    result = score_query(
        query,
        [_make_chunk("loc://a", "loc://a"), _make_chunk("loc://unexpected", "loc://unexpected")],
        latency_ms=30.0,
    )
    assert not result.passed


def test_score_query_latency_captured() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://a"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(query, [chunk], latency_ms=123.0)
    assert result.latency_ms == pytest.approx(123.0)


# ── Aggregation tests ─────────────────────────────────────────────────────────


def test_aggregate_by_class_correct_recall() -> None:
    results = [
        QueryResult(
            query_id="q1",
            query_class="direct_fact",
            passed=True,
            latency_ms=10.0,
            expected_lineage=["loc://a"],
            actual_lineage=["loc://a"],
            answerability_verdict="correct_answer",
        ),
        QueryResult(
            query_id="q2",
            query_class="direct_fact",
            passed=False,
            latency_ms=20.0,
            expected_lineage=["loc://b"],
            actual_lineage=["loc://c"],
            answerability_verdict="missed_answer",
        ),
    ]
    summaries = aggregate_by_class(results)
    assert len(summaries) == 1
    s = summaries[0]
    assert s.query_class == "direct_fact"
    assert s.total == 2
    assert s.passed == 1
    assert s.recall == pytest.approx(0.5)


def test_aggregate_by_class_precision_correct() -> None:
    results = [
        QueryResult(
            query_id="q1",
            query_class="briefing",
            passed=True,
            latency_ms=10.0,
            expected_lineage=["loc://a", "loc://b"],
            actual_lineage=["loc://a", "loc://c"],  # one hit, one miss → 0.5
            answerability_verdict="correct_answer",
        ),
    ]
    summaries = aggregate_by_class(results)
    assert summaries[0].citation_precision == pytest.approx(0.5)


def test_aggregate_by_class_uses_full_citation_contract_when_available() -> None:
    results = [
        QueryResult(
            query_id="q1",
            query_class="direct_fact",
            passed=False,
            latency_ms=10.0,
            expected_lineage=["loc://a"],
            actual_lineage=["loc://a"],
            answerability_verdict="missed_answer",
            expected_citations=[
                BenchmarkCitation("alias", "loc://a", "version-1", 0),
            ],
            actual_citations=[
                BenchmarkCitation("alias", "loc://a", "version-2", 0),
            ],
        ),
    ]
    summaries = aggregate_by_class(results)
    assert summaries[0].citation_precision == pytest.approx(0.0)


def test_aggregate_by_class_no_answer_excluded_from_recall() -> None:
    results = [
        QueryResult(
            query_id="q1",
            query_class="no_answer",
            passed=True,
            latency_ms=5.0,
            expected_lineage=[],
            actual_lineage=[],
            answerability_verdict="correct_no_answer",
        ),
    ]
    summaries = aggregate_by_class(results)
    assert summaries[0].recall == pytest.approx(0.0)  # no answerable queries


def test_aggregate_by_class_avg_latency() -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            100.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        ),
        QueryResult(
            "q2",
            "direct_fact",
            True,
            200.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        ),
    ]
    summaries = aggregate_by_class(results)
    assert summaries[0].avg_latency_ms == pytest.approx(150.0)


def test_aggregate_by_class_multiple_classes() -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            10.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        ),
        QueryResult(
            "q2",
            "briefing",
            True,
            20.0,
            ["loc://b"],
            ["loc://b"],
            "correct_answer",
        ),
        QueryResult("q3", "no_answer", True, 5.0, [], [], "correct_no_answer"),
    ]
    summaries = aggregate_by_class(results)
    classes = {s.query_class for s in summaries}
    assert classes == {"direct_fact", "briefing", "no_answer"}


def test_resolve_corpus_version_returns_12_char_hex() -> None:
    version = resolve_corpus_version(_CORPUS_PATH)
    assert len(version) == 12
    int(version, 16)  # must be valid hex


def test_resolve_corpus_version_ignores_mtime_only_changes(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    gold = corpus / "gold"
    gold.mkdir(parents=True)
    manifest = gold / "queries.yaml"
    manifest.write_text("queries: []\n")
    first = resolve_corpus_version(corpus)
    manifest.touch()
    second = resolve_corpus_version(corpus)
    assert first == second


def test_resolve_corpus_version_changes_when_file_content_changes(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    gold = corpus / "gold"
    gold.mkdir(parents=True)
    manifest = gold / "queries.yaml"
    manifest.write_text("queries: []\n")
    first = resolve_corpus_version(corpus)
    manifest.write_text("queries:\n  - id: q1\n")
    second = resolve_corpus_version(corpus)
    assert first != second


def test_single_lineage_classes_correct() -> None:
    assert "direct_fact" in SINGLE_LINEAGE_CLASSES
    assert "exact_phrase" in SINGLE_LINEAGE_CLASSES
    assert "date_timeline" in SINGLE_LINEAGE_CLASSES
    assert "single_doc_interpretation" in SINGLE_LINEAGE_CLASSES
    assert "cross_doc_synthesis" not in SINGLE_LINEAGE_CLASSES
    assert "briefing" not in SINGLE_LINEAGE_CLASSES
    assert "no_answer" not in SINGLE_LINEAGE_CLASSES


# ── DB-backed retrieval benchmark tests ──────────────────────────────────────


async def _store_eval_doc(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    content: str,
    source_locator: str,
    source_alias: str,
    source_type: str,
    sha: str,
) -> None:
    await store_document_canonical(
        conn,
        source_path=source_locator,
        sha256=sha,
        byte_size=len(content.encode()),
        source_type=source_type,
        source_locator=source_locator,
        source_alias=source_alias,
        chunks=[
            ChunkRecord(
                content=content,
                chunk_index=0,
                token_count=len(content.split()),
            )
        ],
        embeddings=[
            EmbeddingRecord(
                vector=_FIXED_VECTOR,
                model="voyage-3",
                provider="anthropic",
            )
        ],
    )


@pytest.mark.asyncio
async def test_db_direct_fact_keyword_match_returns_expected_lineage(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    """Verifies that store_document_canonical + hybrid_search works end-to-end.

    Uses a short keyword-only query to avoid tsquery stop-word surprises.
    Combined keyword+semantic RRF ≈ 0.033 > min_score 0.02 → result returned.
    """
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    config.retrieval.min_score = 0.02

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_eval_doc(
            conn,
            content="Annual leave entitlement is 25 days.",
            source_locator="local://local-leave-policy",
            source_alias="local://local-leave-policy",
            source_type="local",
            sha=_FAKE_SHA,
        )
        results = await hybrid_search(
            "annual leave entitlement days",
            conn,
            config,
            min_score=config.retrieval.min_score,
        )

    assert len(results) >= 1
    locators = {c.source_locator for c in results}
    assert "local://local-leave-policy" in locators


@pytest.mark.asyncio
async def test_db_no_answer_query_returns_empty_with_threshold(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    """Verifies that a query with no keyword match is filtered by min_score.

    mock_embed returns a uniform vector so semantic-only RRF ≈ 0.016 < 0.02 → empty.
    """
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    config.retrieval.min_score = 0.02

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_eval_doc(
            conn,
            content="Annual leave entitlement is 25 days.",
            source_locator="local://local-leave-policy",
            source_alias="local://local-leave-policy",
            source_type="local",
            sha=_FAKE_SHA,
        )
        results = await hybrid_search(
            "pension contribution",  # no keyword overlap with stored content
            conn,
            config,
            min_score=config.retrieval.min_score,
        )

    # No keyword match + uniform semantic vector → score ≈ 0.016 < 0.02 → empty
    assert results == []


@pytest.mark.asyncio
async def test_db_exact_phrase_query_returns_matching_doc(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    config.retrieval.min_score = 0.02

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_eval_doc(
            conn,
            content="The succession process follows a 9-box grid methodology.",
            source_locator="local://local-succession-plan",
            source_alias="local://local-succession-plan",
            source_type="local",
            sha=_FAKE_SHA + "01",
        )
        results = await hybrid_search(
            "9-box grid methodology",
            conn,
            config,
            min_score=config.retrieval.min_score,
        )

    assert len(results) >= 1
    assert results[0].source_locator == "local://local-succession-plan"


@pytest.mark.asyncio
async def test_db_cross_doc_query_returns_results_from_multiple_sources(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    """Verifies cross-document retrieval when two sources share keyword terms."""
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    config.retrieval.min_score = 0.02

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_eval_doc(
            conn,
            content="Leave policy document: annual leave is 25 days.",
            source_locator="local://local-leave-policy",
            source_alias="local://local-leave-policy",
            source_type="local",
            sha=_FAKE_SHA + "02",
        )
        await _store_eval_doc(
            conn,
            content="Leave policy email: annual leave confirmed 25 days.",
            source_locator="gmail://msg-leave-policy-001",
            source_alias="gmail://msg-leave-policy-001",
            source_type="gmail",
            sha=_FAKE_SHA + "03",
        )
        results = await hybrid_search(
            "annual leave policy days",
            conn,
            config,
            min_score=config.retrieval.min_score,
        )

    locators = {c.source_locator for c in results}
    assert len(locators) >= 1


# ── Observability fields on QueryResult (Story 7.2) ──────────────────────────


def test_score_query_stores_trace_id_and_query_mode() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://a"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(
        query,
        [chunk],
        latency_ms=50.0,
        trace_id="trace-xyz",
        query_mode="direct_fact",
        synthesis_mode="not_run",
    )
    assert result.trace_id == "trace-xyz"
    assert result.query_mode == "direct_fact"
    assert result.synthesis_mode == "not_run"


def test_score_query_stores_candidate_counts() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://a"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    counts = {"keyword": 2, "semantic": 3, "merged": 4, "post_threshold": 4}
    result = score_query(query, [chunk], latency_ms=50.0, candidate_counts=counts)
    assert result.candidate_counts == counts


def test_score_query_defaults_preserve_backward_compat() -> None:
    query = BenchmarkQuery(
        id="q1",
        query="test",
        query_class="direct_fact",
        answerable=True,
        expected_lineage=["loc://a"],
    )
    chunk = _make_chunk("loc://a", "loc://a")
    result = score_query(query, [chunk], latency_ms=50.0)
    assert result.trace_id == ""
    assert result.query_mode == ""
    assert result.candidate_counts == {}
    assert result.failure_stage is None
    assert result.synthesis_mode == "not_run"


# ── attribute_failure unit tests ─────────────────────────────────────────────


def test_attribute_failure_correct_answer_returns_none() -> None:
    assert attribute_failure("correct_answer", {}) is None


def test_attribute_failure_correct_no_answer_returns_none() -> None:
    assert attribute_failure("correct_no_answer", {}) is None


def test_attribute_failure_false_answer_returns_candidate_selection() -> None:
    assert attribute_failure("false_answer", {}) == "candidate_selection"


def test_attribute_failure_missed_answer_zero_merged_returns_candidate_selection() -> None:
    counts = {"keyword": 0, "semantic": 0, "merged": 0}
    assert attribute_failure("missed_answer", counts) == "candidate_selection"


def test_attribute_failure_missed_answer_zero_post_threshold_returns_threshold_filtering() -> None:
    counts = {"merged": 5, "post_threshold": 0}
    assert attribute_failure("missed_answer", counts) == "threshold_filtering"


def test_attribute_failure_missed_answer_zero_post_lineage_returns_lineage_narrowing() -> None:
    counts = {"merged": 5, "post_threshold": 3, "post_lineage": 0}
    assert attribute_failure("missed_answer", counts) == "lineage_narrowing"


def test_attribute_failure_missed_answer_with_candidates_returns_citation_precision() -> None:
    counts = {"merged": 5, "post_threshold": 3, "post_lineage": 2}
    assert attribute_failure("missed_answer", counts) == "citation_precision"


def test_attribute_failure_missed_answer_no_post_lineage_key_returns_citation_precision() -> None:
    # post_lineage not present means lineage narrowing stage did not run
    counts = {"merged": 5, "post_threshold": 3}
    assert attribute_failure("missed_answer", counts) == "citation_precision"
