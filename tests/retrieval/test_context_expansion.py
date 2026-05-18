"""Unit tests for bounded context expansion."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cos.retrieval.citations import CitedChunk
from cos.retrieval.context_expansion import expand_bounded_context

_DOC_ID = "12345678-1234-1234-1234-123456789012"
_DOC_VERSION_ID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
_LOCATOR = "local://test-doc"
_ALIAS = "local://test-doc"


def _chunk(chunk_index: int, score: float = 0.9) -> CitedChunk:
    return CitedChunk(
        content=f"chunk content {chunk_index}",
        source_document_id=_DOC_ID,
        source_alias=_ALIAS,
        source_locator=_LOCATOR,
        document_version_id=_DOC_VERSION_ID,
        chunk_index=chunk_index,
        score=score,
    )


def _make_conn(rows: list[tuple[int, str]]) -> AsyncMock:
    """Return an AsyncMock connection whose execute().fetchall() returns rows."""
    fetch_mock = AsyncMock(return_value=rows)
    result_mock = MagicMock()
    result_mock.fetchall = fetch_mock
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=result_mock)
    return conn


# ── Empty input ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_anchors_returns_empty_expanded_context() -> None:
    conn = _make_conn([])
    result = await expand_bounded_context(conn, [])
    assert result.synthesis_chunks == []
    assert result.evidence_chunks == []
    conn.execute.assert_not_called()


# ── No document_version_id (legacy) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_anchor_without_version_id_falls_back_to_document_id() -> None:
    anchor = CitedChunk(
        content="content",
        source_document_id=_DOC_ID,
        source_alias=_ALIAS,
        source_locator=_LOCATOR,
        document_version_id="",
        chunk_index=2,
        score=0.9,
    )
    conn = _make_conn([(1, "content 1"), (2, "content 2"), (3, "content 3")])
    result = await expand_bounded_context(conn, [anchor])

    assert [chunk.chunk_index for chunk in result.synthesis_chunks] == [1, 2, 3]
    assert result.evidence_chunks == [anchor]
    sql, params = conn.execute.await_args.args
    assert "WHERE document_id = %s::uuid" in sql
    assert params[0] == _DOC_ID


# ── Basic expansion ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anchor_at_chunk_1_expands_to_include_chunks_0_and_2() -> None:
    anchor = _chunk(1)
    db_rows = [
        (0, "chunk content 0"),
        (1, "chunk content 1"),
        (2, "chunk content 2"),
    ]
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor], window=1)

    assert len(result.synthesis_chunks) == 3
    assert [c.chunk_index for c in result.synthesis_chunks] == [0, 1, 2]
    # Anchor (chunk 1) keeps its original score; neighbours have score=0.0
    assert result.synthesis_chunks[0].score == 0.0  # chunk 0 is a neighbour
    assert result.synthesis_chunks[1].score == 0.9  # chunk 1 is the anchor
    assert result.synthesis_chunks[2].score == 0.0  # chunk 2 is a neighbour


@pytest.mark.asyncio
async def test_evidence_chunks_contains_only_anchors_not_neighbours() -> None:
    anchor = _chunk(1)
    db_rows = [(0, "content 0"), (1, "content 1"), (2, "content 2")]
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor], window=1)

    assert result.evidence_chunks == [anchor]
    assert len(result.synthesis_chunks) == 3


@pytest.mark.asyncio
async def test_anchor_at_chunk_0_does_not_request_negative_indices() -> None:
    anchor = _chunk(0)
    db_rows = [(0, "content 0"), (1, "content 1")]
    conn = _make_conn(db_rows)
    await expand_bounded_context(conn, [anchor], window=1)

    # Verify query was called with min_idx=0 (not negative)
    call_args = conn.execute.await_args
    params = call_args[0][1]  # positional args of execute call: (sql, params)
    assert params[1] == 0  # min_idx
    assert params[2] == 1  # max_idx (0 + window=1)


# ── No neighbours available ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_anchor_in_db_returns_anchor_as_synthesis() -> None:
    anchor = _chunk(5)
    db_rows = [(5, "chunk content 5")]
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor], window=1)

    assert len(result.synthesis_chunks) == 1
    assert result.synthesis_chunks[0] is anchor
    assert result.evidence_chunks == [anchor]


# ── Max expanded cap ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_max_expanded_cap_truncates_synthesis_chunks() -> None:
    anchor = _chunk(5)
    db_rows = [(i, f"content {i}") for i in range(3, 9)]  # 6 chunks
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor], window=3, max_expanded=4)

    assert len(result.synthesis_chunks) == 4
    assert len(result.evidence_chunks) == 1


# ── Multiple anchors ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_anchors_from_same_lineage_merged_correctly() -> None:
    anchor_a = _chunk(1)
    anchor_b = _chunk(3)
    db_rows = [(i, f"content {i}") for i in range(0, 5)]  # chunks 0–4
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor_a, anchor_b], window=1)

    indices = [c.chunk_index for c in result.synthesis_chunks]
    assert sorted(indices) == indices  # ordered by chunk_index
    # evidence = only the two anchors
    evidence_indices = {c.chunk_index for c in result.evidence_chunks}
    assert evidence_indices == {1, 3}


@pytest.mark.asyncio
async def test_distant_anchors_query_only_local_windows() -> None:
    anchor_a = _chunk(1)
    anchor_b = _chunk(10)
    conn = _make_conn(
        [
            (0, "content 0"),
            (1, "content 1"),
            (2, "content 2"),
            (9, "content 9"),
            (10, "content 10"),
            (11, "content 11"),
        ]
    )

    await expand_bounded_context(conn, [anchor_a, anchor_b], window=1)

    _, params = conn.execute.await_args.args
    assert params == (_DOC_VERSION_ID, 0, 2, 9, 11)


@pytest.mark.asyncio
async def test_max_expanded_preserves_all_selected_anchors() -> None:
    anchor_a = _chunk(1, score=0.9)
    anchor_b = _chunk(5, score=0.8)
    db_rows = [
        (0, "content 0"),
        (1, "content 1"),
        (2, "content 2"),
        (4, "content 4"),
        (5, "content 5"),
        (6, "content 6"),
    ]
    conn = _make_conn(db_rows)

    result = await expand_bounded_context(
        conn,
        [anchor_a, anchor_b],
        window=1,
        max_expanded=4,
    )

    synthesis_indices = [chunk.chunk_index for chunk in result.synthesis_chunks]
    assert 1 in synthesis_indices
    assert 5 in synthesis_indices
    assert len(synthesis_indices) == 4


# ── Neighbour chunk metadata ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_neighbour_chunk_inherits_lineage_metadata_from_anchor() -> None:
    anchor = _chunk(2)
    db_rows = [(1, "neighbour content"), (2, "anchor content")]
    conn = _make_conn(db_rows)
    result = await expand_bounded_context(conn, [anchor], window=1)

    neighbour = next(c for c in result.synthesis_chunks if c.chunk_index == 1)
    assert neighbour.source_document_id == _DOC_ID
    assert neighbour.source_alias == _ALIAS
    assert neighbour.source_locator == _LOCATOR
    assert neighbour.document_version_id == _DOC_VERSION_ID
    assert neighbour.content == "neighbour content"
