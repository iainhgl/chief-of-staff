# Manual Testing Guide

Structured UAT tests for the CoS platform. Updated at the end of each story or epic that introduces testable behaviour. Tests marked **[LIVE]** can be run now; **[STUB]** means the feature exists but raises `NotImplementedError` — only the scaffolding is testable.

---

## How to use this guide

Run the relevant section after each story completes. Each test has:
- **Steps** — exact commands to run
- **Expected** — what a pass looks like
- **Fail signal** — what to look for if something is wrong

Prerequisites for all tests: Docker running (Rancher Desktop or Docker Desktop), `uv` installed, working directory is `cos/`.

**Always use `uv run python`** (not `python3` or `python`) for any command that imports project code. This ensures the project's virtual environment and dependencies are used. The one exception is T1.1.2, which only uses Python stdlib and pipes from a Docker command.

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

> **Note:** After Story 1.2, `cos-mcp` loads `config.yaml` at startup. Run this test from a directory that contains a valid `config.yaml`, or it will exit immediately with a "config file not found" message (which is itself correct behaviour — see T1.2.3).

```bash
timeout 3 uv run cos-mcp; echo "exit code: $?"
```

**Expected:** Process starts, loads config, logs a structured JSON startup message, then runs for 3 seconds waiting for a MCP client on stdin before timing out. No import errors before the timeout.

**Fail signal:** An error before config is loaded, particularly `ModuleNotFoundError` or `ImportError`.

---

#### T1.1.8 — Automated test suite **[LIVE]**

```bash
uv run pytest tests/ -v
```

**Expected:** All tests pass. Baseline after Story 1.2: 22 tests (16 scaffold stubs + 6 config tests in `tests/test_config.py`).

**Fail signal:** Any test failure or collection error.

---

### Story 1.2: Configuration Loader

**Prerequisite:** A `config.yaml` must exist in the `cos/` directory. If you haven't created one yet:
```bash
cp config.yaml.example config.yaml
# then edit config.yaml and fill in your Anthropic API key
```

#### T1.2.1 — Valid config loads **[LIVE]**

```bash
uv run python -c "
from cos.config import CosConfig
config = CosConfig.load('config.yaml')
print('provider:', config.llm.provider)
print('model:', config.llm.model)
print('role_pack:', config.role_pack.path)
print('channels:', config.channels)
print('database host:', config.database.host)
print('config loaded ok')
"
```

**Expected:** Field values printed from your `config.yaml`, ending with `config loaded ok`. No traceback.

**Fail signal:** Any exception, or unexpected `None` values.

---

#### T1.2.2 — Missing required field exits cleanly **[LIVE]**

```bash
uv run python -c "
import tempfile, pathlib
from cos.config import CosConfig
bad = pathlib.Path(tempfile.mktemp(suffix='.yaml'))
bad.write_text('embedding:\n  provider: anthropic\n  model: voyage-3\n')
try:
    CosConfig.load(bad)
except SystemExit as e:
    print('SystemExit caught — message:')
    print(str(e))
"
```

**Expected:** `SystemExit` is raised with a human-readable message that includes `llm` identifying the missing field. No raw Python traceback.

**Fail signal:** Raw `ValidationError` traceback, or no mention of the missing field in the message.

---

#### T1.2.3 — Missing config file exits cleanly **[LIVE]**

```bash
uv run python -c "
from cos.config import CosConfig
try:
    CosConfig.load('/tmp/does-not-exist.yaml')
except SystemExit as e:
    print('SystemExit caught — message:')
    print(str(e))
"
```

**Expected:** Clean `SystemExit` with a message containing `not found` and a hint to copy `config.yaml.example`.

**Fail signal:** Raw `FileNotFoundError` traceback.

---

#### T1.2.4 — Malformed YAML exits cleanly **[LIVE]**

```bash
uv run python -c "
import tempfile, pathlib
from cos.config import CosConfig
bad = pathlib.Path(tempfile.mktemp(suffix='.yaml'))
bad.write_text('llm:\n  provider: anthropic\n  bad indentation:\nkey: [unclosed')
try:
    CosConfig.load(bad)
except SystemExit as e:
    print('SystemExit caught — message:')
    print(str(e))
"
```

**Expected:** Clean `SystemExit` with a message containing `YAML syntax error`. No raw `yaml.YAMLError` traceback.

**Fail signal:** Unhandled `yaml.YAMLError` traceback.

---

#### T1.2.5 — Secrets do not appear in repr **[LIVE]**

```bash
uv run python -c "
from cos.config import CosConfig
config = CosConfig.load('config.yaml')
db_repr = repr(config.database)
llm_repr = repr(config.llm)
assert \"SecretStr('**********')\" in db_repr, 'FAIL: DB password not masked in repr'
assert \"SecretStr('**********')\" in llm_repr, 'FAIL: LLM API key not masked in repr'
print('database repr:', db_repr)
print('llm repr:', llm_repr)
print('secret masking ok')
"
```

**Expected:** Both repr lines show `SecretStr('**********')` in place of the secret value, ending with `secret masking ok`.

**Fail signal:** `AssertionError`, or the actual key/password value visible in the printed repr.

> **Note:** Do not check for absence of the secret value in the full repr — if your password happens to match another field (e.g. `password: postgres` also appears as the `user` or `host`), the check gives a false failure even when masking is working correctly.

---

#### T1.2.6 — Port validation rejects out-of-range value **[LIVE]**

```bash
uv run python -c "
import tempfile, pathlib
from cos.config import CosConfig
bad = pathlib.Path(tempfile.mktemp(suffix='.yaml'))
bad.write_text(open('config.yaml').read().replace('port: 5432', 'port: 99999'))
try:
    CosConfig.load(bad)
except SystemExit as e:
    print('SystemExit caught — message:')
    print(str(e))
"
```

**Expected:** Clean `SystemExit` with a message identifying the invalid `port` value.

**Fail signal:** Config loads successfully with `port: 99999`, or raw traceback.

---

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

---

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

---

### Story 1.5: Operator Validation — Platform Boots End-to-End

**Prerequisite:** `docker compose up -d` has been run and all three services show `(healthy)` in `docker compose ps`.

#### T1.5.1 — Three containers healthy within 60 seconds [LIVE]

```bash
docker compose down
docker compose up -d
sleep 30
docker compose ps
```

**Expected:** `cos`, `postgres`, `tika` all showing `(healthy)`.

**Fail signal:** Any container showing `unhealthy`, `starting`, or `Exit`.

---

#### T1.5.2 — Claude Code MCP: 4 tools visible [LIVE — requires Claude Code]

Configure Claude Code to connect to the MCP server:

```bash
# From the cos/ directory:
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Then in a new Claude Code session, run `/mcp` or ask "what tools do you have?" — confirm `get_status`, `retrieve`, `get_role_context`, `list_documents` are listed.

---

#### T1.5.3 — `get_status` returns ok with 3 healthy components [LIVE — requires connected MCP client]

From Claude Code with MCP connected:

```
Call get_status and show me the raw JSON response.
```

**Expected:**
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

---

#### T1.5.4 — Restart round-trip: no manual repair needed [LIVE]

```bash
docker compose down
docker compose up -d
sleep 30
docker compose ps
```

**Expected:** All three containers healthy again. No `docker exec`, no `psql` commands, no file deletions required.

**Fail signal:** Any container not reaching `healthy`, or needing manual intervention.

---

#### T1.5.5 — All cos log lines are valid JSON [LIVE]

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

**Expected:** `ok: all log lines are valid JSON`.

**Fail signal:** `FAIL:` output listing non-JSON lines.

---

#### T1.5.6 — Bad config → clear validation error [LIVE]

```bash
# Introduce a bad value (invalid port)
cp config.yaml /tmp/config_backup.yaml
sed 's/port: 5432/port: 99999/' config.yaml > /tmp/config_bad.yaml
cp /tmp/config_bad.yaml config.yaml

docker compose down
docker compose up -d
sleep 10
docker compose ps
docker compose logs cos
```

**Expected:**
- `cos` container shows `unhealthy` or `Exit` (not `healthy`)
- `docker compose logs cos` shows a human-readable error mentioning `port` or `99999`
- No raw Python traceback (`Traceback (most recent call last):` absent)

Restore config:

```bash
cp /tmp/config_backup.yaml config.yaml
docker compose down && docker compose up -d
```

---

## Epic 2 — Document Knowledge Base *(not yet started)*

Tests will be added here after Epic 2 stories complete.

---

## Running all live tests

Smoke-test sequence covering Stories 1.1–1.5. Run from the `cos/` directory with a valid `config.yaml` present.

```bash
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
bad = []
for l in sys.stdin:
    l = l.strip()
    if not l: continue
    try: json.loads(l)
    except: bad.append(l[:80])
print('ok' if not bad else f'FAIL: {len(bad)} non-JSON lines')
"

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

All 8 steps should complete without errors. Step 2 (MCP tool discovery) requires Claude Code — see T1.5.2 for setup.
