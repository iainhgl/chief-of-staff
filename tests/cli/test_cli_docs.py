import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.store.models import DocumentSummary

runner = CliRunner()


def _make_doc(
    alias: str = "notes.md",
    locator: str = "/data/notes.md",
) -> DocumentSummary:
    return DocumentSummary(
        id="00000000-0000-0000-0000-000000000001",
        source_alias=alias,
        source_locator=locator,
        ingested_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        current_version=1,
        chunk_count=3,
    )


def _patch_docs(docs: list[DocumentSummary]):
    return patch(
        "cos.services.provenance.ProvenanceService.list_documents",
        new=AsyncMock(return_value=docs),
    )


def test_docs_table_header_uses_source_alias() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc()]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "SOURCE ALIAS" in output.output
    assert "SOURCE PATH" not in output.output


def test_docs_table_shows_alias_value() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc(alias="notes.md")]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "notes.md" in output.output


def test_docs_json_output_has_source_alias_and_locator() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([_make_doc(alias="notes.md", locator="/data/notes.md")]),
    ):
        output = runner.invoke(app, ["docs", "--json"])

    assert output.exit_code == 0
    data = json.loads(output.output)
    assert len(data) == 1
    doc = data[0]
    assert doc["source_alias"] == "notes.md"
    assert doc["source_locator"] == "/data/notes.md"
    assert "source_path" not in doc


def test_docs_empty_database_shows_hint() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=MagicMock()),
        _patch_docs([]),
    ):
        output = runner.invoke(app, ["docs"])

    assert output.exit_code == 0
    assert "No documents ingested yet" in output.output
