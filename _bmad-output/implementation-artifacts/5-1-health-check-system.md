# Story 5.1: Health Check System (`cos status`)

Status: done

## Story

As an operator,
I want to check the health of all platform components with a single command that tells me exactly what is wrong and what to do about it,
So that I can diagnose problems without understanding Docker or Postgres internals.

## Acceptance Criteria

1. **Given** all containers are running and healthy, **When** `cos status` is run, **Then** the output shows a plain-language summary confirming each component is healthy:

   ```
   CoS Platform Status
   -------------------
   Postgres        ✓ healthy
   Tika            ✓ healthy
   MCP server      ✓ healthy
   Role pack       ✓ CHRO loaded
   Database        ✓ connected (N documents indexed)
   ```

2. **Given** the Postgres container is stopped, **When** `cos status` is run, **Then** the output clearly identifies Postgres as the failed component and includes a specific recovery instruction: `Postgres container not running. Run: cos restart`

3. **Given** the Tika container is unhealthy, **When** `cos status` is run, **Then** the output identifies Tika as the failed component with a specific recovery instruction — not a generic error.

4. **Given** the role pack YAML file cannot be found or parsed, **When** `cos status` is run, **Then** the output identifies the role pack as misconfigured and states the path that was checked: `Role pack not loaded — file not found: role_packs/chro.yaml. Check config.yaml role_pack_path.`

5. **Given** `HealthService.check_all()` is called, **When** it returns, **Then** it returns a list of `ComponentStatus` objects each with `name`, `healthy` (bool), `message` (plain English), and `recovery_hint` (plain English action to take) — and `cos status` formats these into the human-readable output.

6. **Given** `cos status` is run in any state, **When** the output is inspected, **Then** no raw exception tracebacks, Docker internal IDs, or technical jargon appear in the output — it is readable by a non-technical user.

## Tasks / Subtasks

- [x] Task 1: Add `ComponentStatus` dataclass and expand `HealthService` (AC: #2, #3, #4, #5)
  - [x] Add `ComponentStatus` dataclass to `cos/services/health.py` with fields `name`, `healthy`, `message`, `recovery_hint`
  - [x] Add `role_pack_path: str | None = None` to `HealthService.__init__` signature (backward-compatible)
  - [x] Rewrite `_check_postgres()` to return `ComponentStatus` with recovery hint `"Run: cos restart"`
  - [x] Rewrite `_check_tika()` to return `ComponentStatus` with recovery hint `"Run: cos restart"`
  - [x] Add `_check_role_pack()` — try to `load()` the YAML; on success include role name in message; on failure include path in message
  - [x] Add `_check_database()` — run `SELECT COUNT(*) FROM documents` and include count in message
  - [x] Add `_check_mcp_server()` — returns `ComponentStatus(name="MCP server", healthy=True, message="listening on stdio")` (always healthy when CLI is executing inside the container)
  - [x] Update `check_all()` to assemble all five `ComponentStatus` results in order: Postgres, Tika, MCP server, Role pack, Database

- [x] Task 2: Update `tools.py` `get_status` to work with `ComponentStatus` (AC: #5)
  - [x] Import `ComponentStatus` and adapt the `get_status` tool — use `dataclasses.asdict()` to serialize `ComponentStatus` objects to dicts for the MCP JSON envelope
  - [x] Keep the `{"name": "cos", "healthy": True}` top-level entry (or convert to a `ComponentStatus`) — ensure the `ready` flag and JSON shape are unchanged

- [x] Task 3: Implement `cos status` CLI command (AC: #1, #2, #3, #4, #6)
  - [x] Replace `raise NotImplementedError` in `cli.py status()` with a working implementation
  - [x] Load `CosConfig`, build `HealthService` with all five checks wired up
  - [x] Format output in the exact plain-language table shown in AC #1
  - [x] Exit with code 1 if any component is unhealthy (allows scripting)
  - [x] Catch all exceptions inside the command body — never let a raw traceback escape to the terminal

- [x] Task 4: Update tests (AC: #5)
  - [x] Update `tests/services/test_health_service.py` — rewrite existing tests to assert `ComponentStatus` objects instead of plain dicts; check `name`, `healthy`, `message`, `recovery_hint` fields
  - [x] Add tests for `_check_role_pack()`: file not found, YAML parse error, valid YAML
  - [x] Add tests for `_check_database()`: connected with 0 docs, connected with N docs, connection failure
  - [x] Add `tests/cli/test_cli_status.py` — use `typer.testing.CliRunner` to test `cos status` output format for healthy and unhealthy states

## Dev Notes

### What Exists Already

| Item | Location | Current State |
|------|----------|---------------|
| `HealthService` | `src/cos/services/health.py` | Exists — returns `list[dict]` with `name` + `healthy` only; no messages or recovery hints |
| `_check_postgres()` | `src/cos/services/health.py:18` | Returns `bool` — needs to return `ComponentStatus` |
| `_check_tika()` | `src/cos/services/health.py:26` | Returns `bool` — needs to return `ComponentStatus` |
| `get_status` MCP tool | `src/cos/mcp_server/tools.py:15` | Uses `HealthService(db_dsn, tika_url)` and consumes plain dicts |
| `status()` CLI command | `src/cos/cli.py:14` | Raises `NotImplementedError` |
| `cos/health.py` | `src/cos/health.py` | Stub docstring only — do NOT use or modify |
| Existing health tests | `tests/services/test_health_service.py` | Tests current dict return shape — will need updating |

### Critical: `HealthService` Return Type Change Breaks `tools.py`

The existing `HealthService.check_all()` returns `list[dict[str, object]]`. The MCP `get_status` tool consumes these as plain dicts:

```python
# tools.py current — WILL BREAK after Task 1
components = [{"name": "cos", "healthy": True}] + await health.check_all()
ready = bool(components) and all(c["healthy"] for c in components)
```

After Task 1, `check_all()` returns `list[ComponentStatus]`. **Task 2 must update `tools.py`** to use `dataclasses.asdict()` for serialization:

```python
from dataclasses import asdict
# ...
statuses = await health.check_all()
cos_status = ComponentStatus(name="cos", healthy=True, message="healthy", recovery_hint="")
all_statuses = [cos_status] + statuses
ready = all(s.healthy for s in all_statuses)
components = [asdict(s) for s in all_statuses]
```

The MCP JSON response shape must remain unchanged: `{"status": "ok", "data": {"components": [...], "ready": bool}, "citations": []}`.

### `ComponentStatus` Dataclass

Place this in `cos/services/health.py` (before the `HealthService` class):

```python
from dataclasses import dataclass

@dataclass
class ComponentStatus:
    name: str
    healthy: bool
    message: str
    recovery_hint: str = ""
```

### `HealthService` Constructor Backward Compatibility

The current signature is `__init__(self, db_dsn: str, tika_url: str)`. Add `role_pack_path` as an optional third argument so existing callers (`tools.py`) do not need changing for construction:

```python
def __init__(self, db_dsn: str, tika_url: str, role_pack_path: str | None = None) -> None:
    self._db_dsn = db_dsn
    self._tika_url = tika_url
    self._role_pack_path = role_pack_path
```

The `cli.py status()` command passes `role_pack_path=config.role_pack.path`. `tools.py` does not pass it (no change needed to its constructor call).

When `role_pack_path` is `None`, `_check_role_pack()` should return:
```python
ComponentStatus(name="Role pack", healthy=False, message="not configured", recovery_hint="Set role_pack.path in config.yaml")
```

### Role Pack Check

Use `cos.rolepack.loader.load` — this is the existing loader:

```python
from cos.rolepack.loader import load as load_role_pack
from pydantic import ValidationError
import yaml

async def _check_role_pack(self) -> ComponentStatus:
    if self._role_pack_path is None:
        return ComponentStatus(name="Role pack", healthy=False,
                               message="not configured",
                               recovery_hint="Set role_pack.path in config.yaml")
    try:
        rp = load_role_pack(self._role_pack_path)
        return ComponentStatus(name="Role pack", healthy=True,
                               message=f"{rp.role_name} loaded")
    except FileNotFoundError:
        return ComponentStatus(name="Role pack", healthy=False,
                               message=f"file not found: {self._role_pack_path}",
                               recovery_hint="Check config.yaml role_pack_path.")
    except (yaml.YAMLError, ValidationError) as exc:
        return ComponentStatus(name="Role pack", healthy=False,
                               message=f"invalid YAML or schema: {exc}",
                               recovery_hint="Fix the role pack file and restart.")
```

Note: `_check_role_pack` is a sync operation (file I/O via `open()`), but `check_all()` is async. Either keep it as a regular method called with `await asyncio.to_thread()`, or simply call it synchronously from `check_all()`. Calling it synchronously is acceptable for file I/O at this scale.

### Database Check

```python
async def _check_database(self) -> ComponentStatus:
    try:
        async with await psycopg.AsyncConnection.connect(self._db_dsn) as conn:
            row = await conn.execute("SELECT COUNT(*) FROM documents")
            count = (await row.fetchone())[0]
        return ComponentStatus(name="Database", healthy=True,
                               message=f"connected ({count} documents indexed)")
    except Exception:
        return ComponentStatus(name="Database", healthy=False,
                               message="could not connect",
                               recovery_hint="Run: cos restart")
```

### `check_all()` Order

The five components must appear in this order to match the AC output:

```python
async def check_all(self) -> list[ComponentStatus]:
    return [
        await self._check_postgres(),
        await self._check_tika(),
        self._check_mcp_server(),
        self._check_role_pack(),
        await self._check_database(),
    ]
```

### `cos status` Output Format

The exact format from AC #1:

```
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (42 documents indexed)
```

For unhealthy components, the status line shows the message and the recovery hint on the same line:

```
Postgres        ✗ could not connect — Run: cos restart
```

Column width: component name left-padded to 16 characters, then `✓` or `✗`, then message. If `recovery_hint` is non-empty, append ` — {recovery_hint}`.

### `cli.py status()` Implementation Pattern

Follow the same pattern as `docs()` — load config, construct the service, run async, use `typer.echo()` for output, catch all exceptions:

```python
@app.command()
def status() -> None:
    """Show platform health status."""
    try:
        config = CosConfig.load()
        statuses = asyncio.run(_check_status(config))
    except Exception as exc:
        typer.echo(f"Error running status check: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo("CoS Platform Status")
    typer.echo("-------------------")
    all_healthy = True
    for s in statuses:
        icon = "✓" if s.healthy else "✗"
        line = f"{s.name:<16}{icon} {s.message}"
        if not s.healthy and s.recovery_hint:
            line += f" — {s.recovery_hint}"
        typer.echo(line)
        if not s.healthy:
            all_healthy = False

    if not all_healthy:
        raise typer.Exit(code=1)

async def _check_status(config: CosConfig) -> list[ComponentStatus]:
    from cos.services.health import HealthService
    svc = HealthService(
        db_dsn=config.database.libpq_dsn,
        tika_url=config.tika.url,
        role_pack_path=config.role_pack.path,
    )
    return await svc.check_all()
```

Import `ComponentStatus` at the top of `cli.py` from `cos.services.health` (only if the type is referenced in function signatures — otherwise defer the import into the function to avoid circular imports).

### `get_status` MCP Tool — Existing Shape Must Be Preserved

The `get_status` MCP tool currently returns:
```json
{"status": "ok", "data": {"components": [{"name": "...", "healthy": bool}, ...], "ready": bool}, "citations": []}
```

After Task 2, `components` items will also include `message` and `recovery_hint` fields (from `asdict(ComponentStatus)`). This is an additive change — no existing client breaks. The `ready` flag logic is unchanged.

The `cos` component entry (added in `tools.py`, not from `HealthService`) should also become a `ComponentStatus`:

```python
cos_status = ComponentStatus(name="cos", healthy=True, message="healthy", recovery_hint="")
```

### Service Layer Boundary

`cli.py` must only import from `cos/services/*`. The `ComponentStatus` dataclass lives in `cos/services/health.py` and is importable by `cli.py`.

Do NOT import from `cos/rolepack/loader.py` directly in `cli.py`. The role pack check is handled inside `HealthService._check_role_pack()` in `cos/services/health.py`, which is permitted to import from `cos/rolepack/`.

### Existing Tests Will Break

`tests/services/test_health_service.py` asserts `result == [{"name": "postgres", "healthy": True}, ...]`. These assertions must be updated to compare `ComponentStatus` objects or their fields:

```python
assert result[0] == ComponentStatus(name="Postgres", healthy=True, message="healthy", recovery_hint="")
# or
assert result[0].healthy is True
assert result[0].name == "Postgres"
```

Note: Check whether the component name is `"postgres"` (lowercase, current) or `"Postgres"` (title case, per AC output). **Use title case** (`"Postgres"`, `"Tika"`, `"MCP server"`, `"Role pack"`, `"Database"`) to match the AC output table exactly.

### No Files to Avoid

Do NOT modify:
- `docs/manual-testing.md` — updated at end of epic
- `docs/setup.md` — updated in Story 5.6
- `src/cos/health.py` — stub, leave as-is
- `role_packs/` — no changes
- `src/cos/store/migrations/` — no schema changes needed

### Tests Directory Pattern

If `tests/cli/` does not exist, create it with an `__init__.py`. Follow the existing pattern in `tests/services/`.

Use `typer.testing.CliRunner` for CLI tests:
```python
from typer.testing import CliRunner
from cos.cli import app

runner = CliRunner()

def test_status_all_healthy(monkeypatch):
    # patch HealthService.check_all to return healthy ComponentStatus list
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "✓ healthy" in result.output
```

### Key File References

- `HealthService`: `src/cos/services/health.py`
- `cli.py status()`: `src/cos/cli.py:14`
- `get_status` tool: `src/cos/mcp_server/tools.py:15`
- Role pack loader: `src/cos/rolepack/loader.py` — `load(path: str) -> RolePackConfig`
- `CosConfig`: `src/cos/config.py` — `config.role_pack.path`, `config.database.libpq_dsn`, `config.tika.url`
- Existing health tests: `tests/services/test_health_service.py`
- Architecture health spec: `_bmad-output/planning-artifacts/architecture.md` — service layer boundary, `ComponentStatus` contract

### Previous Story Context (Story 4.6)

Story 4.6 was documentation-only. No code patterns from 4.6 are relevant. The implementation patterns that matter for 5.1 come from Epics 1–4:
- Async pattern: `asyncio.run(_helper(config))` in CLI commands (see `ingest`, `docs`)
- Service construction: `ServiceClass(config_fields...)` — not `ServiceClass(config)` in the service layer
- Typer CLI: `typer.echo()` for output, `raise typer.Exit(code=N)` for exit codes
- Exception handling in CLI: wrap `asyncio.run()` call in try/except, print clean message, exit 1

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `uv run pytest tests/services/test_health_service.py tests/cli/test_cli_status.py tests/mcp_server/test_tools.py -q`
- `uv run ruff check src/cos/services/health.py src/cos/mcp_server/tools.py src/cos/cli.py tests/services/test_health_service.py tests/cli/test_cli_status.py tests/mcp_server/test_tools.py`
- `uv run mypy src/cos` (pre-existing failures remain in `src/cos/config.py`, `src/cos/rolepack/loader.py`, and `src/cos/llm/anthropic.py`)
- `docker compose up -d postgres tika`
- `uv run pytest -q`
- `docker compose down`

### Completion Notes List

- Implemented `ComponentStatus`-based health reporting for Postgres, Tika, MCP server, role pack, and database document count.
- Replaced the `cos status` stub with a user-friendly CLI report that exits non-zero for unhealthy components and suppresses raw tracebacks.
- Updated MCP `get_status` serialization to preserve the existing JSON envelope while adding `message` and `recovery_hint` fields to component payloads.
- Added CLI coverage plus expanded health service and MCP status tests.
- Full regression suite passed with local Postgres and Tika services running: `152 passed, 1 skipped`.

### File List

- `_bmad-output/implementation-artifacts/5-1-health-check-system.md`
- `src/cos/cli.py`
- `src/cos/mcp_server/tools.py`
- `src/cos/services/health.py`
- `tests/cli/__init__.py`
- `tests/cli/test_cli_status.py`
- `tests/mcp_server/test_tools.py`
- `tests/services/test_health_service.py`

### Change Log

- 2026-04-30: Implemented the health check system for `cos status`, updated MCP health payloads, and added service/CLI/MCP test coverage.

## Code Review Record

### Review Date

2026-04-30

### Findings

**P1 — `tools.py` omits `role_pack_path`: `ready` always `False` in production [PATCH]**
`tools.py` constructs `HealthService(db_dsn=..., tika_url=...)` without `role_pack_path`. `_check_role_pack()` returns `healthy=False` when path is `None`, so `ready = all(component["healthy"] ...)` is always `False`. Fix: pass `role_pack_path=config.role_pack.path`.

**P2 — `test_get_status_all_components_present` asserts wrong component count [PATCH]**
Test mocks `check_all` to return 2 items (Postgres + Tika), then asserts `len(components) == 3`. Production `check_all` returns 5 items; `get_status` prepends the `"cos"` component, giving 6 total. Test must mock 5 items and assert 6.

**P3 — Fixture override intent in `test_health_service.py` is non-obvious [PATCH]**
`migrated_db` and `clean_tables` in `test_health_service.py` are local overrides of the directory conftest's autouse `clean_tables(migrated_db)` — without them every health service test requires a live DB. The no-op yield bodies are correct, but the override intent was invisible. Add an explanatory comment so future maintainers don't remove them.

**N1 — `_check_tika` marks 4xx responses as healthy**
`status_code < 500` means a 404 (wrong Tika URL) reports as healthy. Standard health check practice is `status_code == 200`. Non-blocking for this story.

**N2 — AC #2 wording uses em-dash separator; AC example implies dot-join**
AC says "includes: `Postgres container not running. Run: cos restart`". Implementation renders `Postgres ✗ container not running — Run: cos restart`. Dev Notes explicitly show the em-dash format, so this matches design intent. Non-blocking.

**N3 — `_display_status_message` hardcodes `"MCP server"` string literal**
If `_check_mcp_server` ever changes the component name, the display override silently stops applying. Acceptable coupling at this scale; note for future rename awareness.

**N4 — Double Postgres connections per `check_all()` call**
`_check_postgres` and `_check_database` each open a separate `AsyncConnection`. Minor overhead for an infrequent health check; acceptable for this stage.

**N5 — Top-level CLI `except` prints raw `str(exc)` for unexpected errors**
Individual check methods catch and translate their own exceptions; this fallback only fires for unexpected errors in `asyncio.run` or config loading. Narrow edge case.

### Patches Applied

- P1: Pass `role_pack_path=config.role_pack.path` to `HealthService` in `tools.py`
- P2: Update `test_get_status_all_components_present` — mock 5 items, assert `len == 6`
- P3: Add override comment to `migrated_db` and `clean_tables` fixtures in `test_health_service.py`
