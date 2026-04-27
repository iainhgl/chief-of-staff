from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import make_test_config

from cos.llm.adapter import LLMAdapter
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.services.retrieval import RetrievalService


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
        source_path="/test/hr-framework.md",
        chunk_index=0,
        score=0.9,
    )


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

    with patch(
        "cos.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=[_make_chunk()]),
    ):
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

    with patch("cos.services.retrieval.hybrid_search", new=AsyncMock(return_value=[])):
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

    with patch(
        "cos.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=[_make_chunk()]),
    ):
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
        "cos.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=[_make_chunk(content="specific chunk text")]),
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

    with patch(
        "cos.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=[_make_chunk()]),
    ):
        await service.query("what is workforce segmentation?", role_pack=role_pack)

    prompt = mock_llm_adapter.complete.call_args.kwargs["prompt"]
    assert "Use a calm executive tone." in prompt


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

    with patch(
        "cos.services.retrieval.hybrid_search",
        new=AsyncMock(return_value=[_make_chunk()]),
    ):
        await service.query(query, role_pack=None)

    prompt = mock_llm_adapter.complete.call_args.kwargs["prompt"]
    assert expected_fragment in prompt
