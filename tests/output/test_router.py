import logging

import pytest

from cos.output.router import OutputRouter


@pytest.mark.asyncio
async def test_send_valid_channel_delivers_output(capsys: pytest.CaptureFixture) -> None:
    router = OutputRouter(configured_channels=["local"])
    await router.send("local", "hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out


@pytest.mark.asyncio
async def test_send_invalid_channel_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    with caplog.at_level(logging.ERROR):
        await router.send("telegram", "should be suppressed")
    # Must not raise — if we got here, the test passes


@pytest.mark.asyncio
async def test_send_invalid_channel_logs_json_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    with caplog.at_level(logging.ERROR):
        await router.send("unknown_channel", "content")
    assert any("unknown_channel" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_send_invalid_channel_suppresses_output(
    capsys: pytest.CaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    await router.send("telegram", "should not appear")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.out


@pytest.mark.asyncio
async def test_send_configured_channel_with_no_handler_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # "email" is configured but has no handler (no extra_handlers provided)
    router = OutputRouter(configured_channels=["email"])
    with caplog.at_level(logging.ERROR):
        await router.send("email", "content")
    assert any("no handler registered" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_send_with_extra_handler_delivers(capsys: pytest.CaptureFixture) -> None:
    delivered: list[str] = []

    async def mock_handler(content: str) -> None:
        delivered.append(content)

    router = OutputRouter(
        configured_channels=["custom"],
        extra_handlers={"custom": mock_handler},
    )
    await router.send("custom", "via custom")
    assert delivered == ["via custom"]


@pytest.mark.asyncio
async def test_send_handler_exception_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing_handler(content: str) -> None:
        raise RuntimeError("simulated failure")

    router = OutputRouter(
        configured_channels=["bad"],
        extra_handlers={"bad": failing_handler},
    )
    with caplog.at_level(logging.ERROR):
        await router.send("bad", "content")
    assert any("handler raised" in record.message for record in caplog.records)
