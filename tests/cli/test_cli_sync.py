"""Tests for `cos sync gmail` and `cos sync calendar` CLI commands."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import SecretStr
from typer.testing import CliRunner

from cos.cli import app
from cos.config import (
    CosConfig,
    GmailConnectorConfig,
    GoogleCalendarConnectorConfig,
    GoogleOAuthConfig,
)
from cos.connectors.google_auth import AuthError
from cos.services.calendar import CalendarSyncDegradedError, CalendarSyncResult
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


# ── skip counts in summary ────────────────────────────────────────────────────

def test_sync_gmail_prints_skip_counts_in_summary() -> None:
    poll_result = GmailPollResult(
        messages_scanned=5,
        body_jobs_enqueued=2,
        attachment_jobs_enqueued=1,
        attachments_skipped=0,
        artifacts_already_processed=3,
        artifacts_already_queued=1,
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch("cos.cli._do_sync_gmail", new=AsyncMock(return_value=poll_result)),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 0
    assert "3 artifacts already processed (skipped)" in result.output
    assert "1 artifacts already queued (skipped)" in result.output


# ── --force flag ──────────────────────────────────────────────────────────────

def test_sync_gmail_force_flag_passes_force_to_service() -> None:
    poll_result = GmailPollResult(
        messages_scanned=3,
        body_jobs_enqueued=3,
        attachment_jobs_enqueued=0,
        attachments_skipped=0,
        artifacts_already_processed=0,
        artifacts_already_queued=0,
    )

    captured_kwargs: dict = {}

    async def _fake_do_sync(config: Any, force: bool = False) -> GmailPollResult:
        captured_kwargs["force"] = force
        return poll_result

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch("cos.cli._do_sync_gmail", new=_fake_do_sync),
    ):
        result = runner.invoke(app, ["sync", "gmail", "--force"])

    assert result.exit_code == 0
    assert captured_kwargs.get("force") is True


def test_sync_gmail_default_does_not_pass_force() -> None:
    poll_result = GmailPollResult(
        messages_scanned=0,
        body_jobs_enqueued=0,
        attachment_jobs_enqueued=0,
        attachments_skipped=0,
    )

    captured_kwargs: dict = {}

    async def _fake_do_sync(config: Any, force: bool = False) -> GmailPollResult:
        captured_kwargs["force"] = force
        return poll_result

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_gmail()),
        patch("cos.cli._do_sync_gmail", new=_fake_do_sync),
    ):
        result = runner.invoke(app, ["sync", "gmail"])

    assert result.exit_code == 0
    assert captured_kwargs.get("force") is False


# ─────────────────────────────────────────────────────────────────────────────
# cos sync calendar
# ─────────────────────────────────────────────────────────────────────────────


def _config_with_calendar(staging_dir: str = "/tmp/staging") -> CosConfig:
    cfg = MagicMock(spec=CosConfig)
    cfg.connectors = ["google_calendar"]
    cfg.google_calendar = GoogleCalendarConnectorConfig(staging_dir=staging_dir)
    cfg.google_oauth = GoogleOAuthConfig(
        client_id="test.apps.googleusercontent.com",
        client_secret=SecretStr("secret"),
    )
    cfg.database = MagicMock()
    cfg.database.libpq_dsn = "postgresql://postgres:postgres@localhost:5432/cos_test"
    return cfg


def _config_without_calendar() -> CosConfig:
    cfg = MagicMock(spec=CosConfig)
    cfg.connectors = []
    return cfg


# ── success path ──────────────────────────────────────────────────────────────

def test_sync_calendar_prints_summary_on_success() -> None:
    sync_result = CalendarSyncResult(
        calendars_scanned=2,
        events_discovered=15,
        jobs_enqueued=15,
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_calendar()),
        patch("cos.cli._do_sync_calendar", new=AsyncMock(return_value=sync_result)),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 0
    assert "2 calendar" in result.output
    assert "15 event" in result.output
    assert "15 job" in result.output


def test_sync_calendar_exit_0_on_empty_calendar() -> None:
    sync_result = CalendarSyncResult(
        calendars_scanned=1,
        events_discovered=0,
        jobs_enqueued=0,
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_calendar()),
        patch("cos.cli._do_sync_calendar", new=AsyncMock(return_value=sync_result)),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 0
    assert "0 event" in result.output


# ── disabled connector ────────────────────────────────────────────────────────

def test_sync_calendar_fails_when_not_in_connectors() -> None:
    with patch("cos.cli.CosConfig.load", return_value=_config_without_calendar()):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 1
    assert "google_calendar" in result.output.lower()


# ── auth error ────────────────────────────────────────────────────────────────

def test_sync_calendar_fails_gracefully_on_auth_error() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_calendar()),
        patch(
            "cos.cli._do_sync_calendar",
            new=AsyncMock(
                side_effect=AuthError(
                    "No token. Run: uv run cos auth calendar"
                )
            ),
        ),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 1
    assert "authentication error" in result.output.lower()
    assert "uv run cos auth calendar" in result.output


# ── degraded Calendar API ─────────────────────────────────────────────────────

def test_sync_calendar_fails_gracefully_on_api_error() -> None:
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_calendar()),
        patch(
            "cos.cli._do_sync_calendar",
            new=AsyncMock(side_effect=RuntimeError("Calendar API unavailable")),
        ),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 1
    assert "calendar sync failed" in result.output.lower()


def test_sync_calendar_surfaces_degraded_partial_failure() -> None:
    degraded = CalendarSyncDegradedError(
        result=CalendarSyncResult(
            calendars_scanned=2,
            events_discovered=4,
            jobs_enqueued=4,
        ),
        failed_calendars=["team@example.com"],
    )
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_calendar()),
        patch("cos.cli._do_sync_calendar", new=AsyncMock(side_effect=degraded)),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 1
    assert "calendar sync degraded" in result.output.lower()
    assert "team@example.com" in result.output
    assert "partial results" in result.output.lower()
    assert "4 events discovered" in result.output


# ── configuration error ───────────────────────────────────────────────────────

def test_sync_calendar_reports_configuration_error() -> None:
    with patch(
        "cos.cli.CosConfig.load",
        side_effect=SystemExit("Invalid config.yaml:\nmax_results must be <= 2500"),
    ):
        result = runner.invoke(app, ["sync", "calendar"])

    assert result.exit_code == 1
    assert "configuration error" in result.output.lower()
    assert "max_results must be <= 2500" in result.output
