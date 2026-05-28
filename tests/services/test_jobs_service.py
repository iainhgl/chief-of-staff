"""Tests for the jobs service layer (submit_ingest_job, process_next_ingest_job)."""
import asyncio
import uuid
from pathlib import Path
from typing import Any

import psycopg
import pytest
from conftest import TEST_DSN, make_test_config

from cos.ingestion.identity import IngestOutcome
from cos.ingestion.pipeline import PipelineResult
from cos.services.jobs import process_next_ingest_job, submit_ingest_job


async def test_submit_ingest_job_creates_queued_job(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
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


async def test_submit_ingest_job_includes_metadata(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
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
    migrated_db: None,
) -> None:
    config = make_test_config(Path("/tmp"))
    processed = await process_next_ingest_job(TEST_DSN, config)
    assert processed is False


async def test_process_next_ingest_job_succeeds_for_valid_file(
    migrated_db: None,
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

    processed = await process_next_ingest_job(TEST_DSN, config)

    assert processed is True

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"


async def test_process_next_ingest_job_marks_retryable_on_error(
    migrated_db: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_test_config(tmp_path)
    staged = tmp_path / "bad.md"
    staged.write_text("content", encoding="utf-8")

    async def _fail(*args: object, **kwargs: object) -> PipelineResult:
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

    await process_next_ingest_job(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status, last_error FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert "transient error" in row[1]


async def test_process_next_ingest_job_marks_terminal_when_attempts_exhausted(
    migrated_db: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_test_config(tmp_path)
    staged = tmp_path / "exhaust.md"
    staged.write_text("content", encoding="utf-8")

    async def _fail(*args: object, **kwargs: object) -> PipelineResult:
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

    await process_next_ingest_job(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status FROM jobs WHERE id = %s::uuid", (job.id,)
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "failed"


async def test_process_next_ingest_job_uses_canonical_identity_path(
    migrated_db: None,
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

    await process_next_ingest_job(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged_b),
            source_type="file",
            source_locator=str(staged_b),
            source_alias=staged_b.name,
        )

    await process_next_ingest_job(TEST_DSN, config)

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


async def test_process_next_ingest_job_commits_running_state_before_ingest(
    migrated_db: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged = tmp_path / "long-running.md"
    staged.write_text("content", encoding="utf-8")
    config = make_test_config(tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _block(*args: object, **kwargs: object) -> PipelineResult:
        entered.set()
        await release.wait()
        return PipelineResult(
            document_id=str(uuid.uuid4()),
            chunk_count=0,
            outcome=IngestOutcome.UNCHANGED,
            message="Content unchanged - no new version or embeddings created.",
        )

    monkeypatch.setattr("cos.services.jobs.run_pipeline_from_source", _block)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="file",
            source_locator=str(staged),
            source_alias=staged.name,
        )

    task = asyncio.create_task(process_next_ingest_job(TEST_DSN, config))
    await entered.wait()

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, attempt_count, started_at IS NOT NULL FROM jobs"
        )
        row = await result.fetchone()

    assert row == ("running", 1, True)

    release.set()
    processed = await task
    assert processed is True


async def test_process_next_ingest_job_requeues_malformed_payload(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await conn.execute(
            "INSERT INTO jobs (job_type, payload) VALUES (%s, %s::jsonb)",
            ("ingest", "{}"),
        )

    processed = await process_next_ingest_job(TEST_DSN, config)

    assert processed is True

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute(
            "SELECT status, last_error, attempt_count FROM jobs"
        )
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert "missing payload fields" in row[1]
    assert row[2] == 1


# ─────────────────────────────────────────────
# Story 8.3 tests — telegram_note job lifecycle
# ─────────────────────────────────────────────

async def test_submit_telegram_note_job_creates_queued_job(
    migrated_db: None,
    db_conn: psycopg.AsyncConnection[Any],
) -> None:
    job = await submit_ingest_job(
        db_conn,
        staged_path="/data/connector-staging/telegram/telegram-note-2026-05-28T101530Z-4321_abc.md",
        source_type="telegram_note",
        source_locator="telegram://chat/111222333/message/4321",
        source_alias="telegram-note-2026-05-28T101530Z-4321.md",
        metadata={
            "connector": "telegram",
            "chat_id": 111222333,
            "message_id": 4321,
            "content_fingerprint": "abc123",
        },
    )

    assert job.status == "queued"
    assert job.payload["source_type"] == "telegram_note"
    assert job.payload["source_locator"] == "telegram://chat/111222333/message/4321"
    assert job.payload["metadata"]["connector"] == "telegram"


async def test_process_telegram_note_job_succeeds(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Worker processes telegram_note source_type without schema changes."""
    staged = tmp_path / "telegram-note-2026-05-28T101530Z-4321.md"
    staged.write_text(
        "# Telegram Note\n\nCaptured: 2026-05-28T10:15:30+00:00\n"
        "Chat ID: 111222333\n\n---\n\nThis is a test note.",
        encoding="utf-8",
    )
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="telegram_note",
            source_locator="telegram://chat/111222333/message/4321",
            source_alias=staged.name,
            metadata={"connector": "telegram", "content_fingerprint": "abc123"},
        )

    processed = await process_next_ingest_job(TEST_DSN, config)
    assert processed is True

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        result = await conn.execute("SELECT status FROM jobs")
        row = await result.fetchone()

    assert row is not None
    assert row[0] == "succeeded"


async def test_telegram_note_job_produces_retrievable_document(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Telegram note appears in list_documents with canonical provenance."""
    from cos.store.db import list_documents

    staged = tmp_path / "telegram-note-2026-05-28T101530Z-4321.md"
    staged.write_text(
        "# Telegram Note\n\nCaptured: 2026-05-28T10:15:30+00:00\n\n"
        "---\n\nSome searchable note content.",
        encoding="utf-8",
    )
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged),
            source_type="telegram_note",
            source_locator="telegram://chat/111222333/message/4321",
            source_alias=staged.name,
        )

    await process_next_ingest_job(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        docs = await list_documents(conn)

    assert len(docs) == 1
    assert staged.name in docs[0].source_alias
    assert "telegram://chat" in docs[0].source_locator


async def test_telegram_note_dedup_same_locator_different_fingerprint(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Exact-byte duplicates from same Telegram source share one canonical document."""
    content = "# Telegram Note\n\n---\n\nSame content from same source."
    staged_a = tmp_path / "note-a.md"
    staged_b = tmp_path / "note-b.md"
    staged_a.write_text(content, encoding="utf-8")
    staged_b.write_text(content, encoding="utf-8")
    config = make_test_config(tmp_path)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged_a),
            source_type="telegram_note",
            source_locator="telegram://chat/111222333/message/9001",
            source_alias="note-a.md",
        )

    await process_next_ingest_job(TEST_DSN, config)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        await submit_ingest_job(
            conn,
            staged_path=str(staged_b),
            source_type="telegram_note",
            source_locator="telegram://chat/111222333/message/9002",
            source_alias="note-b.md",
        )

    await process_next_ingest_job(TEST_DSN, config)

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
