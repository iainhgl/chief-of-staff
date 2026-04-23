"""Read-only service for document provenance queries."""

import uuid as _uuid

import psycopg

from cos.config import CosConfig
from cos.store.db import list_document_versions, list_documents
from cos.store.models import DocumentSummary, VersionSummary

__all__ = ["DocumentSummary", "ProvenanceService", "VersionSummary"]


class ProvenanceService:
    def __init__(self, config: CosConfig) -> None:
        self._config = config

    async def list_documents(self) -> list[DocumentSummary]:
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            return await list_documents(conn)

    async def list_document_versions(self, document_id: str) -> list[VersionSummary]:
        try:
            _uuid.UUID(document_id)
        except ValueError:
            return []
        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            return await list_document_versions(conn, document_id)
