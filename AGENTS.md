# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What This Repository Is

This is a design and planning repository for a reusable **Chief of Staff (CoS) AI platform** — not a code repository yet. The documents here define the architecture, data model, phased delivery plan, and role-specific configuration approach. Implementation has not started.

## Documents

| File | Purpose |
|------|---------|
| `shared_cos_platform_architecture.md` | Primary architecture spec: design principles, platform blocks, data model, phased delivery plan, and tech choices |
| `shared_cos_platform_diagrams_and_handoff.md` | Mermaid diagrams for each phase plus dynamic flows (ingestion, read, scheduled); includes a handoff prompt for generating implementation stories |
| `CoS - CHRO.md` | Concrete example: AI CoS for a CHRO — use this as the reference role pack when building Phase 1 |

## Architecture Summary

The platform has a **stable generic core** and **swappable role packs**. The core handles ingestion, storage, retrieval, and reasoning. The role pack defines who the CoS is for.

### Core Platform Blocks
1. **Source Connectors** — email, calendar, docs, chat, web, business systems
2. **Ingestion Pipeline** — extract → normalize to Markdown → chunk → embed → store
3. **Canonical Store** — Postgres (metadata/workflow), pgvector (embeddings), object storage (originals), Markdown working copies
4. **Retrieval Layer** — keyword + semantic search with recency/source ranking and citation-ready results
5. **Reasoning Layer** — synthesis, drafting, critique, comparison via LLM
6. **Workflow Engine** — reusable actions: summarize, brief, draft, compare, prioritize, prep meeting
7. **Governance Layer** — provenance, confidence, permissions, audit trail, version history
8. **Model Interface** — MCP or REST API to keep model choice interchangeable

### Role Pack Components
Each role pack contains: role goals, knowledge taxonomy, tone/style rules, stakeholder map, workflows, retrieval priorities, decision heuristics.

### Phased Delivery
- **Phase 1** — one ingestion pipeline, one canonical store, one retrieval API, one role pack (CHRO), read-only chat
- **Phase 2** — role pack abstraction (data-driven, second role without changing core code)
- **Phase 3** — external connectors (email, calendar, docs, web, sync jobs)
- **Phase 4** — governance hardening (approvals, audit, confidence scoring, write-back)
- **Phase 5** — advanced reasoning (multi-model, proactive briefings) — only if needed

### Recommended Tech Stack
- **Postgres** — metadata and workflow state
- **pgvector** — embeddings
- **Object storage** — originals and exports
- **Markdown** — editable working format for all source copies
- **Tika or similar** — heterogeneous file ingestion
- **MCP or REST API** — model portability layer

## Key Design Constraints

- **One role per instance** is the default. Multi-tenant comes after Phase 2–3 with strict namespace isolation.
- **Source truth is never mixed with generated output.** Originals and Markdown working copies are preserved separately from LLM-generated content.
- **Retrieval before generation.** Every answer must trace back to source material with citations.
- **Role behavior lives in configuration (role pack), not code.**
- Do not introduce multi-model arbitration, recursive LLMs, or advanced agent systems until Phase 1–4 is working and useful.

## Starting Implementation

To generate a Phase 1 implementation plan with epics and stories, use the handoff prompt in `shared_cos_platform_diagrams_and_handoff.md` (Section 4). The Phase 1 story skeleton (Section 5) gives the epic breakdown: source ingestion, canonical storage, retrieval API, role pack v1, read-only chat workflow, daily calendar check.

## Git Workflow

All implementation work lives in `cos/` which is a git repository (`cos/.git`).

**Branch strategy (from Story 1.4 onwards):**

- Create a feature branch per story before starting implementation: `git checkout -b story/1-4-mcp-server-foundation`
- Name format: `story/<story-key>` (matching the story slug in sprint-status.yaml)
- Commit work to the feature branch. Do not commit story implementation directly to `main`.
- When the story is `review` status and code review patches are applied, push the branch and open a PR.
- **Wait for the user to approve and merge the PR on GitHub before proceeding to the next story.**
- After merge, pull `main` locally before starting the next branch.

**Do not push or merge on the user's behalf** — the user reviews and merges PRs themselves via the GitHub UI.
