# Story 3.5: Operator Validation — End-to-End Q&A with Citations

Status: done

## Story

As Iain (operator and first user),
I want to run a documented end-to-end smoke test of the complete retrieval and Q&A pipeline,
So that I can confirm the knowledge pipeline works correctly — from ingested document to cited answer — before adding role identity in Epic 4.

## Acceptance Criteria

1. **Given** a set of documents has been ingested and the platform is running,
   **When** a question is asked via Claude Desktop or Claude Code using the `retrieve` tool — e.g. "What frameworks do I have for workforce segmentation?",
   **Then** a synthesised answer is returned that references content from the ingested documents, includes at least one citation with a `source_path` pointing to a real ingested file, and does not contain fabricated information absent from the knowledge base.

2. **Given** the same query is asked,
   **When** the citations in the response are checked against the knowledge base,
   **Then** each cited `source_path` corresponds to an actual ingested document visible in `cos docs` output, and each `chunk_index` is a valid index for that document.

3. **Given** a query for which no relevant content exists in the knowledge base,
   **When** the `retrieve` tool responds,
   **Then** the answer clearly states no relevant content was found — it does not fabricate sources or invent citations.

4. **Given** `list_documents` is called from Claude Desktop or Claude Code,
   **When** the response is received,
   **Then** it lists all ingested documents with correct metadata — consistent with `cos docs` CLI output.

5. **Given** a channel name not in `CosConfig.output_channels` is passed to `OutputRouter` (tested directly),
   **When** the router handles it,
   **Then** the output is suppressed, a structured error appears in `docker compose logs cos`, and no response is delivered to any channel.

## Tasks / Subtasks

- [x] Task 1: Update `docs/manual-testing.md` header and capabilities section for Epic 3 (AC: #1–5)
  - [x] Update header to reflect Epic 3: Knowledge Retrieval & Cited Q&A
  - [x] Replace "What Epic 2 delivers" with "What Epic 3 delivers" section
  - [x] Update Test 2 (startup logs) to include new log messages added in Story 3.4
  - [x] Update Test 7 (formerly "stub tools return error envelopes") to verify real tool implementations
  - [x] Update Test 8 (Claude Code live test) to exercise `retrieve` and `list_documents` as working tools

- [x] Task 2: Add Epic 3 validation section to `docs/manual-testing.md` (AC: #1–5)
  - [x] Add T3.5.1 — `retrieve` returns a synthesised answer with citations from ingested docs
  - [x] Add T3.5.2 — Citations are valid: source_path matches ingested documents, chunk_index is present
  - [x] Add T3.5.3 — No-content query returns "no relevant content" without fabrication
  - [x] Add T3.5.4 — `list_documents` MCP tool output matches `cos docs` CLI output
  - [x] Add T3.5.5 — OutputRouter fail-closed: unrecognised channel suppresses output and logs error

- [x] Task 3: Update the "Running all live tests" quick-script in `docs/manual-testing.md` (AC: #1–4)
  - [x] Extend quick-script with MCP `retrieve` and `list_documents` validation steps

### Review Findings

- [x] [Review][Decision] Example JSON in T3.5.1 has `citations` at both top-level and inside `data` — source-confirmed envelope pattern; added explanatory note [docs/manual-testing.md]
- [x] [Review][Decision] Section 7 only tests `get_status` and `get_role_context` — accepted as-is; `retrieve`/`list_documents` covered by T3.5.1/T3.5.4
- [x] [Review][Decision] Section 11 quick-script omits T3.5.5 OutputRouter fail-closed check — added step 7 [docs/manual-testing.md]
- [x] [Review][Patch] T3.5.5 calls `await router.send()` but `OutputRouter.send()` is a synchronous method — removed `await` and simplified to sync call [docs/manual-testing.md, src/cos/output/router.py:19]
- [x] [Review][Patch] T3.5.5 expects log line with `"component": "output_router"` but source logs `"component": "output"` — corrected [docs/manual-testing.md, src/cos/output/router.py:25,38,51]
- [x] [Review][Patch] T3.5.2 gives no concrete command to verify `chunk_index` against document CHUNKS count — added actionable instruction [docs/manual-testing.md]
- [x] [Review][Defer] Quick-script steps assert `len(docs) >= 3` with no prerequisite guard — design concern, not a doc error; docs do reference T2.6.1 in prerequisites [docs/manual-testing.md] — deferred, pre-existing
- [x] [Review][Defer] `_startup_sequence` is a private API called directly in all test snippets — fragile if renamed; established pattern documented in Dev Notes, not introduced by this story [docs/manual-testing.md] — deferred, pre-existing
- [x] [Review][Defer] T3.5.3 no-results query uses domain-specific phrase that may match future KB content — acceptable for current test-docs set [docs/manual-testing.md] — deferred, pre-existing
- [x] [Review][Defer] `list_documents` does not filter by document status — "all ingested documents" claim technically includes inactive docs [src/cos/mcp_server/tools.py] — deferred, pre-existing

## Dev Notes

### What This Story Is

Story 3.5 is an operator validation story. The dev agent's primary deliverable is an updated `docs/manual-testing.md`. The operator (Iain) runs through the tests manually and marks the story done. There are no automated test changes and no `src/` changes.

### Architecture Constraints

- No new source files. No new tests. No changes to `src/` or `tests/`.
- Changes are limited to: `docs/manual-testing.md` (update)
- The `test-docs/` fixtures committed in Story 2.6 (`sample-brief.md`, `sample-report.pdf`, `sample-memo.docx`) are still used. Do not recreate or modify them.

### Current State After Epic 3 Stories

By the end of Story 3.4, all four MCP tools have real implementations:
- `get_status` — already worked from Epic 1; unchanged
- `retrieve` — now calls `RetrievalService.query()` and returns synthesised answer with citations
- `list_documents` — now calls `ProvenanceService.list_documents()` and returns document list
- `get_role_context` — returns ok stub `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}`

**What used to be Test 7** in `manual-testing.md` checked that stubs returned `"Not yet implemented"` error envelopes. This is no longer correct. The test must be replaced with verification of real tool behaviour.

### Updated Startup Log Sequence (After Story 3.4)

The startup log sequence now includes pool, output router, and retrieval service messages:

```
"message": "Postgres: healthy"
"message": "Tika: healthy"
"message": "config loaded"
"message": "migrations applied"
"message": "connection pool: open"
"message": "role pack: stub loaded"
"message": "output router: initialised"
"message": "retrieval service: initialised"
"message": "MCP server: listening"
```

Test 2 in `manual-testing.md` must be updated to expect all nine messages in this order.

### Running the Retrieve Tool Directly (Without MCP Client)

The `retrieve` tool can be exercised without Claude Desktop by calling it directly in the running container. This is the recommended approach for T3.5.1–T3.5.3 so the operator can verify the pipeline without needing a connected MCP client:

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import retrieve, list_documents

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await retrieve(query='What frameworks do I have for workforce segmentation?'))
    print(json.dumps(result, indent=2))

asyncio.run(main())
"
```

**Note:** `_startup_sequence` must be awaited first to initialise `_retrieval_service`, `_pool`, and `_output_service`. Without it, `retrieve` returns a `{"status": "error", "error": "Server not initialized"}` envelope.

### OutputRouter Fail-Closed Test (T3.5.5)

The OutputRouter is in `src/cos/output/router.py`. Testing fail-closed behaviour directly:

```bash
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.output.router import OutputRouter

async def main():
    config = CosConfig.load('/app/config.yaml')
    router = OutputRouter(configured_channels=config.channels)
    await router.send('nonexistent_channel', 'this should be suppressed')
    print('output suppressed — no exception raised')

asyncio.run(main())
"
```

Then verify the structured error appears in the logs:

```bash
docker compose logs cos --tail=10
```

**Expected:** A JSON log line with `"component": "output_router"` and the channel name — no response delivered anywhere.

### Updated `docs/manual-testing.md` Content

#### Header and Capabilities Section

Replace the current header and "What Epic 2 delivers" block with:

```
# Manual Testing Guide

Reflects the platform as built at the end of **Epic 3: Knowledge Retrieval & Cited Q&A**. Run these tests to verify the platform is healthy, documents are ingested, and questions are answered with grounded citations.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.
```

Replace "What Epic 2 delivers" section with:

```
## What Epic 3 delivers

- Full document ingestion pipeline: PDF, Word (.docx), Markdown, and plain text (from Epic 2)
- `cos ingest <path>` — ingest a single file or folder from the CLI
- `cos docs` — list all ingested documents with provenance metadata
- `cos docs --versions <id>` — show version history for a document
- `cos docs --json` — machine-readable JSON output
- All four MCP tools working end-to-end:
  - `get_status` — platform health and component status
  - `retrieve` — hybrid search + LLM synthesis; returns grounded answer with citations
  - `list_documents` — returns all ingested documents with id, source_path, ingested_at, current_version, chunk_count
  - `get_role_context` — returns stub: "default — role pack not yet configured" (role identity arrives in Epic 4)
- OutputRouter enforces fail-closed egress: unrecognised channels suppress output and log a structured error
```

#### Updated Test 2 (Startup Logs)

Replace the existing Test 2 expected log sequence:

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
```

#### Updated Test 7 (Replace Stub Check with Real Tool Verification)

Replace the entire Test 7 block with:

```
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

**Expected:** Both tools print `ok`. `get_role_context` reports `"default — role pack not yet configured"`.

**Fail signal:** `status != "ok"` for either tool, or any exception.
```

#### Updated Test 8 (Claude Code Live Session)

Replace the Test 8 block with:

```
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
Call list_documents and show me the raw JSON response.
```

**Expected:** `status: "ok"`, `data.documents` is a list (may be empty if no documents ingested yet; see Epic 3 tests for ingestion).

Then ask:

```
Call get_role_context.
```

**Expected:** `status: "ok"`, `data.role` contains `"default — role pack not yet configured"` — not an error envelope.
```

#### Epic 3 Validation Tests to Add

Add this full section after the existing Epic 2 section:

```
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
        "chunk_index": <integer>,
        "score": <float>
      }
    ]
  },
  "citations": [...]
}
```

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

**Fail signal:** A citation `source_path` that is not listed in `cos docs`, or a `chunk_index` that is negative or implausibly large (e.g. larger than the `CHUNKS` count for that document).

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

### T3.5.5 — OutputRouter fail-closed: unrecognised channel suppresses output [LIVE]

```bash
docker compose exec -i cos uv run python -c "
import asyncio
from cos.output.router import OutputRouter

async def main():
    router = OutputRouter(configured_channels=['local'])
    await router.send('nonexistent_channel', 'this content must be suppressed')
    print('no exception raised — output suppressed')

asyncio.run(main())
"
```

**Expected:** `no exception raised — output suppressed` is printed. No content is delivered.

Then verify the structured error appears in logs:

```bash
docker compose logs cos --tail=10
```

**Expected:** A JSON log line with `"component": "output_router"` and the `"nonexistent_channel"` value — confirming the error was logged. No content reaches any output.

**Fail signal:** An exception is raised, `"output_router"` does not appear in recent logs, or the channel test content is delivered anywhere.

---
```

#### Updated Quick-Script (Section 11)

Add these steps to the existing quick-script:

```bash
# 15. Retrieve with citations (requires live LLM API — may take up to 5 seconds)
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

# 16. List documents via MCP tool
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
```

### Files to Create or Modify

| File | Action | Notes |
|------|--------|--------|
| `docs/manual-testing.md` | Modify | Update header, capabilities, Test 2, Test 7, Test 8; add Epic 3 test section; extend quick-script |

Do NOT modify: any file in `src/`, `tests/`, `test-docs/`, `_bmad-output/`, or `docker-compose.yml`.

### References

- MCP tools: `src/cos/mcp_server/tools.py` — `retrieve()`, `list_documents()`, `get_role_context()`, `get_status()`
- Server startup: `src/cos/mcp_server/server.py:_startup_sequence()` — initialises `_pool`, `_retrieval_service`, `_output_service`
- OutputRouter: `src/cos/output/router.py` — `OutputRouter.send(channel, content)` — fail-closed on unrecognised channel
- RetrievalService: `src/cos/services/retrieval.py:RetrievalService.query(text, role_pack)` — returns `CitedResponse(answer, citations)`
- Citations shape: `src/cos/retrieval/citations.py` — `CitedChunk` has `source_path`, `chunk_index`, `score`
- ProvenanceService: `src/cos/services/provenance.py:ProvenanceService.list_documents()` — returns `list[DocumentSummary]`
- DocumentSummary: `src/cos/store/models.py` — fields: `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`
- Manual testing guide pattern: `docs/manual-testing.md` (Story 2.6 format)
- Test fixtures: `test-docs/sample-brief.md`, `test-docs/sample-report.pdf`, `test-docs/sample-memo.docx`

### Key Gotcha: `_startup_sequence` Must Be Called Before Direct Tool Invocation

When testing tools directly (via `docker compose exec python -c ...`), you must call `await srv._startup_sequence(config)` first. This initialises `_pool`, `_retrieval_service`, and `_output_service`. Without it, `get_retrieval_service()` returns `None` and `retrieve()` returns a `{"status": "error", "error": "Server not initialized"}` envelope.

This is expected behaviour — in production, the MCP server framework calls `_startup_sequence` on startup before any tools can be called.

### Key Gotcha: LLM API Key Required for T3.5.1–T3.5.3

`retrieve` makes a real Claude API call via `AnthropicAdapter`. Tests T3.5.1 and T3.5.3 will fail with an auth error if `config.yaml` has an invalid or missing `llm.api_key`. Verify the key is valid before running Epic 3 tests.

### Key Gotcha: Source Path Is Container Path

`source_path` values in both `list_documents` and `cos docs` show the **container path** at ingest time (e.g. `/test-docs/sample-brief.md`), not the host path. This is the path that was passed to `cos ingest` inside the container. When verifying T3.5.2, compare container paths to container paths.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- `uv run pytest tests/ -q`
- `git diff -- docs/manual-testing.md`

### Completion Notes List

- Updated `docs/manual-testing.md` to reflect the end of Epic 3 rather than Epic 2.
- Replaced obsolete stub-tool validation with live MCP guidance for `get_status`, `retrieve`, `list_documents`, and `get_role_context`.
- Added a new Epic 3 validation section covering cited retrieval, no-results handling, document-list parity, and OutputRouter fail-closed behavior.
- Extended the condensed live-test script with retrieval and MCP document-list checks.
- Re-ran the repository test suite after the docs-only change to confirm no regressions.

### File List

- `docs/manual-testing.md`
- `_bmad-output/implementation-artifacts/3-5-operator-validation-end-to-end-qa-with-citations.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-28: Updated the Epic 3 manual validation guide and quick-script for cited retrieval and MCP document listing.
