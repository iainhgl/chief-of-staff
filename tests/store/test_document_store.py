import uuid
from datetime import timedelta

import psycopg
import pytest
from conftest import TEST_DSN

from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord


def _make_chunk(index: int = 0, token_count: int = 10) -> ChunkRecord:
    return ChunkRecord(
        content=f"chunk {index}",
        chunk_index=index,
        token_count=token_count,
    )


def _make_embedding(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[(index * 0.001) + (dimension / 1000) for dimension in range(1024)],
        model="voyage-3",
        provider="anthropic",
    )


async def test_store_document_first_ingest_creates_documents_row(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/test.md",
            file_hash="deadbeef",
            chunks=[_make_chunk()],
            embeddings=[_make_embedding()],
        )
        result = await conn.execute(
            "SELECT source_path, file_hash, ingested_at, current_version, status "
            "FROM documents WHERE id = %s",
            (document_id,),
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "docs/test.md"
    assert row[1] == "deadbeef"
    assert row[2].utcoffset() == timedelta(0)
    assert row[2].isoformat().endswith("+00:00")
    assert row[3] == 1
    assert row[4] == "indexed"


async def test_store_document_creates_document_versions_row(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/versioned.md",
            file_hash="hash-v1",
            chunks=[_make_chunk()],
            embeddings=[_make_embedding()],
        )
        result = await conn.execute(
            "SELECT version, content_hash FROM document_versions "
            "WHERE document_id = %s",
            (document_id,),
        )
        rows = await result.fetchall()

    assert rows == [(1, "hash-v1")]


async def test_store_document_creates_chunks_rows(migrated_db: None) -> None:
    chunks = [_make_chunk(0, token_count=10), _make_chunk(1, token_count=12)]
    embeddings = [_make_embedding(0), _make_embedding(1)]

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/chunks.md",
            file_hash="chunk-hash",
            chunks=chunks,
            embeddings=embeddings,
        )
        result = await conn.execute(
            "SELECT document_id::text, content, chunk_index, token_count "
            "FROM chunks WHERE document_id = %s ORDER BY chunk_index",
            (document_id,),
        )
        rows = await result.fetchall()

    assert rows == [
        (document_id, "chunk 0", 0, 10),
        (document_id, "chunk 1", 1, 12),
    ]


async def test_store_document_creates_embeddings_rows(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="docs/embeddings.md",
            file_hash="embed-hash",
            chunks=[_make_chunk(0), _make_chunk(1)],
            embeddings=[_make_embedding(0), _make_embedding(1)],
        )
        result = await conn.execute(
            "SELECT e.model, e.provider, e.vector "
            "FROM embeddings e "
            "JOIN chunks c ON c.id = e.chunk_id "
            "WHERE c.document_id = (SELECT id FROM documents WHERE source_path = %s) "
            "ORDER BY c.chunk_index",
            ("docs/embeddings.md",),
        )
        rows = await result.fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "voyage-3"
    assert rows[0][1] == "anthropic"
    assert len(rows[0][2]) == 1024
    assert rows[0][2][0] == 0.0
    assert rows[1][2][0] == 0.001


async def test_store_document_returns_document_id(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/uuid.md",
            file_hash="uuid-hash",
            chunks=[_make_chunk()],
            embeddings=[_make_embedding()],
        )
        result = await conn.execute(
            "SELECT id::text FROM documents WHERE source_path = %s",
            ("docs/uuid.md",),
        )
        row = await result.fetchone()

    assert row is not None
    assert document_id == row[0]
    assert str(uuid.UUID(document_id)) == document_id


async def test_store_document_reingest_increments_version(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/reingest.md",
            file_hash="hash-v1",
            chunks=[_make_chunk(0)],
            embeddings=[_make_embedding(0)],
        )
        await store_document(
            conn,
            source_path="docs/reingest.md",
            file_hash="hash-v2",
            chunks=[_make_chunk(1)],
            embeddings=[_make_embedding(1)],
        )

        document_result = await conn.execute(
            "SELECT current_version, file_hash FROM documents WHERE id = %s",
            (document_id,),
        )
        versions_result = await conn.execute(
            "SELECT version, content_hash FROM document_versions "
            "WHERE document_id = %s ORDER BY version",
            (document_id,),
        )
        document_row = await document_result.fetchone()
        version_rows = await versions_result.fetchall()

    assert document_row == (2, "hash-v1")  # file_hash must not be overwritten on re-ingest
    assert version_rows == [(1, "hash-v1"), (2, "hash-v2")]


async def test_store_document_reingest_preserves_old_chunks(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        document_id = await store_document(
            conn,
            source_path="docs/preserve.md",
            file_hash="hash-a",
            chunks=[_make_chunk(0), _make_chunk(1)],
            embeddings=[_make_embedding(0), _make_embedding(1)],
        )
        await store_document(
            conn,
            source_path="docs/preserve.md",
            file_hash="hash-b",
            chunks=[_make_chunk(2)],
            embeddings=[_make_embedding(2)],
        )
        index_result = await conn.execute(
            "SELECT chunk_index FROM chunks WHERE document_id = %s "
            "ORDER BY chunk_index",
            (document_id,),
        )
        index_rows = await index_result.fetchall()

        content_result = await conn.execute(
            "SELECT chunk_index, content, token_count FROM chunks "
            "WHERE document_id = %s ORDER BY chunk_index",
            (document_id,),
        )
        content_rows = await content_result.fetchall()

        embedding_result = await conn.execute(
            "SELECT COUNT(*) FROM embeddings e "
            "JOIN chunks c ON c.id = e.chunk_id "
            "WHERE c.document_id = %s",
            (document_id,),
        )
        embedding_count_row = await embedding_result.fetchone()

    assert index_rows == [(0,), (1,), (2,)]
    assert content_rows == [
        (0, "chunk 0", 10),
        (1, "chunk 1", 10),
        (2, "chunk 2", 10),
    ]
    assert embedding_count_row == (3,)


async def test_store_document_atomicity_on_failure(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        with pytest.raises(ValueError):
            await store_document(
                conn,
                source_path="docs/fail.md",
                file_hash="rollback-hash",
                chunks=[_make_chunk(0), _make_chunk(1)],
                embeddings=[_make_embedding(0)],  # length mismatch → zip strict=True raises mid-loop
            )
        result = await conn.execute(
            "SELECT COUNT(*) FROM documents WHERE source_path = %s",
            ("docs/fail.md",),
        )
        row = await result.fetchone()

    assert row == (0,)
