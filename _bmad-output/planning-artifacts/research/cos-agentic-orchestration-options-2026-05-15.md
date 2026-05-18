# CoS Agentic Orchestration Options

Date: 2026-05-15  
Author: Codex technical research pass  
Status: Recommendation draft for platform direction

## Executive Summary

The current CoS platform is built around a synchronous question-and-answer pattern exposed through MCP tools. That is a sensible first product shape because it is easy to test, easy to reason about, and naturally aligned with a human operator using a chat interface.

However, an agent-consumable CoS platform is a meaningfully different system. The moment the platform must support long-running tasks, iteration, retries, human approval gates, background execution, and partial progress across hours or days, the architecture changes. At that point, the key requirement is no longer just retrieval quality. It is durable orchestration.

This is feasible. In fact, the current codebase already contains the beginnings of the required substrate:

- MCP tool exposure for synchronous capabilities
- a worker process
- a jobs table
- retry and stale-job recovery logic

But those capabilities are currently specialized for ingestion rather than for general agent tasks.

The central conclusion is:

> If CoS is meant to support long-running agent workflows rather than only one-shot chat interactions, it will need an orchestration layer. That layer does not have to be a large custom framework immediately, but it does need to exist explicitly.

The best near-term move is not to build a full multi-agent system. It is to add a durable task/workflow substrate and keep CoS itself as a strong tool-and-memory service. More advanced agent orchestration can then sit above it.

## Current State of the CoS Platform

Today’s platform is optimized for synchronous use:

- MCP exposes `retrieve`, `get_status`, `get_role_context`, `ingest_document`, and `list_documents`.
- The MCP server starts retrieval, output, and role-pack services in-process.
- There is a background worker and a `jobs` table, but they are presently scoped to ingest job handling.

Relevant local references:

- `src/cos/mcp_server/tools.py`
- `src/cos/mcp_server/server.py`
- `src/cos/services/jobs.py`
- `src/cos/worker.py`
- `src/cos/store/migrations/002_jobs.sql`

This means CoS already has:

- tool serving
- background execution
- retry semantics
- minimal durable job persistence

What it does not yet have is:

- a general task model
- workflow state
- checkpoints for multi-step reasoning
- resume semantics for paused tasks
- explicit approval gates
- cancellation and deadlines
- agent-specific memory for a task run
- step-level observability

So the platform is not starting from zero, but it is also not yet an agent runtime.

## Why Agent Consumption Is Different

Human Q&A systems can get away with a simple shape:

- user asks a question
- retrieval happens
- synthesis happens
- answer is returned

Agent-consumable systems usually need a different contract:

- accept a task with a goal and constraints
- plan or select a next step
- act using tools
- observe the result
- update task state
- decide whether to continue, pause, escalate, or stop
- resume later without losing work

That difference sounds small conceptually, but it drives major architectural consequences.

## Feasibility

This direction is feasible, and the current system is actually well positioned for it.

Reasons it is feasible:

- CoS already separates retrieval from presentation reasonably well.
- MCP already makes the platform callable as a tool server.
- The existing worker/jobs substrate proves the team can already operate background work with retries.
- The knowledge and provenance model is already stronger than many prototype agent stacks.

What makes it non-trivial:

- long-running tasks need durable state, not just logs
- tool calls need idempotency and replay discipline
- planning loops need cost and failure controls
- side effects need approval and audit
- asynchronous execution changes the product interface, not just the backend

The feasibility answer is therefore:

> Yes, this is feasible. No, it is not just "let an agent call retrieve in a loop."

## Important Distinction: Protocol vs Orchestration

These concepts are related but not interchangeable:

### MCP

MCP is a tool and context protocol. It standardizes how a client interacts with tools, prompts, and resources. It is useful for exposing CoS capabilities to external agent runtimes.

It is not, by itself, a durable orchestration runtime.

### A2A

A2A is an interoperability protocol for communication between agents. It matters when multiple agents or agent services need to talk to each other across systems.

It is not, by itself, a durable execution engine either.

### Orchestration

Orchestration is the layer that manages task state, step execution, retries, timers, approvals, resumability, cancellation, and observability.

This is the missing architectural concept if CoS is to evolve from a chat-oriented MCP server into an agent-ready platform.

## What "Long-Running Agent" Usually Requires

In practice, the platform must support at least:

- task creation
- task state persistence
- step history
- retries with backoff
- timers and scheduling
- pause and resume
- human approval interrupts
- cancellation
- progress updates
- budget and token accounting
- side-effect audit trails

Once those are required, the system is much closer to workflow orchestration than to a conventional chat server.

## Option Space

## Option A: Keep CoS as a Tool Server and Let an External Agent Runtime Orchestrate

In this model, CoS remains primarily:

- a knowledge substrate
- a retrieval service
- a provenance service
- a role-context service
- a structured tool surface via MCP

An external agent runtime handles planning, looping, task state, approval pauses, and resume logic.

Examples of orchestration runtimes in this category:

- LangGraph, which emphasizes durable execution, persistence, and human-in-the-loop controls
- Microsoft Agent Framework, which combines agents with explicit workflow/state features for long-running scenarios
- other agent runtimes that provide durable sessions and workflow control

Advantages:

- smallest change to CoS itself
- preserves CoS as a composable platform component
- avoids building a full agent framework prematurely
- lets different clients choose different orchestration approaches

Disadvantages:

- orchestration behavior lives outside CoS
- agent quality becomes fragmented across clients
- task history and memory may be split across systems
- harder to enforce a single enterprise-grade operating model

Assessment for CoS:

This is the fastest path to agent consumption. It is especially attractive if the main goal is for other agent systems to consume CoS as a high-quality retrieval and memory backend.

## Option B: Generalize the Existing Jobs Substrate into a Native Task Runtime

Today’s `jobs` table and worker can claim, retry, and recover ingest tasks. That pattern can be expanded into a general task runtime inside CoS.

This would likely add concepts such as:

- `tasks`
- `task_steps`
- `task_artifacts`
- `task_events`
- `task_checkpoints`
- `approval_requests`

Advantages:

- keeps task state close to the knowledge base
- gives CoS a first-class asynchronous product surface
- can be shaped tightly around CoS use cases
- simpler operational footprint than introducing a major new external platform

Disadvantages:

- you will be building orchestration software
- determinism, replay, and idempotency are harder than they first appear
- pause/resume logic tends to grow quickly in complexity
- observability and operator tooling become a real workload

Assessment for CoS:

This is viable if the desired orchestration layer is relatively narrow and CoS-specific. It is less attractive if the long-term ambition is a broad, general-purpose autonomous runtime.

## Option C: Introduce a Dedicated Durable Workflow Engine

This option uses a system explicitly built for durable execution rather than extending the current `jobs` queue by hand.

Representative patterns:

- Temporal-style durable workflows
- LangGraph-style persistent agent graphs
- framework-managed workflow engines with checkpoints and resume semantics

Advantages:

- much stronger guarantees for long-running work
- better support for retries, timers, pauses, signals, and resumability
- cleaner model for human-in-the-loop approvals
- less bespoke reinvention of workflow mechanics

Disadvantages:

- new platform dependency
- operational and architectural complexity
- engineers must learn the workflow model
- integration work still remains around tool design and state boundaries

Assessment for CoS:

If the platform really intends to support durable, iterative, multi-step, side-effecting work across hours or days, this is the strongest architectural direction. It is the most likely answer once the problem moves beyond simple background jobs.

## Option D: Multi-Agent Coordination Layer

This option assumes not just one planner/executor loop, but multiple specialized agents:

- planner
- retriever
- drafter
- verifier
- approval coordinator
- channel executor

Advantages:

- can separate concerns clearly
- sometimes improves quality on complex tasks
- can mirror organizational roles naturally

Disadvantages:

- much higher complexity
- more latency and cost
- harder debugging
- error attribution becomes difficult
- often overused before simpler workflows are fully exhausted

Assessment for CoS:

This should be deferred. The current system should move first from synchronous chat to durable single-workflow execution before introducing multiple collaborating agents.

## Option E: Agent Interoperability Layer

This option is about how CoS agents or services talk to other agents and systems.

Likely role of each protocol:

- MCP for tools and context exposure
- A2A for agent-to-agent interoperability, if and when CoS participates in a broader multi-agent ecosystem

Advantages:

- future-proofs interoperability
- avoids locking CoS into a single agent framework

Disadvantages:

- does not solve orchestration on its own
- can distract from the harder internal execution problem

Assessment for CoS:

This matters, but it is a second-order concern. First solve durable task execution. Then standardize external interoperability.

## Do We Need a New Orchestration Layer?

Short answer:

> Yes, if the goal is truly long-running agent work rather than repeated synchronous tool calls.

Longer answer:

- If the next phase is only "allow an external agent to call CoS retrieval and ingest tools," then no major new orchestration layer is required immediately.
- If the next phase is "let tasks run over time, iterate, pause for approval, resume, and produce artifacts," then yes, an orchestration layer is required.

The existing ingest jobs queue is not enough by itself because it is currently:

- single-purpose
- job-oriented rather than workflow-oriented
- not designed around task memory or approval gates
- not exposed as a general agent task API

## Recommended Direction

The recommended design is to separate the problem into two layers:

### Layer 1: CoS as Agent-Grade Capability Server

CoS should remain strong at:

- grounded retrieval
- provenance
- role context
- source ingestion
- memory and artifact storage
- output routing

This layer should expose machine-friendly APIs and MCP tools, not just chat-oriented answers.

### Layer 2: Durable Task Orchestration

Add an orchestration layer for:

- task lifecycle
- planning loops
- step execution
- approval interrupts
- timers
- retries
- resumability

This can initially be:

- a thin native workflow layer built on the current jobs substrate

or, if the ambition is higher:

- a dedicated durable workflow engine

## The Product Shift Required

To support agents cleanly, CoS should move from "chat tools" toward "task primitives."

Examples of new primitives:

- `create_task(goal, constraints, inputs)`
- `get_task(task_id)`
- `list_task_events(task_id)`
- `approve_task_step(task_id, step_id, decision)`
- `cancel_task(task_id)`
- `resume_task(task_id, additional_input)`
- `fetch_artifact(task_id, artifact_id)`

Examples of internal step primitives:

- `search_evidence`
- `retrieve_document_set`
- `extract_facts`
- `compare_sources`
- `draft_output`
- `verify_against_citations`
- `publish_to_channel`

This shift is important because agents do better with explicit, typed, resumable actions than with ambiguous prose-only interfaces.

## Recommended Phased Roadmap

## Phase 0: Define the Agent Task Taxonomy

Clarify which tasks are actually desired. For example:

- prepare a briefing from new source updates
- watch a topic and notify on meaningful changes
- draft and refine an artifact over multiple iterations
- perform scheduled reviews with approval before dispatch

This matters because not every "agent" task needs a fully autonomous planner.

## Phase 1: Make CoS More Machine-Consumable

Add or refine:

- structured outputs
- task-safe idempotent tools
- better retrieval APIs for agent consumption
- artifact-oriented responses rather than only prose answers

At this stage, CoS can already serve as a stronger backend for external agent runtimes.

## Phase 2: Introduce General Task Records and Async Execution

Generalize the current jobs model beyond ingest:

- task entity
- task event log
- task status transitions
- task artifacts
- approval requests

This is the minimum viable orchestration substrate.

## Phase 3: Add Durable Resume and Human Approval Gates

Support:

- pause and resume
- operator review
- deadlines and timers
- continuation after external events

This is the point where CoS starts becoming a true long-running workflow system.

## Phase 4: Decide Build vs Adopt for Orchestration

Make the decision after Phase 2 and 3 prototypes answer these questions:

- Are workflows becoming complex and branching?
- Do tasks need strong durability guarantees across outages?
- Is human approval a first-class feature?
- Do tasks run for hours or days?
- Is replay/idempotency complexity growing too quickly?

If yes, adopt a durable orchestration engine instead of growing a homebrew runtime indefinitely.

## Phase 5: Add Agent Routing or Multi-Agent Patterns Selectively

Only after the workflow substrate is stable should CoS consider:

- planner/executor splits
- verifier agents
- specialized drafting or review agents
- A2A interoperability

## Preferred Near-Term Architecture

For the next stage, the best answer is likely:

1. Keep CoS as the retrieval/provenance/memory platform.
2. Make its interfaces more structured and agent-safe.
3. Add a general task runtime.
4. Use either a thin native workflow model first or adopt durable orchestration if the workflow complexity ramps quickly.

This is more disciplined than trying to turn the MCP server itself into a self-running autonomous agent.

## Architectural Recommendation

If forced to choose today, the recommended answer is:

> Do not make CoS itself a free-form autonomous agent first. Make it an excellent agent backend plus a durable task substrate.

That means:

- strong tool APIs
- durable task records
- resumable workflows
- explicit approval gates
- audit and provenance throughout

Once that foundation exists, a planner agent or external orchestration framework can safely sit on top of it.

## Final View

The current CoS system is well suited to evolve into an agent-capable platform, but not by simply exposing more chat tools. The right next step is to introduce explicit orchestration semantics.

MCP helps expose capabilities. A2A may later help with interoperability. Neither replaces a workflow runtime. If the goal is long-running, iterative, auditable agent work, some form of orchestration layer is necessary.

The real decision is not whether orchestration is needed. It is whether to:

- extend the current queue/worker model into a narrow native runtime

or

- adopt a durable workflow engine once the task model proves valuable

For CoS, the prudent path is to start narrow, keep the interfaces structured, and only escalate to heavier orchestration once the workload demonstrates the need.

## References

- Anthropic, "Building Effective Agents," December 19, 2024. <https://www.anthropic.com/engineering/building-effective-agents>
- LangGraph documentation, durable execution. <https://docs.langchain.com/oss/python/langgraph/durable-execution>
- Temporal documentation and overview. <https://docs.temporal.io/> and <https://temporal.io/>
- Microsoft Agent Framework overview. <https://learn.microsoft.com/en-gb/agent-framework/overview/>
- Semantic Kernel Process Framework example docs. <https://learn.microsoft.com/en-us/semantic-kernel/frameworks/process/examples/example-first-process>
- Model Context Protocol specification overview. <https://modelcontextprotocol.io/specification/2024-11-05/basic/index>
- A2A protocol documentation. <https://a2a-protocol.org/latest/>
