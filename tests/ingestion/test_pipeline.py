import uuid
from pathlib import Path

import psycopg
from conftest import TEST_DSN, make_test_config

from cos.ingestion.identity import IngestOutcome
from cos.ingestion.pipeline import PipelineResult, run_pipeline, run_pipeline_from_source


async def test_run_pipeline_markdown_creates_document(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "notes.md"
    source_path.write_text(
        "# Meeting Notes\n\nDiscussed Q3 strategy.",
        encoding="utf-8",
    )
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline(source_path, config, conn)

    assert isinstance(result, PipelineResult)
    assert str(uuid.UUID(result.document_id)) == result.document_id
    assert result.chunk_count >= 1
    assert result.outcome is IngestOutcome.NEW_CONTENT


async def test_run_pipeline_reingest_increments_version(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "versioned.md"
    source_path.write_text("Version one content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first_result = await run_pipeline(source_path, config, conn)

    source_path.write_text("Version two content", encoding="utf-8")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        second_result = await run_pipeline(source_path, config, conn)
        db_result = await conn.execute(
            "SELECT current_version FROM documents WHERE id = %s",
            (first_result.document_id,),
        )
        row = await db_result.fetchone()

    assert first_result.document_id == second_result.document_id
    assert row == (2,)
    assert first_result.outcome is IngestOutcome.NEW_CONTENT
    assert second_result.outcome is IngestOutcome.CHANGED_CONTENT


async def test_run_pipeline_same_bytes_same_source_is_unchanged(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
    monkeypatch,
) -> None:
    source_path = tmp_path / "same-source.md"
    source_path.write_text("Steady content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first_result = await run_pipeline(source_path, config, conn)

        async def _fail_extract(*args, **kwargs):
            raise AssertionError("extract should not run for unchanged content")

        monkeypatch.setattr("cos.ingestion.pipeline.extract", _fail_extract)
        second_result = await run_pipeline(source_path, config, conn)
        counts_result = await conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM documents), "
            "(SELECT COUNT(*) FROM document_versions), "
            "(SELECT COUNT(*) FROM content_blobs), "
            "(SELECT COUNT(*) FROM source_versions)"
        )
        counts = await counts_result.fetchone()

    assert second_result.document_id == first_result.document_id
    assert second_result.outcome is IngestOutcome.UNCHANGED
    assert second_result.chunk_count == 0
    assert "unchanged" in second_result.message.lower()
    assert counts == (1, 1, 1, 1)


async def test_run_pipeline_same_bytes_new_source_creates_new_provenance_only(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
    monkeypatch,
) -> None:
    first_path = tmp_path / "first.md"
    second_path = tmp_path / "nested" / "second.md"
    second_path.parent.mkdir()
    content = "Identical bytes across different sources"
    first_path.write_text(content, encoding="utf-8")
    second_path.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first_result = await run_pipeline(first_path, config, conn)

        async def _fail_extract(*args, **kwargs):
            raise AssertionError(
                "extract should not run for known content from a new source"
            )

        monkeypatch.setattr("cos.ingestion.pipeline.extract", _fail_extract)
        second_result = await run_pipeline(second_path, config, conn)
        counts_result = await conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM documents), "
            "(SELECT COUNT(*) FROM document_versions), "
            "(SELECT COUNT(*) FROM content_blobs), "
            "(SELECT COUNT(*) FROM sources), "
            "(SELECT COUNT(*) FROM source_versions)"
        )
        counts = await counts_result.fetchone()

    assert second_result.document_id == first_result.document_id
    assert second_result.outcome is IngestOutcome.NEW_SOURCE_KNOWN_CONTENT
    assert second_result.chunk_count == 0
    assert "new source" in second_result.message.lower()
    assert counts == (1, 1, 1, 2, 2)


async def test_run_pipeline_new_bytes_creates_content_blob_record(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "blob.md"
    content = "Blob tracked content"
    source_path.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)
        result = await conn.execute(
            "SELECT sha256, byte_size FROM content_blobs"
        )
        rows = await result.fetchall()

    assert len(rows) == 1
    assert rows[0][1] == len(content.encode("utf-8"))


async def test_run_pipeline_new_bytes_creates_source_and_source_version(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "source-version.md"
    source_path.write_text("Track source provenance", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline(source_path, config, conn)
        db_result = await conn.execute(
            "SELECT s.source_type, s.source_locator, s.source_alias, "
            "sv.document_version_id::text, sv.content_blob_id::text "
            "FROM sources s "
            "JOIN source_versions sv ON sv.source_id = s.id "
            "JOIN document_versions dv ON dv.id = sv.document_version_id "
            "WHERE dv.document_id = %s::uuid",
            (result.document_id,),
        )
        row = await db_result.fetchone()

    assert row is not None
    assert row[0] == "file"
    assert row[1] == str(source_path)
    assert row[2] == source_path.name
    assert str(uuid.UUID(row[3])) == row[3]
    assert str(uuid.UUID(row[4])) == row[4]


async def test_run_pipeline_unchanged_returns_zero_chunk_count(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "unchanged-count.md"
    source_path.write_text("No changes here", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)
        result = await run_pipeline(source_path, config, conn)

    assert result.outcome is IngestOutcome.UNCHANGED
    assert result.chunk_count == 0


async def test_run_pipeline_new_source_known_content_returns_zero_chunk_count(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    first_path = tmp_path / "first-known.md"
    second_path = tmp_path / "other" / "second-known.md"
    second_path.parent.mkdir()
    first_path.write_text("Shared content", encoding="utf-8")
    second_path.write_text("Shared content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(first_path, config, conn)
        result = await run_pipeline(second_path, config, conn)

    assert result.outcome is IngestOutcome.NEW_SOURCE_KNOWN_CONTENT
    assert result.chunk_count == 0


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

    source_path.write_text("Version two content with different bytes", encoding="utf-8")

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
    assert row == (1, 2, 2)


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

    source_path.write_text("Changed bytes with distinct hash", encoding="utf-8")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await run_pipeline(source_path, config, conn)
        result = await conn.execute("SELECT COUNT(*) FROM content_blobs")
        row = await result.fetchone()

    assert row == (2,)


async def test_run_pipeline_changed_content_links_source_version_to_new_document_version(  # noqa: E501
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "sv-link.md"
    source_path.write_text("First version content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await run_pipeline(source_path, config, conn)

    source_path.write_text("Second version content with new bytes", encoding="utf-8")

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
    assert sv_row == (2,)


async def test_run_pipeline_from_source_accepts_explicit_source_metadata(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    staged = tmp_path / "staged.md"
    staged.write_text("Connector-staged content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline_from_source(
            staged_path=staged,
            source_type="gmail_attachment",
            source_locator="gmail://message/abc/attachment/xyz",
            source_alias="board-pack.pdf",
            config=config,
            conn=conn,
        )

    assert isinstance(result, PipelineResult)
    assert str(uuid.UUID(result.document_id)) == result.document_id
    assert result.chunk_count >= 1
    assert result.outcome is IngestOutcome.NEW_CONTENT


async def test_run_pipeline_from_source_uses_source_locator_for_identity(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
    monkeypatch,
) -> None:
    """Re-staging same content at a different path but same source_locator is UNCHANGED."""
    staged_first = tmp_path / "first_stage.md"
    staged_second = tmp_path / "second_stage.md"
    content = "Same content staged twice"
    staged_first.write_text(content, encoding="utf-8")
    staged_second.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)
    source_locator = "gmail://message/abc/attachment/xyz"

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await run_pipeline_from_source(
            staged_path=staged_first,
            source_type="gmail_attachment",
            source_locator=source_locator,
            source_alias="board-pack.pdf",
            config=config,
            conn=conn,
        )

    async def _fail_extract(*args, **kwargs):
        raise AssertionError("extract should not run for unchanged content")

    monkeypatch.setattr("cos.ingestion.pipeline.extract", _fail_extract)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        second = await run_pipeline_from_source(
            staged_path=staged_second,
            source_type="gmail_attachment",
            source_locator=source_locator,
            source_alias="board-pack.pdf",
            config=config,
            conn=conn,
        )

    assert second.document_id == first.document_id
    assert second.outcome is IngestOutcome.UNCHANGED
    assert second.chunk_count == 0


async def test_run_pipeline_wrapper_preserves_file_source_behaviour(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """run_pipeline must remain a thin wrapper with no user-visible behaviour change."""
    source_path = tmp_path / "cli-ingest.md"
    source_path.write_text("CLI-ingested document", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await run_pipeline(source_path, config, conn)

    assert result.outcome is IngestOutcome.NEW_CONTENT
    assert result.chunk_count >= 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        source_result = await conn.execute(
            "SELECT source_type, source_locator, source_alias FROM sources"
        )
        row = await source_result.fetchone()

    assert row is not None
    assert row[0] == "file"
    assert row[1] == str(source_path)
    assert row[2] == source_path.name
