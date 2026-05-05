---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories']
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
---

# CoS - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Chief of Staff AI Platform, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

_Items marked (Growth) are Phase 2. All others are Phase 1 MVP._

**Knowledge Ingestion**

FR1: Operator can ingest a single file or a folder of files into the knowledge base via CLI
FR2: System extracts text and metadata from PDF, Word document, Markdown, and plain text files during ingestion
FR3: System normalises all ingested content to a Markdown working copy stored alongside the original
FR4: System stores the original source file unchanged and permanently in the document store
FR5: System records provenance metadata for each ingested document and source reference, including source locator or external ID, ingestion timestamp, content hash, and version number where applicable
FR6: System creates a new version record when the same logical source is re-ingested with changed content, preserving all prior versions
FR7: System performs exact-byte deduplication across all ingestion sources and avoids re-embedding or duplicating canonically identical content
FR8: System flags ingested content as a semantic near-duplicate when it exceeds a configurable similarity threshold against existing content and does not silently re-index it (Growth)
FR9: User can ingest a short note or thought as a document by sending a message via a connected messaging channel (Growth)
FR10: System ingests email message bodies and attachments received via a connected email account (Growth)

**Knowledge Retrieval**

FR11: User can submit a natural language query and receive a grounded answer with source citations
FR12: System retrieves relevant content using both keyword and semantic (embedding-based) search
FR13: System includes document-level and chunk-level citations in every retrieval response
FR14: System applies role pack retrieval priorities when ranking search results
FR15: User can list all documents currently in the knowledge base with their metadata
FR16: System can invoke a web search to augment local retrieval when local retrieval returns fewer than a configured minimum number of relevant cited results (Growth)

**Reasoning & Output**

FR17: System synthesises retrieved content into a response that matches the active role pack's tone and style
FR18: System can produce common workflow outputs: summary, briefing, draft, comparison, and prioritisation
FR19: System delivers a scheduled briefing at a configured time via a configured output channel (Growth)
FR20: System prepares meeting context from upcoming calendar events at a configured interval before each meeting (Growth)
FR21: System only delivers output to explicitly configured channels or the local interface — no uncontrolled output paths

**Role Pack Management**

FR22: Operator can define a role pack in a configuration file specifying role goals, tone and style rules, knowledge taxonomy, active workflows, stakeholder map, and retrieval priorities
FR23: Operator can activate a different role pack by updating the configuration file, without modifying application code
FR24: System loads and applies the active role pack at startup across all retrieval and reasoning operations
FR25: User can retrieve a summary of the currently active role context via the platform interface

**Platform Operations**

FR26: Operator can check the health status of all platform components with a single CLI command
FR27: Operator can restart all platform components with a single CLI command
FR28: Operator can retrieve diagnostic logs with a single CLI command, in a format suitable for support handoff
FR29: System reports component failures with a recovery message that names the failing component, states the user-visible impact, and provides specific recovery steps
FR30: Operator can provision a complete new platform instance through a single documented bootstrap command or workflow
FR31: Operator can configure all platform settings — API keys, role pack path, output channel config, connector credentials — through a single human-editable configuration artifact

**External Connectivity (Growth)**

FR32: System reads upcoming events from a connected Google Calendar account for use in meeting prep and scheduled briefs
FR33: System reads and ingests email messages and attachments from a connected Gmail account
FR34: User can send a question or note to the platform via Telegram and receive a response
FR35: System sends scheduled briefs and digests to a user via a configured Telegram or email channel

**Security & Governance**

FR36: System enforces egress control — responses are delivered only to configured output channels or the local interface
FR37: System preserves all ingested source documents permanently — originals are never modified or deleted
FR38: Operator can view the full list of ingested documents with their provenance metadata and version history

### Non-Functional Requirements

**Performance**

NFR1: Retrieval queries return a response within 5 seconds under normal operating conditions (local deployment, knowledge base up to 10,000 documents)
NFR2: Document ingestion processes at a rate of at least 10 documents per minute for standard file types (PDF, Word, Markdown) on typical consumer hardware
NFR3: The MCP server responds to tool calls within 2 seconds for non-retrieval operations (`get_status`, `get_role_context`, `list_documents`)
NFR4: System startup from a clean deployment state completes within 60 seconds with all required services healthy and ready to serve

**Security**

NFR5: API keys and connector credentials are stored only in the local configuration file and are never logged, included in responses, or transmitted beyond their intended API endpoint
NFR6: All LLM API calls are made over HTTPS — no plaintext transmission of document content to external providers
NFR7: Output is delivered exclusively to channels listed in the active configuration — the system must fail closed (suppress output) rather than fail open (deliver to an unintended destination) if a channel is misconfigured
NFR8: The platform does not expose any network ports beyond localhost by default in its standard deployment configuration

**Reliability**

NFR9: The platform recovers to a fully operational state within 30 seconds of a `cos restart` command under normal conditions
NFR10: A failure in any single non-core component (e.g. ingestion worker crash) does not make the MCP server or retrieval layer unavailable for more than 30 seconds under normal recovery conditions
NFR11: Connector failures (Gmail API unavailable, Telegram bot unreachable) surface an explicit degraded-status or error signal within 60 seconds while the core retrieval and Q&A path remains available regardless of connector state (Growth)
NFR12: The system preserves knowledge base integrity across unclean shutdowns — no partial ingestion records or corrupted embeddings result from a container crash

**Maintainability**

NFR13: The complete platform can be provisioned on a new machine by a technically competent person following the setup documentation, without assistance, in under 2 hours
NFR14: Routine operation requires no scheduled manual intervention during a 7-day normal-use period after startup
NFR15: All configuration is expressed in a single human-editable configuration file — no environment-specific code changes are required to switch roles, providers, or channels
NFR16: The platform is deployable on a cloud Linux VM using the standard deployment package and configuration model used locally, without code changes

**Integration**

NFR17: The MCP server conforms to the published MCP specification and passes an interoperability test against Claude Desktop for the supported tool set
NFR18: The embedding model is configurable — switching providers requires only a config change, not a code change
NFR19: The LLM provider is configurable — the platform works with any provider supported by the model adapter without modifying ingestion, storage, or retrieval components
NFR20: External connector credentials (Google OAuth tokens, Telegram bot token) are stored and refreshed locally without requiring re-authorisation during a 30-day normal-operation period (Growth)

### Additional Requirements

_Technical requirements from the Architecture document that affect implementation._

- **Project initialisation:** Use `uv init --app --package cos` with a `src/` layout. First story is: run uv init, add all dependencies, create docker-compose.yml with three services (postgres + pgvector, tika, cos), validate `docker compose up` reaches healthy state.
- **Language & runtime:** Python 3.12+ pinned via `.python-version`; async-first throughout using asyncio; `asyncio.run()` only at entry points (cli.py, mcp_server/server.py).
- **Three-container Docker Compose:** `postgres` (pgvector/pgvector:pg16), `tika` (apache/tika), `cos` (Python/uv image). All ports bind to 127.0.0.1 only; MCP server uses stdio transport (no host port).
- **Startup sequence dependency:** Postgres healthcheck (`pg_isready`) → Tika healthcheck (`GET /tika`) → cos (`depends_on` both healthy). MCP server applies migrations then starts FastMCP.
- **Canonical identity model:** Canonical identity is split across `documents`, `document_versions`, `content_blobs`, `sources`, and `source_versions` (or an equivalent additive linking model). `source_path`, filename, and connector locator must not become the effective canonical key.
- **Database strategy:** Raw SQL + numbered migration files in `cos/store/migrations/`; no ORM. Migrations applied idempotently at cos startup (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`). Identity-hardening migration must land before connector stories proceed. `documents.status` column exists from day one; `jobs` table remains deferred to Phase 2.
- **Hash-first ingest:** `content_blobs` use UUID primary keys plus unique SHA-256 hashes. Exact-byte deduplication happens before chunking, embedding, and managed-copy writes.
- **Managed storage layout:** Canonical originals and Markdown working copies are stored by internal ID/hash, never by inbound filenames or connector-provided names. Known content reuses the existing managed copies instead of writing duplicates.
- **Deterministic ingest outcomes:** The ingest workflow must explicitly resolve four cases: new source + new content, known source + unchanged content, known source + changed content, and new source + known content.
- **Chunking defaults:** 1024 tokens per chunk, 100 token overlap. Configurable via CosConfig.
- **Service layer boundary:** `cos/services/*` is the only permitted cross-module import path. `cos/mcp_server/` and `cos/cli.py` import only from `cos/services/*`. Internal modules (`cos/store/`, `cos/ingestion/`, `cos/retrieval/`) never import from each other.
- **Config boundary:** `CosConfig` (Pydantic v2) in `cos/config.py` reads `config.yaml` once at startup. No other module reads config.yaml directly. `config.yaml` is gitignored; `config.yaml.example` is the committed template documenting all required keys.
- **OutputRouter:** Sole exit point for all user-facing output. Injected as dependency (not a module-level singleton). Validates channel against configured channels; suppresses and logs on invalid channel (fail-closed). Never raises an unhandled exception.
- **LLM adapter boundary:** `LLMAdapter` protocol in `cos/llm/adapter.py` defines the `complete()` contract. `cos/llm/anthropic.py` is the Phase 1 Claude implementation. Swapping provider = new implementation file + config change only.
- **MCP server pattern:** FastMCP pattern from official MCP SDK 1.27.0. Tools: `retrieve`, `get_role_context`, `list_documents`, `get_status`. All tools return the standard envelope: `{"status": "ok/error", "data": {...}, "citations": [...]}`. No custom response shapes.
- **Citation integrity:** Retrieval results must cite `document_version` plus source provenance cleanly, using `source_alias` for user-facing listing/citation labels while preserving connector-specific locators underneath.
- **Logging:** Structured JSON to stdout. Mandatory fields: `timestamp`, `level`, `component`, `message`. No bare `print()` calls anywhere. `component` must be one of: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`.
- **Connectors stub:** `cos/connectors/` exists as a stub directory from Phase 1 with a placeholder `__init__.py` only — no dead code.
- **OAuth tokens:** `tokens/` directory for OAuth credentials (gitignored); separate from `config.yaml` because tokens are rotated by the auth library (dynamic) while config is hand-edited (static). Phase 2 only.
- **Migration/backfill expectation:** Existing path-centric Phase 1 data must be migrated onto the canonical identity model before Epic 6 connector work begins, with operator recovery documentation covering backfill and re-run behaviour.
- **Setup documentation:** `docs/setup.md` required — non-technical user setup and restart instructions. Covers provisioning, `cos status`, `cos restart`, `cos logs`, and the three-step restart procedure.
- **Test structure:** `tests/` at root mirroring `src/cos/`. `conftest.py` uses a real Postgres test instance (not mocks — pgvector behaviour is not reliably mockable). Key test: `tests/output/test_router.py` verifies fail-closed behaviour.
- **Entry points:** `pyproject.toml` scripts: `cos = "cos.cli:app"` and `cos-mcp = "cos.mcp_server.server:run"`.
- **Naming conventions:** DB: snake_case tables (plural), snake_case columns, UUID PKs (`gen_random_uuid()`), FK pattern `{table_singular}_id`, index pattern `idx_{table}_{columns}`. Python: snake_case modules/functions/variables, PascalCase classes, UPPER_SNAKE_CASE constants.

### UX Design Requirements

_Not applicable — this is an API backend platform with no UI. The primary interface is Claude Desktop (MCP client) and a terminal CLI. No UX design document exists._

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 2 | CLI ingest file/folder |
| FR2 | Epic 2 | Extract PDF, Word, Markdown, plain text |
| FR3 | Epic 2 | Normalise to Markdown working copy |
| FR4 | Epic 2 | Store original unchanged permanently |
| FR5 | Epic 2 | Record provenance metadata for document and source references |
| FR6 | Epic 2 | Version record on re-ingest of the same logical source |
| FR7 | Epic 6 | Exact-byte deduplication across ingestion sources |
| FR8 | Epic 6 | Semantic near-duplicate warning layer (Growth) |
| FR9 | Epic 7 | Note capture via Telegram (Growth) |
| FR10 | Epic 6 | Email ingestion via Gmail (Growth) |
| FR11 | Epic 3 | Natural language query → cited answer |
| FR12 | Epic 3 | Hybrid keyword + semantic search |
| FR13 | Epic 3 | Document + chunk-level citations |
| FR14 | Epic 3 | Role pack retrieval priorities |
| FR15 | Epic 3 | List documents with metadata |
| FR16 | Epic 7 | Web search augmentation (Growth) |
| FR17 | Epic 3 | Synthesise response in role pack tone |
| FR18 | Epic 3 | Common workflow outputs |
| FR19 | Epic 7 | Scheduled briefing via channel (Growth) |
| FR20 | Epic 7 | Meeting prep from calendar (Growth) |
| FR21 | Epic 3 | Egress control — configured channels only |
| FR22 | Epic 4 | Define role pack in config file |
| FR23 | Epic 4 | Activate different role pack, no code change |
| FR24 | Epic 4 | Load and apply role pack at startup |
| FR25 | Epic 4 | Retrieve active role context summary |
| FR26 | Epic 5 | Health status — single CLI command |
| FR27 | Epic 5 | Restart — single CLI command |
| FR28 | Epic 5 | Diagnostic logs — single CLI command |
| FR29 | Epic 5 | Plain-language recovery messaging |
| FR30 | Epic 1 | Platform bootstrap/provisioning workflow |
| FR31 | Epic 1 | Single human-editable config artifact |
| FR32 | Epic 6 | Google Calendar read (Growth) |
| FR33 | Epic 6 | Gmail read and ingest (Growth) |
| FR34 | Epic 7 | Telegram Q&A and note capture (Growth) |
| FR35 | Epic 7 | Scheduled briefs via configured Telegram or email channel (Growth) |
| FR36 | Epic 3 | Enforce egress control |
| FR37 | Epic 2 | Originals never modified or deleted |
| FR38 | Epic 2 | View documents with provenance history |

## Implementation Baseline Context

Epics 1 through 5 are already implemented and should be read as the historical baseline that existed before the canonical identity / exact-byte deduplication strategy correction. Their story text records what was built; it is not the target contract for new development.

Epic 6 is the migration and hardening pivot:
- it upgrades the implemented path-centric baseline to the canonical identity model defined in `architecture.md`
- it establishes the post-migration provenance contract for listings and citations
- no connector or ambient-intelligence story should introduce new user-facing contract assumptions that bypass Epic 6

For Epic 6 onward, the authoritative user-facing provenance contract is:
- `document_version_id` identifies the cited canonical version
- `source_alias` is the primary human-readable label in `retrieve`, `list_documents`, and `cos docs`
- `source_locator` is retained underneath for traceability, debugging, and connector-specific provenance
- legacy `source_path` behavior from the implemented baseline is treated as migration input, not the desired end state

## Epic List

## Epic 1: Runnable Platform Foundation

Operator can stand up a fully healthy CoS instance from scratch with a single documented bootstrap flow — all containers running, config loaded, migrations applied, and the MCP server ready to accept connections from Claude Desktop or Claude Code.
**FRs covered:** FR30, FR31
**NFRs:** NFR4, NFR8, NFR10, NFR13, NFR15, NFR16
**Architecture requirements:** uv project initialisation, three-container Docker Compose, DB migration runner, CosConfig, service layer interfaces, LLMAdapter protocol, OutputRouter interface, MCP server skeleton

### Story 1.1: Project Scaffold, Containerised Services & Core Interfaces

As an operator,
I want to run `docker compose up -d` and have all three platform services start and reach a healthy state,
So that I have a correctly structured, dependency-resolved foundation on which to build the knowledge platform.

**Acceptance Criteria:**

**Given** a new machine with Docker and uv installed,
**When** `uv init --app --package cos` is run followed by `uv add mcp psycopg[binary] pgvector pydantic typer apscheduler httpx tika-client` and `uv add --dev pytest pytest-asyncio ruff mypy`,
**Then** a `pyproject.toml` is created with `cos` and `cos-mcp` defined as entry points in `[project.scripts]`, and a `uv.lock` file is committed.

**Given** a `docker-compose.yml` defining `postgres` (pgvector/pgvector:pg16), `tika` (apache/tika), and `cos` services,
**When** `docker compose up -d` is run,
**Then** all three containers reach a healthy state within 60 seconds as reported by `docker compose ps`.

**Given** the Docker Compose configuration,
**When** the port bindings are inspected,
**Then** all bound ports use `127.0.0.1` (e.g. `127.0.0.1:5432:5432`), never `0.0.0.0`, and the `cos` service exposes no host ports at all (MCP uses stdio transport).

**Given** the `src/cos/` package structure is created,
**When** the directory is inspected,
**Then** it contains `cos/services/` with stub files `ingestion.py`, `retrieval.py`, `rolepack.py`, `output.py`, and `health.py` — each defining a service class with method signatures that raise `NotImplementedError`.

**Given** the core interface files are created,
**When** `cos/llm/adapter.py` is inspected,
**Then** it defines an `LLMAdapter` protocol with a typed `complete()` method, and `cos/llm/anthropic.py` contains a stub `AnthropicAdapter` implementing the protocol.

**Given** `cos/output/router.py` is created,
**When** it is inspected,
**Then** it contains an `OutputRouter` class with a `send(channel: str, content: str) -> None` method that validates the channel against config and suppresses output (logging a structured JSON error) if the channel is not configured — it never raises an unhandled exception.

**Given** `cos/connectors/__init__.py` is created,
**When** it is inspected,
**Then** it is a placeholder file with a comment marking it as a Growth tier stub and contains no implementation code.

**Given** `docker compose down` followed by `docker compose up -d` is run,
**When** the containers reach healthy state,
**Then** no manual intervention is required between the two runs.

---

### Story 1.2: Configuration Loader

As an operator,
I want all platform settings — API keys, role pack path, output channels, LLM and embedding provider config — defined in a single `config.yaml` file,
So that I can reconfigure the platform for a different role, provider, or channel without modifying any code.

**Acceptance Criteria:**

**Given** a `config.yaml` file with all required keys present,
**When** the `cos` container starts,
**Then** `CosConfig` loads and validates the file using Pydantic v2, and the validated config object is available for injection into all components.

**Given** a `config.yaml` with a missing required key (e.g. no `llm` section),
**When** the container starts,
**Then** startup fails immediately with a clear, human-readable Pydantic validation error identifying the missing field — not a cryptic Python traceback.

**Given** a committed `config.yaml.example` template,
**When** an operator copies it to `config.yaml` and fills in their API keys and role pack path,
**Then** the platform starts successfully using those settings.

**Given** `config.yaml` contains API keys,
**When** the platform is running under normal operation,
**Then** no key value appears in any log output, MCP response, or diagnostic output.

**Given** any module in the codebase other than `cos/config.py`,
**When** imports are inspected,
**Then** no module reads `config.yaml` directly — all config access goes through the `CosConfig` instance.

**Given** `.gitignore` is present,
**When** it is inspected,
**Then** `config.yaml` and `tokens/` are listed as ignored entries, and `config.yaml.example` is not ignored.

---

### Story 1.3: Database Schema & Migration Runner

As an operator,
I want the platform to create and maintain its database schema automatically on every startup,
So that no manual database setup steps are required when provisioning a new instance or restarting the platform.

**Historical baseline note:** This story records the already-implemented pre-Epic 6 baseline schema. Story 6.1 intentionally migrates this baseline to the canonical identity model; do not treat this story as the target schema for new development.

**Acceptance Criteria:**

**Given** the `cos` container starts with a healthy Postgres connection sourced from `CosConfig`,
**When** the MCP server initialises,
**Then** `001_initial.sql` is applied, creating the `documents`, `document_versions`, `chunks`, and `embeddings` tables with correct column definitions, UUID primary keys (`gen_random_uuid()`), foreign key relationships, and the `CREATE EXTENSION IF NOT EXISTS vector` statement.

**Given** the `documents` table is created,
**When** the schema is inspected,
**Then** it includes a `status` column (text) from the start, alongside `id`, `source_path`, `file_hash`, `ingested_at`, and `current_version`.

**Given** the `embeddings` table is created,
**When** the schema is inspected,
**Then** it includes `model` and `provider` columns alongside the `vector` column, enabling future embedding provider tracking and re-embedding operations.

**Given** `001_initial.sql` has already been applied and the container restarts,
**When** migrations run again at startup,
**Then** all statements complete without error and the schema is unchanged — all DDL uses `IF NOT EXISTS` or `ON CONFLICT DO NOTHING` guards.

**Given** a stub `002_jobs.sql` migration file exists in `cos/store/migrations/`,
**When** it is inspected,
**Then** it contains only a comment marking it as a Phase 2 placeholder and no executable SQL — confirming the jobs table design is deferred but the file location is established.

**Given** a container crash occurs mid-ingestion (simulated by killing the container),
**When** the container restarts,
**Then** the migration runner completes without error and no partial schema state is left behind.

---

### Story 1.4: MCP Server Foundation

As an operator,
I want Claude Desktop or Claude Code to connect to the platform and discover its available tools,
So that I have a working MCP query interface ready for the retrieval and ingestion stories that follow.

**Acceptance Criteria:**

**Given** the `cos` container is running with a valid `config.yaml` and healthy Postgres,
**When** `cos-mcp` starts as the container entry point,
**Then** a FastMCP server starts using the official MCP SDK 1.27.0 FastMCP pattern, listens on stdio transport, and logs a structured JSON startup message with `component: "mcp_server"`.

**Given** Claude Desktop or Claude Code is configured to connect to the CoS MCP server,
**When** the client is opened,
**Then** it connects successfully and lists exactly four tools: `retrieve`, `get_role_context`, `list_documents`, and `get_status`.

**Given** a connected MCP client calls `get_status`,
**When** the tool executes,
**Then** it returns a response in the standard envelope: `{"status": "ok", "data": {"components": [...], "ready": true}, "citations": []}`.

**Given** a connected MCP client calls `retrieve`, `get_role_context`, or `list_documents` (not yet fully implemented),
**When** the tool executes,
**Then** it returns `{"status": "error", "error": "Not yet implemented", "detail": "..."}` — not an unhandled exception and not a protocol-level error.

**Given** the MCP server is running,
**When** startup and tool-call log output is inspected,
**Then** all entries are structured JSON with `timestamp`, `level`, `component`, and `message` fields — no bare `print()` calls anywhere in the codebase.

**Given** the startup sequence runs,
**When** logs are inspected,
**Then** the sequence is confirmed: Postgres healthy → Tika healthy → CosConfig loaded → migrations applied → role pack stub loaded → MCP server listening.

---

### Story 1.5: Operator Validation — Platform Boots End-to-End

As Iain (operator and first user),
I want to run a documented smoke test of the assembled platform foundation,
So that I can confirm the complete system is correctly wired up before building the ingestion pipeline.

**Acceptance Criteria:**

**Given** a clean machine with Docker and uv installed and `config.yaml` populated from `config.yaml.example`,
**When** `docker compose up -d` is run,
**Then** all three containers (`postgres`, `tika`, `cos`) show as `healthy` in `docker compose ps` within 60 seconds — without any manual intervention.

**Given** Claude Desktop or Claude Code is configured with the CoS MCP server,
**When** the client is opened after `docker compose up -d`,
**Then** the four tools (`retrieve`, `get_role_context`, `list_documents`, `get_status`) are visible and callable.

**Given** `get_status` is called from the MCP client,
**When** the response is received,
**Then** it is valid JSON with `status: "ok"`, lists all three containers as healthy, and contains no error fields.

**Given** the platform has been running and `docker compose down` is run,
**When** `docker compose up -d` is run again,
**Then** all containers reach healthy state again with no manual database repair, migration commands, or file deletions needed.

**Given** `docker compose logs cos` is run during normal operation,
**When** the output is inspected,
**Then** every log line is valid JSON — no plain text lines, no unhandled exception tracebacks, no bare print output.

**Given** an incorrect or missing value is introduced into `config.yaml`,
**When** `docker compose up -d` is run,
**Then** the `cos` container fails to start and `docker compose logs cos` shows a clear, human-readable validation error identifying the bad field.

---

### Story 1.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all documentation to accurately reflect the platform as built at the end of Epic 1,
So that any technically competent person can provision, configure, and operate the platform foundation without assistance.

**Acceptance Criteria:**

**Given** `docs/setup.md` is created,
**When** it is reviewed,
**Then** it covers: prerequisites (Docker, uv), cloning the repo, copying `config.yaml.example` to `config.yaml` and filling in required values, running `docker compose up -d`, verifying health with `docker compose ps`, configuring Claude Desktop or Claude Code to connect to the MCP server, and the three-step restart procedure (`docker compose down` → `docker compose up -d` → verify).

**Given** the root `README.md` is created or updated,
**When** it is reviewed,
**Then** it describes what the platform is, the current Phase 1 capabilities, how to get started (link to `docs/setup.md`), and the project structure at a high level — accurate to what was actually built, not the full roadmap.

**Given** any decisions or implementation details that deviated from `architecture.md` during Epic 1 stories,
**When** `architecture.md` is reviewed,
**Then** those deviations are documented: either the architecture is updated to reflect the actual decision, or a note is added explaining why the spec was not followed and what was done instead.

**Given** the `config.yaml.example` template,
**When** it is reviewed,
**Then** every key required by `CosConfig` is present with a descriptive comment, the file is complete enough that a new operator can fill it in without reading source code, and it matches the actual `CosConfig` Pydantic model exactly.

**Given** all Epic 1 stories are complete,
**When** `docs/setup.md`, `README.md`, `architecture.md`, and `config.yaml.example` are reviewed together,
**Then** there are no contradictions between them — version numbers, file paths, command syntax, and capability descriptions are consistent across all four documents.

## Epic 2: Document Knowledge Base

Operator can ingest local documents into an immutable, versioned knowledge base and audit provenance/history from the CLI.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR37, FR38
**NFRs:** NFR2, NFR12

### Story 2.1: Document Extraction & Markdown Normalisation

As an operator,
I want the platform to extract text from any common document format and store both the original and a Markdown working copy,
So that all ingested knowledge is preserved immutably and available in a consistent format for downstream processing.

**Acceptance Criteria:**

**Given** a PDF file is passed to the extraction layer,
**When** `extractor.py` sends it to the Tika server via `tika-client`,
**Then** the response contains extracted plain text and document metadata (title, author, content-type where available), with no error for well-formed PDFs.

**Given** a Word document (.docx), a Markdown file (.md), and a plain text file (.txt) are each passed to the extraction layer,
**When** extraction runs,
**Then** each returns extracted text content — Markdown and plain text files bypass Tika and are read directly.

**Given** extraction succeeds for a document,
**When** the extractor writes to the filesystem,
**Then** the original file is written unchanged to the configured originals directory (bind mount), and a Markdown working copy is written to the Markdown copies directory — both on the host filesystem so they survive container restarts.

**Given** a document is written to the originals directory,
**When** the file is subsequently inspected,
**Then** its contents are byte-for-byte identical to the source file — no modification, compression, or re-encoding has occurred.

**Given** Tika is unavailable (container not healthy),
**When** extraction is attempted,
**Then** the extractor raises a structured exception that the service layer catches and logs — it does not silently return empty content or write a blank working copy.

---

### Story 2.2: Text Chunking & Embedding Pipeline

As an operator,
I want extracted document text to be split into appropriately sized chunks and converted to vector embeddings,
So that the knowledge base supports both semantic and keyword search across all ingested content.

**Acceptance Criteria:**

**Given** a Markdown text string is passed to `chunker.py`,
**When** chunking runs with the default configuration,
**Then** the text is split into chunks of approximately 1024 tokens with a 100-token overlap between adjacent chunks, and each chunk carries its `chunk_index` and `token_count`.

**Given** a document shorter than 1024 tokens,
**When** chunking runs,
**Then** it produces a single chunk containing the full text — no empty or near-empty padding chunks are created.

**Given** a list of chunks is passed to `embedder.py`,
**When** the embedding provider is called,
**Then** each chunk is converted to a vector using the provider and model specified in `CosConfig`, and the result carries the `model` and `provider` fields alongside the vector.

**Given** `CosConfig` specifies a different embedding provider or model,
**When** the embedder is instantiated,
**Then** it uses the configured provider without any code changes — only the config value changes.

**Given** the embedding provider API is unavailable,
**When** embedding is attempted,
**Then** the embedder raises a structured exception that propagates to the service layer — it does not return zero-vectors or silently degrade.

---

### Story 2.3: Provenance Storage & Transactional Writes

As an operator,
I want every ingested document and its chunks to be stored with full provenance in a single atomic transaction,
So that the knowledge base is never left in a partial or inconsistent state, even if the container crashes mid-ingest.

**Historical baseline note:** This story records the already-implemented pre-Epic 6 ingest semantics. Stories 6.2 and 6.3 intentionally replace the unchanged-content re-ingest behavior with canonical no-op handling and exact-byte deduplication across sources.

**Acceptance Criteria:**

**Given** a successfully extracted and chunked document,
**When** the store layer writes it to Postgres,
**Then** a single transaction inserts: one `documents` row, one `document_versions` row, N `chunks` rows (one per chunk), and N `embeddings` rows — all committed together or not at all.

**Given** the transaction is committed,
**When** the `documents` row is inspected,
**Then** it contains `source_path`, `file_hash` (SHA-256 of the original file bytes), `ingested_at` (ISO 8601 UTC), `current_version` (1 for first ingest), and `status: "indexed"`.

**Given** the same file is ingested a second time (matching `source_path` and `file_hash`),
**When** the store layer runs,
**Then** a new `document_versions` row is created with an incremented `version_number`, the `documents` row `current_version` is updated, and the prior version's chunks and embeddings remain untouched in the database.

**Given** an error occurs mid-transaction (simulated by killing the DB connection after the `documents` insert but before `chunks` are written),
**When** the container restarts and ingestion is retried,
**Then** no orphaned `documents` row without corresponding chunks exists — the transaction was fully rolled back.

**Given** a document whose original file is already present in the originals directory,
**When** re-ingestion is triggered,
**Then** the existing original file is not overwritten or deleted — a new version record is created pointing to the same or a new path.

---

### Story 2.4: CLI Ingest Command & IngestService

As an operator,
I want to ingest a single file or an entire folder of documents with a single CLI command,
So that I can load my knowledge base quickly without writing any code or interacting with the database directly.

**Acceptance Criteria:**

**Given** a single file path is passed to `cos ingest <path>`,
**When** the command runs,
**Then** `IngestService.ingest_file()` orchestrates the full pipeline (extract → chunk → embed → store) and the CLI prints a plain-language summary: e.g. `Ingested strategy.pdf → 24 chunks indexed`.

**Given** a folder path is passed to `cos ingest <folder>`,
**When** the command runs,
**Then** every supported file in the folder (PDF, .docx, .md, .txt) is ingested in sequence, with per-file progress printed, and a final summary showing total files processed and total chunks indexed.

**Given** a folder contains unsupported file types (e.g. `.xlsx`, `.png`),
**When** `cos ingest <folder>` runs,
**Then** unsupported files are skipped with a plain-language notice (e.g. `Skipped report.xlsx — unsupported format`) and processing continues for supported files.

**Given** a folder of 10 standard documents (mix of PDF, Word, Markdown) is ingested,
**When** ingestion completes,
**Then** the elapsed time is consistent with a rate of at least 10 documents per minute on the test machine.

**Given** a file path that does not exist is passed to `cos ingest`,
**When** the command runs,
**Then** the CLI prints a plain-language error message identifying the missing file and exits with a non-zero status code — no stack trace is shown to the user.

**Given** any call to `cos ingest`,
**When** log output is inspected,
**Then** all structured log entries use `component: "ingestion"` and no raw `print()` calls appear.

---

### Story 2.5: Document Provenance Listing

As an operator,
I want to list all ingested documents with their provenance metadata and version history from the CLI,
So that I can verify what is in the knowledge base, confirm ingestion succeeded, and audit the source of any document.

**Acceptance Criteria:**

**Given** one or more documents have been ingested,
**When** `cos docs` is run,
**Then** the CLI prints a table showing each document's `source_path`, `ingested_at`, `current_version`, and chunk count — one row per document, ordered by most recently ingested first.

**Given** a document that has been re-ingested (has multiple versions),
**When** `cos docs --versions <document_id>` is run,
**Then** the CLI prints all version records for that document, showing `version_number`, `ingested_at`, `file_hash`, and `extraction_method` for each version.

**Given** no documents have been ingested yet,
**When** `cos docs` is run,
**Then** the CLI prints a clear, friendly message such as `No documents ingested yet. Run: cos ingest <path>` — not an empty table or error.

**Given** `cos docs` is run,
**When** the output format is inspected,
**Then** it is human-readable plain text suitable for terminal display — not raw JSON unless a `--json` flag is passed.

---

### Story 2.6: Operator Validation — Documents Ingested & Provenance Verified

As Iain (operator and first user),
I want to run a documented smoke test of the complete ingestion pipeline,
So that I can confirm documents are correctly extracted, stored, and retrievable before building the retrieval layer.

**Acceptance Criteria:**

**Given** a small set of test documents (at least one PDF, one Word doc, one Markdown file) and the platform running,
**When** `cos ingest ./test-docs/` is run,
**Then** all three files are ingested without error, per-file progress is shown in the terminal, and a final summary reports the total files and chunks indexed.

**Given** ingestion has completed,
**When** `cos docs` is run,
**Then** all three test documents appear in the output with correct `source_path`, a recent `ingested_at` timestamp, `current_version: 1`, and a non-zero chunk count for each.

**Given** one of the test documents is ingested a second time,
**When** `cos docs --versions <document_id>` is run,
**Then** two version records are shown for that document with incrementing `version_number` values, and both originals remain on the filesystem.

**Given** the `originals` directory on the host filesystem is inspected after ingestion,
**When** the files are compared to the source files,
**Then** all original files are present, unchanged, and none have been modified or deleted.

**Given** the `cos` container is killed mid-ingest (using `docker kill`) and restarted,
**When** `cos docs` is run after restart,
**Then** no partial document records appear — either the document is fully indexed or not present at all.

---

### Story 2.7: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the complete ingestion pipeline as built in Epic 2,
So that any operator can load documents into the knowledge base without assistance.

**Acceptance Criteria:**

**Given** `docs/setup.md` exists from Epic 1,
**When** it is updated for Epic 2,
**Then** it includes a new section covering: how to prepare documents for ingestion, how to run `cos ingest <path>` for a file and a folder, how to verify ingestion succeeded with `cos docs`, and what to do if a file is skipped or fails.

**Given** the root `README.md`,
**When** it is updated,
**Then** the current capabilities section reflects that documents can now be ingested via CLI and provenance can be inspected — no claims are made about retrieval or Q&A (those come in Epic 3).

**Given** any decisions or implementation details that deviated from `architecture.md` during Epic 2 stories (e.g. changes to chunk size defaults, extraction fallback behaviour, filesystem layout),
**When** `architecture.md` is reviewed,
**Then** those deviations are documented accurately — the spec reflects what was built.

**Given** all Epic 2 documents (`docs/setup.md`, `README.md`, `architecture.md`),
**When** they are reviewed together,
**Then** command syntax, file paths, and capability descriptions are consistent across all three — no contradictions between documents.

## Epic 3: Knowledge Retrieval & Cited Q&A

User can ask natural language questions via Claude Desktop or Claude Code and receive synthesised, grounded answers with full source citations — results ranked by role pack priorities, response shaped by role pack tone, delivered only via configured channels.
**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR17, FR18, FR21, FR36
**NFRs:** NFR1, NFR3, NFR6, NFR7, NFR17
**Note:** FR13 (role pack retrieval weights) and FR16 (role pack tone) are architecturally wired up in this epic using the stub RolePackService. The real CHRO configuration is activated in Epic 4 — the retrieval behaviour will improve once real weights and tone are loaded.

### Story 3.1: Hybrid Search Engine & Citation Formatting

As a user,
I want my queries to match documents using both keyword and semantic search with results ranked by relevance,
So that retrieval finds the right content whether I phrase my question precisely or conceptually.

**Acceptance Criteria:**

**Given** a natural language query string and documents in the knowledge base,
**When** `search.py` runs a keyword search,
**Then** it executes a Postgres `tsvector` full-text search against the `chunks.content_tsv` column and returns ranked matching chunks.

**Given** the same query,
**When** `search.py` runs a semantic search,
**Then** it embeds the query using the configured embedding provider and executes a `pgvector` cosine similarity search against the `embeddings` table, returning the top-N most similar chunks.

**Given** results from both keyword and semantic searches,
**When** the results are merged and re-ranked,
**Then** the combined result list applies role pack retrieval weights (sourced from `RolePackService.get_active()`) to score and order results — higher-weighted sources appear higher in the list.

**Given** the merged search results,
**When** `citations.py` formats them,
**Then** each result in the `CitedResults` object contains: `content`, `source_document_id` (UUID), `source_path` (original file path), `chunk_index`, and `score` — with no result ever missing any of these fields.

**Given** a query that matches no content in the knowledge base,
**When** search runs,
**Then** an empty `CitedResults` list is returned — not an error — and the caller handles the empty case gracefully.

**Given** a retrieval query under normal conditions (knowledge base up to 10,000 documents),
**When** the search completes,
**Then** results are returned within 5 seconds from query submission to `CitedResults` ready for synthesis.

---

### Story 3.2: OutputRouter & Egress Enforcement

As an operator,
I want all platform output to pass through a single validated routing layer,
So that responses are only ever delivered to explicitly configured channels and the platform never accidentally sends output to an unintended destination.

**Acceptance Criteria:**

**Given** `OutputRouter.send(channel, content)` is called with a channel name that exists in `CosConfig.output_channels`,
**When** the router executes,
**Then** the content is passed to the appropriate channel handler (`output/channels/local.py` for the `"local"` channel) and delivered successfully.

**Given** `OutputRouter.send(channel, content)` is called with a channel name that does not exist in `CosConfig.output_channels`,
**When** the router executes,
**Then** the output is suppressed entirely, a structured JSON error is logged with `component: "output_router"` and the channel name, and the method returns without raising an exception.

**Given** `output/channels/local.py` is the handler for the `"local"` channel,
**When** it delivers content,
**Then** the content is returned as the MCP tool response body — not printed to stdout, not written to a file, not sent elsewhere.

**Given** `OutputService` in `services/output.py` wraps `OutputRouter`,
**When** any MCP tool delivers a response,
**Then** it calls `OutputService` which calls `OutputRouter` — no MCP tool calls a channel handler directly.

**Given** a test that deliberately passes an unrecognised channel to `OutputRouter`,
**When** the router handles it,
**Then** `tests/output/test_router.py` confirms the fail-closed behaviour: output suppressed, error logged, no exception raised.

---

### Story 3.3: LLM Synthesis & RetrievalService

As a user,
I want retrieved document chunks to be synthesised into a coherent answer that matches my role's voice and style,
So that I receive a readable, contextually appropriate response — not a raw list of matching text fragments.

**Acceptance Criteria:**

**Given** `AnthropicAdapter.complete(messages, config)` is called with a prompt containing retrieved chunks and a query,
**When** the Claude API is called,
**Then** the request is made over HTTPS using the API key from `CosConfig` — the key is never written to logs, responses, or any observable output.

**Given** a successful API response,
**When** `AnthropicAdapter` returns,
**Then** it returns a `str` containing the synthesised answer — conforming to the `LLMAdapter` protocol contract defined in Epic 1.

**Given** `RetrievalService.query(text, role_pack)` is called,
**When** it executes the full pipeline,
**Then** it calls `search.py` → `citations.py` → `LLMAdapter.complete()` in sequence, and returns a `CitedResponse` containing both the synthesised answer and the full `CitedResults` used to generate it.

**Given** the active `RolePackConfig` includes a tone definition (even the stub default),
**When** the synthesis prompt is constructed,
**Then** the tone instruction is included in the system prompt passed to the LLM — the response style reflects it.

**Given** the user's query implies a specific output type — a question ("what does..."), a comparison ("compare X and Y"), a summary request ("summarise..."), or a briefing request ("brief me on..."),
**When** the synthesised response is returned,
**Then** it is shaped appropriately for that output type — a question gets a direct answer, a comparison gets a structured comparison, a summary gets a concise synthesis — confirming FR17 is addressed through prompt construction, not separate code paths.

**Given** the user's query requests a draft document or communication (e.g. "draft a briefing note on...", "write a first draft of..."),
**When** the synthesised response is returned,
**Then** it is structured as a draft — with an appropriate document shape (heading, body, sign-off where relevant) rather than a conversational answer — and the synthesis prompt includes an explicit draft instruction derived from the query type.

**Given** the user's query requests prioritisation (e.g. "prioritise these initiatives...", "rank the following by..."),
**When** the synthesised response is returned,
**Then** it is structured as a ranked or ordered list with a brief rationale for each item's position — not a flat summary — and the synthesis prompt includes an explicit prioritisation instruction derived from the query type.

**Given** the Claude API is unavailable or returns an error,
**When** synthesis is attempted,
**Then** `RetrievalService` catches the error, logs a structured entry with `component: "retrieval"`, and returns a `CitedResponse` with `answer: null` and the `CitedResults` intact — the caller can handle the degraded response.

---

### Story 3.4: MCP Retrieve & List Documents Tools

As a user,
I want to ask questions and list my knowledge base directly from Claude Desktop or Claude Code,
So that the full retrieval and citation pipeline is accessible through the MCP interface I already use.

**Historical baseline note:** This story records the already-implemented pre-Epic 6 MCP contract. Story 6.4 is the explicit contract-switch story that migrates listings and citations from legacy `source_path` semantics to canonical `document_version_id` plus `source_alias`.

**Acceptance Criteria:**

**Given** a connected MCP client calls the `retrieve` tool with a `query` string,
**When** the tool executes,
**Then** it calls `OutputService` → `RetrievalService.query()` and returns the standard envelope: `{"status": "ok", "data": {"answer": "...", "citations": [...]}, "citations": [...]}` where citations include `source_path`, `chunk_index`, and `score` for each source.

**Given** the `retrieve` tool is called and retrieval finds no matching content,
**When** the tool returns,
**Then** it returns `{"status": "ok", "data": {"answer": "No relevant content found in the knowledge base.", "citations": []}, "citations": []}` — not an error envelope.

**Given** a connected MCP client calls the `list_documents` tool,
**When** the tool executes,
**Then** it returns a list of all ingested documents with `id`, `source_path`, `ingested_at`, `current_version`, and `chunk_count` for each — matching the data available via `cos docs` from Epic 2.

**Given** both `retrieve` and `list_documents` are called under normal conditions,
**When** execution completes,
**Then** each tool call returns within 2 seconds for `list_documents` and within 5 seconds for `retrieve` (including synthesis) — measured from MCP tool invocation to response.

**Given** the `get_role_context` tool is called,
**When** the tool executes,
**Then** it returns a stub response using the default role pack configuration: `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}` — not an error.

**Given** any of the implemented tools is called,
**When** the tool response is inspected,
**Then** the response strictly conforms to the standard envelope shape — no custom fields, no raw exceptions, no protocol-level errors for application-level failures.

---

### Story 3.5: Operator Validation — End-to-End Q&A with Citations

As Iain (operator and first user),
I want to run a documented end-to-end smoke test of the complete retrieval and Q&A pipeline,
So that I can confirm the knowledge pipeline works correctly — from ingested document to cited answer — before adding role identity in Epic 4.

**Acceptance Criteria:**

**Given** a set of documents has been ingested and the platform is running,
**When** a question is asked via Claude Desktop or Claude Code using the `retrieve` tool — e.g. "What frameworks do I have for workforce segmentation?",
**Then** a synthesised answer is returned that references content from the ingested documents, includes at least one citation with a `source_path` pointing to a real ingested file, and does not contain fabricated information absent from the knowledge base.

**Given** the same query is asked,
**When** the citations in the response are checked against the knowledge base,
**Then** each cited `source_path` corresponds to an actual ingested document visible in `cos docs` output, and each `chunk_index` is a valid index for that document.

**Given** a query for which no relevant content exists in the knowledge base,
**When** the `retrieve` tool responds,
**Then** the answer clearly states no relevant content was found — it does not fabricate sources or invent citations.

**Given** `list_documents` is called from Claude Desktop or Claude Code,
**When** the response is received,
**Then** it lists all ingested documents with correct metadata — consistent with `cos docs` CLI output.

**Given** a channel name not in `CosConfig.output_channels` is passed to `OutputRouter` (tested directly),
**When** the router handles it,
**Then** the output is suppressed, a structured error appears in `docker compose logs cos`, and no response is delivered to any channel.

---

### Story 3.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the working retrieval and Q&A pipeline as built in Epic 3,
So that any operator knows how to query the knowledge base and understand what grounded, cited answers look like.

**Acceptance Criteria:**

**Given** `docs/setup.md` is updated for Epic 3,
**When** it is reviewed,
**Then** it includes: how to configure Claude Desktop or Claude Code to connect to the CoS MCP server, how to use the `retrieve` tool to ask questions, how to interpret citations in the response, and how to use `list_documents` to browse the knowledge base.

**Given** the root `README.md` is updated,
**When** it is reviewed,
**Then** the current capabilities section reflects that questions can now be answered with citations via Claude Desktop or Claude Code — and notes that role-specific tone and retrieval weighting arrive in Epic 4.

**Given** any deviations from `architecture.md` that occurred during Epic 3 implementation (e.g. changes to the synthesis prompt structure, OutputRouter contract, or CitedResponse shape),
**When** `architecture.md` is reviewed,
**Then** the actual implementation is accurately documented — no spec fiction.

**Given** all Epic 3 documents are reviewed together,
**When** cross-checked for consistency,
**Then** MCP tool names, response envelope shapes, and capability descriptions match across `docs/setup.md`, `README.md`, and `architecture.md`.

## Epic 4: Role Identity & Configuration

Operator can define a complete role identity — goals, tone, knowledge taxonomy, stakeholder map, retrieval priorities — in a YAML file and activate it without touching the code. The role is applied consistently across all retrieval and reasoning from startup. The CHRO role pack is the first real implementation; a second minimal role pack demonstrates portability.
**FRs covered:** FR22, FR23, FR24, FR25
**NFRs:** NFR15, NFR18, NFR19

### Story 4.1: Role Pack Schema & CHRO Configuration File

As an operator,
I want to define a role identity in a structured YAML file covering goals, tone, knowledge taxonomy, stakeholder map, retrieval priorities, and active workflows,
So that who the CoS is for and how it behaves is captured entirely in configuration — not in code.

**Acceptance Criteria:**

**Given** `RolePackConfig` is defined as a Pydantic v2 model in `cos/rolepack/loader.py`,
**When** the model is inspected,
**Then** it contains typed fields for: `role_name` (str), `goals` (list[str]), `tone` (str), `knowledge_taxonomy` (list[str]), `stakeholder_map` (dict[str, str]), `retrieval_priorities` (list[str] ordered by weight), `active_workflows` (list[str]), and `output_channels` (list[str]).

**Given** the CHRO role pack YAML file is created (e.g. `role_packs/chro.yaml`),
**When** it is reviewed against `initial_docs/CoS - CHRO.md`,
**Then** it accurately reflects the CHRO role: goals covering workforce strategy and executive advisory, tone defined as strategic and evidence-based, knowledge taxonomy covering HR frameworks and org design, stakeholder map including CEO and exco members, and retrieval priorities weighting HR frameworks above general documents.

**Given** `config.yaml.example` is updated,
**When** it is reviewed,
**Then** it includes a `role_pack_path` key pointing to the example CHRO role pack file, with a comment explaining what the file controls.

**Given** a role pack YAML file with a missing required field (e.g. no `tone`),
**When** `RolePackConfig` attempts to parse it,
**Then** a Pydantic validation error is raised with a clear message identifying the missing field — not a cryptic Python exception.

---

### Story 4.2: Role Pack Loader & Startup Integration

As an operator,
I want the platform to load and validate the configured role pack automatically at startup,
So that the role identity is active from the first query without any manual steps after `docker compose up`.

**Acceptance Criteria:**

**Given** `config.yaml` contains a valid `role_pack_path` pointing to a well-formed YAML file,
**When** the `cos` container starts,
**Then** `rolepack/loader.py` reads the file, parses it into a validated `RolePackConfig` instance, and `RolePackService.get_active()` returns that instance — replacing the stub behaviour from Epic 1.

**Given** `config.yaml` points to a role pack YAML file that does not exist,
**When** the container starts,
**Then** startup fails with a clear error message identifying the missing file path — the platform does not start with a null or default role pack silently.

**Given** `config.yaml` points to a role pack YAML file with invalid content (bad YAML syntax or missing required field),
**When** the container starts,
**Then** startup fails with a human-readable validation error identifying the problem — operators can diagnose and fix without reading source code.

**Given** the startup sequence completes successfully,
**When** startup logs are inspected,
**Then** a structured log entry confirms the role pack was loaded: `{"component": "rolepack", "level": "INFO", "message": "Role pack loaded", "role_name": "CHRO"}`.

**Given** `RolePackService.get_active()` is called from any service,
**When** it returns,
**Then** it returns the same `RolePackConfig` instance that was loaded at startup — it does not re-read the file on every call.

---

### Story 4.3: Role Pack Applied to Retrieval & Synthesis

As a user,
I want retrieval results ranked according to my role's knowledge priorities and responses written in my role's voice,
So that the platform feels configured for my specific context rather than returning generic results.

**Acceptance Criteria:**

**Given** the CHRO role pack is loaded and a query is submitted,
**When** `search.py` ranks results,
**Then** chunks from documents tagged or sourced in categories matching `retrieval_priorities` (e.g. HR frameworks) rank higher than equivalent-relevance chunks from lower-priority categories — the role pack weights are applied, not the stub defaults from Epic 3.

**Given** the CHRO role pack defines a tone of "strategic and evidence-based",
**When** `LLMAdapter.complete()` constructs the synthesis prompt,
**Then** the system prompt includes the tone instruction from `RolePackConfig.tone`, and the synthesised response reflects that style — direct, evidence-grounded, without unnecessary padding.

**Given** a connected MCP client calls `get_role_context`,
**When** the tool executes,
**Then** it returns the full active role pack summary in the standard envelope: `{"status": "ok", "data": {"role_name": "CHRO", "goals": [...], "tone": "...", "knowledge_taxonomy": [...], "active_workflows": [...]}, "citations": []}`.

**Given** the role pack specifies `output_channels` (e.g. `["local"]` for Phase 1),
**When** `OutputRouter` validates a delivery request,
**Then** it uses the channels from `RolePackConfig.output_channels` as the authoritative permitted list — consistent with `CosConfig.output_channels`.

---

### Story 4.4: Role Pack & Provider Portability

As an operator,
I want to switch role packs, embedding providers, and LLM providers by changing only configuration values,
So that the platform can be adapted for a new person or updated to use a better model without any code changes.

**Acceptance Criteria:**

**Given** a minimal second role pack YAML file exists (e.g. `role_packs/enterprise_architect.yaml`) with different `role_name`, `tone`, `knowledge_taxonomy`, and `retrieval_priorities`,
**When** `config.yaml` is updated to point `role_pack_path` to this file and the `cos` container is restarted,
**Then** `get_role_context` returns the new role's configuration and retrieval/synthesis behaviour reflects the new role — no code was modified.

**Given** `config.yaml` `embedding.model` is changed to a different model name (e.g. from `text-embedding-3-small` to `text-embedding-3-large`) and the container is restarted,
**When** a new document is ingested,
**Then** the embedder uses the new model for that document's embeddings — no code change was required, only the config value.

**Given** `config.yaml` `embedding.provider` and `llm.provider` each specify a provider name,
**When** the relevant adapter is instantiated at startup,
**Then** the platform resolves the correct adapter implementation based solely on the config value — adding a new provider requires only a new adapter file and a config entry, with no changes to ingestion, retrieval, or MCP tools.

**Given** the `LLMAdapter` protocol defined in Epic 1,
**When** `AnthropicAdapter` is inspected,
**Then** it implements the protocol fully and no code outside `cos/llm/` makes any assumption about the concrete provider type — the boundary is clean.

---

### Story 4.5: Operator Validation — CHRO Role Active & Switchable

As Iain (operator and first user),
I want to run a documented smoke test of the role pack system,
So that I can confirm the CHRO persona is active, applied to queries, and that switching roles works without code changes.

**Acceptance Criteria:**

**Given** the platform is running with the CHRO role pack configured,
**When** `get_role_context` is called from Claude Desktop or Claude Code,
**Then** the response includes the CHRO role name, goals, tone, and knowledge taxonomy — correctly loaded from the YAML file.

**Given** a query is submitted that would benefit from CHRO-specific prioritisation (e.g. "What do I have on workforce segmentation frameworks?"),
**When** the `retrieve` tool responds,
**Then** the answer reflects CHRO tone (strategic, evidence-based) and cites HR-relevant documents with higher priority than general documents — a noticeable difference from the stub behaviour in Epic 3.

**Given** the `enterprise_architect.yaml` role pack exists,
**When** `config.yaml` is updated to point to it and `docker compose restart cos` is run,
**Then** `get_role_context` returns the Enterprise Architect configuration, and the same query as above returns a response with different tone and prioritisation — no files other than `config.yaml` were changed.

**Given** `config.yaml` is reverted to the CHRO role pack and the container is restarted,
**When** `get_role_context` is called,
**Then** the CHRO configuration is active again — the switch is fully reversible.

---

### Story 4.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want complete documentation on how to author and activate role packs,
So that a new operator can configure the platform for a different person without needing to read source code.

**Acceptance Criteria:**

**Given** a new `docs/role-packs.md` guide is created,
**When** it is reviewed,
**Then** it covers: the purpose of a role pack, every field in `RolePackConfig` with an explanation and example value, how to create a new role pack YAML file, how to activate it by updating `config.yaml`, and how to verify it loaded correctly using `get_role_context`.

**Given** `docs/setup.md` is updated,
**When** it is reviewed,
**Then** it includes a reference to `docs/role-packs.md` for role configuration, and notes that the CHRO role pack is the default example.

**Given** the root `README.md` is updated,
**When** it is reviewed,
**Then** it describes that role identity is configuration-only and links to `docs/role-packs.md` for authoring guidance.

**Given** any deviations from `architecture.md` that occurred during Epic 4 (e.g. changes to `RolePackConfig` field names, loader behaviour, or the relationship between `config.yaml` and role pack files),
**When** `architecture.md` is reviewed,
**Then** the role pack section accurately reflects what was built.

**Given** all Epic 4 documents are reviewed together,
**When** cross-checked,
**Then** field names, file paths, and YAML structure are consistent across `docs/role-packs.md`, `config.yaml.example`, `role_packs/chro.yaml`, and `architecture.md`.

## Epic 5: Platform Operations & Resilience

Operator and non-technical users can monitor, diagnose, and recover the platform using simple CLI commands with plain-language guidance — no technical knowledge required to keep the platform running.
**FRs covered:** FR26, FR27, FR28, FR29
**NFRs:** NFR5, NFR9, NFR14

### Story 5.1: Health Check System (`cos status`)

As an operator,
I want to check the health of all platform components with a single command that tells me exactly what is wrong and what to do about it,
So that I can diagnose problems without understanding Docker or Postgres internals.

**Acceptance Criteria:**

**Given** all containers are running and healthy,
**When** `cos status` is run,
**Then** the output shows a plain-language summary confirming each component is healthy, e.g.:

```
CoS Platform Status
-------------------
Postgres        ✓ healthy
Tika            ✓ healthy
MCP server      ✓ healthy
Role pack       ✓ CHRO loaded
Database        ✓ connected (N documents indexed)
```

**Given** the Postgres container is stopped,
**When** `cos status` is run,
**Then** the output clearly identifies Postgres as the failed component and includes a specific recovery instruction: `Postgres container not running. Run: cos restart`

**Given** the Tika container is unhealthy,
**When** `cos status` is run,
**Then** the output identifies Tika as the failed component with a specific recovery instruction — not a generic error.

**Given** the role pack YAML file cannot be found or parsed,
**When** `cos status` is run,
**Then** the output identifies the role pack as misconfigured and states the path that was checked: `Role pack not loaded — file not found: role_packs/chro.yaml. Check config.yaml role_pack_path.`

**Given** `HealthService.check_all()` is called,
**When** it returns,
**Then** it returns a list of `ComponentStatus` objects each with `name`, `healthy` (bool), `message` (plain English), and `recovery_hint` (plain English action to take) — and `cos status` formats these into the human-readable output.

**Given** `cos status` is run in any state,
**When** the output is inspected,
**Then** no raw exception tracebacks, Docker internal IDs, or technical jargon appear in the output — it is readable by a non-technical user.

---

### Story 5.2: Platform Restart & Recovery (`cos restart`)

As an operator,
I want to restart the entire platform with a single command and have it confirm when everything is back up,
So that I can recover from failures without knowing which specific container failed or how Docker Compose works.

**Acceptance Criteria:**

**Given** the platform is running in any state (healthy or partially degraded),
**When** `cos restart` is run,
**Then** it executes `docker compose restart` for all services, waits for all containers to report healthy, and prints a confirmation: `Platform restarted. All components healthy.`

**Given** `cos restart` is run and all containers reach healthy state,
**When** the elapsed time is measured,
**Then** the platform is fully operational (all containers healthy, migrations applied, role pack loaded, MCP server listening) within 30 seconds.

**Given** `cos restart` is run after a `cos` container crash,
**When** the container restarts,
**Then** migrations re-run idempotently, the role pack reloads, and the MCP server resumes accepting connections — no manual database repair or file cleanup is required.

**Given** a container fails to reach healthy state within a timeout after restart,
**When** `cos restart` detects this,
**Then** it prints a plain-language message identifying the stuck component and advises running `cos logs` for diagnostic detail: `Tika did not become healthy. Run: cos logs tika`

**Given** `cos restart` completes successfully,
**When** a query is immediately submitted via Claude Desktop or Claude Code,
**Then** the `retrieve` tool responds correctly — the platform is genuinely operational, not just containers-reporting-healthy.

---

### Story 5.3: Diagnostic Log Export (`cos logs`)

As an operator,
I want to retrieve platform logs with a single command in a format I can send to Iain for support,
So that diagnosing problems does not require me to understand Docker log commands or navigate container filesystems.

**Acceptance Criteria:**

**Given** `cos logs` is run with no arguments,
**When** it executes,
**Then** it outputs the last 100 lines of structured JSON logs from all containers combined, ordered by timestamp — suitable for pasting into a support message.

**Given** `cos logs <component>` is run with a component name (e.g. `cos logs postgres`, `cos logs tika`, `cos logs cos`),
**When** it executes,
**Then** it outputs logs from only that container — allowing targeted diagnosis.

**Given** `cos logs --since 10m` is run,
**When** it executes,
**Then** it outputs only log entries from the last 10 minutes — useful for diagnosing a recent specific failure without scrolling through hours of history.

**Given** log output is inspected from any component,
**When** the entries are reviewed,
**Then** no API keys, OAuth tokens, or credential values appear anywhere in the log output — credentials are not logged even in debug entries.

**Given** `cos logs` is run when no containers are running,
**When** it executes,
**Then** it prints a clear message: `No containers running. Start the platform first: docker compose up -d` — not a Docker error.

---

### Story 5.4: Secrets & Security Audit

As an operator deploying the platform with real API keys and sensitive documents,
I want confidence that credentials are never leaked through logs, responses, or diagnostic output,
So that operating the platform does not create a security exposure.

**Acceptance Criteria:**

**Given** a full audit of all structured log statements in `cos/ingestion/`, `cos/retrieval/`, `cos/llm/`, `cos/mcp_server/`, and `cos/cli.py`,
**When** each log statement is reviewed,
**Then** no log call references any field from `CosConfig` that is a key or credential — specifically: `llm.api_key`, `embedding.api_key`, and any `connectors.*` credential fields.

**Given** the `AnthropicAdapter` makes an API call,
**When** the HTTP request is inspected,
**Then** it is made over HTTPS exclusively — no plaintext HTTP is permitted, and the client raises an error if a non-HTTPS URL is configured.

**Given** any MCP tool response is inspected,
**When** all response fields are reviewed,
**Then** no API key, token, or credential value appears in `data`, `citations`, `error`, or `detail` fields — even in error responses where the LLM or embedding call failed.

**Given** `cos logs` output is reviewed after a failed LLM API call (e.g. invalid key),
**When** the error log entry is inspected,
**Then** it contains the error type and HTTP status code but not the key value that caused the failure: `{"level": "ERROR", "component": "llm", "message": "API call failed", "status_code": 401}` — not the key itself.

**Given** a `config.yaml` audit,
**When** its contents are confirmed against `.gitignore`,
**Then** `config.yaml` is gitignored, `config.yaml.example` contains no real credentials, and the `tokens/` directory is gitignored — verified by checking git status on a fresh clone.

---

### Story 5.5: Operator Validation — Recovery Scenario

As Iain (operator and first user),
I want to run a documented recovery smoke test that proves the platform is genuinely operable by a non-technical user,
So that I can hand the platform to someone else with confidence they can keep it running.

**Acceptance Criteria:**

**Given** the platform is running healthily,
**When** `cos status` is run,
**Then** all components show as healthy in plain-language output with no technical jargon.

**Given** the `postgres` container is manually stopped with `docker stop $(docker compose ps -q postgres)`,
**When** `cos status` is run,
**Then** the output identifies Postgres as not running and states the recovery action: `Run: cos restart`

**Given** `cos restart` is run following the Postgres stop,
**When** the command completes,
**Then** all containers are healthy, `cos status` confirms full health, and the elapsed time from running `cos restart` to all-healthy is under 30 seconds.

**Given** the platform has recovered,
**When** a `retrieve` query is submitted via Claude Desktop or Claude Code,
**Then** a valid cited answer is returned — the recovery was genuine, not cosmetic.

**Given** `cos logs` is run after the recovery,
**When** the output is reviewed,
**Then** the restart event is visible in the logs, no credentials appear, and the log format is structured JSON throughout.

---

### Story 5.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want `docs/setup.md` to include a complete operations reference that a non-technical user can follow without assistance,
So that the platform can be handed over to another person with a simple setup card.

**Acceptance Criteria:**

**Given** `docs/setup.md` is updated for Epic 5,
**When** it is reviewed,
**Then** it includes a dedicated Operations section covering: `cos status` (what it shows, how to read it), `cos restart` (when and how to use it), `cos logs` (how to capture and send logs for support), and a three-step recovery procedure for the most common failure (Postgres not running).

**Given** a one-page setup card could be extracted from `docs/setup.md`,
**When** the operations section is reviewed by someone unfamiliar with Docker,
**Then** they can follow the restart and diagnostic steps without needing to understand what Postgres or Tika are — commands are given verbatim with expected output shown.

**Given** the root `README.md` is updated,
**When** it is reviewed,
**Then** it references `docs/setup.md` for operations guidance and accurately describes the current Phase 1 capabilities including the CLI commands available.

**Given** any deviations from `architecture.md` during Epic 5 (e.g. changes to `ComponentStatus` structure, `cos status` output format, or log filtering behaviour),
**When** `architecture.md` is reviewed,
**Then** the operations and CLI sections reflect what was built.

**Given** all Epic 5 documents are reviewed together,
**When** cross-checked for consistency,
**Then** CLI command syntax, expected output, and recovery steps are identical across `docs/setup.md`, `README.md`, and `architecture.md`.

## Epic 6: Canonical Source Identity & Connected Ingestion

Operator can safely expand from manual ingest to multi-source ingest because the platform resolves canonical document identity correctly, deduplicates exact content across sources, preserves clean provenance and citations, and then adds Gmail and Calendar ingestion on top of that hardened base.
**FRs covered:** FR7, FR8, FR10, FR32, FR33
**NFRs:** NFR11, NFR12, NFR20

**Epic 6 framing:** Epics 1 through 5 are the implemented baseline. Epic 6 is intentionally a migration/hardening epic that upgrades that baseline before any new connector-led development proceeds.

### Story 6.1: Canonical Blob, Source, and Version Schema Hardening

As an operator,
I want the canonical store schema to separate logical documents, immutable content blobs, and source provenance,
So that connector locators and filenames do not accidentally define document identity.

**Acceptance Criteria:**

**Given** the already-implemented Phase 1 baseline schema is present,
**When** the next migration set is applied,
**Then** it upgrades the existing store in place rather than assuming a fresh greenfield database, preserving already-indexed documents while adding canonical identity structures.

**Given** the next migration set is applied,
**When** the schema is inspected,
**Then** it contains canonical identity tables or equivalent structures for `content_blobs`, `sources`, `source_versions`, and `document_versions`, with foreign keys linking them to logical `documents`.

**Given** the canonical schema is in place,
**When** table constraints are reviewed,
**Then** `content_blobs` enforce uniqueness on SHA-256 content hash and `sources` store provenance-specific fields such as `source_type`, `source_locator`, and `source_alias` without making those fields the canonical document key.

**Given** a stored document version is inspected,
**When** its lineage is traced,
**Then** the path from `document_version` to `content_blob` and `source_version` is sufficient to identify both the exact bytes used and the source observation that produced them.

**Given** pre-existing Epic 2 tables are migrated forward,
**When** the migration runs repeatedly in development or CI,
**Then** it remains idempotent and does not duplicate rows or destroy existing provenance history.

---

### Story 6.2: Hash-First Ingest and Exact-Byte Deduplication

As an operator,
I want ingest to detect canonically identical bytes before chunking, embedding, or managed-copy writes,
So that duplicate content from different paths or connectors does not create duplicate storage or retrieval noise.

**Acceptance Criteria:**

**Given** bytes submitted for ingest exactly match an existing `content_blob` SHA-256 hash,
**When** the ingest pipeline evaluates the input,
**Then** it reuses the existing canonical blob record and does not create duplicate chunk, embedding, original-file, or Markdown-copy artifacts.

**Given** the same bytes arrive from a new path or connector locator,
**When** ingest completes,
**Then** a new provenance/source record is created and linked to the existing canonical content without redefining document identity around the new locator.

**Given** the same bytes arrive from the same known source,
**When** the pipeline runs,
**Then** the operation resolves as a no-op for content processing and returns a clear notice that no new version or embeddings were created.

**Given** a truly new byte sequence arrives,
**When** the pipeline runs,
**Then** the hash check completes before chunking or embedding begins, and the new content proceeds through normal ingest exactly once.

---

### Story 6.3: Re-Ingest Semantics and No-Op Handling

As an operator,
I want ingest to resolve the four source/content outcomes deterministically,
So that unchanged re-ingests are no-ops and changed re-ingests create the right new version records.

**Acceptance Criteria:**

**Given** a known source is re-ingested with unchanged content,
**When** the decision engine runs,
**Then** it records the ingest attempt as unchanged and does not create a new `document_version`, `content_blob`, chunk set, or embedding set.

**Given** a known source is re-ingested with changed content,
**When** ingest completes,
**Then** the existing logical document is preserved, a new `content_blob` and `document_version` are created, and the new version becomes current only after all related writes succeed.

**Given** a new source provides bytes already known to the system,
**When** the decision engine runs,
**Then** it creates the new source lineage and links it to the existing canonical content/version without duplicate chunking or embedding.

**Given** the ingest outcome is returned to the caller,
**When** the result is logged or displayed,
**Then** it clearly states which of the four canonical outcomes occurred so operators can reason about connector behaviour without inspecting the database directly.

---

### Story 6.4: Citation and Listing Updates Using Source Alias

As a user,
I want document listings and citations to show stable, readable source aliases while preserving underlying provenance locators,
So that results stay understandable without losing traceability.

**Acceptance Criteria:**

**Given** the implemented pre-Epic 6 baseline exposed path-centric labels such as `source_path`,
**When** Story 6.4 is complete,
**Then** this story becomes the authoritative contract-switch point from legacy path-centric provenance to canonical provenance semantics.

**Given** a document originated from any source type,
**When** `list_documents` or `cos docs` displays it after the Epic 6 migration,
**Then** the primary user-facing label uses `source_alias`, while the underlying canonical provenance retains the full `source_locator`.

**Given** retrieval returns cited results,
**When** citation formatting runs after the Epic 6 migration,
**Then** each result includes the canonical `document_version_id` plus a readable `source_alias`, rather than relying on raw path-centric identifiers alone.

**Given** MCP or CLI consumers still need to trace a result back to the original observation,
**When** a machine-readable response is inspected,
**Then** the underlying provenance includes `source_locator` for traceability, but `source_alias` remains the primary display label.

**Given** multiple source records point at the same canonical content,
**When** a listing or citation is produced,
**Then** the platform shows a stable, deterministic alias selection strategy documented in code and operator docs.

**Given** a legacy path-centric record has been migrated,
**When** it is surfaced through the updated listing/citation path,
**Then** it still appears with a readable alias and complete provenance rather than a broken or empty label.

---

### Story 6.5: Migration, Backfill, and Operator Recovery

As an operator,
I want existing path-centric Phase 1 data migrated onto the canonical identity model with safe recovery steps,
So that we can harden the store before connector work without corrupting provenance or retrieval.

**Acceptance Criteria:**

**Given** an existing Phase 1 database with path-centric provenance records,
**When** the backfill/migration process runs,
**Then** all existing documents are assigned canonical content/source/version relationships without losing retrieval visibility or version history.

**Given** the migration is interrupted mid-run,
**When** the operator reruns the migration,
**Then** the process resumes safely or replays idempotently without creating duplicate canonical blobs or broken foreign-key chains.

**Given** migrated records are sampled after backfill,
**When** the operator compares pre- and post-migration outputs,
**Then** document counts remain stable and citations/listings continue to resolve to valid records.

**Given** the migration introduces a degraded or partial state,
**When** the operator follows the recovery documentation,
**Then** the required rollback, re-run, or reconcile steps are explicit, plain-language, and sufficient to restore a healthy canonical store.

---

### Story 6.6: OAuth Authentication Setup for Gmail and Calendar

As an operator,
I want to authenticate Gmail and Google Calendar once with local token refresh,
So that connectors can access live data without repeated re-authorisation.

**Acceptance Criteria:**

**Given** `config.yaml` contains valid Google OAuth client credentials,
**When** `cos auth gmail` or `cos auth calendar` is run for the first time,
**Then** a browser-based OAuth flow completes and the resulting token is stored under `tokens/` with a plain-language success confirmation.

**Given** tokens exist and later expire,
**When** a connector makes an API call,
**Then** the auth library refreshes the token locally using the stored refresh token without requiring a new manual consent flow.

**Given** the `tokens/` directory exists,
**When** repository ignore rules are reviewed,
**Then** the token directory is gitignored and no generated token artifact is committed.

**Given** a connector runs without the required token file,
**When** authentication fails,
**Then** the system logs a connector-scoped error with a direct recovery instruction and leaves the MCP retrieval path available.

---

### Story 6.7: Jobs Queue and Background Ingestion Worker

As an operator,
I want connector-triggered ingestion to run through a background job mechanism,
So that live-source ingest does not block MCP retrieval or destabilise the core path.

**Acceptance Criteria:**

**Given** the Phase 2 jobs migration is applied,
**When** the jobs table is inspected,
**Then** it supports queued ingestion work with status tracking, retry metadata, and completion/error timestamps.

**Given** a connector discovers new content to ingest,
**When** it submits work,
**Then** it creates a background job carrying the connector payload and does not invoke the ingest pipeline inline on the connector poll loop.

**Given** the worker processes queued jobs,
**When** it handles an ingest request,
**Then** it executes through the same canonical identity decision path used by CLI ingest and records whether the outcome was new content, changed content, known-content/new-source, or no-op.

**Given** the worker crashes or the container restarts mid-job,
**When** processing resumes,
**Then** unfinished work is retried safely and does not leave partial canonical identity records visible to users.

---

### Story 6.8: Gmail Connector

As an operator,
I want Gmail messages and attachments ingested through the hardened identity pipeline,
So that email-based knowledge becomes searchable without manual download and duplicate inflation.

**Acceptance Criteria:**

**Given** Gmail is authenticated and enabled in configuration,
**When** the connector polls for new messages,
**Then** it creates background ingest jobs for message bodies and supported attachments using Gmail identifiers as provenance locators.

**Given** an attachment or message body was already observed from the same Gmail source,
**When** the connector polls again,
**Then** the canonical ingest decision engine prevents duplicate processing and records the appropriate no-op or new-version outcome.

**Given** two different Gmail messages carry byte-identical attachments,
**When** both are ingested,
**Then** they resolve to shared canonical content with distinct source provenance records rather than duplicate embeddings.

**Given** the Gmail API is temporarily unavailable or rate-limited,
**When** the connector handles the failure,
**Then** it logs a degraded connector status, backs off appropriately, and leaves the core retrieval path healthy.

---

### Story 6.9: Google Calendar Connector

As an operator,
I want upcoming calendar events available through the same connected-source foundation,
So that meeting context can later power prep and scheduled briefings.

**Acceptance Criteria:**

**Given** Google Calendar is authenticated and enabled in configuration,
**When** the connector fetches events,
**Then** it returns structured event records containing title, time range, attendees, and description fields suitable for retrieval and downstream workflows.

**Given** calendar events are materialised into the knowledge context,
**When** they are surfaced for retrieval or prep workflows,
**Then** their provenance uses calendar-specific locators and readable aliases without redefining canonical document identity rules.

**Given** an unchanged event is observed on successive syncs,
**When** the connector reprocesses it,
**Then** the ingest decision path treats it as unchanged/no-op rather than creating duplicate records.

**Given** the Calendar API is unavailable,
**When** the connector runs,
**Then** the failure is logged as a degraded connector condition and the rest of the platform continues operating normally.

---

### Story 6.10: `ingest_document` MCP Tool

As a user,
I want to ingest notes or short documents directly through MCP,
So that synthetic note capture also uses the same canonical identity and provenance model.

**Acceptance Criteria:**

**Given** a connected MCP client calls `ingest_document` with content and optional metadata,
**When** the tool executes successfully,
**Then** it routes the request through the same ingest decision engine as CLI and connector ingestion and returns the standard MCP response envelope.

**Given** an MCP-ingested note duplicates existing bytes exactly,
**When** the tool completes,
**Then** it returns a successful response that explains the content was linked to existing canonical content rather than duplicated.

**Given** an MCP-ingested note is semantically very similar but not byte-identical to existing content,
**When** the near-duplicate layer runs,
**Then** the tool returns a warning alongside the successful ingest outcome without blocking capture.

**Given** the tool receives invalid input such as empty content,
**When** validation runs,
**Then** it returns a structured error envelope rather than an unhandled exception.

---

### Story 6.11: Operator Validation — Connected Sources Live

As Iain (operator and first user),
I want a smoke test proving canonical identity hardening and live-source ingestion work together,
So that Epic 7 builds on a stable connected-ingestion base.

**Acceptance Criteria:**

**Given** canonical identity migrations and backfill have completed,
**When** the operator runs the validation checklist,
**Then** local legacy documents, Gmail ingests, Calendar-derived records, and MCP-ingested notes all surface with valid aliases and provenance links.

**Given** a test set includes repeated content across local files, Gmail attachments, and MCP note capture,
**When** validation completes,
**Then** exact-byte duplicates share canonical content while retaining distinct source provenance records.

**Given** a known source is re-ingested unchanged and then changed,
**When** validation compares the outcomes,
**Then** the unchanged case produces a no-op and the changed case produces a new current `document_version` with intact history.

**Given** connector authentication tokens remain valid across a container restart,
**When** the platform restarts,
**Then** connectors recover without fresh authorisation and the canonical identity rules still produce deterministic ingest outcomes.

---

### Story 6.12: Documentation and Housekeeping

As an operator,
I want setup, migration, connector, and recovery documentation updated to match the hardened identity model,
So that the backlog and docs stay consistent with the actual strategy.

**Acceptance Criteria:**

**Given** the Epic 6 work is complete,
**When** the documentation set is reviewed,
**Then** it explains the canonical identity model, the four ingest outcomes, exact-byte deduplication behaviour, and how `source_alias` appears in listings and citations.

**Given** connector setup documentation is updated,
**When** it is reviewed,
**Then** it covers OAuth setup, token storage, connector-specific provenance locators, job processing, and degraded-mode recovery steps.

**Given** migration/backfill documentation is updated,
**When** an operator follows it on an existing Phase 1 instance,
**Then** the instructions are sufficient to migrate, validate, and recover without reading implementation code.

**Given** Epic 6 introduced any divergence from `architecture.md`,
**When** the architecture and planning artifacts are reviewed together,
**Then** the documented model, story ordering, and operator workflow are consistent across `architecture.md`, `epics.md`, and connector documentation.

## Epic 7: Ambient Messaging Intelligence

Users interact with the platform through Telegram — asking questions, capturing notes, and receiving proactive morning briefs — without opening a dedicated interface. The platform comes to them, augmented by live web search when local knowledge is insufficient.
**FRs covered:** FR9, FR16, FR19, FR20, FR34, FR35
**NFRs:** NFR11, NFR20

### Story 7.1: Telegram Bot Setup & Output Channel

As an operator,
I want to configure a Telegram bot that the platform can send messages to and receive messages from,
So that Telegram is a live, verified channel before building the Q&A and briefing flows on top of it.

**Acceptance Criteria:**

**Given** a Telegram bot token is present in `config.yaml` under `connectors.telegram.bot_token`,
**When** the `cos` container starts with Telegram enabled,
**Then** `telegram_bot.py` begins polling the Telegram Bot API for updates using long-polling — no error on startup if the token is valid.

**Given** `output/channels/telegram.py` is implemented,
**When** `OutputRouter.send(channel="telegram", content="test message")` is called,
**Then** the message is delivered to the configured Telegram chat ID via the Bot API `sendMessage` endpoint — and the router validates the `telegram` channel against `CosConfig.output_channels` before dispatching.

**Given** `OutputRouter` attempts to send via Telegram and the Bot API returns an error (e.g. invalid chat ID),
**When** the error is handled,
**Then** the output is suppressed, a structured error is logged with `component: "output_router"`, and no exception propagates — fail-closed behaviour is preserved.

**Given** the Telegram Bot API is temporarily unreachable,
**When** the connector attempts to poll,
**Then** the failure is logged and the connector backs off — the MCP server, retrieval path, and all other components remain fully operational (NFR11).

**Given** a simple test message is sent to the bot from a Telegram client,
**When** the platform polls and receives it,
**Then** the raw message content and sender metadata are available to the message handler — confirming the inbound pipeline is wired up.

---

### Story 7.2: Telegram Inbound Q&A

As a user,
I want to send a question to the platform via Telegram and receive a cited answer,
So that I can access my knowledge base from my phone without opening a laptop or a separate app.

**Acceptance Criteria:**

**Given** a message is received via the Telegram bot,
**When** the message classifier runs,
**Then** it classifies the message as a `question` if it is phrased as a query (ends with `?`, starts with an interrogative, or is a statement clearly seeking information) — and as a `note` otherwise.

**Given** a message is classified as a `question`,
**When** the Q&A path executes,
**Then** it calls `RetrievalService.query(text, role_pack)`, receives a `CitedResponse`, and delivers a reply via `OutputRouter.send(channel="telegram")` containing the synthesised answer and at least the top source reference.

**Given** a question is answered and the response is delivered,
**When** the Telegram message is reviewed,
**Then** the answer is appropriately concise for a messaging context (not a full multi-page document) and includes the source document name so the user can follow up.

**Given** a question is submitted but retrieval finds no relevant content,
**When** the reply is delivered,
**Then** the user receives a clear message such as "I couldn't find relevant content in your knowledge base for that question" — not silence, not an error code.

**Given** the Claude API is temporarily unavailable when a Telegram question arrives,
**When** synthesis fails,
**Then** the user receives a plain-language apology message via Telegram — the failure is handled gracefully and does not crash the bot.

---

### Story 7.3: Telegram Note Capture

As a user,
I want to send a short note or thought to the platform via Telegram and have it saved to my knowledge base immediately,
So that I can capture ideas in the moment, from my phone, knowing they will be searchable later.

**Acceptance Criteria:**

**Given** a message is received via Telegram and classified as a `note` (declarative statement, or prefixed with "Note:"),
**When** the note capture path executes,
**Then** it calls `IngestService.ingest_note(text, metadata)` with the message content and metadata including `source: "telegram"`, `sender_id`, and `timestamp` — and the jobs queue from Epic 6 is used for the ingest operation.

**Given** a note is ingested,
**When** the confirmation reply is delivered via Telegram,
**Then** the user receives a brief acknowledgement: "Note saved." — not silence, not a long status message.

**Given** a note has been ingested via Telegram,
**When** `list_documents` is called,
**Then** the note appears with a readable `source_alias`, a canonical `document_version_id`, and a non-zero `chunk_count`, while the underlying provenance retains the Telegram locator.

**Given** a subsequent `retrieve` query references the content of the captured note,
**When** the retrieval runs,
**Then** the note appears in the cited results — it is a full first-class document, searchable immediately after capture.

**Given** a very short message (one or two words) is received via Telegram,
**When** the classifier and ingestion run,
**Then** the platform still ingests it as a note and confirms — single-word captures are valid and are not discarded.

---

### Story 7.4: Web Search MCP Tool

As a user,
I want the platform to search the live web when my knowledge base does not contain sufficient context,
So that my answers are augmented with current information rather than being limited to what I have manually ingested.

**Acceptance Criteria:**

**Given** the `web_search` tool is registered on the MCP server and a web search API key (Brave or Tavily) is configured in `config.yaml`,
**When** a connected MCP client (Claude Desktop or Claude Code) invokes `web_search` with a `query` string,
**Then** the platform calls the configured search API, retrieves results, and returns them in the standard citation envelope format: `{"status": "ok", "data": {"results": [...]}, "citations": [...]}` where each result includes `title`, `url`, `snippet`, and `source: "web"`.

**Given** web search results are returned,
**When** their citation format is compared to local retrieval citations,
**Then** both use the same `CitedResults` structure — `source_path` is the URL for web results — ensuring consistent behaviour when the LLM reasons over mixed local and web sources.

**Given** a brief caching layer is implemented,
**When** the same query is submitted twice within the cache window (configurable in `config.yaml`),
**Then** the second call returns cached results without making a second API call — avoiding duplicate charges and rate-limit exposure.

**Given** the web search API is unavailable or returns an error,
**When** the `web_search` tool is called,
**Then** it returns `{"status": "error", "error": "Web search unavailable", "detail": "..."}` — not an unhandled exception — and the LLM can fall back to local retrieval.

**Given** `web_search` is called,
**When** the request and response are logged,
**Then** the search query is logged with `component: "connector"` but no API key value appears in any log entry.

---

### Story 7.5: Scheduler Infrastructure & Morning Brief

As a user,
I want to receive a proactive morning brief via a configured output channel at a configured time each day,
So that the platform surfaces relevant knowledge before I start work, without me having to ask.

**Acceptance Criteria:**

**Given** APScheduler is integrated and a brief time plus outbound channel are configured in `config.yaml` (e.g. `scheduler.morning_brief_time: "07:30"` and `scheduler.brief_channel: "telegram"` or `"email"`),
**When** the scheduler triggers at the configured time,
**Then** it fetches today's calendar events via `CalendarConnector`, retrieves relevant documents for each event via `RetrievalService`, synthesises a morning brief via `LLMAdapter`, and delivers it via `OutputRouter.send(channel=<configured brief channel>)`.

**Given** a morning brief is delivered,
**When** the outbound message is reviewed in the configured channel,
**Then** it is appropriately formatted for that channel, references today's key meetings, and cites at least one relevant knowledge base document per meeting where relevant content exists.

**Given** a scheduled brief job runs but the configured output channel is unavailable,
**When** delivery fails,
**Then** the failure is logged with `component: "scheduler"`, the job is marked as `failed` in the jobs table, and the next scheduled job runs normally at its configured time — one delivery failure does not stop the scheduler.

**Given** a day with no calendar events,
**When** the morning brief triggers,
**Then** the brief still delivers — it covers general knowledge base context or a role-relevant summary rather than meeting-specific content — the user always receives something useful.

**Given** the `cos` container restarts while the scheduler is between jobs,
**When** it comes back up,
**Then** APScheduler resumes from the configured schedule — no manual intervention is required to restart scheduled jobs.

---

### Story 7.6: Meeting Prep from Calendar Events

As a user,
I want to receive contextual prep notes before each calendar meeting,
So that I arrive at every meeting with relevant knowledge surfaced from my knowledge base, without having to ask.

**Acceptance Criteria:**

**Given** a meeting prep interval is configured in `config.yaml` (e.g. `scheduler.meeting_prep_minutes: 30`),
**When** a calendar event is 30 minutes away,
**Then** the scheduler triggers a meeting prep job, retrieves documents relevant to the meeting title and attendees via `RetrievalService`, synthesises a brief prep note via `LLMAdapter`, and delivers it via `OutputRouter.send(channel="telegram")`.

**Given** a meeting prep note is delivered,
**When** the Telegram message is reviewed,
**Then** it is concise and meeting-specific — referencing the meeting title, key attendees where known, and citing at least one relevant knowledge base document where relevant content exists.

**Given** a calendar event has no relevant content in the knowledge base,
**When** the meeting prep job runs,
**Then** the prep note is still delivered — it acknowledges the meeting and notes that no specific content was found, rather than sending nothing.

**Given** a meeting prep job runs but delivery fails (Telegram unavailable),
**When** the failure is handled,
**Then** it is logged with `component: "scheduler"`, marked as `failed` in the jobs table, and the morning brief scheduler continues to run — meeting prep failure does not affect the daily brief schedule.

**Given** multiple meetings are scheduled within the prep window simultaneously,
**When** the scheduler evaluates upcoming events,
**Then** a prep note is triggered for each event independently — each meeting gets its own prep job.

---

### Story 7.7: Operator Validation — Ambient Intelligence Live


As Iain (operator and first user),
I want to run a documented end-to-end smoke test of the full ambient intelligence layer,
So that I can confirm the platform genuinely comes to the user through Telegram before handing it to a real user.

**Acceptance Criteria:**

**Given** the Telegram bot is configured and the platform is running,
**When** a question is sent to the bot from a Telegram client,
**Then** a cited answer is received in Telegram within a reasonable response time (target: under 10 seconds from message sent to reply received).

**Given** a note is sent to the bot prefixed with "Note:",
**When** the platform processes it,
**Then** a "Note saved." confirmation is received in Telegram, and a subsequent `retrieve` query that references the note's content returns it as a cited source.

**Given** the morning brief schedule is temporarily set to trigger in 2 minutes for testing,
**When** the scheduler fires,
**Then** a morning brief is received in Telegram — formatted appropriately, referencing calendar events and relevant knowledge base documents.

**Given** the `web_search` MCP tool is available in Claude Desktop or Claude Code,
**When** a query is submitted that the local knowledge base cannot answer well,
**Then** the LLM invokes `web_search`, augments the answer with live results, and the response distinguishes between local citations and web citations.

**Given** all Telegram connector features are working,
**When** the Telegram Bot API is temporarily blocked (simulated),
**Then** `cos status` shows Telegram as degraded, all other components remain healthy, and `retrieve` queries from Claude Desktop or Claude Code continue to be answered normally.

---

### Story 7.8: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the complete ambient intelligence layer,
So that a new user can configure Telegram, understand what they will receive and when, and operate the platform end-to-end from the documentation alone.

**Acceptance Criteria:**

**Given** `docs/connectors.md` is updated for Epic 7,
**When** it is reviewed,
**Then** it covers: how to create a Telegram bot via BotFather, how to add the bot token to `config.yaml`, how to configure the chat ID for outbound delivery, how to enable and test the web search connector, and how to configure scheduler times for morning briefs and meeting prep.

**Given** a new `docs/user-guide.md` is created,
**When** it is reviewed,
**Then** it covers the end-user experience: how to ask questions via Telegram, how to capture notes, what morning briefs look like and when they arrive, and how to interpret cited answers — written for a non-technical user (Sarah or Marcus, not Iain).

**Given** the root `README.md` is updated,
**When** it is reviewed,
**Then** it accurately describes the complete platform capabilities across both phases — Phase 1 (CLI ingestion, MCP Q&A) and Phase 2 (connected sources, Telegram, scheduled briefs, web search) — with links to the relevant docs for each.

**Given** any deviations from `architecture.md` during Epic 7 (e.g. changes to scheduler configuration structure, message classification logic, web search caching behaviour, or OutputRouter telegram channel handling),
**When** `architecture.md` is reviewed,
**Then** those sections reflect what was built.

**Given** all Epic 7 documents are reviewed together,
**When** cross-checked for consistency,
**Then** Telegram setup steps, scheduler config keys, web search config keys, and capability descriptions are consistent across `docs/connectors.md`, `docs/user-guide.md`, `docs/setup.md`, and `architecture.md`.
