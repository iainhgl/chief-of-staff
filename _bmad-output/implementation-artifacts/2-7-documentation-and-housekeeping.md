# Story 2.7: Documentation & Housekeeping

Status: done

## Story

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the complete ingestion pipeline as built in Epic 2,
So that any operator can load documents into the knowledge base without assistance.

## Acceptance Criteria

1. **Given** `docs/setup.md` exists from Epic 1 (and was partially updated during Epic 2 stories),
   **When** it is reviewed for completeness,
   **Then** it includes: how to prepare documents for ingestion, how to run `cos ingest <path>` for a file and a folder, how to verify ingestion succeeded with `cos docs`, and what to do if a file is skipped or fails.

2. **Given** the root `README.md`,
   **When** it is updated,
   **Then** the current capabilities section reflects Epic 2 (not Epic 1): documents can be ingested via CLI and provenance can be inspected — no claims are made about retrieval or Q&A (those come in Epic 3).

3. **Given** any decisions or implementation details that deviated from `architecture.md` during Epic 2 stories,
   **When** `architecture.md` is reviewed,
   **Then** those deviations are documented accurately in a new "Epic 2 Implementation Notes" section — following the same format as the existing "Epic 1 Implementation Notes" section at the end of the file.

4. **Given** all Epic 2 documents (`docs/setup.md`, `README.md`, `architecture.md`),
   **When** they are reviewed together,
   **Then** command syntax, file paths, and capability descriptions are consistent across all three — no contradictions.

## Tasks / Subtasks

- [x] Task 1: Update `docs/setup.md` — add `cos docs` verification subsection (AC: #1, #4)
  - [x] Add a "Verify Ingestion" subsection under the "Ingest Documents" section (after "If a file fails")
  - [x] Show `docker compose run --rm cos uv run cos docs` with expected table output description
  - [x] Show `docker compose run --rm cos uv run cos docs --versions <id>` for version history
  - [x] Do NOT duplicate the existing ingest or "if a file fails" content — only add what's missing

- [x] Task 2: Update `README.md` — reflect Epic 2 capabilities (AC: #2, #4)
  - [x] Change "Current Capabilities (Epic 1)" heading to "Current Capabilities (Epic 2)"
  - [x] Replace the Epic 1 capabilities list with the accurate Epic 2 list (see Dev Notes for exact content)
  - [x] Remove the line "Document ingestion, knowledge retrieval, role pack loading, CLI commands..." — it is no longer accurate
  - [x] Keep project structure section and design principles unchanged

- [x] Task 3: Add "Epic 2 Implementation Notes" to `architecture.md` (AC: #3, #4)
  - [x] Append a new section at the end of `_bmad-output/planning-artifacts/architecture.md` following the same table format as "Epic 1 Implementation Notes"
  - [x] Document the four deviations listed in Dev Notes below
  - [x] Note any deferred issues from Epic 2 reviews

- [x] Task 4: Cross-check consistency (AC: #4)
  - [x] Verify `cos ingest` command syntax matches across setup.md, README.md, and manual-testing.md
  - [x] Verify no document claims retrieval or Q&A capabilities (Epic 3)
  - [x] Verify no document references `cos status`, `cos logs`, or `cos restart` as working commands (CLI stubs raise NotImplementedError)

## Dev Notes

### Audit First — Do Not Overwrite Good Content

Read every file before editing. Several sections already have accurate content from Epic 2 story implementations.

| File | Current state | What's missing |
|------|--------------|----------------|
| `docs/setup.md` | Has complete Ingest Documents section (file + folder + skip/fail) | No "Verify Ingestion" subsection showing `cos docs` |
| `README.md` | Still says "Current Capabilities (Epic 1)"; says "Document ingestion... not yet available" | Full Epic 2 capabilities update |
| `architecture.md` | Has "Epic 1 Implementation Notes" at end | No "Epic 2 Implementation Notes" section |

### Task 1: What to Add to `docs/setup.md`

The existing `setup.md` already covers:
- Ingest a single file (`docker compose run --rm cos uv run cos ingest /path/to/document.pdf`)
- Ingest a folder (with subdirectory recursion noted)
- If a file fails

What is missing: a subsection to verify the ingest succeeded.

Add this subsection **after** "If a file fails" and **before** "View Logs":

```markdown
## Verify Ingestion

After ingesting documents, confirm they are indexed using the `cos docs` command.

### List all ingested documents

```bash
docker compose run --rm cos uv run cos docs
```

Prints a table with one row per document:

| Column | Description |
|--------|-------------|
| `SOURCE PATH` | The in-container path where the file was ingested from |
| `INGESTED AT` | ISO 8601 timestamp of the most recent ingest |
| `VER` | Current version number (1 on first ingest; increments on re-ingest) |
| `CHUNKS` | Number of text chunks indexed for this document |

If no documents have been ingested yet: `No documents ingested yet. Run: cos ingest <path>`

### View version history for a document

```bash
docker compose run --rm cos uv run cos docs --versions <document-id>
```

Copy the document ID from the `cos docs` table output. Each row shows the version number, ingest timestamp, file hash, and extraction method.

### Machine-readable JSON output

```bash
docker compose run --rm cos uv run cos docs --json
```

Returns a JSON array. Each object has: `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`.
```

**Key gotcha to note:** The `source_path` stored in the database is the **in-container** absolute path. When using `docker compose run --rm -v "$(pwd)/test-docs:/test-docs" cos ...`, the stored path will be `/test-docs/sample-brief.md` (the container path), not the host path. This is expected behaviour.

### Task 2: What to Replace in `README.md`

Replace the entire "Current Capabilities" section:

**Remove this block:**
```markdown
## Current Capabilities (Epic 1)

This is the platform foundation. What is working today:

- **Three-container platform** (postgres/pgvector, Tika, cos) that starts with `docker compose up -d`
- **Config validation at startup** — human-readable errors for missing or invalid config values
- **Database schema applied automatically** — idempotent migrations run on every startup
- **MCP server** accessible via `docker compose exec` stdio transport (Claude Code and Claude Desktop)
- **`get_status` tool** — returns JSON with health of all three components (cos, postgres, tika) and a `ready` flag
- **`retrieve`, `get_role_context`, `list_documents`** — registered tools that return "Not yet implemented" error envelopes; will be wired in later epics

Document ingestion, knowledge retrieval, role pack loading, CLI commands, and connected sources (email, calendar) are not yet available. They are planned for later epics.
```

**Replace with this block:**
```markdown
## Current Capabilities (Epic 2)

What is working today:

- **Three-container platform** (postgres/pgvector, Tika, cos) that starts with `docker compose up -d`
- **Config validation at startup** — human-readable errors for missing or invalid config values
- **Database schema applied automatically** — idempotent migrations run on every startup
- **MCP server** accessible via `docker compose exec` stdio transport (Claude Code and Claude Desktop)
- **`get_status` tool** — returns JSON with health of all three components (cos, postgres, tika) and a `ready` flag
- **`cos ingest <path>`** — ingest a single file or folder of documents (PDF, .docx, .md, .txt); per-file progress and final summary printed
- **`cos docs`** — list all ingested documents with provenance metadata (source path, ingested timestamp, version, chunk count)
- **`cos docs --versions <id>`** — show version history for a specific document
- **`cos docs --json`** — machine-readable JSON output
- **Originals preserved** — every ingested file is stored byte-for-byte in `./data/originals/`; Markdown working copies in `./data/markdown/`
- **`retrieve`, `get_role_context`, `list_documents`** — registered MCP tools that return "Not yet implemented" error envelopes; will be wired in later epics

Knowledge retrieval, role pack loading, and connected sources (email, calendar) are not yet available. They are planned for later epics.
```

### Task 3: Epic 2 Implementation Notes for `architecture.md`

Append after the existing "Epic 1 Implementation Notes" section at the end of `_bmad-output/planning-artifacts/architecture.md`:

```markdown
## Epic 2 Implementation Notes

The following deviations from the architecture spec occurred during Epic 2. Future agents should treat these as the actual state of the codebase.

| # | Deviation | Detail |
|---|-----------|--------|
| 1 | **`ProvenanceService` added to `cos/services/`** | The architecture spec listed these services: `ingestion.py`, `retrieval.py`, `rolepack.py`, `output.py`, `health.py`. Story 2.5 added `src/cos/services/provenance.py` containing `ProvenanceService` — a read-only service that queries the `documents`, `document_versions`, and `chunks` tables to power `cos docs`. This follows the service layer pattern correctly and is the authoritative implementation for `list_documents` MCP tool (Story 3.4). |
| 2 | **Embedding uses `voyageai` library with `provider: "anthropic"` config** | The architecture spec said "default to a fast low-cost model (e.g. `text-embedding-3-small`)" implying an OpenAI-style provider. The implementation uses the `voyageai` Python package (Anthropic acquired Voyage AI). The `embedder.py` accepts `provider: "anthropic"` in config and routes to Voyage AI via `voyageai.AsyncClient`. Only this one provider path is implemented — the clean adapter pattern is deferred. Config `embedding.model` defaults to `voyage-3`. |
| 3 | **`docs/setup.md` updated incrementally during Epic 2** | The architecture spec placed documentation updates in the housekeeping story (2.7). In practice, `setup.md` was updated during Stories 2.4 and 2.5 as the ingestion and docs commands were implemented. The housekeeping story (2.7) added only the missing `cos docs` verification section. |
| 4 | **Deferred: Missing UNIQUE constraint on `documents.source_path`** | Identified in Story 2.3 review. Concurrent ingests of the same source path can silently create duplicate document records. Pre-existing; deferred to a future schema migration. Tracked but not yet fixed. |
| 5 | **Deferred: Chunks have no version-linking column** | Identified in Story 2.3 review. All chunk rows across all version records of a document are stored without a `document_version_id` FK — chunks from version 1 and version 2 of the same document are indistinguishable at the chunk level. Deferred as intentional Phase 1 design; the retrieval layer (Epic 3) returns the most recent chunks by default. |
```

### CLI Commands That Are Still Stubs

These CLI commands still raise `NotImplementedError` — do NOT document them as working in any doc:
- `cos status` → use `docker compose ps`
- `cos logs` → use `docker compose logs cos`
- `cos restart` → use the three-step procedure: `docker compose down` → `docker compose up -d` → `docker compose ps`

The only working `cos` CLI commands in Epic 2 are: `cos ingest`, `cos docs`.

### Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `docs/setup.md` | Modify — add section | Add "Verify Ingestion" subsection; do not touch existing content |
| `README.md` | Modify — replace capabilities block | Replace "Current Capabilities (Epic 1)" block only; keep all other sections |
| `_bmad-output/planning-artifacts/architecture.md` | Modify — append section | Append "Epic 2 Implementation Notes" after the "Epic 1 Implementation Notes" section |

Do NOT modify: any file in `src/`, `tests/`, `test-docs/`, `docker-compose.yml`, `config.yaml.example`, `docs/manual-testing.md`.

### References

- Current `docs/setup.md`: has Ingest Documents section added during Story 2.4 — read the file before editing to avoid duplication
- `README.md:14–16`: the Epic 1 capabilities block to replace
- `architecture.md`: "Epic 1 Implementation Notes" section starts at the final heading — append the Epic 2 section after it using the same table format
- `src/cos/services/provenance.py`: `ProvenanceService` — the service added outside the original spec
- `src/cos/ingestion/embedder.py`: embedding provider implementation — Voyage AI via `voyageai` library
- `config.yaml.example`: `embedding.provider: anthropic`, `embedding.model: voyage-3`
- Story 1.6 dev notes: reference for the pattern used in prior housekeeping story

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No debug issues encountered. All tasks were documentation-only edits.

### Completion Notes List

- Task 1: Added "Verify Ingestion" section to `docs/setup.md` after "If a file fails", covering `cos docs`, `cos docs --versions <id>`, `cos docs --json`, and the in-container path gotcha.
- Task 2: Replaced "Current Capabilities (Epic 1)" block in `README.md` with accurate Epic 2 block. Retained all other sections unchanged.
- Task 3: Appended "Epic 2 Implementation Notes" table to `_bmad-output/planning-artifacts/architecture.md` after the existing "Epic 1 Implementation Notes" section. Documented 5 deviations (ProvenanceService, Voyage AI embedder, incremental setup.md updates, and two deferred issues).
- Task 4: Cross-checked command syntax across setup.md, README.md, and manual-testing.md. No stub commands (`cos status`, `cos logs`, `cos restart`) documented as working. No retrieval/Q&A claims made.

### File List

- `docs/setup.md`
- `README.md`
- `_bmad-output/planning-artifacts/architecture.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/2-7-documentation-and-housekeeping.md`

## Change Log

- 2026-04-23: Added "Verify Ingestion" section to docs/setup.md covering cos docs, cos docs --versions, cos docs --json
- 2026-04-23: Updated README.md capabilities from Epic 1 to Epic 2
- 2026-04-23: Appended "Epic 2 Implementation Notes" to architecture.md (5 deviations documented)

### Review Findings

- [x] [Review][Patch] Missing `ID` column in `cos docs` table description — table lists 4 columns but code prints 5; `--versions` instructions say "copy the document ID" but the ID column is never described [`docs/setup.md`]
- [x] [Review][Patch] `--versions` output description claims "extraction method" column that does not exist in the code or DB schema [`docs/setup.md`]
- [x] [Review][Patch] `./data/originals/` and `./data/markdown/` in README appear host-relative but are in-container absolute paths (`/data/originals`, `/data/markdown`) [`README.md`]
- [x] [Review][Patch] Architecture deviation #1 heading says `cos/services/` but the correct path is `src/cos/services/` [`_bmad-output/planning-artifacts/architecture.md`]
- [x] [Review][Patch] Architecture deviation #2 note says `embedding.model` "defaults to `voyage-3`" but this is a `config.yaml.example` suggestion, not a code-level default — both `provider` and `model` are required fields with no defaults [`_bmad-output/planning-artifacts/architecture.md`]
- [x] [Review][Patch] Deviations #4 and #5 say "Tracked but not yet fixed" with no reference to where they are tracked [`_bmad-output/planning-artifacts/architecture.md`]
- [x] [Review][Patch] `setup.md` in-container path Note uses test fixture filename `sample-brief.md`; replace with a neutral placeholder [`docs/setup.md`]
- [x] [Review][Defer] `--versions` + `--json` combination works but is undocumented [`src/cos/cli.py`] — deferred, pre-existing
- [x] [Review][Defer] Invalid UUID passed to `--versions` silently returns empty result instead of a clear error [`src/cos/services/provenance.py`] — deferred, pre-existing code behavior
- [x] [Review][Defer] "What to do if a file is skipped" guidance in setup.md lacks actionable next steps [`docs/setup.md`] — deferred, pre-existing content from Story 2.4
- [x] [Review][Defer] `provider: "anthropic"` config key routes to `voyageai.AsyncClient` — naming collision risk not flagged in deviation #2 as a future hazard [`_bmad-output/planning-artifacts/architecture.md`] — deferred, acknowledged in deviation note
