import json
import logging

import httpx
import pytest

from cos.config import TelegramConnectorConfig
from cos.output.channels.telegram import TelegramChannel


def _make_tg_config(**overrides: object) -> TelegramConnectorConfig:
    defaults: dict[str, object] = {
        "bot_token": "test-bot-token",
        "chat_id": "123456789",
    }
    defaults.update(overrides)
    return TelegramConnectorConfig(**defaults)  # type: ignore[arg-type]


class _SuccessTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})


class _FailureTransport(httpx.AsyncBaseTransport):
    def __init__(self, status_code: int = 400) -> None:
        self.status_code = status_code

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            self.status_code, json={"ok": False, "description": "bad"}
        )


class _NetworkErrorTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")


@pytest.mark.asyncio
async def test_telegram_send_posts_to_sendmessage() -> None:
    transport = _SuccessTransport()
    client = httpx.AsyncClient(transport=transport)
    cfg = _make_tg_config()
    channel = TelegramChannel(config=cfg, client=client)

    await channel.send("hello telegram")

    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert "sendMessage" in str(req.url)
    body = json.loads(req.content)
    assert body["chat_id"] == "123456789"
    assert body["text"] == "hello telegram"


@pytest.mark.asyncio
async def test_telegram_send_does_not_include_token_in_our_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = _SuccessTransport()
    client = httpx.AsyncClient(transport=transport)
    cfg = _make_tg_config(bot_token="super-secret-bot-token")
    channel = TelegramChannel(config=cfg, client=client)

    with caplog.at_level(logging.DEBUG, logger="cos"):
        await channel.send("test")

    # Only check our own application logs — httpx logs its own URL internally
    our_records = [r for r in caplog.records if r.name.startswith("cos")]
    for record in our_records:
        assert "super-secret-bot-token" not in record.message


@pytest.mark.asyncio
async def test_telegram_send_failure_suppresses_and_logs_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = _FailureTransport(status_code=400)
    client = httpx.AsyncClient(transport=transport)
    cfg = _make_tg_config()
    channel = TelegramChannel(config=cfg, client=client)

    with caplog.at_level(logging.ERROR):
        await channel.send("will fail")

    assert any(
        "component" in r.message and "output" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_telegram_send_network_error_suppresses_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = _NetworkErrorTransport()
    client = httpx.AsyncClient(transport=transport)
    cfg = _make_tg_config()
    channel = TelegramChannel(config=cfg, client=client)

    with caplog.at_level(logging.ERROR):
        await channel.send("network error")

    assert any(
        "component" in r.message and "output" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_telegram_send_logs_component_output_on_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = _FailureTransport(status_code=500)
    client = httpx.AsyncClient(transport=transport)
    cfg = _make_tg_config()
    channel = TelegramChannel(config=cfg, client=client)

    with caplog.at_level(logging.ERROR):
        await channel.send("server error")

    error_logs = [r for r in caplog.records if "component" in r.message]
    assert len(error_logs) >= 1
    parsed = json.loads(error_logs[0].message)
    assert parsed["component"] == "output"
    assert parsed["channel"] == "telegram"
