# Story 1.5: Operator Validation — Platform Boots End-to-End

Status: done

## Story

As Iain (operator and first user),
I want to run a documented smoke test of the assembled platform foundation,
So that I can confirm the complete system is correctly wired up before building the ingestion pipeline.

## Acceptance Criteria

1. **Given** a clean machine with Docker and uv installed and `config.yaml` populated from `config.yaml.example`,
   **When** `docker compose up -d` is run,
   **Then** all three containers (`postgres`, `tika`, `cos`) show as `healthy` in `docker compose ps` within 60 seconds — without any manual intervention.

2. **Given** Claude Desktop or Claude Code is configured with the CoS MCP server,
   **When** the client is opened after `docker compose up -d`,
   **Then** the four tools (`retrieve`, `get_role_context`, `list_documents`, `get_status`) are visible and callable.

3. **Given** `get_status` is called from the MCP client,
   **When** the response is received,
   **Then** it is valid JSON with `status: "ok"`, reports all components as healthy, and contains no error fields.

4. **Given** the platform has been running and `docker compose down` is run,
   **When** `docker compose up -d` is run again,
   **Then** all containers reach healthy state again with no manual database repair, migration commands, or file deletions needed.

5. **Given** `docker compose logs cos` is run during normal operation,
   **When** the output is inspected,
   **Then** every log line is valid JSON — no plain text lines, no unhandled exception tracebacks, no bare print output.

6. **Given** an incorrect or missing value is introduced into `config.yaml`,
   **When** `docker compose up -d` is run,
   **Then** the `cos` container fails to start and `docker compose logs cos` shows a clear, human-readable validation error identifying the bad field.

## Tasks / Subtasks

- [x] Task 1: Add `cos` component to `get_status` response (AC: #3)
  - [x] In `cos/src/cos/mcp_server/tools.py`, update `get_status` to include `{"name": "cos", "healthy": True}` in `components` — add it first in the list so it reads: cos → postgres → tika
  - [x] Update `test_get_status_all_components_present` in `tests/mcp_server/test_tools.py` to assert three components and that the `cos` component is always `healthy: True`
  - [x] Update `test_get_status_returns_ok_envelope` to account for three components in `ready` calculation
  - [x] Verify 42+ tests still pass: `uv run pytest tests/ -v`

- [x] Task 2: Add Story 1.3 manual tests to `docs/manual-testing.md` (AC: all)
  - [x] Replace the "Tests will be added here after Story 1.3 is complete" placeholder with T1.3.1 through T1.3.4 (see Dev Notes)
  - [x] Cover: tables exist, correct columns, idempotent restart, migration log output

- [x] Task 3: Add Story 1.4 manual tests to `docs/manual-testing.md` (AC: all)
  - [x] Add Story 1.4 section after Story 1.3 with T1.4.1 through T1.4.4 (see Dev Notes)
  - [x] Cover: MCP server starts cleanly, 4 tools visible, `get_status` returns ok envelope, stub tools return error envelopes, all logs are structured JSON

- [x] Task 4: Add Story 1.5 end-to-end tests to `docs/manual-testing.md` (AC: #1–#6)
  - [x] Add Story 1.5 section with T1.5.1 through T1.5.6 (see Dev Notes)
  - [x] T1.5.1 — docker compose up → 3 containers healthy
  - [x] T1.5.2 — Claude Code MCP config + tool discovery
  - [x] T1.5.3 — `get_status` returns correct envelope with 3 healthy components
  - [x] T1.5.4 — restart round-trip (down → up) with no manual repair
  - [x] T1.5.5 — JSON log validation with inline Python command
  - [x] T1.5.6 — bad config → cos fails with readable error

- [x] Task 5: Update "Running all live tests" section in `docs/manual-testing.md` (AC: all)
  - [x] Replace the current 6-step script with an updated 8-step script covering Stories 1.1–1.4 and the full end-to-end check
  - [x] Include the JSON log validation command
  - [x] Note the MCP client test as a manual step requiring Claude Desktop/Code

### Review Findings

- [x] [Review][Decision] Branch diff scope — RESOLVED: `main` was stale locally (Story 1.4 merged to origin/main on 2026-04-22 but not pulled). `git diff origin/main...story/1-5` shows exactly the 3 permitted files. Pull main before opening the PR.
- [x] [Review][Defer] Startup continues past unhealthy Postgres — Story 1.4 bug (server.py, not in Story 1.5 scope): `run_migrations` called unconditionally after `pg_ok` check; if Postgres is down it raises an unhandled exception [src/cos/mcp_server/server.py:54-62] — deferred, Story 1.4 code
- [x] [Review][Defer] Duplicate health check logic — Story 1.4 bug (not in Story 1.5 scope): `_check_postgres` and `_check_tika` duplicated in both `server.py` and `health.py`; can diverge silently [src/cos/mcp_server/server.py:34-49] — deferred, Story 1.4 code
- [x] [Review][Defer] Tika health check accepts 4xx as healthy — Story 1.4 bug (not in Story 1.5 scope): `status_code < 500` returns True for 404/401/403 [src/cos/mcp_server/server.py:47, src/cos/services/health.py:29] — deferred, Story 1.4 code
- [x] [Review][Defer] `_config` set before `_startup_sequence` completes — latent race if FastMCP startup model changes to concurrent; harmless with current sequential `asyncio.run()` + `mcp.run()` [src/cos/mcp_server/server.py:65-72] — deferred, pre-existing
- [x] [Review][Defer] New DB and HTTP connections per health check call — no pooling; acceptable at Phase 1 poll rates [src/cos/mcp_server/server.py:34-49] — deferred, pre-existing
- [x] [Review][Defer] `get_status` always returns `status:"ok"` even when `ready:false` — by design; `ready` field captures degraded state [src/cos/mcp_server/tools.py:14-16] — deferred, pre-existing
- [x] [Review][Defer] `_emit` falls back silently to INFO on unknown level strings — `getattr(logging, level.lower(), logging.info)` swallows "WARN" vs "WARNING" mismatch [src/cos/mcp_server/server.py:30] — deferred, pre-existing
- [x] [Review][Defer] `get_config()` None-guard only enforced in `get_status` — future tools that call `get_config()` without a check will raise AttributeError [src/cos/mcp_server/server.py] — deferred, pre-existing
- [x] [Review][Defer] Duplicate startup connection — `_check_postgres` and `run_migrations` each open a separate DB connection; minor inefficiency [src/cos/mcp_server/server.py:34-62] — deferred, pre-existing

## Dev Notes

### What This Story Is

Story 1.5 is an operator validation story. The dev agent's primary deliverable is documentation: updating `docs/manual-testing.md` with manual test procedures for Stories 1.3, 1.4, and the end-to-end smoke test. One code change is also required: adding `cos` as a health component to satisfy AC#3 ("all components healthy").

The operator (Iain) then runs through the tests manually and marks the story done.

### Code Change: Adding `cos` Component to `get_status`

AC#3 says "reports all components as healthy." The current `get_status` implementation (Story 1.4) returns only `postgres` and `tika` from `HealthService.check_all()`. To satisfy "all components," add `cos` itself as a component — it is implicitly healthy if the tool is executing:

```python
# In tools.py — get_status, after health.check_all():
components = [{"name": "cos", "healthy": True}] + await health.check_all()
ready = bool(components) and all(c["healthy"] for c in components)
```

The `cos` component is always `healthy: True` because if get_status is executing, the cos service is running. No additional health check logic needed.

**Test update required:** `test_get_status_all_components_present` currently checks 2 components. Update to assert:
- `len(result["data"]["components"]) == 3`
- `result["data"]["components"][0] == {"name": "cos", "healthy": True}`
- `result["data"]["components"][1]["name"] == "postgres"`
- `result["data"]["components"][2]["name"] == "tika"`

### Story 1.3 Manual Tests (for `docs/manual-testing.md`)

Add after line "### Story 1.2: Configuration Loader" section (before the "### Story 1.3:" placeholder):

```
### Story 1.3: Database Schema & Migration Runner

**Prerequisite:** `docker compose up -d` has been run and all services are healthy.

#### T1.3.1 — Schema tables exist [LIVE]

```bash
docker compose exec postgres psql -U postgres -d cos -c "\dt"
```

**Expected:** Four tables listed: `chunks`, `document_versions`, `documents`, `embeddings`.

**Fail signal:** Any table missing, or `psql` error.

---

#### T1.3.2 — Key columns present [LIVE]

```bash
docker compose exec postgres psql -U postgres -d cos -c "\d documents"
```

**Expected:** Columns: `id` (uuid), `source_path` (text), `file_hash` (text), `ingested_at` (timestamp with time zone), `current_version` (integer), `status` (text).

**Fail signal:** Missing column, wrong type.

---

#### T1.3.3 — Embeddings table has model and provider columns [LIVE]

```bash
docker compose exec postgres psql -U postgres -d cos -c "\d embeddings"
```

**Expected:** Columns include `model` (text), `provider` (text), and `vector` (vector).

**Fail signal:** Missing `model` or `provider` column.

---

#### T1.3.4 — Migration is idempotent (restart does not error) [LIVE]

```bash
docker compose restart cos
sleep 15
docker compose ps
```

**Expected:** `cos` container returns to `healthy`. No migration errors in logs.

```bash
docker compose logs cos --tail=20
```

**Expected:** Log lines include `"message": "migration applied"` entries and `"message": "MCP server: listening"` — no error tracebacks.

**Fail signal:** `cos` container shows `unhealthy` or `Exit`, or any traceback in logs.
```

### Story 1.4 Manual Tests (for `docs/manual-testing.md`)

Add a new `### Story 1.4: MCP Server Foundation` section after the Story 1.3 section:

```
### Story 1.4: MCP Server Foundation

**Prerequisite:** `docker compose up -d` has been run and all three services are healthy.

#### T1.4.1 — MCP server starts and logs structured JSON [LIVE]

```bash
docker compose logs cos --tail=30
```

**Expected:** All log lines are JSON objects. The final lines include (in order):
- `"message": "Postgres: healthy"`
- `"message": "Tika: healthy"`
- `"message": "config loaded"`
- `"message": "migration applied"` (one per SQL file with executable statements)
- `"message": "migrations applied"`
- `"message": "role pack: stub loaded"`
- `"message": "MCP server: listening"`

**Fail signal:** Any plain-text log line, any `print()` output, or missing log entries.

---

#### T1.4.2 — `get_status` returns correct envelope [LIVE]

Call `get_status` from a connected MCP client (see T1.5.2 for setup). Or run via:

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
from cos.mcp_server.tools import get_status
import cos.mcp_server.server as srv
from unittest.mock import MagicMock
from cos.config import CosConfig
srv._config = CosConfig.load('/app/config.yaml')
result = asyncio.run(get_status())
data = json.loads(result)
print(json.dumps(data, indent=2))
assert data['status'] == 'ok', f'Expected ok, got: {data}'
assert data['data']['ready'] in (True, False)
assert 'citations' in data
print('get_status envelope: ok')
"
```

**Expected:** JSON output with `status: "ok"`, `data.components` listing components, `data.ready` true or false depending on service health, `citations: []`.

**Fail signal:** `status` is not `"ok"`, or missing `data`/`citations` fields.

---

#### T1.4.3 — Stub tools return error envelopes (not exceptions) [LIVE]

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
from cos.mcp_server.tools import retrieve, get_role_context, list_documents

for coro, kwargs in [
    (retrieve, {'query': 'test'}),
    (get_role_context, {}),
    (list_documents, {}),
]:
    result = json.loads(asyncio.run(coro(**kwargs)))
    assert result['status'] == 'error', f'Expected error envelope: {result}'
    assert 'Not yet implemented' in result['error'], f'Wrong error: {result}'
    print(coro.__name__, 'returns error envelope: ok')
"
```

**Expected:** Each stub prints `<tool_name> returns error envelope: ok`. No exceptions raised.

**Fail signal:** Any exception, or `status` not equal to `"error"`.

---

#### T1.4.4 — No bare print calls in codebase [LIVE]

```bash
grep -r "^print(" cos/src/ || echo "no bare prints found"
```

**Expected:** `no bare prints found`.

**Fail signal:** Any file path printed (indicating a bare `print(` at the start of a line).
```

### Story 1.5 End-to-End Tests (for `docs/manual-testing.md`)

Add a new `### Story 1.5: Operator Validation — Platform Boots End-to-End` section with 6 tests:

**T1.5.1 — Three containers healthy within 60 seconds [LIVE]**

Same as T1.1.1 but also checking `tika` is present. The test script:
```bash
docker compose down
docker compose up -d
sleep 30
docker compose ps
```
Expected: `cos`, `postgres`, `tika` all showing `(healthy)`.

**T1.5.2 — Claude Code MCP: 4 tools visible [LIVE — requires Claude Code]**

Configure Claude Code to connect to the MCP server:
```bash
# From the cos/ directory:
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Then in a new Claude Code session, run:
```
/mcp
```
or ask "what tools do you have?" — confirm `get_status`, `retrieve`, `get_role_context`, `list_documents` are listed.

**T1.5.3 — get_status returns ok with 3 healthy components [LIVE — requires connected MCP client]**

From Claude Code with MCP connected:
```
Call get_status and show me the raw JSON response.
```
Expected response structure:
```json
{
  "status": "ok",
  "data": {
    "components": [
      {"name": "cos", "healthy": true},
      {"name": "postgres", "healthy": true},
      {"name": "tika", "healthy": true}
    ],
    "ready": true
  },
  "citations": []
}
```
No `error` field present.

**T1.5.4 — Restart round-trip: no manual repair needed [LIVE]**

```bash
docker compose down
docker compose up -d
sleep 30
docker compose ps
```
Expected: all three containers healthy again. No `docker exec`, no `psql` commands, no file deletions required.

**T1.5.5 — All cos log lines are valid JSON [LIVE]**

```bash
docker compose logs cos 2>&1 | uv run python -c "
import sys, json
bad = []
for i, line in enumerate(sys.stdin, 1):
    line = line.strip()
    if not line:
        continue
    try:
        json.loads(line)
    except json.JSONDecodeError:
        bad.append(f'  line {i}: {line[:120]}')
if bad:
    print(f'FAIL: {len(bad)} non-JSON lines:')
    print('\n'.join(bad))
    sys.exit(1)
else:
    print('ok: all log lines are valid JSON')
"
```
Expected: `ok: all log lines are valid JSON`.

**T1.5.6 — Bad config → clear validation error [LIVE]**

```bash
# Introduce a bad value (invalid port)
sed 's/port: 5432/port: 99999/' config.yaml > /tmp/config_bad.yaml

# Temporarily replace config.yaml
cp config.yaml /tmp/config_backup.yaml
cp /tmp/config_bad.yaml config.yaml

docker compose down
docker compose up -d
sleep 10
docker compose ps
docker compose logs cos
```

Expected:
- `cos` container shows `unhealthy` or `Exit` (not `healthy`)
- `docker compose logs cos` shows a human-readable error mentioning `port` or `99999`
- No raw Python traceback (no `Traceback (most recent call last):`)

Restore config:
```bash
cp /tmp/config_backup.yaml config.yaml
docker compose down && docker compose up -d
```

### MCP Connection via `docker compose exec` — How It Works

The `cos` container runs `uv run cos-mcp` as its entrypoint and stays running. To connect an MCP client, Claude Code (or Claude Desktop) needs to start a process that communicates over stdio. The recommended command:

```
docker compose exec -i cos uv run cos-mcp
```

This runs a second `cos-mcp` instance inside the already-running container. Both instances share the same Postgres, config, and service layer — this is safe and expected. The `-i` flag keeps stdin open for the stdio MCP protocol.

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "cos": {
      "command": "docker",
      "args": ["compose", "exec", "-i", "cos", "uv", "run", "cos-mcp"],
      "cwd": "/absolute/path/to/cos"
    }
  }
}
```

### Updated "Running all live tests" Section

Replace the existing quick smoke-test section with an 8-step script:

```bash
# Prerequisites: Docker running, cos/ is the working directory, config.yaml exists

# 1. Start services
docker compose up -d && sleep 30

# 2. Verify healthy state
docker compose ps

# 3. Verify imports
uv run python -c "import cos.output.router; import cos.config; import cos.mcp_server.server; print('imports ok')"

# 4. Verify config loads
uv run python -c "from cos.config import CosConfig; c = CosConfig.load('config.yaml'); print('config ok — role pack:', c.role_pack.path)"

# 5. Verify DB schema
docker compose exec postgres psql -U postgres -d cos -c "\dt"

# 6. Verify all log lines are JSON
docker compose logs cos 2>&1 | uv run python -c "
import sys, json
bad = [l for i,l in enumerate(sys.stdin,1) if l.strip() and not json.loads(l.strip()) and True]
" 2>/dev/null || docker compose logs cos 2>&1 | uv run python -c "
import sys, json
bad = []
for l in sys.stdin:
    l = l.strip()
    if not l: continue
    try: json.loads(l)
    except: bad.append(l[:80])
print('ok' if not bad else f'FAIL: {len(bad)} non-JSON lines')"

# 7. Run automated test suite
uv run pytest tests/ -v

# 8. Verify get_status (no MCP client needed — direct call)
docker compose exec -i cos uv run python -c "
import asyncio, json, cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import get_status
srv._config = CosConfig.load('/app/config.yaml')
result = json.loads(asyncio.run(get_status()))
assert result['status'] == 'ok', result
print('get_status ok — components:', [c['name'] for c in result['data']['components']])
"
```

### Architecture Constraints

- All code changes are in `cos/src/cos/mcp_server/tools.py` and `cos/tests/mcp_server/test_tools.py` only
- Do NOT touch `HealthService` in `services/health.py` — the `cos` component is added in `tools.py`, not in the service layer
- The `cos` component's `healthy: True` is not a "check" — it's a fact about the executing context
- Module boundary rule: tools call `cos.services.*` only — adding a static component in `tools.py` does not violate this

### Files to Create or Modify

| File | Action | Notes |
|---|---|---|
| `cos/src/cos/mcp_server/tools.py` | Modify | Prepend `{"name": "cos", "healthy": True}` to components list in `get_status` |
| `cos/tests/mcp_server/test_tools.py` | Modify | Update component assertions to expect 3 components; add cos component check |
| `cos/docs/manual-testing.md` | Modify | Add Story 1.3, 1.4, 1.5 sections; update "Running all live tests" section |

Do NOT modify: `cos/src/cos/services/health.py`, `cos/src/cos/mcp_server/server.py`, any store or config files.

### References

- Story 1.4 `get_status` implementation: [Source: 1-4-mcp-server-foundation.md#tools.py — get_status Implementation]
- MCP tool response envelope: [Source: architecture.md#Format Patterns, "MCP Tool Response Envelope"]
- HealthService.check_all() returns: [Source: 1-4-mcp-server-foundation.md#Completion Notes List]
- docker-compose healthchecks: [Source: cos/docker-compose.yml]
- Startup sequence log order: [Source: 1-4-mcp-server-foundation.md#Startup Sequence]
- Manual testing guide structure: [Source: cos/docs/manual-testing.md]
- Story 1.5 acceptance criteria: [Source: epics.md#Story 1.5]
- NFR4 (60s startup): [Source: architecture.md, NFR4]
- NFR9 (30s recovery): [Source: architecture.md, NFR9]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blockers encountered.

### Completion Notes List

- Task 1: Prepended `{"name": "cos", "healthy": True}` to the components list in `get_status` in `tools.py`. Updated `test_get_status_all_components_present` to assert 3 components in the correct order (cos → postgres → tika). All 42 tests pass.
- Tasks 2–5: Added Story 1.3 (T1.3.1–T1.3.4), Story 1.4 (T1.4.1–T1.4.4), and Story 1.5 (T1.5.1–T1.5.6) sections to `docs/manual-testing.md`. Updated "Running all live tests" from a 6-step to an 8-step script covering Stories 1.1–1.5.

### File List

- `cos/src/cos/mcp_server/tools.py` (modified)
- `cos/tests/mcp_server/test_tools.py` (modified)
- `cos/docs/manual-testing.md` (modified)

## Change Log

- 2026-04-22: Story 1.5 implementation — added cos health component to get_status; added manual test procedures for Stories 1.3, 1.4, and 1.5 end-to-end smoke test; updated "Running all live tests" to 8-step script.
