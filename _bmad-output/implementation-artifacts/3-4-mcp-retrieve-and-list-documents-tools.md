# Story 3.4: MCP Retrieve & List Documents Tools

Status: done

## Story

As a user,
I want to ask questions and list my knowledge base directly from Claude Desktop or Claude Code,
So that the full retrieval and citation pipeline is accessible through the MCP interface I already use.

## Acceptance Criteria

1. **Given** a connected MCP client calls the `retrieve` tool with a `query` string,
   **When** the tool executes,
   **Then** it calls `RetrievalService.query()` and delivers the answer via `OutputService`, returning the standard envelope: `{"status": "ok", "data": {"answer": "...", "citations": [...]}, "citations": [...]}` where citations include `source_path`, `chunk_index`, and `score` for each source.

2. **Given** the `retrieve` tool is called and retrieval finds no matching content,
   **When** the tool returns,
   **Then** it returns `{"status": "ok", "data": {"answer": "No relevant content found in the knowledge base.", "citations": []}, "citations": []}` — not an error envelope.

3. **Given** a connected MCP client calls the `list_documents` tool,
   **When** the tool executes,
   **Then** it returns a list of all ingested documents with `id`, `source_path`, `ingested_at`, `current_version`, and `chunk_count` for each — matching the data available via `cos docs` from Epic 2.

4. **Given** both `retrieve` and `list_documents` are called under normal conditions,
   **When** execution completes,
   **Then** each tool call returns within 2 seconds for `list_documents` and within 5 seconds for `retrieve` (including synthesis).

5. **Given** the `get_role_context` tool is called,
   **When** the tool executes,
   **Then** it returns a stub response using the default role pack configuration: `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}` — not an error.

6. **Given** any of the implemented tools is called,
   **When** the tool response is inspected,
   **Then** the response strictly conforms to the standard envelope shape — no custom fields, no raw exceptions, no protocol-level errors for application-level failures.

## Tasks / Subtasks

- [x] Task 1: Extend `server.py` with pool, retrieval service, and output service globals (AC: #1, #2, #3, #4)
  - [x] Add imports: `from psycopg_pool import AsyncConnectionPool`, `from cos.store.db import create_pool` (alongside existing `run_migrations`), `from cos.llm.anthropic import AnthropicAdapter`, `from cos.services.retrieval import RetrievalService`, `from cos.services.output import OutputService`
  - [x] Add three new module-level globals after `_output_router`: `_pool: AsyncConnectionPool | None = None`, `_retrieval_service: RetrievalService | None = None`, `_output_service: OutputService | None = None`
  - [x] Add getters: `get_pool()`, `get_retrieval_service()`, `get_output_service()`
  - [x] In `_startup_sequence`, declare `global _pool, _retrieval_service, _output_service` (alongside existing `global _output_router`)
  - [x] Insert pool creation BEFORE output router creation: `_pool = await create_pool(config.database.libpq_dsn)` + emit log
  - [x] After creating `_output_router`, create output service: `_output_service = OutputService(router=_output_router)`
  - [x] After output service, create adapter and retrieval service: `_adapter = AnthropicAdapter(model=config.llm.model, api_key=config.llm.api_key.get_secret_value())` then `_retrieval_service = RetrievalService(config=config, pool=_pool, llm_adapter=_adapter)` + emit log
  - [x] Do NOT store `_adapter` as a module global — it is only needed as an argument to `RetrievalService`

- [x] Task 2: Implement `retrieve` tool in `tools.py` (AC: #1, #2, #6)
  - [x] Add import at top of file: `from cos.mcp_server.server import get_config, get_output_router, get_output_service, get_retrieval_service, mcp` (replace current import line)
  - [x] Add import: `from cos.services.output import OutputService`
  - [x] Replace the stub `retrieve` function entirely
  - [x] Guard: if `get_retrieval_service()` returns `None`, return `{"status": "error", "error": "Server not initialized", "detail": "retrieval service not ready"}`
  - [x] Call `response = await retrieval_service.query(query, role_pack=None)`
  - [x] If `response.answer is None`: return `{"status": "error", "error": "Synthesis failed", "detail": "LLM synthesis returned no answer; citations may still be available", "citations": citations_data}`
  - [x] Build `citations_data` as list of dicts with `source_path`, `chunk_index`, `score` for each item in `response.citations`
  - [x] If answer is present, call `output_service = get_output_service()` and `await output_service.send("local", response.answer)` if `output_service is not None`
  - [x] Return `{"status": "ok", "data": {"answer": response.answer, "citations": citations_data}, "citations": citations_data}`

- [x] Task 3: Implement `list_documents` tool in `tools.py` (AC: #3, #4, #6)
  - [x] Add import at top of file: `from cos.services.provenance import ProvenanceService`
  - [x] Replace the stub `list_documents` function entirely
  - [x] Guard: if `get_config()` returns `None`, return `{"status": "error", "error": "Server not initialized", "detail": "config not loaded yet"}`
  - [x] Construct `svc = ProvenanceService(config=config)` inline (same pattern as `HealthService` in `get_status`)
  - [x] Call `docs = await svc.list_documents()`
  - [x] Build `docs_data` as list of dicts with `id`, `source_path`, `ingested_at` (ISO 8601 string via `.isoformat()`), `current_version`, `chunk_count`
  - [x] Return `{"status": "ok", "data": {"documents": docs_data}, "citations": []}`

- [x] Task 4: Implement `get_role_context` tool stub in `tools.py` (AC: #5, #6)
  - [x] Replace the error stub with ok stub
  - [x] Return `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}`
  - [x] No service calls required — pure Phase 1 stub; Epic 4 implements the real version

- [x] Task 5: Update `tests/mcp_server/test_tools.py` (AC: #1–#6)
  - [x] Remove `test_retrieve_returns_error_envelope` — stub is gone
  - [x] Remove `test_list_documents_returns_error_envelope` — stub is gone
  - [x] Remove `test_get_role_context_returns_error_envelope` — tool now returns ok
  - [x] Add `from datetime import datetime, timezone` and `from cos.retrieval.citations import CitedChunk, CitedResponse` imports
  - [x] Add helper `_make_mock_retrieval_service()` that returns an `AsyncMock` with `.query` returning a `CitedResponse` with a real `CitedChunk`
  - [x] Add `test_retrieve_returns_ok_envelope`: monkeypatch `_server._retrieval_service` and `_server._output_service`; call `retrieve(query="test")`; assert `status == "ok"`, `data.answer` is a string, `citations` is a list
  - [x] Add `test_retrieve_no_content_found`: mock `query` returning `CitedResponse(answer="No relevant content found in the knowledge base.", citations=[])`; assert status `"ok"`, answer contains `"no relevant content"` (case-insensitive)
  - [x] Add `test_retrieve_server_not_initialized`: monkeypatch `_server._retrieval_service = None`; assert `status == "error"`
  - [x] Add `test_retrieve_synthesis_failure`: mock `query` returning `CitedResponse(answer=None, citations=[])`; assert `status == "error"`
  - [x] Add `test_list_documents_returns_ok_envelope`: monkeypatch `_config`; patch `cos.services.provenance.ProvenanceService.list_documents` returning `[DocumentSummary(...)]`; assert `status == "ok"`, `data.documents` is a list
  - [x] Add `test_list_documents_no_config_returns_error`: monkeypatch `_server._config = None`; assert `status == "error"`
  - [x] Add `test_list_documents_document_fields_present`: patch list_documents returning a `DocumentSummary`; assert each dict in `data.documents` has keys `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`
  - [x] Add `test_get_role_context_returns_ok_stub`: call `get_role_context()`; assert `status == "ok"`, `data.role` is a string, `citations == []`

- [x] Task 6: Update `tests/mcp_server/test_server.py` to handle new startup steps (AC: #1–#4)
  - [x] Add `from unittest.mock import AsyncMock, MagicMock` import
  - [x] Add `from psycopg_pool import AsyncConnectionPool` import
  - [x] Add `llm` to `_make_config`: `llm=SimpleNamespace(model="claude-3-haiku-20240307", api_key=SimpleNamespace(get_secret_value=lambda: "test-key"))` — this is required because `_startup_sequence` now creates `AnthropicAdapter`
  - [x] Add `create_pool` mock to `_patch_server`: `async def _create_pool(_: str) -> AsyncConnectionPool: return MagicMock(spec=AsyncConnectionPool)` then `monkeypatch.setattr(server, "create_pool", _create_pool)`
  - [x] Add `AnthropicAdapter` mock to `_patch_server` to avoid real API client construction: `monkeypatch.setattr(server, "AnthropicAdapter", MagicMock(return_value=MagicMock()))` — prevents network setup at test time
  - [x] Add `RetrievalService` mock to `_patch_server`: `monkeypatch.setattr(server, "RetrievalService", MagicMock(return_value=MagicMock()))` — prevents constructor side-effects
  - [x] Verify existing `test_startup_sequence_initialises_output_router` and `test_startup_sequence_with_empty_channels_router_created` still pass after these additions
  - [x] Add `test_startup_sequence_initialises_retrieval_service`: call `_startup_sequence`, assert `server.get_retrieval_service() is not None`
  - [x] Add `test_startup_sequence_initialises_output_service`: assert `server.get_output_service() is not None`

## Dev Notes

### What Is Already Done — Do Not Re-Implement

**`src/cos/services/retrieval.py`** — `RetrievalService.query(text, role_pack)` is fully implemented (Story 3.3). Returns `CitedResponse(answer, citations)`. Do not modify.

**`src/cos/retrieval/citations.py`** — `CitedChunk`, `CitedResults`, `CitedResponse`, `format_citations` all implemented. Do not modify.

**`src/cos/services/provenance.py`** — `ProvenanceService.list_documents()` is fully implemented (Story 2.5). Returns `list[DocumentSummary]`. Do not modify.

**`src/cos/store/db.py`** — `create_pool(dsn: str) -> AsyncConnectionPool` and `list_documents(conn)` are implemented. `create_pool` is what `server.py` must call.

**`src/cos/services/output.py`** — `OutputService(router).send(channel, content)` is implemented. Do not modify.

**`src/cos/output/router.py`** — `OutputRouter` is implemented with channel validation. Do not modify.

**`src/cos/llm/anthropic.py`** — `AnthropicAdapter(model, api_key)` fully implemented. Do not modify.

**`src/cos/store/models.py`** — `DocumentSummary` has fields: `id`, `source_path`, `ingested_at` (datetime), `current_version`, `chunk_count`. Use these in the list_documents envelope.

### `server.py` — Complete Extended Pattern

```python
# New imports to add (alongside existing imports):
from psycopg_pool import AsyncConnectionPool
from cos.store.db import create_pool, run_migrations  # add create_pool
from cos.llm.anthropic import AnthropicAdapter
from cos.services.retrieval import RetrievalService
from cos.services.output import OutputService

# Module globals — add after existing _output_router:
_pool: AsyncConnectionPool | None = None
_retrieval_service: RetrievalService | None = None
_output_service: OutputService | None = None

# Getters — add after get_output_router():
def get_pool() -> AsyncConnectionPool | None:
    return _pool

def get_retrieval_service() -> RetrievalService | None:
    return _retrieval_service

def get_output_service() -> OutputService | None:
    return _output_service

# _startup_sequence — updated version:
async def _startup_sequence(config: CosConfig) -> None:
    global _output_router, _pool, _retrieval_service, _output_service
    component: LogComponent = "mcp_server"
    pg_ok = await _check_postgres(config.database.libpq_dsn)
    _emit(component, "INFO", "Postgres: healthy" if pg_ok else "Postgres: unhealthy")
    tika_ok = await _check_tika(config.tika.url)
    _emit(component, "INFO", "Tika: healthy" if tika_ok else "Tika: unhealthy")
    _emit(component, "INFO", "config loaded", role_pack_path=config.role_pack.path)
    await run_migrations(config.database.libpq_dsn)
    _emit(component, "INFO", "migrations applied")
    _pool = await create_pool(config.database.libpq_dsn)
    _emit(component, "INFO", "connection pool: open")
    _emit(component, "INFO", "role pack: stub loaded")
    _output_router = OutputRouter(configured_channels=config.channels)
    _output_service = OutputService(router=_output_router)
    _emit(component, "INFO", "output router: initialised", channels=config.channels)
    _adapter = AnthropicAdapter(
        model=config.llm.model,
        api_key=config.llm.api_key.get_secret_value(),
    )
    _retrieval_service = RetrievalService(config=config, pool=_pool, llm_adapter=_adapter)
    _emit(component, "INFO", "retrieval service: initialised")
    _emit(component, "INFO", "MCP server: listening")
```

Note: `_adapter` is a local variable only — not a module global. It is passed directly to `RetrievalService` and is not needed elsewhere.

### `tools.py` — Complete Patterns

```python
# Full import block for tools.py:
import json
from datetime import datetime

from cos.mcp_server.server import (
    get_config,
    get_output_service,
    get_retrieval_service,
    mcp,
)
from cos.services.health import HealthService
from cos.services.provenance import ProvenanceService
```

**`retrieve` tool:**
```python
@mcp.tool()
async def retrieve(query: str) -> str:
    """Retrieve relevant documents for a query."""
    retrieval_service = get_retrieval_service()
    if retrieval_service is None:
        return json.dumps({
            "status": "error",
            "error": "Server not initialized",
            "detail": "retrieval service not ready",
        })
    response = await retrieval_service.query(query, role_pack=None)
    citations_data = [
        {"source_path": c.source_path, "chunk_index": c.chunk_index, "score": c.score}
        for c in response.citations
    ]
    if response.answer is None:
        return json.dumps({
            "status": "error",
            "error": "Synthesis failed",
            "detail": "LLM synthesis returned no answer; citations may still be available",
            "citations": citations_data,
        })
    output_service = get_output_service()
    if output_service is not None:
        await output_service.send("local", response.answer)
    return json.dumps({
        "status": "ok",
        "data": {"answer": response.answer, "citations": citations_data},
        "citations": citations_data,
    })
```

**`list_documents` tool:**
```python
@mcp.tool()
async def list_documents() -> str:
    """List all ingested documents with provenance."""
    config = get_config()
    if config is None:
        return json.dumps({
            "status": "error",
            "error": "Server not initialized",
            "detail": "config not loaded yet",
        })
    svc = ProvenanceService(config=config)
    docs = await svc.list_documents()
    docs_data = [
        {
            "id": d.id,
            "source_path": d.source_path,
            "ingested_at": d.ingested_at.isoformat(),
            "current_version": d.current_version,
            "chunk_count": d.chunk_count,
        }
        for d in docs
    ]
    return json.dumps({"status": "ok", "data": {"documents": docs_data}, "citations": []})
```

**`get_role_context` tool:**
```python
@mcp.tool()
async def get_role_context() -> str:
    """Return active role pack context."""
    return json.dumps({
        "status": "ok",
        "data": {"role": "default — role pack not yet configured"},
        "citations": [],
    })
```

### Breaking Tests — Must Fix

**`tests/mcp_server/test_tools.py`** has three tests that will immediately fail because they expect error envelopes from stubs:
- `test_retrieve_returns_error_envelope` — **delete this test**, replace with Task 5 tests
- `test_list_documents_returns_error_envelope` — **delete this test**, replace with Task 5 tests
- `test_get_role_context_returns_error_envelope` — **delete this test**, replace with `test_get_role_context_returns_ok_stub`

**`tests/mcp_server/test_server.py`** — `_startup_sequence` now calls `create_pool`, `AnthropicAdapter`, and `RetrievalService`. All three must be mocked in `_patch_server` or the existing tests will attempt real DB connections. See Task 6 for the exact mock setup.

### Test Patterns for `tests/mcp_server/test_tools.py`

```python
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import cos.mcp_server.server as _server
import cos.mcp_server.tools  # noqa: F401 — ensure decorators run
from cos.mcp_server.tools import get_role_context, get_status, list_documents, retrieve
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.store.models import DocumentSummary


def _make_mock_config() -> MagicMock:
    mock_config = MagicMock()
    mock_config.database.libpq_dsn = "postgresql://test:test@localhost/cos_test"
    mock_config.tika.url = "http://tika:9998"
    return mock_config


def _make_chunk() -> CitedChunk:
    return CitedChunk(
        content="test content",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_path="/test/doc.md",
        chunk_index=0,
        score=0.9,
    )


def _make_mock_retrieval_service(answer: str | None = "synthesised answer") -> AsyncMock:
    svc = AsyncMock()
    svc.query = AsyncMock(return_value=CitedResponse(
        answer=answer,
        citations=[_make_chunk()] if answer is not None else [],
    ))
    return svc


def _make_mock_output_service() -> AsyncMock:
    svc = AsyncMock()
    svc.send = AsyncMock()
    return svc


async def test_retrieve_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", _make_mock_retrieval_service())
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="what is workforce segmentation?"))
    assert result["status"] == "ok"
    assert "answer" in result["data"]
    assert isinstance(result["data"]["answer"], str)
    assert isinstance(result["citations"], list)


async def test_retrieve_no_content_found(monkeypatch):
    svc = AsyncMock()
    svc.query = AsyncMock(return_value=CitedResponse(
        answer="No relevant content found in the knowledge base.",
        citations=[],
    ))
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="unknown topic"))
    assert result["status"] == "ok"
    assert "no relevant content" in result["data"]["answer"].lower()
    assert result["data"]["citations"] == []


async def test_retrieve_server_not_initialized(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", None)
    result = json.loads(await retrieve(query="test"))
    assert result["status"] == "error"


async def test_retrieve_synthesis_failure(monkeypatch):
    svc = AsyncMock()
    svc.query = AsyncMock(return_value=CitedResponse(answer=None, citations=[]))
    monkeypatch.setattr(_server, "_retrieval_service", svc)
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="test"))
    assert result["status"] == "error"


async def test_list_documents_returns_ok_envelope(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [DocumentSummary(
        id="abc123",
        source_path="/test/doc.md",
        ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        current_version=1,
        chunk_count=5,
    )]
    with patch("cos.services.provenance.ProvenanceService.list_documents", new=AsyncMock(return_value=docs)):
        result = json.loads(await list_documents())
    assert result["status"] == "ok"
    assert "documents" in result["data"]
    assert isinstance(result["data"]["documents"], list)


async def test_list_documents_no_config_returns_error(monkeypatch):
    monkeypatch.setattr(_server, "_config", None)
    result = json.loads(await list_documents())
    assert result["status"] == "error"


async def test_list_documents_document_fields_present(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [DocumentSummary(
        id="abc123",
        source_path="/test/doc.md",
        ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        current_version=1,
        chunk_count=5,
    )]
    with patch("cos.services.provenance.ProvenanceService.list_documents", new=AsyncMock(return_value=docs)):
        result = json.loads(await list_documents())
    doc = result["data"]["documents"][0]
    assert "id" in doc
    assert "source_path" in doc
    assert "ingested_at" in doc
    assert "current_version" in doc
    assert "chunk_count" in doc


async def test_get_role_context_returns_ok_stub():
    result = json.loads(await get_role_context())
    assert result["status"] == "ok"
    assert "role" in result["data"]
    assert isinstance(result["data"]["role"], str)
    assert result["citations"] == []
```

### Test Patterns for `tests/mcp_server/test_server.py`

The `_patch_server` function must be extended. The key additions:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from psycopg_pool import AsyncConnectionPool

def _make_config(channels: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        database=SimpleNamespace(libpq_dsn="postgresql://test:test@localhost/cos_test"),
        tika=SimpleNamespace(url="http://tika:9998"),
        role_pack=SimpleNamespace(path="role_packs/chro.yaml"),
        channels=channels,
        llm=SimpleNamespace(
            model="claude-3-haiku-20240307",
            api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
        ),
    )

def _patch_server(monkeypatch):
    emitted = []

    async def _check_postgres(_): return True
    async def _check_tika(_): return True
    async def _run_migrations(_): return None
    async def _create_pool(_): return MagicMock(spec=AsyncConnectionPool)

    def _emit(component, level, message, **extra):
        emitted.append((component, level, message, extra))

    monkeypatch.setattr(server, "_output_router", None)
    monkeypatch.setattr(server, "_check_postgres", _check_postgres)
    monkeypatch.setattr(server, "_check_tika", _check_tika)
    monkeypatch.setattr(server, "run_migrations", _run_migrations)
    monkeypatch.setattr(server, "create_pool", _create_pool)
    monkeypatch.setattr(server, "AnthropicAdapter", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(server, "RetrievalService", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(server, "_emit", _emit)
    return emitted
```

The monkeypatches for `AnthropicAdapter` and `RetrievalService` work because `server.py` imports them into its namespace:
```python
from cos.llm.anthropic import AnthropicAdapter   # becomes server.AnthropicAdapter
from cos.services.retrieval import RetrievalService  # becomes server.RetrievalService
```

### Architecture Boundary Reminder

**MCP tools import only from `cos.services.*`** — never from `cos.store.*`, `cos.retrieval.*`, or `cos.llm.*` directly. Correct:
- `from cos.services.provenance import ProvenanceService` ✅
- `from cos.services.health import HealthService` ✅ (already there)

Incorrect (do not add):
- `from cos.store.db import list_documents` ❌
- `from cos.retrieval.citations import CitedChunk` ❌ (only in tests)

**`server.py` imports service layer and implementation layer** — server.py is the composition root, so it may import `AnthropicAdapter` and `RetrievalService` for construction. This is correct.

**`OutputService` wraps `OutputRouter`** — never call `_output_router.send()` in tools.py directly. Use `output_service.send()` via `get_output_service()`.

### Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `src/cos/mcp_server/server.py` | Modify | Add pool/retrieval/output service globals, getters, and startup steps |
| `src/cos/mcp_server/tools.py` | Modify | Wire all three tools to real implementations |
| `tests/mcp_server/test_tools.py` | Replace | Remove 3 stub tests, add 8 real tests |
| `tests/mcp_server/test_server.py` | Modify | Extend `_make_config` and `_patch_server` for new startup dependencies |

Do NOT modify: `src/cos/services/retrieval.py`, `src/cos/services/provenance.py`, `src/cos/services/output.py`, `src/cos/retrieval/citations.py`, `src/cos/store/db.py`, `src/cos/store/models.py`, `src/cos/output/router.py`, `src/cos/llm/anthropic.py`.

### Debug Commands

```bash
# Run new tool tests (no DB needed — all mocked)
uv run pytest tests/mcp_server/test_tools.py tests/mcp_server/test_server.py -v

# Full test suite (requires docker compose up -d postgres tika)
uv run pytest tests/ -q

# Lint and type-check
uv run ruff check src/cos/mcp_server/server.py src/cos/mcp_server/tools.py
uv run mypy src/cos/mcp_server/server.py src/cos/mcp_server/tools.py
```

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Implementation Plan

- Extend the MCP server startup sequence to compose the database pool, output service, and retrieval service from existing platform components.
- Replace MCP tool stubs with envelope-compliant service-backed implementations for retrieval, document listing, and the Phase 1 role-context stub.
- Expand MCP server and tool tests first, then validate with targeted tests, lint, mypy, and the full repository suite.

### Debug Log References

- `uv run pytest tests/mcp_server/test_server.py -q`
- `uv run pytest tests/mcp_server/test_tools.py -q`
- `uv run pytest tests/mcp_server/test_tools.py tests/mcp_server/test_server.py -q`
- `uv run ruff check src/cos/mcp_server/server.py src/cos/mcp_server/tools.py tests/mcp_server/test_server.py tests/mcp_server/test_tools.py`
- `uv run mypy src/cos/mcp_server/server.py src/cos/mcp_server/tools.py`
- `uv run pytest tests/ -q`

### Completion Notes List

- Added MCP server composition for `AsyncConnectionPool`, `OutputService`, and `RetrievalService` during startup, with getters for downstream tool access.
- Replaced `retrieve` and `list_documents` stubs with service-backed implementations that return standard envelopes and citation/document payloads.
- Replaced `get_role_context` with the Phase 1 ok-stub response using the default role pack message.
- Expanded MCP server and tool tests to cover startup wiring, retrieval success and failure paths, document listing, and role-context behavior.
- Verified the story with targeted MCP tests, lint, mypy, and the full repository test suite.

### File List

- `src/cos/mcp_server/server.py`
- `src/cos/mcp_server/tools.py`
- `tests/mcp_server/test_server.py`
- `tests/mcp_server/test_tools.py`
- `_bmad-output/implementation-artifacts/3-4-mcp-retrieve-and-list-documents-tools.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-27: Implemented Story 3.4 MCP retrieve/list_documents wiring, added role-context stub, and expanded MCP startup/tool test coverage.

### Review Findings

- [x] [Review][Decision] Uncaught service exceptions in `retrieve()` and `list_documents()` — resolved: added try/except around `retrieval_service.query()` and `svc.list_documents()`; service exceptions now return `{"status": "error", "error": "...", "detail": str(exc)}`

- [x] [Review][Patch] Error envelope for synthesis failure includes non-standard `citations` field — fixed: removed `citations` from the synthesis-failure error envelope [src/cos/mcp_server/tools.py]
- [x] [Review][Patch] `test_retrieve_synthesis_failure` only asserts `status == "error"` — fixed: added `error`, `detail` key assertions and `citations not in result` guard [tests/mcp_server/test_tools.py]
- [x] [Review][Patch] `test_retrieve_server_not_initialized` only asserts `status == "error"` — fixed: added `error` and `detail` key assertions [tests/mcp_server/test_tools.py]

- [x] [Review][Defer] Startup partial init leaves pool open if RetrievalService construction raises [src/cos/mcp_server/server.py:84-101] — deferred, pre-existing infrastructure concern; Epic 5 scope
- [x] [Review][Defer] No pool teardown on server shutdown [src/cos/mcp_server/server.py] — deferred, pre-existing; Epic 5 scope
- [x] [Review][Defer] `output_service.send("local", ...)` hardcodes channel name [src/cos/mcp_server/tools.py:73] — deferred, Phase 1 assumption; revisit when multi-channel routing is added
- [x] [Review][Defer] `ProvenanceService` opens a raw psycopg connection per call rather than using the shared `_pool` [src/cos/mcp_server/tools.py:109] — deferred, pre-existing ProvenanceService design from Story 2.5; spec prohibits modifying ProvenanceService
- [x] [Review][Defer] Empty query string not validated in `retrieve()` [src/cos/mcp_server/tools.py:38] — deferred, not a specified requirement; service returns "no content" for empty queries
- [x] [Review][Defer] `list_documents` returns all rows with no pagination [src/cos/mcp_server/tools.py:112] — deferred, acceptable for Phase 1 doc volumes
- [x] [Review][Defer] No initialization guard preventing tool calls before `_startup_sequence` completes [src/cos/mcp_server/server.py] — deferred, pre-existing design; getters return None and tools guard on that
