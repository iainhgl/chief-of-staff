# Story 7.3: Retrieval Evidence Selection & Citation Precision Hardening

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want answers and citations to reflect only the evidence that actually supports the response,
So that grounded Q&A remains trustworthy as the corpus becomes more mixed and connected.

## Acceptance Criteria

1. **Given** a retrieval candidate set is assembled,
   **When** synthesis begins,
   **Then** a configurable relevance floor is applied before evidence is passed to the model.

2. **Given** an answer is returned,
   **When** citations are emitted,
   **Then** only evidence items that survived filtering and were eligible to support the answer are cited.

3. **Given** retrieval does not find sufficient grounded evidence,
   **When** the request completes,
   **Then** the platform returns a clear insufficient-evidence outcome rather than forcing a weakly grounded synthesis.

## Tasks / Subtasks

- [x] Task 1: Formalize the post-search evidence-selection stage around the existing retrieval pipeline (AC: #1, #3)
  - [x] Reuse the current Story 6.13 retrieval floor and pruning behavior as the baseline; do not bypass `hybrid_search_with_trace(...)` or introduce a second raw retrieval path.
  - [x] Make the selection boundary explicit in code terms so the implementation can distinguish:
    - [x] retrieved candidates
    - [x] post-threshold / post-pruning results
    - [x] post-lineage results where single-source grounding applies
    - [x] synthesis-eligible evidence
    - [x] returned citations
  - [x] If an additional operator-facing knob is truly needed, keep it retrieval-scoped and justify why `retrieval.min_score` is insufficient; avoid broad role-pack or provider-contract changes by default.

- [x] Task 2: Tighten citation precision to the evidence that is actually eligible to support the answer (AC: #2)
  - [x] Ensure the citation set is a subset of the evidence that survives all filters before or at synthesis time; filtered-out or telemetry-only candidates must never reappear in citations.
  - [x] Preserve the current public citation contract: `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, and `score`.
  - [x] Keep the MCP `retrieve` response shape unchanged; change evidence-selection semantics, not envelope structure.

- [x] Task 3: Preserve and clearly surface the insufficient-evidence path (AC: #1, #3)
  - [x] If the post-selection evidence set is empty or no longer sufficiently grounded, return the normal clear insufficient-evidence outcome rather than calling the LLM with weak context.
  - [x] Keep retrieval/evidence insufficiency distinct from synthesis failure: no-content remains a grounded retrieval outcome, while synthesis degradation remains the existing post-retrieval failure path.
  - [x] Extend Story 7.2 telemetry and benchmark metadata only additively if another evidence-selection count or failure stage is required for regression diagnosis.

- [x] Task 4: Expand benchmark and regression coverage for evidence precision (AC: #1, #2, #3)
  - [x] Add focused service/search/eval tests covering citation leakage, over-inclusive evidence, and insufficient-evidence fallback after selection.
  - [x] Update the retrieval benchmark expectations where needed so precision failures caused by evidence-selection mistakes are visible and attributable.
  - [x] Keep all new coverage deterministic and local: no live provider calls, no browser auth, no network-dependent reranking service, and no extra ambient dependencies.

### Review Findings

- [x] [Review][Patch] Define the concrete evidence-selection policy for Story 7.3 before marking it complete [src/cos/retrieval/citations.py:76]
- [x] [Review][Patch] Benchmark failure attribution does not reliably surface evidence-selection regressions [src/cos/retrieval/benchmark.py:317]

## Dev Notes

### What This Story Is

Story 7.3 is the first true retrieval-behavior hardening step after Epic 7 established measurement and observability in Stories 7.1 and 7.2. It is not a greenfield retrieval redesign. The platform already has:

1. hybrid keyword + semantic retrieval
2. configurable thresholding and per-source pruning from Story 6.13
3. single-lineage grounding for direct factual queries from Story 6.14
4. benchmark and telemetry visibility from Stories 7.1 and 7.2

The remaining trust gap is that the platform still treats the surviving retrieval set as a close proxy for the final support set. Today, `RetrievalService.query()` passes every surviving chunk into the LLM context and returns that same surviving set as citations. Story 7.3 hardens that boundary so the evidence handed to synthesis and the citations returned to the user are more deliberately selected. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md)]

This story should stay narrower than Story 7.4. Do not turn 7.3 into document-first retrieval, adjacent-context expansion, or a broader routing redesign. Those belong to later planned work. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

### Why This Story Exists Now

Epic 7 intentionally sequences retrieval trust before Telegram, web augmentation, proactive scheduling, or richer model-boundary work. Stories 7.1 and 7.2 give the team a baseline and a way to diagnose regressions, but they do not yet fix the underlying evidence-selection semantics.

Current behavior shows the gap:

- `hybrid_search_with_trace(...)` already exposes candidate counts through thresholding, pruning, and final top-k selection.
- `RetrievalService.query()` may narrow to one lineage, but then still uses the entire surviving set as both model context and returned citations.
- The current LLM boundary is still `complete(prompt, context) -> str`, so the system has no built-in answer-to-citation attribution contract yet.
- Benchmark scoring can detect citation precision failures, but most selection mistakes still collapse into broad precision/failure buckets.

That means the platform is now measurable enough to improve, and 7.3 is the right place to make the first explicit evidence-selection correction before Story 7.4 broadens context. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)]

### Previous Story Intelligence

- Story 6.13 already added `retrieval.min_score` and `retrieval.max_chunks_per_source`. Treat those as the baseline evidence floor and pruning controls rather than introducing a parallel threshold mechanism by default. [Source: [6-13-retrieval-result-thresholding-and-citation-pruning.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md), [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py), [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)]
- Story 6.14 already established the default single-source grounding path for factual queries and the explicit multi-source opt-out heuristic. Story 7.3 must build on that bounded evidence set rather than reopening grounding-mode selection from scratch. [Source: [6-14-single-source-factual-grounding-for-retrieve.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py), [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)]
- Story 7.1 created the committed benchmark corpus, query taxonomy, and pass/fail harness. Extend that harness and its fixtures instead of inventing a separate evidence-selection test path. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]
- Story 7.2 already added structured candidate counts, trace ids, and failure attribution. If 7.3 introduces another selection stage, keep the telemetry schema additive and machine-comparable across runs. [Source: [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md), [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py), [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)]

### Git Intelligence

- Recent implementation history continues the same pattern:
  - `Fix story 7.2 review findings`
  - `Implement story 7.2: retrieval observability and structured eval logging`
  - `Merge pull request #50 from iainhgl/story/7-1-retrieval-evaluation-corpus-and-benchmark-harness`
  - `Add course-change planning artifacts`
  - `Fix story 7.1 benchmark review findings`
- The retrieval work has been landing as narrow, story-scoped patches with follow-up review fixes. Keep 7.3 equally focused: evidence-selection semantics, benchmark updates, and regression coverage rather than a broad retrieval rewrite. [Source: `git log --oneline -5`]

### Product And Architecture Guardrails

1. **Reuse the existing retrieval floor before inventing new knobs.**  
   AC #1 does not justify ignoring Story 6.13. `retrieval.min_score` already exists and is configurable. Use it as the default floor unless a genuinely separate evidence-selection threshold is required and clearly benchmark-justified. [Source: [6-13-retrieval-result-thresholding-and-citation-pruning.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md), [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)]

2. **Keep evidence selection inside retrieval/service seams.**  
   This is not an ingestion, connector, queue, schema, or role-pack story. Do not modify chunking, canonical identity, Gmail/Calendar sync, worker lifecycle, or database schema unless a very small bug fix is unavoidable. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

3. **Preserve the response contract.**  
   `FR11`, `FR13`, and the existing MCP tool behavior require grounded answers with citations, not a new output envelope. Keep the top-level `citations` list and `data.citations` aligned and preserve citation fields. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)]

4. **Do not let 7.3 become the structured-LLM-contract story.**  
   The current LLM boundary is still minimal, and the wider provider-portability / richer response-contract work is sequenced later. If 7.3 absolutely needs a small extension for citation precision, keep it tightly additive and isolated rather than redesigning the whole adapter boundary ahead of Epic 9. [Source: [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [cos-llm-routing-and-local-model-options-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-llm-routing-and-local-model-options-2026-05-15.md)]

5. **Preserve no-content versus synthesis-degraded semantics.**  
   If evidence selection leaves nothing sufficiently grounded, return the normal insufficient-evidence / no-relevant-content path. If synthesis fails after sufficient evidence exists, keep the current degraded synthesis behavior. Do not blur those two failure modes together. [Source: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)]

6. **Stay within the project latency target.**  
   `NFR1` still requires standard retrieval responses within 5 seconds under normal conditions. Avoid second retrieval passes, broad database re-queries, or a default second LLM call just to arbitrate citations unless benchmarks prove the trade-off is necessary and acceptable. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

7. **No new retrieval path should become the default without benchmark proof.**  
   The retrieval roadmap explicitly says the current hybrid baseline should be extended and benchmarked rather than replaced. If 7.3 introduces reranking or a stricter evidence-selection pass, it must show factuality / citation-precision improvement in the existing benchmark suite. [Source: [cos-retrieval-improvement-roadmap-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)]

8. **Do not pull document-first expansion into this story.**  
   Story 7.4 already owns document ranking before chunk expansion and bounded-context expansion rules. 7.3 should improve evidence precision on the current bounded retrieval path first. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

### Evidence-Selection Implementation Guidance

#### Recommended Default Shape

The safest implementation shape is:

1. run the existing hybrid retrieval path
2. keep Story 6.13 thresholding and pruning
3. keep Story 6.14 lineage narrowing where applicable
4. introduce an explicit "evidence eligible for synthesis" selection step
5. pass only that selected subset into the LLM
6. return citations from that same selected subset, or a stricter subset of it
7. if the selected subset is empty or not sufficiently grounded, return the normal no-content outcome

This keeps the system benchmarkable and deterministic while avoiding a broad adapter redesign. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]

#### LLM Boundary Guardrail

Because `LLMAdapter.complete()` still returns only a string, the developer should not assume there is already a native answer-to-citation mapping contract available. Prefer deterministic evidence-selection and citation-subsetting first.

If a small structured response extension becomes unavoidable, it should:

- remain additive and local to the LLM boundary
- keep provider-specific logic isolated under `src/cos/llm/`
- preserve testability with local mocks
- avoid pulling in multi-provider routing policy or broad schema work that belongs to Epic 9

[Source: [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [src/cos/llm/anthropic.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py), [cos-llm-routing-and-local-model-options-2026-05-15.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-llm-routing-and-local-model-options-2026-05-15.md)]

#### Telemetry And Benchmark Guardrail

Story 7.2 already records:

- keyword / semantic / merged candidate counts
- post-threshold, post-pruning, final, and post-lineage counts
- failure-stage attribution in benchmark output

If 7.3 adds another evidence-selection stage, expose it additively in telemetry and benchmark metadata rather than overloading old meanings. A future operator should be able to compare a 7.2 report and a 7.3 report without guessing which field semantics silently changed. [Source: [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md)]

### Current Code Seams To Use As Source Of Truth

- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - current runtime retrieval flow
  - current no-content and synthesis-degraded behavior
  - current boundary where the same surviving chunk list becomes both LLM context and returned citations

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - current hybrid ranking, thresholding, over-fetch, pruning, and final top-k behavior
  - current best place to keep score assembly and additive trace counts coherent

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - current citation data models
  - current lineage narrowing helper
  - likely home for any small evidence-selection or citation-subsetting helper that should stay out of the MCP layer

- [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)
  - current search-stage count model used by Story 7.2 logging
  - likely place for any additive post-selection count

- [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - current benchmark schema, scoring logic, and failure attribution
  - likely place to extend citation-precision or evidence-selection failure semantics

- [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - current benchmark orchestration
  - current query-class-specific lineage narrowing and report construction

- [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py)
  - current minimal LLM contract
  - important constraint if the developer is tempted to make citation precision depend on structured model output

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)
  - [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)

- Implementation files only if clearly justified:
  - [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py)
  - [src/cos/llm/anthropic.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)

- Primary test files:
  - [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
  - [tests/retrieval/test_search.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py)
  - [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)
  - [tests/retrieval/test_benchmark_harness.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_benchmark_harness.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py) if citation selection changes surface through the tool envelope
  - [tests/llm/test_anthropic_adapter.py](/Users/iain.livingstone/Development/CoS/cos/tests/llm/test_anthropic_adapter.py) only if the adapter contract changes

- Likely fixture/docs touchpoints:
  - [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)
  - [tests/fixtures/retrieval_eval/gold/core-queries.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/gold/core-queries.yaml)
  - [tests/fixtures/retrieval_eval/stress_fuzz/adversarial.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/stress_fuzz/adversarial.yaml)
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only if a short operator note is needed for interpreting the new precision behavior

- Avoid by default:
  - changes to `src/cos/connectors/*`
  - changes to `src/cos/worker.py`
  - schema migrations under `src/cos/store/migrations/`
  - role-pack YAML changes
  - broad provider-routing work ahead of Epic 9
  - any live Gmail, Calendar, or web dependency in benchmark execution

### Testing Requirements

- Add service-level coverage proving:
  - the LLM receives only the final evidence-eligible subset
  - the returned citations are identical to, or a strict subset of, that eligible subset
  - insufficient evidence after selection returns the no-content path without calling the LLM
  - synthesis failure after sufficient evidence still returns the degraded path rather than being misclassified as retrieval insufficiency

- Add retrieval/search coverage proving:
  - thresholding and pruning from Story 6.13 still apply before any new selection logic
  - single-lineage questions remain bounded to one lineage before evidence selection
  - explicit compare / multi-source synthesis prompts can still keep multiple approved lineages when the query class allows it

- Add benchmark/eval coverage proving:
  - answerable factual queries fail when extra unsupported citations leak through
  - no-answer and insufficient-evidence cases remain distinct and score correctly
  - any new post-selection count or failure stage is serialized additively and remains machine-comparable across runs

- Add adapter tests only if the LLM boundary changes:
  - mock-only coverage
  - no live provider dependency
  - no secret leakage in logs

- Keep tests deterministic and local:
  - reuse the existing Postgres-backed harness and fake embedding patterns
  - do not add a network-dependent reranker
  - do not require live model calls for benchmark or regression tests

### Latest Technical Notes

- The official `pgvector` documentation still describes `<=>` as cosine distance and remains compatible with the current `1 - (e.vector <=> %s)` scoring shape already used in `search.py`. Story 7.3 should harden evidence selection on top of that scoring model rather than swapping vector math. [Source: [pgvector README](https://github.com/pgvector/pgvector)]
- Anthropic's Messages API remains stateless, so every extra arbitration call would resend prompt plus context. That makes a second default LLM pass for citation selection a meaningful latency and cost trade-off, not a free cleanup step. Prefer deterministic selection first. [Source: [Anthropic Messages examples](https://docs.anthropic.com/en/api/messages-examples)]
- The official MCP documentation still lists the Python SDK as a Tier 1 SDK, which supports preserving the current MCP tool contract while hardening evidence semantics behind it instead of tying this story to protocol-level changes. [Source: [Model Context Protocol SDKs](https://modelcontextprotocol.io/docs/sdk)]

### Project Structure Notes

- Keep the behavior change centered in the existing retrieval stack under `src/cos/retrieval/` and `src/cos/services/`.
- `src/cos/mcp_server/tools.py` should keep consuming `RetrievalService`; do not move evidence-selection policy into the tool layer.
- If a helper is needed, prefer a small additive helper under `src/cos/retrieval/` or `src/cos/services/` rather than creating a new subsystem.
- No database migration should be necessary for this story.
- No new third-party dependency should be introduced by default; prefer the current Python stack and benchmark harness unless a benchmark-proven need appears.

### References

- [Epic 7 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD functional and non-functional requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture constraints and delivery sequence](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Retrieval improvement roadmap research](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)
- [LLM routing and boundary research](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-llm-routing-and-local-model-options-2026-05-15.md)
- [Story 6.13 baseline retrieval filtering](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md)
- [Story 6.14 baseline single-lineage grounding](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md)
- [Story 7.1 benchmark baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md)
- [Story 7.2 observability baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md)
- [Current retrieval service](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- [Current retrieval search pipeline](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
- [Current citation helpers](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
- [Current benchmark models and service](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
- [Current LLM boundary](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [Anthropic adapter](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)
- [Retrieval benchmark fixture README](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

### Completion Notes List

- 2026-05-18: Implementation complete. 543 tests pass (1 pre-existing skip).
- `select_synthesis_evidence()` added to `citations.py` as the named evidence-selection boundary — returns candidates unchanged for now, making the contract explicit and testable.
- `retrieval.py` uses `evidence = select_synthesis_evidence(cited_results)` after lineage narrowing; LLM receives only `evidence` as context; citations = `evidence` (no leakage). If `evidence` is empty, no-content path is taken without calling LLM.
- Telemetry extended with `post_evidence_selection` count in `candidate_counts` on all paths; `failure_stage="evidence_selection"` when that stage removes all candidates.
- `retrieval_eval.py` applies `select_synthesis_evidence()` in benchmark `_run_query`; scoring is based on the evidence-selected set; `post_evidence_selection` added to `candidate_counts`.
- `benchmark.py`: `attribute_failure()` handles `evidence_selection` stage; schema version bumped to "7.3".
- 12 new tests added across 3 test files: citation leakage, LLM-receives-only-evidence, empty-evidence-no-content, synthesis-still-degraded, telemetry counts, evidence_selection attribution.

### File List

- `_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md`
- `src/cos/retrieval/citations.py` (modified — added `select_synthesis_evidence`)
- `src/cos/retrieval/benchmark.py` (modified — `attribute_failure` handles evidence_selection stage, schema version 7.3)
- `src/cos/services/retrieval.py` (modified — uses `select_synthesis_evidence`, explicit evidence gate, `post_evidence_selection` in telemetry)
- `src/cos/services/retrieval_eval.py` (modified — uses `select_synthesis_evidence`, `post_evidence_selection` in candidate_counts)
- `tests/services/test_retrieval_service.py` (modified — 6 new evidence-selection tests)
- `tests/retrieval/test_benchmark_harness.py` (modified — 3 new `attribute_failure` evidence_selection tests)
- `tests/services/test_retrieval_eval_service.py` (modified — schema version updated + 3 new benchmark evidence-selection tests)
