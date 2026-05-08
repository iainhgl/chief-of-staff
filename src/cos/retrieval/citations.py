"""Citation formatting helpers for retrieved chunks."""

import uuid
from dataclasses import dataclass


@dataclass
class CitedChunk:
    content: str
    source_document_id: str  # UUID-format string
    source_alias: str
    source_locator: str
    document_version_id: str
    chunk_index: int
    score: float

    def __post_init__(self) -> None:
        uuid.UUID(self.source_document_id)


CitedResults = list[CitedChunk]


@dataclass
class CitedResponse:
    answer: str | None
    citations: CitedResults


def format_citations(results: CitedResults) -> str:
    return "\n".join(
        f"[{index}] {chunk.source_alias} "
        f"(chunk {chunk.chunk_index}, score {chunk.score:.3f})"
        for index, chunk in enumerate(results, start=1)
    )


def prune_citations(
    results: CitedResults,
    max_chunks_per_source: int,
) -> CitedResults:
    seen: dict[str, int] = {}
    pruned: CitedResults = []
    for chunk in results:
        count = seen.get(chunk.source_locator, 0)
        if count < max_chunks_per_source:
            pruned.append(chunk)
            seen[chunk.source_locator] = count + 1
    return pruned


def _lineage_key(chunk: CitedChunk) -> str:
    """Return the most specific stable lineage identifier for a chunk.

    Prefers document_version_id when present; falls back to source_locator
    for legacy/backfilled records where version tracking is absent.
    """
    if chunk.document_version_id:
        return chunk.document_version_id
    return chunk.source_locator


def narrow_to_lineage(results: CitedResults) -> CitedResults:
    """Return only chunks that share the lineage of the highest-ranked chunk.

    Used for direct factual queries to prevent blending facts across sibling
    records.  Results must arrive sorted by descending score (as hybrid_search
    guarantees) so that results[0] is the best-matching chunk.
    """
    if not results:
        return []
    key = _lineage_key(results[0])
    return [chunk for chunk in results if _lineage_key(chunk) == key]
