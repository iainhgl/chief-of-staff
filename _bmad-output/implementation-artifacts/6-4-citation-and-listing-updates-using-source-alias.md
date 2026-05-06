# Story 6.4: Citation and Listing Updates Using Source Alias

Status: done

## Story

As a user,
I want document listings and citations to show stable, readable source aliases while preserving underlying provenance locators,
So that results stay understandable without losing traceability.

## Acceptance Criteria

1. **Given** the implemented pre-Epic 6 baseline exposed path-centric labels such as `source_path`,
   **When** Story 6.4 is complete,
   **Then** this story becomes the authoritative contract-switch point from legacy path-centric provenance to canonical provenance semantics.

2. **Given** a document originated from any source type,
   **When** `list_documents` or `cos docs` displays it after the Epic 6 migration,
   **Then** the primary user-facing label uses `source_alias`, while the underlying canonical provenance retains the full `source_locator`.

3. **Given** retrieval returns cited results,
   **When** citation formatting runs after the Epic 6 migration,
   **Then** each result includes the canonical `document_version_id` plus a readable `source_alias`, rather than relying on raw path-centric identifiers alone.

4. **Given** MCP or CLI consumers still need to trace a result back to the original observation,
   **When** a machine-readable response is inspected,
   **Then** the underlying provenance includes `source_locator` for traceability, but `source_alias` remains the primary display label.

5. **Given** multiple source records point at the same canonical content,
   **When** a listing or citation is produced,
   **Then** the platform shows a stable, deterministic alias selection strategy documented in code and operator docs.

6. **Given** a legacy path-centric record has been migrated,
   **When** it is surfaced through the updated listing/citation path,
   **Then** it still appears with a readable alias and complete provenance rather than a broken or empty label.

---

## Tasks / Subtasks

- [x] Task 1: Update `CitedChunk` and `format_citations` in `src/cos/retrieval/citations.py` (AC: #1, #3, #4)
  - [x] Replace `source_path: str` with `source_alias: str`, `source_locator: str`, `document_version_id: str`
  - [x] Update `format_citations` to use `chunk.source_alias` instead of `chunk.source_path`

- [x] Task 2: Update `hybrid_search` in `src/cos/retrieval/search.py` (AC: #3, #4, #5, #6)
  - [x] Add `c.document_version_id::text AS document_version_id` to both keyword and semantic SQL SELECT clauses
  - [x] Replace the `documents.source_path` bulk lookup with `source_versions` + `sources` JOIN lookup keyed on `document_version_id` (deterministic: `ORDER BY s.created_at ASC`)
  - [x] Implement legacy fallback: when chunk's `document_version_id` is NULL or not found in `source_versions`, use `documents.source_path` for both `source_alias` and `source_locator`
  - [x] Update `CitedChunk` construction to populate `source_alias`, `source_locator`, `document_version_id`
  - [x] Rename `source_path` parameter in `_coerce_priority_weight` to `source_alias`

- [x] Task 3: Update `DocumentSummary` in `src/cos/store/models.py` (AC: #2, #4, #6)
  - [x] Replace `source_path: str = ""` with `source_alias: str = ""` and `source_locator: str = ""`

- [x] Task 4: Update `list_documents` query in `src/cos/store/db.py` (AC: #2, #5, #6)
  - [x] Rewrite SQL to add correlated subqueries that retrieve `source_alias` and `source_locator` from `sources` via `source_versions` and `document_versions`
  - [x] Use `COALESCE(..., d.source_path)` as the legacy fallback for records with no `sources` row
  - [x] Deterministic strategy: `ORDER BY s.created_at ASC LIMIT 1` in each correlated subquery
  - [x] Update `DocumentSummary` construction to use `source_alias` and `source_locator`

- [x] Task 5: Update MCP tools in `src/cos/mcp_server/tools.py` (AC: #3, #4)
  - [x] `list_documents` tool: replace `"source_path": doc.source_path` with `"source_alias": doc.source_alias` and add `"source_locator": doc.source_locator`
  - [x] `retrieve` tool: replace `"source_path": citation.source_path` with `"source_alias": citation.source_alias`, add `"source_locator": citation.source_locator` and `"document_version_id": citation.document_version_id`

- [x] Task 6: Update CLI `cos docs` command in `src/cos/cli.py` (AC: #2, #4)
  - [x] `_docs_list` JSON output: replace `"source_path"` with `"source_alias"` + `"source_locator"`
  - [x] `_print_documents_table`: update column header `SOURCE PATH` → `SOURCE ALIAS`, use `document.source_alias[-40:]`

- [x] Task 7: Update existing tests broken by field renames (AC: all)
  - [x] `tests/retrieval/test_citations.py`: update `CitedChunk` construction (`source_path` → `source_alias`, add `source_locator`, `document_version_id`), update assertion name and content
  - [x] `tests/retrieval/test_search.py`: update `source_path` assertions → `source_alias` assertions
  - [x] `tests/services/test_provenance_service.py`: update `document.source_path` assertion → `document.source_alias` (legacy fallback value)
  - [x] `tests/mcp_server/test_tools.py`: update `_make_chunk()` and `DocumentSummary` construction, update `"source_path"` key assertions to `"source_alias"` and `"source_locator"`

- [x] Task 8: Add new tests (AC: #2, #3, #4, #5, #6)
  - [x] `tests/services/test_provenance_service.py`: `test_list_documents_canonical_record_uses_source_alias` — insert via `store_document_canonical`, verify `source_alias` and `source_locator` fields
  - [x] `tests/services/test_provenance_service.py`: `test_list_documents_legacy_record_falls_back_to_source_path` — insert via `store_document`, verify `source_alias == source_path` and `source_locator == source_path`
  - [x] `tests/cli/test_cli_docs.py` (new file): CLI docs table uses `SOURCE ALIAS` header; JSON output includes `source_alias` + `source_locator` keys
  - [x] `tests/mcp_server/test_tools.py`: `test_retrieve_citations_include_source_alias_and_locator` — verify `source_alias`, `source_locator`, `document_version_id` keys present
  - [x] `tests/mcp_server/test_tools.py`: `test_list_documents_response_includes_source_alias_and_locator` — verify `source_alias` + `source_locator` present, `source_path` absent

### Review Findings

- [x] [Review][Patch] DISTINCT ON non-determinism: add `s.id ASC` tiebreaker to both alias-selection queries [`src/cos/store/db.py`, `src/cos/retrieval/search.py`]
- [x] [Review][Defer] `document_version_id=""` sentinel instead of `Optional[str]` — deferred, consistent with codebase `str=""` pattern throughout models [`src/cos/retrieval/citations.py`]
- [x] [Review][Defer] Fallback documents query fetches all merged doc_ids including those with canonical sources — deferred, performance non-issue at top-k=10 [`src/cos/retrieval/search.py`]
- [x] [Review][Defer] Role pack dict-format path-prefix priorities silently broken when matched against short alias — deferred, dict-format not used by any current role pack; string-list keyword format works correctly [`src/cos/retrieval/search.py`]
- [x] [Review][Defer] Two identical correlated subqueries for source_alias and source_locator run twice per document row — deferred, lateral join optimisation for future housekeeping [`src/cos/store/db.py`]

---

## Dev Notes

### What This Story Is

Story 6.4 is the **contract-switch story** for canonical provenance. Epics 6.1–6.3 built and tested the canonical identity model (`content_blobs`, `sources`, `source_versions`) and all four ingest outcomes. The DB schema and identity engine are complete and correct — do not modify them.

Story 6.4 propagates the canonical identity model upward through three consumer layers:
1. **Retrieval / citations** — `CitedChunk` carries `source_alias`, `source_locator`, `document_version_id`
2. **Listing** — `list_documents` query joins through to `sources`, `DocumentSummary` exposes `source_alias` + `source_locator`
3. **Egress** — MCP tools and CLI `cos docs` expose the new fields; `source_path` no longer appears in any user-facing output

**Legacy records** (ingested before Epic 6.1) have entries in `documents` with a `source_path` column but no corresponding `sources` row. Both the listing and retrieval paths must COALESCE to `documents.source_path` for these records.

**Deterministic alias strategy** (when multiple `sources` point at the same canonical content): ORDER BY `sources.created_at ASC LIMIT 1` — the first source ever to provide this content becomes the display alias. This is consistent across listing and citation and must be documented in a comment in the SQL.

---

### Field Mapping: Before → After

| Layer | Old field | New fields |
|-------|-----------|------------|
| `CitedChunk` | `source_path: str` | `source_alias: str`, `source_locator: str`, `document_version_id: str` |
| `DocumentSummary` | `source_path: str` | `source_alias: str`, `source_locator: str` |
| MCP `retrieve` citations | `"source_path"` | `"source_alias"`, `"source_locator"`, `"document_version_id"` |
| MCP `list_documents` docs | `"source_path"` | `"source_alias"`, `"source_locator"` |
| CLI `cos docs` JSON | `"source_path"` | `"source_alias"`, `"source_locator"` |
| CLI `cos docs` table header | `SOURCE PATH` | `SOURCE ALIAS` |

---

### Task 1: `src/cos/retrieval/citations.py` — exact replacement

Replace the current `CitedChunk` dataclass entirely:

```python
@dataclass
class CitedChunk:
    content: str
    source_document_id: str  # UUID-format string
    source_alias: str        # human-readable display label (filename or alias)
    source_locator: str      # programmatic identifier for traceability
    document_version_id: str # UUID of the document_version this chunk belongs to; "" for legacy
    chunk_index: int
    score: float

    def __post_init__(self) -> None:
        uuid.UUID(self.source_document_id)
```

Update `format_citations`:

```python
def format_citations(results: CitedResults) -> str:
    return "\n".join(
        f"[{index}] {chunk.source_alias} "
        f"(chunk {chunk.chunk_index}, score {chunk.score:.3f})"
        for index, chunk in enumerate(results, start=1)
    )
```

---

### Task 2: `src/cos/retrieval/search.py` — hybrid_search rewrite

**Step 1**: Add `c.document_version_id::text AS document_version_id` to both keyword and semantic SQL. The keyword query becomes:

```sql
SELECT
    c.id::text AS chunk_id,
    c.document_id::text AS document_id,
    c.chunk_index,
    c.content,
    c.document_version_id::text AS document_version_id,
    ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', %s)) AS score
FROM chunks c
WHERE c.content_tsv @@ websearch_to_tsquery('english', %s)
ORDER BY score DESC
LIMIT %s
```

The semantic query becomes:

```sql
SELECT
    c.id::text AS chunk_id,
    c.document_id::text AS document_id,
    c.chunk_index,
    c.content,
    c.document_version_id::text AS document_version_id,
    1 - (e.vector <=> %s) AS score
FROM embeddings e
JOIN chunks c ON c.id = e.chunk_id
ORDER BY score DESC
LIMIT %s
```

Both `keyword_hits` and `semantic_hits` dicts gain a `"document_version_id"` key (may be `None` for legacy chunks).

**Step 2**: After the RRF merge, replace the existing `source_path` lookup with a two-phase lookup:

```python
# Phase 1: look up source info by document_version_id for canonical chunks
document_version_ids = [
    entry["hit"]["document_version_id"]
    for entry in merged_scores.values()
    if entry["hit"].get("document_version_id") is not None
]
source_info_by_version: dict[str, dict[str, str]] = {}
if document_version_ids:
    sv_result = await conn.execute(
        """
        SELECT DISTINCT ON (sv.document_version_id)
            sv.document_version_id::text,
            s.source_alias,
            s.source_locator
        FROM source_versions sv
        JOIN sources s ON s.id = sv.source_id
        WHERE sv.document_version_id = ANY(%s::uuid[])
        ORDER BY sv.document_version_id, s.created_at ASC
        """,
        (document_version_ids,),
    )
    sv_rows = await sv_result.fetchall()
    source_info_by_version = {
        row[0]: {"source_alias": row[1], "source_locator": row[2]}
        for row in sv_rows
    }

# Phase 2: fallback lookup by document_id for legacy chunks (NULL document_version_id
# or no matching source_versions row)
document_ids = list(
    {entry["hit"]["document_id"] for entry in merged_scores.values()}
)
fallback_result = await conn.execute(
    "SELECT id::text, source_path FROM documents WHERE id = ANY(%s::uuid[])",
    (document_ids,),
)
fallback_rows = await fallback_result.fetchall()
fallback_paths = {row[0]: row[1] for row in fallback_rows}
```

**Step 3**: Update the `CitedChunk` construction loop:

```python
cited_results: CitedResults = []
for entry in merged_scores.values():
    hit = entry["hit"]
    doc_version_id = hit.get("document_version_id")

    if doc_version_id and doc_version_id in source_info_by_version:
        info = source_info_by_version[doc_version_id]
        source_alias = info["source_alias"]
        source_locator = info["source_locator"]
    else:
        # Legacy fallback: use source_path from documents for both alias and locator
        legacy_path = fallback_paths.get(hit["document_id"])
        if legacy_path is None:
            continue
        source_alias = legacy_path
        source_locator = legacy_path

    final_score = float(entry["score"])
    if retrieval_priorities is not None:
        final_score *= _coerce_priority_weight(retrieval_priorities, source_alias)

    cited_results.append(
        CitedChunk(
            content=hit["content"],
            source_document_id=hit["document_id"],
            source_alias=source_alias,
            source_locator=source_locator,
            document_version_id=doc_version_id or "",
            chunk_index=hit["chunk_index"],
            score=final_score,
        )
    )
```

**Step 4**: In `_coerce_priority_weight`, rename the `source_path` parameter to `source_alias`. No other change — the function body already works with the alias string (path prefix matching and keyword matching work identically on the alias).

---

### Task 3: `src/cos/store/models.py` — DocumentSummary

```python
@dataclass
class DocumentSummary:
    id: str = ""
    source_alias: str = ""    # replaces source_path
    source_locator: str = ""  # full locator for traceability
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_version: int = 1
    chunk_count: int = 0
```

---

### Task 4: `src/cos/store/db.py` — list_documents query

Replace the entire `list_documents` function body with:

```python
async def list_documents(
    conn: psycopg.AsyncConnection[Any],
) -> list[DocumentSummary]:
    result = await conn.execute(
        """
        SELECT
            d.id::text,
            -- Deterministic alias: first source by created_at ASC; fallback to source_path for legacy records
            COALESCE(
                (SELECT s.source_alias
                 FROM sources s
                 JOIN source_versions sv ON sv.source_id = s.id
                 JOIN document_versions dv ON dv.id = sv.document_version_id
                 WHERE dv.document_id = d.id
                 ORDER BY s.created_at ASC
                 LIMIT 1),
                d.source_path
            ) AS source_alias,
            COALESCE(
                (SELECT s.source_locator
                 FROM sources s
                 JOIN source_versions sv ON sv.source_id = s.id
                 JOIN document_versions dv ON dv.id = sv.document_version_id
                 WHERE dv.document_id = d.id
                 ORDER BY s.created_at ASC
                 LIMIT 1),
                d.source_path
            ) AS source_locator,
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
            source_alias=row[1],
            source_locator=row[2],
            ingested_at=row[3],
            current_version=row[4],
            chunk_count=row[5],
        )
        for row in rows
    ]
```

The `GROUP BY` clause includes `d.source_path` because the correlated subqueries reference it in the COALESCE, and Postgres requires grouped columns to appear in GROUP BY. The `d.source_path` column is not exposed in the result.

---

### Task 5: `src/cos/mcp_server/tools.py` — MCP tool response fields

In `retrieve`, update `citations_data` construction:

```python
citations_data = [
    {
        "source_alias": citation.source_alias,
        "source_locator": citation.source_locator,
        "document_version_id": citation.document_version_id,
        "chunk_index": citation.chunk_index,
        "score": citation.score,
    }
    for citation in response.citations
]
```

In `list_documents`, update `docs_data` construction:

```python
docs_data = [
    {
        "id": doc.id,
        "source_alias": doc.source_alias,
        "source_locator": doc.source_locator,
        "ingested_at": doc.ingested_at.isoformat(),
        "current_version": doc.current_version,
        "chunk_count": doc.chunk_count,
    }
    for doc in docs
]
```

---

### Task 6: `src/cos/cli.py` — CLI docs output

In `_docs_list`, update JSON serialisation:

```python
typer.echo(
    json.dumps(
        [
            {
                "id": document.id,
                "source_alias": document.source_alias,
                "source_locator": document.source_locator,
                "ingested_at": document.ingested_at.isoformat(),
                "current_version": document.current_version,
                "chunk_count": document.chunk_count,
            }
            for document in documents
        ],
        indent=2,
    )
)
```

In `_print_documents_table`, update header and row rendering:

```python
def _print_documents_table(documents: list[DocumentSummary]) -> None:
    header = (
        f"{'ID':<36}  {'SOURCE ALIAS':<40}  {'INGESTED AT':<26}  {'VER':>3}  "
        f"{'CHUNKS':>6}"
    )
    typer.echo(header)
    typer.echo("-" * len(header))
    for document in documents:
        typer.echo(
            f"{document.id:<36}  "
            f"{document.source_alias[-40:]:<40}  "
            f"{document.ingested_at.isoformat(timespec='seconds'):<26}  "
            f"{document.current_version:>3}  "
            f"{document.chunk_count:>6}"
        )
```

---

### Task 7: Existing tests to update

#### `tests/retrieval/test_citations.py`

Replace `CitedChunk` construction throughout to use the new fields. All three tests reference `source_path` on `CitedChunk` — update them:

```python
def _make_chunk(alias: str = "/tmp/policies/leave.md") -> CitedChunk:
    return CitedChunk(
        content="Policy summary",
        source_document_id="4b7726d9-56f0-40f7-8f63-c3203bd2f0d0",
        source_alias=alias,
        source_locator=alias,
        document_version_id="",
        chunk_index=2,
        score=0.98765,
    )


def test_format_citations_empty_input_returns_empty_string() -> None:
    assert format_citations([]) == ""


def test_format_citations_single_result_contains_source_alias() -> None:
    result = _make_chunk("/tmp/policies/leave.md")
    formatted = format_citations([result])
    assert "/tmp/policies/leave.md" in formatted


def test_cited_chunk_has_all_required_fields() -> None:
    result = CitedChunk(
        content="Budget update",
        source_document_id="e3538c27-95cb-4d04-8a01-d78c31ad0fe2",
        source_alias="budget.md",
        source_locator="/tmp/finance/budget.md",
        document_version_id="",
        chunk_index=1,
        score=0.5,
    )
    assert result.content == "Budget update"
    assert isinstance(result.source_document_id, str)
    assert isinstance(result.source_alias, str)
    assert isinstance(result.source_locator, str)
    assert isinstance(result.document_version_id, str)
    assert isinstance(result.chunk_index, int)
    assert isinstance(result.score, float)
```

#### `tests/retrieval/test_search.py`

Update `source_path` assertions to `source_alias`. These tests use `store_document` (legacy helper), so the fallback path applies — `source_alias` will equal the `source_path` string passed in:

- Line 78: `assert results[0].source_path == "/test/hr-framework.md"` → `assert results[0].source_alias == "/test/hr-framework.md"`
- Line 103: `assert results[0].source_path == "/test/leadership-notes.md"` → `assert results[0].source_alias == "/test/leadership-notes.md"`

Rename `test_hybrid_search_result_has_correct_source_path` → `test_hybrid_search_result_has_correct_source_alias`.

Also add a `source_locator` assertion in `test_hybrid_search_keyword_match_returns_result`:
```python
assert results[0].source_alias == "/test/hr-framework.md"
assert results[0].source_locator == "/test/hr-framework.md"
assert isinstance(results[0].document_version_id, str)
```

#### `tests/services/test_provenance_service.py`

The existing `_insert_doc` helper uses `store_document` (legacy, no `sources` row). The legacy fallback makes `source_alias == source_path` and `source_locator == source_path`.

Update `test_list_documents_returns_correct_fields`:
```python
assert document.source_alias == "docs/report.md"
assert document.source_locator == "docs/report.md"
```
Remove the `document.source_path` assertion.

#### `tests/mcp_server/test_tools.py`

Update `_make_chunk()`:
```python
def _make_chunk() -> CitedChunk:
    return CitedChunk(
        content="test content",
        source_document_id="12345678-1234-1234-1234-123456789012",
        source_alias="doc.md",
        source_locator="/test/doc.md",
        document_version_id="",
        chunk_index=0,
        score=0.9,
    )
```

Update all `DocumentSummary` constructions that use `source_path=`:
```python
DocumentSummary(
    id="abc123",
    source_alias="doc.md",
    source_locator="/test/doc.md",
    ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
    current_version=1,
    chunk_count=5,
)
```

In `test_list_documents_document_fields_present`, update the `assert "source_path" in doc` line:
```python
assert "source_alias" in doc
assert "source_locator" in doc
assert "source_path" not in doc
```

---

### Task 8: New tests to add

#### `tests/services/test_provenance_service.py` — new tests (append after existing)

These require importing `store_document_canonical` and helpers from `cos.store.db`:

```python
from cos.store.db import store_document, store_document_canonical
from cos.store.models import ChunkRecord, EmbeddingRecord
```

```python
async def test_list_documents_canonical_record_uses_source_alias(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document_canonical(
            conn,
            source_path="/canonical/notes.md",
            sha256="a" * 64,
            byte_size=100,
            source_type="file",
            source_locator="/canonical/notes.md",
            source_alias="notes.md",
            chunks=[ChunkRecord(content="canonical content", chunk_index=0, token_count=5)],
            embeddings=[EmbeddingRecord(
                vector=[0.1] * 1024, model="voyage-3", provider="anthropic"
            )],
        )
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert len(result) == 1
    assert result[0].source_alias == "notes.md"
    assert result[0].source_locator == "/canonical/notes.md"


async def test_list_documents_legacy_record_falls_back_to_source_path(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await store_document(
            conn,
            source_path="/legacy/report.md",
            file_hash="bbb",
            chunks=[ChunkRecord(content="legacy content", chunk_index=0, token_count=5)],
            embeddings=[EmbeddingRecord(
                vector=[0.2] * 1024, model="voyage-3", provider="anthropic"
            )],
        )
    service = ProvenanceService(make_test_config(tmp_path))

    result = await service.list_documents()

    assert len(result) == 1
    assert result[0].source_alias == "/legacy/report.md"
    assert result[0].source_locator == "/legacy/report.md"
```

#### `tests/cli/test_cli_docs.py` (new file)

```python
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.store.models import DocumentSummary

runner = CliRunner()


def _make_doc(alias: str = "notes.md", locator: str = "/data/notes.md") -> DocumentSummary:
    return DocumentSummary(
        id="00000000-0000-0000-0000-000000000001",
        source_alias=alias,
        source_locator=locator,
        ingested_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        current_version=1,
        chunk_count=3,
    )


def _patch_docs(docs: list[DocumentSummary]):
    return patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(return_value=docs),
    )


def test_docs_table_header_uses_source_alias() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc()]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "SOURCE ALIAS" in output.output
    assert "SOURCE PATH" not in output.output


def test_docs_table_shows_alias_value() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc(alias="notes.md")]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "notes.md" in output.output


def test_docs_json_output_has_source_alias_and_locator() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc(alias="notes.md", locator="/data/notes.md")]),
    ):
        output = runner.invoke(app, ["docs", "--json"])

    assert output.exit_code == 0
    data = json.loads(output.output)
    assert len(data) == 1
    doc = data[0]
    assert doc["source_alias"] == "notes.md"
    assert doc["source_locator"] == "/data/notes.md"
    assert "source_path" not in doc


def test_docs_empty_database_shows_hint() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "No documents ingested yet" in output.output
```

#### `tests/mcp_server/test_tools.py` — new tests (append)

```python
async def test_retrieve_citations_include_source_alias_and_locator(monkeypatch):
    monkeypatch.setattr(_server, "_retrieval_service", _make_mock_retrieval_service())
    monkeypatch.setattr(_server, "_output_service", _make_mock_output_service())
    result = json.loads(await retrieve(query="workforce segmentation"))

    assert result["status"] == "ok"
    citations = result["citations"]
    assert len(citations) == 1
    assert "source_alias" in citations[0]
    assert "source_locator" in citations[0]
    assert "document_version_id" in citations[0]
    assert "source_path" not in citations[0]


async def test_list_documents_response_includes_source_alias_and_locator(monkeypatch):
    monkeypatch.setattr(_server, "_config", _make_mock_config())
    docs = [
        DocumentSummary(
            id="abc123",
            source_alias="doc.md",
            source_locator="/test/doc.md",
            ingested_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
            current_version=1,
            chunk_count=5,
        )
    ]
    with patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(return_value=docs),
    ):
        result = json.loads(await list_documents())

    doc = result["data"]["documents"][0]
    assert doc["source_alias"] == "doc.md"
    assert doc["source_locator"] == "/test/doc.md"
    assert "source_path" not in doc
```

---

### Do NOT Modify

- `src/cos/ingestion/identity.py` — complete and correct
- `src/cos/ingestion/pipeline.py` — no changes needed
- `src/cos/services/ingestion.py` — `IngestResult` unaffected
- `src/cos/store/migrations/` — no new migrations needed; `documents.source_path` column is retained as the legacy fallback column, not removed
- `src/cos/store/db.py` functions other than `list_documents` — the canonical helpers (`store_document_canonical`, `find_source`, `upsert_source`, etc.) are correct
- `src/cos/retrieval/retrieval.py` / `src/cos/services/retrieval.py` — no changes needed; they call `hybrid_search` and receive `CitedResults`, which will automatically carry the new fields
- `src/cos/rolepack/` — no changes needed
- `src/cos/output/` — no changes needed

---

### Schema Reference

The existing `004_canonical_identity.sql` migration added:

```sql
-- sources: one row per distinct source (file, Gmail, Calendar, etc.)
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_locator TEXT NOT NULL,        -- e.g. absolute path, Gmail message ID
    source_alias TEXT NOT NULL,          -- e.g. filename, subject line
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_type_locator_unique UNIQUE (source_type, source_locator)
);

-- source_versions: tracks which source observed which document_version
CREATE TABLE IF NOT EXISTS source_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id),
    document_version_id UUID NOT NULL REFERENCES document_versions(id),
    content_blob_id UUID NOT NULL REFERENCES content_blobs(id),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT source_versions_source_document_unique UNIQUE (source_id, document_version_id)
);
```

`chunks` gained `document_version_id UUID REFERENCES document_versions(id)` in the same migration (nullable for legacy chunks inserted before Epic 6.1).

`documents.source_path` is NOT removed — it remains as the authoritative legacy fallback for pre-Epic-6 records and is used in COALESCE expressions throughout.

---

### Test Patterns

All integration tests use the `migrated_db` pytest fixture (runs all migrations against `cos_test`). The test database is `postgresql://postgres:postgres@localhost:5432/cos_test`. The `make_test_config(tmp_path)` helper from `tests/conftest.py` provides a valid `CosConfig`.

CLI tests use `typer.testing.CliRunner` with `patch("cos.cli.CosConfig.load", ...)` to bypass real config loading, and mock the service layer. Pattern established in `tests/cli/test_cli_ingest.py`.

MCP tool tests use `monkeypatch.setattr(_server, "_config", ...)` and `patch("cos.services.provenance.ProvenanceService.list_documents", ...)` to bypass real DB. Pattern established in `tests/mcp_server/test_tools.py`.

---

### Implementation Order

1. `citations.py` (Task 1) — makes `CitedChunk` the new contract; everything downstream depends on this
2. `models.py` (Task 3) — makes `DocumentSummary` the new contract
3. `search.py` (Task 2) — uses updated `CitedChunk`
4. `db.py` (Task 4) — uses updated `DocumentSummary`
5. `tools.py` (Task 5) — uses both updated types
6. `cli.py` (Task 6) — uses updated `DocumentSummary`
7. Update broken tests (Task 7) — after all production code is done; run `pytest` to find all failures
8. Add new tests (Task 8)

Run the full test suite after each task to catch regressions early: `pytest tests/ -x`.

---

## Dev Agent Record

### Agent Model Used

`gpt-5-codex`

### Implementation Plan

- Update retrieval and listing contracts first so `CitedChunk` and `DocumentSummary` become the canonical alias-based shapes.
- Replace path-only lookups with canonical source joins plus legacy `documents.source_path` fallback, keeping alias selection deterministic via oldest `sources.created_at`.
- Propagate the new response fields through MCP and CLI output, then expand tests to cover canonical records, legacy fallback, and user-facing outputs.

### Debug Log References

- `uv run pytest tests/retrieval/test_citations.py tests/cli/test_cli_docs.py tests/mcp_server/test_tools.py -q` (red phase; expected contract failures before implementation)
- `uv run pytest tests/retrieval/test_citations.py tests/retrieval/test_search.py tests/services/test_provenance_service.py tests/services/test_retrieval_service.py tests/mcp_server/test_tools.py tests/cli/test_cli_docs.py -q`
- `uv run pytest -q`
- `uv run ruff check src/cos/retrieval/citations.py src/cos/retrieval/search.py src/cos/store/models.py src/cos/store/db.py src/cos/mcp_server/tools.py src/cos/cli.py tests/retrieval/test_citations.py tests/retrieval/test_search.py tests/services/test_provenance_service.py tests/services/test_retrieval_service.py tests/mcp_server/test_tools.py tests/cli/test_cli_docs.py`
- `uv run mypy src/cos/retrieval/citations.py src/cos/retrieval/search.py src/cos/store/models.py src/cos/store/db.py src/cos/mcp_server/tools.py src/cos/cli.py`
- `uv run mypy src` (repo-wide pre-existing failure: missing stubs for `yaml` in `src/cos/rolepack/loader.py`)
- `uv run ruff check src tests` (repo-wide pre-existing failures in untouched files)

### Completion Notes List

- Switched retrieval citations from path-centric labels to `source_alias`, `source_locator`, and `document_version_id`, while preserving legacy fallback behavior for pre-Epic-6 chunks.
- Reworked retrieval and document-listing lookups to prefer canonical `sources`/`source_versions` data and deterministically select the oldest source alias when multiple sources map to the same content.
- Updated MCP tool payloads and `cos docs` CLI output so user-facing responses no longer expose `source_path` as the primary label.
- Added canonical and legacy provenance tests, new CLI docs coverage, and MCP response assertions; also updated existing retrieval and service tests for the renamed fields.
- Story-relevant lint and targeted mypy checks passed; full regression suite passed with `195 passed, 2 skipped`.
- Repo-wide `uv run mypy src` remains blocked by a pre-existing missing `PyYAML` stub in `src/cos/rolepack/loader.py`; repo-wide `uv run ruff check src tests` reports pre-existing issues in untouched files.

## File List

- `src/cos/retrieval/citations.py`
- `src/cos/retrieval/search.py`
- `src/cos/store/models.py`
- `src/cos/store/db.py`
- `src/cos/mcp_server/tools.py`
- `src/cos/cli.py`
- `tests/retrieval/test_citations.py`
- `tests/retrieval/test_search.py`
- `tests/services/test_provenance_service.py`
- `tests/services/test_retrieval_service.py`
- `tests/mcp_server/test_tools.py`
- `tests/cli/test_cli_docs.py`

## Change Log

- 2026-05-06: Implemented canonical source-alias citation and document-listing contract updates across retrieval, storage, MCP, CLI, and tests.
