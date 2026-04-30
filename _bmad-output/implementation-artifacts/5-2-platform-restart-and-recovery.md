# Story 5.2: Platform Restart & Recovery (`cos restart`)

Status: done

## Story

As an operator,
I want to restart the entire platform with a single command and have it confirm when everything is back up,
So that I can recover from failures without knowing which specific container failed or how Docker Compose works.

## Acceptance Criteria

1. **Given** the platform is running in any state (healthy or partially degraded), **When** `cos restart` is run, **Then** it executes `docker compose restart` for all services, waits for all containers to report healthy, and prints a confirmation: `Platform restarted. All components healthy.`

2. **Given** `cos restart` is run and all containers reach healthy state, **When** the elapsed time is measured, **Then** the platform is fully operational (all containers healthy, migrations applied, role pack loaded, MCP server listening) within 30 seconds.

3. **Given** `cos restart` is run after a `cos` container crash, **When** the container restarts, **Then** migrations re-run idempotently, the role pack reloads, and the MCP server resumes accepting connections — no manual database repair or file cleanup is required.

4. **Given** a container fails to reach healthy state within a timeout after restart, **When** `cos restart` detects this, **Then** it prints a plain-language message identifying the stuck component and advises running `cos logs` for diagnostic detail: `Tika did not become healthy. Run: cos logs tika`

5. **Given** `cos restart` completes successfully, **When** a query is immediately submitted via Claude Desktop or Claude Code, **Then** the `retrieve` tool responds correctly — the platform is genuinely operational, not just containers-reporting-healthy.

## Tasks / Subtasks

- [x] Task 1: Replace `restart()` stub in `cli.py` with working implementation (AC: #1, #4)
  - [x] Add `import json`, `import subprocess`, `import time` to top-level imports in `cli.py`
  - [x] Define module-level constants `_RESTART_TIMEOUT = 30`, `_POLL_INTERVAL = 2`, `_SERVICES = ("postgres", "tika", "cos")`, and `_DISPLAY_NAMES = {"postgres": "Postgres", "tika": "Tika", "cos": "MCP server"}`
  - [x] Replace `raise NotImplementedError` in `restart()` with: print "Restarting platform...", call `_run_docker_compose_restart()`, call `_wait_for_healthy()`, print success or failure message, exit with appropriate code
  - [x] Wrap the entire body in `try/except` — never allow a raw traceback to reach the terminal

- [x] Task 2: Add helper functions for restart logic (AC: #1, #2, #4)
  - [x] Add `_run_docker_compose_restart() -> None` — calls `subprocess.run(["docker", "compose", "restart"], capture_output=True, text=True)` and raises `RuntimeError` if `returncode != 0`
  - [x] Add `_wait_for_healthy(timeout: int = _RESTART_TIMEOUT, poll_interval: int = _POLL_INTERVAL) -> str | None` — polls `_first_unhealthy_service()` every `poll_interval` seconds; returns `None` if all healthy, or the stuck service name if timeout reached; polls at least once before checking deadline
  - [x] Add `_first_unhealthy_service() -> str | None` — runs `docker compose ps --format json`, parses NDJSON output, returns name of first service in `_SERVICES` that is not `"healthy"`, or `None` if all healthy
  - [x] Add `_parse_compose_ps_json(text: str) -> list[dict]` — parses Docker Compose v2 NDJSON (one JSON object per line); returns list of service dicts

- [x] Task 3: Tests in `tests/cli/test_cli_restart.py` (AC: #1, #4)
  - [x] Create `tests/cli/test_cli_restart.py` — use `typer.testing.CliRunner`; `tests/cli/__init__.py` already exists
  - [x] Test: all services healthy on first poll → exit 0, "Platform restarted. All components healthy." in output
  - [x] Test: `docker compose restart` returns non-zero → exit 1, no traceback in output
  - [x] Test: services remain stuck past timeout → exit 1, "{DisplayName} did not become healthy. Run: cos logs {service}" in output
  - [x] Test: unexpected exception during restart → exit 1, clean error message, no traceback

## Dev Notes

### What Exists Already

| Item | Location | Current State |
|------|----------|---------------|
| `restart()` CLI command | `src/cos/cli.py:33` | Raises `NotImplementedError` — replace body only |
| `logs()` CLI command | `src/cos/cli.py:39` | Also `NotImplementedError` — do NOT touch this story |
| `HealthService` | `src/cos/services/health.py` | Fully implemented (Story 5.1) — do NOT use for health polling in this story |
| `ComponentStatus` | `src/cos/services/health.py` | Fully implemented (Story 5.1) — not needed for restart |
| `tests/cli/__init__.py` | `tests/cli/__init__.py` | Already exists (created in Story 5.1) |
| `tests/cli/test_cli_status.py` | `tests/cli/test_cli_status.py` | Reference for CLI test pattern |
| `docker-compose.yml` | `docker-compose.yml` | Three services: `postgres`, `tika`, `cos` — all have healthchecks |

### Do NOT Use `HealthService` for Health Polling

`HealthService.check_all()` connects over the network to Postgres and Tika. `cos restart` is run by the operator from the host machine (where Docker and docker compose are available). Using `HealthService` would require host config.yaml to have correct DSNs and Tika URLs — fragile. Instead, use `docker compose ps --format json` to check Docker's own health status, which is more reliable and doesn't require service connectivity from the polling context.

### `restart()` Command Pattern

Follow the same try/except shell as `status()`:

```python
@app.command()
def restart() -> None:
    """Restart platform services."""
    try:
        typer.echo("Restarting platform...")
        _run_docker_compose_restart()
        stuck = _wait_for_healthy()
        if stuck is not None:
            display = _DISPLAY_NAMES.get(stuck, stuck.title())
            typer.echo(
                f"{display} did not become healthy. Run: cos logs {stuck}",
                err=True,
            )
            raise typer.Exit(code=1)
        typer.echo("Platform restarted. All components healthy.")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error restarting platform: {exc}", err=True)
        raise typer.Exit(code=1)
```

### Helper Function Implementations

```python
_RESTART_TIMEOUT = 30
_POLL_INTERVAL = 2
_SERVICES = ("postgres", "tika", "cos")
_DISPLAY_NAMES = {"postgres": "Postgres", "tika": "Tika", "cos": "MCP server"}


def _run_docker_compose_restart() -> None:
    result = subprocess.run(
        ["docker", "compose", "restart"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker compose restart failed")


def _wait_for_healthy(
    timeout: int = _RESTART_TIMEOUT, poll_interval: int = _POLL_INTERVAL
) -> str | None:
    """Poll until all services healthy or timeout. Returns stuck service name or None."""
    deadline = time.monotonic() + timeout
    while True:
        time.sleep(poll_interval)
        stuck = _first_unhealthy_service()
        if stuck is None:
            return None
        if time.monotonic() >= deadline:
            return stuck


def _first_unhealthy_service() -> str | None:
    """Return name of first non-healthy service, or None if all healthy."""
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "cos"
    text = result.stdout.strip()
    if not text:
        return "cos"
    try:
        services = _parse_compose_ps_json(text)
        healthy = {svc.get("Service", "") for svc in services if svc.get("Health") == "healthy"}
        for name in _SERVICES:
            if name not in healthy:
                return name
        return None
    except Exception:
        return "cos"


def _parse_compose_ps_json(text: str) -> list[dict]:
    """Parse docker compose ps --format json NDJSON output."""
    parsed = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    if parsed:
        return parsed
    # Fallback: JSON array format (older compose versions)
    return json.loads(text)
```

### `_wait_for_healthy` Loop Design

The loop polls **before** checking the deadline. This ensures at least one health check always executes. If that first poll finds all healthy, returns immediately without wasting time. If it finds a stuck service, checks if deadline has passed — if so, returns the stuck service name.

With `_POLL_INTERVAL = 2` and `_RESTART_TIMEOUT = 30`, up to 15 polls occur. Postgres and Tika healthchecks are set at 5s intervals in docker-compose.yml, so Docker's own health status should update well within the 30-second window.

### Docker Compose JSON Output Format

Docker Compose v2 (`docker compose ps --format json`) outputs NDJSON — one JSON object per line:

```json
{"ID":"abc","Name":"cos-postgres-1","Service":"postgres","State":"running","Health":"healthy","ExitCode":0}
{"ID":"def","Name":"cos-tika-1","Service":"tika","State":"running","Health":"starting","ExitCode":0}
{"ID":"ghi","Name":"cos-cos-1","Service":"cos","State":"running","Health":"healthy","ExitCode":0}
```

Key fields: `Service` (lowercase service name from docker-compose.yml), `Health` ("healthy", "unhealthy", "starting", or "" for no healthcheck).

`_parse_compose_ps_json` tries NDJSON first (each line parsed individually), then falls back to JSON array for older compose versions.

### Why AC #3 Is Satisfied Without Extra Code

AC #3 ("migrations re-run idempotently, role pack reloads, MCP server resumes") is satisfied by the existing architecture:
- `docker compose restart` restarts the `cos` container
- The `cos` container startup sequence (`server.py`) always runs `db.run_migrations()` at boot
- All migrations use `IF NOT EXISTS` — idempotent by construction
- Role pack is loaded at startup via `config.role_pack.path`
- MCP server resumes stdio transport automatically when the container starts

**No code changes required** in `server.py`, migrations, or role pack loader for this story.

### Module-Level Placement

Add the new imports and constants immediately after existing imports at the top of `cli.py`. Add the four helper functions (`_run_docker_compose_restart`, `_wait_for_healthy`, `_first_unhealthy_service`, `_parse_compose_ps_json`) immediately before or after the existing `_check_status` / `_render_status_report` helpers — keep all private helpers grouped together at the bottom of the file.

### Test File Structure

```python
# tests/cli/test_cli_restart.py
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app

runner = CliRunner()


def _ps_output(*services: tuple[str, str]) -> str:
    """Build NDJSON docker compose ps output."""
    return "\n".join(
        json.dumps({"Service": s, "State": "running", "Health": h})
        for s, h in services
    )


ALL_HEALTHY = _ps_output(("postgres", "healthy"), ("tika", "healthy"), ("cos", "healthy"))
TIKA_STUCK  = _ps_output(("postgres", "healthy"), ("tika", "starting"), ("cos", "healthy"))


def test_restart_prints_success_when_all_services_healthy() -> None:
    ok_restart = MagicMock(returncode=0, stderr="")
    ok_ps = MagicMock(returncode=0, stdout=ALL_HEALTHY)

    with (
        patch("cos.cli.subprocess.run", side_effect=[ok_restart, ok_ps]),
        patch("cos.cli.time.sleep"),
        patch("cos.cli.time.monotonic", side_effect=[0.0, 5.0]),
    ):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 0
    assert "Platform restarted. All components healthy." in result.output


def test_restart_exits_error_when_docker_compose_restart_fails() -> None:
    fail_restart = MagicMock(returncode=1, stderr="docker: command not found")

    with patch("cos.cli.subprocess.run", return_value=fail_restart):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Error" in result.output or result.exit_code == 1


def test_restart_reports_stuck_component_when_timeout_reached() -> None:
    ok_restart = MagicMock(returncode=0, stderr="")
    stuck_ps = MagicMock(returncode=0, stdout=TIKA_STUCK)

    with (
        patch("cos.cli.subprocess.run", side_effect=[ok_restart, stuck_ps]),
        patch("cos.cli.time.sleep"),
        # monotonic: [deadline setup] then [timeout check immediately exceeded]
        patch("cos.cli.time.monotonic", side_effect=[0.0, 31.0]),
    ):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Tika did not become healthy" in result.output
    assert "cos logs tika" in result.output


def test_restart_catches_unexpected_exceptions_without_traceback() -> None:
    with patch("cos.cli.subprocess.run", side_effect=FileNotFoundError("docker not found")):
        result = runner.invoke(app, ["restart"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "Error" in result.output
```

### Key File References

- `restart()` stub: `src/cos/cli.py:33`
- `logs()` stub (do not touch): `src/cos/cli.py:39`
- CLI test pattern reference: `tests/cli/test_cli_status.py`
- `docker-compose.yml` services + healthchecks: `docker-compose.yml`
- Architecture restart decision: `_bmad-output/planning-artifacts/architecture.md` — "Recovery | `cos restart` = `docker compose restart`; migrations re-run idempotently | 30-second recovery target (NFR9)"
- Architecture CLI spec: `_bmad-output/planning-artifacts/architecture.md` — "cli.py — Typer app — `cos` entry point. Commands: status, restart, logs, ingest"

### No Files to Avoid

Do NOT modify:
- `src/cos/services/health.py` — no changes needed
- `src/cos/mcp_server/tools.py` — no changes needed
- `src/cos/store/migrations/` — no schema changes needed
- `docs/setup.md` — updated in Story 5.6
- `docs/manual-testing.md` — updated at end of epic
- `cli.py logs()` stub — implemented in Story 5.3

### Test Execution

```bash
uv run pytest tests/cli/test_cli_restart.py -q
uv run ruff check src/cos/cli.py tests/cli/test_cli_restart.py
uv run mypy src/cos/cli.py
uv run pytest -q   # full regression
```

### Previous Story Context (Story 5.1)

Story 5.1 implemented `cos status` and `HealthService`. Key patterns to carry forward:
- Async pattern: `asyncio.run(_helper(config))` — `restart()` does NOT need this (subprocess calls are sync)
- Typer pattern: `typer.echo()` for output, `typer.echo(..., err=True)` for errors, `raise typer.Exit(code=N)` for exit codes
- Exception guard: wrap body in `try/except typer.Exit: raise` then `except Exception as exc:`
- `tests/cli/` directory already has `__init__.py` — no need to create it

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `uv run pytest tests/cli/test_cli_restart.py tests/cli/test_cli_status.py -q`
- `uv run ruff check src/cos/cli.py tests/cli/test_cli_restart.py tests/cli/test_cli_status.py`
- `uv run mypy src/cos/cli.py`
- `docker compose up -d`
- `/Users/iain.livingstone/Development/CoS/cos/.venv/bin/cos restart`
- `/Users/iain.livingstone/Development/CoS/cos/.venv/bin/pytest -q`
- `docker compose down`

### Completion Notes List

- Replaced the `cos restart` stub with a working Typer command that restarts the Compose stack, polls Docker health state, and reports operator-friendly success and failure messages.
- Added Docker Compose polling helpers for restart execution, health waiting, unhealthy service detection, and NDJSON/JSON-array parsing.
- Added CLI coverage for the restart happy path, Compose restart failures, timeout/stuck-service reporting, and unexpected exception handling without raw tracebacks.
- Validated the real operator flow by bringing the local stack up, running `cos restart`, and confirming the command returned `Platform restarted. All components healthy.`
- Full regression suite passed against the local Docker-backed test environment: `156 passed, 1 skipped`.

### File List

- `_bmad-output/implementation-artifacts/5-2-platform-restart-and-recovery.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `src/cos/cli.py`
- `tests/cli/test_cli_restart.py`

### Change Log

- 2026-04-30: Implemented `cos restart`, added restart CLI tests, and validated the feature with a live Compose restart plus full regression coverage.

## Code Review Record

### Review Date

2026-04-30

### Findings

- [x] [Review][Patch] `subprocess.run` called without `timeout` in both `_run_docker_compose_restart` and `_first_unhealthy_service` — a hung docker daemon blocks the CLI indefinitely; add `timeout=30` to the restart call and `timeout=5` to the ps poll call [`src/cos/cli.py:271,294`]
- [x] [Review][Patch] `_wait_for_healthy` sleeps 2s before the first health check — wastes 2s in the success path and reduces effective polling window; move `time.sleep(poll_interval)` to the end of the loop so the first check fires immediately after restart [`src/cos/cli.py:285`]
- [x] [Review][Patch] Success test `time.monotonic` mock has only `[0.0]` — fragile; if loop is restructured (patch above), second call raises `StopIteration`; update to `side_effect=[0.0, 5.0]` [`tests/cli/test_cli_restart.py:37`]
- [x] [Review][Patch] "did not become healthy" failure message uses `err=True` (stderr) — user guidance should go to stdout for consistency with how `cos status` shows unhealthy components; remove `err=True` from that `typer.echo` call [`src/cos/cli.py:75`]
- [x] [Review][Defer] `subprocess.run` called without `cwd` — docker compose resolves project via directory search; expected operator behaviour (running from project root); pre-existing pattern [`src/cos/cli.py`] — deferred, pre-existing
- [x] [Review][Defer] `_first_unhealthy_service` returns `"cos"` on all parse/run failure modes — conflates docker-not-found, empty output, and parse errors; reasonable safe fallback for Phase 1; Story 5.3 `cos logs` provides full diagnostics [`src/cos/cli.py:300,309`] — deferred, pre-existing
- [x] [Review][Defer] No distinction between container "unhealthy" vs "starting" states — both are treated as "not yet healthy"; beyond story scope; operator directed to `cos logs` for details — deferred, pre-existing
- [x] [Review][Defer] AC2 30-second timeout budget excludes restart command duration — total wall time from `cos restart` invocation can exceed 30s if `docker compose restart` itself is slow; integration concern for Story 5.5 operator validation — deferred, pre-existing
- [x] [Review][Defer] `_run_docker_compose_restart` only checks stderr for error detail; some docker versions write errors to stdout — minor P3; fallback message still meaningful [`src/cos/cli.py:277`] — deferred, pre-existing
