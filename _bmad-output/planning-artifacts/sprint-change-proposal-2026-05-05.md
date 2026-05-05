# Sprint Change Proposal - Canonical Document Identity Before Epic 6

**Project:** CoS  
**Date:** 2026-05-05  
**Prepared by:** Codex via `bmad-correct-course`  
**Mode used:** Batch (assumed, to avoid blocking progress)

## 1. Issue Summary

### Trigger

This change was raised ahead of **Epic 6: Connected Knowledge Sources** based on the current implementation and planning model for document provenance and versioning.

The issue is visible in the implemented Epic 2 ingestion/storage path:

- `src/cos/store/db.py` detects re-ingest by `documents.source_path`
- `src/cos/store/migrations/001_initial.sql` stores `source_path` and `file_hash`, but has no cross-source exact-byte dedupe mechanism
- `src/cos/ingestion/extractor.py` writes managed originals by filename and Markdown working copies by stem, which creates collision risk for same-named files from different sources
- `_bmad-output/implementation-artifacts/deferred-work.md` already records:
  - missing uniqueness on `documents.source_path`
  - filename/stem collisions in managed copies
  - ambiguity around version-linked chunk history

### Problem Statement

This is a **technical limitation discovered during implementation** with direct architecture and backlog impact.

The platform currently treats `source_path` as the effective document identity for versioning. That works for manual CLI ingestion from a single local path, but it becomes unsafe once Gmail, Calendar-derived content, MCP note ingest, and future connected sources are introduced.

Specifically:

1. The same bytes arriving from different paths or source systems will be treated as separate documents.
2. Exact-byte deduplication does not work across sources.
3. Managed copies already exist, but their naming/storage does not clearly represent canonical identity.
4. Connector-originated locators such as `gmail://...` or `mcp://...` are provenance references, not stable canonical identity.
5. If this is left unchanged, Epic 6 will build connectors onto an identity model that multiplies duplicates, retrieval noise, and storage ambiguity.

### Evidence

- Current re-ingest logic: `SELECT id, current_version FROM documents WHERE source_path = %s`
- Current schema: `documents(source_path, file_hash, current_version, status, ingested_at)`
- Current Epic 6 story 6.2 assumes exact-hash skip logic, but does not redefine canonical identity or source/reference modelling
- Current PRD says deduplication is "desirable", but upcoming connected sources make exact-byte dedupe a prerequisite rather than a nice-to-have

## 2. Checklist Findings

### Section 1 - Trigger and Context

- `[x] 1.1` Triggering story identified: issue originates in the Epic 2 document model, especially Story 2.3 provenance/versioning, and becomes blocking before Epic 6 starts
- `[x] 1.2` Core problem defined: document identity is path-centric rather than canonical, cross-source exact-byte dedupe is absent
- `[x] 1.3` Evidence gathered from implementation, deferred work, Epic 6 backlog, and planning artifacts

### Section 2 - Epic Impact Assessment

- `[x] 2.1` Current epic containing the trigger can remain complete as historical implementation, but its assumptions should no longer guide Growth work unchanged
- `[x] 2.2` Epic-level change required: Epic 6 must start with identity hardening, not semantic near-duplicate detection alone
- `[x] 2.3` Future epic impact confirmed: Epic 6 directly affected; Epic 7 indirectly affected because `ingest_document` also creates synthetic source locators
- `[x] 2.4` No existing epic becomes obsolete, but a new enabling story is required and some Epic 6 stories should be revised/resequenced
- `[x] 2.5` Epic order change recommended inside Epic 6: identity foundation must precede jobs queue, Gmail, Calendar, and MCP direct-ingest work

### Section 3 - Artifact Conflict and Impact Analysis

- `[x] 3.1` PRD conflict: "matching identity" is underspecified; exact-byte dedupe is too weakly stated for connected sources
- `[x] 3.2` Architecture conflict: data model and ingestion flow still encode `source_path` as effective identity
- `[N/A] 3.3` UI/UX impact: no dedicated UI artifact exists for this backend platform
- `[x] 3.4` Secondary artifacts affected: docs/setup, README, manual testing, connector documentation, validation scripts, and future migration/backfill notes

### Section 4 - Path Forward Evaluation

- `[x] 4.1` Option 1 Direct Adjustment: **Viable**. Effort: Medium-High. Risk: Medium.
- `[ ] 4.2` Option 2 Potential Rollback: **Not viable**. Rolling back completed Epics 2-5 is unnecessary; targeted redesign is better.
- `[ ] 4.3` Option 3 PRD MVP Review: **Not viable as the main path**. MVP scope need not shrink, but the PRD must be clarified.
- `[x] 4.4` Recommended path: **Hybrid of Option 1 + PRD/Architecture clarification**

### Section 5 - Proposal Components

- `[x] 5.1` Issue summary prepared
- `[x] 5.2` Epic and artifact impacts documented
- `[x] 5.3` Recommended path and rationale documented
- `[x] 5.4` MVP impact and action plan documented
- `[x] 5.5` Handoff plan defined

### Section 6 - Final Review

- `[x] 6.1` Checklist reviewed for completeness
- `[x] 6.2` Proposal reviewed for internal consistency
- `[!] 6.3` User approval still required before updating PRD, architecture, `epics.md`, or `sprint-status.yaml`
- `[!] 6.4` `sprint-status.yaml` should only be updated after approval

## 3. Impact Analysis

### Epic Impact

**Epic 2: Document Knowledge Base**

- Remains implemented, but its current identity model should be treated as a Phase 1 simplification, not the durable design for connected sources.
- The codebase needs a forward migration rather than a rollback.

**Epic 6: Connected Knowledge Sources**

- This epic is directly affected.
- Story 6.2 is too narrow in its current form because it addresses duplicate detection without first fixing what counts as the same document.
- Stories 6.3 through 6.7 depend on a correct identity model:
  - jobs need stable payload identity
  - Gmail needs message/attachment source references distinct from canonical document identity
  - Calendar-derived artifacts and MCP-ingested notes need synthetic source references that do not become canonical identity by accident

**Epic 7: Ambient Messaging Intelligence**

- Indirectly affected.
- Story 6.6 / future note capture should not persist `mcp://...` or Telegram-origin references as the only durable identity concept.

### Artifact Conflicts

**PRD**

- FR5/FR6 refer to provenance and "matching identity" but do not define canonical identity, source reference, or cross-source exact-byte dedupe.
- The immutable-store section currently makes dedupe optional/desirable. For connected sources, exact-byte dedupe must be mandatory.

**Architecture**

- The implemented schema and diagrams encode `source_path` in `documents`, reinforcing the wrong boundary between provenance locator and canonical document identity.
- Managed copy storage is described as durable, but not tied to stable document/version identifiers.

**Backlog**

- Epic 6 starts with OAuth, then near-duplicate detection. That sequence underestimates the foundational identity change now required.

### Technical Impact

- New migration(s) likely required
- Ingestion write path must change
- Managed copy naming/path rules must change
- Provenance/source-reference modelling must change
- Retrieval and `list_documents` output may need small contract clarifications
- Existing test fixtures and operator docs will need updates

## 4. Recommended Approach

### Recommendation

Proceed with a **Moderate-scope backlog correction before Epic 6 implementation begins**:

1. Revise the PRD to define canonical document identity explicitly.
2. Revise the architecture to separate:
   - canonical document identity
   - document version/content hash
   - source references / connector locators
   - managed-copy storage paths
3. Rework Epic 6 so identity hardening happens before any connector or MCP direct-ingest work.

### Why this path

- It preserves momentum: no rollback of completed Epics 1-5.
- It fixes the actual design boundary rather than adding duplicate detection on top of an ambiguous model.
- It reduces future migration pain before Gmail/Calendar data starts arriving.
- It keeps the change contained mainly to PRD, architecture, and Epic 6 backlog rather than forcing a full product replan.

### Effort / Risk / Timeline

- **Effort:** Medium-High
- **Risk if done now:** Medium
- **Risk if deferred until after Epic 6 starts:** High
- **Timeline impact:** expect Epic 6 to absorb one new enabling story plus one revised story; connectors should start only after the identity layer lands

## 5. Detailed Change Proposals

### 5.1 PRD Changes

#### PRD Change A - Immutable Document Store

**Section:** `prd.md` -> `Immutable Document Store`

**OLD**

- New versions of a document can be uploaded and will be treated as a new version record
- Deduplication on ingest is desirable (detect exact or near-duplicate content and flag rather than blindly re-index)
- The original file and its ingestion metadata are preserved permanently

**NEW**

- Canonical document identity is defined independently from any one `source_path`, connector locator, or managed-copy filename.
- Re-ingest from the same logical source creates a new version record when content changes.
- Exact-byte deduplication across all ingestion sources is mandatory: identical bytes received from different paths or connectors must not create duplicate canonical documents or duplicate embeddings.
- Provenance references (local path, Gmail attachment URI, MCP note URI, message ID, etc.) are preserved as source records linked to the canonical document or version they produced.
- Managed originals and Markdown working copies are preserved permanently using stable internal identifiers so filename/path collisions do not redefine identity.

**Rationale**

This makes the PRD explicit about the boundary between identity, provenance, and storage, which is now necessary for connected-source correctness.

#### PRD Change B - Functional Requirements

**Section:** `prd.md` -> `Knowledge Ingestion`

**OLD**

- **FR5:** System records provenance metadata for each ingested document (source path, ingestion timestamp, file hash, version number)
- **FR6:** System creates a new version record when a document with matching identity is re-ingested, preserving all prior versions
- **FR7:** System detects near-duplicate content on ingest and flags it without silently re-indexing _(Growth)_

**NEW**

- **FR5:** System records provenance metadata for each ingested document and source reference, including source locator/external ID, ingestion timestamp, content hash, and version number where applicable.
- **FR6:** System creates a new version record when the same logical source is re-ingested with changed content, preserving all prior versions.
- **FR7:** System performs exact-byte deduplication across all ingestion sources and avoids re-embedding or duplicating canonically identical content.
- **FR8:** System detects semantically near-duplicate content on ingest and flags it without silently re-indexing _(Growth)_.

**Rationale**

The current FR set collapses exact-byte dedupe and semantic similarity into one fuzzy bucket. Epic 6 needs those separated.

### 5.2 Architecture Changes

#### Architecture Change A - Data Model

**Section:** `architecture.md` and `architecture-diagrams.md` -> data model / ingestion flow

**OLD**

- `documents` effectively acts as both canonical document and source locator
- `source_path` is the practical identity key in ingestion code
- managed copies are path/filename-based

**NEW**

- `documents` represents the canonical logical document lineage
- `document_versions` represents versioned content snapshots
- a new provenance/source-reference table records where the content came from:
  - local filesystem path
  - Gmail message/attachment identifiers
  - MCP or Telegram note origin
  - future connector-specific locators
- exact-byte matching uses content hash across all sources before new chunks/embeddings are created
- managed originals and Markdown working copies are stored by stable internal ids such as `document_version_id` or equivalent canonical storage key

**Rationale**

This resolves the ambiguity between "where we saw it" and "what the document is".

#### Architecture Change B - Ingestion Decision Flow

**Section:** `architecture.md` -> ingestion pipeline / provenance / retrieval notes

**OLD**

- compute hash
- write managed copies
- store/update document by `source_path`

**NEW**

- compute content hash before canonical write decisions
- resolve source reference:
  - existing logical source + changed content -> new version on same canonical document
  - new source + exact-byte existing content -> create source reference linked to existing canonical version, skip re-embedding
  - new source + new content -> create new canonical document/version
- write managed originals/Markdown copies under stable internal storage ids
- persist chunks/embeddings only for genuinely new content versions

**Rationale**

This is the missing control point that prevents cross-source duplicate growth.

### 5.3 Backlog Changes

#### Epic 6 Change A - Revise Epic Summary

**Section:** `epics.md` -> `Epic 6: Connected Knowledge Sources`

**OLD**

Platform automatically ingests live content from configured Gmail and Google Calendar accounts, keeping the knowledge base current ... Near-duplicate detection keeps the index clean.

**NEW**

Platform establishes canonical identity and exact-byte deduplication across all ingestion sources, then ingests live content from configured Gmail and Google Calendar accounts without creating duplicate canonical documents or ambiguous managed copies.

**Rationale**

The epic goal should reflect the real enabling dependency.

#### Epic 6 Change B - Replace Story 6.2

**Story:** `6.2`

**OLD**

`Story 6.2: Near-Duplicate Detection on Ingest`

**NEW**

`Story 6.2: Canonical Document Identity & Exact-Byte Deduplication Foundation`

**Proposed acceptance focus**

- canonical identity is no longer derived from `source_path`
- source references are stored separately from canonical documents
- exact-byte matches across different sources do not create duplicate chunks/embeddings
- re-ingest from the same logical source with changed content creates a new version
- managed originals and Markdown copies are keyed by stable internal ids, not raw filenames/stems
- a migration/backfill plan exists for pre-Epic-6 local data

**Rationale**

This is the real blocker. Semantic near-duplicate detection is not the first story anymore.

#### Epic 6 Change C - Add a New Semantic Near-Duplicate Story

**Story:** new story after identity foundation

**OLD**

No separate story exists; semantic warning logic is bundled into current 6.2.

**NEW**

Add a new story such as:

`Story 6.3: Semantic Near-Duplicate Warning Layer`

**Proposed acceptance focus**

- configurable similarity threshold
- warning-only behaviour
- no blocking of legitimate new content
- semantic comparison only after exact-byte dedupe and canonical identity resolution

**Rationale**

This preserves the original Growth intent, but in the right order.

#### Epic 6 Change D - Resequence Remaining Stories

**OLD**

6.1 OAuth  
6.2 Near-duplicate detection  
6.3 Jobs queue  
6.4 Gmail  
6.5 Calendar  
6.6 MCP ingest tool  
6.7 Validation  
6.8 Documentation

**NEW**

Recommended sequence:

6.1 OAuth Authentication Setup  
6.2 Canonical Document Identity & Exact-Byte Deduplication Foundation  
6.3 Jobs Queue & Background Ingestion Worker  
6.4 Gmail Connector  
6.5 Google Calendar Connector  
6.6 `ingest_document` MCP Tool  
6.7 Semantic Near-Duplicate Warning Layer  
6.8 Operator Validation - Connected Sources Live  
6.9 Documentation & Housekeeping

**Rationale**

This keeps renumbering moderate, preserves most story intent, and makes semantic similarity an augmentation rather than the foundation.

## 6. Implementation Handoff

### Scope Classification

**Recommended classification: Moderate**

Reason:

- backlog reorganisation is required
- PRD and architecture both require explicit revision
- code and schema changes will likely be non-trivial
- but the product direction and Epic 6 business goal remain intact

**Escalate to Major if any of the following are true:**

- you want a full lossless migration of already-ingested multi-source datasets across multiple live environments
- Epic 6 implementation has already started on the current identity model
- the architecture revision introduces a wider retrieval-contract rewrite or broad citation-shape change

### Handoff Recipients

- **Product Owner / backlog owner**
  - revise `epics.md`
  - decide final story numbering and sequencing
  - update `sprint-status.yaml` after approval
- **Architect**
  - revise canonical data model, ingestion flow, and diagrams
  - define the exact boundary between canonical document, version, and source reference
- **Developer**
  - implement migration plan
  - update ingestion/storage logic
  - retrofit tests and operator docs

### Success Criteria

- PRD explicitly separates canonical identity from provenance/source locator
- Architecture diagrams and schema describe exact-byte dedupe across sources
- Epic 6 starts with identity foundation before connector ingestion
- No connector story depends on `source_path` as canonical identity
- Managed copies can no longer collide by raw filename or stem alone

## 7. Explicit Recommendation

Do **not** start Epic 6 implementation on the current identity model.

Approve a planning correction that:

1. Revises the PRD
2. Revises the architecture
3. Revises the Epic 6 backlog before development begins

This is the smallest responsible change that addresses the risk while preserving the overall roadmap.

## 8. Next Step After Approval

If approved, the next updates should be made in this order:

1. `prd.md`
2. `architecture.md` and `architecture-diagrams.md`
3. `epics.md`
4. `sprint-status.yaml`

No backlog or status files should be changed until this proposal is approved.
