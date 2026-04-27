from typing import Any

from psycopg_pool import AsyncConnectionPool

from cos.config import CosConfig


class RetrievalService:
    def __init__(self, config: CosConfig, pool: AsyncConnectionPool) -> None:
        self._config = config
        self._pool = pool

    async def query(self, text: str, role_pack: Any) -> list[dict[str, Any]]:
        raise NotImplementedError
