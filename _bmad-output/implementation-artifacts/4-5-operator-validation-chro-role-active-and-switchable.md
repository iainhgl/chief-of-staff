# Story 4.5: Operator Validation — CHRO Role Active & Switchable

Status: done

## Story

As Iain (operator and first user),
I want to run a documented smoke test of the role pack system,
So that I can confirm the CHRO persona is active, applied to queries, and that switching roles works without code changes.

## Acceptance Criteria

1. **Given** the platform is running with the CHRO role pack configured,
   **When** `get_role_context` is called from Claude Desktop or Claude Code,
   **Then** the response includes the CHRO role name, goals, tone, and knowledge taxonomy — correctly loaded from the YAML file.

2. **Given** a query is submitted that would benefit from CHRO-specific prioritisation (e.g. "What do I have on workforce segmentation frameworks?"),
   **When** the `retrieve` tool responds,
   **Then** the answer reflects CHRO tone (strategic, evidence-based) and cites HR-relevant documents with higher priority than general documents — a noticeable difference from the stub behaviour in Epic 3.

3. **Given** the `enterprise_architect.yaml` role pack exists,
   **When** `config.yaml` is updated to point to it and `docker compose restart cos` is run,
   **Then** `get_role_context` returns the Enterprise Architect configuration, and the same query as above returns a response with different tone and prioritisation — no files other than `config.yaml` were changed.

4. **Given** `config.yaml` is reverted to the CHRO role pack and the container is restarted,
   **When** `get_role_context` is called,
   **Then** the CHRO configuration is active again — the switch is fully reversible.

## Tasks / Subtasks

- [x] Task 1: Update `docs/manual-testing.md` header and capabilities section for Epic 4 (AC: #1–4)
  - [x] Update header to reflect Epic 4: Role Identity & Configuration
  - [x] Replace "What Epic 3 delivers" with "What Epic 4 delivers" section
  - [x] Update Test 2 (startup logs) to reflect new log sequence: `"Role pack loaded"` replaces `"role pack: stub loaded"`, and `"connection pool: open"` now appears after role pack loading
  - [x] Update Test 7 (`get_role_context` verification): replace `data.role` assertions with `data.role_name`; update expected value from stub to `"CHRO"`
  - [x] Update Test 8 (Claude Code live session): update expected `get_role_context` response to show CHRO role name
  - [x] Remove T3.5.6 (stub role context check — superseded by T4.5.1 in the Epic 4 section)

- [x] Task 2: Add Epic 4 validation section to `docs/manual-testing.md` (AC: #1–4)
  - [x] Add T4.5.1 — `get_role_context` returns CHRO role name, goals, tone, knowledge taxonomy
  - [x] Add T4.5.2 — `retrieve` query with CHRO config shows strategic/evidence-based tone in the answer
  - [x] Add T4.5.3 — Switch to Enterprise Architect: edit `config.yaml`, restart, verify role name and tone change
  - [x] Add T4.5.4 — Revert to CHRO: edit `config.yaml` back, restart, verify CHRO config is active again

- [x] Task 3: Update Section 11 quick-script in `docs/manual-testing.md` (AC: #1)
  - [x] Add step to verify `get_role_context` returns `role_name: "CHRO"` after startup

### Review Findings

- [x] [Review][Patch] T4.5.3 Step 4 `json.dumps(result['data']['answer'], indent=2)` double-encodes a string — should be `print(result['data']['answer'])` [docs/manual-testing.md:T4.5.3 Step 4]
- [x] [Review][Defer] T4.5.1 `'Strategic' in result['data']['tone']` case-sensitive substring check against CHRO YAML; fragile if tone text changes [docs/manual-testing.md:T4.5.1] — deferred, pre-existing concern
- [x] [Review][Defer] Section 11 Step 8 OutputRouter check greps `docker compose logs cos` — contradicts T3.5.5 note that exec stream is the correct stream [docs/manual-testing.md:Section 11] — deferred, pre-existing from Epic 3
- [x] [Review][Defer] `_startup_sequence` called directly inside short-lived exec sessions — establishes a new pool per exec; pool lifecycle is implicit [docs/manual-testing.md:all tests] — deferred, established pattern from Epic 3
- [x] [Review][Defer] "Wait ~30 seconds" is vague — no explicit health-check verification before log inspection [docs/manual-testing.md:T4.5.3, T4.5.4] — deferred, consistent with existing doc pattern
- [x] [Review][Defer] T4.5.3 has no pre-check that `config.yaml` was saved correctly before restart — operator could edit the wrong file silently [docs/manual-testing.md:T4.5.3] — deferred, minor UX gap

## Dev Notes

### What This Story Is

Story 4.5 is an operator validation story. The dev agent's primary deliverable is an updated `docs/manual-testing.md`. The operator (Iain) runs through the tests manually and marks the story done. There are no automated test changes and no `src/` changes.

### Architecture Constraints

- No new source files. No new tests. No changes to `src/` or `tests/`.
- Changes are limited to: `docs/manual-testing.md` (update)
- Do not modify any file in `role_packs/`, `test-docs/`, `_bmad-output/`, or `docker-compose.yml`.

### Current State After Epic 4 Stories

By the end of Story 4.4, the role pack system is fully operational:

- `get_role_context` returns the full CHRO role pack configuration — NOT the old stub response
- `retrieve` applies CHRO tone (`"Strategic and evidence-based — translate HR concepts into business and financial impact..."`) to every synthesis prompt
- `retrieve` applies CHRO retrieval priority weights from `retrieval_priorities` when ranking chunks
- `role_packs/chro.yaml` — CHRO role pack (8 required fields); loaded by default via `config.yaml`
- `role_packs/enterprise_architect.yaml` — second role pack (same 8 fields, Enterprise Architect domain); exists to demonstrate portability
- `src/cos/llm/factory.py` — provider-agnostic factory; `make_llm_adapter(config)` is the only entrypoint used by `server.py`
- Switching role packs requires only editing `config.yaml` and restarting the container — no code changes

### Updated Startup Log Sequence (After Story 4.4)

The startup log sequence changed in Epic 4. Two things changed from Epic 3:

1. `"role pack: stub loaded"` is **removed** — replaced by `"Role pack loaded"` from a **different component** (`"rolepack"` not `"mcp_server"`)
2. `"connection pool: open"` now appears **after** `"Role pack loaded"` (was before in Epic 3)

The correct new sequence for Test 2:

```
"message": "Postgres: healthy"
"message": "Tika: healthy"
"message": "config loaded"        ← also contains "role_pack_path" extra field
"message": "migrations applied"
"message": "Role pack loaded"     ← component: "rolepack", contains "role_name": "CHRO"
"message": "connection pool: open"   ← moved: now AFTER role pack, not before
"message": "output router: initialised"
"message": "retrieval service: initialised"
"message": "MCP server: listening"
```

Replace the old Test 2 expected sequence (which had `"role pack: stub loaded"` before `"connection pool: open"`) with the sequence above.

### Updated `get_role_context` Response Shape (After Story 4.4)

`get_role_context` no longer returns the stub `{"role": "default — role pack not yet configured"}`. It returns the full role pack data.

**Old response (Epic 3 stub — no longer valid):**
```json
{
  "status": "ok",
  "data": {
    "role": "default — role pack not yet configured"
  },
  "citations": []
}
```

**New response (Epic 4 CHRO role pack):**
```json
{
  "status": "ok",
  "data": {
    "role_name": "CHRO",
    "goals": [
      "Drive HR transformation focused on PE value creation levers (productivity, cost, talent)",
      "..."
    ],
    "tone": "Strategic and evidence-based — translate HR concepts into business and financial impact...",
    "knowledge_taxonomy": [
      "HR operating models and transformation frameworks",
      "..."
    ],
    "active_workflows": [
      "hr_diagnostic",
      "ceo_board_prep",
      "weekly_prioritisation",
      "communication_drafting"
    ]
  },
  "citations": []
}
```

Key field name change: `data.role` → `data.role_name`. Any assertion or display referencing `data.role` must be updated.

**Tests that reference the old field and must be updated:**
- Test 7: `assert 'role' in result['data']` → `assert 'role_name' in result['data']`
- Test 7: `result['data']['role']` → `result['data']['role_name']`
- Test 8: expected Claude Code response showing the stub text
- T3.5.6: entire test is for the stub — remove it from the Epic 3 section

### Role Pack Switch Procedure

Both `config.yaml` and `role_packs/` are mounted into the running `cos` container read-only (`docker-compose.yml` lines 38–39). The container reads them at startup only. To switch role packs:

1. On the **host** (in the `cos/` directory), edit `config.yaml`:
   ```yaml
   role_pack:
     path: role_packs/enterprise_architect.yaml   # was: role_packs/chro.yaml
   ```
2. Run:
   ```bash
   docker compose restart cos
   ```
3. Wait ~30 seconds for health checks to pass, then verify:
   ```bash
   docker compose logs cos --tail=20
   ```
   Startup logs should show `"message": "Role pack loaded"` with `"role_name": "Enterprise Architect"`.

To revert, change `role_packs/enterprise_architect.yaml` back to `role_packs/chro.yaml` and restart again.

**No code changes are needed.** The role pack path is the only config value that changes between T4.5.3 and T4.5.4.

### Running `get_role_context` Directly

Use this command to verify role context without a connected MCP client:

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

asyncio.run(main())
"
```

**Note:** `_startup_sequence` must be awaited first to initialise `_role_pack_service`. Without it, `get_role_context` returns `{"status": "error", "error": "Server not initialized"}`.

### `docs/manual-testing.md` — Detailed Content Changes

#### Header and Capabilities Section (replace entirely)

```
# Manual Testing Guide

Reflects the platform as built at the end of **Epic 4: Role Identity & Configuration**. Run these tests to verify the platform is healthy, documents are ingested, questions are answered with grounded citations, and the CHRO role identity is active and switchable.

This guide is rewritten at the end of each epic to reflect current platform state — it does not accumulate historical tests.
```

```
## What Epic 4 delivers

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

Other CLI commands such as `cos status`, `cos logs`, and `cos restart` remain stubs.
```

#### Updated Test 2 (Startup Logs)

Replace the current expected log sequence with:

```
**Expected:** All lines are JSON objects. The sequence ends with these messages in order:

- `"message": "Postgres: healthy"`
- `"message": "Tika: healthy"`
- `"message": "config loaded"`
- `"message": "migrations applied"`
- `"message": "Role pack loaded"` — component is `"rolepack"`, includes `"role_name": "CHRO"`
- `"message": "connection pool: open"`
- `"message": "output router: initialised"`
- `"message": "retrieval service: initialised"`
- `"message": "MCP server: listening"`

**Note:** `"connection pool: open"` now appears after `"Role pack loaded"` — this is intentional (pool creation follows role pack validation).

**Fail signal:** Any plain-text log line, missing entries, `"role pack: stub loaded"` (obsolete stub message), or traceback.
```

#### Updated Test 7 (Tools Verification)

Replace the current Test 7 block with:

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
    assert 'role_name' in result['data'], f'Missing role_name field: {result}'
    print('get_role_context — ok, role:', result['data']['role_name'])

asyncio.run(main())
"
```

**Expected:** Both tools print `ok`. `get_role_context` reports `CHRO` (not the old stub `"default — role pack not yet configured"`).

#### Updated Test 8 (Claude Code Live Session)

Update the `get_role_context` prompt and expected output:

```
Then ask:

    Call get_role_context.

**Expected:** `status: "ok"`, `data.role_name` is `"CHRO"`, `data.goals` is a list, `data.tone` describes the CHRO persona — not the old stub text.
```

#### Remove T3.5.6

Remove the T3.5.6 block entirely (it verified the stub role context, which no longer exists). The equivalent check is now T4.5.1.

#### Epic 4 Validation Section (add after Epic 3 section)

```
## Epic 4: Role Identity & Configuration

**Prerequisites:**

- Platform running: `docker compose up -d` (all three services healthy)
- `config.yaml` has `role_pack.path: role_packs/chro.yaml` (the default)
- Documents ingested (run T2.6.1 if not already done — the retrieve test requires at least one document)
- `config.yaml` has valid `llm.api_key` and `embedding.api_key`
- Working directory: `cos/`

---

### T4.5.1 — `get_role_context` returns CHRO configuration [LIVE]

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
    assert result['data']['role_name'] == 'CHRO', f'unexpected role_name: {result}'
    assert isinstance(result['data']['goals'], list) and len(result['data']['goals']) > 0
    assert 'Strategic' in result['data']['tone'], f'unexpected tone: {result}'
    assert isinstance(result['data']['knowledge_taxonomy'], list)
    assert isinstance(result['data']['active_workflows'], list)
    assert result['citations'] == [], f'expected empty citations: {result}'
    print('get_role_context ok — CHRO role pack active')

asyncio.run(main())
"
```

**Expected:**

```json
{
  "status": "ok",
  "data": {
    "role_name": "CHRO",
    "goals": ["Drive HR transformation focused on PE value creation levers...", "..."],
    "tone": "Strategic and evidence-based — translate HR concepts into business and financial impact...",
    "knowledge_taxonomy": ["HR operating models and transformation frameworks", "..."],
    "active_workflows": ["hr_diagnostic", "ceo_board_prep", "weekly_prioritisation", "communication_drafting"]
  },
  "citations": []
}
```

- `status` is `"ok"`
- `data.role_name` is exactly `"CHRO"`
- `data.goals` is a non-empty list
- `data.tone` contains `"Strategic"` — confirms CHRO persona loaded from YAML
- `data.knowledge_taxonomy` is a non-empty list
- `data.active_workflows` is a non-empty list
- `citations` is an empty list

**Fail signal:** `status != "ok"`, `data.role_name` is missing or not `"CHRO"`, `data` contains `"role": "default..."` (old stub), or any exception.

---

### T4.5.2 — `retrieve` applies CHRO tone to synthesised answers [LIVE]

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

- `status` is `"ok"`
- `data.answer` is a non-empty string with a commercially-minded, evidence-based tone (not generic or HR-jargon-heavy)
- `data.citations` contains at least one item (requires ingested test docs)

Observe the answer language: with the CHRO role pack active, the synthesis prompt includes the instruction to be *"direct, concise, and commercially-minded"* and to *"translate HR concepts into business and financial impact"*. The answer should reflect this framing compared to a plain retrieval without role context.

**Fail signal:** `status != "ok"`, empty `data.citations`, `data.answer` is null.

---

### T4.5.3 — Switch to Enterprise Architect role pack [LIVE]

**Step 1:** Edit `config.yaml` on the host (in the `cos/` directory):

```yaml
role_pack:
  path: role_packs/enterprise_architect.yaml   # was: role_packs/chro.yaml
```

**Step 2:** Restart the `cos` container:

```bash
docker compose restart cos
```

Wait ~30 seconds, then check startup logs:

```bash
docker compose logs cos --tail=20
```

**Expected log entry:** A JSON line with `"message": "Role pack loaded"` and `"role_name": "Enterprise Architect"`.

**Step 3:** Verify `get_role_context` returns Enterprise Architect data:

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
    assert result['data']['role_name'] == 'Enterprise Architect', f'unexpected role_name: {result}'
    assert 'pragmatic' in result['data']['tone'].lower(), f'unexpected tone: {result}'
    print('get_role_context ok — Enterprise Architect role pack active')

asyncio.run(main())
"
```

**Expected:** `data.role_name` is `"Enterprise Architect"`, `data.tone` reflects architecture/pragmatic framing (different from CHRO strategic/evidence-based).

**Step 4:** Run the same workforce query and observe the different response style:

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
    print(json.dumps(result['data']['answer'], indent=2))

asyncio.run(main())
"
```

**Expected:** Answer reflects the Enterprise Architect tone: structured, pragmatic, with technical/business alignment framing — noticeably different from the CHRO answer in T4.5.2.

**Fail signal:** `data.role_name` is `"CHRO"` (container not restarted), `status != "ok"`, or any exception.

---

### T4.5.4 — Revert to CHRO confirms full reversibility [LIVE]

**Step 1:** Edit `config.yaml` back on the host:

```yaml
role_pack:
  path: role_packs/chro.yaml   # restore CHRO
```

**Step 2:** Restart the `cos` container:

```bash
docker compose restart cos
```

Wait ~30 seconds, then verify:

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
    assert result['status'] == 'ok', f'unexpected status: {result}'
    assert result['data']['role_name'] == 'CHRO', f'unexpected role_name: {result}'
    print('get_role_context ok — CHRO restored')

asyncio.run(main())
"
```

**Expected:** `data.role_name` is `"CHRO"` again. The switch is fully reversible with no code changes.

**Fail signal:** `data.role_name` is still `"Enterprise Architect"`, or any exception.
```

#### Updated Quick-Script (Section 11)

Add this step after the existing retrieve and list_documents steps:

```bash
# 8. Role context check (requires CHRO role pack configured in config.yaml)
docker compose exec -i cos uv run python -c "
import asyncio, json
import cos.mcp_server.server as srv
from cos.config import CosConfig
from cos.mcp_server.tools import get_role_context

async def main():
    config = CosConfig.load('/app/config.yaml')
    await srv._startup_sequence(config)
    result = json.loads(await get_role_context())
    assert result['status'] == 'ok', f'get_role_context failed: {result}'
    assert result['data']['role_name'] == 'CHRO', f'Expected CHRO, got: {result[\"data\"].get(\"role_name\")}'
    print(f'get_role_context ok: role={result[\"data\"][\"role_name\"]}')

asyncio.run(main())
"
```

### Files to Create or Modify

| File | Action | Notes |
|------|--------|--------|
| `docs/manual-testing.md` | Modify | Update header, capabilities, Test 2, Test 7, Test 8; remove T3.5.6; add Epic 4 section; extend quick-script |

Do NOT modify: any file in `src/`, `tests/`, `test-docs/`, `role_packs/`, `_bmad-output/`, or `docker-compose.yml`.

### References

- `get_role_context` tool: `src/cos/mcp_server/tools.py:100–125` — returns `role_name`, `goals`, `tone`, `knowledge_taxonomy`, `active_workflows`
- CHRO role pack: `role_packs/chro.yaml` — 8 fields including `tone: "Strategic and evidence-based..."`
- Enterprise Architect role pack: `role_packs/enterprise_architect.yaml` — `tone: "Structured and pragmatic..."`
- Server startup sequence: `src/cos/mcp_server/server.py:86–129` — role pack loading at line 99–113, `"Role pack loaded"` emitted at line 114, pool at line 115
- RolePackService: `src/cos/services/rolepack.py` — `get_active()` returns the loaded `RolePackConfig`
- `RolePackConfig` schema: 8 required fields in `src/cos/rolepack/loader.py`
- Docker Compose volume mounts: `docker-compose.yml:38–39` — `config.yaml` and `role_packs/` mounted read-only
- Previous operator validation story: `_bmad-output/implementation-artifacts/3-5-operator-validation-end-to-end-qa-with-citations.md`
- Test fixtures: `test-docs/sample-brief.md`, `test-docs/sample-report.pdf`, `test-docs/sample-memo.docx`

### Key Gotcha: `_startup_sequence` Must Be Called Before Direct Tool Invocation

When testing tools directly (via `docker compose exec python -c ...`), always call `await srv._startup_sequence(config)` first. This initialises `_role_pack_service`. Without it, `get_role_context` returns `{"status": "error", "error": "Server not initialized", "detail": "role pack service not ready"}`.

### Key Gotcha: Old Stub Field `data.role` No Longer Exists

After Epic 4, `get_role_context` returns `data.role_name` (not `data.role`). Any script or assertion checking `result['data']['role']` will raise a `KeyError`. Use `result['data']['role_name']` throughout.

### Key Gotcha: Container Restart Required When Switching Role Packs

Editing `config.yaml` on the host is not enough — the container only reads it at startup. Always run `docker compose restart cos` after changing `role_pack.path` and wait for the health check to pass before running validation tests.

## Dev Agent Record

### Agent Model Used
GPT-5 Codex

### Debug Log References
- `uv run pytest tests/ -q` → `142 passed, 1 skipped`

### Implementation Plan
- Update `docs/manual-testing.md` only, keeping the change set aligned to the story's operator-validation scope.
- Refresh Epic 3-era role context checks to match the Epic 4 role pack behavior and startup logs.
- Add the Epic 4 live validation section and extend the quick-run script with a direct `get_role_context` verification.

### Completion Notes List
- Updated [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) for Epic 4 role identity behavior, including the CHRO-focused capabilities summary and revised startup log sequence.
- Replaced the old stub `get_role_context` expectations with `role_name: "CHRO"` checks in both direct tool verification and Claude Code live-session guidance.
- Added Epic 4 operator validation coverage for CHRO retrieval tone, role-pack switching to Enterprise Architect, and reversal back to CHRO.
- Extended the Section 11 quick-script with a direct role context check after startup.
- Ran the regression suite: `uv run pytest tests/ -q` → `142 passed, 1 skipped`.

### File List
- `docs/manual-testing.md`
- `_bmad-output/implementation-artifacts/4-5-operator-validation-chro-role-active-and-switchable.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log
- 2026-04-29: Updated the Epic 4 manual testing guide for CHRO role validation and reversible role-pack switching; verified no test regressions.
