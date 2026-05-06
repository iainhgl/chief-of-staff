"""Tests for the jobs service layer (submit_ingest_job, process_next_ingest_job)."""
import uuid
from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.services.jobs import process_next_ingest_job, submit_ingest_job


async def test_submit_ingest_job_creates_queued_job(migrated_db, db_conn) -> None:
    job = await submit_ingest_job(
        db_conn,
        staged_path="/data/test.md",
        source_type="file",
        source_locator="/data/test.md",
        source_alias="test.md",
    )

    assert str(uuid.UUID(job.id)) == job.id
    assert job.job_type == "ingest"
    assert job.status == "queued"
    assert job.payload["staged_path"] == "/data/test.md"
    assert job.payload["source_type"] == "file"
    assert job.payload["source_locator"] == "/data/test.md"
    assert job.payload["source_alias"] == "test.md"


async def test_submit_ingest_job_includes_metadata(migrated_db, db_conn) -> None:
    job = await submit_ingest_job(
        db_conn,
        staged_path="/data/attach.pdf",
        source_type="gmail_attachment",
        source_locator="gmail://message/abc/attachment/xyz",
        source_alias="board-pack.pdf",
        metadata={"connector": "gmail"},
    )

    assert job.payload["metadata"] == {"connector": "gmail"}


async def test_process_next_ingest_job_returns_false_when_empty(
    migrated_db, db_conn
) -> None:
    config = make_test_config(Path("/tmp"))
    processed = await process_next_ingest_job(db_conn, config)
    assert processed is False


async def test_process_next_ingest_job_succeeds_for_valid_file(
    migrated_db,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    staged = tmp_path / "staged.md"
    staged.write_text("Background ingest content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        processed = await process_next_ingest_job(conn, config)

    assert processed is True

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"


async def test_process_next_ingest_job_marks_retryable_on_error(
    migrated_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_test_config(tmp_path)
    staged = tmp_path / "bad.md"
    staged.write_text("content", encoding="utf-8")

    async def _fail(*args, **kwargs):
        raise RuntimeError("simulated transient error")

    monkeypatch.setattr("cos.services.jobs.run_pipeline_from_source", _fail)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await process_next_ingest_job(conn, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status, last_error FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert "transient error" in row[1]


async def test_process_next_ingest_job_marks_terminal_when_attempts_exhausted(
    migrated_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_test_config(tmp_path)
    staged = tmp_path / "exhaust.md"
    staged.write_text("content", encoding="utf-8")

    async def _fail(*args, **kwargs):
        raise RuntimeError("always fails")

    monkeypatch.setattr("cos.services.jobs.run_pipeline_from_source", _fail)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
            metadata={},
        )
        # Force attempt_count to max so next claim is terminal
        await conn.execute(
            "UPDATE jobs SET attempt_count = max_attempts - 1 WHERE id = %s::uuid",
            (job.id,),
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await process_next_ingest_job(conn, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "failed"


async def test_process_next_ingest_job_uses_canonical_identity_path(
    migrated_db,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Worker must go through canonical identity engine, not a shortcut."""
    content = "Shared content for identity test"
    staged_a = tmp_path / "a.md"
    staged_b = tmp_path / "b.md"
    staged_a.write_text(content, encoding="utf-8")
    staged_b.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged_a),
            source_type="file",
            source_locator=str(staged_a),
            source_alias=staged_a.name,
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await process_next_ingest_job(conn, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged_b),
            source_type="file",
            source_locator=str(staged_b),
            source_alias=staged_b.name,
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await process_next_ingest_job(conn, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        doc_count = await conn.execute("SELECT COUNT(*) FROM documents")
        blob_count = await conn.execute("SELECT COUNT(*) FROM content_blobs")
        source_count = await conn.execute("SELECT COUNT(*) FROM sources")

        doc_row = await doc_count.fetchone()
        blob_row = await blob_count.fetchone()
        source_row = await source_count.fetchone()

    assert doc_row == (1,)
    assert blob_row == (1,)
    assert source_row == (2,)
