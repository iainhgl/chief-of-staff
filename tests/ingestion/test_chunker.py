import tiktoken

from cos.ingestion.chunker import DEFAULT_ENCODING, chunk


def _text_with_exact_token_count(token_count: int) -> str:
    encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
    text = ""
    while len(encoding.encode(text)) < token_count:
        text += " hello"
    return encoding.decode(encoding.encode(text)[:token_count])


def test_chunk_short_document_single_chunk() -> None:
    text = " ".join(f"word{i}" for i in range(50))

    chunks = chunk(text)

    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_index == 0
    assert chunks[0].token_count > 0


def test_chunk_returns_chunk_index_and_token_count() -> None:
    text = _text_with_exact_token_count(150)

    chunks = chunk(text, chunk_size=40, chunk_overlap=10)

    assert len(chunks) >= 2
    for index, item in enumerate(chunks):
        assert item.chunk_index == index
        assert item.token_count > 0


def test_chunk_overlap_content() -> None:
    encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
    text = _text_with_exact_token_count(80)

    chunks = chunk(text, chunk_size=30, chunk_overlap=5)

    assert len(chunks) >= 2
    first_tokens = encoding.encode(chunks[0].text)
    second_tokens = encoding.encode(chunks[1].text)
    assert first_tokens[-5:] == second_tokens[:5]


def test_chunk_empty_text_returns_empty_list() -> None:
    assert chunk("") == []


def test_chunk_respects_custom_size() -> None:
    text = _text_with_exact_token_count(90)

    chunks = chunk(text, chunk_size=20, chunk_overlap=5)

    assert len(chunks) >= 2
    assert all(item.token_count <= 20 for item in chunks)


def test_chunk_no_near_empty_tail() -> None:
    text = _text_with_exact_token_count(35)

    chunks = chunk(text, chunk_size=20, chunk_overlap=5)

    assert len(chunks) == 2
    assert chunks[-1].token_count > 5
