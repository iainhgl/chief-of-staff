# Story 3.6: Documentation & Housekeeping

Status: done

## Story

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the working retrieval and Q&A pipeline as built in Epic 3,
So that any operator knows how to query the knowledge base and understand what grounded, cited answers look like.

## Acceptance Criteria

1. **Given** `docs/setup.md` is updated for Epic 3, **When** it is reviewed, **Then** it includes: how to configure Claude Desktop or Claude Code to connect to the CoS MCP server, how to use the `retrieve` tool to ask questions, how to interpret citations in the response, and how to use `list_documents` to browse the knowledge base.

2. **Given** the root `README.md` is updated, **When** it is reviewed, **Then** the current capabilities section reflects that questions can now be answered with citations via Claude Desktop or Claude Code — and notes that role-specific tone and retrieval weighting arrive in Epic 4.

3. **Given** any deviations from `architecture.md` that occurred during Epic 3 implementation (e.g. changes to the synthesis prompt structure, OutputRouter contract, or CitedResponse shape), **When** `architecture.md` is reviewed, **Then** the actual implementation is accurately documented — no spec fiction.

4. **Given** all Epic 3 documents are reviewed together, **When** cross-checked for consistency, **Then** MCP tool names, response envelope shapes, and capability descriptions match across `docs/setup.md`, `README.md`, and `architecture.md`.

## Tasks / Subtasks

- [x] Task 1: Add "Query the Knowledge Base" section to `docs/setup.md` (AC: #1)
  - [x] Add section after "Verify Ingestion" — explain how to ask questions via `retrieve`
  - [x] Document citation structure (`source_path`, `chunk_index`, `score`) in plain language
  - [x] Explain the no-results case ("No relevant content found…")
  - [x] Add `list_documents` usage (call from Claude, compare with `cos docs --json`)
  - [x] Update `docs/structure` in `README.md` project structure section if needed (new doc sections don't need listing but ensure `manual-testing.md` is referenced)

- [x] Task 2: Update `README.md` current capabilities section (AC: #2)
  - [x] Change heading from `## Current Capabilities (Epic 2)` to `## Current Capabilities (Epic 3)`
  - [x] Replace the `retrieve`, `get_role_context`, `list_documents` stub bullet with working-tool descriptions
  - [x] Replace "Knowledge retrieval…not yet available" footer note with Epic 3 reality and Epic 4 preview
  - [x] Update `docs/` project structure entry to reference `manual-testing.md` alongside `setup.md`

- [x] Task 3: Add Epic 3 implementation notes to `architecture.md` (AC: #3, #4)
  - [x] Add `## Epic 3 Implementation Notes` table after the Epic 2 notes section
  - [x] Document the three deviations identified during Epic 3 (see Dev Notes)
  - [x] Verify component names, envelope shapes, and tool descriptions are consistent with the rest of the file

### Review Findings

- [x] [Review][Decision] "Every retrieve response includes citations" phrasing is misleading — patched to "Every successful `retrieve` response includes a `citations` field. When relevant content is found, each citation has:" [docs/setup.md]
- [x] [Review][Patch] `setup.md` title still reads "CoS Platform Setup" — updated to "CoS Platform — Setup, Operations, and Querying Guide" [docs/setup.md:1]
- [x] [Review][Patch] Browse section code block could be mistaken for a terminal command — changed "To see all ingested documents from a Claude session:" to "type this prompt into your Claude session:" [docs/setup.md]
- [x] [Review][Patch] `architecture.md` Epic 3 note 2 states `OutputRouter.send()` sync rule as a structural invariant — qualified to "current implementation: with only the local channel handler implemented" and added forward note about async handlers [_bmad-output/planning-artifacts/architecture.md]
- [x] [Review][Patch] README "Get Started" description of `setup.md` omits querying — added "querying the knowledge base" to the list [README.md]
- [x] [Review][Defer] `cli.py` "stub commands" comment is stale — `ingest` and `docs` are fully working; only `status`/`logs`/`restart` remain stubs; pre-existing, not introduced by this diff [README.md] — deferred, pre-existing
- [x] [Review][Defer] `manual-testing.md` `--tail=5` grep is fragile — may miss OutputRouter log line if other logs scroll past; pre-existing, explicitly out of scope for this story [docs/manual-testing.md] — deferred, pre-existing
- [x] [Review][Defer] `retrieve` error cases undocumented in `setup.md` — server-not-initialized, retrieval-failed, synthesis-failed envelopes not described; valid coverage gap, beyond story 3.6 AC scope [docs/setup.md] — deferred, pre-existing

## Dev Notes

### What This Story Is

Story 3.6 is the Epic 3 documentation and housekeeping story. **There are no code changes.** All changes are limited to:

| File | Action |
|------|--------|
| `docs/setup.md` | Add "Query the Knowledge Base" section |
| `README.md` | Update current capabilities from Epic 2 to Epic 3 |
| `_bmad-output/planning-artifacts/architecture.md` | Add Epic 3 implementation notes |

Do NOT modify: any file in `src/`, `tests/`, `test-docs/`, `docker-compose.yml`, `config.yaml.example`, or `docs/manual-testing.md`.

`docs/manual-testing.md` was fully updated in Story 3.5. Do not touch it.

### Current State of docs/setup.md

`docs/setup.md` was last updated during Epic 2. It already contains:
- Prerequisites, clone, first-time configuration
- Start/stop platform commands
- MCP server connection instructions (Claude Code and Claude Desktop) — **already present, do not duplicate**
- Ingest documents section (single file and folder)
- Verify ingestion section (`cos docs`)
- View logs section

**Missing (your deliverable):** A "Query the Knowledge Base" section that explains how to use `retrieve` and `list_documents` once documents are ingested.

### Exact setup.md Addition

Add the following section after the existing "Verify Ingestion" section and before "View Logs":

```markdown
## Query the Knowledge Base

Once documents are ingested, ask questions using the `retrieve` tool from any connected MCP client (Claude Code or Claude Desktop).

### Ask a question

Open a Claude session and ask any question about your documents:

```
What frameworks do I have for workforce segmentation?
```

Claude calls `retrieve`, searches the knowledge base using hybrid keyword and semantic search, synthesises a grounded answer, and returns it with citations.

### Understanding citations

Every `retrieve` response includes citations. Each citation has:

| Field | Description |
|-------|-------------|
| `source_path` | In-container path of the document the answer draws from |
| `chunk_index` | Which chunk within that document was used |
| `score` | Relevance score — higher is a closer match |

The `source_path` values match what `cos docs` shows in the `SOURCE PATH` column.

If no relevant content exists in the knowledge base, the answer will say "No relevant content found in the knowledge base." — not an error. `citations` will be an empty list.

### Browse the knowledge base

To see all ingested documents from a Claude session:

```
Call list_documents and show me the raw JSON response.
```

This returns the same documents as `cos docs --json`, with `id`, `source_path`, `ingested_at`, `current_version`, and `chunk_count` for each document.
```

### Exact README.md Changes

**Change 1 — heading:**
```
## Current Capabilities (Epic 2)
```
→
```
## Current Capabilities (Epic 3)
```

**Change 2 — stub tools bullet (find and replace the entire bullet):**

Current:
```
- **`retrieve`, `get_role_context`, `list_documents`** — registered MCP tools that return "Not yet implemented" error envelopes; will be wired in later epics
```

Replace with:
```
- **`retrieve`** — ask any question about ingested documents; returns a synthesised answer grounded in source material with citations (`source_path`, `chunk_index`, `score` per source); answers the "no content" case gracefully without fabrication
- **`list_documents`** — returns all ingested documents with `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`; matches `cos docs --json` output
- **`get_role_context`** — returns stub: `"default — role pack not yet configured"`; role-specific tone and retrieval weighting arrive in Epic 4
- **`get_status`** — unchanged from Epic 1; returns health of all three components and a `ready` flag
```

**Change 3 — closing note (find and replace):**

Current:
```
Knowledge retrieval, role pack loading, and connected sources (email, calendar) are not yet available. They are planned for later epics.
```

Replace with:
```
Knowledge retrieval and Q&A with citations are now working. Role pack loading (tone, retrieval weighting, stakeholder context) is planned for Epic 4. Connected sources (email, calendar) are planned for Epic 6.
```

**Change 4 — project structure `docs/` entry (find and replace):**

Current:
```
│   └── setup.md              # setup and operations guide
```

Replace with:
```
│   ├── setup.md              # setup, operations, and querying guide
│   └── manual-testing.md    # end-to-end operator validation tests
```

### Epic 3 Implementation Notes for architecture.md

Add the following table after the Epic 2 Implementation Notes section (after the last row of the Epic 2 table):

```markdown
## Epic 3 Implementation Notes

The following deviations from the architecture spec occurred during Epic 3. Future agents should treat these as the actual state of the codebase.

| # | Deviation | Detail |
|---|-----------|--------|
| 1 | **`OutputRouter` log component is `"output"` not `"output_router"`** | Story 3.2 AC specified `component: "output_router"` in the structured error log. The implementation logs `"component": "output"`. This is consistent with the valid component names in the architecture spec (`component` is one of: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`, `output`). Manual testing and code review (Story 3.5) confirmed and corrected the expected value. Use `"output"` when searching logs for OutputRouter errors. |
| 2 | **`OutputRouter.send()` is a synchronous method** | The architecture async discipline says "All DB calls and external I/O must be async." `OutputRouter.send()` is defined as `def send(self, channel, content) -> None` (synchronous). This is correct — `OutputRouter` does not perform DB calls or external I/O; it dispatches to a channel handler that is itself synchronous for the `local` channel. The method does not need `async`. Do not add `await` when calling `router.send()`. |
| 3 | **`retrieve` tool response has `citations` at both top-level and inside `data`** | The standard response envelope is `{"status": "ok", "data": {...}, "citations": [...]}`. For the `retrieve` tool, the same citations list appears at both levels: `data.citations` and the top-level `citations`. This is the consistent envelope pattern — all four tools return a top-level `citations` field (empty list for tools without citations). For `retrieve`, the citations are surfaced at both levels so consumers can use whichever is more convenient. See `src/cos/mcp_server/tools.py:86-92`. |
```

### Key Architecture References

- `OutputRouter`: `src/cos/output/router.py` — `send(channel: str, content: str) -> None` (synchronous)
- `retrieve` tool: `src/cos/mcp_server/tools.py:37-92`
- `list_documents` tool: `src/cos/mcp_server/tools.py:107-147`
- MCP tool envelope: `{"status": "ok|error", "data": {...}, "citations": [...]}`
- Citation shape: `{"source_path": str, "chunk_index": int, "score": float}` — from `src/cos/retrieval/citations.py`
- No-results response: `{"status": "ok", "data": {"answer": "No relevant content found in the knowledge base.", "citations": []}, "citations": []}`

### Consistency Checklist (run before marking done)

Cross-check these values are identical across all three files after making changes:

| Value | Correct form |
|-------|-------------|
| Tool name | `retrieve`, `list_documents`, `get_status`, `get_role_context` |
| Retrieve envelope | `{"status": "ok", "data": {"answer": "...", "citations": [...]}, "citations": [...]}` |
| List documents fields | `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count` |
| Role context stub | `"default — role pack not yet configured"` |
| OutputRouter log component | `"output"` |
| No-results answer | `"No relevant content found in the knowledge base."` |

### Previous Story Context (Story 3.5 completion)

Story 3.5 (operator validation) is done. The following is confirmed working and does not need to be validated again:
- All four MCP tools return valid envelopes
- `docs/manual-testing.md` is fully updated through Epic 3 — do not touch it
- The `_startup_sequence` must be called before tools can be used directly (established pattern)
- Source paths in citations and `list_documents` are container paths (e.g. `/test-docs/sample-brief.md`)

## Dev Agent Record

### Agent Model Used

gpt-5

### Completion Notes List

- Updated `docs/setup.md` with a new "Query the Knowledge Base" section covering `retrieve`, citation interpretation, no-results behaviour, and `list_documents` usage.
- Updated `README.md` to reflect Epic 3 capabilities, including working MCP retrieval/Q&A behaviour and the `docs/manual-testing.md` project structure entry.
- Added `Epic 3 Implementation Notes` to `_bmad-output/planning-artifacts/architecture.md` and aligned the documented MCP envelope shapes with the running implementation.
- Cross-checked wording across `docs/setup.md`, `README.md`, and `architecture.md` so tool names and response shapes are consistent.
- Validation: `uv run pytest` passed (`116 passed, 1 skipped`).
- Validation: `uv run ruff check` reports pre-existing lint failures in unrelated files under `.claude/`, `src/`, and `tests/`; no new lint issues were introduced by this documentation-only story.

### File List

- `docs/setup.md`
- `README.md`
- `_bmad-output/planning-artifacts/architecture.md`
- `_bmad-output/implementation-artifacts/3-6-documentation-and-housekeeping.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-04-28: Updated Epic 3 operator documentation in `docs/setup.md`, refreshed `README.md` capability notes for grounded Q&A, and added Epic 3 implementation notes to `architecture.md`.
