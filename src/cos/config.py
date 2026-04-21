from pathlib import Path
from typing import Literal
from urllib.parse import quote

import yaml
from pydantic import BaseModel, Field, SecretStr, ValidationError

LogComponent = Literal[
    "ingestion", "retrieval", "mcp_server", "cli", "scheduler", "connector", "output", "config"
]


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key: SecretStr


class EmbeddingConfig(BaseModel):
    provider: str
    model: str
    api_key: SecretStr | None = None


class RolePackRef(BaseModel):
    path: str


class DatabaseConfig(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    user: str
    password: SecretStr
    dbname: str

    @property
    def connection_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )

    @property
    def libpq_dsn(self) -> str:
        # Never log this value — it contains the plaintext password
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.dbname}"


class CosConfig(BaseModel):
    llm: LLMConfig
    embedding: EmbeddingConfig
    role_pack: RolePackRef
    channels: list[str]
    connectors: list[str]
    database: DatabaseConfig

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "CosConfig":
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise SystemExit(
                    f"Invalid config.yaml: expected a YAML mapping, got {type(data).__name__}.\n"
                    "Check that the file is not empty and contains valid key: value pairs."
                )
            return cls.model_validate(data)
        except FileNotFoundError:
            raise SystemExit(
                f"Config file not found: {path}\n"
                "Copy config.yaml.example to config.yaml and fill in your values."
            )
        except yaml.YAMLError as exc:
            raise SystemExit(f"Invalid config.yaml — YAML syntax error:\n{exc}")
        except ValidationError as exc:
            raise SystemExit(f"Invalid config.yaml:\n{exc}")
