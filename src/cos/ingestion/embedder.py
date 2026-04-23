"""Embedding generation for text chunks."""

from dataclasses import dataclass
from typing import Any

import voyageai


class EmbeddingError(RuntimeError):
    pass


@dataclass
class EmbeddingResult:
    vector: list[float]
    model: str
    provider: str


async def embed(
    chunks: list[str],
    provider: str,
    model: str,
    api_key: str,
) -> list[EmbeddingResult]:
    if not chunks:
        raise EmbeddingError("Cannot embed an empty chunk list")
    if provider != "anthropic":
        raise EmbeddingError(f"Unsupported embedding provider: {provider!r}")

    return await _embed_via_voyage(chunks, model, api_key)


async def _embed_via_voyage(
    chunks: list[str],
    model: str,
    api_key: str,
) -> list[EmbeddingResult]:
    try:
        client_factory = getattr(voyageai, "AsyncClient")
        client: Any = client_factory(api_key=api_key)
        result = await client.embed(chunks, model=model)
    except Exception as exc:
        raise EmbeddingError(f"Voyage embedding failed: {exc}") from exc

    return [
        EmbeddingResult(
            vector=[float(value) for value in vector],
            model=model,
            provider="anthropic",
        )
        for vector in result.embeddings
    ]
