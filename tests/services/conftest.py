from collections.abc import AsyncIterator

import psycopg
import pytest
from conftest import TEST_DSN

from cos.ingestion.embedder import EmbeddingResult


@pytest.fixture(autouse=True)
async def clean_tables(migrated_db: None) -> AsyncIterator[None]:
    yield
    async with await psycopg.AsyncConnection.connect(TEST_DSN, autocommit=True) as conn:
        await conn.execute(
            "TRUNCATE embeddings, chunks, document_versions, documents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def mock_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_embed(
        chunks: list[str],
        provider: str,
        model: str,
        api_key: str,
    ) -> list[EmbeddingResult]:
        del api_key
        return [
            EmbeddingResult(
                vector=[float(index) / 100 for index in range(1024)],
                model=model,
                provider=provider,
            )
            for _ in chunks
        ]

    monkeypatch.setattr("cos.ingestion.pipeline.embed", _fake_embed)
