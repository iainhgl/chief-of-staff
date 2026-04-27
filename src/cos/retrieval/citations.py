"""Citation formatting helpers for retrieved chunks."""

import uuid
from dataclasses import dataclass


@dataclass
class CitedChunk:
    content: str
    source_document_id: str  # UUID-format string
    source_path: str
    chunk_index: int
    score: float

    def __post_init__(self) -> None:
        uuid.UUID(self.source_document_id)


CitedResults = list[CitedChunk]


@dataclass
class CitedResponse:
    answer: str | None
    citations: CitedResults


def format_citations(results: CitedResults) -> str:
    return "\n".join(
        f"[{index}] {chunk.source_path} "
        f"(chunk {chunk.chunk_index}, score {chunk.score:.3f})"
        for index, chunk in enumerate(results, start=1)
    )
