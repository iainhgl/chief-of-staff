"""Test fixtures.

Before running tests, create the test database:
    docker compose exec postgres createdb -U postgres cos_test
    # OR
    psql -U postgres -c "CREATE DATABASE cos_test;"
"""
from pathlib import Path

import psycopg
import pytest
from pydantic import SecretStr

from cos.config import (
    ChunkingConfig,
    CosConfig,
    DatabaseConfig,
    EmbeddingConfig,
    LLMConfig,
    RolePackRef,
    StorageConfig,
    TikaConfig,
)
from cos.store.db import run_migrations

TEST_DSN = "postgresql://postgres:postgres@localhost:5432/cos_test"


def make_test_config(tmp_path: Path) -> CosConfig:
    return CosConfig(
        llm=LLMConfig(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            api_key=SecretStr("test"),
        ),
        embedding=EmbeddingConfig(
            provider="anthropic",
            model="voyage-3",
            api_key=SecretStr("test"),
        ),
        role_pack=RolePackRef(path="role_packs/chro.yaml"),
        channels=["local"],
        connectors=[],
        database=DatabaseConfig(
            host="localhost",
            port=5432,
            user="postgres",
            password=SecretStr("postgres"),
            dbname="cos_test",
        ),
        tika=TikaConfig(url="http://localhost:9998"),
        storage=StorageConfig(
            originals_dir=tmp_path / "originals",
            markdown_dir=tmp_path / "markdown",
        ),
        chunking=ChunkingConfig(chunk_size=512, chunk_overlap=50),
    )


@pytest.fixture
async def db_conn():
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        try:
            yield conn
        finally:
            await conn.rollback()


@pytest.fixture
async def migrated_db():
    await run_migrations(TEST_DSN)
    yield
