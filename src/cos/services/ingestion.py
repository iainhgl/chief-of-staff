from dataclasses import dataclass
from pathlib import Path

import psycopg

from cos.config import CosConfig
from cos.ingestion.extractor import SUPPORTED_DIRECT_SUFFIXES, SUPPORTED_TIKA_SUFFIXES
from cos.ingestion.pipeline import run_pipeline

SUPPORTED_SUFFIXES = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES


@dataclass
class IngestResult:
    document_id: str
    chunk_count: int
    source_path: str


class IngestService:
    def __init__(self, config: CosConfig) -> None:
        self._config = config

    async def ingest_file(self, path: str) -> IngestResult:
        source_path = Path(path).resolve()
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            result = await run_pipeline(source_path, self._config, conn)

        return IngestResult(
            document_id=result.document_id,
            chunk_count=result.chunk_count,
            source_path=str(source_path),
        )

    async def ingest_note(self, text: str) -> IngestResult:
        raise NotImplementedError
