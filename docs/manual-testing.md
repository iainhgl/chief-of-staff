# Manual Testing Guide

Reflects the platform as built at the end of **Epic 1: Runnable Platform Foundation**. Run these tests to verify the platform is healthy and behaving correctly.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.

---

## Prerequisites

- Docker Desktop (or Rancher Desktop) running
- `uv` installed
- Working directory: `cos/`
- A valid `config.yaml` present (copy from `config.yaml.example` and fill in `llm.api_key`)

**Always use `uv run python`** (not `python3`) for any command that imports project code.

---

## What Epic 1 delivers

- Three-container platform (`postgres`, `tika`, `cos`) started with `docker compose up -d`
- Config validation at startup — human-readable errors for bad config
- Database schema applied automatically on every startup (idempotent)
- MCP server accessible via `docker compose exec` stdio transport
- **`get_status`** tool — returns JSON health of all three components and a `ready` flag
- **`retrieve`, `get_role_context`, `list_documents`** — registered but return "Not yet implemented" error envelopes

CLI commands (`cos status`, `cos logs`, etc.) are stubs and not available.

---

## 1 — Start the platform

```bash
docker compose up -d
```

Wait 30–60 seconds, then:

```bash
docker compose ps
```

**Expected:** All three services showing `(healthy)`.

```
NAME               STATUS
cos-cos-1          Up X seconds (healthy)
cos-postgres-1     Up X seconds (healthy)
cos-tika-1         Up X seconds (healthy)
```

**Fail signal:** Any service showing `unhealthy`, `starting`, or `Exit`.

---

## 2 — Verify startup logs

```bash
docker compose logs cos --tail=20
```

**Expected:** All lines are JSON objects. The sequence ends with these messages in order:

- `"message": "Postgres: healthy"`
- `"message": "Tika: healthy"`
- `"message": "config loaded"`
- `"message": "migrations applied"`
- `"message": "role pack: stub loaded"`
- `"message": "MCP server: listening"`

**Fail signal:** Any plain-text log line, missing entries, or traceback.

---

## 3 — Verify database schema

```bash
docker compose exec postgres psql -U postgres -d cos -c "\dt"
```

**Expected:** Four tables: `chunks`, `document_versions`, `documents`, `embeddings`.

```bash
docker compose exec postgres psql -U postgres -d cos -c "\d documents"
```

**Expected:** Columns include `id` (uuid), `source_path` (text), `file_hash` (text), `ingested_at` (timestamptz), `current_version` (integer), `status` (text).

**Fail signal:** Missing table or column, or `psql` error.

---

## 4 — Verify config loads correctly

```bash
uv run python -c "
from cos.config import CosConfig
config = CosConfig.load('config.yaml')
print('provider:', config.llm.provider)
print('model:', config.llm.model)
print('role_pack:', config.role_pack.path)
print('channels:', config.channels)
print('database host:', config.database.host)
print('tika url:', config.tika.url)
print('config loaded ok')
"
```

**Expected:** Field values printed from your `config.yaml`, ending with `config loaded ok`.

**Fail signal:** Any exception or unexpected `None` values.

---

## 5 — Verify config validation rejects bad input

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

**Expected:** `SystemExit` with a human-readable message identifying `llm` as the missing field. No raw traceback.

**Fail signal:** Raw `ValidationError` traceback, or no mention of the missing field.

---

## 6 — Verify `get_status` (no MCP client needed)

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json, cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import get_status
srv._config = CosConfig.load('/app/config.yaml')
result = json.loads(asyncio.run(get_status()))
assert result['status'] == 'ok', result
assert result['data']['ready'] == True, result
print('get_status ok')
print(json.dumps(result['data']['components'], indent=2))
"
```

**Expected:** `get_status ok` followed by three components all showing `"healthy": true`.

**Fail signal:** `status` not `"ok"`, `ready` not `true`, or any exception.

---

## 7 — Verify stub tools return error envelopes

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
    print(coro.__name__, '— error envelope: ok')
"
```

**Expected:** Each tool prints `— error envelope: ok`. No exceptions raised.

**Fail signal:** Any exception, or `status` not equal to `"error"`.

---

## 8 — Connect Claude Code and call tools live

If not already configured, run from the `cos/` directory:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Open a new Claude Code session and ask:

```
What MCP tools do you have available?
```

**Expected:** Four tools listed — `get_status`, `retrieve`, `get_role_context`, `list_documents`.

Then ask:

```
Call get_status and show me the raw JSON response.
```

**Expected:** `status: "ok"`, three healthy components, `ready: true`.

Then ask:

```
Call list_documents.
```

**Expected:** An error envelope with `"Not yet implemented"` — not an exception or Claude error.

---

## 9 — Verify all log lines are valid JSON

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

---

## 10 — Restart round-trip

```bash
docker compose down
docker compose up -d
```

Wait 30–60 seconds, then:

```bash
docker compose ps
```

**Expected:** All three services back to `(healthy)` with no manual intervention.

Follow up with test 2 (startup logs) to confirm clean restart.

---

## 11 — Automated test suite

```bash
uv run pytest tests/ -v
```

**Expected:** All tests pass with no failures or collection errors.

---

## 12 — Bad config produces a clear error

```bash
cp config.yaml /tmp/config_backup.yaml
sed 's/port: 5432/port: 99999/' config.yaml > /tmp/config_bad.yaml
cp /tmp/config_bad.yaml config.yaml

docker compose down && docker compose up -d
sleep 15
docker compose logs cos
```

**Expected:**
- `cos` container shows `unhealthy` or `Exit`
- Logs contain a human-readable error mentioning `port` or `99999`
- No raw Python traceback

Restore config and restart:

```bash
cp /tmp/config_backup.yaml config.yaml
docker compose down && docker compose up -d
```
