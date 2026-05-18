import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import make_test_config

from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.retrieval.telemetry import SearchStats
from cos.services.retrieval import RetrievalService

_PATCH = "cos.services.retrieval.hybrid_search_with_trace"


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield


@pytest.fixture
def mock_pool() -> MagicMock:
    mock_conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = cm
    return pool


@pytest.fixture
def mock_llm_adapter() -> AsyncMock:
    adapter = AsyncMock(spec=LLMAdapter)
    adapter.complete = AsyncMock(return_value="synthesised answer")
    return adapter


def _make_chunk(content: str = "workforce segmentation framework") -> CitedChunk:
    return CitedChunk(
        content=content,
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias="hr-framework.md",
        source_locator="/test/hr-framework.md",
        document_version_id="",
        chunk_index=0,
        score=0.9,
    )


def _search_result(
    chunks: list[CitedChunk], stats: SearchStats | None = None
) -> tuple[list[CitedChunk], SearchStats]:
    return chunks, stats or SearchStats(final_candidate_count=len(chunks))


@pytest.mark.asyncio
async def test_query_returns_cited_response_with_answer(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
        response = await service.query(
            "what is workforce segmentation?",
            role_pack=None,
        )

    assert isinstance(response, CitedResponse)
    assert response.answer == "synthesised answer"
    assert len(response.citations) == 1


@pytest.mark.asyncio
async def test_query_empty_search_returns_no_content_found(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([]))):
        response = await service.query("unknown topic", role_pack=None)

    assert "no relevant content" in (response.answer or "").lower()
    assert response.citations == []
    mock_llm_adapter.complete.assert_not_called()


@pytest.mark.asyncio
async def test_query_llm_error_returns_degraded_response(
    tmp_path: Path,
    mock_pool: MagicMock,
) -> None:
    failing_adapter = AsyncMock(spec=LLMAdapter)
    failing_adapter.complete = AsyncMock(side_effect=Exception("API unavailable"))
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=failing_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
        response = await service.query("what is X?", role_pack=None)

    assert response.answer is None
    assert len(response.citations) == 1


@pytest.mark.asyncio
async def test_query_passes_chunk_contents_to_llm_adapter(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([_make_chunk(content="specific chunk text")])),
    ):
        await service.query("what is X?", role_pack=None)

    call_kwargs = mock_llm_adapter.complete.call_args.kwargs
    assert "specific chunk text" in call_kwargs["context"]


@pytest.mark.asyncio
async def test_query_includes_role_tone_in_prompt(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    role_pack = type("RolePack", (), {"tone": "Use a calm executive tone."})()
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
        await service.query("what is workforce segmentation?", role_pack=role_pack)

    prompt = mock_llm_adapter.complete.call_args.kwargs["prompt"]
    assert "Use a calm executive tone." in prompt


# ── Pruning and thresholding tests (Story 6.13) ────────────────────────────


def _make_chunk_from_source(
    source_locator: str,
    score: float,
    chunk_index: int = 0,
    content: str = "",
) -> CitedChunk:
    return CitedChunk(
        content=content or f"content at {source_locator} chunk {chunk_index}",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_locator,
        source_locator=source_locator,
        document_version_id="",
        chunk_index=chunk_index,
        score=score,
    )


@pytest.mark.asyncio
async def test_query_passes_retrieval_filters_to_search(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    config = make_test_config(tmp_path)
    config.retrieval.min_score = 0.02
    config.retrieval.max_chunks_per_source = 1
    pruned_results = [
        _make_chunk_from_source("/docs/hr.md", 0.9, 0),
    ]
    service = RetrievalService(
        config=config,
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )
    search_mock = AsyncMock(return_value=_search_result(pruned_results))

    with patch(_PATCH, new=search_mock):
        response = await service.query("HR planning", role_pack=None)

    assert response.citations == pruned_results
    call_kwargs = search_mock.await_args.kwargs
    assert call_kwargs["min_score"] == pytest.approx(0.02)
    assert call_kwargs["max_chunks_per_source"] == 1


@pytest.mark.asyncio
async def test_query_all_filtered_returns_no_content_response(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([]))):
        response = await service.query("filtered topic", role_pack=None)

    assert "no relevant content" in (response.answer or "").lower()
    assert response.citations == []
    mock_llm_adapter.complete.assert_not_called()


@pytest.mark.asyncio
async def test_query_llm_receives_only_pruned_context(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    pruned_results = [
        _make_chunk_from_source("/docs/hr.md", 0.9, 0, "top chunk content"),
        _make_chunk_from_source("/docs/ops.md", 0.7, 0, "ops chunk content"),
    ]
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result(pruned_results))):
        # compare query keeps multi-source evidence so both chunks reach the LLM
        await service.query("compare HR planning across all sources", role_pack=None)

    call_kwargs = mock_llm_adapter.complete.call_args.kwargs
    context = call_kwargs["context"]
    assert "top chunk content" in context
    assert "ops chunk content" in context


@pytest.mark.asyncio
async def test_query_citations_match_pruned_evidence_set(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    pruned_results = [
        _make_chunk_from_source("/docs/hr.md", 0.9, 0),
        _make_chunk_from_source("/docs/ops.md", 0.7, 0),
    ]
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result(pruned_results))):
        # compare query keeps multi-source evidence so citations match the full set
        response = await service.query("compare HR documents", role_pack=None)

    assert response.citations == pruned_results


@pytest.mark.parametrize(
    ("query", "expected_fragment"),
    [
        (
            "compare X and Y",
            "Structure your response as a structured comparison",
        ),
        (
            "summarise the workforce plan",
            "Provide a concise synthesis of the key points",
        ),
        (
            "draft a briefing note on retention risk",
            "Structure your response as a formal document",
        ),
        (
            "prioritise these initiatives by impact",
            "Structure your response as a ranked list",
        ),
    ],
)
@pytest.mark.asyncio
async def test_query_adds_query_type_instruction_to_prompt(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    query: str,
    expected_fragment: str,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
        await service.query(query, role_pack=None)

    prompt = mock_llm_adapter.complete.call_args.kwargs["prompt"]
    assert expected_fragment in prompt


# ── Grounding tests (Story 6.14) ──────────────────────────────────────────────


def _make_versioned_chunk(
    source_locator: str,
    document_version_id: str,
    score: float,
    chunk_index: int = 0,
    content: str = "",
) -> CitedChunk:
    return CitedChunk(
        content=content or f"content from {source_locator}",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_locator,
        source_locator=source_locator,
        document_version_id=document_version_id,
        chunk_index=chunk_index,
        score=score,
    )


@pytest.mark.asyncio
async def test_direct_factual_query_narrows_to_single_lineage(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    # Mixed corpus: two distinct lineages — Gmail note and local file
    gmail_chunk = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.9, 0, "leave policy from email"
    )
    local_chunk = _make_versioned_chunk(
        "/docs/leave-policy.md", "ver-bbb-001", 0.7, 0, "leave policy from file"
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([gmail_chunk, local_chunk])),
    ):
        response = await service.query(
            "what is the leave policy?", role_pack=None
        )

    # Only the highest-ranked lineage (gmail) should survive into citations
    assert len(response.citations) == 1
    assert response.citations[0].source_locator == "gmail://msg-001"
    assert response.citations[0].document_version_id == "ver-aaa-001"


@pytest.mark.asyncio
async def test_compare_query_allows_multi_source_evidence(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    gmail_chunk = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.9, 0, "leave policy from email"
    )
    local_chunk = _make_versioned_chunk(
        "/docs/leave-policy.md", "ver-bbb-001", 0.7, 0, "leave policy from file"
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([gmail_chunk, local_chunk])),
    ):
        response = await service.query(
            "compare the leave policy email vs the local file", role_pack=None
        )

    # Both lineages survive when an explicit compare query is used
    assert len(response.citations) == 2


@pytest.mark.asyncio
async def test_explicit_summary_query_across_two_sources_keeps_multi_source_evidence(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    gmail_chunk = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.9, 0, "leave policy from email"
    )
    local_chunk = _make_versioned_chunk(
        "/docs/leave-policy.md", "ver-bbb-001", 0.7, 0, "leave policy from file"
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([gmail_chunk, local_chunk])),
    ):
        response = await service.query(
            "summarise the email and the local file", role_pack=None
        )

    assert len(response.citations) == 2


@pytest.mark.asyncio
async def test_single_source_query_with_aggregate_word_still_grounds_to_one_lineage(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    primary_chunk = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.9, 0, "aggregate retention rate is 12%"
    )
    sibling_chunk = _make_versioned_chunk(
        "/docs/retention.md", "ver-bbb-001", 0.7, 0, "aggregate retention rate is 9%"
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([primary_chunk, sibling_chunk])),
    ):
        response = await service.query(
            "what is the aggregate retention rate?", role_pack=None
        )

    assert len(response.citations) == 1
    assert response.citations[0].source_locator == "gmail://msg-001"


@pytest.mark.asyncio
async def test_grounding_no_usable_lineage_returns_no_content(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    # hybrid_search returns an empty list (already filtered to nothing)
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(_PATCH, new=AsyncMock(return_value=_search_result([]))):
        response = await service.query("what is the retention rate?", role_pack=None)

    assert "no relevant content" in (response.answer or "").lower()
    assert response.citations == []
    mock_llm_adapter.complete.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_backfill_uses_source_locator_as_lineage_key(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    # Both chunks have empty document_version_id (legacy/backfilled records)
    # Lineage key falls back to source_locator
    primary_chunk = _make_chunk_from_source("/docs/primary.md", 0.9, 0, "primary")
    sibling_chunk = _make_chunk_from_source("/docs/sibling.md", 0.7, 0, "sibling")
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([primary_chunk, sibling_chunk])),
    ):
        response = await service.query(
            "what does primary say?", role_pack=None
        )

    # Only primary.md chunks survive because source_locator is the lineage key
    assert len(response.citations) == 1
    assert response.citations[0].source_locator == "/docs/primary.md"


@pytest.mark.asyncio
async def test_direct_factual_query_multiple_chunks_same_lineage_all_survive(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
) -> None:
    # Both chunks from the same document_version_id — both should survive grounding
    chunk_a = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.9, 0, "chunk A from email"
    )
    chunk_b = _make_versioned_chunk(
        "gmail://msg-001", "ver-aaa-001", 0.8, 1, "chunk B from email"
    )
    sibling = _make_versioned_chunk(
        "/docs/other.md", "ver-bbb-001", 0.6, 0, "unrelated file"
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with patch(
        _PATCH,
        new=AsyncMock(return_value=_search_result([chunk_a, chunk_b, sibling])),
    ):
        response = await service.query(
            "what did the email say about leave?", role_pack=None
        )

    assert len(response.citations) == 2
    assert all(c.document_version_id == "ver-aaa-001" for c in response.citations)


# ── Telemetry tests (Story 7.2) ──────────────────────────────────────────────


def _parse_telemetry_log(caplog: pytest.LogCaptureFixture) -> dict:
    """Extract the first JSON log record from the retrieval component."""
    for record in caplog.records:
        try:
            data = json.loads(record.getMessage())
            if data.get("component") == "retrieval" and data.get("event") == "retrieval_run":
                return data
        except (json.JSONDecodeError, AttributeError):
            pass
    raise AssertionError("No retrieval_run telemetry log found in captured records")


@pytest.mark.asyncio
async def test_query_emits_structured_telemetry_on_success(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stats = SearchStats(
        keyword_candidate_count=3,
        semantic_candidate_count=5,
        merged_candidate_count=7,
        post_threshold_count=6,
        post_pruning_count=4,
        final_candidate_count=1,
    )
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with caplog.at_level(logging.INFO):
        with patch(_PATCH, new=AsyncMock(return_value=([_make_chunk()], stats))):
            await service.query("what is workforce segmentation?", role_pack=None)

    data = _parse_telemetry_log(caplog)

    assert data["component"] == "retrieval"
    assert data["event"] == "retrieval_run"
    assert data["outcome"] == "success"
    assert data["failure_stage"] is None
    assert data["query_mode"] == "question"
    assert "trace_id" in data
    assert data["candidate_counts"]["keyword"] == 3
    assert data["candidate_counts"]["semantic"] == 5
    assert data["candidate_counts"]["merged"] == 7
    assert data["candidate_counts"]["post_threshold"] == 6
    assert data["candidate_counts"]["post_pruning"] == 4
    assert "retrieval" in data["latency_ms"]
    assert "synthesis" in data["latency_ms"]
    assert "total" in data["latency_ms"]
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-3-haiku-20240307"


@pytest.mark.asyncio
async def test_query_emits_telemetry_on_no_content(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with caplog.at_level(logging.INFO):
        with patch(_PATCH, new=AsyncMock(return_value=_search_result([]))):
            await service.query("unknown topic", role_pack=None)

    data = _parse_telemetry_log(caplog)

    assert data["outcome"] == "no_content"
    assert data["failure_stage"] == "retrieval"
    assert data["latency_ms"]["synthesis"] is None


@pytest.mark.asyncio
async def test_query_emits_telemetry_on_synthesis_failure(
    tmp_path: Path,
    mock_pool: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    failing_adapter = AsyncMock(spec=LLMAdapter)
    failing_adapter.complete = AsyncMock(side_effect=Exception("API down"))
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=failing_adapter,
    )

    with caplog.at_level(logging.ERROR):
        with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
            await service.query("what is X?", role_pack=None)

    data = _parse_telemetry_log(caplog)

    assert data["outcome"] == "synthesis_degraded"
    assert data["failure_stage"] == "synthesis"
    assert data["latency_ms"]["synthesis"] is not None


@pytest.mark.asyncio
async def test_query_telemetry_does_not_log_raw_query_text(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_query = "SENSITIVE_QUERY_TEXT_DO_NOT_LOG"
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with caplog.at_level(logging.INFO):
        with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
            await service.query(raw_query, role_pack=None)

    for record in caplog.records:
        assert raw_query not in record.getMessage(), (
            f"Raw query text appeared in log: {record.getMessage()!r}"
        )


@pytest.mark.asyncio
async def test_query_telemetry_does_not_log_chunk_content(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_content = "SENSITIVE_CHUNK_CONTENT_DO_NOT_LOG"
    chunk = _make_chunk(content=sensitive_content)
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with caplog.at_level(logging.INFO):
        with patch(_PATCH, new=AsyncMock(return_value=([chunk], SearchStats()))):
            await service.query("what is X?", role_pack=None)

    for record in caplog.records:
        assert sensitive_content not in record.getMessage(), (
            f"Chunk content appeared in log: {record.getMessage()!r}"
        )


@pytest.mark.asyncio
async def test_query_telemetry_query_mode_is_not_raw_text(
    tmp_path: Path,
    mock_pool: MagicMock,
    mock_llm_adapter: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_query = "what is the leave policy for senior staff?"
    service = RetrievalService(
        config=make_test_config(tmp_path),
        pool=mock_pool,
        llm_adapter=mock_llm_adapter,
    )

    with caplog.at_level(logging.INFO):
        with patch(_PATCH, new=AsyncMock(return_value=_search_result([_make_chunk()]))):
            await service.query(raw_query, role_pack=None)

    data = _parse_telemetry_log(caplog)
    valid_modes = {"question", "summarise", "compare", "draft", "prioritise"}
    assert data["query_mode"] in valid_modes, (
        f"query_mode {data['query_mode']!r} is not a safe mode token"
    )
    assert data["query_mode"] != raw_query
