# Story 8.5: Documentation and Housekeeping

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the interactive Telegram slice only,
so that users and future agents do not assume web augmentation or proactive briefings are already part of this epic.

## Acceptance Criteria

1. **Given** `docs/connectors.md` is updated for Epic 8,
   **When** it is reviewed,
   **Then** it covers Telegram setup, testing, inbound Q&A, and note capture without implying that morning briefs or web search are already included in the same delivery slice.

2. **Given** a user-facing guide is updated,
   **When** it is reviewed,
   **Then** it explains how to ask questions and capture notes through Telegram in plain language.

3. **Given** architecture and epic documents are cross-checked,
   **When** reviewed together,
   **Then** the Telegram capability is described consistently as reactive messaging only.

## Tasks / Subtasks

- [x] Task 1: Create the connector guide and make Telegram setup explicit (AC: #1, #2, #3)
  - [x] Add [docs/connectors.md](/Users/iain.livingstone/Development/CoS/cos/docs/connectors.md) as the canonical operator guide for optional connectors.
  - [x] Cover the existing connector activation model: `connectors:` is a list of enabled connector names, while settings live in top-level blocks such as `gmail:`, `google_calendar:`, and `telegram:`.
  - [x] Keep Gmail and Google Calendar coverage short and link back to [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) for OAuth/sync details rather than duplicating the whole Google setup flow.
  - [x] Add a Telegram section that explains BotFather token creation, chat ID discovery through Telegram `getUpdates`, the required `telegram:` config fields, adding `"telegram"` to `connectors`, confirming `telegram` is allowed by the active role pack, starting/recreating `telegram-bot`, and reading `docker compose logs telegram-bot`.
  - [x] State plainly that Epic 8 Telegram is reactive only: user-initiated questions, user-initiated `Note:` capture, concise cited replies, and failure isolation. Do not describe web search, proactive morning briefs, scheduled digests, meeting prep, or provider-routing behavior as available in this slice.
  - [x] Include secrets hygiene: never commit `config.yaml`, never paste bot tokens into docs/evidence, redact chat IDs when evidence is sensitive, and remember that Telegram is a lower-trust messaging channel.

- [x] Task 2: Add plain-language Telegram usage guidance for users/operators (AC: #2)
  - [x] Explain how to ask a question from Telegram using ordinary question phrasing or `/ask`, and set the expected result as a concise answer with a `Sources:` block.
  - [x] Explain how to capture a note using the explicit `Note:` prefix and set the expected immediate acknowledgement as exactly `"Note saved."`.
  - [x] Explain the difference between acknowledgement and retrieval availability: `"Note saved."` means the note was staged/queued or deduplicated, while the worker must finish before the note is searchable.
  - [x] Explain unsupported message behavior in simple terms: bare greetings, unknown commands, non-text messages, and empty `Note:` messages do not become knowledge-base documents.
  - [x] Mention that Telegram replies are intentionally short and should not be treated as full analytical reports.

- [x] Task 3: Update existing user-facing docs for the Epic 8 current state (AC: #1, #2, #3)
  - [x] Update [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) from "Current Capabilities (Epic 7)" to Epic 8, add the reactive Telegram capability, include `docs/connectors.md` in the docs tree, and ensure service descriptions account for the `telegram-bot` service without implying it is always useful when Telegram is disabled.
  - [x] Update [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) so startup, connector, provenance, and operations sections include Telegram where appropriate. Keep Google OAuth and sync instructions intact.
  - [x] Update [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) comments that still describe Telegram as a future output channel. Preserve the existing top-level `channels:` field, but clarify that role-pack `output_channels` are the actual egress permission source used by the router.
  - [x] Update [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) only where needed to link to `docs/connectors.md` and keep the Test Pack 12 runbook aligned. Do not claim live Telegram evidence was completed unless implementation actually captures it.
  - [x] Update any stale "Epic 7 only", "four services", or "Gmail/Calendar/MCP notes only" statements that now mislead a reader about Epic 8.

- [x] Task 4: Cross-check planning and architecture artifacts for reactive-only wording (AC: #3)
  - [x] Review [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md), [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md), and [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md) for wording that could make Epic 8 sound like it includes web augmentation or proactive scheduling.
  - [x] Preserve future-roadmap statements when they are clearly labelled as future Epic 10 or Epic 11 behavior.
  - [x] Patch ambiguous current-state labels, especially diagram/system descriptions that mention Telegram scheduled briefs without saying those are future Epic 11 behavior.
  - [x] Keep Story 8.5 scoped to documentation. Do not add web-search configuration, scheduler configuration, new diagrams for later epics, or code changes unless a doc reference is provably wrong because code changed.

- [x] Task 5: Verification and housekeeping (AC: #1, #2, #3)
  - [x] Run a stale-language sweep and resolve any current-state false positives — no false positives in user-facing docs after changes. Planning artifact matches in prd.md, epics.md, sprint-change-proposal, implementation-readiness-report, validation-report are all clearly labelled as future Growth FRs or historical records and were left intact per the scope guardrail.
  - [x] Run `docker compose config` — validated clean (exit 0, no output).
  - [x] Documentation-only changes made — no automated Telegram, retrieval, or ingestion tests required.
  - [x] Updated this story's Dev Agent Record and File List.

## Dev Notes

### What This Story Is

Story 8.5 is the Epic 8 documentation closeout. Stories 8.1, 8.2, 8.3, and 8.4 established the reactive Telegram transport, cited Q&A, note capture, and live validation runbook. This story turns those implemented pieces into coherent operator/user documentation and removes stale Epic 7 or pre-Telegram wording. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

The key product boundary is explicit: Epic 8 is **interactive Telegram messaging only**. It does not include web search, morning briefs, meeting prep, scheduled digests, provider routing, local model endpoints, or task-runtime work. Those belong to later epics. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md), [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

### Current Baseline To Document

- [docker-compose.yml](/Users/iain.livingstone/Development/CoS/cos/docker-compose.yml) includes a separate `telegram-bot` service running `uv run cos-telegram-bot`. It shares `data/`, `config.yaml`, `role_packs/`, certs, and tokens volumes with the other app services.
- [CosConfig](/Users/iain.livingstone/Development/CoS/cos/src/cos/config.py) uses `connectors: list[str]` plus an optional top-level `telegram: TelegramConnectorConfig`. There is no nested `connectors.telegram` config object.
- `TelegramConnectorConfig` fields are `bot_token`, `chat_id`, `api_base_url`, `poll_timeout`, `backoff_initial`, `backoff_max`, and `staging_dir`.
- [role_packs/chro.yaml](/Users/iain.livingstone/Development/CoS/cos/role_packs/chro.yaml) already permits `telegram` in `output_channels`; the output router uses role-pack output channels as the effective egress permission source.
- [telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py) exits cleanly when `"telegram"` is not enabled or `telegram:` is absent.
- When enabled, the bot long-polls `getUpdates`, filters to the configured chat, handles only text messages, classifies `question`, `note`, or `unsupported`, sends Q&A replies through `OutputService.send("telegram", ...)`, and stages `Note:` messages as `telegram_note` ingest jobs.
- Telegram Q&A replies are plain text, capped to Telegram's `sendMessage` limit, and include at most three compact citation lines under `Sources:`.
- Telegram note source aliases look like `telegram-note-YYYY-MM-DDTHHMMSSZ-<id>.md`; locators use `telegram://chat/{chat_id}/message/{message_id}` when a message ID is available.
- The worker processes Telegram notes through the existing canonical ingest pipeline. `Note saved.` is not proof that embeddings are already searchable; worker completion is separate.

### Architecture Guardrails

1. **Reactive-only wording is the acceptance boundary.**
   Documentation may mention that later epics add web search and proactive briefings, but it must not describe those as part of Epic 8 or as currently available Telegram behavior. [Source: [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)]

2. **Retrieval before generation still applies to Telegram.**
   Telegram Q&A should be described as grounded retrieval plus synthesis with citations. A cited `Sources:` block is the success signal; unsupported/no-content outcomes should be explained without implying the bot fabricates answers. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

3. **OutputRouter remains the egress boundary.**
   All Telegram replies are sent through `OutputService`/`OutputRouter` and are subject to role-pack channel permissions. Documentation should not instruct operators or future agents to bypass that boundary with direct Telegram API sends except for the one-time `getUpdates` chat ID discovery call. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

4. **Telegram is lower trust than local.**
   Docs should set expectations for short replies and short notes. Avoid examples that encourage sending sensitive full documents or long analytical reports through Telegram. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)]

5. **Source truth stays separate from generated output.**
   Telegram note text becomes source material. Telegram Q&A replies and `"Note saved."` acknowledgements are generated output and must not be documented as ingested source records. [Source: [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)]

6. **Connector failures are isolated.**
   Telegram API outage guidance should point to `docker compose logs telegram-bot` and the existing Test Pack 12 failure-isolation check. It should also state that local MCP retrieval remains available when Telegram is degraded. [Source: [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md), [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)]

### Documentation Touchpoints

Primary:

- [docs/connectors.md](/Users/iain.livingstone/Development/CoS/cos/docs/connectors.md) - new canonical connector guide.
- [README.md](/Users/iain.livingstone/Development/CoS/cos/README.md) - current capabilities, docs tree, service/component wording, Telegram capability summary.
- [docs/setup.md](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md) - setup, connector, provenance, operations, and Telegram user guidance.
- [config.yaml.example](/Users/iain.livingstone/Development/CoS/cos/config.yaml.example) - stale output-channel comments and Telegram setup comments.
- [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) - links/alignment only, unless a real inconsistency is found.

Planning artifact cross-check:

- [epics.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [architecture.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [architecture-diagrams.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [prd.md](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)

Reference only unless a doc claim needs code context:

- [src/cos/connectors/telegram_bot.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/connectors/telegram_bot.py)
- [src/cos/output/channels/telegram.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/channels/telegram.py)
- [src/cos/output/router.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/output/router.py)
- [src/cos/services/jobs.py](/Users/iain.livingstone/Development/CoS/cos/src/cos/services/jobs.py)

### Latest Technical Notes

- The official Telegram Bot API still documents `getUpdates` as the polling method for inbound updates; the current implementation's `allowed_updates=["message"]` and offset handling remain aligned with that path. [Source: [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)]
- `sendMessage` remains the reply method and Telegram's text limit remains 4096 characters after entity parsing. Keep examples plain-text; do not introduce Markdown/HTML parse-mode requirements in docs. [Source: [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)]
- The `Message` object includes `message_id`, `chat`, Unix `date`, and optional text/sender fields. Documentation should stay defensive: Telegram note metadata is best-effort around optional fields, not a promise that every field is always present. [Source: [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)]

### Previous Story Intelligence

Story 8.4 learnings:

- Test Pack 12 in [docs/manual-testing.md](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md) is the live validation runbook. Story 8.5 should link to it instead of duplicating every command.
- Story 8.4 intentionally deferred live Telegram evidence. Do not state that live Telegram UAT has been completed unless the implementer actually runs it and records evidence.
- The safe outage simulation uses `telegram.api_base_url: http://127.0.0.1:9`, restarts only `telegram-bot`, checks the current `"polling error — retrying after backoff"` log wording, verifies MCP retrieval still works, then restores `https://api.telegram.org`.
- Duplicate Telegram note verification must check the current note's `source_locator` suffix, not note body text in `source_alias`.

Story 8.3 learnings:

- `Note saved.` means the note was durably staged and queued, or deduplicated as already queued/processed. It does not mean the worker has indexed embeddings yet.
- Telegram notes use `source_type="telegram_note"` and locators like `telegram://chat/{chat_id}/message/{message_id}`. Do not describe them as `mcp_note`.
- Logs include IDs and lengths, not full message text. Keep examples and evidence aligned with that privacy boundary.

Story 8.2 learnings:

- The classifier is deterministic: `Note:` prefix wins for notes; `/ask`, question words, request phrases, and trailing `?` route to Q&A.
- Telegram replies are concise plain text with up to three `Sources:` entries.
- Retrieval timeout is currently 60 seconds and returns a recovery reply rather than crashing the polling loop.

Story 8.1 learnings:

- Bot tokens must be redacted. Avoid token-bearing URLs except the operator-owned chat ID discovery command, and tell the reader not to commit/share the token.
- Webhook conflicts are logged explicitly because polling and webhooks cannot both own updates.
- `cos logs` currently filters only `postgres`, `tika`, and `cos`; for `worker` and `telegram-bot`, docs should use `docker compose logs <service>`.

### Git Intelligence

Recent Epic 8 commits show the implemented scope and review patches:

- `c09fdeb chore(epic-8): defer live Telegram evidence`
- `08653e2 fix(epic-8): address Telegram validation review findings`
- `b63c9e5 feat(epic-8): operator validation runbook for interactive Telegram - story 8.4`
- `1e0e826 fix(epic-8): address Telegram note capture review findings`
- `eaea9f2 feat(epic-8): implement Telegram note capture - story 8.3`

Follow the same pattern: narrow docs changes, honest evidence, and no feature expansion hidden inside a housekeeping story.

### Testing Requirements

- Default implementation is documentation-only. Do not add live Telegram automation or secret-dependent tests.
- For documentation-only changes, run the stale-language sweep in Task 5 and `docker compose config`.
- If the implementer changes code, config validation behavior, router behavior, or Telegram runtime behavior, run the focused tests and static checks listed in Task 5.
- If planning artifacts are patched, preserve the future-roadmap distinction: future web and scheduler epics may remain documented, but current Epic 8 wording must remain reactive-only.

### Project Structure Notes

- No repo-level `project-context.md` file was found when this story was created.
- `docs/connectors.md` does not exist yet; create it in this story.
- Existing unrelated untracked files were present when this story was created: `.vscode/`, `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json`, and `_bmad-output/planning-artifacts/research/cos-token-monitoring-and-cost-audit-options-2026-05-27.md`. Do not touch or revert them.
- This story was created while the workspace was still on `story/8-4-operator-validation-interactive-telegram-live`, which has local commits not present on `main`. Before implementing Story 8.5, ensure Story 8.4 has been approved/merged, pull `main`, then create `story/8-5-documentation-and-housekeeping` from the updated `main`.

### References

- [Epic 8 definition and Story 8.5 acceptance criteria](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/epics.md)
- [PRD FR34, FR35 future boundary, NFR11, NFR20, egress control, and channel sensitivity](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/prd.md)
- [Architecture delivery sequence, egress boundary, config boundary, and Telegram integration notes](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture.md)
- [Inbound Telegram Q&A and note-capture flow](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/planning-artifacts/architecture-diagrams.md)
- [Previous story: 8.4 Operator Validation - Interactive Telegram Live](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-4-operator-validation-interactive-telegram-live.md)
- [Previous story: 8.3 Telegram Note Capture](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-3-telegram-note-capture.md)
- [Previous story: 8.2 Telegram Inbound Q&A](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-2-telegram-inbound-qa.md)
- [Previous story: 8.1 Telegram Bot Setup and Output Channel](/Users/iain.livingstone/Development/CoS/cos/_bmad-output/implementation-artifacts/8-1-telegram-bot-setup-and-output-channel.md)
- [Current manual testing guide](/Users/iain.livingstone/Development/CoS/cos/docs/manual-testing.md)
- [Current setup guide](/Users/iain.livingstone/Development/CoS/cos/docs/setup.md)
- [Telegram Bot API - getUpdates](https://core.telegram.org/bots/api#getupdates)
- [Telegram Bot API - sendMessage](https://core.telegram.org/bots/api#sendmessage)
- [Telegram Bot API - Message](https://core.telegram.org/bots/api#message)

## Change Log

- 2026-05-28: Story created and sprint status advanced to `ready-for-dev`.

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — documentation-only story. No test failures or debug output.

### Completion Notes List

- Story context created on 2026-05-28.
- All tasks completed in a single session on 2026-05-28 as pure documentation changes.
- `docs/connectors.md` created as the canonical operator guide for all optional connectors.
- `README.md` updated from Epic 7 to Epic 8; telegram-bot service noted; Telegram capability added; `docs/connectors.md` added to docs tree; `connectors/` description updated to mention `telegram_bot.py`; `cos docs` source type list extended to include Telegram notes.
- `docs/setup.md`: startup service count updated; Telegram note row added to provenance table; `worker` and `telegram-bot` log commands added to operations section.
- `config.yaml.example`: `channels:` comment updated to reflect Telegram availability (Epic 8) and clarify role-pack `output_channels` as the actual egress permission source.
- `docs/manual-testing.md`: line 273 updated to reference `docs/connectors.md` instead of `config.yaml.example` for Telegram setup.
- `_bmad-output/planning-artifacts/architecture-diagrams.md`: two ambiguous Telegram lines in the Growth Roadmap End-State diagrams patched to attribute "outbound scheduled briefs" to Epic 11.
- `_bmad-output/planning-artifacts/architecture.md`: Epic 8 Implementation Notes section added documenting telegram-bot service, connector config model, OutputRouter channel source, reactive-only scope, note provenance, deduplication, and failure isolation.
- Stale-language sweep confirmed clean on user-facing docs. Planning artifact matches in prd.md, epics.md, sprint-change-proposal, validation-report, and implementation-readiness-report are all Growth FRs or historical records — left intact per scope guardrail.
- `docker compose config` returned exit 0 (no Compose wording changed).
- No code changes. No test execution required.

### File List

- `_bmad-output/implementation-artifacts/8-5-documentation-and-housekeeping.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/connectors.md` (created)
- `README.md`
- `docs/setup.md`
- `config.yaml.example`
- `docs/manual-testing.md`
- `_bmad-output/planning-artifacts/architecture-diagrams.md`
- `_bmad-output/planning-artifacts/architecture.md`
