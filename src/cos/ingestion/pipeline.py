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
from cos.store.db import store_document
from cos.store.models import ChunkRecord, EmbeddingRecord


@dataclass
class PipelineResult:
    document_id: str
    chunk_count: int


async def run_pipeline(
    source_path: Path,
    config: CosConfig,
    conn: psycopg.AsyncConnection[Any],
) -> PipelineResult:
    logging.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "component": "ingestion",
                "message": "pipeline start",
                "source_path": str(source_path),
            }
        )
    )

    file_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    extraction = await extract(
        source_path,
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
    document_id = await store_document(
        conn,
        source_path=str(source_path),
        file_hash=file_hash,
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
            }
        )
    )
    return PipelineResult(document_id=document_id, chunk_count=len(chunks))
