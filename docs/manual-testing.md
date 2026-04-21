# Manual Testing Guide

Structured UAT tests for the CoS platform. Updated at the end of each story or epic that introduces testable behaviour. Tests marked **[LIVE]** can be run now; **[STUB]** means the feature exists but raises `NotImplementedError` — only the scaffolding is testable.

---

## How to use this guide

Run the relevant section after each story completes. Each test has:
- **Steps** — exact commands to run
- **Expected** — what a pass looks like
- **Fail signal** — what to look for if something is wrong

Prerequisites for all tests: Docker running (Rancher Desktop or Docker Desktop), `uv` installed, working directory is `cos/`.

---

## Epic 1 — Runnable Platform Foundation

### Story 1.1: Project Scaffold & Containerised Services

#### T1.1.1 — Clean first-time startup **[LIVE]**

```bash
docker compose up -d
```

Wait up to 60 seconds, then:

```bash
docker compose ps
```

**Expected:** All three services show `healthy` in the Status column:
```
NAME       STATUS
cos-cos-1       Up X seconds (healthy)
cos-postgres-1  Up X seconds (healthy)
cos-tika-1      Up X seconds (healthy)
```

**Fail signal:** Any service showing `unhealthy`, `starting`, or `Exit`.

---

#### T1.1.2 — Port binding verification **[LIVE]**

```bash
docker compose ps --format json | python3 -c "
import sys, json
for line in sys.stdin:
    s = json.loads(line)
    ports = s.get('Publishers', [])
    for p in ports:
        host = p.get('URL', '')
        print(s['Name'], host, p.get('PublishedPort'), '->', p.get('TargetPort'))
"
```

**Expected:**
- `cos-postgres-1` binds on `127.0.0.1:5432`
- `cos-tika-1` binds on `127.0.0.1:9998`
- `cos-cos-1` has **no published ports** (stdio only)

**Fail signal:** Any binding on `0.0.0.0` or the `cos` service showing a published port.

---

#### T1.1.3 — Clean restart **[LIVE]**

```bash
docker compose down
docker compose up -d
docker compose ps
```

**Expected:** All three services return to `healthy` within 60 seconds with no manual steps between the two commands.

**Fail signal:** Any service failing to restart, or prompt asking for manual intervention.

---

#### T1.1.4 — Package imports cleanly **[LIVE]**

```bash
uv run python -c "
import cos
import cos.services.ingestion
import cos.services.retrieval
import cos.services.health
import cos.output.router
import cos.llm.adapter
import cos.mcp_server.server
print('all imports ok')
"
```

**Expected:** `all imports ok` with no errors or warnings.

**Fail signal:** `ModuleNotFoundError`, `ImportError`, or any traceback.

---

#### T1.1.5 — OutputRouter fail-closed behaviour **[LIVE]**

```bash
uv run python -c "
import logging, json
logging.basicConfig(level=logging.ERROR)
from cos.output.router import OutputRouter

r = OutputRouter(configured_channels=['local'])

# Valid channel — should print
r.send('local', 'hello from manual test')

# Invalid channel — should not print, should log error
r.send('bogus_channel', 'this should not appear')

# Configured but no handler — should not print, should log error
r2 = OutputRouter(configured_channels=['email'])
r2.send('email', 'this should not appear either')

print('no exceptions raised — pass')
"
```

**Expected:**
- `hello from manual test` appears on stdout
- `this should not appear` does NOT appear on stdout
- An ERROR log line containing `unknown output channel` appears
- An ERROR log line containing `no handler registered` appears
- `no exceptions raised — pass` appears at the end

**Fail signal:** Any unhandled exception, or suppressed content appearing on stdout.

---

#### T1.1.6 — CLI help text **[STUB — scaffolding only]**

```bash
uv run cos --help
```

**Expected:** Help text listing four commands: `status`, `restart`, `logs`, `ingest`.

```bash
uv run cos status
```

**Expected:** A `NotImplementedError` traceback — this confirms the stub is wired correctly. Not a failure.

---

#### T1.1.7 — MCP server entry point **[STUB — scaffolding only]**

```bash
timeout 3 uv run cos-mcp; echo "exit code: $?"
```

**Expected:** Process starts, runs for 3 seconds (waiting for MCP client on stdin), then exits cleanly on timeout. No import errors before the timeout.

**Fail signal:** An error before the 3-second mark, particularly `ModuleNotFoundError` or `ImportError`.

---

#### T1.1.8 — Automated test suite **[LIVE]**

```bash
uv run pytest tests/ -v
```

**Expected:** All tests pass. Current baseline: 15 tests (5 in `tests/output/test_router.py`, remainder are scaffold stubs).

**Fail signal:** Any test failure or collection error.

---

### Story 1.2: Configuration Loader *(not yet implemented)*

Tests will be added here after Story 1.2 is complete.

---

### Story 1.3: Database Schema & Migration Runner *(not yet implemented)*

Tests will be added here after Story 1.3 is complete.

---

## Epic 2 — Document Knowledge Base *(not yet started)*

Tests will be added here after Epic 2 stories complete.

---

## Running all live tests

Quick smoke-test sequence for the current state of the platform:

```bash
# 1. Start services
docker compose up -d

# 2. Wait for healthy state
sleep 30 && docker compose ps

# 3. Imports
uv run python -c "import cos.output.router; print('imports ok')"

# 4. OutputRouter
uv run python -c "
from cos.output.router import OutputRouter
r = OutputRouter(configured_channels=['local'])
r.send('local', 'smoke test ok')
r.send('invalid', 'should be suppressed')
print('router ok')
"

# 5. Tests
uv run pytest tests/ -v
```

All five steps should complete without errors.
