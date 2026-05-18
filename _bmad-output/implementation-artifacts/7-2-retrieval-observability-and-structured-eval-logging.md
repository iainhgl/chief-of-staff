# Story 7.2: Retrieval Observability & Structured Eval Logging

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want retrieval and synthesis runs to emit structured metrics and traceable benchmark output,
So that I can understand which provider, latency, and evidence path produced a result.

## Acceptance Criteria

1. **Given** a retrieval query runs,
   **When** logs are emitted,
   **Then** they include query type, candidate counts, filtered evidence counts, latency, and the model/provider used for synthesis without logging sensitive content or secrets.

2. **Given** a benchmark run is executed,
   **When** results are written,
   **Then** each query record includes pass/fail status, timings, and machine-readable metadata that can be compared across runs.

3. **Given** a retrieval regression occurs,
   **When** the operator reviews the benchmark output,
   **Then** they can identify whether the change came from retrieval candidate selection, evidence filtering, citation formatting, or synthesis.

## Tasks / Subtasks

- [x] Task 1: Define a retrieval/eval telemetry contract that is structured, stable, and content-safe (AC: #1, #2, #3)
  - [x] Add an internal telemetry shape for retrieval runs that captures, at minimum:
    - [x] trace or run identifier
    - [x] query classification / query mode
    - [x] keyword candidate count
    - [x] semantic candidate count
    - [x] merged candidate count
    - [x] post-threshold / post-pruning / post-lineage counts as applicable
    - [x] retrieval latency
    - [x] synthesis latency and total latency where synthesis runs
    - [x] configured synthesis provider and model
    - [x] final outcome / degraded outcome
  - [x] Keep the schema additive and machine-readable so benchmark JSON from different runs can be compared without relying on human interpretation
  - [x] Explicitly forbid raw query text, prompt text, chunk content, API keys, tokens, DSNs, or other secrets from entering logs or report artifacts

- [x] Task 2: Instrument the runtime retrieval and synthesis path with structured JSON logging (AC: #1, #3)
  - [x] Extend the retrieval path so the operator can distinguish:
    - [x] candidate selection volume
    - [x] threshold / pruning effects
    - [x] lineage narrowing effects for direct factual queries
    - [x] synthesis success vs degraded failure
  - [x] Reuse the existing retrieval flow rather than issuing a second retrieval query or a second LLM call solely for observability
  - [x] Log provider/model from configured runtime state; do not hardcode Anthropic-specific assumptions into the retrieval service
  - [x] Preserve the existing MCP response envelope and no-relevant-content behavior while adding observability

- [x] Task 3: Enrich benchmark output with per-query trace metadata and regression-attribution fields (AC: #2, #3)
  - [x] Extend `QueryResult`, `BenchmarkReport`, and JSON serialization so each query record includes:
    - [x] pass/fail
    - [x] timings
    - [x] expected vs actual lineage / citations
    - [x] machine-readable stage metadata for retrieval candidate selection, evidence filtering, citation precision, and synthesis
    - [x] an explicit failure category or attribution field when the query fails
  - [x] Include enough run-level metadata to compare reports across runs, such as corpus version and the retrieval settings that materially affect evaluation
  - [x] If benchmark synthesis remains offline/deterministic, represent that explicitly in the metadata instead of implying a live provider call happened

- [x] Task 4: Add regression tests and light operator-facing documentation for the new observability contract (AC: #1, #2, #3)
  - [x] Add retrieval-service tests that assert structured telemetry fields are emitted on success, no-answer, and synthesis-failure paths
  - [x] Add tests proving sensitive content is not logged
  - [x] Add benchmark/report tests covering additive JSON fields, cross-run-comparable metadata, and failure attribution
  - [x] Add CLI test coverage if the benchmark command output changes
  - [x] Update operator docs only where needed so the benchmark/logging behavior is discoverable without bloating setup docs

## Dev Notes

### What This Story Is

Story 7.2 is the observability layer for the retrieval-trust work introduced in Epic 7. Story 7.1 created a repeatable benchmark corpus and harness. Story 7.2 makes that benchmark diagnosable and makes live retrieval runs explainable, so future ranking or citation regressions can be traced to a specific stage instead of being treated as a black-box quality drop.

This story is still about measurement, not about changing ranking semantics. The hardening work itself belongs primarily to Stories 7.3 and 7.4. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

### Why This Story Exists Now

The current platform can already:

1. run hybrid retrieval
2. narrow direct factual queries to one lineage when appropriate
3. execute an offline benchmark harness with pass/fail scoring

But it still has a visibility gap:

- `RetrievalService.query()` only logs on synthesis failure, not on successful retrieval/synthesis runs
- `hybrid_search(...)` computes several ranking/filtering stages internally but does not expose those counts to operators
- benchmark query records currently report pass/fail, timing, lineage, and citations, but not enough stage metadata to isolate where a regression originated

Epic 7 explicitly calls for observability before additional amplification layers like Telegram, web augmentation, or proactive scheduling. This story closes that gap. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Previous Story Intelligence

- Story 7.1 established the benchmark corpus, query taxonomy, and CLI/report path. Story 7.2 should extend those structures rather than creating a second evaluation format or a separate benchmark-only pipeline. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)]
- Story 6.13 introduced thresholding and citation pruning. If operators are meant to diagnose regressions, the telemetry must make those filtering stages visible instead of collapsing them into one final citation list. [Source: [6-13-retrieval-result-thresholding-and-citation-pruning.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-13-retrieval-result-thresholding-and-citation-pruning.md), [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)]
- Story 6.14 added lineage narrowing for direct factual queries. Story 7.2 should record whether that narrowing occurred and how much evidence survived it, because that is now a distinct stage in the retrieval path. [Source: [6-14-single-source-factual-grounding-for-retrieve.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-14-single-source-factual-grounding-for-retrieve.md), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]
- Story 7.1 deliberately kept benchmark execution offline and deterministic. Story 7.2 must preserve that unless it introduces an explicitly deterministic synthesis stub; it must not silently add live provider dependence to the benchmark path. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md)]

### Git Intelligence

- Recent work patterns remain tightly story-scoped with follow-up review patches. Keep 7.2 focused on observability and benchmark metadata, not on retrieval-policy redesign.
- Most recent relevant commit titles:
  - `Add course-change planning artifacts`
  - `Fix story 7.1 benchmark review findings`
  - `Implement story 7.1: retrieval evaluation corpus and benchmark harness`

### Product And Architecture Guardrails

1. **Keep structured logging content-safe.**
   Architecture requires JSON logging to stdout with stable fields. This story adds observability, but it must not log raw query text, prompt text, chunk contents, secrets, OAuth tokens, DSNs, or other sensitive payloads. If correlation is needed, prefer a generated trace id or a derived fingerprint over raw content. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

2. **Preserve the retrieval/MCP contract.**
   The MCP `retrieve` tool must keep returning the standard envelope and the existing no-relevant-content behavior. Observability belongs alongside the flow, not as a contract rewrite. [Source: [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

3. **Do not add live LLM dependence to benchmarking by accident.**
   Benchmark runs must stay deterministic and offline by default. If synthesis metadata is added to benchmark reports, it should either come from configuration/runtime context or from an explicit deterministic stub mode. [Source: [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]

4. **Do not overbuild Story 9's richer provider boundary early.**
   Today `LLMAdapter.complete()` returns only a string, and the current adapter selection already flows through `make_llm_adapter(config)`. For Story 7.2, provider/model metadata can usually come from config/runtime state without redesigning the whole LLM contract. Save broader request/response metadata work for Epic 9 unless a very small additive extension is clearly justified. [Source: [src/cos/llm/adapter.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/adapter.py), [src/cos/llm/factory.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/factory.py), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

5. **Keep attribution tied to real retrieval stages.**
   Operators need to distinguish candidate selection, evidence filtering, citation formatting, and synthesis. Do not fake this by guessing after the fact; capture the counts/verdicts where those stages actually occur. [Source: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py), [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]

6. **Stay inside the existing latency target.**
   The story asks for richer latency and provider visibility, not for extra retrieval passes or model calls. Instrument the existing path rather than duplicating work. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Observability-Specific Implementation Guidance

#### Runtime Retrieval Trace Boundary

- The cleanest stage boundary is likely:
  - query classification / mode decision
  - keyword candidate retrieval
  - semantic candidate retrieval
  - merged candidate set
  - threshold filtering
  - per-source pruning
  - lineage narrowing when applicable
  - synthesis attempt / degraded failure
- Those counts are already implicit in the retrieval path, especially inside `hybrid_search(...)`. Prefer surfacing them through an additive internal result/trace object rather than recomputing them in a second pass.

#### Benchmark Attribution Contract

- Per-query benchmark output should stay easy to diff and machine-compare.
- Good additive fields include:
  - `trace_id`
  - `retrieval_stage`
  - `failure_stage`
  - `query_mode`
  - `candidate_counts`
  - `final_evidence_count`
  - `synthesis_mode` such as `live`, `deterministic_stub`, or `not_run`
- If benchmark synthesis is not run, say so explicitly. Do not imply that a synthesis regression was measured when the harness only exercised retrieval and citation logic.

#### Logging Safety Guardrail

- Raw queries and chunk text may contain sensitive business data.
- A safe compromise is:
  - log query class / query mode
  - log counts and timings
  - log configured provider/model
  - log trace ids / benchmark ids
  - avoid raw source locators in runtime logs unless they are transformed into a clearly safe identifier
- Benchmark fixtures are repo-controlled and synthetic, so benchmark reports can safely retain richer lineage details than production runtime logs.

### Current Code Seams To Use As Source Of Truth

- [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - current query classification helpers
  - current runtime retrieval flow
  - current synthesis failure logging only
  - likely home for retrieval-run telemetry emission

- [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - current candidate gathering, merge, threshold, and pruning stages
  - best place to surface candidate counts and post-filter counts without extra DB work

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - current lineage narrowing helper
  - useful for exposing whether direct factual runs collapsed to one lineage

- [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - current benchmark orchestration
  - current report build/serialization path
  - likely place to attach run ids, per-query stage metadata, and synthesis-mode markers

- [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - current benchmark data models
  - current pass/fail scoring and report schema
  - likely place for explicit failure attribution enums or helper rules

- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - current `benchmark` command surface
  - keep CLI thin; formatting/serialization changes should still be driven by service/model code

- [src/cos/mcp_server/server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py)
  - example of consistent structured JSON logging via `_emit(...)`
  - useful as a style reference, but avoid coupling retrieval services to MCP-server internals

- [src/cos/llm/anthropic.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/llm/anthropic.py)
  - current provider adapter behavior
  - confirms that provider/model context is configured separately from retrieval logic

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
  - [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
  - [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)

- Primary test files:
  - [tests/services/test_retrieval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_service.py)
  - [tests/retrieval/test_search.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_search.py)
  - [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)
  - [tests/retrieval/test_benchmark_harness.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_benchmark_harness.py)
  - [tests/cli/test_cli_benchmark.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_benchmark.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py) if the retrieval surface or degraded-path behavior changes

- Optional light-touch docs:
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only if a short operator note is needed for interpreting benchmark artifacts
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) only if benchmark/logging usage needs a discoverable command reference

- Avoid by default:
  - changes to `src/cos/connectors/*`
  - changes to `src/cos/worker.py`
  - schema migrations
  - role-pack YAML changes
  - broad LLM adapter redesign ahead of Epic 9
  - any live Gmail, Calendar, or external benchmark dependency

### Testing Requirements

- Add retrieval-service coverage proving:
  - success-path telemetry contains query class, counts, latencies, and provider/model metadata
  - no-answer telemetry is emitted cleanly
  - synthesis-failure telemetry still preserves the degraded path and identifies synthesis as the failing stage

- Add safety tests proving logs/reports do not contain:
  - raw query text
  - prompt text
  - chunk content
  - API keys / OAuth secrets / DSNs

- Add benchmark/report coverage proving:
  - per-query JSON includes additive machine-readable metadata
  - run-level metadata remains stable enough for cross-run comparison
  - failures can be attributed to a concrete stage category
  - offline/deterministic synthesis state is explicit when no live synthesis occurred

- Keep tests deterministic and local:
  - patch embedding calls as in Story 7.1
  - do not require live LLM providers for benchmark tests
  - do not introduce flaky wall-clock assertions beyond bounded latency field presence/shape checks

### Project Structure Notes

- The current project already separates retrieval orchestration, search mechanics, benchmark models, and CLI surface cleanly enough for this story. Preserve that separation.
- If a shared telemetry helper is useful, prefer a small additive module under `src/cos/retrieval/` or `src/cos/services/` rather than scattering ad hoc dict-building across unrelated files.
- Keep the benchmark schema version-controlled and additive. A future operator should be able to compare Story 7.1-style and Story 7.2-style reports without guessing which fields changed meaning.

### References

- Epic 7 definition and Story 7.2 acceptance criteria: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- Product rationale for retrieval-trust-first sequencing: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- Architecture logging contract and provider-portability constraints: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- Existing benchmark harness story and current implementation baseline: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md)
- Current retrieval service: [src/cos/services/retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- Current search pipeline: [src/cos/retrieval/search.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/search.py)
- Current citation helpers: [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
- Current benchmark models/service: [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)

## Dev Agent Record

### Agent Model Used

gpt-5.4

### Debug Log References

### Completion Notes List

- Story context created on 2026-05-18.
- Implementation complete 2026-05-18. 152 tests pass (26 CLI + 126 DB-backed).
- `hybrid_search_with_trace()` added to `search.py` as new function; `hybrid_search()` kept as thin wrapper for backward compat.
- `SearchStats` dataclass introduced in new `src/cos/retrieval/telemetry.py`.
- Structured JSON telemetry emitted via `_emit_retrieval_log()` in `retrieval.py` on all three paths: success, no_content, synthesis_degraded.
- Content-safety enforced: `query_mode` logs only a safe enum token, never raw query text or chunk content.
- Benchmark schema version bumped to "7.2"; `QueryResult` and `BenchmarkReport` extended with observability fields.
- `attribute_failure()` maps (verdict, candidate_counts) → concrete stage name for regression triage.

### File List

- `_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md`
- `src/cos/retrieval/telemetry.py` (new — `SearchStats` dataclass)
- `src/cos/retrieval/search.py` (modified — added `hybrid_search_with_trace`)
- `src/cos/retrieval/benchmark.py` (modified — new fields on `QueryResult`/`BenchmarkReport`, `attribute_failure`, schema version 7.2)
- `src/cos/services/retrieval.py` (modified — structured JSON telemetry on all result paths)
- `src/cos/services/retrieval_eval.py` (modified — uses `hybrid_search_with_trace`, enriched report serialization)
- `tests/retrieval/test_benchmark_harness.py` (modified — 11 new tests for observability fields and `attribute_failure`)
- `tests/services/test_retrieval_service.py` (modified — updated all patches + 6 new telemetry/content-safety tests)
- `tests/services/test_retrieval_eval_service.py` (modified — updated all patches + 7 new benchmark metadata tests)
