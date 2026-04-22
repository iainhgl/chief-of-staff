"""Database helpers — migration runner and connection pool stub."""
import json
import logging
from pathlib import Path
from typing import Any

import psycopg

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _has_executable_sql(sql: str) -> bool:
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return True
    return False


async def run_migrations(dsn: str) -> None:
    if not _MIGRATIONS_DIR.is_dir():
        raise RuntimeError(f"Migrations directory not found: {_MIGRATIONS_DIR}")
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        for migration_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            sql = migration_path.read_text()
            if not _has_executable_sql(sql):
                continue
            await conn.execute(sql)
            logging.info(
                json.dumps(
                    {
                        "component": "mcp_server",
                        "message": "migration applied",
                        "file": migration_path.name,
                    }
                )
            )


async def create_pool(dsn: str) -> Any:
    raise NotImplementedError
