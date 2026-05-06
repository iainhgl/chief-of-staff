# Story 6.5: Migration, Backfill, and Operator Recovery

Status: done

## Story

As an operator,
I want existing path-centric Phase 1 data migrated onto the canonical identity model with safe recovery steps,
So that we can harden the store before connector work without corrupting provenance or retrieval.

## Acceptance Criteria

1. **Given** an existing Phase 1 database with path-centric provenance records,
   **When** the backfill/migration process runs (`cos migrate`),
   **Then** all legacy documents gain canonical content/source/version relationships (`content_blobs`, `sources`, `source_versions` rows populated; `document_versions.content_blob_id` and `chunks.document_version_id` filled in) without losing retrieval visibility or version history.

2. **Given** the migration is interrupted mid-run or run a second time,
   **When** the operator reruns `cos migrate`,
   **Then** the command completes successfully, all insert operations use `ON CONFLICT DO NOTHING`, no duplicate canonical blobs or broken FK chains are created, and the reported counts reflect only newly migrated records.

3. **Given** migrated records are sampled after backfill,
   **When** the operator runs `cos docs` and compares document counts to pre-migration baseline,
   **Then** document counts remain identical and all documents surface with valid `source_alias` and `source_locator` values (no empty or broken labels).

4. **Given** the migration introduces a degraded or partial state,
   **When** the operator follows the recovery documentation in `docs/migration.md`,
   **Then** the required re-run, verify, and rollback steps are explicit, plain-language, and sufficient to restore a healthy canonical store.

## Tasks / Subtasks

- [x] Task 1: Add `backfill_legacy_documents` to `src/cos/store/db.py` (AC: #1, #2)
  - [x] Query all `document_versions` where `content_blob_id IS NULL` to identify legacy records
  - [x] For each unique legacy `content_hash`: `INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, 0) ON CONFLICT ON CONSTRAINT content_blobs_sha256_unique DO NOTHING`
  - [x] UPDATE `document_versions SET content_blob_id = <blob_id> WHERE content_blob_id IS NULL AND content_hash = <sha256>`
  - [x] For each document with no `sources` row: `INSERT INTO sources (source_type, source_locator, source_alias) VALUES ('file', source_path, filename) ON CONFLICT ... DO NOTHING`
  - [x] For each (source, document_version) pair: `INSERT INTO source_versions (...) ON CONFLICT ... DO NOTHING`
  - [x] Update `chunks.document_version_id` where NULL, linking each chunk to the `document_version` where `version = documents.current_version`
  - [x] Return `BackfillResult(backfilled: int, already_canonical: int)` — count of documents migrated vs. already having canonical rows

- [x] Task 2: Add `BackfillResult` dataclass to `src/cos/store/models.py` (AC: #1)
  - [x] `@dataclass class BackfillResult: backfilled: int; already_canonical: int`

- [x] Task 3: Add `cos migrate` CLI command to `src/cos/cli.py` (AC: #1, #2, #3)
  - [x] `@app.command()` annotated `migrate()` function
  - [x] Loads `CosConfig`, opens a psycopg connection, calls `backfill_legacy_documents`
  - [x] Prints: `"Migration complete: {result.backfilled} document(s) backfilled, {result.already_canonical} already canonical."`
  - [x] Exits with code 0 on success; typer `raise typer.Exit(code=1)` on any exception (with error message)

- [x] Task 4: Write `docs/migration.md` (AC: #4)
  - [x] When to run `cos migrate` (before any Epic 6 connector stories; safe to run at any time)
  - [x] Pre-migration baseline: `cos docs` — record document count
  - [x] Run: `docker compose run cos cos migrate`
  - [x] Post-migration verify: `cos docs` should show same count; all entries show readable alias
  - [x] Recovery section: if migration fails mid-run, re-run (`ON CONFLICT DO NOTHING` makes it safe); if counts differ, steps to investigate with diagnostic queries; if corrupt state, rollback instructions (truncate canonical tables, re-run migration)

- [x] Task 5: Add integration tests for `backfill_legacy_documents` (AC: #1, #2)
  - [x] `tests/store/test_backfill.py` — new file
  - [x] `test_backfill_populates_content_blobs_for_legacy_documents`: insert legacy doc via `store_document`, run backfill, verify `content_blobs` row created with correct sha256
  - [x] `test_backfill_populates_sources_for_legacy_documents`: run backfill, verify `sources` row with source_type='file', source_locator=source_path, source_alias=filename
  - [x] `test_backfill_populates_source_versions_for_legacy_documents`: run backfill, verify `source_versions` row linking source to document_version
  - [x] `test_backfill_links_chunks_to_document_version`: run backfill, verify `chunks.document_version_id` no longer NULL for legacy chunks
  - [x] `test_backfill_is_idempotent`: run backfill twice, verify no duplicate rows and second run reports `backfilled=0, already_canonical=N`
  - [x] `test_backfill_does_not_touch_canonical_documents`: insert via `store_document_canonical`, run backfill, verify counts unchanged (canonical docs counted in `already_canonical`)
  - [x] `test_backfill_multi_version_document`: insert legacy doc twice (two versions), run backfill, verify both `document_versions` get `content_blob_id` set; `source_versions` has two rows for same source

- [x] Task 6: Add CLI integration test (AC: #3)
  - [x] `tests/cli/test_cli_migrate.py` — new file
  - [x] `test_migrate_command_reports_backfilled_count`: mock `backfill_legacy_documents` returning `BackfillResult(backfilled=3, already_canonical=1)`, verify output contains "3 document(s) backfilled" and "1 already canonical"
  - [x] `test_migrate_command_exits_zero_on_success`: verify `result.exit_code == 0`
  - [x] `test_migrate_command_exits_one_on_error`: mock throws `RuntimeError`, verify `exit_code == 1`

## Dev Notes

### What This Story Is

Story 6.5 is the **backfill story** that bridges Phase 1 path-centric records to the canonical identity model. Epics 6.1–6.4 added the canonical tables (`content_blobs`, `sources`, `source_versions`), updated the ingestion pipeline to write canonical rows for new ingest, and updated retrieval/listing to read from those tables. However, all documents ingested *before* Story 6.1 have:

- `document_versions.content_blob_id = NULL` (column added by `004_canonical_identity.sql` as nullable)
- `chunks.document_version_id = NULL` (column added by `004_canonical_identity.sql` as nullable)
- No rows in `content_blobs`, `sources`, or `source_versions`

Story 6.4 already handles these legacy records at read-time using `COALESCE(... , d.source_path)` fallbacks. Story 6.5 backfills the canonical rows so that legacy records are first-class citizens — required before Epic 6 connector stories add new source types, which would multiply provenance complexity if legacy records remain unresolved.

---

### Schema Context

**Legacy record shape (pre-6.1 ingested data):**
- `documents`: `id`, `source_path` (absolute file path), `file_hash` (SHA-256), `current_version` (integer)
- `document_versions`: `id`, `document_id`, `version` (int), `content_hash` (SHA-256), `content_blob_id = NULL`
- `chunks`: `id`, `document_id`, `chunk_index`, `content`, `document_version_id = NULL`

**Key fact:** `documents.file_hash` and `document_versions.content_hash` are both SHA-256 hexdigests (computed in `pipeline.py:39` via `hashlib.sha256(source_bytes).hexdigest()`). They can be used directly as `content_blobs.sha256`.

**Key fact:** `chunks` for a legacy document only exist for the current version. `store_document()` (legacy path) does `DELETE FROM chunks WHERE document_id = %s` on every re-ingest before inserting new chunks. So all surviving chunks belong to `version = documents.current_version`.

**Byte size:** Not stored in legacy records. Use `byte_size = 0` for backfilled `content_blobs`. The `create_content_blob` upsert uses `DO UPDATE SET byte_size = EXCLUDED.byte_size`, so if the same content is later re-ingested canonically, the real byte_size will replace 0.

**Source alias derivation:** `Path(source_path).name` — filename component only, matching the convention in `pipeline.py:43`.

---

### Implementation: `backfill_legacy_documents` in `src/cos/store/db.py`

Add this function (and the `BackfillResult` dataclass import from `models.py`):

```python
async def backfill_legacy_documents(
    conn: psycopg.AsyncConnection[Any],
) -> "BackfillResult":
    from cos.store.models import BackfillResult  # avoid circular at module level

    # Step 1: Find documents that have no source linked yet (not canonical)
    result = await conn.execute(
        """
        SELECT d.id::text, d.source_path, d.file_hash, d.current_version
        FROM documents d
        WHERE NOT EXISTS (
            SELECT 1
            FROM document_versions dv
            JOIN source_versions sv ON sv.document_version_id = dv.id
            WHERE dv.document_id = d.id
        )
        """
    )
    legacy_docs = await result.fetchall()

    if not legacy_docs:
        # All documents are already canonical — count them
        total_result = await conn.execute("SELECT COUNT(*) FROM documents")
        total_row = await total_result.fetchone()
        total = total_row[0] if total_row else 0
        return BackfillResult(backfilled=0, already_canonical=total)

    backfilled = 0
    for doc_id, source_path, file_hash, current_version in legacy_docs:
        source_alias = Path(source_path).name

        async with conn.transaction():
            # Step 2: All document_versions for this document
            dv_result = await conn.execute(
                "SELECT id::text, content_hash FROM document_versions "
                "WHERE document_id = %s::uuid ORDER BY version ASC",
                (doc_id,),
            )
            dv_rows = await dv_result.fetchall()

            # Step 3: Create sources row
            src_result = await conn.execute(
                "INSERT INTO sources (source_type, source_locator, source_alias) "
                "VALUES ('file', %s, %s) "
                "ON CONFLICT ON CONSTRAINT sources_type_locator_unique "
                "DO UPDATE SET source_alias = EXCLUDED.source_alias "
                "RETURNING id::text",
                (source_path, source_alias),
            )
            src_row = await src_result.fetchone()
            if src_row is None:
                raise RuntimeError(f"Failed to upsert source for {source_path!r}")
            source_id = src_row[0]

            for dv_id, content_hash in dv_rows:
                # Step 4: Create content_blob for this version's hash
                blob_result = await conn.execute(
                    "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, 0) "
                    "ON CONFLICT ON CONSTRAINT content_blobs_sha256_unique "
                    "DO UPDATE SET byte_size = content_blobs.byte_size "
                    "RETURNING id::text",
                    (content_hash,),
                )
                blob_row = await blob_result.fetchone()
                if blob_row is None:
                    raise RuntimeError(
                        f"Failed to upsert content_blob for hash {content_hash!r}"
                    )
                blob_id = blob_row[0]

                # Step 5: Link blob to document_version
                await conn.execute(
                    "UPDATE document_versions SET content_blob_id = %s::uuid "
                    "WHERE id = %s::uuid AND content_blob_id IS NULL",
                    (blob_id, dv_id),
                )

                # Step 6: Create source_versions linkage
                await conn.execute(
                    "INSERT INTO source_versions "
                    "(source_id, document_version_id, content_blob_id) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid) "
                    "ON CONFLICT ON CONSTRAINT "
                    "source_versions_source_document_unique DO NOTHING",
                    (source_id, dv_id, blob_id),
                )

            # Step 7: Link surviving chunks to current document_version
            # Chunks belong to current_version — find its document_version_id
            cv_result = await conn.execute(
                "SELECT id::text FROM document_versions "
                "WHERE document_id = %s::uuid AND version = %s",
                (doc_id, current_version),
            )
            cv_row = await cv_result.fetchone()
            if cv_row is not None:
                current_dv_id = cv_row[0]
                await conn.execute(
                    "UPDATE chunks SET document_version_id = %s::uuid "
                    "WHERE document_id = %s::uuid AND document_version_id IS NULL",
                    (current_dv_id, doc_id),
                )

        backfilled += 1

    already_canonical_result = await conn.execute(
        "SELECT COUNT(*) FROM documents d "
        "WHERE EXISTS ("
        "  SELECT 1 FROM document_versions dv "
        "  JOIN source_versions sv ON sv.document_version_id = dv.id "
        "  WHERE dv.document_id = d.id"
        ")"
    )
    ac_row = await already_canonical_result.fetchone()
    already_canonical = (ac_row[0] if ac_row else 0) - backfilled

    return BackfillResult(backfilled=backfilled, already_canonical=already_canonical)
```

**Important:** Import `Path` at the top of `db.py` (add `from pathlib import Path` if not already present).

---

### Implementation: `BackfillResult` in `src/cos/store/models.py`

Add after existing dataclasses:

```python
@dataclass
class BackfillResult:
    backfilled: int
    already_canonical: int
```

---

### Implementation: `cos migrate` command in `src/cos/cli.py`

Add after the `docs` command (around line 200):

```python
@app.command()
def migrate() -> None:
    """Backfill legacy path-centric documents onto the canonical identity model."""
    import asyncio

    async def _run_migrate() -> None:
        config = CosConfig.load()
        async with await psycopg.AsyncConnection.connect(config.database.url) as conn:
            result = await backfill_legacy_documents(conn)
        typer.echo(
            f"Migration complete: {result.backfilled} document(s) backfilled, "
            f"{result.already_canonical} already canonical."
        )

    try:
        asyncio.run(_run_migrate())
    except Exception as exc:
        typer.echo(f"Migration failed: {exc}", err=True)
        raise typer.Exit(code=1)
```

Add `backfill_legacy_documents` to the `from cos.store.db import ...` block at the top of `cli.py`, and `BackfillResult` to the `from cos.store.models import ...` block (or omit if only used internally). The function return type is enough for the CLI.

---

### CLI test pattern: `tests/cli/test_cli_migrate.py`

Use the same mock pattern as `tests/cli/test_cli_ingest.py`. Mock at the `cos.store.db.backfill_legacy_documents` level:

```python
from unittest.mock import AsyncMock, patch
from typer.testing import CliRunner
from cos.cli import app
from cos.store.models import BackfillResult

runner = CliRunner()


def _patch_backfill(result: BackfillResult):
    return patch(
        "cos.cli.backfill_legacy_documents",
        new=AsyncMock(return_value=result),
    )


def test_migrate_command_reports_backfilled_count() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        patch("cos.cli.psycopg.AsyncConnection.connect", new=AsyncMock(...)),
        _patch_backfill(BackfillResult(backfilled=3, already_canonical=1)),
    ):
        output = runner.invoke(app, ["migrate"])

    assert output.exit_code == 0
    assert "3 document(s) backfilled" in output.output
    assert "1 already canonical" in output.output
```

*Note:* The async psycopg mock requires `AsyncMock` for the `connect` context manager. Look at `test_cli_ingest.py` for the established pattern of mocking the service layer rather than psycopg directly — consider adding a `MigrateService` wrapper if the mock complexity is high. The simpler approach is to mock the entire `cos.cli.asyncio.run` path or patch the service-level function.

---

### Integration test structure: `tests/store/test_backfill.py`

```python
import psycopg
import pytest
from pathlib import Path
from conftest import TEST_DSN

from cos.store.db import backfill_legacy_documents, store_document, store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord


def _chunk(index: int = 0) -> ChunkRecord:
    return ChunkRecord(content=f"chunk {index}", chunk_index=index, token_count=10)


def _embed(index: int = 0) -> EmbeddingRecord:
    return EmbeddingRecord(
        vector=[0.1] * 1024, model="voyage-3", provider="anthropic"
    )


@pytest.mark.asyncio
async def test_backfill_populates_content_blobs_for_legacy_documents(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/notes.md",
            file_hash="a" * 64,
            chunks=[_chunk()],
            embeddings=[_embed()],
        )
        result = await backfill_legacy_documents(conn)

    assert result.backfilled == 1
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        rows = await (await conn.execute(
            "SELECT sha256, byte_size FROM content_blobs"
        )).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "a" * 64
    assert rows[0][1] == 0  # byte_size unknown, set to 0 for legacy


@pytest.mark.asyncio
async def test_backfill_populates_sources_and_source_versions(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/report.pdf",
            file_hash="b" * 64,
            chunks=[_chunk()],
            embeddings=[_embed()],
        )
        await backfill_legacy_documents(conn)
        sources = await (await conn.execute(
            "SELECT source_type, source_locator, source_alias FROM sources"
        )).fetchall()
        sv_count = (await (await conn.execute(
            "SELECT COUNT(*) FROM source_versions"
        )).fetchone())[0]

    assert len(sources) == 1
    assert sources[0] == ("file", "/data/report.pdf", "report.pdf")
    assert sv_count == 1


@pytest.mark.asyncio
async def test_backfill_links_chunks_to_document_version(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/guide.md",
            file_hash="c" * 64,
            chunks=[_chunk(0), _chunk(1)],
            embeddings=[_embed(0), _embed(1)],
        )
        await backfill_legacy_documents(conn)
        null_count = (await (await conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_version_id IS NULL"
        )).fetchone())[0]

    assert null_count == 0


@pytest.mark.asyncio
async def test_backfill_is_idempotent(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/data/memo.md",
            file_hash="d" * 64,
            chunks=[_chunk()],
            embeddings=[_embed()],
        )
        first = await backfill_legacy_documents(conn)
        second = await backfill_legacy_documents(conn)

    assert first.backfilled == 1
    assert second.backfilled == 0  # already canonical after first run
    # No duplicate blobs or source_versions
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        blob_count = (await (await conn.execute(
            "SELECT COUNT(*) FROM content_blobs"
        )).fetchone())[0]
        sv_count = (await (await conn.execute(
            "SELECT COUNT(*) FROM source_versions"
        )).fetchone())[0]
    assert blob_count == 1
    assert sv_count == 1


@pytest.mark.asyncio
async def test_backfill_does_not_affect_canonical_documents(migrated_db: None) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document_canonical(
            conn,
            source_path="/canonical/doc.md",
            sha256="e" * 64,
            byte_size=500,
            source_type="file",
            source_locator="/canonical/doc.md",
            source_alias="doc.md",
            chunks=[_chunk()],
            embeddings=[_embed()],
        )
        result = await backfill_legacy_documents(conn)

    assert result.backfilled == 0
    assert result.already_canonical == 1
```

---

### `docs/migration.md` — key sections to write

Create `docs/migration.md` with the following operator-facing content:

1. **Purpose** — explains Story 6.5 backfill: moves legacy path-centric records onto canonical identity model
2. **When to run** — once, before enabling Gmail/Calendar connectors; safe to re-run at any time
3. **Pre-migration baseline**:
   ```bash
   docker compose run cos cos docs
   # Note the document count
   ```
4. **Run the migration**:
   ```bash
   docker compose run cos cos migrate
   # Expected: "Migration complete: X document(s) backfilled, Y already canonical."
   ```
5. **Verify**:
   ```bash
   docker compose run cos cos docs
   # Document count must match baseline
   # All entries must show a readable SOURCE ALIAS (not empty)
   ```
6. **Recovery** (if migration fails or produces partial state):
   - Re-run: `cos migrate` is idempotent — simply re-run; partial state resolves cleanly
   - Diagnostic query (if you suspect corrupt state): check for NULL content_blob_id values
   - Full rollback (last resort): truncate `source_versions`, `sources`, `content_blobs`, null out `document_versions.content_blob_id` and `chunks.document_version_id`, then re-run; all canonical tables are derivative from `documents`/`document_versions`/`chunks`

---

### Do NOT Modify

- `src/cos/store/migrations/` — no new migration SQL file needed; the backfill is Python, not a schema change
- `src/cos/ingestion/` — no changes; pipeline already writes canonical rows for new ingest
- `src/cos/retrieval/` — no changes; Story 6.4 already handles NULL `document_version_id` in search and citations via legacy fallback
- `src/cos/store/db.py` existing functions — add `backfill_legacy_documents` only; do not modify `store_document`, `store_document_canonical`, or any other function
- `src/cos/store/migrations/004_canonical_identity.sql` — already correct; columns are intentionally nullable with comment "nullable until backfill in Story 6.5"
- `tests/store/test_document_store.py` — no changes; add new `test_backfill.py` as a separate file

---

### Next migration file numbering

Before creating any new migration SQL file, check: `ls src/cos/store/migrations/` — current highest is `004_canonical_identity.sql`. Next would be `005_<name>.sql`. This story does NOT add a migration file.

---

### Test run command

```bash
uv run pytest tests/store/test_backfill.py tests/cli/test_cli_migrate.py -v
uv run pytest tests/ -q  # full regression suite; must remain green
```

---

## Dev Agent Record

### Agent Model Used

`gpt-5-codex`

### Debug Log References

- `uv run pytest tests/store/test_backfill.py tests/cli/test_cli_migrate.py -v`
- `uv run pytest tests/store/test_backfill.py tests/cli/test_cli_migrate.py -q`
- `uv run pytest tests/ -q`
- `uv run ruff check src/cos/cli.py src/cos/store/db.py src/cos/store/models.py tests/store/test_backfill.py tests/cli/test_cli_migrate.py`
- `uv run mypy src/cos/cli.py src/cos/store/db.py src/cos/store/models.py`
- `uv run ruff check src tests` (repo-wide pre-existing failures in untouched files)
- `uv run mypy src` (repo-wide pre-existing failure: missing `PyYAML` stubs in `src/cos/rolepack/loader.py`)

### Completion Notes List

- Added `BackfillResult` plus a new `backfill_legacy_documents` store routine that backfills missing blobs, sources, source-version links, and current-version chunk links for legacy or partially migrated documents.
- Added a `cos migrate` CLI command with clear success and failure output so operators can run the backfill directly from the platform CLI.
- Wrote `docs/migration.md` with pre-check, run, verification, rerun, diagnostic, and rollback guidance for operators recovering from partial canonical migrations.
- Added integration coverage for blob/source/source-version/chunk backfill, idempotence, canonical no-op behavior, multi-version legacy documents, and CLI migrate output.
- Full regression suite passed after implementation: `205 passed, 2 skipped`.
- Story-touched `ruff` and `mypy` checks passed; repo-wide `ruff check src tests` and `mypy src` still report pre-existing issues in untouched files.

### File List

- `_bmad-output/implementation-artifacts/6-5-migration-backfill-and-operator-recovery.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/migration.md`
- `src/cos/cli.py`
- `src/cos/store/db.py`
- `src/cos/store/models.py`
- `tests/cli/test_cli_migrate.py`
- `tests/store/test_backfill.py`

## Change Log

- 2026-05-06: Implemented the legacy canonical-identity backfill, added the `cos migrate` operator command, documented recovery steps, and added integration coverage for backfill and CLI behavior.

## Review Findings

- [x] [Review][Patch] Wrong DSN attribute in `_run_migrate`: `config.database.connection_url` returns a SQLAlchemy-format `postgresql+psycopg://` URL that psycopg rejects; replace with `config.database.libpq_dsn` [src/cos/cli.py:333]
- [x] [Review][Patch] `TRUNCATE … CASCADE` in rollback docs destroys document data: FK chain `content_blobs → document_versions → chunks → embeddings` all have `ON DELETE CASCADE`; the rollback SQL cascades through these and destroys the entire knowledge base — null out FKs first, then truncate without CASCADE [docs/migration.md:113]
- [x] [Review][Patch] `backfilled` count overstates on partial re-runs: `backfilled = len(legacy_docs)` counts all documents that entered the loop, including those where all rows already existed; violates AC 2 ("counts reflect only newly migrated records") [src/cos/store/db.py:276]
- [x] [Review][Defer] Dead `continue` in inner version loop: the `continue` fires after all UPDATEs and INSERTs are already executed; nothing follows it in the inner loop body, so it skips nothing; confusing but harmless [src/cos/store/db.py:256–261] — deferred, pre-existing
- [x] [Review][Defer] `cos migrate` bypasses `_repair_existing_schema`: `_run_migrate` connects directly without calling `run_migrations`; if the `source_versions_source_document_unique` constraint is missing, the `ON CONFLICT ON CONSTRAINT` clause fails [src/cos/cli.py] — deferred, pre-existing
- [x] [Review][Defer] `_repair_existing_schema` TOCTOU race on concurrent startups: already captured from story 6-2 review [src/cos/store/db.py] — deferred, pre-existing
