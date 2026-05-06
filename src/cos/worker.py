"""Long-running background ingest worker."""
import asyncio
import json
import logging
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.services.jobs import process_next_ingest_job
from cos.store.db import requeue_stale_jobs

_IDLE_SLEEP_SECONDS = 5.0
_STALE_JOB_TIMEOUT_SECONDS = 300


async def recover_stale_jobs(conn: psycopg.AsyncConnection[Any]) -> int:
    """Requeue jobs that were left running after a crash. Returns count requeued."""
    return await requeue_stale_jobs(conn, older_than_seconds=_STALE_JOB_TIMEOUT_SECONDS)


async def run_once(dsn: str, config: CosConfig) -> bool:
    """Claim and process one ingest job. Returns True if a job was processed.

    Test-friendly single-iteration mode — does not run startup recovery or sleep.
    """
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        return await process_next_ingest_job(conn, config)


async def _run_loop(dsn: str, config: CosConfig) -> None:
    logging.info(
        json.dumps(
            {
                "component": "ingestion",
                "message": "worker starting",
            }
        )
    )

    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        stale_count = await recover_stale_jobs(conn)

    if stale_count > 0:
        logging.info(
            json.dumps(
                {
                    "component": "ingestion",
                    "message": "requeued stale jobs on startup",
                    "count": stale_count,
                }
            )
        )

    while True:
        async with await psycopg.AsyncConnection.connect(dsn) as conn:
            processed = await process_next_ingest_job(conn, config)
        if not processed:
            await asyncio.sleep(_IDLE_SLEEP_SECONDS)


def run() -> None:
    """Entry point for the cos-worker script."""
    config = CosConfig.load()
    asyncio.run(_run_loop(config.database.libpq_dsn, config))
