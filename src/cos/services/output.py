from cos.output.router import OutputRouter


class OutputService:
    def __init__(self, router: OutputRouter) -> None:
        self._router = router

    async def send(self, channel: str, content: str) -> None:
        await self._router.send(channel, content)
