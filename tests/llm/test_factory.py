from types import SimpleNamespace

import pytest

import cos.mcp_server.server as server_mod
from cos.llm.adapter import LLMAdapter
from cos.llm.factory import make_llm_adapter


def _make_config(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        llm=SimpleNamespace(
            provider=provider,
            model="claude-3-haiku-20240307",
            api_key=SimpleNamespace(get_secret_value=lambda: "test"),
            ca_bundle_path=None,
            proxy_url=None,
            trust_env=None,
        ),
        embedding=SimpleNamespace(
            ca_bundle_path=None,
            proxy_url=None,
            trust_env=False,
        ),
    )


def test_make_llm_adapter_anthropic_returns_llm_adapter() -> None:
    result = make_llm_adapter(_make_config("anthropic"))

    assert isinstance(result, LLMAdapter)


def test_make_llm_adapter_unknown_provider_raises_system_exit() -> None:
    with pytest.raises(SystemExit, match="Unsupported LLM provider"):
        make_llm_adapter(_make_config("unsupported_xyz"))


def test_server_module_does_not_expose_anthropic_adapter() -> None:
    assert "AnthropicAdapter" not in dir(server_mod)
