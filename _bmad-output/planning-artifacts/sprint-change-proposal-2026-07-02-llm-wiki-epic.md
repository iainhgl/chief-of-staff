# Sprint Change Proposal: Insert LLM Wiki as Next Epic

Date: 2026-07-02  
Status: Approved for artifact update  
Workflow: bmad-correct-course  
Trigger: Insert LLM wiki as the next Epic 9 and renumber existing backlog epics.

## 1. Issue Summary

The current roadmap has Epics 1-8 completed and Epics 9-14 in backlog. Two planning documents now define a concrete LLM-maintained wiki layer:

- `docs/llm-wiki-addendum.md`
- `docs/llm-wiki-implementation-plan.md`

The wiki is a derived knowledge layer built from normalized Markdown and linked back to canonical source citations. It is not a replacement for retrieval. It should be implemented next because it builds directly on the completed ingestion, canonical identity, retrieval, jobs, and MCP foundations from Epics 1-8.

## 2. Impact Analysis

Epic impact:

- Add new Epic 9: LLM-Maintained Wiki & Derived Knowledge Layer.
- Renumber existing backlog epics:
  - old Epic 9 -> Epic 10
  - old Epic 10 -> Epic 11
  - old Epic 11 -> Epic 12
  - old Epic 12 -> Epic 13
  - old Epic 13 -> Epic 14
  - old Epic 14 -> Epic 15

Story impact:

- Add a new Epic 9 story sequence covering schema, services, compiler, jobs, read surfaces, change propagation, freshness controls, optional query routing, validation, and documentation.
- Renumber existing backlog story keys in `sprint-status.yaml` and `epics.md` to match the shifted epic numbers.
- No completed story numbers are changed.

Artifact impact:

- `_bmad-output/planning-artifacts/epics.md` gains the new epic and renumbered backlog.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` gains the new epic and renumbered backlog.
- `docs/connectors.md` needs later-epic references updated because web augmentation and proactive delivery move from old Epics 10/11 to new Epics 11/12.
- Active architecture and design notes containing current roadmap diagrams or future-epic references need corresponding numbering updates.

Technical impact:

- No implementation code changes in this proposal.
- The future wiki epic should reuse `data/originals`, `data/markdown`, canonical source/version tables, existing jobs, and MCP tool patterns.
- `retrieve` remains source-first and unchanged during the first wiki slice.

## 3. Recommended Approach

Recommended scope: Moderate backlog reorganization.

Proceed with a direct artifact update rather than regenerating the full epic plan. The LLM wiki docs already provide the architecture and implementation plan. The active need is to insert this derived-knowledge epic before the existing backlog and keep numbering coherent.

The new Epic 9 should start with a smallest useful implementation: storage root, wiki metadata, topic/decision compilation, compile jobs, CLI/MCP read tools, and operator validation. Query routing and wiki-assisted synthesis should remain later stories in the epic so the compiled wiki can prove trustworthy before changing answer behavior.

## 4. Detailed Change Proposals

`_bmad-output/planning-artifacts/epics.md`:

- Insert new Epic 9: LLM-Maintained Wiki & Derived Knowledge Layer.
- Add stories 9.1-9.10.
- Shift old Epics 9-14 and their story numbers to Epics 10-15.

`_bmad-output/implementation-artifacts/sprint-status.yaml`:

- Insert `epic-9` and stories `9-1` through `9-10` as backlog.
- Shift old backlog `epic-9` through `epic-14` to `epic-10` through `epic-15`.

`docs/connectors.md`:

- Update references to later web/proactive epics after renumbering.

Active architecture and design notes:

- Update `_bmad-output/planning-artifacts/architecture.md`.
- Update `_bmad-output/planning-artifacts/architecture-diagrams.md`.
- Update `_bmad-output/planning-artifacts/retrieval-contract-and-pluggable-retriever-design-2026-06-10.md`.

## 5. Implementation Handoff

Scope classification: Moderate.

Handoff:

- Planning/PO action: accept the new epic and renumbered backlog.
- Developer action after this proposal: create story `9-1-wiki-schema-storage-and-page-model` through the normal `bmad-create-story` workflow.

Success criteria:

- Completed epics 1-8 remain unchanged.
- New wiki epic is the next backlog epic.
- Existing backlog epics retain their content and order under new numbers.
- Sprint status and epic plan agree on story keys.
