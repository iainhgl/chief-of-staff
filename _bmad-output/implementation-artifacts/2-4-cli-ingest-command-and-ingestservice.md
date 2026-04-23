# Story 2.4: CLI Ingest Command & IngestService

Status: done

## Story

As an operator,
I want to ingest a single file or an entire folder of documents with a single CLI command,
so that I can load my knowledge base quickly without writing any code or interacting with the database directly.

## Acceptance Criteria

1. **Given** a single file path is passed to `cos ingest <path>`,
   **When** the command runs,
   **Then** `IngestService.ingest_file()` orchestrates the full pipeline (extract → chunk → embed → store) and the CLI prints a plain-language summary: e.g. `Ingested strategy.pdf → 24 chunks indexed`.

2. **Given** a folder path is passed to `cos ingest <folder>`,
   **When** the command runs,
   **Then** every supported file in the folder (`.pdf`, `.docx`, `.md`, `.txt`) is ingested in sequence, with per-file progress printed, and a final summary showing total files processed and total chunks indexed.

3. **Given** a folder contains unsupported file types (e.g. `.xlsx`, `.png`),
   **When** `cos ingest <folder>` runs,
   **Then** unsupported files are skipped with a plain-language notice (e.g. `Skipped report.xlsx — unsupported format`) and processing continues for supported files.

4. **Given** a folder of 10 standard documents (mix of PDF, Word, Markdown) is ingested,
   **When** ingestion completes,
   **Then** the elapsed time is consistent with a rate of at least 10 documents per minute on the test machine.

5. **Given** a file path that does not exist is passed to `cos ingest`,
   **When** the command runs,
   **Then** the CLI prints a plain-language error message identifying the missing file and exits with a non-zero status code — no stack trace is shown to the user.

6. **Given** any call to `cos ingest`,
   **When** log output is inspected,
   **Then** all structured log entries use `component: "ingestion"` and no raw `print()` calls appear in the ingestion code path.

## Tasks / Subtasks

- [x] Task 1: Add `psycopg-pool` dependency and implement `create_pool()` in `src/cos/store/db.py` (for future MCP server use)
  - [x] Run `uv add psycopg-pool` (adds `psycopg_pool` package; keep `psycopg[binary]` as-is)
  - [x] Add `from psycopg_pool import AsyncConnectionPool` import to `db.py`
  - [x] Implement `async def create_pool(dsn: str) -> AsyncConnectionPool:` — create with `open=False`, then `await pool.open(wait=True)`, return pool
  - [x] Return type annotation: `AsyncConnectionPool` (not `Any`)

- [x] Task 2: Implement `run_pipeline()` in `src/cos/ingestion/pipeline.py` (AC: #1, #2, #4, #6)
  - [x] Replace the stub with the full implementation (new signature — see Dev Notes)
  - [x] Compute `file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()`
  - [x] Call `await extract(source_path, tika_url=..., originals_dir=..., markdown_dir=...)` — use `CosConfig` fields
  - [x] Call `chunk(extraction.text, chunk_size=config.chunking.chunk_size, chunk_overlap=config.chunking.chunk_overlap)`
  - [x] Call `await embed([c.text for c in chunks], provider=..., model=..., api_key=...)` — get api_key from `config.embedding.api_key.get_secret_value()` if not None, else `""`
  - [x] Convert: `ChunkRecord(content=c.text, chunk_index=c.chunk_index, token_count=c.token_count)` for each `Chunk`
  - [x] Convert: `EmbeddingRecord(vector=e.vector, model=e.model, provider=e.provider)` for each `EmbeddingResult`
  - [x] Call `await store_document(conn, source_path=str(source_path), file_hash=file_hash, chunks=chunk_records, embeddings=embedding_records)`
  - [x] Log start/finish with structured JSON (`component: "ingestion"`) — no bare `print()`
  - [x] Return a `PipelineResult(document_id=..., chunk_count=len(chunks))` dataclass (define in `pipeline.py`)

- [x] Task 3: Implement `IngestService` in `src/cos/services/ingestion.py` (AC: #1, #2, #3, #5)
  - [x] Define `IngestResult` dataclass: `document_id: str`, `chunk_count: int`, `source_path: str`
  - [x] Add `__init__(self, config: CosConfig) -> None` — store `self._config = config`
  - [x] Implement `async def ingest_file(self, path: str) -> IngestResult:` — full spec in Dev Notes
  - [x] Leave `ingest_note` as `raise NotImplementedError` (Growth tier — Story 7.3)

- [x] Task 4: Implement `cos ingest` in `src/cos/cli.py` (AC: #1, #2, #3, #5, #6)
  - [x] Replace the `raise NotImplementedError` in `ingest()` with real implementation
  - [x] Update signature: `ingest(path: str = typer.Argument(..., help="File or folder path to ingest"))`
  - [x] Call `CosConfig.load()` at the top — exits with plain-language message if config is invalid (already handled by `CosConfig.load()`)
  - [x] Resolve `target = Path(path).resolve()`; if `not target.exists()`: `typer.echo(f"Error: path not found: {path}", err=True)` and `raise typer.Exit(code=1)`
  - [x] If `target.is_file()`: call `asyncio.run(_ingest_file(target, config))` — single file path
  - [x] If `target.is_dir()`: call `asyncio.run(_ingest_folder(target, config))` — folder path
  - [x] Use `typer.echo()` for all user-facing output — NOT bare `print()`
  - [x] `_ingest_file` and `_ingest_folder` are module-level async helpers — NOT nested closures
  - [x] Do NOT import from `cos.ingestion.*` or `cos.store.*` directly in `cli.py` — only from `cos.services.ingestion`

- [x] Task 5: Replace stub tests in `tests/ingestion/test_pipeline.py` (AC: #1, #4)
  - [x] Remove the existing `test_run_pipeline_not_implemented` test (it tests the old stub)
  - [x] Add `test_run_pipeline_markdown_creates_document` — creates a temp Markdown file, runs pipeline with a real Postgres connection (`TEST_DSN`), asserts `PipelineResult.document_id` is a non-empty UUID string and `chunk_count >= 1`
  - [x] Add `test_run_pipeline_reingest_increments_version` — ingest same file twice, assert `current_version == 2` in DB
  - [x] All tests use `migrated_db` and `clean_tables` fixtures (import `TEST_DSN` from `conftest`)
  - [x] Use `@pytest.mark.integration` marker for any test needing Tika (PDF/docx) — markdown tests can run without Tika

- [x] Task 6: Replace stub tests in `tests/services/test_ingestion_service.py` (AC: #1, #2, #3, #5)
  - [x] Remove the existing `test_ingest_file_not_implemented` and `test_ingest_note_not_implemented` tests
  - [x] Add `test_ingest_file_markdown_returns_result` — create `IngestService(config)`, call `ingest_file`, assert `IngestResult.document_id` is non-empty, `chunk_count >= 1`, `source_path` matches
  - [x] Add `test_ingest_folder_processes_supported_files` — create a temp folder with `.md` and `.txt` files, assert all are ingested
  - [x] Add `test_ingest_folder_skips_unsupported_files` — temp folder with `.md` and `.xlsx` file, assert only `.md` is ingested (`.xlsx` skipped, no exception)
  - [x] `IngestService` tests use a real `CosConfig` built from `conftest` fixtures — see Dev Notes for minimal config construction

### Review Findings

- [x] [Review][Decision] Non-recursive folder walk — resolved: `_ingest_folder` changed to use `target.rglob("*")` for recursive walk; `docs/setup.md` updated to document recursive behaviour [src/cos/cli.py]
- [x] [Review][Patch] Skip notice uses hyphen not em-dash — `"Skipped {name} - unsupported format"` should be `"Skipped {name} — unsupported format"` (AC3 exact wording) [src/cos/cli.py]
- [x] [Review][Patch] Chained exception traceback exposed on single-file error — `raise typer.Exit(code=1) from exc` attaches `__cause__`, which some Typer/Python versions surface as a chained traceback, violating AC5 (no stack trace to user); use plain `raise typer.Exit(code=1)` [src/cos/cli.py]
- [x] [Review][Patch] Root conftest loaded via fragile importlib — `tests/ingestion/conftest.py` and `tests/services/conftest.py` use `spec_from_file_location` / `exec_module` to load `TEST_DSN`; pytest already adds `tests/` to sys.path, so `from conftest import TEST_DSN` works (same as `tests/store/conftest.py`) [tests/ingestion/conftest.py, tests/services/conftest.py]
- [x] [Review][Patch] Empty string passed as api_key when `config.embedding.api_key` is None — pipeline falls back to `api_key=""` which produces a misleading auth error from the embedder rather than a clear config error; raise `ValueError` with descriptive message before calling `embed()` [src/cos/ingestion/pipeline.py]
- [x] [Review][Patch] Folder summary always printed when zero files processed — `_ingest_folder` prints `"Done: 0 file(s) ingested, 0 total chunks indexed"` even when every file was skipped; should print a more informative message (e.g. `"No supported files found in {folder}"`) when `total_files == 0` [src/cos/cli.py]
- [x] [Review][Patch] `AsyncConnectionPool.open()` has no timeout — `pool.open(wait=True)` with no `timeout` argument blocks indefinitely when the database is unreachable; add a reasonable timeout (e.g. `timeout=30.0`) [src/cos/store/db.py]
- [x] [Review][Patch] `_make_test_config` duplicated across two test files — same factory function in `tests/ingestion/test_pipeline.py` and `tests/services/test_ingestion_service.py`; extract to a shared fixture in `tests/conftest.py` or a `tests/helpers.py` module [tests/ingestion/test_pipeline.py, tests/services/test_ingestion_service.py]
- [x] [Review][Defer] Connection-per-file for CLI ingestion — `IngestService.ingest_file` opens a fresh connection per file; `create_pool` is unused by the CLI path; for sequential CLI use AC4 is not at risk, pool is correctly reserved for the MCP server (Epic 3) — deferred, pre-existing
- [x] [Review][Defer] Old chunks not deleted on re-ingest — retrieval will return chunks from all versions of the same document; intentional Phase 1 design (version-linking deferred) — deferred, pre-existing [deferred-work.md]
- [x] [Review][Defer] File read twice for hash and extraction — `read_bytes()` + `shutil.copy2()` in `extract()` are independent reads; fixing requires extractor interface change — deferred, pre-existing
- [x] [Review][Defer] Logging double-encodes JSON — `logging.info(json.dumps(...))` is pre-existing pattern established in Story 2.3 (`db.py` migration logging); consistent with codebase, structured logger migration is a separate concern — deferred, pre-existing

## Dev Notes

### Current State — Audit Before Touching

| File | Current content | Action |
|------|-----------------|--------|
| `src/cos/store/db.py` | `run_migrations()` ✅, `store_document()` ✅, `create_pool()` raises `NotImplementedError` | Add `psycopg_pool` import; implement `create_pool()` only |
| `src/cos/ingestion/pipeline.py` | `run_pipeline(source_uri: str) -> None` raises `NotImplementedError` | Rewrite entirely (new signature) |
| `src/cos/services/ingestion.py` | `IngestService` with `ingest_file(path: str) -> None` and `ingest_note` stubs | Add `IngestResult`, rewrite `ingest_file`; leave `ingest_note` as stub |
| `src/cos/cli.py` | `ingest` command raises `NotImplementedError` | Implement; add `asyncio.run()` wrapper |
| `tests/ingestion/test_pipeline.py` | `test_run_pipeline_not_implemented` (stub test) | Replace entirely |
| `tests/services/test_ingestion_service.py` | Two stub tests (no-arg constructor) | Replace entirely |

**Leave these untouched** — complete and working:
- `src/cos/ingestion/extractor.py` — `extract()`, `ExtractionResult`, `SUPPORTED_DIRECT_SUFFIXES`, `SUPPORTED_TIKA_SUFFIXES`
- `src/cos/ingestion/chunker.py` — `chunk()`, `Chunk`
- `src/cos/ingestion/embedder.py` — `embed()`, `EmbeddingResult`
- `src/cos/store/db.py` — `run_migrations()`, `store_document()` — DO NOT TOUCH these
- `src/cos/store/models.py` — all dataclasses — DO NOT TOUCH
- `src/cos/store/migrations/001_initial.sql` — schema is correct — DO NOT TOUCH
- `tests/store/test_document_store.py` — passing — DO NOT TOUCH
- `tests/ingestion/test_extractor.py`, `test_chunker.py`, `test_embedder.py` — passing — DO NOT TOUCH
- `src/cos/cli.py` — `status`, `restart`, `logs` commands stay as `raise NotImplementedError` (Epic 5)

### `pipeline.py` — New Implementation

```python
"""Ingestion pipeline orchestrator — extract → chunk → embed → store."""
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.ingestion.chunker import chunk
from cos.ingestion.embedder import embed
from cos.ingestion.extractor import extract
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord


@dataclass
class PipelineResult:
    document_id: str
    chunk_count: int


async def run_pipeline(
    source_path: Path,
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> PipelineResult:
    logging.info(json.dumps({
        "timestamp": ...,   # use datetime.now(timezone.utc).isoformat()
        "level": "INFO",
        "component": "ingestion",
        "message": "pipeline start",
        "source_path": str(source_path),
    }))

    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    extraction = await extract(
        source_path,
        tika_url=config.tika.url,
        originals_dir=config.storage.originals_dir,
        markdown_dir=config.storage.markdown_dir,
    )

    chunks = chunk(
        extraction.text,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
    )

    api_key = config.embedding.api_key.get_secret_value() if config.embedding.api_key else ""
    embedding_results = await embed(
        [c.text for c in chunks],
        provider=config.embedding.provider,
        model=config.embedding.model,
        api_key=api_key,
    )

    chunk_records = [
        ChunkRecord(content=c.text, chunk_index=c.chunk_index, token_count=c.token_count)
        for c in chunks
    ]
    embedding_records = [
        EmbeddingRecord(vector=e.vector, model=e.model, provider=e.provider)
        for e in embedding_results
    ]

    document_id = await store_document(
        conn,
        source_path=str(source_path),
        file_hash=file_hash,
        chunks=chunk_records,
        embeddings=embedding_records,
    )

    logging.info(json.dumps({
        "timestamp": ...,
        "level": "INFO",
        "component": "ingestion",
        "message": "pipeline complete",
        "document_id": document_id,
        "chunk_count": len(chunks),
    }))

    return PipelineResult(document_id=document_id, chunk_count=len(chunks))
```

**Critical import note:** `pipeline.py` imports from `cos.store.db` — this is explicitly permitted by the architecture: "cos/ingestion/ ... only from cos/store/ and cos/config.py". It MUST NOT import from `cos/retrieval/`, `cos/services/`, or `cos/mcp_server/`.

**Type field mapping (Story 2.2 → Story 2.3 types):**
- `Chunk.text` → `ChunkRecord.content`
- `Chunk.chunk_index` → `ChunkRecord.chunk_index`
- `Chunk.token_count` → `ChunkRecord.token_count`
- `EmbeddingResult.vector` → `EmbeddingRecord.vector`
- `EmbeddingResult.model` → `EmbeddingRecord.model`
- `EmbeddingResult.provider` → `EmbeddingRecord.provider`

### `services/ingestion.py` — New Implementation

```python
"""IngestService — thin orchestration over the ingestion pipeline."""
import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.ingestion.extractor import SUPPORTED_DIRECT_SUFFIXES, SUPPORTED_TIKA_SUFFIXES, ExtractionError
from cos.ingestion.pipeline import PipelineResult, run_pipeline

SUPPORTED_SUFFIXES = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES


@dataclass
class IngestResult:
    document_id: str
    chunk_count: int
    source_path: str


class IngestService:
    def __init__(self, config: CosConfig) -> None:
        self._config = config

    async def ingest_file(self, path: str) -> IngestResult:
        source_path = Path(path).resolve()
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            result = await run_pipeline(source_path, self._config, conn)
        return IngestResult(
            document_id=result.document_id,
            chunk_count=result.chunk_count,
            source_path=str(source_path),
        )

    async def ingest_note(self, text: str) -> IngestResult:
        raise NotImplementedError  # Growth tier — Story 7.3
```

**Note on connection:** `psycopg.AsyncConnection.connect()` opens in autocommit=False (psycopg3 default). `store_document` uses `conn.transaction()` internally which manages commit/rollback. The connection is closed at the end of the `async with` block.

**Note on `ingest_note`:** Return type changes from `None` to `IngestResult` in the stub — update the signature even though the body raises `NotImplementedError`. This ensures type consistency when Epic 7 implements it.

### `cli.py` — `ingest` Command Implementation

```python
import asyncio
import json
import logging
from pathlib import Path

import typer

from cos.config import CosConfig
from cos.ingestion.extractor import SUPPORTED_DIRECT_SUFFIXES, SUPPORTED_TIKA_SUFFIXES
from cos.services.ingestion import IngestService

SUPPORTED_SUFFIXES = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES


@app.command()
def ingest(path: str = typer.Argument(..., help="File or folder path to ingest")) -> None:
    """Ingest a document or folder into the knowledge base."""
    config = CosConfig.load()
    target = Path(path).resolve()

    if not target.exists():
        typer.echo(f"Error: path not found: {path}", err=True)
        raise typer.Exit(code=1)

    service = IngestService(config)

    if target.is_file():
        asyncio.run(_ingest_single(target, service))
    elif target.is_dir():
        asyncio.run(_ingest_folder(target, service))


async def _ingest_single(target: Path, service: IngestService) -> None:
    result = await service.ingest_file(str(target))
    typer.echo(f"Ingested {target.name} → {result.chunk_count} chunks indexed")


async def _ingest_folder(target: Path, service: IngestService) -> None:
    total_files = 0
    total_chunks = 0
    for file_path in sorted(target.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            typer.echo(f"Skipped {file_path.name} — unsupported format")
            continue
        result = await service.ingest_file(str(file_path))
        typer.echo(f"Ingested {file_path.name} → {result.chunk_count} chunks indexed")
        total_files += 1
        total_chunks += result.chunk_count
    typer.echo(f"\nDone: {total_files} file(s) ingested, {total_chunks} total chunks indexed")
```

**CLI rules:**
- Import `CosConfig` from `cos.config` ✓
- Import `IngestService` from `cos.services.ingestion` ✓ (no direct import from `cos.ingestion.*` or `cos.store.*`)
- `typer.echo()` for user-facing output — NOT `print()`
- `asyncio.run()` only at entry points — `_ingest_single` and `_ingest_folder` are `async def` called via `asyncio.run()`, not directly
- `CosConfig.load()` already handles missing/invalid config with `SystemExit` — no extra try/except needed here
- Exceptions from `IngestService.ingest_file()` (e.g. `ExtractionError`, DB errors) will produce a stack trace to the user — add a try/except at the CLI boundary to catch and print plain-language errors, then `raise typer.Exit(code=1)`

**Error handling at CLI boundary (AC #5):**
Wrap the `asyncio.run()` calls in a try/except:
```python
try:
    asyncio.run(_ingest_single(target, service))
except Exception as exc:
    typer.echo(f"Error ingesting {target.name}: {exc}", err=True)
    raise typer.Exit(code=1)
```
This prevents raw stack traces from appearing in the terminal. Apply same pattern for the folder case (per-file errors should be caught within `_ingest_folder` so processing continues for other files).

### `create_pool()` — Implementation

```python
from psycopg_pool import AsyncConnectionPool

async def create_pool(dsn: str) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(dsn, open=False)
    await pool.open(wait=True)
    return pool
```

Add `from psycopg_pool import AsyncConnectionPool` to `db.py` imports.

`create_pool()` is not called by Story 2.4 itself. It is prepared here for the MCP server's retrieval path (Epic 3) which needs a long-lived connection pool. Adding the dependency now avoids a mid-story context disruption later.

### Dependency to Add

```bash
uv add psycopg-pool
```

This adds `psycopg_pool` as a separate package (psycopg3 split the pool into its own distribution). Do NOT change `psycopg[binary]` — it stays as-is.

### Test Construction for IngestService Tests

Because `IngestService` now requires a `CosConfig`, the tests need a minimal valid config. Build one directly (no YAML file needed for tests):

```python
from cos.config import (
    ChunkingConfig, CosConfig, DatabaseConfig, EmbeddingConfig,
    LLMConfig, RolePackRef, StorageConfig, TikaConfig
)
from pydantic import SecretStr
from pathlib import Path

def _make_test_config(tmp_path: Path) -> CosConfig:
    return CosConfig(
        llm=LLMConfig(provider="anthropic", model="claude-3-haiku-20240307", api_key=SecretStr("test")),
        embedding=EmbeddingConfig(provider="anthropic", model="voyage-3", api_key=SecretStr("test")),
        role_pack=RolePackRef(path="role_packs/chro.yaml"),
        channels=["local"],
        connectors=[],
        database=DatabaseConfig(
            host="localhost", port=5432, user="postgres",
            password=SecretStr("postgres"), dbname="cos_test"
        ),
        tika=TikaConfig(url="http://localhost:9998"),  # not called for .md files
        storage=StorageConfig(
            originals_dir=tmp_path / "originals",
            markdown_dir=tmp_path / "markdown",
        ),
        chunking=ChunkingConfig(chunk_size=512, chunk_overlap=50),
    )
```

**Important:** `EmbeddingConfig.api_key` is `SecretStr | None`. In `run_pipeline`, call `.get_secret_value()` if not None. The actual embedding API call requires a live key — for pipeline tests, use a mock or only test with Markdown content via a controlled embedder mock.

**Embedding in tests:** The embed step hits the real Voyage API. To avoid API calls in tests, either:
- Mark tests requiring the real embedding as `@pytest.mark.integration` and skip in CI
- OR mock the `embed` function in the test — `monkeypatch.setattr("cos.ingestion.pipeline.embed", mock_embed)` — where `mock_embed` returns deterministic 1024-dim vectors

Recommended approach: mock `embed` in unit/integration tests for pipeline and IngestService. The embedder itself is already tested in `tests/ingestion/test_embedder.py`.

```python
# In conftest or test file
@pytest.fixture
def mock_embed(monkeypatch):
    async def _fake_embed(chunks, provider, model, api_key):
        from cos.ingestion.embedder import EmbeddingResult
        return [
            EmbeddingResult(
                vector=[float(i) / 100 for i in range(1024)],
                model=model,
                provider=provider,
            )
            for _ in chunks
        ]
    monkeypatch.setattr("cos.ingestion.pipeline.embed", _fake_embed)
```

### Test Pattern for `tests/ingestion/test_pipeline.py`

```python
from pathlib import Path
import psycopg
import pytest
from conftest import TEST_DSN
from cos.ingestion.pipeline import PipelineResult, run_pipeline

# mock_embed fixture defined above or in conftest

async def test_run_pipeline_markdown_creates_document(
    migrated_db, clean_tables, tmp_path, mock_embed
) -> None:
    src = tmp_path / "notes.md"
    src.write_text("# Meeting Notes\n\nDiscussed Q3 strategy.", encoding="utf-8")

    config = _make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline(src, config, conn)

    assert isinstance(result, PipelineResult)
    assert len(result.document_id) == 36  # UUID format
    assert result.chunk_count >= 1
```

**Why own connections:** Same reason as Story 2.3 — `store_document` uses `conn.transaction()` which commits. The `db_conn` fixture does rollback at teardown, which would conflict. Use fresh connections.

**`clean_tables` fixture:** Defined in `tests/store/conftest.py` — it's scoped to `tests/store/`. For `tests/ingestion/` tests, define a local `clean_tables` autouse fixture in `tests/ingestion/conftest.py` (create this file):

```python
# tests/ingestion/conftest.py
import pytest
import psycopg
from conftest import TEST_DSN

@pytest.fixture(autouse=True)
async def clean_tables(migrated_db) -> None:
    yield
    async with await psycopg.AsyncConnection.connect(TEST_DSN, autocommit=True) as conn:
        await conn.execute(
            "TRUNCATE embeddings, chunks, document_versions, documents RESTART IDENTITY CASCADE"
        )
```

Similarly create `tests/services/conftest.py` with the same fixture if `IngestService` tests also need table cleanup.

### Architecture Compliance

**What `cli.py` may import:**
- `cos.config` ✓
- `cos.services.ingestion` ✓

**What `cli.py` must NOT import:**
- `cos.ingestion.*` ✗
- `cos.store.*` ✗

**What `pipeline.py` may import:**
- `cos.config` ✓
- `cos.ingestion.extractor`, `cos.ingestion.chunker`, `cos.ingestion.embedder` ✓ (intra-package)
- `cos.store.db`, `cos.store.models` ✓ (ingestion may import from store)

**What `pipeline.py` must NOT import:**
- `cos.retrieval.*` ✗
- `cos.services.*` ✗
- `cos.mcp_server.*` ✗

**Logging format:**
```python
json.dumps({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "level": "INFO",
    "component": "ingestion",
    "message": "...",
})
```
Pass this string to `logging.info()`. No bare `print()` anywhere in the ingestion code path.

### Config Fields Used in This Story

| Field | Where | Example |
|---|---|---|
| `config.tika.url` | `extract()` call | `"http://tika:9998"` |
| `config.storage.originals_dir` | `extract()` call | `Path("/data/originals")` |
| `config.storage.markdown_dir` | `extract()` call | `Path("/data/markdown")` |
| `config.chunking.chunk_size` | `chunk()` call | `1024` |
| `config.chunking.chunk_overlap` | `chunk()` call | `100` |
| `config.embedding.provider` | `embed()` call | `"anthropic"` |
| `config.embedding.model` | `embed()` call | `"voyage-3"` |
| `config.embedding.api_key` | `embed()` call | `SecretStr("...")` → `.get_secret_value()` |
| `config.database.libpq_dsn` | `psycopg.AsyncConnection.connect()` | `"postgresql://..."` |

`config.embedding.api_key` is `SecretStr | None` — always check for None before calling `.get_secret_value()`.

### Supported File Types

Defined in `src/cos/ingestion/extractor.py` — do NOT redefine:
```python
SUPPORTED_DIRECT_SUFFIXES: frozenset[str] = frozenset({".md", ".txt"})
SUPPORTED_TIKA_SUFFIXES: frozenset[str] = frozenset({".pdf", ".docx"})
```
In `cli.py` and `services/ingestion.py`: `from cos.ingestion.extractor import SUPPORTED_DIRECT_SUFFIXES, SUPPORTED_TIKA_SUFFIXES` then `SUPPORTED_SUFFIXES = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES`.

### Forward-Looking Notes

- **Story 2.5** (`cos docs`) reads from `documents` and `document_versions` tables written by `store_document()` in this story. No schema changes needed for 2.5 beyond what's already in `001_initial.sql`.
- **Story 2.6** (Operator Validation) exercises `cos ingest ./test-docs/` end-to-end with real files — ensure folder ingestion is robust.
- **Story 3.x** (Retrieval) will call `create_pool()` implemented here for the MCP server's connection pool.
- **Epic 5** (CLI Operations) implements `cos status`, `cos restart`, `cos logs` — leave those as `NotImplementedError` stubs.

### Files to Create or Modify

| File | Action | Key constraint |
|------|--------|----------------|
| `pyproject.toml` | Add `psycopg-pool` via `uv add psycopg-pool` | Run command; uv.lock is updated automatically |
| `src/cos/store/db.py` | Add `create_pool()` + `from psycopg_pool import AsyncConnectionPool` | Do NOT touch `run_migrations` or `store_document` |
| `src/cos/ingestion/pipeline.py` | Rewrite `run_pipeline` (new signature, full implementation) | Imports: `cos.store.*` allowed; no `cos.services.*` |
| `src/cos/services/ingestion.py` | Add `IngestResult`; rewrite `IngestService` with `__init__` + `ingest_file` | Only imports from `cos.services.*` layer and `cos.config` |
| `src/cos/cli.py` | Implement `ingest` command; add `_ingest_single`, `_ingest_folder` helpers | `asyncio.run()` only at entry; `typer.echo()` for output |
| `tests/ingestion/conftest.py` | Create — `clean_tables` autouse fixture | Same pattern as `tests/store/conftest.py` |
| `tests/ingestion/test_pipeline.py` | Replace stub test; add real integration tests | Use `mock_embed`; fresh connections |
| `tests/services/conftest.py` | Create — `clean_tables` autouse fixture | Same as `tests/ingestion/conftest.py` |
| `tests/services/test_ingestion_service.py` | Replace stub tests; add real integration tests | Use `_make_test_config(tmp_path)` |

### References

- Extractor types and constants: `src/cos/ingestion/extractor.py` — `extract()`, `ExtractionResult`, `SUPPORTED_DIRECT_SUFFIXES`, `SUPPORTED_TIKA_SUFFIXES`
- Chunker: `src/cos/ingestion/chunker.py` — `chunk()`, `Chunk` (`text`, `chunk_index`, `token_count`)
- Embedder: `src/cos/ingestion/embedder.py` — `embed()`, `EmbeddingResult` (`vector`, `model`, `provider`)
- Store function: `src/cos/store/db.py:store_document()` — full implementation (commits via `conn.transaction()`)
- Store models: `src/cos/store/models.py` — `ChunkRecord`, `EmbeddingRecord`
- Config: `src/cos/config.py` — `CosConfig` with `tika`, `storage`, `chunking`, `embedding`, `database` sub-models
- Test DSN: `tests/conftest.py:TEST_DSN = "postgresql://postgres:postgres@localhost:5432/cos_test"`
- Migration fixtures: `tests/conftest.py` — `migrated_db`, `db_conn`
- Architecture boundaries: `_bmad-output/planning-artifacts/architecture.md` — service layer, ingestion→store import rules
- Epic 1 architecture deviations: `architecture.md` (Epic 1 Implementation Notes section) — `create_pool` stub, CLI stubs

## Dev Agent Record

### Agent Model Used

gpt-5

### Debug Log References

- `uv add psycopg-pool`
- `uv run pytest tests/ingestion/test_pipeline.py tests/services/test_ingestion_service.py`
- `uv run pytest`
- `uv run ruff check src/cos/store/db.py src/cos/ingestion/pipeline.py src/cos/services/ingestion.py src/cos/cli.py tests/ingestion/conftest.py tests/ingestion/test_pipeline.py tests/services/conftest.py tests/services/test_ingestion_service.py`
- `uv run mypy src/cos/store/db.py src/cos/ingestion/pipeline.py src/cos/services/ingestion.py src/cos/cli.py tests/ingestion/test_pipeline.py tests/services/test_ingestion_service.py`

### Completion Notes List

- Implemented the end-to-end ingestion pipeline in `src/cos/ingestion/pipeline.py`, including hashing, extraction, chunking, embedding, storage, and structured `component: "ingestion"` logging.
- Added `IngestService` orchestration and a CLI `cos ingest` flow that handles single files, folder ingestion, unsupported-file skips, and plain-language error handling without stack traces.
- Added `create_pool()` in `src/cos/store/db.py` and the `psycopg-pool` dependency to prepare the connection-pool path for upcoming retrieval and MCP work.
- Replaced the ingestion and service stub tests with Postgres-backed tests that mock embeddings, plus local cleanup fixtures for the two test packages.
- Validation completed with `uv run pytest` passing (`71 passed, 2 skipped`), targeted Ruff checks passing for all Story 2.4 files, and targeted mypy checks passing for the touched source files.

### File List

- _bmad-output/implementation-artifacts/2-4-cli-ingest-command-and-ingestservice.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- pyproject.toml
- src/cos/cli.py
- src/cos/ingestion/pipeline.py
- src/cos/services/ingestion.py
- src/cos/store/db.py
- tests/ingestion/conftest.py
- tests/ingestion/test_pipeline.py
- tests/services/conftest.py
- tests/services/test_ingestion_service.py
- uv.lock

## Change Log

- 2026-04-23: Implemented Story 2.4 CLI ingestion flow, service orchestration, pipeline persistence, test fixtures, and regression coverage; validated with full test suite plus targeted lint/type checks.
