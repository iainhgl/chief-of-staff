# CoS Future Platform Roadmap

Date: 2026-05-15  
Author: Codex technical research synthesis  
Status: Consolidated recommendation draft

## Purpose

This document consolidates the current forward-looking CoS research into a single platform roadmap. It synthesizes three companion research notes:

- `cos-retrieval-improvement-roadmap-2026-05-15.md`
- `cos-agentic-orchestration-options-2026-05-15.md`
- `cos-llm-routing-and-local-model-options-2026-05-15.md`

The goal is to answer a practical product and architecture question:

> If CoS is expected to evolve from a grounded chat-and-retrieval system into a durable AI operating platform, what should be built next, in what order, and under what decision gates?

## Executive Summary

The current CoS implementation is a credible Phase 1 platform:

- grounded retrieval with citations
- hybrid sparse+dense RAG
- provenance-preserving ingestion
- role-pack-driven behavior
- MCP tool exposure
- a narrow background jobs substrate
- a simple but clean LLM adapter boundary

That is a strong base. It should not be thrown away or replaced wholesale.

The next stage of CoS should not be framed as one grand leap into "agents" or "GraphRAG" or "multi-model orchestration." The better strategy is to evolve the platform in layers:

1. Strengthen the current retrieval baseline and measure quality properly.
2. Make the platform more machine-consumable and model-portable.
3. Add a durable task substrate for asynchronous and iterative work.
4. Introduce richer retrieval modes only where they beat the baseline.
5. Add model-routing policy inside CoS.
6. Only then consider more complex graph retrieval, local inference tiers, or multi-agent orchestration.

This sequence keeps the platform grounded, auditable, and evolvable without overcommitting to premature complexity.

## Current Position

At the time of writing, CoS is best described as:

> A provenance-aware, hybrid chunk-level retrieval platform with role-pack configuration, synchronous MCP tools, a narrow ingest worker substrate, and a single-provider LLM abstraction.

That means the platform is already good at:

- source-preserving ingestion
- citation-grounded Q&A
- document listing and provenance
- basic connected-source sync
- role-specific retrieval shaping

It is not yet optimized for:

- executive synthesis at scale
- long-running iterative task execution
- workflow-level human approvals
- model-provider diversity
- local/self-hosted inference routing
- generalized agent consumption

## Strategic Principles

The consolidated roadmap is guided by these principles:

- Keep retrieval-before-generation as a non-negotiable rule.
- Preserve provenance and auditability as the platform expands.
- Avoid replacing working subsystems before benchmarks justify it.
- Treat routing policy as product logic, not just infrastructure plumbing.
- Prefer explicit task and workflow primitives over implicit chat loops.
- Add complexity only when a narrower substrate has clearly been outgrown.

## The Four Platform Tracks

The future work naturally groups into four tracks.

## Track A: Retrieval Quality and Knowledge Access

This track improves factual grounding and answer quality.

Key themes:

- better hybrid retrieval
- contextual chunk enrichment
- full-context retrieval modes
- hierarchical summaries
- selective graph retrieval
- query routing by question type

This track answers:

- How do we improve answer quality?
- How do we support both factual lookup and executive synthesis?
- When should chunking be bypassed or supplemented?

## Track B: Agentic Orchestration and Task Runtime

This track evolves CoS from synchronous Q&A into durable iterative work.

Key themes:

- task lifecycle
- async execution
- pause/resume
- approval gates
- retries and timers
- workflow state
- agent-safe primitives

This track answers:

- How can CoS support long-running tasks?
- Does it need orchestration?
- When should it adopt a workflow engine?

## Track C: LLM Routing and Model Portability

This track reduces single-vendor dependence and makes the platform policy-aware in how it uses models.

Key themes:

- OpenAI and Gemini support
- internal model-routing policy
- fallback
- workflow-based model selection
- OpenAI-compatible local/self-hosted endpoints
- optional OpenRouter support

This track answers:

- How does CoS support multiple model vendors?
- How should local models be supported?
- Where should model routing live?

## Track D: Platformization and Operations

This track keeps the whole system deployable and governable as it grows.

Key themes:

- repeatable deployment
- operational observability
- resource sizing
- background worker durability
- environment separation
- cost controls

This track is less conceptually flashy but becomes more important as Tracks A through C mature.

## Recommended Sequencing

The key architectural question is not whether all four tracks matter. They do. The real question is ordering.

The recommended order is:

1. evaluation and observability foundations
2. better retrieval baseline
3. richer LLM abstraction and direct provider portability
4. machine-consumable task-safe interfaces
5. durable task substrate
6. full-context and hierarchical retrieval modes
7. model routing policies
8. graph retrieval pilots
9. local/self-hosted model tier
10. advanced orchestration or multi-agent patterns

That order is intentionally conservative. It maximizes learning while minimizing irreversible complexity.

## Consolidated Roadmap

## Phase 0: Establish the Measurement and Visibility Layer

This phase is foundational and should precede nearly everything else.

Deliverables:

- retrieval evaluation set
- benchmark queries across factual, synthesis, and relationship-heavy tasks
- model/provider usage logging
- latency and cost tracing
- structured task/event logging
- clear operator-visible health and failure signals

Why this comes first:

- retrieval changes otherwise become aesthetic rather than measurable
- multi-model routing without observability becomes guesswork
- orchestration without event traces becomes hard to debug

Success criteria:

- every retrieval experiment can be compared against a baseline
- every model call records provider, model, and latency
- key workflow events are reconstructible after the fact

## Phase 1: Strengthen the Existing Retrieval Baseline

This phase keeps the current hybrid RAG architecture but improves it.

Priority work:

- contextual chunk enrichment before indexing
- document-first then chunk-second retrieval
- better metadata filtering
- reranking after initial retrieval
- adjacent-span or parent-context expansion
- better question-type detection

Why this comes early:

- grounded answer quality is still the platform’s core value
- many future orchestration tasks will depend on good retrieval anyway
- this likely delivers the highest value-to-complexity ratio

Success criteria:

- improved factuality and citation precision on the evaluation set
- fewer misses caused by lost chunk context
- no regression in simple citation-grounded lookups

## Phase 2: Refactor the LLM Boundary for Portability

This phase upgrades the current single-provider abstraction without yet introducing complicated routing.

Priority work:

- move from plain `complete(prompt, context)` toward request/response types
- capture provider/model metadata
- capture token usage and latency
- preserve the existing Anthropic path while making room for more adapters

Why this comes before multi-provider routing:

- without a richer internal contract, provider growth will become awkward
- future orchestration and structured tasks will want more than plain text

Success criteria:

- current Anthropic functionality still works
- the abstraction is now ready for additional providers

## Phase 3: Add First-Class OpenAI and Gemini Support

This phase introduces direct provider diversity.

Priority work:

- native OpenAI adapter
- native Gemini adapter
- updated config model for multiple providers
- clear provider selection semantics

Why this comes before local-model support:

- direct providers are easier to validate operationally
- this reduces single-vendor dependence immediately
- it gives a clean basis for later routing policy

Success criteria:

- CoS can run against Anthropic, OpenAI, or Gemini directly
- provider selection is explicit and testable

## Phase 4: Make CoS More Machine-Consumable

This phase starts the shift from "chat server" to "platform component."

Priority work:

- more structured outputs
- clearer MCP contracts
- idempotent tool behavior where relevant
- artifact-oriented responses instead of prose-only where appropriate

Examples:

- task-friendly retrieval envelopes
- explicit evidence bundles
- machine-readable synthesis outputs

Why this matters now:

- external agent runtimes can already consume CoS better
- it lowers the cost of later orchestration work

Success criteria:

- CoS becomes easier to call safely from non-human clients
- responses carry enough structure for downstream workflow logic

## Phase 5: Introduce a General Task Substrate

This phase generalizes the existing ingest jobs substrate into a broader runtime.

Likely concepts:

- tasks
- task_steps
- task_events
- task_artifacts
- checkpoints
- approval_requests

Why this is the architectural turning point:

- this is when CoS starts becoming a durable task platform, not just a tool server

Recommended scope:

- keep it narrow at first
- do not build a general autonomous planner platform immediately
- focus on a few high-value task types

Success criteria:

- tasks can run asynchronously
- state survives process restarts
- progress and failures are inspectable

## Phase 6: Add Full-Context and Hierarchical Retrieval Modes

This phase expands beyond flat chunk retrieval where appropriate.

Priority work:

- full-document or large-span context mode for bounded tasks
- hierarchical summaries for executive briefings
- lineage-preserving summary storage

Why this comes after the task substrate:

- many high-value async tasks will want these capabilities
- summary generation and briefing workflows fit naturally into task execution

Success criteria:

- better performance on briefing and "catch me up" benchmarks
- improved single-artifact reasoning where chunking had been harmful

## Phase 7: Add Model Routing Policy Inside CoS

This phase upgrades from "many adapters" to "managed model policy."

Recommended first routing modes:

- pinned
- fallback
- workflow-based

Examples:

- briefing workflow -> one model
- extraction workflow -> cheaper/faster model
- sensitive workflow -> local-only or approved-provider-only

Why this comes after multiple direct providers exist:

- policy without choice is meaningless
- routing needs actual provider metadata and observability

Success criteria:

- routing decisions are auditable
- fallback works cleanly
- workflows can opt into explicit model policies

## Phase 8: Evaluate Graph Retrieval and Relationship-Centric Modes

This phase should be treated as a bounded pilot, not a foregone platform-wide migration.

Suggested target questions:

- stakeholder relationship mapping
- dependency tracing
- cross-source thematic linkage
- unresolved issue linkage across artifacts

Why this is deferred:

- graph retrieval is powerful but expensive in complexity
- it should earn its place through benchmark wins

Success criteria:

- clear gains on relationship-heavy queries
- manageable indexing and maintenance cost
- no unnecessary contamination of the simpler baseline path

## Phase 9: Add an OpenAI-Compatible Local/Self-Hosted Inference Tier

This phase enables local-model support cleanly.

Recommended approach:

- keep CoS talking to an API endpoint
- support local/self-hosted serving through an OpenAI-compatible adapter
- use Ollama for simple local/dev use
- use vLLM or a dedicated inference service for stronger hosted setups

Why this is not earlier:

- local-model support is strategically valuable but not the biggest early value driver
- it also brings infrastructure implications, especially if GPU-backed

Success criteria:

- sensitive or experimental workflows can target local endpoints
- the main CoS application host remains decoupled from model-serving mechanics

## Phase 10: Introduce Advanced Orchestration and Selective Multi-Agent Patterns

This is the last major phase because it carries the highest complexity risk.

Potential work:

- richer workflow branching
- workflow-engine adoption if the native substrate becomes strained
- planner/executor splits
- verifier agents
- agent-to-agent interoperability where needed

Why this is last:

- most teams reach for multi-agent systems too early
- the platform should first prove value with durable single-workflow execution

Success criteria:

- clear need beyond the simpler task runtime
- operator visibility remains strong
- complexity is justified by task outcomes, not novelty

## Parallelization Guidance

Not everything must happen strictly serially. Some tracks can move in parallel once foundations are in place.

Good parallel combinations:

- Phase 1 retrieval improvements with Phase 2 LLM-boundary refactor
- Phase 3 provider additions with Phase 4 machine-consumable API work
- Phase 5 task substrate with Phase 6 hierarchical retrieval design

Combinations to avoid:

- graph retrieval before retrieval benchmarking exists
- local-model infrastructure before the routing abstraction exists
- multi-agent coordination before durable task execution works

## First Candidate Use Cases

The platform should prove its next-stage architecture on a few concrete tasks rather than on generic abstractions.

Good proving-ground tasks:

- generate a daily or weekly briefing from newly ingested material
- monitor a topic and produce a grounded update when relevant changes appear
- assemble a meeting-prep packet across multiple sources
- draft a document, pause for approval, revise, and publish

These tasks force the platform to exercise:

- retrieval quality
- asynchronous execution
- artifacts
- approval gates
- provider choice

without requiring full autonomy from day one.

## Decision Gates

The following gates should shape implementation choices:

- Do not adopt complex retrieval modes without benchmark wins.
- Do not adopt heavy orchestration until the narrow task substrate proves valuable.
- Do not make OpenRouter foundational.
- Do not couple local-model support to the base CoS application VM.
- Do not add many providers before the LLM abstraction is slightly richer.
- Do not introduce multi-agent patterns before single-workflow durability is strong.

## Recommended Near-Term Delivery Plan

If the team wants the most pragmatic next sequence, it is:

1. Build the evaluation and observability layer.
2. Improve baseline retrieval.
3. Refactor the LLM abstraction.
4. Add OpenAI support.
5. Add Gemini support.
6. Make CoS outputs more machine-consumable.
7. Generalize jobs into a task substrate.
8. Add one proving-ground asynchronous workflow, preferably a briefing workflow.

That sequence would create a significantly more future-ready platform without committing too early to graph pipelines, local GPU inference, or multi-agent complexity.

## Final Recommendation

The best single-sentence recommendation is:

> Evolve CoS from a grounded retrieval application into a durable AI platform by strengthening retrieval first, then adding provider portability, then introducing a narrow but durable task runtime, and only later layering in richer routing, graph retrieval, local inference, and advanced agent orchestration.

This preserves what is already strong about the current system while giving it a disciplined path toward becoming a broader AI operating platform.
