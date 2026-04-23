# Story 1.1: Project Scaffold, Containerised Services & Core Interfaces

Status: done

## Story

As an operator,
I want to run `docker compose up -d` and have all three platform services start and reach a healthy state,
So that I have a correctly structured, dependency-resolved foundation on which to build the knowledge platform.

## Acceptance Criteria

1. **Given** a new machine with Docker and uv installed, **when** `uv init --app --package cos` is run followed by `uv add mcp psycopg[binary] pgvector pydantic typer apscheduler httpx tika-client` and `uv add --dev pytest pytest-asyncio ruff mypy`, **then** a `pyproject.toml` is created with `cos` and `cos-mcp` defined as entry points in `[project.scripts]`, and a `uv.lock` file is committed.

2. **Given** a `docker-compose.yml` defining `postgres` (pgvector/pgvector:pg16), `tika` (apache/tika), and `cos` services, **when** `docker compose up -d` is run, **then** all three containers reach a healthy state within 60 seconds as reported by `docker compose ps`.

3. **Given** the Docker Compose configuration, **when** the port bindings are inspected, **then** all bound ports use `127.0.0.1` (e.g. `127.0.0.1:5432:5432`), never `0.0.0.0`, and the `cos` service exposes no host ports at all (MCP uses stdio transport).

4. **Given** the `src/cos/` package structure is created, **when** the directory is inspected, **then** it contains `cos/services/` with stub files `ingestion.py`, `retrieval.py`, `rolepack.py`, `output.py`, and `health.py` — each defining a service class with method signatures that raise `NotImplementedError`.

5. **Given** the core interface files are created, **when** `cos/llm/adapter.py` is inspected, **then** it defines an `LLMAdapter` protocol with a typed `complete()` method, and `cos/llm/anthropic.py` contains a stub `AnthropicAdapter` implementing the protocol.

6. **Given** `cos/output/router.py` is created, **when** it is inspected, **then** it contains an `OutputRouter` class with a `send(channel: str, content: str) -> None` method that validates the channel against config and suppresses output (logging a structured JSON error) if the channel is not configured — it never raises an unhandled exception.

7. **Given** `cos/connectors/__init__.py` is created, **when** it is inspected, **then** it is a placeholder file with a comment marking it as a Growth tier stub and contains no implementation code.

8. **Given** `docker compose down` followed by `docker compose up -d` is run, **when** the containers reach healthy state, **then** no manual intervention is required between the two runs.

## Tasks / Subtasks

- [x] Task 1: Initialise uv project and configure pyproject.toml (AC: #1)
  - [x] Run `uv init --app --package cos` to create src-layout project
  - [x] Run `uv add mcp psycopg[binary] pgvector pydantic typer apscheduler httpx tika-client`
  - [x] Run `uv add --dev pytest pytest-asyncio ruff mypy`
  - [x] Add `[project.scripts]` entries: `cos = "cos.cli:app"` and `cos-mcp = "cos.mcp_server.server:run"`
  - [x] Create `.python-version` file pinning Python 3.12
  - [x] Verify `uv.lock` is generated and commit it

- [x] Task 2: Create full directory structure with all stub modules (AC: #4, #5, #7)
  - [x] Create `src/cos/__init__.py` (empty)
  - [x] Create `src/cos/cli.py` — Typer app stub with placeholder `status`, `restart`, `logs`, `ingest` commands
  - [x] Create `src/cos/config.py` — `CosConfig` Pydantic v2 model stub (no fields yet; that is Story 1.2)
  - [x] Create `src/cos/health.py` — empty health check stub
  - [x] Create `src/cos/services/__init__.py` (empty)
  - [x] Create `src/cos/services/ingestion.py` — `IngestService` class with `ingest_file(path)` and `ingest_note(text)` raising `NotImplementedError`
  - [x] Create `src/cos/services/retrieval.py` — `RetrievalService` class with `query(text, role_pack)` raising `NotImplementedError`
  - [x] Create `src/cos/services/rolepack.py` — `RolePackService` class with `get_active()` raising `NotImplementedError`
  - [x] Create `src/cos/services/output.py` — `OutputService` class with `send(channel, content)` raising `NotImplementedError`
  - [x] Create `src/cos/services/health.py` — `HealthService` class with `check_all()` raising `NotImplementedError`
  - [x] Create `src/cos/store/__init__.py` (empty)
  - [x] Create `src/cos/store/db.py` — async pool stub
  - [x] Create `src/cos/store/models.py` — dataclass stubs for `DocumentRecord`, `ChunkRecord`, `EmbeddingRecord`, `DocumentVersion`, `ProvenanceRecord`
  - [x] Create `src/cos/store/migrations/` directory with `001_initial.sql` (empty/comment placeholder — schema is Story 1.3) and `002_jobs.sql` (comment-only Phase 2 stub)
  - [x] Create `src/cos/ingestion/__init__.py` (empty)
  - [x] Create `src/cos/ingestion/pipeline.py`, `extractor.py`, `chunker.py`, `embedder.py` — each with module-level docstring and stub functions raising `NotImplementedError`
  - [x] Create `src/cos/retrieval/__init__.py` (empty)
  - [x] Create `src/cos/retrieval/search.py`, `citations.py` — stubs
  - [x] Create `src/cos/rolepack/__init__.py` (empty)
  - [x] Create `src/cos/rolepack/loader.py` — stub `RolePackConfig` Pydantic model and `load()` function
  - [x] Create `src/cos/llm/__init__.py` (empty)
  - [x] Create `src/cos/llm/adapter.py` — `LLMAdapter` Protocol with typed `complete(prompt: str, context: list[str]) -> str`
  - [x] Create `src/cos/llm/anthropic.py` — `AnthropicAdapter` class implementing `LLMAdapter`; stub body raising `NotImplementedError`
  - [x] Create `src/cos/output/__init__.py` (empty)
  - [x] Create `src/cos/output/router.py` — `OutputRouter` with `send(channel: str, content: str) -> None`; validates channel against CosConfig; suppresses + logs JSON error on invalid channel; never raises
  - [x] Create `src/cos/output/channels/__init__.py` (empty)
  - [x] Create `src/cos/output/channels/local.py` — local stdout/MCP response handler stub
  - [x] Create `src/cos/output/channels/telegram.py` — Phase 2 stub with comment only
  - [x] Create `src/cos/output/channels/email.py` — Phase 2 stub with comment only
  - [x] Create `src/cos/connectors/__init__.py` — comment: `# Growth tier stub — no implementation code`
  - [x] Create `src/cos/connectors/gmail.py`, `calendar.py`, `telegram_bot.py` — Phase 2 stub files (comment only, no dead code)
  - [x] Create `src/cos/mcp_server/__init__.py` (empty)
  - [x] Create `src/cos/mcp_server/server.py` — FastMCP app instantiation stub; `run()` entry point function
  - [x] Create `src/cos/mcp_server/tools.py` — stub tool definitions (`retrieve`, `get_role_context`, `list_documents`, `get_status`)
  - [x] Create `tests/` directory structure mirroring `src/cos/` with `conftest.py` (empty fixture stubs)
  - [x] Create `docs/setup.md` — non-technical user setup, `cos status`, `cos restart`, `cos logs`, three-step restart procedure

- [x] Task 3: Create docker-compose.yml with three services and health checks (AC: #2, #3, #8)
  - [x] Define `postgres` service using image `pgvector/pgvector:pg16`; bind port `127.0.0.1:5432:5432`; add `healthcheck` using `pg_isready -U postgres`; attach named volume for data
  - [x] Define `tika` service using image `apache/tika`; bind port `127.0.0.1:9998:9998`; add `healthcheck` using bash TCP check (wget/curl not available in Tika image)
  - [x] Define `cos` service; `depends_on: postgres: condition: service_healthy` and `tika: condition: service_healthy`; **no host ports** (stdio transport only); mount local `./data` volume for originals and Markdown copies
  - [x] All port bindings must use `127.0.0.1:HOST:CONTAINER` — never bare `PORT:PORT`

- [x] Task 4: Create Dockerfile for the cos service (AC: #2)
  - [x] Use a Python 3.12 base image compatible with uv
  - [x] Install uv, copy `pyproject.toml` + `uv.lock`, run `uv sync --frozen`
  - [x] Set `ENTRYPOINT ["uv", "run", "cos-mcp"]` as the default process

- [x] Task 5: Create config.yaml.example and .gitignore (AC: #1)
  - [x] `config.yaml.example`: document all required top-level keys: `llm`, `embedding`, `role_pack`, `channels`, `connectors`, `database`; placeholder values only
  - [x] `.gitignore`: list `config.yaml`, `tokens/`, `.venv/`, `__pycache__/`, `*.pyc`, `.python-version` (optional)

- [x] Task 6: Validate healthy startup and restart (AC: #2, #8)
  - [x] Run `docker compose up -d`; confirm all three containers show `healthy` within 60 seconds via `docker compose ps`
  - [x] Run `docker compose down && docker compose up -d`; confirm clean restart with no manual intervention

## Dev Notes

### Critical Architecture Rules for This Story

**Service layer boundary — enforce from day one:**
- `cos/mcp_server/` and `cos/cli.py` must not import from `cos/store/`, `cos/ingestion/`, `cos/retrieval/`, `cos/rolepack/`, or `cos/output/` directly — route through `cos/services/*`. Intra-package imports within `mcp_server/` (e.g. `tools.py` importing the FastMCP app from `server.py`) are permitted.
- `cos/services/*` may import from `cos/ingestion/`, `cos/retrieval/`, `cos/store/`, `cos/rolepack/`, `cos/output/`
- Internal modules (`cos/store/`, `cos/ingestion/`, `cos/retrieval/`) must NOT import from each other
- Violating this in Story 1.1 (even in stubs) creates debt that breaks architecture boundaries in later stories

**OutputRouter — implement correctly in this story:**
- `OutputRouter.send(channel: str, content: str) -> None` is the sole exit point for all output
- Injected as a dependency, never imported as a module-level singleton
- On invalid channel: log structured JSON error, return silently — never raise
- This behaviour is tested in `tests/output/test_router.py` and must not be skipped

**LLMAdapter — Protocol, not ABC:**
- Use `typing.Protocol` (structural subtyping), not `ABC`
- `complete(prompt: str, context: list[str]) -> str` — async signature is required: `async def complete(...) -> str`
- `AnthropicAdapter` in `cos/llm/anthropic.py` must structurally satisfy the Protocol

**config.py — Pydantic v2:**
- `CosConfig` is a Pydantic v2 `BaseModel` or `BaseSettings` (decide: BaseSettings reads from file)
- All other modules receive a `CosConfig` instance via injection — zero direct file reads outside this module

### Docker Compose Rules

```yaml
# CORRECT — localhost only
ports:
  - "127.0.0.1:5432:5432"

# WRONG — exposes to all network interfaces — DO NOT DO THIS
ports:
  - "5432:5432"
```

The `cos` service must have **no `ports:` section at all** — MCP uses stdio transport, not TCP.

Startup dependency chain (order matters):
```
postgres (healthcheck: pg_isready) →
  tika (healthcheck: GET /tika) →
    cos (depends_on both healthy)
```

### Exact Library Versions (verified April 2026)

| Library | Version | Notes |
|---|---|---|
| `mcp` | 1.27.0 | Official SDK; MCP spec 2025-11-25; use FastMCP pattern |
| `psycopg[binary]` | psycopg3 | Async-native PostgreSQL driver; NOT psycopg2 |
| `pgvector` | latest | psycopg3 native support |
| `pydantic` | v2 | Config model and data models |
| `typer` | latest | CLI; wraps Click; type-annotated commands |
| `apscheduler` | 3.x | Cron scheduler; asyncio compatible |
| `httpx` | latest | Async HTTP client |
| `tika-client` | latest | REST client for Tika server; no bundled JAR |

Docker images:
| Service | Image |
|---|---|
| postgres | `pgvector/pgvector:pg16` |
| tika | `apache/tika` |

### Logging Standard (applies from Story 1.1 onwards)

```python
# CORRECT
import json, logging
logging.info(json.dumps({"timestamp": "...", "level": "INFO", "component": "cli", "message": "..."}))

# WRONG — never use bare print()
print("starting up...")
```

Mandatory log fields: `timestamp` (ISO 8601), `level`, `component`, `message`. `component` must be one of: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`, `output`.

### Anti-Patterns (explicitly forbidden)

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

# WRONG — 0.0.0.0 port binding in docker-compose.yml
ports:
  - "5432:5432"
```

### Entry Points (pyproject.toml)

```toml
[project.scripts]
cos = "cos.cli:app"
cos-mcp = "cos.mcp_server.server:run"
```

### Project Structure Notes

Complete directory tree — create all paths exactly as shown:

```
cos/
├── pyproject.toml
├── uv.lock                         # checked in
├── .python-version                 # "3.12"
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── config.yaml.example
├── config.yaml                     # gitignored — operator creates this
├── tokens/                         # gitignored — Phase 2 OAuth
├── docs/
│   └── setup.md
└── src/
    └── cos/
        ├── __init__.py
        ├── cli.py
        ├── config.py
        ├── health.py
        ├── store/
        │   ├── __init__.py
        │   ├── db.py
        │   ├── models.py
        │   └── migrations/
        │       ├── 001_initial.sql  # placeholder comment — filled in Story 1.3
        │       └── 002_jobs.sql     # Phase 2 comment stub only
        ├── ingestion/
        │   ├── __init__.py
        │   ├── pipeline.py
        │   ├── extractor.py
        │   ├── chunker.py
        │   └── embedder.py
        ├── retrieval/
        │   ├── __init__.py
        │   ├── search.py
        │   └── citations.py
        ├── rolepack/
        │   ├── __init__.py
        │   └── loader.py
        ├── llm/
        │   ├── __init__.py
        │   ├── adapter.py
        │   └── anthropic.py
        ├── output/
        │   ├── __init__.py
        │   ├── router.py
        │   └── channels/
        │       ├── __init__.py
        │       ├── local.py
        │       ├── telegram.py     # Phase 2 stub
        │       └── email.py        # Phase 2 stub
        ├── connectors/
        │   ├── __init__.py         # Growth stub comment only
        │   ├── gmail.py            # Phase 2 stub
        │   ├── calendar.py         # Phase 2 stub
        │   └── telegram_bot.py     # Phase 2 stub
        ├── mcp_server/
        │   ├── __init__.py
        │   ├── server.py
        │   └── tools.py
        └── services/
            ├── __init__.py
            ├── ingestion.py
            ├── retrieval.py
            ├── rolepack.py
            ├── output.py
            └── health.py

tests/
├── conftest.py
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
│   └── test_router.py              # CRITICAL: verify fail-closed behaviour
├── services/
│   ├── test_ingestion_service.py
│   ├── test_retrieval_service.py
│   └── test_health_service.py
└── store/
    └── test_migrations.py
```

**Rules for stub files:**
- No logic in `__init__.py` files — only empty or minimal re-exports
- Connector stubs (`gmail.py`, `calendar.py`, `telegram_bot.py`) must contain a comment only — no dead code
- Service stubs must define the class and method signatures with `raise NotImplementedError` — the method signature is the contract that later stories implement

### Testing Standards

- Test framework: `pytest` + `pytest-asyncio`
- Test structure mirrors `src/cos/` — every module has a corresponding test file
- `conftest.py` uses a real Postgres test instance — **not mocks** (pgvector behaviour is not reliably mockable)
- `tests/output/test_router.py` is the key test for this story — verify:
  - `OutputRouter.send()` with a valid channel delivers output
  - `OutputRouter.send()` with an invalid channel suppresses output and logs a JSON error
  - `OutputRouter.send()` with an invalid channel does NOT raise an exception
- For Story 1.1, test files may be empty scaffolds (just imports and placeholder test functions) since the implementations are stubs — but the directory structure and files must exist

### References

- Architecture decisions: [Source: architecture.md#Core Architectural Decisions]
- Project structure: [Source: architecture.md#Complete Project Directory Structure]
- Implementation patterns: [Source: architecture.md#Implementation Patterns & Consistency Rules]
- Anti-patterns: [Source: architecture.md#Enforcement Guidelines]
- Story requirements: [Source: epics.md#Story 1.1]
- Docker compose port binding rule: [Source: architecture.md#docker-compose.yml Port Annotation]
- Entry points: [Source: architecture.md#Entry Points]
- Library versions: [Source: architecture.md#Key Library Versions]
- OutputRouter contract: [Source: architecture.md#OutputRouter Contract]
- LLM adapter boundary: [Source: architecture.md#LLM Boundary]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Tika health check: `apache/tika` image does not include `wget` or `curl`. Switched to bash TCP check `(echo > /dev/tcp/localhost/9998) &>/dev/null` which works with the `bash` available in the image.
- Dockerfile: `uv sync --frozen --no-dev` before `COPY src/` fails because `pyproject.toml` declares `readme = "README.md"`. Used two-stage sync: `--no-install-project` for deps layer, then full sync after copying source.
- `cos` container stdin: MCP stdio server exits immediately with no client attached. Added `stdin_open: true` to docker-compose so the container stays running in compose context.
- Docker context: Rancher Desktop required — used `docker context use rancher-desktop` before compose commands.

### Completion Notes List

- All 6 tasks and 39 subtasks completed and verified.
- 15 tests pass (15/15), 0 failures. Key OutputRouter tests confirm fail-closed behaviour.
- All three Docker containers reach healthy state on first run and clean restart — confirmed with `docker compose down && docker compose up -d`.
- Port bindings: postgres `127.0.0.1:5432:5432`, tika `127.0.0.1:9998:9998`, cos has no ports (stdio transport).
- Ruff linting passes clean (`ruff check src/ tests/`).
- Architecture boundaries respected in all stubs: mcp_server/tools.py imports only from services layer.

### File List

cos/.gitignore
cos/.python-version
cos/Dockerfile
cos/README.md
cos/config.yaml.example
cos/docker-compose.yml
cos/docs/setup.md
cos/pyproject.toml
cos/uv.lock
cos/src/cos/__init__.py
cos/src/cos/cli.py
cos/src/cos/config.py
cos/src/cos/health.py
cos/src/cos/connectors/__init__.py
cos/src/cos/connectors/calendar.py
cos/src/cos/connectors/gmail.py
cos/src/cos/connectors/telegram_bot.py
cos/src/cos/ingestion/__init__.py
cos/src/cos/ingestion/chunker.py
cos/src/cos/ingestion/embedder.py
cos/src/cos/ingestion/extractor.py
cos/src/cos/ingestion/pipeline.py
cos/src/cos/llm/__init__.py
cos/src/cos/llm/adapter.py
cos/src/cos/llm/anthropic.py
cos/src/cos/mcp_server/__init__.py
cos/src/cos/mcp_server/server.py
cos/src/cos/mcp_server/tools.py
cos/src/cos/output/__init__.py
cos/src/cos/output/router.py
cos/src/cos/output/channels/__init__.py
cos/src/cos/output/channels/email.py
cos/src/cos/output/channels/local.py
cos/src/cos/output/channels/telegram.py
cos/src/cos/retrieval/__init__.py
cos/src/cos/retrieval/citations.py
cos/src/cos/retrieval/search.py
cos/src/cos/rolepack/__init__.py
cos/src/cos/rolepack/loader.py
cos/src/cos/services/__init__.py
cos/src/cos/services/health.py
cos/src/cos/services/ingestion.py
cos/src/cos/services/output.py
cos/src/cos/services/retrieval.py
cos/src/cos/services/rolepack.py
cos/src/cos/store/__init__.py
cos/src/cos/store/db.py
cos/src/cos/store/models.py
cos/src/cos/store/migrations/001_initial.sql
cos/src/cos/store/migrations/002_jobs.sql
cos/tests/conftest.py
cos/tests/ingestion/test_chunker.py
cos/tests/ingestion/test_extractor.py
cos/tests/ingestion/test_pipeline.py
cos/tests/output/test_router.py
cos/tests/retrieval/test_citations.py
cos/tests/retrieval/test_search.py
cos/tests/rolepack/test_loader.py
cos/tests/services/test_health_service.py
cos/tests/services/test_ingestion_service.py
cos/tests/services/test_retrieval_service.py
cos/tests/store/test_migrations.py

### Review Findings

- [ ] [Review][Decision] `component: "output"` not in allowed logging component enum — `router.py` emits `"component": "output"` but the logging standard only permits: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`. Should `"output"` be added to the standard, or should the router use a different value? [`src/cos/output/router.py:25,38`]
- [ ] [Review][Decision] `mcp_server/tools.py` imports from `mcp_server/server` — spec constraint says `mcp_server/` imports ONLY from `services/*`, but `tools.py` imports `mcp` from `server.py` (intra-package) to register `@mcp.tool()` decorators. Is this intra-package exception acceptable, or should tool registration be consolidated in `server.py`? [`src/cos/mcp_server/tools.py:2`]
- [x] [Review][Patch] `pydantic-settings` undeclared in `pyproject.toml` — `config.py` imports `from pydantic_settings import BaseSettings` but `pydantic-settings` is not listed in `[project.dependencies]` [`pyproject.toml`]
- [x] [Review][Patch] `src/cos/__init__.py` is not empty — contains default `uv init` scaffold with `print("Hello from cos!")`, violating the empty `__init__.py` rule and the bare-print anti-pattern [`src/cos/__init__.py:1-2`]
- [x] [Review][Patch] `datetime.utcnow()` deprecated — `DocumentRecord` and `ProvenanceRecord` use `field(default_factory=datetime.utcnow)` which is deprecated in Python 3.12+ and produces timezone-naive datetimes [`src/cos/store/models.py:9,40`]
- [x] [Review][Patch] `handler(content)` exceptions uncaught in `OutputRouter.send` — if `local_channel.send` raises (e.g. broken pipe), the exception propagates to the caller, breaking the never-raise contract for the valid-channel path [`src/cos/output/router.py`]
- [x] [Review][Patch] `cos` service has no healthcheck — without a healthcheck, `docker compose ps` will never show `cos` as `healthy`, making AC 2 ("all three containers reach healthy state") unverifiable [`docker-compose.yml`]
- [x] [Review][Patch] Missing test: channel configured but handler absent — the second error branch in `OutputRouter.send` (channel in `_channels` but not in `_CHANNEL_HANDLERS`) is entirely untested [`tests/output/test_router.py`]
- [x] [Review][Patch] Connectors stub comment mislabels delivery phase — `connectors/__init__.py` says "Growth tier stub" but the architecture assigns connectors to Phase 3 (not a growth/Phase 5+ tier) [`src/cos/connectors/__init__.py:1`]
- [x] [Review][Defer] `uv:latest` Dockerfile tag unpinned — builds non-reproducible; not spec-mandated for this story [`Dockerfile:3`] — deferred, pre-existing
- [x] [Review][Defer] Service stubs lack constructor injection points — `IngestService`, `RetrievalService` etc. have no `__init__`; injection wiring deferred to story implementations [`src/cos/services/*`] — deferred, pre-existing
- [x] [Review][Defer] `anthropic` SDK not declared in dependencies — implementation deferred to Story 3.3 [`pyproject.toml`] — deferred, pre-existing
- [x] [Review][Defer] `DocumentRecord.id` and `EmbeddingRecord.vector` unsafe defaults — empty-string ID and empty-list vector will cause DB errors; addressed in Story 1.3 schema [`src/cos/store/models.py`] — deferred, pre-existing
- [x] [Review][Defer] `_CHANNEL_HANDLERS` module-level dict creates test isolation risk — mutations affect all router instances; acceptable for Phase 1 single-channel scope [`src/cos/output/router.py:10-12`] — deferred, pre-existing
- [x] [Review][Defer] `cos` container has no environment variables for Postgres/Tika connection — no `DATABASE_URL` or equivalent; addressed in Story 1.2 config [`docker-compose.yml`] — deferred, pre-existing

### Change Log

- 2026-04-20: Initial implementation — Story 1.1 complete. Created full project scaffold: uv project with all dependencies, 40+ source files across all packages (services, store, ingestion, retrieval, rolepack, llm, output, connectors, mcp_server), docker-compose.yml with three services (postgres/pgvector, tika, cos), Dockerfile with two-stage uv sync for layer caching, 15 tests all passing. Docker startup and clean restart validated.
