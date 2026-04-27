# Story 3.2: OutputRouter & Egress Enforcement

Status: done

## Story

As an operator,
I want all platform output to pass through a single validated routing layer,
So that responses are only ever delivered to explicitly configured channels and the platform never accidentally sends output to an unintended destination.

## Acceptance Criteria

1. **Given** `OutputRouter.send(channel, content)` is called with a channel name that exists in `CosConfig.channels`,
   **When** the router executes,
   **Then** the content is passed to the appropriate channel handler (`output/channels/local.py` for the `"local"` channel) and delivered successfully.

2. **Given** `OutputRouter.send(channel, content)` is called with a channel name that does not exist in `CosConfig.channels`,
   **When** the router executes,
   **Then** the output is suppressed entirely, a structured JSON error is logged with `component: "output"` and the channel name, and the method returns without raising an exception.

3. **Given** `output/channels/local.py` is the handler for the `"local"` channel,
   **When** it delivers content,
   **Then** the content is written to `sys.stdout` (captured by `capsys` in tests) — the MCP tool return value is the authoritative delivery mechanism in the MCP context; `local.py` handles the enforcement path.

4. **Given** `OutputService` in `services/output.py` wraps `OutputRouter`,
   **When** any MCP tool delivers a response,
   **Then** it calls `OutputService` which calls `OutputRouter` — no MCP tool ever calls a channel handler directly.

5. **Given** a test that deliberately passes an unrecognised channel to `OutputRouter`,
   **When** the router handles it,
   **Then** `tests/output/test_router.py` confirms the fail-closed behaviour: output suppressed, error logged, no exception raised.

## Tasks / Subtasks

- [x] Task 1: Implement `OutputService` constructor and `send()` (AC: #4)
  - [x] Replace the entire stub in `src/cos/services/output.py`
  - [x] Add `__init__(self, router: OutputRouter) -> None` — store `self._router = router`
  - [x] Add `async def send(self, channel: str, content: str) -> None` — delegate to `self._router.send(channel, content)`
  - [x] Import `OutputRouter` from `cos.output.router` at the top of the file
  - [x] Do NOT modify `OutputRouter`, `local.py`, or `tests/output/test_router.py`

- [x] Task 2: Wire `OutputRouter` construction in server startup (AC: #4)
  - [x] Add `_output_router: OutputRouter | None = None` module-level variable to `server.py`
  - [x] Add `get_output_router() -> OutputRouter | None` getter (parallel to `get_config()`)
  - [x] Inside `_startup_sequence`, construct `OutputRouter(configured_channels=config.channels)` and assign to `_output_router`
  - [x] Import `OutputRouter` from `cos.output.router` in `server.py`

- [x] Task 3: Write tests for `OutputService` (AC: #4, #5)
  - [x] Create `tests/services/test_output_service.py`
  - [x] `test_output_service_send_valid_channel_delegates_to_router` — use real `OutputRouter(["local"])`, assert content in stdout via `capsys`
  - [x] `test_output_service_send_invalid_channel_suppresses` — use real `OutputRouter(["local"])`, call `svc.send("unknown", ...)`, assert no exception, check `caplog` for error
  - [x] `test_output_service_delegates_to_router_send` — use `MagicMock` as router, assert `router.send` called with correct args

## Dev Notes

### What Is Already Done — Do Not Re-Implement

`src/cos/output/router.py` is **fully implemented** and all 5 tests in `tests/output/test_router.py` pass. Do not modify either file. The existing `OutputRouter`:
- `__init__(self, configured_channels: list[str]) -> None`
- `send(self, channel: str, content: str) -> None` — **sync, not async**
- Fail-closed: suppresses and logs structured JSON if channel not in `self._channels` or no handler registered
- `_CHANNEL_HANDLERS` dict maps `"local"` → `local_channel.send`

`src/cos/output/channels/local.py` is implemented as:
```python
def send(content: str) -> None:
    sys.stdout.write(content + "\n")
    sys.stdout.flush()
```
Do not modify. Tests capture stdout via `capsys`.

### Component Name — Architecture Is Authoritative

The epics spec says `component: "output_router"` but **`architecture.md` is the authoritative source**: the approved component values are `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`, `output`. The current `router.py` correctly uses `"component": "output"`. **Do NOT change it** — `"output_router"` is not in the approved list.

### OutputService Implementation

`OutputService` receives `OutputRouter` via constructor injection — never instantiate `OutputRouter` inside `send()` and never use a module-level singleton:

```python
from cos.output.router import OutputRouter


class OutputService:
    def __init__(self, router: OutputRouter) -> None:
        self._router = router

    async def send(self, channel: str, content: str) -> None:
        self._router.send(channel, content)
```

`send()` is `async` because future channels (Telegram, email) will involve real I/O. `self._router.send()` is sync — calling a sync function inside an async method is correct.

### Server Wiring

`server.py` uses a module-level `_config: CosConfig | None = None` with a `get_config()` getter. Mirror this pattern for `OutputRouter`:

```python
from cos.output.router import OutputRouter

_output_router: OutputRouter | None = None


def get_output_router() -> OutputRouter | None:
    return _output_router


async def _startup_sequence(config: CosConfig) -> None:
    global _output_router
    # ... existing Postgres check, Tika check, migrations ...
    _output_router = OutputRouter(configured_channels=config.channels)
    _emit(component, "INFO", "output router: initialised", channels=config.channels)
```

`config.channels` is `list[str]` (e.g. `["local"]`) — no transformation needed.

Story 3.4 will use `get_output_router()` when wiring the `retrieve` and `list_documents` MCP tools:
```python
# Future Story 3.4 pattern:
output_svc = OutputService(router=get_output_router())
await output_svc.send("local", formatted_response)
return formatted_response
```

### Phase 1 Local Channel Behavior

In Phase 1, the "local" channel is the MCP tool response path. The MCP tool returns the response string — that return value IS the delivery. `OutputService.send("local", content)` enforces the egress contract (validates channel is configured, suppresses + logs if not). In real MCP usage both happen: `local.py` writes to stdout AND the tool returns the content; FastMCP wraps only the return value in the JSON-RPC response.

### Test Patterns

```python
# tests/services/test_output_service.py

import logging
from unittest.mock import MagicMock

import pytest

from cos.output.router import OutputRouter
from cos.services.output import OutputService


@pytest.mark.asyncio
async def test_output_service_send_valid_channel_delegates_to_router(
    capsys: pytest.CaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    svc = OutputService(router=router)
    await svc.send("local", "hello world")
    assert "hello world" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_output_service_send_invalid_channel_suppresses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    svc = OutputService(router=router)
    with caplog.at_level(logging.ERROR):
        await svc.send("telegram", "should be suppressed")
    # must not raise; error should be logged by OutputRouter


@pytest.mark.asyncio
async def test_output_service_delegates_to_router_send() -> None:
    mock_router = MagicMock()
    svc = OutputService(router=mock_router)
    await svc.send("local", "test content")
    mock_router.send.assert_called_once_with("local", "test content")
```

No DB fixtures needed for `OutputService` tests — no conftest imports required.

### `tests/services/conftest.py` — Do Not Import It

`tests/services/conftest.py` contains `clean_tables` and `mock_embed` fixtures used by ingestion-related service tests. The `test_output_service.py` file does not use those fixtures — import nothing from it and do not add `clean_tables`/`mock_embed` to `test_output_service.py`.

### Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `src/cos/services/output.py` | Replace | `__init__` + `async send()` — full replacement of the 3-line stub |
| `src/cos/mcp_server/server.py` | Modify | Add `_output_router` global + `get_output_router()` + init in `_startup_sequence` |
| `tests/services/test_output_service.py` | Create | 3 tests for `OutputService` |

Do NOT modify: `src/cos/output/router.py`, `src/cos/output/channels/local.py`, `tests/output/test_router.py`.

## Dev Agent Record

### Agent Model Used

gpt-5.4

### Debug Log References

 - `uv run pytest tests/output/test_router.py tests/services/test_output_service.py tests/mcp_server/test_server.py -q`
 - `uv run pytest tests/mcp_server/test_tools.py -q`
 - `uv run pytest tests/ -q` (after starting `postgres` and `tika` with `docker compose up -d postgres tika`)
 - `uv run ruff check src/cos/services/output.py src/cos/mcp_server/server.py tests/services/test_output_service.py tests/mcp_server/test_server.py`

### Completion Notes List

- Implemented `OutputService` with constructor injection and async delegation to `OutputRouter`.
- Wired `OutputRouter` into MCP server startup with a module-level getter for later story use.
- Added unit coverage for `OutputService` plus a startup wiring test for `_output_router` initialization.
- Updated operator docs to use `/app/.venv/bin/cos` entrypoints for quieter one-off Docker commands.

### File List

- `src/cos/services/output.py`
- `src/cos/mcp_server/server.py`
- `tests/services/test_output_service.py`
- `tests/mcp_server/test_server.py`
- `docs/setup.md`
- `docs/manual-testing.md`

## Change Log

- 2026-04-27: Story created.
- 2026-04-27: Implemented OutputService routing, server startup wiring, test coverage, and operator doc command cleanup.

### Review Findings

Note: review was performed against `origin/main` (true PR base). Local `main` was 2 commits stale (Epic 2 bugfix already merged); extractor/embedder/cli findings were out of scope.

- [x] [Review][Patch] test_startup_sequence_initialises_output_router missing @pytest.mark.asyncio — fixed: added decorator; also refactored to shared helpers [tests/mcp_server/test_server.py]
- [x] [Review][Patch] Test asserts on private router._channels — fixed: replaced with `router.send("local", "probe")` + capsys stdout assertion [tests/mcp_server/test_server.py]
- [x] [Review][Patch] test_output_service_send_invalid_channel_suppresses does not assert suppression — fixed: added capsys + `"should be suppressed" not in out` assertion [tests/services/test_output_service.py]
- [x] [Review][Patch] Test missing: empty channels list in server startup — fixed: added test_startup_sequence_with_empty_channels_router_created [tests/mcp_server/test_server.py]

- [x] [Review][Defer] Server starts despite unhealthy Postgres/Tika — unhealthy checks only emit a log; pre-existing design, not introduced by this story [src/cos/mcp_server/server.py] — deferred, pre-existing
- [x] [Review][Defer] OutputRouter swallows handler exceptions — handler errors are caught and logged as JSON but not re-raised; pre-existing router behaviour not modified here [src/cos/output/router.py] — deferred, pre-existing
