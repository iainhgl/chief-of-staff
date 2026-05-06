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

    staged = staging_dir / "msg-003_body.md"
    assert staged.exists()
    assert "Important content" in staged.read_text()


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
