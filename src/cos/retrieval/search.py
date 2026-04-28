"""Hybrid keyword + semantic search."""

from collections.abc import Iterable
from typing import Any

import psycopg
from pgvector import Vector  # type: ignore[import-untyped]
from pgvector.psycopg import register_vector_async  # type: ignore[import-untyped]

from cos.config import CosConfig
from cos.ingestion.embedder import VoyageTransportConfig, embed
from cos.retrieval.citations import CitedChunk, CitedResults
from cos.rolepack.loader import RolePackConfig

_RRF_K = 60


def _coerce_priority_weight(retrieval_priorities: Any, source_path: str) -> float:
    if isinstance(retrieval_priorities, dict):
        for candidate, weight in retrieval_priorities.items():
            if isinstance(candidate, str) and source_path.startswith(candidate):
                if isinstance(weight, int | float):
                    return float(weight)

    if isinstance(retrieval_priorities, Iterable) and not isinstance(
        retrieval_priorities, str
    ):
        for item in retrieval_priorities:
            if not isinstance(item, dict):
                continue
            candidate = (
                item.get("source_path") or item.get("path") or item.get("source")
            )
            weight = item.get("weight")
            if (
                isinstance(candidate, str)
                and source_path.startswith(candidate)
                and isinstance(weight, int | float)
            ):
                return float(weight)

    return 1.0


async def hybrid_search(
    query: str,
    conn: psycopg.AsyncConnection[Any],
    config: CosConfig,
    role_pack: RolePackConfig | None = None,
    top_k: int = 10,
) -> CitedResults:
    if not query.strip():
        return []

    await register_vector_async(conn)

    query_embeddings = await embed(
        [query],
        provider=config.embedding.provider,
        model=config.embedding.model,
        api_key=(
            config.embedding.api_key.get_secret_value()
            if config.embedding.api_key
            else ""
        ),
        transport=VoyageTransportConfig(
            ca_bundle_path=config.embedding.ca_bundle_path,
            proxy_url=config.embedding.proxy_url,
            trust_env=config.embedding.trust_env,
        ),
    )
    query_vector = Vector(query_embeddings[0].vector)

    keyword_result = await conn.execute(
        """
        SELECT
            c.id::text AS chunk_id,
            c.document_id::text AS document_id,
            c.chunk_index,
            c.content,
            ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', %s)) AS score
        FROM chunks c
        WHERE c.content_tsv @@ websearch_to_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s
        """,
        (query, query, top_k),
    )
    keyword_rows = await keyword_result.fetchall()
    keyword_hits = [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "chunk_index": row[2],
            "content": row[3],
            "score": float(row[4]),
        }
        for row in keyword_rows
    ]

    semantic_result = await conn.execute(
        """
        SELECT
            c.id::text AS chunk_id,
            c.document_id::text AS document_id,
            c.chunk_index,
            c.content,
            1 - (e.vector <=> %s) AS score
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        ORDER BY score DESC
        LIMIT %s
        """,
        (query_vector, top_k),
    )
    semantic_rows = await semantic_result.fetchall()
    semantic_hits = [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "chunk_index": row[2],
            "content": row[3],
            "score": float(row[4]),
        }
        for row in semantic_rows
        if float(row[4]) > 0.0
    ]

    if not keyword_hits and not semantic_hits:
        return []

    merged_scores: dict[str, dict[str, Any]] = {}
    for hits in (keyword_hits, semantic_hits):
        for rank, hit in enumerate(hits, start=1):
            chunk_id = hit["chunk_id"]
            merged_scores.setdefault(
                chunk_id,
                {
                    "hit": hit,
                    "score": 0.0,
                },
            )
            merged_scores[chunk_id]["score"] += 1.0 / (_RRF_K + rank)

    document_ids = list(
        {entry["hit"]["document_id"] for entry in merged_scores.values()}
    )
    source_result = await conn.execute(
        """
        SELECT id::text, source_path
        FROM documents
        WHERE id = ANY(%s::uuid[])
        """,
        (document_ids,),
    )
    source_rows = await source_result.fetchall()
    source_paths = {row[0]: row[1] for row in source_rows}

    retrieval_priorities = (
        getattr(role_pack, "retrieval_priorities", None)
        if role_pack is not None
        else None
    )
    cited_results: CitedResults = []
    for entry in merged_scores.values():
        hit = entry["hit"]
        source_path = source_paths.get(hit["document_id"])
        if source_path is None:
            continue

        final_score = float(entry["score"])
        if retrieval_priorities is not None:
            final_score *= _coerce_priority_weight(retrieval_priorities, source_path)

        cited_results.append(
            CitedChunk(
                content=hit["content"],
                source_document_id=hit["document_id"],
                source_path=source_path,
                chunk_index=hit["chunk_index"],
                score=final_score,
            )
        )

    cited_results.sort(key=lambda chunk: chunk.score, reverse=True)
    return cited_results[:top_k]
