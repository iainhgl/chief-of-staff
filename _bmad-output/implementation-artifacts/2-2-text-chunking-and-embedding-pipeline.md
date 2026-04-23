# Story 2.2: Text Chunking & Embedding Pipeline

Status: done

## Story

As an operator,
I want extracted document text to be split into appropriately sized chunks and converted to vector embeddings,
So that the knowledge base supports both semantic and keyword search across all ingested content.

## Acceptance Criteria

1. **Given** a Markdown text string is passed to `chunker.py`,
   **When** chunking runs with the default configuration,
   **Then** the text is split into chunks of approximately 1024 tokens with a 100-token overlap between adjacent chunks, and each chunk carries its `chunk_index` and `token_count`.

2. **Given** a document shorter than 1024 tokens,
   **When** chunking runs,
   **Then** it produces a single chunk containing the full text — no empty or near-empty padding chunks are created.

3. **Given** a list of text chunks is passed to `embedder.py`,
   **When** the embedding provider is called,
   **Then** each chunk is converted to a vector using the provider and model specified in `CosConfig`, and the result carries the `model` and `provider` fields alongside the vector.

4. **Given** `CosConfig` specifies a different embedding model,
   **When** the embedder is called,
   **Then** it uses the configured model without any code changes — only the config value changes.

5. **Given** the embedding provider API is unavailable,
   **When** embedding is attempted,
   **Then** the embedder raises a structured `EmbeddingError` that propagates to the service layer — it does not return zero-vectors or silently degrade.

## Tasks / Subtasks

- [x] Task 1: Add `ChunkingConfig` to `CosConfig` and update `config.yaml.example` (AC: #1)
  - [x] Add `class ChunkingConfig(BaseModel): chunk_size: int = 1024; chunk_overlap: int = 100` to `config.py` after `StorageConfig`, before `CosConfig`
  - [x] Add `chunking: ChunkingConfig = ChunkingConfig()` field to `CosConfig`
  - [x] Add `chunking:` section to `config.yaml.example` after the `storage:` block (see Dev Notes for wording)
  - [x] Add `test_chunking_config_defaults` to `tests/test_config.py`: load config without a `chunking:` block and assert `config.chunking.chunk_size == 1024` and `config.chunking.chunk_overlap == 100`

- [x] Task 2: Add `tiktoken` and `voyageai` to `pyproject.toml` (prerequisites for Tasks 3 and 4)
  - [x] Add `tiktoken>=0.9.0` to `[project] dependencies` in `pyproject.toml`
  - [x] Add `voyageai>=3.0.0` to `[project] dependencies` in `pyproject.toml`
  - [x] Run `uv sync` to install the new dependencies

- [x] Task 3: Implement `chunker.py` — full replacement of stub (AC: #1, #2)
  - [x] Define `Chunk` dataclass with fields: `text: str`, `chunk_index: int`, `token_count: int`
  - [x] Define `DEFAULT_ENCODING: str = "cl100k_base"` at module level
  - [x] Implement `def chunk(text: str, chunk_size: int = 1024, chunk_overlap: int = 100) -> list[Chunk]:`
  - [x] Inside `chunk()`: return `[]` immediately if `text` is empty or whitespace-only
  - [x] Inside `chunk()`: tokenize with `tiktoken.get_encoding(DEFAULT_ENCODING).encode(text)`
  - [x] Inside `chunk()`: step = `chunk_size - chunk_overlap`; iterate with `start` in `range(0, len(tokens), step)` — stop early if remaining tokens ≤ `chunk_overlap` (avoids near-empty tail chunks)
  - [x] Inside `chunk()`: for each window, decode tokens back to text with the same encoder
  - [x] Inside `chunk()`: set `token_count = len(chunk_tokens)` — exact count, not an estimate
  - [x] Remove the old `test_chunk_not_implemented` test from `tests/ingestion/test_chunker.py` (it will be replaced in Task 5)

- [x] Task 4: Implement `embedder.py` — full replacement of stub (AC: #3, #4, #5)
  - [x] Define `EmbeddingError(RuntimeError)` at module level
  - [x] Define `EmbeddingResult` dataclass with fields: `vector: list[float]`, `model: str`, `provider: str`
  - [x] Implement `async def embed(chunks: list[str], provider: str, model: str, api_key: str) -> list[EmbeddingResult]:`
  - [x] Inside `embed()`: raise `EmbeddingError` immediately if `chunks` is empty (no-op guard)
  - [x] Inside `embed()`: dispatch on `provider` — raise `EmbeddingError(f"Unsupported embedding provider: {provider!r}")` for unknown providers
  - [x] Inside `embed()`: for `provider == "anthropic"`, call `_embed_via_voyage(chunks, model, api_key)`
  - [x] Implement `async def _embed_via_voyage(chunks: list[str], model: str, api_key: str) -> list[EmbeddingResult]:` (see Dev Notes for Voyage SDK API)
  - [x] In `_embed_via_voyage`: wrap all exceptions in `EmbeddingError` — never let voyageai SDK exceptions propagate raw

- [x] Task 5: Replace `tests/ingestion/test_chunker.py` with real tests (AC: #1, #2)
  - [x] Remove `test_chunk_not_implemented`
  - [x] `test_chunk_short_document_single_chunk` — text of ~50 words → one chunk, `chunk_index == 0`, `token_count > 0`
  - [x] `test_chunk_returns_chunk_index_and_token_count` — assert each returned `Chunk` has `chunk_index` equal to its position in the list and `token_count > 0`
  - [x] `test_chunk_overlap_content` — long enough text to produce ≥ 2 chunks → assert last tokens of chunk N appear in first tokens of chunk N+1 (overlap preserved)
  - [x] `test_chunk_empty_text_returns_empty_list` — `chunk("") == []`
  - [x] `test_chunk_respects_custom_size` — call with small `chunk_size` (e.g., 20) on a known text and assert multiple chunks produced with `token_count ≤ 20`
  - [x] `test_chunk_no_near_empty_tail` — construct text that would produce a tiny tail chunk with default overlap logic; assert final chunk has at least `chunk_overlap` tokens

- [x] Task 6: Create `tests/ingestion/test_embedder.py` with real tests (AC: #3, #4, #5)
  - [x] `test_embed_empty_chunks_raises` — `embed([], ...)` raises `EmbeddingError`
  - [x] `test_embed_unsupported_provider_raises` — `embed(["text"], provider="openai", ...)` raises `EmbeddingError` matching "Unsupported"
  - [x] `test_embed_voyage_unavailable_raises` — patch voyageai client to raise `Exception("connection refused")` → assert `EmbeddingError` raised (unit, no network)
  - [x] `test_embed_result_shape` — patch voyageai client to return fake vectors → assert each `EmbeddingResult` has `vector` (list[float]), `model == "voyage-3"`, `provider == "anthropic"`
  - [x] `test_embed_result_count_matches_input` — patched client → assert `len(results) == len(chunks)`
  - [x] `@pytest.mark.integration` `test_embed_via_voyage_live` — call `embed(["Hello world"], provider="anthropic", model="voyage-3", api_key=<from env or skip>)`; assert result is non-empty list[float]; skip if `VOYAGE_API_KEY` not set

## Dev Notes

### Current Stub State — Audit Before Touching

| File | Current content | Action |
|------|-----------------|--------|
| `src/cos/ingestion/chunker.py` | `def chunk(text: str, size: int = 512, overlap: int = 64) -> list[str]: raise NotImplementedError` | Full replacement — **note wrong defaults (512/64) and wrong return type** |
| `src/cos/ingestion/embedder.py` | `async def embed(chunks: list[str]) -> list[list[float]]: raise NotImplementedError` | Full replacement — wrong return type, wrong signature |
| `tests/ingestion/test_chunker.py` | Single `test_chunk_not_implemented` | Replace entirely |
| `tests/ingestion/test_embedder.py` | Does not exist | Create |
| `src/cos/config.py` | Has `StorageConfig`; no `ChunkingConfig` | Add `ChunkingConfig` and field to `CosConfig` |
| `config.yaml.example` | Has `storage:` section; no `chunking:` | Append `chunking:` section |
| `pyproject.toml` | No `tiktoken` or `voyageai` | Add both |

**Leave these untouched** — belong to later stories:
- `pipeline.py` — stays as stub, Story 2.4
- `services/ingestion.py` — stays as stub, Story 2.4
- `store/db.py`, `store/models.py`, migration SQL — Story 2.3
- `mcp_server/tools.py`, `server.py` — no changes
- `extractor.py` — complete, do not touch

### `Chunk` Dataclass — Exact Definition

Place in `chunker.py`:

```python
from dataclasses import dataclass

@dataclass
class Chunk:
    text: str           # decoded text for this chunk
    chunk_index: int    # 0-based position in the chunk sequence for this document
    token_count: int    # exact token count for this chunk (from tiktoken)
```

`chunk_index` and `token_count` map directly to `chunks.chunk_index` and `chunks.token_count` columns in the DB schema (Story 2.3 writes them). Do not rename these fields.

### `EmbeddingError` and `EmbeddingResult` — Exact Definitions

Place in `embedder.py`:

```python
from dataclasses import dataclass

class EmbeddingError(RuntimeError):
    pass

@dataclass
class EmbeddingResult:
    vector: list[float]  # embedding vector — length depends on model (voyage-3: 1024 dims)
    model: str           # e.g. "voyage-3"
    provider: str        # e.g. "anthropic"
```

`vector`, `model`, and `provider` map directly to `embeddings.vector`, `embeddings.model`, and `embeddings.provider` columns (Story 2.3 writes them). Do not rename.

### Voyage AI SDK — Exact Usage

Package: `voyageai>=3.0.0`. Async client usage:

```python
import voyageai

async def _embed_via_voyage(
    chunks: list[str],
    model: str,
    api_key: str,
) -> list[EmbeddingResult]:
    try:
        client = voyageai.AsyncClient(api_key=api_key)
        result = await client.embed(chunks, model=model)
    except Exception as exc:
        raise EmbeddingError(f"Voyage embedding failed: {exc}") from exc

    return [
        EmbeddingResult(vector=vec, model=model, provider="anthropic")
        for vec in result.embeddings
    ]
```

Key points:
- `voyageai.AsyncClient(api_key=api_key)` — instantiated per call (no persistent connection needed)
- `client.embed(texts, model=model)` — `texts` is `list[str]`, returns object with `.embeddings: list[list[float]]`
- `result.embeddings[i]` corresponds to `chunks[i]` — same order guaranteed
- Broad `except Exception` is deliberate — wraps network errors, auth failures, rate limits into `EmbeddingError`
- `provider` is hardcoded as `"anthropic"` in `_embed_via_voyage` — matches `config.embedding.provider` value

**Verify against installed package at implementation time.** Run `uv run python -c "import voyageai; help(voyageai.AsyncClient.embed)"` to confirm exact API before writing code.

### `embed()` Signature — Exact Definition

```python
async def embed(
    chunks: list[str],
    provider: str,
    model: str,
    api_key: str,
) -> list[EmbeddingResult]:
```

Receives explicit parameters — do NOT import `CosConfig`. The service layer (Story 2.4) calls this passing `config.embedding.provider`, `config.embedding.model`, and the resolved api_key.

**api_key resolution note (for Story 2.4, not this story):** `EmbeddingConfig.api_key` is `Optional[SecretStr]`. If `None`, the service layer uses `config.llm.api_key` as fallback (same Anthropic key works for both Claude and Voyage). The embedder itself always receives a concrete non-None string.

### `chunk()` Function — Chunking Logic Notes

- Use `tiktoken.get_encoding("cl100k_base")` — this encoding is a reasonable approximation for Voyage models (exact Voyage tokenizer is not publicly available)
- Token-based splitting gives exact `token_count` values for the DB schema — do NOT use character-based estimation
- **Near-empty tail chunk prevention**: if remaining tokens after last full chunk start would be ≤ `chunk_overlap`, do not start another chunk. Example: 1125 tokens, size=1024, overlap=100 → step=924 → chunk 0: [0, 1024), chunk 1 would start at 924 with only 201 tokens remaining. Since 201 > 100, chunk 1 IS created. If instead 1010 tokens: step=924 → chunk 1 would start at 924 with only 86 tokens remaining (≤ overlap=100) → do NOT create chunk 1.
- `enc.decode()` can slightly alter whitespace at boundaries — acceptable; the text is used for embedding and display only
- Chunking is synchronous (pure CPU computation) — no `async` needed

### `config.yaml.example` — Chunking Section

Append after the `storage:` block:

```yaml
# ─────────────────────────────────────────────
# Chunking
# Controls how extracted document text is split before embedding.
# chunk_size: target token count per chunk (default: 1024)
# chunk_overlap: token overlap between adjacent chunks for context continuity (default: 100)
# Changing chunk_size requires re-embedding all existing documents.
# ─────────────────────────────────────────────
chunking:
  chunk_size: 1024
  chunk_overlap: 100
```

### Architecture Compliance

- `chunker.py` and `embedder.py` are internal ingestion modules — do NOT import from `cos.services.*`, `cos.store.*`, `cos.retrieval.*`, `cos.mcp_server.*`, or `cos.cli`
- Do NOT import `CosConfig` in either module — receive explicit parameters; the service layer owns config
- No logging in either module — the extractor only raises; the service layer logs at the boundary
- No bare `print()` calls
- `embed()` must be `async` — external API call
- `chunk()` is sync — pure computation, no I/O

### DB Schema Alignment (for Story 2.3 context)

`chunks` table columns this story's types must match:
- `chunk_index INTEGER` ← `Chunk.chunk_index: int`
- `content TEXT` ← `Chunk.text: str`
- `token_count INTEGER` ← `Chunk.token_count: int`

`embeddings` table columns this story's types must match:
- `vector vector` ← `EmbeddingResult.vector: list[float]`
- `model TEXT` ← `EmbeddingResult.model: str`
- `provider TEXT` ← `EmbeddingResult.provider: str`

voyage-3 produces 1024-dimensional vectors. The `vector` column type in pgvector needs to match — check `001_initial.sql`: it declares `vector vector NOT NULL` without a dimension constraint. This is intentional (allows model changes). No migration changes needed.

### Testing Strategy

`pyproject.toml` already has `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` on async tests.

**Unit tests (no external services):**
- `test_chunker.py`: no mocking needed — chunker is pure function using tiktoken (installed locally)
- `test_embedder.py`: mock/patch the voyageai client — use `unittest.mock.patch` or `pytest-mock`

**Mocking pattern for embedder tests:**

```python
from unittest.mock import AsyncMock, MagicMock, patch

async def test_embed_result_shape(tmp_path) -> None:
    mock_result = MagicMock()
    mock_result.embeddings = [[0.1, 0.2, 0.3]]

    mock_client = AsyncMock()
    mock_client.embed = AsyncMock(return_value=mock_result)

    with patch("cos.ingestion.embedder.voyageai.AsyncClient", return_value=mock_client):
        results = await embed(["hello"], provider="anthropic", model="voyage-3", api_key="test")

    assert len(results) == 1
    assert results[0].vector == [0.1, 0.2, 0.3]
    assert results[0].model == "voyage-3"
    assert results[0].provider == "anthropic"
```

**Integration test pattern:**

```python
@pytest.mark.integration
async def test_embed_via_voyage_live() -> None:
    import os
    api_key = os.environ.get("VOYAGE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No API key found in VOYAGE_API_KEY or ANTHROPIC_API_KEY")

    results = await embed(["Hello from integration test"], provider="anthropic", model="voyage-3", api_key=api_key)

    assert len(results) == 1
    assert isinstance(results[0].vector, list)
    assert len(results[0].vector) > 0
    assert results[0].model == "voyage-3"
    assert results[0].provider == "anthropic"
```

### Files to Create or Modify

| File | Action | Key constraint |
|------|--------|----------------|
| `pyproject.toml` | Add `tiktoken>=0.9.0` and `voyageai>=3.0.0` | Under `[project] dependencies` |
| `src/cos/config.py` | Add `ChunkingConfig` class and `chunking` field | After `StorageConfig`, before `CosConfig` |
| `config.yaml.example` | Append `chunking:` section | After `storage:` block |
| `src/cos/ingestion/chunker.py` | Full replacement | `Chunk` dataclass, `chunk()` function |
| `src/cos/ingestion/embedder.py` | Full replacement | `EmbeddingResult`, `EmbeddingError`, `embed()`, `_embed_via_voyage()` |
| `tests/ingestion/test_chunker.py` | Full replacement | Remove stub test |
| `tests/ingestion/test_embedder.py` | Create new file | Unit tests with mocked voyageai |
| `tests/test_config.py` | Add one test | Follow `test_storage_config_defaults` pattern |

### Cross-Story Notes

- **Story 2.3** consumes `Chunk` (text, chunk_index, token_count) and `EmbeddingResult` (vector, model, provider) to write to DB — field names are contractual, do not change
- **Story 2.4** wires `IngestService.ingest_file()` to call `chunker.chunk()` with `config.chunking.chunk_size/chunk_overlap` and `embedder.embed()` with `config.embedding.provider/model/api_key`
- **Story 3.1** adds `content_tsv` column to `chunks` table — no action needed now

### References

- Epics file: `_bmad-output/planning-artifacts/epics.md:436–463` — Story 2.2 ACs
- Architecture chunking defaults: `_bmad-output/planning-artifacts/architecture.md` — "Chunk size: 1024 tokens / Chunk overlap: 100 tokens"
- Architecture async discipline: `_bmad-output/planning-artifacts/architecture.md` — Process Patterns section
- DB schema: `src/cos/store/migrations/001_initial.sql` — `chunks` and `embeddings` table definitions
- LLM adapter pattern (reference for similar module structure): `src/cos/llm/adapter.py`, `src/cos/llm/anthropic.py`
- `EmbeddingConfig` in `CosConfig`: `src/cos/config.py:26–29`
- `StorageConfig` (pattern to follow for `ChunkingConfig`): `src/cos/config.py:61–63`
- Story 2.1 (extractor pattern — same principles apply): `_bmad-output/implementation-artifacts/2-1-document-extraction-and-markdown-normalisation.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Completion Notes List
- Added `ChunkingConfig` defaults to `CosConfig` and documented chunking settings in `config.yaml.example`.
- Replaced the `chunker.py` and `embedder.py` stubs with token-based chunking and Voyage-backed embedding generation, including structured `EmbeddingError` failures.
- Added unit coverage for chunk sizing, overlap preservation, near-empty-tail avoidance, provider dispatch, and Voyage failure handling, plus a live integration test that skips without credentials.
- Verified the installed Voyage SDK exposes `AsyncClient.embed(texts, model=...)` and adjusted the dependency to `voyageai>=0.3.0` because the story's `>=3.0.0` version is not available on PyPI.

### File List
- pyproject.toml
- uv.lock
- config.yaml.example
- src/cos/config.py
- src/cos/ingestion/chunker.py
- src/cos/ingestion/embedder.py
- tests/test_config.py
- tests/ingestion/test_chunker.py
- tests/ingestion/test_embedder.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-2-text-chunking-and-embedding-pipeline.md

### Change Log
- Added configurable chunking defaults and documented them in the example configuration.
- Implemented production chunking and embedding modules with explicit metadata contracts for later DB persistence stories.
- Added focused automated coverage and validated the story with pytest, Ruff, and targeted mypy checks.

### Review Findings

- [x] [Review][Patch] voyageai version pin too loose — `voyageai>=0.3.0` allows unverified older versions; minimum working version is `0.3.7` [pyproject.toml:22]
- [x] [Review][Defer] Result list construction outside try-except — if `result.embeddings` has unexpected structure, raw exceptions escape instead of `EmbeddingError` [embedder.py:46-53] — deferred, defensive hardening
- [x] [Review][Defer] No assertion that `len(result.embeddings) == len(chunks)` — Voyage API guarantees ordering but silent mismatch possible [embedder.py:46] — deferred, Voyage API is trusted
- [x] [Review][Defer] `ChunkingConfig` has no Pydantic validator for `chunk_overlap >= chunk_size` — caught at runtime in `chunk()` but a startup-time validator would give earlier feedback [config.py] — deferred, out of scope for this story
