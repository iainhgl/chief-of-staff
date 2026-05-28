# Story 8.1: Telegram Bot Setup & Output Channel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want to configure a Telegram bot that the platform can send messages to and receive messages from,
so that Telegram is a live, verified channel before Q&A and note capture are built on top of it.

## Acceptance Criteria

1. **Given** a Telegram bot token is present in `config.yaml` under the Telegram connector configuration,
   **When** the platform starts with Telegram enabled,
   **Then** `telegram_bot.py` begins polling the Telegram Bot API for updates using long polling with graceful backoff.

2. **Given** `output/channels/telegram.py` is implemented,
   **When** `OutputRouter.send(channel="telegram", content="test message")` is called through the output service,
   **Then** the message is delivered to the configured Telegram chat ID only after the router validates the `telegram` channel against the allowed output channels.

3. **Given** Telegram delivery fails,
   **When** the error is handled,
   **Then** output is suppressed, a structured error is logged with `component: "output"`, and the rest of the platform remains healthy.

## Tasks / Subtasks

- [x] Task 1: Add Telegram configuration without breaking existing connector config (AC: #1, #2, #3)
  - [x] Add a `TelegramConnectorConfig` Pydantic model in [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) with at least `bot_token: SecretStr`, `chat_id: str`, `api_base_url: str = "https://api.telegram.org"`, and long-poll/backoff settings with bounded defaults.
  - [x] Add optional `telegram: TelegramConnectorConfig | None = None` to `CosConfig`; keep the existing `connectors: list[str]` activation pattern used by Gmail and Google Calendar.
  - [x] Update [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) with a commented or clearly separated Telegram block and instructions to enable it with `connectors: ["telegram"]`.
  - [x] Add config tests proving the Telegram block is optional, loads when present, validates required fields, and never reveals `bot_token` in `repr(config)` or `str(config)`.

- [x] Task 2: Implement the Telegram output channel behind OutputRouter validation (AC: #2, #3)
  - [x] Replace the current comment-only [telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py) stub with a small async Telegram sender that uses `httpx.AsyncClient` and calls Telegram Bot API `sendMessage`.
  - [x] Refactor [router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py) so network-capable channel handlers can be async; preserve fail-closed behavior for unknown channels and missing handlers.
  - [x] Keep `OutputRouter` handler dependencies injectable at startup. Do not make the Telegram channel read `config.yaml` directly or import server globals.
  - [x] Register the Telegram handler only when Telegram config is present; if `telegram` is permitted by the role pack but no handler is configured, preserve the current "no handler registered" suppression behavior.
  - [x] Log delivery failures as structured JSON with `component: "output"` and `channel: "telegram"`; do not log the bot token, full request URL, or sensitive message body.
  - [x] Update [services/output.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py), MCP call sites, and output tests for the async router contract.

- [x] Task 3: Wire allowed output channels through the active role pack (AC: #2)
  - [x] Update the active CHRO role pack in [chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml) so `output_channels` permits both `local` and `telegram` for the Epic 8 baseline.
  - [x] Keep role-pack-driven output permission as the source of truth. `config.channels` is still legacy/stale for router permission and must not override `RolePackConfig.output_channels`.
  - [x] Fix the existing startup log in [server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py) so it reports the role-pack output channels actually passed to `OutputRouter`, not `config.channels`.
  - [x] Add or update tests in [tests/mcp_server/test_server.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_server.py) proving the router still uses role-pack output channels.

- [x] Task 4: Implement a long-running Telegram polling process (AC: #1, #3)
  - [x] Replace the comment-only [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) stub with an async long-polling loop using Telegram Bot API `getUpdates`.
  - [x] Add a `cos-telegram-bot` script entry point in [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml) and a separate Docker Compose service for the bot, using the same image and mounted config/role packs/certs as the existing `cos` and `worker` services.
  - [x] Keep the polling process separate from the MCP server process so Telegram API failures cannot block local MCP retrieval.
  - [x] Start polling only when `"telegram"` is present in `config.connectors` and `config.telegram` is configured; otherwise emit a clear connector log and exit cleanly.
  - [x] Use `allowed_updates=["message"]`, positive long-poll timeout, and offset advancement after each server response to avoid duplicate update delivery.
  - [x] For Story 8.1, parse and log inbound text-message updates but do not implement Q&A classification or note capture. Those belong to Stories 8.2 and 8.3.
  - [x] Ignore or log messages from chats other than the configured `chat_id`; never reply to unconfigured destinations.
  - [x] Handle network errors, Telegram 429/5xx responses, and webhook-conflict responses with bounded backoff and structured logs under `component: "connector"`, `connector: "telegram"`.

- [x] Task 5: Add focused tests and manual verification notes (AC: #1, #2, #3)
  - [x] Add unit tests for Telegram output delivery using `httpx.MockTransport` or an equivalent injected async client; assert `sendMessage` receives `chat_id` and `text`.
  - [x] Add tests that failed Telegram delivery suppresses output and logs `component: "output"` without raising.
  - [x] Add connector tests for `getUpdates` request parameters, offset advancement, disabled-connector behavior, unauthorised chat filtering, and retry/backoff classification.
  - [x] Update router/output-service tests for async `send`.
  - [x] Run focused tests for config, output, Telegram connector, MCP server startup, plus `uv run ruff` and `uv run mypy`.

### Review Findings

- [x] [Review][Patch] Token-bearing Telegram API URLs leak via httpx INFO logs [src/cos/connectors/telegram_bot.py:27]
- [x] [Review][Patch] Webhook-conflict HTTP responses are downgraded to generic retry warnings [src/cos/connectors/telegram_bot.py:47]
- [x] [Review][Patch] `backoff_initial=0.0` can create a tight retry loop [src/cos/config.py:105]
- [x] [Review][Patch] `sendMessage` ignores Telegram `ok: false` semantic failures [src/cos/output/channels/telegram.py:40]
- [x] [Review][Patch] Empty Telegram token/chat ID values pass startup validation [src/cos/config.py:100]

## Dev Notes

### What This Story Is

Story 8.1 is the Telegram foundation story. It makes Telegram a real, configurable transport and proves outbound delivery plus inbound polling work before the product adds message classification, cited Q&A, or note ingestion. Epic 8 is explicitly reactive Telegram messaging only: no web augmentation, no scheduled briefs, no proactive meeting prep, and no advanced orchestration in this story. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

The story's source acceptance criteria name `connectors.telegram.bot_token`. The current implemented config architecture is different: `connectors` is a list of enabled connector names, while connector-specific settings are top-level blocks such as `gmail:`, `google_calendar:`, and `mcp_note:`. Follow the existing implemented pattern: use `connectors: ["telegram"]` plus a top-level `telegram:` block. Do not refactor `connectors` from `list[str]` into a nested object as part of this story. [Source: [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py), [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

### Current Baseline To Preserve

- Telegram files exist only as stubs today: [connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) and [output/channels/telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py).
- [OutputRouter](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py) currently registers only the local handler and suppresses unknown channels or configured-but-missing handlers by logging `component: "output"`.
- [OutputService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py) is already async but delegates into the currently synchronous router.
- The MCP server initializes the router from `RolePackConfig.output_channels`, not `config.channels`; this is the implemented Epic 4 contract.
- The CHRO role pack currently permits only `local`, so Telegram cannot be delivered until the role pack permits `telegram`.
- Docker Compose currently has `postgres`, `tika`, `cos`, and `worker`; Telegram needs its own long-running process or service rather than being folded into the MCP stdio process. [Source: [router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py), [server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py), [chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml), [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

### Architecture Guardrails

1. **OutputRouter remains the sole egress boundary.**
   Any user-facing output must pass through `OutputRouter`; the Telegram bot and future Q&A path must not call `output/channels/telegram.py` directly. Validation failure suppresses output and logs rather than raising through the caller. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

2. **Make the router async now that a network channel exists.**
   Epic 3 notes explicitly allowed the synchronous router only while local stdout was the sole handler; a future network handler requires an async send path. Story 8.1 is that moment. Update tests and call sites deliberately instead of hiding network I/O behind synchronous calls. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py), [services/output.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py)]

3. **Keep connector failure isolated from MCP retrieval.**
   NFR11 requires connector failures to surface as degraded/error signals while the core retrieval and Q&A path remains available. Run Telegram polling in a separate entry point/process and catch/retry Telegram API failures inside that process. Do not block or crash the MCP server because Telegram is unavailable. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

4. **Do not broaden into Stories 8.2 or 8.3.**
   This story may parse inbound update envelopes and log received text for live verification. It must not implement question classification, `RetrievalService.query(...)`, note staging, ingest jobs, or "Note saved." acknowledgements; those are the next two stories. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

5. **Do not leak credentials or sensitive content.**
   `bot_token` must be a `SecretStr`; logs must not include token values, token-bearing URLs, or full Telegram message contents. Message content may be short and personal; prefer logging lengths, update IDs, chat IDs, and event labels. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)]

6. **Messaging is a lower-trust channel.**
   Telegram is suitable for short notes, quick questions, and concise replies. Even though Q&A is future work, Story 8.1 should avoid adding formatting defaults or examples that imply long-form analytical output should be pushed through Telegram. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Telegram Bot API Details

Use the official Telegram Bot API directly through `httpx`; do not add a Telegram wrapper library for this foundation story. The two API methods needed here are:

- `getUpdates` for long polling. Use a positive `timeout`, pass `allowed_updates=["message"]`, and advance `offset` after each server response to avoid duplicate update delivery. Telegram states `getUpdates` will not work while an outgoing webhook is configured, so handle a webhook-conflict response as a clear degraded/error log rather than crashing the platform. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]
- `sendMessage` for outbound delivery. Send JSON containing configured `chat_id` and `text` to the bot API endpoint; treat non-success responses as delivery failures to suppress/log through the output boundary. [Source: [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)]

Implementation notes for the developer:

- Use `https://api.telegram.org/bot<token>/<method>` internally, but never log the full URL because it contains the token.
- Prefer dependency injection for the async HTTP client or transport so tests can use `httpx.MockTransport`.
- Bound retries/backoff. A simple exponential backoff with a maximum is enough; do not introduce APScheduler, a general task runtime, or a new orchestration dependency.
- Inbound offset persistence can remain in-memory for Story 8.1 because inbound processing has no durable side effects yet. Do not add a database migration for Telegram offsets in this story.

### Suggested File Touchpoints

Primary code:

- [src/cos/config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [src/cos/output/router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py)
- [src/cos/services/output.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py)
- [src/cos/output/channels/telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)
- [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)
- [src/cos/mcp_server/server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py)
- [pyproject.toml](/Users/iain.livingstone/Development/CoS/cos/pyproject.toml)
- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)

Configuration and role pack:

- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [role_packs/chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml)

Tests:

- [tests/test_config.py](/Users/iain.livingstone/Development/CoS/cos/tests/test_config.py)
- [tests/output/test_router.py](/Users/iain.livingstone/Development/CoS/cos/tests/output/test_router.py)
- [tests/services/test_output_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_output_service.py)
- `tests/output/test_telegram.py` or equivalent new test file
- `tests/connectors/test_telegram_bot.py` or equivalent new test file
- [tests/mcp_server/test_server.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_server.py)

### Testing Requirements

Minimum focused verification:

```bash
uv run pytest tests/test_config.py tests/output/test_router.py tests/services/test_output_service.py tests/mcp_server/test_server.py
uv run pytest tests/output/test_telegram.py tests/connectors/test_telegram_bot.py
uv run ruff check
uv run mypy
```

If the developer chooses different test file names, run the equivalent focused set. If Docker Compose service wiring changes, also run:

```bash
docker compose config
```

Do not run live Telegram tests in automated CI unless explicitly marked/manual-gated and configured with real local secrets. Unit tests should mock Telegram with injected `httpx` transports.

### Git Intelligence

Recent history shows the repository just closed Epic 7 cleanly before this story:

- `10cd146` - merge of Epic 7 sprint-status closeout
- `86d0305` - `chore: close epic 7 in sprint status`
- `d53b480` / `9fd551b` - LLM wiki planning docs
- `f323925` - manual evaluation corpus follow-up

Treat Epic 7 as complete and use the current retrieval baseline as a prerequisite, not work to reopen. Story 8.1 should start Epic 8 and keep its changes narrow to Telegram setup/output-channel foundations. [Source: `git log --oneline -5`, [sprint-status.yaml](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/sprint-status.yaml)]

### Project Structure Notes

- No repo-level `project-context.md` file was found.
- The `docs/` project knowledge folder exists, but Story 8.5 owns the user-facing Telegram docs sweep. Story 8.1 should update `config.yaml.example` and any code-adjacent comments needed for setup, but avoid turning this into the full connectors documentation story.
- `docs/connectors.md` does not exist yet; create it only if implementation needs a minimal operator note for Story 8.1. The broader connector guide belongs to Story 8.5.
- There are unrelated worktree changes present (`7-5-benchmark-report.json`, `7-5-benchmark-report-fuzz.json`, token-monitoring research). Do not touch or revert them.

### References

- [Epic 8 definition and Story 8.1 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD channel sensitivity, Telegram requirements, and NFR11/NFR20](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture constraints, OutputRouter contract, project structure, and implementation notes](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Inbound Telegram and OutputRouter diagrams](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Current config model](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)
- [Current OutputRouter](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py)
- [Current OutputService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py)
- [Current MCP startup wiring](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py)
- [Current Docker Compose services](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)
- [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)
- [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)

## File List

- `_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md` - story file
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Epic 8 and Story 8.1 status update
- `src/cos/config.py` - added `TelegramConnectorConfig` model and `telegram` field to `CosConfig`
- `config.yaml.example` - added commented Telegram block with setup instructions
- `src/cos/output/channels/telegram.py` - implemented `TelegramChannel` async sender using httpx
- `src/cos/output/router.py` - refactored `OutputRouter.send` to async; added `extra_handlers` injectable map
- `src/cos/services/output.py` - updated to `await self._router.send(...)`
- `src/cos/mcp_server/server.py` - wires Telegram handler when config present; fixed startup log to use role-pack channels
- `src/cos/connectors/telegram_bot.py` - implemented async long-polling loop with backoff, offset tracking, and structured logging
- `role_packs/chro.yaml` - added `telegram` to `output_channels`
- `pyproject.toml` - added `cos-telegram-bot` entry point
- `docker-compose.yml` - added `telegram-bot` service
- `tests/test_config.py` - added 10 Telegram config tests
- `tests/output/test_router.py` - updated all tests to async; added extra_handler and exception tests
- `tests/services/test_output_service.py` - updated delegate test to use `AsyncMock`
- `tests/mcp_server/test_server.py` - added `telegram=None` to config fixture; updated sync `router.send` calls to `await`; added role-pack channel log test
- `tests/output/test_telegram.py` - new: 5 output channel tests using injected `httpx.AsyncBaseTransport`
- `tests/connectors/test_telegram_bot.py` - new: 12 connector tests for polling, offset, backoff, chat filtering

## Change Log

- 2026-05-28: Story created and sprint status advanced to `ready-for-dev`.
- 2026-05-28: Story implemented — all 5 tasks complete, 82 tests passing, status → review.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1: Added `TelegramConnectorConfig` (bot_token as SecretStr, chat_id, api_base_url, poll_timeout, backoff_initial/max). Optional `telegram` field added to `CosConfig` following the existing Gmail/Calendar pattern. 10 config tests added and passing.
- Task 2: `OutputRouter.send` is now `async def send`. Handler map changed from `dict[str, Callable[[str], None]]` to `dict[str, AsyncHandler]` (where `AsyncHandler = Callable[[str], Awaitable[None]]`). Local channel wrapped in `_local_send` async shim. `extra_handlers` are injectable at construction time. `TelegramChannel.send` uses injected `httpx.AsyncClient` (or creates one) to POST `sendMessage`. Delivery failures log structured JSON with `component: "output", channel: "telegram"` without raising.
- Task 3: `chro.yaml` updated to permit `["local", "telegram"]`. Startup log in `server.py` now emits `channels=_loaded_role_pack.output_channels` (not stale `config.channels`). Server wires `TelegramChannel` into `extra_handlers` only when `config.telegram` is not None. Test added proving startup log reports role-pack channels.
- Task 4: `telegram_bot.py` implements `run_polling` (async infinite loop with `getUpdates` via POST JSON body, offset advancement, bounded exponential backoff). `run()` entry point checks `config.connectors` and `config.telegram` before starting. Unconfigured chats are logged and ignored. Webhook conflicts logged as ERROR. Entry point `cos-telegram-bot` added to `pyproject.toml`; `telegram-bot` service added to `docker-compose.yml` with same volumes as `worker`.
- Task 5: 17 new tests across `tests/output/test_telegram.py` and `tests/connectors/test_telegram_bot.py`. Router and output service tests updated for async contract. MCP server test fixture extended with `telegram=None`. All 82 story-scoped tests pass. Ruff and mypy clean on new/modified files.

### File List
