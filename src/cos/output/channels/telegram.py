import json
import logging
from datetime import datetime, timezone

import httpx

from cos.config import TelegramConnectorConfig

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


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

    def _redact(self, value: object) -> str:
        token = self._config.bot_token.get_secret_value()
        return str(value).replace(token, "<redacted>")

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
                _log_delivery_failure(self._failure_message(resp))
                return
            data = resp.json()
            if data.get("ok") is False:
                _log_delivery_failure(
                    "Telegram sendMessage API error: "
                    f"{self._redact(data.get('description', 'unknown error'))}"
                )
        except Exception as exc:
            _log_delivery_failure(
                f"Telegram sendMessage error: {self._redact(exc)}"
            )

    def _failure_message(self, resp: httpx.Response) -> str:
        try:
            data = resp.json()
            description = data.get("description") if isinstance(data, dict) else None
        except ValueError:
            description = None
        message = f"Telegram sendMessage returned {resp.status_code}"
        if description:
            message = f"{message}: {self._redact(description)}"
        return message


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
