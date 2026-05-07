# Manual Testing Guide

Reflects the platform at the end of **Epic 6: Canonical Source Identity & Connected Ingestion**.

This guide is the current hands-on operator/UAT script for the product as it exists now. It replaces the old Epic 5 checks rather than accumulating every historical test.

---

## Epic 6 Summary

Epic 6 turns the platform from a local-document knowledge base into a connected-ingestion system with a durable provenance model:

- canonical identity is now based on content blobs, not raw file paths
- exact-byte deduplication works across local files, Gmail, Google Calendar, and MCP note ingest
- provenance is preserved as `source_type`, `source_alias`, and `source_locator`
- Gmail sync stages message bodies and supported attachments, then enqueues background ingest jobs
- Google Calendar sync stages event Markdown and enqueues background ingest jobs
- a dedicated `worker` service drains the ingest queue in the background
- the MCP server exposes `ingest_document` for direct note capture with stable external IDs and warning-only near-duplicate detection
- old pre-Epic-6 data can be backfilled onto the canonical model with `cos migrate`

---

## Scope Of This UAT Pass

This runbook verifies the full Epic 6 surface end to end:

- baseline local document ingest still works
- Gmail OAuth and Gmail sync work with a real Google account
- Google Calendar OAuth and Calendar sync work with a real Google account
- queued jobs are processed by the worker
- `cos docs` and MCP tool responses expose `source_alias` / `source_locator`
- canonical dedupe works across repeated and cross-source ingest
- live MCP note capture works from a real client session
- grounded retrieval still works after connected data lands

---

## Prerequisites

- Docker Desktop or Rancher Desktop running
- `uv` installed
- working directory is the repo root: `cos/`
- live Anthropic/Voyage credentials in `config.yaml`
- a real Google account you can safely use for Gmail and Calendar UAT
- Claude Code or Claude Desktop available for the live MCP tests

Important runtime rule:

- use `uv run cos auth ...` on the **host**
- use `docker compose exec cos uv run cos ...` for commands that need the app's Docker network and `database.host: postgres`

---

## Before You Start

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

In the Google Cloud project behind your OAuth desktop client:

- enable **Gmail API**
- enable **Google Calendar API**

### 3. Seed Real Google Test Data

Use the same Google account you will authorise later.

In Gmail:

1. Create a label named `cos-uat`
2. Send yourself an email with:
   - subject: `Epic 6 UAT Gmail Body A`
   - body text containing a unique phrase such as `epic-6-uat-gmail-body-a`
   - the `cos-uat` label applied
3. Send yourself a second email with:
   - subject: `Epic 6 UAT Gmail Body B`
   - body text containing `epic-6-uat-gmail-body-b`
   - the same attachment bytes as the first email if you want to prove cross-source exact-byte dedupe for attachments
   - the `cos-uat` label applied
4. Optional: include one unsupported attachment type to confirm it is skipped cleanly

In Google Calendar:

1. Create an event on your primary calendar within the next 14 days
2. Use a distinctive title such as `Epic 6 UAT Calendar Event`
3. Put a unique marker in the description, for example `epic-6-uat-calendar-description`

For MCP note capture:

- prepare one short note you will ingest via `ingest_document`
- prepare a second very similar version of that note for the near-duplicate warning test

---

## 1. Start The Platform

```bash
docker compose up -d
docker compose ps
```

Expected:

- `postgres` is `healthy`
- `tika` is `healthy`
- `cos` is `healthy`
- `worker` is `Up`

If this environment contains pre-Epic-6 data, run the canonical backfill once:

```bash
docker compose exec cos uv run cos migrate
```

Expected:

- a success message reporting how many documents were backfilled vs already canonical

---

## 2. Verify Startup And Worker Health

```bash
docker compose logs cos --tail=30
docker compose logs worker --tail=30
docker compose exec cos uv run cos status
```

Expected:

- `cos` logs end with the normal startup sequence including `migrations applied`, `Role pack loaded`, and `MCP server: listening`
- `worker` logs show `worker starting`
- `cos status` reports the platform as healthy

---

## 3. Run Google OAuth On The Host

Run these on the host so the browser can open locally:

```bash
uv run cos auth gmail
uv run cos auth calendar
```

Expected:

- the browser consent flow opens for each connector
- both commands finish successfully
- these files exist afterwards:

```text
tokens/gmail.json
tokens/google_calendar.json
```

If the token files do not appear, stop here and fix auth before continuing.

---

## 4. Baseline Local Ingest Still Works

Use the bundled test docs if present:

```bash
docker compose exec cos uv run cos ingest /app/test-docs
docker compose exec cos uv run cos docs --json
```

Expected:

- supported local files ingest successfully
- `cos docs --json` returns objects with:
  - `id`
  - `source_alias`
  - `source_locator`
  - `ingested_at`
  - `current_version`
  - `chunk_count`
- no `source_path` field appears in the JSON output

This confirms the Epic 6 provenance contract did not break local ingest.

---

## 5. Gmail End-To-End Sync

Run the Gmail sync inside the app container:

```bash
docker compose exec cos uv run cos sync gmail
```

Expected:

- the command prints a completion summary
- at least one message is scanned
- body jobs are enqueued
- attachment jobs are enqueued if you seeded supported attachments

Now confirm the worker drains those jobs:

```bash
docker compose logs worker --tail=100
docker compose exec postgres psql -U postgres -d cos -c "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY status;"
```

Expected:

- worker logs show queued ingest jobs being processed
- after the worker catches up, there should be no long-lived build-up of `queued` or `running` ingest jobs

Now inspect provenance rows:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT s.source_type, s.source_alias, s.source_locator
FROM sources s
WHERE s.source_type IN ('gmail_message_body', 'gmail_attachment')
ORDER BY s.created_at DESC;
"
```

Expected:

- `gmail_message_body` rows exist for the test emails
- `gmail_attachment` rows exist for supported attachments
- locators look like Gmail URIs, not file-system paths

If you seeded two different emails with the same attachment bytes, verify canonical dedupe:

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

Expected for the shared-attachment case:

- one row where `distinct_sources` is at least `2`
- that same row has `distinct_documents = 1`

That proves two separate Gmail sources were preserved while the canonical document/blob was deduplicated.

---

## 6. Google Calendar End-To-End Sync

Run the Calendar sync inside the app container:

```bash
docker compose exec cos uv run cos sync calendar
```

Expected:

- the command prints how many calendars were scanned
- at least one event is discovered if you seeded one inside the configured time window
- jobs are enqueued for discovered events

Check resulting provenance:

```bash
docker compose exec postgres psql -U postgres -d cos -c "
SELECT s.source_type, s.source_alias, s.source_locator
FROM sources s
WHERE s.source_type = 'google_calendar_event'
ORDER BY s.created_at DESC;
"
```

Expected:

- at least one `google_calendar_event` row exists
- the alias reflects the event title in slugged form
- the locator begins with `google-calendar://`

Also verify the new content is visible through the CLI:

```bash
docker compose exec cos uv run cos docs --json
```

Expected:

- calendar-derived documents appear alongside local and Gmail-derived content

---

## 7. Live MCP Note Capture (`ingest_document`)

Configure the MCP server in Claude Code if needed:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

Open a fresh Claude Code or Claude Desktop session and run these prompts.

### 7.1 First note ingest

Ask the client:

```text
Call ingest_document with:
- content: "Epic 6 UAT note. This note tracks workforce planning for the quarterly board review. Marker: epic-6-uat-note-a."
- metadata:
  - title: "Epic 6 UAT Note"
  - external_id: "epic-6-uat-note-001"
  - client: "claude-code"
Show me the raw JSON response.
```

Expected:

- `status` is `ok`
- `data.outcome` is usually `new_content`
- `data.source_alias` is present
- `data.source_locator` starts with `mcp_note://`
- `citations` is an empty list

### 7.2 Retry/idempotency check

Ask the client:

```text
Call ingest_document again with the exact same content and identical metadata. Show me the raw JSON response.
```

Expected:

- `status` is `ok`
- `data.outcome` is `unchanged`

### 7.3 New source, same bytes

Ask the client:

```text
Call ingest_document with the same content but metadata.external_id = "epic-6-uat-note-002". Show me the raw JSON response.
```

Expected:

- `status` is `ok`
- `data.outcome` is `new_source_known_content`
- the message explains the content was linked rather than reprocessed

### 7.4 Near-duplicate warning

Ask the client:

```text
Call ingest_document with:
- content: "Epic 6 UAT note. This note tracks workforce planning for the upcoming board review and executive prep. Marker: epic-6-uat-note-b."
- metadata:
  - title: "Epic 6 UAT Similar Note"
  - external_id: "epic-6-uat-note-003"
  - client: "claude-code"
Show me the raw JSON response.
```

Expected:

- `status` is `ok`
- ingest still succeeds
- `data.warning` may be present if the similarity threshold is met

If no warning appears and you want to force this part of the UAT:

- lower `mcp_note.near_duplicate_threshold` in `config.yaml`
- restart the platform
- rerun only this note-ingest step

---

## 8. Retrieval UAT Across Mixed Sources

In the same MCP client session, ask source-specific questions that should hit the seeded data.

Suggested prompts:

```text
Use retrieve to answer: what did the Epic 6 UAT Gmail Body A message say?
```

```text
Use retrieve to answer: what is the Epic 6 UAT Calendar Event about?
```

```text
Use retrieve to answer: what does the Epic 6 UAT note say about workforce planning?
```

Expected:

- each response comes back through the standard MCP envelope
- answers are grounded rather than fabricated
- citations include `source_alias` and `source_locator`
- the cited aliases/locators correspond to the Gmail message body, Calendar event, or MCP note you seeded

---

## 9. Final Operator Spot Checks

Run these from the host or container as shown:

```bash
docker compose exec cos uv run cos docs
docker compose exec cos uv run cos docs --json
docker compose exec postgres psql -U postgres -d cos -c "SELECT source_type, COUNT(*) FROM sources GROUP BY source_type ORDER BY source_type;"
docker compose exec postgres psql -U postgres -d cos -c "SELECT COUNT(*) AS blobs FROM content_blobs;"
docker compose exec postgres psql -U postgres -d cos -c "SELECT COUNT(*) AS source_versions FROM source_versions;"
```

Expected:

- `cos docs` lists a mixture of local, Gmail, Calendar, and MCP-ingested records
- `sources` contains rows for at least:
  - `file`
  - `gmail_message_body`
  - `gmail_attachment` if attachments were seeded
  - `google_calendar_event`
  - `mcp_note`
- `content_blobs` count is less than or equal to the total number of sources when dedupe has occurred

---

## 10. Pass Criteria

Epic 6 UAT is a pass when all of the following are true:

- local ingest still works
- Google OAuth succeeds and token files are created
- Gmail sync enqueues and the worker processes Gmail jobs
- Calendar sync enqueues and the worker processes Calendar jobs
- `cos docs` exposes `source_alias` / `source_locator`
- Gmail shared attachments deduplicate to one canonical document/blob while preserving multiple source rows
- MCP `ingest_document` supports:
  - first ingest
  - unchanged retry
  - new source known content
  - optional warning-bearing near-duplicate success
- retrieval remains grounded with citations after connected data is indexed

---

## Cleanup

If this was a one-off UAT run against a personal Google account:

- remove or archive the `cos-uat` Gmail label and test emails
- delete the Calendar test event
- remove `tokens/gmail.json` and `tokens/google_calendar.json` if you do not want to keep the local auth state
- clear `data/` and restart containers if you want a clean local knowledge base afterwards

