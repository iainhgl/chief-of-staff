# Manual Testing Guide

Reflects the platform at the end of **Epic 6: Canonical Source Identity & Connected Ingestion**.

This guide is organized as self-contained test packs. Other than the shared bootstrap for config and platform startup, a tester should be able to open any pack, run its setup, and complete that validation without needing to read a different section first.

---

## Epic 6 Summary

Epic 6 turns the platform from a local-document knowledge base into a connected-ingestion system with a durable provenance model:

- canonical identity is based on content blobs, not raw file paths
- exact-byte deduplication works across local files, Gmail, Google Calendar, and MCP note ingest
- provenance is preserved as `source_type`, `source_alias`, and `source_locator`
- Gmail sync stages message bodies and supported attachments, then enqueues background ingest jobs
- Google Calendar sync stages event Markdown and enqueues background ingest jobs
- a dedicated `worker` service drains the ingest queue in the background
- the MCP server exposes `ingest_document` for direct note capture with stable external IDs and warning-only near-duplicate detection
- old pre-Epic-6 data can be backfilled onto the canonical model with `cos migrate`

---

## Shared Prerequisites

- Docker Desktop or Rancher Desktop running
- `uv` installed
- working directory is the repo root: `cos/`
- live Anthropic and Voyage credentials in `config.yaml`
- a real Google account you can safely use for Gmail and Calendar UAT
- Claude Code or Claude Desktop available for the live MCP tests

Important runtime rule:

- use `uv run cos auth ...` and `uv run cos restart` on the **host**
- use `docker compose exec cos uv run cos ...` for commands that need the app's Docker network and `database.host: postgres`
- anything you create under `data/` on the host is visible inside the `cos` container under `/data/`

---

## Shared Platform Bootstrap

Run this once before any of the test packs below.

### 1. Prepare `config.yaml`

Copy the template if needed:

```bash
cp config.yaml.example config.yaml
```

For Epic 6 UAT, make sure these areas are populated:

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

### 2. Enable Google APIs

In the Google Cloud project behind your OAuth desktop client, enable:

- Gmail API
- Google Calendar API

### 3. Start the platform

```bash
docker compose up -d
docker compose ps
```

Expected:

- `postgres` is `healthy`
- `tika` is `healthy`
- `cos` is `healthy`
- `worker` is `Up`

### 4. Optional: backfill pre-Epic-6 data

If this environment already contains older local-only data, run the canonical backfill once:

```bash
docker compose exec cos uv run cos migrate
```

Expected:

- a success message reports how many documents were backfilled vs already canonical

### 5. Verify health

```bash
docker compose logs cos --tail=30
docker compose logs worker --tail=30
docker compose exec cos uv run cos status
```

Expected:

- `cos` logs end with the normal startup sequence including migrations and MCP startup
- `worker` logs show `worker starting`
- `cos status` reports the platform as healthy

---

## Test Pack 1: Local File Ingest Still Works

This pack proves the Epic 6 provenance contract did not break local ingest.

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

This pack validates Gmail auth, sync, worker processing, and Gmail provenance rows.

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
- body jobs are enqueued
- attachment jobs are enqueued if you seeded supported attachments
- worker logs show queued ingest jobs being processed
- there is no long-lived build-up of `queued` or `running` jobs after the worker catches up
- `gmail_message_body` rows exist for the test emails
- `gmail_attachment` rows exist for supported attachments
- Gmail body aliases are slugged subjects ending in `.md`
- Gmail attachment aliases use the attachment filename
- Gmail locators begin with `gmail://message/`
- if you used the same attachment bytes in two emails, at least one query row shows `distinct_sources >= 2` and `distinct_documents = 1`

---

## Test Pack 3: Google Calendar OAuth, Sync, and Provenance

This pack validates Calendar auth, sync, and Calendar provenance rows.

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

This pack validates the base MCP note-ingest path.

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

This pack proves identical note ingest with the same stable identity becomes `unchanged`.

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

This pack proves one byte-identical artifact can survive as distinct `file`, `gmail_attachment`, and `mcp_note` provenance rows while collapsing to one canonical content record.

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

This pack validates warning-only near-duplicate detection.

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

This pack proves updated content for a stable `external_id` creates a new `document_version` while keeping history intact.

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

This pack validates grounded retrieval and citations across local, Gmail, Calendar, and MCP-ingested content.

### Pack-specific setup

Seed one record for each source type used in retrieval.

Create and ingest a local file:

```bash
mkdir -p data/uat-docs/retrieval
printf '%s' 'Epic 6 retrieval local note. Marker: epic-6-retrieval-local-a. Workforce segmentation framework lives here.' > data/uat-docs/retrieval/epic-6-retrieval-local.md
docker compose exec cos uv run cos ingest /data/uat-docs/retrieval/epic-6-retrieval-local.md
```

Seed one Gmail message:

1. Send yourself an email with:
   - subject: `Epic 6 Retrieval Gmail`
   - body text: `epic-6-retrieval-gmail-a`
   - label: `cos-uat`
2. Authenticate if needed:

```bash
uv run cos auth gmail
```

3. Sync Gmail:

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

---

## Test Pack 10: Restart and Token Persistence

This pack validates token persistence and deterministic post-restart sync behavior.

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

---

## Pass Criteria

Epic 6 UAT is a pass when all of the following are true:

### 1. Connected-source visibility

- local, Gmail, Calendar, and MCP-note records all appear in `cos docs` output
- all records expose `source_alias` and `source_locator`
- no `source_path` appears as a primary provenance field for connected sources

### 2. Cross-source exact-byte dedupe

- the cross-source dedupe pack shows the local file, Gmail attachment, and MCP note rows sharing one `sha256`
- those same rows share one `document_id`
- the final summary query shows `total_sources > total_blobs` when dedupe has occurred

### 3. Unchanged vs changed content

- the unchanged retry pack returns `data.outcome = unchanged` on the second identical ingest
- the changed-content pack returns `data.outcome = changed_content` when content changes under the same stable `external_id`
- version history shows at least 2 versions with distinct `file_hash` values

### 4. Restart and token persistence

- the platform recovers to healthy after restart
- `tokens/gmail.json` and `tokens/google_calendar.json` persist across restart
- post-restart Gmail and Calendar syncs complete without browser re-authorisation
- post-restart jobs drain back to no long-lived backlog

### 5. Retrieval remains grounded

- retrieval responses remain grounded after connected-source ingestion
- citations include `source_alias` and `source_locator`
- the cited sources correspond to the seeded local, Gmail, Calendar, or MCP records

---

## Cleanup

If this was a one-off UAT run against a personal Google account:

- remove or archive the `cos-uat` Gmail label and test emails
- delete the Calendar test events
- remove `tokens/gmail.json` and `tokens/google_calendar.json` if you do not want to keep the local auth state
- clear `data/` and restart containers if you want a clean local knowledge base afterwards
