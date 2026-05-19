# Manual Testing Guide

Reflects the platform through **Epic 7: Retrieval Trust, Evaluation & Observability**.

This guide now treats **Epic 7 retrieval-trust validation as the default UAT path**. If you only run one check before signing off a retrieval change, run [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite) on a clean benchmark database.

The connected-ingestion and operational packs are still active regression packs for the parts of the product that Test Pack 11 does not cover. Use them when your change touches live source onboarding, provenance, queueing, restart behavior, or MCP note flows.

Other than the shared bootstrap for config and platform startup, each pack is meant to stand on its own: you should be able to open the relevant pack, run its setup, and complete that validation without reading the whole file front to back.

---

## Current Product State

In plain English, the product today can:

- ingest local files, Gmail messages and attachments, Google Calendar events, and MCP-authored notes
- preserve where every piece of content came from, including version history and cross-source deduplication
- expose retrieval APIs that later user-facing workflows can use for grounded answers and citations
- apply score-threshold controls so unsupported questions can fall back to no-answer behavior
- measure retrieval quality with a committed benchmark corpus and a repeatable CLI gate

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

1. **Default UAT path for retrieval changes**  
   Start with [Test Pack 11](#test-pack-11-epic-7-retrieval-trust-regression-suite). This is the primary Epic 7 UAT path and the first check to run whenever retrieval behavior changes.

2. **Connected-source regression after ingestion or provenance changes**  
   Run the shared bootstrap, then only the supporting packs that match what changed:
   local ingest, Gmail, Calendar, MCP note ingest, dedupe, versioning, retrieval, or restart.

3. **Full operator confidence pass**  
   Run Test Pack 11 first, then add the supporting packs that represent the live user journeys you care about in this environment.

---

## Test Pack Index

| Pack | When to run | In plain English, what this is testing |
|---|---|---|
| **11** | Every release-gate pass | Can the assistant retrieve the right evidence, stay grounded to the right source, refuse unsupported answers, and stay fast enough? |
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

If you are running only the Epic 7 benchmark gate, you mainly need a valid bootable config plus a host-side config copy such as `config.host.yaml` for the benchmark command. You do not need Google OAuth or backfilled live data for that path.

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

The benchmark runs from the **host** against the Docker-backed database. The default `config.yaml` has `database.host: postgres` which only resolves inside the Docker network. Create a host-accessible config variant:

```bash
cp config.yaml config.host.yaml
```

Open `config.host.yaml` and change the database host:

```yaml
database:
  host: localhost  # was: postgres
```

`config.host.yaml` is gitignored and must not be committed — it contains your API credentials.

For the authoritative retrieval-trust gate, point `config.host.yaml` at a **clean benchmark database**. The simplest path is to run the benchmark before any other UAT/manual ingestion on a fresh stack, or to use a dedicated empty database prepared for benchmark validation. If the configured database already contains previously ingested non-fixture documents, the benchmark still runs, but the result is diagnostic only because ambient documents participate in retrieval.

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
  --include-fuzz
```

The fuzz layer adds five adversarial queries (noisy phrasing, cross-doc noise, near-synonym matching, empty-corpus no-answer). These are diagnostic only; a fuzz failure does not gate the release unless you explicitly decide to hold on them.

### Trust guarantee checks

Inspect the saved JSON report after the gold run completes.

#### Single-lineage direct facts — gold-df-001 and fuzz-df-002

Direct-fact and equivalent queries must resolve to exactly one supporting source. Multi-source answers for a direct-fact query mean lineage narrowing failed.

```bash
python3 -c "
import json
with open('_bmad-output/implementation-artifacts/7-5-benchmark-report.json') as f:
    r = json.load(f)
for q in r['per_query']:
    if q['query_id'] in ('gold-df-001', 'fuzz-df-002'):
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

## Pass Criteria

Start with Epic 7 for retrieval changes. Add the connected-source criteria whenever you changed ingestion, provenance, queueing, auth, MCP note handling, or restart behaviour.

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
