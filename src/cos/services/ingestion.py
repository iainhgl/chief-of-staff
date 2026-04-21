class IngestService:
    async def ingest_file(self, path: str) -> None:
        raise NotImplementedError

    async def ingest_note(self, text: str) -> None:
        raise NotImplementedError
