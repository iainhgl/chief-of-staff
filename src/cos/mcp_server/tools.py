import json

from cos.mcp_server.server import get_config, mcp
from cos.services.health import HealthService


@mcp.tool()
async def get_status() -> str:
    """Return platform health status."""
    config = get_config()
    if config is None:
        return json.dumps({"status": "error", "error": "Server not initialized", "detail": "config not loaded yet"})
    health = HealthService(db_dsn=config.database.libpq_dsn, tika_url=config.tika.url)
    components = await health.check_all()
    ready = bool(components) and all(c["healthy"] for c in components)
    return json.dumps({"status": "ok", "data": {"components": components, "ready": ready}, "citations": []})


@mcp.tool()
async def retrieve(query: str) -> str:
    """Retrieve relevant documents for a query."""
    return json.dumps({"status": "error", "error": "Not yet implemented", "detail": "retrieve is implemented in Story 3.4"})


@mcp.tool()
async def get_role_context() -> str:
    """Return active role pack context."""
    return json.dumps({"status": "error", "error": "Not yet implemented", "detail": "get_role_context is implemented in Story 4.3"})


@mcp.tool()
async def list_documents() -> str:
    """List all ingested documents with provenance."""
    return json.dumps({"status": "error", "error": "Not yet implemented", "detail": "list_documents is implemented in Story 3.4"})
