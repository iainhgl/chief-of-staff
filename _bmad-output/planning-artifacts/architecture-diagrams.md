---
type: 'architecture-diagrams'
architectureRef: 'architecture.md'
date: '2026-04-17'
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

### Phase 2 — First Real Users (Growth tier additions)

```mermaid
C4Context
    title CoS Platform — System Context (Phase 2, Growth additions)

    Person(iain, "Iain (Operator)", "Configures instances, sets up role packs")
    Person(users, "Sarah / Marcus (Users)", "Senior professionals. Interact via Telegram; receive proactive briefs.")

    System(cos, "CoS Platform", "Now includes connectors, scheduler, and bidirectional messaging.")

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

### Phase 2 — Container additions

```mermaid
C4Container
    title CoS Platform — Container Diagram (Phase 2 additions to cos)

    Person(users, "Sarah / Marcus", "Role pack users")
    System_Ext(telegram_api, "Telegram Bot API", "Bidirectional messaging")
    System_Ext(gmail_api, "Gmail API", "Email and attachment ingestion")
    System_Ext(calendar_api, "Google Calendar API", "Event reading")
    System_Ext(web_search, "Web Search API", "Live internet search")

    System_Boundary(cos_platform, "CoS Platform — Docker Compose (Phase 2)") {
        Container(cos, "cos (extended)", "Python 3.12 / uv", "Now also runs APScheduler for scheduled briefs. Adds Gmail, Calendar, and Telegram connector modules. Adds web_search MCP tool exposed to Claude Desktop.")
        ContainerDb(postgres, "Postgres + pgvector", "pgvector/pgvector:pg16", "Adds jobs table (002_jobs.sql) for background connector-triggered ingestion queue.")
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
        Component(ingestion, "Ingestion Pipeline", "cos/ingestion/", "pipeline.py orchestrates extract→normalise→chunk→embed→store. extractor.py wraps tika-client. chunker.py: 1024 token chunks, 100 token overlap. embedder.py: configurable embedding adapter.")
        Component(retrieval, "Retrieval Engine", "cos/retrieval/", "search.py: hybrid tsvector keyword + pgvector cosine similarity. Role pack retrieval weights applied to ranking. citations.py: formats CitedResults with full provenance.")
        Component(store, "Data Store", "cos/store/", "db.py: psycopg3 async pool with pgvector type registration. models.py: DocumentRecord, ChunkRecord, EmbeddingRecord, ProvenanceRecord dataclasses. migrations/: idempotent numbered SQL files applied at startup.")
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

### 4.1 Ingestion — New Document (Phase 1)

```mermaid
sequenceDiagram
    actor Iain
    participant CLI as cos CLI<br/>(cli.py)
    participant IS as IngestService<br/>(services/ingestion.py)
    participant EX as extractor.py
    participant Tika as Apache Tika
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
    EX->>FS: write original (immutable copy)
    EX->>FS: write Markdown working copy
    EX-->>IS: ExtractedContent(text, metadata)
    IS->>CK: chunk(text, size=1024, overlap=100)
    CK-->>IS: List[Chunk]
    IS->>EM: embed(chunks)
    EM->>EmbAPI: POST embeddings (batch)
    EmbAPI-->>EM: List[Vector]
    EM-->>IS: List[ChunkWithVector]
    IS->>DB: BEGIN TRANSACTION
    DB->>DB: INSERT documents (source_path, file_hash, ingested_at, status)
    DB->>DB: INSERT document_versions (provenance record)
    DB->>DB: INSERT chunks (content, chunk_index, document_id, content_tsv)
    DB->>DB: INSERT embeddings (vector, chunk_id, model, provider)
    DB->>DB: COMMIT
    DB-->>IS: ok
    IS-->>CLI: IngestionResult(doc_id, chunk_count=24)
    CLI-->>Iain: Ingested strategy.pdf → 24 chunks indexed
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
    CI-->>RS: CitedResults (content, source_document_id, source_path, chunk_index, score)
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

### 4.4 Scheduled Morning Brief (Phase 2)

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
    participant TG as output/channels/telegram.py
    participant TelegramAPI as Telegram Bot API
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
    SCH->>OR: send(channel="telegram", content=brief)
    OR->>OR: validate "telegram" in config.output_channels
    OR->>TG: send(brief)
    TG->>TelegramAPI: POST /sendMessage (bot_token from config)
    TelegramAPI-->>User: morning brief message in Telegram
    SCH->>DB: log(job_id, result, provenance)
```

### 4.5 Inbound Telegram Message — Q&A or Note Capture (Phase 2)

```mermaid
sequenceDiagram
    actor User
    participant TelegramAPI as Telegram Bot API
    participant TB as connectors/telegram_bot.py
    participant IS as IngestService
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
        TB->>IS: ingest_note(text, metadata={source:"telegram", timestamp:...})
        IS->>DB: INSERT document (content, auto-tagged, timestamped)
        IS->>DB: INSERT chunks and embeddings
        IS-->>TB: IngestionResult
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
        text source_path
        text file_hash
        text status
        timestamptz ingested_at
        int current_version
    }
    document_versions {
        uuid id PK
        uuid document_id FK
        int version_number
        text source_path
        text file_hash
        timestamptz ingested_at
        text extraction_method
    }
    chunks {
        uuid id PK
        uuid document_id FK
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
    documents ||--o{ chunks : "split into"
    chunks ||--|| embeddings : "embedded as"
```

`jobs` table is Phase 2. All other tables are Phase 1 MVP.

Citation integrity: every `embeddings` row → `chunks` row → `documents` row → original file on filesystem. No answer can be returned without this chain being intact.

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

    subgraph P2["Phase 2 — First Real Users"]
        direction TB
        SCH2["APScheduler\n(daily brief)"]
        BOT2["Telegram Bot\n(bidirectional)"]
        GMAIL2["Gmail Connector\n(ingest email)"]
        CAL2["Calendar Connector\n(meeting prep)"]
        WEB2["Web Search Tool\n(MCP tool)"]
        JOBS2[("jobs table\n(Phase 2 schema)")]
        TG2["Telegram Channel\n(OutputRouter)"]
    end

    subgraph P3["Phase 3 — Governance & Write-back"]
        direction TB
        GOV3["Governance Layer\n(audit, confidence)"]
        WB3["Write-back Actions\n(approval step)"]
        MULTI3["Multi-provider\nLLM support"]
    end

    P1 --> P2 --> P3
```

---

## 7. OutputRouter — Egress Control Logic

The OutputRouter is the single enforcement point for NFR7 (fail-closed egress). This diagram shows its decision logic.

```mermaid
flowchart TD
    REQ[Output request:\nchannel + content]
    VAL{Channel in\nconfig.output_channels?}
    SUPP[Suppress output\nLog structured error:\n component=output_router]
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