# Story 6.1: Canonical Blob, Source, and Version Schema Hardening

Status: done

## Story

As an operator,
I want the canonical store schema to separate logical documents, immutable content blobs, and source provenance,
So that connector locators and filenames do not accidentally define document identity.

## Acceptance Criteria

1. **Given** the already-implemented Phase 1 baseline schema is present,
   **When** the next migration set is applied,
   **Then** it upgrades the existing store in place rather than assuming a fresh greenfield database, preserving already-indexed documents while adding canonical identity structures.

2. **Given** the next migration set is applied,
   **When** the schema is inspected,
   **Then** it contains canonical identity tables or equivalent structures for `content_blobs`, `sources`, `source_versions`, and `document_versions`, with foreign keys linking them to logical `documents`.

3. **Given** the canonical schema is in place,
   **When** table constraints are reviewed,
   **Then** `content_blobs` enforce uniqueness on SHA-256 content hash and `sources` store provenance-specific fields such as `source_type`, `source_locator`, and `source_alias` without making those fields the canonical document key.

4. **Given** a stored document version is inspected,
   **When** its lineage is traced,
   **Then** the path from `document_version` to `content_blob` and `source_version` is sufficient to identify both the exact bytes used and the source observation that produced them.

5. **Given** pre-existing Epic 2 tables are migrated forward,
   **When** the migration runs repeatedly in development or CI,
   **Then** it remains idempotent and does not duplicate rows or destroy existing provenance history.

## Tasks / Subtasks

- [x] Task 1: Create `src/cos/store/migrations/004_canonical_identity.sql` (AC: #1–5)
  - [x] Add `content_blobs` table with UUID PK, `sha256 TEXT NOT NULL`, `byte_size BIGINT NOT NULL`, `created_at`, and `UNIQUE(sha256)` constraint
  - [x] Add `sources` table with UUID PK, `source_type TEXT NOT NULL`, `source_locator TEXT NOT NULL`, `source_alias TEXT NOT NULL`, `created_at`, and `UNIQUE(source_type, source_locator)` constraint
  - [x] Add `source_versions` table with UUID PK, non-nullable FKs to `sources(id)`, `document_versions(id)`, and `content_blobs(id)`, and `observed_at TIMESTAMPTZ`
  - [x] Alter `document_versions`: add `content_blob_id UUID REFERENCES content_blobs(id)` — nullable (no existing rows have blobs yet; backfill is Story 6.5)
  - [x] Alter `chunks`: add `document_version_id UUID REFERENCES document_versions(id)` — nullable (fixes deferred gap from Story 2.3; backfill is Story 6.5)
  - [x] Add all required indexes: `idx_content_blobs_sha256`, `idx_sources_type_locator`, `idx_source_versions_source_id`, `idx_source_versions_document_version_id`, `idx_source_versions_content_blob_id`, `idx_chunks_document_version_id`, `idx_document_versions_content_blob_id`
  - [x] Verify all DDL uses `IF NOT EXISTS` / `IF NOT EXISTS` so the migration is idempotent

- [x] Task 2: Update `tests/store/test_migrations.py` (AC: #1–5)
  - [x] Update `test_migration_files_exist()` to assert `004_canonical_identity.sql` exists
  - [x] Update `test_run_migrations_creates_all_tables()` to include `content_blobs`, `sources`, `source_versions` in the expected table set
  - [x] Add `test_content_blobs_sha256_unique_constraint_exists()` — query `pg_constraint` for the UNIQUE constraint on `content_blobs.sha256`
  - [x] Add `test_sources_type_locator_unique_constraint_exists()` — query `pg_constraint` for the UNIQUE constraint on `(sources.source_type, sources.source_locator)`
  - [x] Add `test_document_versions_has_content_blob_id_column()` — `information_schema.columns` query
  - [x] Add `test_chunks_has_document_version_id_column()` — `information_schema.columns` query
  - [x] Add `test_source_versions_fks_reference_correct_tables()` — inspect `pg_constraint` for the three FK constraints
  - [x] Add `test_canonical_identity_migration_is_idempotent()` — call `run_migrations(TEST_DSN)` twice with no error
  - [x] Verify existing tests still pass (no regressions: `test_run_migrations_is_idempotent`, `test_documents_table_has_status_column`, etc.)

## Dev Notes

### What This Story Is

Story 6.1 is **schema-only**. The deliverables are exactly:

| File | Action |
|------|--------|
| `src/cos/store/migrations/004_canonical_identity.sql` | CREATE (new migration) |
| `tests/store/test_migrations.py` | UPDATE (new test assertions) |

**Do NOT modify:** any file in `src/cos/services/`, `src/cos/ingestion/`, `src/cos/mcp_server/`, `src/cos/cli.py`, `src/cos/retrieval/`, `src/cos/store/db.py`, `src/cos/store/models.py`, `role_packs/`, `docs/`, or `docker-compose.yml`.

The ingestion pipeline (`store_document` in `db.py`) continues to use `source_path` and `file_hash` — wiring the new tables into the write path is Story 6.2. The backfill of existing rows into the new structure is Story 6.5.

---

### Migration Runner Constraints

From `CLAUDE.md` and `db.py`:

- File: `src/cos/store/migrations/004_canonical_identity.sql` (highest existing is `003_search_indexes.sql`)
- The runner at `db.py:run_migrations` executes every `.sql` file in **lexicographic order** on every `docker compose up` startup
- **No tracking table** — every migration re-executes on startup. All DDL must be idempotent: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` is valid PostgreSQL (13+) syntax — use it
- `ADD CONSTRAINT ... IF NOT EXISTS` is **not** standard SQL. For UNIQUE constraints defined inline in `CREATE TABLE IF NOT EXISTS`, idempotency is free. For constraints added via `ALTER TABLE`, use a separate `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$;` block, or define them inside the `CREATE TABLE IF NOT EXISTS` body instead

The safest pattern: define all constraints (`UNIQUE`, `REFERENCES`) inside the `CREATE TABLE IF NOT EXISTS` block so they are never applied separately. The `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for existing tables (`document_versions`, `chunks`) must only add columns — FK constraints on nullable columns are idempotent via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ... REFERENCES`.

---

### Target Schema

The full picture after all six tables exist:

```
documents (id, source_path, file_hash, ingested_at, current_version, status)
    ↓ one-to-many
document_versions (id, document_id FK→documents, version, content_hash, created_at,
                   content_blob_id FK→content_blobs NULLABLE)
    ↓ one-to-many
chunks (id, document_id FK→documents, chunk_index, content, token_count, created_at,
        content_tsv, document_version_id FK→document_versions NULLABLE)
    ↓ one-to-many
embeddings (id, chunk_id FK→chunks, vector, model, provider, created_at)

content_blobs (id, sha256 UNIQUE, byte_size, created_at)
    ↑ referenced by document_versions.content_blob_id
    ↑ referenced by source_versions.content_blob_id

sources (id, source_type, source_locator, source_alias, created_at,
         UNIQUE(source_type, source_locator))
    ↓ one-to-many
source_versions (id, source_id FK→sources, document_version_id FK→document_versions,
                 content_blob_id FK→content_blobs, observed_at)
```

**Key constraints:**
- `content_blobs.sha256` — globally unique; the deduplication key
- `sources.(source_type, source_locator)` — unique; one source record per type+locator
- All FK columns on `document_versions` and `chunks` are **nullable** until Story 6.5 backfills them
- `source_versions` FKs are all `NOT NULL` (new records created in Story 6.2+ must be fully linked)

**Why `document_versions.content_blob_id` is nullable now:** existing Epic 1–5 rows have no blob record because blobs were never created. These nulls will be backfilled in Story 6.5. Story 6.2 introduces the write path that creates blobs at ingest time, so all rows created after Story 6.2 will have non-null `content_blob_id`.

**Why `chunks.document_version_id` is nullable now:** same reason — existing chunks reference `document_id` only (Epic 2 deferred gap). Backfill in Story 6.5. Story 6.2 write path will populate this for new ingests.

---

### Exact SQL Specification

```sql
-- 004_canonical_identity.sql

-- Immutable content blobs — deduplicated by SHA-256
CREATE TABLE IF NOT EXISTS content_blobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256 TEXT NOT NULL,
    byte_size BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT content_blobs_sha256_unique UNIQUE (sha256)
);

-- Source provenance — where content came from
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    source_alias TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_type_locator_unique UNIQUE (source_type, source_locator)
);

-- Source-version linkage — one observation produces one document_version
CREATE TABLE IF NOT EXISTS source_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    document_version_id UUID NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    content_blob_id UUID NOT NULL REFERENCES content_blobs(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Link document versions to their content blob (nullable until backfill in Story 6.5)
ALTER TABLE document_versions
ADD COLUMN IF NOT EXISTS content_blob_id UUID REFERENCES content_blobs(id);

-- Link chunks to their document version (nullable until backfill in Story 6.5)
ALTER TABLE chunks
ADD COLUMN IF NOT EXISTS document_version_id UUID REFERENCES document_versions(id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_content_blobs_sha256
    ON content_blobs(sha256);

CREATE INDEX IF NOT EXISTS idx_sources_type_locator
    ON sources(source_type, source_locator);

CREATE INDEX IF NOT EXISTS idx_source_versions_source_id
    ON source_versions(source_id);

CREATE INDEX IF NOT EXISTS idx_source_versions_document_version_id
    ON source_versions(document_version_id);

CREATE INDEX IF NOT EXISTS idx_source_versions_content_blob_id
    ON source_versions(content_blob_id);

CREATE INDEX IF NOT EXISTS idx_chunks_document_version_id
    ON chunks(document_version_id);

CREATE INDEX IF NOT EXISTS idx_document_versions_content_blob_id
    ON document_versions(content_blob_id);
```

The SQL above is the authoritative specification. Copy it verbatim into the migration file. Do not deviate.

---

### Test Patterns

All migration tests live in `tests/store/test_migrations.py`. The file uses the `migrated_db` and `db_conn` fixtures from `tests/conftest.py`. All async tests are auto-detected by `pytest-asyncio`.

**`migrated_db` fixture** runs `run_migrations(TEST_DSN)` before yielding — so every async test that takes `migrated_db` as a parameter gets a freshly migrated schema.

**`TEST_DSN`** = `"postgresql://postgres:postgres@localhost:5432/cos_test"` — requires local Postgres to be running. Start with `docker compose up -d postgres` before running tests.

**Idempotency test pattern** (existing — follow it):
```python
async def test_canonical_identity_migration_is_idempotent(migrated_db, db_conn) -> None:
    await run_migrations(TEST_DSN)  # second run — must not raise
```

**Constraint existence test pattern** — query `pg_constraint`:
```python
async def test_content_blobs_sha256_unique_constraint_exists(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'content_blobs'::regclass AND contype = 'u'"
    )
    names = {row[0] for row in await result.fetchall()}
    assert "content_blobs_sha256_unique" in names
```

**Column existence test pattern** — query `information_schema.columns` (existing pattern):
```python
async def test_document_versions_has_content_blob_id_column(migrated_db, db_conn) -> None:
    result = await db_conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'document_versions' AND column_name = 'content_blob_id'"
    )
    assert await result.fetchone() is not None
```

---

### What Must NOT Change

- `src/cos/store/db.py` — `store_document()` still inserts using `source_path` and `file_hash`; it does not write to the new tables
- `src/cos/store/models.py` — no new dataclasses; new Pydantic/dataclass models for the canonical tables are Story 6.2's job
- `tests/store/test_document_store.py` — must still pass unchanged
- All existing `test_migrations.py` tests — must still pass

**Deferred gap (Story 2.3) being partially addressed here:** `document_versions.content_blob_id` and `chunks.document_version_id` are the nullable FK columns that resolve the "no version-linking on chunks" gap. The columns are nullable now; Story 6.5 backfills them. The UNIQUE constraint on `documents.source_path` (the other Story 2.3 deferred gap) is intentionally NOT added here — in the canonical model, `source_path` is not the document key and adding a UNIQUE constraint would be architecturally wrong.

---

### Running Tests

```bash
# Prerequisites
docker compose up -d postgres

# Run only migration tests (fastest feedback loop for this story)
uv run pytest tests/store/test_migrations.py -v

# Full suite (must also pass)
uv run pytest -q
```

Expected: `pytest tests/store/test_migrations.py` should report all existing tests plus the new ones passing.

## Dev Agent Record

### Agent Model Used

`gpt-5`

### Implementation Plan

- Update migration tests first to codify the new canonical identity schema expectations and confirm they fail before the migration exists.
- Add `004_canonical_identity.sql` exactly per the story specification, using only idempotent PostgreSQL DDL.
- Run targeted migration tests, then the full regression suite, and record the outcomes before marking the story ready for review.

### Debug Log References

- Created `story/6-1-canonical-blob-source-and-version-schema-hardening` from the existing worktree without modifying unrelated user changes.
- Red phase: `docker compose up -d postgres`, then `uv run pytest tests/store/test_migrations.py -v` confirmed failures for the missing migration file, missing canonical tables, and missing nullable FK columns.
- Green phase: added `src/cos/store/migrations/004_canonical_identity.sql` exactly per story specification and reran `uv run pytest tests/store/test_migrations.py -v` to green.
- Regression validation: `uv run pytest -q` passed with `169 passed, 2 skipped`.
- Quality checks: `uv run ruff check tests/store/test_migrations.py` passed; `uv run mypy src/cos/store` passed; repo-wide `uv run ruff check` and `uv run mypy src` surfaced pre-existing issues outside this story (`.claude/...`, `tests/ingestion/...`, `src/cos/rolepack/loader.py` missing `types-PyYAML` stubs).

### Completion Notes List

- Added idempotent migration `004_canonical_identity.sql` to introduce canonical `content_blobs`, `sources`, and `source_versions` tables plus nullable lineage columns on `document_versions` and `chunks`.
- Extended migration coverage to assert the new file exists, canonical tables are created, uniqueness constraints are present, the new nullable FK columns exist, source-version foreign keys point at the correct tables, and rerunning migrations remains idempotent.
- Verified story acceptance criteria through targeted migration tests and full regression tests without changing ingestion, retrieval, MCP, role pack, or CLI code paths.

### File List

- `src/cos/store/migrations/004_canonical_identity.sql`
- `tests/store/test_migrations.py`
- `_bmad-output/implementation-artifacts/6-1-canonical-blob-source-and-version-schema-hardening.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Review Findings

- [x] [Review][Decision] source_versions lacks uniqueness constraint — resolved: added `CONSTRAINT source_versions_source_document_unique UNIQUE (source_id, document_version_id)`; design is deduplicated (one row per source+version pair), not an audit log. New test `test_source_versions_source_document_unique_constraint_exists` added. [`src/cos/store/migrations/004_canonical_identity.sql`]
- [x] [Review][Decision] Nullable FK columns default to ON DELETE RESTRICT, inconsistent with rest of schema — resolved: added `ON DELETE CASCADE` to both `document_versions.content_blob_id` and `chunks.document_version_id`. [`src/cos/store/migrations/004_canonical_identity.sql:33,37`]
- [x] [Review][Defer] Redundant explicit indexes on UNIQUE-constrained columns [`src/cos/store/migrations/004_canonical_identity.sql`] — deferred; PostgreSQL auto-creates an index per UNIQUE constraint; `idx_content_blobs_sha256` and `idx_sources_type_locator` are therefore duplicate indexes; spec mandated both so removing them requires a spec update
- [x] [Review][Defer] FK constraint names on source_versions use implicit PostgreSQL naming [`src/cos/store/migrations/004_canonical_identity.sql`] — deferred; names like `source_versions_source_id_fkey` are stable PostgreSQL convention but explicit CONSTRAINT clauses (matching the UNIQUE constraint pattern) would be more robust
- [x] [Review][Defer] source_alias NOT NULL column has no existence test [`tests/store/test_migrations.py`] — deferred; no `test_sources_has_source_alias_column` equivalent; column is implicitly covered by constraint tests
- [x] [Review][Defer] No test for ON DELETE behavior of nullable FK columns [`tests/store/test_migrations.py`] — deferred; column existence tests do not verify ON DELETE semantics; regression risk if behavior changes in a future migration

### Change Log

- 2026-05-05: Implemented Story 6.1 by adding canonical identity schema hardening migration, expanding migration tests for canonical tables and constraints, and validating with targeted plus full regression test runs.
