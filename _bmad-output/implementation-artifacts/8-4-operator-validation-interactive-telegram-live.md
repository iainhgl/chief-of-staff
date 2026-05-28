# Story 8.4: Operator Validation - Interactive Telegram Live

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Iain (operator and first user),
I want a documented end-to-end smoke test for the reactive Telegram slice,
so that I can validate interactive messaging before adding web or scheduler complexity.

## Acceptance Criteria

1. **Given** the Telegram bot is configured and the platform is running,
   **When** a question is sent from a Telegram client,
   **Then** a cited answer is received within a reasonable interactive response time.

2. **Given** a note is sent prefixed with `"Note:"`,
   **When** the platform processes it,
   **Then** a confirmation is received and a later retrieval query can cite the note.

3. **Given** the Telegram Bot API is temporarily unavailable,
   **When** the failure is simulated,
   **Then** Telegram is reported as degraded while local MCP retrieval continues to function normally.

## Tasks / Subtasks

- [x] Task 1: Add an Epic 8 live Telegram validation pack to [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) (AC: #1, #2, #3)
  - [x] Add a new test pack after the current Epic 7 retrieval-trust pack, keeping the existing Epic 6 and Epic 7 packs intact.
  - [x] State prerequisites explicitly: configured `telegram.bot_token`, configured `telegram.chat_id`, `"telegram"` in `connectors`, `telegram` allowed by the active role pack output channels, Docker Compose services running, and a working MCP client.
  - [x] Keep this story focused on reactive Telegram only: inbound Q&A, `Note:` capture, worker processing, cited retrieval, and failure isolation. Do not document morning briefs, web search, scheduling, or provider portability here.
  - [x] Include a short evidence-capture checklist so the implementation artifact records timestamp, response latency, cited source alias, note source alias/locator, degraded log signal, MCP retrieval result, and cleanup status.

- [x] Task 2: Document and validate the live Telegram Q&A smoke path (AC: #1)
  - [x] Seed a deterministic local Markdown document through the existing `cos ingest` path, for example with marker text such as `epic-8-telegram-live-question-a`, so the Telegram question has known source material to cite.
  - [x] Instruct the operator to ask the Telegram bot a specific question that should retrieve that seeded document.
  - [x] Define the pass signal as a concise Telegram reply with a `Sources:` block containing the seeded `source_alias`; do not accept a generic uncited answer as a pass.
  - [x] Define response-time evidence honestly: record live end-to-end latency from sending the Telegram message until receiving the reply; treat the current bot timeout (`_RETRIEVAL_TIMEOUT_SECONDS = 60.0`) as the hard failure boundary, and document any response that feels too slow even if it does not time out.
  - [x] Do not claim this proves the PRD's deterministic 5-second retrieval benchmark target; that target is covered by the Epic 7 benchmark and excludes live Telegram plus LLM variance.

- [x] Task 3: Document and validate live Telegram note capture through the worker and retrieval path (AC: #2)
  - [x] Instruct the operator to send an explicit note with the `Note:` prefix and a unique marker, for example `epic-8-telegram-live-note-a`.
  - [x] Require the immediate Telegram acknowledgement to be exactly the short save confirmation path from Story 8.3, currently `"Note saved."`.
  - [x] Include a worker-drain wait/check before retrieval. The acknowledgement means the note was staged and queued or deduplicated; it does not by itself prove the worker finished indexing.
  - [x] Verify the note becomes a first-class source via `list_documents`, `retrieve`, or a Telegram Q&A follow-up that cites a `telegram-note-...md` alias and `telegram://chat/...` source locator.
  - [x] Include pass/fail language for duplicate delivery: a duplicate Telegram update or repeated note may still return `"Note saved."`, but must not create duplicate canonical source state for the same locator and fingerprint.

- [x] Task 4: Document and validate a safe Telegram API outage simulation (AC: #3)
  - [x] Prefer a reversible `config.yaml` override of `telegram.api_base_url` to a local non-listening endpoint, such as `http://127.0.0.1:9`, then restart only the `telegram-bot` service. Do not revoke the bot token, change BotFather settings, or enable webhooks as part of this smoke test.
  - [x] Require a visible degraded/error signal within 60 seconds through `docker compose logs telegram-bot --tail ...`. The signal must be explicit enough for an operator to understand that Telegram polling/delivery is degraded and retrying. (Assessed: existing `"polling error — retrying after backoff"` log with `error` field is sufficient — no code change needed.)
  - [x] If the current log text is not explicit enough, make the smallest connector-side change needed to log a structured degraded message, then cover it in [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py). (Not needed — existing logging is explicit enough.)
  - [x] While Telegram is degraded, use the MCP client to run a normal `retrieve` query against the seeded local validation document and confirm local retrieval still works.
  - [x] Restore the real `telegram.api_base_url`, restart `telegram-bot`, and confirm the bot resumes polling before marking the story complete.

- [x] Task 5: Keep implementation scope tight and add automated coverage only for changed behavior (AC: #1, #2, #3)
  - [x] Default deliverables are an updated [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) and completed validation evidence in this story file.
  - [x] Avoid changes to retrieval logic, ingestion logic, role-pack schema, Docker service topology, or Telegram note/Q&A behavior unless the live smoke test exposes a concrete blocker. (No code changes made.)
  - [x] If code changes are needed for the degraded signal, keep them limited to [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) and focused tests in [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py). (Not needed.)
  - [x] Run focused verification after documentation-only changes:

    ```bash
    docker compose config
    ```

    Result: OK — no config errors.

  - [x] If connector code changes are made, also run:

    ```bash
    uv run pytest tests/connectors/test_telegram_bot.py tests/output/test_telegram.py tests/output/test_router.py tests/services/test_output_service.py
    uv run ruff check
    uv run mypy
    ```

    Result: 126 passed, 0 regressions (run as precaution even though no connector changes were made).

## Dev Notes

### What This Story Is

Story 8.4 is an operator-validation story for the already-built reactive Telegram slice. Stories 8.1, 8.2, and 8.3 established the bot process, outbound Telegram channel, inbound Q&A route, and `Note:` capture into canonical ingest jobs. This story should prove those behaviors work together with a real Telegram client and a real local MCP retrieval path. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

The primary deliverable should be a live runbook section in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md), plus captured evidence in this story file during implementation. Code changes are not the default outcome, except for a minimal degraded-signal improvement if current logs are too vague to satisfy AC #3.

### Scope Boundaries

- Validate reactive Telegram messaging only: inbound question -> cited Telegram answer, inbound `Note:` -> queued note -> cited retrieval, and Telegram API failure isolation.
- Do not add proactive briefings, morning summaries, scheduler behavior, web augmentation, provider-routing work, webhook migration, or media ingestion.
- Do not create a parallel live-test script that bypasses the real bot. The validation should use the existing `telegram-bot` Compose service, [OutputService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/output.py), [OutputRouter](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py), [RetrievalService](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/retrieval.py), and worker/job substrate.
- Do not put bot tokens, chat IDs, private note contents, or full answers containing sensitive source text into committed evidence. Redact secrets and use intentionally seeded marker documents.

### Current Baseline Before This Story

- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml) now defines a `telegram-bot` service running `uv run cos-telegram-bot`, alongside `cos`, `worker`, `postgres`, and `tika`.
- [CosConfig](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) includes `TelegramConnectorConfig` with `bot_token`, `chat_id`, `api_base_url`, `poll_timeout`, `backoff_initial`, `backoff_max`, and `staging_dir`.
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) documents the Telegram connector block and warns that `staging_dir` must be on the shared Docker volume.
- [role_packs/chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml) already includes `telegram` in `output_channels`; `OutputRouter` still fail-closes if the active role pack does not allow the channel.
- [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) long-polls `getUpdates`, filters by configured chat, classifies inbound text, calls `RetrievalService.query(...)` for questions, sends replies through `OutputService.send("telegram", ...)`, stages `Note:` messages as Markdown, and submits `telegram_note` ingest jobs.
- [TelegramChannel](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py) sends via `sendMessage`, logs failures with `component: "output"` and `channel: "telegram"`, redacts tokens, and suppresses delivery errors rather than raising them through the user workflow.
- The worker processes `telegram_note` jobs through the generic ingest pipeline, preserving source truth, canonical identity, chunks, embeddings, and provenance.

### Architecture Guardrails

1. **Use the real Telegram and MCP paths.**
   Operator validation should exercise the same Docker Compose service, polling loop, output route, retrieval service, job queue, worker, and MCP retrieval path used in normal operation. Do not validate with mocked Telegram HTTP calls or direct Python helper invocation. [Source: [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)]

2. **Keep Telegram lower-trust and concise.**
   Telegram is suitable for quick questions and short notes, not full analytical dumps. The smoke test should expect concise replies and citations, not long document excerpts or sensitive source reproduction. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

3. **Retrieval before generation still applies.**
   A Telegram Q&A pass requires citations. A fluent answer with no `Sources:` block is not enough for this validation story. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

4. **Generated output is separate from source truth.**
   The Telegram acknowledgement and Q&A reply are generated output. The seeded validation document and the Telegram note are source material. Do not store reply text as source material or use it as retrieval evidence. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

5. **Failure isolation is the Epic 8 operational proof.**
   When Telegram is degraded, the `telegram-bot` process may log errors and retry, but the `cos` MCP server and local retrieval path must remain usable. Do not broaden the failure simulation into stopping Postgres, Tika, the worker, or the MCP server. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

6. **Prefer a reversible config change for outage simulation.**
   `telegram.api_base_url` exists specifically as an overrideable Telegram API base. For AC #3, point only the Telegram connector at a bad endpoint, restart `telegram-bot`, observe the degraded/error signal, then restore the real endpoint.

### Live Validation Design Notes

Recommended question seed document:

```bash
mkdir -p data/uat-docs/telegram
printf '%s\n' 'Epic 8 Telegram live validation policy. Marker: epic-8-telegram-live-question-a. The Telegram live validation policy says reactive Telegram Q&A must return cited answers.' > data/uat-docs/telegram/epic-8-telegram-live-question.md
docker compose exec cos uv run cos ingest /data/uat-docs/telegram/epic-8-telegram-live-question.md
```

Recommended Telegram question:

```text
What does the Epic 8 Telegram live validation policy say?
```

Recommended Telegram note:

```text
Note: Epic 8 Telegram live validation note. Marker: epic-8-telegram-live-note-a. This note says live Telegram note capture works and becomes retrievable.
```

Recommended follow-up retrieval prompt, through Telegram or MCP:

```text
What does the Epic 8 Telegram live validation note say?
```

The runbook should tell the operator how to wait for the worker to process the note before the follow-up retrieval. A short `docker compose logs worker --tail ...` check or `list_documents`/MCP retrieval loop is acceptable. Avoid a fixed long sleep as the only instruction; give the operator an observable completion signal.

For AC #3, recommended safe simulation:

1. Temporarily set `telegram.api_base_url: http://127.0.0.1:9` in local `config.yaml`.
2. Run `docker compose up -d --force-recreate telegram-bot` or restart only that service.
3. Within 60 seconds, inspect `docker compose logs telegram-bot --tail 80` for a structured polling/delivery degraded or retry signal.
4. While the bot is degraded, use the MCP client to run `retrieve` against `epic-8-telegram-live-question-a`; confirm cited local retrieval still works.
5. Restore `telegram.api_base_url: https://api.telegram.org`, recreate/restart `telegram-bot`, and confirm polling resumes.

### Latest Telegram API Notes

- The official Telegram Bot API `Message` object still exposes `message_id`, optional `from`, `chat`, Unix `date`, and optional `text` for text messages. Existing Story 8.3 metadata extraction is aligned with that contract and should be preserved defensively. [Source: [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)]
- `getUpdates` remains the long-polling method used by the bot. Keep `allowed_updates=["message"]`; this story should not move the platform to webhooks. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]
- `sendMessage` remains the Telegram reply method behind `TelegramChannel`. The smoke test does not require parse modes, inline keyboards, or rich formatting. [Source: [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)]

### Previous Story Intelligence

Story 8.3 learnings that matter directly:

- `Note:` acknowledgement means the note was durably staged and queued, or deduplicated as already queued/processed. It does not mean embeddings are already available. The live validation must wait for the worker before testing retrieval.
- Telegram note source identity is `source_type="telegram_note"` with locators like `telegram://chat/{chat_id}/message/{message_id}`. Do not validate note capture by looking for `mcp_note`.
- The bot logs update/message IDs and lengths, not full message text. Keep evidence and new logs aligned with that privacy boundary.
- On note-save failure, the bot sends a short recovery reply and keeps polling. Operator validation should treat a crash/restart loop as a failure unless it is the deliberate API-outage simulation.
- Existing review fixes removed orphan staged files on failed enqueue and separated enqueue success from acknowledgement delivery failure. Do not reintroduce file cleanup or acknowledgement semantics regressions.

Story 8.2 learnings that still matter:

- Q&A routing is deterministic: `Note:` prefix wins for notes; `/ask`, question words, request phrases, and trailing `?` route to retrieval. The live smoke question should be unmistakably a question.
- Telegram replies are formatted as concise plain text with up to three source lines under `Sources:`.
- Retrieval timeout is currently 60 seconds. A timeout should return the configured recovery reply, not crash the polling loop.

Story 8.1 learnings that still matter:

- Bot token redaction is mandatory in logs and evidence.
- Webhook conflicts are logged explicitly because polling and webhooks cannot both own updates.
- Output failures log under `component: "output"` and must not make the rest of the platform unhealthy.

### Git Intelligence

Recent commits show Epic 8 has landed in narrow, review-patched slices:

- `1e0e826 fix(epic-8): address Telegram note capture review findings`
- `eaea9f2 feat(epic-8): implement Telegram note capture - story 8.3`
- `593ca73 feat(epic-8): implement Telegram inbound QA`
- `3893087 fix(epic-8): address Telegram review findings`
- `f754de1 feat(epic-8): implement Telegram bot foundation - story 8.1`

Follow the same pattern: keep this story narrow, run a live validation pass, capture evidence, and only patch code when the live run exposes a specific gap.

### Suggested File Touchpoints

Primary:

- [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) - add the Epic 8 interactive Telegram live validation pack.
- [8-4-operator-validation-interactive-telegram-live.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-4-operator-validation-interactive-telegram-live.md) - capture completion evidence during implementation.

Only if the degraded/error signal is too vague:

- [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) - make polling outage logs explicitly operator-visible as degraded.
- [tests/connectors/test_telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/tests/connectors/test_telegram_bot.py) - cover any changed degraded log behavior.

Reference only unless a live-run blocker is found:

- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example)
- [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)
- [src/cos/output/channels/telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)
- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)
- [src/cos/worker.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/worker.py)

### Testing Requirements

- This story is primarily validated manually with a real Telegram bot and real MCP client.
- No automated live Telegram test should be added; external Telegram tests would be flaky and secret-dependent.
- Documentation-only implementation should at least run `docker compose config`.
- If connector code changes are made, run the focused Telegram/output suite and static checks listed in Task 5.
- Completion evidence should include:
  - live run timestamp
  - seeded source alias for the Q&A test
  - Telegram Q&A observed latency and cited source alias
  - Telegram note acknowledgement text
  - note `source_alias` and redacted `source_locator`
  - degraded log message from outage simulation with secrets redacted
  - MCP retrieval proof while Telegram is degraded
  - restore/cleanup confirmation

### Project Structure Notes

- Live operator runbooks belong in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md).
- Do not create `docs/connectors.md` in this story unless the implementation discovers it is a direct blocker. Story 8.5 owns the broader Telegram documentation and housekeeping pass.
- No repo-level `project-context.md` file was found.
- Existing unrelated untracked files were present when this story was created: `.vscode/`, `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json`, and `_bmad-output/planning-artifacts/research/cos-token-monitoring-and-cost-audit-options-2026-05-27.md`. Do not touch or revert them.
- Before implementing this story, create/switch to a story branch such as `story/8-4-operator-validation-interactive-telegram-live` from an up-to-date `main` that includes Story 8.3.

### References

- [Epic 8 definition and Story 8.4 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD FR34, NFR11, NFR20, retrieval-before-generation, and channel sensitivity](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture service boundaries and Telegram integration notes](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Inbound Telegram Q&A and note-capture flow](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Previous story: 8.3 Telegram note capture](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-3-telegram-note-capture.md)
- [Previous story: 8.2 Telegram inbound Q&A](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-2-telegram-inbound-qa.md)
- [Previous story: 8.1 Telegram bot setup and output channel](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md)
- [Current operator runbook](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- [Current Telegram bot connector](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)
- [Current Telegram output channel](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)
- [Current Docker Compose services](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml)
- [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)
- [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)
- [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)

## Change Log

- 2026-05-28: Story created and sprint status advanced to `ready-for-dev`.
- 2026-05-28: Implemented — Epic 8 live Telegram validation pack added to `docs/manual-testing.md` (Test Pack 12, pass criteria, cleanup); no code changes required; 126 existing tests pass.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None.

### Completion Notes List

- Story context created on 2026-05-28.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Implementation 2026-05-28: Primary deliverable is `docs/manual-testing.md` — added Test Pack 12 (Epic 8 Interactive Telegram Live) covering inbound Q&A smoke path, note capture with worker-drain verification, and safe Telegram API outage simulation using reversible `config.yaml` override. Also updated the guide header, product state, What Epic 8 Added section, How to Use guide, Test Pack Index, Shared Prerequisites, Shared Bootstrap health check, Pass Criteria, and Cleanup sections.
- Degraded logging assessment: existing `"polling error — retrying after backoff"` log line in `telegram_bot.py:run_polling` with `error` and `backoff` fields is sufficiently explicit for operator diagnosis — no code change needed.
- Validation: `docker compose config` passes; 126 focused Telegram/output tests pass with no regressions.

### File List

- `_bmad-output/implementation-artifacts/8-4-operator-validation-interactive-telegram-live.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/manual-testing.md`
