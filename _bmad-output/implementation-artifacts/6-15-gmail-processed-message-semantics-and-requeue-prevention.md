# Story 6.15: Gmail Processed-Message Semantics and Requeue Prevention

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want Gmail sync to skip already-processed matching messages by default,
So that normal operation does not keep re-scanning and re-queueing work that has already completed successfully.

## Acceptance Criteria

1. **Given** a Gmail message body or attachment source has already been processed successfully,
   **When** the same message still matches the configured query on a later sync,
   **Then** the connector skips re-queueing it by default.

2. **Given** a Gmail message changes in a way that should be treated as new ingestable content or a new source observation,
   **When** sync runs,
   **Then** the connector still submits the appropriate work safely.

3. **Given** the connector resumes after restart,
   **When** it evaluates whether to queue matching Gmail content,
   **Then** processed-message bookkeeping survives restart and does not depend on in-memory state.

4. **Given** the operator needs to intentionally reprocess Gmail content,
   **When** they follow the documented recovery path,
   **Then** a supported override exists without requiring manual database surgery.

## Tasks / Subtasks

- [x] Task 1: Add a deterministic Gmail requeue-decision step in the service layer (AC: #1, #2, #3)
  - [x] Evaluate Gmail body and attachment artifacts at the existing `source_locator` granularity, not only at whole-message granularity, because one message can produce one body source plus multiple attachment sources
  - [x] Compute a stable artifact fingerprint from the exact ingestable content for that artifact:
    - [x] message body: the rendered Markdown body content that is actually staged for ingestion
    - [x] attachment: the exact raw bytes that are staged for ingestion
  - [x] Use that fingerprint to distinguish three cases cleanly before enqueue:
    - [x] already processed successfully with the same content -> skip by default
    - [x] already known source but content changed -> enqueue again so the canonical pipeline can resolve `changed_content`
    - [x] new source observation -> enqueue normally
  - [x] Keep Gmail discovery behavior intact: the connector may still scan matching message IDs each run, but it should stop producing avoidable staging and queue churn for unchanged already-processed artifacts

- [x] Task 2: Persist the skip decision in Postgres using existing authoritative seams first (AC: #1, #3)
  - [x] Prefer the already-authoritative canonical provenance and queue state before inventing a connector-only persistence model:
    - [x] successful prior observations should be inferred from `sources` / `source_versions` / latest canonical content for the existing `source_locator`
    - [x] in-flight duplicate work should be inferred from `jobs` rows that are already `queued` or `running`
  - [x] Add narrow store helpers in [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) for these checks instead of embedding raw SQL in the Gmail service
  - [x] If content fingerprints must be compared against queued or running jobs, store the needed fingerprint in job payload metadata or an equally lightweight durable field already owned by the jobs path
  - [x] Do **not** rely on in-memory sets, process-local caches, or worker-local state; restart safety must come from persisted state
  - [x] Do **not** add a new Gmail-specific bookkeeping table unless the existing canonical + jobs state proves insufficient after careful analysis

- [x] Task 3: Preserve safe reprocessing semantics for changed Gmail content and new observations (AC: #2)
  - [x] Keep the current canonical ingest path unchanged once a job is submitted: Gmail sync must still flow through `submit_ingest_job(...)` and the background worker, not call the ingest pipeline inline
  - [x] Treat content changes at the artifact level:
    - [x] changed message body content for `gmail://message/<id>/body` should be re-enqueued
    - [x] changed bytes for `gmail://message/<id>/attachment/<attachment-id>` should be re-enqueued
    - [x] a newly observed attachment on an existing message should enqueue as a new source locator
  - [x] Do not treat mailbox label churn or other Gmail metadata changes alone as changed ingestable content unless those changes alter the actual staged body Markdown or attachment bytes
  - [x] Keep unsupported-attachment skip behavior exactly as Story 6.8 defined it; this story is about processed-message semantics, not attachment-format expansion

- [x] Task 4: Add an explicit operator override for intentional Gmail reprocessing (AC: #4)
  - [x] Add a one-shot operator-facing override on the Gmail sync path, preferably `cos sync gmail --force`, that bypasses the processed-artifact skip checks for that run
  - [x] Keep the override local to the command invocation:
    - [x] no persistent config toggle
    - [x] no requirement to mutate the mailbox
    - [x] no manual database edits
  - [x] Thread the override through the service boundary cleanly so `cli.py` remains a thin command surface over [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
  - [x] Document the supported override in operator-facing docs so recovery is discoverable without reading source code

- [x] Task 5: Make Gmail sync output and docs reflect the new semantics (AC: #1, #4)
  - [x] Extend `GmailPollResult` and the `cos sync gmail` summary so operators can tell why fewer jobs were enqueued on repeated runs
  - [x] Report at least the number of already-processed artifacts skipped; if in-flight duplicates are also suppressed, make that visible in the summary or logs
  - [x] Update [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) and [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) with:
    - [x] the new default skip-by-success behavior
    - [x] the supported override path
    - [x] the expected repeated-sync behavior after the worker has already succeeded
  - [x] Keep documentation changes tightly scoped to Gmail sync semantics and operator recovery; do not reopen the broader Epic 6 documentation sweep from Story 6.12

- [x] Task 6: Add focused automated coverage for requeue prevention, persistence, and override behavior (AC: #1, #2, #3, #4)
  - [x] Extend [tests/services/test_gmail_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py) with service-level cases covering:
    - [x] second sync after successful processing skips an unchanged Gmail body source
    - [x] second sync after successful processing skips an unchanged Gmail attachment source
    - [x] changed body content for the same message re-enqueues work
    - [x] changed attachment bytes for the same attachment locator re-enqueue work
    - [x] a new attachment on an existing message still enqueues as a new source observation
    - [x] repeated sync before worker success does not keep piling up duplicate `queued` / `running` jobs for the same locator + fingerprint
  - [x] Add persistence-oriented coverage proving the skip decision survives a fresh database connection and worker restart path rather than depending on process memory
  - [x] Extend [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py) for the new summary fields and the intentional override flag
  - [x] Add or extend jobs/store tests if new helper behavior is introduced for pending-job dedupe or successful-observation lookup
  - [x] Keep all tests offline: patch Gmail API calls, use local staged files, and rely on the existing Postgres-backed test harness rather than live Google accounts

## Dev Notes

### What This Story Is

Story 6.15 is an operator-semantics hardening story for the Gmail connector. Story 6.8 made Gmail safe from a canonical data-integrity perspective because repeated submissions eventually collapse to `unchanged` or `changed_content` inside the ingest pipeline. That is not enough for normal connector operation: if a message continues to match the configured Gmail query, the sync path still stages and re-enqueues the same work again and again.

This story fixes that operational gap without changing the canonical identity model underneath it.

### Why This Story Exists Now

Epic 6 UAT identified a specific behavior problem: Gmail messages that still match the configured query after successful processing continue to be rediscovered and re-enqueued on later `cos sync gmail` runs. The system stays safe because canonical identity prevents duplicate content inflation, but the operator experience is noisy and the jobs queue does unnecessary work. [Source: [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)]

The accepted design direction from the change proposal is therefore:

1. keep Gmail read-only in this story
2. track or detect already-processed Gmail content durably
3. provide an intentional reprocessing escape hatch without manual DB edits

### Previous Story Intelligence

- Story 6.8 intentionally enqueues every matching Gmail artifact on every poll run. Its ACs relied on the ingest pipeline to resolve duplicate/no-op outcomes safely, but it did not add operator-facing skip semantics. [Source: [6-8-gmail-connector.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-8-gmail-connector.md)]
- Story 6.7 introduced the jobs queue and worker. That means Gmail sync already has a durable path for `queued`, `running`, `succeeded`, `failed`, and stale-job recovery; this story should build on that instead of bypassing it. [Source: [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py), [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)]
- Story 6.6 established Google OAuth with `gmail.readonly`, token persistence under `tokens/`, and recovery via `cos auth gmail`. This story should not expand scope to mailbox mutation or scope upgrades. [Source: [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py), [tests/connectors/test_google_auth.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_google_auth.py)]
- Story 6.11 recorded the live UAT findings and explicitly framed this as a product-behavior story rather than a local patch. [Source: [6-11-operator-validation-connected-sources-live.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-11-operator-validation-connected-sources-live.md), [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)]
- Story 6.12 is still in `review` and already refreshed the broader Epic 6 docs. Any documentation change here should be narrow and Gmail-semantics-specific rather than reopening the whole sweep. [Source: [6-12-documentation-and-housekeeping.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-12-documentation-and-housekeeping.md)]

### Git Intelligence

- Recent work has stayed tightly story-scoped with focused review-fix follow-ups. Keep 6.15 similarly narrow: Gmail sync semantics, minimal store helpers, CLI override, tests, and only the smallest doc updates needed.
- Most recent relevant commits:
  - `3def5d0` — `Fix story 6.14 review findings`
  - `ab868b8` — `Implement story 6.14 single-source factual grounding for retrieve`
  - `027e675` — `Fix story 6.13 review findings`

### Product And Architecture Guardrails

1. **Keep Gmail read-only in this story.**
   The UAT notes explicitly call `gmail.modify` and processed-label mutation a possible future direction, not the current requirement. Do not expand OAuth scopes or mutate mailbox labels here. [Source: [epic-6-uat-findings-2026-05-07.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md), [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)]

2. **Prefer existing canonical and jobs state before adding new persistence.**
   A successfully processed Gmail artifact already has durable canonical representation through `sources`, `source_versions`, and `document_versions`. In-flight work already lives in `jobs`. Reuse those truths first. [Source: [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

3. **Persisted means Postgres-backed, not in-memory.**
   AC #3 is specifically about restart survival. Any design that depends on a Python set, connector-global cache, or process-local memory fails the story even if tests pass in one process.

4. **Fingerprint actual ingestable content, not Gmail mailbox metadata alone.**
   If the skip decision keys off label state, Gmail `historyId`, or message query membership alone, the connector will either requeue too often or miss genuine content changes. Use the actual staged body Markdown or exact attachment bytes as the content signal.

5. **Keep artifact-level semantics separate.**
   A message body and each attachment are distinct sources today:
   - `gmail://message/<message-id>/body`
   - `gmail://message/<message-id>/attachment/<attachment-id-or-part-id>`
   The skip decision must honor that existing source model rather than flattening everything to one per-message processed flag. [Source: [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)]

6. **Do not bypass the jobs/worker path.**
   Gmail sync remains a discovery-and-enqueue step. Once work should be processed, it must still go through `submit_ingest_job(...)` and the background worker so the four ingest outcomes remain consistent with every other channel. [Source: [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

7. **Keep service boundaries intact.**
   `cli.py` should stay thin, the Gmail connector should remain Gmail-API-specific, and persisted decision logic should live behind service/store helpers rather than leaking raw SQL or connector internals into the CLI. [Source: [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

8. **Do not accidentally change Calendar semantics.**
   Calendar currently re-enqueues unchanged events and relies on the canonical pipeline to resolve no-op behavior. Story 6.15 is a Gmail-specific operator-semantic change and should not broaden into a cross-connector requeue redesign unless a tiny shared helper is clearly reusable and behavior-preserving. [Source: [src/cos/services/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/calendar.py), [tests/services/test_calendar_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_calendar_service.py)]

9. **Preserve the four ingest outcomes and component isolation guarantees.**
   This story changes queue-submission policy, not ingest outcomes, MCP availability, or worker/process isolation. The PRD and architecture still require connector failures to remain isolated from the core retrieval path. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

### Query And Data Design Guidance

- The cleanest default path is:
  - Gmail query returns matching message IDs
  - connector fetches the message and derives the body / attachment artifacts as it does today
  - service computes content fingerprints for those artifacts
  - service checks:
    - successful prior processing for the same `source_locator` + fingerprint
    - any already-queued or running ingest job for the same `source_locator` + fingerprint
  - only artifacts that are new, changed, or explicitly forced get staged/enqueued

- This guidance intentionally favors reusing existing durable data over adding a parallel Gmail-only state table. Only fall back to a new table if the existing canonical and jobs state cannot express the decision safely enough.

### Current Code Seams To Use As Source Of Truth

- [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
  - current message discovery, body rendering, attachment staging, and unconditional enqueue behavior
  - likely primary home for the new skip-decision orchestration

- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
  - canonical provenance queries
  - jobs queue helpers
  - best place for narrow persisted-state lookup helpers

- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)
  - existing job payload contract
  - successful / retryable / failed worker lifecycle

- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)
  - stale-job recovery on startup
  - important for restart-safe semantics when in-flight work exists

- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - current `cos sync gmail` command surface
  - likely home for a one-shot `--force` override option and updated summary output

- [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
  - current Gmail read-only scope and token lifecycle
  - important proof that mailbox mutation is not part of the current contract

- [tests/services/test_gmail_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py)
  - current service tests already cover staging and enqueue contract
  - natural place for the new repeated-sync and changed-content semantics

- [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py)
  - current Gmail sync summary and failure-path coverage
  - should be extended for new summary fields and override path

### Suggested File Touchpoints

- Primary implementation files:
  - [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
  - [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py)
  - [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
  - [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) only if the existing job payload contract needs a lightweight fingerprint field
  - [src/cos/store/models.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/models.py) only if a small helper dataclass is warranted

- Primary test files:
  - [tests/services/test_gmail_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py)
  - [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py)
  - [tests/services/test_jobs_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_jobs_service.py) if pending-job dedupe logic touches the jobs contract
  - [tests/store/test_jobs.py](/Users/iain.livingstone/Development/CoS/cos/tests/store/test_jobs.py) if store-level helpers or query semantics need direct coverage

- Optional documentation files:
  - [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
  - [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)

- Avoid by default:
  - new migrations
  - OAuth scope changes
  - calendar connector files
  - retrieval, MCP, or role-pack modules

### Testing Requirements

- Add at least one full service-level regression proving:
  1. first sync enqueues Gmail work
  2. worker succeeds
  3. second sync with unchanged content skips re-enqueue by default

- Add changed-content coverage for both body and attachment cases so the story does not silently convert legitimate updates into permanent skips.

- Add pending-work coverage:
  - sync run A enqueues work
  - worker has not yet succeeded
  - sync run B with the same content does not enqueue duplicate queued/running work

- Add fresh-connection or restart-oriented coverage proving the decision survives database reconnection and worker recovery semantics.

- Add CLI coverage for:
  - default summary with processed-skip reporting
  - `--force` (or the final chosen one-shot override) re-enqueue behavior
  - existing success and failure behavior remaining intact

- Keep tests deterministic and offline:
  - patch Gmail API calls
  - use the existing Postgres-backed test harness
  - no browser auth
  - no live Gmail account

### Project Structure Notes

- This story should remain a Gmail-sync behavior hardening pass, not a cross-channel architecture rewrite.
- Any reusable helper added for successful-observation lookup or pending-job dedupe should still live inside existing `services` / `store` seams, not as a new connector framework.
- The operator-facing override should be discoverable from the CLI/docs without introducing a permanent config surface unless the implementation uncovers a strong reason for one.

### Assumptions

- Recommended operator override: `cos sync gmail --force`.
- Recommended persistence strategy: reuse canonical source history and jobs state before adding any Gmail-specific table.
- Recommended change boundary: Gmail connector semantics only; Calendar remains behaviorally unchanged in this story.

### References

- [Epic 6 story definition and acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Sprint change proposal that introduced Story 6.15](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-08.md)
- [Epic 6 UAT findings that identified Gmail requeue churn](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epic-6-uat-findings-2026-05-07.md)
- [Architecture constraints for service boundaries, connector isolation, and ingest outcomes](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD FR/NFR references for Gmail ingestion, connector fault isolation, and OAuth token persistence](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Current Gmail service implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
- [Current jobs service implementation](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)
- [Current worker loop and stale-job recovery](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)
- [Current Gmail sync CLI command](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
- [Current Gmail service tests](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py)
- [Current Gmail sync CLI tests](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was straightforward with no significant debug cycles.

### Completion Notes List

- Added `_compute_fingerprint(content: bytes) -> str` helper (SHA-256 hex) and `_check_skip(conn, source_type, source_locator, fingerprint, force) -> str | None` helper in `gmail.py`. Skip returns `'processed'`, `'pending'`, or `None`.
- Added two narrow store helpers in `db.py`: `has_processed_artifact` (queries sources → source_versions → content_blobs by source_type + source_locator + sha256) and `has_pending_job_for_locator` (queries jobs by source_locator + content_fingerprint in metadata for queued/running status). No new tables added.
- `poll_gmail` accepts `force: bool = False`. Fingerprints are computed before staging. Skip checks run before write-to-disk and before `submit_ingest_job`. `content_fingerprint` stored in job metadata for pending-job deduplication.
- `GmailPollResult` extended with `artifacts_already_processed: int = 0` and `artifacts_already_queued: int = 0` (default 0 for backward compatibility).
- `sync_gmail` CLI command gets `--force` typer option; `_do_sync_gmail` passes it through. Summary output adds two new lines for skip counts.
- Docs: `setup.md` and `manual-testing.md` updated with repeated-sync expected output, skip semantics explanation, and `--force` recovery instructions.
- 436 tests pass (1 skipped). 11 new service tests, 3 new CLI tests, 7 new store tests added.

### File List

- `src/cos/services/gmail.py` — added `_compute_fingerprint`, `_check_skip`, extended `GmailPollResult`, rewrote `poll_gmail` with skip logic and `force` param
- `src/cos/store/db.py` — added `has_processed_artifact` and `has_pending_job_for_locator` store helpers
- `src/cos/cli.py` — `sync_gmail` with `--force` option, `_do_sync_gmail` with `force` param, extended summary output
- `tests/services/test_gmail_service.py` — 11 new tests for requeue prevention, persistence, force override
- `tests/cli/test_cli_sync.py` — 3 new tests for skip counts in summary and `--force` flag
- `tests/store/test_jobs.py` — 7 new tests for `has_processed_artifact` and `has_pending_job_for_locator`
- `docs/setup.md` — repeated-sync output examples and `--force` recovery section
- `docs/manual-testing.md` — repeated sync and `--force` test steps added to Gmail test pack
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status updated

## Change Log

- 2026-05-08: Implemented story 6.15 — Gmail processed-message semantics and requeue prevention. Added content fingerprinting, skip-decision logic (processed + pending-job checks), `--force` override, extended `GmailPollResult` with skip counts, two new `db.py` store helpers, CLI summary updates, docs updates, and comprehensive test coverage (21 new tests).
