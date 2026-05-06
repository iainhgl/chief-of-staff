"""Tests for the background ingest worker (run_once, startup recovery)."""
from pathlib import Path

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.services.jobs import submit_ingest_job
from cos.worker import recover_stale_jobs, run_once


async def test_run_once_returns_false_when_queue_empty(migrated_db) -> None:
    config = make_test_config(Path("/tmp"))
    result = await run_once(TEST_DSN, config)
    assert result is False


async def test_run_once_processes_queued_job(
    migrated_db,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    staged = tmp_path / "worker-test.md"
    staged.write_text("Worker processes this content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    result = await run_once(TEST_DSN, config)
    assert result is True

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        status_result = await conn.execute("SELECT status FROM jobs")
        row = await status_result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"


async def test_run_once_marks_job_succeeded_on_success(
    migrated_db,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    staged = tmp_path / "success.md"
    staged.write_text("Content that will be processed successfully", encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    await run_once(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, completed_at FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"
    assert row[1] is not None


async def test_run_once_marks_job_retryable_on_transient_error(
    migrated_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged = tmp_path / "retryable.md"
    staged.write_text("content", encoding="utf-8")
    config = make_test_config(tmp_path)

    async def _fail(*args, **kwargs):
        raise RuntimeError("transient error")

    monkeypatch.setattr("cos.services.jobs.run_pipeline_from_source", _fail)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    await run_once(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, last_error, attempt_count FROM jobs WHERE id = %s::uuid",
            (job.id,),
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert "transient error" in row[1]
    assert row[2] == 1


async def test_run_once_marks_job_terminal_when_max_attempts_reached(
    migrated_db,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged = tmp_path / "terminal.md"
    staged.write_text("content", encoding="utf-8")
    config = make_test_config(tmp_path)

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
        )
        await conn.execute(
            "UPDATE jobs SET attempt_count = max_attempts - 1 WHERE id = %s::uuid",
            (job.id,),
        )

    await run_once(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "failed"


async def test_recover_stale_jobs_requeues_crashed_running_jobs(migrated_db) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await conn.execute(
            "INSERT INTO jobs (job_type, status, payload, attempt_count, started_at) "
            "VALUES ('ingest', 'running', '{\"staged_path\": \"/data/stale.md\", "
            "\"source_type\": \"file\", \"source_locator\": \"/data/stale.md\", "
            "\"source_alias\": \"stale.md\"}', 1, "
            "now() - INTERVAL '10 minutes')"
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        count = await recover_stale_jobs(conn)

    assert count == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status, started_at FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert row[1] is None


async def test_recover_stale_jobs_does_not_disturb_fresh_running_jobs(
    migrated_db,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await conn.execute(
            "INSERT INTO jobs (job_type, status, payload, attempt_count, started_at) "
            "VALUES ('ingest', 'running', '{\"staged_path\": \"/data/fresh.md\", "
            "\"source_type\": \"file\", \"source_locator\": \"/data/fresh.md\", "
            "\"source_alias\": \"fresh.md\"}', 1, now())"
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        count = await recover_stale_jobs(conn)

    assert count == 0
