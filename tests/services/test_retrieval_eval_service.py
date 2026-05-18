"""Service-level tests for the retrieval evaluation service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import make_test_config

from cos.retrieval.benchmark import BenchmarkCitation, QueryResult
from cos.retrieval.citations import CitedChunk
from cos.retrieval.telemetry import SearchStats
from cos.services.retrieval_eval import (
    RetrievalEvalService,
    _build_report,
    format_human_summary,
    report_to_dict,
)

_CORPUS_PATH = Path(__file__).parents[1] / "fixtures" / "retrieval_eval"
_SEEDED_CITATION = BenchmarkCitation(
    source_alias="local://local-leave-policy",
    source_locator="local://local-leave-policy",
    document_version_id="seeded-version-1",
    chunk_index=0,
)

_SEARCH_PATCH = "cos.services.retrieval_eval.hybrid_search_with_trace"


def _empty_search(*args, **kwargs):  # type: ignore[no-untyped-def]
    return ([], SearchStats())


def _make_pool(cited_results_by_query: dict) -> MagicMock:
    """Return a mock pool whose hybrid_search side effect uses a query counter."""
    mock_conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = cm
    return pool


def _make_cited_chunk(
    source_locator: str,
    source_alias: str = "",
    document_version_id: str = "seeded-version-1",
) -> CitedChunk:
    return CitedChunk(
        content="fixture content",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_alias or source_locator,
        source_locator=source_locator,
        document_version_id=document_version_id,
        chunk_index=0,
        score=0.9,
    )


def _make_pool_with_connection() -> MagicMock:
    mock_conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = cm
    return pool


def _search_returning(chunks: list[CitedChunk], stats: SearchStats | None = None):  # type: ignore[no-untyped-def]
    async def _fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return chunks, stats or SearchStats(final_candidate_count=len(chunks))
    return _fake


# ── run_benchmark integration (mocked hybrid_search + seeding) ──────────────


@pytest.mark.asyncio
async def test_run_benchmark_loads_and_runs_all_gold_queries(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    call_count = 0

    async def _fake_search(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        return [], SearchStats()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    # Gold corpus has 7 queries (core-queries.yaml)
    assert report.total_queries == 7
    assert call_count == 7


@pytest.mark.asyncio
async def test_run_benchmark_with_fuzz_includes_fuzz_queries(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(
            _SEARCH_PATCH,
            new=AsyncMock(return_value=([], SearchStats())),
        ),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH, include_stress_fuzz=True)

    # Gold (7) + stress_fuzz (5) = 12
    assert report.total_queries == 12


@pytest.mark.asyncio
async def test_run_benchmark_correct_answer_counted_as_passed(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    leave_chunk = _make_cited_chunk("local://local-leave-policy")

    async def _fake_search(query, conn, cfg, **kwargs):  # type: ignore[no-untyped-def]
        if "annual leave" in query.lower() or "leave policy" in query.lower():
            return [leave_chunk], SearchStats(final_candidate_count=1)
        return [], SearchStats()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    per_query_by_id = {r.query_id: r for r in report.per_query}
    df_result = per_query_by_id["gold-df-001"]
    assert df_result.passed
    assert df_result.answerability_verdict == "correct_answer"


@pytest.mark.asyncio
async def test_run_benchmark_no_answer_case_correct_when_empty(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(
            _SEARCH_PATCH,
            new=AsyncMock(return_value=([], SearchStats())),
        ),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    per_query_by_id = {r.query_id: r for r in report.per_query}
    na_result = per_query_by_id["gold-na-001"]
    assert na_result.passed
    assert na_result.answerability_verdict == "correct_no_answer"


@pytest.mark.asyncio
async def test_run_benchmark_single_lineage_class_applies_narrowing(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    chunk_a = _make_cited_chunk(
        "local://local-leave-policy",
        document_version_id="seeded-version-1",
    )
    chunk_b = _make_cited_chunk(
        "gmail://msg-leave-policy-001",
        document_version_id="seeded-version-2",
    )
    chunk_a.score = 0.9

    returned_chunks = [chunk_a, chunk_b]

    async def _fake_search(*args, **kwargs):  # type: ignore[no-untyped-def]
        return list(returned_chunks), SearchStats(final_candidate_count=2)

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    per_query_by_id = {r.query_id: r for r in report.per_query}
    df_result = per_query_by_id["gold-df-001"]
    # direct_fact → narrow_to_lineage → only highest-ranked lineage survives
    assert len(df_result.actual_lineage) == 1
    assert df_result.actual_lineage[0] == "local://local-leave-policy"


@pytest.mark.asyncio
async def test_run_benchmark_cross_doc_class_not_narrowed(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    chunk_a = _make_cited_chunk(
        "local://local-leave-policy",
        document_version_id="seeded-version-1",
    )
    chunk_b = _make_cited_chunk(
        "gmail://msg-leave-policy-001",
        document_version_id="seeded-version-2",
    )

    async def _fake_search(query, conn, cfg, **kwargs):  # type: ignore[no-untyped-def]
        if "compare" in query.lower():
            return [chunk_a, chunk_b], SearchStats(final_candidate_count=2)
        return [], SearchStats()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    per_query_by_id = {r.query_id: r for r in report.per_query}
    cds_result = per_query_by_id["gold-cds-001"]
    # cross_doc_synthesis is NOT narrowed → both lineages must survive
    assert len(cds_result.actual_lineage) == 2


@pytest.mark.asyncio
async def test_run_benchmark_uses_benchmark_provider_and_namespaced_source_identity(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()
    store_document = AsyncMock()
    seeded_citation = AsyncMock(return_value=_SEEDED_CITATION)

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )) as embed_mock,
        patch(
            "cos.services.retrieval_eval.store_document_canonical",
            new=store_document,
        ),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=seeded_citation,
        ),
        patch(
            _SEARCH_PATCH,
            new=AsyncMock(return_value=([], SearchStats())),
        ),
    ):
        service = RetrievalEvalService(config, pool)
        await service.run_benchmark(_CORPUS_PATH)

    assert embed_mock.await_count == 5
    assert all(
        call.kwargs["provider"] == "benchmark"
        for call in embed_mock.await_args_list
    )
    first_call = store_document.await_args_list[0]
    assert first_call.kwargs["source_type"].startswith("benchmark:")
    assert first_call.kwargs["source_path"].startswith("benchmark://")


@pytest.mark.asyncio
async def test_run_benchmark_cleans_up_when_query_execution_fails(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(
            _SEARCH_PATCH,
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        service = RetrievalEvalService(config, pool)
        cleanup = AsyncMock()
        service._cleanup_fixtures = cleanup  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="boom"):
            await service.run_benchmark(_CORPUS_PATH)

    cleanup.assert_awaited_once()


# ── Benchmark metadata tests (Story 7.2) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_benchmark_query_result_has_trace_id_and_query_mode(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], SearchStats()))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    for result in report.per_query:
        assert result.trace_id, f"query {result.query_id} missing trace_id"
        assert result.query_mode, f"query {result.query_id} missing query_mode"
        assert result.synthesis_mode == "not_run"


@pytest.mark.asyncio
async def test_run_benchmark_query_result_has_candidate_counts(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()
    stats = SearchStats(
        keyword_candidate_count=2,
        semantic_candidate_count=3,
        merged_candidate_count=4,
        post_threshold_count=4,
        post_pruning_count=2,
        final_candidate_count=0,
    )

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], stats))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    result = report.per_query[0]
    counts = result.candidate_counts
    assert counts["keyword"] == 2
    assert counts["semantic"] == 3
    assert counts["merged"] == 4
    assert counts["post_threshold"] == 4
    assert counts["post_pruning"] == 2
    assert counts["final"] == 0


@pytest.mark.asyncio
async def test_run_benchmark_failed_query_has_failure_stage(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    # Empty results — answerable query will fail at candidate_selection stage
    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], SearchStats()))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    # All answerable queries fail with no candidates → candidate_selection
    for result in report.per_query:
        if result.answerability_verdict == "missed_answer":
            assert result.failure_stage == "candidate_selection", (
                f"query {result.query_id}: expected candidate_selection, "
                f"got {result.failure_stage}"
            )


@pytest.mark.asyncio
async def test_run_benchmark_pruning_loss_is_attributed_to_pruning(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()
    stats = SearchStats(
        keyword_candidate_count=3,
        semantic_candidate_count=2,
        merged_candidate_count=4,
        post_threshold_count=2,
        post_pruning_count=0,
        final_candidate_count=0,
    )

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], stats))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    for result in report.per_query:
        if result.answerability_verdict == "missed_answer":
            assert result.failure_stage == "pruning"


@pytest.mark.asyncio
async def test_run_benchmark_lineage_loss_is_attributed_to_lineage_narrowing(
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()
    wrong_lineage = _make_cited_chunk(
        "gmail://msg-leave-policy-001",
        document_version_id="gmail-version-1",
    )
    expected_lineage = _make_cited_chunk("local://local-leave-policy")
    stats = SearchStats(
        keyword_candidate_count=2,
        semantic_candidate_count=2,
        merged_candidate_count=2,
        post_threshold_count=2,
        post_pruning_count=2,
        final_candidate_count=2,
    )

    async def _fake_search(query, conn, cfg, **kwargs):  # type: ignore[no-untyped-def]
        if "annual leave" in query.lower():
            return [wrong_lineage, expected_lineage], stats
        return [], SearchStats()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    result = {r.query_id: r for r in report.per_query}["gold-df-001"]
    assert not result.passed
    assert result.answerability_verdict == "missed_answer"
    assert result.failure_stage == "lineage_narrowing"


@pytest.mark.asyncio
async def test_run_benchmark_passing_query_has_no_failure_stage(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    leave_chunk = _make_cited_chunk("local://local-leave-policy")

    async def _fake_search(query, conn, cfg, **kwargs):  # type: ignore[no-untyped-def]
        if "annual leave" in query.lower() or "leave policy" in query.lower():
            return [leave_chunk], SearchStats(final_candidate_count=1)
        return [], SearchStats()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=_fake_search),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    per_query_by_id = {r.query_id: r for r in report.per_query}
    df_result = per_query_by_id["gold-df-001"]
    assert df_result.passed
    assert df_result.failure_stage is None


@pytest.mark.asyncio
async def test_run_benchmark_report_has_retrieval_settings(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], SearchStats()))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    assert "min_score" in report.retrieval_settings
    assert "max_chunks_per_source" in report.retrieval_settings
    assert "embedding_provider" in report.retrieval_settings
    assert "embedding_model" in report.retrieval_settings


@pytest.mark.asyncio
async def test_run_benchmark_report_has_schema_version(tmp_path: Path) -> None:
    config = make_test_config(tmp_path)
    pool = _make_pool_with_connection()

    with (
        patch("cos.services.retrieval_eval.embed", new=AsyncMock(
            return_value=[MagicMock(vector=[0.1] * 1024)]
        )),
        patch("cos.services.retrieval_eval.store_document_canonical", new=AsyncMock()),
        patch(
            "cos.services.retrieval_eval._resolve_seeded_citation",
            new=AsyncMock(return_value=_SEEDED_CITATION),
        ),
        patch(_SEARCH_PATCH, new=AsyncMock(return_value=([], SearchStats()))),
    ):
        service = RetrievalEvalService(config, pool)
        report = await service.run_benchmark(_CORPUS_PATH)

    assert report.schema_version == "7.2"


# ── Report building and serialisation ────────────────────────────────────────


def test_report_to_dict_contains_required_top_level_keys(tmp_path: Path) -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            50.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report(
        "2026-01-01T00:00:00+00:00",
        "abc123def456",
        results,
        per_class,
    )
    d = report_to_dict(report)

    assert "run_timestamp" in d
    assert "corpus_version" in d
    assert "summary" in d
    assert "per_class" in d
    assert "per_query" in d


def test_report_to_dict_contains_new_top_level_keys(tmp_path: Path) -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            50.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report(
        "2026-01-01T00:00:00+00:00",
        "abc123def456",
        results,
        per_class,
        retrieval_settings={"min_score": 0.0},
    )
    d = report_to_dict(report)

    assert "schema_version" in d
    assert d["schema_version"] == "7.2"
    assert "retrieval_settings" in d
    assert d["retrieval_settings"]["min_score"] == 0.0


def test_report_summary_fields_present(tmp_path: Path) -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            50.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report(
        "2026-01-01T00:00:00+00:00",
        "abc123def456",
        results,
        per_class,
    )
    d = report_to_dict(report)
    summary = d["summary"]

    assert "total_queries" in summary
    assert "passed_queries" in summary
    assert "overall_pass_rate" in summary
    assert "overall_recall" in summary
    assert "overall_citation_precision" in summary
    assert "avg_latency_ms" in summary


def test_report_per_query_has_required_fields() -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            42.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report("2026-01-01T00:00:00+00:00", "ver", results, per_class)
    d = report_to_dict(report)

    pq = d["per_query"][0]
    assert pq["query_id"] == "q1"
    assert "query_class" in pq
    assert "pass" in pq
    assert "latency_ms" in pq
    assert "expected_lineage" in pq
    assert "actual_lineage" in pq
    assert "expected_citations" in pq
    assert "actual_citations" in pq
    assert "answerability_verdict" in pq


def test_report_per_query_has_new_observability_fields() -> None:
    result = QueryResult(
        "q1",
        "direct_fact",
        False,
        42.0,
        ["loc://a"],
        [],
        "missed_answer",
        trace_id="trace-abc",
        query_mode="direct_fact",
        candidate_counts={"merged": 0, "final": 0},
        failure_stage="candidate_selection",
        synthesis_mode="not_run",
    )
    per_class = aggregate_by_class_simple([result])
    report = _build_report("ts", "ver", [result], per_class)
    d = report_to_dict(report)

    pq = d["per_query"][0]
    assert pq["trace_id"] == "trace-abc"
    assert pq["query_mode"] == "direct_fact"
    assert pq["candidate_counts"] == {"merged": 0, "final": 0}
    assert pq["failure_stage"] == "candidate_selection"
    assert pq["synthesis_mode"] == "not_run"


def test_report_per_class_has_required_fields() -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            42.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report("2026-01-01T00:00:00+00:00", "ver", results, per_class)
    d = report_to_dict(report)

    pc = d["per_class"][0]
    assert "query_class" in pc
    assert "total" in pc
    assert "passed" in pc
    assert "recall" in pc
    assert "citation_precision" in pc
    assert "avg_latency_ms" in pc


def test_format_human_summary_contains_pass_rate() -> None:
    results = [
        QueryResult(
            "q1",
            "direct_fact",
            True,
            50.0,
            ["loc://a"],
            ["loc://a"],
            "correct_answer",
        )
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report(
        "2026-01-01T00:00:00+00:00",
        "abc123def456",
        results,
        per_class,
    )
    summary = format_human_summary(report)

    assert "1/1" in summary
    assert "direct_fact" in summary


def test_build_report_overall_recall_correct() -> None:
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
            "direct_fact",
            False,
            10.0,
            ["loc://b"],
            ["loc://c"],
            "missed_answer",
        ),
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report("ts", "ver", results, per_class)
    assert report.overall_recall == pytest.approx(0.5)


def test_build_report_no_answer_excluded_from_recall() -> None:
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
        QueryResult("q2", "no_answer", True, 5.0, [], [], "correct_no_answer"),
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report("ts", "ver", results, per_class)
    # Recall is computed over answerable queries only
    assert report.overall_recall == pytest.approx(1.0)


def test_build_report_overall_citation_precision() -> None:
    results = [
        QueryResult(
            "q1", "direct_fact", True, 10.0,
            ["loc://a"],
            ["loc://a", "loc://b"],  # one in expected, one not → precision 0.5
            "correct_answer",
        ),
    ]
    per_class = aggregate_by_class_simple(results)
    report = _build_report("ts", "ver", results, per_class)
    assert report.overall_citation_precision == pytest.approx(0.5)


def test_report_is_comparable_across_runs_via_corpus_version() -> None:
    """Two reports with same corpus_version are comparable by design."""
    results = [
        QueryResult("q1", "direct_fact", True, 50.0, ["loc://a"], ["loc://a"], "correct_answer")
    ]
    per_class = aggregate_by_class_simple(results)
    report_a = _build_report("ts-a", "shared-corpus-v1", results, per_class)
    report_b = _build_report("ts-b", "shared-corpus-v1", results, per_class)

    d_a = report_to_dict(report_a)
    d_b = report_to_dict(report_b)

    assert d_a["corpus_version"] == d_b["corpus_version"]
    assert d_a["schema_version"] == d_b["schema_version"]


# ── Helper ───────────────────────────────────────────────────────────────────


def aggregate_by_class_simple(results):  # type: ignore[no-untyped-def]
    from cos.retrieval.benchmark import aggregate_by_class
    return aggregate_by_class(results)
