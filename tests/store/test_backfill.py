from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN

from cos.store.db import (
    backfill_legacy_documents,
    store_document,
    store_document_canonical,
)
from cos.store.models import ChunkRecord, EmbeddingRecord


def _chunk(index: int = 0) -> ChunkRecord:
    return ChunkRecord(content=f"chunk {index}", chunk_index=index, token_count=10)


def _embedding(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[(index * 0.001) + (dimension / 1000) for dimension in range(1024)],
        model="voyage-3",
        provider="anthropic",
    )


async def _document_version_id_for(
    conn: psycopg.AsyncConnection[object],
    source_path: str,
    version: int,
) -> str:
    result = await conn.execute(
        "SELECT dv.id::text "
        "FROM document_versions dv "
        "JOIN documents d ON d.id = dv.document_id "
        "WHERE d.source_path = %s AND dv.version = %s",
        (source_path, version),
    )
    row = await result.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.asyncio
async def test_backfill_populates_content_blobs_for_legacy_documents(
    migrated_db: None,
) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/notes.md",
            file_hash="a" * 64,
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )

        result = await backfill_legacy_documents(conn)
        rows = await (
            await conn.execute("SELECT sha256, byte_size FROM content_blobs")
        ).fetchall()

    assert result.backfilled == 1
    assert result.already_canonical == 0
    assert rows == [("a" * 64, 0)]


@pytest.mark.asyncio
async def test_backfill_populates_sources_for_legacy_documents(
    migrated_db: None,
) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/report.pdf",
            file_hash="b" * 64,
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )

        await backfill_legacy_documents(conn)
        rows = await (
            await conn.execute(
                "SELECT source_type, source_locator, source_alias FROM sources"
            )
        ).fetchall()

    assert rows == [("file", "/data/report.pdf", "report.pdf")]


@pytest.mark.asyncio
async def test_backfill_populates_source_versions_for_legacy_documents(
    migrated_db: None,
) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/brief.md",
            file_hash="c" * 64,
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )

        await backfill_legacy_documents(conn)
        row = await (
            await conn.execute(
                "SELECT s.source_locator, dv.content_hash, cb.sha256 "
                "FROM source_versions sv "
                "JOIN sources s ON s.id = sv.source_id "
                "JOIN document_versions dv ON dv.id = sv.document_version_id "
                "JOIN content_blobs cb ON cb.id = sv.content_blob_id"
            )
        ).fetchone()

    assert row == ("/data/brief.md", "c" * 64, "c" * 64)


@pytest.mark.asyncio
async def test_backfill_links_chunks_to_document_version(migrated_db: None) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/guide.md",
            file_hash="d" * 64,
            chunks=[_chunk(0), _chunk(1)],
            embeddings=[_embedding(0), _embedding(1)],
        )

        await backfill_legacy_documents(conn)
        null_count_row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE document_version_id IS NULL"
            )
        ).fetchone()

    assert null_count_row == (0,)


@pytest.mark.asyncio
async def test_backfill_is_idempotent(migrated_db: None) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/memo.md",
            file_hash="e" * 64,
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )

        first = await backfill_legacy_documents(conn)
        second = await backfill_legacy_documents(conn)
        counts = await (
            await conn.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM content_blobs), "
                "(SELECT COUNT(*) FROM sources), "
                "(SELECT COUNT(*) FROM source_versions)"
            )
        ).fetchone()

    assert first.backfilled == 1
    assert first.already_canonical == 0
    assert second.backfilled == 0
    assert second.already_canonical == 1
    assert counts == (1, 1, 1)


@pytest.mark.asyncio
async def test_backfill_does_not_touch_canonical_documents(
    migrated_db: None,
) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        source_path = "/canonical/doc.md"
        await store_document_canonical(
            conn,
            source_path=source_path,
            sha256="f" * 64,
            byte_size=512,
            source_type="file",
            source_locator=source_path,
            source_alias=Path(source_path).name,
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )

        result = await backfill_legacy_documents(conn)
        counts = await (
            await conn.execute(
                "SELECT "
                "(SELECT COUNT(*) FROM content_blobs), "
                "(SELECT COUNT(*) FROM sources), "
                "(SELECT COUNT(*) FROM source_versions)"
            )
        ).fetchone()

    assert result.backfilled == 0
    assert result.already_canonical == 1
    assert counts == (1, 1, 1)


@pytest.mark.asyncio
async def test_backfill_multi_version_document(migrated_db: None) -> None:
    del migrated_db

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        source_path = "/data/history.md"
        await store_document(
            conn,
            source_path=source_path,
            file_hash="1" * 64,
            chunks=[_chunk(0)],
            embeddings=[_embedding(0)],
        )
        await store_document(
            conn,
            source_path=source_path,
            file_hash="2" * 64,
            chunks=[_chunk(1)],
            embeddings=[_embedding(1)],
        )

        result = await backfill_legacy_documents(conn)
        version_rows = await (
            await conn.execute(
                "SELECT version, content_hash, content_blob_id IS NOT NULL "
                "FROM document_versions dv "
                "JOIN documents d ON d.id = dv.document_id "
                "WHERE d.source_path = %s "
                "ORDER BY version",
                (source_path,),
            )
        ).fetchall()
        source_version_count_row = await (
            await conn.execute(
                "SELECT COUNT(*) "
                "FROM source_versions sv "
                "JOIN sources s ON s.id = sv.source_id "
                "WHERE s.source_locator = %s",
                (source_path,),
            )
        ).fetchone()
        current_document_version_id = await _document_version_id_for(
            conn,
            source_path,
            2,
        )
        chunk_rows = await (
            await conn.execute(
                "SELECT chunk_index, document_version_id::text "
                "FROM chunks c "
                "JOIN documents d ON d.id = c.document_id "
                "WHERE d.source_path = %s",
                (source_path,),
            )
        ).fetchall()

    assert result.backfilled == 1
    assert result.already_canonical == 0
    assert version_rows == [
        (1, "1" * 64, True),
        (2, "2" * 64, True),
    ]
    assert source_version_count_row == (2,)
    assert chunk_rows == [(1, current_document_version_id)]
