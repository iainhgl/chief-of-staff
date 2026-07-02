"""Tests for `cos gmail` utility commands."""
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app
from cos.config import CosConfig
from cos.connectors.gmail import GmailLabel
from cos.connectors.google_auth import AuthError

runner = CliRunner()


def _config() -> CosConfig:
    return MagicMock(spec=CosConfig)


def test_gmail_labels_prints_label_table() -> None:
    labels = [
        GmailLabel(id="Label_123", name="cos-uat", type="user"),
        GmailLabel(id="INBOX", name="INBOX", type="system"),
    ]

    with (
        patch("cos.cli.CosConfig.load", return_value=_config()),
        patch("cos.cli._list_gmail_labels", return_value=labels),
    ):
        result = runner.invoke(app, ["gmail", "labels"])

    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "ID" in result.output
    assert "TYPE" in result.output
    assert "cos-uat" in result.output
    assert "Label_123" in result.output
    assert "INBOX" in result.output


def test_gmail_labels_prints_empty_message() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config()),
        patch("cos.cli._list_gmail_labels", return_value=[]),
    ):
        result = runner.invoke(app, ["gmail", "labels"])

    assert result.exit_code == 0
    assert "No Gmail labels found." in result.output


def test_gmail_labels_reports_configuration_error() -> None:
    with patch(
        "cos.cli.CosConfig.load",
        side_effect=SystemExit("Invalid config.yaml:\ngoogle_oauth is malformed"),
    ):
        result = runner.invoke(app, ["gmail", "labels"])

    assert result.exit_code == 1
    assert "configuration error" in result.output.lower()
    assert "google_oauth is malformed" in result.output


def test_gmail_labels_reports_auth_error() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config()),
        patch(
            "cos.cli._list_gmail_labels",
            side_effect=AuthError(
                "No token found for gmail. Run: uv run cos auth gmail"
            ),
        ),
    ):
        result = runner.invoke(app, ["gmail", "labels"])

    assert result.exit_code == 1
    assert "authentication error" in result.output.lower()
    assert "uv run cos auth gmail" in result.output
