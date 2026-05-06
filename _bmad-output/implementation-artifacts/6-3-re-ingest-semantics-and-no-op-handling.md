# Story 6.3: Re-Ingest Semantics and No-Op Handling

Status: done

## Story

As an operator,
I want ingest to resolve the four source/content outcomes deterministically,
So that unchanged re-ingests are no-ops and changed re-ingests create the right new version records.

## Acceptance Criteria

1. **Given** a known source is re-ingested with unchanged content,
   **When** the decision engine runs,
   **Then** it records the ingest attempt as unchanged and does not create a new `document_version`, `content_blob`, chunk set, or embedding set.

2. **Given** a known source is re-ingested with changed content,
   **When** ingest completes,
   **Then** the existing logical document is preserved, a new `content_blob` and `document_version` are created, and the new version becomes current only after all related writes succeed.

3. **Given** a new source provides bytes already known to the system,
   **When** the decision engine runs,
   **Then** it creates the new source lineage and links it to the existing canonical content/version without duplicate chunking or embedding.

4. **Given** the ingest outcome is returned to the caller,
   **When** the result is logged or displayed,
   **Then** it clearly states which of the four canonical outcomes occurred so operators can reason about connector behaviour without inspecting the database directly.

---

## Tasks / Subtasks

- [x] Task 1: Update CLI ingest output to display outcome-aware messages (AC: #4)
  - [x] Update `_ingest_file()` in `src/cos/cli.py` to display outcome-aware message per `result.outcome`
  - [x] Update `_ingest_folder()` in `src/cos/cli.py` to display outcome-aware message per-file (keep counting/summary logic unchanged)

- [x] Task 2: Add CLI tests in `tests/cli/test_cli_ingest.py` (AC: #4)
  - [x] `test_ingest_file_new_content_prints_chunk_count` — new content outcome
  - [x] `test_ingest_file_unchanged_prints_no_change_message` — unchanged outcome
  - [x] `test_ingest_file_changed_content_prints_update_message` — changed_content outcome
  - [x] `test_ingest_file_new_source_known_content_prints_recorded_message` — new_source_known_content outcome

- [x] Task 3: Add CHANGED_CONTENT database state tests to `tests/ingestion/test_pipeline.py` (AC: #2)
  - [x] `test_run_pipeline_changed_content_preserves_document_version_history` — verify 2 `document_versions` rows, correct `current_version`
  - [x] `test_run_pipeline_changed_content_creates_second_content_blob` — verify 2 `content_blobs` rows
  - [x] `test_run_pipeline_changed_content_links_source_version_to_new_document_version` — verify 2 `source_versions` rows linked via `document_versions`

- [x] Task 4: Add service-layer re-ingest tests to `tests/services/test_ingestion_service.py` (AC: #1, #2, #4)
  - [x] `test_ingest_file_unchanged_returns_unchanged_outcome` — re-ingest same file twice, verify second result
  - [x] `test_ingest_file_changed_returns_changed_content_outcome` — re-ingest with changed bytes, verify outcome and chunk_count

---

## Dev Notes

### What This Story Is

Story 6.3 is the **validation and operator-visibility story** for the four canonical ingest outcomes. Story 6.2 built the identity engine (`identity.py`), canonical DB helpers, and wired the pipeline. The identity logic is **complete and correct** — do not modify it.

Story 6.3 adds two things:

1. **Outcome-aware CLI output** — operators need to know if a re-ingest was a no-op, an update, or a new-source link without inspecting logs or the DB. Currently `_ingest_file` and `_ingest_folder` always display the same "Ingested ... -> N chunks indexed" line regardless of outcome.

2. **CHANGED_CONTENT database state tests** — Story 6.2 tests verify that the outcome enum is correct, but do not verify the full DB state after a changed-content re-ingest (two `document_versions`, two `content_blobs`, correct `source_versions` linkage).

**Do NOT modify:**
- `src/cos/ingestion/identity.py` — complete and correct
- `src/cos/store/db.py` — canonical helpers complete
- `src/cos/ingestion/pipeline.py` — pipeline orchestration correct
- `src/cos/services/ingestion.py` — `IngestResult` complete
- `src/cos/store/migrations/` — no new migrations needed
- `src/cos/retrieval/`, `src/cos/mcp_server/`, `src/cos/rolepack/`, `src/cos/output/`

---

### Database State for CHANGED_CONTENT (AC #2)

After a CHANGED_CONTENT re-ingest (same source locator, different byte sequence):

| Table | Count | Detail |
|---|---|---|
| `documents` | 1 | Same row; `current_version = 2` |
| `document_versions` | 2 | Version 1 row preserved; version 2 row created |
| `content_blobs` | 2 | One per distinct byte sequence |
| `chunks` | Only version 2's chunks | Old version's chunks deleted (Phase 1 simplification; old `document_version` row still preserved) |
| `sources` | 1 | Same file source |
| `source_versions` | 2 | One per `document_version`, both linked to the same `source` |

**Atomicity guarantee:** `store_document_canonical` wraps the entire CHANGED_CONTENT write — including `UPDATE documents`, `DELETE FROM chunks`, `INSERT INTO document_versions`, `INSERT INTO source_versions`, and all chunk/embedding inserts — in a single `async with conn.transaction()`. If any write fails, the whole block rolls back, old chunks are restored, and `current_version` stays at 1. The new version only becomes visible after all writes commit.

---

### Outcome-Aware CLI Display

Current code (line 140 and line 163 of `cli.py`):
```python
typer.echo(f"Ingested {target.name} -> {result.chunk_count} chunks indexed")
```

This prints "Ingested notes.md -> 0 chunks indexed" for both unchanged and new-source-known-content cases, which is confusing for operators.

**Target message per outcome:**

| `result.outcome` | `_ingest_file` message | `_ingest_folder` per-file message |
|---|---|---|
| `"new_content"` | `Ingested {name} -> {count} chunks indexed` | same |
| `"changed_content"` | `Updated {name} -> {count} new chunks indexed (new version)` | same |
| `"unchanged"` | `No change detected in {name} — already up to date` | same |
| `"new_source_known_content"` | `Recorded {name} as new source — content already indexed` | same |

`result.outcome` is a `str` (the `.value` of the `IngestOutcome` enum, e.g. `"unchanged"`). It is NOT the enum instance. Do NOT import `IngestOutcome` into `cli.py`.

The `_ingest_folder` counting/summary logic is **unchanged**: `total_files += 1` and `total_chunks += result.chunk_count` continue to run on every successful call regardless of outcome. Only the per-file echo line changes.

---

### Exact Implementations

#### `src/cos/cli.py` — `_ingest_file` (replace lines 138–140)

```python
async def _ingest_file(target: Path, service: IngestService) -> None:
    result = await service.ingest_file(str(target))
    if result.outcome == "unchanged":
        typer.echo(f"No change detected in {target.name} — already up to date")
    elif result.outcome == "new_source_known_content":
        typer.echo(f"Recorded {target.name} as new source — content already indexed")
    elif result.outcome == "changed_content":
        typer.echo(f"Updated {target.name} -> {result.chunk_count} new chunks indexed (new version)")
    else:
        typer.echo(f"Ingested {target.name} -> {result.chunk_count} chunks indexed")
```

#### `src/cos/cli.py` — `_ingest_folder` (replace only the per-file echo at line 163)

```python
        # Replace:
        typer.echo(f"Ingested {file_path.name} -> {result.chunk_count} chunks indexed")
        # With:
        if result.outcome == "unchanged":
            typer.echo(f"No change detected in {file_path.name} — already up to date")
        elif result.outcome == "new_source_known_content":
            typer.echo(f"Recorded {file_path.name} as new source — content already indexed")
        elif result.outcome == "changed_content":
            typer.echo(f"Updated {file_path.name} -> {result.chunk_count} new chunks indexed (new version)")
        else:
            typer.echo(f"Ingested {file_path.name} -> {result.chunk_count} chunks indexed")
```

Everything else in `_ingest_folder` — the loop structure, `try`/`except`, `total_files += 1`, `total_chunks += result.chunk_count`, all summary echo lines — remains **unchanged**.

---

#### `tests/cli/test_cli_ingest.py` — NEW file

CLI tests use `typer.testing.CliRunner` and mock `IngestService` at the `cos.cli` import path. Follow the pattern from `tests/cli/test_cli_status.py`.

```python
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.services.ingestion import IngestResult

runner = CliRunner()


def _make_result(outcome: str, chunk_count: int = 0, name: str = "doc.md") -> IngestResult:
    return IngestResult(
        document_id="00000000-0000-0000-0000-000000000001",
        chunk_count=chunk_count,
        source_path=f"/tmp/{name}",
        outcome=outcome,
        message=f"Mock message for {outcome}",
    )


def _patch_ingest(result: IngestResult):
    """Returns a context-manager patch for IngestService.ingest_file."""
    mock_service = MagicMock()
    mock_service.ingest_file = AsyncMock(return_value=result)
    return patch("cos.cli.IngestService", return_value=mock_service)


def test_ingest_file_new_content_prints_chunk_count() -> None:
    result = _make_result("new_content", chunk_count=5, name="notes.md")
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
        patch("cos.cli.Path.exists", return_value=True),
        patch("cos.cli.Path.is_file", return_value=True),
        patch("cos.cli.Path.is_dir", return_value=False),
    ):
        output = runner.invoke(app, ["ingest", "/tmp/notes.md"])

    assert output.exit_code == 0
    assert "Ingested notes.md -> 5 chunks indexed" in output.output


def test_ingest_file_unchanged_prints_no_change_message() -> None:
    result = _make_result("unchanged", chunk_count=0, name="notes.md")
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
        patch("cos.cli.Path.exists", return_value=True),
        patch("cos.cli.Path.is_file", return_value=True),
        patch("cos.cli.Path.is_dir", return_value=False),
    ):
        output = runner.invoke(app, ["ingest", "/tmp/notes.md"])

    assert output.exit_code == 0
    assert "No change detected in notes.md" in output.output
    assert "already up to date" in output.output


def test_ingest_file_changed_content_prints_update_message() -> None:
    result = _make_result("changed_content", chunk_count=4, name="notes.md")
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
        patch("cos.cli.Path.exists", return_value=True),
        patch("cos.cli.Path.is_file", return_value=True),
        patch("cos.cli.Path.is_dir", return_value=False),
    ):
        output = runner.invoke(app, ["ingest", "/tmp/notes.md"])

    assert output.exit_code == 0
    assert "Updated notes.md -> 4 new chunks indexed (new version)" in output.output


def test_ingest_file_new_source_known_content_prints_recorded_message() -> None:
    result = _make_result("new_source_known_content", chunk_count=0, name="notes.md")
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
        patch("cos.cli.Path.exists", return_value=True),
        patch("cos.cli.Path.is_file", return_value=True),
        patch("cos.cli.Path.is_dir", return_value=False),
    ):
        output = runner.invoke(app, ["ingest", "/tmp/notes.md"])

    assert output.exit_code == 0
    assert "Recorded notes.md as new source" in output.output
    assert "content already indexed" in output.output
```

**Note on `Path` patching:** The CLI resolves `Path(path).resolve()` and then calls `.exists()`, `.is_file()`, `.is_dir()` on the result. The cleanest approach for unit tests is to patch these on the `cos.cli.Path` class. If this approach is too fragile due to `Path` patching complexity, use `tmp_path` with a real file and a mock service instead, following the integration approach used in `tests/services/` tests.

**Simpler alternative (avoid Path patching entirely):** Create a real temp file using `tmp_path` and pass its path to the CLI. The runner can receive a `tmp_path` fixture if the test function is changed to `def test_...(tmp_path)`. The `IngestService.ingest_file` is still mocked. This avoids all `Path` patching:

```python
def test_ingest_file_unchanged_prints_no_change_message(tmp_path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("x", encoding="utf-8")
    result = _make_result("unchanged", chunk_count=0, name="notes.md")
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(source)])

    assert output.exit_code == 0
    assert "No change detected in notes.md" in output.output
    assert "already up to date" in output.output
```

**Use the `tmp_path` approach for all four CLI tests** — it is more robust. Pass `tmp_path` as a test argument; `CliRunner` tests can receive pytest fixtures normally.

---

#### `tests/ingestion/test_pipeline.py` — add 3 CHANGED_CONTENT tests

All three tests follow the same pattern as the existing re-ingest test. Add after the existing tests at the end of the file.

```python
async def test_run_pipeline_changed_content_preserves_document_version_history(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "history.md"
    source_path.write_text("Version one content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await run_pipeline(source_path, config, conn)

    source_path.write_text("Version two content — different bytes", encoding="utf-8")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        second = await run_pipeline(source_path, config, conn)
        counts_result = await conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM documents), "
            "(SELECT COUNT(*) FROM document_versions WHERE document_id = %s::uuid), "
            "(SELECT current_version FROM documents WHERE id = %s::uuid)",
            (first.document_id, first.document_id),
        )
        row = await counts_result.fetchone()

    assert second.document_id == first.document_id
    assert second.outcome is IngestOutcome.CHANGED_CONTENT
    assert row == (1, 2, 2)  # 1 document, 2 version rows, current_version=2


async def test_run_pipeline_changed_content_creates_second_content_blob(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "blob-change.md"
    source_path.write_text("Initial bytes", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)

    source_path.write_text("Changed bytes — distinct hash", encoding="utf-8")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)
        result = await conn.execute("SELECT COUNT(*) FROM content_blobs")
        row = await result.fetchone()

    assert row == (2,)


async def test_run_pipeline_changed_content_links_source_version_to_new_document_version(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "sv-link.md"
    source_path.write_text("First version content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await run_pipeline(source_path, config, conn)

    source_path.write_text("Second version content — new bytes", encoding="utf-8")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        second = await run_pipeline(source_path, config, conn)
        sv_result = await conn.execute(
            "SELECT COUNT(*) FROM source_versions sv "
            "JOIN document_versions dv ON dv.id = sv.document_version_id "
            "WHERE dv.document_id = %s::uuid",
            (first.document_id,),
        )
        sv_row = await sv_result.fetchone()

    assert second.outcome is IngestOutcome.CHANGED_CONTENT
    assert sv_row == (2,)  # one source_version per document_version
```

**Imports already in `test_pipeline.py`:** `psycopg`, `Path`, `IngestOutcome`, `run_pipeline`, `PipelineResult`, `TEST_DSN`, `make_test_config`, `uuid`, `migrated_db`, `mock_embed`. No new imports needed.

---

#### `tests/services/test_ingestion_service.py` — add 2 re-ingest service tests

Append to the end of the existing test file:

```python
async def test_ingest_file_unchanged_returns_unchanged_outcome(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "stable.md"
    source_path.write_text("Stable document content", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    await service.ingest_file(str(source_path))
    second = await service.ingest_file(str(source_path))

    assert second.outcome == "unchanged"
    assert second.chunk_count == 0
    assert "unchanged" in second.message.lower()


async def test_ingest_file_changed_returns_changed_content_outcome(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "changing.md"
    source_path.write_text("Original content", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    first = await service.ingest_file(str(source_path))

    source_path.write_text("Revised content — new bytes", encoding="utf-8")
    second = await service.ingest_file(str(source_path))

    assert second.document_id == first.document_id
    assert second.outcome == "changed_content"
    assert second.chunk_count >= 1
    assert "changed" in second.message.lower() or "new version" in second.message.lower()
```

**Imports already in `test_ingestion_service.py`:** `uuid`, `Path`, `make_test_config`, `IngestService`, `SUPPORTED_SUFFIXES`, `migrated_db`, `mock_embed`. No new imports needed.

---

### Existing Test Suite

The existing pipeline and service tests must all continue to pass. The three new pipeline tests are additive (same test structure as the existing `test_run_pipeline_reingest_increments_version`). The two new service tests are additive.

The existing `test_run_pipeline_reingest_increments_version` still verifies `current_version = 2` and the `CHANGED_CONTENT` outcome — the new tests extend this coverage to full DB state.

---

### Running Tests

```bash
# Prerequisites
docker compose up -d postgres

# New CLI unit tests (no DB needed)
uv run pytest tests/cli/test_cli_ingest.py -v

# New pipeline DB-state tests
uv run pytest tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_preserves_document_version_history tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_creates_second_content_blob tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_links_source_version_to_new_document_version -v

# New service tests
uv run pytest tests/services/test_ingestion_service.py::test_ingest_file_unchanged_returns_unchanged_outcome tests/services/test_ingestion_service.py::test_ingest_file_changed_returns_changed_content_outcome -v

# Full suite — must pass (currently 176 passed, 2 skipped before this story)
uv run pytest -q
```

---

### Project Structure Notes

| File | Change |
|------|--------|
| `src/cos/cli.py` | Update `_ingest_file` and `_ingest_folder` per-file echo |
| `tests/cli/test_cli_ingest.py` | CREATE new file — 4 CLI outcome display tests |
| `tests/ingestion/test_pipeline.py` | Add 3 CHANGED_CONTENT DB-state tests |
| `tests/services/test_ingestion_service.py` | Add 2 re-ingest service-layer tests |

No new migrations. No changes to ingestion logic, store, retrieval, MCP, role pack, or output paths.

---

### References

- Previous story: `_bmad-output/implementation-artifacts/6-2-hash-first-ingest-and-exact-byte-deduplication.md` — identity engine, all DB helpers, pipeline wiring, and 6.2 test patterns
- Current CLI: `src/cos/cli.py` lines 138–174 — `_ingest_file` and `_ingest_folder`
- Architecture ingest outcomes: `_bmad-output/planning-artifacts/architecture.md#Data Architecture`
- CLI test pattern: `tests/cli/test_cli_status.py` — `CliRunner` + `patch` approach

---

## Dev Agent Record

### Agent Model Used

`claude-sonnet-4-6`

### Debug Log References

- `uv run pytest tests/cli/test_cli_ingest.py -q` (fails first, then passes after CLI messaging update)
- `uv run pytest tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_preserves_document_version_history tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_creates_second_content_blob tests/ingestion/test_pipeline.py::test_run_pipeline_changed_content_links_source_version_to_new_document_version -v`
- `uv run pytest tests/services/test_ingestion_service.py::test_ingest_file_unchanged_returns_unchanged_outcome tests/services/test_ingestion_service.py::test_ingest_file_changed_returns_changed_content_outcome -v`
- `uv run pytest -q`
- `uv run ruff check src/cos/cli.py tests/cli/test_cli_ingest.py tests/ingestion/test_pipeline.py tests/services/test_ingestion_service.py`
- `uv run mypy src` (repo-wide pre-existing failure: missing stubs for `yaml` in `src/cos/rolepack/loader.py`)

### Completion Notes List

- Added outcome-aware CLI messaging for `new_content`, `changed_content`, `unchanged`, and `new_source_known_content` without changing folder summary counting behavior.
- Added a new CLI test module covering the four operator-facing ingest messages using `CliRunner` and a mocked `IngestService`.
- Added CHANGED_CONTENT pipeline assertions for preserved version history, second content blob creation, and source-version linkage.
- Added service-layer re-ingest tests verifying `unchanged` and `changed_content` outcomes and chunk-count behavior.
- Full regression suite passed: `185 passed, 2 skipped`.
- Targeted `ruff` checks passed for story-touched files; repo-wide `mypy src` remains blocked by a pre-existing missing `PyYAML` stub dependency in `src/cos/rolepack/loader.py`.

### File List

- `src/cos/cli.py`
- `tests/cli/test_cli_ingest.py`
- `tests/ingestion/test_pipeline.py`
- `tests/services/test_ingestion_service.py`

### Review Findings

- [x] [Review][Patch] No CLI tests for `_ingest_folder` outcome code path — added `test_ingest_folder_unchanged_prints_no_change_message` and `test_ingest_folder_changed_content_prints_update_message` to `tests/cli/test_cli_ingest.py` [tests/cli/test_cli_ingest.py]

- [x] [Review][Defer] `store_document_canonical` deletes ALL chunks across all historical document versions on `CHANGED_CONTENT`, not just current-version chunks — pre-existing; documented in 6.2 review findings; version history at chunk level is a Phase 2 concern [src/cos/store/db.py]
- [x] [Review][Defer] Partially-failed prior ingest leaves source row but no `source_version`, causing `NEW_SOURCE_KNOWN_CONTENT` misclassification on retry — pre-existing `identity.py` behavior; `link_new_source_to_existing_blob` heals the gap implicitly [src/cos/ingestion/identity.py]
- [x] [Review][Defer] `link_new_source_to_existing_blob` uses oldest-first `document_version` ordering — pre-existing ordering decision in `db.py`; same-microsecond tiebreaker deferred from 6.2 review [src/cos/store/db.py]
- [x] [Review][Defer] Content revert scenario (v1→v2→v1) produces undefined behavior — `NEW_SOURCE_KNOWN_CONTENT` or `UNCHANGED` depending on whether the source-version link was pruned; pre-existing gap not introduced by 6.3 [src/cos/ingestion/identity.py]
- [x] [Review][Defer] `CHANGED_CONTENT` with empty extraction body shows "0 new chunks indexed (new version)" — confusing but not crashing; pre-existing edge case (empty document) [src/cos/cli.py]

### Change Log

- 2026-05-06: Story created
- 2026-05-06: Implemented outcome-aware CLI ingest messaging and added CLI, pipeline, and service re-ingest coverage.
