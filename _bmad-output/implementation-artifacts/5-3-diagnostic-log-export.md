# Story 5.3: Diagnostic Log Export (`cos logs`)

Status: done

## Story

As an operator,
I want to retrieve platform logs with a single command in a format I can send to Iain for support,
So that diagnosing problems does not require me to understand Docker log commands or navigate container filesystems.

## Acceptance Criteria

1. **Given** `cos logs` is run with no arguments, **When** it executes, **Then** it outputs the last 100 lines of structured JSON logs from all containers combined, ordered by timestamp — suitable for pasting into a support message.

2. **Given** `cos logs <component>` is run with a component name (e.g. `cos logs postgres`, `cos logs tika`, `cos logs cos`), **When** it executes, **Then** it outputs logs from only that container — allowing targeted diagnosis.

3. **Given** `cos logs --since 10m` is run, **When** it executes, **Then** it outputs only log entries from the last 10 minutes — useful for diagnosing a recent specific failure without scrolling through hours of history.

4. **Given** log output is inspected from any component, **When** the entries are reviewed, **Then** no API keys, OAuth tokens, or credential values appear anywhere in the log output — credentials are not logged even in debug entries.

5. **Given** `cos logs` is run when no containers are running, **When** it executes, **Then** it prints a clear message: `No containers running. Start the platform first: docker compose up -d` — not a Docker error.

## Tasks / Subtasks

- [x] Task 1: Replace `logs()` stub in `cli.py` with working implementation (AC: #1, #2, #3, #5)
  - [x] Add `_VALID_COMPONENTS = frozenset(_SERVICES)` module-level constant (reuses existing `_SERVICES` tuple — keeps the two in sync)
  - [x] Add `_any_containers_running() -> bool` helper — runs `docker compose ps -q --status=running` with `timeout=5`; returns `True` if stdout is non-empty
  - [x] Replace `raise NotImplementedError` in `logs()` with working implementation: validate component if provided, check containers running, build and run `docker compose logs` command, stream output, handle errors
  - [x] Use `--no-color` and `--timestamps` flags always; use `--tail 100` when `--since` is not given; pass `--since {value}` when given; append component name last if provided
  - [x] Wrap body in `try/except typer.Exit: raise` then `except Exception as exc:` — never let a raw traceback escape

- [x] Task 2: Define `logs()` Typer signature (AC: #2, #3)
  - [x] Add optional positional argument `component: str | None = typer.Argument(None, help="Component name: postgres, tika, or cos")`
  - [x] Add option `since: str | None = typer.Option(None, "--since", help="Show logs since duration (e.g. 10m, 1h)")`

- [x] Task 3: Tests in `tests/cli/test_cli_logs.py` (AC: #1, #2, #3, #5)
  - [x] Test: no-args call → subprocess invoked with `["docker", "compose", "logs", "--no-color", "--timestamps", "--tail", "100"]`; output printed; exit 0
  - [x] Test: `cos logs postgres` → command includes `"postgres"` at end; exit 0
  - [x] Test: `cos logs --since 10m` → command includes `"--since", "10m"` and does NOT include `"--tail"`; exit 0
  - [x] Test: invalid component → exit 1, no traceback, error message includes valid options
  - [x] Test: no containers running → `_any_containers_running()` returns False → "No containers running. Start the platform first: docker compose up -d"; exit 1
  - [x] Test: subprocess failure → exit 1, clean error message, no traceback

### Review Findings

- [x] [Review][Patch] Invalid-component error uses `err=True` (stderr) but no-containers error uses stdout — inconsistent routing; test passes only because CliRunner mixes streams by default; remove `err=True` from the invalid-component echo to align both error paths [`src/cos/cli.py` — `typer.echo(f"Unknown component: {component}..."`]
- [x] [Review][Defer] `_any_containers_running` treats non-zero returncode as "no containers" even when docker is unavailable — misleading operator message when Docker socket is down [`src/cos/cli.py:_any_containers_running`] — deferred, pre-existing
- [x] [Review][Defer] `subprocess.TimeoutExpired` from `_any_containers_running` surfaces as confusing "Error retrieving logs: ..." message — timeout occurred in status check, not log retrieval [`src/cos/cli.py:_any_containers_running`] — deferred, pre-existing

## Dev Notes

### What Exists Already

| Item | Location | Current State |
|------|----------|---------------|
| `logs()` CLI command | `src/cos/cli.py:62` | Raises `NotImplementedError` — replace body and add parameters |
| `_SERVICES` tuple | `src/cos/cli.py:18` | `("postgres", "tika", "cos")` — reuse for `_VALID_COMPONENTS` |
| `subprocess` import | `src/cos/cli.py:2` | Already imported (added in Story 5.2) |
| `time` import | `src/cos/cli.py:3` | Already imported (Story 5.2) |
| `_run_docker_compose_restart()` | `src/cos/cli.py:270` | Pattern reference for subprocess calls with timeout |
| `_first_unhealthy_service()` | `src/cos/cli.py:293` | Pattern reference — also calls `docker compose ps` |
| `tests/cli/__init__.py` | `tests/cli/__init__.py` | Already exists |
| `tests/cli/test_cli_restart.py` | `tests/cli/test_cli_restart.py` | Pattern reference for CLI + subprocess mocking |
| `docker-compose.yml` | `docker-compose.yml` | Services: `postgres`, `tika`, `cos` |

### `logs()` Signature

Typer signature to replace the current parameterless stub:

```python
@app.command()
def logs(
    component: str | None = typer.Argument(None, help="Component name: postgres, tika, or cos"),
    since: str | None = typer.Option(None, "--since", help="Show logs since duration (e.g. 10m, 1h)"),
) -> None:
    """Export platform logs for diagnosis or support."""
```

### `logs()` Command Body

```python
_VALID_COMPONENTS = frozenset(_SERVICES)

@app.command()
def logs(
    component: str | None = typer.Argument(None, help="Component name: postgres, tika, or cos"),
    since: str | None = typer.Option(None, "--since", help="Show logs since duration (e.g. 10m, 1h)"),
) -> None:
    """Export platform logs for diagnosis or support."""
    try:
        if component is not None and component not in _VALID_COMPONENTS:
            typer.echo(
                f"Unknown component: {component}. Valid options: {', '.join(sorted(_VALID_COMPONENTS))}",
                err=True,
            )
            raise typer.Exit(code=1)

        if not _any_containers_running():
            typer.echo("No containers running. Start the platform first: docker compose up -d")
            raise typer.Exit(code=1)

        cmd = ["docker", "compose", "logs", "--no-color", "--timestamps"]
        if since:
            cmd += ["--since", since]
        else:
            cmd += ["--tail", "100"]
        if component:
            cmd.append(component)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "docker compose logs failed")
        typer.echo(result.stdout, nl=False)
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Error retrieving logs: {exc}", err=True)
        raise typer.Exit(code=1)
```

### `_any_containers_running()` Helper

Add immediately after the existing `_parse_compose_ps_json` helper (end of file):

```python
def _any_containers_running() -> bool:
    """Return True if at least one Compose service container is running."""
    result = subprocess.run(
        ["docker", "compose", "ps", "-q", "--status=running"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.returncode == 0 and bool(result.stdout.strip())
```

### `_VALID_COMPONENTS` Placement

Add as a module-level constant immediately after `_DISPLAY_NAMES` (around line 17):

```python
_DISPLAY_NAMES = {"postgres": "Postgres", "tika": "Tika", "cos": "MCP server"}
_VALID_COMPONENTS = frozenset(_SERVICES)
```

Using `frozenset(_SERVICES)` ensures the two stay in sync — if a service is ever added to `_SERVICES`, it becomes valid for `cos logs` automatically. The frozenset gives O(1) membership testing.

### `--tail` vs `--since` Interaction

Do NOT combine `--tail 100` with `--since` — the tail cap would silently truncate results from the requested time window. When `--since` is given, omit `--tail` entirely so the operator sees all entries from that period.

```python
if since:
    cmd += ["--since", since]
else:
    cmd += ["--tail", "100"]
```

### Why `--no-color` and `--timestamps`

- `--no-color` — strips ANSI escape codes; clean plain text for pasting into a support message
- `--timestamps` — prepends Docker's RFC3339 timestamp before each line (`2026-04-30T12:00:00.123456789Z cos-1  | ...`); makes ordering visible and unambiguous when logs from multiple containers are interleaved

### `docker compose logs --since` Duration Format

Docker accepts Go duration strings: `"10m"`, `"1h"`, `"2h30m"`, `"30s"`. Pass the user's `--since` value directly to docker without validation — docker compose will surface a clear error for invalid formats.

### Output Handling

- Use `typer.echo(result.stdout, nl=False)` — `nl=False` preserves the exact output without adding an extra blank line, since docker compose logs already ends with `\n`
- If `result.stdout` is empty (containers running but no logs in window), print nothing — empty output is a valid result, not an error
- Route the docker error (non-zero exit) through `RuntimeError` → outer `except Exception` → `typer.echo(..., err=True)` with "Error retrieving logs: ..." — same pattern as `restart()`

### AC #4: Credentials in Logs

AC #4 is satisfied by the existing logging discipline across the platform (no credential fields are passed to `logging.*` calls). The `cos logs` command is a transparent pass-through of `docker compose logs` output — it does not add or filter anything. Story 5.4 performs the full audit. No filtering code is required here.

### No Files to Avoid

Do NOT modify:
- `src/cos/services/health.py` — no changes needed
- `src/cos/store/migrations/` — no schema changes
- `docs/setup.md` — updated in Story 5.6
- `docs/manual-testing.md` — updated at end of epic

### Test Patterns

Follow `tests/cli/test_cli_restart.py` exactly. The key mock target is `cos.cli.subprocess.run`.

For the no-containers test, mock `cos.cli._any_containers_running` directly (simpler than mocking subprocess):

```python
def test_logs_no_containers_running() -> None:
    with patch("cos.cli._any_containers_running", return_value=False):
        result = runner.invoke(app, ["logs"])
    assert result.exit_code == 1
    assert "No containers running. Start the platform first: docker compose up -d" in result.output
```

For the subprocess tests, `_any_containers_running` also calls `subprocess.run`. The cleanest approach: patch `_any_containers_running` to return `True` in all tests that focus on the log command itself, then test `_any_containers_running` separately.

```python
def test_logs_no_args_calls_docker_compose_logs() -> None:
    ok_result = MagicMock(returncode=0, stdout="log line 1\nlog line 2\n")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=ok_result) as mock_run,
    ):
        result = runner.invoke(app, ["logs"])

    assert result.exit_code == 0
    assert "log line 1" in result.output
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd == ["docker", "compose", "logs", "--no-color", "--timestamps", "--tail", "100"]


def test_logs_since_omits_tail_flag() -> None:
    ok_result = MagicMock(returncode=0, stdout="recent log\n")

    with (
        patch("cos.cli._any_containers_running", return_value=True),
        patch("cos.cli.subprocess.run", return_value=ok_result) as mock_run,
    ):
        result = runner.invoke(app, ["logs", "--since", "10m"])

    assert result.exit_code == 0
    called_cmd = mock_run.call_args[0][0]
    assert "--since" in called_cmd
    assert "10m" in called_cmd
    assert "--tail" not in called_cmd
```

### Key File References

- `logs()` stub: `src/cos/cli.py:62`
- `_SERVICES` constant: `src/cos/cli.py:18`
- `_DISPLAY_NAMES` constant: `src/cos/cli.py:19` (add `_VALID_COMPONENTS` after this)
- `_parse_compose_ps_json` (end of helpers): `src/cos/cli.py` — add `_any_containers_running()` after this
- Pattern reference: `tests/cli/test_cli_restart.py`
- Architecture logging decision: `_bmad-output/planning-artifacts/architecture.md` — "Logging | Structured JSON to stdout | Docker-native; `cos logs` wraps `docker compose logs`"
- Previous story (5.2): `_bmad-output/implementation-artifacts/5-2-platform-restart-and-recovery.md`

### Previous Story Context (Story 5.2)

Story 5.2 established the subprocess pattern for docker compose CLI wrappers. Key patterns for 5.3:
- `subprocess.run(cmd, capture_output=True, text=True, timeout=N)` — always set a timeout
- `result.returncode != 0` → `raise RuntimeError(result.stderr.strip() or "fallback message")`
- Wrap in `try/except typer.Exit: raise / except Exception as exc:` — never let traceback escape
- `tests/cli/test_cli_restart.py` — test pattern for subprocess mocking with `side_effect`
- `_any_containers_running()` is new but uses the same `docker compose ps` approach as `_first_unhealthy_service()`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

- Add `cos logs` CLI arguments and validation flow in `src/cos/cli.py`, reusing the existing Docker Compose subprocess pattern from Story 5.2.
- Add `_VALID_COMPONENTS` and `_any_containers_running()` helpers so the command can fail fast with operator-friendly messaging before calling `docker compose logs`.
- Add focused CLI tests in `tests/cli/test_cli_logs.py` for default, component-filtered, `--since`, invalid-component, no-containers, and subprocess-failure paths before implementing the command body.

### Debug Log References

- `uv run pytest tests/cli/test_cli_logs.py -q`  # red: 6 failed, then green: 6 passed
- `uv run pytest tests/cli/test_cli_status.py tests/cli/test_cli_restart.py tests/cli/test_cli_logs.py -q`
- `uv run ruff check src/cos/cli.py tests/cli/test_cli_logs.py tests/cli/test_cli_restart.py tests/cli/test_cli_status.py`
- `uv run mypy src/cos/cli.py`
- `docker compose up -d`
- `.venv/bin/cos logs --since 10m`
- `uv run pytest -q`
- `docker compose down`

### Completion Notes List

- Implemented `cos logs` with component validation, optional `--since` filtering, default `--tail 100`, and operator-friendly error handling around Docker Compose log export.
- Added `_VALID_COMPONENTS` and `_any_containers_running()` so the CLI can reject unknown services and return a clear “start the platform first” message before attempting log retrieval.
- Added focused CLI coverage for default combined logs, component filtering, `--since` behaviour, invalid component input, no-running-containers handling, and subprocess failures without raw tracebacks.
- Validated the command end-to-end by starting the Compose stack, running `.venv/bin/cos logs --since 10m`, and confirming timestamped container logs were returned from the live platform.
- Full regression suite passed with the local stack available: `162 passed, 1 skipped`.

### File List

- `_bmad-output/implementation-artifacts/5-3-diagnostic-log-export.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `src/cos/cli.py`
- `tests/cli/test_cli_logs.py`

### Change Log

- 2026-04-30: Implemented `cos logs`, added CLI coverage for log export scenarios, and validated the live Docker Compose log path plus full regression suite.
