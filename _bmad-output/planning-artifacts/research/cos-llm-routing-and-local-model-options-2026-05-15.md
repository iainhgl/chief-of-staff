# CoS LLM Routing and Local Model Options

Date: 2026-05-15  
Author: Codex technical research pass  
Status: Recommendation draft for platform direction

## Executive Summary

The current CoS platform is intentionally simple in its model layer. It has a single active LLM provider configured in `config.yaml`, a small adapter interface, and one concrete implementation for Anthropic Claude. That is a good design for an early-stage platform because it keeps the retrieval and grounding work separate from model-vendor complexity.

However, if CoS is expected to evolve into a durable platform, it should not remain tied to a single model vendor. It should support at least:

- direct vendor integration for OpenAI, Anthropic, and Gemini
- a path to local or self-hosted models
- explicit routing and fallback policies
- per-workflow model selection
- auditability of which model handled which request

The central conclusion is:

> CoS should own its model-routing policy internally. OpenRouter can be useful as one provider option, but it should not become the core abstraction for the product.

The best next-step architecture is:

1. Refactor the model interface slightly upward from today’s minimal `complete(prompt, context)` shape.
2. Add first-class adapters for OpenAI and Gemini alongside Anthropic.
3. Add a generic OpenAI-compatible adapter for local or self-hosted endpoints such as Ollama or vLLM.
4. Add internal routing and fallback policy in CoS.
5. Optionally add OpenRouter later as one more adapter, not as the whole strategy.

## Current State of the CoS Platform

Today’s model layer is deliberately narrow:

- a single `llm.provider`
- a single `llm.model`
- a single `llm.api_key`
- one adapter factory that only supports Anthropic
- one adapter interface with one method: `complete(prompt, context)`

Relevant local references:

- `src/cos/llm/factory.py`
- `src/cos/llm/adapter.py`
- `src/cos/llm/anthropic.py`
- `src/cos/config.py`

This gives the platform a useful property:

- the rest of CoS is not deeply entangled with Anthropic specifics

But it also imposes current limits:

- no multi-provider support
- no local model endpoint support
- no routing or fallback behavior
- no explicit structured output contract
- no per-task model policy

So the platform is well positioned for extension, but not yet designed for provider diversity.

## Why Multi-Provider Support Matters

There are several reasons CoS should not remain single-vendor:

- cost differences between models
- latency differences between models
- reliability and outage resilience
- different strengths for synthesis, extraction, classification, and drafting
- procurement and compliance flexibility
- the desire to run locally or privately for some workloads

For a CoS product, this is especially relevant because all tasks do not need the same model characteristics. Some tasks may want:

- lowest cost
- strongest reasoning
- fastest turnaround
- private/local handling
- a specific model approved by policy

This is best handled as a product-level routing problem.

## Why Local Models Matter

The request to support local models is strategically sensible even if it is not the default path.

Reasons include:

- sensitive content handling
- lower marginal inference cost at scale
- offline or constrained-network operation
- experimentation with smaller specialized models
- control over upgrade timing

But "support local models" should not be confused with "run local models on the same small VM."

The current recommended GCP deployment shape for CoS is a modest CPU VM. That is appropriate for Postgres, Tika, CoS, and the worker, but not for high-quality self-hosted LLM inference. Useful local inference usually implies one of:

- a separate GPU VM
- a dedicated local workstation
- a self-hosted inference service

So local-model support should be treated as an integration capability, not as an assumption about the main CoS application host.

## Current Codebase Read

The current design makes extension reasonably easy:

### Strengths

- the rest of the application depends on a small protocol
- the provider-specific logic is already isolated
- transport concerns are partially abstracted
- the factory pattern already exists

### Constraints

- config only supports one active provider
- request shape is minimal
- response shape is just a string
- there is no routing policy object
- model selection is global rather than task-aware

This means:

> Adding a second provider is straightforward. Adding a durable multi-provider strategy is a bigger but still manageable refactor.

## Option Space

## Option A: Stay Single-Provider

This means keeping the current shape and only swapping vendors occasionally.

Advantages:

- lowest implementation effort
- simplest operational model
- least configuration complexity

Disadvantages:

- no fallback resilience
- no per-task optimization
- no clean local-model path
- procurement and pricing risk remains concentrated

Assessment for CoS:

This is acceptable only as a temporary state.

## Option B: Add Direct First-Class Provider Adapters

This means CoS integrates separately with:

- Anthropic
- OpenAI
- Gemini

Advantages:

- best control
- clear auditability
- provider-specific tuning remains available
- no third-party broker dependency required

Disadvantages:

- more engineering work
- multiple SDKs or API surfaces to maintain
- routing logic becomes your responsibility

Assessment for CoS:

This should be the default strategic direction.

## Option C: Use an Aggregator Such as OpenRouter as the Primary Abstraction

In this model, CoS mostly integrates with OpenRouter rather than with vendors directly.

Advantages:

- fast access to many models
- easy experimentation
- one integration surface
- useful for fallback and broad model discovery

Disadvantages:

- an extra dependency in the critical path
- less direct control over provider contracts
- governance and audit can become less explicit
- product routing policy risks leaking into infrastructure dependency choices

Assessment for CoS:

OpenRouter is valuable as an option, not as the core architectural abstraction.

## Option D: Support Local Models Through an OpenAI-Compatible Endpoint

This means CoS integrates with a local or self-hosted service that presents an OpenAI-compatible API.

Common examples:

- Ollama for simple local development and testing
- vLLM for more production-like hosted inference
- other OpenAI-compatible gateways

Advantages:

- one adapter can support many local/self-hosted backends
- good separation between CoS and the inference engine
- easier path to experimentation

Disadvantages:

- capability differences still exist under the same API shape
- local model quality may be materially lower than frontier APIs
- infrastructure cost can move from API spend to GPU spend

Assessment for CoS:

This is the cleanest way to support local models without warping the application architecture.

## Option E: Internal Routing Layer in CoS

This means CoS itself decides which model to use based on:

- workflow
- task type
- cost policy
- latency policy
- sensitivity policy
- fallback status

Advantages:

- routing becomes explicit product behavior
- auditability is much stronger
- policy can be attached to role packs or workflows
- vendor lock-in is reduced

Disadvantages:

- more internal complexity
- requires a richer config model
- needs clear observability and failure semantics

Assessment for CoS:

This is the right long-term shape.

## Recommended Architectural Direction

The recommended target state is:

> Direct provider support plus internal routing, with optional support for OpenRouter and OpenAI-compatible local endpoints.

This leads to a layered model:

- CoS owns policy
- adapters own API mechanics
- local inference servers own actual self-hosted generation
- optional aggregators remain optional

## Why CoS Should Own Routing Policy

Routing is not just a technical optimization. It affects:

- answer quality
- cost
- privacy posture
- operational resilience
- auditability

For CoS, routing decisions may eventually depend on:

- the active workflow
- the role pack
- whether the task is retrieval-only, synthesis-heavy, or side-effecting
- whether the task is sensitive enough to require local-only execution
- whether a premium model is justified

Those are product concerns, not merely transport concerns. That is why the routing policy belongs in CoS.

## Why OpenRouter Should Be Optional

OpenRouter is useful for:

- rapid model experimentation
- early-stage access to many models
- fallback to alternate providers
- benchmarking many models with one integration

It is less ideal as the sole foundation if the product cares deeply about:

- exact provider lineage
- long-term enterprise governance
- strict control over which vendors are used when
- explicit operational guarantees

So the right framing is:

- direct providers for primary production paths
- OpenRouter as an optional adapter for experimentation or overflow

## Why OpenAI Should Likely Be the First Additional Provider

If CoS adds providers in sequence, the most sensible order is:

1. OpenAI
2. Gemini
3. generic OpenAI-compatible local endpoint
4. optionally OpenRouter

Reasons OpenAI is the best first addition:

- strong general-purpose API ecosystem
- broad developer familiarity
- useful path to structured and tool-oriented future patterns
- clean complement to Anthropic rather than a duplicate of it

Reasons Gemini is a good next addition:

- strong alternative vendor
- useful diversity in provider options
- good strategic hedge

## Local Model Strategy

The cleanest local-model strategy is:

- do not embed local inference into the CoS application container
- expose local or self-hosted inference behind an API endpoint
- let CoS talk to it through an adapter

Preferred patterns:

- local development: Ollama
- stronger hosted serving: vLLM
- later, if needed, a dedicated GPU-backed inference service

This keeps responsibilities separate:

- CoS handles orchestration, retrieval, provenance, and policy
- the inference service handles model loading, scheduling, and execution

## GCP Cost Implication of Local Models

For planning purposes, there is a major economic difference between:

- a CPU VM running the current CoS stack
- a GPU-backed environment suitable for local model inference

The current recommended CoS application host is in the rough range of about $108 per month before API spend. A GPU-backed local-model host can easily exceed that by several multiples, depending on GPU type and utilization.

This does not make local models a bad idea. It simply means they should be evaluated as a separate infrastructure tier, not as a free extension of the base CoS VM.

## Required Refactor to the LLM Abstraction

The current adapter contract:

- `complete(prompt, context) -> str`

is a good minimum, but it is likely too narrow for a multi-provider future.

It should evolve toward a richer internal model, for example:

- request object with system prompt, user instruction, context, temperature, max tokens, and structured-output hints
- response object with text, provider, model, token usage, latency, finish reason, and raw metadata

Suggested direction:

- `LLMRequest`
- `LLMResponse`
- `LLMAdapter.generate(request) -> response`

Why this matters:

- provider routing needs observability
- future workflows may need structured outputs
- fallback logic should be able to preserve model metadata
- agentic and workflow features will need more than plain-text completion

## Suggested Config Direction

Today’s config supports one provider. A more future-ready shape would look roughly like:

```yaml
llm:
  default_provider: openai
  routing_policy: fallback
  providers:
    openai:
      type: openai
      model: gpt-5-mini
      api_key: ${OPENAI_API_KEY}
    claude:
      type: anthropic
      model: claude-sonnet-4-6
      api_key: ${ANTHROPIC_API_KEY}
    gemini:
      type: gemini
      model: gemini-2.5-flash
      api_key: ${GEMINI_API_KEY}
    local:
      type: openai_compatible
      model: qwen2.5
      base_url: http://ollama:11434/v1
      api_key: dummy
```

Useful policy fields could include:

- `routing_policy`
- `fallback_order`
- `sensitive_data_policy`
- `workflow_overrides`
- `role_pack_overrides`

## Suggested Routing Policies

The first routing modes should be simple and explicit:

### 1. Pinned

Use one configured provider for all requests.

### 2. Fallback

Try a preferred provider, then fail over to one or more alternates.

### 3. Workflow-Based

Choose model by workflow, for example:

- briefing -> Claude
- extraction -> OpenAI
- low-cost summarization -> Gemini Flash

### 4. Sensitivity-Based

Route specific tasks to local/self-hosted models only.

### 5. Cost-Aware

Use cheaper models by default and escalate only when needed.

The main recommendation is to start with:

- pinned
- fallback
- workflow-based

Those are enough to create real value without turning the router into an opaque policy engine too early.

## Recommended Implementation Roadmap

## Phase 0: Refactor the LLM Abstraction

Introduce richer request and response types while preserving the current behavior.

Deliverables:

- `LLMRequest`
- `LLMResponse`
- provider/model metadata in responses
- usage and latency capture

## Phase 1: Add OpenAI

Add a native OpenAI adapter and update config/tests accordingly.

Expected outcome:

- first multi-provider production option
- immediate reduction in single-vendor dependency

## Phase 2: Add Gemini

Add a native Gemini adapter and extend provider registry logic.

Expected outcome:

- stronger vendor diversity
- better fallback options

## Phase 3: Add OpenAI-Compatible Adapter

Support:

- Ollama
- vLLM
- similar compatible endpoints

Expected outcome:

- clean local/self-hosted model path

## Phase 4: Add Routing Policies

Start with:

- pinned
- fallback
- workflow-based

Expected outcome:

- practical provider selection without excessive complexity

## Phase 5: Add Optional OpenRouter Adapter

Only after direct providers work well should CoS consider an OpenRouter adapter.

Use cases:

- experimentation
- broad benchmark comparisons
- overflow or resilience

## Decision Gates

The following should govern the rollout:

- Do not add many providers before upgrading the abstraction slightly.
- Do not make OpenRouter the mandatory path.
- Do not couple local-model support to the main application VM.
- Do not introduce complex routing policies before observability exists.
- Every generated response should record provider and model metadata for auditability.

## Recommended Final Position

If a single recommendation must be stated clearly, it is:

> Build model routing into CoS itself, integrate directly with OpenAI and Gemini next, keep Anthropic, support local models through an OpenAI-compatible endpoint, and treat OpenRouter as optional rather than foundational.

That approach gives CoS:

- control
- flexibility
- future local-model compatibility
- resilience against vendor concentration
- a cleaner path into more agentic workflows later

## Final View

The current model layer is simple enough that extending it is not hard. That is a good position to be in. The risk is not that the platform cannot support multiple models. The risk is that it might adopt the wrong abstraction too early.

The right abstraction is not "one SDK per model" and not "just put everything behind OpenRouter." The right abstraction is:

- internal request/response contract
- adapter-per-provider
- internal routing policy
- optional aggregator support
- optional local OpenAI-compatible inference support

That will keep CoS portable, governable, and better aligned with the platform’s long-term role as a durable AI operating system rather than a single-vendor wrapper.

## References

- OpenAI models overview. <https://platform.openai.com/docs/models>
- OpenAI Responses API. <https://platform.openai.com/docs/api-reference/responses>
- Gemini API models documentation. <https://ai.google.dev/gemini-api/docs/models>
- OpenRouter routing and provider selection docs. <https://openrouter.ai/docs/guides/routing/provider-selection>
- Ollama documentation. <https://docs.ollama.com/>
- vLLM documentation. <https://docs.vllm.ai/>
- Google Cloud Compute pricing. <https://cloud.google.com/compute/all-pricing?hl=en>
- Google Cloud GPU pricing. <https://cloud.google.com/compute/gpus-pricing>
