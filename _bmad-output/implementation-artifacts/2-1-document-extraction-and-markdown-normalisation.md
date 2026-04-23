# Story 2.1: Document Extraction & Markdown Normalisation

Status: done

## Story

As an operator,
I want the platform to extract text from any common document format and store both the original and a Markdown working copy,
So that all ingested knowledge is preserved immutably and available in a consistent format for downstream processing.

## Acceptance Criteria

1. **Given** a PDF file is passed to the extraction layer,
   **When** `extractor.py` sends it to the Tika server via `tika-client`,
   **Then** the response contains extracted plain text and document metadata (title, author, content-type where available), with no error for well-formed PDFs.

2. **Given** a Word document (.docx), a Markdown file (.md), and a plain text file (.txt) are each passed to the extraction layer,
   **When** extraction runs,
   **Then** each returns extracted text content — Markdown and plain text files bypass Tika and are read directly.

3. **Given** extraction succeeds for a document,
   **When** the extractor writes to the filesystem,
   **Then** the original file is written unchanged to the configured originals directory (bind mount), and a Markdown working copy is written to the Markdown copies directory — both on the host filesystem so they survive container restarts.

4. **Given** a document is written to the originals directory,
   **When** the file is subsequently inspected,
   **Then** its contents are byte-for-byte identical to the source file — no modification, compression, or re-encoding has occurred.

5. **Given** Tika is unavailable (container not healthy),
   **When** extraction is attempted,
   **Then** the extractor raises a structured exception that the service layer catches and logs — it does not silently return empty content or write a blank working copy.

## Tasks / Subtasks

- [x] Task 1: Add `StorageConfig` to `CosConfig` and update `config.yaml.example` (AC: #3)
  - [x] Add `class StorageConfig(BaseModel): originals_dir: Path = Path("/data/originals"); markdown_dir: Path = Path("/data/markdown")` to `config.py` after `TikaConfig`, before `CosConfig`
  - [x] Add `storage: StorageConfig = StorageConfig()` field to `CosConfig`
  - [x] Confirm `from pathlib import Path` is present at the top of `config.py` (it is — used by `CosConfig.load()`; do not add a duplicate)
  - [x] Add `storage:` section to `config.yaml.example` after the `tika:` block (exact wording in Dev Notes)
  - [x] Add `test_storage_config_defaults` to `tests/test_config.py`: load a minimal config without a `storage:` block and assert `config.storage.originals_dir == Path("/data/originals")` and `config.storage.markdown_dir == Path("/data/markdown")`

- [x] Task 2: Implement `extractor.py` — full replacement of stub (AC: #1, #2, #3, #4, #5)
  - [x] Define `ExtractionError(RuntimeError)` at module level (see Dev Notes for definition)
  - [x] Define `ExtractionResult` dataclass with exact fields from Dev Notes
  - [x] Define `SUPPORTED_DIRECT_SUFFIXES: frozenset[str] = frozenset({".md", ".txt"})`
  - [x] Define `SUPPORTED_TIKA_SUFFIXES: frozenset[str] = frozenset({".pdf", ".docx"})`
  - [x] Implement `async def extract(source_path: Path, tika_url: str, originals_dir: Path, markdown_dir: Path) -> ExtractionResult` (orchestrator — see Dev Notes)
  - [x] Inside `extract()`: call `originals_dir.mkdir(parents=True, exist_ok=True)` and `markdown_dir.mkdir(parents=True, exist_ok=True)` before any writes
  - [x] Inside `extract()`: raise `ExtractionError` immediately if `source_path.suffix.lower()` is not in `SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES` — before any filesystem writes
  - [x] Inside `extract()`: write original using `shutil.copy2(source_path, originals_dir / source_path.name)` — never open-and-rewrite
  - [x] Inside `extract()`: for `.md`/`.txt` → read text directly; do NOT call Tika; set `extraction_method="direct"`
  - [x] Inside `extract()`: for `.pdf`/`.docx` → call `_extract_via_tika(source_path, tika_url)` private helper
  - [x] Inside `extract()`: write Markdown copy to `markdown_dir / (source_path.stem + ".md")` only after text is successfully obtained — never write a blank copy
  - [x] Implement private `async def _extract_via_tika(source_path: Path, tika_url: str) -> tuple[str, str | None, str | None, str]` — see tika-client API section in Dev Notes
  - [x] In `_extract_via_tika`: catch all `Exception` and re-raise as `ExtractionError` — never let raw httpx or tika-client exceptions propagate up

- [x] Task 3: Replace `tests/ingestion/test_extractor.py` with real tests (AC: all)
  - [x] Remove `test_extract_not_implemented` entirely
  - [x] Add `test_extract_markdown_direct` — write tmp .md file, call `extract()`, assert `result.text` matches content and `result.extraction_method == "direct"` and `result.content_type == "text/markdown"`
  - [x] Add `test_extract_txt_direct` — same pattern for .txt; `result.content_type == "text/plain"`
  - [x] Add `test_original_written_byte_for_byte` — after `extract()`, assert `filecmp.cmp(src, original_dest, shallow=False)` is `True`
  - [x] Add `test_markdown_copy_written` — assert `(markdown_dir / "test.md").exists()` and contents match the extracted text
  - [x] Add `test_unsupported_format_raises` — pass `.xlsx` file → assert `ExtractionError` raised before any writes (confirm originals_dir is empty)
  - [x] Add `test_tika_unavailable_raises` — call `_extract_via_tika(source_path, "http://localhost:19998")` and assert `ExtractionError` raised (no Tika container needed — dead port triggers httpx ConnectError which is caught and re-raised)
  - [x] Add `test_extract_pdf_via_tika` marked `@pytest.mark.integration` — Tika at `http://localhost:9998`; create minimal PDF bytes in tmp_path; assert `result.text` non-empty and `result.extraction_method == "tika"`
  - [x] All non-integration tests use only `tmp_path` (pytest built-in) — no `db_conn` or `migrated_db` fixtures needed
  - [x] Register `integration` marker in `pyproject.toml` under `[tool.pytest.ini_options]`: `markers = ["integration: tests that require external services (Tika, Postgres)"]`

## Dev Notes

### Current Stub State — Audit Before Touching

| File | Current content | Action |
|------|-----------------|--------|
| `cos/src/cos/ingestion/extractor.py` | Single stub function: `async def extract(source_uri: str) -> str: raise NotImplementedError` | Full replacement — new signature, new types, real implementation |
| `cos/src/cos/config.py` | Has `TikaConfig`; no `StorageConfig` | Add `StorageConfig` class and field to `CosConfig` |
| `cos/config.yaml.example` | Complete; no `storage:` section | Append storage section after `tika:` block |
| `cos/tests/test_config.py` | Has `test_tika_config_defaults` pattern | Add one new test using the same pattern |
| `cos/tests/ingestion/test_extractor.py` | Single `test_extract_not_implemented` | Replace entirely |

**Leave these untouched** — they belong to later stories:
- `extractor.py` old test import: calling code currently passes `"file:///test.pdf"` (string URI) — the old test is being removed so there is no breakage
- `chunker.py`, `embedder.py`, `pipeline.py` — stubs stay as stubs (Stories 2.2, 2.4)
- `services/ingestion.py` — stays as stub (Story 2.4)
- `store/db.py`, `store/models.py`, migration SQL — no changes (Stories 2.2, 2.3)
- `mcp_server/tools.py`, `server.py` — no changes

### `ExtractionError` — Exact Definition

```python
class ExtractionError(RuntimeError):
    pass
```

Raised in these cases:
1. `source_path.suffix.lower()` not in `SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES`
2. Tika is unreachable or raises any exception
3. Tika returns no content (`response.content` is `None` or empty/whitespace-only)

The extractor **only raises** — it never logs. The service layer (IngestService, Story 2.4) is responsible for catching `ExtractionError` and writing a structured JSON log entry with `component: "ingestion"`.

### `ExtractionResult` — Exact Definition

Place in `extractor.py` (ingestion-layer type, not a DB model):

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ExtractionResult:
    text: str                    # extracted plain text
    content_type: str            # e.g. "application/pdf; charset=UTF-8", "text/markdown", "text/plain"
    extraction_method: str       # "tika" | "direct"
    title: str | None = None     # from Tika dc:title metadata; None for direct reads
    author: str | None = None    # from Tika dc:creator metadata; None for direct reads
    original_path: Path = field(default_factory=Path)   # absolute path where original was written
    markdown_path: Path = field(default_factory=Path)   # absolute path where markdown copy was written
```

`original_path` and `markdown_path` are set inside `extract()` after writes succeed. They are consumed by the pipeline and IngestService (Story 2.4) to populate provenance records. `document_versions.extraction_method` is the field this populates (Story 2.3 adds that column).

### tika-client API — Exact Usage

Installed version: `tika-client>=0.11.0`. The async path is `AsyncTikaClient` (async context manager wrapping `httpx.AsyncClient`):

```python
from tika_client import AsyncTikaClient
from tika_client.data_models import DublinCoreKey

async def _extract_via_tika(
    source_path: Path,
    tika_url: str,
) -> tuple[str, str | None, str | None, str]:
    """Returns (text, title, author, content_type)."""
    try:
        async with AsyncTikaClient(tika_url) as client:
            response = await client.tika.as_text.from_file(source_path)
    except Exception as exc:
        raise ExtractionError(f"Tika unavailable at {tika_url}: {exc}") from exc

    text = response.content  # str | None
    if not text or not text.strip():
        raise ExtractionError(f"Tika returned no content for {source_path.name}")

    title: str | None = response.title                           # dc:title — mapped in TikaResponse.__init__
    author: str | None = response.data.get(DublinCoreKey.Creator)  # dc:creator — NOT a direct attribute; use .data
    content_type: str = response.type                            # always present — e.g. "application/pdf; charset=UTF-8"

    return text, title, author, content_type
```

Key points:
- `client.tika.as_text.from_file(source_path)` sends the file as multipart to `/tika/form/text` and returns plain text
- **Do NOT use** `client.tika.as_html` — that returns HTML, not plain text
- **Do NOT use** `TikaClient` (sync version) — codebase is async-first
- `response.title` is already parsed from `"dc:title"` in `TikaResponse.__init__` — use it directly
- `response.data.get(DublinCoreKey.Creator)` — author is NOT a direct `TikaResponse` attribute; must access via `.data` dict using the enum key `"dc:creator"`
- Broad `except Exception` is deliberate here — wraps httpx `ConnectError`, `TimeoutException`, Tika HTTP 5xx, and any other failure into `ExtractionError`

### `extract()` — Complete Implementation Sketch

```python
import shutil
from pathlib import Path

async def extract(
    source_path: Path,
    tika_url: str,
    originals_dir: Path,
    markdown_dir: Path,
) -> ExtractionResult:
    originals_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix.lower()
    if suffix not in (SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES):
        raise ExtractionError(f"Unsupported file format: {source_path.suffix!r}")

    # Write original byte-for-byte — before extraction so errors don't leave partial state
    original_dest = originals_dir / source_path.name
    shutil.copy2(source_path, original_dest)

    # Extract text
    if suffix in SUPPORTED_DIRECT_SUFFIXES:
        text = source_path.read_text(encoding="utf-8")
        title, author = None, None
        content_type = "text/markdown" if suffix == ".md" else "text/plain"
        extraction_method = "direct"
    else:
        text, title, author, content_type = await _extract_via_tika(source_path, tika_url)
        extraction_method = "tika"

    # Write markdown copy only after successful extraction
    markdown_dest = markdown_dir / (source_path.stem + ".md")
    markdown_dest.write_text(text, encoding="utf-8")

    return ExtractionResult(
        text=text,
        content_type=content_type,
        extraction_method=extraction_method,
        title=title,
        author=author,
        original_path=original_dest,
        markdown_path=markdown_dest,
    )
```

Order matters: the original is written first (before Tika is called) so that provenance is preserved even if extraction fails. If `_extract_via_tika` raises `ExtractionError`, the original is already safely stored but no markdown copy is written — correct behaviour.

### File Write Rules

**Originals — use `shutil.copy2`:**
- Preserves byte content and file metadata (timestamps, permissions)
- Does NOT open/read/rewrite — zero risk of encoding issues
- Destination: `originals_dir / source_path.name`
- If the file already exists in originals_dir, `shutil.copy2` overwrites it — conflict detection for re-ingest is Story 2.3's responsibility

**Markdown copies — use `Path.write_text`:**
- Write UTF-8 text; no BOM
- Destination: `markdown_dir / (source_path.stem + ".md")`
- `.txt` files get `.md` extension (valid — plain text is valid Markdown)
- Only written after successful extraction — never written if extraction raised

**`shutil.copy2` is synchronous.** Acceptable here: file copy is a local volume operation (~1 ms for typical docs) and is not the bottleneck. Tika extraction dominates. If async becomes needed, wrap with `asyncio.to_thread(shutil.copy2, ...)`.

### `StorageConfig` — Exact Change to `config.py`

```python
class StorageConfig(BaseModel):
    originals_dir: Path = Path("/data/originals")
    markdown_dir: Path = Path("/data/markdown")
```

Add this class **after `TikaConfig`** and **before `CosConfig`` in `config.py`. Then add the field to `CosConfig`:

```python
class CosConfig(BaseModel):
    llm: LLMConfig
    embedding: EmbeddingConfig
    role_pack: RolePackRef
    channels: list[str]
    connectors: list[str]
    database: DatabaseConfig
    tika: TikaConfig = TikaConfig()
    storage: StorageConfig = StorageConfig()  # ADD THIS
```

Pydantic v2 handles `Path` fields natively — no validator needed. Default values work correctly. Field is optional (backward compatible — existing `config.yaml` without `storage:` continues to work with defaults).

### `config.yaml.example` — Storage Section

Append this block **after the `tika:` block** (before any trailing newline):

```yaml
# ─────────────────────────────────────────────
# Storage
# Directories where the ingestion pipeline writes files inside the container.
# These paths map to the host via the Docker Compose volume mount: ./data:/data
# originals_dir: byte-for-byte copy of every source file; never modified after write
# markdown_dir: extracted plain-text working copy of each document; used for chunking
# Both directories are created automatically on first ingest if they do not exist.
# ─────────────────────────────────────────────
storage:
  originals_dir: /data/originals
  markdown_dir: /data/markdown
```

### Docker Volume Context

From `docker-compose.yml`:
```yaml
volumes:
  - ./data:/data
```

Inside the container, `/data/originals` and `/data/markdown` map to `./data/originals` and `./data/markdown` on the host. Both survive container restarts and image rebuilds. The extractor creates subdirectories with `mkdir(parents=True, exist_ok=True)` — the operator does not need to pre-create them.

### Testing Strategy & Patterns

`pyproject.toml` already has `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed on async test functions.

**Unit tests (no Tika, no DB, no Docker):**

```python
async def test_extract_markdown_direct(tmp_path: Path) -> None:
    src = tmp_path / "test.md"
    src.write_text("# Hello\nWorld", encoding="utf-8")
    result = await extract(src, "http://unused", tmp_path / "orig", tmp_path / "md")
    assert result.text == "# Hello\nWorld"
    assert result.extraction_method == "direct"
    assert result.content_type == "text/markdown"

async def test_original_written_byte_for_byte(tmp_path: Path) -> None:
    import filecmp
    src = tmp_path / "doc.md"
    src.write_bytes(b"# Test\n")
    originals = tmp_path / "orig"
    await extract(src, "http://unused", originals, tmp_path / "md")
    assert filecmp.cmp(src, originals / "doc.md", shallow=False)

async def test_tika_unavailable_raises(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(ExtractionError):
        await extract(src, "http://localhost:19998", tmp_path / "orig", tmp_path / "md")

async def test_unsupported_format_raises(tmp_path: Path) -> None:
    src = tmp_path / "spreadsheet.xlsx"
    src.write_bytes(b"fake xlsx")
    with pytest.raises(ExtractionError):
        await extract(src, "http://unused", tmp_path / "orig", tmp_path / "md")
    assert not (tmp_path / "orig").exists() or not list((tmp_path / "orig").iterdir())
```

**Integration tests (require `docker compose up` — Tika at `localhost:9998`):**

```python
@pytest.mark.integration
async def test_extract_pdf_via_tika(tmp_path: Path) -> None:
    # Use a minimal real PDF — create one or copy a fixture
    # Minimal valid PDF bytes that Tika can parse:
    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n..."
    # Better: use a real fixture file if available
    ...
    assert result.text.strip()
    assert result.extraction_method == "tika"
```

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["integration: tests that require external services running (Tika, Postgres)"]
```

Run unit tests only: `uv run pytest -m "not integration"`
Run integration tests: `uv run pytest -m integration` (requires Docker services up)

### `tests/test_config.py` — New Test Pattern

Follow the existing pattern for `test_tika_config_defaults` in that file. Use a minimal config dict (no `storage:` key) passed through `CosConfig.model_validate()`:

```python
def test_storage_config_defaults(tmp_path: Path) -> None:
    minimal_yaml = """
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key: test-key
embedding:
  provider: anthropic
  model: voyage-3
role_pack:
  path: role_packs/chro.yaml
channels: [local]
connectors: []
database:
  host: localhost
  port: 5432
  user: postgres
  password: postgres
  dbname: cos
"""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(minimal_yaml)
    config = CosConfig.load(cfg_file)
    assert config.storage.originals_dir == Path("/data/originals")
    assert config.storage.markdown_dir == Path("/data/markdown")
```

### Architecture Compliance

- `extractor.py` is an internal ingestion module — do NOT import from `cos.services.*`, `cos.store.*`, `cos.retrieval.*`, `cos.mcp_server.*`, or `cos.cli`
- Do NOT import `CosConfig` in `extractor.py` — receive `tika_url`, `originals_dir`, `markdown_dir` as explicit parameters; the service layer owns config
- No logging in `extractor.py` — the extractor only raises; the service layer logs at the boundary
- No bare `print()` calls
- No sync DB calls, no psycopg imports

### What NOT to Implement

- Chunker (`chunker.py` stays as `raise NotImplementedError`) — Story 2.2
- Embedder (`embedder.py` stays as `raise NotImplementedError`) — Story 2.2
- Pipeline orchestration (`pipeline.py` stays as stub) — Story 2.4
- DB writes (`store/db.py`, `store/models.py` untouched) — Story 2.3
- IngestService (`services/ingestion.py` stays as stub) — Story 2.4
- Re-ingest conflict detection (don't check if file exists in originals_dir; just write) — Story 2.3
- `cos ingest` CLI command — Story 2.4
- `content_tsv` column on chunks — Story 3.1

### Files to Create or Modify

| File | Action | Key constraint |
|------|--------|----------------|
| `cos/src/cos/config.py` | Modify — add `StorageConfig` class and field | After `TikaConfig`, before `CosConfig` |
| `cos/config.yaml.example` | Modify — append `storage:` section | After `tika:` block |
| `cos/pyproject.toml` | Modify — add `markers` list under `[tool.pytest.ini_options]` | Preserve existing keys |
| `cos/src/cos/ingestion/extractor.py` | Full replacement | New types, new signature, real implementation |
| `cos/tests/test_config.py` | Modify — add one test | Follow existing pattern |
| `cos/tests/ingestion/test_extractor.py` | Full replacement | Remove stub test, all new tests use `tmp_path` |

### Cross-Story Notes

- **Story 2.2** consumes `ExtractionResult.text` as input to `chunker.py` — define `ExtractionResult` cleanly now
- **Story 2.3** adds `extraction_method` column to `document_versions` — `ExtractionResult.extraction_method` is ready for it; also adds re-ingest conflict detection before writing originals
- **Story 2.4** wires `IngestService.ingest_file()` to call `extract()` passing `config.storage.originals_dir` and `config.storage.markdown_dir` from `CosConfig`
- **Story 3.1** adds `content_tsv` column to `chunks` table — no action needed here

### References

- `tika_client.AsyncTikaClient`: `cos/.venv/.../tika_client/client.py:136`
- `tika_client.TikaResponse`: `cos/.venv/.../tika_client/data_models.py:91` — `.content`, `.title`, `.type`, `.data`
- `tika_client.DublinCoreKey.Creator`: `data_models.py:52` — `"dc:creator"`
- `AsyncTika.as_text.from_file`: `_resource_tika.py:131`
- `CosConfig` and `TikaConfig`: `cos/src/cos/config.py:50–62`
- `docker-compose.yml` volume mount: `./data:/data` — originals/markdown persist on host
- Epic 2 acceptance criteria: `_bmad-output/planning-artifacts/epics.md:406–434`
- Architecture async discipline: `_bmad-output/planning-artifacts/architecture.md` — Process Patterns section
- Architecture module boundaries: `cos/src/cos/services/ingestion.py` is the boundary; extractor is below it

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Completion Notes List

- Implemented `StorageConfig` defaults and wired `storage` into `CosConfig`, plus documented host-mounted originals/markdown directories in `config.yaml.example`.
- Replaced the extractor stub with async direct-read and Tika-backed extraction, structured `ExtractionError`, and `ExtractionResult` metadata/path reporting.
- Added direct extraction, byte-for-byte original copy, markdown copy, unsupported-format, and Tika-unavailable tests, plus an integration-marked PDF/Tika test that skips when Tika is not running locally.
- Validation run: `uv run pytest tests/test_config.py tests/ingestion/test_extractor.py -m 'not integration'` passed (`14 passed, 1 deselected`).
- Validation run: `uv run ruff check src/cos/config.py src/cos/ingestion/extractor.py tests/test_config.py tests/ingestion/test_extractor.py` passed.
- Validation run: `uv run pytest` reached `44 passed, 1 skipped, 4 errors`; the remaining errors are pre-existing Postgres-dependent migration tests failing because `localhost:5432` was not available in this environment.
- Validation run: `uv run mypy src` still reports pre-existing non-story issues in retrieval modules plus missing `yaml` typing stubs.

### File List

- cos/config.yaml.example
- cos/pyproject.toml
- cos/src/cos/config.py
- cos/src/cos/ingestion/extractor.py
- cos/tests/ingestion/test_extractor.py
- cos/tests/test_config.py
- _bmad-output/implementation-artifacts/2-1-document-extraction-and-markdown-normalisation.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Review Findings

- [x] [Review][Patch] `content_type` type unsafety — `response.type` may be `None` but return type declares `str`; no guard before assignment [src/cos/ingestion/extractor.py]
- [x] [Review][Patch] `UnicodeDecodeError` not wrapped as `ExtractionError` for non-UTF-8 `.md`/`.txt` files — unhandled exception escapes extractor [src/cos/ingestion/extractor.py]
- [x] [Review][Patch] Tika-failure path in `extract()` untested — no test verifying `ExtractionError` propagates out of `extract()` (not just `_extract_via_tika`) and that no blank markdown copy is written [tests/ingestion/test_extractor.py]
- [x] [Review][Patch] `test_unsupported_format_raises` only asserts `originals_dir` is empty — missing assertion that `markdown_dir` is also empty [tests/ingestion/test_extractor.py]
- [x] [Review][Patch] No `.docx` routing test through `extract()` — AC 2 names `.docx` explicitly but no test confirms it routes via Tika rather than direct read [tests/ingestion/test_extractor.py]
- [x] [Review][Defer] Filename/stem collision for same-named files from different source directories — `originals_dir / source_path.name` and `markdown_dir / stem.md` silently overwrite [src/cos/ingestion/extractor.py] — deferred, pre-existing; re-ingest conflict detection is Story 2.3 scope
- [x] [Review][Defer] `author` field may receive `list[str]` from tika-client multi-value metadata — `response.data.get(DublinCoreKey.Creator)` behaviour with multiple creators unverified [src/cos/ingestion/extractor.py] — deferred, pre-existing; requires tika-client investigation
- [x] [Review][Defer] Integration test missing assertions for AC 1 metadata fields — `test_extract_pdf_via_tika` does not assert `result.content_type`, `result.title`, or `result.author` [tests/ingestion/test_extractor.py] — deferred, pre-existing; depends on Tika response for minimal PDF fixture

## Change Log

- 2026-04-23: Story created
- 2026-04-23: Implemented document extraction, markdown normalisation, storage config defaults, and extractor test coverage; advanced story to review.
- 2026-04-23: Code review complete — 5 patches, 3 deferred, 10 dismissed.
