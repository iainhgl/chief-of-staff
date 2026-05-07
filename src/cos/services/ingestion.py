import hashlib
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


def _hashed_slug(value: str, prefix: str, max_len: int = 80) -> str:
    slug = _safe_slug(value, max_len=max_len)
    if slug:
        return slug

    prefix_slug = _safe_slug(prefix, max_len=max_len) or "value"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    available = max_len - len(prefix_slug) - 1
    if available <= 0:
        return prefix_slug[:max_len]
    return f"{prefix_slug}-{digest[:available]}"


def _validate_metadata(metadata: object | None) -> dict[str, str]:
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object when provided.")

    validated: dict[str, str] = {}
    for field_name in ("title", "external_id", "client"):
        raw_value = metadata.get(field_name)
        if raw_value is None:
            continue
        if not isinstance(raw_value, str):
            raise ValueError(f"metadata.{field_name} must be a string when provided.")
        value = raw_value.strip()
        if value:
            validated[field_name] = value
    return validated


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

        meta = _validate_metadata(metadata)
        title = meta.get("title", "")
        external_id = meta.get("external_id", "")
        client = meta.get("client", "")
        title_slug = _safe_slug(title) if title else ""
        external_id_slug = (
            _hashed_slug(external_id, prefix="external-id") if external_id else ""
        )
        client_slug = _hashed_slug(client, prefix="client") if client else ""

        # Build source_locator from synthetic source metadata, not from content hash
        if external_id:
            prefix = f"{client_slug}/" if client else "mcp/"
            source_locator = f"mcp_note://{prefix}{external_id_slug}"
        else:
            source_locator = f"mcp_note://mcp/{uuid.uuid4()}"

        # Build human-readable source_alias ending in .md
        if title_slug:
            source_alias = f"{title_slug}.md"
        elif external_id:
            source_alias = f"{external_id_slug}.md"
        else:
            source_alias = f"mcp-note-{uuid.uuid4().hex[:8]}.md"

        mcp_cfg = self._config.mcp_note
        staging_dir = (
            mcp_cfg.staging_dir if mcp_cfg else Path("/data/connector-staging/mcp")
        )
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Deterministic file name when external_id supplied (enables stable retry path)
        if external_id:
            slug = f"{client_slug}-{external_id_slug}" if client else external_id_slug
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
