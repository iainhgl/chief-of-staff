"""Tests for job queue store helpers (enqueue, claim, status transitions)."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from conftest import TEST_DSN

from cos.store.db import (
    claim_next_job,
    enqueue_job,
    mark_job_retryable_failure,
    mark_job_succeeded,
    mark_job_terminal_failure,
    requeue_stale_jobs,
)


async def test_enqueue_job_creates_queued_record(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    payload = {"staged_path": "/data/test.md", "source_type": "file",
               "source_locator": "/data/test.md", "source_alias": "test.md"}
    job = await enqueue_job(db_conn, "ingest", payload)

    assert str(uuid.UUID(job.id)) == job.id
    assert job.job_type == "ingest"
    assert job.status == "queued"
    assert job.payload == payload
    assert job.attempt_count == 0
    assert job.max_attempts == 3


async def test_enqueue_job_respects_custom_max_attempts(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    payload = {"staged_path": "/data/x.md", "source_type": "file",
               "source_locator": "/data/x.md", "source_alias": "x.md"}
    job = await enqueue_job(db_conn, "ingest", payload, max_attempts=5)
    assert job.max_attempts == 5


async def test_claim_next_job_returns_oldest_first(migrated_db: None) -> None:
    payload_a = {"staged_path": "/data/a.md", "source_type": "file",
                 "source_locator": "/data/a.md", "source_alias": "a.md"}
    payload_b = {"staged_path": "/data/b.md", "source_type": "file",
                 "source_locator": "/data/b.md", "source_alias": "b.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job_a = await enqueue_job(conn, "ingest", payload_a)
        await enqueue_job(conn, "ingest", payload_b)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")

    assert claimed is not None
    assert claimed.id == job_a.id
    assert claimed.status == "running"
    assert claimed.attempt_count == 1
    assert claimed.started_at is not None


async def test_claim_next_job_returns_none_when_queue_empty(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    result = await claim_next_job(db_conn, "ingest")
    assert result is None


async def test_claim_next_job_skips_running_jobs(migrated_db: None) -> None:
    payload = {"staged_path": "/data/r.md", "source_type": "file",
               "source_locator": "/data/r.md", "source_alias": "r.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        first = await claim_next_job(conn, "ingest")
        assert first is not None

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        second = await claim_next_job(conn, "ingest")
        assert second is None


async def test_claim_next_job_skips_future_available_at(migrated_db: None) -> None:
    payload = {"staged_path": "/data/f.md", "source_type": "file",
               "source_locator": "/data/f.md", "source_alias": "f.md"}
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload, available_at=future)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await claim_next_job(conn, "ingest")
        assert result is None


async def test_mark_job_succeeded_sets_status(migrated_db: None) -> None:
    payload = {"staged_path": "/data/s.md", "source_type": "file",
               "source_locator": "/data/s.md", "source_alias": "s.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")
        assert claimed is not None
        await mark_job_succeeded(conn, claimed.id)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, completed_at FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"
    assert row[1] is not None


async def test_mark_job_retryable_failure_requeues_with_backoff(
    migrated_db: None,
) -> None:
    payload = {"staged_path": "/data/retry.md", "source_type": "file",
               "source_locator": "/data/retry.md", "source_alias": "retry.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")
        assert claimed is not None
        await mark_job_retryable_failure(
            conn, claimed.id, "transient error", backoff_seconds=0
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, last_error, attempt_count FROM jobs WHERE id = %s::uuid",
            (job.id,),
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert row[1] == "transient error"
    assert row[2] == 1


async def test_mark_job_retryable_failure_uses_failure_time_not_claim_time(
    migrated_db: None,
) -> None:
    payload = {
        "staged_path": "/data/delayed.md",
        "source_type": "file",
        "source_locator": "/data/delayed.md",
        "source_alias": "delayed.md",
    }

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")
        assert claimed is not None
        await conn.execute("SELECT pg_sleep(1)")
        await mark_job_retryable_failure(
            conn, claimed.id, "transient error", backoff_seconds=0
        )
        result = await conn.execute(
            "SELECT started_at, available_at FROM jobs WHERE id = %s::uuid",
            (job.id,),
        )
        row = await result.fetchone()

    assert row is not None
    started_at, available_at = row
    assert available_at > started_at + timedelta(milliseconds=500)


async def test_mark_job_terminal_failure_sets_failed(migrated_db: None) -> None:
    payload = {"staged_path": "/data/fail.md", "source_type": "file",
               "source_locator": "/data/fail.md", "source_alias": "fail.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")
        assert claimed is not None
        await mark_job_terminal_failure(conn, claimed.id, "unrecoverable error")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, last_error, completed_at FROM jobs WHERE id = %s::uuid",
            (job.id,),
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "failed"
    assert row[1] == "unrecoverable error"
    assert row[2] is not None


async def test_requeue_stale_jobs_returns_running_jobs_to_queued(
    migrated_db: None,
) -> None:
    payload = {"staged_path": "/data/stale.md", "source_type": "file",
               "source_locator": "/data/stale.md", "source_alias": "stale.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await claim_next_job(conn, "ingest")
        # Backdate started_at to simulate a stale job
        await conn.execute(
            "UPDATE jobs SET started_at = now() - INTERVAL '10 minutes' "
            "WHERE id = %s::uuid",
            (job.id,),
        )

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        requeued = await requeue_stale_jobs(conn, older_than_seconds=60)

    assert requeued == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, started_at FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert row[1] is None


async def test_requeue_stale_jobs_ignores_fresh_running_jobs(
    migrated_db: None,
) -> None:
    payload = {"staged_path": "/data/fresh.md", "source_type": "file",
               "source_locator": "/data/fresh.md", "source_alias": "fresh.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await claim_next_job(conn, "ingest")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        requeued = await requeue_stale_jobs(conn, older_than_seconds=300)

    assert requeued == 0


async def test_requeue_stale_jobs_ignores_succeeded_and_failed(
    migrated_db: None,
) -> None:
    payload_s = {"staged_path": "/data/done.md", "source_type": "file",
                 "source_locator": "/data/done.md", "source_alias": "done.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload_s)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        claimed = await claim_next_job(conn, "ingest")
        assert claimed is not None
        await mark_job_succeeded(conn, claimed.id)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        requeued = await requeue_stale_jobs(conn, older_than_seconds=0)

    assert requeued == 0


async def test_retry_cycle_eventually_reaches_terminal_failure(
    migrated_db: None,
) -> None:
    payload = {"staged_path": "/data/exhaust.md", "source_type": "file",
               "source_locator": "/data/exhaust.md", "source_alias": "exhaust.md"}

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload, max_attempts=2)

    for _ in range(2):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            claimed = await claim_next_job(conn, "ingest")
            assert claimed is not None
            if claimed.attempt_count < claimed.max_attempts:
                await mark_job_retryable_failure(
                    conn, claimed.id, "error", backoff_seconds=0
                )
            else:
                await mark_job_terminal_failure(conn, claimed.id, "final error")

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "failed"
