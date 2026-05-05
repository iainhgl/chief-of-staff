# Story 5.6: Documentation & Housekeeping

Status: done

## Story

As Iain (operator and platform maintainer),
I want `docs/setup.md` to include a complete operations reference that a non-technical user can follow without assistance,
So that the platform can be handed over to another person with a simple setup card.

## Acceptance Criteria

1. **Given** `docs/setup.md` is updated for Epic 5, **When** it is reviewed, **Then** it includes a dedicated Operations section covering: `cos status` (what it shows, how to read it), `cos restart` (when and how to use it), `cos logs` (how to capture and send logs for support), and a three-step recovery procedure for the most common failure (Postgres not running).

2. **Given** a one-page setup card could be extracted from `docs/setup.md`, **When** the operations section is reviewed by someone unfamiliar with Docker, **Then** they can follow the restart and diagnostic steps without needing to understand what Postgres or Tika are — commands are given verbatim with expected output shown.

3. **Given** the root `README.md` is updated, **When** it is reviewed, **Then** it references `docs/setup.md` for operations guidance and accurately describes the current Phase 1 capabilities including the CLI commands available.

4. **Given** any deviations from `architecture.md` during Epic 5, **When** `architecture.md` is reviewed, **Then** the operations and CLI sections reflect what was built.

5. **Given** all Epic 5 documents are reviewed together, **When** cross-checked for consistency, **Then** CLI command syntax, expected output, and recovery steps are identical across `docs/setup.md`, `README.md`, and `architecture.md`.

## Tasks / Subtasks

- [x] Task 1: Update `docs/setup.md` — replace stub docker-compose references with real CLI commands and add Operations section (AC: #1, #2, #5)
  - [x] Replace `## Check Platform Status` block with `cos status` + full expected output table
  - [x] Replace `## Restart the Platform` block with `cos restart` (single host command) + expected output + timing note
  - [x] Replace `## View Logs` block with `cos logs` family + examples
  - [x] Add `## Platform Operations` section with the three-step recovery procedure for Postgres not running

- [x] Task 2: Update `README.md` (AC: #3, #5)
  - [x] Change `## Current Capabilities (Epic 4)` heading to `## Current Capabilities (Epic 5)`
  - [x] Add `cos status`, `cos restart`, `cos logs` bullets to the capabilities list
  - [x] Update closing note to reference `docs/setup.md` for operations guidance
  - [x] Fix `cli.py` comment in project structure (remove "stub commands")

- [x] Task 3: Add Epic 5 implementation notes to `architecture.md` (AC: #4, #5)
  - [x] Add `## Epic 5 Implementation Notes` section after the Epic 4 notes (after line 797)

## Dev Notes

### What This Story Is

Story 5.6 is the Epic 5 documentation and housekeeping story. **There are no code changes.** All changes are limited to:

| File | Action |
|------|--------|
| `docs/setup.md` | UPDATE — replace `docker compose ps` / `docker compose down/up` / `docker compose logs` with real `cos` CLI commands; add Platform Operations section |
| `README.md` | UPDATE — Epic 5 capabilities heading, add three new CLI bullets, fix cli.py comment |
| `_bmad-output/planning-artifacts/architecture.md` | ADD — Epic 5 implementation notes section |

Do NOT modify: any file in `src/`, `tests/`, `role_packs/`, `test-docs/`, `docker-compose.yml`, `config.yaml.example`, or `docs/manual-testing.md`.

`docs/manual-testing.md` was fully updated in Story 5.5. Do not touch it.

---

### Critical: Where Each Command Runs

This distinction is load-bearing — it must be accurate in every doc change:

| Command | Must run | Why |
|---------|----------|-----|
| `cos status` | **INSIDE** the container via `docker compose exec cos uv run cos status` | Connects to Postgres at `host: postgres` — only resolves on the Docker network |
| `cos restart` | **HOST** via `uv run cos restart` | Calls `docker compose restart` internally — Docker CLI is not in the cos container |
| `cos logs` | **HOST** via `uv run cos logs` | Calls `docker compose logs` internally — Docker CLI is not in the cos container |

---

### Task 1 — Exact `docs/setup.md` changes

#### 1a. Replace `## Check Platform Status` (lines 84–91)

Find and replace the entire block:

```
## Check Platform Status

```bash
docker compose ps
```

Shows all three services and their health state. All should show `healthy` or `running`.
```

Replace with:

```markdown
## Check Platform Status

Run from the `cos/` directory inside the container:

```bash
docker compose exec cos uv run cos status
```

Expected output when the platform is fully healthy:

```
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (N documents indexed)
```

Each row shows a component name, a `✓` (healthy) or `✗` (problem) icon, a plain-language message, and — if something is wrong — an exact recovery instruction. No technical jargon appears in the output.

**Exit code:** 0 when all components are healthy; 1 if any component is unhealthy.
```

#### 1b. Replace `## Restart the Platform` (lines 135–150)

Find and replace the entire block:

```
## Restart the Platform

Three-step restart procedure:

```bash
# Step 1 — stop all services
docker compose down

# Step 2 — start again
docker compose up -d

# Step 3 — verify all services are healthy
docker compose ps
```

No manual intervention is needed between steps.
```

Replace with:

```markdown
## Restart the Platform

Run from the `cos/` directory on the **host** (not inside the container):

```bash
uv run cos restart
```

The command restarts all services and polls until every container is healthy. Expected output:

```
Restarting platform...
Platform restarted. All components healthy.
```

**Timing note:** `cos restart` calls `docker compose restart`, then polls for up to 30 seconds. Total wall time to the confirmation message is typically 35–45 seconds on a standard machine.

**If a container stays stuck**, the output names it and suggests the next step:

```
Tika did not become healthy. Run: cos logs tika
```

Exit code 0 on success, 1 on failure.
```

#### 1c. Replace `## View Logs` (lines 273–283)

Find and replace the entire block:

```
## View Logs

```bash
docker compose logs cos
```

Streams structured JSON logs from the cos service. To follow logs in real time:

```bash
docker compose logs -f cos
```
```

Replace with:

```markdown
## View Logs

Run from the `cos/` directory on the **host** (not inside the container):

```bash
uv run cos logs                # last 100 lines from all containers
uv run cos logs cos            # filter to the cos service only
uv run cos logs --since 10m    # last 10 minutes from all containers
uv run cos logs cos --since 5m # cos service, last 5 minutes
```

Valid component names: `postgres`, `tika`, `cos`.

Log output is a mix of Docker timestamps and structured JSON lines from the cos service. No API keys or credential values appear in any log line.

If no containers are running, the command prints a plain-language message rather than a Docker error:

```
No containers running. Start the platform first: docker compose up -d
```
```

#### 1d. Add `## Platform Operations` section

Insert a new section immediately after `## View Logs` (at the end of the document, after the View Logs block). The full section content:

```markdown
## Platform Operations

### Recovery: Postgres not running

The most common failure is Postgres stopping unexpectedly. The three-step recovery procedure:

**Step 1 — check what is wrong:**

```bash
docker compose exec cos uv run cos status
```

When Postgres is down, both the `Postgres` and `Database` rows fail with a recovery hint:

```
CoS Platform Status
-------------------
Postgres        ✗ container not running — Run: cos restart
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✗ could not connect — Run: cos restart
```

**Step 2 — restart the platform:**

```bash
uv run cos restart
```

Wait for the confirmation: `Platform restarted. All components healthy.`

**Step 3 — confirm recovery:**

```bash
docker compose exec cos uv run cos status
```

All five rows should show `✓` icons. The platform is ready to accept queries again.

---

### Sending logs for support

If you need to share diagnostic information, capture the last 10 minutes of logs from all containers:

```bash
uv run cos logs --since 10m
```

Paste the output into your support message. The output contains no API keys or credential values — it is safe to share.
```

---

### Task 2 — Exact `README.md` changes

**Change 1 — heading:**

Find:
```
## Current Capabilities (Epic 4)
```
Replace with:
```
## Current Capabilities (Epic 5)
```

**Change 2 — add CLI command bullets after the existing capabilities list:**

Find the existing `get_status` bullet:
```
- **`get_status`** — returns a JSON envelope with health of all three components (cos, postgres, tika) and a `ready` flag
```

Replace with:
```
- **`get_status`** — returns a JSON envelope with health of all three components (cos, postgres, tika) and a `ready` flag
- **`cos status`** — plain-language health table for all five components; identifies exactly which component failed and states the recovery action; exit code 1 when any component is unhealthy; run inside the container: `docker compose exec cos uv run cos status`
- **`cos restart`** — single command that restarts all services and polls until every container is healthy; prints confirmation or names the stuck component; run from the host: `uv run cos restart`
- **`cos logs`** — single command log export; supports optional component filter and `--since <duration>` for time filtering; run from the host: `uv run cos logs`
```

**Change 3 — closing note:**

Find:
```
Knowledge retrieval and Q&A with citations are working. Role identity is configuration-only — author a YAML file and point `config.yaml` at it; no code changes are required. See [docs/role-packs.md](docs/role-packs.md) for the authoring guide. Connected sources (email, calendar) are planned for Epic 6.
```

Replace with:
```
Knowledge retrieval and Q&A with citations are working. Role identity is configuration-only — author a YAML file and point `config.yaml` at it; no code changes are required. See [docs/role-packs.md](docs/role-packs.md) for the authoring guide. The platform can be monitored, restarted, and diagnosed using plain-language CLI commands — see [docs/setup.md](docs/setup.md) for the operations reference. Connected sources (email, calendar) are planned for Epic 6.
```

**Change 4 — cli.py comment in project structure:**

Find:
```
│       ├── cli.py            # `cos` CLI entry point (stub commands)
```

Replace with:
```
│       ├── cli.py            # `cos` CLI entry point (status, restart, logs, ingest, docs)
```

**Change 5 — Get Started section:**

Find:
```
See [docs/setup.md](docs/setup.md) for step-by-step provisioning instructions:
prerequisites, configuration, starting the platform, connecting Claude, querying the knowledge base, and the restart procedure.
```

Replace with:
```
See [docs/setup.md](docs/setup.md) for step-by-step provisioning instructions:
prerequisites, configuration, starting the platform, connecting Claude, querying the knowledge base, and the platform operations reference (status, restart, logs, and the Postgres recovery procedure).
```

---

### Task 3 — Epic 5 implementation notes for `architecture.md`

Add the following block **after** the existing Epic 4 Implementation Notes section (after the last line of the Epic 4 table, currently at line 797):

```markdown
## Epic 5 Implementation Notes

The following deviations from the architecture spec occurred during Epic 5. Future agents should treat these as the actual state of the codebase.

| # | Deviation | Detail |
|---|-----------|--------|
| 1 | **Epic 1 Deviation 4 resolved: CLI commands are fully implemented** | Epic 1 Deviation 4 noted that `cos status`, `cos restart`, `cos logs`, and `cos ingest` all raised `NotImplementedError`. After Epic 5, `cos status`, `cos restart`, and `cos logs` are fully operational. `cos ingest` and `cos docs` were implemented in Epic 2. No CLI commands are stubs at the end of Epic 5. |
| 2 | **`cos status` must run inside the Docker container; `cos restart` and `cos logs` must run on the host** | `cos status` connects to Postgres at `host: postgres`, which only resolves on the Docker network. It is invoked via `docker compose exec cos uv run cos status`. `cos restart` and `cos logs` call `docker compose restart` and `docker compose logs` internally — `docker` CLI is not installed in the `cos` container image, so these commands must be run on the host machine where Docker is available. |
| 3 | **`HealthService` checks five components, not three** | The architecture spec described health checks for three services (Postgres, Tika, MCP server). The Epic 5 implementation checks five components: Postgres container, Tika container, MCP server (connection pool), Role pack (YAML file readable and parseable), and Database (Postgres connection + schema query). Each is a `ComponentStatus(name, healthy, message, recovery_hint)`. |
| 4 | **`cos restart` polling window excludes restart duration** | The 30-second timeout (`_RESTART_TIMEOUT = 30`, `_POLL_INTERVAL = 2` in `src/cos/cli.py:17`) is the polling window that starts *after* `docker compose restart` finishes. Total wall time from running `uv run cos restart` to seeing the confirmation message is typically 35–45 seconds on a standard machine. The architecture spec's "within 30 seconds" refers to the polling window, not total elapsed time. |
| 5 | **`cos logs` defaults to last 100 lines; `--since` overrides tail** | When `--since` is not provided, `cos logs` appends `--tail 100` to `docker compose logs`. When `--since` is provided, the tail flag is omitted entirely. Valid component filter values are the Docker service names: `postgres`, `tika`, `cos`. An invalid component name exits with code 1 and lists valid options before running any Docker command. |
```

---

### Consistency Checklist (run before marking done)

Cross-check these values are identical across all affected files:

| Value | Correct form |
|-------|-------------|
| `cos status` invocation | `docker compose exec cos uv run cos status` |
| `cos restart` invocation | `uv run cos restart` |
| `cos logs` invocation | `uv run cos logs [component] [--since <duration>]` |
| `cos restart` success output | `Platform restarted. All components healthy.` |
| `cos restart` failure output | `<Component> did not become healthy. Run: cos logs <component>` |
| Polling timeout | 30 seconds (polling window, not total wall time) |
| Postgres failure — status rows affected | Postgres **and** Database (both fail when Postgres is down) |
| Valid log filter components | `postgres`, `tika`, `cos` |

### Previous Story Context (Story 5.5 completion)

Story 5.5 (operator validation) is done. The following is confirmed working and does not need to be validated again:

- `cos status` output format (5-component table with `✓`/`✗` icons and recovery hints)
- `cos restart` recovers the platform within the 30-second polling window
- `cos logs cos --since 5m` shows structured JSON lines with no credential values
- After a Postgres stop + `cos restart`, a `retrieve` query returns a cited answer
- `docs/manual-testing.md` is fully updated through Epic 5 — do not touch it

### Key File References

- Status render: `src/cos/cli.py:293` — `_render_status_report()`
- Status run: `src/cos/cli.py:25` — `status()`
- Restart command: `src/cos/cli.py:42` — `restart()`
- Restart wait: `src/cos/cli.py:322` — `_wait_for_healthy(timeout=30, poll_interval=2)`
- Logs command: `src/cos/cli.py:61` — `logs(component, since)`
- Health checks: `src/cos/services/health.py:27` — `HealthService.check_all()`
- Component model: `src/cos/services/health.py:12` — `ComponentStatus(name, healthy, message, recovery_hint)`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Implementation Plan

- Update `docs/setup.md` with the Epic 5 CLI-first operations guidance and Postgres recovery flow.
- Update `README.md` so the root project overview reflects Epic 5 capabilities and points operators to the setup guide.
- Append Epic 5 implementation notes to `_bmad-output/planning-artifacts/architecture.md`.
- Run consistency checks on the command strings and execute the regression suite, resolving any environment issue needed to get a trustworthy result.

### Debug Log References

- `git diff -- docs/setup.md README.md _bmad-output/planning-artifacts/architecture.md`
- `uv run pytest -q` (first run failed because local Postgres on `localhost:5432` was not running)
- `docker compose up -d postgres`
- `uv run pytest -q` (rerun passed: 163 passed, 2 skipped)
- `docker compose down`

### Completion Notes List

- Updated `docs/setup.md` to replace Docker-only operational steps with `cos status`, `cos restart`, and `cos logs`, including expected output and a non-technical Postgres recovery procedure.
- Updated `README.md` to describe Epic 5 capabilities accurately and direct operators to `docs/setup.md` for the operations reference.
- Added `## Epic 5 Implementation Notes` to `_bmad-output/planning-artifacts/architecture.md` to capture the real CLI/runtime behavior built in Epic 5.
- Cross-checked command syntax and recovery wording across all touched docs for consistency.
- Ran the full pytest suite successfully after starting the local Postgres service required by the test fixtures.

### File List

- docs/setup.md
- README.md
- _bmad-output/planning-artifacts/architecture.md
- _bmad-output/implementation-artifacts/5-6-documentation-and-housekeeping.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Review Findings

- [x] [Review][Decision] `get_status` describes "three components" but Epic 5 upgraded HealthService to five — verified: `get_status` uses `HealthService.check_all()` (5 components) + prepends "cos" = 6 total; README updated to "six components (cos, postgres, tika, MCP server, role pack, database)" [README.md]
- [x] [Review][Decision] Recovery procedure Step 1 assumes the `cos` container is running — added fallback note: "If `docker compose exec` fails with 'container not running', the `cos` container has also stopped — skip directly to Step 2" [docs/setup.md: Platform Operations]
- [x] [Review][Decision] Operations guidance distributed across four sections — consolidated: `## Check Platform Status`, `## Restart the Platform`, and `## View Logs` moved to subsections under `## Platform Operations` [docs/setup.md]
- [x] [Review][Patch] "inside the container" wording was wrong — fixed to "on the **host** (not inside the container)" in consolidated Platform Operations section [docs/setup.md: Platform Operations → Check Platform Status]
- [x] [Review][Patch] `cos logs` exit code undocumented — added "Exit code 0 when containers are running; 1 if no containers are running" [docs/setup.md: Platform Operations → View Logs]
- [x] [Review][Patch] `--since` duration format unspecified — added note that values follow Docker's duration format (e.g. `10m`, `1h`, `30s`) and are passed through verbatim [docs/setup.md: Platform Operations → View Logs]
- [x] [Review][Patch] `N` placeholder ambiguous — changed to realistic example `42 documents indexed` [docs/setup.md: Platform Operations → Check Platform Status]
- [x] [Review][Defer] 30-second `subprocess.run` timeout on `docker compose restart` is undisclosed — if `docker compose restart` itself takes >30s the command fails at the restart step, not the polling step; the "35–45 seconds total wall time" estimate does not apply in that case [src/cos/cli.py:311] — deferred, pre-existing
- [x] [Review][Defer] `_check_mcp_server` always returns `healthy=True` — MCP server component can never show ✗ or trigger exit code 1; the documented claim that `cos status` "identifies exactly which component failed" is not true for the MCP server [src/cos/services/health.py:73] — deferred, pre-existing
- [x] [Review][Defer] `_check_postgres` and `_check_database` can hang for OS-level TCP timeout (~30s each) — if the Postgres container is paused rather than stopped cleanly, `cos status` may block for ~60s before returning results [src/cos/services/health.py:38] — deferred, pre-existing
- [x] [Review][Defer] "MCP server" display name vs "cos" Docker service name mismatch in stuck-component message — if the `cos` container is stuck, the user sees "MCP server did not become healthy. Run: cos logs cos" (display name and service name differ in the same message) [src/cos/cli.py:49] — deferred, pre-existing

### Change Log

- 2026-05-01: Updated Epic 5 operations documentation in `docs/setup.md`, `README.md`, and `architecture.md`; marked story complete and ready for review after validation.
