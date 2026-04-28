# Chief of Staff

A personal AI platform that acts as a Chief of Staff for a specific role — retaining knowledge in a structured store and reasoning over it to answer questions grounded in source material.

## Current Capabilities (Epic 3)

What is working today:

- **Three-container platform** (postgres/pgvector, Tika, cos) that starts with `docker compose up -d`
- **Config validation at startup** — human-readable errors for missing or invalid config values
- **Database schema applied automatically** — idempotent migrations run on every startup
- **MCP server** accessible via `docker compose exec` stdio transport (Claude Code and Claude Desktop)
- **`cos ingest <path>`** — ingest a single file or folder of documents (PDF, .docx, .md, .txt); per-file progress and final summary printed
- **`cos docs`** — list all ingested documents with provenance metadata (source path, ingested timestamp, version, chunk count)
- **`cos docs --versions <id>`** — show version history for a specific document
- **`cos docs --json`** — machine-readable JSON output
- **Originals preserved** — every ingested file is stored byte-for-byte in `/data/originals/` (in-container path); Markdown working copies in `/data/markdown/`
- **`retrieve`** — ask questions about ingested documents; returns a synthesised answer grounded in source material with citations in both `data.citations` and top-level `citations` (`source_path`, `chunk_index`, `score` per citation); handles the no-content case without fabrication
- **`list_documents`** — returns a JSON envelope with `data.documents`, where each document includes `id`, `source_path`, `ingested_at`, `current_version`, and `chunk_count`; the document rows match `cos docs --json`
- **`get_role_context`** — returns stub role context: `default — role pack not yet configured`; role-specific tone and retrieval weighting arrive in Epic 4
- **`get_status`** — returns a JSON envelope with health of all three components (cos, postgres, tika) and a `ready` flag

Knowledge retrieval and Q&A with citations are now working. Role pack loading (tone, retrieval weighting, stakeholder context) is planned for Epic 4. Connected sources (email, calendar) are planned for Epic 6.

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
prerequisites, configuration, starting the platform, connecting Claude, querying the knowledge base, and the restart procedure.

## Stack

Python · PostgreSQL · pgvector · MCP (model context protocol) · Docker

## Project Structure

```
cos/
├── config.yaml.example       # config template — copy to config.yaml and fill in
├── docker-compose.yml        # postgres, tika, cos services
├── Dockerfile                # cos container image
├── docs/
│   ├── setup.md              # setup, operations, and querying guide
│   └── manual-testing.md     # end-to-end operator validation tests
├── src/
│   └── cos/
│       ├── cli.py            # `cos` CLI entry point (stub commands)
│       ├── config.py         # CosConfig — Pydantic model reads config.yaml at startup
│       ├── mcp_server/       # FastMCP server — tools and startup sequence
│       ├── services/         # thin service layer — only cross-module import path
│       ├── store/            # Postgres schema, migrations, data models
│       ├── ingestion/        # extraction, chunking, embedding pipeline (Epic 2)
│       ├── retrieval/        # hybrid keyword + semantic search (Epic 3)
│       ├── rolepack/         # role pack YAML loader (Epic 4)
│       ├── output/           # OutputRouter — sole exit point for all user-facing output
│       ├── llm/              # LLM provider adapter (provider-agnostic interface)
│       └── connectors/       # external source connectors (Epic 6 — stubs only)
└── tests/
    └── ...                   # pytest test suite
```
