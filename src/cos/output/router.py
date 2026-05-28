import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from cos.output.channels import local as local_channel

logger = logging.getLogger(__name__)

AsyncHandler = Callable[[str], Awaitable[None]]


async def _local_send(content: str) -> None:
    local_channel.send(content)


_BUILTIN_HANDLERS: dict[str, AsyncHandler] = {
    "local": _local_send,
}


class OutputRouter:
    def __init__(
        self,
        configured_channels: list[str],
        extra_handlers: dict[str, AsyncHandler] | None = None,
    ) -> None:
        self._channels = set(configured_channels)
        self._handlers: dict[str, AsyncHandler] = {
            **_BUILTIN_HANDLERS,
            **(extra_handlers or {}),
        }

    async def send(self, channel: str, content: str) -> None:
        if channel not in self._channels:
            logger.error(
                json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "output",
                    "message": f"unknown output channel: {channel!r}",
                    "channel": channel,
                })
            )
            return
        handler = self._handlers.get(channel)
        if handler is None:
            logger.error(
                json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "output",
                    "message": f"no handler registered for channel: {channel!r}",
                    "channel": channel,
                })
            )
            return
        try:
            await handler(content)
        except Exception as exc:
            logger.error(
                json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "component": "output",
                    "message": f"handler raised for channel {channel!r}: {exc}",
                    "channel": channel,
                })
            )
