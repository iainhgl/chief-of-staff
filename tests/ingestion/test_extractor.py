import pytest

from cos.ingestion.extractor import extract


@pytest.mark.asyncio
async def test_extract_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await extract("file:///test.pdf")
