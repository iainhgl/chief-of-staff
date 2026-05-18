from cos.retrieval.citations import (
    CitedChunk,
    format_citations,
    narrow_to_lineage,
    prune_citations,
    select_document_first_anchors,
    select_synthesis_evidence,
)


def _make_chunk(alias: str = "/tmp/policies/leave.md") -> CitedChunk:
    return CitedChunk(
        content="Policy summary",
        source_document_id="4b7726d9-56f0-40f7-8f63-c3203bd2f0d0",
        source_alias=alias,
        source_locator=alias,
        document_version_id="",
        chunk_index=2,
        score=0.98765,
    )


def test_format_citations_empty_input_returns_empty_string() -> None:
    assert format_citations([]) == ""


def test_format_citations_single_result_contains_source_alias() -> None:
    result = _make_chunk("/tmp/policies/leave.md")

    formatted = format_citations([result])

    assert "/tmp/policies/leave.md" in formatted


def test_cited_chunk_has_all_required_fields() -> None:
    result = CitedChunk(
        content="Budget update",
        source_document_id="e3538c27-95cb-4d04-8a01-d78c31ad0fe2",
        source_alias="budget.md",
        source_locator="/tmp/finance/budget.md",
        document_version_id="",
        chunk_index=1,
        score=0.5,
    )

    assert result.content == "Budget update"
    assert isinstance(result.source_document_id, str)
    assert isinstance(result.source_alias, str)
    assert isinstance(result.source_locator, str)
    assert isinstance(result.document_version_id, str)
    assert isinstance(result.chunk_index, int)
    assert isinstance(result.score, float)


# ── Pruning tests (Story 6.13) ─────────────────────────────────────────────


def _make_scored_chunk(
    source_locator: str,
    score: float,
    chunk_index: int = 0,
) -> CitedChunk:
    return CitedChunk(
        content=f"content at {source_locator} chunk {chunk_index}",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_locator,
        source_locator=source_locator,
        document_version_id="",
        chunk_index=chunk_index,
        score=score,
    )


def test_prune_citations_limits_chunks_per_source() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
        _make_scored_chunk("loc://a", 0.7, 2),
    ]
    result = prune_citations(chunks, max_chunks_per_source=2)
    assert len(result) == 2


def test_prune_citations_keeps_highest_scoring_chunks_per_source() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
        _make_scored_chunk("loc://a", 0.3, 2),
    ]
    result = prune_citations(chunks, max_chunks_per_source=2)
    scores = [c.score for c in result]
    assert scores == [0.9, 0.8]


def test_prune_citations_preserves_chunks_under_limit() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
    ]
    result = prune_citations(chunks, max_chunks_per_source=3)
    assert len(result) == 2


def test_prune_citations_empty_input_returns_empty() -> None:
    result = prune_citations([], max_chunks_per_source=2)
    assert result == []


def test_prune_citations_multiple_sources_limited_independently() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://b", 0.85, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
        _make_scored_chunk("loc://b", 0.75, 1),
        _make_scored_chunk("loc://a", 0.5, 2),
    ]
    result = prune_citations(chunks, max_chunks_per_source=2)
    a_chunks = [c for c in result if c.source_locator == "loc://a"]
    b_chunks = [c for c in result if c.source_locator == "loc://b"]
    assert len(a_chunks) == 2
    assert len(b_chunks) == 2


def test_prune_citations_single_chunk_limit() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
    ]
    result = prune_citations(chunks, max_chunks_per_source=1)
    assert len(result) == 1
    assert result[0].score == 0.9


def test_prune_citations_preserves_interleaved_order() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://b", 0.85, 0),
        _make_scored_chunk("loc://a", 0.8, 1),
    ]
    result = prune_citations(chunks, max_chunks_per_source=2)
    assert result[0].source_locator == "loc://a"
    assert result[0].score == 0.9
    assert result[1].source_locator == "loc://b"
    assert result[2].source_locator == "loc://a"
    assert result[2].score == 0.8


# ── Evidence-selection tests (Story 7.3) ──────────────────────────────────────


def test_select_synthesis_evidence_preserves_candidates_by_default() -> None:
    chunks = [
        _make_scored_chunk("loc://a", 0.9, 0),
        _make_scored_chunk("loc://a", 0.55, 1),
        _make_scored_chunk("loc://b", 0.50, 0),
    ]
    result = select_synthesis_evidence(chunks)
    assert result == chunks


def test_select_synthesis_evidence_requires_two_lineages_for_multi_source_queries() -> None:
    chunks = [
        _make_versioned_chunk("loc://a", "ver-001", 0.9, 0),
        _make_versioned_chunk("loc://a", "ver-001", 0.8, 1),
    ]
    assert select_synthesis_evidence(chunks, require_multi_source=True) == []


def test_select_synthesis_evidence_keeps_multi_source_set_when_two_lineages_survive() -> None:
    chunks = [
        _make_versioned_chunk("loc://a", "ver-001", 0.9, 0),
        _make_versioned_chunk("loc://b", "ver-002", 0.7, 0),
    ]
    result = select_synthesis_evidence(chunks, require_multi_source=True)
    assert [chunk.source_locator for chunk in result] == ["loc://a", "loc://b"]


# ── Lineage narrowing tests (Story 6.14) ──────────────────────────────────────


def _make_versioned_chunk(
    source_locator: str,
    document_version_id: str,
    score: float,
    chunk_index: int = 0,
) -> CitedChunk:
    return CitedChunk(
        content=f"content from {source_locator}",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias=source_locator,
        source_locator=source_locator,
        document_version_id=document_version_id,
        chunk_index=chunk_index,
        score=score,
    )


def test_narrow_to_lineage_empty_input_returns_empty() -> None:
    assert narrow_to_lineage([]) == []


def test_narrow_to_lineage_single_chunk_returns_it() -> None:
    chunk = _make_versioned_chunk("loc://a", "ver-001", 0.9)
    result = narrow_to_lineage([chunk])
    assert result == [chunk]


def test_narrow_to_lineage_prefers_document_version_id_over_source_locator() -> None:
    # Two chunks share the same source_locator but different version_ids;
    # only the version_id of the best chunk should be the lineage key.
    best = _make_versioned_chunk("loc://a", "ver-001", 0.9, 0)
    sibling = _make_versioned_chunk("loc://a", "ver-002", 0.7, 0)
    result = narrow_to_lineage([best, sibling])
    assert len(result) == 1
    assert result[0].document_version_id == "ver-001"


def test_narrow_to_lineage_keeps_all_chunks_of_winning_version() -> None:
    chunk_a = _make_versioned_chunk("loc://x", "ver-001", 0.9, 0)
    chunk_b = _make_versioned_chunk("loc://x", "ver-001", 0.8, 1)
    other = _make_versioned_chunk("loc://y", "ver-002", 0.75, 0)
    result = narrow_to_lineage([chunk_a, chunk_b, other])
    assert len(result) == 2
    assert all(c.document_version_id == "ver-001" for c in result)


def test_narrow_to_lineage_excludes_sibling_lineages() -> None:
    best = _make_versioned_chunk("gmail://msg-001", "ver-aaa", 0.9)
    sibling_a = _make_versioned_chunk("/docs/policy.md", "ver-bbb", 0.8)
    sibling_b = _make_versioned_chunk("mcp://note-001", "ver-ccc", 0.7)
    result = narrow_to_lineage([best, sibling_a, sibling_b])
    assert len(result) == 1
    assert result[0].source_locator == "gmail://msg-001"


def test_narrow_to_lineage_falls_back_to_source_locator_when_no_version_id() -> None:
    # Legacy/backfilled chunks have empty document_version_id
    primary = _make_versioned_chunk("/docs/primary.md", "", 0.9)
    sibling = _make_versioned_chunk("/docs/sibling.md", "", 0.7)
    result = narrow_to_lineage([primary, sibling])
    assert len(result) == 1
    assert result[0].source_locator == "/docs/primary.md"


def test_narrow_to_lineage_legacy_multiple_chunks_same_locator_all_survive() -> None:
    chunk_a = _make_versioned_chunk("/docs/report.md", "", 0.9, 0)
    chunk_b = _make_versioned_chunk("/docs/report.md", "", 0.8, 1)
    sibling = _make_versioned_chunk("/docs/other.md", "", 0.7, 0)
    result = narrow_to_lineage([chunk_a, chunk_b, sibling])
    assert len(result) == 2
    assert all(c.source_locator == "/docs/report.md" for c in result)


# ── Document-first anchor selection tests (Story 7.4 review fixes) ──────────


def test_select_document_first_anchors_prefers_highest_aggregate_lineage() -> None:
    top_chunk = _make_versioned_chunk("loc://a", "ver-a", 0.95, 0)
    supported_a = _make_versioned_chunk("loc://b", "ver-b", 0.81, 0)
    supported_b = _make_versioned_chunk("loc://b", "ver-b", 0.80, 1)

    result = select_document_first_anchors([top_chunk, supported_a, supported_b])

    assert [chunk.document_version_id for chunk in result] == ["ver-b", "ver-b"]
    assert [chunk.chunk_index for chunk in result] == [0, 1]


def test_select_document_first_anchors_falls_back_to_source_locator_for_legacy_chunks() -> None:
    legacy_a = _make_versioned_chunk("loc://legacy-a", "", 0.91, 0)
    legacy_b0 = _make_versioned_chunk("loc://legacy-b", "", 0.60, 0)
    legacy_b1 = _make_versioned_chunk("loc://legacy-b", "", 0.59, 1)

    result = select_document_first_anchors([legacy_a, legacy_b0, legacy_b1])

    assert [chunk.source_locator for chunk in result] == ["loc://legacy-b", "loc://legacy-b"]
