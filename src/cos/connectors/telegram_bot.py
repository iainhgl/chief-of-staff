import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from cos.config import CosConfig, TelegramConnectorConfig

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def _log(level: str, message: str, **extra: object) -> None:
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(
        json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "component": "connector",
            "connector": "telegram",
            "message": message,
            **extra,
        })
    )


def _api_url(cfg: TelegramConnectorConfig, method: str) -> str:
    token = cfg.bot_token.get_secret_value()
    return f"{cfg.api_base_url}/bot{token}/{method}"


def _redact_token(cfg: TelegramConnectorConfig, value: object) -> str:
    return str(value).replace(cfg.bot_token.get_secret_value(), "<redacted>")


def _telegram_response_description(resp: httpx.Response) -> str | None:
    try:
        data = resp.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    description = data.get("description")
    return str(description) if description else None


async def _poll_once(
    cfg: TelegramConnectorConfig,
    client: httpx.AsyncClient,
    offset: int,
) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
    payload: dict[str, object] = {
        "timeout": cfg.poll_timeout,
        "allowed_updates": ["message"],
        "offset": offset,
    }
    resp = await client.post(
        _api_url(cfg, "getUpdates"),
        json=payload,
        timeout=cfg.poll_timeout + 10.0,
    )
    if not resp.is_success:
        desc = _telegram_response_description(resp)
        message = f"getUpdates returned HTTP {resp.status_code}"
        if desc:
            message = f"{message}: {_redact_token(cfg, desc)}"
        raise RuntimeError(message)
    data = resp.json()
    if not data.get("ok"):
        desc = data.get("description", "unknown error")
        raise RuntimeError(f"Telegram API error: {_redact_token(cfg, desc)}")
    updates: list[dict] = data.get("result", [])  # type: ignore[type-arg]
    new_offset = offset
    for update in updates:
        uid = update.get("update_id", 0)
        if uid >= new_offset:
            new_offset = uid + 1
    return new_offset, updates


def _handle_update(update: dict, cfg: TelegramConnectorConfig) -> None:  # type: ignore[type-arg]
    msg = update.get("message")
    if msg is None:
        return
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if chat_id != cfg.chat_id:
        _log(
            "warning",
            "received message from unconfigured chat — ignored",
            update_id=update.get("update_id"),
        )
        return
    text_len = len(msg.get("text", ""))
    _log(
        "info",
        "inbound message received",
        update_id=update.get("update_id"),
        text_length=text_len,
    )


async def run_polling(cfg: TelegramConnectorConfig) -> None:
    _log("info", "Telegram polling started", chat_id=cfg.chat_id)
    offset = 0
    backoff = cfg.backoff_initial

    async with httpx.AsyncClient() as client:
        while True:
            try:
                offset, updates = await _poll_once(cfg, client, offset)
                backoff = cfg.backoff_initial
                for update in updates:
                    _handle_update(update, cfg)
            except Exception as exc:
                msg = str(exc)
                if "webhook" in msg.lower() or "conflict" in msg.lower():
                    _log(
                        "error",
                        "webhook conflict detected — polling cannot proceed",
                        error=_redact_token(cfg, msg),
                    )
                else:
                    _log(
                        "warning",
                        "polling error — retrying after backoff",
                        error=_redact_token(cfg, msg),
                        backoff=backoff,
                    )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, cfg.backoff_max)


def run() -> None:
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    config = CosConfig.load()

    if "telegram" not in config.connectors or config.telegram is None:
        _log("info", "Telegram connector not configured — exiting")
        return

    asyncio.run(run_polling(config.telegram))
