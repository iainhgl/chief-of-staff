# Manual Testing Guide

Reflects the platform through **Epic 8: Interactive Telegram Messaging**.

This guide now treats **Epic 7 retrieval-trust validation as the default UAT path** for retrieval changes, and adds **Test Pack 12** as the validation path for the reactive Telegram slice. If you only run one check before signing off a retrieval change, run [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite) on a clean benchmark database. If you are validating Telegram messaging, run [Test Pack 12](#test-pack-12-epic-8-interactive-telegram-live).

The connected-ingestion and operational packs are still active regression packs for the parts of the product that Test Pack 11 does not cover. Use them when your change touches live source onboarding, provenance, queueing, restart behavior, or MCP note flows.

Other than the shared bootstrap for config and platform startup, each pack is meant to stand on its own: you should be able to open the relevant pack, run its setup, and complete that validation without reading the whole file front to back.

---

## Current Product State

In plain English, the product today can:

- ingest local files, Gmail messages and attachments, Google Calendar events, MCP-authored notes, and Telegram notes
- preserve where every piece of content came from, including version history and cross-source deduplication
- expose retrieval APIs that later user-facing workflows can use for grounded answers and citations
- apply score-threshold controls so unsupported questions can fall back to no-answer behavior
- measure retrieval quality with a committed benchmark corpus and a repeatable CLI gate
- answer questions and capture notes interactively via a Telegram bot, with cited answers and background worker processing

Important scope note: [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite) proves retrieval evidence selection, lineage control, no-answer handling, and retrieval-path latency on the benchmark corpus. It does **not** on its own prove Google OAuth, background queueing, restart persistence, or live assistant wording.

From a normal operator's perspective, Epic 7 changes the question from "does the product seem to work?" to "can I prove the retrieval layer is trustworthy before I rely on it in more user-facing behavior?"

---

## What Epic 7 Added

Epic 7 adds a structured evaluation layer and hardens retrieval trust:

- a committed mixed-source evaluation corpus and benchmark harness (`cos benchmark`) with gold and fuzz query layers
- machine-comparable benchmark reports with failure-stage attribution and per-class latency aggregation
- evidence selection hardened to enforce citation precision and single-lineage grounding for direct facts
- document-first routing for `single_doc_interpretation` queries with bounded context expansion
- `gold-na-001` (pension contribution rate) enforced as a mandatory release-gate check for retrieval-trust sign-off

The primary change to operator validation workflow: before signing off a retrieval change, run the benchmark harness using the gold corpus as the release gate on a clean benchmark database. Runs against a populated live database are still useful diagnostics, but they are not authoritative gate results. See [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite) for the full runbook.

---

## What Epic 8 Added

Epic 8 adds reactive Telegram messaging:

- a `telegram-bot` Docker Compose service that long-polls the Telegram Bot API for inbound messages from the configured chat
- inbound question routing: text that looks like a question triggers `RetrievalService.query(...)` and sends a concise cited reply through `OutputService` via `TelegramChannel`
- inbound `Note:` capture: note text is normalised, staged to disk, and submitted as a `telegram_note` ingest job so the worker indexes it into the canonical knowledge base
- deduplication at enqueue time: a note that has already been processed or is already queued returns `"Note saved."` without creating duplicate canonical state
- explicit outage logging: when `getUpdates` returns a non-success HTTP response or Telegram API error, the polling loop logs the error and retries with exponential backoff, keeping the rest of the platform healthy

The primary change to operator validation workflow for Epic 8: run Test Pack 12 before relying on Telegram for interactive Q&A or note capture in any environment.

---

## Supporting Product Capabilities Still Worth Smoke Testing

The current product state still includes the Epic 6 connected-ingestion and provenance model. These capabilities remain worth smoke testing when you change ingestion, provenance, operations, or MCP note flows:

- canonical identity is based on content blobs, not raw file paths
- exact-byte deduplication works across local files, Gmail, Google Calendar, and MCP note ingest
- provenance is preserved as `source_type`, `source_alias`, and `source_locator`
- Gmail sync stages message bodies and supported attachments, then enqueues background ingest jobs
- Google Calendar sync stages event Markdown and enqueues background ingest jobs
- a dedicated `worker` service drains the ingest queue in the background
- the MCP server exposes `ingest_document` for direct note capture with stable external IDs and warning-only near-duplicate detection
- old pre-Epic-6 data can be backfilled onto the canonical model with `cos migrate`

---

## How to Use This Guide

Use one of these paths:

Before you choose a path, complete the pre-UAT isolation step below so this run uses a fresh local database that is separate from your day-to-day or "real" local data.

1. **Default UAT path for retrieval changes**  
   Start with [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite). This is the primary Epic 7 UAT path and the first check to run whenever retrieval behavior changes.

2. **Reactive Telegram validation**  
   Run [Test Pack 12](#test-pack-12-epic-8-interactive-telegram-live) when you have changed the Telegram bot, output routing, or note-capture flow, or when you want to confirm end-to-end Telegram messaging works in a live environment.

3. **Connected-source regression after ingestion or provenance changes**  
   Run the shared bootstrap, then only the supporting packs that match what changed:
   local ingest, Gmail, Calendar, MCP note ingest, dedupe, versioning, retrieval, or restart.

4. **Full operator confidence pass**  
   Run Test Pack 11 first, then Test Pack 12 for Telegram, then add the supporting packs that represent the live user journeys you care about in this environment.

5. **Optional large-document sanity pass**  
   Use `tests/fixtures/real_world_eval/` after extraction, chunking, or format-handling changes. This corpus is manual-only, snapshot-based, and not part of the release gate or CI.

---

## Pre-UAT: Use a Fresh Isolated Database

For reliable manual testing, especially the authoritative Epic 7 benchmark gate,
do **not** point UAT at the same database you use for normal local work.

Preferred approach:

- create a dedicated local UAT database name such as `cos_uat` or
  `cos_benchmark`
- use that same `dbname` in both `config.yaml` and `config.host.yaml`
- keep `host: postgres` in `config.yaml` for container-side commands
- keep `host: localhost` in `config.host.yaml` for host-side commands
- recreate the UAT database when you want a truly fresh run

Convention used below:

- when this guide shows direct `psql` examples with `-d cos`, substitute your
  chosen UAT database name instead if you are following this isolated-database
  workflow
- `cos` CLI commands such as `cos docs`, `cos benchmark`, and `cos migrate`
  already use the database configured in `config.yaml` or `config.host.yaml`

Example setup:

1. Copy the configs if needed:

```bash
cp config.yaml.example config.yaml
cp config.yaml.example config.host.yaml
```

2. Edit `config.yaml` for container-side use:

```yaml
database:
  host: postgres
  dbname: cos_uat
```

3. Edit `config.host.yaml` for host-side use:

```yaml
database:
  host: localhost
  dbname: cos_uat
```

4. Start just Postgres if it is not already running:

```bash
docker compose up -d postgres
```

5. Create or recreate the dedicated UAT database:

```bash
docker compose exec postgres psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS cos_uat WITH (FORCE);"
docker compose exec postgres psql -U postgres -d postgres -c "CREATE DATABASE cos_uat;"
```

6. Start or restart the app services so they point at that database and apply migrations on startup:

```bash
docker compose up -d
```

7. Confirm the UAT database is empty before you begin:

```bash
docker compose exec cos uv run cos docs
```

Expected:

- the command reports `No documents ingested yet. Run: cos ingest <path>`
- this run is now isolated from any older local experimentation in the default `cos` database

Important:

- for the authoritative Test Pack 11 gate, use a freshly recreated isolated database
- for exploratory manual testing, you may keep a dedicated named UAT database between sessions, but the result is then diagnostic rather than authoritative

---

## Post-UAT: Return to Your Normal Local Database

When the manual UAT run is complete, switch both configs back to your normal
local database so day-to-day work does not keep using the temporary UAT DB.

Typical reset:

1. Edit `config.yaml` back to your normal container-side database:

```yaml
database:
  host: postgres
  dbname: cos
```

2. Edit `config.host.yaml` back to your normal host-side database:

```yaml
database:
  host: localhost
  dbname: cos
```

3. Restart the stack so the app services pick up the normal database again:

```bash
docker compose up -d
```

4. Sanity-check that you are back on the normal local DB:

```bash
docker compose exec cos uv run cos docs
```

Expected:

- you see your normal local document set again, or the normal empty-state message
- subsequent `cos` CLI and MCP usage now target the standard local database rather than the temporary UAT database

5. Optional cleanup: remove the temporary UAT database if you do not want to keep it for later diagnostic work:

```bash
docker compose exec postgres psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS cos_uat WITH (FORCE);"
```

If your normal local database name is not `cos`, substitute your usual value in
both config files.

---

## Test Pack Index

| Pack | When to run | In plain English, what this is testing |
|---|---|---|
| **11** | Every release-gate pass | Can the assistant retrieve the right evidence, stay grounded to the right source, refuse unsupported answers, and stay fast enough? |
| **12** | After Telegram bot, output routing, or note-capture changes | Can the reactive Telegram slice — inbound Q&A, note capture, worker processing, cited retrieval, and Telegram failure isolation — work together end-to-end? |
| **1** | After local ingest changes | Can I still drop files into the system and see them show up correctly? |
| **2** | After Gmail/auth/queue changes | Can I connect Gmail, sync messages, and trust background ingest plus provenance? |
| **3** | After Calendar/auth/queue changes | Can I connect Calendar, sync events, and see them preserved correctly? |
| **4** | After MCP first-ingest changes | Can I save a note from Claude into the platform? |
| **5** | After MCP idempotency changes | If I send the same note twice, does the platform avoid duplicate versions? |
| **6** | After dedupe or canonical-identity changes | If the same bytes arrive through different channels, does the platform keep one canonical content record but separate provenance rows? |
| **7** | After similarity-warning changes | Does the platform warn about near-duplicates without blocking normal work? |
| **8** | After versioning changes | If I update a note, does the platform create a new version and keep the old one? |
| **9** | After retrieval changes on live connected content | Can a normal user ask grounded questions across mixed sources and get the right citations? |
| **10** | After restart/token/runtime changes | Can the platform restart cleanly without making me reconnect everything? |
| **Final spot checks** | After Packs 1-10 when you want a quick final sanity check | Does the database now contain the source mix, provenance rows, and dedupe shape I expect? |
| **Manual corpus** | After extraction/chunking/format changes when you want higher realism | Can the platform still ingest and retrieve from larger official PDF, DOCX, and HTML documents? |

---

## Shared Prerequisites

Needed for all packs:

- Docker Desktop or Rancher Desktop running
- `uv` installed
- working directory is the repo root: `cos/`
- live Anthropic and Voyage credentials in `config.yaml`

Needed only for connected-source packs:

- a real Google account you can safely use for Gmail and Calendar UAT

Needed only for MCP packs:

- Claude Code or Claude Desktop available for the live MCP tests

Needed only for the Telegram live pack (Test Pack 12):

- a working Telegram bot token in `config.yaml` under `telegram.bot_token`
- a configured `telegram.chat_id` for the account/group the bot should respond to; if you need to discover it, follow the setup steps in [connectors.md — Telegram Connector](connectors.md#telegram-connector) before relying on the platform bot
- `"telegram"` listed in `connectors` in `config.yaml`
- `telegram` listed in the active role pack's `output_channels` (already present in `role_packs/chro.yaml`)
- the `telegram-bot` service running via Docker Compose (`docker compose up -d`)
- a working MCP client for the local retrieval verification step in AC #3

Needed only for the optional manual large-document corpus:

- a populated local copy of `tests/fixtures/real_world_eval/originals/`
- run `tests/fixtures/real_world_eval/fetch_snapshot.sh` after you have a local `snapshot-manifest.tsv`
- verify the files with `tests/fixtures/real_world_eval/verify_originals.sh` before using them for ingest sanity checks

Important runtime rule:

- use `uv run cos auth ...` and `uv run cos restart` on the **host**
- use `docker compose exec cos uv run cos ...` for commands that need the app's Docker network and `database.host: postgres`
- anything you create under `data/` on the host is visible inside the `cos` container under `/data/`

---

## Shared Platform Bootstrap

Run this once after the pre-UAT isolation step above.

### 1. Prepare `config.yaml`

Copy the templates if needed:

```bash
cp config.yaml.example config.yaml
cp config.yaml.example config.host.yaml
```

If you are running only the Epic 7 benchmark gate, you mainly need a valid bootable config plus a host-side config copy such as `config.host.yaml` for the benchmark command. You do not need Google OAuth or backfilled live data for that path.

If you followed the pre-UAT isolation step, make sure both files use the same dedicated `database.dbname`, with:

- `config.yaml` using `database.host: postgres`
- `config.host.yaml` using `database.host: localhost`

If you are running the connected-source and MCP supporting packs, make sure these areas are populated:

```yaml
llm:
  api_key: YOUR_ANTHROPIC_KEY

embedding:
  api_key: YOUR_VOYAGE_KEY_OR_NULL_IF_SHARED

connectors:
  - gmail
  - google_calendar

google_oauth:
  client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
  client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET

gmail:
  query: "label:cos-uat newer_than:7d"
  label_ids: []
  max_results: 25
  include_spam_trash: false
  staging_dir: /data/connector-staging/gmail

google_calendar:
  calendar_ids:
    - primary
  lookback_hours: 24
  lookahead_days: 14
  max_results: 100
  staging_dir: /data/connector-staging/google-calendar

mcp_note:
  staging_dir: /data/connector-staging/mcp
  near_duplicate_threshold: 0.95
```

Notes:

- if your `database.host` is `postgres` and `tika.url` is `http://tika:9998`, DB-backed CLI commands should be run inside the `cos` container
- if you want a more forgiving near-duplicate UAT pass, temporarily lower `mcp_note.near_duplicate_threshold` to `0.90`
- if you are doing a benchmark-only Epic 7 gate, you can skip the Google API and backfill steps below until you actually need connected-source flows

### 2. Start the platform

```bash
docker compose up -d
docker compose ps
```

Expected:

- `postgres` is `healthy`
- `tika` is `healthy`
- `cos` is `healthy`
- `worker` is `Up`
- `telegram-bot` is `Up` (if `"telegram"` is in `connectors` in `config.yaml`)

### 3. Verify health

```bash
docker compose logs cos --tail=30
docker compose logs worker --tail=30
docker compose exec cos uv run cos status
```

Expected:

- `cos` logs end with the normal startup sequence including migrations and MCP startup
- `worker` logs show `worker starting`
- `cos status` reports the platform as healthy
- if Telegram is configured: `docker compose logs telegram-bot --tail=50` contains a structured log line with `"message": "Telegram polling started"` and no repeated startup errors after that line

### 4. Enable Google APIs (connected-source packs only)

In the Google Cloud project behind your OAuth desktop client, enable:

- Gmail API
- Google Calendar API

### 5. Optional: backfill older local-only data for live connected-content packs

If this environment already contains older local-only data, run the canonical backfill once:

```bash
docker compose exec cos uv run cos migrate
```

Expected:

- a success message reports how many documents were backfilled vs already canonical
- do **not** run this before an authoritative Test Pack 11 gate on a clean benchmark database; it adds ambient content to retrieval

---

## Test Pack 1: Local File Ingest Still Works

Plain English: if you drop a couple of files into the platform, they should ingest cleanly and show up as local documents with sensible metadata.

### Pack-specific setup

Create a dedicated local UAT folder on the host:

```bash
mkdir -p data/uat-docs/local
printf '%s' 'Epic 6 local ingest note. Marker: epic-6-local-note-a.' > data/uat-docs/local/epic-6-local-note.md
printf '%s' 'Epic 6 local ingest brief. Marker: epic-6-local-brief-a.' > data/uat-docs/local/epic-6-local-brief.md
```

### Run the test

```bash
docker compose exec cos uv run cos ingest /data/uat-docs/local
docker compose exec cos uv run cos docs --json
```

Expected:

- both markdown files ingest successfully
- `cos docs --json` returns objects with:
  - `id`
  - `source_alias`
  - `source_locator`
  - `ingested_at`
  - `current_version`
  - `chunk_count`
- `epic-6-local-note.md` and `epic-6-local-brief.md` appear as local `file` sources
- each local `source_locator` begins with `/data/uat-docs/local/`
- no `source_path` field appears in the JSON output

---

## Test Pack 2: Gmail OAuth, Sync, Queue Drain, and Provenance

Plain English: can you connect Gmail once, sync labelled mail, and trust the platform to ingest it in the background without losing provenance?

### Pack-specific setup

Make sure `config.yaml` still contains:

```yaml
connectors:
  - gmail

google_oauth:
  client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
  client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET

gmail:
  query: "label:cos-uat newer_than:7d"
```

Create a shared attachment on the host:

```bash
mkdir -p data/uat-docs/gmail
printf '%s' 'Epic 6 Gmail attachment content. Marker: epic-6-gmail-attachment-a.' > data/uat-docs/gmail/epic-6-gmail-shared-attachment.md
```

In Gmail, using the same Google account you will authenticate:

1. Create a label named `cos-uat` if it does not already exist.
2. Send yourself an email with:
   - subject: `Epic 6 UAT Gmail Body A`
   - body text containing `epic-6-uat-gmail-body-a`
   - attachment: `data/uat-docs/gmail/epic-6-gmail-shared-attachment.md`
   - label: `cos-uat`
3. Send yourself a second email with:
   - subject: `Epic 6 UAT Gmail Body B`
   - body text containing `epic-6-uat-gmail-body-b`
   - the same attachment bytes again
   - label: `cos-uat`
4. Optional: include one unsupported attachment type to confirm it is skipped cleanly.

### Run the test

Authenticate on the host if `tokens/gmail.json` is missing or stale:

```bash
uv run cos auth gmail
```

Then run the sync inside the container:

```bash
docker compose exec cos uv run cos sync gmail
docker compose logs worker --tail=100
docker compose exec postgres psql -U postgres -d cos -c "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY status;"
```

Inspect Gmail provenance rows:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT s.source_type, s.source_alias, s.source_locator
FROM sources s
WHERE s.source_type IN ('gmail_message_body', 'gmail_attachment')
ORDER BY s.created_at DESC;
"
```

Optional attachment dedupe proof:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT
  cb.sha256,
  COUNT(DISTINCT s.id) AS distinct_sources,
  COUNT(DISTINCT dv.document_id) AS distinct_documents
FROM sources s
JOIN source_versions sv ON sv.source_id = s.id
JOIN content_blobs cb ON cb.id = sv.content_blob_id
JOIN document_versions dv ON dv.id = sv.document_version_id
WHERE s.source_type = 'gmail_attachment'
GROUP BY cb.sha256
ORDER BY distinct_sources DESC;
"
```

Expected:

- `uv run cos auth gmail` completes successfully and creates `tokens/gmail.json`
- the sync command prints a completion summary
- at least one message is scanned
- body jobs are enqueued on the first run
- attachment jobs are enqueued if you seeded supported attachments
- worker logs show queued ingest jobs being processed
- there is no long-lived build-up of `queued` or `running` jobs after the worker catches up
- `gmail_message_body` rows exist for the test emails
- `gmail_attachment` rows exist for supported attachments
- Gmail body aliases are slugged subjects ending in `.md`
- Gmail attachment aliases use the attachment filename
- Gmail locators begin with `gmail://message/`
- if you used the same attachment bytes in two emails, at least one query row shows `distinct_sources >= 2` and `distinct_documents = 1`

#### Repeated sync (skip semantics)

After the worker has drained the queue, run the sync again:

```bash
docker compose exec cos uv run cos sync gmail
```

Expected output on the second run:

```text
Gmail sync complete:
  <N> messages scanned
  0 body jobs enqueued
  0 attachment jobs enqueued
  <N> artifacts already processed (skipped)
  0 artifacts already queued (skipped)
  0 unsupported attachments skipped
```

All previously processed artifacts should be skipped. The `artifacts already processed` count should equal the number of body + attachment sources ingested on the first run. No new jobs should appear in the queue.

#### Intentional reprocessing with --force

To force all matching artifacts to be re-staged and re-enqueued for the current run (useful after changing ingestion configuration):

```bash
docker compose exec cos uv run cos sync gmail --force
```

Expected: the summary shows body and attachment jobs enqueued again, with `0 artifacts already processed (skipped)`. The `--force` flag applies to that invocation only and does not change any persistent configuration.

---

## Test Pack 3: Google Calendar OAuth, Sync, and Provenance

Plain English: can you connect Calendar, ingest events, and see them preserved as real knowledge-base records?

### Pack-specific setup

Make sure `config.yaml` still contains:

```yaml
connectors:
  - google_calendar

google_oauth:
  client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
  client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET

google_calendar:
  calendar_ids:
    - primary
  lookback_hours: 24
  lookahead_days: 14
```

In Google Calendar, on the authenticated account's primary calendar, create an event within the configured lookahead window:

- title: `Epic 6 UAT Calendar Event`
- description: `epic-6-uat-calendar-description`

### Run the test

Authenticate on the host if `tokens/google_calendar.json` is missing or stale:

```bash
uv run cos auth calendar
```

Then run the sync inside the container:

```bash
docker compose exec cos uv run cos sync calendar
docker compose logs worker --tail=100
```

Inspect Calendar provenance rows:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT s.source_type, s.source_alias, s.source_locator
FROM sources s
WHERE s.source_type = 'google_calendar_event'
ORDER BY s.created_at DESC;
"
```

Also confirm the results are visible through the CLI:

```bash
docker compose exec cos uv run cos docs --json
```

Expected:

- `uv run cos auth calendar` completes successfully and creates `tokens/google_calendar.json`
- the sync command prints how many calendars were scanned
- at least one event is discovered if you seeded one inside the configured time window
- jobs are enqueued for discovered events
- at least one `google_calendar_event` row exists
- the alias is a slugged title plus calendar ID and event ID, ending in `.md`
- the locator begins with `google-calendar://`
- calendar-derived documents appear alongside local and Gmail-derived content in `cos docs --json`

---

## Test Pack 4: MCP `ingest_document` First Ingest

Plain English: can a normal user save a new note from Claude into the platform?

### Pack-specific setup

If the MCP server is not already configured in Claude Code, run:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Open a fresh Claude Code or Claude Desktop session connected to the `cos` MCP server.

### Run the test

Ask the MCP client:

```text
Call ingest_document with:
- content: "Epic 6 MCP note. Marker: epic-6-mcp-first-ingest-a."
- metadata:
  - title: "Epic 6 MCP First Ingest"
  - external_id: "epic-6-mcp-first-ingest-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Expected:

- `status` is `ok`
- `data.outcome` is `new_content`
- `data.source_alias` is present
- `data.source_locator` starts with `mcp_note://`
- `citations` is an empty list

---

## Test Pack 5: MCP Unchanged Retry / Idempotency

Plain English: if you accidentally send the same note twice, the platform should recognise that and avoid creating duplicate versions.

### Pack-specific setup

If needed, add the MCP server:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Open a fresh Claude Code or Claude Desktop session connected to the `cos` MCP server.

### Run the test

First ingest:

```text
Call ingest_document with:
- content: "Epic 6 retry note. Marker: epic-6-retry-note-a."
- metadata:
  - title: "Epic 6 Retry Note"
  - external_id: "epic-6-retry-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Then immediately repeat the exact same request:

```text
Call ingest_document again with:
- content: "Epic 6 retry note. Marker: epic-6-retry-note-a."
- metadata:
  - title: "Epic 6 Retry Note"
  - external_id: "epic-6-retry-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Expected:

- the first response returns `data.outcome = new_content`
- the second response returns `data.outcome = unchanged`
- the second response does not create a new version

---

## Test Pack 6: Cross-Source Exact-Byte Dedupe

Plain English: if the same bytes arrive through different channels, the platform should keep separate provenance rows but only one canonical content record.

### Pack-specific setup

Create the exact-byte local file on the host. Use `printf`, not `echo`, so no trailing newline is added:

```bash
mkdir -p data/uat-docs/cross-source
printf '%s' 'Epic 6 cross-source note. This note tracks workforce planning for the quarterly board review. Marker: epic-6-cross-source-note-a.' > data/uat-docs/cross-source/epic-6-cross-source-note.md
```

In Gmail, using the authenticated UAT account:

1. Create or reuse the `cos-uat` label.
2. Send yourself one email with:
   - subject: `Epic 6 Cross Source Gmail Attachment`
   - body text containing `epic-6-cross-source-gmail-body-a`
   - attachment: `data/uat-docs/cross-source/epic-6-cross-source-note.md`
   - label: `cos-uat`

If `tokens/gmail.json` is missing or stale, authenticate on the host:

```bash
uv run cos auth gmail
```

If needed, add the MCP server:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

### Run the test

Ingest the local file:

```bash
docker compose exec cos uv run cos ingest /data/uat-docs/cross-source/epic-6-cross-source-note.md
```

Sync Gmail and wait for the worker:

```bash
docker compose exec cos uv run cos sync gmail
docker compose logs worker --tail=100
```

In a fresh Claude Code or Claude Desktop session, ingest the same bytes as an MCP note:

```text
Call ingest_document with:
- content: "Epic 6 cross-source note. This note tracks workforce planning for the quarterly board review. Marker: epic-6-cross-source-note-a."
- metadata:
  - title: "Epic 6 Cross Source Note"
  - external_id: "epic-6-cross-source-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Now verify the cross-source dedupe proof with SQL:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT
  s.source_type,
  s.source_alias,
  s.source_locator,
  cb.sha256,
  dv.document_id
FROM sources s
JOIN source_versions sv ON sv.source_id = s.id
JOIN content_blobs cb ON cb.id = sv.content_blob_id
JOIN document_versions dv ON dv.id = sv.document_version_id
WHERE
  (s.source_type = 'file' AND s.source_locator = '/data/uat-docs/cross-source/epic-6-cross-source-note.md')
  OR (s.source_type = 'gmail_attachment' AND s.source_alias = 'epic-6-cross-source-note.md')
  OR (s.source_type = 'mcp_note' AND s.source_locator = 'mcp_note://claude-code/epic-6-cross-source-note-001')
ORDER BY s.created_at;
"
```

Expected:

- at least three rows exist: one `file`, one `gmail_attachment`, and one `mcp_note`
- all rows share the same `sha256`
- all rows share the same `document_id`
- all rows have different `source_type` and `source_locator` values

---

## Test Pack 7: Near-Duplicate Warning

Plain English: if you submit a very similar note, the platform should warn you without blocking normal work.

### Pack-specific setup

If needed, add the MCP server:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

If you want a more aggressive UAT pass, temporarily lower the threshold in `config.yaml`:

```yaml
mcp_note:
  near_duplicate_threshold: 0.90
```

If you changed the threshold, restart the platform:

```bash
uv run cos restart
```

Open a fresh Claude Code or Claude Desktop session connected to the `cos` MCP server.

### Run the test

Seed the baseline note:

```text
Call ingest_document with:
- content: "Epic 6 near-duplicate baseline. Marker: epic-6-near-duplicate-a."
- metadata:
  - title: "Epic 6 Near Duplicate Baseline"
  - external_id: "epic-6-near-duplicate-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Then submit a similar note:

```text
Call ingest_document with:
- content: "Epic 6 near duplicate baseline. Marker: epic-6-near-duplicate-a with slightly revised wording for executive prep."
- metadata:
  - title: "Epic 6 Near Duplicate Similar"
  - external_id: "epic-6-near-duplicate-002"
  - client: "claude-code"
Show me the raw JSON response.
```

Expected:

- both calls return `status = ok`
- the second ingest still succeeds
- the second response may include `data.warning`
- if no warning appears and you want to force the scenario, lower the threshold, restart, and rerun this pack

---

## Test Pack 8: Changed Content and Version History

Plain English: if you update an existing note, the platform should create a new version and preserve the older one.

### Pack-specific setup

If needed, add the MCP server:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Open a fresh Claude Code or Claude Desktop session connected to the `cos` MCP server.

### Run the test

First ingest:

```text
Call ingest_document with:
- content: "Epic 6 versioned note. Marker: epic-6-versioned-note-a."
- metadata:
  - title: "Epic 6 Versioned Note"
  - external_id: "epic-6-versioned-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Record the returned `data.document_id`.

Then submit updated content for the same stable identity:

```text
Call ingest_document with:
- content: "Epic 6 versioned note updated. Marker: epic-6-versioned-note-a-v2. This version adds succession planning."
- metadata:
  - title: "Epic 6 Versioned Note"
  - external_id: "epic-6-versioned-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Verify version history through the CLI:

```bash
docker compose exec cos uv run cos docs --versions <document_id>
docker compose exec cos uv run cos docs --versions <document_id> --json
```

Expected:

- the first response returns `data.outcome = new_content`
- the second response returns `data.outcome = changed_content`
- the second response message refers to a new version
- `cos docs --versions <document_id>` shows at least 2 versions
- version numbers increase from `1` to `2` or higher
- the versions have distinct `ingested_at` timestamps and `file_hash` values

---

## Test Pack 9: Retrieval Across Mixed Sources

Plain English: can a normal user ask grounded questions across local files, Gmail, Calendar, and MCP notes and get the right citations back?

### Pack-specific setup

Seed one record for each source type used in retrieval, plus one deliberate
“sibling record” pair for the single-source grounding checks.

Create and ingest a local file:

```bash
mkdir -p data/uat-docs/retrieval
printf '%s' 'Epic 6 retrieval local note. Marker: epic-6-retrieval-local-a. Workforce segmentation framework lives here.' > data/uat-docs/retrieval/epic-6-retrieval-local.md
printf '%s' 'Epic 6 retrieval local leave policy note. Marker: epic-6-retrieval-local-leave-a. Local file says the leave policy allows 20 days.' > data/uat-docs/retrieval/epic-6-retrieval-local-leave.md
docker compose exec cos uv run cos ingest /data/uat-docs/retrieval/epic-6-retrieval-local.md
docker compose exec cos uv run cos ingest /data/uat-docs/retrieval/epic-6-retrieval-local-leave.md
```

Seed two Gmail messages:

1. Send yourself an email with:
   - subject: `Epic 6 Retrieval Gmail`
   - body text: `epic-6-retrieval-gmail-a`
   - label: `cos-uat`
2. Send yourself a second email with:
   - subject: `Epic 6 Retrieval Gmail Leave Policy`
   - body text: `epic-6-retrieval-gmail-leave-a. Email says the leave policy allows 25 days.`
   - label: `cos-uat`
3. Authenticate if needed:

```bash
uv run cos auth gmail
```

4. Sync Gmail:

```bash
docker compose exec cos uv run cos sync gmail
docker compose logs worker --tail=100
```

Seed one Calendar event:

1. Create an event on the primary calendar with:
   - title: `Epic 6 Retrieval Calendar Event`
   - description: `epic-6-retrieval-calendar-a`
2. Authenticate if needed:

```bash
uv run cos auth calendar
```

3. Sync Calendar:

```bash
docker compose exec cos uv run cos sync calendar
docker compose logs worker --tail=100
```

Seed one MCP note:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

In a fresh Claude Code or Claude Desktop session:

```text
Call ingest_document with:
- content: "Epic 6 retrieval MCP note. Marker: epic-6-retrieval-mcp-a. Workforce planning note for the quarterly board review."
- metadata:
  - title: "Epic 6 Retrieval MCP Note"
  - external_id: "epic-6-retrieval-mcp-001"
  - client: "claude-code"
Show me the raw JSON response.
```

### Run the test

In the same MCP client session, ask retrieval questions:

```text
Use retrieve to answer: what did the Epic 6 Retrieval Gmail message say?
```

```text
Use retrieve to answer: what is the Epic 6 Retrieval Calendar Event about?
```

```text
Use retrieve to answer: what does the Epic 6 retrieval MCP note say about workforce planning?
```

```text
Use retrieve to answer: what does the Epic 6 retrieval local note say about workforce segmentation?
```

Expected:

- each response comes back through the standard MCP envelope
- answers are grounded rather than fabricated
- citations include `source_alias` and `source_locator`
- the cited aliases and locators correspond to the seeded Gmail, Calendar, MCP, or local records

### Single-lineage grounding spot checks (Story 6.14)

In the same MCP client session, ask a direct factual question about the
leave-policy email:

```text
Use retrieve to answer: what did the Epic 6 Retrieval Gmail Leave Policy message say about leave?
```

Then ask an explicit comparison query:

```text
Use retrieve to answer: compare the Epic 6 Retrieval Gmail Leave Policy message vs the Epic 6 retrieval local leave policy note.
```

Expected:

- the direct factual query stays grounded to one source lineage
- the direct factual query answer reflects the Gmail message's `25 days` statement
- the direct factual query citations point only to the Gmail leave-policy record, not the local leave-policy file
- the explicit compare query is allowed to use multi-source evidence
- the compare query citations include both the Gmail leave-policy record and the local leave-policy file
- the compare query does not pull in unrelated seeded records such as the Calendar event or the workforce-planning MCP note

### No-answer threshold fallback spot check (Story 6.13)

Temporarily raise the retrieval threshold high enough that no result can
survive filtering.

Edit `config.yaml` and add or update:

```yaml
retrieval:
  min_score: 1.0
```

Restart the platform:

```bash
docker compose restart cos
docker compose ps
```

Then rerun one of the known-good retrieval questions, for example:

```text
Use retrieve to answer: what does the Epic 6 retrieval local note say about workforce segmentation?
```

Expected:

- the response still comes back through the normal MCP envelope
- the answer is exactly `No relevant content found in the knowledge base.`
- both top-level `citations` and `data.citations` are empty

After this check, restore your previous `retrieval.min_score` value and restart
the `cos` container again before moving on to the restart pack.

---

## Test Pack 10: Restart and Token Persistence

Plain English: after a restart, the platform should come back healthy without making you reconnect Gmail or Calendar.

### Pack-specific setup

Make sure both OAuth token files exist. If they do not, re-authenticate on the host:

```bash
uv run cos auth gmail
uv run cos auth calendar
```

Optionally seed one fresh Gmail message and one fresh Calendar event before running the restart check so there is visible work after restart.

### Run the test

Restart the platform from the host:

```bash
uv run cos restart
```

If `cos restart` is unavailable from the host path, use Docker Compose directly:

```bash
docker compose restart
docker compose ps
```

Verify token files still exist on the host:

```bash
ls -la tokens/gmail.json tokens/google_calendar.json
```

Capture a UTC timestamp before re-running the syncs:

```bash
export RESTART_SYNC_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
```

Re-run the connected-source syncs without re-authorising:

```bash
docker compose exec cos uv run cos sync gmail
docker compose exec cos uv run cos sync calendar
docker compose logs worker --tail=100
docker compose exec postgres psql -U postgres -d cos -c "
SELECT status, COUNT(*)
FROM jobs
WHERE created_at >= TIMESTAMPTZ '${RESTART_SYNC_STARTED_AT}'
GROUP BY status
ORDER BY status;
"
```

Expected:

- the restart command brings the platform back healthy
- `tokens/gmail.json` and `tokens/google_calendar.json` survive the restart
- re-running Gmail and Calendar sync does not open a browser
- the sync commands complete using the persisted token state
- post-restart jobs may briefly appear as `queued` or `running`
- after the worker catches up, there is no long-lived backlog for jobs created since `RESTART_SYNC_STARTED_AT`

---

## Final Operator Spot Checks

Plain English: this is the quick sanity check that the database now contains the source mix and dedupe shape you expect after the supporting packs.

Run these from the host or container as shown:

```bash
docker compose exec cos uv run cos docs
docker compose exec cos uv run cos docs --json
docker compose exec postgres psql -U postgres -d cos -c "SELECT source_type, COUNT(*) FROM sources GROUP BY source_type ORDER BY source_type;"
docker compose exec postgres psql -U postgres -d cos -c "SELECT COUNT(*) AS blobs FROM content_blobs;"
docker compose exec postgres psql -U postgres -d cos -c "SELECT COUNT(*) AS source_versions FROM source_versions;"
```

Run the dedupe summary:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT
  COUNT(DISTINCT s.id) AS total_sources,
  COUNT(DISTINCT cb.id) AS total_blobs,
  COUNT(DISTINCT dv.document_id) AS total_documents
FROM sources s
JOIN source_versions sv ON sv.source_id = s.id
JOIN content_blobs cb ON cb.id = sv.content_blob_id
JOIN document_versions dv ON dv.id = sv.document_version_id;
"
```

Expected:

- `cos docs` lists a mixture of local, Gmail, Calendar, and MCP-ingested records
- `sources` contains rows for at least:
  - `file`
  - `gmail_message_body`
  - `gmail_attachment` if attachments were seeded
  - `google_calendar_event`
  - `mcp_note`
- `content_blobs` count is less than or equal to the total number of sources
- `total_sources` is greater than `total_blobs` and `total_documents` if any dedupe occurred across sources

## Test Pack 11: Epic 7 Retrieval Trust Regression Suite

Plain English: this is the release-gate check for retrieval trust. It answers the question, "if a user asks for a fact, a document-reading question, a comparison, a briefing request, or a no-answer case, does the retrieval layer pull the right evidence and avoid bluffing before any final prose is written?"

Technically, this pack validates the combined retrieval stack from Stories 7.1 through 7.5 using the committed evaluation corpus. It is a retrieval-trust gate, not a full connected-source or live-synthesis end-to-end test.

### What a normal user is really checking

In user terms, this pack is checking what the system would have in hand before it writes the final answer:

- **Direct questions stay grounded to one source.** If one document says `20 days` and another says `25 days`, retrieval should not pull both as the basis for a simple fact answer.
- **Document-reading questions keep enough same-document context.** If the answer depends on the middle of a longer document, retrieval should pull enough surrounding context from that document to support an accurate answer later.
- **Compare and briefing prompts broaden only when appropriate.** Retrieval can collect multiple sources for a compare request, but it should not widen scope unnecessarily.
- **No-answer prompts stay honest.** If the knowledge base does not contain the answer, retrieval should return no good evidence rather than a misleading near match.
- **Retrieval remains fast enough to support interactive use.**

### What each benchmark class means in user terms

| Query class | In plain English |
|---|---|
| `direct_fact` | "Answer one concrete factual question from the right source." |
| `exact_phrase` | "Find the exact wording I remember." |
| `date_timeline` | "Pull the right date or time-based fact." |
| `single_doc_interpretation` | "Understand one document well enough to answer a context-dependent question." |
| `cross_doc_synthesis` | "Compare or combine multiple sources because I explicitly asked for it." |
| `briefing` | "Gather the evidence for a short grounded brief, even if only one strong source is available." |
| `no_answer` | "Tell me there is no evidence instead of making something up." |

The benchmark does **not** require connected sources, OAuth tokens, or live LLM synthesis. It needs only the running platform (Postgres accessible) and a copy of the repo on the host.

At a high level, think of this pack as checking three retrieval promises:

- **"Use the right evidence."**
- **"Do not blend sources unless I asked you to."**
- **"Do not make up answers when the evidence is missing."**

It does not, by itself, say anything about Gmail auth, Calendar sync, worker durability, or final assistant phrasing. Use the supporting packs for those.

### Pack-specific setup

The benchmark runs from the **host** against the Docker-backed database. If you already completed the pre-UAT isolation step, you should already have a host-accessible `config.host.yaml` that points at the same dedicated UAT database name as `config.yaml`.

If you do not already have `config.host.yaml`, create a host-accessible config variant:

```bash
cp config.yaml config.host.yaml
```

Open `config.host.yaml` and change the database host:

```yaml
database:
  host: localhost  # was: postgres
```

`config.host.yaml` is gitignored and must not be committed — it contains your API credentials.

For the authoritative retrieval-trust gate, point `config.host.yaml` at a **clean benchmark database**. The preferred path is the pre-UAT isolated-database workflow near the start of this guide: create a dedicated local `dbname`, recreate it, then run the benchmark before any other UAT/manual ingestion. If the configured database already contains previously ingested non-fixture documents, the benchmark still runs, but the result is diagnostic only because ambient documents participate in retrieval.

Confirm the platform is running:

```bash
docker compose ps
```

Expected:

- `postgres` is `healthy`
- `cos` is `healthy`

### Run the gold-corpus benchmark (authoritative gate on a clean benchmark database)

```bash
uv run cos benchmark \
  --config config.host.yaml \
  --corpus tests/fixtures/retrieval_eval \
  --output _bmad-output/implementation-artifacts/7-5-benchmark-report.json
```

Expected:

- The benchmark seeds six fixture documents, runs all eight gold queries, then cleans up the fixtures.
- A human-readable summary prints to stdout, grouped by query class.
- A JSON report is written to `_bmad-output/implementation-artifacts/7-5-benchmark-report.json`.
- On a clean benchmark database, this run is the authoritative retrieval-trust gate.
- Exit code 0 when all eight gold queries pass; exit code 1 when any fail.

### Run the fuzz layer (optional diagnostic)

```bash
uv run cos benchmark \
  --config config.host.yaml \
  --corpus tests/fixtures/retrieval_eval \
  --include-fuzz \
  --output _bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json
```

Expected:

- The fuzz layer adds five adversarial queries (noisy phrasing, cross-doc noise, near-synonym matching, empty-corpus no-answer).
- A human-readable summary prints to stdout.
- A JSON report is written to `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json`.
- These results are diagnostic only; a fuzz failure does not gate the release unless you explicitly decide to hold on it.

### Trust guarantee checks

Inspect the saved JSON report after the relevant run completes:

- use `_bmad-output/implementation-artifacts/7-5-benchmark-report.json` for gold-only checks
- use `_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json` for fuzz-specific checks

If you run the fuzz layer without `--output`, the CLI prints the full JSON report to stdout and does **not** update the saved gold report file.

#### Single-lineage direct facts — gold-df-001 and fuzz-df-002

Direct-fact and equivalent queries must resolve to exactly one supporting source. Multi-source answers for a direct-fact query mean lineage narrowing failed.

Gold run:

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] == 'gold-df-001':
        print(q['query_id'], 'pass=' + str(q['pass']),
              'actual_lineage=' + str(q['actual_lineage']))
"
```

Fuzz run:

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report-fuzz.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] == 'fuzz-df-002':
        print(q['query_id'], 'pass=' + str(q['pass']),
              'actual_lineage=' + str(q['actual_lineage']))
"
```

Expected:

- `gold-df-001`: `pass=True`, `actual_lineage` is `['local://local-leave-policy']` only
- `fuzz-df-002` (fuzz layer only): `pass=True`, `actual_lineage` is `['mcp://note-retention-q4-2024']` only

If either query returns more than one lineage source, or returns the wrong source, check `failure_stage` in the JSON. A `failure_stage` of `lineage_narrowing` means the top-ranked source after RRF was not the expected document.

#### Bounded-context document-first recovery — gold-sdi-002

This query tests Story 7.4's document-first routing and bounded context expansion for a multi-chunk document.

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] == 'gold-sdi-002':
        print('pass=' + str(q['pass']),
              'actual_lineage=' + str(q['actual_lineage']))
        print('failure_stage=' + str(q['failure_stage']))
        cc = q['candidate_counts']
        print('expansion_mode=' + str(cc.get('expansion_mode')),
              'expanded_context=' + str(cc.get('expanded_context')))
"
```

Expected: `pass=True`, `actual_lineage` is `['local://local-performance-policy']`, `expansion_mode=bounded`.

Note: The benchmark scores strictly against `citation_chunk_index=1` declared in the corpus manifest for `local-performance-policy.md`. If bounded context expansion returns multiple chunks from the same document and the evidence selection does not narrow to chunk 1, `citation_precision` will drop and the query will fail with `failure_stage=citation_precision`. The source document is still found correctly — only the chunk index matching is strict. This is a known scoring characteristic of multi-chunk fixture documents.

#### Allowed multi-source synthesis — gold-cds-001 and gold-br-001

These queries check the two allowed multi-source behaviours: explicit comparison must use the requested sources, while briefing may use one or more approved sources depending on what is actually relevant.

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] in ('gold-cds-001', 'gold-br-001'):
        print(q['query_id'], 'pass=' + str(q['pass']),
              'actual_lineage=' + str(q['actual_lineage']))
"
```

Expected:

- `gold-cds-001`: on a clean benchmark database, `actual_lineage` contains both `local://local-leave-policy` and `gmail://msg-leave-policy-001`, and no additional sources beyond those two
- `gold-br-001`: `actual_lineage` is a subset of the approved retention sources (`mcp://note-retention-q4-2024`, `calendar://event-q1-review-001`); one or both may appear, but no unapproved source should

If `gold-cds-001` returns additional sources beyond the expected two, the database is not clean enough for an authoritative gate run. The benchmark fixture documents and any live production/UAT content share the same retrieval index. This may reflect ambient data rather than a retrieval logic error, but it still disqualifies the run as the authoritative retrieval-trust gate; capture it as diagnostic evidence and rerun on a clean benchmark database.

#### No-answer contract — gold-na-001

This is a mandatory release gate. The system must decline to answer when there is no relevant evidence in the corpus.

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] == 'gold-na-001':
        print('pass=' + str(q['pass']),
              'verdict=' + q['answerability_verdict'])
        print('actual_lineage=' + str(q['actual_lineage']))
"
```

Expected: `pass=True`, `answerability_verdict=correct_no_answer`, `actual_lineage=[]`.

If `pass=False` with `answerability_verdict=false_answer`, the retrieval system returned a topically-related document (often `local://local-performance-policy`, which has HR-domain overlap with pension-related vocabulary) with a score above the current threshold:

1. Add `retrieval.min_score: 0.005` to `config.host.yaml` (or whichever file you pass to `--config`) — see the retrieval section in `config.yaml.example` for the RRF score range explanation.
2. Rerun the benchmark.

No restart is required for the benchmark rerun: `cos benchmark` reads the file passed to `--config` directly.

The `min_score` threshold is the primary operator control for the no-answer contract. At the default `min_score: 0.0`, any result passes regardless of similarity. A value in the range `0.001–0.02` prunes weak matches while preserving strong ones.

### Latency review

The PRD target for interactive retrieval is **under 5 seconds** per query.

**Scope of the measurement:** The benchmark measures deterministic retrieval and citation-path latency using static embeddings. It does not include live LLM synthesis latency. The `avg_latency_ms` values in the JSON report represent the retrieval and citation pipeline only — not the full round-trip time an operator sees in the MCP client.

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
target_ms = 5000
latency_classes = ['direct_fact', 'exact_phrase', 'date_timeline', 'single_doc_interpretation']
print(f'PRD retrieval target: <{target_ms}ms (retrieval path only, excludes LLM)')
for c in r['per_class']:
    if c['query_class'] in latency_classes:
        status = 'OK' if c['avg_latency_ms'] < target_ms else 'EXCEEDS TARGET'
        print(f'  [{status}] {c[\"query_class\"]}: {c[\"avg_latency_ms\"]:.0f}ms avg')
"
```

If any interactive class exceeds 5000ms, record in your UAT notes or release checklist:

1. The query class and observed average latency
2. The `candidate_counts` from the failing queries (available per query in the JSON)
3. A likely explanation (database load, index scan size, network round-trip to Docker host)
4. The decision: accept the gap with documentation for this release, or fix first

### Reading the JSON report

For a non-technical read, start with:

- `summary` for the overall pass rate
- `per_class` for whether a whole query style regressed
- `per_query` only when you need to explain a specific failure

For a technical read, use the fields below.

Key fields in `per_query` entries:

| Field | Meaning |
|-------|---------|
| `pass` | True if recall and citation precision both satisfied |
| `answerability_verdict` | `correct_answer`, `missed_answer`, `correct_no_answer`, `false_answer` |
| `actual_lineage` | Source locators returned by the retrieval pipeline |
| `expected_lineage` | Source locators the query should have returned |
| `failure_stage` | Stage where evidence was lost: `candidate_selection`, `threshold_filtering`, `pruning`, `top_k_truncation`, `lineage_narrowing`, `evidence_selection`, `context_expansion`, `citation_precision` |
| `candidate_counts.keyword` | BM25 search candidates |
| `candidate_counts.semantic` | Vector search candidates |
| `candidate_counts.merged` | Candidates after RRF merge |
| `candidate_counts.post_threshold` | Candidates surviving `min_score` filter |
| `candidate_counts.final` | Candidates after top-k truncation |
| `candidate_counts.post_lineage` | Candidates remaining after lineage selection: winning anchors for BOUNDED queries, or lineage-narrowed chunks for DEFAULT queries |
| `candidate_counts.expansion_mode` | `bounded` for `single_doc_interpretation`, `none` for other classes |
| `candidate_counts.expanded_context` | Total chunks in the bounded synthesis context after expansion |
| `latency_ms` | Retrieval pipeline latency for this query in milliseconds |

---

## Test Pack 12: Epic 8 Interactive Telegram Live

Plain English: can you send a question and a note via Telegram and get the right cited answer back, have the note become a first-class knowledge-base source, and confirm that a Telegram API outage does not take down local MCP retrieval?

This pack validates the reactive Telegram slice from Stories 8.1, 8.2, and 8.3 using a real Telegram client and a real Docker Compose deployment. It is intentionally a live manual runbook, not an automated test.

### Pack-specific prerequisites

Before running this pack, confirm all of the following:

- `telegram.bot_token` is set to a valid bot token in `config.yaml`
- `telegram.chat_id` is set to the numeric chat ID for your test conversation. To discover it, send `/start` or any short message to the bot, then run `curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"` from the host and copy the returned `message.chat.id`; the platform connector intentionally does not log incoming chat IDs.
- `"telegram"` is listed in `connectors` in `config.yaml`
- `telegram` is in the active role pack's `output_channels` (already present in `role_packs/chro.yaml`)
- all Docker Compose services are running: `docker compose ps` shows `postgres`, `tika`, `cos`, `worker`, and `telegram-bot` all `Up` or `healthy`
- `docker compose logs telegram-bot --tail=50` contains a log line with `"message": "Telegram polling started"` and no repeated startup errors after that line
- a working MCP client is available for the local retrieval verification step

If `telegram-bot` is not running or is in a restart loop, check `docker compose logs telegram-bot --tail=50` for startup errors before continuing.

### Pack-specific setup: seed the Q&A validation document

Run these commands from the repo root on the **host**:

```bash
mkdir -p data/uat-docs/telegram
printf '%s\n' 'Epic 8 Telegram live validation policy. Marker: epic-8-telegram-live-question-a. The Telegram live validation policy says reactive Telegram Q&A must return cited answers.' > data/uat-docs/telegram/epic-8-telegram-live-question.md
docker compose exec cos uv run cos ingest /data/uat-docs/telegram/epic-8-telegram-live-question.md
```

Expected:

- the ingest command prints a completion summary with no errors
- `docker compose exec cos uv run cos docs` lists `epic-8-telegram-live-question.md` as a `file` source

Record the `source_alias` returned by `cos docs`:

```text
[EVIDENCE] Seeded Q&A source_alias: ________________________________
```

### Step 1 — Live Telegram Q&A smoke path (AC #1)

Send the following message to the bot from your Telegram client:

```text
What does the Epic 8 Telegram live validation policy say?
```

Record the time you sent the message.

**Pass signal:** the bot replies with a concise answer containing a `Sources:` block that names the exact seeded `source_alias` you recorded above. A fluent answer with no `Sources:` block is not a pass.

**Fail boundary:** the bot timeout is 60 seconds (`_RETRIEVAL_TIMEOUT_SECONDS`). Any reply received within 60 seconds passes the time boundary. A timeout returns the recovery reply `"I could not answer that just now. Check 'cos logs' for diagnostics."` and is a time-boundary failure.

Evidence to record:

```text
[EVIDENCE] Q&A run timestamp (UTC):  ________________________________
[EVIDENCE] Observed end-to-end latency (send → reply):  ______ s
[EVIDENCE] Reply received: YES / NO
[EVIDENCE] Sources: block present: YES / NO
[EVIDENCE] Cited source_alias in reply:  ________________________________
[EVIDENCE] Q&A pass: YES / NO
[EVIDENCE] Notes (e.g. slow but within timeout): ________________________________
```

Note on latency: this measurement includes live Telegram API round-trip and LLM synthesis. It is not the same as the deterministic retrieval latency measured by the Epic 7 benchmark. Record the observed latency honestly; treat responses that feel too slow (even if within 60 seconds) as worth noting for future tuning.

### Step 2 — Live Telegram note capture through worker and retrieval path (AC #2)

Send the following message to the bot:

```text
Note: Epic 8 Telegram live validation note. Marker: epic-8-telegram-live-note-a. This note says live Telegram note capture works and becomes retrievable.
```

**Immediate pass signal:** the bot replies with exactly `"Note saved."` This means the note was durably staged and queued (or deduplicated as already queued/processed).

Record the acknowledgement:

```text
[EVIDENCE] Note acknowledgement received: ________________________________
[EVIDENCE] Acknowledgement text was exactly "Note saved.": YES / NO
```

Wait for the worker to index the note before testing retrieval. First, capture the note locator suffix from the bot logs. The connector logs `message_id` and `update_id`, but not full note text:

```bash
docker compose logs telegram-bot --tail=120 | grep '"message": "note enqueued"'
```

Set `NOTE_LOCATOR_SUFFIX` from that log line. Use `/message/<message_id>` when `message_id` is present; if the bot had to fall back to update identity, use `/update/<update_id>`:

```bash
NOTE_LOCATOR_SUFFIX='/message/REPLACE_WITH_MESSAGE_ID'
```

Then poll `cos docs --json` until the current note appears. This check is intentionally tied to the current note's locator suffix so older `telegram-note-...` sources cannot satisfy the wait:

```bash
docker compose exec -T cos uv run cos docs --json | NOTE_LOCATOR_SUFFIX="$NOTE_LOCATOR_SUFFIX" python3 -c '
import json, os, sys
suffix = os.environ["NOTE_LOCATOR_SUFFIX"]
docs = json.load(sys.stdin)
matches = [d for d in docs if d.get("source_locator", "").endswith(suffix)]
print(f"{len(matches)} telegram note(s) found for locator suffix {suffix}")
for d in matches:
    print("  alias={}  locator={}".format(d["source_alias"], d.get("source_locator", "")))
'
```

Wait until the above command shows exactly one `telegram-note-...md` source for the current note before continuing. Worker logs may show `job succeeded`, but the durable pass signal is the document record with the expected locator suffix.

Once the worker has drained, verify the note is retrievable via a Telegram follow-up question:

```text
What does the Epic 8 Telegram live validation note say?
```

**Pass signal:** the bot replies with an answer referencing the note content and a `Sources:` block citing a `telegram-note-...md` alias.

Evidence to record:

```text
[EVIDENCE] telegram-note source_alias:  ________________________________
[EVIDENCE] telegram-note source_locator (redact chat ID if sensitive):  telegram://chat/***/{message_id}
[EVIDENCE] Note locator suffix used for worker drain:  /message/________
[EVIDENCE] Worker processed the note before retrieval: YES / NO
[EVIDENCE] Follow-up retrieval reply cited the note: YES / NO
[EVIDENCE] Note capture pass: YES / NO
```

#### Duplicate delivery check

If you received the original `"Note saved."` twice (e.g. a Telegram retry delivered the update a second time), verify no duplicate canonical state was created:

```bash
NOTE_SOURCE_LOCATOR='telegram://chat/REAL_CHAT_ID/message/REPLACE_WITH_MESSAGE_ID'
docker compose exec -T cos uv run cos docs --json | NOTE_SOURCE_LOCATOR="$NOTE_SOURCE_LOCATOR" python3 -c '
import json, os, sys
locator = os.environ["NOTE_SOURCE_LOCATOR"]
docs = json.load(sys.stdin)
matches = [d for d in docs if d.get("source_locator") == locator]
print(f"{len(matches)} note source(s) for the recorded locator")
for d in matches:
    print("  alias={}  locator={}".format(d["source_alias"], d.get("source_locator", "")))
'
```

Expected: exactly one record for the recorded `source_locator` regardless of whether the bot sent `"Note saved."` twice. Use the real unredacted locator when running the local command; redact the chat ID only in committed evidence.

### Step 3 — Safe Telegram API outage simulation (AC #3)

This step uses a reversible `config.yaml` override. Do not revoke the bot token, change BotFather settings, or enable webhooks.

**Simulate the outage:**

1. Open `config.yaml` and temporarily change only the existing `telegram.api_base_url` value to a non-listening local endpoint. Keep the rest of the `telegram:` block, including `bot_token` and `chat_id`, unchanged:

   ```yaml
   telegram:
     api_base_url: http://127.0.0.1:9
   ```

2. Restart only the `telegram-bot` service so the bad endpoint takes effect:

   ```bash
   docker compose up -d --force-recreate telegram-bot
   ```

3. Within 60 seconds, inspect the bot logs:

   ```bash
   docker compose logs telegram-bot --tail=80
   ```

**Degraded pass signal:** look for a structured log line with `"message": "polling error — retrying after backoff"` and an `error` field describing the connection failure (e.g. `"ConnectError"` or similar). This confirms the connector is in a degraded-and-retrying state.

Evidence to record:

```text
[EVIDENCE] Degraded log line seen within 60s: YES / NO
[EVIDENCE] Log message text (redact any tokens):  ________________________________
```

**Verify local MCP retrieval still works while Telegram is degraded:**

In the MCP client, run a retrieval query against the seeded Q&A document:

```text
Use retrieve to answer: what does the Epic 8 Telegram live validation policy say?
```

**Pass signal:** the MCP retrieval returns a cited answer from the seeded `epic-8-telegram-live-question.md` source. The `cos` MCP server and local retrieval path must remain fully functional while `telegram-bot` is degraded.

Evidence to record:

```text
[EVIDENCE] MCP retrieve succeeded while Telegram degraded: YES / NO
[EVIDENCE] Cited source_alias in MCP result:  ________________________________
[EVIDENCE] Failure isolation pass: YES / NO
```

**Restore Telegram:**

1. Revert only the `telegram.api_base_url` value in `config.yaml` to the real Telegram API base:

   ```yaml
   telegram:
     api_base_url: https://api.telegram.org
   ```

2. Restart `telegram-bot`:

   ```bash
   docker compose up -d --force-recreate telegram-bot
   ```

3. Within 30 seconds, confirm polling resumes:

   ```bash
   docker compose logs telegram-bot --tail=20
   ```

   Expected: a log line containing `"message": "Telegram polling started"` followed eventually by lines without error messages.

Evidence to record:

```text
[EVIDENCE] Telegram bot resumed polling after restore: YES / NO
[EVIDENCE] Cleanup complete (api_base_url restored): YES / NO
```

### Step 4 — Verify platform config is consistent (documentation-only check)

Since this story makes no changes to Docker Compose topology, confirm the config renders cleanly:

```bash
docker compose config > /dev/null && echo "OK"
```

Expected: prints `OK` with no errors.

### Evidence Summary

Record the following before marking this story complete:

| Item | Value |
|------|-------|
| Run timestamp (UTC) | |
| Seeded Q&A `source_alias` | |
| Telegram Q&A observed latency | |
| Q&A cited `source_alias` in reply | |
| Note acknowledgement text | |
| Note `source_alias` | |
| Note `source_locator` (redact chat ID) | |
| Degraded log signal (excerpt) | |
| MCP retrieval result while degraded | |
| Bot resumed polling after restore | |
| Cleanup status | |

---

## Pass Criteria

Start with Epic 7 for retrieval changes. Run the Telegram pass criteria when you have changed the bot, output routing, or note-capture flow. Add the connected-source criteria whenever you changed ingestion, provenance, queueing, auth, MCP note handling, or restart behaviour.

### Epic 7 Retrieval Trust Regression

In plain English, Epic 7 is a pass when the benchmark proves the product can stay grounded, stay honest, and stay fast enough for interactive use.

#### 1. Benchmark completes without error

- `uv run cos benchmark --config config.host.yaml --corpus tests/fixtures/retrieval_eval` exits without a Python exception
- The human-readable summary prints a per-class breakdown to stdout
- The JSON report is written to the nominated output path
- The run is executed against a clean benchmark database; if previously ingested non-fixture documents are present, the report is diagnostic only and cannot be used as the authoritative retrieval-trust gate

#### 2. Gold-corpus pass rate

- All eight gold queries pass (exit code 0) on that clean benchmark database
- If any gold query fails, the failure is documented in the UAT notes: query ID, `failure_stage`, `actual_lineage`, and a root-cause note

#### 3. Direct-fact single-lineage contract

- `gold-df-001` passes with `actual_lineage` containing exactly one entry: `local://local-leave-policy`
- If the fuzz layer is run: `fuzz-df-002` passes with `actual_lineage` containing exactly one entry: `mcp://note-retention-q4-2024`

#### 4. No-answer contract

- `gold-na-001` passes with `answerability_verdict=correct_no_answer` and `actual_lineage=[]`
- If this fails, `retrieval.min_score` must be set to a positive value (e.g., `0.005`) and the benchmark re-run before sign-off

#### 5. Latency within target

- All interactive classes (`direct_fact`, `exact_phrase`, `date_timeline`, `single_doc_interpretation`) have `avg_latency_ms < 5000` in the JSON `per_class` breakdown
- If any class exceeds the target, the observed latency, candidate counts, and likely explanation are recorded in the UAT notes

#### 6. Evidence captured in the test record

- The benchmark JSON report is saved at a stable path under `_bmad-output/implementation-artifacts/`
- The UAT notes include the run timestamp, corpus version, pass rate, per-class summary, and any documented exceptions
- If a populated-database run is captured for diagnostics, the test record labels it as diagnostic rather than treating it as the authoritative retrieval-trust gate

### Epic 8 Reactive Telegram

In plain English, Epic 8 is a pass when all three reactive Telegram behaviors work end-to-end: a question gets a cited answer, a note becomes a first-class knowledge-base source, and a Telegram API failure does not degrade local MCP retrieval.

#### 1. Live Telegram Q&A (AC #1)

- a question sent from the Telegram client is answered within 60 seconds
- the reply contains a `Sources:` block citing the seeded `source_alias`
- a fluent answer with no `Sources:` block is not a pass
- the observed end-to-end latency is recorded honestly; a timeout returns the recovery reply and is a failure

#### 2. Live Telegram note capture (AC #2)

- the immediate acknowledgement is exactly `"Note saved."`
- after the worker drains, the note appears in `cos docs` as a `telegram_note` source with a `telegram-note-...md` alias and a `telegram://chat/.../message/...` locator
- a follow-up retrieval query (via Telegram or MCP) cites the note's `source_alias`
- if a duplicate delivery occurred, exactly one canonical source record exists for the same locator and fingerprint

#### 3. Telegram failure isolation (AC #3)

- after pointing `telegram.api_base_url` at a non-listening local endpoint and restarting `telegram-bot`, the bot logs `"polling error — retrying after backoff"` with an error field within 60 seconds
- local MCP `retrieve` against the seeded Q&A document returns a cited answer while the bot is degraded
- after restoring the real `api_base_url`, the bot logs `"Telegram polling started"` and resumes normal polling
- the `config.yaml` `api_base_url` is confirmed restored before the story is marked complete

#### 4. Evidence captured

- all evidence fields in the Test Pack 12 Evidence Summary table are filled in
- no bot tokens, full chat IDs, or private note text appear in the committed evidence

---

### Connected-Source and Operations Regression

In plain English, this is the "does the current product still behave like a usable connected knowledge base?" layer.

This layer is a pass when all of the following are true:

#### 1. Connected-source visibility

- local, Gmail, Calendar, and MCP-note records all appear in `cos docs` output
- all records expose `source_alias` and `source_locator`
- no `source_path` appears as a primary provenance field for connected sources

#### 2. Cross-source exact-byte dedupe

- the cross-source dedupe pack shows the local file, Gmail attachment, and MCP note rows sharing one `sha256`
- those same rows share one `document_id`
- the final summary query shows `total_sources > total_blobs` when dedupe has occurred

#### 3. Unchanged vs changed content

- the unchanged retry pack returns `data.outcome = unchanged` on the second identical ingest
- the changed-content pack returns `data.outcome = changed_content` when content changes under the same stable `external_id`
- version history shows at least 2 versions with distinct `file_hash` values

#### 4. Restart and token persistence

- the platform recovers to healthy after restart
- `tokens/gmail.json` and `tokens/google_calendar.json` persist across restart
- post-restart Gmail and Calendar syncs complete without browser re-authorisation
- post-restart jobs drain back to no long-lived backlog

#### 5. Retrieval hardening remains correct

- retrieval responses remain grounded after connected-source ingestion
- direct factual queries stay on a single source lineage when sibling records disagree
- explicit compare/synthesis queries can still use multi-source evidence
- citations include `source_alias` and `source_locator`
- the cited sources correspond to the seeded local, Gmail, Calendar, or MCP records
- when `retrieval.min_score` is temporarily raised high enough to filter everything out, `retrieve` returns `No relevant content found in the knowledge base.` with empty citations rather than a weakly grounded answer

---

## Cleanup

If this was a one-off UAT run against a personal Google account:

- remove or archive the `cos-uat` Gmail label and test emails
- delete the Calendar test events
- remove `tokens/gmail.json` and `tokens/google_calendar.json` if you do not want to keep the local auth state
- clear `data/` and restart containers if you want a clean local knowledge base afterwards

If you ran Test Pack 12 (Telegram live):

- confirm `telegram.api_base_url` in `config.yaml` is restored to `https://api.telegram.org` (the outage simulation step should have already done this)
- remove `data/uat-docs/telegram/epic-8-telegram-live-question.md` from the host if you do not want it to remain in the knowledge base
- the seeded `telegram-note-...` source will remain in the knowledge base after the worker indexes it; remove it via SQL or recreate the UAT database if you want a fully clean state after the run
