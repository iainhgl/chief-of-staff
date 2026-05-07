import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg

from cos.config import CosConfig
from cos.ingestion.extractor import SUPPORTED_DIRECT_SUFFIXES, SUPPORTED_TIKA_SUFFIXES
from cos.ingestion.pipeline import run_pipeline, run_pipeline_from_source
from cos.retrieval.near_duplicate import find_near_duplicate

SUPPORTED_SUFFIXES = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES

_SAFE_RE = re.compile(r"[^\w\-]")


def _safe_slug(value: str, max_len: int = 80) -> str:
    return _SAFE_RE.sub("-", value).strip("-")[:max_len]


@dataclass
class IngestResult:
    document_id: str
    chunk_count: int
    source_path: str
    outcome: str
    message: str
    source_alias: str = field(default="")
    source_locator: str = field(default="")
    warning: str | None = field(default=None)


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
            outcome=result.outcome.value,
            message=result.message,
        )

    async def ingest_note(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> IngestResult:
        if not text or not text.strip():
            raise ValueError("Note content must not be empty or whitespace-only.")

        meta = metadata or {}
        title = str(meta["title"]) if meta.get("title") else ""
        external_id = str(meta["external_id"]) if meta.get("external_id") else ""
        client = str(meta["client"]) if meta.get("client") else ""

        # Build source_locator from synthetic source metadata, not from content hash
        if external_id:
            prefix = f"{_safe_slug(client)}/" if client else "mcp/"
            source_locator = f"mcp_note://{prefix}{_safe_slug(external_id)}"
        else:
            source_locator = f"mcp_note://mcp/{uuid.uuid4()}"

        # Build human-readable source_alias ending in .md
        if title:
            source_alias = f"{_safe_slug(title)}.md"
        elif external_id:
            source_alias = f"{_safe_slug(external_id)}.md"
        else:
            source_alias = f"mcp-note-{uuid.uuid4().hex[:8]}.md"

        mcp_cfg = self._config.mcp_note
        staging_dir = (
            mcp_cfg.staging_dir if mcp_cfg else Path("/data/connector-staging/mcp")
        )
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Deterministic file name when external_id supplied (enables stable retry path)
        if external_id:
            slug = (
                f"{_safe_slug(client)}-{_safe_slug(external_id)}"
                if client
                else _safe_slug(external_id)
            )
            staged_path = staging_dir / f"{slug}.md"
        else:
            staged_path = staging_dir / source_alias

        staged_path.write_text(text, encoding="utf-8")

        async with await psycopg.AsyncConnection.connect(
            self._config.database.libpq_dsn
        ) as conn:
            result = await run_pipeline_from_source(
                staged_path=staged_path,
                source_type="mcp_note",
                source_locator=source_locator,
                source_alias=source_alias,
                config=self._config,
                conn=conn,
            )

            warning: str | None = None
            if result.outcome.value in ("new_content", "changed_content"):
                threshold = mcp_cfg.near_duplicate_threshold if mcp_cfg else 0.95
                near_dup = await find_near_duplicate(
                    text=text,
                    exclude_document_id=result.document_id,
                    conn=conn,
                    config=self._config,
                    threshold=threshold,
                )
                if near_dup is not None:
                    warning = (
                        f"Semantically similar content already exists: "
                        f"'{near_dup['source_alias']}' "
                        f"(similarity: {float(near_dup['similarity']):.2f})"
                    )

        return IngestResult(
            document_id=result.document_id,
            chunk_count=result.chunk_count,
            source_path=str(staged_path),
            outcome=result.outcome.value,
            message=result.message,
            source_alias=source_alias,
            source_locator=source_locator,
            warning=warning,
        )
