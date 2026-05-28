# Story 8.2: Telegram Inbound Q&A

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to send a question to the platform via Telegram and receive a cited answer,
so that I can access my knowledge base from my phone without opening a laptop or separate interface.

## Acceptance Criteria

1. **Given** a message is received via the Telegram bot,
   **When** the message classifier runs,
   **Then** it identifies questions using documented heuristics and routes them to the reactive Q&A path.

2. **Given** a message is classified as a question,
   **When** the Q&A path executes,
   **Then** it calls `RetrievalService.query(...)` and delivers a concise Telegram-appropriate cited reply via `OutputRouter.send(channel="telegram")`.

3. **Given** no relevant grounded content is found or synthesis fails,
   **When** the reply is sent,
   **Then** the user receives a clear plain-language outcome rather than silence or an uncaught error.

## Tasks / Subtasks

- [x] Task 1: Add explicit inbound message classification for Story 8.2 scope (AC: #1, #3)
  - [x] Add a small, testable classifier in [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py), for example `_classify_inbound_text(text: str) -> Literal["question", "unsupported"]` or an equivalent enum/dataclass.
  - [x] Document the question heuristics directly beside the classifier with a concise docstring or constant comment, and cover them with named tests. Do not rely on an LLM to classify Telegram messages in this story.
  - [x] Treat text ending in `?`, slash commands such as `/ask`, common question words (`what`, `why`, `how`, `when`, `where`, `who`, `which`), and explicit knowledge-base request phrases (`tell me`, `show me`, `find`, `look up`, `summarise`, `summarize`, `compare`, `brief me`, `draft`) as questions.
  - [x] Leave note capture out of scope. `note:` prefixes and short declarative notes should not enter the Q&A path; Story 8.3 owns note ingestion and "Note saved" acknowledgements.
  - [x] For configured-chat text that is not classified as a question, send a short plain-language response explaining that Telegram Q&A is available and note capture is not yet enabled, rather than silently doing nothing.

- [x] Task 2: Wire the Telegram polling process to existing retrieval and output services (AC: #2, #3)
  - [x] Keep `cos-telegram-bot` as the separate long-running process created in Story 8.1. Do not move Telegram polling into the MCP server process.
  - [x] Build the Q&A dependencies at Telegram bot startup: load `CosConfig`, load the active role pack with `rolepack.loader.load`, create a database pool with `create_pool`, create the LLM adapter with `make_llm_adapter`, construct `RetrievalService`, construct `OutputRouter` with a registered `TelegramChannel`, and wrap it in `OutputService`.
  - [x] Do not import MCP server globals such as `get_retrieval_service()` or reuse the MCP `retrieve` tool function from [tools.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/tools.py). The bot is a separate runtime and should use the same service classes, not the MCP tool envelope.
  - [x] Preserve fail-closed output permission: the bot must call `OutputService.send("telegram", content)` or `OutputRouter.send("telegram", content)`, never `TelegramChannel.send(...)` directly.
  - [x] Ensure startup exits cleanly when `"telegram"` is not in `config.connectors` or `config.telegram` is absent, preserving the Story 8.1 disabled-connector behavior.

- [x] Task 3: Implement the reactive Q&A handler on top of `RetrievalService.query(...)` (AC: #2, #3)
  - [x] Refactor `_handle_update` or add an async handler so configured-chat text updates can be processed without blocking the polling loop longer than the Q&A request itself requires.
  - [x] Continue ignoring updates from chats other than `config.telegram.chat_id`; never reply to unconfigured destinations.
  - [x] Extract only Telegram `message.text` for Story 8.2. Ignore or log non-text messages without calling retrieval or leaking content.
  - [x] For question text, call `RetrievalService.query(text, role_pack=active_role_pack)` exactly once per accepted message.
  - [x] Log structured connector events for accepted question, unsupported text, no-content outcome, synthesis-degraded outcome, and unexpected handler failure. Logs must include update/message identifiers where available, but not full message text or bot tokens.

- [x] Task 4: Format Telegram replies as concise cited plain text (AC: #2, #3)
  - [x] Add a focused formatter, for example `_format_telegram_qa_reply(response: CitedResponse) -> str`, that converts the retrieval response into mobile-appropriate plain text.
  - [x] Successful replies should include the answer plus a compact `Sources:` block derived from `response.citations`. Prefer `source_alias` and `chunk_index`; avoid exposing full `source_locator` values in Telegram unless there is no safer alias.
  - [x] Do not send raw JSON envelopes or MCP-style `{"status": ...}` payloads to Telegram.
  - [x] Do not enable Markdown or HTML `parse_mode` for this story. Plain text avoids escaping bugs and is enough for cited Q&A.
  - [x] Keep the final message within Telegram's `sendMessage` text limit of 4096 characters. Prefer trimming the answer and limiting citation count over sending an overlong message that Telegram rejects.
  - [x] When `response.answer` is `"No relevant content found in the knowledge base."` with no citations, send a clear no-content message to the user.
  - [x] When `response.answer is None` because synthesis failed but citations exist, send a clear degraded message. Include a compact source list only if it helps the user understand that material was found but synthesis failed.
  - [x] If `RetrievalService.query(...)` raises unexpectedly, catch it in the Telegram handler and send a short recovery message such as "I could not answer that just now. Check `cos logs` for diagnostics." Do not let the poller crash.

- [x] Task 5: Add focused tests and verification commands (AC: #1, #2, #3)
  - [x] Extend [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py) for classifier heuristics, unsupported text behavior, configured-chat filtering, non-text update handling, Q&A routing, no-content response, synthesis-degraded response, and retrieval exception recovery.
  - [x] Use `AsyncMock` or injected lightweight test doubles for `RetrievalService` and `OutputService`; do not make live Telegram, live LLM, or live database calls in unit tests.
  - [x] Add or update tests proving the Q&A handler calls retrieval once with the active role pack and sends through the output service on channel `"telegram"`.
  - [x] Add tests proving formatter output includes citation aliases, avoids raw JSON, stays under 4096 characters for long answers, and does not include full sensitive locators when aliases are present.
  - [x] Preserve existing Story 8.1 tests for polling, token redaction, webhook conflict logging, output channel delivery, and config validation.
  - [ ] Run focused tests and static checks:

    ```bash
    uv run pytest tests/connectors/test_telegram_bot.py tests/output/test_telegram.py tests/output/test_router.py tests/services/test_retrieval_service.py
    uv run pytest tests/mcp_server/test_server.py tests/services/test_output_service.py tests/test_config.py
    uv run ruff check
    uv run mypy
    docker compose config
    ```

### Review Findings

- [x] [Review][Decision] Keep Telegram sender authorization scoped to configured `chat_id` for Story 8.2 — resolved by user decision during review.
- [x] [Review][Patch] Add a simple per-question retrieval timeout while keeping serial polling [src/cos/connectors/telegram_bot.py:235]
- [x] [Review][Patch] Ensure every Telegram reply path stays within 4096 characters and preserves a usable source block [src/cos/connectors/telegram_bot.py:121]
- [x] [Review][Patch] Sanitize citation labels before showing them in Telegram replies [src/cos/connectors/telegram_bot.py:105]
- [x] [Review][Patch] Include Telegram `message_id` in structured handler logs when available [src/cos/connectors/telegram_bot.py:220]
- [x] [Review][Patch] Keep malformed update payloads inside per-update error handling so one bad update cannot skip the rest of a batch [src/cos/connectors/telegram_bot.py:198]
- [x] [Review][Patch] Tighten `/ask` and phrase classification boundaries, and normalize `/ask` before retrieval [src/cos/connectors/telegram_bot.py:91]
- [x] [Review][Patch] Avoid sending an empty Telegram message when retrieval returns an empty answer [src/cos/connectors/telegram_bot.py:133]
- [x] [Review][Patch] Exit non-zero for invalid role-pack startup errors instead of returning successfully [src/cos/connectors/telegram_bot.py:329]

## Dev Notes

### What This Story Is

Story 8.2 turns the Telegram bot from a verified transport into a reactive Q&A interface. It should reuse the hardened retrieval and output substrate that already exists: classify inbound Telegram text, route questions to `RetrievalService.query(...)`, format a short cited answer, and send it through the Telegram output channel guarded by `OutputRouter`. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

This story must not implement note capture. The architecture diagram shows the inbound Telegram branch splitting into note capture and question handling, but Story 8.3 owns the note path, ingest job enqueueing, Telegram metadata, and "Note saved" acknowledgements. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

### Current Baseline To Preserve

- [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) already loads `CosConfig`, exits cleanly when Telegram is disabled, long-polls `getUpdates`, advances offsets, filters unauthorized chats, logs inbound text length, handles webhook conflicts, and redacts bot tokens.
- [telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py) already implements async `sendMessage` delivery with `httpx`, handles non-2xx and `ok: false`, logs structured output failures, and suppresses exceptions.
- [router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py) is already async and fail-closed: unknown channels, missing handlers, and handler exceptions log `component: "output"` rather than raising through callers.
- [server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py) builds the MCP runtime with a role pack, database pool, LLM adapter, `RetrievalService`, `OutputRouter`, and `OutputService`. Reuse the same service classes and patterns, but do not depend on server globals from the Telegram process.
- [RetrievalService.query](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py) already returns `CitedResponse(answer, citations)`, including no-content and synthesis-degraded outcomes. Do not reimplement hybrid search, citation selection, context expansion, or LLM prompting in the Telegram connector.
- [role_packs/chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml) already permits `telegram` in `output_channels`; role-pack output channels remain the egress source of truth.

### Architecture Guardrails

1. **Retrieval before generation remains mandatory.**
   Telegram Q&A must call the existing retrieval service and use its `CitedResponse`. Do not call an LLM directly from `telegram_bot.py`, and do not synthesize answers without citations. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [retrieval.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)]

2. **OutputRouter remains the only egress boundary.**
   The architecture explicitly marks direct `telegram_bot.send_message(chat_id, response)` as wrong. Every Telegram reply must pass through `OutputRouter` or `OutputService` on channel `"telegram"` so configured channel validation and failure suppression still apply. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py)]

3. **Telegram is a lower-trust channel.**
   Messaging channels are for short notes, quick questions, and brief digests, not full analytical documents. Keep answers concise, include compact citations, and avoid dumping source locators or long sensitive excerpts into Telegram. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

4. **Connector failures must not take down core retrieval.**
   NFR11 requires connector failures to surface as degraded/error signals while the core retrieval and Q&A path remains available. Catch Telegram-handler errors inside the bot process, log them as connector errors, and send a user-readable fallback when possible. Do not crash the MCP server because Telegram Q&A fails. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)]

5. **Preserve credential and content hygiene.**
   Continue using `SecretStr` for the Telegram token. Logs must not include token-bearing URLs, full inbound message text, full outbound answer text, or local file paths when safer identifiers are available. Prefer lengths, update IDs, chat IDs, outcome labels, and trace-level operational metadata. [Source: [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py), [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)]

6. **Avoid a new orchestration layer.**
   This is a reactive, single-message path. Do not add APScheduler usage, task runtime records, queues, new databases, multi-agent orchestration, web search, or provider-routing abstractions as part of Story 8.2. Later epics own those expansions. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

### Telegram Bot API Details

- `getUpdates` receives incoming updates with long polling. Telegram documents that positive `timeout` is long polling, offset should be recalculated after each server response to avoid duplicate updates, and `getUpdates` will not work while a webhook is configured. Story 8.1 already implemented these foundations; preserve them. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]
- `sendMessage` requires a `chat_id` and `text`. Telegram currently limits message text to 4096 characters after entity parsing. Because this story should use plain text with no `parse_mode`, the formatter can treat 4096 as the hard output ceiling and keep a small buffer for safety. [Source: [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)]
- Telegram update payloads include many update types. Keep `allowed_updates=["message"]` from Story 8.1 and handle only `message.text` for this story. Do not add inline queries, callback queries, voice transcription, photos, documents, or webhooks. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]

### Suggested File Touchpoints

Primary code:

- [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) - classifier, async Q&A handler, runtime wiring, reply formatter, structured connector logs.
- [src/cos/output/channels/telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py) - only if a small guard is needed for the 4096-character send limit; prefer formatting in the Q&A layer first.
- [src/cos/mcp_server/server.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/mcp_server/server.py) - avoid touching unless extracting shared startup helpers is clearly cleaner than duplicating runtime construction.
- [src/cos/retrieval/citations.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/retrieval/citations.py) - avoid changing retrieval semantics; a Telegram-specific formatter can consume `CitedChunk` without altering citation selection.

Tests:

- [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py) - primary Story 8.2 test surface.
- [tests/output/test_telegram.py](/Users/iain.livingstone/Development/CoS/cos/tests/output/test_telegram.py) - only if channel-level send-limit behavior changes.
- [tests/output/test_router.py](/Users/iain.livingstone/Development/CoS/cos/tests/output/test_router.py) and [tests/services/test_output_service.py](/Users/iain.livingstone/Development/CoS/cos/tests/services/test_output_service.py) - protect async egress behavior if touched.
- [tests/mcp_server/test_server.py](/Users/iain.livingstone/Development/CoS/cos/tests/mcp_server/test_server.py) - protect shared startup behavior if a helper is extracted.

### Previous Story Intelligence

Story 8.1 established the Telegram foundation and had review findings that matter directly here:

- Token-bearing Telegram API URLs leaked through `httpx` INFO logs before logging was tightened. Keep `logging.getLogger("httpx").setLevel(logging.WARNING)` or equivalent protection, and never log full request URLs. [Source: [8-1 story](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md), [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)]
- Webhook-conflict responses needed explicit error classification. Preserve the current conflict handling while adding Q&A behavior. [Source: [8-1 story](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md)]
- `backoff_initial=0.0` was patched because it could create tight retry loops. Do not introduce new unbounded retry or sleep-free loops around Q&A failures. [Source: [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)]
- `sendMessage` semantic failures with `ok: false` are already treated as delivery failures. Q&A code should trust `OutputRouter`/`TelegramChannel` to suppress delivery failures rather than adding a second raw Telegram client. [Source: [telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)]
- Empty Telegram token/chat ID validation was patched in `TelegramConnectorConfig`. Do not bypass `CosConfig.load()` or hand-parse `config.yaml`. [Source: [config.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py)]

### Git Intelligence

Recent history is directly relevant:

- `3893087 fix(epic-8): address Telegram review findings` patched Story 8.1 review issues in config, Telegram polling, Telegram output delivery, and tests.
- `f754de1 feat(epic-8): implement Telegram bot foundation - story 8.1` added the `cos-telegram-bot` entry point, Docker Compose service, async output router, Telegram channel, and Telegram connector tests.
- `10cd146 Merge pull request #58 ...` and `86d0305 chore: close epic 7 in sprint status` confirm Epic 7 retrieval trust is complete. Treat the retrieval baseline as a prerequisite, not work to reopen.

### Project Structure Notes

- No repo-level `project-context.md` file was found.
- There are existing unrelated worktree changes outside Story 8.2 context: `_bmad-output/implementation-artifacts/7-5-benchmark-report.json`, `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json`, `_bmad-output/planning-artifacts/research/cos-token-monitoring-and-cost-audit-options-2026-05-27.md`, and `.vscode/`. Do not touch or revert them.
- `docs/connectors.md` still does not exist. Story 8.5 owns the broader Telegram documentation sweep, so Story 8.2 should keep documentation minimal and directly tied to classifier heuristics and tests.
- Branch strategy from repo instructions still applies for implementation: create a feature branch per story before coding, commit there, push/open PR after review patches, and wait for user approval/merge before the next story.

### References

- [Epic 8 definition and Story 8.2 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD FR11-FR17, FR21, FR34, FR36, NFR5, NFR7, NFR11, and messaging channel sensitivity](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture anti-patterns and project boundaries](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Inbound Telegram Q&A or note-capture flow](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Current Telegram connector](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)
- [Current Telegram output channel](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)
- [Current OutputRouter](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py)
- [Current RetrievalService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py)
- [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)
- [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented `_classify_inbound_text(text: str) -> Literal["question", "unsupported"]` with documented heuristics constants (`_QUESTION_WORDS`, `_QUESTION_PHRASES`). No LLM classification used.
- Added `_format_telegram_qa_reply(response: CitedResponse) -> str` that produces plain-text replies with a compact `Sources:` block using `source_alias` and `chunk_index`, with progressive trimming to stay within the 4096-character Telegram limit.
- Converted `_handle_update` to async with optional `retrieval_service`, `output_service`, `role_pack` parameters (defaulting to `None` for backward compat with existing log-only tests). When services are wired, routes questions to `RetrievalService.query()` once per message and sends all output through `OutputService.send("telegram", ...)`.
- Added `_run_telegram_bot(config)` async startup function that builds all Q&A dependencies (role pack, pool, LLM adapter, OutputRouter, OutputService, RetrievalService) before calling `run_polling`. `run()` now calls `asyncio.run(_run_telegram_bot(config))`.
- Updated `run_polling` signature to accept optional service kwargs, forwards them to `_handle_update` without breaking existing test callers.
- Existing sync `_handle_update` tests updated to async (`@pytest.mark.asyncio`) — behaviour preserved, only the awaiting mechanism changed.
- 54 tests total (54/54 pass): 14 Story 8.1 baseline tests preserved, 23 classifier heuristic tests, 8 handler routing tests, 9 formatter tests.
- Pre-existing failures in `test_retrieval_service.py` (2 `compare`-query tests) confirmed on `main` before this story; not caused by Story 8.2 changes.

### File List

- `src/cos/connectors/telegram_bot.py` (modified)
- `tests/connectors/test_telegram_bot.py` (modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified)
- `_bmad-output/implementation-artifacts/8-2-telegram-inbound-qa.md` (modified)

## Change Log

- 2026-05-28: Story 8.2 implementation — added inbound message classifier, Q&A handler, reply formatter, async startup wiring, and 40 new tests (claude-sonnet-4-6)
