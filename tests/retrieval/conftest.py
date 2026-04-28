from collections.abc import AsyncIterator
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import psycopg
import pytest

from cos.ingestion.embedder import EmbeddingResult

_ROOT_CONFTEST_PATH = Path(__file__).resolve().parents[1] / "conftest.py"
_ROOT_CONFTEST_SPEC = spec_from_file_location("root_test_conftest", _ROOT_CONFTEST_PATH)
if _ROOT_CONFTEST_SPEC is None or _ROOT_CONFTEST_SPEC.loader is None:
    raise RuntimeError(f"Unable to load root conftest from {_ROOT_CONFTEST_PATH}")

_ROOT_CONFTEST_MODULE = module_from_spec(_ROOT_CONFTEST_SPEC)
_ROOT_CONFTEST_SPEC.loader.exec_module(_ROOT_CONFTEST_MODULE)
TEST_DSN: str = _ROOT_CONFTEST_MODULE.TEST_DSN
make_test_config = _ROOT_CONFTEST_MODULE.make_test_config


@pytest.fixture(autouse=True)
async def clean_tables(migrated_db: None) -> AsyncIterator[None]:
    yield
    async with await psycopg.AsyncConnection.connect(TEST_DSN, autocommit=True) as conn:
        await conn.execute(
            "TRUNCATE embeddings, chunks, document_versions, documents "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def mock_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_embed(
        chunks: list[str],
        provider: str,
        model: str,
        api_key: str,
        transport=None,
    ) -> list[EmbeddingResult]:
        del api_key, transport
        return [
            EmbeddingResult(
                vector=[float(index) / 100 for index in range(1024)],
                model=model,
                provider=provider,
            )
            for _ in chunks
        ]

    monkeypatch.setattr("cos.retrieval.search.embed", _fake_embed)
