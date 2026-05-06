"""Canonical identity decision engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

import psycopg

from cos.store.db import (
    find_content_blob_by_sha256,
    find_source,
    find_source_version_for_blob,
)


class IngestOutcome(str, enum.Enum):
    NEW_CONTENT = "new_content"
    CHANGED_CONTENT = "changed_content"
    NEW_SOURCE_KNOWN_CONTENT = "new_source_known_content"
    UNCHANGED = "unchanged"


@dataclass
class IdentityCheckResult:
    outcome: IngestOutcome
    document_id: str | None
    document_version_id: str | None
    content_blob_id: str | None
    source_id: str | None
    message: str


async def check_canonical_identity(
    conn: psycopg.AsyncConnection[Any],
    sha256: str,
    source_type: str,
    source_locator: str,
) -> IdentityCheckResult:
    existing_blob = await find_content_blob_by_sha256(conn, sha256)

    if existing_blob is not None:
        existing_source = await find_source(conn, source_type, source_locator)
        if existing_source is not None:
            existing_source_version = await find_source_version_for_blob(
                conn,
                existing_source.id,
                existing_blob.id,
            )
            if existing_source_version is not None:
                result = await conn.execute(
                    "SELECT document_id::text FROM document_versions "
                    "WHERE id = %s::uuid",
                    (existing_source_version.document_version_id,),
                )
                row = await result.fetchone()
                document_id = row[0] if row is not None else None
                return IdentityCheckResult(
                    outcome=IngestOutcome.UNCHANGED,
                    document_id=document_id,
                    document_version_id=existing_source_version.document_version_id,
                    content_blob_id=existing_blob.id,
                    source_id=existing_source.id,
                    message="Content unchanged - no new version or embeddings created.",
                )

        return IdentityCheckResult(
            outcome=IngestOutcome.NEW_SOURCE_KNOWN_CONTENT,
            document_id=None,
            document_version_id=None,
            content_blob_id=existing_blob.id,
            source_id=existing_source.id if existing_source is not None else None,
            message=(
                "Known content from a new source - provenance will be linked "
                "without reprocessing."
            ),
        )

    existing_source = await find_source(conn, source_type, source_locator)
    if existing_source is not None:
        return IdentityCheckResult(
            outcome=IngestOutcome.CHANGED_CONTENT,
            document_id=None,
            document_version_id=None,
            content_blob_id=None,
            source_id=existing_source.id,
            message="Source content changed - a new canonical version will be created.",
        )

    return IdentityCheckResult(
        outcome=IngestOutcome.NEW_CONTENT,
        document_id=None,
        document_version_id=None,
        content_blob_id=None,
        source_id=None,
        message="New content detected - full ingest will proceed.",
    )
