# LLM Wiki Implementation Plan

## Purpose

This document turns the LLM wiki idea into a practical implementation plan for the current CoS codebase.

It is intentionally written as a standalone planning artifact rather than a formal BMAD story file. The BMAD architecture and epic workflows in this repo are interactive and checkpoint-driven; this plan is meant to become a clean input to those workflows later rather than a partial in-progress workflow artifact.

## Delivery Strategy

Build the wiki as a thin, governed layer on top of the existing ingestion, storage, retrieval, and MCP foundations.

Do not:

- replace `retrieve`
- create a second canonical truth model
- bypass current provenance and citation patterns

Do:

- reuse the current `data/originals`, `data/markdown`, Postgres, pgvector, and jobs substrate
- keep wiki pages rebuildable
- make the initial slice useful before adding sophisticated routing or maintenance

## Current Codebase Seams To Reuse

The plan should build on these existing areas:

- `src/cos/config.py`
  - current storage roots already define originals and Markdown
- `src/cos/store/migrations/004_canonical_identity.sql`
  - canonical content identity and provenance already exist
- `src/cos/services/ingestion.py`
  - current ingest surface already normalizes note and file inputs
- `src/cos/services/jobs.py`
  - existing jobs queue and worker provide the right substrate for background compilation
- `src/cos/services/retrieval.py`
  - existing source-grounded answer path should remain the baseline
- `src/cos/mcp_server/tools.py`
  - existing MCP surface is the natural place to expose wiki read tools later

## Recommended Target Shape

### Filesystem

Add a new writable storage root:

- `data/wiki/`

This should hold the current rendered Markdown pages for human browsing and possible Obsidian use.

### Database

Add wiki metadata tables to Postgres:

- `wiki_pages`
- `wiki_page_versions`
- `wiki_page_citations`
- `wiki_page_links`

This combination gives you:

- readable pages on disk
- lineage and versioning in the database
- rebuildability from the canonical corpus

### Application surface

Add a new package area:

```text
src/cos/wiki/
  __init__.py
  compiler.py
  page_types.py
  renderer.py
  citations.py
  links.py
  lint.py
```

And new services:

```text
src/cos/services/wiki.py
src/cos/services/wiki_compile.py
```

## Proposed Delivery Increments

## Increment 1: Storage And Schema Foundation

### Goal

Create the data structures that let the platform persist current wiki pages without disturbing the existing retrieval model.

### Work

- extend `CosConfig` with a `storage.wiki_dir` path, defaulting to `/data/wiki`
- create a new migration for wiki tables and indexes
- define file layout conventions for page families and slugs
- define a minimal page taxonomy:
  - topic
  - person
  - project
  - decision
- decide the citation granularity for v1
  - recommended: page section -> `document_version_id` plus chunk anchors when available

### Acceptance Criteria

- the app starts with the new schema in place
- `data/wiki/` is created on startup or first use
- wiki page metadata can be inserted, updated, and listed without affecting existing ingest or retrieval flows

## Increment 2: Compile Pipeline From Markdown Corpus

### Goal

Compile wiki pages from the normalized Markdown corpus, not from raw binaries and not from retrieval snippets alone.

### Work

- add a compiler service that reads document Markdown plus provenance metadata
- create compile routines for the initial page taxonomy
- generate:
  - page title
  - body Markdown
  - page links
  - cited source references
  - compiled timestamp
- store the rendered page in `data/wiki/`
- write page metadata, citations, and link relationships to Postgres
- ensure the compiler is idempotent for unchanged source inputs

### Implementation Notes

- use existing `document_versions` and `source_versions` as the authoritative upstream lineage
- treat Markdown working copies as the direct input to compilation
- keep the rendered wiki page replaceable from source at any time

### Acceptance Criteria

- a known set of Markdown inputs produces deterministic page files and citation records
- recompiling unchanged inputs does not create duplicate page versions
- changed source content creates a new wiki page version or marks the page stale before refresh

## Increment 3: Background Jobs And Change Propagation

### Goal

Make the wiki update automatically as the corpus changes.

### Work

- extend the existing jobs queue to support a new job type such as `wiki_compile`
- enqueue compilation work after successful ingest outcomes
- support both:
  - targeted recompile for affected pages
  - full rebuild for operator recovery
- add CLI commands such as:
  - `cos wiki compile`
  - `cos wiki rebuild`
  - `cos wiki status`

### Implementation Notes

- reuse the existing worker pattern rather than introducing a second task runner
- start with compile-after-ingest and operator-triggered rebuilds
- do not add continuous autonomous maintenance in the first slice

### Acceptance Criteria

- ingesting or updating a source can enqueue wiki compilation work
- the worker can process `wiki_compile` jobs independently of `ingest` jobs
- operators can rebuild the wiki from the current corpus without manual database surgery

## Increment 4: Read Surface And MCP Exposure

### Goal

Expose the wiki as a first-class read surface without destabilizing the existing retrieval tool.

### Work

- add a `WikiService` for listing and loading pages
- add MCP tools such as:
  - `list_wiki_pages`
  - `get_wiki_page`
  - optionally `get_wiki_index`
- include compiled-at, page type, and source citation metadata in responses
- add a CLI surface for local inspection

### Recommended Product Behavior

Keep `retrieve` unchanged at first. Do not fold the wiki into the main retrieval tool until the wiki has proven trustworthy.

This staged approach makes it easier to compare:

- source-first answers from `retrieve`
- wiki-backed syntheses from the new read surface

### Acceptance Criteria

- an operator can browse wiki pages through CLI and MCP
- every wiki page response includes underlying source citations
- existing `retrieve`, `list_documents`, and `get_role_context` behavior is unchanged

## Increment 5: Query Routing And Wiki-Assisted Synthesis

### Goal

Use the wiki to improve synthesis-heavy tasks while preserving the source-first path for direct factual queries.

### Work

- add a routing layer that classifies requests into:
  - source-first
  - wiki-first
  - hybrid
- keep routing heuristics simple at first:
  - direct fact lookup -> source-first
  - briefing, compare, orient, summarize across time -> wiki-first or hybrid
- allow the wiki to act as a context condenser for synthesis prompts
- require final outputs to retain source citations, not wiki-only citations

### Implementation Notes

- this likely belongs near `src/cos/services/retrieval.py` but should remain a distinct layer rather than hiding wiki behavior deep inside hybrid search
- if uncertainty is high, default back to source-first

### Acceptance Criteria

- synthesis-heavy prompts can use the wiki as condensed context
- direct questions still behave like ordinary retrieval by default
- the user can tell when an answer used wiki assistance

## Increment 6: Trust, Linting, And Freshness Controls

### Goal

Prevent the wiki from becoming an ungoverned second truth store.

### Work

- add lint jobs for:
  - orphan pages
  - duplicate entity pages
  - pages with missing citations
  - stale pages after upstream changes
  - contradiction candidates
- add freshness metadata to pages
- add operator-visible repair commands
- optionally add a low-friction manual review queue for sensitive pages such as decisions or people summaries

### Acceptance Criteria

- stale or weakly grounded pages are detectable
- operators can inspect and repair wiki health without hand-editing database rows
- sensitive pages can be spot-checked against raw sources

## Optional Later Increment: Topic-Scoped Research Workspaces

This is the Paul Iusztin variant and should be treated as optional after the persistent wiki works.

### Goal

Create temporary or semi-persistent topic workspaces for deep research on a bounded question, built from a selected subset of the broader corpus.

### Work

- allow a topic-scoped subset to compile into `data/wiki/workspaces/<slug>/`
- support focused page sets and distilled briefings
- optionally promote reviewed workspace pages back into the main wiki

### Why Later

This is valuable, but it adds lifecycle complexity. The persistent cross-topic wiki should come first.

## Suggested Story Grouping For Later BMAD Use

If you want to convert this into BMAD stories later, a clean grouping would be:

1. Wiki schema and storage roots
2. Markdown-to-page compiler
3. Compile jobs and rebuild commands
4. Wiki CLI and MCP read tools
5. Query routing and synthesis integration
6. Linting, freshness, and governance
7. Optional topic-scoped research workspaces

## Testing Strategy

Recommended tests:

- migration tests for wiki tables and indexes
- compiler tests from fixture Markdown inputs to rendered page outputs
- provenance tests verifying every wiki page maps back to source lineage
- worker tests for `wiki_compile` jobs
- MCP tests for wiki read tools
- regression tests proving `retrieve` behavior stays stable while the wiki is introduced

## Recommended First Slice

If you want the smallest useful implementation, build only this first:

1. `data/wiki/` storage root
2. `wiki_pages` plus `wiki_page_citations`
3. topic and decision pages only
4. compile-on-ingest for changed Markdown documents
5. `get_wiki_page` and `list_wiki_pages`

That gives you a tangible wiki without overcommitting to routing, lints, or advanced page families too early.

## Suggested Follow-on Prompt

When you are ready to formalize this in BMAD, a good next prompt would be:

> Use `docs/llm-wiki-addendum.md` and `docs/llm-wiki-implementation-plan.md` as additional inputs. Propose an architecture update and a phased epic/story breakdown for adding an LLM-maintained wiki layer to the CoS platform. Keep raw originals as truth, Markdown as compiler input, the wiki as derived knowledge, and preserve source-grounded citations throughout.
