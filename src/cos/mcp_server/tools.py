import json

from cos.mcp_server.server import (
    get_config,
    get_output_service,
    get_retrieval_service,
    mcp,
)
from cos.services.health import HealthService
from cos.services.provenance import ProvenanceService


@mcp.tool()
async def get_status() -> str:
    """Return platform health status."""
    config = get_config()
    if config is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Server not initialized",
                "detail": "config not loaded yet",
            }
        )
    health = HealthService(db_dsn=config.database.libpq_dsn, tika_url=config.tika.url)
    components = [{"name": "cos", "healthy": True}] + await health.check_all()
    ready = bool(components) and all(c["healthy"] for c in components)
    return json.dumps(
        {
            "status": "ok",
            "data": {"components": components, "ready": ready},
            "citations": [],
        }
    )


@mcp.tool()
async def retrieve(query: str) -> str:
    """Retrieve relevant documents for a query."""
    retrieval_service = get_retrieval_service()
    if retrieval_service is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Server not initialized",
                "detail": "retrieval service not ready",
            }
        )

    try:
        response = await retrieval_service.query(query, role_pack=None)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error": "Retrieval failed",
                "detail": str(exc),
            }
        )

    citations_data = [
        {
            "source_path": citation.source_path,
            "chunk_index": citation.chunk_index,
            "score": citation.score,
        }
        for citation in response.citations
    ]

    if response.answer is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Synthesis failed",
                "detail": (
                    "LLM synthesis returned no answer; citations may still be"
                    " available"
                ),
            }
        )

    output_service = get_output_service()
    if output_service is not None:
        await output_service.send("local", response.answer)

    return json.dumps(
        {
            "status": "ok",
            "data": {"answer": response.answer, "citations": citations_data},
            "citations": citations_data,
        }
    )


@mcp.tool()
async def get_role_context() -> str:
    """Return active role pack context."""
    return json.dumps(
        {
            "status": "ok",
            "data": {"role": "default — role pack not yet configured"},
            "citations": [],
        }
    )


@mcp.tool()
async def list_documents() -> str:
    """List all ingested documents with provenance."""
    config = get_config()
    if config is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Server not initialized",
                "detail": "config not loaded yet",
            }
        )

    svc = ProvenanceService(config=config)
    try:
        docs = await svc.list_documents()
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "error": "Document listing failed",
                "detail": str(exc),
            }
        )
    docs_data = [
        {
            "id": doc.id,
            "source_path": doc.source_path,
            "ingested_at": doc.ingested_at.isoformat(),
            "current_version": doc.current_version,
            "chunk_count": doc.chunk_count,
        }
        for doc in docs
    ]
    return json.dumps(
        {
            "status": "ok",
            "data": {"documents": docs_data},
            "citations": [],
        }
    )
