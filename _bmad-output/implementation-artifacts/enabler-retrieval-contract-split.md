# Story EN.2: Retrieval Contract Split — Pure `retrieve` and Synthesis `answer`

Status: review

## Story

As Iain, the CoS operator and platform maintainer,
I want the retrieval surface split into a pure `retrieve` (cited evidence, no generated prose) and a synthesis `answer` (cited prose),
so that the platform's context layer is portable — any external harness can reason over grounded evidence with its own model — while thin clients (CLI, Telegram) still get a finished cited answer.

## Acceptance Criteria

1. `RetrievalService` exposes `retrieve()` returning a `RetrievalResult` (cited evidence + synthesis context + strategy + outcome) and performing no LLM call.
2. `RetrievalService` exposes `answer()` returning a `CitedResponse` (retrieve + synthesise), behaviourally identical to the previous `query()` including telemetry.
3. The MCP `retrieve` tool returns cited chunks (`data.chunks` with content, plus `strategy` and `outcome`) and emits to no output channel.
4. A new MCP `answer` tool returns synthesised prose + citations and routes egress through `OutputService` exactly as the previous `retrieve` tool did.
5. Internal thin clients (Telegram bot; CLI where applicable) call `answer`; their behaviour is unchanged.
6. Telemetry: the `answer` path emits a single combined (retrieval + synthesis) record as before; the pure `retrieve` path emits a retrieval-only record with `synthesis_latency_ms = null`.
7. No real external callers exist yet, so `retrieve` becoming pure is a clean rename, not a managed break. `query()` is retained as a deprecated alias of `answer()` to avoid churn in the existing test suite.
8. The existing test suite continues to pass (excluding two pre-existing `compare`-query failures that also fail on `main`).

## Tasks / Subtasks

- [x] Service split (AC: 1, 2, 6, 7)
  - [x] Add `RetrievalResult` dataclass to `src/cos/retrieval/citations.py`.
  - [x] Extract `_retrieve_with_telemetry()` (search → strategy routing → evidence selection) from `query()`.
  - [x] Add `retrieve()` (pure) emitting a retrieval-only telemetry record on the evidence-bearing path.
  - [x] Add `answer()` (retrieve + synthesise) preserving the single combined telemetry record.
  - [x] Keep `query()` as a deprecated alias of `answer()`.
- [x] MCP tool split (AC: 3, 4)
  - [x] Make the `retrieve` tool pure — return `data.chunks` + `strategy` + `outcome`, no `OutputService.send`.
  - [x] Add an `answer` tool — synthesised prose + citations, egress via `OutputService`.
  - [x] Factor `_citation_dict` helper to share citation shaping.
- [x] Repoint thin clients (AC: 5)
  - [x] `src/cos/connectors/telegram_bot.py` calls `retrieval_service.answer(...)`.
- [x] Tests (AC: 1–8)
  - [x] Add `retrieve()` service tests (evidence without LLM, no-content outcome, retrieval-only telemetry, `query` alias).
  - [x] Split MCP tool tests into pure-`retrieve` (chunks, no egress) and `answer` (prose, egress).
  - [x] Repoint Telegram tests from `retrieval.query` to `retrieval.answer`.
- [x] Documentation & traceability (AC: all)
  - [x] Add a Retrieval Contract Boundary + implementation note to `architecture.md`.
  - [x] Mark the source design note Decisions section as implemented and link this story.
  - [x] Register `enabler-retrieval-contract-split` in `sprint-status.yaml`.

### Review Findings

Independent sub-agent code review (2026-06-10): **no blocking (A) issues.** Reviewer traced all five telemetry branches against `main`, confirmed pure-path purity (no LLM, no egress), egress/error-envelope parity, and `assert ctx is not None` soundness; ran the suites.

- [x] [Review][Patch] (C) No test asserted the pure `retrieve()` success path emits exactly one telemetry record (riskiest deferred-logging code). Added `test_retrieve_emits_exactly_one_telemetry_record` and `test_answer_emits_exactly_one_telemetry_record` (record-count assertions). [tests/services/test_retrieval_service.py]
- [ ] [Review][NoAction] (B) `answer` tool's `Synthesis failed` envelope drops citations despite the detail string saying "citations may still be available." Confirmed **identical to the original `query` tool** — not a regression. Left as-is for parity; revisit only if the detail text is to be honoured.
- [ ] [Review][NoAction] (C) Several synthesis tests retain `test_query_*` names / call `query()` (the alias). Harmless; exercises the alias path.

## Dev Notes

This is a standalone architectural enabler created after Epic 8 / EN.1. It implements only the **contract split** (Stories A+B) from the source design note. The **pluggable `Retriever` seam** (Stories C+D — vector/file/graph/fusion mechanisms) is deliberately **not** in scope and remains future work; the design note remains the reference for it.

Order-independent: this enabler has no hard dependency on any epic and blocks none. It strengthens existing retrieval FRs (FR11–FR14, FR21, FR36) without closing a new FR.

Key implementation choices:
- **Single combined telemetry on the answer path is preserved** via an internal `_retrieve_with_telemetry()` that defers logging on the evidence-bearing path. Terminal outcomes (no candidates, no surviving evidence, retrieval failure) still emit and return inside the retrieval phase, exactly as before. This keeps all existing telemetry tests green and adds a retrieval-only emit only for the direct pure-`retrieve` path.
- **`query()` kept as a deprecated alias** of `answer()`. There are no real external callers, but the alias avoids churning ~40 existing `service.query(...)` test call sites. New code should call `answer` (prose) or `retrieve` (evidence).
- The `retrieve` MCP tool returns chunk **content** inline alongside citations so a calling harness has everything needed to reason and re-cite.

Egress control is unchanged: only `answer` emits to a channel, via `OutputService` / `OutputRouter` (FR21, FR36). Pure `retrieve` returns a tool result and opens no output path.

Two pre-existing test failures (`test_query_citations_match_pruned_evidence_set` and the `compare X and Y` parametrisation of `test_query_adds_query_type_instruction_to_prompt`) fail identically on `main` and are unrelated to this change (multi-source `compare` queries yield empty evidence with the synthetic test chunks). EN.1's completion notes already recorded the first as pre-existing.

DB-backed integration tests (store/migrations, worker) error without a running Postgres and are environmental, not affected by this change.

## References

- Source design note: `_bmad-output/planning-artifacts/retrieval-contract-and-pluggable-retriever-design-2026-06-10.md`
- Motivating article: `docs/build-configure-use.md`
- Architecture boundaries + implementation notes: `_bmad-output/planning-artifacts/architecture.md`
- Retrieval service: `src/cos/services/retrieval.py`
- MCP tools: `src/cos/mcp_server/tools.py`
- Sprint tracker: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

claude-opus-4-8

### Completion Notes List

- Standalone enabler EN.2 implemented 2026-06-10. Implements the contract split only; the pluggable `Retriever` seam from the design note is deferred.
- `RetrievalResult` added to `citations.py`; `RetrievalService` now exposes `retrieve()`, `answer()`, and a deprecated `query()` alias.
- MCP `retrieve` tool is now pure (cited chunks, no egress); new `answer` tool carries the previous synthesis-and-egress behaviour.
- Telegram bot repointed to `answer()`.
- Test results on this branch: 202 passed in the retrieval/MCP/telegram suites (plus 2 pre-existing `compare`-query failures shared with `main`). Full suite: 423 passed, 2 pre-existing failures, 344 DB-connection errors (no Postgres in the dev sandbox — environmental).
- `ruff check` clean on all changed source files. Pre-existing E501 line-length debt in `tests/services/test_retrieval_service.py` (9 lines) is also present on `main` and was left untouched.

### File List

- `src/cos/retrieval/citations.py` (RetrievalResult added)
- `src/cos/services/retrieval.py` (retrieve/answer/query split)
- `src/cos/mcp_server/tools.py` (retrieve pure + answer tool)
- `src/cos/connectors/telegram_bot.py` (call answer)
- `tests/services/test_retrieval_service.py`
- `tests/mcp_server/test_tools.py`
- `tests/connectors/test_telegram_bot.py`
- `_bmad-output/planning-artifacts/architecture.md` (boundary + note)
- `_bmad-output/planning-artifacts/retrieval-contract-and-pluggable-retriever-design-2026-06-10.md` (design note)
- `_bmad-output/implementation-artifacts/enabler-retrieval-contract-split.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-06-10 | 1.0 | Initial standalone enabler story created from retrieval contract design note; contract split implemented. | Claude (Opus 4.8) |
