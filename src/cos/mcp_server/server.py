import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
import psycopg
from mcp.server.fastmcp import FastMCP

from cos.config import CosConfig, LogComponent
from cos.store.db import run_migrations

mcp = FastMCP("cos")

_config: CosConfig | None = None


def get_config() -> CosConfig | None:
    return _config


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
    component: LogComponent = "mcp_server"
    pg_ok = await _check_postgres(config.database.libpq_dsn)
    _emit(component, "INFO", "Postgres: healthy" if pg_ok else "Postgres: unhealthy")
    tika_ok = await _check_tika(config.tika.url)
    _emit(component, "INFO", "Tika: healthy" if tika_ok else "Tika: unhealthy")
    _emit(component, "INFO", "config loaded", role_pack_path=config.role_pack.path)
    await run_migrations(config.database.libpq_dsn)
    _emit(component, "INFO", "migrations applied")
    _emit(component, "INFO", "role pack: stub loaded")
    _emit(component, "INFO", "MCP server: listening")


def run() -> None:
    global _config
    import cos.mcp_server.tools  # noqa: F401  — registers @mcp.tool() handlers
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = CosConfig.load()
    _config = config
    asyncio.run(_startup_sequence(config))
    mcp.run()
