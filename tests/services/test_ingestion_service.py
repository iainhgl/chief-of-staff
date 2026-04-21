import pytest

from cos.services.ingestion import IngestService


@pytest.mark.asyncio
async def test_ingest_file_not_implemented() -> None:
    svc = IngestService()
    with pytest.raises(NotImplementedError):
        await svc.ingest_file("/tmp/test.pdf")


@pytest.mark.asyncio
async def test_ingest_note_not_implemented() -> None:
    svc = IngestService()
    with pytest.raises(NotImplementedError):
        await svc.ingest_note("meeting notes")
