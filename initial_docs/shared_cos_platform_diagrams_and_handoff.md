# Shared CoS Platform — Architecture Diagrams and Handoff Pack

This companion document contains:
- logical static architecture by phase
- dynamic flows for ingestion, read, and scheduled checks
- a compact handoff prompt that can be pasted into another chat to create an implementation plan with stories/tasks

---

## 1. Static Architecture by Phase

### Phase 1 — Shared Core MVP
```mermaid
flowchart LR
  U[User / Role Owner] --> UI[Chat / Workflow Interface]
  UI --> ORCH[CoS Orchestrator]
  ORCH --> RP[Role Pack v1]
  ORCH --> RET[Retrieval API]
  RET --> PG[(Postgres metadata)]
  RET --> VEC[(pgvector embeddings)]
  ORCH --> RLM[Reasoning / LLM]
  ORCH --> OUT[Grounded response with citations]

  ING[Ingestion Job] --> EX[Extract + Normalize]
  EX --> MD[Markdown working copy]
  EX --> OBJ[(Object storage: originals)]
  EX --> PG
  EX --> VEC
```

### Phase 2 — Role Pack Abstraction
```mermaid
flowchart LR
  UI[Existing Chat UI / Claude / ChatGPT] --> ORCH[CoS Orchestrator]
  ORCH --> RP[Role Pack Registry]
  RP --> CHRO[CHRO Pack]
  RP --> EA[Enterprise Architect Pack]
  ORCH --> RET[Retrieval API]
  RET --> CORE[(Canonical Store)]
  CORE --> PG[(Postgres)]
  CORE --> VEC[(pgvector)]
  CORE --> OBJ[(Object Storage)]
  ORCH --> WF[Reusable Workflow Templates]
  ORCH --> LLM[Model Adapter / MCP]
```

### Phase 3 — External Connectivity
```mermaid
flowchart LR
  UI --> ORCH[CoS Orchestrator]
  ORCH --> RP[Role Pack]
  ORCH --> RET[Retrieval API]
  ORCH --> EXT[External Connectors]
  EXT --> EML[Email]
  EXT --> CAL[Calendar]
  EXT --> DOCS[Docs / Files]
  EXT --> WEB[Web / Public Sources]
  EXT --> SYS[Business Systems]
  EXT --> ING[Ingestion Pipeline]
  ING --> CORE[(Canonical Store)]
  CORE --> RET
  RET --> ORCH
```

### Phase 4 — Workflow and Governance Hardening
```mermaid
flowchart LR
  ORCH[CoS Orchestrator] --> GOV[Governance Layer]
  GOV --> AUTH[Permissions + Approvals]
  GOV --> AUD[Audit Trail]
  GOV --> CONF[Confidence / Source Trust]
  ORCH --> WF[Workflow Engine]
  WF --> ACT[Read / Draft / Suggest / Write-back]
  ACT --> EXT[Email / Calendar / Docs / Systems]
  ACT --> CORE[(Canonical Store)]
```

### Phase 5 — Advanced Reasoning
```mermaid
flowchart LR
  ORCH[CoS Orchestrator] --> RET[Retrieval]
  ORCH --> R1[Model A]
  ORCH --> R2[Model B]
  ORCH --> R3[Model C]
  RET --> R1
  RET --> R2
  RET --> R3
  R1 --> ARB[Arbitration / Synthesis]
  R2 --> ARB
  R3 --> ARB
  ARB --> OUT[Final answer / action]
```

---

## 2. Dynamic Flows

### 2.1 Ingestion Flow — New Source
```mermaid
flowchart TD
  SRC[New source item: file / email / note / web page] --> CAP[Capture source metadata]
  CAP --> EX[Extract text + structure]
  EX --> NORM[Normalize to Markdown]
  NORM --> KEEP[Store original in object storage]
  NORM --> DOC[Create / update document record]
  DOC --> CHUNK[Chunk for retrieval]
  CHUNK --> EMB[Create embeddings]
  EMB --> IDX[Store chunk + vector index]
  IDX --> AVAIL[Searchable in knowledge base]
```

### 2.2 Ingestion Flow — Update / Re-ingest
```mermaid
flowchart TD
  EDIT[User edits source / new version arrives] --> VER[Create new version record]
  VER --> DIFF[Optional diff against prior version]
  DIFF --> EX[Re-extract + normalize]
  EX --> NORM[Update Markdown working copy]
  NORM --> CHUNK[Refresh chunks]
  CHUNK --> EMB[Refresh embeddings]
  EMB --> IDX[Replace / version index entries]
  IDX --> HIST[Preserve provenance and history]
  HIST --> AVAIL[Updated content becomes searchable]
```

### 2.3 Read Flow — Chat Query to Grounded Answer
```mermaid
flowchart TD
  Q[User asks a question] --> RP[Load role pack]
  RP --> INT[Interpret task: brief / answer / draft / compare]
  INT --> RET[Retrieve relevant internal context]
  RET --> EXT[Optional external lookup]
  EXT --> SYN[Synthesize with model]
  SYN --> CIT[Attach citations / source links]
  CIT --> OUT[Answer in role-appropriate tone]
```

### 2.4 Scheduled Task — Daily Calendar Check
```mermaid
flowchart TD
  SCH[Scheduler triggers daily] --> CAL[Read calendar]
  CAL --> CMP[Compare against role priorities]
  CMP --> RET[Retrieve related meetings / docs / threads]
  RET --> BRF[Generate briefing / risks / prep]
  BRF --> SEND[Send digest / draft / reminder]
  SEND --> LOG[Log result + provenance]
```

---

## 3. What Gets Stored

```mermaid
flowchart LR
  SRC[Source material] --> ORIG[Original file / message / page]
  SRC --> MD[Editable Markdown working copy]
  SRC --> META[Metadata + provenance]
  MD --> CH[Chunks]
  CH --> VEC[Embeddings]
  META --> DB[(Postgres)]
  CH --> DB
  VEC --> DB
  ORIG --> OBJ[(Object storage)]
  DB --> UI[Readable views / search results / citations]
```

Stored artefacts:
- original source files
- editable Markdown copies
- metadata records
- chunk records
- embeddings
- provenance / version history
- permissions and confidence tags
- workflow logs

---

## 4. Suggested Handoff Prompt for a New Chat

Paste the following into a fresh chat when you want implementation stories and tasks:

> You are helping implement a reusable Chief of Staff platform. Use the attached architecture spec and diagrams as the source of truth. Produce an implementation plan broken into epics, stories, and tasks. Start with Phase 1 only. Keep the design role-agnostic in the core platform and role-specific only in the role pack. Focus on supportability, provenance, editable Markdown source copies, Postgres + pgvector, and a simple retrieval-first workflow. Include acceptance criteria for each story and call out dependencies and risks. Do not introduce MemPalace, recursive LLMs, or multi-model arbitration unless explicitly asked.

---

## 5. Phase 1 Story Skeleton

For convenience, here is a starter breakdown for Phase 1:

- **Epic 1: Source ingestion**
  - upload or connect source documents
  - extract and normalize text
  - preserve originals and version history

- **Epic 2: Canonical storage**
  - document records
  - chunk records
  - metadata / provenance
  - pgvector embeddings

- **Epic 3: Retrieval API**
  - keyword search
  - semantic search
  - source filtering
  - citations

- **Epic 4: Role pack v1**
  - role profile
  - tone rules
  - workflow list
  - retrieval priorities

- **Epic 5: Read-only chat workflow**
  - grounded answer path
  - citations / links
  - safe fallback behavior

- **Epic 6: Daily calendar check**
  - scheduled job
  - relevant meeting retrieval
  - brief generation

---

## 6. Notes on Keeping It Simple

- Use one core platform.
- Keep role behavior in configuration, not code.
- Keep original content human-readable and editable.
- Make every generated answer trace back to source material.
- Add advanced reasoning later only if the Phase 1–4 system is already useful.

