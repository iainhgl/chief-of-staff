# Sprint Change Proposal - Post-Epic-6 Backlog Resequencing

**Project:** CoS  
**Date:** 2026-05-15  
**Prepared by:** Codex via `bmad-correct-course`  
**Mode used:** Batch  
**Approval status:** Approved and applied to planning artifacts

## 1. Issue Summary

The original Growth backlog after Epic 6 bundled interactive Telegram access, web augmentation, and proactive scheduling into one Epic 7. Research completed on 2026-05-15 showed that this sequence would amplify retrieval-trust risk too early and would mix reactive, proactive, and platform-foundation work into a single backlog slice.

## 2. Approved Change

Epics 1 through 6 remain unchanged as implemented history.

Epic 7 onward is resequenced to:

1. Epic 7 — Retrieval Trust, Evaluation & Observability
2. Epic 8 — Interactive Telegram Messaging
3. Epic 9 — Structured LLM Boundary & Provider Portability
4. Epic 10 — Web Augmentation & External Context
5. Epic 11 — Proactive Briefings & Meeting Prep
6. Epic 12 — Agent-Safe Task Runtime
7. Epic 13 — Internal Model Routing & Local Endpoints
8. Epic 14 — Advanced Retrieval Modes & Orchestration Pilots

## 3. Artifact Updates Applied

- `prd.md`
- `architecture.md`
- `architecture-diagrams.md`
- `epics.md`
- `sprint-status.yaml`

The update preserves BMAD traceability by keeping implemented history intact, remapping Growth FR coverage to the new epics, and aligning the architecture diagrams with the approved sequencing.

## 4. Scope Classification

**Major** in BMAD terms.

Reason:
- future epics were renumbered and split
- new enabling epics were inserted before former Epic 7 capabilities
- multiple planning artifacts required coordinated updates

## 5. Exact Next BMAD Step

Run **`bmad-sprint-planning`** against the updated `epics.md` and `sprint-status.yaml`.

Reason:
- epic order changed materially
- the next implementation candidate is no longer derivable from the prior sprint plan
- sprint planning should be regenerated before `bmad-create-story` is used for the next backlog item
