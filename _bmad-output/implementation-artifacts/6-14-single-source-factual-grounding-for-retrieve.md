# Story 6.14: Single-Source Factual Grounding for `retrieve`

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want direct factual questions to stay grounded in the source actually being asked about,
So that the answer layer does not blend facts across similar but distinct records.

## Acceptance Criteria

1. **Given** a direct factual query about one apparent source item,
   **When** the retrieval service prepares synthesis context,
   **Then** it defaults to evidence from the best matching single source locator or document version rather than mixing multiple unrelated source items.

2. **Given** a query explicitly asks for synthesis, comparison, or aggregation,
   **When** retrieval runs,
   **Then** multi-source evidence remains allowed.

3. **Given** a single-source grounded answer is returned,
   **When** citations are inspected,
   **Then** they point to the same source lineage that supports the factual claim.

4. **Given** a mixed-source corpus containing semantically similar Gmail, local-file, or MCP-note records,
   **When** a factual lookup is tested,
   **Then** the answer does not import unsupported facts from sibling records.

## Tasks / Subtasks

- [x] Task 1: Add a deterministic grounding decision before synthesis context is built (AC: #1, #2, #4)
  - [x] Introduce or extend a small in-process helper that decides whether a query should follow the default single-source grounding path or the existing multi-source synthesis path
  - [x] Treat explicit compare/synthesis/aggregation language as the narrow opt-out that keeps multi-source evidence enabled; direct factual lookups should remain single-source by default
  - [x] Keep the decision deterministic and local to the retrieval layer; do not add a second LLM call, a classifier service, or extra database round-trips just to choose the grounding mode

- [x] Task 2: Narrow direct factual retrieval to one source lineage using the already-filtered evidence set (AC: #1, #3, #4)
  - [x] Start from the Story 6.13 result set after thresholding and per-source pruning, not from the raw pre-filter ranking
  - [x] Choose the best matching lineage from the highest-ranked surviving evidence, preferring `document_version_id` when present and falling back to `source_locator` for legacy/backfilled records
  - [x] Build the synthesis context and returned citations only from the chosen lineage so sibling Gmail, local-file, or MCP-note records cannot contribute unsupported facts to a direct factual answer

- [x] Task 3: Preserve the existing multi-source path and MCP contract (AC: #2, #3)
  - [x] Queries that explicitly ask for comparison, summarisation across sources, or aggregation should continue to use multi-source evidence
  - [x] Keep the `retrieve` response envelope unchanged: top-level `citations` and `data.citations` stay aligned, and each citation still exposes `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, and `score`
  - [x] Preserve the current degraded-path behavior: if synthesis fails, return the existing synthesis error; if no evidence survives the grounding path, return the normal no-relevant-content answer with empty citations

- [x] Task 4: Expand automated coverage for grounding mode, lineage narrowing, and citation consistency (AC: #1, #2, #3, #4)
  - [x] Add service-level tests proving direct factual queries collapse to one lineage while explicit compare/synthesis prompts still allow multi-source evidence
  - [x] Add regression coverage using semantically similar Gmail/local/MCP-style records so the answer path cannot blend sibling facts into one claim
  - [x] Add MCP tests proving the serialized citations match the chosen lineage exactly at both `data.citations` and top level
  - [x] Cover the legacy/backfill fallback case where `document_version_id` is empty and `source_locator` is the only safe lineage key

## Dev Notes

### What This Story Is

Story 6.14 is the second retrieval-trust hardening story that follows the Epic 6 UAT findings. Story 6.13 cleaned the evidence set by filtering low-signal results and pruning citation noise. Story 6.14 closes the remaining trust gap: even with cleaner evidence, direct factual lookups can still blend details across several semantically similar records unless the answer path narrows itself to one source lineage by default.

This story is intentionally narrower than a general retrieval redesign. The goal is not to replace hybrid search, introduce a second ranking stage, or add LLM-based evidence arbitration. The goal is to keep direct factual answers tied to one source lineage unless the user explicitly asks for synthesis across sources.

### Why This Story Exists Now

The Epic 6 UAT finding was specific: the system answered a seeded Gmail retrieval question with the correct Gmail body marker but also pulled in an attachment fact from a different source record. That means Story 6.13's thresholding and pruning are necessary but not sufficient. The remaining gap is answer grounding, not just retrieval cleanliness.

Story 6.14 should therefore build on the current 6.13 behavior rather than reopen it:

1. low-signal results are already filtered before synthesis
2. citations are already pruned to the bounded evidence set
3. the remaining defect is that direct factual prompts can still mix facts across several strong-but-similar source records

### Previous Story Intelligence

- Story 6.13 already added `retrieval.min_score` and `retrieval.max_chunks_per_source`, and `hybrid_search(...)` now returns the filtered/pruned evidence set that actually feeds synthesis. This story must use that bounded set as its input rather than inventing a second raw retrieval path. [Source: [6-13-retrieval-result-thresholding-and-citation-pruning.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md)]
- Story 6.12 aligned the public retrieval contract around `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, and `score`. Story 6.14 must preserve those fields and their meanings. [Source: [6-12-documentation-and-housekeeping.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-12-documentation-and-housekeeping.md)]
- Story 6.11 produced the live Epic 6 UAT artifact and is the source of the concrete mixed-source grounding failure that motivated this story. Use that failure mode as the behavioral regression target. [Source: [6-11-operator-validation-connected-sources-live.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-11-operator-validation-connected-sources-live.md), [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)]
- Story 6.10 introduced `ingest_document` and stable external IDs for MCP notes, which means the corpus can now contain many semantically similar records from local files, Gmail, Calendar artifacts, and MCP notes. This story must handle that mixed-source reality without special-casing one ingest channel. [Source: [6-10-ingest-document-mcp-tool.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-10-ingest-document-mcp-tool.md)]

### Git Intelligence

- Recent commit history shows retrieval work landing as tight, story-scoped changes followed by review-fix patches. Keep this story similarly narrow and well-tested so review can stay focused on grounding semantics rather than broad refactors.
- Most recent relevant commit titles:
  - `Merge remote-tracking branch 'origin/main' into story/6-13-retrieval-result-thresholding-and-citation-pruning`
  - `Fix story 6.13 review findings`
  - `Implement story 6.13 retrieval result thresholding and citation pruning`

### Product And Architecture Guardrails

1. **Preserve the MCP retrieve contract.**
   The success envelope remains `{"status": "ok", "data": {...}, "citations": [...]}`. Story 6.14 changes which evidence is allowed to support a direct factual answer, not the shape of the tool response. [Source: [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

2. **Ground on lineage, not on alias text alone.**
   `source_alias` is operator-facing and human-readable; it is not the safest uniqueness key. Prefer `document_version_id` when it exists, and use `source_locator` as the fallback for legacy/backfilled cases. Returned citations for a grounded factual answer should all share that chosen lineage. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

3. **Build on Story 6.13's bounded evidence set.**
   Thresholding and per-source pruning are already implemented. Do not bypass them, rerun retrieval per source, or introduce a separate "grounding search" query unless a very small helper is unavoidable. The default path should remain: hybrid search -> filtered/pruned evidence -> lineage narrowing (when needed) -> synthesis. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]

4. **Keep the multi-source opt-out explicit and narrow.**
   This story should default plain factual lookups to single-source grounding. Only explicit synthesis/comparison/aggregation prompts should keep the multi-source path. Do not make the opt-out so broad that ordinary factual questions continue blending sources by accident.

5. **Do not add another LLM pass.**
   Grounding mode selection and lineage narrowing should be deterministic and in-process. A second model call for intent classification or citation selection would add cost, latency, and failure modes without being required by the story. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

6. **Preserve current fallback behavior.**
   If no evidence survives the grounded path, return `No relevant content found in the knowledge base.` with empty citations. If synthesis fails, keep the existing degraded behavior where the MCP tool returns the synthesis error rather than an invented answer. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)]

7. **No schema, connector, worker, or role-pack contract changes are required.**
   The problem is answer-grounding policy inside retrieval, not canonical identity, OAuth, queueing, or connector ingestion semantics.

8. **Stay inside the existing latency budget.**
   PRD target remains under 5 seconds for a standard query. Keep the solution to lightweight grouping/filtering over already-ranked results; avoid extra DB round-trips or second LLM completions. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Query-Intent Guardrail

`src/cos/services/retrieval.py` already contains `_detect_query_type(...)`, but today that helper only supports response-formatting instructions like `draft`, `prioritise`, `compare`, and `summarise`. Story 6.14 should not blindly equate that existing formatter logic with safe grounding semantics.

If the developer reuses `_detect_query_type(...)`, they must do so carefully:

- `compare` is a clear multi-source opt-out signal
- `summarise` may still need single-source grounding if the user is summarising one record
- the default `question` bucket is too broad to prove multi-source intent

The safest pattern is a dedicated helper or a small extension that explicitly recognizes multi-source requests, while treating direct factual lookups as single-source by default.

### Current Code Seams To Use As Source Of Truth

- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - current no-content fallback
  - current synthesis prompt builder
  - current context assembly for `LLMAdapter.complete()`
  - current degraded behavior when synthesis fails

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - current hybrid ranking logic
  - current Story 6.13 thresholding and per-source pruning
  - current `document_version_id`, `source_alias`, `source_locator`, and score flow

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - current `CitedChunk` and `CitedResponse` models
  - current `prune_citations(...)` helper
  - likely good home for a small lineage-filtering helper if it should stay outside the service layer

- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
  - current `retrieve` JSON envelope
  - current top-level and nested citation serialization

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
  - current retrieval config already contains `min_score` and `max_chunks_per_source`
  - avoid adding a new config surface unless a real operator-facing knob is clearly justified

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py) only if a tiny ranking/lineage helper is truly needed

- Primary test files:
  - [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)
  - [tests/retrieval/test_citations.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_citations.py) if lineage narrowing is implemented as a helper there
  - [tests/retrieval/test_search.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py) only if search-layer behavior changes

- Optional light-touch docs or config updates:
  - [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) only if a new retrieval knob is truly added
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only if the team wants a human UAT check for grounded factual retrieval after implementation

### Testing Requirements

- Preserve the current retrieval-service and MCP regression suites; add focused tests rather than broad end-to-end-only coverage.
- Add at least one direct factual test case where semantically similar records exist across distinct source lineages and only one lineage should survive into the answer context.
- Add at least one explicit comparison or synthesis query proving multi-source evidence still works when the user asks for it.
- Add a fallback test where lineage narrowing leaves no usable evidence and the service returns the existing no-content answer with empty citations.
- Add a legacy/backfill case where `document_version_id` is blank and `source_locator` is the only safe grounding key.
- Keep automated checks deterministic and local; no live Gmail, Calendar, Docker, or MCP-client session should be required for this story.

### Project Structure Notes

- Retrieval behavior belongs in the existing retrieval/service seams under `src/cos/retrieval/` and `src/cos/services/`.
- `src/cos/mcp_server/tools.py` should keep consuming `RetrievalService`; do not move grounding policy into the MCP tool layer.
- Connector modules in `src/cos/connectors/`, queue processing in `src/cos/worker.py`, schema migrations, and role-pack YAML files should remain untouched unless a truly minimal bug fix is discovered.
- If a helper is needed, prefer a small additive helper in `src/cos/retrieval/` or `src/cos/services/` rather than a new subsystem.

### References

- [Epic 6 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Sprint change proposal that introduced Stories 6.13-6.15](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-08.md)
- [Epic 6 UAT findings that identified mixed-source factual blending](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)
- [Architecture constraints for provenance, citation integrity, and MCP response shape](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD retrieval expectations and latency target](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Current retrieval service implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- [Current retrieval search implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
- [Current citation helpers](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
- [Current MCP retrieve tool implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
- [Current retrieval service tests](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
- [Current MCP tool tests](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)

### Review Findings

- [x] [Review][Patch] Missing explicit synthesis opt-out in grounding heuristic [src/cos/services/retrieval.py:13]
- [x] [Review][Patch] Generic `aggregate` signal makes multi-source opt-out too broad [src/cos/services/retrieval.py:19]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Added `_lineage_key()` and `narrow_to_lineage()` helpers to `citations.py`. `_lineage_key` prefers `document_version_id` and falls back to `source_locator` for legacy/backfilled records.
- Added dedicated multi-source detection helpers in `retrieval.py`, centered on `_is_multi_source_query()`, rather than repurposing `_detect_query_type`, per the story's Query-Intent Guardrail note.
- Wired grounding into `RetrievalService.query()`: after 6.13 thresholding/pruning, direct factual queries are narrowed to one lineage before context and citations are built. Multi-source path is preserved for explicit compare/aggregate queries.
- Two existing 6.13 tests (`test_query_llm_receives_only_pruned_context`, `test_query_citations_match_pruned_evidence_set`) updated to use compare queries so they keep testing 6.13 pruning behavior without conflicting with 6.14 grounding.
- 414 tests pass, 1 skipped; ruff clean.
- Review fixes tightened the multi-source heuristic so explicit cross-source summaries stay multi-source while bare `aggregate` no longer disables grounding on single-source factual lookups.
- Focused regression suite passed after review fixes: 66 passed.

### File List

src/cos/retrieval/citations.py
src/cos/services/retrieval.py
tests/retrieval/test_citations.py
tests/services/test_retrieval_service.py
tests/mcp_server/test_tools.py
_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md
_bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-05-08: Implemented story 6.14 — added `narrow_to_lineage()` helper and `_is_multi_source_query()` grounding decision; wired single-source grounding into `RetrievalService.query()`; added 14 new tests covering lineage narrowing, grounding modes, and MCP citation alignment.
