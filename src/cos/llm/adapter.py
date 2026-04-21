from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMAdapter(Protocol):
    async def complete(self, prompt: str, context: list[str]) -> str:
        ...
