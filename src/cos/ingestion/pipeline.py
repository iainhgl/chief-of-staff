"""Ingestion pipeline orchestrator."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.ingestion.chunker import chunk
from cos.ingestion.embedder import VoyageTransportConfig, embed
from cos.ingestion.extractor import extract
from cos.ingestion.identity import IngestOutcome, check_canonical_identity
from cos.store.db import (
    link_new_source_to_existing_blob,
    store_document_canonical,
)
from cos.store.models import ChunkRecord, EmbeddingRecord


@dataclass
class PipelineResult:
    document_id: str
    chunk_count: int
    outcome: IngestOutcome
    message: str


async def run_pipeline_from_source(
    staged_path: Path,
    source_type: str,
    source_locator: str,
    source_alias: str,
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> PipelineResult:
    """Source-aware ingest core. Uses source_* fields for provenance identity."""
    source_bytes = staged_path.read_bytes()
    file_hash = hashlib.sha256(source_bytes).hexdigest()
    byte_size = len(source_bytes)

    logging.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "component": "ingestion",
                "message": "pipeline start",
                "source_locator": source_locator,
            }
        )
    )

    identity = await check_canonical_identity(
        conn,
        file_hash,
        source_type,
        source_locator,
    )
    if identity.outcome is IngestOutcome.UNCHANGED:
        if identity.document_id is None:
            raise RuntimeError(
                "Canonical identity returned unchanged without document_id"
            )
        logging.info(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "component": "ingestion",
                    "message": identity.message,
                    "document_id": identity.document_id,
                    "chunk_count": 0,
                    "outcome": identity.outcome.value,
                }
            )
        )
        return PipelineResult(
            document_id=identity.document_id,
            chunk_count=0,
            outcome=identity.outcome,
            message=identity.message,
        )

    if identity.outcome is IngestOutcome.NEW_SOURCE_KNOWN_CONTENT:
        document_id = await link_new_source_to_existing_blob(
            conn,
            file_hash,
            source_type,
            source_locator,
            source_alias,
        )
        logging.info(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "component": "ingestion",
                    "message": identity.message,
                    "document_id": document_id,
                    "chunk_count": 0,
                    "outcome": identity.outcome.value,
                }
            )
        )
        return PipelineResult(
            document_id=document_id,
            chunk_count=0,
            outcome=identity.outcome,
            message=identity.message,
        )

    extraction = await extract(
        staged_path,
        tika_url=config.tika.url,
        originals_dir=config.storage.originals_dir,
        markdown_dir=config.storage.markdown_dir,
    )
    chunks = chunk(
        extraction.text,
        chunk_size=config.chunking.chunk_size,
        chunk_overlap=config.chunking.chunk_overlap,
    )

    api_key = (
        config.embedding.api_key.get_secret_value()
        if config.embedding.api_key is not None
        else ""
    )
    if not api_key:
        raise ValueError(
            f"embedding.api_key is required for provider "
            f"'{config.embedding.provider}' but is not set in config.yaml"
        )
    embedding_results = await embed(
        [item.text for item in chunks],
        provider=config.embedding.provider,
        model=config.embedding.model,
        api_key=api_key,
        transport=VoyageTransportConfig(
            ca_bundle_path=config.embedding.ca_bundle_path,
            proxy_url=config.embedding.proxy_url,
            trust_env=config.embedding.trust_env,
        ),
    )

    chunk_records = [
        ChunkRecord(
            content=item.text,
            chunk_index=item.chunk_index,
            token_count=item.token_count,
        )
        for item in chunks
    ]
    embedding_records = [
        EmbeddingRecord(
            vector=item.vector,
            model=item.model,
            provider=item.provider,
        )
        for item in embedding_results
    ]
    document_id = await store_document_canonical(
        conn,
        source_path=source_locator,
        sha256=file_hash,
        byte_size=byte_size,
        source_type=source_type,
        source_locator=source_locator,
        source_alias=source_alias,
        chunks=chunk_records,
        embeddings=embedding_records,
    )

    logging.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "component": "ingestion",
                "message": "pipeline complete",
                "document_id": document_id,
                "chunk_count": len(chunks),
                "outcome": identity.outcome.value,
            }
        )
    )
    return PipelineResult(
        document_id=document_id,
        chunk_count=len(chunks),
        outcome=identity.outcome,
        message=identity.message,
    )


async def run_pipeline(
    source_path: Path,
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> PipelineResult:
    """CLI-facing ingest. Thin wrapper over run_pipeline_from_source."""
    return await run_pipeline_from_source(
        staged_path=source_path,
        source_type="file",
        source_locator=str(source_path),
        source_alias=source_path.name,
        config=config,
        conn=conn,
    )
