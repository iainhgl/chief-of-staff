import pytest

from cos.retrieval.search import hybrid_search


@pytest.mark.asyncio
async def test_hybrid_search_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await hybrid_search("query", config=None)
