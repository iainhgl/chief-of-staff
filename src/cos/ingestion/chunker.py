"""Token-based text chunking for ingestion."""

from dataclasses import dataclass

import tiktoken

DEFAULT_ENCODING = "cl100k_base"


@dataclass
class Chunk:
    text: str
    chunk_index: int
    token_count: int


def chunk(
    text: str,
    chunk_size: int = 1024,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    if not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
    tokens = encoding.encode(text)
    step = chunk_size - chunk_overlap

    chunks: list[Chunk] = []
    for start in range(0, len(tokens), step):
        remaining = len(tokens) - start
        if start > 0 and remaining <= chunk_overlap:
            break

        chunk_tokens = tokens[start : start + chunk_size]
        chunks.append(
            Chunk(
                text=encoding.decode(chunk_tokens),
                chunk_index=len(chunks),
                token_count=len(chunk_tokens),
            )
        )

    return chunks
