from dataclasses import dataclass

import httpx
import psycopg
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from cos.rolepack.loader import load as load_role_pack


@dataclass
class ComponentStatus:
    name: str
    healthy: bool
    message: str
    recovery_hint: str = ""


class HealthService:
    def __init__(
        self, db_dsn: str, tika_url: str, role_pack_path: str | None = None
    ) -> None:
        self._db_dsn = db_dsn
        self._tika_url = tika_url
        self._role_pack_path = role_pack_path

    async def check_all(self) -> list[ComponentStatus]:
        return [
            await self._check_postgres(),
            await self._check_tika(),
            self._check_mcp_server(),
            self._check_role_pack(),
            await self._check_database(),
        ]

    async def _check_postgres(self) -> ComponentStatus:
        try:
            async with await psycopg.AsyncConnection.connect(self._db_dsn) as conn:
                await conn.execute("SELECT 1")
            return ComponentStatus(
                name="Postgres",
                healthy=True,
                message="healthy",
            )
        except Exception:
            return ComponentStatus(
                name="Postgres",
                healthy=False,
                message="container not running",
                recovery_hint="Run: cos restart",
            )

    async def _check_tika(self) -> ComponentStatus:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self._tika_url, timeout=5.0)
            if resp.status_code < 500:
                return ComponentStatus(name="Tika", healthy=True, message="healthy")
            return ComponentStatus(
                name="Tika",
                healthy=False,
                message="service unhealthy",
                recovery_hint="Run: cos restart",
            )
        except Exception:
            return ComponentStatus(
                name="Tika",
                healthy=False,
                message="service not responding",
                recovery_hint="Run: cos restart",
            )

    def _check_mcp_server(self) -> ComponentStatus:
        return ComponentStatus(
            name="MCP server",
            healthy=True,
            message="listening on stdio",
        )

    def _check_role_pack(self) -> ComponentStatus:
        if self._role_pack_path is None:
            return ComponentStatus(
                name="Role pack",
                healthy=False,
                message="not configured",
                recovery_hint="Set role_pack.path in config.yaml",
            )

        try:
            role_pack = load_role_pack(self._role_pack_path)
        except FileNotFoundError:
            return ComponentStatus(
                name="Role pack",
                healthy=False,
                message="not loaded",
                recovery_hint=(
                    f"file not found: {self._role_pack_path}. "
                    "Check config.yaml role_pack_path."
                ),
            )
        except (yaml.YAMLError, ValidationError, TypeError, ValueError):
            return ComponentStatus(
                name="Role pack",
                healthy=False,
                message="not loaded",
                recovery_hint=(
                    f"invalid role pack: {self._role_pack_path}. "
                    "Fix the role pack file and restart."
                ),
            )

        return ComponentStatus(
            name="Role pack",
            healthy=True,
            message=f"{role_pack.role_name} loaded",
        )

    async def _check_database(self) -> ComponentStatus:
        try:
            async with await psycopg.AsyncConnection.connect(self._db_dsn) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM documents")
                row = await cursor.fetchone()
            count = 0 if row is None else int(row[0])
            return ComponentStatus(
                name="Database",
                healthy=True,
                message=f"connected ({count} documents indexed)",
            )
        except Exception:
            return ComponentStatus(
                name="Database",
                healthy=False,
                message="could not connect",
                recovery_hint="Run: cos restart",
            )
