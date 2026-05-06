"""Tests for Gmail API connector: message parsing, MIME traversal, backoff."""
import base64
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from cos.config import GmailConnectorConfig
from cos.connectors.gmail import (
    _decode_b64url,
    _execute_with_retry,
    extract_body_text,
    fetch_attachment_bytes,
    get_message_header,
    list_message_ids,
    walk_mime_parts,
)


def _b64url(text: str | bytes) -> str:
    raw = text.encode() if isinstance(text, str) else text
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _http_error(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b"error")


# ── list_message_ids ──────────────────────────────────────────────────────────

def _set_list_response(service: MagicMock, response: dict) -> None:
    (service.users.return_value.messages.return_value
     .list.return_value.execute.return_value) = response


def test_list_message_ids_returns_ids() -> None:
    service = MagicMock()
    _set_list_response(service, {"messages": [{"id": "abc"}, {"id": "def"}]})
    result = list_message_ids(service, GmailConnectorConfig(max_results=10))
    assert result == ["abc", "def"]


def test_list_message_ids_empty_inbox() -> None:
    service = MagicMock()
    _set_list_response(service, {})
    assert list_message_ids(service, GmailConnectorConfig()) == []


def test_list_message_ids_passes_query_and_labels() -> None:
    service = MagicMock()
    _set_list_response(service, {"messages": []})
    cfg = GmailConnectorConfig(query="is:unread", label_ids=["INBOX"])
    list_message_ids(service, cfg)
    service.users.return_value.messages.return_value.list.assert_called_with(
        userId="me",
        maxResults=25,
        includeSpamTrash=False,
        q="is:unread",
        labelIds=["INBOX"],
    )


def test_list_message_ids_omits_query_when_none() -> None:
    service = MagicMock()
    _set_list_response(service, {"messages": []})
    list_message_ids(service, GmailConnectorConfig())
    call_kwargs = service.users.return_value.messages.return_value.list.call_args.kwargs
    assert "q" not in call_kwargs
    assert "labelIds" not in call_kwargs


# ── walk_mime_parts ───────────────────────────────────────────────────────────

def test_walk_mime_parts_flat_plain_text() -> None:
    payload = {"mimeType": "text/plain", "body": {"data": _b64url("hello")}}
    parts = walk_mime_parts(payload)
    assert len(parts) == 1
    assert parts[0]["mimeType"] == "text/plain"


def test_walk_mime_parts_multipart_returns_all_leaves() -> None:
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64url("hello")}},
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": _b64url("alt")}},
                    {"mimeType": "text/html", "body": {"data": _b64url("<b>hi</b>")}},
                ],
            },
            {
                "mimeType": "application/pdf",
                "filename": "report.pdf",
                "body": {"attachmentId": "att-xyz"},
            },
        ],
    }
    parts = walk_mime_parts(payload)
    assert len(parts) == 4
    mime_types = [p["mimeType"] for p in parts]
    assert mime_types.count("text/plain") == 2
    assert "text/html" in mime_types
    assert "application/pdf" in mime_types


def test_walk_mime_parts_deeply_nested() -> None:
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/related",
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": _b64url("deep")},
                            },
                        ],
                    }
                ],
            }
        ],
    }
    parts = walk_mime_parts(payload)
    assert len(parts) == 1
    assert parts[0]["mimeType"] == "text/plain"


# ── extract_body_text ─────────────────────────────────────────────────────────

def test_extract_body_text_plain_message() -> None:
    message = {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": _b64url("Hello, world!")},
        }
    }
    assert extract_body_text(message) == "Hello, world!"


def test_extract_body_text_multipart_prefers_plain() -> None:
    message = {
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64url("plain body")}},
                {"mimeType": "text/html", "body": {"data": _b64url("<b>html</b>")}},
            ],
        }
    }
    assert extract_body_text(message) == "plain body"


def test_extract_body_text_falls_back_to_html() -> None:
    message = {
        "payload": {
            "mimeType": "text/html",
            "body": {"data": _b64url("<b>html only</b>")},
        }
    }
    assert extract_body_text(message) == "<b>html only</b>"


def test_extract_body_text_returns_empty_when_no_body() -> None:
    message = {"payload": {"mimeType": "multipart/mixed", "parts": []}}
    assert extract_body_text(message) == ""


# ── base64url decoding ────────────────────────────────────────────────────────

def test_decode_b64url_no_padding() -> None:
    original = b"hello world"
    encoded = base64.urlsafe_b64encode(original).rstrip(b"=").decode()
    assert _decode_b64url(encoded) == original


def test_decode_b64url_with_padding() -> None:
    original = b"test"
    encoded = base64.urlsafe_b64encode(original).decode()
    assert _decode_b64url(encoded) == original


def test_decode_b64url_binary_content() -> None:
    content = bytes(range(256))
    encoded = base64.urlsafe_b64encode(content).rstrip(b"=").decode()
    assert _decode_b64url(encoded) == content


# ── retry / backoff ───────────────────────────────────────────────────────────

def test_execute_with_retry_succeeds_on_first_try() -> None:
    request = MagicMock()
    request.execute.return_value = {"ok": True}
    assert _execute_with_retry(request) == {"ok": True}
    request.execute.assert_called_once()


def test_execute_with_retry_retries_on_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cos.connectors.gmail.time.sleep", lambda s: None)
    call_count = 0

    class _FakeRequest:
        def execute(self) -> dict[str, object]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise _http_error(429)
            return {"messages": []}

    result = _execute_with_retry(_FakeRequest())
    assert result == {"messages": []}
    assert call_count == 3


def test_execute_with_retry_raises_on_non_transient_error() -> None:
    request = MagicMock()
    request.execute.side_effect = _http_error(404)
    with pytest.raises(HttpError):
        _execute_with_retry(request)


def test_execute_with_retry_exhausts_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cos.connectors.gmail.time.sleep", lambda s: None)
    request = MagicMock()
    request.execute.side_effect = _http_error(503)
    with pytest.raises(HttpError):
        _execute_with_retry(request)
    assert request.execute.call_count == 5


# ── fetch_attachment_bytes ────────────────────────────────────────────────────

def test_fetch_attachment_bytes_decodes_correctly() -> None:
    content = b"PDF content bytes"
    encoded = base64.urlsafe_b64encode(content).decode()
    service = MagicMock()
    att_mock = service.users.return_value.messages.return_value.attachments
    att_mock.return_value.get.return_value.execute.return_value = {"data": encoded}
    result = fetch_attachment_bytes(service, "msg-1", "att-1")
    assert result == content


# ── get_message_header ────────────────────────────────────────────────────────

def test_get_message_header_returns_value() -> None:
    message = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Q3 Budget"},
                {"name": "From", "value": "alice@example.com"},
            ]
        }
    }
    assert get_message_header(message, "subject") == "Q3 Budget"
    assert get_message_header(message, "from") == "alice@example.com"


def test_get_message_header_case_insensitive() -> None:
    message = {"payload": {"headers": [{"name": "SUBJECT", "value": "Test"}]}}
    assert get_message_header(message, "subject") == "Test"


def test_get_message_header_missing_returns_empty() -> None:
    message = {"payload": {"headers": []}}
    assert get_message_header(message, "subject") == ""
