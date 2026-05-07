import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from conftest import make_test_config

from cos.config import McpNoteIngestConfig
from cos.services.ingestion import SUPPORTED_SUFFIXES, IngestService


def _make_note_config(tmp_path: Path):
    return make_test_config(tmp_path).model_copy(
        update={"mcp_note": McpNoteIngestConfig(staging_dir=tmp_path / "mcp-staging")}
    )


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
    assert result.outcome == "new_content"
    assert "full ingest" in result.message.lower()


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


async def test_ingest_file_unchanged_returns_unchanged_outcome(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "stable.md"
    source_path.write_text("Stable document content", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    await service.ingest_file(str(source_path))
    second = await service.ingest_file(str(source_path))

    assert second.outcome == "unchanged"
    assert second.chunk_count == 0
    assert "unchanged" in second.message.lower()


async def test_ingest_file_changed_returns_changed_content_outcome(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    source_path = tmp_path / "changing.md"
    source_path.write_text("Original content", encoding="utf-8")
    service = IngestService(make_test_config(tmp_path))

    first = await service.ingest_file(str(source_path))

    source_path.write_text("Revised content with new bytes", encoding="utf-8")
    second = await service.ingest_file(str(source_path))

    assert second.document_id == first.document_id
    assert second.outcome == "changed_content"
    assert second.chunk_count >= 1
    assert (
        "changed" in second.message.lower()
        or "new version" in second.message.lower()
    )


# ─────────────────────────────────────────────
# ingest_note tests
# ─────────────────────────────────────────────


async def test_ingest_note_success_returns_result(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    service = IngestService(_make_note_config(tmp_path))
    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(return_value=None),
    ):
        result = await service.ingest_note(
            "Operational review notes from Q1 planning session.",
            metadata={"title": "Q1 Planning Notes", "external_id": "note-001"},
        )

    assert str(uuid.UUID(result.document_id)) == result.document_id
    assert result.chunk_count >= 1
    assert result.outcome == "new_content"
    assert result.source_alias == "Q1-Planning-Notes.md"
    assert result.source_locator.startswith("mcp_note://mcp/note-001")
    assert result.warning is None


async def test_ingest_note_empty_content_raises_value_error(
    tmp_path: Path,
) -> None:
    service = IngestService(_make_note_config(tmp_path))
    with pytest.raises(ValueError, match="empty or whitespace"):
        await service.ingest_note("   ")


async def test_ingest_note_empty_string_raises_value_error(
    tmp_path: Path,
) -> None:
    service = IngestService(_make_note_config(tmp_path))
    with pytest.raises(ValueError, match="empty or whitespace"):
        await service.ingest_note("")


async def test_ingest_note_exact_byte_duplicate_returns_new_source_known_content(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Same bytes ingested via file then via note → new_source_known_content."""
    note_text = "Shared content for dedup test."
    file_path = tmp_path / "shared.md"
    file_path.write_text(note_text, encoding="utf-8")
    service = IngestService(_make_note_config(tmp_path))

    await service.ingest_file(str(file_path))

    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(return_value=None),
    ):
        note_result = await service.ingest_note(
            note_text, metadata={"external_id": "dedup-test"}
        )

    assert note_result.outcome == "new_source_known_content"
    assert (
        "linked" in note_result.message.lower()
        or "known" in note_result.message.lower()
    )
    assert note_result.warning is None


async def test_ingest_note_stable_external_id_returns_unchanged_on_retry(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Same external_id + same content on second call → unchanged."""
    service = IngestService(_make_note_config(tmp_path))
    text = "Meeting notes from the all-hands."

    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(return_value=None),
    ):
        first = await service.ingest_note(
            text, metadata={"external_id": "meeting-001"}
        )
        second = await service.ingest_note(
            text, metadata={"external_id": "meeting-001"}
        )

    assert first.outcome == "new_content"
    assert second.outcome == "unchanged"
    assert second.chunk_count == 0


async def test_ingest_note_near_duplicate_warning_returned(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    service = IngestService(_make_note_config(tmp_path))
    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(
            return_value={"source_alias": "existing-doc.md", "similarity": 0.97}
        ),
    ):
        result = await service.ingest_note(
            "New note content.", metadata={"title": "New Note"}
        )

    assert result.outcome == "new_content"
    assert result.warning is not None
    assert "existing-doc.md" in result.warning
    assert "0.97" in result.warning


async def test_ingest_note_near_duplicate_not_triggered_for_exact_duplicate(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    """Near-duplicate check is only run for new_content/changed_content outcomes."""
    note_text = "Exact bytes for skip-near-dup test."
    service = IngestService(_make_note_config(tmp_path))

    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(return_value=None),
    ) as mock_near_dup:
        await service.ingest_note(note_text, metadata={"external_id": "skip-near-dup"})
        second = await service.ingest_note(
            note_text, metadata={"external_id": "skip-near-dup"}
        )

    assert second.outcome == "unchanged"
    # find_near_duplicate called once (first ingest only), not on unchanged
    assert mock_near_dup.call_count == 1


async def test_ingest_note_without_metadata_uses_generated_alias(
    migrated_db: None,
    tmp_path: Path,
    mock_embed: None,
) -> None:
    service = IngestService(_make_note_config(tmp_path))
    with patch(
        "cos.services.ingestion.find_near_duplicate",
        new=AsyncMock(return_value=None),
    ):
        result = await service.ingest_note("A standalone note without metadata.")

    assert result.source_alias.endswith(".md")
    assert result.source_locator.startswith("mcp_note://mcp/")
    assert str(uuid.UUID(result.document_id)) == result.document_id
