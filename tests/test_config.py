from pathlib import Path

import pytest

from cos.config import CosConfig, GmailConnectorConfig, GoogleOAuthConfig

VALID_CONFIG_YAML = """\
llm:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key: sk-test-key-1234

embedding:
  provider: anthropic
  model: voyage-3
  api_key: null

role_pack:
  path: role_packs/chro.yaml

channels:
  - local

connectors: []

database:
  host: localhost
  port: 5432
  user: postgres
  password: secret-db-pass
  dbname: cos
"""


def _write_config(tmp_path, content: str):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(content)
    return cfg


def test_valid_config_loads(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)

    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-sonnet-4-6"
    assert config.llm.ca_bundle_path is None
    assert config.llm.proxy_url is None
    assert config.llm.trust_env is None
    assert config.embedding.provider == "anthropic"
    assert config.embedding.api_key is None
    assert config.embedding.ca_bundle_path is None
    assert config.embedding.proxy_url is None
    assert config.embedding.trust_env is False
    assert config.role_pack.path == "role_packs/chro.yaml"
    assert config.channels == ["local"]
    assert config.connectors == []
    assert config.database.host == "localhost"
    assert config.database.port == 5432


def test_missing_llm_section_raises_system_exit(tmp_path):
    llm_block = (
        "llm:\n  provider: anthropic\n  model: claude-sonnet-4-6\n"
        "  api_key: sk-test-key-1234\n\n"
    )
    yaml_no_llm = VALID_CONFIG_YAML.replace(llm_block, "")
    cfg_file = _write_config(tmp_path, yaml_no_llm)
    with pytest.raises(SystemExit) as exc_info:
        CosConfig.load(cfg_file)
    assert "llm" in str(exc_info.value).lower()


def test_missing_nested_required_field_raises_system_exit(tmp_path):
    yaml_no_api_key = VALID_CONFIG_YAML.replace("  api_key: sk-test-key-1234\n", "")
    cfg_file = _write_config(tmp_path, yaml_no_api_key)
    with pytest.raises(SystemExit) as exc_info:
        CosConfig.load(cfg_file)
    assert "api_key" in str(exc_info.value)


def test_embedding_network_overrides_load(tmp_path):
    cfg_file = _write_config(
        tmp_path,
        VALID_CONFIG_YAML.replace(
            "  api_key: null\n",
            "  api_key: null\n"
            "  ca_bundle_path: /tmp/zscaler-root.pem\n"
            "  proxy_url: http://proxy.internal:8080\n"
            "  trust_env: true\n",
        ),
    )
    config = CosConfig.load(cfg_file)

    assert config.embedding.ca_bundle_path == Path("/tmp/zscaler-root.pem")
    assert config.embedding.proxy_url == "http://proxy.internal:8080"
    assert config.embedding.trust_env is True


def test_llm_network_overrides_load(tmp_path):
    cfg_file = _write_config(
        tmp_path,
        VALID_CONFIG_YAML.replace(
            "  api_key: sk-test-key-1234\n",
            "  api_key: sk-test-key-1234\n"
            "  ca_bundle_path: /tmp/anthropic-root.pem\n"
            "  proxy_url: http://proxy.internal:8080\n"
            "  trust_env: true\n",
        ),
    )
    config = CosConfig.load(cfg_file)

    assert config.llm.ca_bundle_path == Path("/tmp/anthropic-root.pem")
    assert config.llm.proxy_url == "http://proxy.internal:8080"
    assert config.llm.trust_env is True


def test_secret_str_masking(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)

    config_repr = repr(config)
    config_str = str(config)

    assert "sk-test-key-1234" not in config_repr
    assert "sk-test-key-1234" not in config_str
    assert "secret-db-pass" not in config_repr
    assert "secret-db-pass" not in config_str


def test_database_connection_url(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)

    url = config.database.connection_url
    assert url.startswith("postgresql+psycopg://")
    assert "postgres" in url
    assert "secret-db-pass" in url
    assert "localhost" in url
    assert "5432" in url
    assert "cos" in url


def test_missing_config_file_raises_system_exit(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        CosConfig.load(tmp_path / "nonexistent.yaml")
    assert "not found" in str(exc_info.value).lower()


def test_tika_config_defaults(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.tika.url == "http://tika:9998"


def test_storage_config_defaults(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.storage.originals_dir == Path("/data/originals")
    assert config.storage.markdown_dir == Path("/data/markdown")


def test_chunking_config_defaults(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.chunking.chunk_size == 1024
    assert config.chunking.chunk_overlap == 100


# ── Google OAuth config tests (Story 6.6) ──────────────────────────────────

_GOOGLE_OAUTH_BLOCK = """\
google_oauth:
  client_id: my-client-id.apps.googleusercontent.com
  client_secret: GOCSPX-supersecret
"""


def test_google_oauth_block_is_optional(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.google_oauth is None


def test_google_oauth_block_loads_when_present(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _GOOGLE_OAUTH_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.google_oauth is not None
    assert config.google_oauth.client_id == "my-client-id.apps.googleusercontent.com"


def test_google_oauth_client_secret_is_masked(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _GOOGLE_OAUTH_BLOCK)
    config = CosConfig.load(cfg_file)

    assert config.google_oauth is not None
    config_repr = repr(config)
    config_str = str(config)
    assert "GOCSPX-supersecret" not in config_repr
    assert "GOCSPX-supersecret" not in config_str


def test_google_oauth_client_secret_accessible_via_get_secret_value(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _GOOGLE_OAUTH_BLOCK)
    config = CosConfig.load(cfg_file)

    assert config.google_oauth is not None
    assert config.google_oauth.client_secret.get_secret_value() == "GOCSPX-supersecret"


def test_google_oauth_model_is_exported():
    assert GoogleOAuthConfig is not None


# ── Google Calendar config tests (Story 6.9) ──────────────────────────────

_GOOGLE_CALENDAR_BLOCK = """\
google_calendar:
  calendar_ids:
    - primary
  lookback_hours: 12
  lookahead_days: 14
  max_results: 100
  staging_dir: /data/connector-staging/google-calendar
"""


def test_google_calendar_config_is_optional(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.google_calendar is None


def test_google_calendar_config_loads_when_present(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _GOOGLE_CALENDAR_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.google_calendar is not None
    assert config.google_calendar.calendar_ids == ["primary"]
    assert config.google_calendar.lookback_hours == 12
    assert config.google_calendar.lookahead_days == 14
    assert config.google_calendar.max_results == 100
    assert config.google_calendar.staging_dir == Path(
        "/data/connector-staging/google-calendar"
    )


def test_google_calendar_config_defaults(tmp_path):
    from cos.config import GoogleCalendarConnectorConfig

    cal = GoogleCalendarConnectorConfig()
    assert cal.calendar_ids == ["primary"]
    assert cal.lookback_hours == 12
    assert cal.lookahead_days == 14
    assert cal.max_results == 100
    assert cal.staging_dir == Path("/data/connector-staging/google-calendar")


def test_google_calendar_config_max_results_cap(tmp_path):
    import pytest

    from cos.config import GoogleCalendarConnectorConfig

    with pytest.raises(Exception):
        GoogleCalendarConnectorConfig(max_results=2501)


def test_google_calendar_config_rejects_negative_lookback_hours(tmp_path):
    import pytest

    from cos.config import GoogleCalendarConnectorConfig

    with pytest.raises(Exception):
        GoogleCalendarConnectorConfig(lookback_hours=-1)


def test_google_calendar_config_rejects_negative_lookahead_days(tmp_path):
    import pytest

    from cos.config import GoogleCalendarConnectorConfig

    with pytest.raises(Exception):
        GoogleCalendarConnectorConfig(lookahead_days=-1)


def test_gmail_config_defaults():
    cfg = GmailConnectorConfig()
    assert cfg.label_names == []
    assert cfg.label_ids == []


def test_gmail_config_accepts_label_names():
    cfg = GmailConnectorConfig(label_names=["cos-uat"])
    assert cfg.label_names == ["cos-uat"]
    assert cfg.label_ids == []


def test_gmail_config_rejects_label_names_and_label_ids_together():
    with pytest.raises(Exception, match="mutually exclusive"):
        GmailConnectorConfig(label_names=["cos-uat"], label_ids=["Label_123"])


def test_gmail_config_rejects_label_names_and_label_ids_on_load(tmp_path):
    yaml_with_gmail = VALID_CONFIG_YAML + (
        "\ngmail:\n"
        "  query: newer_than:7d\n"
        "  label_names:\n"
        "    - cos-uat\n"
        "  label_ids:\n"
        "    - Label_123\n"
    )
    cfg_file = _write_config(tmp_path, yaml_with_gmail)

    with pytest.raises(SystemExit) as exc_info:
        CosConfig.load(cfg_file)

    assert "label_names" in str(exc_info.value)
    assert "label_ids" in str(exc_info.value)


def test_existing_config_loads_unchanged_without_calendar_block(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.google_calendar is None
    assert config.gmail is None


def test_mcp_note_config_absent_by_default(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.mcp_note is None


def test_mcp_note_config_optional_block_loads(tmp_path):
    yaml_with_mcp_note = VALID_CONFIG_YAML + (
        "\nmcp_note:\n"
        "  staging_dir: /data/connector-staging/mcp\n"
        "  near_duplicate_threshold: 0.90\n"
    )
    cfg_file = _write_config(tmp_path, yaml_with_mcp_note)
    config = CosConfig.load(cfg_file)

    assert config.mcp_note is not None
    assert config.mcp_note.staging_dir == Path("/data/connector-staging/mcp")
    assert config.mcp_note.near_duplicate_threshold == pytest.approx(0.90)


def test_mcp_note_config_defaults_when_block_empty(tmp_path):
    from cos.config import McpNoteIngestConfig

    cfg = McpNoteIngestConfig()
    assert cfg.staging_dir == Path("/data/connector-staging/mcp")
    assert cfg.near_duplicate_threshold == pytest.approx(0.95)


def test_mcp_note_config_rejects_threshold_above_one(tmp_path):
    from cos.config import McpNoteIngestConfig

    with pytest.raises(Exception):
        McpNoteIngestConfig(near_duplicate_threshold=1.1)


def test_mcp_note_config_rejects_negative_threshold(tmp_path):
    from cos.config import McpNoteIngestConfig

    with pytest.raises(Exception):
        McpNoteIngestConfig(near_duplicate_threshold=-0.1)


# ── Retrieval config tests (Story 6.13) ────────────────────────────────────


def test_retrieval_config_default_min_score():
    from cos.config import RetrievalConfig

    cfg = RetrievalConfig()
    assert cfg.min_score == 0.0


def test_retrieval_config_default_max_chunks_per_source():
    from cos.config import RetrievalConfig

    cfg = RetrievalConfig()
    assert cfg.max_chunks_per_source == 2


def test_retrieval_config_rejects_negative_min_score():
    from cos.config import RetrievalConfig

    with pytest.raises(Exception):
        RetrievalConfig(min_score=-0.1)


def test_retrieval_config_rejects_min_score_above_one():
    from cos.config import RetrievalConfig

    with pytest.raises(Exception):
        RetrievalConfig(min_score=1.1)


def test_retrieval_config_rejects_zero_max_chunks_per_source():
    from cos.config import RetrievalConfig

    with pytest.raises(Exception):
        RetrievalConfig(max_chunks_per_source=0)


def test_cos_config_has_retrieval_defaults(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)

    assert config.retrieval.min_score == 0.0
    assert config.retrieval.max_chunks_per_source == 2


def test_retrieval_config_loads_from_yaml(tmp_path):
    yaml_with_retrieval = VALID_CONFIG_YAML + (
        "\nretrieval:\n  min_score: 0.01\n  max_chunks_per_source: 3\n"
    )
    cfg_file = _write_config(tmp_path, yaml_with_retrieval)
    config = CosConfig.load(cfg_file)

    assert config.retrieval.min_score == pytest.approx(0.01)
    assert config.retrieval.max_chunks_per_source == 3


# ── Telegram connector config tests (Story 8.1) ───────────────────────────

_TELEGRAM_BLOCK = """\
telegram:
  bot_token: tg-bot-secret-token
  chat_id: "123456789"
"""


def test_telegram_config_is_optional(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.telegram is None


def test_telegram_config_loads_when_present(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _TELEGRAM_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.telegram is not None
    assert config.telegram.chat_id == "123456789"


def test_telegram_config_bot_token_accessible(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _TELEGRAM_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.telegram is not None
    assert config.telegram.bot_token.get_secret_value() == "tg-bot-secret-token"


def test_telegram_config_bot_token_masked_in_repr(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _TELEGRAM_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.telegram is not None
    assert "tg-bot-secret-token" not in repr(config)
    assert "tg-bot-secret-token" not in str(config)
    assert "tg-bot-secret-token" not in repr(config.telegram)
    assert "tg-bot-secret-token" not in str(config.telegram)


def test_telegram_config_defaults(tmp_path):
    cfg_file = _write_config(tmp_path, VALID_CONFIG_YAML + _TELEGRAM_BLOCK)
    config = CosConfig.load(cfg_file)
    assert config.telegram is not None
    assert config.telegram.api_base_url == "https://api.telegram.org"
    assert config.telegram.poll_timeout == 30
    assert config.telegram.backoff_initial == pytest.approx(1.0)
    assert config.telegram.backoff_max == pytest.approx(60.0)


def test_telegram_config_requires_bot_token(tmp_path):
    yaml_missing_token = VALID_CONFIG_YAML + (
        "\ntelegram:\n  chat_id: \"123456789\"\n"
    )
    cfg_file = _write_config(tmp_path, yaml_missing_token)
    with pytest.raises(SystemExit):
        CosConfig.load(cfg_file)


def test_telegram_config_requires_chat_id(tmp_path):
    yaml_missing_chat = VALID_CONFIG_YAML + (
        "\ntelegram:\n  bot_token: tg-secret\n"
    )
    cfg_file = _write_config(tmp_path, yaml_missing_chat)
    with pytest.raises(SystemExit):
        CosConfig.load(cfg_file)


def test_telegram_config_rejects_poll_timeout_below_minimum(tmp_path):
    from cos.config import TelegramConnectorConfig

    with pytest.raises(Exception):
        TelegramConnectorConfig(bot_token="tok", chat_id="1", poll_timeout=0)


def test_telegram_config_rejects_poll_timeout_above_maximum(tmp_path):
    from cos.config import TelegramConnectorConfig

    with pytest.raises(Exception):
        TelegramConnectorConfig(bot_token="tok", chat_id="1", poll_timeout=121)


def test_telegram_config_rejects_zero_backoff_initial(tmp_path):
    from cos.config import TelegramConnectorConfig

    with pytest.raises(Exception):
        TelegramConnectorConfig(bot_token="tok", chat_id="1", backoff_initial=0.0)


def test_telegram_config_rejects_blank_bot_token(tmp_path):
    from cos.config import TelegramConnectorConfig

    with pytest.raises(Exception):
        TelegramConnectorConfig(bot_token="   ", chat_id="1")


def test_telegram_config_rejects_blank_chat_id(tmp_path):
    from cos.config import TelegramConnectorConfig

    with pytest.raises(Exception):
        TelegramConnectorConfig(bot_token="tok", chat_id="   ")


# ── Telegram staging_dir config tests (Story 8.3) ─────────────────────────

def test_telegram_config_staging_dir_default(tmp_path):
    from cos.config import TelegramConnectorConfig

    cfg = TelegramConnectorConfig(bot_token="tok", chat_id="123")
    assert cfg.staging_dir == Path("/data/connector-staging/telegram")


def test_telegram_config_staging_dir_override(tmp_path):
    from cos.config import TelegramConnectorConfig

    cfg = TelegramConnectorConfig(
        bot_token="tok", chat_id="123", staging_dir="/custom/staging"
    )
    assert cfg.staging_dir == Path("/custom/staging")


def test_telegram_config_staging_dir_loads_from_yaml(tmp_path):
    yaml_with_staging = VALID_CONFIG_YAML + (
        "\ntelegram:\n"
        "  bot_token: tg-secret\n"
        "  chat_id: \"111222333\"\n"
        "  staging_dir: /data/connector-staging/telegram\n"
    )
    cfg_file = _write_config(tmp_path, yaml_with_staging)
    config = CosConfig.load(cfg_file)
    assert config.telegram is not None
    assert config.telegram.staging_dir == Path("/data/connector-staging/telegram")
