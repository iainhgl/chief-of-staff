# CoS Platform Setup

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

## Start the Platform

```bash
docker compose up -d
```

All three services (postgres, tika, cos) will start and reach a healthy state within 60 seconds.

## Check Platform Status

```bash
docker compose ps
```

Shows all three services and their health state. All should show `healthy` or `running`.

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

## Restart the Platform

Three-step restart procedure:

```bash
# Step 1 — stop all services
docker compose down

# Step 2 — start again
docker compose up -d

# Step 3 — verify all services are healthy
docker compose ps
```

No manual intervention is needed between steps.

## Ingest Documents

Load documents into the knowledge base using the `cos ingest` command, run inside the `cos` container.

### Ingest a single file

```bash
docker compose run --rm --entrypoint uv cos run cos ingest /path/to/document.pdf
```

Supported formats: `.pdf`, `.docx`, `.md`, `.txt`

On success the command prints a plain-language summary:

```text
Ingested strategy.pdf -> 24 chunks indexed
```

### Ingest a folder

```bash
docker compose run --rm --entrypoint uv cos run cos ingest /path/to/docs/
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
docker compose run --rm --entrypoint uv cos run cos docs
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
docker compose run --rm --entrypoint uv cos run cos docs --versions <document-id>
```

Copy the document ID from the `ID` column in the `cos docs` table output. Each row shows the version number, ingest timestamp, and file hash.

### Machine-readable JSON output

```bash
docker compose run --rm --entrypoint uv cos run cos docs --json
```

Returns a JSON array. Each object has: `id`, `source_path`, `ingested_at`, `current_version`, `chunk_count`.

> **Note:** The `source_path` stored in the database is the **in-container** absolute path. When using `docker compose run --rm --entrypoint uv -v "$(pwd)/test-docs:/test-docs" cos ...`, the stored path will be `/test-docs/report.pdf` (the container path), not the host path. This is expected behaviour.

## View Logs

```bash
docker compose logs cos
```

Streams structured JSON logs from the cos service. To follow logs in real time:

```bash
docker compose logs -f cos
```
