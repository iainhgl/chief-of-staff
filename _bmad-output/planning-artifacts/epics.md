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
- **MCP server pattern:** FastMCP pattern from official MCP SDK 1.27.0. Tools: `retrieve`, `get_role_context`, `list_documents`, `get_status`, `ingest_document` (added in Epic 6). All tools return the standard envelope: `{"status": "ok/error", "data": {...}, "citations": [...]}`. No custom response shapes.
- **Citation integrity:** Retrieval results must cite `document_version` plus source provenance cleanly, using `source_alias` for user-facing listing/citation labels while preserving connector-specific locators underneath.
- **Logging:** Structured JSON to stdout. Mandatory fields: `timestamp`, `level`, `component`, `message`. No bare `print()` calls anywhere. `component` must be one of: `ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`.
- **Connectors:** `cos/connectors/` was a stub from Phase 1; after Epic 6 it contains working Gmail and Google Calendar connectors (`google_auth.py`, `gmail.py`, `calendar.py`). Enabled by adding `gmail` / `google_calendar` to the `connectors:` list in `config.yaml` and running `cos auth gmail` / `cos auth calendar`.
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
| FR9 | Epic 8 | Note capture via Telegram (Growth) |
| FR10 | Epic 6 | Email ingestion via Gmail (Growth) |
| FR11 | Epic 3, Epic 7 | Natural language query → cited answer |
| FR12 | Epic 3, Epic 7 | Hybrid keyword + semantic search |
| FR13 | Epic 3, Epic 7 | Document + chunk-level citations |
| FR14 | Epic 3 | Role pack retrieval priorities |
| FR15 | Epic 3 | List documents with metadata |
| FR16 | Epic 11 | Web search augmentation (Growth) |
| FR17 | Epic 3, Epic 7 | Synthesise response in role pack tone |
| FR18 | Epic 3 | Common workflow outputs |
| FR19 | Epic 12 | Scheduled briefing via channel (Growth) |
| FR20 | Epic 12 | Meeting prep from calendar (Growth) |
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
| FR34 | Epic 8 | Telegram Q&A and note capture (Growth) |
| FR35 | Epic 12 | Scheduled briefs via configured Telegram or email channel (Growth) |
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
**Then** the output is suppressed entirely, a structured JSON error is logged with `component: "output"` and the channel name, and the method returns without raising an exception.

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
So that the post-Epic-6 growth backlog builds on a stable connected-ingestion base.

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

### Story 6.13: Retrieval Result Thresholding and Citation Pruning

As a user,
I want retrieval to filter low-signal results and cite only supporting evidence,
So that grounded answers stay precise in a mixed-source corpus.

**Acceptance Criteria:**

**Given** a mixed-source retrieval query,
**When** the search results are assembled,
**Then** chunks below a configurable relevance threshold are excluded from synthesis input.

**Given** an answer is synthesized,
**When** citations are returned,
**Then** the citation list includes only chunks or source records that materially support the answer rather than the full pre-filter retrieval set.

**Given** no result clears the relevance threshold,
**When** `retrieve` completes,
**Then** it returns the normal no-relevant-content behavior rather than forcing a weakly grounded answer.

**Given** the filtered retrieval path runs under normal conditions,
**When** it is measured end to end,
**Then** it remains within the existing retrieval latency target.

---

### Story 6.14: Single-Source Factual Grounding for `retrieve`

As a user,
I want direct factual questions to stay grounded in the source actually being asked about,
So that the answer layer does not blend facts across similar but distinct records.

**Acceptance Criteria:**

**Given** a direct factual query about one apparent source item,
**When** the retrieval service prepares synthesis context,
**Then** it defaults to evidence from the best matching single source locator or document version rather than mixing multiple unrelated source items.

**Given** a query explicitly asks for synthesis, comparison, or aggregation,
**When** retrieval runs,
**Then** multi-source evidence remains allowed.

**Given** a single-source grounded answer is returned,
**When** citations are inspected,
**Then** they point to the same source lineage that supports the factual claim.

**Given** a mixed-source corpus containing semantically similar Gmail, local-file, or MCP-note records,
**When** a factual lookup is tested,
**Then** the answer does not import unsupported facts from sibling records.

---

### Story 6.15: Gmail Processed-Message Semantics and Requeue Prevention

As an operator,
I want Gmail sync to skip already-processed matching messages by default,
So that normal operation does not keep re-scanning and re-queueing work that has already completed successfully.

**Acceptance Criteria:**

**Given** a Gmail message body or attachment source has already been processed successfully,
**When** the same message still matches the configured query on a later sync,
**Then** the connector skips re-queueing it by default.

**Given** a Gmail message changes in a way that should be treated as new ingestable content or a new source observation,
**When** sync runs,
**Then** the connector still submits the appropriate work safely.

**Given** the connector resumes after restart,
**When** it evaluates whether to queue matching Gmail content,
**Then** processed-message bookkeeping survives restart and does not depend on in-memory state.

**Given** the operator needs to intentionally reprocess Gmail content,
**When** they follow the documented recovery path,
**Then** a supported override exists without requiring manual database surgery.

## Epic 7: Retrieval Trust, Evaluation & Observability

Retrieval quality is measured and hardened before broader ambient expansion. The platform gains an explicit evaluation corpus, benchmark harness, structured observability, and stricter evidence-selection rules so later Telegram, web, and scheduling features amplify a trustworthy retrieval layer rather than a fragile one.
**FRs covered:** FR11, FR12, FR13, FR17
**NFRs:** NFR1, NFR3, NFR12

### Story 7.1: Retrieval Evaluation Corpus & Benchmark Harness

As Iain (operator and maintainer),
I want a repeatable retrieval evaluation corpus and harness,
So that future retrieval changes can be compared against a stable baseline instead of being judged ad hoc.

**Acceptance Criteria:**

**Given** the benchmark assets are reviewed,
**When** the corpus layout is inspected,
**Then** it contains a generated candidate layer, a curated gold benchmark layer, and a stress/fuzz layer with a documented schema.

**Given** benchmark queries are prepared,
**When** they are classified,
**Then** they cover direct fact lookup, exact phrase lookup, date/timeline, single-document interpretation, cross-document synthesis, briefing-style prompts, and no-answer cases.

**Given** a benchmark run is executed,
**When** the harness completes,
**Then** it emits a structured report showing retrieval recall, citation precision, answerability handling, and latency per query class.

---

### Story 7.2: Retrieval Observability & Structured Eval Logging

As an operator,
I want retrieval and synthesis runs to emit structured metrics and traceable benchmark output,
So that I can understand which provider, latency, and evidence path produced a result.

**Acceptance Criteria:**

**Given** a retrieval query runs,
**When** logs are emitted,
**Then** they include query type, candidate counts, filtered evidence counts, latency, and the model/provider used for synthesis without logging sensitive content or secrets.

**Given** a benchmark run is executed,
**When** results are written,
**Then** each query record includes pass/fail status, timings, and machine-readable metadata that can be compared across runs.

**Given** a retrieval regression occurs,
**When** the operator reviews the benchmark output,
**Then** they can identify whether the change came from retrieval candidate selection, evidence filtering, citation formatting, or synthesis.

---

### Story 7.3: Retrieval Evidence Selection & Citation Precision Hardening

As a user,
I want answers and citations to reflect only the evidence that actually supports the response,
So that grounded Q&A remains trustworthy as the corpus becomes more mixed and connected.

**Acceptance Criteria:**

**Given** a retrieval candidate set is assembled,
**When** synthesis begins,
**Then** a configurable relevance floor is applied before evidence is passed to the model.

**Given** an answer is returned,
**When** citations are emitted,
**Then** only evidence items that survived filtering and were eligible to support the answer are cited.

**Given** retrieval does not find sufficient grounded evidence,
**When** the request completes,
**Then** the platform returns a clear insufficient-evidence outcome rather than forcing a weakly grounded synthesis.

---

### Story 7.4: Document-First Retrieval & Context Expansion

As a user,
I want retrieval to preserve more document context when needed,
So that answers are less brittle on single-document and bounded-context questions.

**Acceptance Criteria:**

**Given** a query is classified as a bounded or document-centric question,
**When** retrieval runs,
**Then** documents are ranked before chunk-level expansion so the platform can preserve local context more effectively.

**Given** a highly ranked chunk is selected,
**When** context expansion is applied,
**Then** adjacent or parent context is included according to documented rules rather than passing isolated fragments only.

**Given** the benchmark harness is rerun after this change,
**When** results are compared to the prior baseline,
**Then** bounded-context query classes improve or hold steady with no material regression in direct factual lookup.

---

### Story 7.5: Operator Validation — Retrieval Trust Regression Suite

As Iain (operator and first maintainer),
I want a documented retrieval trust validation pass,
So that Epic 8 and later growth work starts only after the grounded-answer baseline is proven stable.

**Acceptance Criteria:**

**Given** the evaluation corpus and hardening work are complete,
**When** the validation suite is run against a representative mixed-source corpus,
**Then** benchmark results are captured and attached to the implementation artifact.

**Given** direct factual prompts are included in the validation set,
**When** answers are inspected,
**Then** single-source questions remain grounded to a single supporting lineage unless the prompt explicitly requests synthesis.

**Given** latency-sensitive query classes are measured,
**When** results are reviewed,
**Then** interactive retrieval remains within the project’s stated performance expectations or the gap is documented explicitly.

---

### Story 7.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want the retrieval trust layer documented clearly,
So that future BMAD workflows and implementation stories treat benchmarking and observability as part of the platform contract rather than optional extras.

**Acceptance Criteria:**

**Given** the retrieval trust work is complete,
**When** `architecture.md` and `architecture-diagrams.md` are reviewed,
**Then** they describe the evaluation harness, evidence-selection contract, and sequenced placement of retrieval hardening before Telegram/web/scheduler features.

**Given** operator-facing docs are reviewed,
**When** they are updated,
**Then** they explain how to run the benchmark harness, where reports are stored, and how to interpret retrieval regressions.

**Given** all Epic 7 documents are cross-checked,
**When** reviewed together,
**Then** benchmark terminology, evidence-selection rules, and observability fields are consistent across PRD, architecture, epics, and sprint tracking.

## Epic 8: Interactive Telegram Messaging

Users interact reactively with the platform through Telegram — asking questions and capturing notes — without yet depending on web augmentation or proactive scheduling. This is the smallest end-user messaging slice that validates mobile access and message-driven capture on top of the hardened retrieval base.
**FRs covered:** FR9, FR34
**NFRs:** NFR11, NFR20

### Story 8.1: Telegram Bot Setup & Output Channel

As an operator,
I want to configure a Telegram bot that the platform can send messages to and receive messages from,
So that Telegram is a live, verified channel before Q&A and note capture are built on top of it.

**Acceptance Criteria:**

**Given** a Telegram bot token is present in `config.yaml` under `connectors.telegram.bot_token`,
**When** the `cos` container starts with Telegram enabled,
**Then** `telegram_bot.py` begins polling the Telegram Bot API for updates using long-polling with graceful backoff.

**Given** `output/channels/telegram.py` is implemented,
**When** `OutputRouter.send(channel="telegram", content="test message")` is called,
**Then** the message is delivered to the configured Telegram chat ID only after the router validates the `telegram` channel against the allowed output channels.

**Given** Telegram delivery fails,
**When** the error is handled,
**Then** output is suppressed, a structured error is logged with `component: "output"`, and the rest of the platform remains healthy.

---

### Story 8.2: Telegram Inbound Q&A

As a user,
I want to send a question to the platform via Telegram and receive a cited answer,
So that I can access my knowledge base from my phone without opening a laptop or separate interface.

**Acceptance Criteria:**

**Given** a message is received via the Telegram bot,
**When** the message classifier runs,
**Then** it identifies questions using documented heuristics and routes them to the reactive Q&A path.

**Given** a message is classified as a question,
**When** the Q&A path executes,
**Then** it calls `RetrievalService.query(...)` and delivers a concise Telegram-appropriate cited reply via `OutputRouter.send(channel="telegram")`.

**Given** no relevant grounded content is found or synthesis fails,
**When** the reply is sent,
**Then** the user receives a clear plain-language outcome rather than silence or an uncaught error.

---

### Story 8.3: Telegram Note Capture

As a user,
I want to send a short note or thought to the platform via Telegram and have it saved immediately,
So that in-the-moment capture becomes part of the searchable knowledge base.

**Acceptance Criteria:**

**Given** a message is classified as a note,
**When** the note capture path executes,
**Then** it routes the content into the Epic 6 ingest/job substrate with Telegram metadata including sender and timestamp.

**Given** the note is ingested successfully,
**When** confirmation is returned,
**Then** the user receives a short acknowledgement such as `"Note saved."`.

**Given** the note has been ingested,
**When** `list_documents` or `retrieve` is used later,
**Then** the note appears as a first-class document with canonical provenance and searchable content.

---

### Story 8.4: Operator Validation — Interactive Telegram Live

As Iain (operator and first user),
I want a documented end-to-end smoke test for the reactive Telegram slice,
So that I can validate interactive messaging before adding web or scheduler complexity.

**Acceptance Criteria:**

**Given** the Telegram bot is configured and the platform is running,
**When** a question is sent from a Telegram client,
**Then** a cited answer is received within a reasonable interactive response time.

**Given** a note is sent prefixed with `"Note:"`,
**When** the platform processes it,
**Then** a confirmation is received and a later retrieval query can cite the note.

**Given** the Telegram Bot API is temporarily unavailable,
**When** the failure is simulated,
**Then** Telegram is reported as degraded while local MCP retrieval continues to function normally.

---

### Story 8.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all documentation updated to reflect the interactive Telegram slice only,
So that users and future agents do not assume web augmentation or proactive briefings are already part of this epic.

**Acceptance Criteria:**

**Given** `docs/connectors.md` is updated for Epic 8,
**When** it is reviewed,
**Then** it covers Telegram setup, testing, inbound Q&A, and note capture without implying that morning briefs or web search are already included in the same delivery slice.

**Given** a user-facing guide is updated,
**When** it is reviewed,
**Then** it explains how to ask questions and capture notes through Telegram in plain language.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** the Telegram capability is described consistently as reactive messaging only.

## Epic 9: LLM-Maintained Wiki & Derived Knowledge Layer

The platform adds a derived, rebuildable wiki layer on top of existing source ingestion, canonical storage, Markdown working copies, retrieval, jobs, and MCP foundations. The wiki is a governed synthesis layer for orientation and cross-document memory; raw originals and normalized Markdown remain the authoritative substrate, and every wiki page retains source citations.
**FRs covered:** Vision-track derived knowledge layer; supports FR11, FR13, FR17, FR18, FR21, FR37, FR38
**NFRs:** NFR1, NFR12, NFR14, NFR15

### Story 9.1: Wiki Schema, Storage & Page Model

As an operator,
I want the platform to have an explicit wiki storage root and metadata schema,
So that derived wiki pages can be persisted without becoming a second source of truth.

**Acceptance Criteria:**

**Given** the configuration model is reviewed,
**When** wiki storage is added,
**Then** `CosConfig.storage` includes a `wiki_dir` path with a documented default of `/data/wiki`.

**Given** migrations are applied,
**When** the database schema is inspected,
**Then** wiki metadata tables exist for pages, page versions, citations, and page links using the repository's raw SQL migration conventions.

**Given** a wiki page record is created,
**When** its type and slug are validated,
**Then** the page follows a documented taxonomy and filesystem layout for at least topic, person, project, and decision pages.

**Given** the app starts with no existing wiki directory,
**When** wiki storage is initialized,
**Then** `data/wiki/` can be created without disturbing originals, Markdown working copies, chunks, embeddings, or retrieval state.

---

### Story 9.2: Wiki Metadata Service & Citation Contract

As a maintainer,
I want a service boundary for wiki page metadata, versions, citations, and links,
So that future compilers and read tools use one governed contract.

**Acceptance Criteria:**

**Given** `src/cos/services/` is the cross-module boundary,
**When** wiki service code is added,
**Then** callers can create, update, list, and load wiki page metadata through `cos.services` rather than importing store internals directly.

**Given** a wiki page cites source material,
**When** citations are stored,
**Then** each citation links to canonical source lineage using `document_version_id` and source alias metadata, with chunk anchors where available.

**Given** a wiki page is updated,
**When** the rendered content changes,
**Then** a new page version is recorded without overwriting source artifacts or losing prior wiki provenance.

**Given** page links are stored,
**When** a page references another page,
**Then** the relationship is queryable for index and freshness workflows.

---

### Story 9.3: Markdown Corpus Compiler v1

As a user,
I want the platform to compile useful wiki pages from normalized Markdown,
So that I can browse durable summaries and entity/context pages grounded in my corpus.

**Acceptance Criteria:**

**Given** normalized Markdown working copies exist,
**When** the compiler runs,
**Then** it reads Markdown plus canonical provenance metadata rather than raw binaries or retrieval snippets alone.

**Given** fixture Markdown inputs are compiled,
**When** topic and decision page outputs are generated,
**Then** the rendered Markdown is deterministic for unchanged inputs and includes source citation references.

**Given** source content changes,
**When** the compiler reruns,
**Then** changed upstream content creates a new wiki page version or marks the existing page stale before refresh.

**Given** no useful source evidence exists for a candidate page,
**When** compilation is attempted,
**Then** the compiler avoids creating uncited generated claims.

---

### Story 9.4: Wiki Compile Jobs & Rebuild CLI

As an operator,
I want wiki compilation to use the existing jobs substrate and have explicit rebuild commands,
So that derived pages can be maintained and repaired without manual database work.

**Acceptance Criteria:**

**Given** the existing `jobs` table and worker pattern,
**When** wiki compilation work is queued,
**Then** it uses a distinct job type such as `wiki_compile` with bounded retry and failure visibility.

**Given** an operator runs `cos wiki compile`,
**When** target inputs are provided,
**Then** the command compiles the requested page or page family and reports the result.

**Given** an operator runs `cos wiki rebuild`,
**When** the current corpus is available,
**Then** the wiki can be regenerated from Markdown and provenance metadata without hand-editing rows.

**Given** an operator runs `cos wiki status`,
**When** wiki health is inspected,
**Then** page counts, stale page counts, and recent compile failures are visible.

---

### Story 9.5: MCP & CLI Wiki Read Surface

As a user,
I want to list and read wiki pages through the platform interfaces,
So that the derived knowledge layer is useful before it changes retrieval behavior.

**Acceptance Criteria:**

**Given** wiki pages exist,
**When** an MCP client calls `list_wiki_pages`,
**Then** it receives page identity, type, title, slug, freshness, and compiled-at metadata in the standard response envelope.

**Given** a page slug or id is provided,
**When** an MCP client calls `get_wiki_page`,
**Then** it receives rendered Markdown plus underlying source citations.

**Given** an operator uses the CLI,
**When** they list or read wiki pages locally,
**Then** the output matches the MCP read contract closely enough for debugging and handoff.

**Given** existing `retrieve`, `answer`, `list_documents`, and `get_role_context` tools are exercised,
**When** wiki read tools are added,
**Then** their current behavior remains unchanged.

---

### Story 9.6: Compile-on-Ingest Change Propagation

As a user,
I want wiki pages to update when the corpus changes,
So that the wiki remains a current derived view rather than a stale snapshot.

**Acceptance Criteria:**

**Given** a new or changed source is ingested,
**When** ingestion succeeds,
**Then** the platform can enqueue targeted wiki compilation work for affected page candidates.

**Given** an ingest result is unchanged or a duplicate,
**When** change propagation is evaluated,
**Then** duplicate wiki work is avoided unless an operator forces a recompile.

**Given** an upstream document version changes,
**When** dependent wiki pages are known,
**Then** those pages are marked stale until the next successful compile.

**Given** wiki compile jobs fail,
**When** operator status is inspected,
**Then** failure details are visible without breaking normal ingestion or retrieval.

---

### Story 9.7: Freshness, Linting & Governance Controls

As an operator,
I want the wiki to expose freshness and grounding issues,
So that synthesized pages do not become an ungoverned second truth store.

**Acceptance Criteria:**

**Given** wiki pages exist,
**When** linting runs,
**Then** it can detect stale pages, missing citations, orphan pages, duplicate entity candidates, and broken page links.

**Given** a page has weak or missing grounding,
**When** it is listed or loaded,
**Then** the response includes a clear freshness or grounding signal.

**Given** an operator wants to repair wiki health,
**When** repair commands are run,
**Then** stale or invalid pages can be recompiled or flagged without manual database surgery.

**Given** sensitive page types such as people or decisions are produced,
**When** governance metadata is reviewed,
**Then** the operator can identify source lineage and compile history.

---

### Story 9.8: Wiki-Assisted Synthesis Routing Decision Gate

As a maintainer,
I want a deliberate decision gate before wiki-assisted answers become part of normal retrieval,
So that source-first citation behavior remains stable until the wiki is proven trustworthy.

**Acceptance Criteria:**

**Given** wiki read tools and validation evidence exist,
**When** query routing is designed,
**Then** direct factual questions remain source-first by default.

**Given** synthesis-heavy prompts such as briefings, comparisons, and orientation questions are evaluated,
**When** the wiki is used as condensed context,
**Then** final answers still cite underlying source material rather than wiki pages alone.

**Given** routing confidence is low,
**When** a query is classified,
**Then** the platform defaults back to source-first retrieval.

**Given** wiki assistance is used,
**When** the response is returned,
**Then** the user can tell that wiki assistance contributed to the answer.

---

### Story 9.9: Operator Validation - Browsable Wiki with Source Citations

As Iain,
I want an end-to-end validation pass for the wiki layer,
So that I can confirm the derived knowledge layer is useful, cited, and rebuildable before routing depends on it.

**Acceptance Criteria:**

**Given** a representative corpus is ingested,
**When** wiki compilation runs,
**Then** topic and decision pages are generated with readable Markdown and source citations.

**Given** the wiki is rebuilt from the current corpus,
**When** outputs are compared,
**Then** unchanged inputs do not create duplicate page versions or uncited drift.

**Given** MCP and CLI read paths are exercised,
**When** pages are listed and loaded,
**Then** citation metadata, freshness metadata, and rendered content are visible.

**Given** existing retrieval validation is rerun,
**When** wiki functionality is present,
**Then** source-first `retrieve` and `answer` behavior remains stable.

---

### Story 9.10: Documentation & Housekeeping

As Iain,
I want the LLM wiki layer documented as a derived, governed knowledge layer,
So that future BMAD work does not confuse it with source truth or ordinary retrieval.

**Acceptance Criteria:**

**Given** Epic 9 is complete,
**When** architecture and operator docs are reviewed,
**Then** they explain originals as truth, Markdown as compiler input, wiki pages as derived artifacts, and Postgres metadata as governance.

**Given** setup and usage docs are updated,
**When** an operator reads them,
**Then** they can configure wiki storage, compile or rebuild the wiki, inspect status, and use MCP/CLI read tools.

**Given** roadmap artifacts are cross-checked,
**When** they are reviewed together,
**Then** Epic 9 numbering and downstream renumbering remain consistent across epics, sprint status, and active docs.

## Epic 10: Structured LLM Boundary & Provider Portability

The model boundary is upgraded before routing policy or local endpoint expansion. The platform gains richer request/response contracts, explicit model/provider metadata, and direct support for additional providers without disturbing retrieval or ingestion layers.
**FRs covered:** Supports the existing provider-agnostic intent behind FR17 and FR31
**NFRs:** NFR5, NFR6, NFR19

### Story 10.1: LLM Request/Response Contract & Metadata

As a maintainer,
I want a richer internal LLM contract than plain `complete(prompt, context)`,
So that future providers, audits, and workflow-specific model decisions have a stable interface.

**Acceptance Criteria:**

**Given** the LLM boundary is reviewed,
**When** the interface is updated,
**Then** it uses structured request/response objects that capture prompt intent, provider/model metadata, latency, and usage information.

**Given** the existing Anthropic path is exercised,
**When** the refactor lands,
**Then** current retrieval-based synthesis still works without changing ingestion or retrieval call sites beyond the new typed contract.

**Given** a response is returned,
**When** it is logged or surfaced to internal callers,
**Then** provider and model identifiers are available for audit and later routing logic.

---

### Story 10.2: OpenAI Provider Adapter

As an operator,
I want OpenAI to be a first-class provider option,
So that the platform is no longer tied to a single model vendor.

**Acceptance Criteria:**

**Given** OpenAI credentials and model settings are added to config,
**When** the provider is selected,
**Then** the platform can complete the same structured LLM requests through a native OpenAI adapter.

**Given** the adapter is used for grounded retrieval synthesis,
**When** representative queries are run,
**Then** the system returns responses through the same internal contract and audit fields as the Anthropic path.

**Given** configuration is invalid,
**When** startup or invocation occurs,
**Then** the platform returns a structured configuration or provider error instead of failing opaquely.

---

### Story 10.3: Gemini Provider Adapter

As an operator,
I want Gemini to be a first-class provider option,
So that provider diversity and fallback options improve further.

**Acceptance Criteria:**

**Given** Gemini credentials and model settings are added to config,
**When** the provider is selected,
**Then** the platform can execute the structured LLM request contract through a native Gemini adapter.

**Given** the Gemini adapter is used,
**When** benchmark retrieval prompts are run,
**Then** provider/model metadata and error semantics match the shared internal contract.

**Given** a provider-specific failure occurs,
**When** it is handled,
**Then** the failure is surfaced clearly without leaking secrets or breaking the rest of the platform.

---

### Story 10.4: Multi-Provider Config & Selection Semantics

As a maintainer,
I want the configuration model to support multiple registered providers cleanly,
So that later routing and fallback work can build on explicit product-level semantics rather than ad hoc flags.

**Acceptance Criteria:**

**Given** multiple providers are configured,
**When** the config is validated,
**Then** the active provider, model choice, and any workflow-level overrides follow a documented schema.

**Given** no routing policy has been introduced yet,
**When** a request is made,
**Then** selection still follows simple explicit semantics rather than implicit or opaque behavior.

**Given** provider configuration changes,
**When** tests and startup validation run,
**Then** the platform confirms that only supported, fully specified provider entries are accepted.

---

### Story 10.5: Operator Validation — Provider Portability

As Iain (operator and maintainer),
I want a portability validation pass across supported providers,
So that the platform proves the model boundary is genuinely swappable before later routing work starts.

**Acceptance Criteria:**

**Given** Anthropic plus at least one new provider are configured,
**When** the validation suite is run,
**Then** the same representative retrieval-driven prompts complete successfully on each provider.

**Given** provider metadata is reviewed,
**When** logs and result artifacts are inspected,
**Then** each run records the provider, model, and timing details cleanly.

**Given** a provider is unavailable,
**When** the validation path is exercised,
**Then** failure behavior is explicit and bounded rather than cascading through unrelated components.

---

### Story 10.6: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want the structured LLM boundary and provider setup documented,
So that future BMAD implementation work extends the same abstraction instead of inventing parallel patterns.

**Acceptance Criteria:**

**Given** Epic 10 is complete,
**When** architecture and setup documents are reviewed,
**Then** they describe the structured request/response boundary, provider registration, and audit metadata expectations.

**Given** operator docs are updated,
**When** they are reviewed,
**Then** they explain how to configure supported providers and interpret provider-specific validation output.

**Given** Epic 10 planning artifacts are cross-checked,
**When** reviewed together,
**Then** provider terminology and configuration semantics are consistent across PRD, architecture, epics, and sprint tracking.

## Epic 11: Web Augmentation & External Context

Local retrieval remains primary, but the platform can augment it with live external context once retrieval trust, interactive messaging, and provider portability are in place. This epic keeps web augmentation explicit and bounded rather than making it part of the first Telegram slice.
**FRs covered:** FR16
**NFRs:** NFR11

### Story 11.1: Web Search MCP Tool

As a user,
I want the platform to search the live web when local knowledge is insufficient,
So that grounded answers can incorporate current external context when needed.

**Acceptance Criteria:**

**Given** a web search API key is configured,
**When** a connected MCP client invokes `web_search`,
**Then** the platform returns results in the standard response envelope with structured web citations.

**Given** a query is submitted that local knowledge cannot answer well,
**When** `web_search` runs,
**Then** the returned results include titles, URLs, snippets, and a clear `source: "web"` marker.

**Given** the search API is unavailable,
**When** the tool is called,
**Then** a structured error response is returned and local retrieval remains available.

---

### Story 11.2: Local + Web Citation Contract

As a user,
I want mixed local and web evidence to stay distinguishable,
So that I can tell what came from my knowledge base versus the live internet.

**Acceptance Criteria:**

**Given** local and web results are both available,
**When** the citation structure is reviewed,
**Then** local citations retain canonical provenance fields while web citations retain URL-based provenance with no ambiguity between the two.

**Given** synthesis is performed over mixed evidence,
**When** the response is returned,
**Then** it distinguishes local citations from web citations clearly enough for follow-up and audit.

**Given** no useful web evidence is found,
**When** the run completes,
**Then** the response falls back cleanly to local-only behavior or an explicit insufficient-context outcome.

---

### Story 11.3: Web Search Cache & Failure Handling

As an operator,
I want web augmentation to be cost-aware and failure-tolerant,
So that external-context lookup does not create unnecessary spend or brittle runtime behavior.

**Acceptance Criteria:**

**Given** the same query is submitted repeatedly within a configured cache window,
**When** `web_search` is called,
**Then** cached results are returned instead of making duplicate paid requests.

**Given** a web provider error or rate limit occurs,
**When** it is handled,
**Then** the platform logs a bounded connector failure and returns a structured error envelope.

**Given** logging is reviewed,
**When** web requests are inspected,
**Then** query metadata is visible without logging API key material.

---

### Story 11.4: Operator Validation — Web-Augmented Retrieval

As Iain (operator and maintainer),
I want a documented validation pass for web-augmented retrieval,
So that current-external-context behavior is verified before proactive briefing flows depend on it.

**Acceptance Criteria:**

**Given** the web search tool is configured,
**When** representative current-context prompts are tested,
**Then** results show correct envelope structure and clear distinction between local and web evidence.

**Given** a failure mode is simulated,
**When** the provider is unavailable,
**Then** local retrieval remains usable and the failure is surfaced explicitly.

**Given** validation artifacts are reviewed,
**When** they are checked in the implementation artifact,
**Then** they show both successful augmentation cases and bounded-failure cases.

---

### Story 11.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want web augmentation documented as a separate later growth layer,
So that future work does not treat it as interchangeable with local retrieval or the initial Telegram slice.

**Acceptance Criteria:**

**Given** Epic 11 documentation is reviewed,
**When** it is updated,
**Then** it explains configuration, validation, and mixed local/web citation behavior.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** web augmentation is described consistently as an opt-in later layer on top of local retrieval.

**Given** user-facing guidance is updated,
**When** it is reviewed,
**Then** it sets expectations about what kinds of answers may use live external context.

## Epic 12: Proactive Briefings & Meeting Prep

Proactive scheduling follows validated retrieval, interactive messaging, and web-augmentation layers. The platform can now deliver morning briefs and meeting prep through configured channels without bundling those behaviors into the first reactive Telegram implementation.
**FRs covered:** FR19, FR20, FR35
**NFRs:** NFR11, NFR14

### Story 12.1: Scheduler Infrastructure & Morning Brief

As a user,
I want to receive a proactive morning brief at a configured time each day,
So that the platform surfaces relevant knowledge before I start work, without me needing to ask.

**Acceptance Criteria:**

**Given** APScheduler is integrated and a brief time plus outbound channel are configured,
**When** the scheduler triggers,
**Then** it gathers the necessary context, generates a brief, and delivers it through `OutputRouter`.

**Given** a morning brief is delivered,
**When** the output is reviewed,
**Then** it is formatted appropriately for the channel and cites relevant knowledge-base context where available.

**Given** the platform restarts between jobs,
**When** it comes back up,
**Then** scheduled jobs resume without manual repair.

---

### Story 12.2: Meeting Prep from Calendar Events

As a user,
I want to receive contextual prep notes before calendar meetings,
So that I arrive at meetings with relevant knowledge already surfaced.

**Acceptance Criteria:**

**Given** a meeting-prep interval is configured,
**When** an event approaches the threshold,
**Then** the scheduler retrieves relevant meeting context and delivers a concise prep note through the configured output channel.

**Given** no relevant knowledge-base content exists for a meeting,
**When** the prep job runs,
**Then** the platform still returns a useful bounded outcome rather than remaining silent.

**Given** multiple meetings fall inside the prep window,
**When** the scheduler evaluates them,
**Then** each event is handled independently.

---

### Story 12.3: Delivery Failure Handling & Job Visibility

As an operator,
I want proactive delivery failures to be visible and recoverable,
So that one bad delivery does not silently disable scheduled behavior.

**Acceptance Criteria:**

**Given** a scheduled delivery fails,
**When** the error is handled,
**Then** it is logged with `component: "scheduler"` and recorded against the corresponding job/task state.

**Given** one scheduled job fails,
**When** the next scheduled run occurs,
**Then** later jobs still execute normally rather than stalling the scheduler.

**Given** operator diagnostics are reviewed,
**When** logs or status output are inspected,
**Then** they show enough information to distinguish retrieval failure, generation failure, and channel-delivery failure.

---

### Story 12.4: Operator Validation — Proactive Briefings Live

As Iain (operator and first user),
I want a documented end-to-end validation pass for proactive briefings,
So that scheduled value delivery is proven after the reactive and trust layers are already stable.

**Acceptance Criteria:**

**Given** the schedule is configured for near-term testing,
**When** a morning brief run is triggered,
**Then** the brief arrives in the configured channel with the expected structure and citations.

**Given** a calendar-driven meeting-prep test is run,
**When** the prep event reaches the configured interval,
**Then** a concise prep message is delivered successfully.

**Given** a delivery failure is simulated,
**When** validation is reviewed,
**Then** the failure is visible, bounded, and does not stop later scheduled runs.

---

### Story 12.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want the proactive scheduling layer documented clearly,
So that it remains distinct from the earlier Telegram and web-augmentation slices.

**Acceptance Criteria:**

**Given** proactive-briefing documentation is updated,
**When** it is reviewed,
**Then** it explains scheduler configuration, morning brief behavior, meeting prep behavior, and failure handling.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** proactive scheduling is described consistently as the growth layer that follows retrieval trust, Telegram, and web augmentation.

**Given** user-facing guidance is reviewed,
**When** it is updated,
**Then** it sets expectations about what will be delivered proactively and when.

## Epic 13: Agent-Safe Task Runtime

The platform gains a durable task substrate for asynchronous, resumable, approval-aware work only after the first real user flows are in place. This is a platformization epic, not a free-form autonomous-agent leap.
**FRs covered:** Vision-track platform foundation; no direct MVP/Growth FR closure
**NFRs:** NFR10, NFR12, NFR14

### Story 13.1: General Task Records & State Model

As a maintainer,
I want the current jobs substrate generalized into a task model,
So that non-ingest async work can be represented durably and consistently.

**Acceptance Criteria:**

**Given** the task runtime design is reviewed,
**When** the schema is implemented,
**Then** it introduces a durable task entity with explicit lifecycle states, ownership, timestamps, and idempotent identifiers.

**Given** a non-ingest async workflow is created,
**When** it is persisted,
**Then** it uses the same task model rather than inventing a parallel queue concept.

**Given** existing ingest work is reviewed,
**When** migration boundaries are documented,
**Then** the relationship between the legacy jobs flow and the generalized task model is explicit.

---

### Story 13.2: Task Events, Artifacts & Audit Trail

As an operator,
I want long-running tasks to leave behind a readable event and artifact trail,
So that progress and outcomes can be reconstructed after the fact.

**Acceptance Criteria:**

**Given** a task executes over multiple steps,
**When** state changes occur,
**Then** the platform records step-level events and generated artifacts in durable storage.

**Given** an operator reviews a task run,
**When** they inspect the task history,
**Then** they can see what happened, when it happened, and what outputs were produced.

**Given** a failure occurs mid-task,
**When** the audit trail is reviewed,
**Then** the failure point is identifiable without reconstructing behavior from raw container logs alone.

---

### Story 13.3: Pause/Resume & Approval Gates

As a user and operator,
I want long-running workflows to pause, resume, and wait for approval explicitly,
So that the platform can support durable iterative work without becoming opaque or unsafe.

**Acceptance Criteria:**

**Given** a task reaches an approval boundary,
**When** execution pauses,
**Then** the platform records a pending approval state instead of continuing implicitly.

**Given** an approved task is resumed,
**When** execution continues,
**Then** it resumes from the recorded checkpoint rather than replaying the entire workflow blindly.

**Given** a task is cancelled or times out,
**When** the runtime handles it,
**Then** final state is explicit and side effects remain auditable.

---

### Story 13.4: Operator Validation — Task Runtime

As Iain (operator and maintainer),
I want a validation pass for the generalized task runtime,
So that resumability and approval-aware behavior are proven before heavier routing or orchestration patterns are added.

**Acceptance Criteria:**

**Given** representative async tasks are exercised,
**When** validation runs,
**Then** task creation, pause/resume, cancellation, and completion states all persist correctly.

**Given** a failure or restart occurs mid-task,
**When** the runtime recovers,
**Then** task state remains consistent and restart behavior is documented.

**Given** approval-gated flows are tested,
**When** validation results are reviewed,
**Then** they show that human intervention boundaries are explicit and durable.

---

### Story 13.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want the task runtime documented as a narrow durable substrate,
So that future BMAD workflows do not mistake it for a fully autonomous orchestration engine.

**Acceptance Criteria:**

**Given** Epic 13 documentation is updated,
**When** it is reviewed,
**Then** it explains the task model, event/artifact records, and approval/resume semantics.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** the task runtime is described consistently as a platform foundation layer that follows the first real user features.

**Given** future implementation guidance is reviewed,
**When** it is updated,
**Then** it warns against bypassing the task model with ad hoc long-running loops.

## Epic 14: Internal Model Routing & Local Endpoints

Routing policy and OpenAI-compatible local endpoint support build on the richer provider boundary from Epic 10 and the durable task/platform substrate from Epic 13. The platform owns routing policy internally rather than delegating that responsibility to an external aggregator by default.
**FRs covered:** Vision-track platform portability; no direct MVP/Growth FR closure
**NFRs:** NFR5, NFR6, NFR19

### Story 14.1: Provider Registry & Routing Policy Scaffold

As a maintainer,
I want an internal provider registry and routing policy scaffold,
So that model selection becomes explicit product behavior instead of a hidden infrastructure detail.

**Acceptance Criteria:**

**Given** multiple providers are available,
**When** the routing scaffold is implemented,
**Then** provider registration, capabilities, and policy hooks are represented in a documented internal model.

**Given** no advanced policy has been enabled yet,
**When** a request is routed,
**Then** selection remains deterministic and traceable.

**Given** logs or task artifacts are reviewed,
**When** a model-handled response is inspected,
**Then** the selected provider and policy path are visible for audit.

---

### Story 14.2: OpenAI-Compatible Local Endpoint Adapter

As an operator,
I want the platform to support OpenAI-compatible local or self-hosted model endpoints,
So that local-model experimentation and private inference paths remain open.

**Acceptance Criteria:**

**Given** an OpenAI-compatible endpoint such as Ollama or vLLM is configured,
**When** the adapter is selected,
**Then** the platform can execute the shared structured LLM contract against that endpoint.

**Given** local endpoint behavior differs from frontier APIs,
**When** validation runs,
**Then** capability or quality limitations are surfaced explicitly rather than hidden.

**Given** configuration is invalid or the endpoint is unavailable,
**When** the adapter is exercised,
**Then** failure is bounded and does not break unrelated providers.

---

### Story 14.3: Pinned, Fallback & Workflow-Based Routing

As a maintainer,
I want a small set of explicit routing modes,
So that the platform gains practical flexibility without becoming an opaque policy engine too early.

**Acceptance Criteria:**

**Given** routing is configured,
**When** a request is made,
**Then** the platform supports at least pinned provider selection, ordered fallback, and workflow-based selection semantics.

**Given** a provider fails under fallback routing,
**When** another provider is available,
**Then** the failover path is recorded explicitly and remains auditable.

**Given** workflow-based routing is used,
**When** task or retrieval artifacts are reviewed,
**Then** they show why the chosen route was used.

---

### Story 14.4: Operator Validation — Routing & Local Endpoints

As Iain (operator and maintainer),
I want a validation pass for routing behavior and local endpoint support,
So that the platform proves routing policy works before more advanced retrieval/orchestration pilots depend on it.

**Acceptance Criteria:**

**Given** pinned, fallback, and workflow-based modes are configured,
**When** validation runs,
**Then** each mode shows the expected provider selection behavior.

**Given** a local endpoint is configured,
**When** representative prompts are executed,
**Then** results and limitations are captured in the validation artifact.

**Given** provider failure scenarios are exercised,
**When** results are reviewed,
**Then** fallback behavior is explicit and bounded.

---

### Story 14.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want routing and local-endpoint support documented clearly,
So that future implementation work builds on explicit internal policy rather than relying on undocumented assumptions.

**Acceptance Criteria:**

**Given** Epic 14 documentation is updated,
**When** it is reviewed,
**Then** it explains supported routing modes, provider registry expectations, and local-endpoint configuration.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** routing is described consistently as an internal platform policy layer added after provider portability is already in place.

**Given** operator guidance is reviewed,
**When** it is updated,
**Then** it explains how to validate routing behavior and interpret fallback outcomes.

## Epic 15: Advanced Retrieval Modes & Orchestration Pilots

More complex retrieval and orchestration work is explicitly gated behind benchmarks and prior platform layers. The goal is to explore full-context retrieval, hierarchical summaries, graph retrieval, and orchestration adoption only where they outperform the established baseline for the right query classes.
**FRs covered:** Vision-track experimentation; no direct MVP/Growth FR closure
**NFRs:** NFR1, NFR12, NFR19

### Story 15.1: Full-Context Retrieval Mode Pilot

As a maintainer,
I want to pilot a full-context retrieval mode for bounded tasks,
So that single-document and tightly scoped questions can preserve more original context where chunking is harmful.

**Acceptance Criteria:**

**Given** bounded-context query classes are identified,
**When** the pilot runs,
**Then** the platform can pass larger contiguous context or whole candidate documents to the model under documented limits.

**Given** the benchmark harness is rerun,
**When** pilot results are compared to the baseline,
**Then** the pilot is judged on factuality, citation discipline, latency, and cost rather than intuition alone.

**Given** the pilot underperforms,
**When** results are reviewed,
**Then** the mode remains experimental rather than becoming the default.

---

### Story 15.2: Hierarchical Summary Retrieval Pilot

As a maintainer,
I want to pilot hierarchical summary retrieval,
So that briefing-style and corpus-wide synthesis questions can be evaluated against the baseline chunk-retrieval approach.

**Acceptance Criteria:**

**Given** summary layers are generated,
**When** they are stored,
**Then** their relationship to source evidence remains inspectable and grounded.

**Given** briefing-style benchmark queries are run,
**When** pilot results are compared,
**Then** the pilot is judged on summary quality, grounding, latency, and maintenance overhead.

**Given** summary drift or grounding concerns appear,
**When** the pilot is reviewed,
**Then** those risks are documented explicitly before any broader adoption decision.

---

### Story 15.3: Graph Retrieval Pilot

As a maintainer,
I want to pilot graph-based retrieval for relationship-heavy questions,
So that the platform can test whether graph structure earns its complexity on the query classes where it might help most.

**Acceptance Criteria:**

**Given** a bounded slice of the corpus is selected,
**When** graph extraction and indexing are piloted,
**Then** entities, relationships, and provenance mappings are limited to a documented experimental scope.

**Given** relationship-heavy benchmark queries are run,
**When** results are compared to the baseline,
**Then** gains or losses are measured explicitly rather than assumed.

**Given** the graph pilot does not outperform the simpler baseline where expected,
**When** the decision is recorded,
**Then** graph retrieval remains experimental and non-default.

---

### Story 15.4: Orchestration Adoption Decision Record

As an architect and maintainer,
I want an explicit build-vs-adopt decision record for durable orchestration,
So that the platform does not drift into a homegrown workflow engine without a deliberate review.

**Acceptance Criteria:**

**Given** the task runtime and later pilots are in place,
**When** orchestration options are reviewed,
**Then** the decision record compares extending the native runtime against adopting a durable external engine.

**Given** evaluation criteria are applied,
**When** the decision is made,
**Then** it considers workflow complexity, resume semantics, approval gates, outages, replay/idempotency burden, and operational cost.

**Given** the decision is approved,
**When** future BMAD planning work starts,
**Then** it references the recorded decision instead of reopening the question implicitly in unrelated stories.

---

### Story 15.5: Documentation & Housekeeping

As Iain (operator and platform maintainer),
I want all advanced retrieval and orchestration pilot work documented clearly,
So that experimental layers remain distinguishable from the production baseline.

**Acceptance Criteria:**

**Given** Epic 15 documentation is updated,
**When** it is reviewed,
**Then** it describes each pilot, the benchmark gates, and the non-default status of experimental modes.

**Given** architecture and epic documents are cross-checked,
**When** reviewed together,
**Then** they show that advanced retrieval and orchestration work occurs only after the earlier approved post-Epic-6 roadmap sequence.

**Given** future planning artifacts are created,
**When** they are reviewed,
**Then** they can trace later experimentation back to these documented pilots and decision gates.
