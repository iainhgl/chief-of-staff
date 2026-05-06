"""Public orchestration layer for background ingest jobs."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.ingestion.pipeline import run_pipeline_from_source
from cos.store.db import (
    claim_next_job,
    enqueue_job,
    mark_job_retryable_failure,
    mark_job_succeeded,
    mark_job_terminal_failure,
)
from cos.store.models import IngestJobPayload, JobRecord

_REQUIRED_INGEST_PAYLOAD_FIELDS = (
    "staged_path",
    "source_type",
    "source_locator",
    "source_alias",
)


async def submit_ingest_job(
    conn: psycopg.AsyncConnection[Any],
    staged_path: str,
    source_type: str,
    source_locator: str,
    source_alias: str,
    metadata: dict[str, Any] | None = None,
) -> JobRecord:
    """Enqueue an ingest job. Connectors call this instead of the pipeline directly."""
    payload: dict[str, Any] = {
        "staged_path": staged_path,
        "source_type": source_type,
        "source_locator": source_locator,
        "source_alias": source_alias,
        "metadata": metadata or {},
    }
    return await enqueue_job(conn, "ingest", payload)


def _hydrate_ingest_payload(job: JobRecord) -> IngestJobPayload:
    missing = [
        field for field in _REQUIRED_INGEST_PAYLOAD_FIELDS if field not in job.payload
    ]
    if missing:
        missing_fields = ", ".join(missing)
        raise ValueError(
            f"ingest job {job.id} missing payload fields: {missing_fields}"
        )

    metadata = job.payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError(f"ingest job {job.id} metadata must be an object")

    values: dict[str, str] = {}
    for field in _REQUIRED_INGEST_PAYLOAD_FIELDS:
        value = job.payload[field]
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"ingest job {job.id} field {field!r} must be a non-empty string"
            )
        values[field] = value

    return IngestJobPayload(
        staged_path=values["staged_path"],
        source_type=values["source_type"],
        source_locator=values["source_locator"],
        source_alias=values["source_alias"],
        metadata=metadata,
    )


async def process_next_ingest_job(
    dsn: str,
    config: CosConfig,
) -> bool:
    """Claim and process one ingest job. Returns True if a job was processed."""
    async with await psycopg.AsyncConnection.connect(dsn) as claim_conn:
        job = await claim_next_job(claim_conn, "ingest")
    if job is None:
        return False

    try:
        payload = _hydrate_ingest_payload(job)
        async with await psycopg.AsyncConnection.connect(dsn) as process_conn:
            result = await run_pipeline_from_source(
                staged_path=Path(payload.staged_path),
                source_type=payload.source_type,
                source_locator=payload.source_locator,
                source_alias=payload.source_alias,
                config=config,
                conn=process_conn,
            )
        async with await psycopg.AsyncConnection.connect(dsn) as update_conn:
            await mark_job_succeeded(update_conn, job.id)
        logging.info(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "component": "ingestion",
                    "message": "job succeeded",
                    "job_id": job.id,
                    "outcome": result.outcome.value,
                }
            )
        )
    except Exception as exc:
        error_str = str(exc)
        if job.attempt_count >= job.max_attempts:
            async with await psycopg.AsyncConnection.connect(dsn) as update_conn:
                await mark_job_terminal_failure(update_conn, job.id, error_str)
            logging.error(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "ERROR",
                        "component": "ingestion",
                        "message": "job failed terminally",
                        "job_id": job.id,
                        "error": error_str,
                    }
                )
            )
        else:
            async with await psycopg.AsyncConnection.connect(dsn) as update_conn:
                await mark_job_retryable_failure(update_conn, job.id, error_str)
            logging.warning(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "WARNING",
                        "component": "ingestion",
                        "message": "job will retry",
                        "job_id": job.id,
                        "error": error_str,
                        "attempt_count": job.attempt_count,
                    }
                )
            )

    return True
