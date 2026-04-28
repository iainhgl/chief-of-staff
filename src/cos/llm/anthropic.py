import ssl
from dataclasses import dataclass
from pathlib import Path

import anthropic
import httpx

SYSTEM_PROMPT = (
    "You are a precise knowledge assistant. Answer based solely on the context "
    "provided. If the context does not contain relevant information, say so "
    "clearly. Do not fabricate sources or invent information."
)


class AnthropicAdapter:
    """Anthropic Claude adapter."""

    def __init__(
        self,
        model: str,
        api_key: str,
        transport: "HttpTransportConfig | None" = None,
    ) -> None:
        self._model = model
        client_kwargs: dict[str, object] = {"api_key": api_key}
        if transport is not None and transport.has_overrides:
            client_kwargs["http_client"] = httpx.AsyncClient(
                verify=_build_verify(transport.ca_bundle_path),
                proxy=transport.proxy_url,
                trust_env=transport.trust_env,
            )
        self._client = anthropic.AsyncAnthropic(**client_kwargs)

    async def complete(self, prompt: str, context: list[str]) -> str:
        context_text = "\n\n".join(
            f"[{index}] {chunk}" for index, chunk in enumerate(context, start=1)
        )
        if not context_text:
            context_text = "(no context provided)"

        user_message = f"Context:\n{context_text}\n\nInstruction: {prompt}"
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        for block in message.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                return text
        raise RuntimeError("Anthropic response did not include a text content block")


@dataclass(frozen=True)
class HttpTransportConfig:
    ca_bundle_path: Path | None = None
    proxy_url: str | None = None
    trust_env: bool = False

    @property
    def has_overrides(self) -> bool:
        return (
            self.ca_bundle_path is not None
            or self.proxy_url is not None
            or self.trust_env
        )


def _build_verify(ca_bundle_path: Path | None) -> ssl.SSLContext | bool:
    if ca_bundle_path is None:
        return True

    expanded_path = ca_bundle_path.expanduser()
    if not expanded_path.exists():
        raise RuntimeError(f"llm.ca_bundle_path not found: {expanded_path}")

    try:
        return ssl.create_default_context(cafile=str(expanded_path))
    except Exception as exc:  # pragma: no cover - platform SSL errors vary
        raise RuntimeError(
            f"Unable to load llm.ca_bundle_path {expanded_path}: {exc}"
        ) from exc
