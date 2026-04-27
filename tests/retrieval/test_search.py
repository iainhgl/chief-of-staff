from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.retrieval.citations import CitedChunk
from cos.retrieval.search import hybrid_search
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord


async def _store_search_document(
    conn: psycopg.AsyncConnection[tuple[object, ...]],
    *,
    source_path: str,
    content: str,
    vector: list[float],
) -> None:
    await store_document(
        conn,
        source_path=source_path,
        file_hash="abc123",
        chunks=[
            ChunkRecord(
                content=content,
                chunk_index=0,
                token_count=len(content.split()),
            )
        ],
        embeddings=[
            EmbeddingRecord(
                vector=vector,
                model="voyage-3",
                provider="anthropic",
            )
        ],
    )


@pytest.mark.asyncio
async def test_hybrid_search_empty_database_returns_empty_list(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        assert await hybrid_search("anything", conn, config) == []


@pytest.mark.asyncio
async def test_hybrid_search_keyword_match_returns_result(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    vector = [float(index) / 100 for index in range(1024)]

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_search_document(
            conn,
            source_path="/test/hr-framework.md",
            content="workforce segmentation framework",
            vector=vector,
        )

        results = await hybrid_search("segmentation", conn, config)

    assert len(results) == 1
    assert isinstance(results[0], CitedChunk)
    assert results[0].content == "workforce segmentation framework"
    assert results[0].source_document_id
    assert results[0].source_path == "/test/hr-framework.md"
    assert results[0].chunk_index == 0
    assert results[0].score > 0


@pytest.mark.asyncio
async def test_hybrid_search_result_has_correct_source_path(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    vector = [float(index) / 100 for index in range(1024)]

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_search_document(
            conn,
            source_path="/test/leadership-notes.md",
            content="succession planning priorities",
            vector=vector,
        )

        results = await hybrid_search("planning", conn, config)

    assert results[0].source_path == "/test/leadership-notes.md"


@pytest.mark.asyncio
async def test_hybrid_search_no_match_returns_empty_list(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    # Negative stored vector produces cosine similarity < 0 against mock_embed's
    # positive query vector, so the semantic score is filtered (score <= 0.0).
    # Combined with no keyword match, this guarantees an empty result.
    vector = [-(float(index) / 100) for index in range(1024)]

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_search_document(
            conn,
            source_path="/test/fantasy.md",
            content="dragons guard the mountain pass",
            vector=vector,
        )

        results = await hybrid_search(
            "machine learning best practices",
            conn,
            config,
        )

    assert results == []
