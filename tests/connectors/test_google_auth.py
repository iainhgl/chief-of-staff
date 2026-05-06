import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from cos.config import GoogleOAuthConfig
from cos.connectors.google_auth import (
    AuthError,
    load_credentials,
    run_oauth_flow,
)

OAUTH_CONFIG = GoogleOAuthConfig(
    client_id="test-client-id.apps.googleusercontent.com",
    client_secret=SecretStr("test-client-secret"),
)

_VALID_TOKEN_DATA = json.dumps(
    {
        "token": "access-token",
        "refresh_token": "refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "expiry": "2020-01-01T00:00:00.000000Z",
    }
)


# ── Token path selection ────────────────────────────────────────────────────

def test_token_path_for_gmail_is_correct():
    from cos.connectors.google_auth import _TOKEN_PATHS
    assert _TOKEN_PATHS["gmail"] == Path("tokens/gmail.json")


def test_token_path_for_google_calendar_is_correct():
    from cos.connectors.google_auth import _TOKEN_PATHS
    assert _TOKEN_PATHS["google_calendar"] == Path("tokens/google_calendar.json")


# ── run_oauth_flow ──────────────────────────────────────────────────────────

def test_run_oauth_flow_writes_token_file(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = _VALID_TOKEN_DATA

    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds

    with (
        patch("cos.connectors.google_auth.InstalledAppFlow") as mock_flow_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_flow_cls.from_client_config.return_value = mock_flow
        result = run_oauth_flow("gmail", OAUTH_CONFIG)

    assert token_file.exists()
    assert result is mock_creds
    saved = json.loads(token_file.read_text())
    assert saved["refresh_token"] == "refresh-token"


def test_run_oauth_flow_creates_token_directory(tmp_path):
    token_file = tmp_path / "nested" / "tokens" / "gmail.json"

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = _VALID_TOKEN_DATA

    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds

    with (
        patch("cos.connectors.google_auth.InstalledAppFlow") as mock_flow_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_flow_cls.from_client_config.return_value = mock_flow
        run_oauth_flow("gmail", OAUTH_CONFIG)

    assert token_file.exists()


def test_run_oauth_flow_requests_offline_access(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = _VALID_TOKEN_DATA

    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds

    with (
        patch("cos.connectors.google_auth.InstalledAppFlow") as mock_flow_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_flow_cls.from_client_config.return_value = mock_flow
        run_oauth_flow("gmail", OAUTH_CONFIG)

    call_kwargs = mock_flow.run_local_server.call_args[1]
    assert call_kwargs.get("access_type") == "offline"


# ── load_credentials ────────────────────────────────────────────────────────

def test_load_credentials_returns_valid_creds(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"
    token_file.parent.mkdir(parents=True)
    token_file.write_text(_VALID_TOKEN_DATA)

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False

    with (
        patch("cos.connectors.google_auth.Credentials") as mock_creds_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_creds_cls.from_authorized_user_info.return_value = mock_creds
        result = load_credentials("gmail", OAUTH_CONFIG)

    assert result is mock_creds


def test_load_credentials_refreshes_expired_token_and_rewrites(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"
    token_file.parent.mkdir(parents=True)
    token_file.write_text(_VALID_TOKEN_DATA)

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh-token"
    mock_creds.to_json.return_value = json.dumps({"refreshed": True})

    with (
        patch("cos.connectors.google_auth.Credentials") as mock_creds_cls,
        patch("cos.connectors.google_auth.Request") as mock_request_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_creds_cls.from_authorized_user_info.return_value = mock_creds
        mock_creds.refresh = MagicMock()
        result = load_credentials("gmail", OAUTH_CONFIG)

    mock_creds.refresh.assert_called_once_with(mock_request_cls())
    saved = json.loads(token_file.read_text())
    assert saved.get("refreshed") is True
    assert result is mock_creds


def test_load_credentials_raises_auth_error_when_token_missing(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"

    with (
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        with pytest.raises(AuthError) as exc_info:
            load_credentials("gmail", OAUTH_CONFIG)

    assert "cos auth gmail" in str(exc_info.value)


def test_load_credentials_raises_auth_error_when_token_malformed(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"
    token_file.parent.mkdir(parents=True)
    token_file.write_text("not valid json {{{")

    with (
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        with pytest.raises(AuthError) as exc_info:
            load_credentials("gmail", OAUTH_CONFIG)

    assert "cos auth gmail" in str(exc_info.value)


def test_load_credentials_raises_auth_error_when_required_scope_missing(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"
    token_file.parent.mkdir(parents=True)
    token_file.write_text(
        json.dumps(
            {
                "token": "access-token",
                "refresh_token": "refresh-token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "test-client-id.apps.googleusercontent.com",
                "client_secret": "test-client-secret",
                "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
            }
        )
    )

    with patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}):
        with pytest.raises(AuthError) as exc_info:
            load_credentials("gmail", OAUTH_CONFIG)

    assert "missing required scopes" in str(exc_info.value)
    assert "cos auth gmail" in str(exc_info.value)


def test_load_credentials_raises_auth_error_when_no_refresh_token(tmp_path):
    token_file = tmp_path / "tokens" / "gmail.json"
    token_file.parent.mkdir(parents=True)
    token_file.write_text(_VALID_TOKEN_DATA)

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = None

    with (
        patch("cos.connectors.google_auth.Credentials") as mock_creds_cls,
        patch("cos.connectors.google_auth._TOKEN_PATHS", {"gmail": token_file}),
    ):
        mock_creds_cls.from_authorized_user_info.return_value = mock_creds
        with pytest.raises(AuthError) as exc_info:
            load_credentials("gmail", OAUTH_CONFIG)

    assert "cos auth gmail" in str(exc_info.value)


def test_load_credentials_raises_auth_error_for_calendar_with_correct_command(tmp_path):
    token_file = tmp_path / "tokens" / "google_calendar.json"

    with patch(
        "cos.connectors.google_auth._TOKEN_PATHS",
        {"google_calendar": token_file},
    ):
        with pytest.raises(AuthError) as exc_info:
            load_credentials("google_calendar", OAUTH_CONFIG)

    assert "cos auth calendar" in str(exc_info.value)


def test_load_credentials_raises_auth_error_when_oauth_config_is_none():
    with pytest.raises(AuthError) as exc_info:
        load_credentials("gmail", None)

    assert "google_oauth" in str(exc_info.value).lower()
