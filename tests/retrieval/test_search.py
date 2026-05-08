from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.retrieval.citations import CitedChunk
from cos.retrieval.search import _coerce_priority_weight, hybrid_search
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
    assert results[0].source_alias == "/test/hr-framework.md"
    assert results[0].source_locator == "/test/hr-framework.md"
    assert isinstance(results[0].document_version_id, str)
    assert results[0].chunk_index == 0
    assert results[0].score > 0


@pytest.mark.asyncio
async def test_hybrid_search_result_has_correct_source_alias(
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

    assert results[0].source_alias == "/test/leadership-notes.md"


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


def test_coerce_priority_weight_list_str_first_item_gets_max_boost() -> None:
    priorities = ["HR frameworks", "General documents"]

    weight = _coerce_priority_weight(priorities, "/docs/hr-frameworks.md")

    assert weight == pytest.approx(2.0)


def test_coerce_priority_weight_list_str_higher_rank_beats_lower_rank() -> None:
    priorities = ["HR frameworks", "General documents"]

    hr_weight = _coerce_priority_weight(priorities, "/hr-frameworks.md")
    general_weight = _coerce_priority_weight(priorities, "/general-notes.md")

    assert hr_weight > general_weight


def test_coerce_priority_weight_list_str_no_match_returns_one() -> None:
    priorities = ["HR frameworks"]

    weight = _coerce_priority_weight(priorities, "/docs/zzz-unrelated.md")

    assert weight == pytest.approx(1.0)


def test_coerce_priority_weight_list_str_first_match_wins() -> None:
    priorities = ["HR frameworks", "HR documents"]

    weight = _coerce_priority_weight(priorities, "/hr-frameworks-and-documents.md")

    assert weight == pytest.approx(2.0)


# ── Threshold filtering tests (Story 6.13) ──────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_search_high_min_score_filters_all_results(
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
            source_path="/test/doc.md",
            content="workforce segmentation framework",
            vector=vector,
        )
        # max RRF score is ~0.033; setting min_score=1.0 filters everything
        results = await hybrid_search("segmentation", conn, config, min_score=1.0)

    assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_zero_min_score_preserves_existing_behavior(
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
        results = await hybrid_search("segmentation", conn, config, min_score=0.0)

    assert len(results) == 1


@pytest.mark.asyncio
async def test_hybrid_search_role_priority_cannot_resurrect_filtered_chunk(
    migrated_db: None,
    mock_embed: None,
    tmp_path: Path,
) -> None:
    del migrated_db, mock_embed
    config = make_test_config(tmp_path)
    vector = [float(index) / 100 for index in range(1024)]
    role_pack = type(
        "RolePack",
        (),
        {"retrieval_priorities": {"workforce": 9999.0}, "tone": ""},
    )()

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await _store_search_document(
            conn,
            source_path="workforce-planning.md",
            content="workforce planning strategy",
            vector=vector,
        )
        # min_score=1.0 means raw RRF (never exceeds ~0.033) is always below threshold;
        # role priority weight of 9999x must not resurrect the filtered chunk
        results = await hybrid_search(
            "workforce planning",
            conn,
            config,
            role_pack=role_pack,
            min_score=1.0,
        )

    assert results == []


def _mock_result(rows: list[tuple[object, ...]]) -> MagicMock:
    result = MagicMock()
    result.fetchall = AsyncMock(return_value=rows)
    return result


@pytest.mark.asyncio
async def test_hybrid_search_overfetches_before_pruning_to_backfill_other_sources(
    tmp_path: Path,
    mock_embed: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del mock_embed
    config = make_test_config(tmp_path)
    conn = MagicMock()
    register_vector = AsyncMock()
    monkeypatch.setattr("cos.retrieval.search.register_vector_async", register_vector)

    document_a = "10000000-0000-0000-0000-000000000001"
    document_b = "10000000-0000-0000-0000-000000000002"
    document_c = "10000000-0000-0000-0000-000000000003"
    version_a = "00000000-0000-0000-0000-000000000001"
    version_b = "00000000-0000-0000-0000-000000000002"
    version_c = "00000000-0000-0000-0000-000000000003"
    conn.execute = AsyncMock(
        side_effect=[
            _mock_result(
                [
                    ("chunk-a0", document_a, 0, "A0", version_a, 10.0),
                    ("chunk-a1", document_a, 1, "A1", version_a, 9.0),
                    ("chunk-b0", document_b, 0, "B0", version_b, 8.0),
                    ("chunk-c0", document_c, 0, "C0", version_c, 7.0),
                ]
            ),
            _mock_result([]),
            _mock_result(
                [
                    (version_a, "source-a", "loc://a"),
                    (version_b, "source-b", "loc://b"),
                    (version_c, "source-c", "loc://c"),
                ]
            ),
            _mock_result([]),
        ]
    )

    results = await hybrid_search(
        "topic",
        conn,
        config,
        top_k=2,
        max_chunks_per_source=1,
    )

    assert [chunk.source_locator for chunk in results] == ["loc://a", "loc://b"]
    keyword_limit = conn.execute.await_args_list[0].args[1][2]
    semantic_limit = conn.execute.await_args_list[1].args[1][1]
    assert keyword_limit == 4
    assert semantic_limit == 4


@pytest.mark.asyncio
async def test_hybrid_search_filters_mixed_source_hits_below_threshold(
    tmp_path: Path,
    mock_embed: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del mock_embed
    config = make_test_config(tmp_path)
    conn = MagicMock()
    monkeypatch.setattr("cos.retrieval.search.register_vector_async", AsyncMock())

    document_a = "10000000-0000-0000-0000-000000000011"
    document_b = "10000000-0000-0000-0000-000000000012"
    version_a = "00000000-0000-0000-0000-000000000011"
    version_b = "00000000-0000-0000-0000-000000000012"
    conn.execute = AsyncMock(
        side_effect=[
            _mock_result(
                [
                    ("chunk-a", document_a, 0, "A content", version_a, 1.0),
                ]
            ),
            _mock_result(
                [
                    ("chunk-a", document_a, 0, "A content", version_a, 0.9),
                    ("chunk-b", document_b, 0, "B content", version_b, 0.8),
                ]
            ),
            _mock_result(
                [
                    (version_a, "source-a", "loc://a"),
                    (version_b, "source-b", "loc://b"),
                ]
            ),
            _mock_result([]),
        ]
    )

    results = await hybrid_search(
        "topic",
        conn,
        config,
        min_score=0.02,
        max_chunks_per_source=2,
    )

    assert [chunk.source_locator for chunk in results] == ["loc://a"]


@pytest.mark.asyncio
async def test_hybrid_search_breaks_equal_score_ties_deterministically_before_pruning(
    tmp_path: Path,
    mock_embed: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del mock_embed
    config = make_test_config(tmp_path)
    conn = MagicMock()
    monkeypatch.setattr("cos.retrieval.search.register_vector_async", AsyncMock())

    document_a = "10000000-0000-0000-0000-000000000021"
    version_a = "00000000-0000-0000-0000-000000000021"
    conn.execute = AsyncMock(
        side_effect=[
            _mock_result(
                [
                    ("chunk-a1", document_a, 1, "A1 content", version_a, 1.0),
                ]
            ),
            _mock_result(
                [
                    ("chunk-a0", document_a, 0, "A0 content", version_a, 0.9),
                ]
            ),
            _mock_result(
                [
                    (version_a, "source-a", "loc://a"),
                ]
            ),
            _mock_result([]),
        ]
    )

    results = await hybrid_search(
        "topic",
        conn,
        config,
        top_k=1,
        max_chunks_per_source=1,
    )

    assert len(results) == 1
    assert results[0].chunk_index == 0
