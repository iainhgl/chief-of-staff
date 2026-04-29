from cos.config import CosConfig
from cos.llm.adapter import LLMAdapter


def make_llm_adapter(config: CosConfig) -> LLMAdapter:
    if config.llm.provider == "anthropic":
        from cos.llm.anthropic import AnthropicAdapter, HttpTransportConfig

        return AnthropicAdapter(
            model=config.llm.model,
            api_key=config.llm.api_key.get_secret_value(),
            transport=HttpTransportConfig(
                ca_bundle_path=(
                    config.llm.ca_bundle_path
                    if config.llm.ca_bundle_path is not None
                    else config.embedding.ca_bundle_path
                ),
                proxy_url=(
                    config.llm.proxy_url
                    if config.llm.proxy_url is not None
                    else config.embedding.proxy_url
                ),
                trust_env=(
                    config.llm.trust_env
                    if config.llm.trust_env is not None
                    else config.embedding.trust_env
                ),
            ),
        )
    raise SystemExit(
        f"Unsupported LLM provider: {config.llm.provider!r}\n"
        "Add a new adapter in cos/llm/ and register it in cos/llm/factory.py."
    )
