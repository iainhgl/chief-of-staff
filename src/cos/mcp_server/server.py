import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
import psycopg
from mcp.server.fastmcp import FastMCP
from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig, LogComponent
from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig
from cos.output.router import OutputRouter
from cos.services.output import OutputService
from cos.services.retrieval import RetrievalService
from cos.store.db import create_pool, run_migrations

mcp = FastMCP("cos")

_config: CosConfig | None = None
_output_router: OutputRouter | None = None
_pool: AsyncConnectionPool | None = None
_retrieval_service: RetrievalService | None = None
_output_service: OutputService | None = None


def get_config() -> CosConfig | None:
    return _config


def get_output_router() -> OutputRouter | None:
    return _output_router


def get_pool() -> AsyncConnectionPool | None:
    return _pool


def get_retrieval_service() -> RetrievalService | None:
    return _retrieval_service


def get_output_service() -> OutputService | None:
    return _output_service


def _emit(component: LogComponent, level: str, message: str, **extra: object) -> None:
    record: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": component,
        "message": message,
        **extra,
    }
    log_fn = getattr(logging, level.lower(), logging.info)
    log_fn(json.dumps(record))


async def _check_postgres(dsn: str) -> bool:
    try:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False


async def _check_tika(url: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            return resp.status_code < 500
    except Exception:
        return False


async def _startup_sequence(config: CosConfig) -> None:
    global _output_router, _pool, _retrieval_service, _output_service
    component: LogComponent = "mcp_server"
    pg_ok = await _check_postgres(config.database.libpq_dsn)
    _emit(component, "INFO", "Postgres: healthy" if pg_ok else "Postgres: unhealthy")
    tika_ok = await _check_tika(config.tika.url)
    _emit(component, "INFO", "Tika: healthy" if tika_ok else "Tika: unhealthy")
    _emit(component, "INFO", "config loaded", role_pack_path=config.role_pack.path)
    await run_migrations(config.database.libpq_dsn)
    _emit(component, "INFO", "migrations applied")
    _pool = await create_pool(config.database.libpq_dsn)
    _emit(component, "INFO", "connection pool: open")
    _emit(component, "INFO", "role pack: stub loaded")
    _output_router = OutputRouter(configured_channels=config.channels)
    _output_service = OutputService(router=_output_router)
    _emit(component, "INFO", "output router: initialised", channels=config.channels)
    adapter = AnthropicAdapter(
        model=config.llm.model,
        api_key=config.llm.api_key.get_secret_value(),
        transport=HttpTransportConfig(
            ca_bundle_path=(
                config.llm.ca_bundle_path
                if config.llm.ca_bundle_path is not None
                else config.embedding.ca_bundle_path
            ),
            proxy_url=(
                config.llm.proxy_url
                if config.llm.proxy_url is not None
                else config.embedding.proxy_url
            ),
            trust_env=(
                config.llm.trust_env
                if config.llm.trust_env is not None
                else config.embedding.trust_env
            ),
        ),
    )
    _retrieval_service = RetrievalService(
        config=config,
        pool=_pool,
        llm_adapter=adapter,
    )
    _emit(component, "INFO", "retrieval service: initialised")
    _emit(component, "INFO", "MCP server: listening")


def run() -> None:
    global _config
    import cos.mcp_server.tools  # noqa: F401  — registers @mcp.tool() handlers
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = CosConfig.load()
    _config = config
    asyncio.run(_startup_sequence(config))
    mcp.run()
