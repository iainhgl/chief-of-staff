# Story 6.12: Documentation and Housekeeping

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want setup, migration, connector, and recovery documentation updated to match the hardened identity model,
So that the backlog and docs stay consistent with the actual strategy.

## Acceptance Criteria

1. **Given** the Epic 6 work is complete,
   **When** the documentation set is reviewed,
   **Then** it explains the canonical identity model, the four ingest outcomes, exact-byte deduplication behaviour, and how `source_alias` appears in listings and citations.

2. **Given** connector setup documentation is updated,
   **When** it is reviewed,
   **Then** it covers OAuth setup, token storage, connector-specific provenance locators, job processing, and degraded-mode recovery steps.

3. **Given** migration/backfill documentation is updated,
   **When** an operator follows it on an existing Phase 1 instance,
   **Then** the instructions are sufficient to migrate, validate, and recover without reading implementation code.

4. **Given** Epic 6 introduced any divergence from `architecture.md`,
   **When** the architecture and planning artifacts are reviewed together,
   **Then** the documented model, story ordering, and operator workflow are consistent across `architecture.md`, `epics.md`, and connector documentation.

## Tasks / Subtasks

- [x] Task 1: Refresh operator-facing setup and querying documentation to the Epic 6 provenance contract (AC: #1, #2)
  - [x] Update [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) so `cos docs`, `list_documents`, and `retrieve` describe `source_alias`, `source_locator`, and citation fields that match current CLI/MCP behaviour
  - [x] Replace any stale guidance that still presents `source_path` as the primary operator-facing document or citation field; if legacy fallback behaviour is worth mentioning, frame it explicitly as pre-migration compatibility rather than the normal Epic 6 contract
  - [x] Document the four deterministic ingest outcomes in operator language: `new_content`, `unchanged`, `changed_content`, and `new_source_known_content`
  - [x] Make exact-byte deduplication expectations clear across local files, Gmail attachments, Google Calendar artifacts, and MCP note ingest

- [x] Task 2: Align connector setup, provenance, queueing, and recovery documentation with the landed Epic 6 implementation (AC: #2)
  - [x] Keep [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) aligned with the current OAuth flow in `cos auth gmail` / `cos auth calendar`, including host-only execution, token paths in `tokens/`, and refresh/re-authorisation guidance
  - [x] Add or tighten connector provenance examples so Gmail, Calendar, and MCP note flows show realistic locator patterns and readable aliases
  - [x] Explain that Gmail and Calendar sync enqueue background ingest jobs and that the `worker` service drains them, including the degraded-mode expectation that connector failures must not take down the MCP/retrieval path
  - [x] Preserve the host-vs-container command boundary throughout the docs so operators do not run `cos restart` or browser auth from the wrong environment

- [x] Task 3: Update migration/backfill and recovery guidance for existing Phase 1 instances (AC: #3)
  - [x] Revise [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md) so the baseline, migrate, validate, rerun, and rollback steps match the current canonical schema and CLI behaviour
  - [x] Replace stale validation language that still assumes `source_path`-centric listings or asks the operator to infer correctness from implementation details
  - [x] Ensure recovery guidance explains when rerunning `cos migrate` is sufficient, when SQL inspection is appropriate, and what evidence to capture before any destructive manual repair
  - [x] Keep the migration guide self-sufficient for an operator moving from a Phase 1 local-document instance to the Epic 6 connected-ingestion model

- [x] Task 4: Reconcile top-level and planning-document drift introduced by Epic 6 (AC: #1, #4)
  - [x] Update [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) so the product summary, current-capabilities section, and tool-field descriptions reflect Epic 6 rather than stopping at Epic 5
  - [x] Remove stale statements implying connected sources are only planned or that connector modules remain stubs when the repo now includes working Gmail, Calendar, worker, and `ingest_document` paths
  - [x] Review [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), and connector/operator docs together; make only the minimal consistency edits needed if genuine divergence remains
  - [x] Keep story-order or planning-artifact edits tightly scoped to Epic 6 consistency work; do not expand into a broader product replan

- [x] Task 5: Cross-check the final documentation set against the actual code and implementation seams (AC: #1, #2, #3, #4)
  - [x] Verify all commands, field names, and response-shape claims against current code in [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py) and [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
  - [x] Use [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) as the authoritative live UAT companion created in Story 6.11, and align setup/migration/README language around it rather than duplicating or contradicting it
  - [x] Confirm the final doc set presents one coherent operator workflow: configure, authenticate, migrate if needed, sync connected sources, validate provenance, recover from degraded states
  - [x] Keep implementation documentation-focused by default; avoid `src/` or `tests/` changes unless a concrete product/doc mismatch is discovered and cannot be resolved by documentation alone

## Dev Notes

### What This Story Is

Story 6.12 is the Epic 6 documentation consolidation pass that follows the live UAT work from Story 6.11. The purpose is to make the operator-facing docs, top-level repo summary, and any still-relevant planning notes match the connected-ingestion system that now exists.

The default deliverable is documentation only. This story should not reopen connector implementation, schema design, or retrieval behaviour unless the docs reveal a specific factual mismatch that cannot be resolved without a minimal product fix.

### Current Drift To Correct

The current repo already shows concrete documentation drift that this story should close:

1. [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) still describes `cos docs`, `list_documents`, and retrieval citations in `source_path` terms, while current CLI and MCP responses expose `source_alias` and `source_locator` as the primary contract.
2. [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) still labels the product as “Current Capabilities (Epic 5)”, says connected sources are only planned, and describes MCP retrieval/listing fields using `source_path`.
3. [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md) correctly explains the canonical tables at a high level, but still needs a stronger operator-facing validation/recovery path that reflects the Epic 6 document listing contract and current CLI workflow.
4. [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) has become the most current Epic 6 source of truth, so the rest of the docs should align around it rather than contradict it.

### Previous Story Intelligence

- Story 6.11 deliberately limited itself to the UAT runbook and explicitly reserved broader documentation consolidation for Story 6.12.
- Story 6.10 established `ingest_document`, stable external IDs, and the warning-only near-duplicate layer, so documentation here must describe those outcomes accurately without implying a separate note-ingest model.
- Stories 6.8 and 6.9 established the connector provenance patterns and worker-backed job flow for Gmail and Calendar. The docs should describe those patterns in operator language rather than inventing new abstractions.
- Story 6.5 established the migration/backfill and recovery baseline for older Phase 1 stores. The migration guide should build on that work and stay safe to rerun.
- Story 6.6 is still marked `review` in [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml). Treat the code on the current branch as the source of truth, not any assumed-but-unmerged review patch.

### Product And Architecture Guardrails

1. **Canonical identity is separate from provenance.**
   `content_blobs` are deduplicated by SHA-256, `documents` represent logical lineage, and `sources` capture where content came from. Do not let filenames, Gmail locators, calendar locators, or MCP note locators read like canonical identity keys in the docs. [Source: _bmad-output/planning-artifacts/architecture.md]

2. **The four ingest outcomes are now the cross-channel contract.**
   Documentation should consistently describe `new_content`, `unchanged`, `changed_content`, and `new_source_known_content` across local CLI ingest, connected sources, and MCP note capture. [Source: _bmad-output/planning-artifacts/architecture.md]

3. **Operator-facing provenance is `source_alias` + `source_locator`.**
   Current CLI and MCP responses have already moved to alias/locator-based outputs; `source_path` only remains as a fallback for legacy records that have not been backfilled. Docs should treat that as compatibility behaviour, not the normal model. [Source: src/cos/cli.py, src/cos/mcp_server/tools.py, src/cos/store/db.py]

4. **Connector sync is queue-backed and fault-isolated.**
   Gmail and Calendar sync enqueue jobs that the `worker` service processes later. Connector degradation should be documented as non-fatal to the MCP and retrieval path. [Source: _bmad-output/planning-artifacts/architecture.md, docs/manual-testing.md]

5. **Token lifecycle is a real operator concern.**
   Gmail and Calendar OAuth tokens live in `tokens/`, refresh automatically when valid, and must survive restart/recovery without being committed. [Source: docs/setup.md, _bmad-output/planning-artifacts/architecture.md]

6. **Keep this story as documentation housekeeping, not feature expansion.**
   No Telegram work, no scheduler work, no new connector implementation, and no broad rewrite of planning artifacts beyond minimal Epic 6 consistency repairs.

### Current Code Seams To Use As Source Of Truth

- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - `cos auth gmail`
  - `cos auth calendar`
  - `cos sync gmail`
  - `cos sync calendar`
  - `cos migrate`
  - `cos docs`
  - `cos restart`

- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
  - `retrieve` citation fields: `source_alias`, `source_locator`, `document_version_id`, `chunk_index`, `score`
  - `list_documents` document fields: `id`, `source_alias`, `source_locator`, `ingested_at`, `current_version`, `chunk_count`
  - `ingest_document` response fields and near-duplicate warning behaviour

- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
  - canonical-source fallback behaviour for legacy `source_path` records
  - backfill/recovery semantics that the migration docs should explain safely

- [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
  - live Epic 6 operator/UAT reference for provenance checks, dedupe proof, restart validation, and connected-source recovery expectations

### Suggested File Touchpoints

- Primary:
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
  - [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md)
  - [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md)

- Likely reference or light-touch alignment:
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
  - [_bmad-output/planning-artifacts/architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
  - [_bmad-output/planning-artifacts/epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)

- Only if a genuine contradiction is found:
  - other connector-facing documentation artifacts that still describe pre-Epic-6 behaviour

### Testing Requirements

- This is primarily a documentation-validation story, so new automated tests are not required by default.
- Verification should be done by cross-checking documentation claims against code and existing tests, especially:
  - [tests/cli/test_cli_docs.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_docs.py)
  - [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py)
  - connector service tests that show real `source_alias` / `source_locator` patterns
- If the developer discovers a doc/code mismatch, prefer correcting the docs unless the mismatch reveals an actual product bug with a narrow, justified fix.
- The final review should confirm that an operator can follow the updated docs end-to-end without needing to inspect `src/`.

### Project Structure Notes

- Operator setup, query guidance, and recovery steps live in [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md).
- Migration/backfill and repair guidance lives in [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md).
- Live Epic 6 UAT and smoke-test validation lives in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md).
- The top-level product summary and capability snapshot live in [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md).
- Story 6.12 should make those surfaces coherent; it should not duplicate the entire UAT guide into every document.

### References

- [Epic 6 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for canonical identity, provenance, ingest outcomes, queueing, and token handling](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD references for connected sources, note capture, restart, and OAuth token persistence](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Sprint change proposal that introduced the Epic 6 identity hardening and documentation impact](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-05.md)
- [Previous story: 6.11 operator validation and Epic 6 UAT guide](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-11-operator-validation-connected-sources-live.md)
- [Current setup guide](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [Current migration guide](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md)
- [Current Epic 6 manual-testing guide](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- [Current top-level README](/Users/iain.livingstone/Development/CoS/cos/README.md)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- docs/setup.md: replaced `SOURCE PATH` with `SOURCE ALIAS` in `cos docs` table; updated `cos docs --json`, `retrieve` citations, and `list_documents` fields from `source_path` to `source_alias`/`source_locator`; added "Sync Connected Sources" section with `cos sync gmail`/`cos sync calendar`, worker job processing, degraded-mode, and realistic provenance example table using verified locator formats from code; added "Ingest Outcomes" table with four deterministic outcomes and cross-source deduplication explanation; added `ingest_document` MCP tool documentation; updated platform service count from three to four; added connector enablement config example (`connectors:` block)
- docs/migration.md: replaced `docker compose run cos cos ...` with `docker compose exec cos uv run cos ...` for consistency with Epic 6 operator workflow; updated verification step to check `source_alias`/`source_locator` fields in JSON output; rewrote diagnostic SQL block to remove `d.source_path` reference; added explicit guidance on rerun-vs-inspect decision and log-capture before manual repair
- README.md: updated "Current Capabilities (Epic 5)" to "Current Capabilities (Epic 6)"; expanded capabilities list with auth/sync/migrate/ingest_document/worker/deduplication entries; updated `retrieve` citations and `list_documents` fields; updated project structure to remove stubs annotation from `connectors/`, add `worker`, `tokens/`, and `migration.md`; removed stale "planned for Epic 6" statement
- _bmad-output/planning-artifacts/architecture.md: added "Epic 6 Implementation Notes" section (8 deviations) covering four-service platform, working connectors, source_alias/source_locator contract, four ingest outcomes, ingest_document tool, auth/sync CLI sub-commands, cos migrate command, and Epic 2 Deviation 4 resolution
- _bmad-output/planning-artifacts/epics.md: updated connectors stub note to reflect working connectors; added `ingest_document` to MCP tool list
- All 374 unit tests pass; no regressions

### File List

- docs/setup.md
- docs/migration.md
- README.md
- _bmad-output/planning-artifacts/architecture.md
- _bmad-output/planning-artifacts/epics.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/6-12-documentation-and-housekeeping.md

## Change Log

- 2026-05-07: Updated docs/setup.md, docs/migration.md, README.md, architecture.md, epics.md, sprint-status.yaml to reflect Epic 6 canonical identity model, connected-source capabilities, and four-service platform (Date: 2026-05-07)
