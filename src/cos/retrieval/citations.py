"""Citation formatting helpers for retrieved chunks."""

import re
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
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "all",
    "across",
    "about",
    "are",
    "as",
    "at",
    "be",
    "by",
    "company",
    "current",
    "describe",
    "described",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "say",
    "the",
    "their",
    "this",
    "to",
    "what",
    "when",
    "with",
}
_SYNONYMS = {
    "attrition": "turnover",
    "briefing": "brief",
    "conclude": "conclusion",
    "concluded": "conclusion",
    "concludes": "conclusion",
    "days": "day",
    "effective": "effect",
    "effectively": "effect",
    "employees": "employee",
    "entitlement": "leave",
    "entitlements": "leave",
    "full-time": "fulltime",
    "holiday": "leave",
    "holidays": "leave",
    "permanent": "fulltime",
    "staff": "employee",
    "summarise": "summarize",
    "summarised": "summarize",
    "summarising": "summarize",
    "updated": "update",
}


@dataclass(frozen=True)
class _RankedLineages:
    items: list[tuple[str, list[tuple[int, CitedChunk]], int, int]]
    max_total_overlap: int


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


def _normalized_query_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _TOKEN_PATTERN.findall(text.lower()):
        token = _SYNONYMS.get(raw, raw)
        if token in _STOPWORDS:
            continue
        terms.add(token)
    return terms


def _chunk_terms(chunk: CitedChunk) -> set[str]:
    return _normalized_query_terms(chunk.content)


def _source_priority(chunk: CitedChunk) -> int:
    locator = chunk.source_locator
    if locator.startswith("local://"):
        return 0
    if locator.startswith("mcp://"):
        return 1
    if locator.startswith("calendar://"):
        return 2
    if locator.startswith("gmail://"):
        return 3
    return 4


def _query_mentions_connector(text: str) -> bool:
    lowered = text.lower()
    return any(
        signal in lowered
        for signal in ("email", "gmail", "message", "calendar", "event", "note", "mcp")
    )


def _minimum_match_count(query_terms: set[str], *, strict_matching: bool) -> int:
    if not strict_matching or not query_terms:
        return 0
    return 2 if len(query_terms) >= 3 else 1


def _ranked_chunks_by_lineage(
    results: CitedResults,
) -> dict[str, list[tuple[int, CitedChunk]]]:
    grouped: dict[str, list[tuple[int, CitedChunk]]] = {}
    for rank, chunk in enumerate(results):
        grouped.setdefault(_lineage_key(chunk), []).append((rank, chunk))
    return grouped


def _lineage_overlap(
    ranked_chunks: list[tuple[int, CitedChunk]],
    query_terms: set[str],
) -> tuple[int, int]:
    if not query_terms:
        return (0, 0)
    chunk_term_sets = [_chunk_terms(chunk) for _, chunk in ranked_chunks]
    union_terms: set[str] = set()
    for term_set in chunk_term_sets:
        union_terms.update(term_set)
    total_overlap = len(query_terms & union_terms)
    best_overlap = max(
        (len(query_terms & term_set) for term_set in chunk_term_sets),
        default=0,
    )
    return total_overlap, best_overlap


def _best_ranked_chunk_for_query(
    ranked_chunks: list[tuple[int, CitedChunk]],
    query_terms: set[str],
) -> CitedChunk:
    _, chunk = max(
        ranked_chunks,
        key=lambda ranked: (
            len(query_terms & _chunk_terms(ranked[1])),
            ranked[1].score,
            -ranked[0],
        ),
    )
    return chunk


def _legacy_document_first_anchors(results: CitedResults) -> CitedResults:
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


def _query_ranked_lineages(
    results: CitedResults,
    query_text: str,
    *,
    strict_matching: bool,
    prefer_local_when_unspecified: bool,
) -> _RankedLineages:
    query_terms = _normalized_query_terms(query_text)
    minimum_match_count = _minimum_match_count(
        query_terms,
        strict_matching=strict_matching,
    )
    connector_explicit = _query_mentions_connector(query_text)
    overlaps: list[tuple[str, list[tuple[int, CitedChunk]], int, int]] = []
    for lineage_key, ranked_chunks in _ranked_chunks_by_lineage(results).items():
        total_overlap, best_overlap = _lineage_overlap(ranked_chunks, query_terms)
        overlaps.append((lineage_key, ranked_chunks, total_overlap, best_overlap))

    max_total_overlap = max(
        (total_overlap for _, _, total_overlap, _ in overlaps),
        default=0,
    )

    ranked = [
        item for item in overlaps if item[2] >= minimum_match_count
    ]

    def _lineage_rank_key(
        item: tuple[str, list[tuple[int, CitedChunk]], int, int],
    ) -> tuple:
        lineage_key, ranked_chunks, total_overlap, best_overlap = item
        chunks = [chunk for _, chunk in ranked_chunks]
        best_score = max(chunk.score for chunk in chunks)
        total_score = sum(chunk.score for chunk in chunks)
        first_rank = min(rank for rank, _ in ranked_chunks)
        source_priority = _source_priority(chunks[0])
        adjusted_overlap = total_overlap
        if (
            prefer_local_when_unspecified
            and not connector_explicit
            and source_priority == 0
            and total_overlap > 0
        ):
            adjusted_overlap += 1
        source_bias = (
            -source_priority
            if prefer_local_when_unspecified and not connector_explicit
            else 0
        )
        return (
            adjusted_overlap,
            source_bias,
            total_overlap,
            best_overlap,
            best_score,
            total_score,
            -first_rank,
            lineage_key,
        )

    ranked.sort(key=_lineage_rank_key, reverse=True)
    return _RankedLineages(items=ranked, max_total_overlap=max_total_overlap)


def narrow_to_lineage(
    results: CitedResults,
    *,
    query_text: str | None = None,
    strict_matching: bool = False,
) -> CitedResults:
    """Return only chunks that share the lineage of the highest-ranked chunk.

    Used for direct factual queries to prevent blending facts across sibling
    records.  Results must arrive sorted by descending score (as hybrid_search
    guarantees) so that results[0] is the best-matching chunk.
    """
    if not results:
        return []
    if query_text is not None:
        ranked = _query_ranked_lineages(
            results,
            query_text,
            strict_matching=strict_matching,
            prefer_local_when_unspecified=True,
        )
        if not ranked.items:
            if strict_matching and ranked.max_total_overlap == 0:
                key = _lineage_key(results[0])
                return [chunk for chunk in results if _lineage_key(chunk) == key]
            return []
        winning_key = ranked.items[0][0]
        return [chunk for chunk in results if _lineage_key(chunk) == winning_key]
    key = _lineage_key(results[0])
    return [chunk for chunk in results if _lineage_key(chunk) == key]


def select_document_first_anchors(
    results: CitedResults,
    *,
    query_text: str | None = None,
    strict_matching: bool = False,
) -> CitedResults:
    """Rank lineages first, then return all retrieved chunks from the winner.

    For bounded, document-centric questions we want the winning document to be
    chosen based on the full set of retrieved support, not just whichever
    individual chunk happened to rank first.
    """
    if not results:
        return []
    if query_text is not None:
        ranked = _query_ranked_lineages(
            results,
            query_text,
            strict_matching=strict_matching,
            prefer_local_when_unspecified=False,
        )
        if not ranked.items:
            if strict_matching and ranked.max_total_overlap == 0:
                return _legacy_document_first_anchors(results)
            else:
                return []
        if ranked.items:
            _, winning_ranked_chunks, _, _ = ranked.items[0]
            query_terms = _normalized_query_terms(query_text)
            return [_best_ranked_chunk_for_query(winning_ranked_chunks, query_terms)]
    return _legacy_document_first_anchors(results)


def select_synthesis_evidence(
    candidates: CitedResults,
    *,
    require_multi_source: bool = False,
    query_text: str | None = None,
    strict_matching: bool = False,
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
    if query_text is not None:
        ranked = _query_ranked_lineages(
            evidence,
            query_text,
            strict_matching=strict_matching,
            prefer_local_when_unspecified=False,
        )
        if ranked.items:
            allowed_lineages = {lineage_key for lineage_key, *_ in ranked.items}
            evidence = [
                chunk for chunk in evidence if _lineage_key(chunk) in allowed_lineages
            ]
        elif not (strict_matching and ranked.max_total_overlap == 0):
            evidence = []
    if require_multi_source:
        lineages = {_lineage_key(chunk) for chunk in evidence}
        if len(lineages) < _MIN_MULTI_SOURCE_LINEAGES:
            return []
    return evidence
