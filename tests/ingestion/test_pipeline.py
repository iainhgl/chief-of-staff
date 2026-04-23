import uuid
from pathlib import Path

import psycopg
from conftest import TEST_DSN, make_test_config

from cos.ingestion.pipeline import PipelineResult, run_pipeline


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
