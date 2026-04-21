import pytest

from cos.ingestion.chunker import chunk


def test_chunk_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        chunk("some text")
