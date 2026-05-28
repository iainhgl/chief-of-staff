# Story 8.3: Telegram Note Capture

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to send a short note or thought to the platform via Telegram and have it saved immediately,
so that in-the-moment capture becomes part of the searchable knowledge base.

## Acceptance Criteria

1. **Given** a message is classified as a note,
   **When** the note capture path executes,
   **Then** it routes the content into the Epic 6 ingest/job substrate with Telegram metadata including sender and timestamp.

2. **Given** the note is ingested successfully,
   **When** confirmation is returned,
   **Then** the user receives a short acknowledgement such as `"Note saved."`.

3. **Given** the note has been ingested,
   **When** `list_documents` or `retrieve` is used later,
   **Then** the note appears as a first-class document with canonical provenance and searchable content.

## Tasks / Subtasks

- [x] Task 1: Extend inbound classification for note capture without breaking Q&A (AC: #1)
  - [x] Update the current classifier in [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) to return `question`, `note`, or `unsupported` using a small enum or `Literal`.
  - [x] Treat an explicit `note:` prefix, case-insensitive and whitespace-tolerant, as the guaranteed note path. Strip the prefix before ingesting so the stored note contains the user's content, not the command wrapper.
  - [x] Support deterministic short declarative notes only if the heuristic is conservative and tested. Keep bare greetings, empty text, `/start`, `/help`, unknown slash commands, and malformed values out of ingestion.
  - [x] Preserve Q&A precedence and behavior from Story 8.2: `/ask`, question words, request phrases, and trailing `?` still route to retrieval unless the user explicitly uses the `note:` prefix.
  - [x] Reject `note:` with no remaining content by sending a plain-language guidance response; do not enqueue empty notes.
  - [x] Update the unsupported-message copy so it no longer says note capture is unavailable once this story lands.

- [x] Task 2: Stage Telegram notes and enqueue canonical ingest jobs (AC: #1, #3)
  - [x] Add a narrow Telegram note-staging helper, for example `_stage_telegram_note(...)`, in [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) or a small connector service module if the helper becomes too large.
  - [x] Add `staging_dir: Path = Path("/data/connector-staging/telegram")` to `TelegramConnectorConfig` and [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example), preserving the existing optional top-level `telegram:` config pattern.
  - [x] Write a UTF-8 Markdown staged copy under the Telegram staging directory. Include a concise metadata header with captured timestamp, sender display/user id when available, chat id, message id, and then the note body.
  - [x] Use `source_type="telegram_note"` for Telegram note jobs; do not reuse `mcp_note` because Telegram is a distinct source channel.
  - [x] Build a stable `source_locator`, preferably `telegram://chat/{chat_id}/message/{message_id}`; if `message_id` is unavailable, use `update_id` as the fallback. Do not use the note text, content hash, or raw filename as the locator.
  - [x] Build a human-readable `source_alias` ending in `.md`, for example `telegram-note-2026-05-28T101530Z-4321.md`, with safe fallback slugs for missing timestamps or IDs.
  - [x] Include Telegram metadata in the job payload: `connector`, `chat_id`, `message_id`, `update_id`, sender fields from `message.from` where available, Telegram message `date` converted to ISO-8601 UTC, `received_at`, and `content_fingerprint`.
  - [x] Use the existing jobs substrate: open a Postgres async connection from `config.database.libpq_dsn` and call [submit_ingest_job](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) rather than calling the MCP `ingest_document` tool or creating a parallel ingestion path.
  - [x] Before enqueueing, use [has_processed_artifact](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) and [has_pending_job_for_locator](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) with the content fingerprint so duplicate Telegram update delivery does not create duplicate pending jobs.
  - [x] If the source is already processed or already queued with the same fingerprint, treat the user-facing outcome as saved and return the same short acknowledgement.

- [x] Task 3: Wire note capture into the Telegram handler and output boundary (AC: #1, #2)
  - [x] Extend `_handle_update(...)` so configured-chat text classified as `note` durably stages the note, enqueues the ingest job, and then sends `"Note saved."` through `OutputService.send("telegram", ...)`.
  - [x] Preserve unconfigured-chat filtering, non-text ignore behavior, malformed payload handling, message-id logging, retrieval timeout handling, and Q&A reply formatting from Story 8.2.
  - [x] Keep all user-facing Telegram replies behind `OutputService`/`OutputRouter`; do not call `TelegramChannel.send(...)` or Telegram `sendMessage` directly from the note path.
  - [x] Log structured connector events for note accepted, note already queued/processed, note enqueued, invalid empty note, and note-save failure. Logs must include IDs and lengths, not full note content or bot tokens.
  - [x] On enqueue/staging/database failure, catch the error inside the Telegram process and send a short recovery reply such as `"I could not save that note just now. Check `cos logs` for diagnostics."` Do not crash the polling loop.

- [x] Task 4: Prove Telegram notes become first-class retrievable documents (AC: #3)
  - [x] Ensure the existing worker path can process `source_type="telegram_note"` jobs without schema changes or connector-specific branching.
  - [x] Add tests that enqueue/process a Telegram note job through [process_next_ingest_job](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) and confirm `list_documents` exposes the Telegram `source_alias` and `source_locator`.
  - [x] Add a retrieval-oriented test at the lowest practical level proving the note body is chunked/searchable after the worker processes the job. Use the existing mocked embedding pattern; do not call live Telegram, live LLM, or live embedding APIs.
  - [x] Preserve canonical identity semantics: exact byte duplicates across files/MCP/Telegram should link to known content rather than duplicate canonical documents.

- [x] Task 5: Add focused automated coverage and verification commands (AC: #1, #2, #3)
  - [x] Extend [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py) for `note:` classification, prefix stripping, empty note guidance, declarative-note heuristic if implemented, duplicate update suppression, note-save success acknowledgement, note-save failure recovery, and unchanged Q&A routing.
  - [x] Add config tests in [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py) for the optional Telegram `staging_dir` default and override.
  - [x] Add service/store tests near [tests/services/test_jobs_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_jobs_service.py) or [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py) for the `telegram_note` job lifecycle and canonical provenance.
  - [x] Preserve existing Story 8.1 and 8.2 tests for polling, token redaction, webhook conflict logging, configured-chat filtering, Q&A routing, reply formatting, and output-router egress.
  - [x] Run focused tests and static checks:

    ```bash
    uv run pytest tests/connectors/test_telegram_bot.py tests/test_config.py tests/services/test_jobs_service.py tests/services/test_ingestion_service.py tests/mcp_server/test_tools.py
    uv run pytest tests/output/test_telegram.py tests/output/test_router.py tests/services/test_output_service.py tests/mcp_server/test_server.py
    uv run ruff check
    uv run mypy
    docker compose config
    ```

### Review Findings

- [x] [Review][Patch] Missing retrieval/search proof for Telegram note body [tests/services/test_jobs_service.py:354]
- [x] [Review][Patch] Note-save error handling conflates enqueue success with acknowledgement failure [src/cos/connectors/telegram_bot.py:517]
- [x] [Review][Patch] Failed enqueue leaves orphaned staged note files [src/cos/connectors/telegram_bot.py:511]
- [x] [Review][Patch] Required note event logs omit note/text lengths [src/cos/connectors/telegram_bot.py:463]

## Dev Notes

### What This Story Is

Story 8.3 completes the reactive Telegram slice by turning inbound text notes into canonical knowledge-base material. It should extend the separate `cos-telegram-bot` process from Stories 8.1 and 8.2, classify note messages deterministically, stage the note as Markdown, enqueue an ingest job, and acknowledge the save through the existing Telegram output channel. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

This story is not a documentation sweep, not proactive scheduling, not web augmentation, and not a new task runtime. Story 8.4 owns live operator validation; Story 8.5 owns broader user-facing docs. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

### Current Baseline To Preserve

- [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) already long-polls Telegram, filters to the configured `chat_id`, handles malformed/non-text updates, classifies Q&A, calls `RetrievalService.query(...)`, and sends replies through `OutputService`.
- `_classify_inbound_text(...)` currently returns `question` or `unsupported`. `note:` prefixes and declarative notes were intentionally unsupported in Story 8.2; this story should update those tests rather than work around them.
- [TelegramChannel](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py), [OutputRouter](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py), and [OutputService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py) already provide the fail-closed egress boundary. Reuse it for `"Note saved."`.
- [submit_ingest_job](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) and the `worker` Compose service are the existing connected-ingest substrate. Gmail and Calendar stage files and enqueue jobs; Telegram note capture should follow that connector pattern.
- [IngestService.ingest_note](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/ingestion.py) and the MCP `ingest_document` tool exist, but they are the synchronous MCP note path. Do not call the MCP tool from Telegram, and do not label Telegram notes as `mcp_note`.
- [process_next_ingest_job](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) already hydrates queued ingest jobs and calls `run_pipeline_from_source(...)`, which applies canonical identity, exact-byte dedupe, chunking, embeddings, and source provenance.

### Architecture Guardrails

1. **Use the job substrate for Telegram notes.**
   Story 8.3 acceptance criteria and the Epic 8 sequence diagram explicitly put note capture through the ingest/job path. Avoid direct pipeline calls from the bot unless a review explicitly approves changing the story contract. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

   For this async connector path, the user-facing `"Note saved."` acknowledgement should mean the note has been durably staged and an ingest job has been successfully queued or deduplicated as already queued/processed. Worker completion and later retrieval are verified separately under AC #3.

2. **Keep source truth separate from generated output.**
   The note body and Telegram provenance are source material. The `"Note saved."` acknowledgement is generated output and must not be stored as part of the note. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

3. **Preserve canonical identity and provenance.**
   Filenames, Telegram message text, and content hashes are not the source identity. Use a stable Telegram source locator plus the existing canonical blob/version/source model. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

4. **OutputRouter remains the only Telegram egress path.**
   All acknowledgements and error replies must go through `OutputService.send("telegram", ...)` or `OutputRouter.send("telegram", ...)`. This keeps role-pack channel permissions and fail-closed delivery intact. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

5. **Telegram remains a lower-trust channel.**
   Acknowledge saves tersely. Do not echo the note body back to Telegram, and do not include local source locators or long diagnostic detail in user-facing replies. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

6. **Do not broaden the classifier into LLM intent detection.**
   Keep note/question routing deterministic and testable. No LLM classification, no new orchestration layer, and no provider-routing work in this story.

7. **Connector failures must stay isolated.**
   Staging, enqueueing, database, or Telegram delivery failures should log degraded/error outcomes in the Telegram process while local MCP retrieval remains available. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Telegram Note Metadata Contract

Use the Telegram `message` payload as the source observation:

- `message.message_id` is the preferred per-chat stable message identifier when it is present and non-zero.
- `message.chat.id` must still match the configured `telegram.chat_id`.
- `message.from` is optional; extract sender fields only when present.
- `message.date` is a Unix timestamp. Convert it to ISO-8601 UTC for staged Markdown and job metadata.
- `message.text` is the only accepted note content field for this story. Do not ingest captions, photos, voice notes, documents, checklists, or forwarded media.

Recommended staged Markdown shape:

```markdown
# Telegram Note

Captured: 2026-05-28T10:15:30+00:00
Sender: Iain Livingstone (@iain, id 123456)
Chat ID: 111222333
Message ID: 4321

---

Actual note body here.
```

Keep this shape simple. The goal is searchable note content and visible provenance, not rich Telegram export fidelity.

### Latest Telegram API Notes

- The official Telegram Bot API `Message` object currently exposes `message_id`, optional `from`, `chat`, Unix `date`, and optional `text` for text messages. Build metadata defensively because some fields are optional. [Source: [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)]
- `getUpdates` is still the long-polling API already used by Story 8.1. Keep `allowed_updates=["message"]` and in-memory offset advancement; do not switch to webhooks in this story. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]
- `sendMessage` remains the reply mechanism behind `TelegramChannel`; this story should not add parse modes or rich formatting for acknowledgements. [Source: [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)]

### Previous Story Intelligence

Story 8.2 learnings that matter directly:

- The Telegram process is separate from the MCP server and builds its own config, role pack, database pool, LLM adapter, retrieval service, output router, and output service. Keep note-specific dependencies local to this process; do not import MCP server globals.
- `OutputService.send("telegram", ...)` is the safe outbound path. Direct `TelegramChannel` calls were explicitly avoided.
- Logs include update/message identifiers and content lengths, not full message text. Preserve that privacy boundary for notes.
- The retrieval timeout and Q&A failure handling must continue to work unchanged after note capture is added.
- `/ask` normalization and question phrase boundaries were tightened in review. Add note parsing around that logic carefully so Q&A does not regress.

Epic 6 learnings that matter directly:

- `ingest_document` proved synthetic note capture should reuse the canonical pipeline and exact-byte dedupe semantics.
- The MCP path is synchronous by design, but Telegram is a connected-source path. For Telegram, stage a file and submit an ingest job like Gmail/Calendar.
- `metadata.external_id` is meaningful for MCP notes, but Telegram should use Telegram source locator fields (`chat_id`, `message_id`/`update_id`) for idempotency.
- The current worker does not persist arbitrary job metadata into canonical tables. If sender/timestamp must be visible later, include essential provenance in the staged Markdown and source locator/alias, not only in the job payload.

Recent git history:

- `593ca73 feat(epic-8): implement Telegram inbound QA` completed Story 8.2.
- `3893087 fix(epic-8): address Telegram review findings` patched token redaction, webhook conflict logging, backoff validation, and Telegram delivery error handling.
- `f754de1 feat(epic-8): implement Telegram bot foundation - story 8.1` added the Telegram bot entry point, Compose service, output channel, and config model.

### Suggested File Touchpoints

Primary code:

- [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) - classifier, note normalisation, staging helpers, enqueueing, note handler, structured logs.
- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) - optional Telegram staging directory field.
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) - document the Telegram note staging default.
- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py) - avoid changes unless helper extraction is necessary; `submit_ingest_job` already exists.
- [src/cos/store/db.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/store/db.py) - avoid changes unless existing duplicate checks are insufficient for Telegram.
- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py) - avoid changes unless verification shows the worker cannot process `telegram_note` jobs generically.

Tests:

- [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py) - main unit surface for classification, note handling, output calls, and failure recovery.
- [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py) - Telegram config validation/defaults.
- [tests/services/test_jobs_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_jobs_service.py) - worker/job lifecycle for `telegram_note`.
- [tests/services/test_ingestion_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_ingestion_service.py) - canonical identity and dedupe regression coverage if easier there.
- [tests/mcp_server/test_tools.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_tools.py) - protect `list_documents`/`retrieve` envelopes if provenance output changes.

### Non-Goals

- No live Telegram tests in automated coverage.
- No webhook migration.
- No voice/photo/document ingestion.
- No new Telegram wrapper library.
- No database schema expansion solely to store arbitrary Telegram metadata.
- No change to role-pack output permissions unless tests prove the current CHRO `telegram` channel permission has regressed.
- No web search, proactive briefings, scheduler work, or task-runtime records.

### Project Structure Notes

- No repo-level `project-context.md` file was found.
- `docs/connectors.md` still does not exist. Story 8.5 owns the broader Telegram docs sweep; keep this story's documentation changes limited to code-adjacent config comments.
- Existing unrelated untracked files are present: `.vscode/`, `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json`, and `_bmad-output/planning-artifacts/research/cos-token-monitoring-and-cost-audit-options-2026-05-27.md`. Do not touch or revert them.
- Branch strategy still applies for implementation: create a story branch before coding, commit there, push/open a PR after review patches, and wait for user approval/merge before starting the next story.

### References

- [Epic 8 definition and Story 8.3 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [Inbound Telegram Q&A or note-capture flow](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Architecture constraints and Epic 6 implementation notes](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [PRD FR9, FR34, NFR11, NFR20, and channel sensitivity](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Previous story: 8.2 Telegram inbound Q&A](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-2-telegram-inbound-qa.md)
- [Previous story: 8.1 Telegram bot setup and output channel](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md)
- [Previous story: 6.10 ingest_document MCP tool](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/6-10-ingest-document-mcp-tool.md)
- [Current Telegram connector](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)
- [Current jobs service](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)
- [Current worker](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)
- [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)
- [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)
- [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation ran cleanly; only ruff E501 line-length violations required iterative fixes.

### Completion Notes List

- Added `staging_dir` to `TelegramConnectorConfig` and documented it in `config.yaml.example`.
- Classifier extended to `Literal["question", "note", "unsupported"]`; `note:` prefix wins deterministically before Q&A heuristics.
- `_normalise_note_text` strips prefix and leading whitespace before staging; empty body returns guidance reply, not an ingest job.
- Note staging produces a UUID-suffixed filename to prevent collisions on delivery retries; the human-readable alias is still `telegram-note-<iso8601>-<message_id>.md`.
- Dedup via `has_processed_artifact`/`has_pending_job_for_locator` before staging; both return `"Note saved."` to avoid leaking internal queue state.
- Pool passed as `pool: Any = None` through `run_polling` → `_handle_update`; tests mock with `@asynccontextmanager` helper.
- Worker processes `telegram_note` source_type generically — no schema changes required.
- 230 tests pass across bot, config, and jobs suites. All ruff checks clean; mypy errors are all pre-existing (unrelated files).

### File List

- `src/cos/connectors/telegram_bot.py` — classifier, note path, staging helpers, metadata builders, structured logs
- `src/cos/config.py` — `staging_dir` field on `TelegramConnectorConfig`
- `config.yaml.example` — documented `staging_dir` for Telegram connector
- `tests/connectors/test_telegram_bot.py` — 45+ new Story 8.3 unit tests; renamed one 8.2 test
- `tests/test_config.py` — 3 new tests for `staging_dir` default and override
- `tests/services/test_jobs_service.py` — 4 new integration tests for `telegram_note` job lifecycle

## Change Log

- 2026-05-28: Story context created and marked ready-for-dev.
- 2026-05-28: Implementation complete; status set to review.
- 2026-05-28: Code review patches applied; status set to done.
