# Story 6.8: Gmail Connector

Status: done

## Story

As an operator,
I want Gmail messages and attachments ingested through the hardened identity pipeline,
So that email-based knowledge becomes searchable without manual download and duplicate inflation.

## Acceptance Criteria

1. **Given** Gmail is authenticated and enabled in configuration,
   **When** the connector polls for new messages,
   **Then** it creates background ingest jobs for message bodies and supported attachments using Gmail identifiers as provenance locators.

2. **Given** an attachment or message body was already observed from the same Gmail source,
   **When** the connector polls again,
   **Then** the canonical ingest decision engine prevents duplicate processing and records the appropriate no-op or new-version outcome.

3. **Given** two different Gmail messages carry byte-identical attachments,
   **When** both are ingested,
   **Then** they resolve to shared canonical content with distinct source provenance records rather than duplicate embeddings.

4. **Given** the Gmail API is temporarily unavailable or rate-limited,
   **When** the connector handles the failure,
   **Then** it logs a degraded connector status, backs off appropriately, and leaves the core retrieval path healthy.

## Tasks / Subtasks

- [ ] Task 1: Extend the config contract for Gmail polling without making connected sources mandatory at startup (AC: #1, #4)
  - [ ] Add an optional `GmailConnectorConfig` model in [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) and wire it into `CosConfig` as `gmail: GmailConnectorConfig | None = None`
  - [ ] Keep `connectors: []` as the Epic 1-5 safe default; existing configs must continue loading unchanged when Gmail is not enabled
  - [ ] Support a minimal operator-facing block that can drive a manual poll cycle without introducing scheduler complexity yet:
    - [ ] `query: str | None = None`
    - [ ] `label_ids: list[str] = []`
    - [ ] `max_results: int = 25` with validation cap at 500
    - [ ] `include_spam_trash: bool = False`
    - [ ] `staging_dir: Path = Path("/data/connector-staging/gmail")`
  - [ ] Update [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) to show the new optional `gmail:` block and that `"gmail"` must appear in `connectors:` to enable it

- [ ] Task 2: Replace the Gmail stub with a real Gmail API reader that reuses Story 6.6 auth (AC: #1, #4)
  - [ ] Expand [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py) beyond `get_gmail_credentials()` to include a small Gmail connector surface built on the official Google client library
  - [ ] Add the minimum dependency required for Gmail API reads in [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml) and refresh `uv.lock`; prefer `google-api-python-client` over hand-rolled REST calls or IMAP
  - [ ] Build the Gmail API client with refreshed creds from `get_gmail_credentials(config)` and keep auth ownership in [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py)
  - [ ] Implement helpers for:
    - [ ] listing message IDs via `users.messages.list`
    - [ ] fetching full message payloads via `users.messages.get`
    - [ ] fetching detached attachment bytes via `users.messages.attachments.get`
    - [ ] recursively walking MIME parts so nested attachments are not missed
  - [ ] Decode Gmail `data` payloads as base64url, not plain base64

- [ ] Task 3: Stage message bodies and supported attachments onto the shared worker volume, then enqueue ingest jobs through the existing jobs service (AC: #1, #2, #3)
  - [ ] Create a new service-layer orchestration file such as [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py) so CLI/runtime entry points do not import connector internals directly
  - [ ] Reuse [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) `submit_ingest_job(...)`; do not call `run_pipeline_from_source(...)` inline from the Gmail poll path
  - [ ] Stage each discovered artifact under `/data/connector-staging/gmail/...` before enqueueing jobs
  - [ ] Use **unique staged filenames** that include Gmail IDs, not raw attachment filenames alone, because the current extractor writes managed copies using `source_path.name` / `source_path.stem` and same-name staged files would collide
  - [ ] For message bodies:
    - [ ] materialise a UTF-8 `.md` file containing a readable body representation plus lightweight metadata header if helpful
    - [ ] enqueue with `source_type="gmail_message_body"`
    - [ ] use locator `gmail://message/<message-id>/body`
  - [ ] For attachments:
    - [ ] only enqueue files whose suffix is currently supported by the ingest pipeline (`.md`, `.txt`, `.pdf`, `.docx`)
    - [ ] skip unsupported attachment types with structured connector logs instead of forcing them through extraction
    - [ ] enqueue with `source_type="gmail_attachment"`
    - [ ] use locator `gmail://message/<message-id>/attachment/<attachment-id>`
  - [ ] Include connector metadata in the job payload `metadata` map where useful, for example `connector`, `message_id`, `thread_id`, `subject`, `from`, `internal_date`, `mime_type`

- [ ] Task 4: Add a manual Gmail poll command that fits the current architecture without inventing the Epic 7 scheduler early (AC: #1, #4)
  - [ ] Add a CLI entry point in [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py), preferably under a dedicated sub-app such as `cos sync gmail`
  - [ ] Validate that Gmail is both configured and enabled:
    - [ ] `"gmail"` appears in `config.connectors`
    - [ ] `config.gmail` exists or defaults are acceptable
    - [ ] usable OAuth credentials are available via Story 6.6
  - [ ] Run a **single poll cycle** and print a plain-language summary: messages scanned, body jobs enqueued, attachment jobs enqueued, unsupported attachments skipped
  - [ ] Keep this as a manual operator trigger for now; do not add APScheduler, a long-running scheduler container, or morning-brief logic in this story

- [ ] Task 5: Handle degraded Gmail API conditions with connector-scoped logging and bounded retry/backoff (AC: #4)
  - [ ] Catch Gmail API transient failures such as rate limits and backend errors and log them with `component: "connector"` and `connector: "gmail"`
  - [ ] Implement exponential backoff for retryable failures inside the Gmail polling path, starting at no less than 1 second and growing across a small bounded retry budget
  - [ ] Treat permanent auth/config issues as recovery-friendly failures with direct operator instructions (`uv run cos auth gmail`, update `config.yaml`, etc.)
  - [ ] Do not let Gmail connector errors crash the MCP server path, modify retrieval services, or mark the whole platform unhealthy in this story

- [ ] Task 6: Lock the source identity contract so Gmail dedupe works exactly through the existing canonical pipeline (AC: #2, #3)
  - [ ] Message-body re-polls for the same Gmail message must reuse the exact same `source_locator` so Story 6.3 unchanged/no-op behaviour applies
  - [ ] Attachment re-polls for the same Gmail attachment must reuse the exact same `source_locator`
  - [ ] Byte-identical attachments from different Gmail messages must intentionally produce **different** source locators but identical staged bytes, allowing Story 6.2 canonical blob dedupe to collapse content while preserving two `sources` rows
  - [ ] Keep `source_alias` human-readable:
    - [ ] message body alias: stable subject-derived or message-id-derived label ending in `.md`
    - [ ] attachment alias: original attachment filename when present; deterministic fallback when absent

- [ ] Task 7: Add automated coverage for Gmail API parsing, staging, queue submission, and duplicate semantics (AC: #1, #2, #3, #4)
  - [ ] Add connector unit tests in a new file such as [tests/connectors/test_gmail.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_gmail.py)
  - [ ] Cover at minimum:
    - [ ] `users.messages.list` response handling and max-results/query wiring
    - [ ] MIME tree traversal finds inline body text plus nested attachments
    - [ ] base64url decoding for bodies and attachments
    - [ ] unsupported attachments are skipped cleanly
    - [ ] retry/backoff on retryable Gmail API errors
  - [ ] Add service-layer tests in a new file such as [tests/services/test_gmail_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py)
  - [ ] Assert the service stages files to the configured shared path and calls `submit_ingest_job(...)` with the exact `source_type`, `source_locator`, `source_alias`, and `metadata` contract
  - [ ] Add CLI tests in a new file such as [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py) for success output, disabled-config failure, and degraded Gmail API failure
  - [ ] Add one integration-style test that proves two staged Gmail attachments with different Gmail locators but identical bytes collapse to one canonical blob after the worker processes both jobs
  - [ ] Keep all tests offline: patch Google client objects and HTTP errors; no live Gmail account, browser auth, or external network

## Dev Notes

### Story Positioning

Story 6.8 is the first **live external-content connector** in the repo.

- Story 6.6 already added the Google OAuth foundation and token storage under [tokens/](/Users/iain.livingstone/Development/CoS/cos/tokens)
- Story 6.7 already added the background ingest queue, shared staged-file payload contract, and worker reuse of the canonical identity pipeline
- Story 6.8 must now do only the Gmail-specific discovery, staging, and enqueue work

This story is **not** the scheduler, not the Calendar connector, and not the `ingest_document` MCP tool.

### Product and Architecture Requirements Driving This Story

- FR10 / FR33: Gmail messages and attachments must become ingestible platform knowledge
- FR31: operator configuration remains in a single human-editable `config.yaml`
- NFR5: Gmail credentials and token contents must never be logged or echoed
- NFR10 / NFR11: Gmail failures must degrade the connector path only, not MCP retrieval
- NFR20: token refresh remains local and automatic through the Story 6.6 auth path

Architecture guardrails already locked in [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md):

- CLI and MCP entry points should route through `cos/services/*`, not import connector internals directly
- connector-triggered ingest must flow through the shared jobs queue and worker
- shared state lives in Postgres and shared volumes, not in ad hoc in-memory caches
- `component` log values must stay within the approved set; for this story use `connector` and the existing `ingestion` worker logs

### Current Code Seams To Reuse

#### Google auth foundation from Story 6.6

- [src/cos/connectors/google_auth.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/google_auth.py) owns scopes, token paths, refresh, and recovery messaging
- [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py) already exposes `get_gmail_credentials(config)`
- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py) already defines `cos auth gmail`

Do not re-implement OAuth or token refresh inside the Gmail connector.

#### Jobs queue foundation from Story 6.7

- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) exposes `submit_ingest_job(...)`
- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py) processes staged-file jobs asynchronously
- [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py) already accepts explicit `source_type`, `source_locator`, and `source_alias`

The Gmail connector must enqueue work into this existing substrate. Do not create a Gmail-only ingest shortcut.

#### Attachment support boundary today

[src/cos/services/ingestion.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) defines `SUPPORTED_SUFFIXES` from the existing extractor stack:

- direct: `.md`, `.txt`
- Tika-backed: `.pdf`, `.docx`

That is the real supported set today. Skip unsupported Gmail attachments for now instead of pretending image, spreadsheet, or archive ingest exists.

### Critical Implementation Guardrails

1. **Do not call the ingest pipeline inline from the Gmail poll loop.** The acceptance criteria explicitly depend on Story 6.7 queue isolation. The right sequence is: Gmail API discovery -> stage file -> `submit_ingest_job(...)`.

2. **Do not import connectors directly from `cli.py`.** Add a service-layer seam first, then let the CLI call the service. This keeps the architecture boundary intact and gives Story 6.9 a reusable pattern.

3. **Stage to the shared `/data` volume, never container-local `/tmp`.** The worker is a separate process/container and must be able to read every staged file.

4. **Use unique staged filenames.** Current extraction still copies to `originals_dir / source_path.name` and `markdown_dir / f"{source_path.stem}.md"` in [src/cos/ingestion/extractor.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/extractor.py). If two Gmail artifacts are staged with the same basename, managed copies can overwrite each other before canonical dedupe even runs.

5. **Keep the source identity contract stable and explicit.** Suggested locator forms:
   - body: `gmail://message/<message-id>/body`
   - attachment: `gmail://message/<message-id>/attachment/<attachment-id>`

6. **Byte-identical attachments across different emails must not share the same source locator.** Shared content identity should come from the canonical blob hash, not from collapsing provenance.

7. **Connector errors must be recovery-friendly and non-fatal to the core platform.** Use structured JSON logging with `component: "connector"` and plain-language operator guidance where useful.

8. **Keep scheduler scope out of this story.** A manual one-shot Gmail poll command is enough here. APScheduler-based recurring behaviour belongs later.

### Gmail API Notes (Verified Against Official Docs on 2026-05-06)

Use these implementation facts; they are more precise than guesswork:

- `users.messages.list` returns lightweight message references; fetch full message structure separately with `users.messages.get`
- `users.messages.list` supports `maxResults`, `q`, `labelIds`, `includeSpamTrash`; `maxResults` defaults to 100 and caps at 500
- detached attachment bytes come from `users.messages.attachments.get`
- Gmail message-part body data and attachment data arrive base64url-encoded
- retryable Gmail API failures should use exponential backoff; Google’s guidance starts retries at 1 second and increases from there

### Suggested File Touchpoints

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [src/cos/connectors/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/gmail.py)
- [src/cos/services/gmail.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/gmail.py)
- [src/cos/cli.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/cli.py)
- [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml)
- [uv.lock](/Users/iain.livingstone/Development/CoS/cos/uv.lock)
- [tests/connectors/test_gmail.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_gmail.py)
- [tests/services/test_gmail_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_gmail_service.py)
- [tests/cli/test_cli_sync.py](/Users/iain.livingstone/Development/CoS/cos/tests/cli/test_cli_sync.py)

### Testing Strategy

- Patch the Google discovery client and `HttpError` responses; no live Gmail account or network calls
- Use synthetic MIME payload fixtures that include:
  - plain-text body
  - multipart nesting
  - one supported attachment
  - one unsupported attachment
- Assert exact job payload contracts rather than only high-level counts
- Reuse the existing worker + canonical identity path in at least one integration test so Story 6.3/6.7 behaviour is actually exercised for Gmail source types

### Non-Goals

- No Google Calendar work here
- No APScheduler or always-on scheduler container here
- No `cos status` / health expansion for connector status in this story
- No new ingest pipeline separate from [src/cos/ingestion/pipeline.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/ingestion/pipeline.py)
- No support for unsupported Gmail attachment types beyond clean skip logging
- No broad documentation rewrite; reserve major doc consolidation for Story 6.12

### Review Findings

- [x] [Review][Patch] Inline attachments can collide and filename-less attachments are skipped instead of getting a deterministic fallback identity [src/cos/services/gmail.py:93]
- [x] [Review][Patch] `extract_body_text(...)` can ingest a text attachment as the message body because it does not exclude filename-bearing MIME parts [src/cos/connectors/gmail.py:77]
- [x] [Review][Patch] Retry logic does not treat Gmail 403 rate-limit responses as retryable, so quota throttling can fail fast without backoff [src/cos/connectors/gmail.py:117]
- [x] [Review][Patch] `cos sync gmail` loads config outside its recovery handling, so malformed Gmail config exits before printing an operator-friendly error [src/cos/cli.py:47]

### Source References

- [Epic 6 in epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Architecture decisions for connectors, jobs, and config](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD Gmail / external connectivity requirements](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Previous story: 6.6 OAuth authentication setup](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-6-oauth-authentication-setup-for-gmail-and-calendar.md)
- [Previous story: 6.7 jobs queue and worker](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-7-jobs-queue-and-background-ingestion-worker.md)
- [Google Gmail API `users.messages.list`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- [Google Gmail API `users.messages.get`](https://developers.google.com/gmail/api/v1/reference/users/messages/get)
- [Google Gmail API `users.messages.attachments.get`](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages.attachments/get)
- [Google Gmail API error handling and backoff guidance](https://developers.google.com/workspace/gmail/api/guides/handle-errors)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Integration test for blob deduplication initially used PDF attachments which required Tika; switched to `.txt` to avoid Tika dependency in test environment.
- Integration test failed on first run because `process_next_ingest_job` was only called twice but poll_gmail enqueues 4 jobs (2 body + 2 attachment). Fixed by draining all 4 jobs.

### Completion Notes List

- `GmailConnectorConfig` added to `config.py` as an optional field on `CosConfig`; existing configs load unchanged.
- `google-api-python-client` added as a dependency; `uv.lock` updated.
- `src/cos/connectors/gmail.py` expanded from a stub into a full Gmail API connector with MIME traversal, base64url decoding, and exponential backoff.
- `src/cos/services/gmail.py` created as the service-layer seam; CLI and future connectors must call this, not the connector internals directly.
- `src/cos/cli.py` gains a `sync` sub-app with a `cos sync gmail` command.
- All tests are offline (patched Google client, no live network).
- Integration test proves byte-identical attachments from different messages collapse to one `content_blob` with two `sources` rows via the existing Story 6.2/6.3 canonical identity pipeline.

### File List

- `src/cos/config.py` — added `GmailConnectorConfig`, wired into `CosConfig.gmail`
- `config.yaml.example` — added commented-out `gmail:` block
- `src/cos/connectors/gmail.py` — full Gmail API connector implementation
- `src/cos/services/gmail.py` — new service orchestration layer
- `src/cos/cli.py` — added `sync_app` and `cos sync gmail` command
- `pyproject.toml` — added `google-api-python-client` dependency
- `uv.lock` — updated
- `tests/connectors/test_gmail.py` — 22 unit tests for connector
- `tests/services/test_gmail_service.py` — 9 service tests including blob deduplication integration test
- `tests/cli/test_cli_sync.py` — 5 CLI tests
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 6.8 → review
