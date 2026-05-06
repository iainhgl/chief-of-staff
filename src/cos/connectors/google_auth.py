import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from cos.config import GoogleOAuthConfig

ConnectorName = Literal["gmail", "google_calendar"]

_CONNECTOR_SCOPES: dict[str, list[str]] = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
    "google_calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
}

_TOKEN_PATHS: dict[str, Path] = {
    "gmail": Path("tokens/gmail.json"),
    "google_calendar": Path("tokens/google_calendar.json"),
}

# Maps internal connector key → the CLI command operators should run to recover
_CLI_AUTH_COMMAND: dict[str, str] = {
    "gmail": "uv run cos auth gmail",
    "google_calendar": "uv run cos auth calendar",
}


class AuthError(Exception):
    """Connector-scoped auth failure with a plain-language recovery instruction."""


def run_oauth_flow(
    connector: ConnectorName, oauth_config: GoogleOAuthConfig
) -> Credentials:
    """Run browser-based installed-app OAuth flow and persist token to disk."""
    scopes = _CONNECTOR_SCOPES[connector]
    token_file = _TOKEN_PATHS[connector]
    token_file.parent.mkdir(parents=True, exist_ok=True)

    client_config = {
        "installed": {
            "client_id": oauth_config.client_id,
            "client_secret": oauth_config.client_secret.get_secret_value(),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_file.write_text(creds.to_json())
    return creds


def load_credentials(
    connector: ConnectorName, oauth_config: GoogleOAuthConfig | None
) -> Credentials:
    """Load and (if needed) refresh credentials for the given connector.

    Raises AuthError with a direct recovery instruction on any failure.
    """
    recovery_cmd = _CLI_AUTH_COMMAND.get(connector, f"uv run cos auth {connector}")

    if oauth_config is None:
        _log_auth_error(connector, "google_oauth block is missing from config.yaml")
        raise AuthError(
            f"Google OAuth credentials not configured. "
            f"Add a google_oauth block to config.yaml, then run: {recovery_cmd}"
        )

    token_file = _TOKEN_PATHS[connector]
    required_scopes = _CONNECTOR_SCOPES[connector]
    if not token_file.exists():
        _log_auth_error(connector, f"missing {connector} OAuth token")
        raise AuthError(
            f"No token found for {connector}. Run: {recovery_cmd}"
        )

    try:
        token_data = _read_token_data(token_file)
        _require_granted_scopes(connector, token_data, required_scopes, recovery_cmd)
        creds = Credentials.from_authorized_user_info(token_data)
    except AuthError:
        raise
    except Exception as exc:
        _log_auth_error(connector, f"token file is malformed: {exc}")
        raise AuthError(
            f"Token file for {connector} is malformed. Run: {recovery_cmd}"
        ) from exc

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_file.write_text(creds.to_json())
            except Exception as exc:
                _log_auth_error(connector, f"token refresh failed: {exc}")
                raise AuthError(
                    f"Token refresh failed for {connector}. Run: {recovery_cmd}"
                ) from exc
        else:
            _log_auth_error(connector, "token expired and no refresh token available")
            raise AuthError(
                f"Token for {connector} is expired and cannot be refreshed. "
                f"Run: {recovery_cmd}"
            )

    return creds


def _read_token_data(token_file: Path) -> dict[str, object]:
    token_data = json.loads(token_file.read_text())
    if not isinstance(token_data, dict):
        raise ValueError("token file must contain a JSON object")
    return token_data


def _require_granted_scopes(
    connector: ConnectorName,
    token_data: dict[str, object],
    required_scopes: list[str],
    recovery_cmd: str,
) -> None:
    granted_scopes = _parse_granted_scopes(token_data.get("scopes"))
    missing_scopes = sorted(set(required_scopes) - granted_scopes)
    if not missing_scopes:
        return

    _log_auth_error(
        connector,
        "token missing required scopes: " + ", ".join(missing_scopes),
    )
    raise AuthError(
        f"Token for {connector} is missing required scopes. Run: {recovery_cmd}"
    )


def _parse_granted_scopes(raw_scopes: object) -> set[str]:
    if isinstance(raw_scopes, str):
        return {scope for scope in raw_scopes.split() if scope}
    if isinstance(raw_scopes, list) and all(
        isinstance(scope, str) for scope in raw_scopes
    ):
        return set(raw_scopes)
    raise ValueError("token scopes field is malformed")


def _log_auth_error(connector: str, message: str) -> None:
    logging.error(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "component": "connector",
                "connector": connector,
                "message": message,
                "recovery": _CLI_AUTH_COMMAND.get(
                    connector, f"uv run cos auth {connector}"
                ),
            }
        )
    )
