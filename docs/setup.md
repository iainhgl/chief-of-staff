# CoS Platform — Setup, Operations, and Querying Guide

## Prerequisites

- Docker Desktop (includes Docker Compose)
- [uv](https://docs.astral.sh/uv/) package manager

## Clone the Repository

```bash
git clone <repository-url>
cd cos
```

## First-time Configuration

Before starting the platform, create your local config file:

```bash
cp config.yaml.example config.yaml
```

Then open `config.yaml` and fill in the required values — at minimum:
- `llm.api_key` — your Anthropic API key
- `database.password` — must match the `POSTGRES_PASSWORD` value in `docker-compose.yml` (default: `postgres`)

`config.yaml` is git-ignored and never committed. `config.yaml.example` is the safe template that stays in the repo.

### Corporate Proxy / TLS Intercept Networks

If document ingest fails at the embedding step with an error like `Cannot connect to host api.voyageai.com:443 ssl:default`, the Voyage SDK needs explicit network settings. It uses `aiohttp`, so common fixes aimed at `requests` do not apply here.

The standard project setup is:

1. Place your corporate root certificate PEM in `./local/certs/`
2. Point `embedding.ca_bundle_path` in `config.yaml` at `/certs/<filename>.pem`

`docker-compose.yml` already mounts `./local/certs` into the container as `/certs`, so you should not need to edit the Compose file per laptop.

Set one or more of these under `embedding:` in `config.yaml`:

- `ca_bundle_path` — path to a PEM file containing your corporate root certificate (for example a Zscaler root CA)
- `proxy_url` — explicit proxy URL if your network requires outbound HTTPS through a proxy
- `trust_env: true` — tells the Voyage client to honor `HTTPS_PROXY`, `HTTP_PROXY`, and `NO_PROXY`

The same three settings are also available under `llm:` if the Anthropic call path needs different values. If the `llm` transport fields are left unset, the platform falls back to the `embedding` transport settings.

Example:

```yaml
embedding:
  provider: anthropic
  model: voyage-3
  api_key: null
  ca_bundle_path: /certs/zscaler-root.pem
  proxy_url: null
  trust_env: true
```

Example host file layout:

```text
cos/
├── config.yaml
└── local/
    └── certs/
        └── zscaler-root.pem
```

After adding or changing files in `./local/certs`, recreate the `cos` container:

```bash
docker compose up -d --build --force-recreate cos
```

## Start the Platform

```bash
docker compose up -d
```

All four services (postgres, tika, cos, worker) will start. The postgres, tika, and cos containers reach a healthy state within 60 seconds; the worker container starts alongside them and begins draining any queued ingest jobs.

## Configure the MCP Server

Connect Claude to the CoS MCP server so it can call the platform's tools.

### Claude Code (CLI)

Run from the `cos/` directory:

```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

### Claude Desktop

Add the following to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cos": {
      "command": "docker",
      "args": ["compose", "exec", "-i", "cos", "uv", "run", "cos-mcp"],
      "cwd": "/absolute/path/to/cos"
    }
  }
}
```

Replace `/absolute/path/to/cos` with the full path to your `cos/` directory.

The `cos` container runs `cos-mcp` as its persistent process. The MCP client starts a second `cos-mcp` instance inside the same container via `docker compose exec -i` (stdio transport). Both instances share Postgres and config — this is safe and expected.

## Configure the Role Pack

The platform ships with two example role packs: `role_packs/chro.yaml` (CHRO) and `role_packs/enterprise_architect.yaml` (Enterprise Architect). The active role pack is set in `config.yaml`:

```yaml
role_pack:
  path: role_packs/chro.yaml
```

To use a different role or author your own, see [role-packs.md](role-packs.md) for the full authoring guide and field reference.

## Google OAuth Setup (Gmail and Calendar Connectors)

This section is only needed if you are enabling the Gmail or Google Calendar connectors. For a local-only deployment that uses only `cos ingest` and local files, skip this section entirely.

### 1. Create OAuth credentials in Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Set **Application type** to **Desktop app**
4. Copy the **Client ID** and **Client Secret**

### 2. Add credentials to config.yaml

```yaml
google_oauth:
  client_id: YOUR_CLIENT_ID.apps.googleusercontent.com
  client_secret: YOUR_CLIENT_SECRET
```

The `client_secret` is masked in all logs and repr() output. The `google_oauth` block is optional — existing configs without it continue to work.

Also enable whichever connectors you plan to use in the `connectors:` list:

```yaml
connectors:
  - gmail
  - google_calendar
```

Connector-specific settings (`gmail:`, `google_calendar:`) can be added as well; omitting them leaves all defaults in place. See `config.yaml.example` for the full set of options.

### 3. Authenticate on the host (first time)

Run the following commands from the `cos/` directory on the **host** (not inside the container), so the browser can open on your machine:

```bash
uv run cos auth gmail
uv run cos auth calendar
```

Each command opens a browser tab for Google's consent screen. After you grant access:

- `tokens/gmail.json` is written for Gmail
- `tokens/google_calendar.json` is written for Google Calendar

A plain-language confirmation is printed naming the connector and the token file:

```text
Authenticated gmail successfully.
Token saved to tokens/gmail.json
```

### 4. Token storage and refresh

- Token files live in `tokens/` which is **gitignored** — they are never committed
- The `docker-compose.yml` mounts `./tokens` into the container as `/app/tokens` so connector-side token refresh survives container rebuilds
- Tokens refresh automatically in the background when they expire — no manual re-consent is needed as long as the refresh token is valid

### 5. Recovery: token missing or revoked

If a connector cannot authenticate, the platform logs a structured error and leaves the MCP retrieval path available. To recover, re-run the auth command for the affected connector:

```bash
uv run cos auth gmail       # re-authorise Gmail
uv run cos auth calendar    # re-authorise Google Calendar
```

## Sync Connected Sources

This section applies only when the Gmail and/or Google Calendar connectors are enabled. Skip it for local-only deployments.

After completing the OAuth steps above, run the relevant sync commands inside the `cos` container. These commands poll the connector for new content and enqueue ingest jobs for the background `worker` service to process.

### Sync Gmail

```bash
docker compose exec cos uv run cos sync gmail
```

Expected output on a first run:

```text
Gmail sync complete:
  14 messages scanned
  12 body jobs enqueued
  3 attachment jobs enqueued
  0 artifacts already processed (skipped)
  0 artifacts already queued (skipped)
  1 unsupported attachments skipped
```

On repeated runs after the worker has processed the initial jobs, already-processed artifacts are skipped automatically:

```text
Gmail sync complete:
  14 messages scanned
  0 body jobs enqueued
  0 attachment jobs enqueued
  15 artifacts already processed (skipped)
  0 artifacts already queued (skipped)
  1 unsupported attachments skipped
```

To intentionally reprocess all matching Gmail content for the current run (for example after correcting an ingestion configuration), use the `--force` flag:

```bash
docker compose exec cos uv run cos sync gmail --force
```

`--force` applies only to that single invocation. It bypasses skip checks so that all matching artifacts are re-staged and re-enqueued, regardless of prior ingestion status. The canonical pipeline will still deduplicate unchanged content through the normal ingest outcomes.

### Sync Google Calendar

```bash
docker compose exec cos uv run cos sync calendar
```

Expected output:

```text
Calendar sync complete:
  1 calendars scanned
  8 events discovered
  8 jobs enqueued
```

### How the Worker Processes Jobs

Gmail and Calendar sync commands enqueue background ingest jobs. The `worker` service (a separate container) drains those jobs asynchronously. To confirm jobs are being processed:

```bash
docker compose logs worker --tail=50
```

Worker logs show each job being picked up and completed. After the worker catches up, all queued content will be searchable through `retrieve` and visible in `cos docs`.

### Degraded Mode

If a connector fails before jobs are enqueued (for example, a revoked OAuth token, an expired credential, or a Google API outage), the failure appears in the `cos sync gmail` or `cos sync calendar` command output and in the `cos` service logs:

```bash
docker compose logs cos --tail=100
```

If the sync command succeeds but a staged ingest job later fails, the `worker` logs the error while processing that queued job:

```bash
docker compose logs worker --tail=100
```

In both cases, the MCP server and retrieval path remain available. Recover by re-running the auth command for the affected connector if needed (see the token recovery step in the Google OAuth section above), then re-run the sync command.

### Connector Provenance Examples

After sync, `cos docs --json` shows ingested connector content alongside local files. Example provenance for each source type:

| Source Type | `source_alias` example | `source_locator` example |
|---|---|---|
| Local file | `strategy.pdf` | `/data/uat-docs/local/strategy.pdf` |
| Gmail message body | `Epic_6_UAT_Gmail_Body_A.md` | `gmail://message/msg-001/body` |
| Gmail attachment | `report.pdf` | `gmail://message/msg-010/attachment/att-id-001` |
| Calendar event | `Q3_Planning_Review_primary_evt123.md` | `google-calendar://calendar/primary/event/evt123` |
| MCP note | `Board-Prep-Q3.md` | `mcp_note://claude-code/board-prep-q3-2026` |

## Ingest Documents

Load documents into the knowledge base using the `cos ingest` command, run inside the `cos` container.

### Ingest a single file

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos ingest /path/to/document.pdf
```

Supported formats: `.pdf`, `.docx`, `.md`, `.txt`

On success the command prints a plain-language summary:

```text
Ingested strategy.pdf -> 24 chunks indexed
```

### Ingest a folder

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos ingest /path/to/docs/
```

All supported files are ingested **recursively** — subdirectories are walked automatically. Each file reports its own progress line and a final summary is printed:

```text
Ingested overview.md -> 3 chunks indexed
Ingested reports/q3.pdf -> 18 chunks indexed
Skipped spreadsheet.xlsx — unsupported format
Ingested 2 files -> 21 total chunks indexed
```

Unsupported file types are skipped with a notice and do not cause the command to fail.

### If a file fails

A plain-language error is shown for the failed file. In folder mode, ingestion continues for the remaining files. The error message identifies the file and the reason — no stack trace is shown.

### Ingest Outcomes

Every ingest operation — whether through `cos ingest`, `cos sync`, or the `ingest_document` MCP tool — resolves to one of four deterministic outcomes:

| Outcome | Meaning |
|---------|---------|
| `new_content` | New bytes, new source — content indexed for the first time |
| `unchanged` | Same bytes, same source — no-op; nothing written |
| `changed_content` | Same source, different bytes — new document version created; prior versions kept |
| `new_source_known_content` | New source, identical bytes to existing content — provenance recorded; content not reprocessed |

The `new_source_known_content` outcome is how exact-byte deduplication works across sources: a Gmail attachment and a local file with identical bytes are each recorded as distinct provenance entries while sharing one canonical content record and embedding set.

## Verify Ingestion

After ingesting documents, confirm they are indexed using the `cos docs` command.

### List all ingested documents

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs
```

Prints a table with one row per document:

| Column | Description |
|--------|-------------|
| `ID` | UUID for the document — use this with `--versions` |
| `SOURCE ALIAS` | Human-readable source label: filename for local files, slugged subject for Gmail bodies, attachment filename for Gmail attachments, slugged event title plus calendar and event ID for Calendar, and usually the note title slug for MCP notes |
| `INGESTED AT` | ISO 8601 timestamp of the most recent ingest |
| `VER` | Current version number (1 on first ingest; increments on re-ingest) |
| `CHUNKS` | Number of text chunks indexed for this document |

If no documents have been ingested yet: `No documents ingested yet. Run: cos ingest <path>`

### View version history for a document

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --versions <document-id>
```

Copy the document ID from the `ID` column in the `cos docs` table output. Each row shows the version number, ingest timestamp, and file hash.

### Machine-readable JSON output

```bash
docker compose run --rm --entrypoint /app/.venv/bin/cos cos docs --json
```

Returns a JSON array. Each object has: `id`, `source_alias`, `source_locator`, `ingested_at`, `current_version`, `chunk_count`.

| Field | Description |
|-------|-------------|
| `id` | Document UUID |
| `source_alias` | Human-readable source label |
| `source_locator` | Unique source URI — for local files, this is the in-container path; for Gmail and Calendar, it is a connector-specific URI; for MCP notes, it begins with `mcp_note://` |
| `ingested_at` | ISO 8601 timestamp |
| `current_version` | Current document version number |
| `chunk_count` | Number of indexed text chunks |

## Query the Knowledge Base

Once documents are ingested, ask questions using the `retrieve` tool from any connected MCP client (Claude Code or Claude Desktop).

### Ask a question

Open a Claude session and ask any question about your documents:

```text
What frameworks do I have for workforce segmentation?
```

Claude calls `retrieve`, searches the knowledge base using hybrid keyword and semantic search, synthesises a grounded answer, and returns a JSON envelope with:

- `status: "ok"`
- `data.answer` containing the answer text
- `data.citations` and top-level `citations`, each listing the sources used

### Understanding citations

Every successful `retrieve` response includes a `citations` field. When relevant content is found, each citation has:

| Field | Description |
|-------|-------------|
| `source_alias` | Human-readable source label — matches the `SOURCE ALIAS` column in `cos docs` |
| `source_locator` | Unique source URI — matches the `source_locator` field in `cos docs --json` |
| `document_version_id` | The specific document version the cited chunk came from |
| `chunk_index` | Which chunk within that document was used |
| `score` | Relevance score — higher is a closer match |

If no relevant content exists in the knowledge base, the answer says `No relevant content found in the knowledge base.` This is not an error. In that case, both `data.citations` and top-level `citations` are empty lists.

### Browse the knowledge base

To see all ingested documents, type this prompt into your Claude session:

```text
Call list_documents and show me the raw JSON response.
```

This returns a standard JSON envelope. The document rows live in `data.documents` and match the output of `cos docs --json`. Each document includes `id`, `source_alias`, `source_locator`, `ingested_at`, `current_version`, and `chunk_count`.

### Capture Notes via MCP

Use the `ingest_document` MCP tool to capture notes or short documents directly from a Claude session without staging files on disk:

```text
Call ingest_document with:
- content: "Quarterly board prep note: key themes are workforce planning and succession."
- metadata:
  - title: "Board Prep Q3"
  - external_id: "board-prep-q3-2026"
  - client: "claude-code"
Show me the raw JSON response.
```

The response includes `data.outcome` (one of the four ingest outcomes), `data.source_alias`, and `data.source_locator` (which begins with `mcp_note://`). If the same `external_id` is submitted again with updated content, the outcome is `changed_content` and a new document version is created while prior versions are preserved. If the content is byte-identical, the outcome is `unchanged`.

A `data.warning` field may appear if the submitted content is semantically similar to an already-indexed document (controlled by `mcp_note.near_duplicate_threshold` in `config.yaml`). The ingest still succeeds — the warning is informational.

## Platform Operations

### Check Platform Status

Run from the `cos/` directory on the **host** (not inside the container):

```bash
docker compose exec cos uv run cos status
```

Expected output when the platform is fully healthy:

```text
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (42 documents indexed)
```

Each row shows a component name, a `✓` (healthy) or `✗` (problem) icon, a plain-language message, and — if something is wrong — an exact recovery instruction. No technical jargon appears in the output.

**Exit code:** 0 when all components are healthy; 1 if any component is unhealthy.

### Restart the Platform

Run from the `cos/` directory on the **host** (not inside the container):

```bash
uv run cos restart
```

The command restarts all services and polls until every container is healthy. Expected output:

```text
Restarting platform...
Platform restarted. All components healthy.
```

**Timing note:** `cos restart` calls `docker compose restart`, then polls for up to 30 seconds. Total wall time to the confirmation message is typically 35–45 seconds on a standard machine.

**If a container stays stuck**, the output names it and suggests the next step:

```text
Tika did not become healthy. Run: cos logs tika
```

Exit code 0 on success, 1 on failure.

### View Logs

Run from the `cos/` directory on the **host** (not inside the container):

```bash
uv run cos logs                # last 100 lines from all containers
uv run cos logs cos            # filter to the cos service only
uv run cos logs --since 10m    # last 10 minutes from all containers
uv run cos logs cos --since 5m # cos service, last 5 minutes
```

Valid component names: `postgres`, `tika`, `cos`. The `--since` value is passed directly to `docker compose logs` and follows Docker's duration format (e.g. `10m`, `1h`, `30s`); invalid values produce a Docker error message.

Log output is a mix of Docker timestamps and structured JSON lines from the cos service. No API keys or credential values appear in any log line.

If no containers are running, the command prints a plain-language message rather than a Docker error:

```text
No containers running. Start the platform first: docker compose up -d
```

**Exit code:** 0 when containers are running; 1 if no containers are running.

### Recovery: Postgres not running

The most common failure is Postgres stopping unexpectedly. The three-step recovery procedure:

**Step 1 — check what is wrong:**

```bash
docker compose exec cos uv run cos status
```

When Postgres is down, both the `Postgres` and `Database` rows fail with a recovery hint:

```text
CoS Platform Status
-------------------
Postgres        ✗ container not running — Run: cos restart
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✗ could not connect — Run: cos restart
```

> **If `docker compose exec` fails** with "container not running", the `cos` container has also stopped — skip directly to Step 2.

**Step 2 — restart the platform:**

```bash
uv run cos restart
```

Wait for the confirmation: `Platform restarted. All components healthy.`

**Step 3 — confirm recovery:**

```bash
docker compose exec cos uv run cos status
```

All five rows should show `✓` icons. The platform is ready to accept queries again.

---

### Sending logs for support

If you need to share diagnostic information, capture the last 10 minutes of logs from all containers:

```bash
uv run cos logs --since 10m
```

Paste the output into your support message. The output contains no API keys or credential values — it is safe to share.
