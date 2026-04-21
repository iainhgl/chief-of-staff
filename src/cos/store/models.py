from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class DocumentRecord:
    id: str = ""
    source_uri: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChunkRecord:
    id: str = ""
    document_id: str = ""
    content: str = ""
    chunk_index: int = 0


@dataclass
class EmbeddingRecord:
    id: str = ""
    chunk_id: str = ""
    vector: list[float] = field(default_factory=list)


@dataclass
class DocumentVersion:
    id: str = ""
    document_id: str = ""
    version: int = 0
    content_hash: str = ""


@dataclass
class ProvenanceRecord:
    id: str = ""
    document_id: str = ""
    source: str = ""
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
