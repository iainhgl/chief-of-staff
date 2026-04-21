class OutputService:
    async def send(self, channel: str, content: str) -> None:
        raise NotImplementedError
