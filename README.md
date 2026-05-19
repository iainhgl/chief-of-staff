# Chief of Staff

A personal AI platform that acts as a Chief of Staff for a specific role — retaining knowledge in a structured store and reasoning over it to answer questions grounded in source material.

## Current Capabilities (Epic 7)

What is working today:

- **Four-service platform** (postgres/pgvector, Tika, cos, worker) that starts with `docker compose up -d`
- **Config validation at startup** — human-readable errors for missing or invalid config values
- **Database schema applied automatically** — idempotent migrations run on every startup
- **MCP server** accessible via `docker compose exec` stdio transport (Claude Code and Claude Desktop)
- **`cos ingest <path>`** — ingest a single file or folder of documents (PDF, .docx, .md, .txt); per-file progress and final summary printed; resolves to one of four deterministic outcomes (`new_content`, `unchanged`, `changed_content`, `new_source_known_content`)
- **`cos docs`** — list all ingested documents with provenance metadata (source alias, source locator, ingested timestamp, version, chunk count); shows content from all source types (local files, Gmail, Calendar, MCP notes)
- **`cos docs --versions <id>`** — show version history for a specific document
- **`cos docs --json`** — machine-readable JSON; each object includes `id`, `source_alias`, `source_locator`, `ingested_at`, `current_version`, `chunk_count`
- **Originals preserved** — every ingested file is stored byte-for-byte in `/data/originals/` (in-container path); Markdown working copies in `/data/markdown/`
- **`cos auth gmail`** / **`cos auth calendar`** — OAuth browser consent flow; run from the **host** so the browser can open; writes token files to `tokens/`
- **`cos sync gmail`** / **`cos sync calendar`** — poll the connected source for new content and enqueue background ingest jobs; run inside the `cos` container
- **`cos migrate`** — backfill legacy Phase 1 path-centric documents onto the canonical identity model; safe to rerun; idempotent
- **`cos benchmark`** — run the retrieval evaluation harness against the committed gold corpus; seeds fixture documents, runs all gold queries, cleans up, then prints a per-class summary and, when `--output` is supplied, writes a JSON report; run from the **host** with a host-accessible config (`--config config.host.yaml`); gold-only runs on a **clean benchmark database** are the authoritative release gate; add `--include-fuzz` for optional adversarial diagnostic coverage; see [docs/manual-testing.md](docs/manual-testing.md) for the full regression runbook
- **Background `worker` service** — drains the ingest job queue; connector failures are fault-isolated and do not affect the MCP server or retrieval path
- **Exact-byte deduplication** — a file, Gmail attachment, Calendar event, and MCP note with identical bytes share one canonical content record; each is preserved as a distinct provenance entry
- **`retrieve`** — ask questions about ingested documents; returns a synthesised answer grounded in source material with citations in both `data.citations` and top-level `citations` (`source_alias`, `source_locator`, `document_version_id`, `chunk_index`, `score` per citation); handles the no-content case without fabrication
- **`list_documents`** — returns a JSON envelope with `data.documents`; each document includes `id`, `source_alias`, `source_locator`, `ingested_at`, `current_version`, `chunk_count`; matches `cos docs --json`
- **`ingest_document`** — MCP tool for direct note capture from a Claude session; accepts `content` and optional `metadata` (including a stable `external_id`); returns `outcome`, `source_alias`, `source_locator`; emits a near-duplicate warning if enabled
- **`get_role_context`** — returns the active role summary from the loaded role pack; `data.role_name` is the role's display name and the response also includes `goals`, `tone`, `knowledge_taxonomy`, and `active_workflows`
- **`get_status`** — returns a JSON envelope with health of all six components (cos, postgres, tika, MCP server, role pack, database) and a `ready` flag
- **`cos status`** — plain-language health table for all five components; identifies exactly which component failed and states the recovery action; exit code 1 when any component is unhealthy; run from the host: `docker compose exec cos uv run cos status`
- **`cos restart`** — single command that restarts all services and polls until every container is healthy; prints confirmation or names the stuck component; run from the host: `uv run cos restart`
- **`cos logs`** — single command log export; supports optional component filter and `--since <duration>` for time filtering; run from the host: `uv run cos logs`

Knowledge retrieval and Q&A with citations are working. Role identity is configuration-only — author a YAML file and point `config.yaml` at it; no code changes are required. See [docs/role-packs.md](docs/role-packs.md) for the authoring guide. The platform can be monitored, restarted, and diagnosed using plain-language CLI commands — see [docs/setup.md](docs/setup.md) for the operations reference. Retrieval quality is validated via a committed benchmark corpus and the `cos benchmark` command; see [docs/manual-testing.md](docs/manual-testing.md) for the regression runbook.

## How it Works

The platform has two parts: a **generic core** that handles ingestion, storage, retrieval, and reasoning; and a **role pack** — a configuration file that defines the specific role, its goals, stakeholders, and working style. Swapping the role pack changes who the platform serves without touching the core.

The model layer is kept behind an interface so the underlying LLM can be changed without affecting the rest of the system.

## Design Principles

- Every answer traces back to source material — no generation without retrieval
- Source documents are never mixed with generated output
- Secrets and credentials never appear in logs or API responses
- Role behaviour lives in configuration, not code

## Get Started

See [docs/setup.md](docs/setup.md) for step-by-step provisioning instructions:
prerequisites, configuration, starting the platform, connecting Claude, querying the knowledge base, and the platform operations reference (status, restart, logs, and the Postgres recovery procedure).

## Stack

Python · PostgreSQL · pgvector · MCP (model context protocol) · Docker

## Project Structure

```
cos/
├── config.yaml.example       # config template — copy to config.yaml and fill in
├── docker-compose.yml        # postgres, tika, cos, worker services
├── Dockerfile                # cos and worker container image (shared build)
├── role_packs/               # role pack YAML files — define who the platform serves
│   ├── chro.yaml             # CHRO example (default)
│   └── enterprise_architect.yaml  # Enterprise Architect example
├── tokens/                   # OAuth token files (gitignored) — gmail.json, google_calendar.json
├── docs/
│   ├── setup.md              # setup, operations, and querying guide
│   ├── migration.md          # migration/backfill guide for existing Phase 1 stores
│   ├── role-packs.md         # role pack authoring guide and field reference
│   └── manual-testing.md     # Epic 7 retrieval-trust regression runbook (also covers Epic 6 UAT packs)
├── src/
│   └── cos/
│       ├── cli.py            # `cos` CLI entry point (status, restart, logs, ingest, docs, auth, sync, benchmark, migrate)
│       ├── config.py         # CosConfig — Pydantic model reads config.yaml at startup
│       ├── mcp_server/       # FastMCP server — tools and startup sequence
│       ├── services/         # thin service layer — ingestion, provenance, health, gmail, calendar
│       ├── store/            # Postgres schema, migrations, data models
│       ├── ingestion/        # extraction, chunking, embedding pipeline
│       ├── retrieval/        # hybrid keyword + semantic search
│       ├── rolepack/         # role pack YAML loader
│       ├── output/           # OutputRouter — sole exit point for all user-facing output
│       ├── llm/              # LLM provider adapter (provider-agnostic interface)
│       └── connectors/       # Gmail, Google Calendar OAuth and sync connectors
└── tests/
    └── ...                   # pytest test suite
```
