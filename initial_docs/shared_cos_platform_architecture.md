# Shared Chief of Staff Platform

## 1. Goal

### 1.1 Deployment Model (Important)
- **Default assumption: one role per instance.** Each CoS instance is built and operated for a single role (e.g., one CHRO or one Enterprise Architect) with its own data store and connectors.
- This keeps **security, retrieval, and reasoning simple and reliable** during early phases.
- The platform is **designed to support multi-role / multi-tenant in the future**, but this should only be introduced after Phase 2–3 once the role pack abstraction is stable.
- If/when multi-role is introduced, enforce **strict namespaces/tenants** so data, permissions, and retrieval are isolated per role.

Build a reusable Chief of Staff (CoS) platform that can support different roles and domains by combining:
Build a reusable Chief of Staff (CoS) platform that can support different roles and domains by combining:
- a common technical core
- a role-specific configuration pack
- one or more knowledge domains
- workflows that turn knowledge into action

The platform should support multiple concrete implementations such as:
- CHRO CoS
- enterprise architect CoS
- founder / operator CoS
- finance / strategy CoS

## 2. Design Principles
1. **Separate core platform from role-specific behavior**
2. **Keep the source material human-readable and editable**
3. **Preserve provenance and version history**
4. **Use retrieval before generation**
5. **Make model choice interchangeable**
6. **Start simple, then add capability only when needed**

## 3. Core Platform Blocks

### 3.1 Source Connectors
Inputs from:
- email
- calendar
- docs / files
- chat / messaging
- web / public sources
- business systems

Responsibilities:
- read content
- capture metadata
- preserve source links
- support incremental sync

### 3.2 Ingestion Pipeline
Steps:
1. extract text and metadata
2. normalize into a canonical text format
3. chunk into retrieval units
4. tag with source, date, domain, confidence
5. store originals and working copies
6. create embeddings for retrieval

### 3.3 Canonical Store
Stores:
- original source files
- editable human-readable working copies
- document metadata
- chunk records
- embeddings
- provenance
- permissions
- workflow state

### 3.4 Retrieval Layer
Provides:
- keyword search
- semantic search
- recency ranking
- source ranking
- domain filters
- citation-ready retrieval results

### 3.5 Reasoning Layer
Responsible for:
- synthesis
- comparison
- drafting
- critique
- long-context analysis
- optional multi-model arbitration

### 3.6 Workflow Engine
Reusable actions such as:
- summarize
- brief
- draft
- compare
- critique
- prioritize
- prepare meeting
- detect contradictions
- extract decisions

### 3.7 Governance Layer
Handles:
- source provenance
- confidence levels
- read/write permissions
- approval workflows
- version control
- audit trail

### 3.8 Model Interface
Expose the platform through a stable interface such as:
- MCP
- REST API
- internal service API

This makes it usable by multiple LLMs and client tools.

## 4. Role Pack Model
A role pack is a configuration bundle that tells the platform how to behave for a specific person or function.

### 4.1 Role Pack Components
- role name
- role goals
- success criteria
- knowledge taxonomy
- tone and style rules
- stakeholder map
- key workflows
- preferred output formats
- decision heuristics
- vocabulary and taboo phrases
- retrieval priorities

### 4.2 Example Role Packs

#### CHRO Pack
Knowledge areas:
- workforce strategy
- org design
- talent and retention
- reward and culture
- HR transformation
- board / executive communication

Common workflows:
- CEO prep
- board prep
- workforce diagnostics
- HR prioritization
- communication drafting

#### Enterprise Architect Pack
Knowledge areas:
- target architecture
- systems landscape
- integration patterns
- constraints
- non-functional requirements
- client domain knowledge

Common workflows:
- project onboarding
- architecture review
- decision memo drafting
- trade-off analysis
- gap assessment

## 5. Recommended Data Model

### 5.1 Documents
A document is a source item such as:
- note
- transcript
- doc
- page
- email
- web article

Fields:
- id
- title
- source type
- origin URI
- owner
- created at
- modified at
- role domain
- confidence
- status

### 5.2 Chunks
A chunk is a retrieval unit extracted from a document.

Fields:
- chunk id
- document id
- chunk text
- chunk order
- semantic tags
- embedding vector
- citation pointer

### 5.3 Entities
Optional structured objects for:
- people
- projects
- teams
- systems
- decisions
- risks
- stakeholders

### 5.4 Role Profile
Fields:
- role id
- role name
- goals
- tone profile
- workflows enabled
- domain weights
- stakeholder priorities
- preferred model settings

### 5.5 Memory Items
Structured memory records for:
- facts
- opinions
- decisions
- preferences
- operating assumptions
- action items

## 6. How the System Works

### 6.1 Read Path
1. user asks a question or triggers a workflow
2. platform identifies role pack and task type
3. retrieval layer pulls relevant internal context
4. optional external search adds public context
5. reasoning layer synthesizes the answer
6. output is formatted in the role’s style
7. citations and source links are attached

### 6.2 Write Path
1. user edits a source document or adds a new item
2. ingestion pipeline extracts and normalizes
3. canonical store updates the working copy
4. chunks and embeddings are refreshed
5. provenance and version history are preserved
6. the system becomes immediately searchable again

## 7. Phased Delivery Plan

### Phase 1: Shared Core MVP
Build:
- one ingestion pipeline
- one canonical store
- one retrieval API
- one simple interface
- one role pack

Outcome:
- a usable CoS brain for one concrete role

### Phase 2: Role Pack Abstraction
Refactor so the role-specific behavior is data-driven.
Add:
- role profiles
- workflow templates
- style presets
- retrieval weights

Outcome:
- platform can support a second role without changing core code

### Phase 3: External Connectivity
Add:
- email
- calendar
- docs
- web sources
- sync jobs

Outcome:
- the CoS becomes operational, not just informational

### Phase 4: Workflow and Governance Hardening
Add:
- approvals
- permissions
- audit trails
- confidence scoring
- write-back actions

Outcome:
- safe enough for real work

### Phase 5: Advanced Reasoning
Add only if needed:
- multi-model arbitration
- recursive long-context reasoning
- proactive briefings
- richer agent behavior

Outcome:
- deeper analysis without compromising maintainability

## 8. Recommended Architecture Choices
- **Postgres** for metadata and workflow state
- **pgvector** for embeddings
- **object storage** for originals and exports
- **Markdown** as the editable working format
- **MCP or API layer** for model portability
- **Tika or similar extraction layer** for heterogeneous file ingestion
- **lightweight orchestration** before adding complex agent systems

## 9. What to Avoid Early
- too many agent personas
- custom model logic inside the database layer
- over-summarizing source material
- building a custom UI before the core works
- adding advanced reasoning before the role pack is stable
- mixing source truth with generated output

## 10. Decision Rule
If a feature does not help the platform:
- capture knowledge
- retrieve knowledge
- reason over knowledge
- act on knowledge
- preserve provenance

then defer it.

## 11. Summary
The platform should be a reusable CoS engine with a stable core and swappable role packs. The core should remain generic; the role pack should define who the CoS is for and what “good” looks like. This is the best path to a system that is portable, supportable, and capable of growing over time without becoming brittle.

