import pytest

from cos.services.retrieval import RetrievalService


@pytest.mark.asyncio
async def test_query_not_implemented() -> None:
    svc = RetrievalService()
    with pytest.raises(NotImplementedError):
        await svc.query("what is the budget?", role_pack=None)
