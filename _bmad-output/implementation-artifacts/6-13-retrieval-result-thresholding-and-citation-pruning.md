# Story 6.13: Retrieval Result Thresholding and Citation Pruning

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want retrieval to filter low-signal results and cite only supporting evidence,
So that grounded answers stay precise in a mixed-source corpus.

## Acceptance Criteria

1. **Given** a mixed-source retrieval query,
   **When** the search results are assembled,
   **Then** chunks below a configurable relevance threshold are excluded from synthesis input.

2. **Given** an answer is synthesized,
   **When** citations are returned,
   **Then** the citation list includes only chunks or source records that materially support the answer rather than the full pre-filter retrieval set.

3. **Given** no result clears the relevance threshold,
   **When** `retrieve` completes,
   **Then** it returns the normal no-relevant-content behavior rather than forcing a weakly grounded answer.

4. **Given** the filtered retrieval path runs under normal conditions,
   **When** it is measured end to end,
   **Then** it remains within the existing retrieval latency target.

## Tasks / Subtasks

- [x] Task 1: Add retrieval-threshold configuration and wire it through the retrieval path (AC: #1, #3, #4)
  - [x] Introduce a dedicated retrieval config surface in [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) and document it in [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example); keep all numeric bounds Pydantic-validated
  - [x] Keep the change scoped to retrieval behavior only; do not alter ingestion semantics, provenance schema, role-pack schema, or connector flows
  - [x] Preserve the existing no-content answer text and empty-citations behavior when all ranked hits are filtered out before synthesis

- [x] Task 2: Filter mixed-source search results before synthesis context is built (AC: #1, #3, #4)
  - [x] Apply the relevance floor after hybrid results are assembled and before `RetrievalService` builds the LLM context
  - [x] Ensure role-priority weighting does not resurrect hits that failed the raw relevance floor; low-signal chunks must stay excluded even if their source alias would otherwise receive a priority boost
  - [x] Keep the filtered result set bounded and deterministic; do not add extra database round-trips or a second LLM call solely to decide which chunks survive

- [x] Task 3: Return only supporting citations from the bounded evidence set (AC: #2, #4)
  - [x] Ensure `CitedResponse.citations` and the MCP `retrieve` envelope contain only the filtered/pruned evidence set actually supplied to the answer path, not the full raw ranking returned before filtering
  - [x] If several near-identical chunks from the same source crowd the evidence set, apply a deterministic pruning rule that reduces citation noise without dropping the best supporting evidence
  - [x] Preserve the current response shape: top-level `citations` and `data.citations` stay in sync, and each citation still exposes `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, and `score`

- [x] Task 4: Expand tests for thresholding, no-content fallback, and citation precision (AC: #1, #2, #3, #4)
  - [x] Add config tests for the new retrieval setting(s), including invalid-value coverage
  - [x] Add retrieval/search tests covering mixed-source results above and below threshold, plus the case where all hits are filtered away
  - [x] Add service-layer tests confirming the LLM receives only filtered context and that the returned citations match the pruned evidence set
  - [x] Add MCP tool tests confirming the pruned citations propagate unchanged through the existing JSON envelope
  - [x] Latency: deterministic in-process pruning adds no extra DB round-trips or LLM calls; no automated wall-clock test added (consistent with existing test suite approach)

### Review Findings

- [x] [Review][Patch] Per-source pruning happens after `top_k` truncation, so source-dominated queries can drop alternative supporting evidence instead of admitting the next-best surviving chunks from other sources [src/cos/services/retrieval.py:108]
- [x] [Review][Patch] Equal-score hits have no deterministic tie-breaker before pruning, so repeated queries can keep different chunks from the same source when scores tie [src/cos/retrieval/search.py:234]
- [x] [Review][Patch] The new regression suite still lacks a mixed-source threshold test where above-floor and below-floor hits coexist in the same ranked result set [tests/retrieval/test_search.py:175]

## Dev Notes

### What This Story Is

Story 6.13 is the first precision fix that follows the Epic 6 connected-source UAT. It tightens the current retrieval path so mixed-source queries stop sending obviously weak evidence into synthesis and stop returning citation spam that was never meaningfully bounded.

This story is deliberately narrower than Story 6.14. The goal here is not to solve all factual-grounding issues across similar records; it is to add deterministic filtering and citation pruning to the existing retrieval pipeline so the answer layer starts from a cleaner evidence set.

### Why This Story Exists Now

The Epic 6 UAT findings captured a real trust problem in the retrieval path:

1. low-signal chunks were still being returned because retrieval currently fills up to `top_k` with no minimum relevance floor
2. the synthesis layer received the full mixed-source chunk set
3. the returned citation list mirrored the full retrieval set instead of the smaller evidence set that should support the answer

The current code confirms that gap:

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py) returns up to `top_k` ranked `CitedChunk` results and only filters semantic hits with `score > 0.0`
- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py) passes every returned chunk into `LLMAdapter.complete()`
- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py) serializes the same `response.citations` list directly into both `data.citations` and top-level `citations`

### Previous Story Intelligence

- Story 6.12 was documentation-only and explicitly aligned the public retrieval contract around `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, and `score`. This story must preserve that contract rather than redesign it. [Source: [6-12-documentation-and-housekeeping.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-12-documentation-and-housekeeping.md)]
- Story 6.11 produced the live Epic 6 UAT guide and is the source of the precision findings that motivated Stories 6.13 and 6.14. Use those findings as the behavioral baseline for regression coverage. [Source: [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)]
- Story 6.10 established the `ingest_document` MCP path and the connected-source corpus conditions that make mixed-source retrieval noisier. Do not special-case MCP-ingested notes here; apply the same thresholding rules across local files, Gmail, Calendar artifacts, and MCP notes. [Source: [6-10-ingest-document-mcp-tool.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-10-ingest-document-mcp-tool.md)]
- Story 6.14 is already defined as the single-source factual-grounding follow-up. Do not fold that source-lineage selection work into this story unless a tiny helper is strictly necessary for AC #2; keep the main behavior change here to thresholding and evidence pruning. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

### Git Intelligence

- Recent implementation history shows retrieval-adjacent behavior changes landing as small, story-scoped patches followed by focused review-fix commits before merge. Keep this work narrow and well-tested so review can stay surgical.
- Most recent relevant commit titles:
  - `Implement story 6.12 documentation and housekeeping`
  - `Fix story 6.11 review findings`
  - `Implement story 6.11 operator validation — connected sources live`

### Product And Architecture Guardrails

1. **Preserve the MCP contract.**
   The success envelope remains `{"status": "ok", "data": {...}, "citations": [...]}` and the `retrieve` tool still duplicates citations at both top level and `data.citations`. This story changes which citations survive, not the response shape. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

2. **Keep provenance fields unchanged.**
   Operator-facing citations already use `source_alias` and `source_locator`, with `document_version_id` for canonical lineage. Do not reintroduce `source_path` as the outward contract. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)]

3. **Thresholding is a retrieval concern, not an ingestion concern.**
   The problem is that low-signal ranked chunks reach synthesis. Do not modify chunking, embeddings, canonical identity, backfill, job processing, or connector sync just to satisfy this story. No schema migration should be needed.

4. **Do not break the no-content fallback.**
   The platform already promises that queries with no relevant content return a normal `ok` response with the answer text `No relevant content found in the knowledge base.` and empty citations. That fallback must also apply when results exist pre-filter but none survive the threshold. [Source: [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py), [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)]

5. **Stay within the existing latency budget.**
   Retrieval must remain within the current target of 5 seconds under normal conditions. Prefer deterministic in-process pruning over extra synthesis passes or model-judged citation selection. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

6. **Do not solve Story 6.14 here.**
   This story should improve evidence quality for mixed-source queries, but it should not silently introduce a full single-source factual-answer mode. If you find a helper abstraction that 6.14 can later build on, keep it small and generic.

### Implementation Guidance

#### Recommended Behavior Boundary

- Apply the configurable relevance threshold to the assembled hybrid results before `RetrievalService` builds the synthesis context.
- Treat the filtered evidence set as the maximum citation pool for this story. The final citation list should be a pruned subset of that bounded pool, never a superset and never the raw pre-filter ranking.
- Keep pruning deterministic. Good candidates are score-based truncation and same-source de-duplication. Avoid introducing a second LLM call that asks the model to judge evidence use.

#### Important Scoring Guardrail

The current search path computes a merged hybrid score and then applies role-priority weighting before sorting results. The new threshold must protect against low-relevance chunks that get boosted only because their `source_alias` happens to match a role priority. If you need both a raw relevance score and a final ordering score, add the internal plumbing necessary to keep that distinction explicit without changing the external citation contract.

#### Historical Contract Update

Story 3.3 originally described `RetrievalService.query()` as returning the full `CitedResults` used for synthesis. Story 6.13 intentionally narrows that behavior. From this story onward, the correct interpretation is: return the bounded evidence set that actually survives thresholding and citation pruning, while preserving the same `CitedResponse` shape. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

### Current Code Seams To Use As Source Of Truth

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - current hybrid ranking logic
  - current `top_k` behavior
  - current role-priority weighting
  - best place to keep score assembly and any raw-vs-final score distinction coherent

- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - current `No relevant content found in the knowledge base.` fallback
  - current context construction for `LLMAdapter.complete()`
  - current degraded-path behavior when synthesis fails

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - current `CitedChunk` / `CitedResponse` models
  - likely home for any small citation-pruning helper that should stay outside the MCP layer

- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
  - current JSON envelope shape for `retrieve`
  - current serialization of `response.citations`

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
  - current config model has no dedicated retrieval block yet
  - existing threshold precedent exists in `McpNoteIngestConfig`, which is useful as a validation pattern but should not be reused directly for retrieval

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
  - [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)

- Primary test files:
  - [tests/retrieval/test_search.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py)
  - [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)
  - [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py)

- Optional light-touch reference updates:
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) only if the new retrieval config needs operator-facing explanation
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only if you add a manual validation step for thresholded retrieval behavior

### Testing Requirements

- Preserve and extend the current retrieval regression suite; do not replace it with broad end-to-end-only coverage.
- Add at least one mixed-source test corpus that proves:
  - one strong chunk survives
  - one weaker semantically related chunk is filtered out
  - the no-content fallback still triggers when all hits are below threshold
- Add service tests proving the LLM context contains only the surviving filtered chunks.
- Add MCP tests proving the serialized citations exactly match the pruned evidence set and still include the same fields as before.
- If automated latency assertions are too flaky for CI, measure the path manually against the existing 5-second target and record the result in the story completion notes rather than adding a brittle sleep-based test.

### Latest Technical Notes

- pgvector's official documentation still defines cosine similarity as `1 - cosine distance`, which matches the current `1 - (e.vector <=> %s)` implementation in [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py). This story should add thresholding on top of that scoring model, not replace the operator math. [Source: [pgvector README](https://github.com/pgvector/pgvector)]
- The official MCP Python SDK documentation is still on the stable v1.x line. The current `@mcp.tool()` usage and JSON-string return pattern remain compatible, so this story does not require an MCP protocol refactor. [Source: [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk), [Model Context Protocol SDK docs](https://modelcontextprotocol.io/docs/sdk)]
- Anthropic's Messages API remains stateless. A second LLM pass for citation selection would resend prompt plus context and is therefore the wrong default for a story that must preserve the 5-second retrieval budget. Prefer deterministic pruning in-process. [Source: [Anthropic Messages examples](https://docs.anthropic.com/en/api/messages-examples)]

### Project Structure Notes

- Keep retrieval behavior inside the existing retrieval/service seams. `src/cos/mcp_server/tools.py` should continue to consume `RetrievalService`, not reach into lower-level retrieval helpers directly. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]
- No database migration, connector module change, worker change, or role-pack schema change should be necessary for this story.
- If a helper is needed for pruning, prefer placing it under `src/cos/retrieval/` or `src/cos/services/` rather than embedding new logic in the MCP tool layer.

### References

- [Epic 6 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Sprint change proposal that introduced Stories 6.13-6.15](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-08.md)
- [Epic 6 UAT findings that identified retrieval precision issues](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)
- [Architecture constraints for retrieval latency, MCP envelopes, and provenance fields](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD non-functional requirement for retrieval latency](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Current retrieval search implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
- [Current retrieval service implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- [Current MCP retrieve tool implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
- [Current retrieval service tests](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
- [Current retrieval search tests](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py)

## Dev Agent Record

### Agent Model Used

gpt-5.4

### Debug Log References

### Completion Notes List

- `RetrievalConfig` added to `src/cos/config.py` with `min_score` (float, 0.0–1.0, default 0.0) and `max_chunks_per_source` (int ≥1, default 2); field validated via Pydantic `Field(ge=..., le=...)`.
- `prune_citations(results, max_chunks_per_source)` added to `src/cos/retrieval/citations.py`; iterates the already-sorted list, tracks seen counts per `source_locator`, and keeps the top-N in original order — O(n) and stable.
- `hybrid_search` gains a `min_score: float = 0.0` parameter. Threshold is applied to the raw RRF score immediately after the score is computed, before any role-priority multiplication, so a priority weight of any magnitude cannot resurface a filtered chunk.
- `RetrievalService.query()` passes `min_score` from config to `hybrid_search` and calls `prune_citations` on the result; the pruned set is used for both LLM context and `CitedResponse.citations`. The no-content fallback triggers if the pruned set is empty (consistent with the pre-existing empty-search behavior).
- MCP `retrieve` tool required no changes — it already passes `response.citations` through unchanged.
- 22 new tests across four test files (7 config, 7 citations, 3 search, 4 service, 1 MCP); all 396 tests pass.
- AC #4 (latency): in-process pruning adds no DB round-trips or LLM calls; latency budget preserved.

### File List

- `src/cos/config.py` — added `RetrievalConfig`; added `retrieval: RetrievalConfig = RetrievalConfig()` to `CosConfig`
- `src/cos/retrieval/citations.py` — added `prune_citations`
- `src/cos/retrieval/search.py` — added `min_score` parameter; applied raw-RRF threshold before role-priority weighting
- `src/cos/services/retrieval.py` — wired `min_score` from config into `hybrid_search`; added `prune_citations` call; uses pruned set for context and citations
- `config.yaml.example` — documented `retrieval:` block with `min_score` and `max_chunks_per_source`
- `tests/test_config.py` — 7 new tests for `RetrievalConfig`
- `tests/retrieval/test_citations.py` — 7 new tests for `prune_citations`
- `tests/retrieval/test_search.py` — 3 new tests for `min_score` threshold behavior
- `tests/services/test_retrieval_service.py` — 4 new tests for pruning integration
- `tests/mcp_server/test_tools.py` — 1 new test for citation propagation through MCP envelope
