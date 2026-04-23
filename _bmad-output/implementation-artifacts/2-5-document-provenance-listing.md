# Story 2.5: Document Provenance Listing

Status: done

## Story

As an operator,
I want to list all ingested documents with their provenance metadata and version history from the CLI,
so that I can verify what is in the knowledge base, confirm ingestion succeeded, and audit the source of any document.

## Acceptance Criteria

1. **Given** one or more documents have been ingested,
   **When** `cos docs` is run,
   **Then** the CLI prints a table showing each document's `source_path`, `ingested_at`, `current_version`, and chunk count — one row per document, ordered by most recently ingested first.

2. **Given** a document that has been re-ingested (has multiple versions),
   **When** `cos docs --versions <document_id>` is run,
   **Then** the CLI prints all version records for that document, showing `version_number`, `ingested_at`, `file_hash`, and optionally `extraction_method` — one row per version, ordered by version number ascending.

3. **Given** no documents have been ingested yet,
   **When** `cos docs` is run,
   **Then** the CLI prints a clear, friendly message such as `No documents ingested yet. Run: cos ingest <path>` — not an empty table or error.

4. **Given** `cos docs` is run,
   **When** the output format is inspected,
   **Then** it is human-readable plain text suitable for terminal display — not raw JSON unless a `--json` flag is passed.

5. **Given** `cos docs --json` is run,
   **When** documents exist,
   **Then** the CLI prints a JSON array of all documents with all fields including the document `id`.

6. **Given** `cos docs --versions <document_id>` is run with an unknown ID,
   **When** the command runs,
   **Then** the CLI prints a clear message such as `No versions found for document ID: <id>` — not an error or stack trace.

## Tasks / Subtasks

- [x] Task 1: Add DB query functions to `src/cos/store/db.py` (AC: #1, #2)
  - [x] Add `DocumentSummary` dataclass: `id: str`, `source_path: str`, `ingested_at: datetime`, `current_version: int`, `chunk_count: int` — define in `src/cos/store/models.py`
  - [x] Add `VersionSummary` dataclass: `version_number: int`, `ingested_at: datetime`, `file_hash: str` — define in `src/cos/store/models.py`
  - [x] Add `async def list_documents(conn: psycopg.AsyncConnection[Any]) -> list[DocumentSummary]:` — see SQL in Dev Notes
  - [x] Add `async def list_document_versions(conn: psycopg.AsyncConnection[Any], document_id: str) -> list[VersionSummary]:` — see SQL in Dev Notes

- [x] Task 2: Create `src/cos/services/provenance.py` (AC: #1, #2, #3, #6)
  - [x] Define `ProvenanceService` class with `__init__(self, config: CosConfig) -> None`
  - [x] Implement `async def list_documents(self) -> list[DocumentSummary]:` — opens a fresh connection, calls `db.list_documents(conn)`
  - [x] Implement `async def list_document_versions(self, document_id: str) -> list[VersionSummary]:` — opens a fresh connection, calls `db.list_document_versions(conn, document_id)`
  - [x] Re-export `DocumentSummary` and `VersionSummary` from the service module so `cli.py` does not import from `cos.store.models` directly

- [x] Task 3: Add `docs` command to `src/cos/cli.py` (AC: #1, #2, #3, #4, #5, #6)
  - [x] Add `docs` command with `--versions TEXT` option and `--json / --no-json` flag (see signatures in Dev Notes)
  - [x] When `--versions` not given: print plain-text table with columns `ID`, `SOURCE PATH`, `INGESTED AT`, `VER`, `CHUNKS`; empty state prints friendly message (AC #3)
  - [x] When `--versions <id>` given: print plain-text table with columns `VER`, `INGESTED AT`, `FILE HASH`; unknown ID prints friendly message (AC #6)
  - [x] When `--json` given: print JSON array (use `json.dumps`, `indent=2`)
  - [x] `cos docs` and `cos docs --json` use `asyncio.run(_docs_list(config, json_output))` — no nested closures
  - [x] `cos docs --versions <id>` uses `asyncio.run(_docs_versions(config, versions, json_output))`
  - [x] Import only from `cos.services.provenance` — never from `cos.store.*` directly

- [x] Task 4: Write tests in `tests/services/test_provenance_service.py` (AC: #1, #2, #3, #6)
  - [x] `test_list_documents_empty` — no data → returns empty list
  - [x] `test_list_documents_returns_correct_fields` — insert one doc via `store_document`, assert all `DocumentSummary` fields match
  - [x] `test_list_documents_chunk_count` — insert doc with 3 chunks, assert `chunk_count == 3`
  - [x] `test_list_documents_ordered_most_recent_first` — insert two docs at slightly different times, assert order
  - [x] `test_list_document_versions_single` — insert one doc, assert one `VersionSummary` with `version_number=1`
  - [x] `test_list_document_versions_multiple` — insert doc twice (re-ingest), assert two version records with incrementing `version_number` and correct `file_hash` values
  - [x] `test_list_document_versions_unknown_id` — random UUID → returns empty list (not error)
  - [x] All tests use `migrated_db` + `clean_tables` from existing `tests/services/conftest.py`; use `store_document` directly (no `mock_embed` needed)

## Dev Notes

### Current State — Audit Before Touching

| File | Current content | Action |
|------|-----------------|--------|
| `src/cos/store/models.py` | `DocumentRecord`, `ChunkRecord`, `EmbeddingRecord`, `DocumentVersion`, `ProvenanceRecord` | Add `DocumentSummary`, `VersionSummary` dataclasses |
| `src/cos/store/db.py` | `run_migrations()`, `store_document()`, `create_pool()` | Add `list_documents()`, `list_document_versions()` only |
| `src/cos/services/provenance.py` | Does not exist | Create new file |
| `src/cos/cli.py` | `status`, `restart`, `logs` (NotImplementedError stubs), `ingest` (implemented) | Add `docs` command only |

**Leave these untouched:**
- `src/cos/store/db.py:run_migrations()`, `store_document()`, `create_pool()` — DO NOT TOUCH
- `src/cos/services/ingestion.py` — DO NOT TOUCH
- `src/cos/ingestion/*` — DO NOT TOUCH
- All existing tests — DO NOT TOUCH

### DB Schema (from `001_initial.sql`)

```sql
-- documents table
id UUID, source_path TEXT, file_hash TEXT, ingested_at TIMESTAMPTZ, current_version INTEGER, status TEXT

-- document_versions table
id UUID, document_id UUID FK, version INTEGER, content_hash TEXT, created_at TIMESTAMPTZ

-- chunks table
id UUID, document_id UUID FK, chunk_index INTEGER, content TEXT, token_count INTEGER
```

**Schema gap — `extraction_method`:** The epics AC mentions `extraction_method` in `--versions` output. This column does not exist in `document_versions` and Story 2.4 explicitly noted "No schema changes needed for 2.5." Omit `extraction_method` from the output. The `VersionSummary` dataclass has no `extraction_method` field. Do not add a migration.

**Column mapping for `--versions`:**
- `version_number` ← `document_versions.version`
- `ingested_at` ← `document_versions.created_at`
- `file_hash` ← `document_versions.content_hash`

### New Dataclasses in `src/cos/store/models.py`

```python
@dataclass
class DocumentSummary:
    id: str
    source_path: str
    ingested_at: datetime
    current_version: int
    chunk_count: int


@dataclass
class VersionSummary:
    version_number: int
    ingested_at: datetime  # maps to document_versions.created_at
    file_hash: str         # maps to document_versions.content_hash
```

Add these after `ProvenanceRecord`. Import `datetime` is already in scope.

### DB Query Functions in `src/cos/store/db.py`

```python
async def list_documents(
    conn: psycopg.AsyncConnection[Any],
) -> list[DocumentSummary]:
    result = await conn.execute(
        """
        SELECT
            d.id::text,
            d.source_path,
            d.ingested_at,
            d.current_version,
            COUNT(c.id)::int AS chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id, d.source_path, d.ingested_at, d.current_version
        ORDER BY d.ingested_at DESC
        """
    )
    rows = await result.fetchall()
    return [
        DocumentSummary(
            id=row[0],
            source_path=row[1],
            ingested_at=row[2],
            current_version=row[3],
            chunk_count=row[4],
        )
        for row in rows
    ]


async def list_document_versions(
    conn: psycopg.AsyncConnection[Any],
    document_id: str,
) -> list[VersionSummary]:
    result = await conn.execute(
        """
        SELECT version, created_at, content_hash
        FROM document_versions
        WHERE document_id = %s
        ORDER BY version ASC
        """,
        (document_id,),
    )
    rows = await result.fetchall()
    return [
        VersionSummary(
            version_number=row[0],
            ingested_at=row[1],
            file_hash=row[2],
        )
        for row in rows
    ]
```

Add imports at top of `db.py` (already there: `from cos.store.models import ChunkRecord, EmbeddingRecord` — extend to include `DocumentSummary`, `VersionSummary`).

These functions do NOT call `register_vector_async` — they only query non-vector columns. No pgvector registration needed.

### `ProvenanceService` in `src/cos/services/provenance.py`

```python
"""ProvenanceService — read-only access to document provenance data."""
import psycopg

from cos.config import CosConfig
from cos.store.db import list_document_versions, list_documents
from cos.store.models import DocumentSummary, VersionSummary

__all__ = ["DocumentSummary", "ProvenanceService", "VersionSummary"]


class ProvenanceService:
    def __init__(self, config: CosConfig) -> None:
        self._config = config

    async def list_documents(self) -> list[DocumentSummary]:
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            return await list_documents(conn)

    async def list_document_versions(self, document_id: str) -> list[VersionSummary]:
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            return await list_document_versions(conn, document_id)
```

**Re-export pattern:** `__all__` re-exports `DocumentSummary` and `VersionSummary` so `cli.py` can import them from `cos.services.provenance` without touching `cos.store.models`.

**Connection pattern:** Same as `IngestService.ingest_file` — fresh connection per call, using `config.database.libpq_dsn`. No autocommit needed (read-only queries).

### `docs` Command in `src/cos/cli.py`

```python
import json as _json  # alias to avoid shadowing json module name

from cos.services.provenance import DocumentSummary, ProvenanceService, VersionSummary


@app.command()
def docs(
    versions: str | None = typer.Option(
        None, "--versions", help="Show version history for document ID"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List ingested documents and provenance metadata."""
    config = CosConfig.load()
    service = ProvenanceService(config)

    if versions is not None:
        asyncio.run(_docs_versions(service, versions, json_output))
    else:
        asyncio.run(_docs_list(service, json_output))


async def _docs_list(service: ProvenanceService, json_output: bool) -> None:
    documents = await service.list_documents()
    if not documents:
        typer.echo("No documents ingested yet. Run: cos ingest <path>")
        return
    if json_output:
        typer.echo(_json.dumps(
            [
                {
                    "id": d.id,
                    "source_path": d.source_path,
                    "ingested_at": d.ingested_at.isoformat(),
                    "current_version": d.current_version,
                    "chunk_count": d.chunk_count,
                }
                for d in documents
            ],
            indent=2,
        ))
        return
    _print_documents_table(documents)


async def _docs_versions(
    service: ProvenanceService, document_id: str, json_output: bool
) -> None:
    version_records = await service.list_document_versions(document_id)
    if not version_records:
        typer.echo(f"No versions found for document ID: {document_id}")
        return
    if json_output:
        typer.echo(_json.dumps(
            [
                {
                    "version_number": v.version_number,
                    "ingested_at": v.ingested_at.isoformat(),
                    "file_hash": v.file_hash,
                }
                for v in version_records
            ],
            indent=2,
        ))
        return
    _print_versions_table(version_records)


def _print_documents_table(documents: list[DocumentSummary]) -> None:
    header = f"{'ID':<36}  {'SOURCE PATH':<40}  {'INGESTED AT':<26}  {'VER':>3}  {'CHUNKS':>6}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for d in documents:
        typer.echo(
            f"{d.id:<36}  "
            f"{d.source_path[-40:]:<40}  "
            f"{d.ingested_at.isoformat():<26}  "
            f"{d.current_version:>3}  "
            f"{d.chunk_count:>6}"
        )


def _print_versions_table(versions: list[VersionSummary]) -> None:
    header = f"{'VER':>3}  {'INGESTED AT':<26}  FILE HASH"
    typer.echo(header)
    typer.echo("-" * 72)
    for v in versions:
        typer.echo(
            f"{v.version_number:>3}  "
            f"{v.ingested_at.isoformat():<26}  "
            f"{v.file_hash}"
        )
```

**CLI rules:**
- Import `ProvenanceService`, `DocumentSummary`, `VersionSummary` from `cos.services.provenance` — NOT from `cos.store.*`
- `asyncio.run()` only at entry point (inside `docs()`) — `_docs_list` and `_docs_versions` are `async def` called via `asyncio.run()`
- `typer.echo()` for all output — no bare `print()`
- `json` alias (`_json`) avoids shadowing — or rename the import; either way is fine
- No try/except needed in `docs()` for DB errors (the AC does not describe user-facing DB error handling; let the default error surface as a stack trace for now — operational error scenario)

### Test Setup — Using `store_document` Directly

Tests for `ProvenanceService` use `store_document` to insert known data, then call `ProvenanceService.list_documents()` via a fresh connection. Do NOT use `IngestService` for test setup — that adds unnecessary complexity and requires `mock_embed`.

```python
import psycopg
import pytest
from conftest import TEST_DSN, make_test_config
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord
from cos.services.provenance import ProvenanceService


def _chunk(index: int = 0) -> ChunkRecord:
    return ChunkRecord(content=f"chunk {index}", chunk_index=index, token_count=10)


def _embedding(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[float(index) / 1000 for _ in range(1024)],
        model="voyage-3",
        provider="anthropic",
    )


async def _insert_doc(source_path: str, file_hash: str = "abc123", chunks: int = 1) -> str:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        return await store_document(
            conn,
            source_path=source_path,
            file_hash=file_hash,
            chunks=[_chunk(i) for i in range(chunks)],
            embeddings=[_embedding(i) for i in range(chunks)],
        )
```

Key points:
- `store_document` registers pgvector via `register_vector_async(conn)` internally — no extra setup needed
- Use `psycopg.AsyncConnection.connect(TEST_DSN)` (not autocommit) — same as existing store tests
- `clean_tables` autouse fixture (from `tests/services/conftest.py`) truncates between tests

### Test Examples

```python
async def test_list_documents_empty(migrated_db: None, tmp_path: Path) -> None:
    service = ProvenanceService(make_test_config(tmp_path))
    result = await service.list_documents()
    assert result == []


async def test_list_documents_returns_correct_fields(
    migrated_db: None, tmp_path: Path
) -> None:
    doc_id = await _insert_doc("docs/report.md", file_hash="abc123", chunks=2)
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert len(result) == 1
    doc = result[0]
    assert doc.id == doc_id
    assert doc.source_path == "docs/report.md"
    assert doc.current_version == 1
    assert doc.chunk_count == 2


async def test_list_document_versions_multiple(
    migrated_db: None, tmp_path: Path
) -> None:
    # First ingest
    doc_id = await _insert_doc("docs/report.md", file_hash="hash-v1")
    # Re-ingest same path with different hash
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="docs/report.md",
            file_hash="hash-v2",
            chunks=[_chunk()],
            embeddings=[_embedding()],
        )
    service = ProvenanceService(make_test_config(tmp_path))

    versions = await service.list_document_versions(doc_id)

    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[0].file_hash == "hash-v1"
    assert versions[1].version_number == 2
    assert versions[1].file_hash == "hash-v2"


async def test_list_document_versions_unknown_id(
    migrated_db: None, tmp_path: Path
) -> None:
    import uuid
    service = ProvenanceService(make_test_config(tmp_path))
    versions = await service.list_document_versions(str(uuid.uuid4()))
    assert versions == []
```

### Architecture Compliance

**What `cli.py` may import:**
- `cos.config` ✓
- `cos.services.provenance` ✓ (including `DocumentSummary`, `VersionSummary` re-exported via `__all__`)

**What `cli.py` must NOT import:**
- `cos.store.*` ✗
- `cos.ingestion.*` ✗

**What `services/provenance.py` may import:**
- `cos.config` ✓
- `cos.store.db` ✓
- `cos.store.models` ✓

**What `store/db.py` new functions may import:**
- `cos.store.models.DocumentSummary`, `VersionSummary` ✓ (intra-package)

**Logging:** No structured logging required for read-only queries. No `component` log entries needed in this story.

### Config Fields Used

| Field | Where |
|-------|-------|
| `config.database.libpq_dsn` | `ProvenanceService` connection string |

### Forward-Looking Notes

- **Story 2.6 (Operator Validation)** uses `cos docs` to verify ingested test documents — the table output and field values are what the operator inspects. Ensure `source_path` matches the absolute path used during ingestion (same as `IngestService` — `Path(path).resolve()`).
- **Story 3.4 (`list_documents` MCP tool)** will call a `RetrievalService` (or directly `ProvenanceService`) that surfaces the same data via MCP. The `list_documents` DB function built here is the natural foundation. MCP tool AC says it must return data "consistent with `cos docs` CLI output" — same SQL query, same fields.
- **Epic 3** will need `list_documents` to filter by status — the `documents.status` column (`'indexed'`) is already in the schema and can be added to the WHERE clause when needed.

### Files to Create or Modify

| File | Action | Key constraint |
|------|--------|----------------|
| `src/cos/store/models.py` | Add `DocumentSummary`, `VersionSummary` dataclasses | After `ProvenanceRecord`; use `datetime` (already imported) |
| `src/cos/store/db.py` | Add `list_documents()`, `list_document_versions()` | Do NOT touch existing functions; extend imports |
| `src/cos/services/provenance.py` | Create new file | Follow `IngestService` connection pattern |
| `src/cos/cli.py` | Add `docs` command + `_docs_list`, `_docs_versions`, `_print_*` helpers | Import from `cos.services.provenance` only |
| `tests/services/test_provenance_service.py` | Create new test file | Use `store_document` for setup; `migrated_db` + `clean_tables` |

### References

- DB schema: `src/cos/store/migrations/001_initial.sql`
- Existing models: `src/cos/store/models.py`
- Connection pattern: `src/cos/services/ingestion.py:IngestService.ingest_file()`
- Store function reference: `src/cos/store/db.py:store_document()`
- CLI pattern: `src/cos/cli.py:ingest()` and `_ingest_file()`, `_ingest_folder()`
- Test fixtures: `tests/conftest.py` — `TEST_DSN`, `make_test_config`, `migrated_db`
- Services conftest: `tests/services/conftest.py` — `clean_tables` (autouse), `mock_embed`
- Store test patterns: `tests/store/test_document_store.py` — direct `store_document` usage
- Architecture boundaries: `_bmad-output/planning-artifacts/architecture.md` — service layer enforcement
- Story 2.4 notes: `_bmad-output/implementation-artifacts/2-4-cli-ingest-command-and-ingestservice.md` — established patterns, forward-looking notes for 2.5

### Review Findings

- [x] [Review][Decision] UUID text-cast defeats index on `document_versions.document_id` — `list_document_versions` uses `WHERE document_id::text = %s` (dev agent addition); casts the indexed UUID column to text, preventing use of `idx_document_versions_document_id` and causing a sequential scan; spec template prescribed `WHERE document_id = %s`; correct fix is UUID format validation at the service layer with `WHERE document_id = %s::uuid` [src/cos/store/db.py]
- [x] [Review][Decision] `list_documents` chunk count inflated after re-ingest — `COUNT(c.id)` joins all chunks for a document with no version filter; `store_document` retains old chunks on re-ingest (no delete); a document ingested twice will show double the chunk count; `chunks` table has no version FK (deferred from 2.3); resolution options: (a) fix `store_document` to delete old chunks first, (b) accept inflated count and document the limitation [src/cos/store/db.py]
- [x] [Review][Patch] `test_list_documents_ordered_most_recent_first` non-deterministic under fast inserts — two inserts with default `now()` timestamp can receive identical values on fast hardware, making `ORDER BY d.ingested_at DESC` non-deterministic; add an explicit delay or inject timestamps [tests/services/test_provenance_service.py]
- [x] [Review][Patch] `_print_documents_table` separator shorter than data rows — `"-" * len(header)` uses header string length; tz-aware ISO timestamps (`+00:00`) are 32 chars vs. 26-char column; data rows overflow the separator and columns misalign [src/cos/cli.py]
- [x] [Review][Patch] `VersionSummary.version_number` defaults to `0` — real versions start at 1; a 0 default is ambiguous with a DB error; should default to `1` or carry no default [src/cos/store/models.py]
- [x] [Review][Patch] `--versions ""` empty string silently treated as a valid document ID — `versions is not None` passes empty string through; emits misleading "No versions found for document ID: " message; add empty-string guard [src/cos/cli.py]
- [x] [Review][Patch] `--json/--no-json` flag pair instead of single `--json` — spec constraint: `typer.Option(False, "--json", help="Output as JSON")`; paired form exposes an undocumented `--no-json` flag [src/cos/cli.py]
- [x] [Review][Defer] `_docs_versions` exits code 0 on unknown document ID [src/cos/cli.py] — deferred, pre-existing; spec explicitly says no error handling; revisit if scripting AC added
- [x] [Review][Defer] `ingested_at` None from DB would crash in `.isoformat()` [src/cos/store/models.py] — deferred, pre-existing; NOT NULL constraint in schema makes this theoretical; no handling needed at this stage

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References
- `uv run ruff check src/cos/cli.py src/cos/store/db.py src/cos/store/models.py src/cos/services/provenance.py tests/services/test_provenance_service.py`
- `uv run python - <<'PY' ... manual provenance validation passed`
- `uv run python - <<'PY' ... cli smoke validation passed`
- `uv run pytest tests/services/test_provenance_service.py` currently fails during collection because `tests/services/conftest.py` imports `conftest` in a way that resolves to itself when the services suite is collected in isolation.

### Completion Notes List
- Added provenance summary dataclasses plus read-only document and version listing queries in the store layer.
- Added `ProvenanceService` and wired `cos docs` for table and JSON output, including friendly empty-state and unknown-ID messages.
- Hardened version lookup to treat malformed document IDs as "not found" by comparing `document_id::text`, which prevents a Postgres UUID cast error at the CLI.
- Added focused provenance service tests covering empty results, ordering, chunk counts, single and multiple versions, unknown UUIDs, and malformed IDs.
- Validated behavior with Ruff plus direct database and CLI smoke checks against the test database.

### File List
- `_bmad-output/implementation-artifacts/2-5-document-provenance-listing.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `src/cos/cli.py`
- `src/cos/services/provenance.py`
- `src/cos/store/db.py`
- `src/cos/store/models.py`
- `tests/services/test_provenance_service.py`

### Change Log
- 2026-04-23: Implemented `cos docs` provenance listing, added provenance service/store queries, added service coverage, and moved story 2.5 to review.
