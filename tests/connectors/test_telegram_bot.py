import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from cos.config import TelegramConnectorConfig
from cos.connectors.telegram_bot import (
    _build_note_alias,
    _build_note_locator,
    _classify_inbound_text,
    _format_note_md,
    _format_telegram_qa_reply,
    _handle_update,
    _normalise_note_text,
    _poll_once,
    _stage_telegram_note,
    run_polling,
)
from cos.retrieval.citations import CitedChunk, CitedResponse


async def _noop_sleep(_seconds: float) -> None:
    pass


def _make_tg_config(**overrides: object) -> TelegramConnectorConfig:
    defaults: dict[str, object] = {
        "bot_token": "test-bot-token",
        "chat_id": "111222333",
        "poll_timeout": 5,
    }
    defaults.update(overrides)
    return TelegramConnectorConfig(**defaults)  # type: ignore[arg-type]


def _updates_response(updates: list[dict]) -> dict:  # type: ignore[type-arg]
    return {"ok": True, "result": updates}


def _make_cited_chunk(
    *,
    source_alias: str = "policy-doc",
    chunk_index: int = 1,
    source_locator: str = "/internal/path/to/file.pdf",
    content: str = "sample content",
    score: float = 0.9,
) -> CitedChunk:
    return CitedChunk(
        content=content,
        source_document_id="00000000-0000-0000-0000-000000000001",
        source_alias=source_alias,
        source_locator=source_locator,
        document_version_id="00000000-0000-0000-0000-000000000002",
        chunk_index=chunk_index,
        score=score,
    )


class _MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = iter(responses)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return next(self._responses)


# ─────────────────────────────────────────────
# Story 8.1 tests — polling and HTTP behaviour
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_poll_once_sends_getupdates_request() -> None:
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        await _poll_once(cfg, client, 0)

    assert len(transport.requests) == 1
    req = transport.requests[0]
    assert "getUpdates" in str(req.url)


@pytest.mark.asyncio
async def test_poll_once_passes_allowed_updates_message() -> None:
    import json as _json

    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        await _poll_once(cfg, client, 0)

    req = transport.requests[0]
    body = _json.loads(req.content)
    assert "message" in body.get("allowed_updates", [])


@pytest.mark.asyncio
async def test_poll_once_advances_offset() -> None:
    updates = [{"update_id": 10, "message": {}}, {"update_id": 11, "message": {}}]
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response(updates)),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        new_offset, result = await _poll_once(cfg, client, 0)

    assert new_offset == 12
    assert len(result) == 2


@pytest.mark.asyncio
async def test_poll_once_does_not_regress_offset_with_no_updates() -> None:
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        new_offset, _ = await _poll_once(cfg, client, 42)

    assert new_offset == 42


@pytest.mark.asyncio
async def test_poll_once_raises_on_non_success_http_status() -> None:
    transport = _MockTransport([
        httpx.Response(500, json={"ok": False, "description": "server error"}),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RuntimeError, match="HTTP 500"):
            await _poll_once(cfg, client, 0)


@pytest.mark.asyncio
async def test_poll_once_preserves_webhook_conflict_description() -> None:
    transport = _MockTransport([
        httpx.Response(
            409,
            json={"ok": False, "description": "Conflict: webhook active"},
        ),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RuntimeError, match="Conflict: webhook active"):
            await _poll_once(cfg, client, 0)


@pytest.mark.asyncio
async def test_poll_once_raises_on_telegram_api_error() -> None:
    transport = _MockTransport([
        httpx.Response(
            200, json={"ok": False, "description": "Conflict: webhook active"}
        ),
    ])
    cfg = _make_tg_config()
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(RuntimeError, match="Telegram API error"):
            await _poll_once(cfg, client, 0)


@pytest.mark.asyncio
async def test_poll_once_does_not_log_token_via_httpx(
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = _MockTransport([
        httpx.Response(200, json=_updates_response([])),
    ])
    cfg = _make_tg_config(bot_token="super-secret-bot-token")
    async with httpx.AsyncClient(transport=transport) as client:
        with caplog.at_level(logging.INFO):
            await _poll_once(cfg, client, 0)

    for record in caplog.records:
        assert "super-secret-bot-token" not in record.message


@pytest.mark.asyncio
async def test_handle_update_ignores_unconfigured_chat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 1,
        "message": {"chat": {"id": 999999}, "text": "from stranger"},
    }
    with caplog.at_level(logging.WARNING):
        await _handle_update(update, cfg)

    assert any("unconfigured chat" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handle_update_logs_inbound_for_configured_chat(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 2,
        "message": {"chat": {"id": 111222333}, "text": "hello"},
    }
    with caplog.at_level(logging.INFO):
        await _handle_update(update, cfg)

    assert any("inbound message received" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handle_update_does_not_log_message_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 3,
        "message": {"chat": {"id": 111222333}, "text": "private-content-xyz"},
    }
    with caplog.at_level(logging.DEBUG):
        await _handle_update(update, cfg)

    for record in caplog.records:
        assert "private-content-xyz" not in record.message


@pytest.mark.asyncio
async def test_run_polling_retries_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Polling loop retries after transient errors and exits after second call."""
    calls = [0]
    cfg = _make_tg_config()

    monkeypatch.setattr("cos.connectors.telegram_bot.asyncio.sleep", _noop_sleep)

    async def _fake_poll_once(
        _cfg: TelegramConnectorConfig,
        _client: httpx.AsyncClient,
        offset: int,
    ) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("transient error")
        raise asyncio.CancelledError()

    import cos.connectors.telegram_bot as tg_mod

    original = tg_mod._poll_once
    tg_mod._poll_once = _fake_poll_once  # type: ignore[assignment]
    try:
        with pytest.raises(asyncio.CancelledError):
            await run_polling(cfg)
    finally:
        tg_mod._poll_once = original

    assert calls[0] == 2


@pytest.mark.asyncio
async def test_run_polling_logs_webhook_conflict_as_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config()
    call_count = [0]

    monkeypatch.setattr("cos.connectors.telegram_bot.asyncio.sleep", _noop_sleep)

    async def _fake_poll_once(
        _cfg: TelegramConnectorConfig,
        _client: httpx.AsyncClient,
        offset: int,
    ) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Conflict: webhook active")
        raise asyncio.CancelledError()

    import cos.connectors.telegram_bot as tg_mod

    original = tg_mod._poll_once
    tg_mod._poll_once = _fake_poll_once  # type: ignore[assignment]
    try:
        with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
            await run_polling(cfg)
    finally:
        tg_mod._poll_once = original

    assert any("webhook conflict" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handle_update_skips_update_with_no_message() -> None:
    cfg = _make_tg_config()
    await _handle_update({"update_id": 99}, cfg)


# ─────────────────────────────────────────────
# Story 8.2 tests — classifier heuristics
# ─────────────────────────────────────────────

def test_classify_question_ends_with_question_mark() -> None:
    assert _classify_inbound_text("What is the leave policy?") == "question"


def test_classify_question_starts_with_what() -> None:
    assert _classify_inbound_text("what is the leave policy") == "question"


def test_classify_question_starts_with_why() -> None:
    assert _classify_inbound_text("why did turnover increase") == "question"


def test_classify_question_starts_with_how() -> None:
    assert _classify_inbound_text("how do I submit a request") == "question"


def test_classify_question_starts_with_when() -> None:
    assert _classify_inbound_text("when is the next review") == "question"


def test_classify_question_starts_with_where() -> None:
    assert _classify_inbound_text("where is the benefits document") == "question"


def test_classify_question_starts_with_who() -> None:
    assert _classify_inbound_text("who owns onboarding") == "question"


def test_classify_question_starts_with_which() -> None:
    assert _classify_inbound_text("which roles are impacted") == "question"


def test_classify_question_slash_ask() -> None:
    assert _classify_inbound_text("/ask about the hiring policy") == "question"


def test_classify_question_slash_ask_with_bot_username() -> None:
    assert _classify_inbound_text("/ask@CosBot about the hiring policy") == "question"


def test_classify_unsupported_slash_ask_prefix_false_positive() -> None:
    assert _classify_inbound_text("/askew about the hiring policy") == "unsupported"


def test_classify_question_tell_me() -> None:
    assert _classify_inbound_text("tell me about the annual review") == "question"


def test_classify_question_show_me() -> None:
    assert _classify_inbound_text("show me the headcount report") == "question"


def test_classify_question_find() -> None:
    assert _classify_inbound_text("find the policy on remote work") == "question"


def test_classify_question_look_up() -> None:
    assert _classify_inbound_text("look up the compensation bands") == "question"


def test_classify_question_summarise() -> None:
    assert _classify_inbound_text("summarise the board update") == "question"


def test_classify_question_summarize() -> None:
    assert _classify_inbound_text("summarize last quarter results") == "question"


def test_classify_question_compare() -> None:
    assert _classify_inbound_text("compare the two job descriptions") == "question"


def test_classify_question_brief_me() -> None:
    assert _classify_inbound_text("brief me on the talent strategy") == "question"


def test_classify_question_draft() -> None:
    assert _classify_inbound_text("draft a memo on the policy change") == "question"


def test_classify_unsupported_plain_statement() -> None:
    assert _classify_inbound_text("hello there") == "unsupported"


def test_classify_note_prefix_basic() -> None:
    assert _classify_inbound_text("note: remember to follow up") == "note"


def test_classify_unsupported_declarative() -> None:
    assert _classify_inbound_text("I just had a great meeting") == "unsupported"


def test_classify_unsupported_phrase_prefix_false_positive() -> None:
    assert _classify_inbound_text("drafting notes from the meeting") == "unsupported"


def test_classify_unsupported_empty() -> None:
    assert _classify_inbound_text("") == "unsupported"


def test_classify_unsupported_whitespace_only() -> None:
    assert _classify_inbound_text("   ") == "unsupported"


# ─────────────────────────────────────────────
# Story 8.2 tests — handle_update routing
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_update_ignores_non_text_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 10,
        "message": {"chat": {"id": 111222333}, "photo": [{"file_id": "abc"}]},
    }
    retrieval = AsyncMock()
    output = AsyncMock()

    with caplog.at_level(logging.INFO):
        await _handle_update(
            update, cfg, retrieval_service=retrieval, output_service=output
        )

    assert any("non-text message" in r.message for r in caplog.records)
    retrieval.query.assert_not_called()
    output.send.assert_not_called()


@pytest.mark.asyncio
async def test_handle_update_routes_question_to_retrieval() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 20,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    mock_response = CitedResponse(
        answer="Annual leave is 25 days.",
        citations=[_make_cited_chunk()],
    )
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=mock_response)
    output = AsyncMock()
    role_pack = MagicMock()

    await _handle_update(
        update,
        cfg,
        retrieval_service=retrieval,
        output_service=output,
        role_pack=role_pack,
    )

    retrieval.query.assert_called_once_with(
        "what is the leave policy?", role_pack
    )
    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"


@pytest.mark.asyncio
async def test_handle_update_strips_ask_command_before_retrieval() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 20,
        "message": {"chat": {"id": 111222333}, "text": "/ask what is the policy?"},
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer="Policy answer.",
        citations=[_make_cited_chunk()],
    ))
    output = AsyncMock()
    role_pack = MagicMock()

    await _handle_update(
        update,
        cfg,
        retrieval_service=retrieval,
        output_service=output,
        role_pack=role_pack,
    )

    retrieval.query.assert_called_once_with("what is the policy?", role_pack)


@pytest.mark.asyncio
async def test_handle_update_ask_command_without_question_sends_guidance() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 20,
        "message": {"chat": {"id": 111222333}, "text": "/ask"},
    }
    retrieval = AsyncMock()
    output = AsyncMock()

    await _handle_update(
        update,
        cfg,
        retrieval_service=retrieval,
        output_service=output,
    )

    retrieval.query.assert_not_called()
    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "question" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_sends_unsupported_reply_for_non_question() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 21,
        "message": {"chat": {"id": 111222333}, "text": "hello there"},
    }
    retrieval = AsyncMock()
    output = AsyncMock()

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    retrieval.query.assert_not_called()
    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "knowledge base" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_does_not_reply_to_unconfigured_chat() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 22,
        "message": {"chat": {"id": 999999}, "text": "what is the policy?"},
    }
    retrieval = AsyncMock()
    output = AsyncMock()

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    retrieval.query.assert_not_called()
    output.send.assert_not_called()


@pytest.mark.asyncio
async def test_handle_update_sends_recovery_on_retrieval_exception() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 23,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(side_effect=RuntimeError("db error"))
    output = AsyncMock()

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "cos logs" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_sends_recovery_on_retrieval_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 23,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }

    async def _slow_query(_text: str, _role_pack: object) -> CitedResponse:
        await asyncio.sleep(0.05)
        return CitedResponse(answer="Too late.", citations=[])

    retrieval = AsyncMock()
    retrieval.query = AsyncMock(side_effect=_slow_query)
    output = AsyncMock()
    monkeypatch.setattr("cos.connectors.telegram_bot._RETRIEVAL_TIMEOUT_SECONDS", 0.01)

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "cos logs" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_no_content_sends_no_relevant_content_reply() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 24,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer="No relevant content found in the knowledge base.",
        citations=[],
    ))
    output = AsyncMock()

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "no relevant content" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_synthesis_degraded_sends_degraded_reply() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 25,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer=None,
        citations=[_make_cited_chunk(source_alias="policy-doc", chunk_index=1)],
    ))
    output = AsyncMock()

    await _handle_update(
        update, cfg, retrieval_service=retrieval, output_service=output
    )

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "could not synthesise" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_logs_structured_events_for_question(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 26,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer="25 days.",
        citations=[_make_cited_chunk()],
    ))
    output = AsyncMock()

    with caplog.at_level(logging.INFO):
        await _handle_update(
            update, cfg, retrieval_service=retrieval, output_service=output
        )

    messages = " ".join(r.message for r in caplog.records)
    assert "accepted question" in messages


@pytest.mark.asyncio
async def test_handle_update_logs_message_id_when_available(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 27,
        "message": {
            "message_id": 4321,
            "chat": {"id": 111222333},
            "text": "what is the leave policy?",
        },
    }
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer="25 days.",
        citations=[_make_cited_chunk()],
    ))
    output = AsyncMock()

    with caplog.at_level(logging.INFO):
        await _handle_update(
            update, cfg, retrieval_service=retrieval, output_service=output
        )

    log_records = [json.loads(r.message) for r in caplog.records]
    assert any(record.get("message_id") == 4321 for record in log_records)


@pytest.mark.asyncio
async def test_run_polling_continues_after_malformed_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    updates = [
        {"update_id": 30, "message": []},
        {
            "update_id": 31,
            "message": {"chat": {"id": 111222333}, "text": "what is the policy?"},
        },
    ]
    calls = [0]

    async def _fake_poll_once(
        _cfg: TelegramConnectorConfig,
        _client: httpx.AsyncClient,
        _offset: int,
    ) -> tuple[int, list[dict]]:  # type: ignore[type-arg]
        calls[0] += 1
        if calls[0] == 1:
            return 32, updates
        raise asyncio.CancelledError()

    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=CitedResponse(
        answer="Policy answer.",
        citations=[_make_cited_chunk()],
    ))
    output = AsyncMock()

    import cos.connectors.telegram_bot as tg_mod

    original = tg_mod._poll_once
    tg_mod._poll_once = _fake_poll_once  # type: ignore[assignment]
    try:
        with pytest.raises(asyncio.CancelledError):
            await run_polling(
                cfg,
                retrieval_service=retrieval,
                output_service=output,
                role_pack=MagicMock(),
            )
    finally:
        tg_mod._poll_once = original

    output.send.assert_called_once()


# ─────────────────────────────────────────────
# Story 8.2 tests — reply formatter
# ─────────────────────────────────────────────

def test_format_reply_includes_answer_and_sources() -> None:
    response = CitedResponse(
        answer="Annual leave is 25 days.",
        citations=[_make_cited_chunk(source_alias="leave-policy", chunk_index=3)],
    )
    result = _format_telegram_qa_reply(response)
    assert "Annual leave is 25 days." in result
    assert "Sources:" in result
    assert "leave-policy" in result
    assert "chunk 3" in result


def test_format_reply_no_raw_json() -> None:
    response = CitedResponse(
        answer="Some answer.",
        citations=[_make_cited_chunk()],
    )
    result = _format_telegram_qa_reply(response)
    assert '{"status"' not in result
    assert '"answer"' not in result


def test_format_reply_avoids_source_locator_when_alias_present() -> None:
    response = CitedResponse(
        answer="Some answer.",
        citations=[_make_cited_chunk(
            source_alias="safe-alias",
            source_locator="/internal/sensitive/path.pdf",
        )],
    )
    result = _format_telegram_qa_reply(response)
    assert "/internal/sensitive/path.pdf" not in result
    assert "safe-alias" in result


def test_format_reply_stays_under_4096_chars_for_long_answer() -> None:
    long_answer = "A" * 5000
    response = CitedResponse(
        answer=long_answer,
        citations=[_make_cited_chunk()],
    )
    result = _format_telegram_qa_reply(response)
    assert len(result) <= 4096
    assert "Sources:" in result
    assert "policy-doc" in result


def test_format_reply_no_content_outcome() -> None:
    response = CitedResponse(
        answer="No relevant content found in the knowledge base.",
        citations=[],
    )
    result = _format_telegram_qa_reply(response)
    assert "no relevant content" in result.lower()
    assert "knowledge base" not in result.lower()


def test_format_reply_synthesis_degraded_with_citations() -> None:
    response = CitedResponse(
        answer=None,
        citations=[_make_cited_chunk(source_alias="report-q1", chunk_index=2)],
    )
    result = _format_telegram_qa_reply(response)
    assert "could not synthesise" in result.lower()
    assert "report-q1" in result
    assert "Sources:" in result


def test_format_reply_synthesis_degraded_no_citations() -> None:
    response = CitedResponse(answer=None, citations=[])
    result = _format_telegram_qa_reply(response)
    assert "no relevant content" in result.lower()


def test_format_reply_many_citations_still_under_limit() -> None:
    citations = [
        _make_cited_chunk(source_alias=f"doc-{i}", chunk_index=i)
        for i in range(20)
    ]
    response = CitedResponse(answer="Short answer.", citations=citations)
    result = _format_telegram_qa_reply(response)
    assert len(result) <= 4096


def test_format_reply_uses_chunk_index_fallback_when_no_alias() -> None:
    chunk = CitedChunk(
        content="content",
        source_document_id="00000000-0000-0000-0000-000000000001",
        source_alias="",
        source_locator="/path/file.pdf",
        document_version_id="00000000-0000-0000-0000-000000000002",
        chunk_index=5,
        score=0.8,
    )
    response = CitedResponse(answer="An answer.", citations=[chunk])
    result = _format_telegram_qa_reply(response)
    assert "chunk 5" in result


def test_format_reply_synthesis_degraded_with_long_alias_stays_under_limit() -> None:
    response = CitedResponse(
        answer=None,
        citations=[_make_cited_chunk(source_alias="A" * 5000, chunk_index=2)],
    )
    result = _format_telegram_qa_reply(response)
    assert len(result) <= 4096
    assert "Sources:" in result


def test_format_reply_sanitizes_path_like_alias() -> None:
    response = CitedResponse(
        answer="Some answer.",
        citations=[_make_cited_chunk(source_alias="/legacy/private/report.pdf")],
    )
    result = _format_telegram_qa_reply(response)
    assert "/legacy/private" not in result
    assert "report.pdf" in result


def test_format_reply_sanitizes_control_characters_in_alias() -> None:
    response = CitedResponse(
        answer="Some answer.",
        citations=[_make_cited_chunk(source_alias="safe\nInjected: nope")],
    )
    result = _format_telegram_qa_reply(response)
    assert "safe Injected: nope" in result
    assert "\n  Injected: nope" not in result


def test_format_reply_empty_answer_is_non_empty() -> None:
    response = CitedResponse(answer="", citations=[])
    result = _format_telegram_qa_reply(response)
    assert result
    assert len(result) <= 4096


# ─────────────────────────────────────────────
# Story 8.3 tests — note classifier
# ─────────────────────────────────────────────

def test_classify_note_prefix_uppercase() -> None:
    assert _classify_inbound_text("NOTE: meeting recap") == "note"


def test_classify_note_prefix_mixed_case() -> None:
    assert _classify_inbound_text("Note: action item") == "note"


def test_classify_note_prefix_with_space_before_colon() -> None:
    assert _classify_inbound_text("note : a thought") == "note"


def test_classify_note_prefix_beats_question_mark() -> None:
    assert _classify_inbound_text("note: what is this?") == "note"


def test_classify_note_prefix_beats_question_word() -> None:
    assert _classify_inbound_text("note: why we did this") == "note"


def test_classify_note_empty_prefix_still_classified_as_note() -> None:
    # Empty content after note: is handled in the handler, not the classifier
    assert _classify_inbound_text("note:") == "note"


def test_classify_note_prefix_with_whitespace_only_body() -> None:
    assert _classify_inbound_text("note:   ") == "note"


def test_classify_declarative_still_unsupported() -> None:
    assert _classify_inbound_text("I just had a great meeting") == "unsupported"


def test_classify_question_unaffected_by_note_changes() -> None:
    assert _classify_inbound_text("what is the leave policy?") == "question"


def test_classify_ask_command_unaffected() -> None:
    assert _classify_inbound_text("/ask what is the policy?") == "question"


# ─────────────────────────────────────────────
# Story 8.3 tests — note text normalisation
# ─────────────────────────────────────────────

def test_normalise_note_text_strips_prefix() -> None:
    result = _normalise_note_text("note: remember to follow up")
    assert result == "remember to follow up"


def test_normalise_note_text_case_insensitive() -> None:
    assert _normalise_note_text("NOTE: action item") == "action item"


def test_normalise_note_text_strips_surrounding_whitespace() -> None:
    assert _normalise_note_text("  note:   thought  ") == "thought"


def test_normalise_note_text_empty_body() -> None:
    assert _normalise_note_text("note:") == ""


def test_normalise_note_text_whitespace_only_body() -> None:
    assert _normalise_note_text("note:   ") == ""


# ─────────────────────────────────────────────
# Story 8.3 tests — note locator and alias
# ─────────────────────────────────────────────

def test_build_note_locator_uses_message_id_when_present() -> None:
    locator = _build_note_locator("111222333", 4321, 99)
    assert locator == "telegram://chat/111222333/message/4321"


def test_build_note_locator_falls_back_to_update_id() -> None:
    locator = _build_note_locator("111222333", None, 99)
    assert locator == "telegram://chat/111222333/update/99"


def test_build_note_locator_falls_back_when_message_id_zero() -> None:
    locator = _build_note_locator("111222333", 0, 99)
    assert locator == "telegram://chat/111222333/update/99"


def test_build_note_alias_format() -> None:
    dt = datetime(2026, 5, 28, 10, 15, 30, tzinfo=timezone.utc)
    alias = _build_note_alias(dt, 4321)
    assert alias == "telegram-note-2026-05-28T101530Z-4321.md"


def test_build_note_alias_ends_with_md() -> None:
    dt = datetime(2026, 5, 28, 10, 15, 30, tzinfo=timezone.utc)
    alias = _build_note_alias(dt, "upd12345")
    assert alias.endswith(".md")


# ─────────────────────────────────────────────
# Story 8.3 tests — note Markdown formatting
# ─────────────────────────────────────────────

def _make_tg_msg(
    *,
    text: str = "note: test",
    chat_id: int = 111222333,
    message_id: int = 4321,
    date: int = 1748424930,
    from_info: dict | None = None,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    msg: dict = {  # type: ignore[type-arg]
        "text": text,
        "chat": {"id": chat_id},
        "message_id": message_id,
        "date": date,
    }
    if from_info is not None:
        msg["from"] = from_info
    return msg


def test_format_note_md_contains_heading() -> None:
    msg = _make_tg_msg()
    result = _format_note_md("my note body", msg)
    assert "# Telegram Note" in result


def test_format_note_md_contains_note_body() -> None:
    msg = _make_tg_msg()
    result = _format_note_md("this is my note", msg)
    assert "this is my note" in result


def test_format_note_md_contains_captured_timestamp() -> None:
    msg = _make_tg_msg(date=1748424930)
    result = _format_note_md("body", msg)
    assert "Captured:" in result


def test_format_note_md_contains_chat_id() -> None:
    msg = _make_tg_msg(chat_id=111222333)
    result = _format_note_md("body", msg)
    assert "Chat ID: 111222333" in result


def test_format_note_md_contains_message_id() -> None:
    msg = _make_tg_msg(message_id=4321)
    result = _format_note_md("body", msg)
    assert "Message ID: 4321" in result


def test_format_note_md_contains_sender_when_present() -> None:
    msg = _make_tg_msg(from_info={"id": 123, "first_name": "Iain", "username": "iain"})
    result = _format_note_md("body", msg)
    assert "Sender:" in result
    assert "Iain" in result


def test_format_note_md_no_sender_when_from_absent() -> None:
    msg = _make_tg_msg()
    result = _format_note_md("body", msg)
    assert "Sender:" not in result


def test_format_note_md_has_separator() -> None:
    msg = _make_tg_msg()
    result = _format_note_md("body", msg)
    assert "---" in result


# ─────────────────────────────────────────────
# Story 8.3 tests — staging helper
# ─────────────────────────────────────────────

def test_stage_telegram_note_writes_file(tmp_path: Path) -> None:
    staging_dir = tmp_path / "telegram"
    path = _stage_telegram_note(
        staging_dir, "# Note\n\nbody here", "telegram-note-test.md"
    )
    assert path.exists()
    assert "body here" in path.read_text(encoding="utf-8")


def test_stage_telegram_note_creates_staging_dir(tmp_path: Path) -> None:
    staging_dir = tmp_path / "new" / "subdir"
    _stage_telegram_note(staging_dir, "content", "alias.md")
    assert staging_dir.is_dir()


def test_stage_telegram_note_unique_per_call(tmp_path: Path) -> None:
    staging_dir = tmp_path / "telegram"
    p1 = _stage_telegram_note(staging_dir, "same content", "same-alias.md")
    p2 = _stage_telegram_note(staging_dir, "same content", "same-alias.md")
    assert p1 != p2


# ─────────────────────────────────────────────
# Story 8.3 tests — handle_update note routing
# ─────────────────────────────────────────────

def _make_note_pool(
    *,
    already_processed: bool = False,
    already_pending: bool = False,
) -> MagicMock:
    """Return a mock pool that yields a mock connection via .connection()."""
    mock_conn = AsyncMock()

    @asynccontextmanager
    async def _fake_connection():  # type: ignore[return]
        yield mock_conn

    mock_conn.has_processed = already_processed
    mock_conn.has_pending = already_pending

    pool = MagicMock()
    pool.connection = _fake_connection
    return pool, mock_conn


_TGB = "cos.connectors.telegram_bot"
_NO_PROCESSED = AsyncMock(return_value=False)
_NO_PENDING = AsyncMock(return_value=False)


@pytest.mark.asyncio
async def test_handle_update_routes_note_to_enqueue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    update = {
        "update_id": 50,
        "message": {
            "message_id": 1001,
            "chat": {"id": 111222333},
            "text": "note: great idea from the meeting",
            "date": 1748424930,
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()
    mock_submit = AsyncMock()

    with (
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(f"{_TGB}.submit_ingest_job", mock_submit),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert content == "Note saved."
    mock_submit.assert_called_once()


@pytest.mark.asyncio
async def test_handle_update_note_submit_receives_telegram_note_source_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    update = {
        "update_id": 51,
        "message": {
            "message_id": 1002,
            "chat": {"id": 111222333},
            "text": "note: important thought",
            "date": 1748424930,
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()
    captured: list = []

    async def _capture_submit(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs)
        return MagicMock()

    with (
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(f"{_TGB}.submit_ingest_job", _capture_submit),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    assert len(captured) == 1
    assert captured[0]["source_type"] == "telegram_note"
    expected_locator = "telegram://chat/111222333/message/1002"
    assert captured[0]["source_locator"] == expected_locator
    assert captured[0]["source_alias"].startswith("telegram-note-")
    assert captured[0]["source_alias"].endswith(".md")


@pytest.mark.asyncio
async def test_handle_update_note_empty_sends_guidance() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 52,
        "message": {"chat": {"id": 111222333}, "text": "note:"},
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()

    await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    channel, content = output.send.call_args[0]
    assert channel == "telegram"
    assert "note:" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_note_whitespace_only_sends_guidance() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 53,
        "message": {"chat": {"id": 111222333}, "text": "note:   "},
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()

    await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    _, content = output.send.call_args[0]
    assert "note:" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_note_already_processed_acks_as_saved() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 54,
        "message": {
            "message_id": 1003,
            "chat": {"id": 111222333},
            "text": "note: dup",
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()
    mock_submit = AsyncMock()

    with (
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=True)),
        patch(f"{_TGB}.submit_ingest_job", mock_submit),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    _, content = output.send.call_args[0]
    assert content == "Note saved."
    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_handle_update_note_already_pending_acks_as_saved() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 55,
        "message": {
            "message_id": 1004,
            "chat": {"id": 111222333},
            "text": "note: pending",
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()
    mock_submit = AsyncMock()

    with (
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=True)),
        patch(f"{_TGB}.submit_ingest_job", mock_submit),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    _, content = output.send.call_args[0]
    assert content == "Note saved."
    mock_submit.assert_not_called()


@pytest.mark.asyncio
async def test_handle_update_note_enqueue_failure_sends_failure_reply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    update = {
        "update_id": 56,
        "message": {
            "message_id": 1005,
            "chat": {"id": 111222333},
            "text": "note: fail test",
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()

    with (
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(
            f"{_TGB}.submit_ingest_job",
            AsyncMock(side_effect=RuntimeError("db unavailable")),
        ),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    output.send.assert_called_once()
    _, content = output.send.call_args[0]
    assert "cos logs" in content.lower()
    assert list((tmp_path / "telegram").glob("*.md")) == []


@pytest.mark.asyncio
async def test_handle_update_note_ack_failure_does_not_report_unsaved(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    update = {
        "update_id": 156,
        "message": {
            "message_id": 1105,
            "chat": {"id": 111222333},
            "text": "note: saved but ack failed",
        },
    }
    output = AsyncMock()
    output.send = AsyncMock(side_effect=RuntimeError("telegram unavailable"))
    pool, _ = _make_note_pool()
    mock_submit = AsyncMock()

    with (
        caplog.at_level(logging.ERROR),
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(f"{_TGB}.submit_ingest_job", mock_submit),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    mock_submit.assert_called_once()
    output.send.assert_called_once_with("telegram", "Note saved.")
    messages = " ".join(r.message for r in caplog.records)
    assert "note save acknowledgement failed" in messages
    assert "note save failed" not in messages


@pytest.mark.asyncio
async def test_handle_update_note_no_pool_sends_failure_reply() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 57,
        "message": {"chat": {"id": 111222333}, "text": "note: no pool available"},
    }
    output = AsyncMock()

    await _handle_update(update, cfg, output_service=output, pool=None)

    output.send.assert_called_once()
    _, content = output.send.call_args[0]
    assert "cos logs" in content.lower()


@pytest.mark.asyncio
async def test_handle_update_note_does_not_log_note_body(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    secret_text = "SECRET-NOTE-BODY-XYZ"
    update = {
        "update_id": 58,
        "message": {
            "message_id": 1006,
            "chat": {"id": 111222333},
            "text": f"note: {secret_text}",
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()

    with (
        caplog.at_level(logging.DEBUG),
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(f"{_TGB}.submit_ingest_job", AsyncMock()),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    for record in caplog.records:
        assert secret_text not in record.message


@pytest.mark.asyncio
async def test_handle_update_note_logs_structured_events(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _make_tg_config(chat_id="111222333")
    monkeypatch.setattr(cfg, "staging_dir", tmp_path / "telegram")
    update = {
        "update_id": 59,
        "message": {
            "message_id": 1007,
            "chat": {"id": 111222333},
            "text": "note: log test",
        },
    }
    output = AsyncMock()
    pool, _ = _make_note_pool()

    with (
        caplog.at_level(logging.INFO),
        patch(f"{_TGB}.has_processed_artifact", AsyncMock(return_value=False)),
        patch(f"{_TGB}.has_pending_job_for_locator", AsyncMock(return_value=False)),
        patch(f"{_TGB}.submit_ingest_job", AsyncMock()),
    ):
        await _handle_update(update, cfg, output_service=output, pool=pool)

    messages = " ".join(r.message for r in caplog.records)
    assert "note accepted" in messages
    assert "note enqueued" in messages
    events = [json.loads(r.message) for r in caplog.records]
    accepted = next(e for e in events if e["message"] == "note accepted")
    enqueued = next(e for e in events if e["message"] == "note enqueued")
    assert accepted["note_length"] == len("log test")
    assert enqueued["note_length"] == len("log test")


@pytest.mark.asyncio
async def test_handle_update_qa_routing_unchanged_after_note_changes() -> None:
    """Q&A routing from Story 8.2 must be unaffected by note capture changes."""
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 60,
        "message": {"chat": {"id": 111222333}, "text": "what is the leave policy?"},
    }
    mock_response = CitedResponse(answer="25 days.", citations=[_make_cited_chunk()])
    retrieval = AsyncMock()
    retrieval.query = AsyncMock(return_value=mock_response)
    output = AsyncMock()
    pool, _ = _make_note_pool()

    await _handle_update(
        update,
        cfg,
        retrieval_service=retrieval,
        output_service=output,
        pool=pool,
    )

    retrieval.query.assert_called_once()
    output.send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_update_unsupported_reply_no_longer_says_not_available() -> None:
    cfg = _make_tg_config(chat_id="111222333")
    update = {
        "update_id": 61,
        "message": {"chat": {"id": 111222333}, "text": "hello there"},
    }
    output = AsyncMock()

    await _handle_update(update, cfg, output_service=output)

    _, content = output.send.call_args[0]
    assert "not yet enabled" not in content.lower()
    assert "unavailable" not in content.lower()
