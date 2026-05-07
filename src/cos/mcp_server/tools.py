import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from cos.mcp_server.server import (
    get_config,
    get_output_service,
    get_retrieval_service,
    get_role_pack_service,
    mcp,
)
from cos.services.health import ComponentStatus, HealthService
from cos.services.ingestion import IngestService
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
    health = HealthService(
        db_dsn=config.database.libpq_dsn,
        tika_url=config.tika.url,
        role_pack_path=config.role_pack.path,
    )
    statuses = await health.check_all()
    components = [asdict(ComponentStatus(name="cos", healthy=True, message="healthy"))]
    components.extend(asdict(status) for status in statuses)
    ready = bool(components) and all(component["healthy"] for component in components)
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

    role_pack_svc = get_role_pack_service()
    role_pack = role_pack_svc.get_active() if role_pack_svc is not None else None

    try:
        response = await retrieval_service.query(query, role_pack=role_pack)
    except Exception:
        logging.error(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "mcp_server",
                    "message": "Retrieval tool failed",
                }
            )
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Retrieval failed",
                "detail": "An internal error occurred. Run cos logs for diagnostics.",
            }
        )

    citations_data = [
        {
            "source_alias": citation.source_alias,
            "source_locator": citation.source_locator,
            "document_version_id": citation.document_version_id,
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
    svc = get_role_pack_service()
    if svc is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Server not initialized",
                "detail": "role pack service not ready",
            }
        )

    role_pack = svc.get_active()
    return json.dumps(
        {
            "status": "ok",
            "data": {
                "role_name": role_pack.role_name,
                "goals": role_pack.goals,
                "tone": role_pack.tone,
                "knowledge_taxonomy": role_pack.knowledge_taxonomy,
                "active_workflows": role_pack.active_workflows,
            },
            "citations": [],
        }
    )


@mcp.tool()
async def ingest_document(
    content: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Ingest a note or short document directly through MCP."""
    config = get_config()
    if config is None:
        return json.dumps(
            {
                "status": "error",
                "error": "Server not initialized",
                "detail": "config not loaded yet",
            }
        )

    if not content or not content.strip():
        return json.dumps(
            {
                "status": "error",
                "error": "Invalid input",
                "detail": "content must not be empty or whitespace-only",
            }
        )

    svc = IngestService(config)
    try:
        result = await svc.ingest_note(text=content, metadata=metadata)
    except ValueError as exc:
        return json.dumps(
            {
                "status": "error",
                "error": "Invalid input",
                "detail": str(exc),
            }
        )
    except Exception:
        logging.error(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "mcp_server",
                    "message": "ingest_document tool failed",
                }
            )
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Ingest failed",
                "detail": "An internal error occurred. Run cos logs for diagnostics.",
            }
        )

    data: dict[str, object] = {
        "document_id": result.document_id,
        "chunk_count": result.chunk_count,
        "outcome": result.outcome,
        "message": result.message,
        "source_alias": result.source_alias,
        "source_locator": result.source_locator,
    }
    if result.warning is not None:
        data["warning"] = result.warning

    return json.dumps(
        {
            "status": "ok",
            "data": data,
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
    except Exception:
        logging.error(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "mcp_server",
                    "message": "list_documents tool failed",
                }
            )
        )
        return json.dumps(
            {
                "status": "error",
                "error": "Document listing failed",
                "detail": "An internal error occurred. Run cos logs for diagnostics.",
            }
        )
    docs_data = [
        {
            "id": doc.id,
            "source_alias": doc.source_alias,
            "source_locator": doc.source_locator,
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
