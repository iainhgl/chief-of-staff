import uuid
from pathlib import Path

from conftest import make_test_config

from cos.services.ingestion import SUPPORTED_SUFFIXES, IngestService


async def test_ingest_file_markdown_returns_result(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "notes.md"
    source_path.write_text("# Notes\n\nOperational update", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    result = await service.ingest_file(str(source_path))

    assert str(uuid.UUID(result.document_id)) == result.document_id
    assert result.chunk_count >= 1
    assert result.source_path == str(source_path.resolve())


async def test_ingest_folder_processes_supported_files(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    first = folder / "alpha.md"
    second = folder / "beta.txt"
    first.write_text("Alpha document", encoding="utf-8")
    second.write_text("Beta document", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    results = []
    for file_path in sorted(folder.iterdir()):
        if file_path.suffix.lower() in SUPPORTED_SUFFIXES:
            results.append(await service.ingest_file(str(file_path)))

    assert [Path(result.source_path).name for result in results] == [
        "alpha.md",
        "beta.txt",
    ]
    assert all(result.chunk_count >= 1 for result in results)


async def test_ingest_folder_skips_unsupported_files(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    supported = folder / "alpha.md"
    unsupported = folder / "report.xlsx"
    supported.write_text("Alpha document", encoding="utf-8")
    unsupported.write_text("spreadsheet data", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    results = []
    skipped = []
    for file_path in sorted(folder.iterdir()):
        if file_path.suffix.lower() in SUPPORTED_SUFFIXES:
            results.append(await service.ingest_file(str(file_path)))
        else:
            skipped.append(file_path.name)

    assert [Path(result.source_path).name for result in results] == ["alpha.md"]
    assert skipped == ["report.xlsx"]
