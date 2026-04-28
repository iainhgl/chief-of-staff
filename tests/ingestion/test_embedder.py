import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voyageai

from cos.ingestion.embedder import (
    EmbeddingError,
    EmbeddingResult,
    VoyageTransportConfig,
    embed,
)


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


async def test_embed_uses_custom_voyage_session_for_proxy_and_trust_env() -> None:
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]
    original_proxy = voyageai.proxy

    fake_session = MagicMock()
    fake_session.close = AsyncMock()

    async def _assert_transport(*args, **kwargs):
        del args, kwargs
        assert voyageai.aiosession.get() is fake_session
        assert voyageai.proxy == "http://proxy.internal:8080"
        return mock_result

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(side_effect=_assert_transport)

    with (
        patch("cos.ingestion.embedder.aiohttp.ClientSession", return_value=fake_session),
        patch("cos.ingestion.embedder.voyageai.AsyncClient", return_value=mock_client),
    ):
        results = await embed(
            ["hello"],
            provider="anthropic",
            model="voyage-3",
            api_key="test-key",
            transport=VoyageTransportConfig(
                proxy_url="http://proxy.internal:8080",
                trust_env=True,
            ),
        )

    assert len(results) == 1
    fake_session.close.assert_awaited_once()
    assert voyageai.aiosession.get() is None
    assert voyageai.proxy == original_proxy


async def test_embed_missing_ca_bundle_raises() -> None:
    with pytest.raises(EmbeddingError, match="embedding.ca_bundle_path not found"):
        await embed(
            ["hello"],
            provider="anthropic",
            model="voyage-3",
            api_key="test-key",
            transport=VoyageTransportConfig(
                ca_bundle_path=Path("/definitely/missing/zscaler.pem")
            ),
        )


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
