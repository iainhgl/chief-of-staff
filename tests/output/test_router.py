import logging

import pytest

from cos.output.router import OutputRouter


def test_send_valid_channel_delivers_output(capsys: pytest.CaptureFixture) -> None:
    router = OutputRouter(configured_channels=["local"])
    router.send("local", "hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_send_invalid_channel_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    router = OutputRouter(configured_channels=["local"])
    with caplog.at_level(logging.ERROR):
        router.send("telegram", "should be suppressed")
    # Must not raise — if we got here, the test passes


def test_send_invalid_channel_logs_json_error(caplog: pytest.LogCaptureFixture) -> None:
    router = OutputRouter(configured_channels=["local"])
    with caplog.at_level(logging.ERROR):
        router.send("unknown_channel", "content")
    assert any("unknown_channel" in record.message for record in caplog.records)


def test_send_invalid_channel_suppresses_output(capsys: pytest.CaptureFixture) -> None:
    router = OutputRouter(configured_channels=["local"])
    router.send("telegram", "should not appear")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.out


def test_send_configured_channel_with_no_handler_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # "email" is configured but has no entry in _CHANNEL_HANDLERS (Phase 2+ channel)
    router = OutputRouter(configured_channels=["email"])
    with caplog.at_level(logging.ERROR):
        router.send("email", "content")
    assert any("no handler registered" in record.message for record in caplog.records)
