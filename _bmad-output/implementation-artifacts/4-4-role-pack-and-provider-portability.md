# Story 4.4: Role Pack & Provider Portability

Status: done

## Story

As an operator,
I want to switch role packs, embedding providers, and LLM providers by changing only configuration values,
So that the platform can be adapted for a new person or updated to use a better model without any code changes.

## Acceptance Criteria

1. **Given** a minimal second role pack YAML file exists (`role_packs/enterprise_architect.yaml`) with different `role_name`, `tone`, `knowledge_taxonomy`, and `retrieval_priorities`, **When** `config.yaml` is updated to point `role_pack.path` to this file and the `cos` container is restarted, **Then** `get_role_context` returns the new role's configuration and retrieval/synthesis behaviour reflects the new role — no code was modified.

2. **Given** `config.yaml` `embedding.model` is changed to a different model name (e.g. from `voyage-3` to `voyage-3-large`) and the container is restarted, **When** a new document is ingested, **Then** the embedder uses the new model for that document's embeddings — no code change was required, only the config value.

3. **Given** `config.yaml` `embedding.provider` and `llm.provider` each specify a provider name, **When** the relevant adapter is instantiated at startup, **Then** the platform resolves the correct adapter implementation based solely on the config value — adding a new provider requires only a new adapter file and a config entry, with no changes to `pipeline.py`, `services/retrieval.py`, `services/ingestion.py`, or `mcp_server/tools.py`.

4. **Given** the `LLMAdapter` protocol defined in Epic 1, **When** `AnthropicAdapter` is inspected, **Then** it implements the protocol fully and no code outside `cos/llm/` makes any assumption about the concrete provider type — `server.py` references only `make_llm_adapter`, not `AnthropicAdapter`.

## Tasks / Subtasks

- [x] Task 1: Create `role_packs/enterprise_architect.yaml` (AC: #1)
  - [x] Add all 8 required `RolePackConfig` fields: `role_name`, `goals`, `tone`, `knowledge_taxonomy`, `stakeholder_map`, `retrieval_priorities`, `active_workflows`, `output_channels`
  - [x] Use `role_name: Enterprise Architect` — genuinely different from CHRO
  - [x] `output_channels: [local]` — same as CHRO (only channel implemented)
  - [x] At least 5 entries in `retrieval_priorities` — different domain from CHRO
  - [x] Do NOT modify any Python code; this is a YAML file only

- [x] Task 2: Create `src/cos/llm/factory.py` (AC: #3, #4)
  - [x] Define `make_llm_adapter(config: CosConfig) -> LLMAdapter` function
  - [x] Import `LLMAdapter` from `cos.llm.adapter` — the return type annotation uses only the protocol
  - [x] For `config.llm.provider == "anthropic"`: instantiate `AnthropicAdapter` with transport config fallback logic (see Dev Notes — move the full 20-line block from `server.py` here)
  - [x] For unknown providers: raise `SystemExit(f"Unsupported LLM provider: {config.llm.provider!r}\nAdd a new adapter in cos/llm/ and register it in cos/llm/factory.py.")`
  - [x] The `AnthropicAdapter` and `HttpTransportConfig` imports stay inside `factory.py` — they must NOT appear in `server.py`

- [x] Task 3: Refactor `src/cos/mcp_server/server.py` to use the factory (AC: #4)
  - [x] Remove line: `from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig`
  - [x] Add line: `from cos.llm.factory import make_llm_adapter`
  - [x] In `_startup_sequence`, replace the entire `adapter = AnthropicAdapter(...)` block (lines 122–142) with: `adapter = make_llm_adapter(config)`
  - [x] No other changes to `server.py`

- [x] Task 4: Refactor `src/cos/ingestion/embedder.py` to use a provider registry (AC: #3)
  - [x] Define `_EMBED_PROVIDERS: dict[str, Any]` at module level mapping `"anthropic"` → `_embed_via_voyage`
  - [x] In `embed()`: replace the `if provider != "anthropic": raise ...` / `return await _embed_via_voyage(...)` block with a registry lookup:
    ```python
    fn = _EMBED_PROVIDERS.get(provider)
    if fn is None:
        raise EmbeddingError(f"Unsupported embedding provider: {provider!r}")
    return await fn(chunks, model, api_key, transport)
    ```
  - [x] `_embed_via_voyage` must be defined BEFORE the registry dict (it's referenced in the dict)
  - [x] All existing embedder tests must continue to pass — the observable behaviour is identical

- [x] Task 5: Add `tests/llm/test_factory.py` (AC: #3, #4)
  - [x] Test `test_make_llm_adapter_anthropic_returns_llm_adapter`: build a minimal config SimpleNamespace (`llm.provider="anthropic"`, `llm.model="claude-3-haiku-20240307"`, `llm.api_key` with `.get_secret_value()→"test"`, `llm.ca_bundle_path=None`, `llm.proxy_url=None`, `llm.trust_env=None`, `embedding.ca_bundle_path=None`, `embedding.proxy_url=None`, `embedding.trust_env=False`); call `make_llm_adapter(config)`; assert `isinstance(result, LLMAdapter)`
  - [x] Test `test_make_llm_adapter_unknown_provider_raises_system_exit`: same config but `llm.provider="unsupported_xyz"`; assert `pytest.raises(SystemExit, match="Unsupported LLM provider")`
  - [x] Test `test_server_module_does_not_expose_anthropic_adapter`: `import cos.mcp_server.server as server_mod`; assert `"AnthropicAdapter" not in dir(server_mod)` — validates the clean boundary

- [x] Task 6: Update `tests/mcp_server/test_server.py` (AC: #4)
  - [x] In `_patch_server`, remove: `monkeypatch.setattr(server, "AnthropicAdapter", MagicMock(return_value=MagicMock()), raising=False)`
  - [x] In `_patch_server`, add: `monkeypatch.setattr(server, "make_llm_adapter", MagicMock(return_value=MagicMock()))`
  - [x] `raising=False` is NOT needed for `make_llm_adapter` — it will be in server's namespace after the refactor
  - [x] All existing server tests must continue to pass; no logic changes

## Dev Notes

### What Exists at End of Story 4.3

The following are complete and MUST NOT be modified:

- `src/cos/llm/adapter.py` — `LLMAdapter` Protocol with `complete(prompt, context) -> str`
- `src/cos/llm/anthropic.py` — `AnthropicAdapter` (implements `LLMAdapter`) and `HttpTransportConfig`
- `src/cos/ingestion/embedder.py` — `embed()` function, `_embed_via_voyage()`, `VoyageTransportConfig`, `EmbeddingError`, `EmbeddingResult`
- `src/cos/mcp_server/server.py` — `_startup_sequence`, `make_llm_adapter` is NOT yet imported; `AnthropicAdapter` is currently imported at line 14
- `role_packs/chro.yaml` — reference role pack, do not modify
- `src/cos/rolepack/loader.py` — `RolePackConfig` (8 required fields), `load()` — do not modify
- All tests pass; baseline count: 140

### Task 2: Full `factory.py` Implementation

The transport fallback logic to move from `server.py` into `factory.py`:

```python
from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter


def make_llm_adapter(config: CosConfig) -> LLMAdapter:
    if config.llm.provider == "anthropic":
        from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig
        return AnthropicAdapter(
            model=config.llm.model,
            api_key=config.llm.api_key.get_secret_value(),
            transport=HttpTransportConfig(
                ca_bundle_path=(
                    config.llm.ca_bundle_path
                    if config.llm.ca_bundle_path is not None
                    else config.embedding.ca_bundle_path
                ),
                proxy_url=(
                    config.llm.proxy_url
                    if config.llm.proxy_url is not None
                    else config.embedding.proxy_url
                ),
                trust_env=(
                    config.llm.trust_env
                    if config.llm.trust_env is not None
                    else config.embedding.trust_env
                ),
            ),
        )
    raise SystemExit(
        f"Unsupported LLM provider: {config.llm.provider!r}\n"
        "Add a new adapter in cos/llm/ and register it in cos/llm/factory.py."
    )
```

Note: lazy imports (`from cos.llm.anthropic import ...` inside the `if` block) keep the Anthropic dependency from loading when a future provider is used. This is the established extensibility contract.

### Task 3: `server.py` Changes — Exact Lines

**Remove** (line 14 currently):
```python
from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig
```

**Add** (in the imports block):
```python
from cos.llm.factory import make_llm_adapter
```

**Replace** the `adapter = AnthropicAdapter(...)` block at lines 122–142:

```python
# BEFORE (remove all of this):
adapter = AnthropicAdapter(
    model=config.llm.model,
    api_key=config.llm.api_key.get_secret_value(),
    transport=HttpTransportConfig(
        ca_bundle_path=(
            config.llm.ca_bundle_path
            if config.llm.ca_bundle_path is not None
            else config.embedding.ca_bundle_path
        ),
        proxy_url=(
            config.llm.proxy_url
            if config.llm.proxy_url is not None
            else config.embedding.proxy_url
        ),
        trust_env=(
            config.llm.trust_env
            if config.llm.trust_env is not None
            else config.embedding.trust_env
        ),
    ),
)

# AFTER (one line):
adapter = make_llm_adapter(config)
```

The `_retrieval_service = RetrievalService(config=config, pool=_pool, llm_adapter=adapter)` line immediately after does NOT change.

### Task 4: `embedder.py` Registry Change — Exact Location

The `_EMBED_PROVIDERS` dict must be defined AFTER `_embed_via_voyage` (so the function exists when the dict is built). Insert after the closing of the `_embed_via_voyage` function (currently ends around line 69):

```python
_EMBED_PROVIDERS: dict[str, Any] = {
    "anthropic": _embed_via_voyage,
}
```

Then in `embed()`, replace:
```python
# BEFORE (lines 40–43):
    if provider != "anthropic":
        raise EmbeddingError(f"Unsupported embedding provider: {provider!r}")

    return await _embed_via_voyage(chunks, model, api_key, transport)

# AFTER:
    fn = _EMBED_PROVIDERS.get(provider)
    if fn is None:
        raise EmbeddingError(f"Unsupported embedding provider: {provider!r}")
    return await fn(chunks, model, api_key, transport)
```

The `Any` import is already present (`from typing import Any`) — no new imports needed.

### Task 5: Test File Location

Create `tests/llm/test_factory.py`. Note `tests/llm/__init__.py` already exists — no new `__init__.py` needed.

The test for `test_make_llm_adapter_anthropic_returns_llm_adapter` uses a `SimpleNamespace` config (same pattern as `test_server.py::_make_config`). The factory calls `AnthropicAdapter(model=..., api_key=..., transport=...)` which tries to build an `httpx.AsyncClient` only if transport overrides are present. With all transport fields as `None`/`False`, no external calls are made — the instantiation succeeds locally.

### Architecture Boundary — What This Story Does NOT Touch

- `src/cos/services/retrieval.py` — no changes; uses `LLMAdapter` protocol, never references `AnthropicAdapter`
- `src/cos/services/ingestion.py` — no changes
- `src/cos/ingestion/pipeline.py` — no changes; `embed()` already reads provider/model from config
- `src/cos/mcp_server/tools.py` — no changes
- `src/cos/rolepack/loader.py` — no changes
- `src/cos/config.py` — no changes; `LLMConfig.provider` and `EmbeddingConfig.provider` already exist as fields

### Test Count

Before Story 4.4: 140 tests.

Changes:
- `tests/llm/test_factory.py`: +3 (`test_make_llm_adapter_anthropic_returns_llm_adapter`, `test_make_llm_adapter_unknown_provider_raises_system_exit`, `test_server_module_does_not_expose_anthropic_adapter`)
- `tests/mcp_server/test_server.py`: mock name change only (±0 tests)

Expected total: 143 tests. Run `uv run pytest` to confirm all pass.

### Verification Commands

```bash
uv run pytest tests/llm/test_factory.py tests/mcp_server/test_server.py tests/ingestion/test_embedder.py -q
uv run pytest -q
uv run ruff check src/cos/llm/factory.py src/cos/mcp_server/server.py src/cos/ingestion/embedder.py
uv run mypy src/cos/llm/factory.py src/cos/mcp_server/server.py src/cos/ingestion/embedder.py
```

### References

- `LLMAdapter` protocol: `src/cos/llm/adapter.py:1–7`
- `AnthropicAdapter` + `HttpTransportConfig`: `src/cos/llm/anthropic.py`
- Current `AnthropicAdapter` instantiation in server (to move): `src/cos/mcp_server/server.py:122–142`
- Existing `AnthropicAdapter` import in server (to remove): `src/cos/mcp_server/server.py:14`
- Embedder `embed()` function: `src/cos/ingestion/embedder.py:31–43`
- `_embed_via_voyage` function: `src/cos/ingestion/embedder.py:46–69`
- `_patch_server` mock to update: `tests/mcp_server/test_server.py:76` (`AnthropicAdapter` monkeypatch line)
- Existing LLM test file to place factory tests alongside: `tests/llm/test_anthropic_adapter.py`
- `RolePackConfig` schema: 8 required fields in `src/cos/rolepack/loader.py`

## Dev Agent Record

### Agent Model Used

gpt-5

### Completion Notes List

- Added `role_packs/enterprise_architect.yaml` with all required role-pack fields, a distinct enterprise architecture domain, and `output_channels: [local]`.
- Added `src/cos/llm/factory.py` with `make_llm_adapter(config)` so provider selection is configuration-driven and `server.py` no longer imports `AnthropicAdapter` directly.
- Refactored `src/cos/ingestion/embedder.py` to resolve embedding providers through a registry while preserving existing runtime behavior and tightening types for `mypy`.
- Added factory boundary tests and updated MCP server tests to patch `make_llm_adapter` instead of a concrete Anthropic class.
- Validation completed with `uv run pytest tests/llm/test_factory.py tests/mcp_server/test_server.py tests/ingestion/test_embedder.py -q`, `uv run pytest -q`, `uv run ruff check ...`, and `uv run mypy ...` all passing.

### File List

- role_packs/enterprise_architect.yaml
- src/cos/llm/factory.py
- src/cos/mcp_server/server.py
- src/cos/ingestion/embedder.py
- tests/llm/test_factory.py
- tests/mcp_server/test_server.py
- _bmad-output/implementation-artifacts/4-4-role-pack-and-provider-portability.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-04-29: Added configuration-driven LLM adapter factory, embedder provider registry, enterprise architect role pack, and supporting tests; story completed and moved to review.

### Review Findings

- [x] [Review][Patch] `_EMBED_PROVIDERS` annotated as `dict[str, EmbedProvider]` — spec and Dev Notes require `dict[str, Any]` [src/cos/ingestion/embedder.py:79]
- [x] [Review][Patch] Unnecessary string forward reference in `EmbedProvider` type alias — `VoyageTransportConfig` is defined before the alias, no quotes needed [src/cos/ingestion/embedder.py:32-35]
- [x] [Review][Defer] Silent LLM→embedding transport fallback has no log or comment — pre-existing behavior moved verbatim from server.py [src/cos/llm/factory.py:13-25]
- [x] [Review][Defer] `enterprise_architect.yaml` `active_workflows` references unregistered identifiers — pre-existing schema design; same gap exists in chro.yaml [role_packs/enterprise_architect.yaml:39-43]
- [x] [Review][Defer] Provider string not stripped/validated — whitespace or empty string reaches the factory/registry check uncaught; pre-existing concern for embedder [src/cos/llm/factory.py:6, src/cos/ingestion/embedder.py:47]
- [x] [Review][Defer] Embedder registry doesn't enforce error-handling contract for future provider functions — architectural concern for when a second provider is added [src/cos/ingestion/embedder.py:47-50]
- [x] [Review][Defer] `isinstance(result, LLMAdapter)` only checks presence, not method signature — runtime_checkable Protocol limitation [tests/llm/test_factory.py:31]
