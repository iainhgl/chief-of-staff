---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-02b-vision', 'step-02c-executive-summary', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional', 'step-11-polish', 'step-12-complete', 'step-e-01-discovery', 'step-e-02-review', 'step-e-03-edit']
inputDocuments:
  - 'initial_docs/shared_cos_platform_architecture.md'
  - 'initial_docs/shared_cos_platform_diagrams_and_handoff.md'
  - 'initial_docs/CoS - CHRO.md'
documentCounts:
  briefs: 0
  research: 0
  brainstorming: 0
  projectDocs: 3
workflowType: 'prd'
workflow: 'edit'
date: '2026-04-16'
classification:
  projectType: 'api_backend_platform'
  domain: 'enterprise_ai_knowledge_management'
  complexity: 'high'
  projectContext: 'greenfield'
  deploymentTarget: 'local-first (macOS + Windows), containerised, cloud-portable'
  modelStrategy: 'provider-agnostic adapter; Claude first; multi-provider incl. adversarial'
  multiTenancy: 'single role per instance'
  connectivityEssential:
    - 'calendar read'
    - 'email read/ingest'
    - 'open internet search'
  connectivityChannels:
    - 'bidirectional messaging (e.g. WhatsApp): inbound Q&A + note capture, outbound briefings/digests'
    - 'email with attachments as ingestion channel'
lastEdited: '2026-05-05'
editHistory:
  - date: '2026-05-05'
    changes: 'Clarified canonical document identity, made cross-source exact-byte deduplication mandatory, aligned phased scope sequencing, and rewrote knowledge-ingestion requirements with sequential FR renumbering.'
---

# Product Requirements Document - Chief of Staff AI Platform

**Author:** Iain.livingstone
**Date:** 2026-04-16

## Executive Summary

The Chief of Staff AI Platform is a portable, ambient intelligence layer for senior professionals. It gives an executive a single, always-available thinking partner that combines their accumulated personal expertise — captured in documents, decks, notes, and frameworks — with the live context of their current role: organisation data, calendar, email, and stakeholder intelligence. The platform surfaces the right knowledge at the right moment, through whatever channel the person uses, grounded in real source material with full citations.

The primary user is a senior professional — initially a CHRO, but the platform is role-agnostic by design — who carries significant intellectual capital between roles and needs it to be searchable, connectable to new context, and available proactively (morning briefs, meeting prep) and reactively (on-demand questions via chat or messaging). The platform is built for personal and small-group use by known individuals, not anonymous end users.

The core problem is twofold: **quality of thinking** (surfacing the right expertise and context to inform better decisions) and **speed of recall** (eliminating the friction of hunting for what you know you know). The platform solves both by treating the knowledge base as the durable asset and the reasoning layer as a thin, swappable service on top.

### What Makes This Special

The platform is deliberately not an agent system. It makes one architectural bet: **keep the knowledge stable, make everything else replaceable**. The LLM provider, the channels, the environment can all change without touching the knowledge store. This makes the system simple, maintainable, and long-lived — which matters for personal infrastructure that needs to work reliably over years, not quarters.

Role behaviour — tone, priorities, workflows, stakeholder maps — lives entirely in configuration (the role pack), not code. This means a new role can be configured without a code change. The core platform is generic; the role pack is what makes it personal.

The platform meets users where they are: a morning message via their configured channel, an email with an attachment to ingest, a question before a board meeting. It does not require the user to go to a dedicated interface.

Every answer traces back to source material with citations. The platform never confabulates from memory; it retrieves and then reasons.

## Project Classification

| Property | Value |
|---|---|
| **Project Type** | API backend / platform — ingestion pipeline, canonical store, retrieval API, model adapter, role pack configuration |
| **Domain** | Enterprise AI / knowledge management and executive decision support |
| **Complexity** | High — vector search, multi-source ingestion, external search, calendar/email integration, bidirectional messaging channels, provider-agnostic model layer, role pack abstraction, provenance tracking |
| **Project Context** | Greenfield — no existing code; substantial design thinking captured in seed documents |
| **Deployment** | Local-first (macOS + Windows), containerised data layer (Postgres + pgvector in Docker), cloud-portable without rewrite |
| **Model strategy** | Provider-agnostic adapter; Claude as first implementation; multi-provider supported including adversarial/multi-model patterns |
| **Instance model** | Single role per instance; role identity defined by ingested documents and role pack configuration |

## Success Criteria

### User Success

- A user can ingest documents, notes, and quick thoughts with minimal friction — the captured content is searchable and surfaced when relevant, including weeks or months later
- Retrieval is fast and accurate: the system finds what the user knows is there; answers cite the source material they came from
- The platform delivers value both reactively (ad-hoc questions via chat or messaging) and proactively (morning briefs, meeting prep delivered without prompting)
- Two users with different role packs find the platform genuinely and regularly useful in their respective roles — this is the primary success signal

### Business Success

_(This is personal infrastructure, not a commercial product. "Business success" is platform health and sustained usefulness.)_

- At least two instances are running reliably with two different role configurations, used regularly by known individuals
- Maintenance burden is low — no routine manual intervention required to keep the system running
- The platform is portable: an instance can be moved to a different machine or a cloud VM without a rewrite

### Technical Success

- The system starts cleanly and stays up; containers and Postgres behave reliably under normal use
- Non-technical users have clear, simple instructions for restarting or diagnosing common failures — the system fails gracefully and explains itself
- Retrieval latency is acceptable for conversational use (target: under 5 seconds for a standard query)
- The ingestion pipeline handles common formats: PDF, Word, Markdown, plain text, email with attachments
- The model adapter is genuinely swappable — changing LLM provider does not require changes to the ingestion, storage, or retrieval layers

### Measurable Outcomes

| Outcome | Measure |
|---|---|
| Two role packs operational | Two distinct users using different configs regularly |
| Retrieval accuracy | User can find content they know is in the system |
| Infrastructure reliability | No unrecoverable failures under normal use |
| Ingestion coverage | Common doc types ingest without manual intervention |
| Low maintenance | No routine manual intervention needed week-to-week |

## Product Scope

### MVP — Builder Validation (Phase 1)

What Iain needs to validate the core pipeline is working:
- Ingestion pipeline: upload docs → extract → normalise to Markdown → chunk → embed → store
- Canonical store: Postgres + pgvector running in Docker, schema for documents, chunks, embeddings, provenance
- Retrieval API: keyword + semantic search, citation-ready results
- Role pack v1: CHRO configuration (static — loaded from config, not live-connected yet)
- Read-only chat interface: question → retrieve → reason → grounded answer with citations
- Containerised setup with clean start/stop and basic diagnostic instructions

_At this stage, all content is manually ingested (no live connectors). This is enough to validate that the knowledge pipeline and retrieval logic work correctly._

### Growth — Sequenced Expansion After Epic 6 (Phases 2–4)

What makes the platform genuinely operational for two users with different roles, in the approved order after Epic 6:
- Retrieval trust foundation first: evaluation corpus, benchmark queries, observability, and retrieval/citation hardening before broader ambient expansion
- Interactive Telegram slice next: bidirectional messaging for inbound questions and note capture, with Telegram as the first real mobile access path
- Structured LLM boundary and provider portability after that: richer internal request/response contracts plus direct provider expansion without changing retrieval or ingestion code
- Open internet search only after the retrieval baseline and reactive messaging path are trustworthy: augment local retrieval with live external context when needed
- Proactive scheduling after the reactive and trust foundations are proven: daily brief generation and meeting prep from calendar events
- Role pack abstraction remains part of growth validation: second role configured without core-code changes
- Improved ingestion remains in scope as a later growth convenience, not ahead of retrieval trust

### Vision — Future Platformization (Phases 5+)

To add only when the sequenced Growth layers are stable and proven useful:
- Durable task runtime for long-running, resumable, approval-aware workflows
- Internal model-routing policy and local/self-hosted model endpoint support
- Advanced retrieval modes: full-context retrieval, hierarchical summaries, graph-retrieval pilots
- Governance hardening: permissions, audit trail, confidence scoring, approval workflows
- Write-back actions: draft and send (email, calendar, messaging) with approval step
- Multi-agent or heavier orchestration patterns only if the narrower task substrate proves insufficient

## User Journeys

### Journey 1: The Executive — Daily Use (Happy Path)

**Sarah** is a CHRO at a PE-backed business. She joined three months ago and has been building her AI CoS instance ever since — her ten years of HR frameworks, transformation playbooks, and leadership thinking now live alongside the new company's org charts, financials, and stakeholder maps.

It's 7:45am. Before she opens her laptop, a WhatsApp message arrives from her platform: a short morning brief. Today's board meeting includes a workforce productivity discussion; the brief surfaces three relevant docs from her knowledge base — her own benchmarking framework from a prior role, the current company's attrition data she ingested last week, and a PE value creation playbook she'd forgotten she had. It takes her two minutes to scan. She feels prepared rather than scrambling.

In the meeting, someone challenges her on span-of-control ratios. On her phone, she sends a quick message to the platform: *"What does the org chart say about spans of control in the ops function?"* Within four seconds she has a cited answer pulled from the org chart she ingested, with the exact section reference. She quotes it with confidence.

After the meeting, she voice-notes a quick thought about a tension she observed between two exco members. It goes straight into her knowledge base, tagged and searchable.

**Capabilities revealed:** scheduled brief generation, WhatsApp bidirectional channel, reactive Q&A with citations, note capture via messaging, calendar integration for meeting context.

---

### Journey 2: The Executive — Onboarding a New Role

**Marcus** is an Enterprise Architect who has just joined a large financial services firm. He has eight years of architecture decision records, trade-off analyses, target state diagrams, and client domain knowledge spread across his laptop, Dropbox, and Notion.

Iain sets up a new instance for him. They spend an afternoon running the ingestion pipeline against his Dropbox folder — 340 documents normalised, chunked, and indexed. Marcus's role pack is configured with his knowledge taxonomy (integration patterns, NFRs, constraints, client domains), his preferred output tone (precise, structured, no fluff), and his key stakeholder map.

The next morning Marcus asks: *"What have I said in the past about API gateway patterns for financial services?"* The platform surfaces three decision records from different client engagements with exact citations. Marcus didn't remember writing two of them.

Three weeks later he's onboarded. The platform has absorbed the new company's architecture landscape documents. Now when he asks questions, it blends his prior expertise with the new context — answering from both simultaneously.

**Capabilities revealed:** bulk document ingestion, role pack configuration, knowledge taxonomy, multi-document retrieval across time and context, cross-corpus reasoning.

---

### Journey 3: Spur-of-the-Moment Capture

**Sarah** is in a taxi between meetings. A thought strikes her about a pattern she keeps seeing in high-attrition roles — she wants to connect it to the workforce segmentation work she's doing. She sends a WhatsApp message: *"Note: high attrition in senior individual contributor roles seems correlated to unclear progression paths, not compensation. Worth testing this hypothesis."*

The message is ingested, stored with timestamp and context tag, and searchable immediately. Three weeks later, when she asks the platform to help her build a workforce diagnostic framework, it surfaces this note alongside the relevant supporting docs — the hypothesis she captured off the cuff is now part of her thinking.

If she had not had the platform, this thought would have evaporated before she reached her desk.

**Capabilities revealed:** inbound message ingestion, automatic tagging and timestamping, note-as-document storage, surfacing in future retrieval.

---

### Journey 4: The Platform Configurator — Setting Up a New Instance

**Iain** has been asked by a colleague to set up a CoS instance for a Finance Director. He clones the platform configuration, creates a new role pack file, and defines the FD's knowledge taxonomy: financial modelling, board reporting, investor relations, cost management. He writes the tone rules: concise, commercially-framed, sceptical of narrative without numbers.

He spins up the Docker containers with a single command. The FD sends over a folder of board packs, budget files, and strategy documents. Iain runs the ingestion job — it processes Word docs, PDFs, and spreadsheet exports without intervention. He validates by asking a few test questions and checking the citations point to the right source files.

He hands the FD a simple setup card: how to ask questions, how to send a note via messaging, and the three-step restart procedure if anything stops responding.

**Capabilities revealed:** role pack as configuration file, Docker-based setup, multi-format ingestion, instance validation, non-technical user handover documentation.

---

### Journey 5: Infrastructure Edge Case — Something Goes Wrong

**Marcus** opens his laptop on a Monday morning and sends a question to his platform via the chat interface. Nothing comes back. He waits. Still nothing.

He checks the setup card Iain gave him. Step 1: open Terminal and run `cos status`. The output tells him: *"Postgres container not running. Run `cos restart` to recover."* He runs it. Within thirty seconds the containers are back up and his question is answered.

He doesn't know what Postgres is. He doesn't need to. The platform told him exactly what to do in plain language, and it worked.

If it hadn't worked, the card tells him to run `cos logs` and send the output to Iain — one command, one message.

**Capabilities revealed:** CLI health check command (`cos status`), plain-language error messages, one-command restart, log export for support handoff, robust container restart behaviour.

---

### Journey Requirements Summary

| Journey | Capabilities Required |
|---|---|
| Daily executive use | Messaging channel, scheduled briefs, reactive Q&A, citations, calendar integration, note capture |
| New role onboarding | Bulk ingestion, role pack config, knowledge taxonomy, multi-corpus retrieval |
| Spur-of-moment capture | Inbound message ingestion, auto-tagging, note storage, future retrieval surfacing |
| Platform configuration | Role pack as config file, Docker setup, multi-format ingestion, handover docs |
| Infrastructure recovery | CLI health/status command, plain-language errors, one-command restart, log export |

_Note: journeys reference WhatsApp as the messaging channel for narrative clarity; Telegram Bot API is the first implementation target. WhatsApp can be added later via Twilio._

## Domain-Specific Requirements

### Data Sensitivity and Access Model

The platform ingests and indexes highly sensitive personal and organisational material: strategic documents, board packs, career notes, stakeholder intelligence, confidential emails. The following constraints apply:

- **Single-user access per instance** is the enforced model for this phase. Access is controlled by physical access to the device (local deployment) or by the security of the external channel (private email inbox, private WhatsApp group). Multi-user and delegated access (e.g. EA sharing an inbox) are deferred to future phases.
- **Access control is the user's responsibility** for the channels they configure. The platform does not implement channel-level authentication beyond what the channel itself provides.

### Egress Control — Primary Security Concern

The platform's primary security obligation is **controlling where output goes**. Responses must only be delivered via:
- The local chat/query interface (screen or disk)
- Explicitly configured output channels (defined in the role pack or platform config)

No uncontrolled output paths. The platform must not send responses to unconfigured destinations. This applies to scheduled briefs, reactive Q&A responses, and any generated content.

### LLM Data Handling — Accepted Trade-off

For this phase, the platform uses public LLM provider APIs (Claude and others). This means **document chunks are sent to external APIs** as part of query processing. This is an accepted trade-off with the following conditions:

- The platform documentation must clearly state that query context (retrieved document chunks) is transmitted to external LLM providers
- Users and their organisations are responsible for ensuring they have appropriate data handling agreements with their chosen provider (via their own API subscription or enterprise agreement)
- The platform architecture must make it straightforward to substitute a local or on-premise model in future — the model adapter layer must not make assumptions about external connectivity

### Immutable Document Store

Original source documents are **never deleted or overwritten**. The canonical store is append-only for source material:
- Canonical document identity is defined independently from any one `source_path`, connector locator, or managed-copy filename
- Re-ingest from the same logical source creates a new version record when content changes
- Exact-byte deduplication across all ingestion sources is mandatory: identical bytes received from different paths or connectors do not create duplicate canonical documents or duplicate embeddings
- Provenance references (local path, Gmail attachment URI, MCP note URI, message ID, and similar locators) are preserved as source records linked to the canonical document or version they produced
- Managed originals and Markdown working copies are preserved permanently using stable internal identifiers so filename and path collisions do not redefine identity
- This simplifies provenance, supports citation integrity, and means retrieval results always have a traceable source

### Channel Sensitivity Hierarchy

The platform handles channels with different sensitivity profiles. By design:
- **Local interface (screen/disk):** highest trust — full responses, detailed content
- **Configured email channel:** medium-high trust — full responses, appropriate for document-level output
- **Messaging channels (e.g. Telegram):** lower trust — suitable for short notes, quick questions, brief digests; not intended for sensitive document content or full analytical responses

The role pack configuration must define what output types are permitted per channel.

### Risk Mitigations

| Risk | Mitigation |
|---|---|
| Sensitive content sent to wrong channel | Egress control: output only via configured channels |
| LLM provider receives confidential content | Documented trade-off; user/org handles provider agreement; local model path kept open |
| Source documents corrupted or lost | Immutable store; originals preserved in object storage |
| Duplicate ingestion inflating retrieval noise | Deduplication check on ingest (hash or semantic similarity) |
| Non-technical user unable to diagnose data issues | Plain-language status/diagnostic CLI; clear handover documentation |

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Channel-first ambient intelligence**
Most AI knowledge tools assume the user goes to them — opens a chat interface, navigates to a dashboard. This platform inverts that: it comes to the user through whichever channel they already use (WhatsApp, email, calendar context). The interface is ambient, not dedicated. This is a meaningful design departure from the current generation of AI assistant products.

**2. Knowledge/environment separation as a first-class architectural principle**
The explicit separation of the stable knowledge store from the variable environment (model provider, channels, connectors) is a deliberate architectural bet that most AI products don't make. It makes the system long-lived in a way that LLM-coupled products are not — the knowledge asset outlasts any particular model or API.

**3. Role pack as pure configuration**
Role behaviour — tone, priorities, workflows, stakeholder maps, retrieval weights — lives entirely in a configuration file, not in code. A new role can be instantiated without touching the platform. This is a clean separation that enables genuine portability across personas and contexts without the fragility of prompt-injected persona instructions baked into the application layer.

**4. Multi-provider adversarial reasoning** _(Growth/Vision tier)_
The model adapter design explicitly enables routing queries to multiple providers simultaneously for adversarial review — one model proposes, another critiques. This is a concrete use case for multi-model architecture that goes beyond redundancy or cost optimisation.

**5. Personal infrastructure, not SaaS**
The platform is designed for a small number of known individuals, not anonymous users at scale. This enables a depth of personalisation (deep knowledge ingestion, role-specific configuration, user-specific tone calibration) that SaaS products can't economically deliver. It's infrastructure that gets richer over time as the knowledge base grows — not a product you subscribe to and cancel.

### Market Context

This is not a space without competition — Notion AI, Microsoft Copilot, Google Workspace AI, and various RAG-based enterprise tools all address parts of this problem. The differentiating factors here are:

- **Portability** — the knowledge base is owned by the user, not locked to a vendor's platform
- **Role depth** — configuration is designed for a single specific person, not a generic user persona
- **Ambient delivery** — responses come to the user via their existing channels, not via a new app
- **Architectural longevity** — the knowledge/environment separation means the platform doesn't become obsolete when a new model arrives

### Validation Approach

The Phase 1 MVP (builder validation) is inherently a validation exercise: does the knowledge pipeline work? Does retrieval find what you know is there? The Growth tier adds the ambient delivery and channel integrations — the real validation question is whether two users with different role packs find it genuinely useful in their daily work without Iain's ongoing intervention to keep it running.

### Risk Mitigation

| Innovation Risk | Mitigation |
|---|---|
| Channel-first delivery feels intrusive rather than useful | Start with opt-in scheduled briefs; reactive Q&A is always user-initiated |
| Role pack config too complex for non-technical users to set up themselves | Iain configures and maintains instances; users receive a setup card |
| Knowledge/environment separation adds complexity with no near-term payoff | Phase 1 validates the pipeline before the adapter layer is exercised |
| Adversarial multi-model adds cost and latency | Deferred to Vision tier; only activated for specific high-stakes workflows |

## API Backend / Platform Specific Requirements

### Project-Type Overview

The platform is a local-first API backend exposing its capabilities primarily through the **Model Context Protocol (MCP)**. Claude Desktop (or any MCP-compatible client) is the primary chat interface — the platform does not build its own chat UI. A secondary CLI interface handles operations, health checks, and ingestion jobs. All components run in Docker containers managed by Docker Compose.

### API / Interface Layer

**MCP Server (primary interface)**
- The platform runs as an MCP server, exposing tools to any MCP-compatible client
- Core tools exposed via MCP:
  - `retrieve` — keyword + semantic search over the knowledge base, returns cited results
  - `get_role_context` — return current role pack configuration for use in system prompts
  - `list_documents` — list ingested documents with metadata
  - `get_status` — platform health and component status
  - `ingest_document` — add a document to the knowledge base (file path or content) _(Growth)_
  - `web_search` — live internet search, called by the LLM when local context is insufficient _(Growth)_

**CLI (operational interface)**
- `cos status` — health check across all containers and services
- `cos restart` — clean restart of all containers
- `cos logs` — tail logs for support/diagnostic handoff
- `cos ingest <path>` — ingest a file or folder into the knowledge base

**No authentication on localhost** — the platform trusts host machine access controls. LLM provider authentication is handled via API keys in the platform configuration file (not hardcoded).

### Data Schemas and Formats

**Ingestion accepts:**
- PDF (via extraction layer — Apache Tika or equivalent)
- Word documents (.docx)
- Markdown and plain text
- Email with attachments (via Gmail API — message body + attachments processed separately)
- Plain text notes (via MCP `ingest_document` tool or Telegram bot message)

**Internal canonical format:** Markdown working copies for all ingested content

**API responses:** JSON with consistent structure including `content`, `citations[]`, `confidence`, `source_document_id`, `retrieved_chunks[]`

### Authentication Model

- **Local interface:** No authentication — trust host machine
- **LLM provider:** API key in platform config file (`config.yaml`); never in code or environment leakage
- **External connectors (Gmail, Google Calendar):** OAuth 2.0, credentials stored locally in platform config directory
- **Telegram bot:** Bot token in platform config

### External Connectors — Phase Priority

**Growth tier (first real users):**

| Connector | Protocol | Notes |
|---|---|---|
| Gmail | Gmail API (OAuth 2.0) | Read email, ingest attachments, receive messages as notes |
| Google Calendar | Google Calendar API (OAuth 2.0) | Read upcoming events for meeting prep and daily brief |
| Telegram Bot | Telegram Bot API | Bidirectional: inbound questions + note capture, outbound briefs |
| Web search | Brave Search API or Tavily | Exposed as MCP `web_search` tool; LLM calls when needed |

**Later tiers:**
- Outlook / Microsoft 365 (email + calendar)
- WhatsApp via Twilio (if a specific user requires it)
- Dropbox / Google Drive folder watch

### Internet Search Architecture

Web search is exposed as an MCP tool (`web_search`). The LLM decides autonomously when to invoke it based on whether local retrieval is sufficient. The platform handles the API call, caches results briefly to avoid duplicate requests, and returns results in the same citation format as local retrieval. This ensures consistent behaviour across interactive sessions and scheduled programmatic jobs.

### Deployment

- **Docker Compose** — single `docker-compose.yml` defines all services: Postgres + pgvector, object storage (local volume), ingestion worker, MCP server, scheduler
- **Single command startup:** `docker compose up -d`
- **Config file:** `config.yaml` in platform directory — role pack, API keys, connector credentials, output channel config
- **Data directory:** local volume mount — knowledge base, originals, Markdown working copies all persist on host disk (survives container restarts)
- **Cloud portability:** Docker Compose on a Linux VM requires no changes to platform code

### Implementation Considerations

- Tika (or equivalent) for heterogeneous document extraction — handles PDF, Word, and other formats without per-format code
- pgvector extension on Postgres for embedding storage — no separate vector database needed
- Embedding model: provider-agnostic; default to a fast, low-cost model (e.g. `text-embedding-3-small`) with the provider configurable
- MCP server framework: use an existing Python or TypeScript MCP SDK rather than implementing the protocol from scratch
- Scheduler: simple cron-based job runner (e.g. APScheduler in Python, or system cron calling CLI commands) — no complex workflow orchestration needed in Phase 1

## Project Scoping & Phased Development

_This section expands on the Product Scope summary above with detailed capability tables, exclusions, and risk mitigations for each phase._

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP — the goal is to validate that the core knowledge pipeline (ingest → store → retrieve → reason → cite) works correctly and reliably. This is not a user-facing product launch; it is builder validation. The MVP is considered successful when Iain can ingest his own documents, ask questions via Claude Desktop, and get accurate cited answers.

**Builder profile:** Solo build. Scope must be achievable by one person working incrementally. Complexity is managed by using established libraries (MCP SDK, Tika, pgvector) rather than building foundational components from scratch.

### MVP Feature Set (Phase 1 — Builder Validation)

**Core user journeys supported:**
- Platform configurator sets up an instance from scratch
- Documents ingested via CLI (`cos ingest`)
- Questions answered via Claude Desktop (MCP) with cited responses
- System restarts cleanly after failure

**Must-have capabilities:**

| Capability | Rationale |
|---|---|
| Docker Compose setup with Postgres + pgvector | No other components work without this |
| Document ingestion pipeline (PDF, Word, Markdown, plain text) | Core value depends on knowledge being in the store |
| Tika-based extraction to Markdown working copies | Required for format-agnostic ingestion |
| Chunking and embedding pipeline | Required for semantic retrieval |
| Keyword + semantic retrieval with citations | Core retrieval — must work accurately |
| MCP server with `retrieve`, `get_role_context`, `get_status` tools | Claude Desktop is the Phase 1 chat interface |
| Role pack v1 (CHRO) loaded from config file | Required to validate role-specific behaviour |
| CLI: `cos status`, `cos restart`, `cos logs`, `cos ingest` | Required for operational use by non-technical users |
| Plain-language error messages and restart instructions | Non-technical user floor |
| Immutable document store with provenance records | Core architectural principle — must be in from the start |

**Deliberately excluded from MVP:**
- `cos chat` REPL (Claude Desktop via MCP covers this)
- `ingest_document` MCP tool (CLI ingestion is sufficient for Phase 1)
- All external connectors (Gmail, Calendar, Telegram)
- Web search tool
- Scheduled jobs / daily brief
- Cross-source canonical identity hardening and exact-byte deduplication for connector-driven ingestion
- Semantic near-duplicate warning layer

### Post-MVP Features

**Phase 2 — Retrieval Trust and Interactive Messaging:**
- Retrieval evaluation corpus, benchmark harness, and observability
- Retrieval and citation hardening against the evaluation set
- Telegram bot: bidirectional inbound Q&A and note capture
- `ingest_document` MCP tool: allows note capture from any MCP client
- Second role pack validation continues as the main product-level portability check

**Phase 3 — External Context and Proactive Delivery:**
- Web search MCP tool (Brave or Tavily): LLM-callable for live external context
- Scheduled jobs: daily brief generation and calendar-driven meeting prep
- Gmail connector (OAuth 2.0): read email, ingest attachments
- Google Calendar connector: read upcoming events for meeting prep
- Semantic near-duplicate warning layer after exact-byte deduplication and identity resolution are in place

**Phase 4 — Platform Portability and Task Foundations:**
- Structured LLM boundary with provider metadata and direct multi-provider support
- Durable task/runtime substrate for async, resumable, approval-aware workflows
- Outlook / Microsoft 365 connectors if demanded by real users
- WhatsApp via Twilio (if a specific user requires it)

**Phase 5 — Expansion (Vision):**
- Governance hardening: permissions, audit trail, confidence scoring
- Write-back actions with approval step (draft and send via email/messaging)
- Internal model routing and local/self-hosted endpoint support
- Advanced retrieval modes and richer orchestration patterns only where benchmarks justify them

### Risk Mitigation Strategy

**Technical risks:**

| Risk | Likelihood | Mitigation |
|---|---|---|
| Tika extraction quality poor for some doc types | Medium | Test early with representative documents; fall back to direct text extraction for simpler formats |
| pgvector retrieval accuracy insufficient | Medium | Tune chunk size and overlap during Phase 1 validation; test with known content |
| MCP server protocol stability / client compatibility | Low-Medium | Use official MCP SDK; pin to a stable version; test with Claude Desktop |
| OAuth flow complexity for Gmail / Google Calendar | Medium | Defer to Growth tier; use established Python libraries (google-auth) |
| Docker Compose networking issues on Windows | Medium | Test on both macOS and Windows early; document known quirks |

**Validation risks:**

| Risk | Mitigation |
|---|---|
| Phase 1 pipeline works but retrieval quality is poor | Validate with known test questions before declaring Phase 1 done |
| Growth tier users don't find it useful enough to use regularly | Set a clear 30-day usage check after each user is onboarded |

**Resource risks:**

| Risk | Mitigation |
|---|---|
| Solo build scope creep | MVP scope is explicitly defined; additions go to Growth tier |
| Knowledge base grows too large for local Postgres performance | Acceptable at personal-use scale; cloud VM path available if needed |

## Functional Requirements

_Items marked (Growth) are scoped to Phase 2. All others are MVP (Phase 1)._

### Knowledge Ingestion

- **FR1:** Operator can ingest a single file or a folder of files into the knowledge base via CLI
- **FR2:** System extracts text and metadata from PDF, Word document, Markdown, and plain text files during ingestion
- **FR3:** System normalises all ingested content to a Markdown working copy stored alongside the original
- **FR4:** System stores the original source file unchanged and permanently in the document store
- **FR5:** System records provenance metadata for each ingested document and source reference, including source locator or external ID, ingestion timestamp, content hash, and version number where applicable
- **FR6:** System creates a new version record when the same logical source is re-ingested with changed content, preserving all prior versions
- **FR7:** System performs exact-byte deduplication across all ingestion sources and avoids re-embedding or duplicating canonically identical content
- **FR8:** System flags ingested content as a semantic near-duplicate when it exceeds a configurable similarity threshold against existing content and does not silently re-index it _(Growth)_
- **FR9:** User can ingest a short note or thought as a document by sending a message via a connected messaging channel _(Growth)_
- **FR10:** System ingests email message bodies and attachments received via a connected email account _(Growth)_

### Knowledge Retrieval

- **FR11:** User can submit a natural language query and receive a grounded answer with source citations
- **FR12:** System retrieves relevant content using both keyword and semantic (embedding-based) search
- **FR13:** System includes document-level and chunk-level citations in every retrieval response
- **FR14:** System applies role pack retrieval priorities when ranking search results
- **FR15:** User can list all documents currently in the knowledge base with their metadata
- **FR16:** System can invoke a web search to augment local retrieval when local retrieval returns fewer than a configured minimum number of relevant cited results _(Growth)_

### Reasoning & Output

- **FR17:** System synthesises retrieved content into a response that matches the active role pack's tone and style
- **FR18:** System can produce common workflow outputs: summary, briefing, draft, comparison, and prioritisation
- **FR19:** System delivers a scheduled briefing at a configured time via a configured output channel _(Growth)_
- **FR20:** System prepares meeting context from upcoming calendar events at a configured interval before each meeting _(Growth)_
- **FR21:** System only delivers output to explicitly configured channels or the local interface — no uncontrolled output paths

### Role Pack Management

- **FR22:** Operator can define a role pack in a configuration file specifying role goals, tone and style rules, knowledge taxonomy, active workflows, stakeholder map, and retrieval priorities
- **FR23:** Operator can activate a different role pack by updating the configuration file, without modifying application code
- **FR24:** System loads and applies the active role pack at startup across all retrieval and reasoning operations
- **FR25:** User can retrieve a summary of the currently active role context via the platform interface

### Platform Operations

- **FR26:** Operator can check the health status of all platform components with a single CLI command
- **FR27:** Operator can restart all platform components with a single CLI command
- **FR28:** Operator can retrieve diagnostic logs with a single CLI command, in a format suitable for support handoff
- **FR29:** System reports component failures with a recovery message that names the failing component, states the user-visible impact, and provides specific recovery steps
- **FR30:** Operator can provision a complete new platform instance through a single documented bootstrap command or workflow
- **FR31:** Operator can configure all platform settings — API keys, role pack path, output channel config, connector credentials — through a single human-editable configuration artifact

### External Connectivity _(Growth)_

- **FR32:** System reads upcoming events from a connected Google Calendar account for use in meeting prep and scheduled briefs
- **FR33:** System reads and ingests email messages and attachments from a connected Gmail account
- **FR34:** User can send a question or note to the platform via Telegram and receive a response
- **FR35:** System sends scheduled briefs and digests to a user via a configured Telegram or email channel

### Security & Governance

- **FR36:** System enforces egress control — responses are delivered only to configured output channels or the local interface
- **FR37:** System preserves all ingested source documents permanently — originals are never modified or deleted
- **FR38:** Operator can view the full list of ingested documents with their provenance metadata and version history

## Non-Functional Requirements

### Performance

- **NFR1:** Retrieval queries return a response within 5 seconds under normal operating conditions (local deployment, knowledge base up to 10,000 documents)
- **NFR2:** Document ingestion processes at a rate of at least 10 documents per minute for standard file types (PDF, Word, Markdown) on typical consumer hardware
- **NFR3:** The MCP server responds to tool calls within 2 seconds for non-retrieval operations (`get_status`, `get_role_context`, `list_documents`)
- **NFR4:** System startup from a clean deployment state completes within 60 seconds with all required services healthy and ready to serve

### Security

- **NFR5:** API keys and connector credentials are stored only in the local configuration file and are never logged, included in responses, or transmitted beyond their intended API endpoint
- **NFR6:** All LLM API calls are made over HTTPS — no plaintext transmission of document content to external providers
- **NFR7:** Output is delivered exclusively to channels listed in the active configuration — the system must fail closed (suppress output) rather than fail open (deliver to an unintended destination) if a channel is misconfigured
- **NFR8:** The platform does not expose any network ports beyond localhost by default in its standard deployment configuration

### Reliability

- **NFR9:** The platform recovers to a fully operational state within 30 seconds of a `cos restart` command under normal conditions
- **NFR10:** A failure in any single non-core component (e.g. ingestion worker crash) does not make the MCP server or retrieval layer unavailable for more than 30 seconds under normal recovery conditions
- **NFR11:** Connector failures (Gmail API unavailable, Telegram bot unreachable) surface an explicit degraded-status or error signal within 60 seconds while the core retrieval and Q&A path remains available regardless of connector state _(Growth)_
- **NFR12:** The system preserves knowledge base integrity across unclean shutdowns — no partial ingestion records or corrupted embeddings result from a container crash

### Maintainability

- **NFR13:** The complete platform can be provisioned on a new machine by a technically competent person following the setup documentation, without assistance, in under 2 hours
- **NFR14:** Routine operation requires no scheduled manual intervention during a 7-day normal-use period after startup
- **NFR15:** All configuration is expressed in a single human-editable configuration file — no environment-specific code changes are required to switch roles, providers, or channels
- **NFR16:** The platform is deployable on a cloud Linux VM using the standard deployment package and configuration model used locally, without code changes

### Integration

- **NFR17:** The MCP server conforms to the published MCP specification and passes an interoperability test against Claude Desktop for the supported tool set
- **NFR18:** The embedding model is configurable — switching providers requires only a config change, not a code change
- **NFR19:** The LLM provider is configurable — the platform works with any provider supported by the model adapter without modifying ingestion, storage, or retrieval components
- **NFR20:** External connector credentials (Google OAuth tokens, Telegram bot token) are stored and refreshed locally without requiring re-authorisation during a 30-day normal-operation period _(Growth)_
