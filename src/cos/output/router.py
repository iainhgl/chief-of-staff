import json
import logging
from datetime import datetime, timezone
from typing import Callable

from cos.output.channels import local as local_channel

logger = logging.getLogger(__name__)

_CHANNEL_HANDLERS: dict[str, Callable[[str], None]] = {
    "local": local_channel.send,
}


class OutputRouter:
    def __init__(self, configured_channels: list[str]) -> None:
        self._channels = set(configured_channels)

    def send(self, channel: str, content: str) -> None:
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
        handler = _CHANNEL_HANDLERS.get(channel)
        if handler is None:
            # Channel is configured but handler not yet implemented (Phase 2+)
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
            handler(content)
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
