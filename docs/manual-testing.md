# Manual Testing Guide

Reflects the platform as built at the end of **Epic 2: Document Knowledge Base**. Run these tests to verify the platform is healthy and the ingestion pipeline is working correctly.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.

---

## Prerequisites

- Docker Desktop (or Rancher Desktop) running
- `uv` installed
- Working directory: `cos/`
- A valid `config.yaml` present (copy from `config.yaml.example` and fill in `llm.api_key` and `embedding.api_key` — both are required; `embedding.api_key` is needed for document ingestion to generate embeddings)

**Always use `uv run python`** (not `python3`) for any command that imports project code.

---

## What Epic 2 delivers

- Full document ingestion pipeline: PDF, Word (`.docx`), Markdown, and plain text
- `cos ingest <path>` — ingest a single file or folder from the CLI
- `cos docs` — list all ingested documents with provenance metadata
- `cos docs --versions <id>` — show version history for a document
- `cos docs --json` — machine-readable JSON output
- Originals stored byte-for-byte in `./data/originals/`; Markdown copies in `./data/markdown/`
- All four MCP tools registered: `get_status`, `retrieve`, `get_role_context`, `list_documents`
- `retrieve`, `get_role_context`, and `list_documents` MCP tools still return "Not yet implemented" error envelopes

Other CLI commands such as `cos status`, `cos logs`, and `cos restart` remain stubs.

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

## Epic 2: Document Ingestion & Provenance

**Prerequisites:**

- Platform running: `docker compose up -d` with all three services healthy
- `test-docs/` directory exists with `sample-brief.md`, `sample-report.pdf`, `sample-memo.docx`
- Working directory: `cos/`

### T2.6.1 — Ingest `test-docs/` folder: all 3 files ingested [LIVE]

```bash
docker compose run --rm -v "$(pwd)/test-docs:/test-docs" cos uv run cos ingest /test-docs/
```

**Expected output (order may vary):**

```text
Ingested sample-brief.md -> N chunks indexed
Ingested sample-report.pdf -> N chunks indexed
Ingested sample-memo.docx -> N chunks indexed
Ingested 3 files -> N total chunks indexed
```

All three file names appear. Chunk counts are at least 1. No error lines appear.

**Fail signal:** Any `Error:` line, a file listed as skipped unexpectedly, or a chunk count of `0` for any file.

### T2.6.2 — `cos docs` shows 3 documents with correct metadata [LIVE]

```bash
docker compose run --rm cos uv run cos docs
```

**Expected:** A table with 3 rows, one per test document.

Each row must have:

- `ID` — a UUID for the document (copy this value when using `--versions`)
- `SOURCE PATH` ending in `/test-docs/sample-brief.md`, `/test-docs/sample-report.pdf`, or `/test-docs/sample-memo.docx`
- `INGESTED AT` showing a recent timestamp
- `VER` = `1` for each document on first ingest
- `CHUNKS` >= `1` for each document

**Fail signal:** Fewer than 3 rows, `CHUNKS = 0`, `VER` not equal to `1`, or source paths that do not match the test files.

### T2.6.3 — Re-ingest and version history [LIVE]

First capture the document ID for `sample-brief.md`:

```bash
docker compose run --rm cos uv run cos docs
```

Copy the UUID from the `ID` column in the row for `sample-brief.md`.

Re-ingest the same file:

```bash
docker compose run --rm -v "$(pwd)/test-docs:/test-docs" cos uv run cos ingest /test-docs/sample-brief.md
```

Check version history:

```bash
docker compose run --rm cos uv run cos docs --versions "<document-id>"
```

**Expected:** Two rows are shown with version numbers `1` and `2`. The timestamps should be distinct and the file hashes may either match or differ depending on whether the file changed.

**Fail signal:** Only one version row appears, or the CLI prints `No versions found for document ID`.

### T2.6.4 — Originals are preserved byte-for-byte [LIVE]

```bash
ls -la data/originals/
diff test-docs/sample-brief.md data/originals/sample-brief.md && echo "sample-brief.md: identical"
diff test-docs/sample-report.pdf data/originals/sample-report.pdf && echo "sample-report.pdf: identical"
diff test-docs/sample-memo.docx data/originals/sample-memo.docx && echo "sample-memo.docx: identical"
```

**Expected:** All three comparison commands print `<name>: identical` and the three files are present in `data/originals/`.

**Fail signal:** Any `diff` output, any missing file, or a size mismatch between a source file and its stored original.

### T2.6.5 — Crash recovery leaves no partial document rows [LIVE]

Use `exec` rather than `run` for this test so the ingest process runs inside the existing `cos` container and can be killed predictably. First copy the fixtures into the running container:

```bash
docker compose cp test-docs/. cos:/tmp/test-docs
docker compose exec cos uv run cos ingest /tmp/test-docs
```

While ingestion is running, in a second terminal:

```bash
docker compose kill cos
docker compose up -d cos
sleep 10
docker compose run --rm cos uv run cos docs
```

**Expected:** After restart, `cos docs` shows only fully indexed documents. No row should appear with a missing chunk count or partially written state. A document is either present with a valid chunk count or absent.

**Fail signal:** Any partial record appears after restart, such as a document row with `CHUNKS = 0` caused by the interrupted ingest.

### T2.6.6 — `cos docs --json` returns valid JSON with all fields [LIVE]

```bash
docker compose run --rm cos uv run cos docs --json
```

**Expected:** A JSON array. Each item includes:

- `id`
- `source_path`
- `ingested_at`
- `current_version`
- `chunk_count`

**Fail signal:** Invalid JSON, missing fields, or an empty array after successful ingestion.

---

## 11 — Running all live tests

Use this sequence for a concise end-to-end operator pass:

```bash
docker compose up -d
docker compose ps
docker compose run --rm -v "$(pwd)/test-docs:/test-docs" cos uv run cos ingest /test-docs/
docker compose run --rm cos uv run cos docs
docker compose run --rm cos uv run cos docs --json | uv run python -c "
import sys, json
docs = json.load(sys.stdin)
assert len(docs) >= 3 and all(d['chunk_count'] > 0 for d in docs)
print(f'cos docs ok: {len(docs)} documents, all indexed')
"
```

**Expected:** Services are healthy, all three test documents ingest successfully, `cos docs` shows correct provenance metadata, and the JSON assertion prints `cos docs ok: 3 documents, all indexed`.

---

## 12 — Automated test suite

```bash
uv run pytest tests/ -v
```

**Expected:** All tests pass with no failures or collection errors.

---

## 13 — Bad config produces a clear error

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
