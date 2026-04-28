# Manual Testing Guide

Reflects the platform as built at the end of **Epic 3: Knowledge Retrieval & Cited Q&A**. Run these tests to verify the platform is healthy, documents are ingested, and questions are answered with grounded citations.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.

---

## Prerequisites

- Docker Desktop (or Rancher Desktop) running
- `uv` installed
- Working directory: `cos/`
- A valid `config.yaml` present (copy from `config.yaml.example` and fill in `llm.api_key` and `embedding.api_key` — both are required; `embedding.api_key` is needed for document ingestion to generate embeddings)

**Always use `uv run python`** (not `python3`) for any command that imports project code.

---

## What Epic 3 delivers

- Full document ingestion pipeline: PDF, Word (`.docx`), Markdown, and plain text (from Epic 2)
- `cos ingest <path>` — ingest a single file or folder from the CLI
- `cos docs` — list all ingested documents with provenance metadata
- `cos docs --versions <id>` — show version history for a document
- `cos docs --json` — machine-readable JSON output
- All four MCP tools working end-to-end:
  - `get_status` — platform health and component status
  - `retrieve` — hybrid search + LLM synthesis; returns grounded answer with citations
  - `list_documents` — returns all ingested documents with `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`
  - `get_role_context` — returns stub: `default — role pack not yet configured` (role identity arrives in Epic 4)
- OutputRouter enforces fail-closed egress: unrecognised channels suppress output and log a structured error

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
- `"message": "connection pool: open"`
- `"message": "role pack: stub loaded"`
- `"message": "output router: initialised"`
- `"message": "retrieval service: initialised"`
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

## 7 — Verify tools return valid envelopes

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import get_role_context, get_status

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)

    # get_status
    result = json.loads(await get_status())
    assert result['status'] == 'ok', f'get_status failed: {result}'
    print('get_status — ok')

    # get_role_context
    result = json.loads(await get_role_context())
    assert result['status'] == 'ok', f'get_role_context failed: {result}'
    assert 'role' in result['data'], f'Missing role field: {result}'
    print('get_role_context — ok, role:', result['data']['role'])

asyncio.run(main())
"
```

**Expected:** Both tools print `ok`. `get_role_context` reports `default — role pack not yet configured`.

**Fail signal:** `status != "ok"` for either tool, or any exception.

---

## 8 — Connect Claude Code and call tools live

**Prerequisite:** Documents must be ingested before testing `retrieve`. Run T2.6.1 (ingest `test-docs/`) if you have not already done so — the live `retrieve` query in this section requires at least one document in the knowledge base.

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
Use retrieve to answer: What frameworks do I have for workforce segmentation?
```

**Expected:** `status: "ok"`, `data.answer` is a grounded summary, and `citations` contains at least one source from the ingested knowledge base.

Then ask:

```
Call list_documents and show me the raw JSON response.
```

**Expected:** `status: "ok"`, `data.documents` is a list (may be empty if no documents ingested yet; see Epic 3 tests for ingestion).

Then ask:

```
Call get_role_context.
```

**Expected:** `status: "ok"`, `data.role` contains `default — role pack not yet configured` — not an error envelope.

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
docker compose run --rm --entrypoint /app/.venv/bin/cos -v "$(pwd)/test-docs:/test-docs" cos ingest /test-docs/
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
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs
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
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs
```

Copy the UUID from the `ID` column in the row for `sample-brief.md`.

Re-ingest the same file:

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos -v "$(pwd)/test-docs:/test-docs" cos ingest /test-docs/sample-brief.md
```

Check version history:

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --versions "<document-id>"
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
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs
```

**Expected:** After restart, `cos docs` shows only fully indexed documents. No row should appear with a missing chunk count or partially written state. A document is either present with a valid chunk count or absent.

**Fail signal:** Any partial record appears after restart, such as a document row with `CHUNKS = 0` caused by the interrupted ingest.

### T2.6.6 — `cos docs --json` returns valid JSON with all fields [LIVE]

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --json
```

**Expected:** A JSON array. Each item includes:

- `id`
- `source_path`
- `ingested_at`
- `current_version`
- `chunk_count`

**Fail signal:** Invalid JSON, missing fields, or an empty array after successful ingestion.

---

## Epic 3: Knowledge Retrieval & Cited Q&A

**Prerequisites:**

- Platform running: `docker compose up -d` (all three services healthy)
- `test-docs/` directory exists with `sample-brief.md`, `sample-report.pdf`, `sample-memo.docx`
- Documents ingested (run T2.6.1 if not already done)
- `config.yaml` has a valid `llm.api_key` — synthesis requires a live Claude API call
- Working directory: `cos/`

---

### T3.5.1 — `retrieve` returns a synthesised answer with citations [LIVE]

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

asyncio.run(main())
"
```

**Expected:**

```json
{
  "status": "ok",
  "data": {
    "answer": "<synthesised answer referencing ingested content>",
    "citations": [
      {
        "source_path": "/test-docs/sample-brief.md",
        "chunk_index": 0,
        "score": 0.91
      }
    ]
  },
  "citations": [
    {
      "source_path": "/test-docs/sample-brief.md",
      "chunk_index": 0,
      "score": 0.91
    }
  ]
}
```

Note: `citations` appears at both the top level and inside `data` — this is the standard tool envelope. Both fields contain identical data; the top-level `citations` field is consistent across all four tools.

- `status` is `"ok"`
- `data.answer` is a non-empty string
- `data.citations` contains at least one item
- Each citation has `source_path`, `chunk_index` (integer), and `score` (float)
- `source_path` is a path to one of the ingested test documents

**Fail signal:** `status != "ok"`, empty `data.citations`, or `data.answer` is null.

---

### T3.5.2 — Citations correspond to actual ingested documents [LIVE]

Run the `retrieve` tool (T3.5.1 above) and collect the `source_path` values from citations.

Then verify each appears in `cos docs` output:

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs
```

**Expected:** Every `source_path` returned in the `retrieve` response appears as a `SOURCE PATH` row in `cos docs` output. No citation points to a file that is not in the knowledge base.

To verify `chunk_index` validity: note the `CHUNKS` count for each cited document in `cos docs` output. Every `chunk_index` must be >= 0 and strictly less than that document's `CHUNKS` count.

**Fail signal:** A citation `source_path` not listed in `cos docs`, or a `chunk_index` that is negative or >= the `CHUNKS` count for that document.

---

### T3.5.3 — No-content query returns graceful no-results answer [LIVE]

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import retrieve

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await retrieve(query='quantum entanglement theory and photon spin states'))
    print(json.dumps(result, indent=2))

asyncio.run(main())
"
```

**Expected:**

- `status` is `"ok"`
- `data.answer` clearly states no relevant content was found — wording similar to `"No relevant content found in the knowledge base."`
- `data.citations` is an empty list `[]`
- No invented source paths or fabricated chunk references

**Fail signal:** `status == "error"`, fabricated citations, or an answer that invents content not present in any ingested document.

---

### T3.5.4 — `list_documents` MCP tool matches `cos docs` CLI [LIVE]

Run both and compare:

```bash
# MCP tool output
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import list_documents

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await list_documents())
    print(json.dumps(result, indent=2))

asyncio.run(main())
"

# CLI output (for comparison)
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --json
```

**Expected:**

- `list_documents` returns `status: "ok"`, `data.documents` is a list
- Each item in `data.documents` has: `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`
- The set of `source_path` values matches between `list_documents` and `cos docs --json`
- Document count is the same in both outputs

**Fail signal:** Mismatched document counts, missing fields in MCP response, or `status != "ok"`.

---

### T3.5.6 — `get_role_context` returns stub envelope [LIVE]

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import get_role_context

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await get_role_context())
    print(json.dumps(result, indent=2))
    assert result['status'] == 'ok', f'unexpected status: {result}'
    assert result['data']['role'] == 'default — role pack not yet configured', f'unexpected role: {result}'
    assert result['citations'] == [], f'expected empty citations: {result}'
    print('get_role_context ok')

asyncio.run(main())
"
```

**Expected:**

```json
{
  "status": "ok",
  "data": {
    "role": "default — role pack not yet configured"
  },
  "citations": []
}
```

- `status` is `"ok"`
- `data.role` is exactly `default — role pack not yet configured` (not an error envelope)
- `citations` is an empty list

**Fail signal:** `status != "ok"`, `data.role` contains an error message, or an exception is raised.

---

### T3.5.5 — OutputRouter fail-closed: unrecognised channel suppresses output [LIVE]

```bash
docker compose exec -i cos uv run python -c "
from cos.output.router import OutputRouter
router = OutputRouter(configured_channels=['local'])
router.send('nonexistent_channel', 'this content must be suppressed')
print('no exception raised — output suppressed')
"
```

**Expected:** `no exception raised — output suppressed` is printed. No content is delivered.

Then verify the structured error appears in logs:

```bash
docker compose logs cos --tail=10
```

**Expected:** A JSON log line with `"component": "output"` and the `"nonexistent_channel"` value — confirming the error was logged. No content reaches any output.

**Fail signal:** An exception is raised, `"output"` does not appear in recent logs, or the channel test content is delivered anywhere.

---

## 11 — Running all live tests

Use this sequence for a concise end-to-end operator pass:

```bash
# 1. Start services
docker compose up -d
docker compose ps

# 2. Ingest test fixtures
docker compose run --rm --entrypoint /app/.venv/bin/cos -v "$(pwd)/test-docs:/test-docs" cos ingest /test-docs/

# 3. Check provenance table output
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs

# 4. Validate JSON docs output
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --json | uv run python -c "
import sys, json
docs = json.load(sys.stdin)
assert len(docs) >= 3 and all(d['chunk_count'] > 0 for d in docs)
print(f'cos docs ok: {len(docs)} documents, all indexed')
"

# 5. Retrieve with citations (requires live LLM API — may take up to 5 seconds)
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import retrieve

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await retrieve(query='What frameworks do I have for workforce segmentation?'))
    assert result['status'] == 'ok', f'retrieve failed: {result}'
    assert len(result['data']['citations']) > 0, 'No citations returned'
    print(f'retrieve ok: {len(result[\"data\"][\"citations\"])} citations, answer length {len(result[\"data\"][\"answer\"])} chars')

asyncio.run(main())
"

# 6. List documents via MCP tool
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import list_documents

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await list_documents())
    assert result['status'] == 'ok', f'list_documents failed: {result}'
    docs = result['data']['documents']
    assert len(docs) >= 3, f'Expected >= 3 docs, got {len(docs)}'
    print(f'list_documents ok: {len(docs)} documents')

asyncio.run(main())
"

# 7. OutputRouter fail-closed (no API key needed)
docker compose exec -i cos uv run python -c "
from cos.output.router import OutputRouter
router = OutputRouter(configured_channels=['local'])
router.send('nonexistent_channel', 'this must be suppressed')
print('output suppressed — ok')
"
docker compose logs cos --tail=50 | grep '"component": "output"' | grep nonexistent || echo 'WARN: no output_router log found — check logs manually'
```

**Expected:** Services are healthy, all three test documents ingest successfully, `cos docs` shows correct provenance metadata, the retrieval step returns a cited answer, the MCP document listing reports the same ingested corpus, and the OutputRouter suppresses output for an unrecognised channel.

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
