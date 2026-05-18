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


def _dedupe_anchors_by_index(anchors: CitedResults) -> CitedResults:
    deduped: CitedResults = []
    seen_indices: set[int] = set()
    for anchor in anchors:
        if anchor.chunk_index in seen_indices:
            continue
        seen_indices.add(anchor.chunk_index)
        deduped.append(anchor)
    return deduped


def _select_anchor_subset(
    anchors: CitedResults,
    max_expanded: int,
) -> CitedResults:
    selected = _dedupe_anchors_by_index(anchors)
    if len(selected) <= max_expanded:
        return selected
    return selected[:max_expanded]


def _merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not windows:
        return []

    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if not merged:
            merged.append((start, end))
            continue

        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
            continue

        merged.append((start, end))
    return merged


def _window_clauses(windows: list[tuple[int, int]]) -> tuple[str, list[int]]:
    clauses = []
    params: list[int] = []
    for start, end in windows:
        clauses.append("(chunk_index BETWEEN %s AND %s)")
        params.extend((start, end))
    return " OR ".join(clauses), params


async def _fetch_window_rows(
    conn: psycopg.AsyncConnection[Any],
    *,
    identifier_column: str,
    identifier: str,
    windows: list[tuple[int, int]],
) -> list[tuple[int, str]]:
    clauses, params = _window_clauses(windows)
    query = f"""
        SELECT chunk_index, content
        FROM chunks
        WHERE {identifier_column} = %s::uuid
          AND ({clauses})
        ORDER BY chunk_index
        """
    result = await conn.execute(query, (identifier, *params))
    rows = await result.fetchall()
    return [(int(row[0]), str(row[1])) for row in rows]


def _distance_to_nearest_anchor(index: int, anchor_indices: set[int]) -> int:
    return min(abs(index - anchor_index) for anchor_index in anchor_indices)


def _trim_synthesis_chunks(
    synthesis_chunks: CitedResults,
    anchor_indices: set[int],
    max_expanded: int,
) -> CitedResults:
    if len(synthesis_chunks) <= max_expanded:
        return synthesis_chunks

    kept_indices = set(anchor_indices)
    remaining_slots = max_expanded - len(kept_indices)
    if remaining_slots <= 0:
        return [
            chunk
            for chunk in synthesis_chunks
            if chunk.chunk_index in kept_indices
        ]

    neighbours = [
        chunk for chunk in synthesis_chunks if chunk.chunk_index not in anchor_indices
    ]
    neighbours.sort(
        key=lambda chunk: (
            _distance_to_nearest_anchor(chunk.chunk_index, anchor_indices),
            chunk.chunk_index,
        )
    )
    for neighbour in neighbours[:remaining_slots]:
        kept_indices.add(neighbour.chunk_index)

    return [chunk for chunk in synthesis_chunks if chunk.chunk_index in kept_indices]


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

    If document_version_id is absent (legacy records), expansion falls back to
    document_id so older chunks can still recover bounded neighbours.
    """
    if not anchors:
        return ExpandedContext(synthesis_chunks=[], evidence_chunks=[])

    selected_anchors = _select_anchor_subset(anchors, max_expanded=max_expanded)
    representative = selected_anchors[0]
    doc_version_id = representative.document_version_id

    anchor_indices = {c.chunk_index for c in selected_anchors}
    windows = _merge_windows(
        [
            (max(0, anchor_index - window), anchor_index + window)
            for anchor_index in sorted(anchor_indices)
        ]
    )

    if doc_version_id:
        rows = await _fetch_window_rows(
            conn,
            identifier_column="document_version_id",
            identifier=doc_version_id,
            windows=windows,
        )
    else:
        rows = await _fetch_window_rows(
            conn,
            identifier_column="document_id",
            identifier=representative.source_document_id,
            windows=windows,
        )

    anchor_map: dict[int, CitedChunk] = {
        chunk.chunk_index: chunk for chunk in selected_anchors
    }
    synthesis_chunks: CitedResults = []
    for idx, content in rows:
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

    synthesis_chunks = _trim_synthesis_chunks(
        synthesis_chunks,
        anchor_indices=anchor_indices,
        max_expanded=max_expanded,
    )

    return ExpandedContext(
        synthesis_chunks=synthesis_chunks,
        evidence_chunks=list(selected_anchors),
    )
