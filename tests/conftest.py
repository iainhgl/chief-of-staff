"""Test fixtures.

Before running tests, create the test database:
    docker compose exec postgres createdb -U postgres cos_test
    # OR
    psql -U postgres -c "CREATE DATABASE cos_test;"
"""
import pytest
import psycopg

from cos.store.db import run_migrations

TEST_DSN = "postgresql://postgres:postgres@localhost:5432/cos_test"


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
