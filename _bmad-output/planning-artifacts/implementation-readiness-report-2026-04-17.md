---
date: 2026-04-17
project: CoS
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
filesIncluded:
  - prd.md
  - architecture.md
  - architecture-diagrams.md
  - epics.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-17
**Project:** CoS

## Document Inventory

| Type | File | Size | Modified |
|------|------|------|----------|
| PRD | prd.md | 40K | 2026-04-16 |
| Architecture | architecture.md | 41K | 2026-04-17 |
| Architecture (Diagrams) | architecture-diagrams.md | 22K | 2026-04-17 |
| Epics & Stories | epics.md | 97K | 2026-04-17 |
| UX Design | *(not found — no UI in Phase 1)* | — | — |

**No duplicate conflicts identified.**

---

## PRD Analysis

### Functional Requirements

| ID | Requirement | Phase |
|----|-------------|-------|
| FR1 | Operator can ingest a single file or a folder of files into the knowledge base via CLI | MVP |
| FR2 | System extracts text and metadata from PDF, Word document, Markdown, and plain text files during ingestion | MVP |
| FR3 | System normalises all ingested content to a Markdown working copy stored alongside the original | MVP |
| FR4 | System stores the original source file unchanged and permanently in the document store | MVP |
| FR5 | System records provenance metadata for each ingested document (source path, ingestion timestamp, file hash, version number) | MVP |
| FR6 | System creates a new version record when a document with matching identity is re-ingested, preserving all prior versions | MVP |
| FR7 | System detects near-duplicate content on ingest and flags it without silently re-indexing | Growth |
| FR8 | User can ingest a short note or thought as a document by sending a message via a connected messaging channel | Growth |
| FR9 | System ingests email message bodies and attachments received via a connected email account | Growth |
| FR10 | User can submit a natural language query and receive a grounded answer with source citations | MVP |
| FR11 | System retrieves relevant content using both keyword and semantic (embedding-based) search | MVP |
| FR12 | System includes document-level and chunk-level citations in every retrieval response | MVP |
| FR13 | System applies role pack retrieval priorities when ranking search results | MVP |
| FR14 | User can list all documents currently in the knowledge base with their metadata | MVP |
| FR15 | System can invoke a web search to augment local retrieval when local context is insufficient | Growth |
| FR16 | System synthesises retrieved content into a response that matches the active role pack's tone and style | MVP |
| FR17 | System can produce common workflow outputs: summary, briefing, draft, comparison, and prioritisation | MVP |
| FR18 | System delivers a scheduled briefing at a configured time via a configured output channel | Growth |
| FR19 | System prepares meeting context from upcoming calendar events at a configured interval before each meeting | Growth |
| FR20 | System only delivers output to explicitly configured channels or the local interface — no uncontrolled output paths | MVP |
| FR21 | Operator can define a role pack in a configuration file specifying role goals, tone and style rules, knowledge taxonomy, active workflows, stakeholder map, and retrieval priorities | MVP |
| FR22 | Operator can activate a different role pack by updating the configuration file, without modifying application code | MVP |
| FR23 | System loads and applies the active role pack at startup across all retrieval and reasoning operations | MVP |
| FR24 | User can retrieve a summary of the currently active role context via the platform interface | MVP |
| FR25 | Operator can check the health status of all platform components with a single CLI command | MVP |
| FR26 | Operator can restart all platform components with a single CLI command | MVP |
| FR27 | Operator can retrieve diagnostic logs with a single CLI command, in a format suitable for support handoff | MVP |
| FR28 | System reports component failures with a plain-language description of the problem and specific recovery steps | MVP |
| FR29 | Operator can provision a complete new platform instance using a single Docker Compose startup command | MVP |
| FR30 | Operator can configure all platform settings — API keys, role pack path, output channel config, connector credentials — via a single YAML file | MVP |
| FR31 | System reads upcoming events from a connected Google Calendar account for use in meeting prep and scheduled briefs | Growth |
| FR32 | System reads and ingests email messages and attachments from a connected Gmail account | Growth |
| FR33 | User can send a question or note to the platform via Telegram and receive a response | Growth |
| FR34 | System sends scheduled briefs and digests to a user via a configured Telegram or email channel | Growth |
| FR35 | System enforces egress control — responses are delivered only to configured output channels or the local interface | MVP |
| FR36 | System preserves all ingested source documents permanently — originals are never modified or deleted | MVP |
| FR37 | Operator can view the full list of ingested documents with their provenance metadata and version history | MVP |

**Total FRs: 37** (MVP: 25, Growth: 12)

---

### Non-Functional Requirements

| ID | Requirement | Category | Phase |
|----|-------------|----------|-------|
| NFR1 | Retrieval queries return a response within 5 seconds under normal operating conditions (local, up to 10,000 docs) | Performance | MVP |
| NFR2 | Document ingestion processes at ≥10 documents per minute for standard file types on typical consumer hardware | Performance | MVP |
| NFR3 | MCP server responds to non-retrieval tool calls within 2 seconds | Performance | MVP |
| NFR4 | System startup (all containers healthy) completes within 60 seconds on `docker compose up` | Performance | MVP |
| NFR5 | API keys and credentials stored only in local config file — never logged, included in responses, or leaked | Security | MVP |
| NFR6 | All LLM API calls made over HTTPS — no plaintext transmission of document content | Security | MVP |
| NFR7 | Output delivered exclusively to configured channels — fail closed (suppress) rather than fail open if misconfigured | Security | MVP |
| NFR8 | No network ports exposed beyond localhost by default in Docker Compose configuration | Security | MVP |
| NFR9 | Platform recovers to fully operational state within 30 seconds of `cos restart` | Reliability | MVP |
| NFR10 | Failure in any single component does not cause MCP server or retrieval layer to become unavailable | Reliability | MVP |
| NFR11 | Connector failures (Gmail, Telegram) handled gracefully — core retrieval/Q&A path remains available | Reliability | Growth |
| NFR12 | System preserves knowledge base integrity across unclean shutdowns — no partial records or corrupted embeddings | Reliability | MVP |
| NFR13 | Complete platform can be provisioned on a new machine by a technically competent person in under 2 hours | Maintainability | MVP |
| NFR14 | Routine operation requires no manual intervention — platform runs unattended once started | Maintainability | MVP |
| NFR15 | All configuration in a single `config.yaml` file — no environment-specific code changes to switch roles/providers/channels | Maintainability | MVP |
| NFR16 | Platform is deployable on a cloud Linux VM using the same Docker Compose config, without code changes | Maintainability | MVP |
| NFR17 | MCP server conforms to the published MCP specification and is verified to work with Claude Desktop | Integration | MVP |
| NFR18 | Embedding model is configurable — switching providers requires only a config change, not a code change | Integration | MVP |
| NFR19 | LLM provider is configurable — works with any provider supported by the model adapter without modifying ingestion/storage/retrieval | Integration | MVP |
| NFR20 | External connector credentials (Google OAuth, Telegram bot token) stored and refreshed locally without re-authorisation | Integration | Growth |

**Total NFRs: 20** (MVP: 17, Growth: 3)

---

### Additional Requirements & Constraints

| Category | Requirement |
|----------|-------------|
| Data handling | Document chunks are transmitted to external LLM APIs — this is an accepted trade-off; must be documented; users responsible for provider agreements |
| Data model | Immutable document store — append-only for source material; no deletes or overwrites |
| Data model | Deduplication on ingest (hash or semantic similarity) — nice-to-have in MVP, required in Growth |
| Access model | Single-user access per instance; multi-user/delegated access deferred |
| Access model | No authentication on localhost — host machine access controls are trusted |
| Channel sensitivity | Local interface: full responses; email: full responses; messaging (Telegram): short notes/briefs only — role pack defines permitted output types per channel |
| MCP tools (MVP) | `retrieve`, `get_role_context`, `list_documents`, `get_status` |
| MCP tools (Growth) | `ingest_document`, `web_search` |
| CLI commands | `cos status`, `cos restart`, `cos logs`, `cos ingest <path>` |
| API response format | JSON with `content`, `citations[]`, `confidence`, `source_document_id`, `retrieved_chunks[]` |
| Deployment | Single `docker-compose.yml`; single command startup; data persists on host disk via volume mount |
| Portability | Cloud portability: Docker Compose on Linux VM requires no code changes |
| Role pack | CHRO as Phase 1 reference; second role validates abstraction in Phase 2 |
| Scope boundary | No `cos chat` REPL in MVP (Claude Desktop via MCP covers this); no `ingest_document` MCP tool in MVP |

---

## Epic Coverage Validation

### FR Coverage Matrix

| FR | PRD Requirement (summary) | Phase | Epic | Stories | Status |
|----|--------------------------|-------|------|---------|--------|
| FR1 | CLI ingest file/folder | MVP | Epic 2 | 2.4 | ✓ Covered |
| FR2 | Extract PDF, Word, Markdown, plain text | MVP | Epic 2 | 2.1 | ✓ Covered |
| FR3 | Normalise to Markdown working copy | MVP | Epic 2 | 2.1 | ✓ Covered |
| FR4 | Store original unchanged permanently | MVP | Epic 2 | 2.1, 2.3 | ✓ Covered |
| FR5 | Record provenance metadata | MVP | Epic 2 | 2.3 | ✓ Covered |
| FR6 | Version record on re-ingest | MVP | Epic 2 | 2.3 | ✓ Covered |
| FR7 | Near-duplicate detection | Growth | Epic 6 | 6.2 | ✓ Covered |
| FR8 | Note capture via messaging channel | Growth | Epic 7 | 7.3, 6.6 | ✓ Covered |
| FR9 | Email ingestion via Gmail | Growth | Epic 6 | 6.4 | ✓ Covered |
| FR10 | NL query → grounded answer with citations | MVP | Epic 3 | 3.3, 3.4 | ✓ Covered |
| FR11 | Hybrid keyword + semantic search | MVP | Epic 3 | 3.1 | ✓ Covered |
| FR12 | Document + chunk citations in every response | MVP | Epic 3 | 3.1, 3.4 | ✓ Covered |
| FR13 | Role pack retrieval priorities applied | MVP | Epic 3 | 3.1 (stub), 4.3 (real) | ✓ Covered |
| FR14 | List documents with metadata | MVP | Epic 3 | 2.5, 3.4 | ✓ Covered |
| FR15 | Web search augmentation | Growth | Epic 7 | 7.4 | ✓ Covered |
| FR16 | Synthesise in role pack tone | MVP | Epic 3 | 3.3 (stub), 4.3 (real) | ✓ Covered |
| FR17 | Workflow outputs: summary, briefing, draft, comparison, prioritisation | MVP | Epic 3 | 3.3 | ⚠️ Partial — see gap below |
| FR18 | Scheduled briefing via configured channel | Growth | Epic 7 | 7.5 | ✓ Covered |
| FR19 | Meeting prep from calendar events | Growth | Epic 7 | 7.5 | ✓ Covered |
| FR20 | Output only to configured channels | MVP | Epic 3 | 3.2 | ✓ Covered |
| FR21 | Define role pack in config file | MVP | Epic 4 | 4.1 | ✓ Covered |
| FR22 | Activate different role pack, no code change | MVP | Epic 4 | 4.4 | ✓ Covered |
| FR23 | Load and apply role pack at startup | MVP | Epic 4 | 4.2 | ✓ Covered |
| FR24 | Retrieve active role context via platform | MVP | Epic 4 | 3.4 (stub), 4.3 (real) | ✓ Covered |
| FR25 | Health status — single CLI command | MVP | Epic 5 | 5.1 | ✓ Covered |
| FR26 | Restart — single CLI command | MVP | Epic 5 | 5.2 | ✓ Covered |
| FR27 | Diagnostic logs — single CLI command | MVP | Epic 5 | 5.3 | ✓ Covered |
| FR28 | Plain-language errors with recovery steps | MVP | Epic 5 | 5.1, 5.2 | ✓ Covered |
| FR29 | Docker Compose provisioning | MVP | Epic 1 | 1.1, 1.5 | ✓ Covered |
| FR30 | Single YAML config for all settings | MVP | Epic 1 | 1.2 | ✓ Covered |
| FR31 | Google Calendar read | Growth | Epic 6 | 6.5 | ✓ Covered |
| FR32 | Gmail read and ingest | Growth | Epic 6 | 6.4 | ✓ Covered |
| FR33 | Telegram Q&A and note capture | Growth | Epic 7 | 7.2, 7.3 | ✓ Covered |
| FR34 | Scheduled briefs via Telegram or email | Growth | Epic 7 | 7.5 | ⚠️ Partial — see gap below |
| FR35 | Enforce egress control | MVP | Epic 3 | 3.2 | ✓ Covered |
| FR36 | Originals never modified or deleted | MVP | Epic 2 | 2.1, 2.3 | ✓ Covered |
| FR37 | View documents with provenance history | MVP | Epic 2 | 2.5 | ✓ Covered |

**Coverage: 35/37 fully covered, 2 partial gaps identified**

---

### NFR Coverage Matrix

| NFR | Category | Epic(s) | Story / Mechanism | Status |
|-----|----------|---------|-------------------|--------|
| NFR1 | Performance — 5s query | Epic 3 | 3.1 AC | ✓ Covered |
| NFR2 | Performance — 10 docs/min ingestion | Epic 2 | 2.4 AC | ✓ Covered |
| NFR3 | Performance — 2s non-retrieval MCP tools | Epic 3 | 3.4 AC | ✓ Covered |
| NFR4 | Performance — 60s startup | Epic 1 | 1.1 AC | ✓ Covered |
| NFR5 | Security — credentials never logged | Epic 5 | 5.4 | ✓ Covered |
| NFR6 | Security — HTTPS only | Epic 3 | 3.3, 5.4 | ✓ Covered |
| NFR7 | Security — fail-closed output | Epic 3 | 3.2 | ✓ Covered |
| NFR8 | Security — localhost ports only | Epic 1 | 1.1 AC | ✓ Covered |
| NFR9 | Reliability — 30s restart | Epic 5 | 5.2 AC | ✓ Covered |
| NFR10 | Reliability — component isolation | Epic 1 | 1.1 (service interfaces) | ✓ Covered |
| NFR11 | Reliability — connector failure isolation | Epic 6, 7 | 6.4, 6.5, 7.1 | ✓ Covered |
| NFR12 | Reliability — integrity across crashes | Epic 2 | 2.3 (transactions) | ✓ Covered |
| NFR13 | Maintainability — 2hr provisioning | Epic 1 | 1.6 docs | ✓ Covered |
| NFR14 | Maintainability — unattended operation | Epic 5 | 5.2, 5.5 | ✓ Covered |
| NFR15 | Maintainability — single config file | Epic 1, 4 | 1.2, 4.4 | ✓ Covered |
| NFR16 | Maintainability — cloud VM deploy | Epic 1 | 1.1 (Docker Compose) | ✓ Covered |
| NFR17 | Integration — MCP spec compliance | Epic 3 | 3.4, 1.4 | ✓ Covered |
| NFR18 | Integration — embedding configurable | Epic 4 | 4.4 | ✓ Covered |
| NFR19 | Integration — LLM provider configurable | Epic 4 | 4.4 | ✓ Covered |
| NFR20 | Integration — OAuth auto-refresh | Epic 6, 7 | 6.1 | ✓ Covered |

**NFR Coverage: 20/20 fully covered**

---

### Gaps Identified

#### Gap 1: FR17 — Workflow Outputs (Draft and Prioritisation)

**FR17 requires:** "System can produce common workflow outputs: summary, briefing, draft, comparison, and prioritisation"

**What the stories say:** Story 3.3 states that output types are handled "through prompt construction, not separate code paths" and names four types: question, comparison, summary, briefing. The acceptance criteria demonstrate: question → direct answer; comparison → structured comparison; summary → concise synthesis; briefing → briefing format.

**Missing:** "draft" (producing a draft document/email/communication) and "prioritisation" (producing a ranked/ordered list of items by priority) are not explicitly mentioned in any acceptance criteria. It is possible the author intended these to be covered implicitly by "prompt construction," but no story AC tests for them.

**Impact:** Medium. Draft generation and prioritisation are both legitimate executive use cases cited in the user journeys (e.g. drafting a response for a board meeting, prioritising competing initiatives). If these output types are expected to work at launch, at least one story should have an AC that verifies them.

**Recommendation:** Add AC to Story 3.3 explicitly covering: (a) a "draft" prompt producing a structured draft document and (b) a "prioritisation" prompt producing a ranked list — confirming both work via the prompt construction approach.

---

#### Gap 2: FR34 — Scheduled Briefs "or Email" Channel

**FR34 requires:** "System sends scheduled briefs and digests to a user via a configured Telegram or email channel"

**What the stories say:** Story 7.5 (APScheduler, Morning Brief & Meeting Prep) delivers via `OutputRouter.send(channel="telegram")` only. No story addresses an email output channel for scheduled delivery.

**Impact:** Low-Medium. For Phase 2 users who do not use Telegram but receive briefs via email, this gap matters. The `OutputRouter` architecture supports multiple channels in principle, but no story creates an email output channel handler for scheduled delivery.

**Recommendation:** Either (a) add a story in Epic 7 for an email output channel (`output/channels/email.py`), wired into `OutputRouter` and usable by the scheduler — or (b) explicitly descope the "email" option from FR34 in the PRD and epics to avoid a false promise.

---

### Additional Observations (Not Gaps, But Worth Noting)

| Item | Observation |
|------|-------------|
| FR20 / FR35 duplication | These two FRs describe the same egress control requirement. FR20 is in "Reasoning & Output," FR35 is in "Security & Governance." Both are correctly mapped to the same story (3.2). No functional gap, but the PRD has redundant requirements. |
| `cos auth` command | Not defined as an FR in the PRD but introduced in Story 6.1. This is a necessary operational capability for OAuth setup. The epics have correctly filled this gap without needing a PRD change. |
| `cos docs` command | Not in the PRD CLI list (FR27 mentions `cos status`, `cos restart`, `cos logs`) but added in Story 2.5 as a natural companion to FR14/FR37. Fine addition, not a gap. |
| Stub-to-real progression | FR13 and FR16 are delivered in two stages: stub in Epic 3, real in Epic 4. This is correctly documented in Epic 3's Note section. No gap, but builders should be aware the retrieval quality will improve only after Epic 4. |

---

### Coverage Statistics

- **Total PRD FRs:** 37 (25 MVP, 12 Growth)
- **FRs fully covered in epics:** 35 (94.6%)
- **FRs with partial gaps:** 2 (FR17, FR34)
- **FRs not covered:** 0
- **Total PRD NFRs:** 20
- **NFRs covered:** 20 (100%)

---

### PRD Completeness Assessment

The PRD is **well-structured and thorough**. Requirements are clearly numbered, phased, and cross-referenced against user journeys. Key observations:

- **Strengths:** Clear FR/NFR separation, explicit phase tagging (MVP vs Growth), detailed journey-to-capability mapping, explicit scope exclusions, and risk registers.
- **Potential gaps to validate against epics:**
  - FR7 (deduplication) is excluded from MVP but flagged as "nice-to-have" — epics should clarify this is not in scope.
  - FR17 (workflow outputs: summary, briefing, draft, comparison, prioritisation) is MVP — this is a broad capability; epic coverage should confirm all five output types are addressed.
  - NFR12 (integrity across unclean shutdowns) is an MVP requirement but relatively subtle — epic/story coverage should include explicit Postgres transaction handling or volume mount durability story.
  - The API response format (JSON with `citations[]`, `confidence`, `source_document_id`, `retrieved_chunks[]`) is a concrete contract — stories should validate this schema is implemented consistently.

---

## UX Alignment Assessment

### UX Document Status

**Not applicable — no UX document exists or is required for this project.**

The platform is an API backend with no built UI:
- Primary query interface: Claude Desktop / Claude Code (existing MCP-compatible clients, not built by this platform)
- Operational interface: terminal CLI (`cos` commands)
- Messaging interface: Telegram (plain text messages, no UI to design)

The epics document explicitly confirms: *"Not applicable — this is an API backend platform with no UI. The primary interface is Claude Desktop (MCP client) and a terminal CLI."*

### Alignment Issues

None. The absence of a UX document is by design, not an oversight.

### Warnings

None. For completeness:

| Interface | Handled by | UX Design Needed? |
|-----------|------------|-------------------|
| Chat / Q&A | Claude Desktop / Claude Code (MCP) | No — third-party client |
| CLI operations | Terminal (`cos` commands) | No — plain text output |
| Messaging | Telegram Bot API (plain text) | No |
| Morning briefs | Telegram / email (plain text) | No |

**Verdict:** No UX design documentation gap exists for this project type.

---

## Epic Quality Review

### Overview

7 epics reviewed. 46 stories assessed. Findings are classified as Critical (🔴), Major (🟠), or Minor (🟡).

---

### Epic-Level Assessment

#### Epic 1: Runnable Platform Foundation

**User Value Check:** The goal statement is user-centric: "Operator can stand up a fully healthy CoS instance from scratch with a single command." The title is slightly technical ("Foundation") but the value is clear. After Epic 1 alone, an operator can run the platform and connect Claude Desktop. ✓

**Independence:** Standalone. No prior epics. ✓

**Story Sizing:**

| Story | Assessment |
|-------|------------|
| 1.1 Project Scaffold, Containerised Services & Core Interfaces | 🟠 Oversized — 7 distinct AC blocks covering: uv init, Docker Compose, port binding, service stubs, LLMAdapter protocol, OutputRouter, connectors stub, and restart cycle. This is a very large story. Could reasonably be split into "Project Scaffold & Docker Compose" and "Core Interface Stubs." |
| 1.2 Configuration Loader | ✓ Well-sized, user-centric, clear ACs |
| 1.3 Database Schema & Migration Runner | 🟡 Creates `chunks` and `embeddings` tables that are not needed until Epic 2. Violates the "create tables when first needed" principle. |
| 1.4 MCP Server Foundation | ✓ Well-sized, user-centric (Claude Desktop can connect) |
| 1.5 Operator Validation | ✓ Correct pattern — smoke test of assembled Epic 1 |
| 1.6 Documentation & Housekeeping | ✓ Correct placement (last story) |

---

#### Epic 2: Document Knowledge Base

**User Value Check:** "Operator can load documents...permanently stored with full provenance." — clear user outcome. ✓

**Independence:** Builds only on Epic 1 foundation. ✓

| Story | Assessment |
|-------|------------|
| 2.1 Document Extraction & Markdown Normalisation | ✓ Well-scoped, clear ACs |
| 2.2 Text Chunking & Embedding Pipeline | 🟡 More technical, but a necessary distinct unit. ACs are measurable (1024 tokens, 100 overlap, configurable provider). ✓ |
| 2.3 Provenance Storage & Transactional Writes | ✓ Good technical story, user-value framed around data integrity |
| 2.4 CLI Ingest Command & IngestService | ✓ Best story in the epic — clear user action, concrete ACs |
| 2.5 Document Provenance Listing | ✓ User-centric (`cos docs`), good ACs |
| 2.6 Operator Validation | ✓ Correct pattern |
| 2.7 Documentation & Housekeeping | ✓ Correct placement |

**Dependency note:** Stories 2.1 → 2.2 → 2.3 → 2.4 form a natural chain. Story 2.4 depends on 2.1–2.3 being complete. This is acceptable within-epic dependency. ✓

---

#### Epic 3: Knowledge Retrieval & Cited Q&A

**User Value Check:** "User can ask natural language questions and receive synthesised, grounded answers." — clear user outcome. ✓

**Independence:** Depends on Epics 1 and 2. Epic 3 does NOT require Epic 4. The role pack runs on stubs. ✓

| Story | Assessment |
|-------|------------|
| 3.1 Hybrid Search Engine & Citation Formatting | ✓ Well-scoped, technical but enables FR11/FR12 |
| 3.2 OutputRouter & Egress Enforcement | ✓ Clear user value (egress security), measurable ACs |
| 3.3 LLM Synthesis & RetrievalService | ✓ Good — note below |
| 3.4 MCP Retrieve & List Documents Tools | ✓ User-centric, clear interface contract |
| 3.5 Operator Validation | ✓ Correct pattern |
| 3.6 Documentation & Housekeeping | ✓ Correct placement |

**Story 3.3 — FR17 note:** Story 3.3 AC states output types are handled "through prompt construction, not separate code paths" and names: question, comparison, summary, briefing. The FR requires 5 types: summary, briefing, draft, comparison, prioritisation. "Draft" and "prioritisation" are not named in any AC. The story may deliver them implicitly, but no acceptance criterion verifies them. **(Confirmed gap from Step 3.)**

**Forward reference in Story 3.4:** AC states `get_role_context` returns `{"status": "ok", "data": {"role": "stub — configured in Epic 4"}}`. This is a forward reference in acceptance criteria text. Not a hard dependency (the stub works), but it contains implementation guidance that references future work, which is a minor structural smell.

---

#### Epic 4: Role Identity & Configuration

**User Value Check:** "Operator can define a complete role identity...without touching the code." — clear user outcome. ✓

**Independence:** Builds on Epic 3 stubs. Epic 3 delivers working Q&A; Epic 4 improves it. ✓ (Epic 3 is explicitly usable without Epic 4.)

| Story | Assessment |
|-------|------------|
| 4.1 Role Pack Schema & CHRO Configuration File | ✓ User-centric, well-scoped |
| 4.2 Role Pack Loader & Startup Integration | ✓ Replaces Epic 1 stub with real implementation |
| 4.3 Role Pack Applied to Retrieval & Synthesis | ✓ High-value story — demonstrably improves answers |
| 4.4 Role Pack & Provider Portability | ✓ Validates the abstraction — important capability |
| 4.5 Operator Validation | ✓ Correct pattern |
| 4.6 Documentation & Housekeeping | ✓ Correct placement |

---

#### Epic 5: Platform Operations & Resilience

**User Value Check:** "Operator and non-technical users can monitor, diagnose, and recover the platform using simple CLI commands." — clear user outcome. ✓

**Independence:** CLI operations are independent of knowledge pipeline quality. ✓

| Story | Assessment |
|-------|------------|
| 5.1 Health Check System (`cos status`) | ✓ Excellent story — specific, measurable, plain-language ACs |
| 5.2 Platform Restart & Recovery (`cos restart`) | ✓ Clear user value, measurable (30s) |
| 5.3 Diagnostic Log Export (`cos logs`) | ✓ User-centric, concrete ACs |
| 5.4 Secrets & Security Audit | 🟠 **Issue — see below** |
| 5.5 Operator Validation | ✓ Correct pattern |
| 5.6 Documentation & Housekeeping | ✓ Correct placement |

**Story 5.4 Issue:** "Secrets & Security Audit" is a cross-cutting audit story, not a capability delivery story. Its ACs are all validation checks ("Given a full audit of all structured log statements... When each log statement is reviewed... Then no log call references any credential"). This is a code review / testing task, not a new feature. Best practice says security constraints should be ACs within the relevant implementation stories (e.g. Story 3.3 for HTTPS, Story 5.3 for credential logging), not grouped into a separate audit story. The risk is that security is treated as something to "audit later" rather than built correctly from the start.

---

#### Epic 6: Connected Knowledge Sources

**User Value Check:** "Platform automatically ingests live content from Gmail and Google Calendar." — clear user outcome. ✓

**Independence:** Builds on Epic 2 ingestion pipeline and Epic 1 foundation. ✓

| Story | Assessment |
|-------|------------|
| 6.1 OAuth Authentication Setup | ✓ Necessary first step, user-centric |
| 6.2 Near-Duplicate Detection | ✓ User-centric (clean knowledge base), measurable |
| 6.3 Jobs Queue & Background Ingestion Worker | 🟡 Technical infrastructure story. Framed with operator value but the user benefit is indirect. Acceptable as a prerequisite for 6.4/6.5. |
| 6.4 Gmail Connector | ✓ User-centric, good ACs |
| 6.5 Google Calendar Connector | ✓ User-centric, good ACs |
| 6.6 `ingest_document` MCP Tool | ✓ User-centric, well-defined ACs |
| 6.7 Operator Validation | ✓ Correct pattern |
| 6.8 Documentation & Housekeeping | ✓ Correct placement |

**Database timing — Story 6.3:** The `jobs` table is created in Epic 6 Story 6.3 (via `002_jobs.sql`). The stub migration file was placed in Epic 1, but the actual table creation is deferred to Epic 6. This correctly follows the "create tables when first needed" principle. ✓

---

#### Epic 7: Ambient Messaging Intelligence

**User Value Check:** "Users interact with the platform through Telegram — asking questions, capturing notes, receiving proactive morning briefs." — clear user outcome. ✓

**Independence:** Builds on Epic 6 (jobs queue) and Epic 3 (retrieval). ✓

| Story | Assessment |
|-------|------------|
| 7.1 Telegram Bot Setup & Output Channel | ✓ Necessary foundation for Telegram layer |
| 7.2 Telegram Inbound Q&A | ✓ High-value, clear ACs |
| 7.3 Telegram Note Capture | ✓ User-centric, well-defined |
| 7.4 Web Search MCP Tool | ✓ User-centric, measurable ACs |
| 7.5 APScheduler, Morning Brief & Meeting Prep | 🟠 **Oversized — see below** |
| 7.6 Operator Validation | ✓ Correct pattern |
| 7.7 Documentation & Housekeeping | ✓ Correct placement |

**Story 7.5 Issue:** This story combines three distinct concerns: APScheduler integration, morning brief generation, and meeting prep scheduling. Each is a substantial user-facing feature:
- APScheduler setup is infrastructure
- Morning brief is a distinct daily scheduled output
- Meeting prep is a distinct event-triggered output

Combining all three produces a story with 6 AC blocks covering scheduler wiring, brief content quality, meeting prep timing, delivery failure handling, empty-calendar fallback, and container restart recovery. This is likely a 3–4 sprint story wrapped as one. Recommendation: split into (a) Scheduler Infrastructure & Morning Brief and (b) Meeting Prep from Calendar Events.

---

### Quality Summary by Severity

#### 🔴 Critical Violations

None found. All epics deliver user value. No epic-level forward dependencies. Epic ordering is sound.

#### 🟠 Major Issues

| # | Epic | Story | Issue |
|---|------|-------|-------|
| M1 | Epic 1 | 1.1 | Story is oversized — 7 distinct AC groups covering scaffold, Docker, port binding, service stubs, LLMAdapter, OutputRouter, connectors stub, and restart cycle. Should be considered for splitting. |
| M2 | Epic 5 | 5.4 | "Secrets & Security Audit" is a testing/audit story, not a capability story. Security constraints should be ACs within implementation stories (3.3, 5.3, etc.), not deferred to a separate audit. Risk: security as afterthought. |
| M3 | Epic 7 | 7.5 | Story is oversized — combines APScheduler, morning brief, and meeting prep into one story. Three distinct user-facing features that would benefit from separation. |

#### 🟡 Minor Concerns

| # | Epic | Story | Issue |
|---|------|-------|-------|
| m1 | Epic 1 | 1.3 | Creates `chunks` and `embeddings` tables in Epic 1, though they are not first used until Epic 2. Minor violation of "create tables when first needed" principle. Not blocking — migration runner needs to be established here. |
| m2 | Epic 3 | 3.3 | FR17 gap — "draft" and "prioritisation" output types not named in any AC. Story claims all 5 types work via prompt construction but only verifies 3 (question, comparison, summary, briefing). |
| m3 | Epic 3 | 3.4 | AC text contains forward reference: "stub — configured in Epic 4." Not a hard dependency but references future work in an acceptance criterion. Minor structural smell. |
| m4 | Epic 6 | 6.3 | Jobs Queue story is infrastructure-focused with indirect user value. Acceptable as prerequisite for connector stories but framing could be more user-centric. |

---

### Best Practices Compliance Summary

| Epic | Delivers User Value | Independent | Stories Sized OK | No Forward Deps | DB Timing | Clear ACs |
|------|---------------------|-------------|------------------|-----------------|-----------|-----------|
| Epic 1 | ✓ | ✓ | ⚠️ 1.1 oversized | ✓ | ⚠️ 1.3 creates future tables | ✓ |
| Epic 2 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Epic 3 | ✓ | ✓ | ✓ | ⚠️ 3.4 refs Epic 4 | ✓ | ⚠️ FR17 gap in 3.3 |
| Epic 4 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Epic 5 | ✓ | ✓ | ✓ | ✓ | ✓ | ⚠️ 5.4 is audit not feature |
| Epic 6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Epic 7 | ✓ | ✓ | ⚠️ 7.5 oversized | ✓ | ✓ | ✓ |

---

## Summary and Recommendations

### Overall Readiness Status

**READY — with 5 recommended improvements before the affected stories are implemented.**

The documentation set is of high quality overall. The PRD is well-structured with 37 clearly numbered, phased requirements. The architecture is thorough and technically specific. The epics map all requirements to stories with correct epic progression, proper validation stories, and documentation housekeeping stories. No critical violations were found.

The issues identified are specific, contained, and addressable story-by-story — they do not require rework of the overall architecture or epic structure.

---

### All Issues Consolidated

| # | Severity | Source | Epic/Story | Issue |
|---|----------|--------|-----------|-------|
| 1 | 🟠 Major | FR Coverage | Story 3.3 | FR17 gap — "draft" and "prioritisation" output types not covered in any AC |
| 2 | 🟠 Major | FR Coverage | Story 7.5 | FR34 gap — email output channel for scheduled briefs not addressed; only Telegram covered |
| 3 | 🟠 Major | Epic Quality | Story 1.1 | Story is oversized — 7 distinct AC groups across scaffold, Docker, interfaces, OutputRouter, connectors |
| 4 | 🟠 Major | Epic Quality | Story 5.4 | Audit/testing story masquerading as feature story — security ACs should be in implementation stories |
| 5 | 🟠 Major | Epic Quality | Story 7.5 | Story is oversized — APScheduler + morning brief + meeting prep are 3 distinct features |
| 6 | 🟡 Minor | Epic Quality | Story 1.3 | `chunks` and `embeddings` tables created in Epic 1, not first needed until Epic 2 |
| 7 | 🟡 Minor | Epic Quality | Story 3.4 | AC text contains forward reference to Epic 4 ("stub — configured in Epic 4") |
| 8 | 🟡 Minor | Epic Quality | Story 6.3 | Jobs queue story is infrastructure-framed with indirect user value |
| 9 | 🟡 Minor | PRD | FR20/FR35 | Duplicate requirements — both describe egress control; covered correctly but redundant in PRD |

**Total issues: 9** (5 Major, 4 Minor | 0 Critical, 0 Blocking)

---

### Recommended Next Steps

The following actions are listed in order of priority. Items 1–5 should be addressed before implementing the affected stories.

**1. Fix FR17 in Story 3.3 — Add ACs for "draft" and "prioritisation" output types**

Add two acceptance criteria to Story 3.3:
- Given a prompt requesting a draft (e.g. "Draft a briefing note on..."), when the synthesised response is returned, then it is structured as a draft document with appropriate sections.
- Given a prompt requesting prioritisation (e.g. "Prioritise these initiatives..."), when the synthesised response is returned, then it is structured as a ranked list with reasoning.

This closes the only MVP functional requirement gap.

**2. Resolve FR34 in Epic 7 — Clarify or add email channel for scheduled briefs**

Choose one:
- (a) Add a story in Epic 7 for an email output channel handler (`output/channels/email.py`) and wire it into `OutputRouter` and the scheduler; or
- (b) Explicitly descope the "or email" clause from FR34 in the PRD and update the Epic 7 coverage map note accordingly.

Option (b) is lower effort and likely sufficient if Telegram is the primary channel for the initial users.

**3. Split Story 1.1 into two stories**

- Story 1.1a: "Project Scaffold & Containerised Services" — uv init, docker-compose.yml, port binding, docker down/up cycle
- Story 1.1b: "Core Service Interfaces & Protocol Stubs" — service stubs, LLMAdapter protocol, OutputRouter stub, connectors placeholder

Both are independently completable and deliverable. This makes the foundation epic more manageable.

**4. Redistribute Story 5.4 ACs into implementation stories**

Move the security constraint ACs from Story 5.4 to their appropriate implementation stories:
- HTTPS-only LLM calls → Story 3.3 AC
- Credential logging audit → Story 5.3 AC (or Story 3.3)
- Credentials never in MCP responses → Story 3.4 AC
- `config.yaml` not committed → Story 1.2 AC (already partially there)

Then remove Story 5.4 or repurpose it as a lightweight integration test story ("run the full security validation checklist as part of Operator Validation").

**5. Split Story 7.5 into two stories**

- Story 7.5a: "Scheduler Infrastructure & Morning Brief" — APScheduler integration, daily brief at configured time, Telegram delivery, fallback for no-event days
- Story 7.5b: "Meeting Prep from Calendar Events" — event-triggered prep job, calendar-to-retrieval query, pre-meeting delivery

Both can stand independently, and each is substantial enough to warrant its own validation.

---

### Minor Items (Address At Discretion)

- **Story 1.3 DB timing:** Acceptable for a migration-runner-first architecture. The runner needs to exist, and having the full schema in `001_initial.sql` is pragmatic. Low priority to change.
- **Story 3.4 forward reference:** Replace "stub — configured in Epic 4" with "role pack not yet loaded — returns default configuration" to avoid referencing future epics in ACs.
- **Story 6.3 framing:** Reframe the user story to: "As an operator, I want live ingestion from connectors to happen in the background without affecting my ability to ask questions, so that connector activity is transparent to normal use." More user-centric.
- **PRD FR20/FR35 duplication:** Note for a future PRD revision. No action needed before implementation.

---

### Final Note

This assessment identified **9 issues** across **3 categories** (FR coverage, epic quality, PRD). No critical or blocking issues were found. The 5 major issues are contained to specific stories and are straightforward to fix. The platform documentation set demonstrates strong architectural thinking, clear phasing discipline, and genuine attention to non-technical user experience.

**Assessment completed:** 2026-04-17
**Documents assessed:** `prd.md`, `architecture.md`, `architecture-diagrams.md`, `epics.md`
**FRs with full coverage:** 35/37 (94.6%) | **NFRs with full coverage:** 20/20 (100%)
