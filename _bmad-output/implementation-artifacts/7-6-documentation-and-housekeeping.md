# Story 7.6: Documentation & Housekeeping

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Iain (operator and platform maintainer),
I want the retrieval trust layer documented clearly,
So that future BMAD workflows and implementation stories treat benchmarking and observability as part of the platform contract rather than optional extras.

## Acceptance Criteria

1. **Given** the retrieval trust work is complete,
   **When** `architecture.md` and `architecture-diagrams.md` are reviewed,
   **Then** they describe the evaluation harness, evidence-selection contract, and sequenced placement of retrieval hardening before Telegram/web/scheduler features.

2. **Given** operator-facing docs are reviewed,
   **When** they are updated,
   **Then** they explain how to run the benchmark harness, where reports are stored, and how to interpret retrieval regressions.

3. **Given** all Epic 7 documents are cross-checked,
   **When** reviewed together,
   **Then** benchmark terminology, evidence-selection rules, and observability fields are consistent across PRD, architecture, epics, and sprint tracking.

## Tasks / Subtasks

- [x] Task 1: Refresh operator-facing docs so Epic 7 retrieval trust is discoverable without reopening the whole runbook (AC: #2, #3)
  - [x] Update [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) from `Current Capabilities (Epic 6)` to the Epic 7 baseline and surface the benchmark harness as a first-class platform capability rather than an internal implementation detail.
  - [x] Fix the stale [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) project-structure note that still labels [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) as an Epic 6 guide even though Story 7.5 turned it into the Epic 7 retrieval-trust regression runbook.
  - [x] Add a short benchmark-discoverability section to [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) that points operators to the authoritative Epic 7 runbook in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), including the host-run `--config` requirement and the saved JSON report path.
  - [x] Keep [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) as the single deep runbook for benchmark execution and regression interpretation; only edit it where terminology or field-name drift is discovered, not to duplicate the whole procedure into other docs.

- [x] Task 2: Align benchmark corpus and report terminology with the current harness contract (AC: #2, #3)
  - [x] Update [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md) so it matches the actual CLI behavior: gold queries are the default authoritative gate, while stress/fuzz cases are opt-in diagnostics via `--include-fuzz`, not automatically part of every release-gating run.
  - [x] Document the `generated/manifest.yaml` fixture fields added by Story 7.4, especially `chunk_count` and `citation_chunk_index`, so the benchmark corpus README reflects the current multi-chunk bounded-context fixture model.
  - [x] Cross-check operator-facing explanations of report fields against the actual JSON emitted by [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py) and [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), including `actual_lineage`, `answerability_verdict`, `failure_stage`, `candidate_counts`, `expansion_mode`, `synthesis_mode`, and `per_class`.
  - [x] Preserve the current scoring semantics in documentation: explain the current harness truthfully instead of rewriting the benchmark contract in prose.

- [x] Task 3: Add Epic 7 implementation notes to the planning architecture and diagrams (AC: #1, #3)
  - [x] Add an `## Epic 7 Implementation Notes` section to [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md) after Epic 6 so future agents treat the retrieval-trust layer as implemented reality rather than still-in-flight intent.
  - [x] Capture the actual benchmark surface in those notes: `cos benchmark`, `--config`, `--corpus`, optional `--include-fuzz`, saved JSON output, repo-local corpus fixtures, and the current host-vs-container execution seam.
  - [x] Document the implemented retrieval-trust contract in architecture terms: evidence selection happens after thresholding/pruning, direct factual classes remain single-lineage by default, document-first bounded-context recovery applies to `single_doc_interpretation`, and benchmark observability fields are additive rather than silent contract rewrites.
  - [x] Add a focused Epic 7 benchmark / release-gate diagram to [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md) instead of a broad rewrite, and keep the existing delivery-sequence diagrams explicit that Epic 7 hardening lands before Telegram, web augmentation, and proactive scheduling.

- [x] Task 4: Cross-check planning artifacts and sprint tracking for minimal but real consistency fixes (AC: #1, #3)
  - [x] Review [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), and [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml) together for terminology drift around benchmark gating, observability, evidence selection, and bounded-context retrieval.
  - [x] Make only the minimum wording edits needed where real drift exists; do not use Story 7.6 as a pretext for a broader roadmap rewrite, channel redesign, or PM re-planning.
  - [x] Keep Epic 7 sequencing language consistent everywhere: retrieval trust is the gate before Epics 8 through 11, and advanced retrieval experiments remain explicitly later and benchmark-gated.

- [x] Task 5: Verify every documentation claim against code and shipped artifacts, keeping the story docs-first by default (AC: #1, #2, #3)
  - [x] Treat [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py), [src/cos/retrieval/strategy.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/strategy.py), and [src/cos/retrieval/context_expansion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/context_expansion.py) as the source of truth for benchmark/report field names and retrieval-trust behavior.
  - [x] Reuse the committed [7-5-benchmark-report.json](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-benchmark-report.json) and the Story 7.5 runbook as concrete evidence of the current operator-facing contract instead of inventing a second example path.
  - [x] If a mismatch is documentation-only, fix the docs. Only change code or tests if a factual contradiction cannot be resolved any other way, and keep any such fix tightly scoped to the benchmark/documentation surface.

## Dev Notes

### What This Story Is

Story 7.6 is the Epic 7 documentation-consolidation pass. The retrieval-trust work itself already landed across Stories 7.1 through 7.5:

1. Story 7.1 created the benchmark corpus and harness.
2. Story 7.2 added structured retrieval and benchmark observability.
3. Story 7.3 hardened evidence selection and citation precision.
4. Story 7.4 added document-first bounded-context recovery.
5. Story 7.5 turned the benchmark into an explicit operator regression gate with a saved JSON artifact and runbook.

The remaining job is to make the repo's docs and planning artifacts reflect that implemented baseline clearly enough that future BMAD story generation and implementation do not treat benchmarking, observability, or retrieval hardening as optional side work. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md), [7-3-retrieval-evidence-selection-and-citation-precision-hardening.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md), [7-4-document-first-retrieval-and-context-expansion.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-4-document-first-retrieval-and-context-expansion.md), [7-5-operator-validation-retrieval-trust-regression-suite.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-operator-validation-retrieval-trust-regression-suite.md)]

This is primarily a documentation story. Default scope is docs and planning artifacts. Do not reopen retrieval policy, benchmark scoring, or corpus structure unless a concrete factual contradiction is found that cannot be resolved through documentation alone. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

### Current Drift To Correct

The repo already shows several concrete Epic 7 documentation gaps:

1. [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) still presents the current baseline as Epic 6 and still labels [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) as an Epic 6 guide, even though Story 7.5 made it the Epic 7 retrieval-trust runbook.
2. [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) explains setup, querying, and operations, but does not surface `cos benchmark`, the host-side `--config` requirement, or where benchmark reports are written.
3. [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md) contains Epic 1 through Epic 6 implementation notes, but no Epic 7 section capturing the benchmark harness, observability fields, evidence-selection contract, or bounded-context retrieval behavior as the actual system baseline.
4. [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md) shows Epic 7 only at the delivery-sequence level; it does not yet diagram the benchmark/release-gate flow or how retrieval hardening sits in front of later Telegram/web/scheduler layers.
5. [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md) still says stress/fuzz cases are included in full benchmark runs, which conflicts with the current CLI and manual-testing contract where fuzz is opt-in via `--include-fuzz` and gold is the authoritative gate.
6. That same corpus README also predates Story 7.4's multi-chunk fixture additions and does not document `chunk_count` or `citation_chunk_index` in `generated/manifest.yaml`, despite those fields now being part of the supported corpus schema. [Source: [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md), [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md), [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md), [tests/fixtures/retrieval_eval/generated/manifest.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/generated/manifest.yaml)]

### Previous Story Intelligence

- Story 7.5 deliberately made [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) the authoritative operator runbook for Epic 7 retrieval-trust validation, added the `--config` flag to `cos benchmark`, and saved the current gold-pass report at [7-5-benchmark-report.json](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-benchmark-report.json). Story 7.6 should build discoverability around that runbook rather than duplicating it. [Source: [7-5-operator-validation-retrieval-trust-regression-suite.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-operator-validation-retrieval-trust-regression-suite.md), [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)]
- Story 7.4 introduced document-first routing and bounded context expansion for `single_doc_interpretation`, and expanded the benchmark corpus/metadata with multi-chunk fixture semantics. Documentation in this story must reflect those terms accurately instead of continuing to describe the corpus as single-chunk only. [Source: [7-4-document-first-retrieval-and-context-expansion.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-4-document-first-retrieval-and-context-expansion.md), [tests/fixtures/retrieval_eval/generated/manifest.yaml](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/generated/manifest.yaml), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)]
- Story 7.3 made evidence selection a distinct post-search stage and expanded benchmark failure attribution accordingly. Story 7.6 should treat `failure_stage` and evidence-selection language as a stable contract to document, not as an open design question. [Source: [7-3-retrieval-evidence-selection-and-citation-precision-hardening.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)]
- Story 7.2 already established additive observability fields and machine-comparable benchmark metadata. This story should preserve that additive framing in docs: no silent redefinition of old fields, no vague "benchmark output includes some metrics" language. [Source: [7-2-retrieval-observability-and-structured-eval-logging.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [src/cos/retrieval/telemetry.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/telemetry.py)]
- Story 7.1 established the three-layer corpus shape. Story 7.6 should keep that structure, but correct the now-stale operator implication that fuzz is always part of the release-gating run. [Source: [7-1-retrieval-evaluation-corpus-and-benchmark-harness.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]

### Git Intelligence

- Recent history shows Epic 7 landing as narrow, story-scoped changes with follow-up fixes rather than broad rewrites:
  - `d760196` - `Fix story 7.5 gold benchmark regressions`
  - `4aef199` - `Implement story 7.5: retrieval trust regression suite`
  - `6e88d94` - `Merge pull request #53 from iainhgl/story/7-4-document-first-retrieval-and-context-expansion`
  - `a5f1852` - `Fix story 7.4 review findings`
  - `753b72d` - `Implement story 7.4: document-first retrieval and context expansion`
- The 7.5 implementation commit touched [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), [tests/cli/test_cli_benchmark.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_benchmark.py), the saved [7-5-benchmark-report.json](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-benchmark-report.json), and the Story 7.5 artifact. That is the baseline this story should document, not redesign. [Source: `git log --oneline -5`, `git show --stat --summary 4aef199`]

### Product And Architecture Guardrails

1. **Keep one authoritative runbook.**  
   [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) should remain the single detailed benchmark-execution and regression-interpretation guide. Use [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) and [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) for discoverability and summaries, not copy-pasted duplicates. [Source: [7-5-operator-validation-retrieval-trust-regression-suite.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-operator-validation-retrieval-trust-regression-suite.md), [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)]

2. **Gold is the gate; fuzz is diagnostic.**  
   The current operator contract is: gold queries are the authoritative gate on a clean benchmark database, while `--include-fuzz` is optional diagnostic coverage. Do not let any doc imply fuzz is always part of release gating unless the CLI and runbook are intentionally changed to make that true. [Source: [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)]

3. **Document the actual benchmark/report fields, not a simplified fantasy.**  
   The current JSON report already includes `schema_version`, `per_class`, `actual_lineage`, `answerability_verdict`, `candidate_counts`, `failure_stage`, and `synthesis_mode`. Docs should use those exact names and current meanings. [Source: [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)]

4. **Preserve the retrieval-trust behavior contract.**  
   Direct-fact, exact-phrase, date/timeline, and single-document interpretation queries still default to one lineage; explicit compare and briefing prompts may span approved multiple sources; `single_doc_interpretation` now uses document-first bounded context expansion; insufficient evidence remains a first-class outcome. Documentation should describe these behaviors consistently across operator docs and planning artifacts. [Source: [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py), [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py), [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)]

5. **Keep Epic 7 sequenced ahead of amplification layers.**  
   Architecture and diagrams must keep retrieval hardening explicitly ahead of Telegram, web augmentation, and proactive scheduling. This sequencing is part of the product contract, not just historical narration. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

6. **Stay docs-first.**  
   Do not change retrieval logic, corpus scoring, or benchmark execution semantics just to make the docs easier. If the current behavior is awkward but factual, document it clearly; if the behavior is wrong, fix it narrowly and prove it with focused tests. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)]

7. **No broader roadmap rewrite.**  
   Story 7.6 can make minimal consistency edits in [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), or [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml) where real drift exists, but it should not turn into a new change-proposal exercise. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml)]

### Current Code Seams To Use As Source Of Truth

- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - `cos benchmark`
  - `--corpus`, `--include-fuzz`, `--output`, `--config`
  - current human-summary and JSON-output behavior

- [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - benchmark orchestration
  - report serialization
  - current candidate-count and expansion metadata
  - current host-side benchmark execution assumptions

- [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - corpus schema
  - valid query classes
  - `QueryResult` / `BenchmarkReport` field names
  - `chunk_count` / `citation_chunk_index` support
  - failure-stage attribution

- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
  - lineage narrowing
  - evidence-selection semantics

- [src/cos/retrieval/strategy.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/strategy.py)
  - query-strategy selection for default, bounded, and multi-source flows

- [src/cos/retrieval/context_expansion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/context_expansion.py)
  - bounded context expansion support used by Story 7.4

- [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
  - current authoritative operator runbook
  - current field glossary and pass criteria

- [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)
  - corpus README that needs Epic 7 terminology alignment

### Suggested File Touchpoints

- Primary:
  - [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md)
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
  - [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)
  - [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
  - [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)

- Likely reference or light-touch alignment:
  - [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
  - [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
  - [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml)
  - [7-5-benchmark-report.json](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-benchmark-report.json)

- Code/tests only if a real contradiction forces it:
  - [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - [src/cos/services/retrieval_eval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
  - [src/cos/retrieval/benchmark.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
  - [tests/cli/test_cli_benchmark.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_benchmark.py)
  - [tests/retrieval/test_benchmark_harness.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_benchmark_harness.py)
  - [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)

### Testing Requirements

- This is primarily a documentation-validation story. New automated tests are not required by default.
- Verification should be done by checking every benchmark/doc claim against current code and existing tests, especially:
  - [tests/cli/test_cli_benchmark.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_benchmark.py)
  - [tests/retrieval/test_benchmark_harness.py](/Users/iain.livingstone/Development/CoS/cos/tests/retrieval/test_benchmark_harness.py)
  - [tests/services/test_retrieval_eval_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_retrieval_eval_service.py)
- If the developer discovers a documentation-only mismatch, fix the docs.
- If the developer discovers a real code/doc contradiction and changes benchmark behavior or report shape, add focused tests for:
  - CLI benchmark flag semantics
  - report field names / JSON serialization
  - corpus README assumptions such as fuzz inclusion or multi-chunk manifest support
- Avoid rerunning or regenerating the benchmark report unless the story intentionally updates the operator example path and can explain why the artifact changed.

### Project Structure Notes

- Top-level product summary and capability snapshot live in [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md).
- Setup, operations, and querying guidance live in [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md).
- Live operator benchmark/UAT guidance lives in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md).
- Benchmark corpus documentation lives alongside the fixtures in [tests/fixtures/retrieval_eval/README.md](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md).
- Planning truth for architecture and sequencing lives in [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), and [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md).
- No repo-level `project-context.md` file was found; the planning artifacts and the Epic 7 implementation chain are the authoritative context for this story.

### References

- [Epic 7 definition and Story 7.6 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD retrieval-trust sequencing](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture baseline and approved post-Epic-6 sequence](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Architecture diagrams baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Story 7.1 benchmark baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-1-retrieval-evaluation-corpus-and-benchmark-harness.md)
- [Story 7.2 observability baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-2-retrieval-observability-and-structured-eval-logging.md)
- [Story 7.3 evidence-selection baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-3-retrieval-evidence-selection-and-citation-precision-hardening.md)
- [Story 7.4 bounded-context baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-4-document-first-retrieval-and-context-expansion.md)
- [Story 7.5 validation runbook baseline](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-operator-validation-retrieval-trust-regression-suite.md)
- [Current operator runbook](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- [Current setup guide](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [Current README](/Users/iain.livingstone/Development/CoS/cos/README.md)
- [Current benchmark corpus README](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/README.md)
- [Current benchmark CLI surface](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
- [Current retrieval eval orchestration](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval_eval.py)
- [Current benchmark schema and scoring rules](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/benchmark.py)
- [Current evidence-selection helpers](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py)
- [Current query-strategy selector](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/strategy.py)
- [Current context-expansion helper](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/context_expansion.py)
- [Current mixed-source fixture manifest](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/generated/manifest.yaml)
- [Current gold benchmark queries](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/gold/core-queries.yaml)
- [Current stress/fuzz benchmark queries](/Users/iain.livingstone/Development/CoS/cos/tests/fixtures/retrieval_eval/stress_fuzz/adversarial.yaml)
- [Current benchmark evidence artifact](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/7-5-benchmark-report.json)
- [Retrieval improvement roadmap research](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/research/cos-retrieval-improvement-roadmap-2026-05-15.md)

## File List

- `README.md` — updated heading to Epic 7, added `cos benchmark` capability, updated `manual-testing.md` project structure label, added benchmark discovery sentence to summary paragraph
- `docs/setup.md` — added "Run the Retrieval Benchmark" section under Platform Operations
- `tests/fixtures/retrieval_eval/README.md` — corrected fuzz-as-default claim to opt-in, added fixture document schema section documenting `chunk_count` and `citation_chunk_index` fields, renamed Manifest Schema section to Query Manifest Schema
- `_bmad-output/planning-artifacts/architecture.md` — added `## Epic 7 Implementation Notes` section after Epic 6 notes, documenting benchmark CLI surface, report fields, retrieval-trust behaviour contract, and corpus structure
- `_bmad-output/planning-artifacts/architecture-diagrams.md` — added `## 7. Epic 7 — Benchmark / Release-Gate Flow` with flowchart diagram and retrieval-trust sequencing diagram; renumbered `OutputRouter` section to `## 8`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — updated `last_updated` comment and `7-6` status to `in-progress` → `review`
- `_bmad-output/implementation-artifacts/7-6-documentation-and-housekeeping.md` — story file (this file)

## Change Log

- 2026-05-19: Story created and sprint status advanced to `ready-for-dev`.
- 2026-05-19: Story implemented — all five tasks complete; status advanced to `review`.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Pre-existing test failure `test_query_citations_match_pruned_evidence_set` in `tests/services/test_retrieval_eval_service.py` was confirmed to exist on `main` before this story started — not caused by any documentation change.

### Completion Notes List

- Story context created on 2026-05-19.
- Sprint status advanced from `backlog` to `ready-for-dev` on 2026-05-19.
- Implementation complete 2026-05-19.

**Task 1** — `README.md` updated from "Epic 6" to "Epic 7" baseline; `cos benchmark` added as first-class CLI capability; project structure note for `manual-testing.md` corrected from "Epic 6 guide" to "Epic 7 retrieval-trust regression runbook". `docs/setup.md` gained a "Run the Retrieval Benchmark" section pointing operators to the host-side execution requirement and the full runbook. `docs/manual-testing.md` left unchanged — it was already accurate.

**Task 2** — `tests/fixtures/retrieval_eval/README.md` corrected the stale "Included in full benchmark runs" claim to the actual opt-in `--include-fuzz` semantics. Added a new Fixture Document Schema section documenting `chunk_count` and `citation_chunk_index` with explanation of multi-chunk seeding semantics introduced in Story 7.4.

**Task 3** — `architecture.md` gained `## Epic 7 Implementation Notes` documenting the full benchmark CLI surface (`--config`, `--corpus`, `--output`, `--include-fuzz`), all JSON report fields (`schema_version`, `per_class`, `actual_lineage`, `answerability_verdict`, `failure_stage`, `candidate_counts`, `expansion_mode`, `synthesis_mode`), the retrieval-trust behaviour contract (single-lineage classes, bounded context expansion, evidence selection, insufficient-evidence outcome, `min_score` thresholding), and the corpus structure including multi-chunk fixtures. `architecture-diagrams.md` gained a focused `## 7. Epic 7 — Benchmark / Release-Gate Flow` section with a flowchart diagram of the benchmark execution and gate decision, plus a sequencing diagram keeping Epic 7 explicitly ahead of Telegram, web, and scheduling.

**Task 4** — `prd.md`, `epics.md`, and `sprint-status.yaml` reviewed for terminology drift; no real drift found that required edits beyond the `sprint-status.yaml` status update.

**Task 5** — All documentation claims verified against `src/cos/cli.py`, `src/cos/services/retrieval_eval.py`, `src/cos/retrieval/benchmark.py` (confirms `BENCHMARK_SCHEMA_VERSION = "7.4"` and all field names), `tests/fixtures/retrieval_eval/generated/manifest.yaml` (confirms `chunk_count: 3` and `citation_chunk_index: 1` for `local-performance-policy.md`). No code or test changes required.
