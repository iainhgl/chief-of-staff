"""Gmail API connector — discovery, MIME parsing, and attachment handling."""
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build as _google_build
from googleapiclient.errors import HttpError

from cos.config import CosConfig, GmailConnectorConfig
from cos.connectors.google_auth import load_credentials

_TRANSIENT_HTTP_CODES = frozenset({429, 500, 502, 503, 504})
_RETRYABLE_403_REASONS = frozenset(
    {"ratelimitexceeded", "userratelimitexceeded", "quotaexceeded", "backenderror"}
)
_MAX_RETRIES = 5
_INITIAL_BACKOFF = 1.0


def get_gmail_credentials(config: CosConfig) -> Any:
    """Return valid Gmail credentials, refreshing locally when possible."""
    return load_credentials("gmail", config.google_oauth)


def build_gmail_service(config: CosConfig) -> Any:
    """Build an authenticated Gmail API service resource."""
    creds = get_gmail_credentials(config)
    return _google_build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_message_ids(service: Any, gmail_config: GmailConnectorConfig) -> list[str]:
    """Return message IDs matching the configured query/label filters."""
    params: dict[str, Any] = {
        "userId": "me",
        "maxResults": gmail_config.max_results,
        "includeSpamTrash": gmail_config.include_spam_trash,
    }
    if gmail_config.query:
        params["q"] = gmail_config.query
    if gmail_config.label_ids:
        params["labelIds"] = gmail_config.label_ids

    response = _execute_with_retry(service.users().messages().list(**params))
    return [m["id"] for m in response.get("messages", [])]


def fetch_message(service: Any, message_id: str) -> dict[str, Any]:
    """Fetch the full message payload for a given message ID."""
    return _execute_with_retry(
        service.users().messages().get(userId="me", id=message_id, format="FULL")
    )


def fetch_attachment_bytes(
    service: Any, message_id: str, attachment_id: str
) -> bytes:
    """Fetch and base64url-decode a detached attachment."""
    response = _execute_with_retry(
        service.users().messages().attachments().get(
            userId="me", messageId=message_id, id=attachment_id
        )
    )
    return _decode_b64url(response.get("data", ""))


def walk_mime_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Recursively walk a message payload, returning all leaf MIME parts."""
    sub_parts = payload.get("parts")
    if sub_parts:
        result: list[dict[str, Any]] = []
        for part in sub_parts:
            result.extend(walk_mime_parts(part))
        return result
    return [payload]


def extract_body_text(message: dict[str, Any]) -> str:
    """Extract plain-text body from a Gmail message, falling back to HTML."""
    payload = message.get("payload", {})
    all_parts = walk_mime_parts(payload)

    for preferred in ("text/plain", "text/html"):
        part = next(
            (
                p
                for p in all_parts
                if p.get("mimeType") == preferred and not _is_attachment_part(p)
            ),
            None,
        )
        if part:
            data = part.get("body", {}).get("data", "")
            if data:
                return _decode_b64url(data).decode("utf-8", errors="replace")

    return ""


def get_message_header(message: dict[str, Any], name: str) -> str:
    """Return the value of the named header from a Gmail message, or empty string."""
    return _get_header_value(message.get("payload", {}).get("headers", []), name)


def _decode_b64url(data: str) -> bytes:
    """Decode a base64url string, adding padding as required."""
    pad = (4 - len(data) % 4) % 4
    return base64.urlsafe_b64decode(data + "=" * pad)


def _execute_with_retry(request: Any) -> dict[str, Any]:
    """Execute a Gmail API request with exponential backoff on transient errors."""
    delay = _INITIAL_BACKOFF
    last_exc: HttpError | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            result: dict[str, Any] = request.execute()
            return result
        except HttpError as exc:
            if not _is_retryable_http_error(exc):
                raise
            last_exc = exc
            _log_connector_warning(
                f"retryable HTTP {exc.resp.status} "
                f"on attempt {attempt + 1}/{_MAX_RETRIES}"
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    raise last_exc  # type: ignore[misc]


def _is_attachment_part(part: dict[str, Any]) -> bool:
    if part.get("filename"):
        return True

    body = part.get("body", {})
    if isinstance(body, dict) and body.get("attachmentId"):
        return True

    disposition = _get_header_value(part.get("headers", []), "Content-Disposition")
    lowered = disposition.lower()
    return "attachment" in lowered or "inline" in lowered


def _get_header_value(headers: Any, name: str) -> str:
    if not isinstance(headers, list):
        return ""
    for header in headers:
        if not isinstance(header, dict):
            continue
        if str(header.get("name", "")).lower() == name.lower():
            return str(header.get("value", ""))
    return ""


def _is_retryable_http_error(exc: HttpError) -> bool:
    if exc.resp.status in _TRANSIENT_HTTP_CODES:
        return True
    if exc.resp.status != 403:
        return False

    try:
        payload = json.loads(exc.content.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    candidates: list[str] = []
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "status"):
            value = error.get(key)
            if isinstance(value, str):
                candidates.append(value.lower())
        errors = error.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if not isinstance(item, dict):
                    continue
                reason = item.get("reason")
                if isinstance(reason, str):
                    candidates.append(reason.lower())

    candidate_text = " ".join(candidates)
    return bool(
        set(candidates) & _RETRYABLE_403_REASONS
        or "rate limit" in candidate_text
        or "quota" in candidate_text
    )


def _log_connector_warning(message: str) -> None:
    logging.warning(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "WARNING",
                "component": "connector",
                "connector": "gmail",
                "message": message,
            }
        )
    )
