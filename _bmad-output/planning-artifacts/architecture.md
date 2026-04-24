---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-04-17'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - 'initial_docs/shared_cos_platform_architecture.md'
  - 'initial_docs/shared_cos_platform_diagrams_and_handoff.md'
  - 'initial_docs/CoS - CHRO.md'
workflowType: 'architecture'
project_name: 'CoS'
user_name: 'Iain.livingstone'
date: '2026-04-16'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:** 37 total across 7 categories

| Category | Count | Phase |
|---|---|---|
| Knowledge Ingestion | 9 | FR1–6 MVP; FR7–9 Growth |
| Knowledge Retrieval | 6 | FR10–14 MVP; FR15 Growth |
| Reasoning & Output | 5 | FR16–17, FR20 MVP; FR18–19 Growth |
| Role Pack Management | 4 | All MVP |
| Platform Operations | 6 | All MVP |
| External Connectivity | 4 | All Growth |
| Security & Governance | 3 | All MVP |

Phase 1 MVP carries 26 FRs; Growth adds 11.

**Non-Functional Requirements:** 20 total

Critical NFRs that will drive architectural decisions:
- **NFR1** — Retrieval response ≤ 5 seconds (local, up to 10,000 docs): shapes chunk size, index design, and hybrid search implementation
- **NFR2** — Ingestion ≥ 10 docs/min: extraction layer must not be a bottleneck; async worker pattern preferred
- **NFR3** — MCP non-retrieval calls ≤ 2 seconds: lightweight status/context tools; no blocking I/O on these paths
- **NFR4** — Container startup ≤ 60 seconds: health check readiness probes required
- **NFR9** — Recovery ≤ 30 seconds on `cos restart`: containers must restart cleanly with no manual DB repair
- **NFR10** — Single component failure must not take down MCP server: process isolation between ingestion worker and server
- **NFR12** — Knowledge base integrity across unclean shutdowns: transactional writes; no partial embedding records
- **NFR15** — All configuration in `config.yaml`; no environment-specific code changes: deeply constrains how the role pack, credentials, and provider settings are loaded
- **NFR18/19** — Embedding and LLM providers independently swappable via config: requires clean adapter interfaces at both levels

**Scale & Complexity:**

- Primary domain: API backend / knowledge management platform
- Complexity level: High
- Deployment target: Local-first (Docker Compose), cloud-portable
- Builder profile: Solo — use established libraries; avoid building foundational infrastructure
- Estimated architectural components: 7 (Ingestion Worker, Document Store, Embedding Service, Retrieval API, MCP Server, Role Pack Loader, Scheduler/Connector layer)

### Technical Constraints & Dependencies

- **Docker Compose** is the deployment unit — all components must be expressible as Compose services
- **Postgres + pgvector** is the chosen store — metadata, workflow state, and embeddings in one system; no separate vector DB
- **MCP SDK** (Python or TypeScript) — must use the official SDK; do not implement the protocol from scratch
- **Apache Tika** (or equivalent) — format-agnostic extraction layer for PDF, Word; avoids per-format parsing code
- **OAuth 2.0** for Gmail and Google Calendar — deferred to Growth but must not require architectural rework when added
- **Telegram Bot API** — bidirectional channel; Growth tier
- **Embedding provider** — configurable; default to a fast low-cost model (e.g. `text-embedding-3-small`); swappable via config
- **LLM provider** — Claude first; provider-agnostic adapter from day one
- **Single `config.yaml`** — role pack path, API keys, connector credentials, output channel config all centralised here

### Cross-Cutting Concerns Identified

1. **Provenance & citation integrity** — every stored chunk must carry a traceable link back to its source document and ingestion record; this constraint touches ingestion, storage schema, retrieval response format, and the MCP tool contract
2. **Egress control** — all output paths (MCP responses, scheduled briefs, connector replies) must validate against configured channels before delivering; must fail closed
3. **Role pack propagation** — the active role pack affects retrieval ranking weights, reasoning tone, output channel permissions, and scheduled workflow definitions; it is loaded at startup and must be consistently applied across all components without tight coupling
4. **Provider-agnostic abstraction** — two independent adapter boundaries: embedding (ingestion + retrieval) and LLM (reasoning); must be isolated so swapping one does not affect the other
5. **Component isolation** — ingestion worker, MCP server, and scheduler must be separate processes; a crash in one must not affect the others; shared state only via the database
6. **Immutability** — original source files and their ingestion metadata are write-once; no update or delete paths for source material; version records are additive
7. **Configuration-driven behaviour** — no environment-specific branching in code; all variable behaviour (role, provider, channels) resolved from `config.yaml` at startup

## Starter Template Evaluation

### Primary Technology Domain

API backend / knowledge management platform — no web UI, no frontend framework.
Primary interface is an MCP server; secondary interface is a CLI. Deployment is Docker Compose.

### Scaffold Approach

No application-level starter template applies. The project is initialised as a Python package
using `uv` with a `src`-layout. All services (MCP server, ingestion worker, CLI, scheduler)
are entry points within a single package for Phase 1 — shared DB models, config loader, and
type definitions without cross-package duplication.

### Key Library Versions (verified April 2026)

| Library | Version | Notes |
|---|---|---|
| `mcp` (MCP Python SDK) | 1.27.0 | Official SDK; MCP spec 2025-11-25; FastMCP pattern |
| `psycopg[binary]` | psycopg3 | Modern async-native PostgreSQL driver; replaces psycopg2 |
| `pgvector` | latest | Supports psycopg3 natively; no separate vector DB needed |
| `tika-client` | latest | Modern REST client for Apache Tika server; no bundled JAR |
| `pydantic` | v2 | Config validation and data models |
| `typer` | latest | CLI framework; wraps Click; type-annotated commands |
| `apscheduler` | 3.x | Lightweight cron scheduler; no workflow orchestration overhead |
| `httpx` | latest | Async HTTP client for LLM adapter, web search, connector calls |

### Initialization Command

```bash
uv init --app --package cos
uv add mcp psycopg[binary] pgvector pydantic typer apscheduler httpx tika-client
uv add --dev pytest pytest-asyncio ruff mypy
```

### Project Structure

```
cos/
├── pyproject.toml              # package metadata, dependencies, entry points
├── uv.lock                     # checked in — reproducible installs
├── .python-version             # Python version pin
├── docker-compose.yml          # all services: postgres, tika, cos
├── Dockerfile                  # cos package image
├── config.yaml                 # role pack, API keys, connector config
└── src/
    └── cos/
        ├── __init__.py
        ├── cli.py              # `cos` CLI entry point (status, restart, logs, ingest)
        ├── config.py           # config.yaml loader (Pydantic settings model)
        ├── ingestion/
        │   ├── pipeline.py     # extract → normalise → chunk → embed → store
        │   ├── extractor.py    # tika-client wrapper → Markdown
        │   └── chunker.py      # text splitting with overlap
        ├── store/
        │   ├── db.py           # psycopg3 async pool + pgvector registration
        │   ├── models.py       # Document, Chunk, Embedding, ProvenanceRecord
        │   └── migrations/     # SQL migration files (applied at startup)
        ├── retrieval/
        │   ├── search.py       # hybrid keyword + semantic search
        │   └── citations.py    # citation formatting for MCP responses
        ├── rolepack/
        │   └── loader.py       # role pack YAML → typed config object
        ├── mcp_server/
        │   └── tools.py        # MCP tool definitions: retrieve, get_role_context,
        │                       # list_documents, get_status
        └── connectors/         # Growth tier: gmail, calendar, telegram stubs
            └── __init__.py
```

### Architectural Decisions Made by This Scaffold

**Language & Runtime:** Python 3.12+ (pinned via `.python-version`); async-first using `asyncio` throughout

**Package Management:** `uv` — fast installs, lockfile checked in, no conda/virtualenv management overhead

**Database Access:** psycopg3 async pool — native async, modern API, pgvector registers custom types at connect time

**Configuration Loading:** Pydantic v2 settings model reads `config.yaml` at startup; all services share the same config object; no environment-specific branching in code

**CLI Framework:** `typer` — type-annotated CLI commands match the `cos status / restart / logs / ingest` contract; produces plain-language output for non-technical users

**Testing:** `pytest` + `pytest-asyncio`; `ruff` for linting; `mypy` for type checking

**MCP Server Pattern:** FastMCP pattern from the official SDK — decorator-based tool registration; no manual protocol implementation

**Note:** The first implementation story is project initialisation: run `uv init`, add dependencies, create the Docker Compose file with Postgres + pgvector + Tika services, and validate `docker compose up` reaches a healthy state.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Raw SQL schema with startup migrations — no ORM; psycopg3 async directly
- Thin service layer (`cos.services.*`) — only public interface between modules
- `OutputRouter` as sole exit point — fail-closed egress enforcement
- Three-container Compose structure — postgres, tika, cos
- MCP server applies migrations at startup

**Important Decisions (Shape Architecture):**
- 1024 token / 100 token overlap chunk defaults
- CLI-triggered ingestion for Phase 1; schema pre-designed for Phase 2 job queue
- Structured errors returned in MCP tool results (not protocol errors)
- JSON logging to stdout; `cos status` via Docker health checks
- `tokens/` directory for OAuth (separate from `config.yaml`)

**Deferred Decisions (Post-MVP):**
- Background job queue (Postgres `jobs` table) — Phase 2, when connectors need to trigger ingestion; if Phase 1 CLI approach proves problematic, move to this pattern earlier
- OAuth token flow implementation — `tokens/` directory structure decided; implementation deferred to Growth tier
- Multi-provider LLM adapter — adapter interface defined in Phase 1; second provider wired in Phase 2+
- `cos re-embed` CLI command — Phase 2; re-embeds all existing chunks using the currently configured embedding provider; required when switching embedding models; implementation: re-embed into temp table, swap atomically in a transaction to avoid mixed-model state; the `embeddings` table `model` and `provider` columns make it possible to detect which model was used and verify consistency before and after

---

### Data Architecture

| Decision | Choice | Rationale |
|---|---|---|
| Schema strategy | Raw SQL + migration files | Solo build; stay close to the data; no ORM magic; easy to read and debug |
| Migration execution | Applied by MCP server at startup | Single operator; `docker compose up` should just work with no extra steps |
| Chunk size | 1024 tokens | Mixed corpus (strategy docs, frameworks, emails); larger chunks suit narrative content |
| Chunk overlap | 100 tokens | Preserves cross-boundary context without excessive duplication |
| Document store | Append-only; version records additive | Immutability per PRD; originals never modified or deleted |
| Schema layout | `documents` → `chunks` → `embeddings`; `document_versions` for provenance | Clean FK chain; citation integrity traceable at chunk level |

**Phase 2 design note:** The `documents` table will include a `status` column from day one. A `jobs` table (ingestion job queue) will be added in Phase 2 without requiring schema rework — the document model already supports it.

---

### Authentication & Security

| Decision | Choice | Rationale |
|---|---|---|
| Config secrets | Plain `config.yaml` + `.gitignore` | PRD mandates single config file (NFR15); `.gitignore` is the correct boundary |
| Egress enforcement | `OutputRouter` — sole exit point for all output | Hardest to accidentally bypass; single place to validate against configured channels |
| Egress failure mode | Suppress + log — never raise unhandled error | Fail closed per NFR7; error must not fall through to unintended output |
| OAuth token storage | Separate `tokens/` directory | Config is hand-edited (static); tokens are rotated by auth library (dynamic) |
| Localhost auth | None — trust host machine access controls | PRD explicit; adds no value at local deployment scope |
| LLM API calls | HTTPS only; keys never logged | NFR5 and NFR6 — keys in config only, not in logs or responses |

---

### API & Communication Patterns

| Decision | Choice | Rationale |
|---|---|---|
| Ingestion trigger (Phase 1) | CLI in-process (`cos ingest`) | Manual ingestion only in Phase 1; no queue overhead needed |
| Ingestion trigger (Phase 2) | Postgres `jobs` table + background worker | Connector-triggered ingestion requires async queue; schema pre-designed for this |
| MCP tool errors | Structured content response `{"error": "...", "detail": "..."}` | LLM can reason about the error and report it meaningfully to the user |
| Module boundaries | Thin service layer — `cos.services.*` only | Other modules import only from `cos.services.*`; internals stay private; enables clean test stubs |
| Inter-service communication | Shared Postgres only | No IPC, no message bus; state lives in DB; component crashes do not cascade |

---

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|---|---|---|
| Container structure | Three containers: `postgres`, `tika`, `cos` | Single `cos` image used as running server and CLI runner; sufficient for Phase 1 |
| Startup sequence | Postgres health check → Tika health check → cos (migrations then serve) | Ensures dependencies are ready; migration applied once per startup |
| Logging | Structured JSON to stdout | Docker-native; `cos logs` wraps `docker compose logs`; cloud-VM portable |
| Health checks | Docker Compose `healthcheck` per container; `cos status` formats output | Plain-language status for non-technical users; no additional service endpoints needed |
| Recovery | `cos restart` = `docker compose restart`; migrations re-run idempotently | 30-second recovery target (NFR9); idempotent migrations mean no manual DB repair |
| Data persistence | Named Docker volume for Postgres data; local bind mount for originals + Markdown copies | Survives container restarts and rebuilds; portable to cloud VM |

---

### Decision Impact Analysis

**Implementation Sequence:**
1. Docker Compose scaffold (postgres + pgvector + tika + cos skeleton)
2. DB schema + migration runner (applied at cos startup)
3. Config loader (`cos/config.py` — Pydantic model from `config.yaml`)
4. Service layer stubs (`cos/services/` — interfaces defined before implementations)
5. Ingestion pipeline (`cos/ingestion/` → `cos/services/ingestion`)
6. Retrieval layer (`cos/retrieval/` → `cos/services/retrieval`)
7. MCP server tools (consume service layer only)
8. CLI (`cos status`, `cos ingest`, `cos logs`, `cos restart`)
9. Role pack loader (YAML → typed config; consumed by retrieval + MCP tools)
10. OutputRouter (used by MCP tools and, later, scheduler/connectors)

**Cross-Component Dependencies:**
- Every component depends on `cos/config.py` — build this first, build it right
- MCP tools only call `cos/services/*` — never `cos/store/*` or `cos/ingestion/*` directly
- `OutputRouter` is a dependency of MCP tools (Phase 1) and connectors/scheduler (Phase 2) — define its interface in Phase 1 even if only the local output path is implemented
- Migration idempotency is a hard constraint — every migration file must be safe to re-run

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 5 areas where AI agents could make different choices — naming, structure, response formats, async discipline, and egress enforcement.

### Naming Patterns

**Database Naming Conventions:**

| Element | Convention | Example |
|---|---|---|
| Tables | snake_case, plural | `documents`, `chunks`, `embeddings`, `document_versions` |
| Columns | snake_case | `source_path`, `ingested_at`, `chunk_index` |
| Primary keys | `id` (UUID) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Foreign keys | `{table_singular}_id` | `document_id`, `chunk_id` |
| Indexes | `idx_{table}_{column(s)}` | `idx_chunks_document_id`, `idx_embeddings_chunk_id` |

**Code Naming Conventions:**

| Element | Convention | Example |
|---|---|---|
| Python modules/files | snake_case | `ingestion/pipeline.py`, `store/db.py` |
| Python classes | PascalCase | `DocumentRecord`, `OutputRouter`, `CosConfig` |
| Python functions/methods | snake_case | `get_pool()`, `retrieve_chunks()`, `send_output()` |
| Python variables | snake_case | `chunk_size`, `source_path`, `role_pack` |
| Constants | UPPER_SNAKE_CASE | `DEFAULT_CHUNK_SIZE`, `MAX_RETRIES` |

### Structure Patterns

**Project Organisation:**
- `tests/` at root, mirroring `src/cos/` — `tests/ingestion/`, `tests/retrieval/`, `tests/store/`, etc.
- `cos/services/` contains thin orchestration only — no business logic, no direct DB calls
- `cos/config.py` is the one and only config reader — no module reads `config.yaml` directly
- `cos/store/migrations/` contains numbered SQL files — `001_initial.sql`, `002_add_jobs.sql`; applied in order at startup

**File Structure Rules:**
- No logic in `__init__.py` files — only re-exports if needed
- One class per file for service layer; internal modules may contain multiple related functions
- `cos/connectors/` exists as a stub directory from Phase 1 — placeholder `__init__.py` only, no dead code

### Format Patterns

**MCP Tool Response Envelope (all tools must return this shape):**
```python
# Success
{"status": "ok", "data": {...}, "citations": [...]}

# Error
{"status": "error", "error": "human-readable message", "detail": "technical detail for logs"}
```

**Retrieval Result Shape (every chunk result must include all fields):**
```python
{
    "content": "...",
    "source_document_id": "uuid",
    "source_path": "path/to/original",
    "chunk_index": 3,
    "score": 0.87
}
```

**Logging (structured JSON — mandatory fields):**
```python
{"timestamp": "2026-04-17T08:00:00Z", "level": "INFO", "component": "ingestion", "message": "..."}
```
- No bare `print()` calls anywhere in the codebase
- `component` is always one of: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`, `output`

**Dates:** ISO 8601 strings in all external interfaces — `"2026-04-17T08:00:00Z"`. Never Unix timestamps.

### Process Patterns

**Error Handling:**
- Exceptions bubble up to the service layer boundary only
- Services catch, log structured JSON, and return the error envelope — nothing above `cos/services/` sees raw exceptions
- Unhandled exceptions in the MCP server return `{"status": "error", ...}` — never propagate as uncaught

**Async Discipline:**
- All DB calls and external I/O must be `async`
- `asyncio.run()` only at entry points (`cli.py`, `mcp_server/tools.py`) — never inside library code
- No sync wrappers around async functions

**Idempotency:**
- All migration SQL files must be safe to re-run (use `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`)
- All ingestion pipeline steps must handle re-runs gracefully — document this in the function docstring

**OutputRouter Contract:**
- Any code that delivers output to a user calls `OutputRouter.send(channel, content)` — never calls a channel handler directly
- `OutputRouter` is injected as a dependency, not imported as a module-level singleton
- Validation failure always suppresses output and logs — never raises an exception that could fall through

### Enforcement Guidelines

**All AI Agents MUST:**
- Import config only via `CosConfig` from `cos.config` — never read `config.yaml` directly
- Import only from `cos.services.*` when crossing module boundaries — never from `cos.store.*` or `cos.ingestion.*` directly
- Return the standard MCP response envelope from every tool — no custom response shapes
- Use `async` for all I/O — no synchronous DB or HTTP calls
- Send all output through `OutputRouter` — no direct channel calls

**Anti-Patterns (explicitly forbidden):**
```python
# WRONG — reading config directly
import yaml; cfg = yaml.safe_load(open("config.yaml"))

# WRONG — crossing module boundary
from cos.store.db import get_pool  # in mcp_server/tools.py

# WRONG — bare print
print("ingesting document...")

# WRONG — sync DB call in async context
conn = psycopg2.connect(...)

# WRONG — direct channel call bypassing OutputRouter
telegram_bot.send_message(chat_id, response)
```

## Project Structure & Boundaries

### Requirements to Structure Mapping

| FR Category | Maps To |
|---|---|
| Knowledge Ingestion (FR1–9) | `cos/ingestion/`, `cos/services/ingestion.py` |
| Knowledge Retrieval (FR10–15) | `cos/retrieval/`, `cos/services/retrieval.py` |
| Reasoning & Output (FR16–20) | `cos/output/`, `cos/services/output.py`, `OutputRouter` |
| Role Pack Management (FR21–24) | `cos/rolepack/`, `cos/services/rolepack.py` |
| Platform Operations (FR25–30) | `cos/cli.py`, `cos/health.py` |
| External Connectivity (FR31–34) | `cos/connectors/` (Phase 2 stubs only in Phase 1) |
| Security & Governance (FR35–37) | `cos/output/router.py`, `cos/store/models.py` (provenance) |

### Complete Project Directory Structure

```
cos/
├── pyproject.toml                  # uv package config, entry points, dependencies
├── uv.lock                         # checked in — reproducible installs
├── .python-version                 # Python version pin (3.12)
├── .gitignore                      # excludes config.yaml, tokens/, .venv/, __pycache__
├── docker-compose.yml              # postgres, tika, cos services
├── Dockerfile                      # cos image: uv install + entrypoint
├── config.yaml.example             # template — copy to config.yaml, never commit config.yaml
├── config.yaml                     # gitignored — role pack path, API keys, channel config
├── tokens/                         # gitignored — OAuth tokens written by auth library
│   ├── gmail.json                  # (Phase 2) written by google-auth on first OAuth flow
│   └── google_calendar.json        # (Phase 2)
├── docs/
│   └── setup.md                    # non-technical user setup and restart instructions
└── src/
    └── cos/
        ├── __init__.py
        ├── cli.py                  # Typer app — `cos` entry point
        │                           # Commands: status, restart, logs, ingest
        ├── config.py               # CosConfig — Pydantic v2 model; reads config.yaml once at startup
        ├── health.py               # health check logic called by `cos status`
        │
        ├── store/                  # data layer — never imported directly by mcp_server or cli
        │   ├── __init__.py
        │   ├── db.py               # psycopg3 async pool; pgvector type registration
        │   ├── models.py           # DocumentRecord, ChunkRecord, EmbeddingRecord,
        │   │                       # DocumentVersion, ProvenanceRecord dataclasses
        │   └── migrations/         # numbered SQL files; applied idempotently at startup
        │       ├── 001_initial.sql # documents, chunks, embeddings, document_versions tables
        │       └── 002_jobs.sql    # (Phase 2) jobs table for background ingestion queue
        │
        ├── ingestion/              # ingestion implementation — consumed via services layer
        │   ├── __init__.py
        │   ├── pipeline.py         # orchestrates: extract → normalise → chunk → embed → store
        │   ├── extractor.py        # tika-client wrapper; returns Markdown string + metadata
        │   ├── chunker.py          # text splitting; default 1024 tokens / 100 overlap
        │   └── embedder.py         # embedding provider adapter; configurable via CosConfig
        │
        ├── retrieval/              # retrieval implementation — consumed via services layer
        │   ├── __init__.py
        │   ├── search.py           # hybrid search: keyword (tsvector) + semantic (pgvector)
        │   │                       # applies role pack retrieval weights from RolePackConfig
        │   └── citations.py        # formats retrieval results into citation-ready response shape
        │
        ├── rolepack/               # role pack loading and validation
        │   ├── __init__.py
        │   └── loader.py           # reads role pack YAML → RolePackConfig (Pydantic model)
        │                           # RolePackConfig: goals, tone, taxonomy, workflows,
        │                           #   stakeholder_map, retrieval_priorities, output_channels
        │
        ├── output/                 # output delivery — sole exit point for all user-facing output
        │   ├── __init__.py
        │   ├── router.py           # OutputRouter: validates channel against config, routes to handler
        │   │                       # Fail-closed: suppresses + logs on invalid channel
        │   └── channels/
        │       ├── __init__.py
        │       ├── local.py        # local output handler (stdout / MCP response)
        │       ├── telegram.py     # (Phase 2) Telegram Bot API handler
        │       └── email.py        # (Phase 2) email delivery handler
        │
        ├── connectors/             # external data connectors — Phase 2 implementations
        │   ├── __init__.py         # Phase 1: empty stubs only
        │   ├── gmail.py            # (Phase 2) Gmail API — read email, ingest attachments
        │   ├── calendar.py         # (Phase 2) Google Calendar API — read events
        │   └── telegram_bot.py     # (Phase 2) Telegram Bot — inbound Q&A and note capture
        │
        ├── llm/                    # LLM provider adapter — provider-agnostic interface
        │   ├── __init__.py
        │   ├── adapter.py          # LLMAdapter protocol/ABC — complete() method contract
        │   └── anthropic.py        # Claude implementation of LLMAdapter (Phase 1)
        │
        ├── mcp_server/             # MCP server entry point and tool definitions
        │   ├── __init__.py
        │   ├── server.py           # FastMCP app instantiation; registers all tools; startup hook
        │   │                       # Entry point: `uv run cos-mcp` via pyproject.toml [scripts]
        │   └── tools.py            # MCP tool definitions: retrieve, get_role_context,
        │                           # list_documents, get_status
        │                           # All tools consume cos/services/* only
        │
        └── services/               # thin service layer — ONLY public interface between modules
            ├── __init__.py
            ├── ingestion.py        # IngestService: ingest_file(path), ingest_note(text)
            ├── retrieval.py        # RetrievalService: query(text, role_pack) → CitedResults
            ├── rolepack.py         # RolePackService: get_active() → RolePackConfig
            ├── output.py           # OutputService: wraps OutputRouter; used by MCP tools
            └── health.py           # HealthService: check_all() → ComponentStatus[]

tests/
├── conftest.py                     # shared fixtures: test DB, mock CosConfig, mock OutputRouter
├── ingestion/
│   ├── test_pipeline.py
│   ├── test_extractor.py
│   └── test_chunker.py
├── retrieval/
│   ├── test_search.py
│   └── test_citations.py
├── rolepack/
│   └── test_loader.py
├── output/
│   └── test_router.py              # key test: verify fail-closed behaviour
├── services/
│   ├── test_ingestion_service.py
│   ├── test_retrieval_service.py
│   └── test_health_service.py
└── store/
    └── test_migrations.py          # verify migrations are idempotent
```

### Architectural Boundaries

**Service Layer Boundary (primary enforcement point):**
- `cos/mcp_server/` and `cos/cli.py` must not import from `cos/store/`, `cos/ingestion/`, `cos/retrieval/`, `cos/rolepack/`, or `cos/output/` directly — route through `cos/services/*`. Intra-package imports within `mcp_server/` (e.g. `tools.py` importing the FastMCP app from `server.py`) are permitted.
- `cos/services/*` import from `cos/ingestion/`, `cos/retrieval/`, `cos/store/`, `cos/rolepack/`, `cos/output/`
- `cos/ingestion/`, `cos/retrieval/` etc. do NOT import from each other — only from `cos/store/` and `cos/config.py`

**Output Boundary (egress enforcement):**
- `OutputRouter` in `cos/output/router.py` is the sole exit point
- MCP tool responses pass through `OutputService` which wraps `OutputRouter`
- Phase 2 connectors deliver via `OutputRouter` — never write to channels directly

**Config Boundary:**
- `CosConfig` in `cos/config.py` is instantiated once at startup and injected
- No module other than `cos/config.py` reads `config.yaml`

**LLM Boundary:**
- `LLMAdapter` protocol in `cos/llm/adapter.py` is the only interface the retrieval and output layers use
- Swapping provider = implementing the protocol in a new file + updating config

### Data Flow

**Ingestion path:**
```
cos ingest <path>
  → IngestService.ingest_file()
    → extractor.py (Tika → Markdown)
    → chunker.py (Markdown → chunks)
    → embedder.py (chunks → vectors via embedding adapter)
    → store/db.py (write documents, chunks, embeddings, provenance — transactional)
```

**Query path:**
```
MCP client calls `retrieve` tool
  → OutputService validates channel
    → RetrievalService.query()
      → retrieval/search.py (keyword + semantic, role pack weights applied)
      → retrieval/citations.py (format cited results)
    → LLMAdapter.complete() (synthesise response from retrieved chunks)
  → OutputRouter.send(channel="local", content=response)
```

**Startup sequence:**
```
docker compose up
  → postgres (healthcheck: pg_isready)
  → tika (healthcheck: HTTP GET /tika)
  → cos (depends_on postgres+tika healthy)
      → load CosConfig from config.yaml
      → run pending SQL migrations (idempotent)
      → load RolePackConfig
      → start MCP server
```

### Integration Points

**Internal:**
- All inter-module communication via `cos/services/*` interfaces
- All shared state via Postgres — no in-process shared mutable state between logical components

**External (Phase 1):**
- Claude API (via `cos/llm/anthropic.py`) — HTTPS, key from config
- Tika server (via `tika-client`) — localhost Docker network
- Embedding provider API — HTTPS, key from config, provider-configurable

**External (Phase 2 — stubbed in structure, not implemented):**
- Gmail API — OAuth 2.0, tokens in `tokens/gmail.json`
- Google Calendar API — OAuth 2.0, tokens in `tokens/google_calendar.json`
- Telegram Bot API — bot token from config
- Web search API (Brave or Tavily) — key from config

### Entry Points (pyproject.toml scripts)

```toml
[project.scripts]
cos = "cos.cli:app"           # CLI: cos status / restart / logs / ingest
cos-mcp = "cos.mcp_server.server:run"  # MCP server: started by Docker Compose `cos` service
```

The `cos` container runs `cos-mcp` as its default process. The `cos` CLI is used for one-off commands via `docker compose run cos cos ingest <path>`.

### docker-compose.yml Port Annotation (Required)

All services must bind only to `127.0.0.1` (localhost) — never `0.0.0.0`. Example:

```yaml
# CORRECT — localhost only (NFR8)
ports:
  - "127.0.0.1:5432:5432"

# WRONG — exposes to all interfaces
ports:
  - "5432:5432"
```

The MCP server exposes no host port at all — Claude Desktop connects to it via stdio transport, not TCP.

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:**
All technology choices are mutually compatible. psycopg3 + pgvector-python natively supports the async pool pattern. MCP SDK 1.27.0 FastMCP works with Python 3.12+. Tika-client connects to a containerised Tika server over Docker's internal network. APScheduler 3.x is compatible with asyncio. No version conflicts identified.

**Pattern Consistency:**
The thin service layer pattern is coherent with the async discipline rule — the service boundary is the natural place to bridge Typer's sync CLI entry points with the async internals via `asyncio.run()`. Naming conventions (snake_case DB, snake_case Python, PascalCase classes) are consistent throughout. The `OutputRouter` as sole exit point is consistently reflected in both the patterns rules and the structure boundaries.

**Structure Alignment:**
The project structure directly maps to each architectural boundary: `cos/services/` enforces the module boundary, `cos/output/router.py` enforces egress control, `cos/config.py` enforces the config boundary, and `cos/llm/adapter.py` enforces the LLM provider boundary. The `mcp_server/` module has been added back to the tree with a clear entry point contract.

### Requirements Coverage Validation

**Functional Requirements — all 37 verified:**

| Category | MVP FRs | Growth FRs | Coverage |
|---|---|---|---|
| Knowledge Ingestion | FR1–6 | FR7–9 | ✅ MVP implemented; Growth stubbed |
| Knowledge Retrieval | FR10–14 | FR15 | ✅ MVP implemented; Growth stubbed |
| Reasoning & Output | FR16–17, FR20 | FR18–19 | ✅ MVP implemented; Growth stubbed |
| Role Pack Management | FR21–24 | — | ✅ Fully covered |
| Platform Operations | FR25–30 | — | ✅ Fully covered |
| External Connectivity | — | FR31–34 | ✅ Stubbed in structure |
| Security & Governance | FR35–37 | — | ✅ Fully covered |

**Non-Functional Requirements — all 20 verified:**

| NFR | Mechanism | Status |
|---|---|---|
| NFR1 ≤5s retrieval | pgvector + tsvector hybrid; 1024-token chunks; FK indexes | ✅ |
| NFR2 ≥10 docs/min | Async pipeline; Tika in Docker | ✅ |
| NFR3 ≤2s non-retrieval MCP | Lightweight tools; no blocking I/O on fast path | ✅ |
| NFR4 ≤60s startup | `depends_on` + healthchecks; fast idempotent migrations | ✅ |
| NFR5/6 Key security | Keys in `config.yaml` only; HTTPS enforced in `LLMAdapter` | ✅ |
| NFR7 Fail-closed egress | `OutputRouter` suppresses + logs; no unhandled exception path | ✅ |
| NFR8 No exposed ports | localhost-only port bindings; MCP via stdio, not TCP | ✅ |
| NFR9 ≤30s recovery | `cos restart` = `docker compose restart`; idempotent migrations | ✅ |
| NFR10 Component isolation | Separate processes; shared state via DB only | ✅ |
| NFR11 Connector fault tolerance | Connectors in separate process; MCP server unaffected | ✅ (Growth) |
| NFR12 Integrity on crash | Transactional writes; no partial ingestion records | ✅ |
| NFR13 ≤2h provisioning | `docker compose up` + `config.yaml.example` + `docs/setup.md` | ✅ |
| NFR14 Unattended operation | No manual steps after startup; scheduler self-managing | ✅ |
| NFR15 Single config file | `CosConfig` from `config.yaml`; no env branching in code | ✅ |
| NFR16 Cloud VM portable | Same Docker Compose config works on Linux VM | ✅ |
| NFR17 MCP spec compliance | Official MCP SDK 1.27.0; FastMCP pattern | ✅ |
| NFR18 Swappable embedding | `embedder.py` provider configurable via `CosConfig` | ✅ |
| NFR19 Swappable LLM | `LLMAdapter` protocol; new provider = new implementation file | ✅ |
| NFR20 OAuth token refresh | `tokens/` directory; google-auth handles refresh automatically | ✅ (Growth) |

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with library versions verified against live PyPI/GitHub as of April 2026. Rationale recorded for every decision. Deferred decisions flagged with phase and trigger condition.

**Structure Completeness:** Complete directory tree defined with file-level annotations. Entry points specified in `pyproject.toml` scripts. Docker Compose port binding requirement documented. Phase 2 stubs present in structure so agents don't invent new locations.

**Pattern Completeness:** Naming conventions cover DB, Python code, and files. Format patterns specify exact response envelopes. Process patterns cover error handling, async discipline, idempotency, and the `OutputRouter` contract. Anti-patterns explicitly listed to prevent the most common failure modes.

### Gap Analysis Results

**Critical gaps — resolved during this validation:**
- `cos/mcp_server/tools.py` added back to project tree ✅
- `mcp_server/server.py` entry point and `pyproject.toml` scripts documented ✅
- NFR8 localhost-only port binding requirement documented with example ✅

**Important notes for implementation:**
- `config.yaml.example` must document all required top-level keys (`role_pack`, `llm`, `embedding`, `channels`, `connectors`) — this is the contract that `CosConfig` implements
- `001_initial.sql` must include both `CREATE EXTENSION IF NOT EXISTS vector` and the `status` column on `documents` from day one
- `conftest.py` test fixtures should use a real Postgres instance (test DB), not mocks — the pgvector behaviour is not reliably mockable

**Nice-to-have (not blocking):**
- A `Makefile` or `justfile` for common dev commands (`make up`, `make test`, `make ingest`) prevents agents inventing different invocation patterns

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analysed — 37 FRs, 20 NFRs categorised
- [x] Scale and complexity assessed — High; solo builder; local-first
- [x] Technical constraints identified — Docker Compose, pgvector, MCP SDK, Tika
- [x] Cross-cutting concerns mapped — provenance, egress, role pack, provider abstraction, immutability

**✅ Architectural Decisions**
- [x] Critical decisions documented with verified library versions
- [x] Technology stack fully specified — Python 3.12, uv, psycopg3, pgvector, MCP 1.27.0
- [x] Integration patterns defined — service layer, LLMAdapter, OutputRouter
- [x] Performance considerations addressed — chunk size, hybrid search, async-first

**✅ Implementation Patterns**
- [x] Naming conventions established — DB, Python code, files
- [x] Structure patterns defined — service layer, config boundary, test layout
- [x] Response format patterns specified — MCP envelope, retrieval result shape, logging
- [x] Process patterns documented — error handling, async discipline, idempotency, OutputRouter contract

**✅ Project Structure**
- [x] Complete directory tree defined with file-level annotations
- [x] Entry points specified — `cos` CLI and `cos-mcp` server
- [x] Component boundaries established and cross-referenced
- [x] Requirements to structure mapping complete for all 7 FR categories

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Clean separation of concerns — each boundary (service layer, config, LLM, output) has a single enforcement point
- Phase 2 growth path is pre-designed in structure without adding Phase 1 complexity
- Every NFR has a concrete architectural mechanism; none are deferred to implementation discretion
- Anti-patterns explicitly documented — reduces agent divergence on the most common failure modes

**Areas for Future Enhancement:**
- Chunk size (1024/100) should be validated empirically during Phase 1 and tuned if retrieval accuracy is insufficient
- `LLMAdapter.complete()` method signature should be extended to support streaming responses in Phase 2
- The `jobs` table in `002_jobs.sql` should be designed collaboratively when Phase 2 begins — the table stub exists but the schema is intentionally deferred

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented — do not introduce new patterns without updating this document
- Use `cos/services/*` as the only cross-module import path — never shortcut to `cos/store/*` directly
- Every MCP tool must return the standard response envelope — no custom shapes
- `OutputRouter` must be injected, not imported as a singleton
- All migrations must be idempotent — use `IF NOT EXISTS` and `ON CONFLICT DO NOTHING`

**First Implementation Story:**
```bash
uv init --app --package cos
uv add mcp psycopg[binary] pgvector pydantic typer apscheduler httpx tika-client
uv add --dev pytest pytest-asyncio ruff mypy
```
Then: create `docker-compose.yml` with `postgres` (pgvector image), `tika`, and `cos` services; validate `docker compose up` reaches healthy state across all three containers.

## Epic 1 Implementation Notes

The following deviations from this architecture spec occurred during Epic 1. Future agents should treat these as the actual state of the codebase, not the spec above.

| # | Deviation | Detail |
|---|---|---|
| 1 | **`TikaConfig` added to `CosConfig`** | The spec did not include a `tika` sub-section in `CosConfig`. Story 1.4 added `TikaConfig(url: str = "http://tika:9998")` to support startup health checks and future Tika extraction calls. The field defaults to `TikaConfig()` so existing `config.yaml` files without a `tika:` block continue to work. |
| 2 | **Startup health checks duplicated** | `server.py` contains standalone `_check_postgres(dsn)` and `_check_tika(url)` functions used during `_startup_sequence`. `HealthService` in `cos/services/health.py` contains near-identical implementations used by `get_status`. The service-layer boundary is partially violated at startup. These should be consolidated — tracked in deferred-work.md. |
| 3 | **`_config` module-level global in `server.py`** | Config is held as `_config: CosConfig | None = None` (module-level mutable state) rather than being injected via dependency. This is a pragmatic choice given FastMCP's decorator-based tool registration pattern, which does not expose a clean injection point at registration time. Deviates from the injection-preferred architecture documented above. |
| 4 | **CLI commands are stubs** | `cos status`, `cos restart`, `cos logs`, and `cos ingest` all raise `NotImplementedError`. The architecture spec describes these as implemented CLI commands. They will be implemented in a later epic. `docs/setup.md` uses `docker compose ps` and `docker compose logs cos` as working alternatives. |
| 5 | **Role pack file not yet created** | `config.yaml.example` references `role_packs/chro.yaml`. This file does not exist. The server logs "role pack: stub loaded" without reading a file. The role pack loader and the CHRO YAML are planned for Epic 4. |

## Epic 2 Implementation Notes

The following deviations from the architecture spec occurred during Epic 2. Future agents should treat these as the actual state of the codebase.

| # | Deviation | Detail |
|---|-----------|--------|
| 1 | **`ProvenanceService` added to `src/cos/services/`** | The architecture spec listed these services: `ingestion.py`, `retrieval.py`, `rolepack.py`, `output.py`, `health.py`. Story 2.5 added `src/cos/services/provenance.py` containing `ProvenanceService` — a read-only service that queries the `documents`, `document_versions`, and `chunks` tables to power `cos docs`. This follows the service layer pattern correctly and is the authoritative implementation for `list_documents` MCP tool (Story 3.4). |
| 2 | **Embedding uses `voyageai` library with `provider: "anthropic"` config** | The architecture spec said "default to a fast low-cost model (e.g. `text-embedding-3-small`)" implying an OpenAI-style provider. The implementation uses the `voyageai` Python package (Anthropic acquired Voyage AI). The `embedder.py` accepts `provider: "anthropic"` in config and routes to Voyage AI via `voyageai.AsyncClient`. Only this one provider path is implemented — the clean adapter pattern is deferred. `config.yaml.example` suggests `embedding.model: voyage-3`; both `provider` and `model` are required fields with no code-level defaults. |
| 3 | **`docs/setup.md` updated incrementally during Epic 2** | The architecture spec placed documentation updates in the housekeeping story (2.7). In practice, `setup.md` was updated during Stories 2.4 and 2.5 as the ingestion and docs commands were implemented. The housekeeping story (2.7) added only the missing `cos docs` verification section. |
| 4 | **Deferred: Missing UNIQUE constraint on `documents.source_path`** | Identified in Story 2.3 review. Concurrent ingests of the same source path can silently create duplicate document records. Pre-existing; deferred to a future schema migration. Tracked in `deferred-work.md`; not yet fixed. |
| 5 | **Deferred: Chunks have no version-linking column** | Identified in Story 2.3 review. All chunk rows across all version records of a document are stored without a `document_version_id` FK — chunks from version 1 and version 2 of the same document are indistinguishable at the chunk level. Deferred as intentional Phase 1 design; the retrieval layer (Epic 3) returns the most recent chunks by default. |
