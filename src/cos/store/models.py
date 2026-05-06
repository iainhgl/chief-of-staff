from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DocumentRecord:
    id: str = ""
    source_path: str = ""
    file_hash: str = ""
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_version: int = 1
    status: str = "active"


@dataclass
class ChunkRecord:
    id: str = ""
    document_id: str = ""
    content: str = ""
    chunk_index: int = 0
    token_count: int = 0


@dataclass
class EmbeddingRecord:
    id: str = ""
    chunk_id: str = ""
    vector: list[float] = field(default_factory=list)
    model: str = ""
    provider: str = ""


@dataclass
class DocumentVersion:
    id: str = ""
    document_id: str = ""
    version: int = 0
    content_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ProvenanceRecord is not a database table.
# Provenance is captured in document_versions.
# Retained as a future abstraction placeholder.
@dataclass
class ProvenanceRecord:
    id: str = ""
    document_id: str = ""
    source: str = ""
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ContentBlobRecord:
    id: str = ""
    sha256: str = ""
    byte_size: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SourceRecord:
    id: str = ""
    source_type: str = ""
    source_locator: str = ""
    source_alias: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SourceVersionRecord:
    id: str = ""
    source_id: str = ""
    document_version_id: str = ""
    content_blob_id: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DocumentSummary:
    id: str = ""
    source_path: str = ""
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_version: int = 1
    chunk_count: int = 0


@dataclass
class VersionSummary:
    version_number: int = 1
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    file_hash: str = ""
