from google.oauth2.credentials import Credentials

from cos.config import CosConfig
from cos.connectors.google_auth import load_credentials


def get_gmail_credentials(config: CosConfig) -> Credentials:
    """Return valid Gmail credentials, refreshing locally when possible."""
    return load_credentials("gmail", config.google_oauth)
