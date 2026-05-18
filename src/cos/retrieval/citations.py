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
_MIN_MULTI_SOURCE_LINEAGES = 2


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


def select_document_first_anchors(results: CitedResults) -> CitedResults:
    """Rank lineages first, then return all retrieved chunks from the winner.

    For bounded, document-centric questions we want the winning document to be
    chosen based on the full set of retrieved support, not just whichever
    individual chunk happened to rank first.
    """
    if not results:
        return []

    grouped: dict[str, list[tuple[int, CitedChunk]]] = {}
    for rank, chunk in enumerate(results):
        grouped.setdefault(_lineage_key(chunk), []).append((rank, chunk))

    def _document_rank_key(item: tuple[str, list[tuple[int, CitedChunk]]]) -> tuple:
        lineage_key, ranked_chunks = item
        chunks = [chunk for _, chunk in ranked_chunks]
        best_score = max(chunk.score for chunk in chunks)
        total_score = sum(chunk.score for chunk in chunks)
        first_rank = min(rank for rank, _ in ranked_chunks)
        return (-total_score, -best_score, first_rank, lineage_key)

    _, winning_ranked_chunks = min(grouped.items(), key=_document_rank_key)
    return [
        chunk
        for _, chunk in sorted(winning_ranked_chunks, key=lambda ranked: ranked[0])
    ]


def select_synthesis_evidence(
    candidates: CitedResults,
    *,
    require_multi_source: bool = False,
) -> CitedResults:
    """Return the subset of candidates eligible to be passed to synthesis.

    This is the explicit evidence-selection boundary: every chunk that enters
    here becomes both the LLM context and the returned citations.  Chunks that
    do not survive must never reappear in either place.

    Story 6.13 remains responsible for thresholding and pruning the bounded
    retrieval set. Story 7.3 makes the final synthesis boundary explicit and,
    for prompts that explicitly request multi-source synthesis, requires the
    surviving evidence to span at least two distinct lineages.
    """
    evidence = list(candidates)
    if require_multi_source:
        lineages = {_lineage_key(chunk) for chunk in evidence}
        if len(lineages) < _MIN_MULTI_SOURCE_LINEAGES:
            return []
    return evidence
