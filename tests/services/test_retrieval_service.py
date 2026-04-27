from pathlib import Path
from unittest.mock import MagicMock

import pytest
from conftest import make_test_config

from cos.services.retrieval import RetrievalService


@pytest.mark.asyncio
async def test_query_not_implemented(tmp_path: Path) -> None:
    svc = RetrievalService(config=make_test_config(tmp_path), pool=MagicMock())
    with pytest.raises(NotImplementedError):
        await svc.query("what is the budget?", role_pack=None)
