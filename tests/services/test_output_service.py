import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from cos.output.router import OutputRouter
from cos.services.output import OutputService


@pytest.fixture(autouse=True)
def clean_tables() -> None:
    """Override package-level DB cleanup for this unit-only module."""


@pytest.mark.asyncio
async def test_output_service_send_valid_channel_delegates_to_router(
    capsys: pytest.CaptureFixture[str],
) -> None:
    router = OutputRouter(configured_channels=["local"])
    service = OutputService(router=router)

    await service.send("local", "hello world")

    assert "hello world" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_output_service_send_invalid_channel_suppresses(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = OutputRouter(configured_channels=["local"])
    service = OutputService(router=router)

    with caplog.at_level(logging.ERROR):
        await service.send("unknown", "should be suppressed")

    assert "should be suppressed" not in capsys.readouterr().out
    assert any("unknown output channel" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_output_service_delegates_to_router_send() -> None:
    router = MagicMock()
    router.send = AsyncMock()
    service = OutputService(router=router)

    await service.send("local", "test content")

    router.send.assert_awaited_once_with("local", "test content")
