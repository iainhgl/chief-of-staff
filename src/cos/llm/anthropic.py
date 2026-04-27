import anthropic

SYSTEM_PROMPT = (
    "You are a precise knowledge assistant. Answer based solely on the context "
    "provided. If the context does not contain relevant information, say so "
    "clearly. Do not fabricate sources or invent information."
)


class AnthropicAdapter:
    """Anthropic Claude adapter."""

    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

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
