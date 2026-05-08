"""Tests for Gmail service layer: staging, job submission, duplicate semantics."""
import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import psycopg
from conftest import TEST_DSN, make_test_config

from cos.config import GmailConnectorConfig
from cos.services.gmail import GmailPollResult, poll_gmail


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _plain_message(
    message_id: str,
    subject: str = "Test Subject",
    from_addr: str = "alice@example.com",
    body: str = "Hello from Gmail",
) -> dict[str, Any]:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": from_addr},
            ],
            "body": {"data": _b64url(body.encode())},
        },
    }


def _multipart_message_with_attachment(
    message_id: str,
    att_filename: str,
    att_data: bytes,
    attachment_id: str = "att-id-001",
) -> dict[str, Any]:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Subject", "value": "Message with attachment"},
                {"name": "From", "value": "bob@example.com"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64url(b"See attachment.")},
                },
                {
                    "mimeType": "application/pdf",
                    "filename": att_filename,
                    "body": {"attachmentId": attachment_id},
                },
            ],
        },
    }


def _patch_gmail(
    message_ids: list[str],
    messages: dict[str, Any],
    attachment_bytes: dict[tuple[str, str], bytes] | None = None,
):
    """Context manager that patches Gmail API calls with synthetic data."""
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        service = MagicMock()

        def _fetch_message(svc: Any, mid: str) -> dict[str, Any]:
            return messages[mid]

        def _fetch_att(svc: Any, mid: str, aid: str) -> bytes:
            return (attachment_bytes or {}).get((mid, aid), b"")

        with (
            patch("cos.services.gmail.build_gmail_service", return_value=service),
            patch("cos.services.gmail.list_message_ids", return_value=message_ids),
            patch("cos.services.gmail.fetch_message", side_effect=_fetch_message),
            patch("cos.services.gmail.fetch_attachment_bytes", side_effect=_fetch_att),
        ):
            yield

    return _ctx()


# ── body job submission ───────────────────────────────────────────────────────

async def test_poll_gmail_enqueues_body_job(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    msg = _plain_message("msg-001", subject="Budget Review")
    with _patch_gmail(["msg-001"], {"msg-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.messages_scanned == 1
    assert result.body_jobs_enqueued == 1
    assert result.attachment_jobs_enqueued == 0

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    payload = row[0]
    assert payload["source_type"] == "gmail_message_body"
    assert payload["source_locator"] == "gmail://message/msg-001/body"
    assert payload["metadata"]["message_id"] == "msg-001"
    assert payload["metadata"]["subject"] == "Budget Review"
    assert payload["metadata"]["connector"] == "gmail"


async def test_poll_gmail_body_alias_uses_subject(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    msg = _plain_message("msg-002", subject="Q3 Board Pack")
    with _patch_gmail(["msg-002"], {"msg-002": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute("SELECT payload FROM jobs")).fetchone()

    assert row is not None
    assert row[0]["source_alias"].endswith(".md")
    assert "Q3_Board_Pack" in row[0]["source_alias"]


async def test_poll_gmail_body_file_staged_on_disk(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-003", body="Important content")
    with _patch_gmail(["msg-003"], {"msg-003": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    staged_files = list(staging_dir.glob("msg-003_body_*.md"))
    assert len(staged_files) == 1
    assert "Important content" in staged_files[0].read_text()


# ── attachment job submission ─────────────────────────────────────────────────

async def test_poll_gmail_enqueues_pdf_attachment_job(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    pdf_bytes = b"%PDF-1.4 fake content"
    msg = _multipart_message_with_attachment("msg-010", "report.pdf", pdf_bytes)
    with _patch_gmail(
        ["msg-010"],
        {"msg-010": msg},
        {("msg-010", "att-id-001"): pdf_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 1
    assert result.attachments_skipped == 0

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        rows = await (await conn.execute(
            "SELECT payload FROM jobs "
            "WHERE payload->>'source_type' = 'gmail_attachment'"
        )).fetchall()

    assert len(rows) == 1
    payload = rows[0][0]
    assert payload["source_locator"] == "gmail://message/msg-010/attachment/att-id-001"
    assert payload["source_alias"] == "report.pdf"
    assert payload["metadata"]["mime_type"] == "application/pdf"


async def test_poll_gmail_skips_unsupported_attachment(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    msg = {
        "id": "msg-020",
        "threadId": "thread-020",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "Subject", "value": "Has image"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url(b"body")}},
                {
                    "mimeType": "image/png",
                    "filename": "photo.png",
                    "body": {"attachmentId": "att-img"},
                },
            ],
        },
    }
    with _patch_gmail(["msg-020"], {"msg-020": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 0
    assert result.attachments_skipped == 1


async def test_poll_gmail_attachment_staged_with_unique_name(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    pdf_bytes = b"%PDF content"
    msg = _multipart_message_with_attachment("msg-030", "report.pdf", pdf_bytes)
    with _patch_gmail(
        ["msg-030"],
        {"msg-030": msg},
        {("msg-030", "att-id-001"): pdf_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    staged_files = list(staging_dir.glob("*.pdf"))
    assert len(staged_files) == 1
    assert "msg-030" in staged_files[0].name


async def test_poll_gmail_filename_less_supported_attachment_gets_fallback_alias(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    pdf_bytes = b"%PDF filename-less"
    msg = {
        "id": "msg-031",
        "threadId": "thread-msg-031",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "Subject", "value": "No filename"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url(b"body")}},
                {
                    "mimeType": "application/pdf",
                    "partId": "2",
                    "body": {"attachmentId": "att-no-name"},
                },
            ],
        },
    }

    with _patch_gmail(
        ["msg-031"],
        {"msg-031": msg},
        {("msg-031", "att-no-name"): pdf_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (
            await conn.execute(
                "SELECT payload FROM jobs "
                "WHERE payload->>'source_type' = 'gmail_attachment'"
            )
        ).fetchone()

    assert row is not None
    payload = row[0]
    assert payload["source_locator"] == "gmail://message/msg-031/attachment/att-no-name"
    assert payload["source_alias"] == "attachment-att-no-name.pdf"


async def test_poll_gmail_inline_attachments_without_ids_get_unique_paths(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = {
        "id": "msg-032",
        "threadId": "thread-msg-032",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "Subject", "value": "Inline attachments"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url(b"body")}},
                {
                    "mimeType": "text/plain",
                    "partId": "1.2",
                    "filename": "a.txt",
                    "headers": [{"name": "Content-Disposition", "value": "inline"}],
                    "body": {"data": _b64url(b"first attachment")},
                },
                {
                    "mimeType": "text/plain",
                    "partId": "1.3",
                    "filename": "b.txt",
                    "headers": [{"name": "Content-Disposition", "value": "inline"}],
                    "body": {"data": _b64url(b"second attachment")},
                },
            ],
        },
    }

    with _patch_gmail(["msg-032"], {"msg-032": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 2

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        rows = await (
            await conn.execute(
                "SELECT payload->>'staged_path', payload->>'source_locator' "
                "FROM jobs WHERE payload->>'source_type' = 'gmail_attachment' "
                "ORDER BY payload->>'source_alias'"
            )
        ).fetchall()

    assert len(rows) == 2
    staged_paths = {row[0] for row in rows}
    locators = {row[1] for row in rows}
    assert len(staged_paths) == 2
    assert locators == {
        "gmail://message/msg-032/attachment/1.2",
        "gmail://message/msg-032/attachment/1.3",
    }


async def test_poll_gmail_long_attachment_id_uses_short_staged_filename(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    long_attachment_id = "att-" + ("x" * 400)
    markdown_bytes = b"long attachment id content"
    msg = {
        "id": "msg-033",
        "threadId": "thread-msg-033",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "Subject", "value": "Long attachment id"}],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url(b"body")}},
                {
                    "mimeType": "text/markdown",
                    "filename": "shared-note.md",
                    "body": {"attachmentId": long_attachment_id},
                },
            ],
        },
    }

    with _patch_gmail(
        ["msg-033"],
        {"msg-033": msg},
        {("msg-033", long_attachment_id): markdown_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (
            await conn.execute(
                "SELECT payload->>'staged_path', payload->>'source_locator' "
                "FROM jobs WHERE payload->>'source_type' = 'gmail_attachment'"
            )
        ).fetchone()

    assert row is not None
    staged_path, source_locator = row
    assert staged_path is not None
    assert len(Path(staged_path).name) <= 240
    assert source_locator == f"gmail://message/msg-033/attachment/{long_attachment_id}"


# ── empty poll ────────────────────────────────────────────────────────────────

async def test_poll_gmail_returns_zero_counts_for_empty_inbox(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=tmp_path / "staging"),
        }
    )

    with _patch_gmail([], {}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result == GmailPollResult(
        messages_scanned=0,
        body_jobs_enqueued=0,
        attachment_jobs_enqueued=0,
        attachments_skipped=0,
    )


# ── default config ────────────────────────────────────────────────────────────

async def test_poll_gmail_uses_default_config_when_gmail_is_none(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    """config.gmail=None should fall back to GmailConnectorConfig() defaults."""
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={"connectors": ["gmail"], "gmail": None}
    )

    msg = _plain_message("msg-040")
    with (
        _patch_gmail(["msg-040"], {"msg-040": msg}),
        patch("cos.services.gmail.GmailConnectorConfig") as mock_cfg_cls,
    ):
        mock_cfg = MagicMock()
        mock_cfg.staging_dir = tmp_path / "staging"
        mock_cfg_cls.return_value = mock_cfg

        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.messages_scanned == 1


# ── integration: blob deduplication ──────────────────────────────────────────

async def test_identical_attachments_from_different_messages_share_one_blob(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Two Gmail messages with byte-identical attachments → 1 blob, 2 sources."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    # Use .txt to avoid Tika dependency in this test environment
    shared_content = b"Shared text content for deduplication test"

    def _txt_msg(mid: str, att_id: str) -> dict[str, Any]:
        return {
            "id": mid,
            "threadId": f"thread-{mid}",
            "internalDate": "1746518400000",
            "payload": {
                "mimeType": "multipart/mixed",
                "headers": [{"name": "Subject", "value": "Shared attachment"}],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64url(b"body")}},
                    {
                        "mimeType": "text/plain",
                        "filename": "notes.txt",
                        "body": {"attachmentId": att_id},
                    },
                ],
            },
        }

    msg_a = _txt_msg("msg-dup-a", "att-a-001")
    msg_b = _txt_msg("msg-dup-b", "att-b-001")

    with _patch_gmail(
        ["msg-dup-a", "msg-dup-b"],
        {"msg-dup-a": msg_a, "msg-dup-b": msg_b},
        {
            ("msg-dup-a", "att-a-001"): shared_content,
            ("msg-dup-b", "att-b-001"): shared_content,
        },
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    # Locators must be distinct
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        job_rows = await (await conn.execute(
            "SELECT payload->>'source_locator' FROM jobs "
            "WHERE payload->>'source_type' = 'gmail_attachment'"
        )).fetchall()

    locators = [r[0] for r in job_rows]
    assert len(locators) == 2
    assert locators[0] != locators[1]
    assert "msg-dup-a" in locators[0]
    assert "msg-dup-b" in locators[1]

    # Drain all enqueued jobs (2 body + 2 attachment)
    from cos.services.jobs import process_next_ingest_job

    for _ in range(4):
        await process_next_ingest_job(TEST_DSN, config)

    # One canonical blob, two attachment source rows
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        blob_count = await (await conn.execute(
            "SELECT COUNT(*) FROM content_blobs "
            "WHERE sha256 = encode(sha256(%s::bytea), 'hex')",
            (shared_content,),
        )).fetchone()
        source_count = await (await conn.execute(
            "SELECT COUNT(*) FROM sources WHERE source_type = 'gmail_attachment'"
        )).fetchone()

    assert blob_count == (1,)
    assert source_count == (2,)


# ── requeue prevention: body ──────────────────────────────────────────────────

async def test_second_sync_skips_unchanged_body_after_successful_processing(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Second poll with same body content skips re-enqueue after worker succeeds."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-skip-body-001", body="Hello from Gmail")

    # First sync: enqueue job
    with _patch_gmail(["msg-skip-body-001"], {"msg-skip-body-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await poll_gmail(config, conn)

    assert result1.body_jobs_enqueued == 1
    assert result1.artifacts_already_processed == 0

    # Worker processes the body job
    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync: same content — should skip
    with _patch_gmail(["msg-skip-body-001"], {"msg-skip-body-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await poll_gmail(config, conn)

    assert result2.body_jobs_enqueued == 0
    assert result2.artifacts_already_processed == 1
    assert result2.artifacts_already_queued == 0


async def test_second_sync_reenqueues_changed_body_content(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Second poll with changed body content re-enqueues work."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg_v1 = _plain_message("msg-changed-body-001", body="Body version one")
    msg_v2 = _plain_message("msg-changed-body-001", body="Body version two - updated")

    # First sync + worker
    with _patch_gmail(["msg-changed-body-001"], {"msg-changed-body-001": msg_v1}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync with changed body: should enqueue again
    with _patch_gmail(["msg-changed-body-001"], {"msg-changed-body-001": msg_v2}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.body_jobs_enqueued == 1
    assert result.artifacts_already_processed == 0


async def test_reverting_to_previous_body_content_reenqueues_against_latest_version(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """A -> B -> A should enqueue A again because B is the latest processed version."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg_v1 = _plain_message("msg-revert-body-001", body="Body version A")
    msg_v2 = _plain_message("msg-revert-body-001", body="Body version B")

    from cos.services.jobs import process_next_ingest_job

    with _patch_gmail(["msg-revert-body-001"], {"msg-revert-body-001": msg_v1}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)
    await process_next_ingest_job(TEST_DSN, config)

    with _patch_gmail(["msg-revert-body-001"], {"msg-revert-body-001": msg_v2}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)
    await process_next_ingest_job(TEST_DSN, config)

    with _patch_gmail(["msg-revert-body-001"], {"msg-revert-body-001": msg_v1}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.body_jobs_enqueued == 1
    assert result.artifacts_already_processed == 0


async def test_second_sync_with_pending_body_job_does_not_duplicate(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    """Second poll before worker runs does not add a duplicate queued body job."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-pending-body-001", body="Pending body content")

    # First sync: job queued, worker NOT run
    with _patch_gmail(["msg-pending-body-001"], {"msg-pending-body-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await poll_gmail(config, conn)

    assert result1.body_jobs_enqueued == 1

    # Second sync: same content, job still queued — should skip
    with _patch_gmail(["msg-pending-body-001"], {"msg-pending-body-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await poll_gmail(config, conn)

    assert result2.body_jobs_enqueued == 0
    assert result2.artifacts_already_queued == 1

    # Confirm only one queued job exists
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"
        )).fetchone()
    assert row == (1,)


# ── requeue prevention: attachment ───────────────────────────────────────────

async def test_second_sync_skips_unchanged_attachment_after_successful_processing(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Second poll with same attachment bytes skips re-enqueue after worker succeeds."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    att_bytes = b"Attachment text content for skip test"
    msg = _multipart_message_with_txt_attachment(
        "msg-skip-att-001", "notes.txt", att_bytes
    )

    # First sync + worker processes both body and attachment jobs
    with _patch_gmail(
        ["msg-skip-att-001"],
        {"msg-skip-att-001": msg},
        {("msg-skip-att-001", "att-id-001"): att_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await poll_gmail(config, conn)

    assert result1.body_jobs_enqueued == 1
    assert result1.attachment_jobs_enqueued == 1

    from cos.services.jobs import process_next_ingest_job
    # Process body and attachment jobs
    await process_next_ingest_job(TEST_DSN, config)
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync: same bytes — attachment should skip
    with _patch_gmail(
        ["msg-skip-att-001"],
        {"msg-skip-att-001": msg},
        {("msg-skip-att-001", "att-id-001"): att_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await poll_gmail(config, conn)

    assert result2.attachment_jobs_enqueued == 0
    assert result2.artifacts_already_processed >= 1  # at least the attachment


async def test_second_sync_reenqueues_changed_attachment_bytes(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Changed attachment bytes for same locator re-enqueue work."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    att_v1 = b"Attachment version one"
    att_v2 = b"Attachment version two - updated content"
    msg_v1 = _multipart_message_with_txt_attachment(
        "msg-changed-att-001", "notes.txt", att_v1
    )
    msg_v2 = _multipart_message_with_txt_attachment(
        "msg-changed-att-001", "notes.txt", att_v2
    )

    # First sync + worker
    with _patch_gmail(
        ["msg-changed-att-001"],
        {"msg-changed-att-001": msg_v1},
        {("msg-changed-att-001", "att-id-001"): att_v1},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync with changed bytes: should re-enqueue
    with _patch_gmail(
        ["msg-changed-att-001"],
        {"msg-changed-att-001": msg_v2},
        {("msg-changed-att-001", "att-id-001"): att_v2},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn)

    assert result.attachment_jobs_enqueued == 1
    # Body content is unchanged so it is skipped; only the attachment re-enqueues
    assert result.artifacts_already_processed == 1  # body skipped
    assert result.artifacts_already_queued == 0


async def test_new_attachment_on_existing_message_enqueues_as_new_source(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """A newly observed attachment on an existing message enqueues as a new source."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    att_bytes = b"New attachment bytes"

    # Sync 1: multipart message with no attachment parts (only body)
    msg_no_att = _multipart_message_no_attachment("msg-new-att-001")
    with _patch_gmail(["msg-new-att-001"], {"msg-new-att-001": msg_no_att}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await poll_gmail(config, conn)

    assert result1.body_jobs_enqueued == 1
    assert result1.attachment_jobs_enqueued == 0

    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)

    # Sync 2: same message structure but now has a new attachment
    msg_with_att = _multipart_message_with_txt_attachment(
        "msg-new-att-001", "new_file.txt", att_bytes, attachment_id="att-new-001"
    )
    with _patch_gmail(
        ["msg-new-att-001"],
        {"msg-new-att-001": msg_with_att},
        {("msg-new-att-001", "att-new-001"): att_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await poll_gmail(config, conn)

    assert result2.attachment_jobs_enqueued == 1
    assert result2.body_jobs_enqueued == 0  # body unchanged → skipped
    assert result2.artifacts_already_processed == 1  # body was already done


async def test_second_sync_with_pending_attachment_job_does_not_duplicate(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    """Second poll before worker runs does not add a duplicate queued attachment job."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    att_bytes = b"Pending attachment content"
    msg = _multipart_message_with_txt_attachment(
        "msg-pending-att-001", "notes.txt", att_bytes
    )

    # First sync: body + attachment queued, worker NOT run
    with _patch_gmail(
        ["msg-pending-att-001"],
        {"msg-pending-att-001": msg},
        {("msg-pending-att-001", "att-id-001"): att_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result1 = await poll_gmail(config, conn)

    assert result1.attachment_jobs_enqueued == 1

    # Second sync: same content, both jobs still queued — should skip
    with _patch_gmail(
        ["msg-pending-att-001"],
        {"msg-pending-att-001": msg},
        {("msg-pending-att-001", "att-id-001"): att_bytes},
    ):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result2 = await poll_gmail(config, conn)

    assert result2.attachment_jobs_enqueued == 0
    assert result2.artifacts_already_queued >= 1

    # Confirm job count has not grown: still just 2 queued (body + attachment)
    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        row = await (await conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"
        )).fetchone()
    assert row == (2,)


# ── requeue prevention: persistence ──────────────────────────────────────────

async def test_skip_decision_survives_fresh_db_connection(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Skip decision does not depend on process memory — survives a new connection."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-persist-001", body="Persistent body content")

    # First sync + worker (uses conn1)
    with _patch_gmail(["msg-persist-001"], {"msg-persist-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn1:
            await poll_gmail(config, conn1)

    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync uses a completely separate connection (conn2)
    with _patch_gmail(["msg-persist-001"], {"msg-persist-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn2:
            result = await poll_gmail(config, conn2)

    assert result.artifacts_already_processed == 1
    assert result.body_jobs_enqueued == 0


# ── force override ────────────────────────────────────────────────────────────

async def test_force_flag_bypasses_already_processed_skip(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """force=True re-enqueues artifacts even when they were already processed."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-force-001", body="Force reprocess content")

    # First sync + worker
    with _patch_gmail(["msg-force-001"], {"msg-force-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    from cos.services.jobs import process_next_ingest_job
    await process_next_ingest_job(TEST_DSN, config)

    # Second sync with force=True: should re-enqueue despite already processed
    with _patch_gmail(["msg-force-001"], {"msg-force-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn, force=True)

    assert result.body_jobs_enqueued == 1
    assert result.artifacts_already_processed == 0


async def test_force_flag_bypasses_pending_job_skip(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    """force=True re-enqueues even when there is already a queued job."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-force-pending-001", body="Force pending content")

    # First sync: job queued, worker NOT run
    with _patch_gmail(["msg-force-pending-001"], {"msg-force-pending-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    # Second sync with force=True: should enqueue again despite pending job
    with _patch_gmail(["msg-force-pending-001"], {"msg-force-pending-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn, force=True)

    assert result.body_jobs_enqueued == 1
    assert result.artifacts_already_queued == 0


async def test_force_reenqueue_uses_distinct_staged_paths(
    migrated_db: None,
    tmp_path: Path,
) -> None:
    """Forced re-enqueues keep separate staged snapshots for each queued job."""
    staging_dir = tmp_path / "staging"
    config = make_test_config(tmp_path)
    config = config.model_copy(
        update={
            "connectors": ["gmail"],
            "gmail": GmailConnectorConfig(staging_dir=staging_dir),
        }
    )

    msg = _plain_message("msg-force-stage-001", body="Body content")

    with _patch_gmail(["msg-force-stage-001"], {"msg-force-stage-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            await poll_gmail(config, conn)

    with _patch_gmail(["msg-force-stage-001"], {"msg-force-stage-001": msg}):
        async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
            result = await poll_gmail(config, conn, force=True)

    assert result.body_jobs_enqueued == 1

    async with await psycopg.AsyncConnection.connect(TEST_DSN) as conn:
        rows = await (
            await conn.execute(
                "SELECT payload->>'staged_path' FROM jobs "
                "WHERE payload->>'source_locator' = 'gmail://message/msg-force-stage-001/body' "
                "ORDER BY created_at ASC"
            )
        ).fetchall()

    staged_paths = [row[0] for row in rows]
    assert len(staged_paths) == 2
    assert staged_paths[0] != staged_paths[1]


# ── helper: txt attachment message ───────────────────────────────────────────

def _multipart_message_with_txt_attachment(
    message_id: str,
    att_filename: str,
    att_data: bytes,
    attachment_id: str = "att-id-001",
) -> dict[str, Any]:
    """Like _multipart_message_with_attachment but uses text/plain for no-Tika testing."""
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Subject", "value": "Message with txt attachment"},
                {"name": "From", "value": "bob@example.com"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64url(b"See attachment.")},
                },
                {
                    "mimeType": "text/plain",
                    "filename": att_filename,
                    "body": {"attachmentId": attachment_id},
                },
            ],
        },
    }


def _multipart_message_no_attachment(message_id: str) -> dict[str, Any]:
    """Multipart message structure with same headers/body as _multipart_message_with_txt_attachment but no attachment."""
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1746518400000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Subject", "value": "Message with txt attachment"},
                {"name": "From", "value": "bob@example.com"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": _b64url(b"See attachment.")},
                },
            ],
        },
    }
