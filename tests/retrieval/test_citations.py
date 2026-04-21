import pytest

from cos.retrieval.citations import format_citations


def test_format_citations_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        format_citations([])
