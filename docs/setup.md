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

All three services (postgres, tika, cos) will start and reach a healthy state within 60 seconds.

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

This section is only needed if you are enabling the Gmail or Google Calendar connectors (Epic 6). For a local-only Epic 1–5 deployment, skip this section entirely.

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
| `SOURCE PATH` | The in-container path where the file was ingested from |
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

Returns a JSON array. Each object has: `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`.

> **Note:** The `source_path` stored in the database is the **in-container** absolute path. When using `docker compose run --rm --entrypoint /app/.venv/bin/cos -v "$(pwd)/test-docs:/test-docs" cos ...`, the stored path will be `/test-docs/report.pdf` (the container path), not the host path. This is expected behaviour.

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
| `source_path` | In-container path of the document the answer draws from |
| `chunk_index` | Which chunk within that document was used |
| `score` | Relevance score — higher is a closer match |

The `source_path` values match what `cos docs` shows in the `SOURCE PATH` column.

If no relevant content exists in the knowledge base, the answer says `No relevant content found in the knowledge base.` This is not an error. In that case, both `data.citations` and top-level `citations` are empty lists.

### Browse the knowledge base

To see all ingested documents, type this prompt into your Claude session:

```text
Call list_documents and show me the raw JSON response.
```

This returns a standard JSON envelope. The document rows live in `data.documents` and match the output of `cos docs --json`. Each document includes `id`, `source_path`, `ingested_at`, `current_version`, and `chunk_count`.

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
