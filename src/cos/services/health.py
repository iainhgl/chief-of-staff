import httpx
import psycopg


class HealthService:
    def __init__(self, db_dsn: str, tika_url: str) -> None:
        self._db_dsn = db_dsn
        self._tika_url = tika_url

    async def check_all(self) -> list[dict[str, object]]:
        pg_ok = await self._check_postgres()
        tika_ok = await self._check_tika()
        return [
            {"name": "postgres", "healthy": pg_ok},
            {"name": "tika", "healthy": tika_ok},
        ]

    async def _check_postgres(self) -> bool:
        try:
            async with await psycopg.AsyncConnection.connect(self._db_dsn) as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def _check_tika(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self._tika_url, timeout=5.0)
                return resp.status_code < 500
        except Exception:
            return False
