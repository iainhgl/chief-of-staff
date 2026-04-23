import asyncio
import uuid
from datetime import timedelta
from pathlib import Path

import psycopg
from conftest import TEST_DSN, make_test_config

from cos.services.provenance import ProvenanceService
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord


def _chunk(index: int = 0) -> ChunkRecord:
    return ChunkRecord(content=f"chunk {index}", chunk_index=index, token_count=10)


def _embedding(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[float(index) / 1000 for _ in range(1024)],
        model="voyage-3",
        provider="anthropic",
    )


async def _insert_doc(
    source_path: str,
    file_hash: str = "abc123",
    chunks: int = 1,
) -> str:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        return await store_document(
            conn,
            source_path=source_path,
            file_hash=file_hash,
            chunks=[_chunk(i) for i in range(chunks)],
            embeddings=[_embedding(i) for i in range(chunks)],
        )


async def test_list_documents_empty(migrated_db: None, tmp_path: Path) -> None:
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert result == []


async def test_list_documents_returns_correct_fields(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    doc_id = await _insert_doc("docs/report.md", file_hash="abc123", chunks=2)
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert len(result) == 1
    document = result[0]
    assert document.id == doc_id
    assert document.source_path == "docs/report.md"
    assert document.ingested_at.utcoffset() == timedelta(0)
    assert document.current_version == 1
    assert document.chunk_count == 2


async def test_list_documents_chunk_count(migrated_db: None, tmp_path: Path) -> None:
    await _insert_doc("docs/chunks.md", chunks=3)
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert len(result) == 1
    assert result[0].chunk_count == 3


async def test_list_documents_ordered_most_recent_first(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    first_id = await _insert_doc("docs/older.md", file_hash="older")
    await asyncio.sleep(0.01)
    second_id = await _insert_doc("docs/newer.md", file_hash="newer")
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert [document.id for document in result] == [second_id, first_id]


async def test_list_document_versions_single(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    doc_id = await _insert_doc("docs/versioned.md", file_hash="hash-v1")
    service = ProvenanceService(make_test_config(tmp_path))

    versions = await service.list_document_versions(doc_id)

    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].file_hash == "hash-v1"
    assert versions[0].ingested_at.utcoffset() == timedelta(0)


async def test_list_document_versions_multiple(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    doc_id = await _insert_doc("docs/report.md", file_hash="hash-v1")
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="docs/report.md",
            file_hash="hash-v2",
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )
    service = ProvenanceService(make_test_config(tmp_path))

    versions = await service.list_document_versions(doc_id)

    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[0].file_hash == "hash-v1"
    assert versions[1].version_number == 2
    assert versions[1].file_hash == "hash-v2"


async def test_list_document_versions_unknown_id(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    service = ProvenanceService(make_test_config(tmp_path))

    versions = await service.list_document_versions(str(uuid.uuid4()))

    assert versions == []


async def test_list_document_versions_invalid_id_string(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    service = ProvenanceService(make_test_config(tmp_path))

    versions = await service.list_document_versions("missing-id")

    assert versions == []
