from pathlib import Path

import pytest

from cos.config import CosConfig

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
    assert config.embedding.provider == "anthropic"
    assert config.embedding.api_key is None
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
