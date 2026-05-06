"""Tests for `cos sync gmail` CLI command."""
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr
from typer.testing import CliRunner

from cos.cli import app
from cos.config import (
    CosConfig,
    GmailConnectorConfig,
    GoogleOAuthConfig,
)
from cos.connectors.google_auth import AuthError
from cos.services.gmail import GmailPollResult

runner = CliRunner()


def _config_with_gmail(staging_dir: str = "/tmp/staging") -> CosConfig:
    cfg = MagicMock(spec=CosConfig)
    cfg.connectors = ["gmail"]
    cfg.gmail = GmailConnectorConfig(staging_dir=staging_dir)
    cfg.google_oauth = GoogleOAuthConfig(
        client_id="test.apps.googleusercontent.com",
        client_secret=SecretStr("secret"),
    )
    cfg.database = MagicMock()
    cfg.database.libpq_dsn = "postgresql://postgres:postgres@localhost:5432/cos_test"
    return cfg


def _config_without_gmail() -> CosConfig:
    cfg = MagicMock(spec=CosConfig)
    cfg.connectors = []
    return cfg


# ── success path ──────────────────────────────────────────────────────────────

def test_sync_gmail_prints_summary_on_success() -> None:
    poll_result = GmailPollResult(
        messages_scanned=10,
        body_jobs_enqueued=10,
        attachment_jobs_enqueued=3,
        attachments_skipped=1,
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch("cos.cli._do_sync_gmail", new=AsyncMock(return_value=poll_result)),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 0
    assert "10 messages scanned" in result.output
    assert "10 body jobs enqueued" in result.output
    assert "3 attachment jobs enqueued" in result.output
    assert "1 unsupported attachments skipped" in result.output


def test_sync_gmail_exit_0_on_empty_inbox() -> None:
    poll_result = GmailPollResult(
        messages_scanned=0,
        body_jobs_enqueued=0,
        attachment_jobs_enqueued=0,
        attachments_skipped=0,
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch("cos.cli._do_sync_gmail", new=AsyncMock(return_value=poll_result)),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 0
    assert "0 messages scanned" in result.output


# ── disabled connector ────────────────────────────────────────────────────────

def test_sync_gmail_fails_when_gmail_not_in_connectors() -> None:
    with patch("cos.cli.CosConfig.load", return_value=_config_without_gmail()):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 1
    assert "gmail" in result.output.lower()


# ── auth error ────────────────────────────────────────────────────────────────

def test_sync_gmail_fails_gracefully_on_auth_error() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch(
            "cos.cli._do_sync_gmail",
            new=AsyncMock(
                side_effect=AuthError("No token. Run: uv run cos auth gmail")
            ),
        ),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 1
    assert "authentication error" in result.output.lower()
    assert "uv run cos auth gmail" in result.output


# ── degraded Gmail API ────────────────────────────────────────────────────────

def test_sync_gmail_fails_gracefully_on_api_error() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch(
            "cos.cli._do_sync_gmail",
            new=AsyncMock(side_effect=RuntimeError("Gmail API unavailable")),
        ),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 1
    assert "gmail sync failed" in result.output.lower()


def test_sync_gmail_reports_configuration_error() -> None:
    with patch(
        "cos.cli.CosConfig.load",
        side_effect=SystemExit("Invalid config.yaml:\nmax_results must be <= 500"),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 1
    assert "configuration error" in result.output.lower()
    assert "max_results must be <= 500" in result.output
