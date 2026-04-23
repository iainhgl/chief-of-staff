import filecmp
from pathlib import Path

import pytest

from cos.ingestion.extractor import ExtractionError, _extract_via_tika, extract


async def test_extract_markdown_direct(tmp_path: Path) -> None:
    src = tmp_path / "test.md"
    src.write_text("# Hello\nWorld", encoding="utf-8")

    result = await extract(src, "http://unused", tmp_path / "orig", tmp_path / "md")

    assert result.text == "# Hello\nWorld"
    assert result.extraction_method == "direct"
    assert result.content_type == "text/markdown"


async def test_extract_txt_direct(tmp_path: Path) -> None:
    src = tmp_path / "test.txt"
    src.write_text("Hello\nWorld", encoding="utf-8")

    result = await extract(src, "http://unused", tmp_path / "orig", tmp_path / "md")

    assert result.text == "Hello\nWorld"
    assert result.extraction_method == "direct"
    assert result.content_type == "text/plain"


async def test_original_written_byte_for_byte(tmp_path: Path) -> None:
    src = tmp_path / "doc.md"
    src.write_bytes(b"# Test\n")
    originals_dir = tmp_path / "orig"

    await extract(src, "http://unused", originals_dir, tmp_path / "md")

    assert filecmp.cmp(src, originals_dir / "doc.md", shallow=False)


async def test_markdown_copy_written(tmp_path: Path) -> None:
    src = tmp_path / "test.txt"
    src.write_text("Hello markdown copy", encoding="utf-8")
    markdown_dir = tmp_path / "md"

    await extract(src, "http://unused", tmp_path / "orig", markdown_dir)

    markdown_copy = markdown_dir / "test.md"
    assert markdown_copy.exists()
    assert markdown_copy.read_text(encoding="utf-8") == "Hello markdown copy"


async def test_unsupported_format_raises(tmp_path: Path) -> None:
    src = tmp_path / "spreadsheet.xlsx"
    src.write_bytes(b"fake xlsx")
    originals_dir = tmp_path / "orig"

    with pytest.raises(ExtractionError, match="Unsupported file format"):
        await extract(src, "http://unused", originals_dir, tmp_path / "md")

    assert not list(originals_dir.iterdir())
    assert not list((tmp_path / "md").iterdir())


async def test_tika_unavailable_raises(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 fake")

    with pytest.raises(ExtractionError, match="Tika unavailable"):
        await _extract_via_tika(src, "http://localhost:19998")


async def test_extract_pdf_tika_failure_no_markdown_written(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    markdown_dir = tmp_path / "md"

    with pytest.raises(ExtractionError, match="Tika unavailable"):
        await extract(src, "http://localhost:19998", tmp_path / "orig", markdown_dir)

    assert not list(markdown_dir.iterdir())


async def test_extract_docx_routes_via_tika(tmp_path: Path) -> None:
    src = tmp_path / "report.docx"
    src.write_bytes(b"PK fake docx")

    with pytest.raises(ExtractionError, match="Tika unavailable"):
        await extract(src, "http://localhost:19998", tmp_path / "orig", tmp_path / "md")


@pytest.mark.integration
async def test_extract_pdf_via_tika(tmp_path: Path) -> None:
    src = tmp_path / "test.pdf"
    src.write_bytes(
        b"%PDF-1.1\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 18 Tf 72 72 Td (Hello from PDF) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n"
        b"0000000010 00000 n \n0000000053 00000 n \n0000000110 00000 n \n"
        b"0000000237 00000 n \n0000000332 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n402\n%%EOF\n"
    )

    try:
        result = await extract(
            src,
            "http://localhost:9998",
            tmp_path / "orig",
            tmp_path / "md",
        )
    except ExtractionError as exc:
        if "Tika unavailable" in str(exc):
            pytest.skip("Tika is not running on http://localhost:9998")
        raise

    assert result.text.strip()
    assert result.extraction_method == "tika"
