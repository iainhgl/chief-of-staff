# Story 5.5: Operator Validation — Recovery Scenario

Status: done

## Story

As Iain (operator and first user),
I want to run a documented recovery smoke test that proves the platform is genuinely operable by a non-technical user,
So that I can hand the platform to someone else with confidence they can keep it running.

## Acceptance Criteria

1. **Given** the platform is running healthily,
   **When** `cos status` is run,
   **Then** all components show as healthy in plain-language output with no technical jargon.

2. **Given** the `postgres` container is manually stopped with `docker stop $(docker compose ps -q postgres)`,
   **When** `cos status` is run,
   **Then** the output identifies Postgres as not running and states the recovery action: `Run: cos restart`

3. **Given** `cos restart` is run following the Postgres stop,
   **When** the command completes,
   **Then** all containers are healthy, `cos status` confirms full health, and the elapsed time from running `cos restart` to all-healthy is under 30 seconds.

4. **Given** the platform has recovered,
   **When** a `retrieve` query is submitted via Claude Desktop or Claude Code,
   **Then** a valid cited answer is returned — the recovery was genuine, not cosmetic.

5. **Given** `cos logs` is run after the recovery,
   **When** the output is reviewed,
   **Then** the restart event is visible in the logs, no credentials appear, and the log format is structured JSON throughout.

## Tasks / Subtasks

- [x] Task 1: Update `docs/manual-testing.md` header, capabilities, and Section 10 (AC: #1–5)
  - [x] Replace the header paragraph — change "Epic 4: Role Identity & Configuration" to "Epic 5: Platform Operations & Resilience"; update the summary line to mention recovery
  - [x] Replace "What Epic 4 delivers" section with "What Epic 5 delivers" — add the three CLI commands (`cos status`, `cos restart`, `cos logs`) as implemented capabilities; remove the stubs note on line 36
  - [x] Replace Section 10 (Restart round-trip, currently uses `docker compose down/up/ps`) with `uv run cos restart` + `docker compose exec cos uv run cos status` confirmation

- [x] Task 2: Add Epic 5 validation section to `docs/manual-testing.md` (AC: #1–5)
  - [x] Add Epic 5 prerequisites block (platform running, test docs ingested, valid `llm.api_key`)
  - [x] Add T5.5.1 — `docker compose exec cos uv run cos status` shows all-healthy plain-language table
  - [x] Add T5.5.2 — stop Postgres with `docker stop $(docker compose ps -q postgres)`, run `cos status`, assert Postgres failure line and recovery hint
  - [x] Add T5.5.3 — `uv run cos restart` recovers, final `cos status` confirms healthy, note timing caveat
  - [x] Add T5.5.4 — `retrieve` query returns cited answer (use existing `docker compose exec` python pattern)
  - [x] Add T5.5.5 — `uv run cos logs cos --since 5m` output review: restart event, no credential strings, JSON lines

- [x] Task 3: Update Section 11 quick-script (AC: #1)
  - [x] Add step 0 to the quick-script: `docker compose exec cos uv run cos status` before the ingest steps; assert all components healthy

## Dev Notes

### What This Story Is

Story 5.5 is an operator validation story. The dev agent's primary deliverable is an updated `docs/manual-testing.md`. The operator (Iain) runs through the tests manually and marks the story done. There are no automated test changes and no `src/` changes.

### Architecture Constraints

- No new source files. No new tests. No changes to `src/` or `tests/`.
- Changes are limited to: `docs/manual-testing.md` (update only)
- Do not modify any file in `src/`, `tests/`, `role_packs/`, `test-docs/`, `_bmad-output/`, or `docker-compose.yml`.

### Current State After Epic 5 Stories 5.1–5.4

By the end of Story 5.4, all Epic 5 CLI commands are fully operational:

| Command | Location | Notes |
|---------|----------|-------|
| `cos status` | `src/cos/cli.py:status()` | Plain-language table; exits 1 on any unhealthy component |
| `cos restart` | `src/cos/cli.py:restart()` | Calls `docker compose restart`, polls 30s for healthy, then confirms |
| `cos logs` | `src/cos/cli.py:logs()` | Wraps `docker compose logs`; supports `--since`, component filter |

The manual-testing.md currently says "Other CLI commands such as `cos status`, `cos logs`, and `cos restart` remain stubs." (line 36) — this line must be removed in Task 1.

### How to Run Each CLI Command

**Critical:** `cos restart` and `cos logs` call `subprocess.run(["docker", "compose", ...])` internally. The `cos` Docker container has no Docker CLI installed, so these commands cannot be run via `docker compose exec`. They must be run from the **HOST** machine where Docker is available.

**`cos status`** — run INSIDE the running `cos` container (uses Docker-network config where `host: postgres` resolves correctly):
```bash
docker compose exec cos uv run cos status
```

**`cos restart`** — run from the **HOST** (Docker CLI required; no config load needed):
```bash
uv run cos restart
```
`restart()` does not call `CosConfig.load()`. It only invokes `docker compose restart` and then polls `docker compose ps` until all services are healthy.

**`cos logs`** — run from the **HOST** (Docker CLI required; no config load needed):
```bash
uv run cos logs                        # last 100 lines from all containers
uv run cos logs cos                    # filter to the cos container
uv run cos logs --since 5m             # last 5 minutes
uv run cos logs cos --since 5m         # cos container, last 5 minutes
```
`logs()` does not call `CosConfig.load()`. It only invokes `docker compose logs`.

### `cos status` Output Format

**All healthy:**
```
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (N documents indexed)
```

**Postgres stopped (after `docker stop $(docker compose ps -q postgres)`):**
```
CoS Platform Status
-------------------
Postgres        ✗ container not running — Run: cos restart
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✗ could not connect — Run: cos restart
```

Both the Postgres and Database rows fail when Postgres is down — `_check_database()` in `health.py:118` also tries to connect. The `role_pack` check is independent (reads a local YAML file) and stays healthy.

From `_render_status_report()` at `src/cos/cli.py:293`:
```python
line = f"{status.name:<16}{icon} {message}"
if not status.healthy and status.recovery_hint:
    line += f" — {status.recovery_hint}"
```

### `cos restart` Timing Details

`_wait_for_healthy(timeout=30, poll_interval=2)` in `src/cos/cli.py:322` starts counting AFTER `docker compose restart` finishes. The 30-second budget is for the polling window only — total operator wall time includes the restart command duration too.

From `src/cos/cli.py:17`: `_RESTART_TIMEOUT = 30`, `_POLL_INTERVAL = 2`.

Success output:
```
Restarting platform...
Platform restarted. All components healthy.
```

Failure output (if a service stays stuck):
```
Restarting platform...
Tika did not become healthy. Run: cos logs tika
```

Exit code 0 on success, 1 on failure.

### `cos logs` After Restart

`cos logs cos --since 5m` outputs `docker compose logs --no-color --timestamps --since 5m cos`. After a restart, expect to see container start/stop events in the Docker log stream, followed by structured JSON log lines from the cos MCP server startup sequence.

The structured JSON log lines (from `src/cos/mcp_server/server.py`) look like:
```json
{"level": "INFO", "component": "rolepack", "message": "Role pack loaded", "role_name": "CHRO"}
{"level": "INFO", "component": "mcp_server", "message": "connection pool: open"}
{"level": "INFO", "component": "mcp_server", "message": "MCP server: listening"}
```

No API key, database password, or token values should appear in any line.

### Stopping Individual Containers for T5.5.2

```bash
docker stop $(docker compose ps -q postgres)
```

The `cos` container continues running after Postgres stops — `docker compose exec cos` will still succeed. The `cos status` command will fail its Postgres health check because it attempts a new connection on each call.

To restore: `uv run cos restart` (restarts all services including Postgres).

### Known Deferred Issues — Do Not Fix Here

- **`_any_containers_running` treats Docker-unavailable as "no containers"** (deferred from 5.3 review): If Docker itself is broken (socket down), `cos logs` prints "No containers running. Start the platform first." rather than a Docker error. This is acceptable; note it in T5.5.5 as a known limitation, not a test failure.
- **30-second timeout excludes restart duration** (deferred from 5.2 review): AC #3's "under 30 seconds" refers to the `_wait_for_healthy` polling window. Total wall time from operator pressing Enter to `Platform restarted` can be 35–40 seconds on a slow machine — note this in T5.5.3 so the operator is not surprised.

### `docs/manual-testing.md` — Exact Content Changes

#### New Header (replace lines 1–6 entirely)

```
# Manual Testing Guide

Reflects the platform as built at the end of **Epic 5: Platform Operations & Resilience**. Run these tests to verify the platform is healthy, documents are ingested, questions are answered with grounded citations, the CHRO role identity is active, and the platform recovers gracefully from component failures.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.
```

#### New "What Epic 5 delivers" Section (replace "## What Epic 4 delivers" block entirely)

```
## What Epic 5 delivers

- Full document ingestion pipeline: PDF, Word (`.docx`), Markdown, and plain text (from Epic 2)
- `cos ingest <path>` — ingest a single file or folder from the CLI
- `cos docs` — list all ingested documents with provenance metadata
- `cos docs --versions <id>` — show version history for a document
- `cos docs --json` — machine-readable JSON output
- All four MCP tools working end-to-end:
  - `get_status` — platform health and component status
  - `retrieve` — hybrid search + LLM synthesis with CHRO tone and retrieval priorities applied
  - `list_documents` — returns all ingested documents with `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`
  - `get_role_context` — returns full CHRO configuration: role name, goals, tone, knowledge taxonomy, active workflows
- Role pack system: define role identity in `role_packs/chro.yaml`; switch by editing `config.yaml` and restarting — no code change required
- Two role packs included: `role_packs/chro.yaml` (CHRO) and `role_packs/enterprise_architect.yaml`
- OutputRouter enforces fail-closed egress: unrecognised channels suppress output and log a structured error
- `cos status` — plain-language health table; identifies exactly which component failed and how to fix it; exits with code 1 when any component is unhealthy
- `cos restart` — single command that restarts all services and polls until all containers report healthy; prints confirmation or identifies the stuck component
- `cos logs` — single command log export; supports `--since <duration>` for time filtering and optional component filter
```

#### Updated Section 10 (Restart round-trip — replace lines 286–301 entirely)

```
## 10 — Restart round-trip

```bash
uv run cos restart
```

Wait for the command to complete — it polls until all containers are healthy (up to ~30 seconds of polling after the restart finishes).

**Expected:**
```
Restarting platform...
Platform restarted. All components healthy.
```

Confirm health:

```bash
docker compose exec cos uv run cos status
```

**Expected:** All five components healthy with `✓` icons and no recovery hints.

Follow up with test 2 (startup logs) to confirm clean restart.
```

#### New Epic 5 Validation Section (insert after the Epic 4 section, before `## 11 — Running all live tests`)

```
## Epic 5: Platform Operations & Resilience

**Prerequisites:**

- Platform running: `docker compose up -d` (all three services healthy)
- At least one document ingested (`cos ingest` or T2.6.1 already run — the `retrieve` test at T5.5.4 requires at least one indexed document)
- Working directory: `cos/`
- Valid `llm.api_key` in `config.yaml`

---

### T5.5.1 — `cos status` shows all components healthy [LIVE]

```bash
docker compose exec cos uv run cos status
```

**Expected:**
```
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (N documents indexed)
```

- All five rows have `✓` icons
- "Role pack" shows `CHRO loaded` (confirms role pack is active)
- "Database" shows a document count (N ≥ 0)
- No recovery hints appear
- No raw tracebacks or technical jargon

**Fail signal:** Any `✗` row, a missing component row, a raw Python exception, or the error `"cos status" is not a command` (indicates Epic 5 is not built on this branch).

---

### T5.5.2 — Postgres stopped: `cos status` identifies failure and recovery action [LIVE]

**Step 1:** Stop the Postgres container:
```bash
docker stop $(docker compose ps -q postgres)
```

**Step 2:** Immediately run `cos status`:
```bash
docker compose exec cos uv run cos status
```

**Expected:**
```
CoS Platform Status
-------------------
Postgres        ✗ container not running — Run: cos restart
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✗ could not connect — Run: cos restart
```

- Both Postgres and Database rows show `✗` (both depend on the Postgres connection)
- Recovery hint `Run: cos restart` appears on both failing rows
- Tika, MCP server, and Role pack rows are unaffected — they don't depend on Postgres
- No Docker internals, container IDs, or raw tracebacks in the output
- Command exits with code 1 (verify: `echo $?` returns `1`)

**Fail signal:** Output shows Postgres `✓ healthy` (it was stopped), raw traceback appears, or recovery hint is absent.

---

### T5.5.3 — `cos restart` recovers the platform within the 30-second polling window [LIVE]

Run from the **host** (Docker CLI required):

```bash
uv run cos restart
```

**Expected:**
```
Restarting platform...
Platform restarted. All components healthy.
```

Timing note: `cos restart` calls `docker compose restart` then polls for healthy state. The 30-second timeout is the polling window — total wall time from running the command to seeing the confirmation may be 35–45 seconds on a typical machine.

Confirm with status:
```bash
docker compose exec cos uv run cos status
```

**Expected:** All five components healthy (same output as T5.5.1). `cos restart` exits with code 0.

**Fail signal:** `did not become healthy` message, exit code 1, or `cos status` still shows any `✗` row after the restart command reported success.

---

### T5.5.4 — `retrieve` query returns a cited answer after recovery [LIVE]

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import retrieve

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await retrieve(query='What frameworks do I have for workforce segmentation?'))
    print(json.dumps(result, indent=2))
    assert result['status'] == 'ok', f'retrieve failed: {result}'
    assert result['data']['answer'] is not None, 'answer is null — synthesis failed'
    assert len(result['data']['citations']) > 0, 'No citations returned'
    print(f'retrieve ok after recovery: {len(result[\"data\"][\"citations\"])} citations')

asyncio.run(main())
"
```

**Expected:**

- `status` is `"ok"`
- `data.answer` is a non-empty string
- `data.citations` contains at least one item with `source_path`, `chunk_index`, `score`
- No error envelope or null answer

This confirms the recovery was genuine: the platform can synthesise and return grounded answers after a restart, not just report healthy containers.

**Fail signal:** `status != "ok"`, `data.answer` is null (synthesis failed), or `data.citations` is empty.

---

### T5.5.5 — `cos logs` shows restart event, structured JSON, no credentials [LIVE]

Run from the **host**:

```bash
uv run cos logs cos --since 5m
```

**Expected:**

- Output is a mix of Docker log timestamps and structured JSON log lines from the `cos` service
- The startup sequence is visible in the log: lines include `"message": "migrations applied"`, `"message": "Role pack loaded"`, `"message": "MCP server: listening"`
- All `cos`-service log lines are valid JSON objects (not plain text)
- No line contains: `api_key`, `get_secret_value`, `password`, `YOUR_API_KEY_HERE`, or any API key value
- Exit code 0

Run a quick credential scan:
```bash
uv run cos logs cos --since 5m | grep -E "api_key|get_secret_value|password" || echo "No credential strings found — ok"
```

**Expected:** No matches. Prints `No credential strings found — ok`.

**Known limitation (already deferred):** If Docker is unavailable (not just containers stopped), `cos logs` prints "No containers running. Start the platform first." rather than a Docker error. This is expected behaviour — not a test failure in this scenario.

**Fail signal:** Any log line containing an API key value, structured log lines in plain text (not JSON), or exit code 1.
```

#### Updated Section 11 Quick-Script (add step 0 before existing step 1)

Add this block at the top of the script, immediately after the `# 1. Start services` step (i.e., after `docker compose ps`):

```bash
# 0. Status check
docker compose exec cos uv run cos status
```

The expected output is the all-healthy table from T5.5.1. If any component is unhealthy, fix it before running the rest of the quick-script.

### Files to Create or Modify

- `docs/manual-testing.md`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

- Restore the missing Story 5.5 artifact on the fresh branch, move sprint tracking to `in-progress`, and treat `docs/manual-testing.md` as the only implementation target.
- Update the manual testing guide header, Epic capabilities summary, and restart round-trip section so Epic 5 CLI operations are documented as shipped behavior rather than stubs.
- Insert the new Epic 5 recovery validation walkthrough and adjust the quick-run script so operators verify `cos status` before the ingest-and-retrieve flow.

### Debug Log References

- `rg -n '^## ' docs/manual-testing.md`
- `rg -n 'remain stubs|What Epic 5 delivers|Epic 5: Platform Operations & Resilience|uv run cos restart|docker compose exec cos uv run cos status|No credential strings found' docs/manual-testing.md`
- `sed -n '1,60p' docs/manual-testing.md`
- `sed -n '840,930p' docs/manual-testing.md`

### Completion Notes List

- Updated `docs/manual-testing.md` to reflect Epic 5 rather than Epic 4, including the recovery-focused header text and the shipped `cos status`, `cos restart`, and `cos logs` CLI capabilities.
- Replaced the old restart round-trip with the real Epic 5 recovery flow using `uv run cos restart` plus in-container `cos status` confirmation.
- Added a dedicated Epic 5 operator validation section covering healthy status, intentional Postgres failure, recovery timing caveat, post-recovery `retrieve`, and post-recovery `cos logs` review guidance.
- Updated the all-tests quick script so operators run `cos status` before ingestion and stop early if the platform is not healthy.
- Verified the document structure and required phrases directly with `rg`/`sed`; no automated test suite was run because this story changes documentation only.
### File List

- `docs/manual-testing.md`
- `_bmad-output/implementation-artifacts/5-5-operator-validation-recovery-scenario.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Review Findings

- [x] [Review][Patch] Section 11 step numbering: `# 0. Status check` is placed after `# 1. Start services`, creating a 1→0→2 sequence — reorder so step 0 precedes step 1 [docs/manual-testing.md]
- [x] [Review][Patch] Section 10 missing `---` divider: removed by the diff with no replacement, leaving Section 10 running directly into `## Epic 2` with no visual break [docs/manual-testing.md]
- [x] [Review][Patch] T5.5.2 recovery dependency undocumented: no note that the platform stays broken until T5.5.3 runs — operator who pauses between tests has no in-section recovery path [docs/manual-testing.md]
- [x] [Review][Patch] T5.5.3 timing note understates maximum: "35-45 seconds" but `_run_docker_compose_restart` has a 30s subprocess timeout plus `_wait_for_healthy` has a 30s polling timeout = potentially ~60s total on a slow machine [docs/manual-testing.md]
- [x] [Review][Patch] T5.5.5 credential scan grep masks `cos logs` failure: `uv run cos logs ... | grep -E "..." || echo "ok"` — if `cos logs` fails with no output, grep finds nothing (exit 1), `||` fires and prints the false-positive "ok" [docs/manual-testing.md]
- [x] [Review][Defer] `docker compose ps -q postgres` may silently return empty string if Docker Compose container naming differs from service name — deferred, pre-existing Docker behavior; project defines service as `postgres`
- [x] [Review][Defer] T5.5.4 fresh subprocess doesn't test live running server's state — deferred, by design; spec acknowledges this as a proxy for Claude Desktop/MCP behaviour
- [x] [Review][Defer] T5.5.4 `_startup_sequence` runs `run_migrations` as side-effect without warning — deferred, pre-existing; migrations are idempotent
- [x] [Review][Defer] T5.5.4 `answer is not None` doesn't verify non-empty string — deferred, minor; empty answer would still be a visible failure in the printed JSON output
- [x] [Review][Defer] "three services" vs "five components" inconsistency in pre-existing doc sections — deferred, pre-existing; outside scope of this diff
- [x] [Review][Defer] sprint-status.yaml duplicate `last_updated` field in comment header and YAML data — deferred, pre-existing design
- [x] [Review][Defer] CosConfig.load('/app/config.yaml') hardcoded path fragile if volume mount changes — deferred, pre-existing; path matches current docker-compose.yml

### Change Log

- 2026-05-01: Updated the manual testing guide for Epic 5 recovery operations and added the operator recovery validation walkthrough.
