"""Semantic near-duplicate detection for warning-only MCP note capture."""

from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector_async

from cos.config import CosConfig
from cos.ingestion.embedder import VoyageTransportConfig, embed


async def find_near_duplicate(
    text: str,
    exclude_document_id: str,
    conn: psycopg.AsyncConnection[Any],
    config: CosConfig,
    threshold: float = 0.95,
) -> dict[str, object] | None:
    """Find the nearest previously indexed chunk excluding exclude_document_id.

    Returns {'source_alias': str, 'similarity': float} when similarity >= threshold,
    otherwise None.  Returns None immediately when no embedding key is configured.
    """
    api_key = (
        config.embedding.api_key.get_secret_value()
        if config.embedding.api_key is not None
        else ""
    )
    if not api_key:
        return None

    await register_vector_async(conn)

    embedding_results = await embed(
        [text],
        provider=config.embedding.provider,
        model=config.embedding.model,
        api_key=api_key,
        transport=VoyageTransportConfig(
            ca_bundle_path=config.embedding.ca_bundle_path,
            proxy_url=config.embedding.proxy_url,
            trust_env=config.embedding.trust_env,
        ),
    )
    query_vector = Vector(embedding_results[0].vector)

    result = await conn.execute(
        """
        SELECT
            1 - (e.vector <=> %s) AS similarity,
            COALESCE(s.source_alias, d.source_path) AS source_alias
        FROM embeddings e
        JOIN chunks c ON c.id = e.chunk_id
        JOIN documents d ON d.id = c.document_id
        LEFT JOIN source_versions sv ON sv.document_version_id = c.document_version_id
        LEFT JOIN sources s ON s.id = sv.source_id
        WHERE c.document_id != %s::uuid
        ORDER BY similarity DESC
        LIMIT 1
        """,
        (query_vector, exclude_document_id),
    )
    row = await result.fetchone()
    if row is None:
        return None

    similarity = float(row[0])
    if similarity >= threshold:
        return {"source_alias": str(row[1]), "similarity": similarity}
    return None
