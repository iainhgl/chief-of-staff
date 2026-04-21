from typing import Any


class RetrievalService:
    async def query(self, text: str, role_pack: Any) -> list[dict]:
        raise NotImplementedError
