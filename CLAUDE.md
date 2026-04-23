# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

This is the **Chief of Staff (CoS) AI platform** — a reusable AI platform with a stable generic core and swappable role packs. The repository contains both planning artifacts and implementation code.

| Layer | Location |
|-------|----------|
| Planning artifacts (PRD, architecture, epics, stories) | `_bmad-output/` |
| Original design documents | `initial_docs/` |
| Implementation code | `src/cos/` |
| Tests | `tests/` |

## Planning Artifacts

| File | Purpose |
|------|---------|
| `_bmad-output/planning-artifacts/architecture.md` | Architecture decisions, patterns, and project structure — the primary reference for all implementation |
| `_bmad-output/planning-artifacts/epics.md` | All epics and stories with acceptance criteria |
| `_bmad-output/planning-artifacts/prd.md` | Product requirements document |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | Current story status tracking |
| `initial_docs/shared_cos_platform_architecture.md` | Original architecture spec (source of truth for design intent) |
| `initial_docs/CoS - CHRO.md` | Reference role pack example — use when building Epic 4 |

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

## Git Workflow

This is a git repository. Planning artifacts (`_bmad-output/`, `initial_docs/`) and implementation code (`src/`, `tests/`) are both tracked here.

**Branch strategy (from Story 1.4 onwards):**

- Name format: `story/<story-key>` (matching the story slug in `_bmad-output/implementation-artifacts/sprint-status.yaml`)
- Commit work to the feature branch. Do not commit story implementation directly to `main`.
- When the story is `review` status and code review patches are applied, push the branch and open a PR.
- **Wait for the user to approve and merge the PR on GitHub before proceeding to the next story.**

**Before creating a feature branch, you MUST run these exact commands in order and confirm each succeeds:**

```bash
git fetch origin
git checkout main
git pull origin main
git log --oneline -3   # confirm main tip matches the merged PR commit
git checkout -b story/<story-key>
```

Never branch from an existing story branch. Always branch from `main` after pulling. If `git pull` shows "Already up to date" but the last merged PR is not visible in `git log`, stop and tell the user.

**Do not push or merge on the user's behalf** — the user reviews and merges PRs themselves via the GitHub UI.
