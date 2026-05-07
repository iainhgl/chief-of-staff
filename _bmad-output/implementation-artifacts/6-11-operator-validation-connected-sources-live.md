# Story 6.11: Operator Validation — Connected Sources Live

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Iain (operator and first user),
I want a smoke test proving canonical identity hardening and live-source ingestion work together,
So that Epic 7 builds on a stable connected-ingestion base.

## Acceptance Criteria

1. **Given** canonical identity migrations and backfill have completed,
   **When** the operator runs the validation checklist,
   **Then** local legacy documents, Gmail ingests, Calendar-derived records, and MCP-ingested notes all surface with valid aliases and provenance links.

2. **Given** a test set includes repeated content across local files, Gmail attachments, and MCP note capture,
   **When** validation completes,
   **Then** exact-byte duplicates share canonical content while retaining distinct source provenance records.

3. **Given** a known source is re-ingested unchanged and then changed,
   **When** validation compares the outcomes,
   **Then** the unchanged case produces a no-op and the changed case produces a new current `document_version` with intact history.

4. **Given** connector authentication tokens remain valid across a container restart,
   **When** the platform restarts,
   **Then** connectors recover without fresh authorisation and the canonical identity rules still produce deterministic ingest outcomes.

## Tasks / Subtasks

- [x] Task 1: Tighten the existing Epic 6 UAT guide in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) instead of rewriting it from scratch (AC: #1, #2, #3, #4)
  - [x] Treat the current Epic 6 runbook as the baseline artifact; verify its commands and expectations against the code and docs that landed in Stories 6.5-6.10
  - [x] Keep this story focused on operator validation only; do not turn it into the broader documentation sweep reserved for Story 6.12
  - [x] Refresh prerequisites and seed-data instructions so the operator can intentionally exercise duplicate, unchanged, and changed-content outcomes across source types

- [x] Task 2: Add explicit connected-source provenance checks covering all live Epic 6 ingest paths (AC: #1)
  - [x] Ensure the runbook verifies visibility of local-file, Gmail, Google Calendar, and MCP-note records through `cos docs` and/or direct SQL inspection
  - [x] Make the operator confirm that user-facing labels are `source_alias` values and connector-specific provenance remains visible via `source_locator`
  - [x] Remove or avoid any legacy validation language that still implies `source_path` is the primary provenance contract for Epic 6 connected sources

- [x] Task 3: Add a deterministic cross-source exact-byte dedupe proof, not just per-source spot checks (AC: #2)
  - [x] Extend the seed-data/setup instructions so the same byte-identical artifact can be observed through at least two distinct source types, ideally all three of `file`, `gmail_attachment`, and `mcp_note`
  - [x] Add a concrete verification query or step showing that duplicate bytes collapse to shared canonical content (`content_blobs` / `document_versions`) while preserving distinct `sources` rows
  - [x] Keep this proof grounded in the current Epic 6 schema: `sources`, `source_versions`, `content_blobs`, and `document_versions`

- [x] Task 4: Add known-source unchanged-versus-changed validation using a stable source identifier (AC: #3)
  - [x] Use one source that can be deterministically retried, preferably `ingest_document` with a stable `metadata.external_id`, so the operator can drive first-ingest, unchanged re-ingest, and changed-content re-ingest from the same provenance identity
  - [x] Document the expected outcomes explicitly: `new_content` (or first-ingest success), `unchanged`, and changed-content/new-version behavior
  - [x] Add a follow-up verification step using `cos docs --versions <document_id>` and/or SQL so the operator can confirm version history remains intact after the changed-content pass

- [x] Task 5: Add restart-and-token-persistence validation after the first successful connected-source ingest pass (AC: #4)
  - [x] Insert a restart step using the current operator-facing restart workflow, then rerun Gmail and Calendar sync without repeating browser auth
  - [x] Verify the token files still exist in `tokens/` and that the post-restart sync path succeeds without fresh authorisation
  - [x] Confirm that immediate post-restart re-syncs still resolve to deterministic no-op / unchanged outcomes where appropriate, rather than creating duplicate source or document state

- [x] Task 6: Refresh pass criteria and cleanup guidance so Epic 6 has a crisp operator gate (AC: #1, #2, #3, #4)
  - [x] Update the pass criteria to name all four required proofs: connected-source visibility, cross-source dedupe, unchanged-vs-changed behavior, and restart/token persistence
  - [x] Keep cleanup steps practical for a personal Google account and local knowledge base
  - [x] Reserve any setup, migration, or architecture-document consolidation beyond the UAT guide for Story 6.12

## Dev Notes

### What This Story Is

Story 6.11 is an operator validation story. The primary implementation deliverable should be an updated [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) that lets Iain run a real Epic 6 smoke test against live connected sources.

The operator performs the live run and decides when the story is done. No automated test expansion is expected here, and `src/` changes should not be the default plan.

### Scope Boundaries

- Default scope: update [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only.
- Reference-only inputs: [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) and [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md).
- Do not treat this story as the broad documentation cleanup for Epic 6. That is Story 6.12.
- Avoid changes to `src/`, `tests/`, connector code, or planning artifacts unless a small, concrete mismatch blocks the UAT script from matching already-landed behavior. If that happens, keep any fix minimal and document why.

### Current Baseline Before This Story

The repo already contains an Epic 6 UAT runbook in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md). Recent git history confirms that Story 6.10 ended with a manual-testing refresh rather than a blank slate:

- `0204d15` — `Finish story 6.10 and refresh Epic 6 UAT guide`
- `0897307` — `Implement story 6.10 ingest_document MCP tool`
- `93eb7c6` — `Implement story 6.9 Google Calendar connector`

That means the developer should audit and strengthen the existing guide, not replace it wholesale.

### Gaps To Close From The Current UAT Guide

The current Epic 6 guide already covers platform startup, Google OAuth, local ingest, Gmail sync, Calendar sync, MCP note ingest, retrieval checks, and final pass criteria. The story should specifically close the gaps that remain against ACs 2-4:

1. The current dedupe proof is mostly Gmail-attachment-centric; Story 6.11 needs a stronger cross-source proof that spans local files, connected sources, and MCP note capture.
2. The current MCP note section proves unchanged retry and new-source-known-content, but it does not explicitly prove changed-content re-ingest for the same source identity with preserved version history.
3. The current runbook does not clearly force a restart-and-resync pass proving token persistence and deterministic outcomes after restart.

### Relevant Existing Implementation Seams

Use these runtime seams and commands as the source of truth when tightening the guide:

- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - `cos migrate`
  - `cos restart`
  - `cos sync gmail`
  - `cos sync calendar`
  - `cos docs`
- [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
  - host-side Google OAuth entrypoints and token lifecycle expectations
- [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
  - Gmail staging and enqueue flow
- [src/cos/services/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/calendar.py)
  - Calendar staging and enqueue flow
- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) and [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)
  - background ingest processing for connected sources
- [src/cos/mcp_server/tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py)
  - `ingest_document` outcomes and envelope shape

### Architecture And Product Guardrails

1. **Validate the Epic 6 provenance contract, not the pre-Epic-6 one.**
   Operator checks should use `source_alias` and `source_locator`, with `document_version_id`-backed citations where applicable. Do not reintroduce `source_path` as the primary operator-facing contract for connected sources.

2. **Use the canonical identity schema for proofs.**
   When documenting SQL spot checks, stay anchored to the hardened model: `content_blobs`, `sources`, `source_versions`, `document_versions`, and `jobs`.

3. **Prefer one deterministic provenance identity for unchanged/changed tests.**
   A stable `metadata.external_id` in `ingest_document` is the safest operator-facing way to prove unchanged then changed behavior without inventing new tooling.

4. **Keep the restart test operator-realistic.**
   Use the documented restart path from Epic 5 / current setup docs, then re-run the connected-source flows without reauthorising. This story should prove persistence, not a fresh clean boot from scratch.

5. **Separate host-only commands from container-only commands clearly.**
   OAuth commands run on the host. Database-backed and network-local app commands typically run via `docker compose exec cos ...`. Preserve that distinction in the runbook so the operator does not hit avoidable failures.

6. **Do not broaden this story into scheduler, Telegram, or documentation consolidation work.**
   No scheduler setup, no Telegram validation, no architecture doc rewrite, and no cross-repo housekeeping beyond the Epic 6 UAT guide.

### Dependency And Story-Order Notes

- Story 6.5 established canonical migration/backfill and operator recovery. Epic 6 UAT should still treat migration as a prerequisite when validating an older local database.
- Story 6.6 added OAuth authentication setup and is still marked `review` in [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml). Validate the guide against the code actually present on the working branch rather than assuming unmerged review fixes.
- Story 6.8 established Gmail connected ingest and worker-based job submission.
- Story 6.9 established Google Calendar connected ingest and the `google-calendar://` provenance pattern.
- Story 6.10 established `ingest_document`, stable external IDs, and warning-only near-duplicate handling.

### Suggested File Touchpoints

- Primary: [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- Reference only unless a blocking mismatch is discovered:
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
  - [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md)

### Testing Requirements

- This story is validated manually with a real Google account and a real MCP client session.
- No new automated tests are required by default.
- The guide should tell the operator exactly what to seed, what commands to run, and what outcomes prove pass/fail.
- Any SQL checks should be copy-pasteable and consistent with the current Postgres schema.
- Make expected outcomes explicit for:
  - first ingest / first sync success
  - unchanged re-run
  - changed-content re-run
  - cross-source duplicate collapse
  - post-restart token persistence and deterministic re-sync

### Project Structure Notes

- Live operator runbooks belong in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md).
- Stable operator setup and auth instructions live in [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md).
- Migration/backfill recovery instructions live in [docs/migration.md](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md).
- This story should align those references, but it should not rewrite their broader content.

### References

- [Epic 6 stories and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for canonical identity, jobs, and connected sources](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD references for Gmail, Calendar, and `ingest_document`](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Current Epic 6 UAT guide](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- [Setup and Google OAuth guidance](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [Migration/backfill guide](/Users/iain.livingstone/Development/CoS/cos/docs/migration.md)
- [Previous story: 6.5 migration, backfill, and operator recovery](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-5-migration-backfill-and-operator-recovery.md)
- [Previous story: 6.8 Gmail connector](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-8-gmail-connector.md)
- [Previous story: 6.9 Google Calendar connector](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-9-google-calendar-connector.md)
- [Previous story: 6.10 `ingest_document` MCP tool](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-10-ingest-document-mcp-tool.md)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — no code changes required. All implementation is documentation.

### Completion Notes List

- Verified all CLI commands in manual-testing.md against current code: `cos migrate`, `cos restart`, `cos sync gmail/calendar`, `cos docs` (with `--versions`/`--json`), `cos status`, `cos auth gmail/calendar`, `cos ingest` — all present and correct in cli.py
- Verified `ingest_document` outcomes from tools.py/ingestion.py: `new_content`, `unchanged`, `new_source_known_content`, `changed_content` — all reflected in guide
- Added explicit seed-data content for all three MCP note scenarios (Note A first ingest, Note B near-duplicate, Note A v2 changed-content)
- Added SQL cross-source dedupe proof after Section 7.3: two `mcp_note` sources sharing one `sha256`/`document_id`
- Added Section 7.5: changed-content re-ingest using same `external_id: "epic-6-uat-note-001"` with updated content → `changed_content` outcome, followed by `cos docs --versions <document_id>` version history check
- Added new Section 9: Restart and Token Persistence Validation (4 subsections covering restart, token file check, post-restart syncs without re-auth, deterministic outcomes)
- Updated Prerequisites to note `cos restart` runs on the host
- Renumbered old Section 9 (Final Spot Checks) → Section 10; added cross-source dedupe summary SQL
- Renumbered old Section 10 (Pass Criteria) → Section 11; restructured into four named proofs matching AC #1–4
- Scope-limited to `docs/manual-testing.md` only; no `src/` or `tests/` changes

### File List

- docs/manual-testing.md (modified)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified)
- _bmad-output/implementation-artifacts/6-11-operator-validation-connected-sources-live.md (modified)

### Change Log

- 2026-05-07: Updated Epic 6 UAT guide with cross-source dedupe proof, changed-content validation, restart/token-persistence section, and four-proof pass criteria (Story 6.11)
