"""MCP tool definitions — implemented in Story 3.4."""
from cos.mcp_server.server import mcp


@mcp.tool()
async def retrieve(query: str) -> str:
    """Retrieve relevant documents for a query."""
    raise NotImplementedError


@mcp.tool()
async def get_role_context() -> str:
    """Return active role pack context."""
    raise NotImplementedError


@mcp.tool()
async def list_documents() -> str:
    """List all ingested documents with provenance."""
    raise NotImplementedError


@mcp.tool()
async def get_status() -> str:
    """Return platform health status."""
    raise NotImplementedError
