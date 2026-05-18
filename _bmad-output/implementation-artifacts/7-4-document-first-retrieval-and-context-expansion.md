# Story 7.4: Document-First Retrieval & Context Expansion

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want retrieval to preserve more document context when needed,
So that answers are less brittle on single-document and bounded-context questions.

## Acceptance Criteria

1. **Given** a query is classified as a bounded or document-centric question,
   **When** retrieval runs,
   **Then** documents are ranked before chunk-level expansion so the platform can preserve local context more effectively.

2. **Given** a highly ranked chunk is selected,
   **When** context expansion is applied,
   **Then** adjacent or parent context is included according to documented rules rather than passing isolated fragments only.

3. **Given** the benchmark harness is rerun after this change,
   **When** results are compared to the prior baseline,
   **Then** bounded-context query classes improve or hold steady with no material regression in direct factual lookup.

## Tasks / Subtasks

- [ ] Task 1: Introduce a document-first retrieval strategy for bounded and document-centric questions (AC: #1, #3)
  - [ ] Reuse the current `hybrid_search_with_trace(...)` candidate-gathering path as the baseline; do not introduce a second independent retrieval engine, a new storage model, or a benchmark-only search algorithm.
  - [ ] Add a shared query-strategy helper so runtime retrieval and the benchmark harness can both reason about at least:
    - [ ] default chunk-first retrieval
    - [ ] single-lineage bounded or document-centric retrieval
    - [ ] explicit multi-source synthesis
  - [ ] Aggregate existing chunk candidates into document or lineage candidates using `document_version_id` where present and `source_locator` only as the legacy fallback.
  - [ ] Rank documents before final chunk or span selection when the bounded-context strategy triggers, while leaving direct fact and exact phrase behavior stable when it does not.

- [ ] Task 2: Add bounded context expansion around winning anchors without undoing Story 7.3 citation hardening (AC: #1, #2, #3)
  - [ ] Define deterministic expansion rules around anchor chunks, such as adjacent chunk windows and/or same-document contiguous spans, instead of ad hoc prompt stuffing.
  - [ ] Preserve document order and chronology in expanded context; for email, calendar, and note style records, do not scramble local narrative order by score alone.
  - [ ] Keep a clear internal boundary between:
    - [ ] synthesis context sent to the model
    - [ ] citation-eligible supporting evidence returned to the caller
  - [ ] Expanded context must not automatically widen the returned citation set unless the chunk is still eligible to support the answer under Story 7.3 precision rules.
  - [ ] Bound total context expansion so the feature does not silently turn into unbounded whole-document prompting by default.

- [ ] Task 3: Extend telemetry and benchmark semantics additively so this work is measurable and debuggable (AC: #1, #2, #3)
  - [ ] Add additive document-first and expansion stage metadata to the retrieval trace, such as document candidate counts, selected document counts, expansion mode, or expanded context counts.
  - [ ] Preserve the existing content-safety contract: no raw query text, prompt text, chunk text, secrets, DSNs, or tokens in runtime telemetry.
  - [ ] Keep benchmark report fields machine-comparable across Story 7.2, 7.3, and 7.4 outputs; add fields rather than silently changing the meaning of existing ones.
  - [ ] Surface enough stage data that a regression can be attributed to document ranking, anchor selection, context expansion, citation filtering, or synthesis.

- [ ] Task 4: Fix the benchmark-fixture blind spot and add regression coverage for multi-chunk bounded-context behavior (AC: #2, #3)
  - [ ] Address the current harness limitation in `RetrievalEvalService._seed_fixtures(...)`, which stores each generated fixture document as a single chunk today and therefore cannot prove adjacent-chunk or parent-context recovery.
  - [ ] Add deterministic multi-chunk fixture coverage for at least one `single_doc_interpretation` case and one bounded multi-paragraph case where the answer depends on local context across chunk boundaries.
  - [ ] Add retrieval-service and retrieval-search tests proving document-first ranking and expansion use the existing retrieval path rather than bypassing it.
  - [ ] Add tests proving citation precision does not regress when context expansion introduces non-anchor neighbor chunks into the model context.
  - [ ] Rerun or extend benchmark coverage so bounded-context classes are explicitly evaluated and direct factual lookup remains protected from regression.

- [ ] Task 5: Add only the minimum config and docs surface necessary for safe operation (AC: #2, #3)
  - [ ] If new operator-facing controls are required, keep them retrieval-scoped in `CosConfig` and `config.yaml.example` rather than adding role-pack or provider-specific toggles.
  - [ ] Document any new tuning knobs or benchmark expectations briefly in the existing operator-facing docs only where discoverability is needed.
  - [ ] Keep this story scoped to document-first ranking and bounded context expansion; do not pull in hierarchical summaries, graph retrieval, provider-routing redesign, or a general long-context mode.

## Dev Notes

### What This Story Is

Story 7.4 is the first context-preservation step after Epic 7 established:

1. a repeatable benchmark corpus and harness in Story 7.1
2. additive retrieval telemetry and regression attribution in Story 7.2
3. a stricter evidence-selection and citation-precision boundary in Story 7.3

The remaining retrieval-trust gap is chunk-boundary brittleness. The current platform still retrieves flat chunk candidates, narrows direct factual queries to one lineage where appropriate, and sends `context = [chunk.content, ...]` into the LLM adapter. That works well for direct facts and citation-heavy lookup, but it is still fragile when the answer depends on nearby qualifiers, narrative continuity, chronology, or document-local framing. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [src/cos/llm/anthropic.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)]

This story is not a full long-context mode, not hierarchical summary retrieval, and not graph retrieval. It is a bounded extension of the existing hybrid baseline so single-document and bounded-context questions become more robust before later growth epics amplify the retrieval layer. [Source: [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

### Why This Story Exists Now

Epic 7 intentionally sequences retrieval trust before Telegram, web augmentation, proactive scheduling, or richer provider-routing work. Stories 7.1 through 7.3 made the platform measurable, diagnosable, and stricter about what counts as supporting evidence. They did not yet fix the fact that isolated chunk text can lose local qualifiers and narrative continuity. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

Today the code path is still:

1. hybrid chunk retrieval in `search.py`
2. optional lineage narrowing in `citations.py`
3. explicit evidence selection in `select_synthesis_evidence(...)`
4. plain chunk-content list passed to `LLMAdapter.complete(prompt, context)`

That means the system is now precise enough to benchmark and diagnose, but still not yet document-aware enough for bounded-context interpretation. Story 7.4 is the right place to improve context integrity without skipping ahead to the more advanced retrieval modes described in the roadmap. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

### Previous Story Intelligence

- Story 6.13 already established `retrieval.min_score` and `retrieval.max_chunks_per_source`. Story 7.4 must build on those controls rather than bypassing them with a second unbounded retrieval path. [Source: [6-13-retrieval-result-thresholding-and-citation-pruning.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md), [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py), [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)]
- Story 6.14 already tightened direct factual queries to a single winning lineage unless the prompt explicitly asks for multi-source synthesis. Document-first ranking must not reintroduce casual cross-source fact blending. [Source: [6-14-single-source-factual-grounding-for-retrieve.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)]
- Story 7.1 already created the eval corpus and harness, but the current fixture seeding path stores each generated document as a single `ChunkRecord`. That means the harness cannot yet prove adjacent-chunk recovery or document-local context preservation. This is a real blind spot for Story 7.4 and should be fixed as part of the work, not deferred. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]
- Story 7.2 already requires additive, content-safe telemetry. If 7.4 adds document-ranking or expansion stages, it must expose them without silently repurposing existing `candidate_counts` fields. [Source: [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md), [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)]
- Story 7.3 made evidence selection explicit and bound citations tightly to eligible evidence. Story 7.4 is the first story where synthesis context may need to be larger than the final citation set. If that distinction is introduced, it must remain precise, testable, and internal to the retrieval stack rather than leaking a confusing new public contract. [Source: [7-3-retrieval-evidence-selection-and-citation-precision-hardening.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)]

### Git Intelligence

- Recent implementation history stays tightly scoped and review-driven:
  - `2a2e1cd` - `Fix story 7.3 review findings`
  - `55169fe` - `Implement story 7.3: retrieval evidence selection and citation precision hardening`
  - `22f760f` - `Merge pull request #51 from iainhgl/story/7-2-retrieval-observability-and-structured-eval-logging`
  - `ede0df0` - `Fix story 7.2 review findings`
  - `bfcd5a3` - `Implement story 7.2: retrieval observability and structured eval logging`
- Keep 7.4 equally focused: document ranking, bounded context expansion, telemetry, benchmark coverage, and only the minimum config/docs updates truly required.

### Product And Architecture Guardrails

1. **Extend the baseline; do not replace it.**  
   The approved roadmap is explicit: improve the current hybrid RAG baseline before adopting more advanced retrieval modes. Story 7.4 should add a bounded document-first mode, not replace chunk retrieval wholesale. [Source: [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

2. **Keep service boundaries intact.**  
   `cos/mcp_server/` and `cos/cli.py` should continue to go through `cos/services/*`. Retrieval policy belongs in the retrieval stack and service layer, not in the MCP tool wrapper. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)]

3. **Preserve Story 7.3 citation trust.**  
   Context expansion is useful only if it does not reintroduce citation spam or support leakage. A larger synthesis context must not automatically mean a larger returned citation set. [Source: [7-3-retrieval-evidence-selection-and-citation-precision-hardening.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md)]

4. **Stay inside the existing latency budget.**  
   PRD and architecture still expect interactive retrieval within the stated performance envelope. Prefer one retrieval pass plus bounded ranking/expansion over multiple full retrieval passes or multiple default LLM calls. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

5. **Do not require a schema migration by default.**  
   The current chunk and document-version model already provides enough identity to prototype document-first ranking and adjacent-chunk recovery. Only introduce schema work if a specific blocker is proven, not by default. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

6. **Keep benchmark execution deterministic and local.**  
   No live LLM provider, no browser auth, no Gmail/Calendar network dependency, and no external reranker should be required for benchmark or regression tests. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)]

7. **Keep telemetry additive and content-safe.**  
   Any new document-ranking or expansion metadata must follow the existing JSON-logging contract without exposing raw content. [Source: [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md), [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)]

8. **Do not pull in later-roadmap retrieval modes early.**  
   Hierarchical summaries, graph retrieval, and broader query routing remain later roadmap work. Story 7.4 should stay focused on document-first ranking and bounded context expansion inside the existing hybrid retrieval architecture. [Source: [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

9. **If knobs are added, keep them retrieval-scoped and minimal.**  
   Any operator-facing tuning should belong under `retrieval:` in `CosConfig` and `config.yaml.example`, not in role-pack config or provider config. [Source: [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py), [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)]

10. **No `project-context.md` is present; the planning artifacts are authoritative.**  
   There is no repo-level `project-context.md` to rely on here. Use `epics.md`, `prd.md`, `architecture.md`, and the retrieval roadmap research as the source of truth for scope and constraints.

### Recommended Implementation Shape

#### Recommended Default Flow

The safest 7.4 implementation shape is:

1. run the existing hybrid retrieval path and collect additive stage counts
2. preserve Story 6.13 thresholding and per-source pruning
3. preserve Story 6.14 lineage discipline where the query class calls for it
4. when the query is bounded or document-centric, aggregate chunk candidates into document candidates
5. rank candidate documents or lineages deterministically
6. select anchor chunks from the winning document set
7. expand bounded local context around those anchors using documented rules
8. build the synthesis context from that ordered expanded set
9. derive citations from the support-eligible subset only
10. benchmark the result against bounded-context classes and direct-fact non-regression

This keeps 7.4 measurable, scoped, and compatible with the current retrieval stack. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]

#### Query Strategy Guardrail

The current runtime has helpers for query mode and multi-source intent, but no explicit bounded-context strategy selector yet. Prefer a shared helper that can be used by both runtime retrieval and the benchmark harness so the logic does not drift between:

- benchmark query classes such as `single_doc_interpretation`
- runtime text heuristics for bounded or document-centric questions
- explicit multi-source compare or synthesis questions

Avoid scattering these decisions across `RetrievalService`, benchmark code, and tests separately. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]

#### Context Expansion Guardrail

Expanded context should stay within the same document or lineage unless the query explicitly asks for multi-source synthesis. Good default behavior would include:

- anchor chunk selection from the highest-ranked document(s)
- immediate neighbor chunk expansion and/or bounded contiguous span recovery
- overlap deduplication when anchors land near each other
- stable ordering by document and `chunk_index`
- explicit caps on the number of expanded chunks or selected documents

Avoid an implementation that simply "takes more chunks" globally. That would change quantity, not context integrity. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

#### Citation vs Synthesis-Context Guardrail

This story likely needs a more explicit distinction than the current "same list goes everywhere" shape:

- the model may benefit from a larger ordered context span
- the user should still receive only the evidence that is actually eligible to support the answer

If an internal dual representation is added, keep it local to the retrieval stack and preserve the external MCP response envelope. This is the most likely place for 7.4 to trip over 7.3 if it is implemented naively. [Source: [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py), [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py), [7-3-retrieval-evidence-selection-and-citation-precision-hardening.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md)]

#### Benchmark Fixture Reality Check

Right now `RetrievalEvalService._seed_fixtures(...)` seeds every generated fixture document as a single chunk. That means a benchmark can currently prove document ranking or citation behavior, but not actual adjacent-chunk recovery. Story 7.4 should either:

- teach the benchmark harness to seed deterministic multi-chunk fixtures, or
- add deterministic multi-chunk service-level coverage that is strong enough to catch context-loss regressions

Prefer doing both for the highest-signal bounded-context cases. [Source: [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [tests/fixtures/retrieval_eval/gold/core-queries.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/gold/core-queries.yaml), [tests/fixtures/retrieval_eval/stress_fuzz/adversarial.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/stress_fuzz/adversarial.yaml)]

### Current Code Seams To Use As Source Of Truth

- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - current runtime query path
  - existing query-mode and multi-source heuristics
  - current boundary where `context` becomes a list of plain chunk strings

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - current hybrid candidate gathering, thresholding, pruning, and scoring
  - likely home for additive document-ranking support or result structs

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - lineage helpers
  - current evidence-selection boundary
  - likely home for bounded expansion helpers or support-vs-context modeling if kept retrieval-local

- [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)
  - current additive count model
  - likely place for any document-first or expansion-stage counters

- [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - current schema versioning and report attribution logic
  - likely place for additive bounded-context metadata in benchmark output

- [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - current benchmark orchestration
  - fixture seeding path that currently hides adjacent-chunk behavior

- [src/cos/llm/anthropic.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)
  - current prompt assembly shape: context first, instruction second, numbered context blocks
  - important for preserving useful ordering if expanded spans get larger

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
  - existing retrieval-scoped configuration surface
  - likely place for minimal new expansion knobs only if truly needed

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)
  - [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)

- Optional additive helper only if the logic becomes too tangled:
  - `src/cos/retrieval/strategy.py`
  - `src/cos/retrieval/context_expansion.py`

- Configuration or docs only if justified:
  - [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
  - [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
  - [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only if a concise operator note is truly useful

- Primary test files:
  - [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
  - [tests/retrieval/test_search.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py)
  - [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)
  - [tests/retrieval/test_benchmark_harness.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_benchmark_harness.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py) only if surface-level citation ordering or envelope semantics change
  - [tests/cli/test_cli_benchmark.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_benchmark.py) only if benchmark summary output changes

- Avoid by default:
  - changes to `src/cos/connectors/*`
  - changes to `src/cos/worker.py`
  - schema migrations under `src/cos/store/migrations/`
  - role-pack YAML changes
  - broad LLM adapter redesign
  - provider-routing work ahead of Epic 9
  - web augmentation or external reranking dependencies

### Testing Requirements

- Add retrieval-service coverage proving:
  - bounded or document-centric questions trigger the document-first path
  - direct factual queries still preserve the existing single-lineage discipline
  - expanded synthesis context remains ordered and bounded
  - citation output remains a support-eligible subset rather than blindly mirroring all expanded context

- Add retrieval/search coverage proving:
  - thresholding and per-source pruning still apply before document-first expansion
  - document ranking uses existing candidates rather than re-querying the database through a second ad hoc path
  - adjacent-chunk recovery works across real multi-chunk fixtures, not just single-chunk mocks

- Add benchmark/eval coverage proving:
  - bounded-context query classes improve or hold steady
  - direct factual lookup does not materially regress
  - benchmark output can attribute regressions to document ranking vs context expansion vs citation filtering
  - multi-chunk seeded fixtures remain deterministic and local

- Add MCP-tool tests only if needed to prove:
  - response envelope is unchanged
  - citation ordering or subset behavior is still correct from the tool consumer's perspective

- Keep tests deterministic and local:
  - reuse the existing Postgres-backed harness
  - reuse fake embedding patterns already used in retrieval tests
  - do not require live model calls
  - do not require live connector auth

### Latest Technical Notes

- The official `pgvector` documentation still defines `<=>` as cosine distance and recommends `1 - cosine distance` for cosine similarity. That supports keeping the current similarity math in `search.py` while changing ranking shape above it instead of swapping vector semantics mid-story. [Source: [pgvector README](https://github.com/pgvector/pgvector)]
- Anthropic's current long-context guidance recommends keeping longform data before the query, structuring multi-document inputs clearly, and grounding responses in quoted evidence. The current adapter already places context before instruction; Story 7.4 should preserve or improve that ordering if expanded spans become larger. [Source: [Anthropic prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#long-context-prompting)]
- The official MCP docs still list the Python SDK as Tier 1. That reinforces keeping this story inside the existing retrieval implementation and MCP tool contract rather than coupling document-first work to protocol changes. [Source: [Model Context Protocol SDKs](https://modelcontextprotocol.io/docs/sdk)]

### Project Structure Notes

- Keep the behavior change centered under `src/cos/retrieval/` and `src/cos/services/`.
- If a new helper is needed, prefer a small additive module under `src/cos/retrieval/` over pushing strategy logic into `mcp_server/` or `cli.py`.
- No `project-context.md` was found in the repo; the planning artifacts above are the authoritative context for this story.
- No database migration should be necessary unless a concrete blocker is discovered during implementation.

### References

- [Epic 7 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD functional and non-functional requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture boundaries and data flow](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Retrieval improvement roadmap research](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)
- [Story 6.13 baseline retrieval filtering](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md)
- [Story 6.14 baseline single-lineage grounding](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md)
- [Story 7.1 benchmark baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md)
- [Story 7.2 observability baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md)
- [Story 7.3 evidence-selection baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md)
- [Current retrieval service](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- [Current retrieval search pipeline](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
- [Current citation helpers](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
- [Current telemetry model](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)
- [Current benchmark models and service](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
- [Current LLM adapter contract](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [Anthropic adapter](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)
- [Benchmark fixture README](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)

### Review Findings

- [x] [Review][Patch] Bounded retrieval still narrows by top chunk lineage instead of ranking document candidates first [src/cos/services/retrieval.py:214]
- [x] [Review][Patch] Bounded mode bypasses the shared Story 7.3 evidence-selection boundary [src/cos/services/retrieval.py:217]
- [x] [Review][Patch] Context expansion is not safe for legacy records or widely separated anchors [src/cos/retrieval/context_expansion.py:64]
- [x] [Review][Patch] The benchmark still cannot prove chunk-level bounded-context recovery or citation precision [src/cos/services/retrieval_eval.py:123]
- [x] [Review][Patch] Runtime bounded-query heuristics are broad enough to reroute direct-fact lookups [src/cos/retrieval/strategy.py:90]

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

### Completion Notes List

- Story context created on 2026-05-18.
- Sprint status advanced from `backlog` to `ready-for-dev` on 2026-05-18.
- Review findings resolved on 2026-05-18; targeted retrieval tests and production retrieval lint passed.
- No repo `project-context.md` file was found; the story was grounded in the planning artifacts, current Epic 7 story chain, and the live retrieval codebase.
- Primary implementation risk called out explicitly: the benchmark harness currently seeds one chunk per fixture document, which would otherwise hide adjacent-context regressions.

### File List

- `_bmad-output/implementation-artifacts/7-4-document-first-retrieval-and-context-expansion.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
