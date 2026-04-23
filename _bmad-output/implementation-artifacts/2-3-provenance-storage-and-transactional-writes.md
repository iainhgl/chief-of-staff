# Story 2.3: Provenance Storage & Transactional Writes

Status: done

## Story

As an operator,
I want every ingested document and its chunks to be stored with full provenance in a single atomic transaction,
So that the knowledge base is never left in a partial or inconsistent state, even if the container crashes mid-ingest.

## Acceptance Criteria

1. **Given** a successfully extracted and chunked document,
   **When** the store layer writes it to Postgres,
   **Then** a single transaction inserts: one `documents` row, one `document_versions` row, N `chunks` rows (one per chunk), and N `embeddings` rows — all committed together or not at all.

2. **Given** the transaction is committed,
   **When** the `documents` row is inspected,
   **Then** it contains `source_path`, `file_hash` (SHA-256 of the original file bytes), `ingested_at` (ISO 8601 UTC), `current_version` (1 for first ingest), and `status: "indexed"`.

3. **Given** the same file is ingested a second time (matching `source_path`),
   **When** the store layer runs,
   **Then** a new `document_versions` row is created with an incremented `version` number, the `documents` row `current_version` is updated, and the prior version's chunks and embeddings remain untouched in the database.

4. **Given** an error occurs mid-transaction (simulated in tests by raising within the transaction context),
   **When** the transaction is rolled back,
   **Then** no orphaned `documents` row without corresponding chunks exists — the database is left in the pre-call state.

5. **Given** a document whose original file is already present in the originals directory,
   **When** re-ingestion is triggered,
   **Then** the existing original file is not overwritten or deleted — a new version record is created. (The original-file preservation is enforced by `extractor.py` which is already implemented; Story 2.3 only adds the DB version record.)

## Tasks / Subtasks

- [x] Task 1: Add `store_document()` to `src/cos/store/db.py` (AC: #1, #2, #3, #4)
  - [x] Add imports: `from pgvector.psycopg import register_vector_async` and `from cos.store.models import ChunkRecord, EmbeddingRecord` at the top of `db.py`
  - [x] Add `from typing import Any` if not already present
  - [x] Implement `async def store_document(conn: psycopg.AsyncConnection[Any], source_path: str, file_hash: str, chunks: list[ChunkRecord], embeddings: list[EmbeddingRecord]) -> str:` — full spec in Dev Notes
  - [x] Inside `store_document`: call `await register_vector_async(conn)` once before any SQL
  - [x] Inside `store_document`: use `async with conn.transaction():` to wrap all inserts — this commits on success and rolls back on any exception
  - [x] Inside `store_document`: detect re-ingest by querying `SELECT id, current_version FROM documents WHERE source_path = %s`
  - [x] If document does NOT exist: INSERT into `documents` with `status='indexed'`, `current_version=1`, `RETURNING id`; INSERT into `document_versions` with `version=1`, `content_hash=file_hash`
  - [x] If document DOES exist: UPDATE `documents SET current_version = current_version + 1 WHERE id = %s RETURNING current_version`; INSERT into `document_versions` with the new version number and `content_hash=file_hash`
  - [x] For each `(chunk, embedding)` pair: INSERT into `chunks` with `RETURNING id` to get the chunk UUID; INSERT into `embeddings` using that chunk UUID
  - [x] Return `str(document_id)` — the UUID as a string

- [x] Task 2: Create `tests/store/conftest.py` with test isolation fixture
  - [x] Create `tests/store/conftest.py` with a `clean_tables` autouse async fixture that runs `TRUNCATE embeddings, chunks, document_versions, documents RESTART IDENTITY CASCADE` after every test — prevents data from one test leaking into the next
  - [x] Import `TEST_DSN` from `conftest` (not `tests.conftest` — pytest adds `tests/` to sys.path so `from conftest import TEST_DSN` works)

- [x] Task 3: Create `tests/store/test_document_store.py` with real integration tests (AC: #1, #2, #3, #4)
  - [x] `test_store_document_first_ingest_creates_documents_row` — call `store_document` with 1 chunk + 1 embedding; assert `documents` row has correct `source_path`, `file_hash`, `current_version=1`, `status='indexed'`
  - [x] `test_store_document_creates_document_versions_row` — assert one `document_versions` row exists with `version=1`, `content_hash=file_hash`
  - [x] `test_store_document_creates_chunks_rows` — assert N `chunks` rows exist with correct `document_id`, `content`, `chunk_index`, `token_count`
  - [x] `test_store_document_creates_embeddings_rows` — assert N `embeddings` rows exist with correct `chunk_id`, `model`, `provider`, and non-empty `vector`
  - [x] `test_store_document_returns_document_id` — assert return value is a non-empty UUID string matching the `documents` row id
  - [x] `test_store_document_reingest_increments_version` — call `store_document` twice with the same `source_path`; assert `documents.current_version == 2` and two `document_versions` rows exist
  - [x] `test_store_document_reingest_preserves_old_chunks` — after re-ingest, assert total chunks count equals N_first + N_second (old chunks are NOT deleted)
  - [x] `test_store_document_atomicity_on_failure` — within a `conn.transaction()` block, call `store_document` then raise `RuntimeError`; catch the error; assert no `documents` rows exist (full rollback)
  - [x] All tests use the `migrated_db` fixture (for migration state) and the `clean_tables` autouse fixture (for data isolation)
  - [x] Tests create their own connections via `await psycopg.AsyncConnection.connect(TEST_DSN)` — do NOT use the `db_conn` fixture (which rolls back at teardown, conflicting with `store_document`'s internal commit)

### Review Findings

- [x] [Review][Patch] Atomicity test exercises caller rollback, not store_document's internal atomicity [tests/store/test_document_store.py:213-228]
- [x] [Review][Patch] file_hash immutability after re-ingest not asserted in tests [tests/store/test_document_store.py:150-175]
- [x] [Review][Patch] Reingest chunk preservation test checks chunk_index only — content/embeddings of old chunks unverified [tests/store/test_document_store.py:176-211]
- [x] [Review][Patch] Atomicity COUNT(*) not scoped to the failed document's source_path [tests/store/test_document_store.py:220-228]
- [x] [Review][Defer] Missing UNIQUE constraint on documents.source_path — concurrent ingests can silently create duplicates — deferred, pre-existing [src/cos/store/migrations/001_initial.sql]
- [x] [Review][Defer] Chunks have no version-linking column — chunks from all versions are indistinguishable at query time — deferred, intentional design for Phase 1 [src/cos/store/db.py]

## Dev Notes

### Current State — Audit Before Touching

| File | Current content | Action |
|------|-----------------|--------|
| `src/cos/store/db.py` | Has `run_migrations()`; `create_pool()` raises `NotImplementedError` | Add `store_document()` — do NOT touch `run_migrations()` or `create_pool()` |
| `src/cos/store/models.py` | Has `DocumentRecord`, `ChunkRecord`, `EmbeddingRecord`, `DocumentVersion`, `ProvenanceRecord` | No changes needed — use as-is |
| `src/cos/store/migrations/001_initial.sql` | Complete schema: `documents`, `document_versions`, `chunks`, `embeddings` tables | No changes — schema is correct |
| `tests/store/test_migrations.py` | Existing tests passing | No changes — do not touch |
| `tests/store/conftest.py` | Does not exist | Create with `clean_tables` fixture |
| `tests/store/test_document_store.py` | Does not exist | Create with integration tests |

**Leave these untouched** — belong to later stories:
- `src/cos/store/db.py` — `create_pool()` stub stays as-is (Story 2.4 implements it when IngestService is wired)
- `src/cos/ingestion/pipeline.py` — stays as stub (Story 2.4)
- `src/cos/services/ingestion.py` — stays as stub (Story 2.4)
- `src/cos/ingestion/chunker.py`, `embedder.py`, `extractor.py` — complete, do not touch

### `store_document()` — Exact Implementation

Place in `src/cos/store/db.py` below `run_migrations()`:

```python
async def store_document(
    conn: psycopg.AsyncConnection[Any],
    source_path: str,
    file_hash: str,
    chunks: list["ChunkRecord"],
    embeddings: list["EmbeddingRecord"],
) -> str:
    await register_vector_async(conn)

    async with conn.transaction():
        result = await conn.execute(
            "SELECT id, current_version FROM documents WHERE source_path = %s",
            (source_path,),
        )
        existing = await result.fetchone()

        if existing is None:
            result = await conn.execute(
                "INSERT INTO documents (source_path, file_hash, current_version, status)"
                " VALUES (%s, %s, 1, 'indexed') RETURNING id",
                (source_path, file_hash),
            )
            row = await result.fetchone()
            document_id = row[0]
            new_version = 1
        else:
            document_id, current_version = existing
            new_version = current_version + 1
            await conn.execute(
                "UPDATE documents SET current_version = %s WHERE id = %s",
                (new_version, document_id),
            )

        await conn.execute(
            "INSERT INTO document_versions (document_id, version, content_hash)"
            " VALUES (%s, %s, %s)",
            (document_id, new_version, file_hash),
        )

        for chunk, embedding in zip(chunks, embeddings):
            result = await conn.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, token_count)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                (document_id, chunk.chunk_index, chunk.content, chunk.token_count),
            )
            chunk_row = await result.fetchone()
            chunk_id = chunk_row[0]

            await conn.execute(
                "INSERT INTO embeddings (chunk_id, vector, model, provider)"
                " VALUES (%s, %s, %s, %s)",
                (chunk_id, embedding.vector, embedding.model, embedding.provider),
            )

    return str(document_id)
```

**Key implementation notes:**
- `async with conn.transaction():` creates a savepoint if the connection is already in a transaction; starts a new transaction if idle. On success: commits (or releases savepoint). On exception: rolls back (or rolls back to savepoint).
- `register_vector_async(conn)` must be called BEFORE any SQL that uses vector types. It registers the pgvector type adapter so psycopg3 knows how to serialise `list[float]` → `vector`. Calling it multiple times on the same connection is safe.
- `embedding.vector` is `list[float]` — after `register_vector_async`, psycopg3 accepts this directly for `vector` columns.
- The `documents.status` column defaults to `'active'` in the schema, but the ACs require `'indexed'`. Always pass `'indexed'` explicitly in the INSERT — never rely on the default.
- `documents.file_hash` is set on first ingest and never updated. `document_versions.content_hash` tracks each version's hash.
- Re-ingest detection is by `source_path` alone (not by `file_hash`) — any re-submission of the same source path creates a new version record.

### Imports Required in `db.py`

Add to the existing imports at the top of `src/cos/store/db.py`:

```python
from typing import Any

import psycopg
from pgvector.psycopg import register_vector_async

from cos.store.models import ChunkRecord, EmbeddingRecord
```

Check existing imports first — `psycopg` is already imported. Add only what's missing.

### `ChunkRecord` and `EmbeddingRecord` — Exact Definitions (already in `models.py`)

Do NOT redefine these. They exist in `src/cos/store/models.py`:

```python
@dataclass
class ChunkRecord:
    id: str = ""            # not required by caller — DB generates UUID
    document_id: str = ""   # not required by caller — set internally by store_document
    content: str = ""       # ← maps from Chunk.text (Story 2.2)
    chunk_index: int = 0    # ← maps from Chunk.chunk_index (Story 2.2)
    token_count: int = 0    # ← maps from Chunk.token_count (Story 2.2)

@dataclass
class EmbeddingRecord:
    id: str = ""            # not required by caller — DB generates UUID
    chunk_id: str = ""      # not required by caller — set internally by store_document
    vector: list[float] = field(default_factory=list)  # ← maps from EmbeddingResult.vector
    model: str = ""         # ← maps from EmbeddingResult.model
    provider: str = ""      # ← maps from EmbeddingResult.provider
```

The conversion from Story 2.2 types (`Chunk`, `EmbeddingResult`) to Story 2.3 types (`ChunkRecord`, `EmbeddingRecord`) happens in the IngestService / pipeline layer (Story 2.4), not here.

### DB Schema — Column Mapping

```
documents:
  source_path TEXT         ← store_document.source_path parameter
  file_hash TEXT           ← store_document.file_hash parameter
  ingested_at TIMESTAMPTZ  ← DB DEFAULT now() — do NOT pass explicitly
  current_version INTEGER  ← 1 on first ingest, incremented on re-ingest
  status TEXT              ← explicitly pass 'indexed' (schema default is 'active')

document_versions:
  document_id UUID         ← FK to documents.id
  version INTEGER          ← 1 on first ingest; current_version value on re-ingest
  content_hash TEXT        ← same as file_hash parameter for that ingest event
  created_at TIMESTAMPTZ   ← DB DEFAULT now()

chunks:
  document_id UUID         ← FK to documents.id
  chunk_index INTEGER      ← ChunkRecord.chunk_index
  content TEXT             ← ChunkRecord.content
  token_count INTEGER      ← ChunkRecord.token_count
  created_at TIMESTAMPTZ   ← DB DEFAULT now()

embeddings:
  chunk_id UUID            ← FK to chunks.id (from RETURNING id)
  vector vector            ← EmbeddingRecord.vector (list[float], voyage-3 → 1024 dims)
  model TEXT               ← EmbeddingRecord.model (e.g. "voyage-3")
  provider TEXT            ← EmbeddingRecord.provider (e.g. "anthropic")
  created_at TIMESTAMPTZ   ← DB DEFAULT now()
```

`chunks` and `embeddings` are parallel arrays: `chunks[i]` and `embeddings[i]` must refer to the same document chunk. The caller guarantees `len(chunks) == len(embeddings)`.

### pgvector Registration — Critical Detail

`psycopg[binary]` does NOT automatically handle pgvector types. Without `register_vector_async`, inserting a `list[float]` into a `vector` column raises a `psycopg.errors.DatatypeMismatch` error.

The `pgvector` package (`pgvector>=0.4.2` — already in `pyproject.toml`) provides:
```python
from pgvector.psycopg import register_vector_async

await register_vector_async(conn)  # Must be called before any vector INSERT/SELECT
```

After registration:
- `list[float]` → accepted as `vector` column value in INSERT parameters
- `vector` column values → returned as `list[float]` in SELECT results

**Do NOT use `numpy.ndarray`** — `EmbeddingRecord.vector` is `list[float]` and passes directly after registration.

### Test Pattern — `tests/store/conftest.py`

```python
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

This fixture:
- Runs after every test in `tests/store/` (autouse=True)
- Truncates all data tables in FK order (embeddings → chunks → document_versions → documents)
- Leaves migration state intact (schema tables remain)
- Makes `migrated_db` implicit — `clean_tables` depends on it so migrations always run first

### Test Pattern — `tests/store/test_document_store.py`

Tests create their own connections (do NOT use the `db_conn` fixture — it does a rollback at teardown which conflicts with `store_document`'s internal `conn.transaction()` commit):

```python
import psycopg
import pytest
from conftest import TEST_DSN
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord

def _make_chunk(index: int = 0) -> ChunkRecord:
    return ChunkRecord(content=f"chunk {index}", chunk_index=index, token_count=10)

def _make_embedding(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[float(i) / 100 for i in range(1024)],  # 1024-dim dummy vector
        model="voyage-3",
        provider="anthropic",
    )

async def test_store_document_first_ingest_creates_documents_row(migrated_db) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        doc_id = await store_document(
            conn,
            source_path="docs/test.md",
            file_hash="deadbeef",
            chunks=[_make_chunk()],
            embeddings=[_make_embedding()],
        )
        result = await conn.execute(
            "SELECT source_path, file_hash, current_version, status FROM documents WHERE id = %s",
            (doc_id,),
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "docs/test.md"
    assert row[1] == "deadbeef"
    assert row[2] == 1
    assert row[3] == "indexed"
```

Key points for all tests:
- Use `async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:` — creates a fresh connection per test
- The `clean_tables` autouse fixture (from `tests/store/conftest.py`) truncates data after each test
- `migrated_db` is a transitive dependency of `clean_tables` — no need to declare it explicitly in test signatures (but it doesn't hurt to add it)
- The dummy vector `[float(i)/100 for i in range(1024)]` produces 1024 floats — matching voyage-3 output dimension

### Atomicity Test Pattern

```python
async def test_store_document_atomicity_on_failure(migrated_db) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        try:
            async with conn.transaction():
                await store_document(
                    conn,
                    source_path="docs/fail.md",
                    file_hash="abc",
                    chunks=[_make_chunk()],
                    embeddings=[_make_embedding()],
                )
                raise RuntimeError("simulated crash")
        except RuntimeError:
            pass

        result = await conn.execute("SELECT COUNT(*) FROM documents")
        count = (await result.fetchone())[0]

    assert count == 0
```

Note: wrapping `store_document` in an OUTER `conn.transaction()` makes the outer one a no-op for the inner (psycopg3 uses savepoints for nested transactions). When the outer raises, psycopg3 rolls back to the savepoint, then rolls back the outer transaction, leaving the DB clean. After the `except` block, the connection is idle — the subsequent SELECT sees no rows.

### Architecture Compliance

- `store/db.py` imports from `store/models.py` only (intra-package) — this is correct
- `store/db.py` does NOT import from `ingestion/`, `retrieval/`, `services/`, or `mcp_server/`
- The type conversion from `Chunk` / `EmbeddingResult` (ingestion types) to `ChunkRecord` / `EmbeddingRecord` (store types) is done by the service layer in Story 2.4
- No bare `print()` calls — use structured logging if needed (but `store_document` has no logging; the service layer logs at the boundary)
- All DB calls are `async` — psycopg3 async connection throughout

### What `create_pool` Does (Leave Untouched)

`create_pool(dsn: str) -> Any` remains `raise NotImplementedError`. Story 2.4 (IngestService) implements this when wiring the service layer. It will require `psycopg_pool` package (`uv add psycopg_pool`). Do NOT add this dependency in Story 2.3.

### Forward-Looking Note for Story 2.5

Story 2.5 ACs require displaying `extraction_method` per version (`cos docs --versions <id>`). The current `document_versions` schema has NO `extraction_method` column. Story 2.5 will need to either:
- Add a new migration (e.g., `003_add_extraction_method.sql`) to add `extraction_method TEXT` to `document_versions`
- OR source the extraction_method from a different location

Story 2.3 does NOT add this column — it is explicitly out of scope.

### Files to Create or Modify

| File | Action | Key constraint |
|------|--------|----------------|
| `src/cos/store/db.py` | Add `store_document()` below `run_migrations()` | Import `register_vector_async`, `ChunkRecord`, `EmbeddingRecord`; do not touch existing functions |
| `tests/store/conftest.py` | Create new file | `clean_tables` autouse fixture; imports `TEST_DSN` from `conftest` |
| `tests/store/test_document_store.py` | Create new file | 8 tests listed in Task 3; uses fresh connections, not `db_conn` fixture |

### Cross-Story Notes

- **Story 2.2 contracts** — `store_document` accepts `ChunkRecord` (not `Chunk`). Field mapping: `Chunk.text` → `ChunkRecord.content`, `Chunk.chunk_index` → `ChunkRecord.chunk_index`, `Chunk.token_count` → `ChunkRecord.token_count`. `EmbeddingResult.vector/model/provider` → `EmbeddingRecord.vector/model/provider`.
- **Story 2.4 (IngestService)** will call `store_document` from `pipeline.py`. It computes `file_hash = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()` before the call. It also converts `Chunk` / `EmbeddingResult` objects to `ChunkRecord` / `EmbeddingRecord` before passing them. It implements `create_pool()` and manages connection lifecycle.
- **Story 2.5 (Document Provenance Listing)** queries `documents` and `document_versions` tables written by this story. The `source_path`, `ingested_at`, `current_version`, and chunk count query all flow from Story 2.3's writes.

### References

- DB schema: `src/cos/store/migrations/001_initial.sql` — complete table definitions
- Store models: `src/cos/store/models.py` — `ChunkRecord`, `EmbeddingRecord`, `DocumentVersion`
- pgvector psycopg3 usage: `pgvector>=0.4.2` already in `pyproject.toml` — `from pgvector.psycopg import register_vector_async`
- psycopg3 async transaction: `async with conn.transaction():` — auto-commits on exit, auto-rolls-back on exception
- Story 2.2 types: `src/cos/ingestion/chunker.py` (`Chunk`), `src/cos/ingestion/embedder.py` (`EmbeddingResult`) — read-only reference
- Existing test pattern: `tests/store/test_migrations.py` — uses `migrated_db` + `db_conn` fixtures from `conftest.py`
- Architecture boundary rules: `_bmad-output/planning-artifacts/architecture.md` — "cos/services/* only" cross-module import rule

## Dev Agent Record

### Agent Model Used

gpt-5.4

### Completion Notes List

- Added `store_document()` to the store layer with pgvector registration, single-transaction document/version/chunk/embedding writes, and version increments on re-ingest by `source_path`.
- Added `tests/store/conftest.py` to truncate provenance tables after each store test while preserving migration state.
- Added integration coverage for first ingest, provenance/version rows, chunk and embedding persistence, document ID return value, re-ingest preservation, rollback atomicity, and UTC-backed `ingested_at`.
- Verified the implementation with `uv run ruff check src/cos/store/db.py tests/store/conftest.py tests/store/test_document_store.py`, `uv run mypy src/cos/store/db.py tests/store/conftest.py tests/store/test_document_store.py`, and `uv run pytest tests/store/test_document_store.py tests/store/test_migrations.py`.

### File List

- _bmad-output/implementation-artifacts/2-3-provenance-storage-and-transactional-writes.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- src/cos/store/db.py
- tests/store/conftest.py
- tests/store/test_document_store.py

### Change Log

- 2026-04-23: Implemented transactional provenance storage, added isolated store integration tests, and moved Story 2.3 to review.
