# Chief of Staff

A personal AI platform that acts as a Chief of Staff for a specific role — retaining knowledge in a structured store and reasoning over it to answer questions grounded in source material.

## Current Capabilities (Epic 1)

This is the platform foundation. What is working today:

- **Three-container platform** (postgres/pgvector, Tika, cos) that starts with `docker compose up -d`
- **Config validation at startup** — human-readable errors for missing or invalid config values
- **Database schema applied automatically** — idempotent migrations run on every startup
- **MCP server** accessible via `docker compose exec` stdio transport (Claude Code and Claude Desktop)
- **`get_status` tool** — returns JSON with health of all three components (cos, postgres, tika) and a `ready` flag
- **`retrieve`, `get_role_context`, `list_documents`** — registered tools that return "Not yet implemented" error envelopes; will be wired in later epics

Document ingestion, knowledge retrieval, role pack loading, CLI commands, and connected sources (email, calendar) are not yet available. They are planned for later epics.

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
prerequisites, configuration, starting the platform, connecting Claude, and the restart procedure.

## Stack

Python · PostgreSQL · pgvector · MCP (model context protocol) · Docker

## Project Structure

```
cos/
├── config.yaml.example       # config template — copy to config.yaml and fill in
├── docker-compose.yml        # postgres, tika, cos services
├── Dockerfile                # cos container image
├── docs/
│   └── setup.md              # setup and operations guide
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
