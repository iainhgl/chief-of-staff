# LLM Wiki Addendum

## Purpose

This addendum proposes an LLM-maintained wiki as a new derived knowledge layer for the CoS platform. It is intended to sit alongside the current retrieval-first Q&A system, not replace it.

The goal is to give the CoS two complementary modes:

- direct, source-grounded retrieval for precise questions and citations
- a maintained, browsable wiki for synthesis, orientation, and cross-document memory

## Decision Summary

The recommended design is:

1. Keep raw source artifacts as the system-of-record truth layer.
2. Keep normalized Markdown as the canonical text layer for indexing and LLM processing.
3. Add a compiled wiki layer built from the Markdown corpus and linked back to source citations.
4. Route queries between source-first and wiki-first paths based on the task, while preserving source-grounded citations in both modes.

This matches the original CoS platform direction in `initial_docs/shared_cos_platform_architecture.md`: preserve originals, maintain editable working copies, retrieve before generation, and keep provenance intact.

## What The Research Suggests

The recent "LLM wiki" pattern is best understood as a compilation pipeline for knowledge.

- Andrej Karpathy's `llm-wiki` gist frames the wiki as a persistent artifact that is rebuilt and enriched from raw sources over time rather than generated from scratch on every question.
- Urvil Joshi's write-up makes the three-layer pattern explicit: immutable raw sources, LLM-owned wiki pages, and a schema file that defines how the agent ingests, updates, and queries the wiki.
- Paul Iusztin's article shows a useful operating variant: a broader personal corpus can power smaller topic-scoped research workspaces when you want deeper synthesis without searching the whole world every time.
- Anthropic's work on context engineering supports the same direction in practice: agents become more effective when important context is externalized into durable, structured artifacts rather than reconstructed ad hoc for every run.

The key takeaway is that this is not "better RAG." It is a different layer:

- RAG answers questions from indexed source fragments.
- An LLM wiki maintains a durable map of entities, themes, links, and synthesized context across those fragments.

## Fit With The Current CoS

This repo already has most of the substrate the pattern needs:

- raw storage roots in `config.py` via `storage.originals_dir` and `storage.markdown_dir`
- canonical identity and provenance in `content_blobs`, `sources`, `source_versions`, and `document_versions`
- chunking, embeddings, and hybrid retrieval
- service boundaries in `src/cos/services/`
- an MCP surface in `src/cos/mcp_server/tools.py`
- a jobs substrate and worker that can schedule background compilation

That means the wiki should be added as a new derived layer, not introduced as a second competing knowledge base.

## What Should Be The Base Store?

The best answer is a hybrid one, with different roles for each layer.

| Layer | Recommended role | Why |
|---|---|---|
| Raw originals | Source-of-truth | Highest fidelity, strongest provenance, reprocessable when extraction improves |
| Normalized Markdown working copies | Operational base for compilation | Human-readable, diffable, consistent across formats, efficient for LLM processing |
| Compiled wiki pages | Derived synthesis layer | Persistent summaries, entity pages, links, and curated memory |

### Recommendation

Use the Markdown working copies as the direct compiler input for the wiki, while treating the raw originals as the underlying truth that citations and audits can always fall back to.

### Why Not Use Raw Files Directly As The Wiki Base?

Pros:

- maximum fidelity
- preserves layout-dependent nuance when needed
- avoids trusting lossy extraction too early

Cons:

- heterogeneous formats are expensive and awkward to process repeatedly
- poor diffability and poor human editability
- weak fit for incremental page updates and link maintenance

### Why Not Treat Markdown As The Only Truth?

Pros:

- uniform input shape for chunking, embedding, and page compilation
- easy to inspect and fix manually
- naturally compatible with file-backed wiki pages

Cons:

- extraction loss can become invisible if the original is ignored
- tables, images, and rich formatting may be flattened
- bad normalization can quietly propagate into the wiki

### Recommended Operating Rule

- Truth lives in originals.
- Day-to-day LLM processing runs on Markdown.
- The wiki is always rebuildable from the Markdown plus provenance metadata.

## Proposed Architecture Addition

Add a new compiled knowledge layer with both file-backed and database-backed parts.

### File-backed artifacts

Recommended new storage root:

- `data/wiki/`

Suggested page families:

- `data/wiki/index.md`
- `data/wiki/log.md`
- `data/wiki/people/`
- `data/wiki/projects/`
- `data/wiki/decisions/`
- `data/wiki/risks/`
- `data/wiki/topics/`
- `data/wiki/meetings/`
- `data/wiki/briefings/`

This keeps the resulting knowledge human-readable and easy to browse in Obsidian or any Markdown viewer.

### Database-backed metadata

Recommended new tables:

- `wiki_pages`
- `wiki_page_versions`
- `wiki_page_citations`
- `wiki_page_links`

These should track:

- logical page identity and page type
- current and historical rendered Markdown
- compilation timestamp
- source document/version lineage
- cross-page relationships
- compiler metadata such as model/provider used

This lets the wiki stay inspectable as files while still supporting governance, freshness checks, and query routing inside the app.

## How The Layer Should Behave

### Ingest

When new content is ingested:

1. Store original bytes and normalized Markdown as usual.
2. Refresh chunks and embeddings as usual.
3. Enqueue wiki compilation for affected entities and topics.
4. Update or create wiki pages with citations back to `document_versions` and source aliases.

### Query

The platform should support two read paths:

- source-first for direct questions, fresh facts, exact citations, and high-stakes answers
- wiki-first for briefings, comparisons, "bring me up to speed", decision context, and ongoing research topics

Even on the wiki-first path, the final answer should still cite underlying source material, not only wiki pages.

### Maintenance

The system should periodically lint the wiki for:

- stale pages after source changes
- orphan pages with no inbound or outbound links
- duplicated entities
- claims with missing citations
- contradiction candidates across related pages

## Why This Is Valuable For A CoS

This layer is especially useful for a CoS because the hard problems are rarely single-document lookups. They are usually:

- assembling context across many notes and messages
- tracking people, projects, risks, and decisions over time
- maintaining continuity between meetings
- surfacing contradictions and drift
- keeping a practical "working memory" that gets denser as the corpus grows

That is where a compiled wiki adds more value than pure retrieval.

## Risks And Controls

### Risk: synthesized errors become durable

Control:

- require every wiki page to retain structured source citations
- make pages rebuildable
- show freshness and compiled-at metadata
- add lint/audit jobs

### Risk: wiki pages drift from source changes

Control:

- compile on ingest and re-ingest
- record which document versions contributed to each page version
- mark dependent pages stale when upstream versions change

### Risk: the wiki becomes a second unsupervised truth store

Control:

- keep originals and Markdown as the authoritative substrate
- keep the wiki explicitly labeled as derived
- favor source-first routing for exact and high-stakes tasks

### Risk: early scope explodes

Control:

- start with a small page taxonomy
- begin with read-only wiki compilation
- add query routing before adding any write-back or autonomous maintenance actions

## Recommended Initial Scope

The smallest useful version should support:

- topic pages
- people pages
- project pages
- decision pages
- page-level citations back to source material
- a simple page index
- a compile-on-ingest job for changed source documents

It should not initially attempt:

- automatic editing of source documents
- autonomous approval loops
- generalized agent swarms
- replacing the existing `retrieve` path

## Open Design Choices

The main implementation choice is not whether to build the wiki, but where to anchor it.

Recommended answer:

- anchor truth in raw originals
- anchor compilation in normalized Markdown
- anchor usability in file-backed wiki pages
- anchor governance in Postgres metadata and citations

## Suggested Next Use In BMAD

If you later want to formalize this through BMAD, treat this document as an architecture-side input and pair it with a story-planning artifact. The clean follow-on would be:

1. architecture update or architecture addendum review
2. epics and stories for the wiki layer
3. readiness check before implementation

## References

- [Karpathy `llm-wiki` gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Urvil Joshi: Andrej Karpathy's LLM Wiki](https://medium.com/@urvvil08/andrej-karpathys-llm-wiki-create-your-own-knowledge-base-8779014accd5)
- [Paul Iusztin: Karpathy Named It. I Built One on My Notes.](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm)
- [Anthropic: Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
