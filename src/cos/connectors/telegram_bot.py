import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx

from cos.config import CosConfig, TelegramConnectorConfig
from cos.retrieval.citations import CitedChunk, CitedResponse
from cos.services.jobs import submit_ingest_job
from cos.store.db import has_pending_job_for_locator, has_processed_artifact

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

_TELEGRAM_MAX_CHARS = 4096
_RETRIEVAL_TIMEOUT_SECONDS = 60.0
_MAX_SOURCE_LABEL_CHARS = 80
_NO_CONTENT_ANSWER = "No relevant content found in the knowledge base."
_NO_CONTENT_REPLY = "No relevant content was found for your question."
_RECOVERY_REPLY = "I could not answer that just now. Check `cos logs` for diagnostics."
_EMPTY_ANSWER_REPLY = "I could not produce an answer from the retrieved content."
_NOTE_SAVE_REPLY = "Note saved."
_NOTE_SAVE_FAILURE_REPLY = (
    "I could not save that note just now. Check `cos logs` for diagnostics."
)
_EMPTY_NOTE_GUIDANCE = (
    "No content found after `note:`. Try: `note: your thought here`"
)

# Question heuristics for the inbound message classifier.
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
_NOTE_PREFIX_RE = re.compile(r"^note\s*:", re.IGNORECASE)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]+")

_UNSUPPORTED_REPLY = (
    "Send a question to get a cited answer from the knowledge base, "
    "or use `note:` followed by your text to save a note."
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


def _classify_inbound_text(text: str) -> Literal["question", "note", "unsupported"]:
    """Classify inbound Telegram text as 'question', 'note', or 'unsupported'.

    Classification order:
    1. note: prefix (case-insensitive) — always wins over Q&A heuristics
    2. Ends with '?'
    3. Starts with '/ask' slash command
    4. First word is a question word (what, why, how, when, where, who, which)
    5. Starts with a KB-request phrase (tell me, show me, find, look up, ...)

    Everything else is unsupported.
    """
    stripped = text.strip()
    if not stripped:
        return "unsupported"
    lower = stripped.lower()

    if _NOTE_PREFIX_RE.match(stripped):
        return "note"

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


def _normalise_note_text(text: str) -> str:
    """Strip the 'note:' prefix and surrounding whitespace, return the note body."""
    stripped = text.strip()
    match = _NOTE_PREFIX_RE.match(stripped)
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


def _compute_fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _build_note_locator(
    chat_id: str,
    message_id: object,
    update_id: object,
) -> str:
    """Return a stable Telegram source locator for a note message."""
    mid_str = str(message_id) if message_id is not None else ""
    if mid_str.isdigit() and int(mid_str) > 0:
        return f"telegram://chat/{chat_id}/message/{message_id}"
    return f"telegram://chat/{chat_id}/update/{update_id}"


def _build_note_alias(capture_dt: datetime, id_ref: object) -> str:
    """Return a human-readable alias like telegram-note-2026-05-28T101530Z-4321.md."""
    ts = capture_dt.strftime("%Y-%m-%dT%H%M%SZ")
    safe_id = re.sub(r"[^0-9a-zA-Z]", "", str(id_ref or "0"))[:12] or "0"
    return f"telegram-note-{ts}-{safe_id}.md"


def _format_sender(from_info: dict) -> str:  # type: ignore[type-arg]
    first = str(from_info.get("first_name", "")).strip()
    last = str(from_info.get("last_name", "")).strip()
    username = str(from_info.get("username", "")).strip()
    user_id = from_info.get("id")

    name = " ".join(p for p in [first, last] if p)
    handle = f"@{username}" if username else ""
    id_part = f"id {user_id}" if user_id is not None else ""
    detail_parts = [p for p in [handle, id_part] if p]
    detail = f"({', '.join(detail_parts)})" if detail_parts else ""
    return " ".join(p for p in [name, detail] if p)


def _extract_capture_dt(msg: dict) -> datetime:  # type: ignore[type-arg]
    msg_date = msg.get("date")
    if msg_date and isinstance(msg_date, int):
        try:
            return datetime.fromtimestamp(msg_date, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    return datetime.now(timezone.utc)


def _format_note_md(note_body: str, msg: dict) -> str:  # type: ignore[type-arg]
    """Build the staged Markdown content for a Telegram note."""
    lines = ["# Telegram Note", ""]
    lines.append(f"Captured: {_extract_capture_dt(msg).isoformat()}")

    from_info = msg.get("from")
    if from_info and isinstance(from_info, dict):
        sender = _format_sender(from_info)
        if sender:
            lines.append(f"Sender: {sender}")

    chat = msg.get("chat") or {}
    if isinstance(chat, dict) and chat.get("id") is not None:
        lines.append(f"Chat ID: {chat['id']}")

    message_id = msg.get("message_id")
    if message_id is not None:
        lines.append(f"Message ID: {message_id}")

    lines.extend(["", "---", "", note_body])
    return "\n".join(lines)


def _build_note_metadata(
    msg: dict,  # type: ignore[type-arg]
    update_id: object,
    fingerprint: str,
    capture_dt: datetime,
) -> dict[str, object]:
    """Build the ingest job metadata dict for a Telegram note."""
    chat = msg.get("chat") or {}
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    from_info = msg.get("from") or {}

    metadata: dict[str, object] = {
        "connector": "telegram",
        "chat_id": chat_id,
        "message_id": msg.get("message_id"),
        "update_id": update_id,
        "message_date": capture_dt.isoformat(),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "content_fingerprint": fingerprint,
    }
    if isinstance(from_info, dict):
        if from_info.get("id") is not None:
            metadata["sender_id"] = from_info["id"]
        if from_info.get("first_name"):
            metadata["sender_first_name"] = str(from_info["first_name"])
        if from_info.get("last_name"):
            metadata["sender_last_name"] = str(from_info["last_name"])
        if from_info.get("username"):
            metadata["sender_username"] = str(from_info["username"])
    return {k: v for k, v in metadata.items() if v is not None}


def _stage_telegram_note(staging_dir: Path, note_md: str, source_alias: str) -> Path:
    """Write the note Markdown to a uniquely-named staged file and return its path."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    stem = source_alias[: -len(".md")] if source_alias.endswith(".md") else source_alias
    token = uuid4().hex[:8]
    staged_path = staging_dir / f"{stem}_{token}.md"
    staged_path.write_text(note_md, encoding="utf-8")
    return staged_path


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
    pool: Any = None,
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

        elif classification == "note":
            note_body = _normalise_note_text(text)
            if not note_body:
                _log(
                    "info",
                    "empty note received — sending guidance",
                    **_log_ids(update_id, message_id),
                )
                await output_service.send("telegram", _EMPTY_NOTE_GUIDANCE)
                return

            _log(
                "info",
                "note accepted",
                **_log_ids(update_id, message_id),
                note_length=len(note_body),
            )
            try:
                capture_dt = _extract_capture_dt(msg)
                note_md = _format_note_md(note_body, msg)
                fingerprint = _compute_fingerprint(note_md.encode("utf-8"))
                source_locator = _build_note_locator(cfg.chat_id, message_id, update_id)
                source_alias = _build_note_alias(capture_dt, message_id or update_id)

                if pool is None:
                    raise RuntimeError("no database pool — note capture unavailable")

                async with pool.connection() as conn:
                    if await has_processed_artifact(
                        conn, "telegram_note", source_locator, fingerprint
                    ):
                        _log(
                            "info",
                            "note already processed — acking as saved",
                            **_log_ids(update_id, message_id),
                        )
                        await output_service.send("telegram", _NOTE_SAVE_REPLY)
                        return

                    already_pending = await has_pending_job_for_locator(
                        conn, source_locator, fingerprint
                    )
                    if already_pending:
                        _log(
                            "info",
                            "note already queued — acking as saved",
                            **_log_ids(update_id, message_id),
                        )
                        await output_service.send("telegram", _NOTE_SAVE_REPLY)
                        return

                    staged_path = _stage_telegram_note(
                        cfg.staging_dir, note_md, source_alias
                    )
                    metadata = _build_note_metadata(
                        msg, update_id, fingerprint, capture_dt
                    )
                    await submit_ingest_job(
                        conn,
                        staged_path=str(staged_path),
                        source_type="telegram_note",
                        source_locator=source_locator,
                        source_alias=source_alias,
                        metadata=metadata,
                    )

                _log("info", "note enqueued", **_log_ids(update_id, message_id))
                await output_service.send("telegram", _NOTE_SAVE_REPLY)
            except Exception as exc:
                _log(
                    "error",
                    "note save failed",
                    **_log_ids(update_id, message_id),
                    error=str(exc)[:200],
                )
                try:
                    await output_service.send("telegram", _NOTE_SAVE_FAILURE_REPLY)
                except Exception:
                    pass

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
    pool: Any = None,
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
                        pool=pool,
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
    """Build Q&A and note-capture service dependencies and start the polling loop."""
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

    _log(
        "info",
        "Q&A and note-capture services initialised",
        role_name=role_pack.role_name,
    )

    await run_polling(
        cfg,
        retrieval_service=retrieval_service,
        output_service=output_service,
        role_pack=role_pack,
        pool=pool,
    )


def run() -> None:
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    config = CosConfig.load()

    if "telegram" not in config.connectors or config.telegram is None:
        _log("info", "Telegram connector not configured — exiting")
        return

    asyncio.run(_run_telegram_bot(config))
