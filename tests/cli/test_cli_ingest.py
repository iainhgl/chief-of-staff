from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.services.ingestion import IngestResult

runner = CliRunner()


def _make_result(
    outcome: str,
    chunk_count: int = 0,
    name: str = "doc.md",
) -> IngestResult:
    return IngestResult(
        document_id="00000000-0000-0000-0000-000000000001",
        chunk_count=chunk_count,
        source_path=f"/tmp/{name}",
        outcome=outcome,
        message=f"Mock message for {outcome}",
    )


def _patch_ingest(result: IngestResult):
    mock_service = MagicMock()
    mock_service.ingest_file = AsyncMock(return_value=result)
    return patch("cos.cli.IngestService", return_value=mock_service)


def _write_source(tmp_path: Path, name: str = "notes.md") -> Path:
    source = tmp_path / name
    source.write_text("source content", encoding="utf-8")
    return source


def test_ingest_file_new_content_prints_chunk_count(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    result = _make_result("new_content", chunk_count=5, name=source.name)

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(source)])

    assert output.exit_code == 0
    assert "Ingested notes.md -> 5 chunks indexed" in output.output


def test_ingest_file_unchanged_prints_no_change_message(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    result = _make_result("unchanged", chunk_count=0, name=source.name)

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(source)])

    assert output.exit_code == 0
    assert "No change detected in notes.md \u2014 already up to date" in output.output


def test_ingest_file_changed_content_prints_update_message(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    result = _make_result("changed_content", chunk_count=4, name=source.name)

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(source)])

    assert output.exit_code == 0
    assert (
        "Updated notes.md -> 4 new chunks indexed (new version)" in output.output
    )


def test_ingest_file_new_source_known_content_prints_recorded_message(
    tmp_path: Path,
) -> None:
    source = _write_source(tmp_path)
    result = _make_result("new_source_known_content", chunk_count=0, name=source.name)

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(source)])

    assert output.exit_code == 0
    assert (
        "Recorded notes.md as new source \u2014 content already indexed"
        in output.output
    )


def test_ingest_folder_unchanged_prints_no_change_message(tmp_path: Path) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    _write_source(folder, "report.md")
    result = _make_result("unchanged", chunk_count=0, name="report.md")

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(folder)])

    assert output.exit_code == 0
    assert "No change detected in report.md \u2014 already up to date" in output.output


def test_ingest_folder_changed_content_prints_update_message(tmp_path: Path) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    _write_source(folder, "report.md")
    result = _make_result("changed_content", chunk_count=3, name="report.md")

    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_ingest(result),
    ):
        output = runner.invoke(app, ["ingest", str(folder)])

    assert output.exit_code == 0
    assert "Updated report.md -> 3 new chunks indexed (new version)" in output.output
