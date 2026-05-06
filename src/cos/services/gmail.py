"""Gmail connector service — staging, deduplication, and job enqueue orchestration."""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig, GmailConnectorConfig
from cos.connectors.gmail import (
    _decode_b64url,
    build_gmail_service,
    extract_body_text,
    fetch_attachment_bytes,
    fetch_message,
    get_message_header,
    list_message_ids,
    walk_mime_parts,
)
from cos.services.ingestion import SUPPORTED_SUFFIXES
from cos.services.jobs import submit_ingest_job

_CONNECTOR = "gmail"


@dataclass
class GmailPollResult:
    messages_scanned: int
    body_jobs_enqueued: int
    attachment_jobs_enqueued: int
    attachments_skipped: int


async def poll_gmail(
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> GmailPollResult:
    """Poll Gmail for new messages, stage artifacts, and enqueue ingest jobs."""
    gmail_config = config.gmail or GmailConnectorConfig()
    staging_dir = gmail_config.staging_dir
    staging_dir.mkdir(parents=True, exist_ok=True)

    service = build_gmail_service(config)
    message_ids = list_message_ids(service, gmail_config)

    body_jobs = 0
    attachment_jobs = 0
    attachments_skipped = 0

    for message_id in message_ids:
        try:
            message = fetch_message(service, message_id)
        except Exception as exc:
            _log_connector_error(f"failed to fetch message {message_id}: {exc}")
            continue

        subject = get_message_header(message, "subject")
        from_addr = get_message_header(message, "from")
        thread_id = str(message.get("threadId", ""))
        internal_date = str(message.get("internalDate", ""))

        base_metadata: dict[str, Any] = {
            "connector": _CONNECTOR,
            "message_id": message_id,
            "thread_id": thread_id,
            "subject": subject,
            "from": from_addr,
            "internal_date": internal_date,
        }

        # Stage message body
        body_text = extract_body_text(message)
        body_content = _format_body_md(from_addr, subject, internal_date, body_text)
        body_staged = staging_dir / f"{message_id}_body.md"
        body_staged.write_text(body_content, encoding="utf-8")

        await submit_ingest_job(
            conn,
            staged_path=str(body_staged),
            source_type="gmail_message_body",
            source_locator=f"gmail://message/{message_id}/body",
            source_alias=_body_alias(subject, message_id),
            metadata={**base_metadata},
        )
        body_jobs += 1

        # Stage supported attachments
        payload = message.get("payload", {})
        for part in walk_mime_parts(payload):
            filename = part.get("filename", "")
            if not filename:
                continue

            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_SUFFIXES:
                _log_connector_info(
                    f"skipping unsupported attachment {filename!r} "
                    f"(mime_type={part.get('mimeType', 'unknown')}) "
                    f"in message {message_id}"
                )
                attachments_skipped += 1
                continue

            body_info = part.get("body", {})
            attachment_id = body_info.get("attachmentId")
            inline_data = body_info.get("data", "")

            try:
                if attachment_id:
                    att_bytes = fetch_attachment_bytes(
                        service, message_id, attachment_id
                    )
                elif inline_data:
                    att_bytes = _decode_b64url(inline_data)
                else:
                    _log_connector_info(
                        f"attachment {filename!r} has no data — skipping"
                    )
                    attachments_skipped += 1
                    continue
            except Exception as exc:
                _log_connector_error(
                    f"failed to fetch attachment {filename!r} "
                    f"in message {message_id}: {exc}"
                )
                attachments_skipped += 1
                continue

            att_id_slug = attachment_id or "inline"
            staged_name = f"{message_id}_{att_id_slug}{suffix}"
            att_staged = staging_dir / staged_name
            att_staged.write_bytes(att_bytes)

            locator = (
                f"gmail://message/{message_id}/attachment/{att_id_slug}"
                if attachment_id
                else f"gmail://message/{message_id}/body/{filename}"
            )

            await submit_ingest_job(
                conn,
                staged_path=str(att_staged),
                source_type="gmail_attachment",
                source_locator=locator,
                source_alias=filename,
                metadata={**base_metadata, "mime_type": part.get("mimeType", "")},
            )
            attachment_jobs += 1

    return GmailPollResult(
        messages_scanned=len(message_ids),
        body_jobs_enqueued=body_jobs,
        attachment_jobs_enqueued=attachment_jobs,
        attachments_skipped=attachments_skipped,
    )


def _format_body_md(
    from_addr: str,
    subject: str,
    internal_date: str,
    body_text: str,
) -> str:
    header_lines = []
    if from_addr:
        header_lines.append(f"From: {from_addr}")
    if subject:
        header_lines.append(f"Subject: {subject}")
    if internal_date:
        try:
            ts = int(internal_date) / 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            header_lines.append(f"Date: {dt}")
        except (ValueError, OSError):
            pass

    if header_lines:
        return "\n".join(header_lines) + "\n\n---\n\n" + body_text
    return body_text


def _body_alias(subject: str, message_id: str) -> str:
    if not subject:
        return f"{message_id}.md"
    clean = re.sub(r"[^\w\s\-]", "", subject)
    clean = re.sub(r"\s+", "_", clean.strip())[:80]
    return f"{clean}.md" if clean else f"{message_id}.md"


def _log_connector_info(message: str) -> None:
    logging.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "component": "connector",
                "connector": _CONNECTOR,
                "message": message,
            }
        )
    )


def _log_connector_error(message: str) -> None:
    logging.error(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "component": "connector",
                "connector": _CONNECTOR,
                "message": message,
            }
        )
    )
