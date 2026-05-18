# CoS Retrieval Improvement Roadmap

Date: 2026-05-15  
Author: Codex technical research pass  
Status: Recommendation draft for platform direction

## Executive Summary

The current CoS platform is a sound first-generation retrieval-augmented generation system. It ingests source material, preserves provenance, chunks normalized text, generates embeddings, runs hybrid sparse and dense retrieval, and asks the LLM to synthesize from cited evidence. In other words, it is not a naive vector-only system, but it is still fundamentally a flat chunk-retrieval architecture.

That architecture is a good baseline for direct factual lookup, citation-heavy answers, and operational simplicity. It is not the end state if the goal is to return consistently high-quality, fact-grounded answers across a wider range of CoS-style questions such as weekly briefings, cross-source synthesis, timeline reconstruction, stakeholder analysis, and multi-hop reasoning.

The strongest conclusion from current research is not that "RAG is obsolete" or that "vector search is dead." It is that retrieval structure should match query structure:

- Direct factual lookup still favors strong hybrid retrieval.
- Corpus-wide synthesis benefits from hierarchical summaries or global search.
- Multi-hop and relationship-centric questions may benefit from graph retrieval.
- Small, bounded corpora can sometimes skip chunking entirely and use full-context prompting.

The recommended direction for CoS is therefore a staged hybrid system:

1. Keep the current hybrid RAG baseline.
2. Improve it substantially before replacing it.
3. Add a no-chunking / long-context path for small candidate sets.
4. Add hierarchical summarization for executive briefing queries.
5. Add graph-based retrieval only for the query classes where it clearly beats the simpler methods.
6. Route queries to the cheapest method that meets grounded-answer quality targets.

## Current State of the CoS Platform

Today’s implementation does the following:

- Extracts source content and stores originals plus Markdown working copies.
- Chunks text using token windows with overlap.
- Embeds chunks and stores vectors in Postgres with `pgvector`.
- Builds a lexical full-text index over chunk content.
- Retrieves with both keyword and vector search, then merges results with reciprocal-rank fusion.
- Applies role-pack retrieval weighting and evidence pruning.
- Narrows single-source factual queries to a single lineage to reduce fact blending.
- Sends retrieved chunk text to the LLM for synthesis, returning citations.

Key local implementation references:

- `src/cos/ingestion/pipeline.py`
- `src/cos/ingestion/chunker.py`
- `src/cos/retrieval/search.py`
- `src/cos/retrieval/citations.py`
- `src/cos/services/retrieval.py`

This means the platform is best described as:

> A provenance-aware, hybrid sparse+dense, chunk-level RAG system with role-aware ranking and limited query-type handling.

That is a credible architecture. It should be treated as the baseline to beat, not as a mistake to be discarded.

## Problem Statement

The objective is not merely to improve retrieval recall. The platform should return answers that are:

- Factually grounded in source material
- Consistent across repeated runs
- Resistant to hallucination and cross-document fact blending
- Useful for both factual lookup and executive synthesis
- Cost-effective enough to run routinely
- Operationally explainable to a human operator

In practice, this means the platform must handle several distinct question types well:

- Direct fact lookup
- Exact-match lookup for identifiers, names, dates, and phrases
- Single-document interpretation
- Multi-document synthesis
- Timeline reconstruction
- Stakeholder and relationship questions
- Periodic briefing questions such as "catch me up on the last two weeks"

No single retrieval design is best at all of these.

## Why Flat Chunk RAG Becomes Fragile

Recent work surfaces a repeatable set of failure modes in flat chunk retrieval:

### 1. Context is lost during chunking

When chunks are separated from their document context, key qualifiers can disappear. A sentence may contain the right number or claim but lose the associated actor, date, project, or decision status. Anthropic’s Contextual Retrieval article frames this as a central weakness of traditional RAG.

### 2. Global questions are not really retrieval questions

Questions like "What are the main themes in the corpus?" or "Catch me up on the last two weeks of updates" are often query-focused summarization tasks, not simple nearest-neighbor retrieval tasks. Microsoft’s GraphRAG work is explicitly motivated by this gap.

### 3. Multi-hop reasoning is hard when evidence is flattened

If the answer depends on traversing relationships across entities, documents, or events, independent chunk ranking may surface locally relevant fragments without surfacing the connective structure between them.

### 4. Long context is helpful, but not a full substitute

A tempting alternative is to skip retrieval and place more material directly in the prompt. That sometimes works, especially on smaller corpora. But long-context models still suffer from position effects and can miss relevant evidence in the middle of large prompts.

## Evaluation Criteria

Before choosing an architecture, CoS should define success along these axes:

- Answer factuality: Are claims supported by the cited evidence?
- Citation precision: Do citations actually justify the answer text?
- Retrieval recall: Was the right evidence surfaced at all?
- Cross-source discipline: Are sources combined only when the query calls for it?
- Temporal correctness: Are dates, chronology, and version lineage preserved?
- Latency: Can the method support interactive use?
- Cost: Indexing cost plus query-time cost
- Operability: Can an operator understand why the system answered as it did?

## Option Space

## Option A: Stay with Chunked Hybrid RAG, but Make It Better

This path keeps the current architecture but improves the weak spots.

Likely upgrades:

- Contextual chunk enrichment before embedding and BM25 indexing
- Parent-document and neighbor-chunk expansion
- Better metadata-aware filtering
- Reranking after initial retrieval
- Document-first, chunk-second retrieval
- Better chunk semantics for email threads, calendar events, and notes

Advantages:

- Lowest implementation risk
- Preserves current provenance model
- Best fit for factual lookup and citation-heavy workflows
- Easy to benchmark incrementally

Disadvantages:

- Still weak on corpus-wide summarization unless extra summary layers are added
- Still fundamentally limited for relationship-centric and multi-hop queries

Assessment for CoS:

This should remain the baseline path and should be improved before any large architectural pivot.

## Option B: Do Not Chunk, Use Full-Context Prompting Where Feasible

This option treats chunking as optional rather than mandatory. For small bounded corpora, or after retrieving a small number of candidate documents, the system passes full documents or large contiguous sections directly to the model.

When this is attractive:

- Small knowledge bases
- Narrow candidate sets
- High-value questions where context integrity matters more than latency
- Questions about a single meeting, thread, memo, or tightly bounded packet

Advantages:

- Avoids chunk-boundary context loss
- Preserves narrative flow, chronology, and local nuance
- Simpler reasoning for the model on single-document tasks

Disadvantages:

- Does not scale cleanly to larger corpora
- Susceptible to long-context degradation and "lost in the middle"
- Query cost and latency can rise sharply
- Harder to compare and rank evidence pieces

Assessment for CoS:

This should not replace retrieval, but it should become a supported execution mode. The most useful form is likely:

- retrieve candidate documents or threads
- pass the most relevant whole documents or expanded spans to the model
- reserve this for bounded, high-context tasks

## Option C: Hierarchical Retrieval and Summary Layers

This path builds intermediate abstractions above raw chunks:

- document summaries
- thread summaries
- daily summaries
- weekly summaries
- role-relevant topic summaries

RAPTOR is the research archetype here: retrieve from a tree of summaries and leaves rather than only from leaf chunks.

Advantages:

- Strong fit for executive briefings and synthesis questions
- Reduces token load for recurring overview tasks
- Makes high-level questions answerable without brute-force scanning of raw chunks

Disadvantages:

- Requires summary generation and refresh strategy
- Summary drift must be managed and audited
- Introduces a second evidence layer that itself must remain grounded

Assessment for CoS:

This is probably the highest-value next architectural addition after baseline retrieval improvements. A Chief of Staff system is asked synthesis questions constantly.

## Option D: Graph-Based Retrieval

This path represents the corpus as entities, relationships, claims, communities, and reports. Microsoft GraphRAG is the clearest current reference implementation in this family, and HippoRAG shows a related graph-memory direction.

Typical strengths:

- relationship-heavy questions
- multi-hop questions
- entity-centric exploration
- global sensemaking across many documents

Typical costs:

- higher indexing complexity
- meaningful prompt-tuning burden
- higher LLM indexing cost for standard GraphRAG
- graph noise if extraction quality is uneven

Assessment for CoS:

Graph retrieval should be treated as a specialized capability, not the default first-line retriever. It becomes compelling if CoS must routinely answer questions such as:

- "Which stakeholders are repeatedly connected to this risk?"
- "What themes link these incidents across email, calendar, and notes?"
- "What unresolved dependencies connect these projects?"

If those questions are common, graph retrieval may earn its place. If not, the complexity may outweigh the gain.

## Option E: Late-Interaction Retrieval and Stronger Ranking

This path keeps the general RAG architecture but improves the retriever itself. ColBERT-style late interaction is the canonical example: documents are represented with richer token-level signal instead of a single vector per chunk.

Advantages:

- Often materially better than one-vector-per-chunk dense retrieval
- Good fit for subtle lexical-semantic matching
- Less radical than adopting a graph pipeline

Disadvantages:

- More infrastructure and serving complexity
- Larger index and slower ranking than simple vector similarity

Assessment for CoS:

This is worth considering if the current retriever becomes the bottleneck after baseline fixes. It is likely a better medium-complexity upgrade than jumping straight to full GraphRAG.

## Option F: Routed Hybrid System

This path accepts that different queries deserve different retrieval strategies and introduces a query router.

Illustrative routing:

- direct fact question -> hybrid chunk retrieval
- exact phrase or identifier query -> lexical-heavy retrieval
- single bounded artifact question -> full-document context mode
- weekly briefing query -> hierarchical summary retrieval
- relationship or dependency query -> graph retrieval

Assessment for CoS:

This is the likely end state. It aligns best with the diversity of CoS tasks and lets the platform stay simple where simplicity is enough.

## Recommendation

The recommended target architecture is a routed hybrid retrieval system built in stages.

The key strategic decision is:

> Do not replace the current hybrid RAG baseline wholesale. Extend it, benchmark it, and add specialized retrieval paths only where they clearly outperform the baseline on defined CoS query classes.

## Roadmap

## Phase 0: Establish the Measurement Harness

Before changing architecture, create a retrieval evaluation set covering at least:

- exact factual questions
- temporal questions
- single-document interpretation
- cross-document synthesis
- weekly briefing questions
- stakeholder/relationship questions

For each benchmark item, store:

- query
- gold answer or gold evidence
- expected source set
- whether multi-source synthesis is allowed
- grading rubric for factuality and citation quality

Deliverables:

- benchmark corpus
- repeatable eval runner
- retrieval trace logging
- answer grading rubric

This phase is mandatory. Without it, the team will optimize for novelty instead of answer quality.

## Phase 1: Strengthen the Existing Baseline

Priority improvements:

- Add contextual retrieval style chunk enrichment before embedding and lexical indexing.
- Add post-retrieval reranking.
- Add document-level candidate retrieval before chunk-level selection.
- Add adjacent-chunk or section expansion for bounded context recovery.
- Add stronger temporal and source metadata filters.
- Improve query classification beyond the current multi-source heuristic.

Expected outcome:

- materially better factual lookup
- fewer retrieval misses caused by chunk context loss
- better support for dates, names, and exact phrases

This phase should probably be completed before any graph investment.

## Phase 2: Add Full-Context and Large-Span Modes

Introduce a retrieval mode that can pass:

- a whole short document
- a whole meeting packet
- an entire email thread
- a small set of large contiguous sections

Use this mode when:

- the candidate set is small
- the answer depends on local narrative continuity
- citation and chronology matter more than response speed

Expected outcome:

- improved single-artifact reasoning
- reduced chunk-boundary errors
- better handling of nuanced meeting and memo questions

## Phase 3: Add Hierarchical Summary Retrieval

Build grounded summary layers such as:

- per-document executive summary
- per-thread summary
- daily source digest
- weekly cross-source briefing summary

Each summary should preserve lineage back to the underlying documents.

Use this path for:

- "catch me up"
- "what changed"
- "what are the main themes"
- briefing and synthesis workflows

Expected outcome:

- much better performance on executive briefing style queries
- lower token cost for recurring overview tasks

## Phase 4: Evaluate Graph Retrieval for Specific Query Families

Pilot graph indexing on a bounded slice of the corpus first, likely:

- calendar events
- email threads
- notes
- project or stakeholder entities

Only proceed if benchmarks show clear gains on:

- dependency mapping
- stakeholder relationship questions
- multi-hop thematic synthesis

Do not make graph retrieval the platform default unless it wins broadly enough to justify the operational cost.

## Phase 5: Introduce Query Routing

Once multiple retrieval modes exist, add a router that chooses among:

- hybrid chunk retrieval
- lexical-heavy retrieval
- full-context mode
- hierarchical summary mode
- graph retrieval mode

The router may start with rules and later evolve into a learned or LLM-assisted policy if needed.

## Decision Gates

The following gates should govern progression:

- Graph retrieval should not be expanded if it does not beat the baseline on relationship-heavy benchmarks.
- Full-context mode should not be used broadly if latency or cost is unacceptable.
- Hierarchical summaries should not be trusted unless summary-to-source grounding is inspectable.
- No new retrieval path should become default without benchmark improvement on factuality and citation precision.

## Practical Near-Term Priority Order

If only one roadmap is funded, the best order for CoS is:

1. Evaluation harness
2. Better baseline hybrid retrieval
3. Full-context mode for bounded tasks
4. Hierarchical summaries for briefing
5. Graph pilot
6. Query router

This ordering is intentionally conservative. It maximizes quality gains per unit of complexity and keeps the system operationally understandable while it matures.

## Final View

The strategic mistake would be to frame the choice as:

- keep current chunked RAG
- or replace it with GraphRAG

That is too binary. The stronger design is a layered system in which:

- chunked hybrid RAG handles the factual core
- full-context mode protects local context where chunking harms quality
- hierarchical summaries support briefing and synthesis
- graph retrieval handles relationship-heavy and multi-hop questions

That is the most plausible route to consistently high-quality, fact-grounded answers for a Chief of Staff platform.

## References

- Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS 2020. <https://arxiv.org/abs/2005.11401>
- Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization," April 24, 2024. <https://arxiv.org/abs/2404.16130>
- Microsoft GraphRAG repository and docs. <https://github.com/microsoft/graphrag>
- GraphRAG query overview. <https://github.com/microsoft/graphrag/blob/main/docs/query/overview.md>
- GraphRAG indexing methods. <https://github.com/microsoft/graphrag/blob/main/docs/index/methods.md>
- Anthropic, "Contextual Retrieval," September 19, 2024. <https://www.anthropic.com/engineering/contextual-retrieval>
- Liu et al., "Lost in the Middle: How Language Models Use Long Contexts," July 6, 2023. <https://arxiv.org/abs/2307.03172>
- Sarthi et al., "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval," ICLR 2024. <https://arxiv.org/abs/2401.18059>
- Gutiérrez et al., "HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models," NeurIPS 2024. <https://arxiv.org/abs/2405.14831>
- Gutiérrez et al., "From RAG to Memory: Non-Parametric Continual Learning for Large Language Models," ICML 2025. <https://openreview.net/forum?id=LWH8yn4HS2>
- Santhanam et al., "ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction," 2021. <https://arxiv.org/abs/2112.01488>
