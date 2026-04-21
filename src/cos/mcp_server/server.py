import json
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from cos.config import CosConfig, LogComponent

mcp = FastMCP("cos")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = CosConfig.load()
    _log_startup(config)
    mcp.run()


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
