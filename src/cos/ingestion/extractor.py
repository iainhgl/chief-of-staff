"""Document extraction via Tika and direct file reads."""

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from tika_client import AsyncTikaClient
from tika_client.data_models import DublinCoreKey


class ExtractionError(RuntimeError):
    pass


@dataclass
class ExtractionResult:
    text: str
    content_type: str
    extraction_method: str
    title: str | None = None
    author: str | None = None
    original_path: Path = field(default_factory=Path)
    markdown_path: Path = field(default_factory=Path)


SUPPORTED_DIRECT_SUFFIXES: frozenset[str] = frozenset({".md", ".txt"})
SUPPORTED_TIKA_SUFFIXES: frozenset[str] = frozenset({".pdf", ".docx"})
WORDPROCESSINGML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _extract_docx_xml(source_path: Path) -> str:
    """Extract plain text directly from a DOCX package as a fallback."""
    try:
        with ZipFile(source_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError, OSError) as exc:
        raise ExtractionError(
            f"DOCX fallback extraction failed for {source_path.name}: {exc}"
        ) from exc

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise ExtractionError(
            f"DOCX fallback extraction failed for {source_path.name}: {exc}"
        ) from exc

    namespace = {"w": WORDPROCESSINGML_NS}
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:body/w:p", namespace):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{WORDPROCESSINGML_NS}}}t":
                parts.append(node.text or "")
            elif node.tag == f"{{{WORDPROCESSINGML_NS}}}tab":
                parts.append("\t")
            elif node.tag in {
                f"{{{WORDPROCESSINGML_NS}}}br",
                f"{{{WORDPROCESSINGML_NS}}}cr",
            }:
                parts.append("\n")

        paragraph_text = "".join(parts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)

    text = "\n\n".join(paragraphs).strip()
    if not text:
        raise ExtractionError(f"DOCX fallback returned no content for {source_path.name}")

    return text


async def _extract_via_tika(
    source_path: Path,
    tika_url: str,
) -> tuple[str, str | None, str | None, str]:
    """Return extracted text and selected metadata from Tika."""
    try:
        async with AsyncTikaClient(tika_url) as client:
            response = await client.tika.as_text.from_file(source_path)
    except Exception as exc:
        raise ExtractionError(f"Tika unavailable at {tika_url}: {exc}") from exc

    text = response.content
    if not text or not text.strip():
        if source_path.suffix.lower() == ".docx":
            text = _extract_docx_xml(source_path)
        else:
            raise ExtractionError(f"Tika returned no content for {source_path.name}")

    title = response.title
    author = response.data.get(DublinCoreKey.Creator)
    content_type = response.type or "application/octet-stream"

    return text, title, author, content_type


async def extract(
    source_path: Path,
    tika_url: str,
    originals_dir: Path,
    markdown_dir: Path,
) -> ExtractionResult:
    originals_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix.lower()
    supported_suffixes = SUPPORTED_DIRECT_SUFFIXES | SUPPORTED_TIKA_SUFFIXES
    if suffix not in supported_suffixes:
        raise ExtractionError(f"Unsupported file format: {source_path.suffix!r}")

    original_dest = originals_dir / source_path.name
    shutil.copy2(source_path, original_dest)

    if suffix in SUPPORTED_DIRECT_SUFFIXES:
        try:
            text = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ExtractionError(
                f"Cannot decode {source_path.name} as UTF-8: {exc}"
            ) from exc
        title = None
        author = None
        content_type = "text/markdown" if suffix == ".md" else "text/plain"
        extraction_method = "direct"
    else:
        text, title, author, content_type = await _extract_via_tika(
            source_path,
            tika_url,
        )
        extraction_method = "tika"

    markdown_dest = markdown_dir / f"{source_path.stem}.md"
    markdown_dest.write_text(text, encoding="utf-8")

    return ExtractionResult(
        text=text,
        content_type=content_type,
        extraction_method=extraction_method,
        title=title,
        author=author,
        original_path=original_dest,
        markdown_path=markdown_dest,
    )
