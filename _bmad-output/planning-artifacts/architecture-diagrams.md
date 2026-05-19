---
type: 'architecture-diagrams'
architectureRef: 'architecture.md'
date: '2026-05-15'
---

# CoS Platform — Architecture Diagrams

Companion to `architecture.md`. All diagrams are derived from the decisions recorded there and supersede the diagrams in `initial_docs/shared_cos_platform_diagrams_and_handoff.md`.

---

## 1. System Context (C4 Level 1)

### Phase 1 — Builder Validation

```mermaid
C4Context
    title CoS Platform — System Context (Phase 1)

    Person(iain, "Iain (Operator / User)", "Sets up instances, ingests documents via CLI, queries knowledge via Claude Desktop")

    System(cos, "CoS Platform", "Local-first AI knowledge platform running in Docker Compose. Ingest → retrieve → reason → cite.")

    System_Ext(claude_desktop, "Claude Desktop", "MCP client. Primary query interface in Phase 1. Connects to CoS via stdio transport.")
    System_Ext(claude_api, "Claude API (Anthropic)", "LLM reasoning and synthesis. Called over HTTPS with retrieved document chunks.")
    System_Ext(embedding_api, "Embedding Provider API", "Generates vector embeddings for document chunks. Configurable provider (default: text-embedding-3-small).")

    Rel(iain, cos, "Ingests documents, checks status, restarts", "Terminal / CLI")
    Rel(iain, claude_desktop, "Asks questions, reads cited answers")
    Rel(claude_desktop, cos, "MCP tool calls: retrieve, get_role_context, list_documents, get_status", "stdio / MCP 2025-11-25")
    Rel(cos, claude_api, "Sends retrieved chunks + query for synthesis", "HTTPS")
    Rel(cos, embedding_api, "Sends text chunks for vectorisation during ingestion", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### Growth Roadmap End-State (sequenced delivery after Epic 6)

```mermaid
C4Context
    title CoS Platform — System Context (Growth roadmap end-state)

    Person(iain, "Iain (Operator)", "Configures instances, sets up role packs")
    Person(users, "Sarah / Marcus (Users)", "Senior professionals. Interact via Telegram; receive proactive briefs.")

    System(cos, "CoS Platform", "Growth roadmap end-state after the approved Epic 7+ sequence: retrieval trust, interactive messaging, provider portability, web augmentation, and proactive delivery.")

    System_Ext(claude_desktop, "Claude Desktop", "MCP client")
    System_Ext(claude_api, "Claude API (Anthropic)", "LLM synthesis")
    System_Ext(embedding_api, "Embedding Provider API", "Vector embeddings")
    System_Ext(gmail_api, "Gmail API (Google)", "Read email, ingest attachments. OAuth 2.0.")
    System_Ext(calendar_api, "Google Calendar API", "Read upcoming events for meeting prep and daily brief. OAuth 2.0.")
    System_Ext(telegram_api, "Telegram Bot API", "Bidirectional: inbound Q&A and note capture, outbound scheduled briefs.")
    System_Ext(web_search, "Web Search API (Brave / Tavily)", "Live internet search when local knowledge is insufficient.")

    Rel(iain, cos, "Operates instances", "CLI")
    Rel(users, telegram_api, "Sends questions and notes, receives briefs")
    Rel(claude_desktop, cos, "MCP tool calls", "stdio / MCP")
    Rel(cos, claude_api, "LLM synthesis", "HTTPS")
    Rel(cos, embedding_api, "Embedding generation", "HTTPS")
    Rel(cos, gmail_api, "Read email and ingest attachments", "HTTPS / OAuth 2.0")
    Rel(cos, calendar_api, "Read calendar events", "HTTPS / OAuth 2.0")
    Rel(cos, telegram_api, "Send and receive messages", "HTTPS / Bot API")
    Rel(cos, web_search, "Augment local retrieval with live results", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

---

## 2. Container Diagram (C4 Level 2)

### Phase 1 — Docker Compose services

```mermaid
C4Container
    title CoS Platform — Container Diagram (Phase 1)

    Person(iain, "Iain", "Operator / User")
    System_Ext(claude_desktop, "Claude Desktop", "MCP client (primary query interface)")
    System_Ext(claude_api, "Claude API", "LLM reasoning and synthesis")
    System_Ext(embedding_api, "Embedding Provider", "Vector embedding generation")

    System_Boundary(cos_platform, "CoS Platform — Docker Compose") {
        Container(cos, "cos", "Python 3.12 / uv / FastMCP 1.27.0", "Long-running MCP server (entrypoint: cos-mcp). Also used as one-off CLI runner (entrypoint: cos) via docker compose run. Handles ingestion, retrieval, reasoning, and output.")
        ContainerDb(postgres, "Postgres + pgvector", "pgvector/pgvector:pg16", "Stores documents, chunks, embeddings, and provenance records. Schema managed via idempotent SQL migrations applied at cos startup.")
        Container(tika, "Apache Tika", "apache/tika", "Format-agnostic text extraction. Accepts PDF, Word, and other formats via REST. Returns plain text and metadata.")
        ContainerDb(filesystem, "Local Filesystem", "Docker bind mount", "Immutable original source files. Markdown working copies. Persists across container restarts.")
    }

    Rel(iain, cos, "cos ingest / cos status / cos logs / cos restart", "Terminal → docker compose run")
    Rel(claude_desktop, cos, "retrieve, get_role_context, list_documents, get_status", "stdio / MCP protocol")
    Rel(cos, postgres, "Read/write documents, chunks, embeddings, provenance", "psycopg3 async pool")
    Rel(cos, tika, "POST file content for extraction", "HTTP REST (tika-client)")
    Rel(cos, filesystem, "Write originals and Markdown copies on ingest", "File I/O")
    Rel(cos, claude_api, "Send retrieved chunks and query for synthesis", "HTTPS / Anthropic SDK")
    Rel(cos, embedding_api, "Send text chunks for vectorisation", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### Growth Roadmap End-State — Container additions on top of the baseline

```mermaid
C4Container
    title CoS Platform — Container Diagram (Growth roadmap end-state)

    Person(users, "Sarah / Marcus", "Role pack users")
    System_Ext(telegram_api, "Telegram Bot API", "Bidirectional messaging")
    System_Ext(gmail_api, "Gmail API", "Email and attachment ingestion")
    System_Ext(calendar_api, "Google Calendar API", "Event reading")
    System_Ext(web_search, "Web Search API", "Live internet search")

    System_Boundary(cos_platform, "CoS Platform — Docker Compose (Growth roadmap)") {
        Container(cos, "cos (extended)", "Python 3.12 / uv", "Runs the Epic 6 migration/hardening flow on top of the implemented Phase 1 baseline, then adds the approved Epic 7+ layers in sequence: retrieval-trust instrumentation, Telegram messaging, structured LLM/provider portability, web_search, and later scheduler-driven briefings.")
        ContainerDb(postgres, "Postgres + pgvector", "pgvector/pgvector:pg16", "Carries the implemented baseline schema from Epics 1-5, then is migrated in Epic 6 to canonical identity tables for content blobs and source lineage; jobs table (002_jobs.sql) is added for background connector-triggered ingestion.")
        Container(tika, "Apache Tika", "apache/tika", "Unchanged from Phase 1.")
        ContainerDb(filesystem, "Local Filesystem", "Docker bind mount", "Adds tokens/ directory for OAuth credentials (gitignored).")
    }

    Rel(users, telegram_api, "Sends questions and notes")
    Rel(cos, telegram_api, "Polls for inbound messages; sends briefs and responses", "HTTPS / Bot API")
    Rel(cos, gmail_api, "Reads email; ingests attachments", "HTTPS / OAuth 2.0")
    Rel(cos, calendar_api, "Reads upcoming events for meeting prep", "HTTPS / OAuth 2.0")
    Rel(cos, web_search, "Calls when local retrieval is insufficient", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## 3. Component Diagram (C4 Level 3) — `cos` container internals

```mermaid
C4Component
    title cos Container — Component Diagram (Phase 1)

    System_Ext(claude_desktop, "Claude Desktop", "MCP client")
    System_Ext(postgres, "Postgres + pgvector", "Data store")
    System_Ext(tika, "Apache Tika", "Text extraction")
    System_Ext(claude_api, "Claude API", "LLM synthesis")
    System_Ext(embedding_api, "Embedding Provider", "Vectorisation")
    System_Ext(filesystem, "Filesystem", "Originals and Markdown copies")

    Container_Boundary(cos, "cos (Python 3.12 / uv)") {
        Component(config, "CosConfig", "cos/config.py — Pydantic v2", "Reads config.yaml once at startup. Single source of truth for all settings. Injected into all components that need it.")
        Component(mcp_server, "MCP Server", "cos/mcp_server/ — FastMCP 1.27.0", "FastMCP app (server.py). Tool definitions in tools.py: retrieve, get_role_context, list_documents, get_status. Calls services layer only. Entrypoint: cos-mcp.")
        Component(cli, "CLI", "cos/cli.py — Typer", "Commands: cos status, cos restart, cos logs, cos ingest. Calls services layer only. Entrypoint: cos.")
        Component(services, "Service Layer", "cos/services/", "IngestService, RetrievalService, RolePackService, OutputService, HealthService. The only permitted cross-module import path. Thin orchestration — no business logic.")
        Component(ingestion, "Ingestion Pipeline", "cos/ingestion/", "pipeline.py orchestrates extract→normalise→hash→dedupe decision→chunk→embed→store. extractor.py wraps tika-client. chunker.py: 1024 token chunks, 100 token overlap. embedder.py: configurable embedding adapter.")
        Component(retrieval, "Retrieval Engine", "cos/retrieval/", "search.py: hybrid tsvector keyword + pgvector cosine similarity. Role pack retrieval weights applied to ranking. citations.py: formats CitedResults with source_alias plus full provenance.")
        Component(store, "Data Store", "cos/store/", "db.py: psycopg3 async pool with pgvector type registration. models.py: DocumentRecord, DocumentVersionRecord, ContentBlobRecord, SourceRecord, SourceVersionRecord, ChunkRecord, EmbeddingRecord. migrations/: idempotent numbered SQL files applied at startup.")
        Component(rolepack, "Role Pack Loader", "cos/rolepack/", "loader.py reads YAML role pack → RolePackConfig (Pydantic). Contains: role goals, tone and style, knowledge taxonomy, retrieval priorities, output channels, stakeholder map.")
        Component(output_router, "OutputRouter", "cos/output/router.py", "Sole exit point for all user-facing output. Validates channel against configured channels. Fail-closed: suppresses and logs on invalid channel. Never raises an unhandled exception.")
        Component(llm, "LLM Adapter", "cos/llm/", "adapter.py: LLMAdapter protocol defining complete() contract. anthropic.py: Claude implementation. Swapping provider requires only a new implementation file and config change.")
    }

    Rel(claude_desktop, mcp_server, "MCP tool calls", "stdio / MCP")
    Rel(mcp_server, services, "All tool implementations delegate to services")
    Rel(cli, services, "All CLI commands delegate to services")
    Rel(services, ingestion, "IngestService delegates to pipeline")
    Rel(services, retrieval, "RetrievalService delegates to search and citations")
    Rel(services, rolepack, "RolePackService delegates to loader")
    Rel(services, output_router, "OutputService wraps OutputRouter")
    Rel(services, store, "All DB access via store layer")
    Rel(services, llm, "RetrievalService calls LLMAdapter for synthesis")
    Rel(ingestion, tika, "POST files for text extraction", "HTTP REST")
    Rel(ingestion, embedding_api, "Embed chunks", "HTTPS")
    Rel(ingestion, filesystem, "Write originals and Markdown copies", "File I/O")
    Rel(store, postgres, "All SQL queries and writes", "psycopg3 async")
    Rel(llm, claude_api, "Synthesis requests", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

---

## 4. Dynamic Flows

### 4.1 Ingestion — Canonical Ingest Decision (Identity-Hardened Flow)

```mermaid
sequenceDiagram
    actor Iain
    participant CLI as cos CLI<br/>(cli.py)
    participant IS as IngestService<br/>(services/ingestion.py)
    participant EX as extractor.py
    participant Tika as Apache Tika
    participant DEC as ingest decision engine
    participant CK as chunker.py
    participant EM as embedder.py
    participant EmbAPI as Embedding Provider
    participant DB as store/db.py<br/>(Postgres + pgvector)
    participant FS as Filesystem

    Iain->>CLI: cos ingest ./docs/strategy.pdf
    CLI->>IS: ingest_file("./docs/strategy.pdf")
    IS->>EX: extract("./docs/strategy.pdf")
    EX->>Tika: POST /tika/form (PDF bytes)
    Tika-->>EX: plain text + metadata
    EX-->>IS: ExtractedContent(text, metadata, sha256)
    IS->>DEC: resolve(source_locator, source_alias, sha256)
    DEC->>DB: lookup source lineage + content_blob hash
    DB-->>DEC: current canonical state

    alt New source + new content
        DEC-->>IS: create canonical blob, document, version, and source lineage
        IS->>FS: write original under internal blob key
        IS->>FS: write Markdown copy under internal blob key
        IS->>CK: chunk(text, size=1024, overlap=100)
        CK-->>IS: List[Chunk]
        IS->>EM: embed(chunks)
        EM->>EmbAPI: POST embeddings (batch)
        EmbAPI-->>EM: List[Vector]
        EM-->>IS: List[ChunkWithVector]
        IS->>DB: BEGIN TRANSACTION
        DB->>DB: INSERT content_blobs, documents, document_versions
        DB->>DB: INSERT sources, source_versions
        DB->>DB: INSERT chunks (document_version_id, content, chunk_index, content_tsv)
        DB->>DB: INSERT embeddings (vector, chunk_id, model, provider)
        DB->>DB: COMMIT
        DB-->>IS: ok
        IS-->>CLI: IngestionResult(new_version_created=true, chunk_count=24)
    else Known source + unchanged content
        DEC-->>IS: no-op outcome
        IS-->>CLI: IngestionResult(no_op=true, reason="unchanged content")
    else Known source + changed content
        DEC-->>IS: create new content blob + new document_version
        IS->>FS: write new original and Markdown copy under new blob key
        IS->>CK: chunk(text)
        CK-->>IS: List[Chunk]
        IS->>EM: embed(chunks)
        EM->>EmbAPI: POST embeddings
        EmbAPI-->>EM: List[Vector]
        IS->>DB: BEGIN TRANSACTION
        DB->>DB: INSERT new content_blob, document_version, source_version
        DB->>DB: INSERT chunks and embeddings for new version only
        DB->>DB: COMMIT
        IS-->>CLI: IngestionResult(new_version_created=true, chunk_count=24)
    else New source + known content
        DEC-->>IS: link new source lineage to existing canonical content
        IS->>DB: INSERT source + source_version only
        DB-->>IS: linked without duplicate chunking
        IS-->>CLI: IngestionResult(reused_existing_content=true, chunk_count=0)
    end

    CLI-->>Iain: Clear outcome message with canonical identity result
```

### 4.2 Query — MCP Retrieve Tool (Phase 1)

```mermaid
sequenceDiagram
    actor User
    participant CD as Claude Desktop
    participant MCP as MCP Server<br/>(mcp_server/tools.py)
    participant OS as OutputService<br/>(services/output.py)
    participant OR as OutputRouter<br/>(output/router.py)
    participant RS as RetrievalService<br/>(services/retrieval.py)
    participant SR as search.py
    participant CI as citations.py
    participant RPS as RolePackService
    participant LLM as LLMAdapter<br/>(llm/anthropic.py)
    participant ClaudeAPI as Claude API
    participant DB as Postgres + pgvector

    User->>CD: "What do the org charts say about spans of control in ops?"
    CD->>MCP: tool_call: retrieve(query="spans of control ops function")
    MCP->>OS: handle_retrieve(query, channel="local")
    OS->>OR: validate_channel("local")
    OR-->>OS: valid ✓
    OS->>RS: query("spans of control ops function", role_pack)
    RS->>RPS: get_active()
    RPS-->>RS: RolePackConfig (CHRO — retrieval weights, tone)
    RS->>SR: search(query, retrieval_priorities)
    SR->>DB: tsvector keyword search on chunks
    SR->>DB: pgvector cosine similarity on embeddings
    DB-->>SR: ranked results from both searches
    SR-->>RS: merged and re-ranked chunks (role pack weights applied)
    RS->>CI: format_citations(chunks)
    CI-->>RS: CitedResults (content, source_document_id, document_version_id, source_alias, source_locator, chunk_index, score)
    RS->>LLM: complete(retrieved_chunks, query, tone=RolePackConfig.tone)
    LLM->>ClaudeAPI: POST /messages (system prompt + context + query)
    ClaudeAPI-->>LLM: synthesised response
    LLM-->>RS: SynthesisResult
    RS-->>OS: CitedResponse(answer, citations)
    OS-->>MCP: {"status": "ok", "data": answer, "citations": [...]}
    MCP-->>CD: tool_result
    CD-->>User: Cited answer with source references
```

### 4.3 Platform Startup Sequence

```mermaid
sequenceDiagram
    participant DC as docker compose up
    participant PG as postgres container
    participant TK as tika container
    participant COS as cos container
    participant CFG as config.py
    participant MIG as store/migrations/
    participant RP as rolepack/loader.py
    participant SRV as mcp_server/server.py

    DC->>PG: start (pgvector/pgvector:pg16)
    DC->>TK: start (apache/tika)
    loop healthcheck loop
        DC->>PG: pg_isready
        DC->>TK: GET /tika
    end
    Note over PG,TK: Both containers healthy
    DC->>COS: start cos container (entrypoint: cos-mcp)
    COS->>CFG: load CosConfig from config.yaml
    CFG-->>COS: CosConfig (Pydantic validated)
    COS->>PG: create psycopg3 async pool
    COS->>PG: CREATE EXTENSION IF NOT EXISTS vector
    COS->>MIG: apply pending migrations in order
    MIG->>PG: 001_initial.sql (IF NOT EXISTS guards)
    PG-->>MIG: ok
    MIG-->>COS: all migrations applied
    COS->>RP: load_role_pack(CosConfig.role_pack_path)
    RP-->>COS: RolePackConfig (validated)
    COS->>SRV: start FastMCP, register tools
    SRV-->>DC: ready — MCP server listening on stdio
    Note over COS: Platform operational. Claude Desktop can now connect.
```

### 4.4 Scheduled Morning Brief (Epic 11)

```mermaid
sequenceDiagram
    participant SCH as APScheduler
    participant CAL as calendar.py connector
    participant CalAPI as Google Calendar API
    participant RS as RetrievalService
    participant DB as Postgres + pgvector
    participant LLM as LLMAdapter
    participant ClaudeAPI as Claude API
    participant OR as OutputRouter
    participant CH as output channel handler
    participant OUT as Configured output channel
    actor User

    SCH->>SCH: trigger at configured time (e.g. 07:30)
    SCH->>CAL: get_today_events()
    CAL->>CalAPI: GET /calendars/primary/events (OAuth 2.0, tokens/google_calendar.json)
    CalAPI-->>CAL: today's events
    CAL-->>SCH: List[CalendarEvent]
    loop for each calendar event
        SCH->>RS: query(event.title + attendees, role_pack)
        RS->>DB: hybrid search (relevant documents for this meeting)
        DB-->>RS: CitedResults
    end
    SCH->>LLM: complete(events + retrieved_docs, "generate morning brief", role_pack.tone)
    LLM->>ClaudeAPI: POST /messages
    ClaudeAPI-->>LLM: brief content
    LLM-->>SCH: MorningBrief
    SCH->>OR: send(channel=config.scheduler.brief_channel, content=brief)
    OR->>OR: validate configured channel in output_channels
    OR->>CH: dispatch(brief)
    CH->>OUT: deliver brief
    OUT-->>User: morning brief message
    SCH->>DB: log(job_id, result, provenance)
```

### 4.5 Inbound Telegram Message — Q&A or Note Capture (Epic 8)

```mermaid
sequenceDiagram
    actor User
    participant TelegramAPI as Telegram Bot API
    participant TB as connectors/telegram_bot.py
    participant IS as IngestService
    participant JOBS as jobs queue / worker
    participant RS as RetrievalService
    participant LLM as LLMAdapter
    participant OR as OutputRouter
    participant TG as output/channels/telegram.py
    participant DB as Postgres + pgvector

    User->>TelegramAPI: sends message
    TB->>TelegramAPI: GET /getUpdates (polling)
    TelegramAPI-->>TB: message update
    TB->>TB: classify: note or question?

    alt Note capture (prefixed "Note:" or short declarative statement)
        TB->>JOBS: enqueue ingest job (source_locator=telegram://..., source_alias=message timestamp)
        JOBS->>IS: ingest_note(text, metadata={source:"telegram", timestamp:...})
        IS->>DB: canonical ingest decision + writes
        IS-->>JOBS: IngestionResult
        JOBS-->>TB: completed
        TB->>OR: send(channel="telegram", content="Note saved")
        OR->>TG: send("Note saved")
        TG->>TelegramAPI: POST /sendMessage
        TelegramAPI-->>User: "Note saved"
    else Question
        TB->>RS: query(text, role_pack)
        RS->>DB: hybrid search
        RS->>LLM: complete(chunks, query, role_pack.tone)
        LLM-->>RS: CitedResponse
        RS-->>TB: CitedResponse
        TB->>OR: send(channel="telegram", content=cited_response)
        OR->>TG: send(cited_response)
        TG->>TelegramAPI: POST /sendMessage
        TelegramAPI-->>User: cited answer
    end
```

---

## 5. Data Model

```mermaid
erDiagram
    documents {
        uuid id PK
        text status
        uuid current_document_version_id FK
        timestamptz created_at
    }
    document_versions {
        uuid id PK
        uuid document_id FK
        uuid content_blob_id FK
        int version_number
        timestamptz ingested_at
        text extraction_method
    }
    content_blobs {
        uuid id PK
        text sha256_hash
        text original_storage_key
        text markdown_storage_key
        timestamptz created_at
    }
    sources {
        uuid id PK
        text source_type
        text source_locator
        text source_alias
        timestamptz first_seen_at
    }
    source_versions {
        uuid id PK
        uuid source_id FK
        uuid document_version_id FK
        uuid content_blob_id FK
        timestamptz observed_at
    }
    chunks {
        uuid id PK
        uuid document_version_id FK
        int chunk_index
        text content
        tsvector content_tsv
        int token_count
    }
    embeddings {
        uuid id PK
        uuid chunk_id FK
        vector embedding
        text model
        text provider
    }
    jobs {
        uuid id PK
        text job_type
        text status
        jsonb payload
        timestamptz created_at
        timestamptz completed_at
    }

    documents ||--o{ document_versions : "versioned by"
    content_blobs ||--o{ document_versions : "materialises as"
    sources ||--o{ source_versions : "observed as"
    document_versions ||--o{ source_versions : "linked from"
    document_versions ||--o{ chunks : "split into"
    chunks ||--|| embeddings : "embedded as"
```

`jobs` table is Phase 2. The canonical identity tables (`content_blobs`, `sources`, `source_versions`) are the identity-hardening foundation that must land before connector expansion.

Citation integrity: every `embeddings` row → `chunks` row → `document_versions` row → `content_blobs` and `source_versions` → `sources` → managed original/Markdown copies. User-facing citations use `source_alias`; raw locators remain available for traceability.

---

## 6. Phase Evolution — What Gets Added When

```mermaid
flowchart LR
    subgraph P1["Phase 1 — Builder Validation"]
        direction TB
        MCP1["MCP Server\n(FastMCP)"]
        CLI1["CLI\n(Typer)"]
        ING1["Ingestion Pipeline\n(Tika + pgvector)"]
        RET1["Retrieval Engine\n(hybrid search)"]
        DB1[("Postgres\n+ pgvector")]
        LLM1["LLM Adapter\n(Claude)"]
        RP1["Role Pack Loader\n(CHRO config)"]
        OR1["OutputRouter\n(local channel)"]
    end

    subgraph P2["Approved Growth Sequence — Epics 7-11"]
        direction TB
        E7["Epic 7\nRetrieval trust + eval + observability"]
        E8["Epic 8\nInteractive Telegram messaging"]
        E9["Epic 9\nStructured LLM boundary + provider portability"]
        E10["Epic 10\nWeb augmentation"]
        E11["Epic 11\nProactive briefings + meeting prep"]
        JOBS2[("jobs table\n(background work substrate)")]
        TG2["Telegram Channel\n(OutputRouter)"]
    end

    subgraph P3["Later Roadmap — Epics 12-14"]
        direction TB
        E12["Epic 12\nAgent-safe task runtime"]
        E13["Epic 13\nModel routing + local endpoints"]
        E14["Epic 14\nAdvanced retrieval + orchestration pilots"]
    end

    P1 --> P2 --> P3
    E7 --> E8 --> E9 --> E10 --> E11
    E11 --> E12
    E12 --> E13 --> E14
    JOBS2 --> E8
    JOBS2 --> E11
```

---

## 7. Epic 7 — Benchmark / Release-Gate Flow

Epic 7 is the retrieval-trust gate that must pass before Epic 8 (Telegram) or any later growth work begins. The diagram below shows the operator benchmark execution flow and how the release gate is evaluated.

```mermaid
flowchart TD
    OP[Operator runs benchmark\nuv run cos benchmark\n--config config.host.yaml\n--corpus tests/fixtures/retrieval_eval\n--output report.json]

    SEED[Harness seeds 6 fixture\ndocuments into Postgres\nvia static embeddings]

    GOLD[Run 8 gold queries\ndirect_fact · exact_phrase\ndate_timeline · single_doc_interpretation\ncross_doc_synthesis · briefing · no_answer]

    FUZZ{--include-fuzz?}
    FUZZ_RUN[Run 5 fuzz queries\nnoisy phrasing · cross-doc noise\nnear-synonym · empty-corpus]
    FUZZ_DIAG[Fuzz failures: diagnostic only\nnot release-gating]

    CLEANUP[Harness cleans up\nfixture documents]

    SCORE[Score each query:\nrecall · citation_precision\nanswerability_verdict\nfailure_stage if failed]

    REPORT[Write JSON report\nschema_version · run_timestamp\ncorpus_version · per_query · per_class\nretrieval_settings]

    CLEAN_DB{Clean benchmark\ndatabase?}
    GATE_PASS[All 8 gold pass +\nclean DB → Epic 8 gate satisfied]
    GATE_DIAG[Populated DB run →\ndiagnostic only\nlabel artifact accordingly]

    OP --> SEED --> GOLD
    GOLD --> FUZZ
    FUZZ -- yes --> FUZZ_RUN --> FUZZ_DIAG --> CLEANUP
    FUZZ -- no --> CLEANUP
    CLEANUP --> SCORE --> REPORT --> CLEAN_DB
    CLEAN_DB -- yes --> GATE_PASS
    CLEAN_DB -- no --> GATE_DIAG
```

### Retrieval-Trust Sequencing

Epic 7 hardening is the prerequisite for all amplification layers:

```mermaid
flowchart LR
    E7["Epic 7\nRetrieval trust\neval + observability"]
    E8["Epic 8\nInteractive Telegram\nmessaging"]
    E9["Epic 9\nStructured LLM boundary\n+ provider portability"]
    E10["Epic 10\nWeb augmentation\n+ external context"]
    E11["Epic 11\nProactive briefings\n+ meeting prep"]
    E14["Epic 14\nAdvanced retrieval modes\n(benchmark-gated)"]

    E7 -->|"benchmark gate\nmust pass"| E8
    E8 --> E9 --> E10 --> E11
    E7 -.->|"benchmark-gated\nafter E9–E11"| E14
```

Epic 7 must land before Telegram messaging, web augmentation, and proactive scheduling. Advanced retrieval modes (Epic 14) are explicitly benchmark-gated and come after the full growth sequence.

---

## 8. OutputRouter — Egress Control Logic

The OutputRouter is the single enforcement point for NFR7 (fail-closed egress). This diagram shows its decision logic.

```mermaid
flowchart TD
    REQ[Output request:\nchannel + content]
    VAL{Channel in\nconfig.output_channels?}
    SUPP[Suppress output\nLog structured error:\n component=output]
    ROUTE{Select channel\nhandler}
    LOCAL[output/channels/local.py\nReturn in MCP response]
    TG[output/channels/telegram.py\nPOST to Telegram Bot API]
    EMAIL[output/channels/email.py\nSend via email handler]
    DONE[Output delivered]

    REQ --> VAL
    VAL -- No --> SUPP
    VAL -- Yes --> ROUTE
    ROUTE -- local --> LOCAL --> DONE
    ROUTE -- telegram --> TG --> DONE
    ROUTE -- email --> EMAIL --> DONE
    SUPP --> END[Return error envelope\nNo output sent]
```
