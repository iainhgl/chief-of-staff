from cos.retrieval.citations import CitedChunk, format_citations, prune_citations


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
