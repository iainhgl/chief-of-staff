import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cos.llm.adapter import LLMAdapter
from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig


@pytest.mark.asyncio
async def test_anthropic_adapter_conforms_to_llm_adapter_protocol() -> None:
    adapter = AnthropicAdapter(model="claude-3-haiku-20240307", api_key="test")
    assert isinstance(adapter, LLMAdapter)


@pytest.mark.asyncio
async def test_complete_returns_string_from_api() -> None:
    adapter = AnthropicAdapter(model="claude-3-haiku-20240307", api_key="test")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="synthesised answer")]

    with patch.object(
        adapter._client.messages,
        "create",
        new=AsyncMock(return_value=mock_response),
    ):
        result = await adapter.complete("what is X?", ["chunk one", "chunk two"])

    assert result == "synthesised answer"
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_complete_api_key_never_in_log_output(
    caplog: pytest.LogCaptureFixture,
) -> None:
    api_key = "sk-sentinel-9999"
    adapter = AnthropicAdapter(model="claude-3-haiku-20240307", api_key=api_key)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="safe response")]

    with caplog.at_level(logging.DEBUG):
        with patch.object(
            adapter._client.messages,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            await adapter.complete("what is X?", ["chunk one"])

    assert api_key not in caplog.text


@pytest.mark.asyncio
async def test_complete_includes_context_chunks_in_user_message() -> None:
    adapter = AnthropicAdapter(model="claude-3-haiku-20240307", api_key="test")
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="safe response")]
    create_mock = AsyncMock(return_value=mock_response)

    with patch.object(adapter._client.messages, "create", new=create_mock):
        await adapter.complete("what is X?", ["first chunk", "second chunk"])

    call_kwargs = create_mock.call_args.kwargs
    user_message = call_kwargs["messages"][0]["content"]
    assert "first chunk" in user_message
    assert "second chunk" in user_message


def test_adapter_builds_http_client_for_transport_overrides(tmp_path: Path) -> None:
    cert_path = tmp_path / "corp-root.pem"
    cert_path.write_text("not-a-real-cert", encoding="utf-8")

    with (
        patch("cos.llm.anthropic.httpx.AsyncClient") as mock_http_client,
        patch("cos.llm.anthropic.ssl.create_default_context", return_value=MagicMock()),
        patch("cos.llm.anthropic.anthropic.AsyncAnthropic") as mock_anthropic,
    ):
        AnthropicAdapter(
            model="claude-3-haiku-20240307",
            api_key="test",
            transport=HttpTransportConfig(
                ca_bundle_path=cert_path,
                proxy_url="http://proxy.internal:8080",
                trust_env=True,
            ),
        )

    mock_http_client.assert_called_once()
    mock_anthropic.assert_called_once()


def test_adapter_missing_ca_bundle_raises() -> None:
    with pytest.raises(RuntimeError, match="llm.ca_bundle_path not found"):
        AnthropicAdapter(
            model="claude-3-haiku-20240307",
            api_key="test",
            transport=HttpTransportConfig(
                ca_bundle_path=Path("/definitely/missing/zscaler.pem")
            ),
        )
