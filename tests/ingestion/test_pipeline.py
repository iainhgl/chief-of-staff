import pytest

from cos.ingestion.pipeline import run_pipeline


@pytest.mark.asyncio
async def test_run_pipeline_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await run_pipeline("file:///test.pdf")
