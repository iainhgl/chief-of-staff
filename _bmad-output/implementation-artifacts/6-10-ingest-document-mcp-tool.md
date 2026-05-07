# Story 6.10: `ingest_document` MCP Tool

Status: done

## Story

As a user,
I want to ingest notes or short documents directly through MCP,
So that synthetic note capture also uses the same canonical identity and provenance model.

## Acceptance Criteria

1. **Given** a connected MCP client calls `ingest_document` with content and optional metadata,
   **When** the tool executes successfully,
   **Then** it routes the request through the same ingest decision engine as CLI and connector ingestion and returns the standard MCP response envelope.

2. **Given** an MCP-ingested note duplicates existing bytes exactly,
   **When** the tool completes,
   **Then** it returns a successful response that explains the content was linked to existing canonical content rather than duplicated.

3. **Given** an MCP-ingested note is semantically very similar but not byte-identical to existing content,
   **When** the near-duplicate layer runs,
   **Then** the tool returns a warning alongside the successful ingest outcome without blocking capture.

4. **Given** the tool receives invalid input such as empty content,
   **When** validation runs,
   **Then** it returns a structured error envelope rather than an unhandled exception.

## Tasks / Subtasks

- [x] Task 1: Finish the synthetic-note ingestion seam in [src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) so MCP note capture reuses the canonical pipeline (AC: #1, #2, #4)
  - [x] Replace the current `ingest_note()` stub with a real async implementation that accepts `text: str` plus optional metadata
  - [x] Validate note content before any file or DB work; reject empty or whitespace-only content with a service-level validation error
  - [x] Materialise note content as a UTF-8 Markdown file under a deterministic MCP staging directory on `/data`, not under container-local `/tmp`
  - [x] Call [run_pipeline_from_source(...)](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) rather than creating a second note-only ingest path
  - [x] Use a dedicated synthetic source type such as `mcp_note`
  - [x] Support a stable client-supplied external identifier in metadata when present so retries can resolve to the existing source/unchanged path; otherwise generate a new synthetic locator for one-off note capture
  - [x] Keep [ingest_file()](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) behaviour unchanged for CLI file ingest

- [x] Task 2: Define the MCP note metadata and provenance contract without turning synthetic provenance into canonical identity (AC: #1, #2, #4)
  - [x] Add a small optional config block in [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) and [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) for MCP note ingest defaults, including:
    - [x] `staging_dir: Path = Path("/data/connector-staging/mcp")`
    - [x] `near_duplicate_threshold` as the warning cutoff for semantic similarity
  - [x] Keep the new config optional so existing Epic 1-5 and Epic 6 connector configs still load unchanged
  - [x] Define a minimal, validated metadata contract for the tool, using metadata only where it materially affects ingest behaviour:
    - [x] optional `title` for a human-readable alias
    - [x] optional `external_id` for stable retry/idempotency behaviour
    - [x] optional `client`/origin label for provenance-friendly locator construction
  - [x] Build `source_alias` from human-readable note metadata when available, with a deterministic fallback ending in `.md`
  - [x] Build `source_locator` from synthetic source metadata, not from the content hash and not from a raw filename alone
  - [x] Do not invent schema changes just to persist arbitrary note metadata if the current canonical model does not need it; only thread through what is necessary for provenance and tool output

- [x] Task 3: Add a warning-only semantic near-duplicate check that fits the current repo structure (AC: #3)
  - [x] Reuse the existing embedding stack and pgvector search path rather than adding a second embedding provider or custom ML dependency
  - [x] Implement a helper in the existing ingestion/store/retrieval seams that can find the nearest previously indexed chunk or document for newly ingested MCP note content
  - [x] Run the near-duplicate check only after exact-byte dedupe and canonical identity resolution, so exact duplicates still take the normal `unchanged` or `new_source_known_content` path first
  - [x] Make the near-duplicate result warning-only: successful ingest still completes and indexes normally
  - [x] Return a concise warning payload that includes the matched `source_alias` and similarity score or score band
  - [x] Avoid warning on the just-created record itself; compare against previously stored content only

- [x] Task 4: Add the `ingest_document` MCP tool in [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py) using the repo’s current MCP tool conventions (AC: #1, #2, #3, #4)
  - [x] Register a new `@mcp.tool()` named `ingest_document`
  - [x] Accept `content: str` and optional `metadata: dict[str, object] | None = None`
  - [x] Follow the current repo pattern for non-retrieval tools: instantiate the needed service from config inside the tool, return a JSON envelope string, and do not introduce a new direct dependency from `mcp_server/` to lower-level modules
  - [x] Return success as the standard envelope shape:
    - [x] `status: "ok"`
    - [x] `data.document_id`
    - [x] `data.chunk_count`
    - [x] `data.outcome`
    - [x] `data.message`
    - [x] `data.source_alias`
    - [x] `data.source_locator`
    - [x] `data.warning` when the semantic near-duplicate layer fires
    - [x] `citations: []`
  - [x] Return invalid-input and service failures as structured error envelopes, never as uncaught exceptions or protocol-level failures
  - [x] Keep response-copying through [OutputService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py) aligned with the repo’s current non-retrieval tool behaviour; do not broaden OutputRouter semantics in this story

- [x] Task 5: Add automated coverage for service behaviour, near-duplicate warnings, and MCP envelopes (AC: #1, #2, #3, #4)
  - [x] Extend [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py) for note ingest success, exact-byte duplicate behaviour, invalid empty content, and stable-id retry semantics
  - [x] Extend [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py) for:
    - [x] `ingest_document` success envelope
    - [x] duplicate-content success message
    - [x] warning-bearing success response for a semantic near-duplicate
    - [x] empty-content structured error
    - [x] server-not-initialized error path
  - [x] Extend [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py) if a new optional MCP ingest config block is introduced
  - [x] Add or extend lower-level tests around the near-duplicate helper so the threshold and warning behaviour are deterministic and testable
  - [x] Keep all tests offline and local: no live MCP client, no external APIs, and no network dependency

### Review Findings

- [x] [Review][Patch] Validate `metadata` shape and field types before dereferencing `.get()` or coercing arbitrary objects to strings [src/cos/services/ingestion.py:62]
- [x] [Review][Patch] Provide non-empty fallbacks after slug sanitisation so punctuation-only `title` / `client` / `external_id` values cannot collapse into `.md`, `mcp_note:///...`, or shared staging filenames [src/cos/services/ingestion.py:68]

## Dev Notes

### Story Positioning

Story 6.10 is the first **synthetic note capture** story in the repo.

- Story 6.7 established the shared queue/worker path for connectors, but this MCP tool needs a synchronous result because the caller expects an immediate tool response
- Stories 6.8 and 6.9 established the connected-source provenance pattern and the canonical identity guardrails this story must reuse
- This story is the bridge between file/connector ingest and future message-based note capture in Epic 7

This story is not Telegram note capture, not web search, and not a documentation sweep.

### Product and Architecture Requirements Driving This Story

- FR5 / FR6: provenance and versioning still apply to synthetic note sources
- FR8: semantic near-duplicate detection is warning-only and must not silently suppress user capture
- FR31: configuration stays human-editable and optional additions must not break existing operator configs
- NFR3: this is an MCP non-retrieval tool, so it should stay lightweight and avoid queue/scheduler indirection
- NFR10 / NFR11: note-ingest failures must not destabilise the rest of the MCP server path

Architecture guardrails already locked in [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md):

- synthetic note capture must resolve the same four ingest outcomes as CLI and connector ingest
- canonical identity is separate from provenance; synthetic locators must not become canonical identity by accident
- `mcp_server/` should call service-layer seams, not lower-level ingestion/store modules directly
- every MCP tool must return the standard response envelope

### Current Code Seams To Reuse

#### Ingestion pipeline and identity engine

- [src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) already owns the user-facing ingestion seam and contains the current `ingest_note()` stub
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) already exposes [run_pipeline_from_source(...)](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py), which is the correct shared entry point for source-aware ingest
- [src/cos/ingestion/identity.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/identity.py) already locks the four outcomes:
  - `new_content`
  - `changed_content`
  - `new_source_known_content`
  - `unchanged`

Do not create a second ingest implementation for MCP notes.

#### MCP tool pattern already in the repo

- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py) currently defines `get_status`, `retrieve`, `get_role_context`, and `list_documents`
- Non-retrieval tools currently return JSON envelope strings directly and instantiate lightweight services from config where needed
- [src/cos/mcp_server/server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py) already imports `tools.py` at startup so decorated tools are registered automatically

Match this existing tool style unless there is a compelling reason to refactor multiple MCP tools together.

#### Retrieval and vector-search seam for semantic similarity

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py) already embeds a query and runs pgvector-backed similarity search
- The repo already has the ingredients for semantic comparison: embeddings, pgvector registration, and vector-distance queries
- There is no shipped semantic near-duplicate warning path yet, so this story likely introduces the first user-facing warning-only integration point for FR8

### Previous Story Intelligence

- Story 6.7 proved the value of reusing the existing canonical pipeline rather than building connector-specific ingest logic
- Story 6.8 review feedback matters here too:
  - operator-facing failures should be explicit and recovery-friendly
  - deterministic fallback identity matters whenever external/human names are missing
  - exact-byte dedupe should be allowed to do the heavy lifting before higher-level warning logic runs
- Story 6.9 kept connector-specific shaping in a narrow seam; the same restraint applies here for MCP note shaping

### Critical Implementation Guardrails

1. **Do not route this MCP tool through the jobs queue unless it can still return the final ingest outcome synchronously.**
   The acceptance criteria expect the tool itself to report success, duplicate linking, and warnings in one response.

2. **Do not use a random source locator unconditionally.**
   If the caller provides a stable external identifier, use it so client retries can resolve to the existing source/unchanged path instead of always looking like a new source.

3. **Do not use content hash, filename, or note title as the effective canonical identity.**
   Synthetic source locators are provenance only. Canonical identity still comes from the existing blob/version model.

4. **Validate note input before staging a file or opening a DB connection.**
   Empty and whitespace-only content should fail fast with a structured error envelope.

5. **Keep semantic near-duplicate detection warning-only.**
   Successful note capture should not be blocked just because content is similar to something already indexed.

6. **Run the semantic warning after exact-byte identity resolution.**
   Exact duplicates should still follow the canonical `unchanged` or `new_source_known_content` path and should not be re-described as semantic duplicates.

7. **Do not silently promise arbitrary metadata persistence if the schema does not support it.**
   Use metadata for alias/locator derivation and tool output where needed, but do not invent broad new schema work here.

8. **Stage under `/data`, not `/tmp`.**
   Even though this tool is synchronous today, the shared storage pattern should stay compatible with future message-channel ingest paths.

9. **Keep scope out of Epic 7.**
   No Telegram bot implementation, no scheduling, no outbound confirmations beyond the MCP tool response, and no broad doc consolidation in this story.

### Suggested File Touchpoints

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py)
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py)
- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py) or a closely related helper seam
- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
- [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py)
- [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)
- [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py)

### Testing Strategy

- Use a real test database and the existing embedder patching pattern already used by ingestion tests
- Prove exact-byte duplicate behaviour across source types, for example:
  - ingest a local file
  - ingest the same bytes through `ingest_note`
  - assert the second path reports canonical reuse rather than duplicate reprocessing
- Add one retry/idempotency-style test where an MCP note with the same stable external identifier and unchanged content resolves to `unchanged`
- Add one semantic-warning test with controlled embeddings or a patched helper so the threshold behaviour is deterministic
- Keep MCP tool tests focused on envelope shape and user-visible messaging, not internal implementation details

### Non-Goals

- No Telegram bot implementation
- No queue-first note capture path
- No broad documentation rewrite
- No new ingestion pipeline separate from the current canonical path
- No schema expansion purely to persist arbitrary note metadata
- No web-search MCP tool work

### Source References

- [Epic 6 in epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for canonical identity, synthetic note capture, and MCP tools](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD MCP tool and note-capture requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Sprint change proposal note about synthetic source references](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-05.md)
- [Previous story: 6.7 jobs queue and worker](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-7-jobs-queue-and-background-ingestion-worker.md)
- [Previous story: 6.8 Gmail connector](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-8-gmail-connector.md)
- [Previous story: 6.9 Google Calendar connector](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-9-google-calendar-connector.md)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was clean.

### Completion Notes List

- Implemented `ingest_note()` in `IngestService` replacing the prior stub. Validates empty/whitespace input, materialises note to a staged UTF-8 Markdown file under `mcp_note.staging_dir`, calls `run_pipeline_from_source()` with `source_type="mcp_note"`, and threads `source_alias`/`source_locator`/`warning` through `IngestResult`.
- Added `McpNoteIngestConfig` to `config.py` with `staging_dir` and `near_duplicate_threshold` fields. Config is fully optional — all existing operator configs load unchanged.
- Added `find_near_duplicate()` helper in `src/cos/retrieval/near_duplicate.py` using the same embedding stack and pgvector as the retrieval path. Returns `None` immediately when no embedding API key is set; excludes the just-created document from comparison to prevent self-match.
- Added `ingest_document` MCP tool following existing tool conventions: config-instantiated service, JSON envelope response, structured error envelopes for invalid input and exceptions.
- Extended test coverage: 8 new ingestion service tests, 6 new MCP tool tests, 5 new near-duplicate helper tests, 6 new config tests.
- All 370 tests pass; ruff lint clean.

### File List

- `src/cos/config.py` — added `McpNoteIngestConfig`; added `mcp_note` field to `CosConfig`
- `config.yaml.example` — added commented-out `mcp_note:` block
- `src/cos/services/ingestion.py` — implemented `ingest_note()`; extended `IngestResult` with `source_alias`, `source_locator`, `warning` fields
- `src/cos/retrieval/near_duplicate.py` — new file: `find_near_duplicate()` helper
- `src/cos/mcp_server/tools.py` — added `ingest_document` MCP tool
- `tests/services/conftest.py` — extended `mock_embed` to also patch `cos.retrieval.near_duplicate.embed`
- `tests/services/test_ingestion_service.py` — added 8 note ingest tests
- `tests/mcp_server/test_tools.py` — added 6 `ingest_document` tool tests
- `tests/retrieval/test_near_duplicate.py` — new file: 5 near-duplicate helper tests
- `tests/test_config.py` — added 6 `McpNoteIngestConfig` tests
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status updated to `review`

## Change Log

- 2026-05-07: Implemented story 6.10 — `ingest_document` MCP tool with synthetic note capture via canonical pipeline, `McpNoteIngestConfig`, `find_near_duplicate()` helper, and full test coverage (370 passing, 0 regressions).
