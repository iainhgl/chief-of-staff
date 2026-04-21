class AnthropicAdapter:
    """Anthropic Claude adapter — implemented in Story 3.3."""

    async def complete(self, prompt: str, context: list[str]) -> str:
        raise NotImplementedError
