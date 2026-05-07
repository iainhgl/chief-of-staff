from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.ingestion.embedder import EmbeddingResult
from cos.retrieval.near_duplicate import find_near_duplicate
from cos.store.db import store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord


def _make_chunk(
    content: str, vector: list[float]
) -> tuple[ChunkRecord, EmbeddingRecord]:
    return (
        ChunkRecord(content=content, chunk_index=0, token_count=len(content.split())),
        EmbeddingRecord(vector=vector, model="voyage-3", provider="anthropic"),
    )


async def _store_note(
    conn: psycopg.AsyncConnection,
    *,
    source_locator: str,
    source_alias: str,
    content: str,
    vector: list[float],
) -> str:
    chunk, embedding = _make_chunk(content, vector)
    return await store_document_canonical(
        conn,
        source_path=source_locator,
        sha256=__import__("hashlib").sha256(content.encode()).hexdigest(),
        byte_size=len(content.encode()),
        source_type="mcp_note",
        source_locator=source_locator,
        source_alias=source_alias,
        chunks=[chunk],
        embeddings=[embedding],
    )


@pytest.fixture
def mock_near_dup_embed(monkeypatch: pytest.MonkeyPatch):
    """Patches near_duplicate embed to return the vector of the first chunk text."""
    _vector_map: dict[str, list[float]] = {}

    def register(text: str, vector: list[float]) -> None:
        _vector_map[text] = vector

    async def _fake_embed(
        chunks: list[str],
        provider: str,
        model: str,
        api_key: str,
        transport=None,
    ) -> list[EmbeddingResult]:
        del api_key, transport
        results = []
        for text in chunks:
            vec = _vector_map.get(text, [0.5] * 1024)
            results.append(EmbeddingResult(vector=vec, model=model, provider=provider))
        return results

    monkeypatch.setattr("cos.retrieval.near_duplicate.embed", _fake_embed)
    return register


async def test_find_near_duplicate_empty_db_returns_none(
    migrated_db: None,
    tmp_path: Path,
    mock_near_dup_embed,
) -> None:
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await find_near_duplicate(
            text="Some note content.",
            exclude_document_id="00000000-0000-0000-0000-000000000000",
            conn=conn,
            config=config,
            threshold=0.95,
        )
    assert result is None


async def test_find_near_duplicate_above_threshold_returns_warning(
    migrated_db: None,
    tmp_path: Path,
    mock_near_dup_embed,
) -> None:
    high_sim_vector = [1.0] + [0.0] * 1023
    config = make_test_config(tmp_path)
    mock_near_dup_embed("Query note text.", high_sim_vector)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_note(
            conn,
            source_locator="mcp_note://mcp/existing-001",
            source_alias="existing-note.md",
            content="Existing note content.",
            vector=high_sim_vector,
        )
        await conn.commit()

        result = await find_near_duplicate(
            text="Query note text.",
            exclude_document_id="00000000-0000-0000-0000-000000000001",
            conn=conn,
            config=config,
            threshold=0.95,
        )

    assert result is not None
    assert result["source_alias"] == "existing-note.md"
    assert float(result["similarity"]) >= 0.95


async def test_find_near_duplicate_below_threshold_returns_none(
    migrated_db: None,
    tmp_path: Path,
    mock_near_dup_embed,
) -> None:
    low_sim_vector = [1.0] + [0.0] * 1023
    query_vector = [0.0, 1.0] + [0.0] * 1022  # orthogonal → similarity ≈ 0
    config = make_test_config(tmp_path)
    mock_near_dup_embed("Orthogonal query.", query_vector)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_note(
            conn,
            source_locator="mcp_note://mcp/existing-002",
            source_alias="dissimilar-note.md",
            content="Dissimilar existing content.",
            vector=low_sim_vector,
        )
        await conn.commit()

        result = await find_near_duplicate(
            text="Orthogonal query.",
            exclude_document_id="00000000-0000-0000-0000-000000000002",
            conn=conn,
            config=config,
            threshold=0.95,
        )

    assert result is None


async def test_find_near_duplicate_excludes_own_document(
    migrated_db: None,
    tmp_path: Path,
    mock_near_dup_embed,
) -> None:
    identical_vector = [1.0] + [0.0] * 1023
    config = make_test_config(tmp_path)
    mock_near_dup_embed("The new note text.", identical_vector)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        own_doc_id = await _store_note(
            conn,
            source_locator="mcp_note://mcp/own-doc-001",
            source_alias="own-note.md",
            content="The new note text.",
            vector=identical_vector,
        )
        await conn.commit()

        result = await find_near_duplicate(
            text="The new note text.",
            exclude_document_id=own_doc_id,
            conn=conn,
            config=config,
            threshold=0.95,
        )

    assert result is None


async def test_find_near_duplicate_no_api_key_returns_none(
    migrated_db: None,
    tmp_path: Path,
) -> None:

    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={"embedding": config.embedding.model_copy(update={"api_key": None})}
    )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await find_near_duplicate(
            text="Any text.",
            exclude_document_id="00000000-0000-0000-0000-000000000000",
            conn=conn,
            config=config,
            threshold=0.95,
        )

    assert result is None
