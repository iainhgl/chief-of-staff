# Story 4.2: Role Pack Loader & Startup Integration

Status: done

## Story

As an operator,
I want the platform to load and validate the configured role pack automatically at startup,
so that the role identity is active from the first query without any manual steps after `docker compose up`.

## Acceptance Criteria

1. **Given** `config.yaml` contains a valid `role_pack.path` pointing to a well-formed YAML file, **When** the `cos` container starts, **Then** `rolepack/loader.py` reads the file, parses it into a validated `RolePackConfig` instance, and `RolePackService.get_active()` returns that instance — replacing the stub `NotImplementedError` behaviour from Epic 1.

2. **Given** `config.yaml` points to a role pack YAML file that does not exist, **When** the container starts, **Then** startup fails with a `SystemExit` whose message identifies the missing file path — the platform does not start with a null or default role pack silently.

3. **Given** `config.yaml` points to a role pack YAML file with invalid content (bad YAML syntax or missing required field), **When** the container starts, **Then** startup fails with a human-readable `SystemExit` message identifying the problem — operators can diagnose and fix without reading source code.

4. **Given** the startup sequence completes successfully, **When** startup logs are inspected, **Then** a structured log entry confirms the role pack was loaded: `{"component": "rolepack", "level": "INFO", "message": "Role pack loaded", "role_name": "CHRO"}`.

5. **Given** `RolePackService.get_active()` is called multiple times, **When** it returns, **Then** it returns the same `RolePackConfig` instance that was loaded at startup — it does not re-read the file on every call.

## Tasks / Subtasks

- [x] Task 1: Add `"rolepack"` to `LogComponent` in `src/cos/config.py` (AC: #4)
  - [x] In `src/cos/config.py`, extend the `LogComponent` Literal to include `"rolepack"` — e.g. after `"output"` and `"config"`
  - [x] Verify existing `_emit()` calls in `server.py` continue to type-check (no changes needed, they already use valid components)

- [x] Task 2: Implement `RolePackService` in `src/cos/services/rolepack.py` (AC: #1, #5)
  - [x] Replace the stub class entirely with a typed implementation:
    ```python
    from cos.rolepack.loader import RolePackConfig

    class RolePackService:
        def __init__(self, role_pack: RolePackConfig) -> None:
            self._role_pack = role_pack

        def get_active(self) -> RolePackConfig:
            return self._role_pack
    ```
  - [x] No `Any` import — remove it
  - [x] `get_active()` must return the exact same object instance on every call (no re-loading)

- [x] Task 3: Wire role pack loading into `_startup_sequence` in `src/cos/mcp_server/server.py` (AC: #1, #2, #3, #4)
  - [x] Add imports at top of file: `import yaml`, `from pydantic import ValidationError`, `from cos.rolepack.loader import load as load_role_pack`, `from cos.services.rolepack import RolePackService`
  - [x] Add module-level global: `_role_pack_service: RolePackService | None = None`
  - [x] Add getter function: `def get_role_pack_service() -> RolePackService | None: return _role_pack_service`
  - [x] In `_startup_sequence`, **after** `run_migrations` and **before** `create_pool`, replace the existing `_emit(component, "INFO", "role pack: stub loaded")` line with:
    ```python
    global _role_pack_service
    try:
        _loaded_role_pack = load_role_pack(config.role_pack.path)
    except FileNotFoundError:
        raise SystemExit(
            f"Role pack file not found: {config.role_pack.path}\n"
            "Check role_pack.path in config.yaml."
        )
    except yaml.YAMLError as exc:
        raise SystemExit(
            f"Role pack YAML syntax error in {config.role_pack.path}:\n{exc}"
        )
    except ValidationError as exc:
        raise SystemExit(
            f"Role pack validation error in {config.role_pack.path}:\n{exc}"
        )
    _role_pack_service = RolePackService(role_pack=_loaded_role_pack)
    _emit("rolepack", "INFO", "Role pack loaded", role_name=_loaded_role_pack.role_name)
    ```
  - [x] Confirm `global _role_pack_service` is declared at the top of `_startup_sequence` alongside `global _config, _output_router, _pool, _retrieval_service, _output_service`

- [x] Task 4: Mount `role_packs/` in `docker-compose.yml` (AC: #1)
  - [x] In the `cos` service `volumes` block, add: `- ./role_packs:/app/role_packs:ro`
  - [x] This enables `role_packs/chro.yaml` to be accessible at `/app/role_packs/chro.yaml` inside the container (matching the relative path `role_packs/chro.yaml` from CWD `/app`)
  - [x] Place the new mount after `./config.yaml:/app/config.yaml:ro`

- [x] Task 5: Create `tests/services/test_rolepack_service.py` (AC: #1, #5)
  - [x] Create new file `tests/services/test_rolepack_service.py`
  - [x] Test `test_get_active_returns_loaded_role_pack`: instantiate a minimal `RolePackConfig`, pass to `RolePackService`, call `get_active()`, assert it returns the exact config object
  - [x] Test `test_get_active_returns_same_instance`: call `get_active()` twice on the same service, assert `result1 is result2`
  - [x] No DB needed — unit tests only, no fixtures required
  - [x] Use a minimal `RolePackConfig` constructed directly (do not load from file — that's tested in `test_loader.py`)

- [x] Task 6: Update `tests/mcp_server/test_server.py` to mock role pack loading (AC: #1, #2, #3)
  - [x] In `_patch_server()`, add a mock for the role pack loader so existing startup tests don't fail when `load_role_pack` is called:
    ```python
    from cos.rolepack.loader import RolePackConfig as _RolePackConfig

    mock_role_pack = _RolePackConfig(
        role_name="Test",
        goals=["goal"],
        tone="direct",
        knowledge_taxonomy=["cat"],
        stakeholder_map={"CEO": "partner"},
        retrieval_priorities=["cat"],
        active_workflows=["wf"],
        output_channels=["local"],
    )
    monkeypatch.setattr(server, "load_role_pack", lambda _path: mock_role_pack)
    monkeypatch.setattr(server, "_role_pack_service", None, raising=False)
    ```
  - [x] Add test `test_startup_sequence_initialises_role_pack_service`: after `_startup_sequence`, assert `server.get_role_pack_service()` is not None
  - [x] Add test `test_startup_sequence_role_pack_loaded_log`: assert an emitted log entry has component `"rolepack"` and message `"Role pack loaded"`
  - [x] Add test `test_startup_sequence_role_pack_file_not_found_raises_system_exit`: patch `load_role_pack` to raise `FileNotFoundError`, assert `pytest.raises(SystemExit)`, assert the exit message contains the path from config
  - [x] Add test `test_startup_sequence_role_pack_yaml_error_raises_system_exit`: patch `load_role_pack` to raise `yaml.YAMLError("bad syntax")`, assert `pytest.raises(SystemExit)`, assert message contains "YAML syntax error"
  - [x] Add test `test_startup_sequence_role_pack_validation_error_raises_system_exit`: patch `load_role_pack` to raise `ValidationError.from_exception_data(...)` — or simpler: patch to raise `SystemExit` directly via a stub — actually test by patching `load_role_pack` to raise `pydantic.ValidationError` and assert `pytest.raises(SystemExit)` with "validation error" in message

## Dev Notes

### Current State — What Exists From Story 4.1

The following are already implemented and must NOT be modified:
- `src/cos/rolepack/loader.py` — `RolePackConfig` (Pydantic v2 model, 8 required fields) and `load(path: str) -> RolePackConfig` function. Raises `FileNotFoundError`, `yaml.YAMLError`, or `ValidationError` — never catches them.
- `role_packs/chro.yaml` — CHRO role pack at `cos/role_packs/chro.yaml`
- `tests/rolepack/test_loader.py` — 4 tests covering valid load, missing field, file not found, invalid YAML

### Current State — What This Story Replaces

**`src/cos/services/rolepack.py`** (current stub):
```python
from typing import Any

class RolePackService:
    def get_active(self) -> Any:
        raise NotImplementedError
```
Replace entirely.

**`src/cos/mcp_server/server.py`** line 90 (current):
```python
_emit(component, "INFO", "role pack: stub loaded")
```
Replace this single line with the role pack loading block from Task 3.

**`src/cos/config.py`** — `LogComponent` does not include `"rolepack"`. Add it.

### Critical: docker-compose.yml Volume Gap

The Dockerfile (`WORKDIR /app`) does not COPY `role_packs/` into the image. The `docker-compose.yml` currently mounts:
```yaml
- ./data:/data
- ./config.yaml:/app/config.yaml:ro
- ./local/certs:/certs:ro
```
Without `./role_packs:/app/role_packs:ro`, `open("role_packs/chro.yaml")` inside the container raises `FileNotFoundError` at startup. This is the task-4 fix.

### Path Resolution

`config.role_pack.path` is `"role_packs/chro.yaml"` — a relative path. The `load()` function calls `open(path, encoding="utf-8")` which resolves relative to the process working directory. In Docker (WORKDIR `/app`), the path resolves to `/app/role_packs/chro.yaml`. In local development, it resolves relative to wherever `cos-mcp` or tests are launched from (typically `cos/`). No special path manipulation needed in Story 4.2 — the existing `open(path)` pattern is sufficient.

### Server Module Globals Pattern

`server.py` uses module-level globals for all services. Follow the exact same pattern:
```python
# Add at module level alongside existing globals:
_role_pack_service: RolePackService | None = None

# Add getter (alongside get_config, get_pool, etc.):
def get_role_pack_service() -> RolePackService | None:
    return _role_pack_service
```
The `global _role_pack_service` declaration goes inside `_startup_sequence` at the same line as the existing `global _config, _output_router, _pool, _retrieval_service, _output_service`.

### Log Message Format

The acceptance criteria specifies this exact structured log for success:
```json
{"component": "rolepack", "level": "INFO", "message": "Role pack loaded", "role_name": "CHRO"}
```
Use: `_emit("rolepack", "INFO", "Role pack loaded", role_name=_loaded_role_pack.role_name)`

`_emit` is the existing server helper that adds `timestamp` automatically. The `**extra` kwargs (`role_name=...`) are added to the JSON record as additional fields.

### SystemExit Error Messages

Mirror the `CosConfig.load()` pattern from `src/cos/config.py:101-109`. Messages must identify the file path so operators can diagnose without reading source code:
- File not found: `f"Role pack file not found: {config.role_pack.path}\nCheck role_pack.path in config.yaml."`
- YAML error: `f"Role pack YAML syntax error in {config.role_pack.path}:\n{exc}"`
- Validation error: `f"Role pack validation error in {config.role_pack.path}:\n{exc}"`

### Architecture Boundaries — What This Story Does NOT Touch

- `src/cos/mcp_server/tools.py` — `get_role_context` still returns the stub `"default — role pack not yet configured"`. Story 4.3 wires `RolePackService.get_active()` into tools.
- `src/cos/retrieval/search.py` — no role pack weight application. Story 4.3.
- `src/cos/llm/anthropic.py` — no tone injection. Story 4.3.
- `src/cos/rolepack/loader.py` — do not modify. Already done in Story 4.1.
- `tests/rolepack/test_loader.py` — do not modify. Already done in Story 4.1.

### Testing: Avoiding Pydantic ValidationError Construction Complexity

Constructing a `pydantic.ValidationError` directly in tests is verbose. For the validation error test case, the simplest approach:
```python
import yaml
from pydantic import ValidationError

# Easier: create a real ValidationError by calling model_validate with bad data
def _raise_validation_error(_path: str) -> None:
    from cos.rolepack.loader import RolePackConfig
    RolePackConfig.model_validate({})  # raises ValidationError — missing all fields

monkeypatch.setattr(server, "load_role_pack", _raise_validation_error)
```

### `_patch_server` Must Be Updated Before Adding New Tests

The existing `_patch_server()` helper in `tests/mcp_server/test_server.py` patches `_check_postgres`, `_check_tika`, `run_migrations`, `create_pool`, `AnthropicAdapter`, `RetrievalService`, and `_emit`. After Story 4.2, `_startup_sequence` calls `load_role_pack()` — the existing tests will fail unless `_patch_server` also mocks it. Update `_patch_server` first, then add new tests.

### Test Count Expectation

Before Story 4.2: 127 tests. After:
- New `tests/services/test_rolepack_service.py`: +2 tests
- New server startup tests: +5 tests
Expected total: ~134 tests. Run `uv run pytest` to confirm all pass.

### Project Structure Notes

- `src/cos/services/rolepack.py` — replace stub entirely, do not create a new file
- `src/cos/mcp_server/server.py` — targeted edits only; do not restructure existing startup logic
- `src/cos/config.py` — one-line change to `LogComponent` Literal
- `docker-compose.yml` — add one volume mount line
- `tests/services/test_rolepack_service.py` — NEW file (create it; `tests/services/__init__.py` does not exist and is not needed)
- `tests/mcp_server/test_server.py` — update `_patch_server` + add 5 new tests

### References

- `RolePackConfig` model and `load()` function: `src/cos/rolepack/loader.py`
- CHRO role pack YAML: `role_packs/chro.yaml`
- `RolePackService` stub to replace: `src/cos/services/rolepack.py`
- Startup sequence to modify: `src/cos/mcp_server/server.py:77-121`
- `LogComponent` Literal to extend: `src/cos/config.py:8-17`
- `docker-compose.yml` volumes block to update: `docker-compose.yml` (`cos` service)
- SystemExit pattern to follow: `src/cos/config.py:101-109`
- `_emit` helper: `src/cos/mcp_server/server.py:47-56`
- Existing startup tests to update: `tests/mcp_server/test_server.py`
- Architecture role pack boundary: `_bmad-output/planning-artifacts/architecture.md` — "Role Pack Management (FR21–24) → `cos/rolepack/`, `cos/services/rolepack.py`"
- Architecture startup sequence: `_bmad-output/planning-artifacts/architecture.md` — "load RolePackConfig → start MCP server"

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `uv run pytest tests/services/test_rolepack_service.py tests/mcp_server/test_server.py -q`
- `uv run pytest -q`
- `uv run ruff check src/cos/config.py src/cos/services/rolepack.py src/cos/mcp_server/server.py tests/mcp_server/test_server.py tests/services/test_rolepack_service.py`
- `uv run ruff check .` reports pre-existing repository-wide lint violations outside this story
- `uv run mypy src/cos/config.py src/cos/services/rolepack.py src/cos/mcp_server/server.py tests/mcp_server/test_server.py tests/services/test_rolepack_service.py` reports pre-existing typing issues around missing `yaml` stubs and the existing `SimpleNamespace` test pattern

### Completion Notes List

- Replaced the stub role pack service with a typed in-memory service that returns the same loaded `RolePackConfig` instance on every call.
- Wired role pack loading and validation into MCP server startup before pool creation, with structured success logging and human-readable `SystemExit` failures for missing files, YAML syntax errors, and validation errors.
- Mounted `role_packs/` into the `cos` container so `role_packs/chro.yaml` resolves correctly from `/app`.
- Added unit coverage for `RolePackService` and startup coverage for success plus failure cases around role pack loading.
- Verified the full test suite passes: `133 passed, 1 skipped`.

### File List

- `src/cos/config.py`
- `src/cos/services/rolepack.py`
- `src/cos/mcp_server/server.py`
- `docker-compose.yml`
- `tests/services/test_rolepack_service.py`
- `tests/mcp_server/test_server.py`

### Review Findings

- [x] [Review][Defer] `PermissionError`/`IsADirectoryError` not caught — crash instead of clean `SystemExit` [src/cos/mcp_server/server.py:98-112] — deferred, outside spec scope (spec defines FileNotFoundError, YAMLError, ValidationError only)
- [x] [Review][Defer] `UnicodeDecodeError` not caught for invalid UTF-8 role pack files [src/cos/mcp_server/server.py:98-112] — deferred, outside spec scope
- [x] [Review][Defer] Partial startup leaves `_role_pack_service` set while later globals remain None if `create_pool` fails [src/cos/mcp_server/server.py:86-119] — deferred, pre-existing globals pattern shared by all services

### Change Log

- 2026-04-28: Implemented story 4.2 by loading the configured role pack during startup, replacing the stub role pack service, mounting role packs in Docker, and adding role pack service/startup tests.
- 2026-04-29: Code review complete. 0 patches, 3 deferred, 4 dismissed.
