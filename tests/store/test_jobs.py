"""Tests for job queue store helpers (enqueue, claim, status transitions)."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
import pytest
from conftest import TEST_DSN

from cos.store.db import (
    claim_next_job,
    enqueue_job,
    has_pending_job_for_locator,
    has_processed_artifact,
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


# ── has_processed_artifact ────────────────────────────────────────────────────

async def test_has_processed_artifact_returns_false_when_nothing_ingested(
    migrated_db: None,
) -> None:
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        found = await has_processed_artifact(
            conn, "gmail_message_body", "gmail://message/x/body", "abc123"
        )
    assert found is False


async def test_has_processed_artifact_returns_true_after_ingestion(
    migrated_db: None,
) -> None:
    import hashlib

    content = b"some body content"
    fingerprint = hashlib.sha256(content).hexdigest()

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        blob = await conn.execute(
            "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, %s) RETURNING id::text",
            (fingerprint, len(content)),
        )
        blob_row = await blob.fetchone()
        assert blob_row is not None
        blob_id = blob_row[0]

        source = await conn.execute(
            "INSERT INTO sources (source_type, source_locator, source_alias) "
            "VALUES ('gmail_message_body', 'gmail://message/msg-1/body', 'msg-1.md') "
            "RETURNING id::text",
        )
        source_row = await source.fetchone()
        assert source_row is not None
        source_id = source_row[0]

        doc = await conn.execute(
            "INSERT INTO documents (source_path, file_hash, current_version, status) "
            "VALUES ('/tmp/staged.md', %s, 1, 'indexed') RETURNING id",
            (fingerprint,),
        )
        doc_row = await doc.fetchone()
        assert doc_row is not None
        document_id = doc_row[0]

        dv = await conn.execute(
            "INSERT INTO document_versions (document_id, version, content_hash, content_blob_id) "
            "VALUES (%s, 1, %s, %s::uuid) RETURNING id::text",
            (document_id, fingerprint, blob_id),
        )
        dv_row = await dv.fetchone()
        assert dv_row is not None
        dv_id = dv_row[0]

        await conn.execute(
            "INSERT INTO source_versions (source_id, document_version_id, content_blob_id) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid)",
            (source_id, dv_id, blob_id),
        )

        found = await has_processed_artifact(
            conn, "gmail_message_body", "gmail://message/msg-1/body", fingerprint
        )
    assert found is True


async def test_has_processed_artifact_returns_false_for_different_fingerprint(
    migrated_db: None,
) -> None:
    """Different fingerprint (changed content) is not considered already processed."""
    import hashlib

    fingerprint_a = hashlib.sha256(b"version a").hexdigest()
    fingerprint_b = hashlib.sha256(b"version b").hexdigest()

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        blob = await conn.execute(
            "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, %s) RETURNING id::text",
            (fingerprint_a, 9),
        )
        blob_row = await blob.fetchone()
        assert blob_row is not None
        blob_id = blob_row[0]

        source = await conn.execute(
            "INSERT INTO sources (source_type, source_locator, source_alias) "
            "VALUES ('gmail_message_body', 'gmail://message/msg-x/body', 'msg-x.md') "
            "RETURNING id::text",
        )
        source_row = await source.fetchone()
        assert source_row is not None
        source_id = source_row[0]

        doc = await conn.execute(
            "INSERT INTO documents (source_path, file_hash, current_version, status) "
            "VALUES ('/tmp/staged-x.md', %s, 1, 'indexed') RETURNING id",
            (fingerprint_a,),
        )
        doc_row = await doc.fetchone()
        assert doc_row is not None
        document_id = doc_row[0]

        dv = await conn.execute(
            "INSERT INTO document_versions (document_id, version, content_hash, content_blob_id) "
            "VALUES (%s, 1, %s, %s::uuid) RETURNING id::text",
            (document_id, fingerprint_a, blob_id),
        )
        dv_row = await dv.fetchone()
        assert dv_row is not None
        dv_id = dv_row[0]

        await conn.execute(
            "INSERT INTO source_versions (source_id, document_version_id, content_blob_id) "
            "VALUES (%s::uuid, %s::uuid, %s::uuid)",
            (source_id, dv_id, blob_id),
        )

        # Query with a DIFFERENT fingerprint → should return False
        found = await has_processed_artifact(
            conn, "gmail_message_body", "gmail://message/msg-x/body", fingerprint_b
        )
    assert found is False


async def test_has_processed_artifact_only_matches_latest_source_version(
    migrated_db: None,
) -> None:
    fingerprint_a = "fingerprint-a"
    fingerprint_b = "fingerprint-b"

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        source = await conn.execute(
            "INSERT INTO sources (source_type, source_locator, source_alias) "
            "VALUES ('gmail_message_body', 'gmail://message/msg-latest/body', 'msg.md') "
            "RETURNING id::text",
        )
        source_row = await source.fetchone()
        assert source_row is not None
        source_id = source_row[0]

        for version, fingerprint in enumerate((fingerprint_a, fingerprint_b), start=1):
            blob = await conn.execute(
                "INSERT INTO content_blobs (sha256, byte_size) VALUES (%s, %s) RETURNING id::text",
                (fingerprint, 1),
            )
            blob_row = await blob.fetchone()
            assert blob_row is not None
            blob_id = blob_row[0]

            if version == 1:
                doc = await conn.execute(
                    "INSERT INTO documents (source_path, file_hash, current_version, status) "
                    "VALUES ('/tmp/staged-latest.md', %s, 2, 'indexed') RETURNING id",
                    (fingerprint,),
                )
                doc_row = await doc.fetchone()
                assert doc_row is not None
                document_id = doc_row[0]

            dv = await conn.execute(
                "INSERT INTO document_versions (document_id, version, content_hash, content_blob_id) "
                "VALUES (%s, %s, %s, %s::uuid) RETURNING id::text",
                (document_id, version, fingerprint, blob_id),
            )
            dv_row = await dv.fetchone()
            assert dv_row is not None
            dv_id = dv_row[0]

            await conn.execute(
                "INSERT INTO source_versions (source_id, document_version_id, content_blob_id, observed_at) "
                "VALUES (%s::uuid, %s::uuid, %s::uuid, now() + (%s * INTERVAL '1 second'))",
                (source_id, dv_id, blob_id, version),
            )

        latest_old = await has_processed_artifact(
            conn,
            "gmail_message_body",
            "gmail://message/msg-latest/body",
            fingerprint_a,
        )
        latest_new = await has_processed_artifact(
            conn,
            "gmail_message_body",
            "gmail://message/msg-latest/body",
            fingerprint_b,
        )

    assert latest_old is False
    assert latest_new is True


# ── has_pending_job_for_locator ───────────────────────────────────────────────

async def test_has_pending_job_returns_false_when_no_jobs(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    found = await has_pending_job_for_locator(
        db_conn, "gmail://message/x/body", "fingerprintabc"
    )
    assert found is False


async def test_has_pending_job_returns_true_for_queued_job(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    locator = "gmail://message/msg-pend-1/body"
    fingerprint = "fp-queued-001"
    payload = {
        "staged_path": "/tmp/msg.md",
        "source_type": "gmail_message_body",
        "source_locator": locator,
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": fingerprint},
    }
    await enqueue_job(db_conn, "ingest", payload)

    found = await has_pending_job_for_locator(db_conn, locator, fingerprint)
    assert found is True


async def test_has_pending_job_returns_false_after_job_succeeds(
    migrated_db: None,
) -> None:
    locator = "gmail://message/msg-done-1/body"
    fingerprint = "fp-done-001"
    payload = {
        "staged_path": "/tmp/msg.md",
        "source_type": "gmail_message_body",
        "source_locator": locator,
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": fingerprint},
    }

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job = await enqueue_job(conn, "ingest", payload)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await claim_next_job(conn, "ingest")
        await mark_job_succeeded(conn, job.id)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        found = await has_pending_job_for_locator(conn, locator, fingerprint)
    assert found is False


async def test_has_pending_job_returns_false_for_different_fingerprint(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    locator = "gmail://message/msg-fp-1/body"
    payload = {
        "staged_path": "/tmp/msg.md",
        "source_type": "gmail_message_body",
        "source_locator": locator,
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": "fingerprint-A"},
    }
    await enqueue_job(db_conn, "ingest", payload)

    # Query with a different fingerprint → should return False
    found = await has_pending_job_for_locator(db_conn, locator, "fingerprint-B")
    assert found is False


async def test_has_pending_job_treats_legacy_gmail_job_without_fingerprint_as_pending(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    locator = "gmail://message/msg-legacy/body"
    payload = {
        "staged_path": "/tmp/msg.md",
        "source_type": "gmail_message_body",
        "source_locator": locator,
        "source_alias": "msg.md",
        "metadata": {},
    }
    await enqueue_job(db_conn, "ingest", payload)

    found = await has_pending_job_for_locator(db_conn, locator, "fingerprint-new")
    assert found is True


async def test_pending_gmail_unique_index_rejects_duplicate_locator_and_fingerprint(
    migrated_db: None,
) -> None:
    payload = {
        "staged_path": "/tmp/msg.md",
        "source_type": "gmail_message_body",
        "source_locator": "gmail://message/msg-unique/body",
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": "fp-unique-001"},
    }

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload)
        with pytest.raises(psycopg.errors.UniqueViolation):
            await enqueue_job(conn, "ingest", payload)


async def test_pending_gmail_unique_index_allows_same_locator_with_new_fingerprint(
    migrated_db: None,
) -> None:
    payload_a = {
        "staged_path": "/tmp/msg-a.md",
        "source_type": "gmail_message_body",
        "source_locator": "gmail://message/msg-unique/body",
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": "fp-unique-A"},
    }
    payload_b = {
        "staged_path": "/tmp/msg-b.md",
        "source_type": "gmail_message_body",
        "source_locator": "gmail://message/msg-unique/body",
        "source_alias": "msg.md",
        "metadata": {"content_fingerprint": "fp-unique-B"},
    }

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await enqueue_job(conn, "ingest", payload_a)
        await enqueue_job(conn, "ingest", payload_b)
