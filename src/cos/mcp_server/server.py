import asyncio
import json
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from cos.config import CosConfig, LogComponent
from cos.store.db import run_migrations

mcp = FastMCP("cos")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = CosConfig.load()
    _log_startup(config)
    asyncio.run(_apply_migrations(config))
    mcp.run()


async def _apply_migrations(config: CosConfig) -> None:
    await run_migrations(config.database.libpq_dsn)
    component: LogComponent = "mcp_server"
    logging.info(json.dumps({"component": component, "message": "migrations applied"}))


def _log_startup(config: CosConfig) -> None:
    component: LogComponent = "mcp_server"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "component": component,
        "message": "config loaded",
        "role_pack_path": config.role_pack.path,
    }
    logging.info(json.dumps(record))
