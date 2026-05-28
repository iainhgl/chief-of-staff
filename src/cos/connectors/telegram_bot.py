import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from cos.config import CosConfig, TelegramConnectorConfig
from cos.retrieval.citations import CitedChunk, CitedResponse

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

_TELEGRAM_MAX_CHARS = 4096
_RETRIEVAL_TIMEOUT_SECONDS = 60.0
_MAX_SOURCE_LABEL_CHARS = 80
_NO_CONTENT_ANSWER = "No relevant content found in the knowledge base."
_NO_CONTENT_REPLY = "No relevant content was found for your question."
_RECOVERY_REPLY = "I could not answer that just now. Check `cos logs` for diagnostics."
_EMPTY_ANSWER_REPLY = "I could not produce an answer from the retrieved content."

# Question heuristics for the inbound message classifier.
# Note capture (note: prefix, declarative statements) is out of scope — Story 8.3.
_QUESTION_WORDS = frozenset({"what", "why", "how", "when", "where", "who", "which"})
_QUESTION_PHRASES = (
    "tell me",
    "show me",
    "find ",
    "look up",
    "summarise",
    "summarize",
    "compare",
    "brief me",
    "draft",
)
_ASK_COMMAND_RE = re.compile(r"^/ask(?:@[a-zA-Z0-9_]+)?(?:\s+|$)")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")

_UNSUPPORTED_REPLY = (
    "Send a question to get a cited answer from the knowledge base. "
    "Note capture is not yet enabled."
)


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


def _log_ids(update_id: object, message_id: object | None = None) -> dict[str, object]:
    fields = {"update_id": update_id}
    if message_id is not None:
        fields["message_id"] = message_id
    return fields


def _starts_with_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.strip()
    return text == phrase or text.startswith(f"{phrase} ")


def _classify_inbound_text(text: str) -> Literal["question", "unsupported"]:
    """Classify inbound Telegram text as 'question' or 'unsupported'.

    Question heuristics (checked in order):
    - Ends with '?'
    - Starts with '/ask' slash command
    - First word is a question word (what, why, how, when, where, who, which)
    - Starts with a KB-request phrase (tell me, show me, find, look up, ...)

    Note capture (note: prefix, declarative sentences) is out of scope — Story 8.3.
    """
    stripped = text.strip()
    if not stripped:
        return "unsupported"
    lower = stripped.lower()

    if stripped.endswith("?"):
        return "question"

    if _ASK_COMMAND_RE.match(stripped):
        return "question"

    first_word = lower.split()[0]
    if first_word in _QUESTION_WORDS:
        return "question"

    for phrase in _QUESTION_PHRASES:
        if _starts_with_phrase(lower, phrase):
            return "question"

    return "unsupported"


def _normalise_question_text(text: str) -> str:
    stripped = text.strip()
    match = _ASK_COMMAND_RE.match(stripped)
    if match is not None:
        return stripped[match.end() :].strip()
    return stripped


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "." * max_chars
    return f"{text[: max_chars - 3]}..."


def _safe_source_label(c: CitedChunk) -> str:
    raw = c.source_alias.strip() if c.source_alias else ""
    if raw:
        label = raw.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    else:
        label = f"chunk {c.chunk_index}"
    label = _CONTROL_CHARS_RE.sub(" ", label)
    label = " ".join(label.split())
    if not label:
        label = f"chunk {c.chunk_index}"
    return _truncate_text(label, _MAX_SOURCE_LABEL_CHARS)


def _citation_line(c: CitedChunk) -> str:
    alias = _safe_source_label(c)
    return f"  {alias} (chunk {c.chunk_index})"


def _assemble_telegram_reply(answer: str, citations: list[CitedChunk]) -> str:
    answer = answer.strip() or _EMPTY_ANSWER_REPLY
    source_lines = [_citation_line(c) for c in citations[:3]]
    if not source_lines:
        return _truncate_text(answer, _TELEGRAM_MAX_CHARS)

    sources_suffix = "\n\nSources:\n" + "\n".join(source_lines)
    max_answer_len = _TELEGRAM_MAX_CHARS - len(sources_suffix)
    if max_answer_len <= 0:
        return _truncate_text(sources_suffix.lstrip(), _TELEGRAM_MAX_CHARS)
    return f"{_truncate_text(answer, max_answer_len)}{sources_suffix}"


def _format_telegram_qa_reply(response: CitedResponse) -> str:
    """Convert a CitedResponse into a plain-text Telegram message.

    Trims the answer or limits citations before sending, to stay within
    Telegram's 4096-character sendMessage limit.
    """
    if response.answer == _NO_CONTENT_ANSWER:
        return _NO_CONTENT_REPLY

    if response.answer is None:
        if response.citations:
            return _assemble_telegram_reply(
                "I found relevant material but could not synthesise an answer.",
                response.citations,
            )
        return _NO_CONTENT_REPLY

    return _assemble_telegram_reply(response.answer, response.citations)


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


async def _handle_update(
    update: dict,  # type: ignore[type-arg]
    cfg: TelegramConnectorConfig,
    *,
    retrieval_service: Any = None,
    output_service: Any = None,
    role_pack: Any = None,
) -> None:
    update_id = update.get("update_id") if isinstance(update, dict) else None
    message_id: object | None = None
    try:
        msg = update.get("message")
        if msg is None:
            return
        if not isinstance(msg, dict):
            _log("warning", "malformed message payload — ignored", update_id=update_id)
            return

        message_id = msg.get("message_id")
        chat = msg.get("chat", {})
        if not isinstance(chat, dict):
            _log(
                "warning",
                "malformed chat payload — ignored",
                **_log_ids(update_id, message_id),
            )
            return

        chat_id = str(chat.get("id", ""))
        if chat_id != cfg.chat_id:
            _log(
                "warning",
                "received message from unconfigured chat — ignored",
                **_log_ids(update_id, message_id),
            )
            return

        text = msg.get("text")
        if text is None:
            _log(
                "info",
                "non-text message received — ignored",
                **_log_ids(update_id, message_id),
            )
            return
        if not isinstance(text, str):
            _log(
                "warning",
                "malformed text payload — ignored",
                **_log_ids(update_id, message_id),
            )
            return

        classification = _classify_inbound_text(text)
        _log(
            "info",
            "inbound message received",
            **_log_ids(update_id, message_id),
            text_length=len(text),
            classification=classification,
        )

        if output_service is None:
            return

        if classification == "question":
            question_text = _normalise_question_text(text)
            if not question_text:
                _log(
                    "info",
                    "unsupported text — sending guidance",
                    **_log_ids(update_id, message_id),
                )
                await output_service.send("telegram", _UNSUPPORTED_REPLY)
                return

            _log("info", "accepted question", **_log_ids(update_id, message_id))
            response: CitedResponse = await asyncio.wait_for(
                retrieval_service.query(question_text, role_pack),
                timeout=_RETRIEVAL_TIMEOUT_SECONDS,
            )
            if response.answer is None:
                _log(
                    "info",
                    "synthesis-degraded outcome",
                    **_log_ids(update_id, message_id),
                    citation_count=len(response.citations),
                )
            elif response.answer == _NO_CONTENT_ANSWER:
                _log("info", "no-content outcome", **_log_ids(update_id, message_id))
            reply = _format_telegram_qa_reply(response)
            await output_service.send("telegram", reply)
        else:
            _log(
                "info",
                "unsupported text — sending guidance",
                **_log_ids(update_id, message_id),
            )
            await output_service.send("telegram", _UNSUPPORTED_REPLY)
    except TimeoutError:
        _log(
            "error",
            "retrieval timed out",
            **_log_ids(update_id, message_id),
            timeout_seconds=_RETRIEVAL_TIMEOUT_SECONDS,
        )
        if output_service is not None:
            try:
                await output_service.send("telegram", _RECOVERY_REPLY)
            except Exception:
                pass
    except Exception as exc:
        _log(
            "error",
            "unexpected handler failure",
            **_log_ids(update_id, message_id),
            error=str(exc)[:200],
        )
        if output_service is not None:
            try:
                await output_service.send("telegram", _RECOVERY_REPLY)
            except Exception:
                pass


async def run_polling(
    cfg: TelegramConnectorConfig,
    *,
    retrieval_service: Any = None,
    output_service: Any = None,
    role_pack: Any = None,
) -> None:
    _log("info", "Telegram polling started", chat_id=cfg.chat_id)
    offset = 0
    backoff = cfg.backoff_initial

    async with httpx.AsyncClient() as client:
        while True:
            try:
                offset, updates = await _poll_once(cfg, client, offset)
                backoff = cfg.backoff_initial
                for update in updates:
                    await _handle_update(
                        update,
                        cfg,
                        retrieval_service=retrieval_service,
                        output_service=output_service,
                        role_pack=role_pack,
                    )
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


async def _run_telegram_bot(config: CosConfig) -> None:
    """Build Q&A service dependencies and start the polling loop."""
    import yaml  # type: ignore[import-untyped]
    from pydantic import ValidationError

    from cos.llm.factory import make_llm_adapter
    from cos.output.channels.telegram import TelegramChannel
    from cos.output.router import AsyncHandler, OutputRouter
    from cos.rolepack.loader import load as load_role_pack
    from cos.services.output import OutputService
    from cos.services.retrieval import RetrievalService
    from cos.store.db import create_pool

    cfg = config.telegram
    assert cfg is not None  # verified by caller before asyncio.run

    try:
        role_pack = load_role_pack(config.role_pack.path)
    except FileNotFoundError as exc:
        _log("error", "role pack not found — exiting", error=str(exc))
        raise SystemExit(1) from exc
    except (yaml.YAMLError, ValidationError) as exc:
        _log("error", "role pack invalid — exiting", error=str(exc))
        raise SystemExit(1) from exc

    pool = await create_pool(config.database.libpq_dsn)
    llm_adapter = make_llm_adapter(config)

    tg_channel = TelegramChannel(config=cfg)
    extra_handlers: dict[str, AsyncHandler] = {"telegram": tg_channel.send}
    output_router = OutputRouter(
        configured_channels=role_pack.output_channels,
        extra_handlers=extra_handlers,
    )
    output_service = OutputService(router=output_router)
    retrieval_service = RetrievalService(
        config=config,
        pool=pool,
        llm_adapter=llm_adapter,
    )

    _log("info", "Q&A services initialised", role_name=role_pack.role_name)

    await run_polling(
        cfg,
        retrieval_service=retrieval_service,
        output_service=output_service,
        role_pack=role_pack,
    )


def run() -> None:
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    config = CosConfig.load()

    if "telegram" not in config.connectors or config.telegram is None:
        _log("info", "Telegram connector not configured — exiting")
        return

    asyncio.run(_run_telegram_bot(config))
