# CoS Platform — Connector Guide

Connectors extend the platform with external data sources (Gmail, Google Calendar) and interactive messaging (Telegram). This guide covers how to activate each connector and how to use Telegram for interactive Q&A and note capture.

---

## Connector Activation Model

Connectors are controlled in two places in `config.yaml`:

1. **`connectors:` list** — names the connectors that should be active. A connector not listed here is completely disabled regardless of any other config.
2. **Top-level settings block** — each connector has its own block (e.g. `gmail:`, `google_calendar:`, `telegram:`) that controls its specific settings. Gmail and Google Calendar can use default connector settings when their blocks are omitted; Telegram requires an explicit `telegram:` block because `bot_token` and `chat_id` have no safe defaults.

For connectors that deliver responses (Telegram), the **role pack's `output_channels`** list is the actual egress permission source used by the output router. The connector must appear in `connectors:`, and the channel name must appear in the role pack's `output_channels` for outbound replies to work.

---

## Gmail Connector

The Gmail connector polls for new messages and stages them as background ingest jobs so the `worker` service can index them into the knowledge base.

To activate:

```yaml
connectors:
  - gmail
```

Gmail requires Google OAuth credentials and the Gmail API enabled in Google Cloud Console. See [setup.md — Google OAuth Setup](setup.md#google-oauth-setup-gmail-and-calendar-connectors) for credential setup, authentication commands, and sync instructions.

Optional settings (`gmail:` block) are described in `config.yaml.example`.

---

## Google Calendar Connector

The Calendar connector fetches upcoming events and stages them as background ingest jobs.

To activate:

```yaml
connectors:
  - google_calendar
```

Calendar also requires Google OAuth setup. See [setup.md — Google OAuth Setup](setup.md#google-oauth-setup-gmail-and-calendar-connectors) for credential setup, and [setup.md — Sync Connected Sources](setup.md#sync-connected-sources) for the sync commands and expected output.

Optional settings (`google_calendar:` block) are described in `config.yaml.example`.

---

## Telegram Connector

Epic 8 adds a reactive Telegram bot. The bot accepts user-initiated questions and note-capture messages from the configured chat. It does **not** send morning briefs, scheduled digests, meeting prep, or any proactive content — those belong to a later epic (Epic 11). Every Telegram interaction is user-initiated.

### 1. Create a Telegram Bot

1. Open Telegram and start a conversation with [@BotFather](https://t.me/botfather).
2. Send `/newbot` and follow the prompts. You will receive a **bot token** — a string like `7234567890:ABCDEFabcdef...`.
3. Treat the bot token as a password. Never commit it to git, paste it into documentation, or share it in chat logs.

### 2. Discover Your Chat ID

After creating the bot, send it any message in Telegram to register a chat update. Then run this command from your terminal, replacing `<YOUR_TOKEN>` with your bot token:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
```

Look for `"chat"` → `"id"` in the JSON response. That numeric value (e.g. `123456789`) is your chat ID. Copy it now — you will not need to run this command again. Redact the chat ID when recording screenshots or sharing evidence in shared documents.

### 3. Configure `config.yaml`

Add `"telegram"` to the `connectors` list and uncomment (or add) the `telegram:` block:

```yaml
connectors:
  - telegram

telegram:
  bot_token: YOUR_TELEGRAM_BOT_TOKEN
  chat_id: "123456789"
```

Leave all other `telegram:` fields at their defaults unless you have a specific reason to change them. See `config.yaml.example` for the full field reference (`api_base_url`, `poll_timeout`, `backoff_initial`, `backoff_max`, `staging_dir`).

### 4. Confirm Role-Pack Permission

The role pack's `output_channels` list controls whether Telegram replies are routed. The built-in `role_packs/chro.yaml` already includes `telegram`. If you are using a custom role pack, verify the field:

```yaml
output_channels:
  - local
  - telegram
```

### 5. Start (or Recreate) the Telegram Bot Service

Start the `telegram-bot` service:

```bash
docker compose up -d telegram-bot
```

If you changed the config after the service was already running, recreate it so it picks up the new settings:

```bash
docker compose up -d --force-recreate telegram-bot
```

### 6. Verify the Bot is Polling

```bash
docker compose logs telegram-bot --tail=50
```

A successful start shows the bot polling for updates. Send a question such as `/ask What content is in my knowledge base?` to the bot in Telegram. It should respond within a few seconds, either with a cited answer or a plain no-content message.

---

## Telegram Usage — Asking Questions

Send any message that reads as a question. The bot classifies inbound text automatically — no special prefix or command is required.

Examples that route to Q&A:

```
What frameworks do I have for workforce planning?
/ask What are the key themes from the Q3 board meeting?
Tell me about the succession pipeline.
Can you summarise the retention strategy?
```

The bot searches the knowledge base, synthesises a grounded answer, and replies with concise plain text. Every answer includes a `Sources:` block with up to three citations:

```
The workforce planning framework covers three segments: high-potential accelerators,
stable performers, and at-risk attrition. The segmentation criteria are...

Sources:
  1. workforce-strategy-2026.pdf (chunk 3)
  2. board-prep-q3.md (chunk 1)
  3. succession-pipeline.pdf (chunk 7)
```

Replies are intentionally short — Telegram is a messaging channel, not an analytical report tool. For detailed synthesis across many documents, use the MCP `retrieve` tool from a Claude session instead.

If no relevant content is found in the knowledge base, the bot replies with a plain statement to that effect. It does not fabricate answers.

---

## Telegram Usage — Capturing Notes

Prefix your message with `Note:` to capture it as a knowledge-base entry:

```
Note: Discussed expanding the succession pool in the UK region. Follow up with regional HRD by end of Q2.
```

The bot replies immediately with:

```
Note saved.
```

**What `Note saved.` means:** the note has been durably staged to disk and queued for the background `worker` service to ingest. It is **not** yet searchable. The worker must finish processing before the note appears in retrieval results or `cos docs`.

To confirm the worker has processed the note:

```bash
docker compose logs worker --tail=50
```

Worker log lines show each job being picked up and completed. After the worker catches up, the note will be retrievable and visible in `cos docs`.

Duplicate deliveries of the same Telegram message are idempotent. If the same message update is delivered again with the same locator and fingerprint, the bot returns `"Note saved."` without creating a duplicate ingest job or canonical record. If you send the same text again as a new Telegram message, it may become a separate note.

---

## Unsupported Message Behavior

The following do not become knowledge-base documents:

- Bare greetings (`Hi`, `Hello`, `hey`) receive short usage guidance
- Unknown bot commands (`/help`, `/status`, `/anything`) receive short usage guidance
- Empty `Note:` messages (the prefix with no content) receive note-format guidance
- Non-text messages (images, voice notes, stickers, files) are ignored

Unsupported text is answered with guidance so the user can recover. Non-text messages are ignored to keep the conversation clean.

---

## Telegram Scope (Epic 8)

Epic 8 Telegram is **reactive messaging only**:

- User-initiated questions → grounded cited replies
- User-initiated `Note:` capture → worker-backed knowledge-base indexing
- Connector failure isolation → outages do not affect local MCP retrieval or the rest of the platform

Not included in Epic 8: web search augmentation, morning briefs, scheduled digests, meeting prep, provider routing, or local model endpoints. Those belong to later epics (Epic 10, 11).

---

## Failure Handling and Outage Recovery

If the Telegram API becomes unreachable (network issue, wrong token, API outage), the polling loop logs the error and retries with exponential backoff. The rest of the platform remains available — MCP retrieval, ingestion, Gmail, and Calendar are unaffected.

To diagnose:

```bash
docker compose logs telegram-bot --tail=100
```

Look for `"polling error — retrying after backoff"` log lines. If the token or chat ID is wrong, correct `config.yaml` and recreate the service:

```bash
docker compose up -d --force-recreate telegram-bot
```

If the Telegram API itself is temporarily down, the bot recovers automatically when connectivity is restored. Local MCP retrieval remains available during any Telegram outage.

For the full Telegram validation runbook, see [manual-testing.md — Test Pack 12](manual-testing.md#test-pack-12-epic-8-interactive-telegram-live).

---

## Secrets Hygiene

- **Never commit `config.yaml`** — it contains your bot token. It is git-ignored by default.
- **Never paste bot tokens** into documentation, evidence files, or messages. Treat them as passwords.
- **Redact chat IDs** when recording screenshots or evidence in shared documents — the chat ID identifies your Telegram account.
- **Telegram is a lower-trust channel** than a local MCP session. Keep interactions concise — avoid sending sensitive full documents or detailed analytical requests through Telegram.
- The one-time `getUpdates` curl call during setup is the only place your token appears in a terminal command. Do not store or share the full token URL after you have copied the chat ID.
