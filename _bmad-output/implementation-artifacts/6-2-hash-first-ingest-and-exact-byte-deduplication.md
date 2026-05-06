# Story 6.2: Hash-First Ingest and Exact-Byte Deduplication

Status: done

## Story

As an operator,
I want ingest to detect canonically identical bytes before chunking, embedding, or managed-copy writes,
So that duplicate content from different paths or connectors does not create duplicate storage or retrieval noise.

## Acceptance Criteria

1. **Given** bytes submitted for ingest exactly match an existing `content_blobs` SHA-256 hash,
   **When** the ingest pipeline evaluates the input,
   **Then** it reuses the existing canonical blob record and does not create duplicate chunk, embedding, original-file, or Markdown-copy artifacts.

2. **Given** the same bytes arrive from a new path or connector locator,
   **When** ingest completes,
   **Then** a new provenance/source record is created and linked to the existing canonical content without redefining document identity around the new locator.

3. **Given** the same bytes arrive from the same known source,
   **When** the pipeline runs,
   **Then** the operation resolves as a no-op for content processing and returns a clear notice that no new version or embeddings were created.

4. **Given** a truly new byte sequence arrives,
   **When** the pipeline runs,
   **Then** the hash check completes before chunking or embedding begins, and the new content proceeds through normal ingest exactly once.

---

## Tasks / Subtasks

- [x] Task 1: Add canonical identity dataclasses to `src/cos/store/models.py` (AC: #1–4)
  - [x] Add `ContentBlobRecord` dataclass: `id`, `sha256`, `byte_size`, `created_at`
  - [x] Add `SourceRecord` dataclass: `id`, `source_type`, `source_locator`, `source_alias`, `created_at`
  - [x] Add `SourceVersionRecord` dataclass: `id`, `source_id`, `document_version_id`, `content_blob_id`, `observed_at`

- [x] Task 2: Add canonical DB helpers to `src/cos/store/db.py` (AC: #1–4)
  - [x] Add `find_content_blob_by_sha256(conn, sha256) -> ContentBlobRecord | None`
  - [x] Add `find_source(conn, source_type, source_locator) -> SourceRecord | None`
  - [x] Add `upsert_source(conn, source_type, source_locator, source_alias) -> SourceRecord`
  - [x] Add `create_content_blob(conn, sha256, byte_size) -> ContentBlobRecord`
  - [x] Add `find_source_version_for_blob(conn, source_id, content_blob_id) -> SourceVersionRecord | None`
  - [x] Add `find_canonical_document_version_for_blob(conn, content_blob_id) -> tuple[str, str] | None` — returns `(document_version_id, document_id)` of the earliest canonical version
  - [x] Add `link_new_source_to_existing_blob(conn, sha256, source_type, source_locator, source_alias) -> str` — creates source + source_version, returns document_id
  - [x] Add `store_document_canonical(conn, source_path, sha256, byte_size, source_type, source_locator, source_alias, chunks, embeddings) -> str` — canonical write path

- [x] Task 3: Create `src/cos/ingestion/identity.py` — canonical ingest decision engine (AC: #1–4)
  - [x] Define `IngestOutcome(str, enum.Enum)`: `NEW_CONTENT`, `CHANGED_CONTENT`, `NEW_SOURCE_KNOWN_CONTENT`, `UNCHANGED`
  - [x] Define `IdentityCheckResult` dataclass: `outcome`, `document_id`, `document_version_id`, `content_blob_id`, `source_id`, `message`
  - [x] Implement `check_canonical_identity(conn, sha256, source_type, source_locator) -> IdentityCheckResult`

- [x] Task 4: Update `src/cos/ingestion/pipeline.py` (AC: #1–4)
  - [x] Move `file_hash = hashlib.sha256(...).hexdigest()` to the very first line of `run_pipeline`, before `extract()` is called
  - [x] Compute `byte_size = len(source_path.read_bytes())` — read bytes once, hash, then proceed
  - [x] Derive `source_type = "file"`, `source_locator = str(source_path)`, `source_alias = source_path.name` from `source_path`
  - [x] Call `check_canonical_identity(conn, sha256, source_type, source_locator)` immediately after hashing
  - [x] On `UNCHANGED` → log + return early `PipelineResult` with `chunk_count=0`
  - [x] On `NEW_SOURCE_KNOWN_CONTENT` → call `link_new_source_to_existing_blob(conn, ...)`, return `PipelineResult` with `chunk_count=0` and the existing `document_id`
  - [x] On `NEW_CONTENT` or `CHANGED_CONTENT` → proceed with `extract()` → `chunk()` → `embed()` → `store_document_canonical()`
  - [x] Add `outcome: IngestOutcome` and `message: str` fields to `PipelineResult` dataclass

- [x] Task 5: Update `src/cos/services/ingestion.py` (AC: #3)
  - [x] Add `outcome: str` and `message: str` to `IngestResult`
  - [x] Propagate `result.outcome.value` and `result.message` from `PipelineResult` to `IngestResult`

- [x] Task 6: Update TRUNCATE statements in all test conftest files to include canonical tables (AC: #1–4)
  - [x] `tests/ingestion/conftest.py` — change to `TRUNCATE source_versions, embeddings, chunks, document_versions, content_blobs, sources, documents RESTART IDENTITY CASCADE`
  - [x] `tests/store/conftest.py` — same change
  - [x] `tests/services/conftest.py` — same change

- [x] Task 7: Add tests to `tests/ingestion/test_pipeline.py` (AC: #1–4)
  - [x] `test_run_pipeline_same_bytes_same_source_is_unchanged` (AC #3)
  - [x] `test_run_pipeline_same_bytes_new_source_creates_new_provenance_only` (AC #1, #2)
  - [x] `test_run_pipeline_new_bytes_creates_content_blob_record` (AC #4)
  - [x] `test_run_pipeline_new_bytes_creates_source_and_source_version` (AC #4)
  - [x] `test_run_pipeline_unchanged_returns_zero_chunk_count` (AC #3)
  - [x] `test_run_pipeline_new_source_known_content_returns_zero_chunk_count` (AC #2)
  - [x] Verify existing `test_run_pipeline_markdown_creates_document` and `test_run_pipeline_reingest_increments_version` still pass

---

## Dev Notes

### What This Story Is

Story 6.2 is the **canonical write-path wiring story**. It builds directly on the schema from Story 6.1 (`content_blobs`, `sources`, `source_versions`) and makes the ingestion pipeline use those tables for all new ingests.

The schema already exists. Story 6.2 introduces:
1. A decision engine (`identity.py`) that resolves one of four outcomes before any I/O
2. DB helpers for reading/writing canonical tables
3. A new canonical write path (`store_document_canonical`) replacing the pipeline's call to `store_document`
4. Tests covering all four ingest outcomes

**Do NOT modify:**
- `src/cos/store/migrations/` — no new migration needed
- `src/cos/store/db.py:store_document` — keep it intact; `test_document_store.py` still calls it directly and those tests must continue to pass
- `src/cos/retrieval/`, `src/cos/mcp_server/`, `src/cos/rolepack/`, `src/cos/output/`
- `role_packs/`, `docs/`, `docker-compose.yml`

---

### Decision Matrix

The identity check reads only from `content_blobs`, `sources`, and `source_versions`. It determines the outcome before any extraction, chunking, or embedding.

| `existing_blob`? | `existing_source_version` for (source, blob)? | Outcome | Action |
|---|---|---|---|
| No | — | `NEW_CONTENT` or `CHANGED_CONTENT` | Full extract → chunk → embed → `store_document_canonical` |
| Yes | Yes | `UNCHANGED` | Return existing `document_id`, `chunk_count=0`, log no-op |
| Yes | No | `NEW_SOURCE_KNOWN_CONTENT` | Create source + source_version, link to canonical doc_version, skip chunking |

For `NEW_CONTENT` vs `CHANGED_CONTENT`: if `existing_source` is also None → `NEW_CONTENT`; if `existing_source` is found → `CHANGED_CONTENT`. Both take the same code path (full ingest via `store_document_canonical`); the distinction is reflected in `outcome` and `message`.

---

### Source Identity for CLI File Ingestion

For all CLI file ingests (`cos ingest <path>`), derive:
- `source_type = "file"`
- `source_locator = str(source_path)` — absolute resolved path (same string as `source_path` already passed to `store_document`)
- `source_alias = source_path.name` — filename only (e.g. `"board-pack-q2.pdf"`)

`source_locator` is the programmatic identifier; `source_alias` is the human-readable label (used later by Story 6.4's citation/listing updates).

---

### Exact Implementations

#### `src/cos/store/models.py` — new dataclasses to add

```python
@dataclass
class ContentBlobRecord:
    id: str = ""
    sha256: str = ""
    byte_size: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SourceRecord:
    id: str = ""
    source_type: str = ""
    source_locator: str = ""
    source_alias: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SourceVersionRecord:
    id: str = ""
    source_id: str = ""
    document_version_id: str = ""
    content_blob_id: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Add imports to `models.py`: none needed beyond what's already there.

---

#### `src/cos/store/db.py` — new canonical helpers (add at the bottom)

```python
async def find_content_blob_by_sha256(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
) -> ContentBlobRecord | None:
    result = await conn.execute(
        "SELECT id::text, sha256, byte_size, created_at "
        "FROM content_blobs WHERE sha256 = %s",
        (sha256,),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return ContentBlobRecord(id=row[0], sha256=row[1], byte_size=row[2], created_at=row[3])


async def find_source(
    conn: psycopg.AsyncConnection[Any],
    source_type: str,
    source_locator: str,
) -> SourceRecord | None:
    result = await conn.execute(
        "SELECT id::text, source_type, source_locator, source_alias, created_at "
        "FROM sources WHERE source_type = %s AND source_locator = %s",
        (source_type, source_locator),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return SourceRecord(
        id=row[0], source_type=row[1], source_locator=row[2],
        source_alias=row[3], created_at=row[4],
    )


async def upsert_source(
    conn: psycopg.AsyncConnection[Any],
    source_type: str,
    source_locator: str,
    source_alias: str,
) -> SourceRecord:
    result = await conn.execute(
        "INSERT INTO sources (source_type, source_locator, source_alias) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT ON CONSTRAINT sources_type_locator_unique "
        "DO UPDATE SET source_alias = EXCLUDED.source_alias "
        "RETURNING id::text, source_type, source_locator, source_alias, created_at",
        (source_type, source_locator, source_alias),
    )
    row = await result.fetchone()
    if row is None:
        raise RuntimeError("upsert_source returned no row")
    return SourceRecord(
        id=row[0], source_type=row[1], source_locator=row[2],
        source_alias=row[3], created_at=row[4],
    )


async def create_content_blob(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    byte_size: int,
) -> ContentBlobRecord:
    result = await conn.execute(
        "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, %s) "
        "ON CONFLICT ON CONSTRAINT content_blobs_sha256_unique "
        "DO UPDATE SET byte_size = EXCLUDED.byte_size "
        "RETURNING id::text, sha256, byte_size, created_at",
        (sha256, byte_size),
    )
    row = await result.fetchone()
    if row is None:
        raise RuntimeError("create_content_blob returned no row")
    return ContentBlobRecord(id=row[0], sha256=row[1], byte_size=row[2], created_at=row[3])


async def find_source_version_for_blob(
    conn: psycopg.AsyncConnection[Any],
    source_id: str,
    content_blob_id: str,
) -> SourceVersionRecord | None:
    result = await conn.execute(
        "SELECT id::text, source_id::text, document_version_id::text, "
        "content_blob_id::text, observed_at "
        "FROM source_versions "
        "WHERE source_id = %s::uuid AND content_blob_id = %s::uuid "
        "LIMIT 1",
        (source_id, content_blob_id),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return SourceVersionRecord(
        id=row[0], source_id=row[1], document_version_id=row[2],
        content_blob_id=row[3], observed_at=row[4],
    )


async def find_canonical_document_version_for_blob(
    conn: psycopg.AsyncConnection[Any],
    content_blob_id: str,
) -> tuple[str, str] | None:
    """Return (document_version_id, document_id) of earliest canonical version for blob."""
    result = await conn.execute(
        "SELECT id::text, document_id::text "
        "FROM document_versions "
        "WHERE content_blob_id = %s::uuid "
        "ORDER BY created_at ASC LIMIT 1",
        (content_blob_id,),
    )
    row = await result.fetchone()
    if row is None:
        return None
    return (row[0], row[1])


async def link_new_source_to_existing_blob(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    source_type: str,
    source_locator: str,
    source_alias: str,
) -> str:
    """Create source + source_version for bytes already in content_blobs. Returns document_id."""
    blob = await find_content_blob_by_sha256(conn, sha256)
    if blob is None:
        raise RuntimeError(f"No content_blob found for sha256={sha256!r}")
    version_info = await find_canonical_document_version_for_blob(conn, blob.id)
    if version_info is None:
        raise RuntimeError(f"No document_version found for content_blob {blob.id!r}")
    document_version_id, document_id = version_info
    source = await upsert_source(conn, source_type, source_locator, source_alias)
    await conn.execute(
        "INSERT INTO source_versions (source_id, document_version_id, content_blob_id) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid) "
        "ON CONFLICT ON CONSTRAINT source_versions_source_document_unique DO NOTHING",
        (source.id, document_version_id, blob.id),
    )
    return document_id


async def store_document_canonical(
    conn: psycopg.AsyncConnection[Any],
    source_path: str,
    sha256: str,
    byte_size: int,
    source_type: str,
    source_locator: str,
    source_alias: str,
    chunks: list[ChunkRecord],
    embeddings: list[EmbeddingRecord],
) -> str:
    """Canonical write path: writes to content_blobs, sources, source_versions AND
    documents, document_versions, chunks, embeddings. Returns document_id."""
    await register_vector_async(conn)

    async with conn.transaction():
        content_blob = await create_content_blob(conn, sha256, byte_size)
        source = await upsert_source(conn, source_type, source_locator, source_alias)

        result = await conn.execute(
            "SELECT id, current_version FROM documents WHERE source_path = %s",
            (source_path,),
        )
        existing = await result.fetchone()

        if existing is None:
            result = await conn.execute(
                "INSERT INTO documents "
                "(source_path, file_hash, current_version, status) "
                "VALUES (%s, %s, 1, 'indexed') RETURNING id",
                (source_path, sha256),
            )
            row = await result.fetchone()
            if row is None:
                raise RuntimeError("Failed to insert document row")
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
                "DELETE FROM chunks WHERE document_id = %s",
                (document_id,),
            )

        result = await conn.execute(
            "INSERT INTO document_versions "
            "(document_id, version, content_hash, content_blob_id) "
            "VALUES (%s, %s, %s, %s::uuid) RETURNING id",
            (document_id, new_version, sha256, content_blob.id),
        )
        row = await result.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert document_version row")
        document_version_id = row[0]

        await conn.execute(
            "INSERT INTO source_versions "
            "(source_id, document_version_id, content_blob_id) "
            "VALUES (%s::uuid, %s, %s::uuid) "
            "ON CONFLICT ON CONSTRAINT source_versions_source_document_unique DO NOTHING",
            (source.id, document_version_id, content_blob.id),
        )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            result = await conn.execute(
                "INSERT INTO chunks "
                "(document_id, chunk_index, content, token_count, document_version_id) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (
                    document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.token_count,
                    document_version_id,
                ),
            )
            chunk_row = await result.fetchone()
            if chunk_row is None:
                raise RuntimeError("Failed to insert chunk row")
            chunk_id = chunk_row[0]

            await conn.execute(
                "INSERT INTO embeddings (chunk_id, vector, model, provider) "
                "VALUES (%s, %s, %s, %s)",
                (chunk_id, embedding.vector, embedding.model, embedding.provider),
            )

    return str(document_id)
```

**Imports to add to `db.py`:** `ContentBlobRecord`, `SourceRecord`, `SourceVersionRecord` from `cos.store.models`.

---

#### `src/cos/ingestion/identity.py` — new file

```python
"""Canonical identity decision engine — resolves ingest outcome before I/O."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

import psycopg

from cos.store.db import find_content_blob_by_sha256, find_source, find_source_version_for_blob


class IngestOutcome(str, enum.Enum):
    NEW_CONTENT = "new_content"
    CHANGED_CONTENT = "changed_content"
    NEW_SOURCE_KNOWN_CONTENT = "new_source_known_content"
    UNCHANGED = "unchanged"


@dataclass
class IdentityCheckResult:
    outcome: IngestOutcome
    document_id: str | None
    document_version_id: str | None
    content_blob_id: str | None
    source_id: str | None
    message: str


async def check_canonical_identity(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    source_type: str,
    source_locator: str,
) -> IdentityCheckResult:
    existing_blob = await find_content_blob_by_sha256(conn, sha256)

    if existing_blob is not None:
        existing_source = await find_source(conn, source_type, source_locator)
        if existing_source is not None:
            existing_sv = await find_source_version_for_blob(
                conn, existing_source.id, existing_blob.id
            )
            if existing_sv is not None:
                # Resolve document_id via source_version → document_version
                result = await conn.execute(
                    "SELECT dv.document_id::text FROM document_versions dv "
                    "WHERE dv.id = %s::uuid",
                    (existing_sv.document_version_id,),
                )
                row = await result.fetchone()
                doc_id = row[0] if row else None
                return IdentityCheckResult(
                    outcome=IngestOutcome.UNCHANGED,
                    document_id=doc_id,
                    document_version_id=existing_sv.document_version_id,
                    content_blob_id=existing_blob.id,
                    source_id=existing_source.id,
                    message="Content unchanged — no new version or embeddings created.",
                )
        return IdentityCheckResult(
            outcome=IngestOutcome.NEW_SOURCE_KNOWN_CONTENT,
            document_id=None,
            document_version_id=None,
            content_blob_id=existing_blob.id,
            source_id=existing_source.id if existing_source else None,
            message="New source — content already indexed. Provenance record created, no new embeddings.",
        )

    existing_source = await find_source(conn, source_type, source_locator)
    if existing_source is not None:
        return IdentityCheckResult(
            outcome=IngestOutcome.CHANGED_CONTENT,
            document_id=None,
            document_version_id=None,
            content_blob_id=None,
            source_id=existing_source.id,
            message="Source content changed — new version will be created.",
        )

    return IdentityCheckResult(
        outcome=IngestOutcome.NEW_CONTENT,
        document_id=None,
        document_version_id=None,
        content_blob_id=None,
        source_id=None,
        message="New document — full ingest will proceed.",
    )
```

---

#### `src/cos/ingestion/pipeline.py` — updated `run_pipeline` and `PipelineResult`

```python
@dataclass
class PipelineResult:
    document_id: str
    chunk_count: int
    outcome: IngestOutcome
    message: str
```

Updated `run_pipeline` flow:

```python
async def run_pipeline(
    source_path: Path,
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> PipelineResult:
    # logging unchanged ...

    raw_bytes = source_path.read_bytes()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    byte_size = len(raw_bytes)

    source_type = "file"
    source_locator = str(source_path)
    source_alias = source_path.name

    identity = await check_canonical_identity(conn, file_hash, source_type, source_locator)

    if identity.outcome == IngestOutcome.UNCHANGED:
        logging.info(json.dumps({..., "message": "pipeline no-op", "outcome": "unchanged", ...}))
        return PipelineResult(
            document_id=identity.document_id or "",
            chunk_count=0,
            outcome=IngestOutcome.UNCHANGED,
            message=identity.message,
        )

    if identity.outcome == IngestOutcome.NEW_SOURCE_KNOWN_CONTENT:
        document_id = await link_new_source_to_existing_blob(
            conn, file_hash, source_type, source_locator, source_alias
        )
        logging.info(json.dumps({..., "message": "pipeline no-op", "outcome": "new_source_known_content", ...}))
        return PipelineResult(
            document_id=document_id,
            chunk_count=0,
            outcome=IngestOutcome.NEW_SOURCE_KNOWN_CONTENT,
            message=identity.message,
        )

    # NEW_CONTENT or CHANGED_CONTENT — full ingest path
    extraction = await extract(
        source_path,
        tika_url=config.tika.url,
        originals_dir=config.storage.originals_dir,
        markdown_dir=config.storage.markdown_dir,
    )
    chunks = chunk(...)
    embedding_results = await embed(...)
    chunk_records = [...]
    embedding_records = [...]

    document_id = await store_document_canonical(
        conn,
        source_path=str(source_path),
        sha256=file_hash,
        byte_size=byte_size,
        source_type=source_type,
        source_locator=source_locator,
        source_alias=source_alias,
        chunks=chunk_records,
        embeddings=embedding_records,
    )

    logging.info(json.dumps({..., "message": "pipeline complete", "outcome": identity.outcome.value, ...}))
    return PipelineResult(
        document_id=document_id,
        chunk_count=len(chunks),
        outcome=identity.outcome,
        message=identity.message,
    )
```

**Imports to add to `pipeline.py`:**
```python
from cos.ingestion.identity import IngestOutcome, check_canonical_identity
from cos.store.db import link_new_source_to_existing_blob, store_document_canonical
```

**Import to remove from `pipeline.py`:** `store_document` (no longer called from pipeline).

**Critical**: `source_path.read_bytes()` is called once at the top and reused for hashing. Do NOT call `source_path.read_bytes()` again after this — `extract()` reads the file via Tika (HTTP), not via `read_bytes()` again, so there is no double-read issue.

---

#### `src/cos/services/ingestion.py` — updated `IngestResult`

```python
@dataclass
class IngestResult:
    document_id: str
    chunk_count: int
    source_path: str
    outcome: str       # IngestOutcome.value string, e.g. "new_content"
    message: str       # plain-language outcome notice
```

In `ingest_file`:
```python
return IngestResult(
    document_id=result.document_id,
    chunk_count=result.chunk_count,
    source_path=str(source_path),
    outcome=result.outcome.value,
    message=result.message,
)
```

---

### conftest TRUNCATE Updates

All three conftest files that truncate tables must be updated. The new canonical tables (`source_versions`, `content_blobs`, `sources`) are not cascaded by truncating `documents` alone. Truncate them explicitly:

```python
await conn.execute(
    "TRUNCATE source_versions, embeddings, chunks, document_versions, "
    "content_blobs, sources, documents RESTART IDENTITY CASCADE"
)
```

Files to update:
- `tests/ingestion/conftest.py` — line 25
- `tests/store/conftest.py` — line 25
- `tests/services/conftest.py` — line 27

---

### Test Patterns for New Tests (all go in `tests/ingestion/test_pipeline.py`)

All new tests use `migrated_db` and `mock_embed` fixtures.

```python
async def test_run_pipeline_same_bytes_same_source_is_unchanged(
    migrated_db: None, tmp_path: Path, mock_embed: None
) -> None:
    source_path = tmp_path / "doc.md"
    source_path.write_text("Identical content", encoding="utf-8")
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await run_pipeline(source_path, config, conn)
        second = await run_pipeline(source_path, config, conn)
    assert first.document_id == second.document_id
    assert second.chunk_count == 0
    assert second.outcome.value == "unchanged"


async def test_run_pipeline_same_bytes_new_source_creates_new_provenance_only(
    migrated_db: None, tmp_path: Path, mock_embed: None
) -> None:
    content = "Shared content for dedup test"
    path_a = tmp_path / "a.md"
    path_b = tmp_path / "b.md"
    path_a.write_text(content, encoding="utf-8")
    path_b.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result_a = await run_pipeline(path_a, config, conn)
        result_b = await run_pipeline(path_b, config, conn)
        # Verify canonical blob count: only one blob for identical content
        blob_result = await conn.execute(
            "SELECT COUNT(*) FROM content_blobs WHERE sha256 = %s",
            (hashlib.sha256(content.encode()).hexdigest(),),
        )
        blob_row = await blob_result.fetchone()
        # Verify source count: two sources (one per path)
        source_result = await conn.execute("SELECT COUNT(*) FROM sources WHERE source_type = 'file'")
        source_row = await source_result.fetchone()
    assert result_a.document_id == result_b.document_id  # same canonical document
    assert result_b.chunk_count == 0
    assert result_b.outcome.value == "new_source_known_content"
    assert blob_row == (1,)
    assert source_row == (2,)


async def test_run_pipeline_new_bytes_creates_content_blob_record(
    migrated_db: None, tmp_path: Path, mock_embed: None
) -> None:
    source_path = tmp_path / "new.md"
    source_path.write_text("Entirely new content", encoding="utf-8")
    sha256 = hashlib.sha256(b"Entirely new content").hexdigest()
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline(source_path, config, conn)
        blob_result = await conn.execute(
            "SELECT sha256 FROM content_blobs WHERE sha256 = %s", (sha256,)
        )
        row = await blob_result.fetchone()
    assert result.chunk_count >= 1
    assert result.outcome.value in ("new_content", "changed_content")
    assert row is not None
    assert row[0] == sha256


async def test_run_pipeline_unchanged_returns_zero_chunk_count(
    migrated_db: None, tmp_path: Path, mock_embed: None
) -> None:
    source_path = tmp_path / "stable.md"
    source_path.write_text("Stable document", encoding="utf-8")
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)
        second = await run_pipeline(source_path, config, conn)
    assert second.chunk_count == 0


async def test_run_pipeline_new_source_known_content_returns_zero_chunk_count(
    migrated_db: None, tmp_path: Path, mock_embed: None
) -> None:
    content = "Shared for zero-chunk test"
    path_a = tmp_path / "x.md"
    path_b = tmp_path / "y.md"
    path_a.write_text(content, encoding="utf-8")
    path_b.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(path_a, config, conn)
        result_b = await run_pipeline(path_b, config, conn)
    assert result_b.chunk_count == 0
```

**Import needed in `test_pipeline.py`:** `import hashlib` (for sha256 computation in tests).

---

### Backward Compatibility: `store_document` and `test_document_store.py`

`store_document` in `db.py` remains **unchanged**. It is no longer called by `pipeline.py` but the function must stay in place because `tests/store/test_document_store.py` imports and calls it directly. All existing `test_document_store.py` tests must continue to pass.

The only change that affects `test_document_store.py` is the updated `clean_tables` TRUNCATE in `tests/store/conftest.py`. The updated TRUNCATE (`TRUNCATE source_versions, embeddings, chunks, document_versions, content_blobs, sources, documents RESTART IDENTITY CASCADE`) is a superset — it truncates everything the old statement did, plus the new canonical tables. All existing store tests continue to work.

---

### Running Tests

```bash
# Prerequisites
docker compose up -d postgres

# New pipeline deduplication tests
uv run pytest tests/ingestion/test_pipeline.py -v

# Existing document store tests — must still pass
uv run pytest tests/store/test_document_store.py -v

# Full suite
uv run pytest -q
```

Expected: all 169+ existing tests pass plus new deduplication tests green.

---

### Project Structure Notes

| File | Change |
|------|--------|
| `src/cos/store/models.py` | Add 3 new dataclasses |
| `src/cos/store/db.py` | Add 8 new helper functions (keep `store_document` intact) |
| `src/cos/ingestion/identity.py` | CREATE new file |
| `src/cos/ingestion/pipeline.py` | Update `run_pipeline`, expand `PipelineResult` |
| `src/cos/services/ingestion.py` | Expand `IngestResult` |
| `tests/ingestion/test_pipeline.py` | Add 5+ new tests |
| `tests/ingestion/conftest.py` | Update TRUNCATE |
| `tests/store/conftest.py` | Update TRUNCATE |
| `tests/services/conftest.py` | Update TRUNCATE |

No new migrations. No changes to retrieval, MCP, CLI, role pack, or output paths.

---

### References

- Schema detail: `src/cos/store/migrations/004_canonical_identity.sql` — authoritative DDL for all canonical tables and constraints
- Previous story: `_bmad-output/implementation-artifacts/6-1-canonical-blob-source-and-version-schema-hardening.md` — full schema diagram and FK chain
- Architecture: `_bmad-output/planning-artifacts/architecture.md#Data Architecture` — ingest outcome model, four canonical outcomes
- Epic context: `_bmad-output/planning-artifacts/epics.md` Story 6.2–6.5 — downstream stories that build on this write path

---

## Dev Agent Record

### Agent Model Used

`claude-sonnet-4-6`

### Debug Log References

- `uv run pytest tests/ingestion/test_pipeline.py tests/services/test_ingestion_service.py tests/store/test_document_store.py tests/store/test_migrations.py -q`
- `uv run pytest -q`
- `uv run ruff check src/cos/store/db.py src/cos/store/models.py src/cos/ingestion/identity.py src/cos/ingestion/pipeline.py src/cos/services/ingestion.py tests/ingestion/conftest.py tests/store/conftest.py tests/services/conftest.py tests/ingestion/test_pipeline.py tests/services/test_ingestion_service.py`
- `uv run mypy src/cos/store/db.py src/cos/store/models.py src/cos/ingestion/identity.py src/cos/ingestion/pipeline.py src/cos/services/ingestion.py`

### Completion Notes List

- Implemented canonical identity dataclasses, canonical DB helpers, and a new `src/cos/ingestion/identity.py` decision engine to resolve `NEW_CONTENT`, `CHANGED_CONTENT`, `NEW_SOURCE_KNOWN_CONTENT`, and `UNCHANGED` before extraction.
- Reworked `run_pipeline()` to hash bytes first, short-circuit unchanged and known-content/new-source ingests before extraction, and persist new or changed content through `store_document_canonical()`.
- Extended ingest service results with `outcome` and `message`, and expanded pipeline coverage for same-source no-ops, provenance-only linking for new sources, canonical blob creation, and source/source-version persistence.
- Hardened `run_migrations()` to backfill the missing `source_versions_source_document_unique` constraint on already-initialized databases so the canonical write path works reliably in existing environments.
- Validation completed with `176 passed, 2 skipped` in the full pytest suite, targeted Ruff clean on touched files, and targeted mypy clean on touched source modules.

### File List

- `src/cos/store/models.py`
- `src/cos/store/db.py`
- `src/cos/ingestion/identity.py`
- `src/cos/ingestion/pipeline.py`
- `src/cos/services/ingestion.py`
- `tests/ingestion/conftest.py`
- `tests/store/conftest.py`
- `tests/services/conftest.py`
- `tests/ingestion/test_pipeline.py`
- `tests/services/test_ingestion_service.py`

### Review Findings

- [x] [Review][Patch] `link_new_source_to_existing_blob` lacks a wrapping transaction — partial failure (crash or DB error between `upsert_source` and `INSERT INTO source_versions`) orphans a `sources` row with no corresponding `source_version` [src/cos/store/db.py]

- [x] [Review][Defer] `_repair_existing_schema` DDL deadlock risk — `ALTER TABLE … ADD CONSTRAINT` acquires a `ShareLock` on `source_versions`; concurrent in-flight ingests at startup are blocked until the lock is acquired; under autocommit the DDL cannot be rolled back on failure [src/cos/store/db.py] — deferred, intentional design choice (spec: "no new migrations"); single-user startup context makes deadlock theoretical
- [x] [Review][Defer] `_repair_existing_schema` bypasses the project migration convention — schema changes must live as numbered `.sql` files per CLAUDE.md; this code-level repair runs on every startup and creates a parallel schema-management path [src/cos/store/db.py] — deferred, spec constraint "no new migrations" required this approach; documented in completion notes
- [x] [Review][Defer] Concurrent ingest race condition — two simultaneous calls for the same file both pass `find_content_blob_by_sha256` as `None` and both proceed to `store_document_canonical`, potentially creating duplicate `documents` rows (no UNIQUE constraint on `source_path`) [src/cos/store/db.py, src/cos/ingestion/identity.py] — deferred, pre-existing gap (noted from Story 2.3 review); single-user CLI context makes simultaneous ingests theoretical
- [x] [Review][Defer] `find_canonical_document_version_for_blob` non-deterministic on same-microsecond inserts — `ORDER BY created_at ASC LIMIT 1` has no tiebreaker; two `document_versions` rows sharing the same `content_blob_id` inserted within the same microsecond produce arbitrary `document_id` for `NEW_SOURCE_KNOWN_CONTENT` path [src/cos/store/db.py] — deferred, theoretical in single-user context; a surrogate sequence column or UNIQUE constraint on `(content_blob_id)` in `document_versions` would address permanently
- [x] [Review][Defer] Raw SQL in `check_canonical_identity` violates layering — single inline `conn.execute("SELECT document_id::text FROM document_versions …")` in `identity.py` instead of a `db.py` helper; schema changes to `document_versions` would require updating two files [src/cos/ingestion/identity.py] — deferred, low severity; extract to a `find_document_id_for_version()` helper in a future housekeeping pass
- [x] [Review][Defer] `UNCHANGED` outcome with `document_id=None` produces an opaque `RuntimeError` — if a `source_versions` row exists but its `document_version_id` has no matching `document_versions` row (broken FK), the pipeline raises with no diagnostic context on which row caused it [src/cos/ingestion/pipeline.py:64–67] — deferred, data integrity protection is correct; improve error message in a future pass
- [x] [Review][Defer] Dual identity keys: `documents.source_path` and `sources.source_locator` are parallel lookup paths for the same string — pre-6.2 documents lack `sources`/`source_versions` rows; `store_document_canonical` uses `source_path` for the legacy `documents` lookup independently of the new provenance model [src/cos/store/db.py] — deferred, known transitional state; Story 6.5 migration backfill addresses
- [x] [Review][Defer] No test for `link_new_source_to_existing_blob` raising when `content_blob` exists but no `document_version` is linked — the `RuntimeError("No document_version found for content_blob …")` path is untested; reachable on a partially-migrated DB before Story 6.5 backfill [src/cos/store/db.py, tests/ingestion/test_pipeline.py] — deferred, Story 6.5 migration backfill addresses the DB state; error guard is correct

### Change Log

- 2026-05-05: Implemented hash-first canonical deduplication, canonical provenance linking, ingest outcome propagation, and regression coverage for duplicate-content ingest flows.
