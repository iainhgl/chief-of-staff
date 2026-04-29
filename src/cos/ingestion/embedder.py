"""Embedding generation for text chunks."""

import ssl
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import voyageai


class EmbeddingError(RuntimeError):
    pass


@dataclass
class EmbeddingResult:
    vector: list[float]
    model: str
    provider: str


@dataclass(frozen=True)
class VoyageTransportConfig:
    ca_bundle_path: Path | None = None
    proxy_url: str | None = None
    trust_env: bool = False


EmbedProvider = Callable[
    [list[str], str, str, VoyageTransportConfig | None],
    Awaitable[list[EmbeddingResult]],
]


async def embed(
    chunks: list[str],
    provider: str,
    model: str,
    api_key: str,
    transport: VoyageTransportConfig | None = None,
) -> list[EmbeddingResult]:
    if not chunks:
        raise EmbeddingError("Cannot embed an empty chunk list")
    fn = _EMBED_PROVIDERS.get(provider)
    if fn is None:
        raise EmbeddingError(f"Unsupported embedding provider: {provider!r}")
    return await fn(chunks, model, api_key, transport)  # type: ignore[no-any-return]


async def _embed_via_voyage(
    chunks: list[str],
    model: str,
    api_key: str,
    transport: VoyageTransportConfig | None = None,
) -> list[EmbeddingResult]:
    try:
        async with _voyage_session(transport):
            client_factory = getattr(voyageai, "AsyncClient")
            client: Any = client_factory(api_key=api_key)
            result = await client.embed(chunks, model=model)
    except Exception as exc:
        detail = _format_exception_chain(exc)
        hint = _transport_hint(transport)
        raise EmbeddingError(f"Voyage embedding failed: {detail}{hint}") from exc

    return [
        EmbeddingResult(
            vector=[float(value) for value in vector],
            model=model,
            provider="anthropic",
        )
        for vector in result.embeddings
    ]


_EMBED_PROVIDERS: dict[str, Any] = {
    "anthropic": _embed_via_voyage,
}


@asynccontextmanager
async def _voyage_session(
    transport: VoyageTransportConfig | None,
) -> AsyncIterator[None]:
    if transport is None or not _has_transport_overrides(transport):
        yield
        return

    session_kwargs: dict[str, Any] = {
        "trust_env": transport.trust_env,
    }
    if transport.ca_bundle_path is not None:
        ca_bundle_path = transport.ca_bundle_path.expanduser()
        if not ca_bundle_path.exists():
            raise EmbeddingError(
                f"embedding.ca_bundle_path not found: {ca_bundle_path}"
            )
        session_kwargs["connector"] = aiohttp.TCPConnector(
            ssl=_build_ssl_context(ca_bundle_path)
        )

    session = aiohttp.ClientSession(**session_kwargs)
    token = voyageai.aiosession.set(session)
    original_proxy: Any = voyageai.proxy

    if transport.proxy_url:
        setattr(voyageai, "proxy", transport.proxy_url)

    try:
        yield
    finally:
        setattr(voyageai, "proxy", original_proxy)
        voyageai.aiosession.reset(token)
        await session.close()


def _has_transport_overrides(transport: VoyageTransportConfig) -> bool:
    return (
        transport.ca_bundle_path is not None
        or transport.proxy_url is not None
        or transport.trust_env
    )


def _build_ssl_context(ca_bundle_path: Path) -> ssl.SSLContext:
    try:
        return ssl.create_default_context(cafile=str(ca_bundle_path))
    except Exception as exc:  # pragma: no cover - platform SSL errors vary
        raise EmbeddingError(
            f"Unable to load embedding.ca_bundle_path {ca_bundle_path}: {exc}"
        ) from exc


def _transport_hint(transport: VoyageTransportConfig | None) -> str:
    if transport is None:
        return ""
    if not _has_transport_overrides(transport):
        return (
            " (if you are behind a corporate proxy or TLS interception layer, "
            "set embedding.ca_bundle_path, embedding.proxy_url, or embedding.trust_env)"
        )
    return ""


def _format_exception_chain(exc: BaseException) -> str:
    messages: list[str] = []
    current: BaseException | None = exc

    while current is not None:
        message = str(current).strip() or current.__class__.__name__
        if message and message not in messages:
            messages.append(message)
        current = current.__cause__

    return " <- ".join(messages) if messages else exc.__class__.__name__
