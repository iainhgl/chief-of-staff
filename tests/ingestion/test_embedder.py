import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cos.ingestion.embedder import EmbeddingError, EmbeddingResult, embed


async def test_embed_empty_chunks_raises() -> None:
    with pytest.raises(EmbeddingError, match="empty chunk list"):
        await embed([], provider="anthropic", model="voyage-3", api_key="test-key")


async def test_embed_unsupported_provider_raises() -> None:
    with pytest.raises(EmbeddingError, match="Unsupported"):
        await embed(
            ["text"],
            provider="openai",
            model="text-embedding-3-large",
            api_key="test-key",
        )


async def test_embed_voyage_unavailable_raises() -> None:
    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=Exception("connection refused"))

    with patch("cos.ingestion.embedder.voyageai.AsyncClient", return_value=mock_client):
        with pytest.raises(
            EmbeddingError,
            match="Voyage embedding failed: connection refused",
        ):
            await embed(
                ["hello"],
                provider="anthropic",
                model="voyage-3",
                api_key="test-key",
            )


async def test_embed_result_shape() -> None:
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value=mock_result)

    with patch("cos.ingestion.embedder.voyageai.AsyncClient", return_value=mock_client):
        results = await embed(
            ["hello"],
            provider="anthropic",
            model="voyage-3",
            api_key="test-key",
        )

    assert len(results) == 1
    assert isinstance(results[0], EmbeddingResult)
    assert results[0].vector == [0.1, 0.2, 0.3]
    assert results[0].model == "voyage-3"
    assert results[0].provider == "anthropic"


async def test_embed_result_count_matches_input() -> None:
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2], [0.3, 0.4]]

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value=mock_result)

    with patch("cos.ingestion.embedder.voyageai.AsyncClient", return_value=mock_client):
        results = await embed(
            ["hello", "world"],
            provider="anthropic",
            model="voyage-3",
            api_key="test-key",
        )

    assert len(results) == 2


@pytest.mark.integration
async def test_embed_via_voyage_live() -> None:
    api_key = os.environ.get("VOYAGE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key found in VOYAGE_API_KEY or ANTHROPIC_API_KEY")

    results = await embed(
        ["Hello world"],
        provider="anthropic",
        model="voyage-3",
        api_key=api_key,
    )

    assert len(results) == 1
    assert isinstance(results[0].vector, list)
    assert len(results[0].vector) > 0
    assert results[0].model == "voyage-3"
    assert results[0].provider == "anthropic"
