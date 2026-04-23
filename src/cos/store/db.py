"""Database helpers — migration runner and connection pool stub."""
import json
import logging
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector_async  # type: ignore[import-untyped]

from cos.store.models import ChunkRecord, EmbeddingRecord

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


async def store_document(
    conn: psycopg.AsyncConnection[Any],
    source_path: str,
    file_hash: str,
    chunks: list[ChunkRecord],
    embeddings: list[EmbeddingRecord],
) -> str:
    await register_vector_async(conn)

    async with conn.transaction():
        result = await conn.execute(
            "SELECT id, current_version FROM documents WHERE source_path = %s",
            (source_path,),
        )
        existing = await result.fetchone()

        if existing is None:
            result = await conn.execute(
                "INSERT INTO documents "
                "(source_path, file_hash, current_version, status) "
                "VALUES (%s, %s, 1, 'indexed') RETURNING id",
                (source_path, file_hash),
            )
            row = await result.fetchone()
            if row is None:
                raise RuntimeError("Failed to insert document row")
            document_id = row[0]
            new_version = 1
        else:
            document_id, current_version = existing
            new_version = current_version + 1
            await conn.execute(
                "UPDATE documents SET current_version = %s WHERE id = %s",
                (new_version, document_id),
            )

        await conn.execute(
            "INSERT INTO document_versions (document_id, version, content_hash) "
            "VALUES (%s, %s, %s)",
            (document_id, new_version, file_hash),
        )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            result = await conn.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, token_count) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (document_id, chunk.chunk_index, chunk.content, chunk.token_count),
            )
            chunk_row = await result.fetchone()
            if chunk_row is None:
                raise RuntimeError("Failed to insert chunk row")
            chunk_id = chunk_row[0]

            await conn.execute(
                "INSERT INTO embeddings (chunk_id, vector, model, provider) "
                "VALUES (%s, %s, %s, %s)",
                (chunk_id, embedding.vector, embedding.model, embedding.provider),
            )

    return str(document_id)


async def create_pool(dsn: str) -> Any:
    raise NotImplementedError
