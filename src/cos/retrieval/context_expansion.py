"""Bounded context expansion around anchor chunks.

Fetches adjacent chunks within the same document lineage so that the
synthesis context preserves local narrative order and document framing
without introducing citation leakage from non-anchor neighbours.

Content-safety contract: only counts, indices, and chunk text enter
this module.  Raw query text, prompt text, secrets, and DSNs must
never appear here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from cos.retrieval.citations import CitedChunk, CitedResults

# Default expansion window: ±N adjacent chunks around each anchor.
_DEFAULT_WINDOW = 1

# Hard cap on the total number of chunks in synthesis context.
# Prevents a long document from silently expanding into an unbounded prompt.
_DEFAULT_MAX_EXPANDED = 10


@dataclass
class ExpandedContext:
    """Dual representation separating synthesis context from citation evidence.

    synthesis_chunks: ordered span passed to the LLM (anchors + neighbours).
    evidence_chunks:  citation-eligible anchors only; no neighbour leakage.
    """

    synthesis_chunks: CitedResults
    evidence_chunks: CitedResults


async def expand_bounded_context(
    conn: psycopg.AsyncConnection[Any],
    anchors: CitedResults,
    *,
    window: int = _DEFAULT_WINDOW,
    max_expanded: int = _DEFAULT_MAX_EXPANDED,
) -> ExpandedContext:
    """Return an ExpandedContext built around the given anchor chunks.

    Fetches the window of adjacent chunks from the same document lineage so
    that the model receives a contiguous, ordered context span.  Only anchor
    chunks remain in evidence_chunks; neighbour chunks fill out the synthesis
    context but are not returned as citations.

    If document_version_id is absent (legacy records), expansion is skipped
    and synthesis_chunks equals evidence_chunks.
    """
    if not anchors:
        return ExpandedContext(synthesis_chunks=[], evidence_chunks=[])

    representative = anchors[0]
    doc_version_id = representative.document_version_id

    if not doc_version_id:
        return ExpandedContext(
            synthesis_chunks=list(anchors),
            evidence_chunks=list(anchors),
        )

    anchor_indices = {c.chunk_index for c in anchors}
    min_idx = max(0, min(anchor_indices) - window)
    max_idx = max(anchor_indices) + window

    result = await conn.execute(
        """
        SELECT chunk_index, content
        FROM chunks
        WHERE document_version_id = %s::uuid
          AND chunk_index BETWEEN %s AND %s
        ORDER BY chunk_index
        """,
        (doc_version_id, min_idx, max_idx),
    )
    rows = await result.fetchall()

    anchor_map: dict[int, CitedChunk] = {c.chunk_index: c for c in anchors}
    synthesis_chunks: CitedResults = []
    for row in rows:
        idx: int = row[0]
        content: str = row[1]
        if idx in anchor_map:
            synthesis_chunks.append(anchor_map[idx])
        else:
            synthesis_chunks.append(
                CitedChunk(
                    content=content,
                    source_document_id=representative.source_document_id,
                    source_alias=representative.source_alias,
                    source_locator=representative.source_locator,
                    document_version_id=doc_version_id,
                    chunk_index=idx,
                    score=0.0,
                )
            )

    if len(synthesis_chunks) > max_expanded:
        synthesis_chunks = synthesis_chunks[:max_expanded]

    return ExpandedContext(
        synthesis_chunks=synthesis_chunks,
        evidence_chunks=list(anchors),
    )
