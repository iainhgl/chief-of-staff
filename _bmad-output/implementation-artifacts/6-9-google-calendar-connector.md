# Story 6.9: Google Calendar Connector

Status: done

## Story

As an operator,
I want upcoming calendar events available through the same connected-source foundation,
So that meeting context can later power prep and scheduled briefings.

## Acceptance Criteria

1. **Given** Google Calendar is authenticated and enabled in configuration,
   **When** the connector fetches events,
   **Then** it returns structured event records containing title, time range, attendees, and description fields suitable for retrieval and downstream workflows.

2. **Given** calendar events are materialised into the knowledge context,
   **When** they are surfaced for retrieval or prep workflows,
   **Then** their provenance uses calendar-specific locators and readable aliases without redefining canonical document identity rules.

3. **Given** an unchanged event is observed on successive syncs,
   **When** the connector reprocesses it,
   **Then** the ingest decision path treats it as unchanged/no-op rather than creating duplicate records.

4. **Given** the Calendar API is unavailable,
   **When** the connector runs,
   **Then** the failure is logged as a degraded connector condition and the rest of the platform continues operating normally.

## Tasks / Subtasks

- [x] Task 1: Extend the config contract for manual Google Calendar sync without making connected sources mandatory at startup (AC: #1, #4)
  - [x] Add an optional `GoogleCalendarConnectorConfig` model in [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) and wire it into `CosConfig` as `google_calendar: GoogleCalendarConnectorConfig | None = None`
  - [x] Keep `connectors: []` as the Epic 1-5 safe default; existing configs must continue loading unchanged when Calendar is not enabled
  - [x] Support a minimal operator-facing block that drives a one-shot upcoming-events sync without introducing scheduler state yet:
    - [x] `calendar_ids: list[str] = ["primary"]`
    - [x] `lookback_hours: int = 12`
    - [x] `lookahead_days: int = 14`
    - [x] `max_results: int = 100` with validation cap at 2500
    - [x] `staging_dir: Path = Path("/data/connector-staging/google-calendar")`
  - [x] Update [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) to show the new optional `google_calendar:` block and that `"google_calendar"` must appear in `connectors:` to enable it

- [x] Task 2: Replace the Calendar stub with a real Calendar API reader that reuses Story 6.6 auth and Story 6.8 client-library patterns (AC: #1, #4)
  - [x] Expand [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py) beyond `get_calendar_credentials()` to include a small Calendar connector surface built on the already-added `google-api-python-client`
  - [x] Reuse the existing Google auth ownership in [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py); do not re-implement OAuth, token refresh, or token-path logic
  - [x] Implement helpers for:
    - [x] building the Calendar API client from refreshed credentials
    - [x] listing events via `events.list`
    - [x] normalising Calendar event payloads into a typed structure or dataclass with the fields later workflows will need
    - [x] converting both timed events (`dateTime`) and all-day events (`date`) into a consistent internal representation
  - [x] Set `singleEvents=True` for the fetch path so recurring meetings materialise as individual instances suitable for meeting-context retrieval
  - [x] Avoid `maxAttendees` truncation unless there is a strong reason; AC #1 requires attendee data to survive into retrieval-ready records

- [x] Task 3: Add a service-layer orchestration file that stages event documents and enqueues ingest jobs through the existing jobs service (AC: #1, #2, #3)
  - [x] Create [src/cos/services/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/calendar.py) so CLI/runtime entry points do not import connector internals directly
  - [x] Reuse [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) `submit_ingest_job(...)`; do not call `run_pipeline_from_source(...)` inline from the Calendar sync path
  - [x] Stage each event under `/data/connector-staging/google-calendar/...` before enqueueing the job
  - [x] Materialise each event as a UTF-8 `.md` file with a readable structure that exposes, at minimum:
    - [x] title / summary
    - [x] calendar identifier or display label
    - [x] start and end values
    - [x] attendee names and/or emails
    - [x] organiser
    - [x] description
    - [x] optional location / HTML link / status if available
  - [x] Use `source_type="google_calendar_event"`
  - [x] Include connector metadata in the job payload `metadata` map where useful, for example `connector`, `calendar_id`, `event_id`, `recurring_event_id`, `original_start_time`, `status`, `html_link`

- [x] Task 4: Lock the Calendar source identity contract so re-syncs land on the existing canonical no-op / changed-content path (AC: #2, #3)
  - [x] For non-recurring events, use a stable locator such as `google-calendar://calendar/<calendar-id>/event/<event-id>`
  - [x] For recurring instances, use a stable locator that incorporates the recurring series plus the instance identity, for example `google-calendar://calendar/<calendar-id>/recurring/<recurringEventId>/instance/<originalStartTime>`
  - [x] Do not key provenance off event title, rendered timestamp text, or staged filename
  - [x] Keep `source_alias` human-readable and deterministic, for example a calendar-aware event label ending in `.md`
  - [x] Stage files with unique filenames that include calendar and event identity, not raw meeting titles alone, because the extractor still derives managed copy paths from staged basenames
  - [x] Ensure unchanged re-syncs reuse the exact same `source_locator`, while changed descriptions / attendees / times for the same event resolve as the existing `changed_content` path rather than duplicate-source inflation

- [x] Task 5: Add a manual `cos sync calendar` command that matches the current architecture and defers scheduler work to later stories (AC: #1, #4)
  - [x] Add a CLI entry point in [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), preferably alongside the existing `sync` sub-app used by Gmail
  - [x] Validate that Calendar is both configured and enabled:
    - [x] `"google_calendar"` appears in `config.connectors`
    - [x] `config.google_calendar` exists or defaults are acceptable
    - [x] usable OAuth credentials are available via Story 6.6
  - [x] Run a single fetch cycle and print a plain-language summary such as calendars scanned, events discovered, and jobs enqueued
  - [x] Keep this as a manual operator trigger for now; do not add APScheduler, cron-like loops, or the Story 7.6 meeting-prep workflow here

- [x] Task 6: Handle degraded Calendar API conditions with connector-scoped logging and bounded retry/backoff (AC: #4)
  - [x] Catch transient Calendar API failures such as rate limits and backend errors and log them with `component: "connector"` and `connector: "google_calendar"`
  - [x] Implement exponential backoff for retryable failures inside the Calendar fetch path, starting at no less than 1 second and growing across a small bounded retry budget
  - [x] Treat permanent auth/config issues as recovery-friendly failures with direct operator instructions (`uv run cos auth calendar`, update `config.yaml`, etc.)
  - [x] Do not let Calendar connector errors crash the MCP server path, modify retrieval services, or mark the whole platform unhealthy in this story

- [x] Task 7: Add automated coverage for Calendar API parsing, event staging, queue submission, and unchanged-event semantics (AC: #1, #2, #3, #4)
  - [x] Add connector tests in a new file such as [tests/connectors/test_calendar.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_calendar.py)
  - [x] Cover at least:
    - [x] request parameter construction for `events.list`
    - [x] timed vs all-day event normalisation
    - [x] recurring-instance handling with `recurringEventId` and `originalStartTime`
    - [x] retry/backoff classification for transient Calendar API failures
  - [x] Add service-layer tests in a new file such as [tests/services/test_calendar_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_calendar_service.py)
  - [x] Assert the service stages Markdown files to the configured shared path and calls `submit_ingest_job(...)` with the exact `source_type`, `source_locator`, `source_alias`, and `metadata` contract
  - [x] Extend [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py) for `cos sync calendar` success output, disabled-config failure, auth recovery failure, and degraded API failure
  - [x] Add one integration-style test that proves a second sync of the same unchanged event resolves to the existing canonical no-op path after the worker processes both jobs
  - [x] Keep all tests offline: patch Google client objects and `HttpError` responses; no live Calendar account, browser auth, or external network

## Dev Notes

### Story Positioning

Story 6.9 is the second live external-content connector in the repo.

- Story 6.6 already added the Google OAuth foundation and token storage under [tokens/](/Users/iain.livingstone/Development/CoS/cos/tokens)
- Story 6.7 already added the background ingest queue, shared staged-file payload contract, and worker reuse of the canonical identity pipeline
- Story 6.8 already established the connector pattern of `connector -> service -> staged file -> jobs queue -> worker -> canonical pipeline`
- Story 6.9 should stay focused on Calendar-specific discovery, event shaping, staging, and enqueue work

This story is not the scheduler, not meeting-prep generation, and not the `ingest_document` MCP tool.

### Product and Architecture Requirements Driving This Story

- FR32: Google Calendar read for meeting context
- FR31: operator configuration remains in a single human-editable `config.yaml`
- NFR10 / NFR11: Calendar failures must degrade the connector path only, not MCP retrieval
- NFR12: repeated syncs must preserve knowledge-base integrity without duplicate canonical records for unchanged content
- NFR20: token refresh remains local and automatic through the Story 6.6 auth path

Architecture guardrails already locked in [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md):

- CLI and MCP entry points should route through `cos/services/*`, not import connector internals directly
- connector-triggered ingest must flow through the shared jobs queue and worker
- shared state lives in Postgres and shared volumes, not in ad hoc in-memory caches
- provenance locators must never become canonical document identity by accident
- managed originals / Markdown copies still derive from staged paths, so filename collisions remain a real risk if staging names are not unique

### Current Code Seams To Reuse

#### Google auth foundation from Story 6.6

- [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py) owns scopes, token paths, refresh, and recovery messaging
- [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py) already exposes `get_calendar_credentials(config)`
- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py) already defines `cos auth calendar`

Do not re-implement OAuth or token refresh inside the Calendar connector.

#### Gmail connector pattern from Story 6.8

- [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py) already demonstrates the intended Google API client + retry helper pattern
- [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py) already demonstrates the intended service-layer seam and staging-to-jobs orchestration
- [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py) already contains the `sync` command test pattern that Calendar should extend rather than duplicate

Calendar should mirror those boundaries where they fit, but avoid Gmail-specific assumptions such as MIME traversal or attachment handling.

#### Jobs queue foundation from Story 6.7

- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) exposes `submit_ingest_job(...)`
- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py) processes staged-file jobs asynchronously
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) already accepts explicit `source_type`, `source_locator`, and `source_alias`

The Calendar connector must enqueue work into this existing substrate. Do not create a Calendar-only ingest shortcut.

### Previous Story Intelligence

- Story 6.8 proved that connector code should stay small and API-facing, while service code owns staging, source-locator construction, and job submission
- Story 6.8 review feedback is directly relevant here:
  - keep connector-specific retry classification explicit
  - keep CLI configuration failures operator-friendly
  - use deterministic fallback identity for edge cases instead of assuming every external artifact has a clean human filename
- Story 6.7 already locked the job payload contract around a staged path plus source metadata; Calendar should reuse that exact contract instead of inventing a richer queue schema

### Recent Git Intelligence

Recent commits show the live implementation sequence:

- `Implement story 6.8 Gmail connector`
- `Apply code review fixes for story 6.8`
- `Implement story 6.7 jobs queue and background ingestion worker`

That sequence implies two practical rules for 6.9:

1. Reuse the just-landed Gmail / queue patterns instead of creating a second connector architecture.
2. Bake the 6.8 review lessons into the first implementation pass so Calendar does not repeat the same mistakes.

### Critical Implementation Guardrails

1. **Do not call the ingest pipeline inline from the Calendar fetch loop.** The acceptance criteria depend on Story 6.7 queue isolation. The right sequence is: Calendar API discovery -> stage Markdown event file -> `submit_ingest_job(...)`.

2. **Do not import connectors directly from `cli.py`.** Add a service-layer seam first, then let the CLI call the service. This keeps the architecture boundary intact and matches the Gmail pattern already in the repo.

3. **Stage to the shared `/data` volume, never container-local `/tmp`.** The worker is a separate process/container and must be able to read every staged event file.

4. **Use unique staged filenames.** Current extraction still derives managed-copy paths from staged basenames, so two meetings with the same title cannot safely stage as `Board Sync.md`.

5. **Preserve a stable locator contract.** Suggested forms:
   - single event: `google-calendar://calendar/<calendar-id>/event/<event-id>`
   - recurring instance: `google-calendar://calendar/<calendar-id>/recurring/<recurringEventId>/instance/<originalStartTime>`

6. **Handle all-day and timed events correctly.** Calendar events may use either `start.date` / `end.date` or `start.dateTime` / `end.dateTime`; do not assume every event is timed.

7. **Use recurring-instance identity, not rendered meeting text, for rescheduled recurring events.** Google documents `originalStartTime` as the field that uniquely identifies an instance within a recurring series even if it was moved.

8. **Do not add sync-token persistence in this story if the fetch strategy relies on an upcoming-events time window.** The Calendar API does not allow `syncToken` to be combined with `timeMin`, `timeMax`, or `orderBy`, so a manual rolling-window sync should rely on canonical no-op semantics for now.

9. **Keep cancellation / tombstone propagation out of this story unless it falls out cleanly from the existing ingest contract.** The current pipeline is append-only and not designed for destructive sync semantics.

10. **Connector errors must be recovery-friendly and non-fatal to the core platform.** Use structured JSON logging with `component: "connector"` and direct operator guidance where useful.

11. **Keep scheduler scope out of this story.** A manual one-shot Calendar sync command is enough here. Scheduled meeting prep belongs later.

### Google Calendar API Notes (Verified Against Official Docs on 2026-05-06)

Use these implementation facts; they are more precise than guesswork:

- `events.list` uses `calendarId`, and the special value `primary` refers to the authenticated user's primary calendar
- `events.list` defaults to 250 results per page and caps `maxResults` at 2500
- `singleEvents=true` expands recurring series into individual instances; `orderBy="startTime"` is used with that instance-oriented view
- `syncToken` supports incremental sync, but it cannot be combined with `timeMin`, `timeMax`, or `orderBy`
- recurring instances expose both `recurringEventId` and `originalStartTime`; Google documents `originalStartTime` as uniquely identifying the instance within the series even if it is moved
- event resources expose `summary`, `description`, `start`, `end`, `attendees`, `organizer`, `status`, and `htmlLink`

### Suggested File Touchpoints

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [src/cos/connectors/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/calendar.py)
- [src/cos/services/calendar.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/calendar.py)
- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
- [tests/connectors/test_calendar.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_calendar.py)
- [tests/services/test_calendar_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_calendar_service.py)
- [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py)

### Testing Strategy

- Patch the Google discovery client and `HttpError` responses; no live Calendar account or network calls
- Use synthetic event fixtures that include:
  - timed event
  - all-day event
  - recurring instance with `recurringEventId` and `originalStartTime`
  - event with attendees and description
- Assert exact job payload contracts rather than only high-level counts
- Reuse the existing worker + canonical identity path in at least one integration test so Story 6.3 / 6.7 unchanged-event behaviour is actually exercised for Calendar source types

### Non-Goals

- No Gmail changes here
- No APScheduler or always-on scheduler container here
- No meeting-prep generation or morning-brief logic here
- No `ingest_document` MCP tool work here
- No destructive deletion / tombstone sync semantics for removed events here
- No broad documentation rewrite; reserve major doc consolidation for Story 6.12

### Source References

- [Epic 6 in epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for connectors, jobs, and config](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD connected-source and calendar requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Previous story: 6.6 OAuth authentication setup](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-6-oauth-authentication-setup-for-gmail-and-calendar.md)
- [Previous story: 6.7 jobs queue and worker](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-7-jobs-queue-and-background-ingestion-worker.md)
- [Previous story: 6.8 Gmail connector](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-8-gmail-connector.md)
- [Google Calendar API `events.list`](https://developers.google.com/calendar/api/v3/reference/events/list?hl=en)
- [Google Calendar API event resource](https://developers.google.com/workspace/calendar/api/v3/reference/events)
- [Google Calendar recurring events guide](https://developers.google.com/calendar/api/guides/recurringevents)
- [Google Calendar incremental sync guide](https://developers.google.com/workspace/calendar/api/guides/sync)

### Review Findings

- [x] [Review][Patch] Surface degraded Calendar API failures to the operator instead of logging and returning success [src/cos/services/calendar.py:54]
- [x] [Review][Patch] Make `source_alias` human-readable rather than opaque `calendar_id`/`event_id` slugs [src/cos/services/calendar.py:111]
- [x] [Review][Patch] Reject Calendar events with missing IDs before building locators and staged filenames [src/cos/connectors/calendar.py:97]
- [x] [Review][Patch] Validate `lookback_hours` and `lookahead_days` as non-negative config values [src/cos/config.py:82]
- [Google Calendar API overview](https://developers.google.com/workspace/calendar/api/guides/overview)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- All tasks implemented in a single session. 340 tests pass (2 skipped). No regressions.

### Completion Notes List

- Added `GoogleCalendarConnectorConfig` to `src/cos/config.py` with `calendar_ids`, `lookback_hours`, `lookahead_days`, `max_results` (capped at 2500), and `staging_dir`. Wired into `CosConfig` as optional field.
- Expanded `src/cos/connectors/calendar.py` from a one-line stub into a full connector: `build_calendar_service`, `list_events`, `normalise_event`, `CalendarEvent` dataclass, `_execute_with_retry`, and `_is_retryable_http_error`. Reuses Story 6.6 auth; mirrors Story 6.8 Gmail retry pattern.
- Created `src/cos/services/calendar.py` with `sync_calendar` and `CalendarSyncResult`. Iterates over configured calendar IDs, normalises events, stages each as a UTF-8 Markdown file (with title, calendar, start/end, attendees, organiser, description, location, status, link), then calls `submit_ingest_job(...)`.
- Source identity: single events use `google-calendar://calendar/<cal>/event/<id>`; recurring instances use `google-calendar://calendar/<cal>/recurring/<recurringEventId>/instance/<originalStartTime>`. Source aliases and staged filenames both include calendar and event ID for uniqueness.
- Added `sync_calendar` CLI command under `sync_app` in `src/cos/cli.py`, matching the Gmail sync pattern. Validates `google_calendar` in connectors, handles `AuthError` and general failures gracefully.
- Calendar API errors inside the fetch loop are caught and logged with `component: "connector"`, `connector: "google_calendar"`. Auth failures propagate to the CLI for operator-friendly messages. Platform-level health is unaffected.
- Tests: 15 connector tests, 8 service tests (including 1 end-to-end no-op integration test), 6 CLI tests, 5 config tests. All offline — Google client and HttpError patched throughout.
- `config.yaml.example` updated with full `google_calendar:` block documentation and an updated connectors comment.

### File List

- src/cos/config.py
- src/cos/connectors/calendar.py
- src/cos/services/calendar.py
- src/cos/cli.py
- config.yaml.example
- tests/connectors/test_calendar.py (new)
- tests/services/test_calendar_service.py (new)
- tests/cli/test_cli_sync.py
- tests/test_config.py

## Change Log

- 2026-05-06: Implemented story 6.9 Google Calendar Connector — config model, connector (CalendarEvent dataclass, list_events, normalise_event, retry/backoff), service layer (sync_calendar, Markdown staging, job submission, stable source identity), CLI command (cos sync calendar), and full offline test suite (29 new tests across 3 new/extended test files).
