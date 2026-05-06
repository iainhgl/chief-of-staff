from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cos.cli import app

runner = CliRunner()


def _config_with_oauth():
    from pydantic import SecretStr

    from cos.config import CosConfig, GoogleOAuthConfig

    cfg = MagicMock(spec=CosConfig)
    cfg.google_oauth = GoogleOAuthConfig(
        client_id="test-client.apps.googleusercontent.com",
        client_secret=SecretStr("test-secret"),
    )
    return cfg


def _config_without_oauth():
    cfg = MagicMock()
    cfg.google_oauth = None
    return cfg


# ── cos auth gmail ──────────────────────────────────────────────────────────

def test_auth_gmail_success_prints_confirmation():
    mock_creds = MagicMock()

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", return_value=mock_creds),
    ):
        result = runner.invoke(app, ["auth", "gmail"])

    assert result.exit_code == 0
    assert "gmail" in result.output.lower()
    assert "tokens/gmail.json" in result.output


def test_auth_gmail_names_token_file_in_success_message():
    mock_creds = MagicMock()

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", return_value=mock_creds),
    ):
        result = runner.invoke(app, ["auth", "gmail"])

    assert result.exit_code == 0
    assert "tokens/gmail.json" in result.output


def test_auth_gmail_fails_when_google_oauth_missing():
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_without_oauth()),
    ):
        result = runner.invoke(app, ["auth", "gmail"])

    assert result.exit_code == 1
    assert "google_oauth" in result.output.lower()


def test_auth_gmail_fails_gracefully_when_oauth_flow_raises():
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", side_effect=Exception("browser error")),
    ):
        result = runner.invoke(app, ["auth", "gmail"])

    assert result.exit_code == 1
    assert "browser error" in result.output.lower() or "failed" in result.output.lower()


# ── cos auth calendar ───────────────────────────────────────────────────────

def test_auth_calendar_success_prints_confirmation():
    mock_creds = MagicMock()

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", return_value=mock_creds),
    ):
        result = runner.invoke(app, ["auth", "calendar"])

    assert result.exit_code == 0
    assert "calendar" in result.output.lower()
    assert "tokens/google_calendar.json" in result.output


def test_auth_calendar_names_token_file_in_success_message():
    mock_creds = MagicMock()

    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", return_value=mock_creds),
    ):
        result = runner.invoke(app, ["auth", "calendar"])

    assert result.exit_code == 0
    assert "tokens/google_calendar.json" in result.output


def test_auth_calendar_fails_when_google_oauth_missing():
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_without_oauth()),
    ):
        result = runner.invoke(app, ["auth", "calendar"])

    assert result.exit_code == 1
    assert "google_oauth" in result.output.lower()


def test_auth_calendar_fails_gracefully_when_oauth_flow_raises():
    with (
        patch("cos.cli.CosConfig.load", return_value=_config_with_oauth()),
        patch("cos.cli.run_oauth_flow", side_effect=Exception("network timeout")),
    ):
        result = runner.invoke(app, ["auth", "calendar"])

    assert result.exit_code == 1
    output = result.output.lower()
    assert "network timeout" in output or "failed" in output
