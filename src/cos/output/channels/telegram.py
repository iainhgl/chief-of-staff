import json
import logging
from datetime import datetime, timezone

import httpx

from cos.config import TelegramConnectorConfig

logger = logging.getLogger(__name__)


class TelegramChannel:
    def __init__(
        self,
        config: TelegramConnectorConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client

    def _endpoint(self, method: str) -> str:
        token = self._config.bot_token.get_secret_value()
        return f"{self._config.api_base_url}/bot{token}/{method}"

    async def send(self, content: str) -> None:
        payload = {
            "chat_id": self._config.chat_id,
            "text": content,
        }
        try:
            if self._client is not None:
                resp = await self._client.post(
                    self._endpoint("sendMessage"), json=payload
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        self._endpoint("sendMessage"), json=payload
                    )
            if not resp.is_success:
                _log_delivery_failure(
                    f"Telegram sendMessage returned {resp.status_code}"
                )
        except Exception as exc:
            _log_delivery_failure(f"Telegram sendMessage error: {exc}")


def _log_delivery_failure(message: str) -> None:
    logger.error(
        json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "component": "output",
            "channel": "telegram",
            "message": message,
        })
    )
