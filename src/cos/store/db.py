"""Database helpers — migration runner and connection pool support."""
import json
import logging
from pathlib import Path
from typing import Any

import psycopg
from pgvector.psycopg import register_vector_async  # type: ignore[import-untyped]
from psycopg_pool import AsyncConnectionPool

from cos.store.models import (
    ChunkRecord,
    ContentBlobRecord,
    DocumentSummary,
    EmbeddingRecord,
    SourceRecord,
    SourceVersionRecord,
    VersionSummary,
)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _has_executable_sql(sql: str) -> bool:
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return True
    return False


async def _repair_existing_schema(conn: psycopg.AsyncConnection[Any]) -> None:
    await conn.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'source_versions'::regclass
                  AND conname = 'source_versions_source_document_unique'
            ) THEN
                ALTER TABLE source_versions
                ADD CONSTRAINT source_versions_source_document_unique
                UNIQUE (source_id, document_version_id);
            END IF;
        END $$;
        """
    )


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
        await _repair_existing_schema(conn)


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
                "DELETE FROM chunks WHERE document_id = %s",
                (document_id,),
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


async def create_pool(dsn: str) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(dsn, open=False)
    await pool.open(wait=True, timeout=30.0)
    return pool


async def list_documents(
    conn: psycopg.AsyncConnection[Any],
) -> list[DocumentSummary]:
    result = await conn.execute(
        """
        SELECT
            d.id::text,
            -- Deterministic alias: first source by created_at ASC; fallback to
            -- source_path for legacy records without canonical source rows.
            COALESCE(
                (SELECT s.source_alias
                 FROM sources s
                 JOIN source_versions sv ON sv.source_id = s.id
                 JOIN document_versions dv ON dv.id = sv.document_version_id
                 WHERE dv.document_id = d.id
                 ORDER BY s.created_at ASC, s.id ASC
                 LIMIT 1),
                d.source_path
            ) AS source_alias,
            COALESCE(
                (SELECT s.source_locator
                 FROM sources s
                 JOIN source_versions sv ON sv.source_id = s.id
                 JOIN document_versions dv ON dv.id = sv.document_version_id
                 WHERE dv.document_id = d.id
                 ORDER BY s.created_at ASC, s.id ASC
                 LIMIT 1),
                d.source_path
            ) AS source_locator,
            d.ingested_at,
            d.current_version,
            COUNT(c.id)::int AS chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id, d.source_path, d.ingested_at, d.current_version
        ORDER BY d.ingested_at DESC
        """
    )
    rows = await result.fetchall()
    return [
        DocumentSummary(
            id=row[0],
            source_alias=row[1],
            source_locator=row[2],
            ingested_at=row[3],
            current_version=row[4],
            chunk_count=row[5],
        )
        for row in rows
    ]


async def list_document_versions(
    conn: psycopg.AsyncConnection[Any],
    document_id: str,
) -> list[VersionSummary]:
    result = await conn.execute(
        """
        SELECT version, created_at, content_hash
        FROM document_versions
        WHERE document_id = %s::uuid
        ORDER BY version ASC
        """,
        (document_id,),
    )
    rows = await result.fetchall()
    return [
        VersionSummary(
            version_number=row[0],
            ingested_at=row[1],
            file_hash=row[2],
        )
        for row in rows
    ]


async def find_content_blob_by_sha256(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
) -> ContentBlobRecord | None:
    result = await conn.execute(
        "SELECT id::text, sha256, byte_size, created_at "
        "FROM content_blobs WHERE sha256 = %s",
        (sha256,),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return ContentBlobRecord(
        id=row[0],
        sha256=row[1],
        byte_size=row[2],
        created_at=row[3],
    )


async def find_source(
    conn: psycopg.AsyncConnection[Any],
    source_type: str,
    source_locator: str,
) -> SourceRecord | None:
    result = await conn.execute(
        "SELECT id::text, source_type, source_locator, source_alias, created_at "
        "FROM sources WHERE source_type = %s AND source_locator = %s",
        (source_type, source_locator),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return SourceRecord(
        id=row[0],
        source_type=row[1],
        source_locator=row[2],
        source_alias=row[3],
        created_at=row[4],
    )


async def upsert_source(
    conn: psycopg.AsyncConnection[Any],
    source_type: str,
    source_locator: str,
    source_alias: str,
) -> SourceRecord:
    result = await conn.execute(
        "INSERT INTO sources (source_type, source_locator, source_alias) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT ON CONSTRAINT sources_type_locator_unique "
        "DO UPDATE SET source_alias = EXCLUDED.source_alias "
        "RETURNING id::text, source_type, source_locator, source_alias, created_at",
        (source_type, source_locator, source_alias),
    )
    row = await result.fetchone()
    if row is None:
        raise RuntimeError("upsert_source returned no row")
    return SourceRecord(
        id=row[0],
        source_type=row[1],
        source_locator=row[2],
        source_alias=row[3],
        created_at=row[4],
    )


async def create_content_blob(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    byte_size: int,
) -> ContentBlobRecord:
    result = await conn.execute(
        "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, %s) "
        "ON CONFLICT ON CONSTRAINT content_blobs_sha256_unique "
        "DO UPDATE SET byte_size = EXCLUDED.byte_size "
        "RETURNING id::text, sha256, byte_size, created_at",
        (sha256, byte_size),
    )
    row = await result.fetchone()
    if row is None:
        raise RuntimeError("create_content_blob returned no row")
    return ContentBlobRecord(
        id=row[0],
        sha256=row[1],
        byte_size=row[2],
        created_at=row[3],
    )


async def find_source_version_for_blob(
    conn: psycopg.AsyncConnection[Any],
    source_id: str,
    content_blob_id: str,
) -> SourceVersionRecord | None:
    result = await conn.execute(
        "SELECT id::text, source_id::text, document_version_id::text, "
        "content_blob_id::text, observed_at "
        "FROM source_versions "
        "WHERE source_id = %s::uuid AND content_blob_id = %s::uuid "
        "LIMIT 1",
        (source_id, content_blob_id),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return SourceVersionRecord(
        id=row[0],
        source_id=row[1],
        document_version_id=row[2],
        content_blob_id=row[3],
        observed_at=row[4],
    )


async def find_canonical_document_version_for_blob(
    conn: psycopg.AsyncConnection[Any],
    content_blob_id: str,
) -> tuple[str, str] | None:
    result = await conn.execute(
        "SELECT id::text, document_id::text "
        "FROM document_versions "
        "WHERE content_blob_id = %s::uuid "
        "ORDER BY created_at ASC LIMIT 1",
        (content_blob_id,),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return (row[0], row[1])


async def link_new_source_to_existing_blob(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    source_type: str,
    source_locator: str,
    source_alias: str,
) -> str:
    blob = await find_content_blob_by_sha256(conn, sha256)
    if blob is None:
        raise RuntimeError(f"No content_blob found for sha256={sha256!r}")

    version_info = await find_canonical_document_version_for_blob(conn, blob.id)
    if version_info is None:
        raise RuntimeError(f"No document_version found for content_blob {blob.id!r}")

    document_version_id, document_id = version_info
    async with conn.transaction():
        source = await upsert_source(conn, source_type, source_locator, source_alias)
        await conn.execute(
            "INSERT INTO source_versions "
            "(source_id, document_version_id, content_blob_id) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid) "
            "ON CONFLICT ON CONSTRAINT "
            "source_versions_source_document_unique DO NOTHING",
            (source.id, document_version_id, blob.id),
        )
    return document_id


async def store_document_canonical(
    conn: psycopg.AsyncConnection[Any],
    source_path: str,
    sha256: str,
    byte_size: int,
    source_type: str,
    source_locator: str,
    source_alias: str,
    chunks: list[ChunkRecord],
    embeddings: list[EmbeddingRecord],
) -> str:
    await register_vector_async(conn)

    async with conn.transaction():
        content_blob = await create_content_blob(conn, sha256, byte_size)
        source = await upsert_source(conn, source_type, source_locator, source_alias)

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
                (source_path, sha256),
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
                "DELETE FROM chunks WHERE document_id = %s",
                (document_id,),
            )

        result = await conn.execute(
            "INSERT INTO document_versions "
            "(document_id, version, content_hash, content_blob_id) "
            "VALUES (%s, %s, %s, %s::uuid) RETURNING id",
            (document_id, new_version, sha256, content_blob.id),
        )
        row = await result.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert document_version row")
        document_version_id = row[0]

        await conn.execute(
            "INSERT INTO source_versions "
            "(source_id, document_version_id, content_blob_id) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid) "
            "ON CONFLICT ON CONSTRAINT "
            "source_versions_source_document_unique DO NOTHING",
            (source.id, document_version_id, content_blob.id),
        )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            result = await conn.execute(
                "INSERT INTO chunks "
                "(document_id, chunk_index, content, token_count, document_version_id) "
                "VALUES (%s, %s, %s, %s, %s::uuid) RETURNING id",
                (
                    document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.token_count,
                    document_version_id,
                ),
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
