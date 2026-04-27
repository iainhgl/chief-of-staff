from cos.retrieval.citations import CitedChunk, format_citations


def test_format_citations_empty_input_returns_empty_string() -> None:
    assert format_citations([]) == ""


def test_format_citations_single_result_contains_source_path() -> None:
    result = CitedChunk(
        content="Policy summary",
        source_document_id="4b7726d9-56f0-40f7-8f63-c3203bd2f0d0",
        source_path="/tmp/policies/leave.md",
        chunk_index=2,
        score=0.98765,
    )

    formatted = format_citations([result])

    assert "/tmp/policies/leave.md" in formatted


def test_cited_chunk_has_all_required_fields() -> None:
    result = CitedChunk(
        content="Budget update",
        source_document_id="e3538c27-95cb-4d04-8a01-d78c31ad0fe2",
        source_path="/tmp/finance/budget.md",
        chunk_index=1,
        score=0.5,
    )

    assert result.content == "Budget update"
    assert isinstance(result.source_document_id, str)
    assert isinstance(result.source_path, str)
    assert isinstance(result.chunk_index, int)
    assert isinstance(result.score, float)
