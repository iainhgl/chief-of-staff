from google.oauth2.credentials import Credentials

from cos.config import CosConfig
from cos.connectors.google_auth import load_credentials


def get_calendar_credentials(config: CosConfig) -> Credentials:
    """Return valid Google Calendar credentials, refreshing locally when possible."""
    return load_credentials("google_calendar", config.google_oauth)
