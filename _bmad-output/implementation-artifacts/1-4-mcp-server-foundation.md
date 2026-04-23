# Story 1.4: MCP Server Foundation

Status: done

## Story

As an operator,
I want Claude Desktop or Claude Code to connect to the platform and discover its available tools,
So that I have a working MCP query interface ready for the retrieval and ingestion stories that follow.

## Acceptance Criteria

1. **Given** the `cos` container is running with a valid `config.yaml` and healthy Postgres,
   **When** `cos-mcp` starts as the container entry point,
   **Then** a FastMCP server starts using the official MCP SDK 1.27.0 FastMCP pattern, listens on stdio transport, and logs a structured JSON startup message with `component: "mcp_server"`.

2. **Given** Claude Desktop or Claude Code is configured to connect to the CoS MCP server,
   **When** the client is opened,
   **Then** it connects successfully and lists exactly four tools: `retrieve`, `get_role_context`, `list_documents`, and `get_status`.

3. **Given** a connected MCP client calls `get_status`,
   **When** the tool executes,
   **Then** it returns a response in the standard envelope: `{"status": "ok", "data": {"components": [...], "ready": true}, "citations": []}`.

4. **Given** a connected MCP client calls `retrieve`, `get_role_context`, or `list_documents` (not yet fully implemented),
   **When** the tool executes,
   **Then** it returns `{"status": "error", "error": "Not yet implemented", "detail": "..."}` — not an unhandled exception and not a protocol-level error.

5. **Given** the MCP server is running,
   **When** startup and tool-call log output is inspected,
   **Then** all entries are structured JSON with `timestamp`, `level`, `component`, and `message` fields — no bare `print()` calls anywhere in the codebase.

6. **Given** the startup sequence runs,
   **When** logs are inspected,
   **Then** the sequence is confirmed: Postgres healthy → Tika healthy → CosConfig loaded → migrations applied → role pack stub loaded → MCP server listening.

## Tasks / Subtasks

- [x] Task 1: Add `TikaConfig` to `CosConfig` (AC: #6)
  - [x] Add `class TikaConfig(BaseModel): url: str = "http://tika:9998"` to `config.py` (before `CosConfig`)
  - [x] Add `tika: TikaConfig = TikaConfig()` field to `CosConfig` — optional with default; preserves all existing test compatibility
  - [x] Add `tika:\n  url: http://tika:9998` section to `config.yaml.example`
  - [x] Add `test_tika_config_defaults` to `tests/test_config.py`: load a minimal config (no `tika` section) and assert `config.tika.url == "http://tika:9998"`

- [x] Task 2: Implement `HealthService` in `services/health.py` (AC: #3)
  - [x] Replace the stub class with: `def __init__(self, db_dsn: str, tika_url: str) -> None` constructor storing both values
  - [x] Implement `async def check_all(self) -> list[dict[str, object]]` — returns `[{"name": "postgres", "healthy": bool}, {"name": "tika", "healthy": bool}]`
  - [x] Implement `async def _check_postgres(self) -> bool` — connect via `psycopg.AsyncConnection.connect(self._db_dsn)`, execute `SELECT 1`, return `True`; `except Exception: return False`
  - [x] Implement `async def _check_tika(self) -> bool` — `GET self._tika_url` via `httpx.AsyncClient(timeout=5.0)`, return `True` if `status_code < 500`; `except Exception: return False`
  - [x] Replace `test_check_all_not_implemented` in `tests/services/test_health_service.py` with tests for healthy and unhealthy paths (mock psycopg + httpx — do NOT hit real services)

- [x] Task 3: Restructure `server.py` startup sequence (AC: #1, #5, #6)
  - [x] Add module-level `_config: CosConfig | None = None` and `def get_config() -> CosConfig | None: return _config`
  - [x] Add `_emit(component: LogComponent, level: str, message: str, **extra: object) -> None` helper for structured JSON log output
  - [x] Add inline `async def _check_postgres(dsn: str) -> bool` and `async def _check_tika(url: str) -> bool` (same logic as `HealthService` — startup does NOT call `HealthService` to avoid service layer dependency at boot)
  - [x] Implement `async def _startup_sequence(config: CosConfig) -> None` emitting 6 messages in order (see Dev Notes for exact sequence)
  - [x] Refactor `run()`: set `global _config = config`; add `import cos.mcp_server.tools  # noqa: F401` at the top of `run()` to register tool handlers; replace old `_log_startup` + `_apply_migrations` calls with `asyncio.run(_startup_sequence(config))`
  - [x] Delete `_log_startup` and `_apply_migrations` functions (replaced by `_startup_sequence`)

- [x] Task 4: Fix `tools.py` — implement `get_status` and return error envelopes (AC: #2, #3, #4, #5)
  - [x] Add imports: `import json`, `from cos.mcp_server.server import get_config`, `from cos.services.health import HealthService`
  - [x] `get_status`: call `get_config()`, create `HealthService(db_dsn=config.database.libpq_dsn, tika_url=config.tika.url)`, call `await health.check_all()`, return standard `ok` envelope; return `error` envelope if `config is None`
  - [x] `retrieve`: return `json.dumps({"status": "error", "error": "Not yet implemented", "detail": "retrieve is implemented in Story 3.4"})`
  - [x] `get_role_context`: return `json.dumps({"status": "error", "error": "Not yet implemented", "detail": "get_role_context is implemented in Story 4.3"})`
  - [x] `list_documents`: return `json.dumps({"status": "error", "error": "Not yet implemented", "detail": "list_documents is implemented in Story 3.4"})`

- [x] Task 5: Add `tests/mcp_server/` tests (AC: #2, #3, #4, #5)
  - [x] Create `tests/mcp_server/__init__.py` (empty)
  - [x] Create `tests/mcp_server/test_tools.py` with tests for all four tools (see Dev Notes for patterns)
  - [x] Cover: `test_get_status_returns_ok_envelope`, `test_get_status_all_components_present`, `test_get_status_ready_false_when_unhealthy`, `test_get_status_no_config_returns_error`, `test_retrieve_returns_error_envelope`, `test_get_role_context_returns_error_envelope`, `test_list_documents_returns_error_envelope`

## Dev Notes

### Pre-existing State (inherited from Stories 1.1–1.3)

`server.py` currently has:
- `mcp = FastMCP("cos")` — reuse; do NOT recreate
- `run()` calling: `CosConfig.load()` → `_log_startup(config)` → `asyncio.run(_apply_migrations(config))` → `mcp.run()`
- `_apply_migrations(config)` — calls `run_migrations()` then logs `{"message": "migrations applied"}`
- `_log_startup(config)` — logs `{"message": "config loaded", "role_pack_path": ...}`

Story 1.4 **deletes** both `_log_startup` and `_apply_migrations` and replaces them with `_startup_sequence`.

**CRITICAL — Tools NOT Currently Registered:** `tools.py` is never imported by `server.py`. The `@mcp.tool()` decorators in `tools.py` have never executed, so no tools are registered when `mcp.run()` is called. Story 1.4 MUST add `import cos.mcp_server.tools  # noqa: F401` at the top of `run()` to register all four tools before `mcp.run()`.

### `TikaConfig` in `config.py`

Add BEFORE `CosConfig`:
```python
class TikaConfig(BaseModel):
    url: str = "http://tika:9998"
```

Add to `CosConfig`:
```python
tika: TikaConfig = TikaConfig()
```

Using `= TikaConfig()` (not `= Field(default_factory=TikaConfig)`) is fine for Pydantic v2 with a no-arg constructor. The `tika` section in `config.yaml` is OPTIONAL — existing config files and all 27 existing tests continue to work without modification.

In `config.yaml.example`, add after the `database` section:
```yaml
tika:
  url: http://tika:9998
```

### Startup Sequence — Exact Log Order Required (AC #6)

Code loads config silently first (needed to get DB credentials and Tika URL), then emits in this order:

```python
async def _startup_sequence(config: CosConfig) -> None:
    component: LogComponent = "mcp_server"
    pg_ok = await _check_postgres(config.database.libpq_dsn)
    _emit(component, "INFO", "Postgres: healthy" if pg_ok else "Postgres: unhealthy")
    tika_ok = await _check_tika(config.tika.url)
    _emit(component, "INFO", "Tika: healthy" if tika_ok else "Tika: unhealthy")
    _emit(component, "INFO", "config loaded", role_pack_path=config.role_pack.path)
    await run_migrations(config.database.libpq_dsn)  # db.py emits per-file logs here
    _emit(component, "INFO", "migrations applied")
    _emit(component, "INFO", "role pack: stub loaded")
    _emit(component, "INFO", "MCP server: listening")
```

This produces log entries in the AC-required order: Postgres → Tika → config loaded → (per-file migration logs) → migrations applied → role pack → listening.

### `_emit` Helper

```python
def _emit(component: LogComponent, level: str, message: str, **extra: object) -> None:
    record: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": component,
        "message": message,
        **extra,
    }
    logging.info(json.dumps(record))
```

Pattern mirrors `OutputRouter` structured logging in `cos/src/cos/output/router.py`.

### Inline Health Checks in `server.py`

Startup uses inline functions (not `HealthService`) to avoid the service layer at boot:

```python
async def _check_postgres(dsn: str) -> bool:
    try:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False

async def _check_tika(url: str) -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            return resp.status_code < 500
    except Exception:
        return False
```

`httpx` is already in `pyproject.toml`. Add `import httpx` to `server.py` imports. Add `import psycopg` (psycopg3) to `server.py` imports.

### `get_config()` Accessor Pattern

```python
_config: CosConfig | None = None

def get_config() -> CosConfig | None:
    return _config
```

Set in `run()`:
```python
def run() -> None:
    global _config
    import cos.mcp_server.tools  # noqa: F401  — registers @mcp.tool() handlers
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = CosConfig.load()
    _config = config
    asyncio.run(_startup_sequence(config))
    mcp.run()
```

**CRITICAL — never import `_config` as a value from `tools.py`:**
```python
# WRONG — captures None at import time, never updates
from cos.mcp_server.server import _config

# CORRECT — callable, always returns current module-level value
from cos.mcp_server.server import get_config
config = get_config()
```

### `tools.py` — `get_status` Implementation

```python
import json
from cos.mcp_server.server import mcp, get_config
from cos.services.health import HealthService

@mcp.tool()
async def get_status() -> str:
    config = get_config()
    if config is None:
        return json.dumps({"status": "error", "error": "Server not initialized", "detail": "config not loaded yet"})
    health = HealthService(db_dsn=config.database.libpq_dsn, tika_url=config.tika.url)
    components = await health.check_all()
    ready = all(c["healthy"] for c in components)
    return json.dumps({"status": "ok", "data": {"components": components, "ready": ready}, "citations": []})
```

Stub error tools:
```python
@mcp.tool()
async def retrieve(query: str) -> str:
    return json.dumps({"status": "error", "error": "Not yet implemented", "detail": "retrieve is implemented in Story 3.4"})
```
Apply the same pattern to `get_role_context` and `list_documents` with appropriate story references.

### `HealthService` — Existing Test Must Be Replaced

`tests/services/test_health_service.py` currently calls `HealthService()` (no args) and expects `NotImplementedError`. Once `HealthService.__init__` requires `db_dsn` and `tika_url`, this test fails. **Delete** `test_check_all_not_implemented` and replace with new tests.

### Test Patterns for `tests/mcp_server/test_tools.py`

Tests must NOT hit real Postgres or Tika. Use `monkeypatch` to set `_config` and patch `HealthService.check_all`:

```python
from unittest.mock import AsyncMock, patch
import json
import cos.mcp_server.server as _server
import cos.mcp_server.tools  # ensure module + decorators are loaded
from cos.mcp_server.tools import get_status, retrieve, get_role_context, list_documents

async def test_get_status_returns_ok_envelope(monkeypatch):
    mock_config = MagicMock()
    mock_config.database.libpq_dsn = "postgresql://test:test@localhost/cos_test"
    mock_config.tika.url = "http://tika:9998"
    monkeypatch.setattr(_server, "_config", mock_config)

    healthy_components = [{"name": "postgres", "healthy": True}, {"name": "tika", "healthy": True}]
    with patch("cos.services.health.HealthService.check_all", new_callable=AsyncMock, return_value=healthy_components):
        result = json.loads(await get_status())

    assert result["status"] == "ok"
    assert result["data"]["ready"] is True
    assert result["citations"] == []
```

For stub tool tests (no config or HealthService needed):
```python
async def test_retrieve_returns_error_envelope():
    result = json.loads(await retrieve(query="test"))
    assert result["status"] == "error"
    assert "Not yet implemented" in result["error"]
```

`asyncio_mode = "auto"` is already in `pyproject.toml` — no `@pytest.mark.asyncio` needed.

### Architecture Constraints

- MCP tools call **only** `cos.services.*` — `get_status` uses `HealthService` from `cos.services.health` ✓
- No bare `print()` anywhere — use `_emit()` or `logging.*` with JSON payload
- `asyncio.run()` only at entry points — `_startup_sequence` is called via `asyncio.run()` in `run()` ✓
- Tools return `{"status": "error", ...}` for unimplemented paths — never `raise` to the MCP protocol layer

### Anti-Patterns

```python
# WRONG — tool raises instead of returning error envelope
async def retrieve(query: str) -> str:
    raise NotImplementedError  # causes protocol error; AC #4 forbids this

# WRONG — bare print
print("MCP server listening")  # AC #5 forbids bare print() anywhere in codebase

# WRONG — tools.py importing _config as a value (gets None at import time)
from cos.mcp_server.server import _config  # always None; use get_config() instead

# WRONG — recreating FastMCP in tools.py
mcp = FastMCP("cos")  # must import the existing mcp from server.py

# WRONG — tools calling store layer directly
from cos.store.db import run_migrations  # forbidden; tools use cos.services.* only

# WRONG — forgetting to import tools.py in run()
def run() -> None:
    mcp.run()  # tools never registered; client sees zero tools
```

### Files to Create or Modify

| File | Action | Notes |
|---|---|---|
| `cos/src/cos/config.py` | Modify | Add `TikaConfig`; add `tika: TikaConfig = TikaConfig()` to `CosConfig` |
| `cos/config.yaml.example` | Modify | Add `tika:` section |
| `cos/src/cos/services/health.py` | Modify | Replace stub with `HealthService(db_dsn, tika_url)` implementation |
| `cos/src/cos/mcp_server/server.py` | Modify | Add `_config`, `get_config()`, `_emit()`, `_startup_sequence()`, inline health checks; remove `_log_startup()`, `_apply_migrations()` |
| `cos/src/cos/mcp_server/tools.py` | Modify | Implement `get_status`; return error envelopes from other three tools |
| `cos/tests/mcp_server/__init__.py` | Create | Empty |
| `cos/tests/mcp_server/test_tools.py` | Create | Tests for all four tools |
| `cos/tests/services/test_health_service.py` | Modify | Replace `test_check_all_not_implemented` with real tests |
| `cos/tests/test_config.py` | Modify | Add `test_tika_config_defaults` |

Do NOT modify: `cos/src/cos/store/db.py`, `cos/src/cos/store/models.py`, `cos/src/cos/rolepack/loader.py`, `cos/src/cos/output/router.py`, `cos/tests/conftest.py`.

### References

- FastMCP pattern: [Source: architecture.md#Technology Choices Table, `mcp (MCP Python SDK)`]
- MCP tool response envelope: [Source: architecture.md#Format Patterns, "MCP Tool Response Envelope"]
- Module boundary rule — tools use services only: [Source: architecture.md#Enforcement Guidelines]
- Logging format: [Source: architecture.md#Format Patterns, "Logging"]
- No bare print: [Source: architecture.md#Anti-Patterns, "bare print"]
- httpx for async HTTP: [Source: architecture.md#Technology Choices Table, `httpx`]
- asyncio discipline: [Source: architecture.md#Process Patterns, "Async Discipline"]
- Story 1.4 requirements: [Source: epics.md#Story 1.4]
- Tika service name/port: [Source: cos/docker-compose.yml, `tika` service]
- `_emit` pattern mirrors: [Source: cos/src/cos/output/router.py]
- psycopg3 `AsyncConnection` pattern: [Source: 1-3-database-schema-and-migration-runner.md#Dev Notes]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `TikaConfig` as optional Pydantic model with default URL; all 27 existing config tests pass unmodified.
- Replaced `HealthService` stub with full async implementation using `psycopg` and `httpx`; 7 unit tests cover healthy/unhealthy paths via mocks (no real services hit).
- Rewrote `server.py`: added `_config` module-level accessor, `_emit()` structured JSON helper, inline `_check_postgres`/`_check_tika` boot functions, and `_startup_sequence()` emitting logs in AC-required order. Deleted `_log_startup` and `_apply_migrations`.
- Added `import cos.mcp_server.tools` in `run()` so all four `@mcp.tool()` decorators execute before `mcp.run()`.
- Rewrote `tools.py`: `get_status` calls `HealthService` and returns standard ok envelope; `retrieve`, `get_role_context`, `list_documents` return error envelopes — no unhandled exceptions.
- Added `tests/mcp_server/test_tools.py` with 8 tests covering all four tools (5 for get_status, 3 for stubs). Full suite: 42/42 passed.

### File List

- `cos/src/cos/config.py` — added `TikaConfig`; added `tika` field to `CosConfig`
- `cos/config.yaml.example` — added `tika:` section
- `cos/src/cos/services/health.py` — replaced stub with full `HealthService` implementation
- `cos/src/cos/mcp_server/server.py` — full rewrite: `_config`, `get_config()`, `_emit()`, `_startup_sequence()`, inline health checks; removed `_log_startup`, `_apply_migrations`
- `cos/src/cos/mcp_server/tools.py` — implemented `get_status`; error envelopes for three stub tools
- `cos/tests/mcp_server/__init__.py` — created (empty)
- `cos/tests/mcp_server/test_tools.py` — created with 8 tool tests
- `cos/tests/services/test_health_service.py` — replaced `test_check_all_not_implemented` with 7 real tests
- `cos/tests/test_config.py` — added `test_tika_config_defaults`

### Review Findings

- [x] [Review][Decision] Startup runs migrations even when Postgres is unhealthy — deferred to Story 1.5; Docker Compose `service_healthy` condition guarantees Postgres is up before cos starts, so this path is a genuine failure scenario, not a boot race
- [x] [Review][Patch] `_emit` always calls `logging.info` regardless of the `level` parameter — fixed: routes via `getattr(logging, level.lower(), logging.info)` [server.py:~30]
- [x] [Review][Patch] `get_status` returns `"ready": True` vacuously when `check_all()` returns an empty list — fixed: `bool(components) and all(...)` [tools.py:~15]
- [x] [Review][Patch] Error envelope tests don't assert `detail` field — fixed: added `assert "detail" in result` to all four tests [tests/mcp_server/test_tools.py]
- [x] [Review][Defer] `retrieve` stub ignores `query` parameter — expected for stub; parameter is part of the future API for Story 3.4 [tools.py:~19]
- [x] [Review][Defer] `httpx.AsyncClient` created per health-check call — minor inefficiency; acceptable for the call frequency of a health check, optimize if needed later [health.py:~26, server.py:~46]
- [x] [Review][Defer] Hardcoded credentials in `config.yaml.example` — pre-existing from Story 1.1/1.2, already noted in prior review
- [x] [Review][Defer] `run_migrations` behavior with multi-statement SQL — pre-existing from Story 1.3, not introduced here
- [x] [Review][Defer] No test for `run_migrations` raising during `_startup_sequence` — pre-existing gap from Story 1.3

## Change Log

- 2026-04-21: Story created by create-story workflow
- 2026-04-21: Story implemented by claude-sonnet-4-6 — MCP server foundation complete; 42/42 tests passing
- 2026-04-22: Code review complete — 1 decision needed, 3 patches, 5 deferred, 12 dismissed
