import asyncio
import logging

import httpx
import pytest

from cos.config import TelegramConnectorConfig
from cos.connectors.telegram_bot import _handle_update, _poll_once, run_polling


async def _noop_sleep(_seconds: float) -> None:
    pass


def _make_tg_config(**overrides: object) -> TelegramConnectorConfig:
    defaults: dict[str, object] = {
        "bot_token": "test-bot-token",
        "chat_id": "111222333",
        "poll_timeout": 5,
    }
    defaults.update(overrides)
    return TelegramConnectorConfig(**defaults)  # type: ignore[arg-type]


def _updates_response(updates: list[dict]) -> dict:  # type: ignore[type-arg]
    return {"ok": True, "result": updates}


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return next(self._responses)


@pytest.mark.asyncio
async def test_poll_once_sends_getupdates_request() -> None:
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        await _poll_once(cfg, client, 0)

    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert "getUpdates" in str(req.url)


@pytest.mark.asyncio
async def test_poll_once_passes_allowed_updates_message() -> None:
    import json as _json

    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        await _poll_once(cfg, client, 0)

    req = transport.requests[0]
    body = _json.loads(req.content)
    assert "message" in body.get("allowed_updates", [])


@pytest.mark.asyncio
async def test_poll_once_advances_offset() -> None:
    updates = [{"update_id": 10, "message": {}}, {"update_id": 11, "message": {}}]
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response(updates)),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        new_offset, result = await _poll_once(cfg, client, 0)

    assert new_offset == 12
    assert len(result) == 2


@pytest.mark.asyncio
async def test_poll_once_does_not_regress_offset_with_no_updates() -> None:
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        new_offset, _ = await _poll_once(cfg, client, 42)

    assert new_offset == 42


@pytest.mark.asyncio
async def test_poll_once_raises_on_non_success_http_status() -> None:
    transport = _MockTransport([
        httpx.Response(500, json={"ok": False, "description": "server error"}),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RuntimeError, match="HTTP 500"):
            await _poll_once(cfg, client, 0)


@pytest.mark.asyncio
async def test_poll_once_raises_on_telegram_api_error() -> None:
    transport = _MockTransport([
        httpx.Response(
            200, json={"ok": False, "description": "Conflict: webhook active"}
        ),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RuntimeError, match="Telegram API error"):
            await _poll_once(cfg, client, 0)


def test_handle_update_ignores_unconfigured_chat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 1,
        "message": {"chat": {"id": 999999}, "text": "from stranger"},
    }
    with caplog.at_level(logging.WARNING):
        _handle_update(update, cfg)

    assert any("unconfigured chat" in r.message for r in caplog.records)


def test_handle_update_logs_inbound_for_configured_chat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 2,
        "message": {"chat": {"id": 111222333}, "text": "hello"},
    }
    with caplog.at_level(logging.INFO):
        _handle_update(update, cfg)

    assert any("inbound message received" in r.message for r in caplog.records)


def test_handle_update_does_not_log_message_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 3,
        "message": {"chat": {"id": 111222333}, "text": "private-content-xyz"},
    }
    with caplog.at_level(logging.DEBUG):
        _handle_update(update, cfg)

    for record in caplog.records:
        assert "private-content-xyz" not in record.message


@pytest.mark.asyncio
async def test_run_polling_retries_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Polling loop retries after transient errors and exits after second call."""
    calls = [0]
    cfg = _make_tg_config()

    monkeypatch.setattr("cos.connectors.telegram_bot.asyncio.sleep", _noop_sleep)

    async def _fake_poll_once(
        _cfg: TelegramConnectorConfig,
        _client: httpx.AsyncClient,
        offset: int,
    ) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("transient error")
        raise asyncio.CancelledError()

    import cos.connectors.telegram_bot as tg_mod

    original = tg_mod._poll_once
    tg_mod._poll_once = _fake_poll_once  # type: ignore[assignment]
    try:
        with pytest.raises(asyncio.CancelledError):
            await run_polling(cfg)
    finally:
        tg_mod._poll_once = original  # type: ignore[assignment]

    assert calls[0] == 2


@pytest.mark.asyncio
async def test_run_polling_logs_webhook_conflict_as_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config()
    call_count = [0]

    monkeypatch.setattr("cos.connectors.telegram_bot.asyncio.sleep", _noop_sleep)

    async def _fake_poll_once(
        _cfg: TelegramConnectorConfig,
        _client: httpx.AsyncClient,
        offset: int,
    ) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Conflict: webhook active")
        raise asyncio.CancelledError()

    import cos.connectors.telegram_bot as tg_mod

    original = tg_mod._poll_once
    tg_mod._poll_once = _fake_poll_once  # type: ignore[assignment]
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
            await run_polling(cfg)
    finally:
        tg_mod._poll_once = original  # type: ignore[assignment]

    assert any("webhook conflict" in r.message for r in caplog.records)


def test_handle_update_skips_update_with_no_message() -> None:
    cfg = _make_tg_config()
    # No exception should be raised
    _handle_update({"update_id": 99}, cfg)
