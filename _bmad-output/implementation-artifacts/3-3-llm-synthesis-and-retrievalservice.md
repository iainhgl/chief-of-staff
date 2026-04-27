# Story 3.3: LLM Synthesis & RetrievalService

Status: done

## Story

As a user,
I want retrieved document chunks to be synthesised into a coherent answer that matches my role's voice and style,
So that I receive a readable, contextually appropriate response — not a raw list of matching text fragments.

## Acceptance Criteria

1. **Given** `AnthropicAdapter.complete(messages, config)` is called with a prompt containing retrieved chunks and a query,
   **When** the Claude API is called,
   **Then** the request is made over HTTPS using the API key from `CosConfig` — the key is never written to logs, responses, or any observable output.

2. **Given** a successful API response,
   **When** `AnthropicAdapter` returns,
   **Then** it returns a `str` containing the synthesised answer — conforming to the `LLMAdapter` protocol contract defined in Epic 1.

3. **Given** `RetrievalService.query(text, role_pack)` is called,
   **When** it executes the full pipeline,
   **Then** it calls `search.py` → `citations.py` → `LLMAdapter.complete()` in sequence, and returns a `CitedResponse` containing both the synthesised answer and the full `CitedResults` used to generate it.

4. **Given** the active `RolePackConfig` includes a tone definition (even the stub default),
   **When** the synthesis prompt is constructed,
   **Then** the tone instruction is included in the prompt passed to the LLM — the response style reflects it.

5. **Given** the user's query implies a specific output type — a question ("what does..."), a comparison ("compare X and Y"), a summary request ("summarise..."), or a briefing request ("brief me on..."),
   **When** the synthesised response is returned,
   **Then** it is shaped appropriately for that output type — a question gets a direct answer, a comparison gets a structured comparison, a summary gets a concise synthesis — confirming FR17 is addressed through prompt construction, not separate code paths.

6. **Given** the user's query requests a draft document or communication (e.g. "draft a briefing note on...", "write a first draft of..."),
   **When** the synthesised response is returned,
   **Then** it is structured as a draft — with an appropriate document shape (heading, body, sign-off where relevant) rather than a conversational answer — and the synthesis prompt includes an explicit draft instruction derived from the query type.

7. **Given** the user's query requests prioritisation (e.g. "prioritise these initiatives...", "rank the following by..."),
   **When** the synthesised response is returned,
   **Then** it is structured as a ranked or ordered list with a brief rationale for each item's position — not a flat summary — and the synthesis prompt includes an explicit prioritisation instruction derived from the query type.

8. **Given** the Claude API is unavailable or returns an error,
   **When** synthesis is attempted,
   **Then** `RetrievalService` catches the error, logs a structured entry with `component: "retrieval"`, and returns a `CitedResponse` with `answer: null` and the `CitedResults` intact — the caller can handle the degraded response.

## Tasks / Subtasks

- [x] Task 1: Add `anthropic` SDK dependency (AC: #1, #2)
  - [x] Add `anthropic>=0.50.0` to `[project] dependencies` in `pyproject.toml`
  - [x] Run `uv add anthropic` to install and update `uv.lock`
  - [x] Verify `uv run python -c "import anthropic; print(anthropic.__version__)"` succeeds

- [x] Task 2: Add `CitedResponse` to `src/cos/retrieval/citations.py` (AC: #3, #8)
  - [x] Append `CitedResponse` as a `@dataclass` after the existing `CitedChunk` and `CitedResults` definitions
  - [x] Fields: `answer: str | None`, `citations: CitedResults`
  - [x] No changes to `CitedChunk`, `CitedResults`, or `format_citations` — additive only
  - [x] Example:
    ```python
    @dataclass
    class CitedResponse:
        answer: str | None
        citations: CitedResults
    ```

- [x] Task 3: Implement `AnthropicAdapter` in `src/cos/llm/anthropic.py` (AC: #1, #2)
  - [x] Replace the entire stub file
  - [x] Add `__init__(self, model: str, api_key: str) -> None`:
    - Store `self._model = model`
    - Instantiate `self._client = anthropic.AsyncAnthropic(api_key=api_key)`
    - Do NOT store `api_key` as an instance attribute — pass it directly to `AsyncAnthropic`
  - [x] Implement `complete(self, prompt: str, context: list[str]) -> str`:
    - Build `context_text`: numbered list of context chunks, e.g. `[1] {chunk}\n\n[2] {chunk}`
    - If `context` is empty, `context_text = "(no context provided)"`
    - Build `user_message = f"Context:\n{context_text}\n\nInstruction: {prompt}"`
    - Call `await self._client.messages.create(model=self._model, max_tokens=2048, system=SYSTEM_PROMPT, messages=[{"role": "user", "content": user_message}])`
    - Return `message.content[0].text`
  - [x] Define `SYSTEM_PROMPT` as a module-level constant: `"You are a precise knowledge assistant. Answer based solely on the context provided. If the context does not contain relevant information, say so clearly. Do not fabricate sources or invent information."`
  - [x] Class must satisfy `isinstance(adapter, LLMAdapter)` — the protocol is `@runtime_checkable`
  - [x] No bare `print()` calls; no logging of `api_key` or response content at DEBUG level

- [x] Task 4: Implement `RetrievalService.query()` in `src/cos/services/retrieval.py` (AC: #3–#8)
  - [x] Replace the entire file
  - [x] Updated `__init__` signature: `def __init__(self, config: CosConfig, pool: AsyncConnectionPool, llm_adapter: LLMAdapter) -> None`
    - Store `self._config = config`, `self._pool = pool`, `self._llm_adapter = llm_adapter`
  - [x] Implement `async def query(self, text: str, role_pack: Any) -> CitedResponse`:
    - Open pool connection: `async with self._pool.connection() as conn:`
    - Call `cited_results = await hybrid_search(text, conn, self._config, role_pack)`
    - If `cited_results` is empty: return `CitedResponse(answer="No relevant content found in the knowledge base.", citations=[])`
    - Build `prompt` string using `_build_synthesis_prompt(text, role_pack)` (see below)
    - Build `context = [c.content for c in cited_results]`
    - Call synthesis: `answer = await self._llm_adapter.complete(prompt=prompt, context=context)`
    - Return `CitedResponse(answer=answer, citations=cited_results)`
    - Wrap synthesis in `try/except Exception as exc`: on error, log structured JSON with `component: "retrieval"`, return `CitedResponse(answer=None, citations=cited_results)`
  - [x] Add module-level helper `_detect_query_type(text: str) -> str`:
    - `t = text.lower()`
    - Draft: `t.startswith(("draft ", "write a draft", "write a first draft"))` → return `"draft"`
    - Prioritise: `any(kw in t for kw in ("prioritise", "prioritize", "rank the following", "rank these", "rank by"))` → return `"prioritise"`
    - Compare: `any(kw in t for kw in ("compare ", "comparison between", "differences between", " vs ", " versus "))` → return `"compare"`
    - Summarise: `any(kw in t for kw in ("summarise", "summarize", "summary of", "brief me on", "brief on"))` → return `"summarise"`
    - Default: return `"question"`
  - [x] Add module-level constant `_TASK_INSTRUCTIONS: dict[str, str]`:
    ```python
    _TASK_INSTRUCTIONS = {
        "draft": "Structure your response as a formal document: title, body paragraphs, and a conclusion or sign-off where appropriate.",
        "prioritise": "Structure your response as a ranked list. For each item, give its rank position and a brief rationale.",
        "compare": "Structure your response as a structured comparison, covering key differences and similarities clearly.",
        "summarise": "Provide a concise synthesis of the key points from the provided context.",
        "question": "",
    }
    ```
  - [x] Add module-level helper `_build_synthesis_prompt(text: str, role_pack: Any) -> str`:
    - `tone = getattr(role_pack, "tone", "") if role_pack is not None else ""`
    - `query_type = _detect_query_type(text)`
    - `task_instruction = _TASK_INSTRUCTIONS[query_type]`
    - Build parts list: append tone (if non-empty), append query, append task_instruction (if non-empty)
    - Return `"\n".join(parts)`
  - [x] Imports required:
    ```python
    import json
    import logging
    from datetime import datetime, timezone
    from typing import Any
    from psycopg_pool import AsyncConnectionPool
    from cos.config import CosConfig
    from cos.llm.adapter import LLMAdapter
    from cos.retrieval.citations import CitedResponse, CitedResults
    from cos.retrieval.search import hybrid_search
    ```

- [x] Task 5: Create `tests/llm/__init__.py` and `tests/llm/test_anthropic_adapter.py` (AC: #1, #2)
  - [x] Create `tests/llm/__init__.py` (empty file)
  - [x] Create `tests/llm/test_anthropic_adapter.py` with these four tests:
    - [x] `test_anthropic_adapter_conforms_to_llm_adapter_protocol`:
      - Construct `AnthropicAdapter(model="claude-3-haiku-20240307", api_key="test")`
      - Assert `isinstance(adapter, LLMAdapter)` is `True`
    - [x] `test_complete_returns_string_from_api` (mock API call):
      - `patch.object(adapter._client.messages, "create", new=AsyncMock(return_value=mock_response))`
      - Call `adapter.complete("what is X?", ["chunk one", "chunk two"])`
      - Assert result equals `mock_response.content[0].text` (a `str`)
    - [x] `test_complete_api_key_never_in_log_output`:
      - Use a recognisable sentinel key: `api_key = "sk-sentinel-9999"`
      - Call `complete()` with mocked API
      - Assert `api_key not in caplog.text` (use `caplog.at_level(logging.DEBUG)`)
    - [x] `test_complete_includes_context_chunks_in_user_message`:
      - Mock API call, capture `call_args`
      - Assert both `"first chunk"` and `"second chunk"` appear in the `content` of `messages[0]`
  - [x] No conftest required for `tests/llm/` — all tests use mocks only

- [x] Task 6: Replace stub test in `tests/services/test_retrieval_service.py` (AC: #3, #5–#8)
  - [x] Delete `test_query_not_implemented` — it tests the old stub
  - [x] Add a `mock_pool` fixture (not autouse):
    ```python
    @pytest.fixture
    def mock_pool() -> MagicMock:
        mock_conn = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        pool = MagicMock()
        pool.connection.return_value = cm
        return pool
    ```
  - [x] Add a `mock_llm_adapter` fixture:
    ```python
    @pytest.fixture
    def mock_llm_adapter() -> AsyncMock:
        adapter = AsyncMock(spec=LLMAdapter)
        adapter.complete = AsyncMock(return_value="synthesised answer")
        return adapter
    ```
  - [x] Write four tests (all `@pytest.mark.asyncio`, all mock-only — no real DB needed):
    - [x] `test_query_returns_cited_response_with_answer`: patch `hybrid_search` returning one `CitedChunk`; assert `CitedResponse` with `answer == "synthesised answer"` and `citations` has 1 item
    - [x] `test_query_empty_search_returns_no_content_found`: patch `hybrid_search` returning `[]`; assert `CitedResponse.answer` contains `"no relevant content"` (case-insensitive); assert `mock_llm_adapter.complete` not called
    - [x] `test_query_llm_error_returns_degraded_response`: `adapter.complete` raises `Exception("API unavailable")`; assert `CitedResponse.answer is None` and `citations` contains the result from search
    - [x] `test_query_passes_chunk_contents_to_llm_adapter`: patch `hybrid_search` returning a `CitedChunk` with `content="specific chunk text"`; after `query()`, assert `mock_llm_adapter.complete` was called with `context` containing `"specific chunk text"`
  - [x] No DB fixtures needed — all tests use `mock_pool`; remove `clean_tables` autouse from these tests if present

## Dev Notes

### What Is Already Done — Do Not Re-Implement

**`src/cos/retrieval/search.py`** is fully implemented (`hybrid_search()` — Story 3.1). Do not modify.

**`src/cos/retrieval/citations.py`** is fully implemented (`CitedChunk`, `CitedResults`, `format_citations` — Story 3.1). Task 2 adds `CitedResponse` only — do not change existing code.

**`src/cos/llm/adapter.py`** defines the `LLMAdapter` protocol as:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMAdapter(Protocol):
    async def complete(self, prompt: str, context: list[str]) -> str:
        ...
```
Do not modify. The `@runtime_checkable` decorator enables `isinstance(adapter, LLMAdapter)` checks.

**`src/cos/output/router.py`**, **`src/cos/output/channels/local.py`**, **`src/cos/services/output.py`** — all implemented in Story 3.2. Do not touch.

**`src/cos/mcp_server/server.py`** has `_config` and `_output_router` module-level globals and `get_config()` / `get_output_router()` getters. Story 3.4 will add pool and retrieval service globals — do not pre-empt that in this story.

**`src/cos/mcp_server/tools.py`** — `retrieve` tool is still a stub returning `"Not yet implemented"`. Do not wire it in this story. Story 3.4 does that.

### `anthropic` SDK — Currently Missing from `pyproject.toml`

This is a known deferred item from Story 1.1 code review: "anthropic SDK not declared in pyproject.toml — add when AnthropicAdapter is implemented in Story 3.3".

Run `uv add anthropic` — this updates both `pyproject.toml` and `uv.lock`. The SDK version as of April 2026 is `>=0.50.0`. Confirm with `uv run python -c "import anthropic; print(anthropic.__version__)"`.

### `AnthropicAdapter` — SDK Usage Pattern

```python
import anthropic

class AnthropicAdapter:
    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, prompt: str, context: list[str]) -> str:
        context_text = "\n\n".join(
            f"[{i + 1}] {chunk}" for i, chunk in enumerate(context)
        ) or "(no context provided)"
        user_message = f"Context:\n{context_text}\n\nInstruction: {prompt}"
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
```

`message.content` is a list of `ContentBlock` objects. For text responses, `message.content[0].text` is the string. This is stable across `anthropic` SDK `>=0.20`.

**Key: never log `api_key`.** The `AsyncAnthropic` client stores it internally; never access `self._client.api_key` in logs.

### `CitedResponse` — Where It Lives

`CitedResponse` belongs in `src/cos/retrieval/citations.py` alongside `CitedChunk` and `CitedResults`. Story 3.4's MCP tools will import it from there. Keep it as a `@dataclass`.

### `RetrievalService.query()` — Constructor Change

The current stub is:
```python
def __init__(self, config: CosConfig, pool: AsyncConnectionPool) -> None:
```

This story changes it to:
```python
def __init__(self, config: CosConfig, pool: AsyncConnectionPool, llm_adapter: LLMAdapter) -> None:
```

**Impact on existing test:** `tests/services/test_retrieval_service.py` has one test `test_query_not_implemented` that constructs `RetrievalService(config=..., pool=MagicMock())`. Delete this test entirely and replace with the four new tests (Task 6). The stub test is intentionally removed — it tested the old `NotImplementedError` stub.

**Impact on server.py:** `server.py` does not construct `RetrievalService` yet (that happens in Story 3.4). No change to `server.py` in this story.

### `RetrievalService.query()` — Full Implementation Pattern

```python
async def query(self, text: str, role_pack: Any) -> CitedResponse:
    async with self._pool.connection() as conn:
        cited_results = await hybrid_search(text, conn, self._config, role_pack)

    if not cited_results:
        return CitedResponse(
            answer="No relevant content found in the knowledge base.",
            citations=[],
        )

    prompt = _build_synthesis_prompt(text, role_pack)
    context = [c.content for c in cited_results]

    try:
        answer = await self._llm_adapter.complete(prompt=prompt, context=context)
    except Exception as exc:
        logging.error(
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "component": "retrieval",
                "message": "LLM synthesis failed",
                "error": str(exc),
            })
        )
        return CitedResponse(answer=None, citations=cited_results)

    return CitedResponse(answer=answer, citations=cited_results)
```

### Tone Handling — Phase 1 Notes

`RolePackConfig` in `src/cos/rolepack/loader.py` is currently:
```python
class RolePackConfig(BaseModel):
    """Role pack configuration — schema defined in Story 4.1."""
    pass
```

There is no `tone` field. `_build_synthesis_prompt()` uses `getattr(role_pack, "tone", "")` — returns `""` safely for the Phase 1 stub. The structure is in place for Epic 4 to add the `tone` field to `RolePackConfig` without changing `RetrievalService`.

The AC says "tone instruction is included in the system prompt passed to the LLM." For Phase 1 (empty `RolePackConfig`), tone is `""` and is omitted from the prompt entirely. When Epic 4 activates a real role pack, `tone` will flow through `_build_synthesis_prompt()` automatically. Note: in the current design, tone ends up in the user message (not the Anthropic `system` parameter) since `LLMAdapter.complete(prompt, context)` has no `system` parameter. This is a Phase 1 pragmatic choice documented here. Epic 4 or a future story can extend the protocol if a distinct system-prompt channel is needed.

### Query Type Detection — Implementation

```python
def _detect_query_type(text: str) -> str:
    t = text.lower()
    if t.startswith(("draft ", "write a draft", "write a first draft")):
        return "draft"
    if any(kw in t for kw in ("prioritise", "prioritize", "rank the following", "rank these", "rank by")):
        return "prioritise"
    if any(kw in t for kw in ("compare ", "comparison between", "differences between", " vs ", " versus ")):
        return "compare"
    if any(kw in t for kw in ("summarise", "summarize", "summary of", "brief me on", "brief on")):
        return "summarise"
    return "question"
```

Detection runs on the lowercased text. Default is `"question"` — any query not matching a pattern gets a direct-answer instruction (empty string = no additional framing).

### Test Patterns for `tests/llm/test_anthropic_adapter.py`

Tests are pure unit tests with mocked Anthropic API — no DB, no conftest required.

Mocking pattern:
```python
from unittest.mock import AsyncMock, MagicMock, patch

async def test_complete_returns_string_from_api() -> None:
    adapter = AnthropicAdapter(model="claude-3-haiku-20240307", api_key="test")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="synthesised answer")]
    with patch.object(adapter._client.messages, "create", new=AsyncMock(return_value=mock_response)):
        result = await adapter.complete("what is X?", ["chunk one", "chunk two"])
    assert result == "synthesised answer"
    assert isinstance(result, str)
```

Key: `patch.object(adapter._client.messages, "create", ...)` patches the specific client instance — no module-level patch needed.

### Test Patterns for `tests/services/test_retrieval_service.py`

The `mock_pool` fixture must set up the async context manager correctly:

```python
@pytest.fixture
def mock_pool() -> MagicMock:
    mock_conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = cm
    return pool
```

`hybrid_search` is patched at the module path `cos.services.retrieval.hybrid_search` (since `services/retrieval.py` imports it as `from cos.retrieval.search import hybrid_search`).

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pathlib import Path
from conftest import make_test_config
from cos.services.retrieval import RetrievalService
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.llm.adapter import LLMAdapter

@pytest.fixture
def mock_pool() -> MagicMock:
    mock_conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.connection.return_value = cm
    return pool

@pytest.fixture
def mock_llm_adapter() -> AsyncMock:
    adapter = AsyncMock(spec=LLMAdapter)
    adapter.complete = AsyncMock(return_value="synthesised answer")
    return adapter

def _make_chunk() -> CitedChunk:
    return CitedChunk(
        content="workforce segmentation framework",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_path="/test/hr-framework.md",
        chunk_index=0,
        score=0.9,
    )

@pytest.mark.asyncio
async def test_query_returns_cited_response_with_answer(
    tmp_path: Path, mock_pool: MagicMock, mock_llm_adapter: AsyncMock
) -> None:
    svc = RetrievalService(
        config=make_test_config(tmp_path), pool=mock_pool, llm_adapter=mock_llm_adapter
    )
    with patch("cos.services.retrieval.hybrid_search", new=AsyncMock(return_value=[_make_chunk()])):
        response = await svc.query("what is workforce segmentation?", role_pack=None)
    assert isinstance(response, CitedResponse)
    assert response.answer == "synthesised answer"
    assert len(response.citations) == 1

@pytest.mark.asyncio
async def test_query_empty_search_returns_no_content_found(
    tmp_path: Path, mock_pool: MagicMock, mock_llm_adapter: AsyncMock
) -> None:
    svc = RetrievalService(
        config=make_test_config(tmp_path), pool=mock_pool, llm_adapter=mock_llm_adapter
    )
    with patch("cos.services.retrieval.hybrid_search", new=AsyncMock(return_value=[])):
        response = await svc.query("unknown topic", role_pack=None)
    assert "no relevant content" in (response.answer or "").lower()
    assert response.citations == []
    mock_llm_adapter.complete.assert_not_called()

@pytest.mark.asyncio
async def test_query_llm_error_returns_degraded_response(
    tmp_path: Path, mock_pool: MagicMock
) -> None:
    failing_adapter = AsyncMock(spec=LLMAdapter)
    failing_adapter.complete = AsyncMock(side_effect=Exception("API unavailable"))
    svc = RetrievalService(
        config=make_test_config(tmp_path), pool=mock_pool, llm_adapter=failing_adapter
    )
    with patch("cos.services.retrieval.hybrid_search", new=AsyncMock(return_value=[_make_chunk()])):
        response = await svc.query("what is X?", role_pack=None)
    assert response.answer is None
    assert len(response.citations) == 1

@pytest.mark.asyncio
async def test_query_passes_chunk_contents_to_llm_adapter(
    tmp_path: Path, mock_pool: MagicMock, mock_llm_adapter: AsyncMock
) -> None:
    chunk = CitedChunk(
        content="specific chunk content for testing",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_path="/test/doc.md",
        chunk_index=0,
        score=0.9,
    )
    svc = RetrievalService(
        config=make_test_config(tmp_path), pool=mock_pool, llm_adapter=mock_llm_adapter
    )
    with patch("cos.services.retrieval.hybrid_search", new=AsyncMock(return_value=[chunk])):
        await svc.query("what is X?", role_pack=None)
    call_kwargs = mock_llm_adapter.complete.call_args
    context_arg = call_kwargs.kwargs.get("context") or call_kwargs.args[1]
    assert "specific chunk content for testing" in context_arg
```

### `tests/services/conftest.py` — Do Not Import It

`tests/services/conftest.py` has `clean_tables` (autouse fixture requiring `migrated_db`) and `mock_embed` (used by ingestion service tests). The new `test_retrieval_service.py` tests use mock pool and mock adapter — they do NOT need `migrated_db`, `clean_tables`, or `mock_embed`. These autouse fixtures will still apply because conftest is loaded automatically. Verify that `clean_tables` autouse doesn't break the new tests (it should be harmless since it only truncates tables — which won't fail even if the DB isn't running, as long as `migrated_db` runs first).

Actually: `clean_tables` depends on `migrated_db` fixture. If the test database isn't running, conftest autouse will fail. To avoid this, consider marking the new retrieval service tests with `@pytest.mark.no_db` or run them with `docker compose up -d postgres tika` as documented.

### Story 3.4 Context — What It Will Wire

Story 3.4 will:
1. Add `psycopg_pool.AsyncConnectionPool` creation to `server.py` `_startup_sequence`
2. Create `AnthropicAdapter(model=config.llm.model, api_key=config.llm.api_key.get_secret_value())`
3. Construct `RetrievalService(config=config, pool=pool, llm_adapter=adapter)` and store as `_retrieval_service` module global
4. Wire `retrieve` MCP tool to call `_retrieval_service.query()`

Do not pre-implement any of this in Story 3.3.

### Architecture Boundary Reminder

`cos.mcp_server` and `cos.cli` import only from `cos.services.*`. The new `RetrievalService.query()` uses `from cos.retrieval.search import hybrid_search` — this is correct because `cos.services` imports from implementation modules. `cos.retrieval.citations.CitedResponse` is also importable from services — that is also correct.

The `anthropic` library call lives only in `cos/llm/anthropic.py`. No other module touches the `anthropic` SDK directly.

### Files to Create / Modify

| File | Action | Notes |
|------|--------|-------|
| `pyproject.toml` | Modify | Add `anthropic>=0.50.0` to dependencies |
| `src/cos/retrieval/citations.py` | Modify | Add `CitedResponse` dataclass — additive only |
| `src/cos/llm/anthropic.py` | Replace | Full `AnthropicAdapter` implementation |
| `src/cos/services/retrieval.py` | Replace | Full `RetrievalService.query()` implementation |
| `tests/llm/__init__.py` | Create | Empty |
| `tests/llm/test_anthropic_adapter.py` | Create | 4 unit tests — mock Anthropic API |
| `tests/services/test_retrieval_service.py` | Replace | 4 real tests replacing single stub test |

Do NOT modify: `src/cos/llm/adapter.py`, `src/cos/retrieval/search.py`, `src/cos/mcp_server/tools.py`, `src/cos/mcp_server/server.py`, `src/cos/output/router.py`, `tests/output/test_router.py`, `tests/services/conftest.py`.

### Debug Commands

```bash
# Run new tests only (no DB needed — all mocked)
uv run pytest tests/llm/test_anthropic_adapter.py tests/services/test_retrieval_service.py -v

# Full test suite (requires docker compose up -d postgres tika)
uv run pytest tests/ -q

# Lint and type-check modified files
uv run ruff check src/cos/llm/anthropic.py src/cos/services/retrieval.py src/cos/retrieval/citations.py tests/llm/test_anthropic_adapter.py tests/services/test_retrieval_service.py
uv run mypy src/cos/llm/anthropic.py src/cos/services/retrieval.py src/cos/retrieval/citations.py
```

## Dev Agent Record

### Agent Model Used

gpt-5.4

### Debug Log References

- `uv add anthropic`
- `uv run python -c "import anthropic; print(anthropic.__version__)"`
- `uv run pytest tests/llm/test_anthropic_adapter.py tests/services/test_retrieval_service.py -q`
- `uv run ruff check src/cos/llm/anthropic.py src/cos/services/retrieval.py src/cos/retrieval/citations.py tests/llm/test_anthropic_adapter.py tests/services/test_retrieval_service.py`
- `uv run mypy src/cos/llm/anthropic.py src/cos/services/retrieval.py src/cos/retrieval/citations.py`
- `uv run pytest tests/ -q`

### Completion Notes List

- Added the `anthropic` SDK dependency and verified the installed version through `uv run`.
- Implemented `CitedResponse`, a production `AnthropicAdapter`, and a fully wired `RetrievalService.query()` pipeline with query-type prompt shaping and degraded-error handling.
- Added mocked adapter and retrieval service coverage, including tone injection, draft/compare/summarise/prioritise prompt instructions, and no-DB service test isolation.
- Validated the story with focused tests, Ruff, mypy, and the full repository test suite (`107 passed, 1 skipped`).

### File List

- `pyproject.toml`
- `uv.lock`
- `src/cos/retrieval/citations.py`
- `src/cos/llm/anthropic.py`
- `src/cos/services/retrieval.py`
- `tests/llm/__init__.py`
- `tests/llm/test_anthropic_adapter.py`
- `tests/services/test_retrieval_service.py`

### Review Findings

- [x] [Review][Patch] LLM error handler uses `logging.error()` — stack trace lost on synthesis failure [`src/cos/services/retrieval.py`]
- [x] [Review][Defer] No test for `RuntimeError` path when `message.content` has no text block [`tests/llm/test_anthropic_adapter.py`] — deferred, not in spec scope; low-probability production scenario

## Change Log

- 2026-04-27: Story created.
- 2026-04-27: Implemented Anthropic-backed synthesis, retrieval prompt shaping, and test coverage for Story 3.3.
- 2026-04-27: Code review complete — 1 patch, 1 deferred, 8 dismissed.
