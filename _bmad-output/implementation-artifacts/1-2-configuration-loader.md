# Story 1.2: Configuration Loader

Status: done

## Story

As an operator,
I want all platform settings — API keys, role pack path, output channels, LLM and embedding provider config — defined in a single `config.yaml` file,
So that I can reconfigure the platform for a different role, provider, or channel without modifying any code.

## Acceptance Criteria

1. **Given** a `config.yaml` file with all required keys present, **when** the `cos` container starts, **then** `CosConfig` loads and validates the file using Pydantic v2, and the validated config object is available for injection into all components.

2. **Given** a `config.yaml` with a missing required key (e.g. no `llm` section), **when** the container starts, **then** startup fails immediately with a clear, human-readable Pydantic validation error identifying the missing field — not a cryptic Python traceback.

3. **Given** a committed `config.yaml.example` template, **when** an operator copies it to `config.yaml` and fills in their API keys and role pack path, **then** the platform starts successfully using those settings.

4. **Given** `config.yaml` contains API keys, **when** the platform is running under normal operation, **then** no key value appears in any log output, MCP response, or diagnostic output.

5. **Given** any module in the codebase other than `cos/config.py`, **when** imports are inspected, **then** no module reads `config.yaml` directly — all config access goes through the `CosConfig` instance.

6. **Given** `.gitignore` is present, **when** it is inspected, **then** `config.yaml` and `tokens/` are listed as ignored entries, and `config.yaml.example` is not ignored.

## Tasks / Subtasks

- [x] Task 1: Add `pyyaml` dependency and update `pyproject.toml` (AC: #1)
  - [x] Run `uv add pyyaml` in the `cos/` directory
  - [x] Verify `uv.lock` is updated and commit it

- [x] Task 2: Implement `CosConfig` with all nested models (AC: #1, #2, #4)
  - [x] Replace stub `CosConfig` in `src/cos/config.py` with full Pydantic v2 `BaseModel` implementation
  - [x] Define `LLMConfig(provider: str, model: str, api_key: SecretStr)` nested model
  - [x] Define `EmbeddingConfig(provider: str, model: str, api_key: SecretStr | None = None)` nested model
  - [x] Define `RolePackConfig(path: str)` nested model (note: same name as rolepack loader's model — use `ConfigRolePackConfig` to avoid collision or house in separate namespace; see Dev Notes)
  - [x] Define `DatabaseConfig(host: str, port: int, user: str, password: SecretStr, dbname: str)` with `@property connection_url() -> str` that returns `postgresql+psycopg://{user}:{password.get_secret_value()}@{host}:{port}/{dbname}`
  - [x] Define `CosConfig(llm: LLMConfig, embedding: EmbeddingConfig, role_pack: RolePackConfig, channels: list[str], connectors: list[str], database: DatabaseConfig)` as the root model
  - [x] Add `@classmethod def load(cls, path: str | Path = "config.yaml") -> "CosConfig":` that reads YAML with `yaml.safe_load()`, then passes the dict to `cls.model_validate()`; wraps `ValidationError` in a `SystemExit` with a human-readable formatted message
  - [x] Ensure `SecretStr` fields never appear in `repr()`, `str()`, or logging — verify Pydantic v2's default `SecretStr` masking is active

- [x] Task 3: Mount `config.yaml` into the `cos` container (AC: #1, #3)
  - [x] Add `./config.yaml:/app/config.yaml:ro` bind mount to the `cos` service volumes in `docker-compose.yml`
  - [x] Update `config.yaml.example` to include the `embedding.api_key` field (optional, `null` when provider shares the LLM key) — add a comment explaining when it is needed
  - [x] Verify `config.yaml` remains in `.gitignore` and `config.yaml.example` is NOT ignored

- [x] Task 4: Wire `CosConfig.load()` into the MCP server startup (AC: #1, #2)
  - [x] In `src/cos/mcp_server/server.py`, call `CosConfig.load()` at server startup before any other initialisation
  - [x] Log a structured JSON startup message: `{"timestamp": "...", "level": "INFO", "component": "mcp_server", "message": "config loaded", "role_pack_path": "<path>"}` — never log any key values
  - [x] If `CosConfig.load()` raises `SystemExit`, the container exits with a readable error; no further startup proceeds

- [x] Task 5: Write tests for `CosConfig` (AC: #1, #2, #4, #5)
  - [x] `tests/test_config.py` — create this file (no existing equivalent in 1.1 scaffold)
  - [x] Test: valid YAML with all required keys → `CosConfig` instance with correct field values
  - [x] Test: YAML missing `llm` section → `SystemExit` raised; error message includes the word `llm`
  - [x] Test: YAML missing nested required field (e.g. `llm.api_key`) → `SystemExit`; error message identifies the missing field
  - [x] Test: `repr(config)` and `str(config)` do not contain the literal API key value — confirm `SecretStr` masking
  - [x] Test: `config.database.connection_url` returns a well-formed `postgresql+psycopg://...` URL

## Dev Notes

### Naming Collision: `RolePackConfig`

`cos/rolepack/loader.py` (from Story 1.1) already defines a `RolePackConfig` stub. Story 1.2 defines a `RolePackConfig` as a nested config model inside `CosConfig`. These are different things:

- `cos/config.py` → the operator-level config struct (just a `path: str`)
- `cos/rolepack/loader.py` → the full role pack definition loaded from the YAML file at that path

**Resolution:** Name the config-level model `RolePackRef` (or `RolePackPathConfig`) in `cos/config.py` to avoid the collision. Update `config.yaml.example` comments accordingly if needed. The `RolePackConfig` name stays in `cos/rolepack/loader.py` for the richer loaded model.

### `CosConfig.load()` — Pattern

```python
import yaml
from pathlib import Path
from pydantic import BaseModel, SecretStr, ValidationError

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
            return cls.model_validate(data)
        except FileNotFoundError:
            raise SystemExit(f"Config file not found: {path}\nCopy config.yaml.example to config.yaml and fill in your values.")
        except ValidationError as exc:
            raise SystemExit(f"Invalid config.yaml:\n{exc}")
```

The `SystemExit` approach surfaces a human-readable error in `docker compose logs` without a Python traceback overwhelming the operator.

### `SecretStr` — Key Masking

Pydantic v2's `SecretStr` returns `'**********'` from `repr()` and `str()`. **Never** call `.get_secret_value()` in any logging statement. The `connection_url` property is the only place where `.get_secret_value()` is acceptable — and the returned URL string must never be logged.

```python
# CORRECT — masked in repr
llm_provider = config.llm.provider  # log this if needed

# WRONG — exposes secret
logging.info(json.dumps({"api_key": config.llm.api_key.get_secret_value()}))

# CORRECT — connection_url is used internally only, never logged
pool = await asyncpg.create_pool(config.database.connection_url)
```

### `DatabaseConfig.connection_url`

psycopg3 (not asyncpg) is the driver. The connection string format for psycopg3 is:

```
postgresql+psycopg://user:password@host:port/dbname
```

This is used when constructing the psycopg3 async pool in Story 1.3. Expose it as a `@property` on `DatabaseConfig` so no other module constructs a connection string manually.

### docker-compose.yml Volume Mount

The `cos` service currently has no visibility of `config.yaml`. Add a read-only bind mount:

```yaml
cos:
  ...
  volumes:
    - ./data:/data
    - ./config.yaml:/app/config.yaml:ro   # ADD THIS
```

The `CosConfig.load()` default path `"config.yaml"` must resolve relative to the container working directory `/app`. Confirm the `Dockerfile` sets `WORKDIR /app`.

### Open Decision from Story 1.1 (carry forward)

The Story 1.1 review flagged that `component: "output"` is not in the allowed logging component enum (`ingestion`, `retrieval`, `mcp_server`, `cli`, `scheduler`, `connector`). This story is a good place to resolve it:

- **Option A:** Add `"output"` and `"config"` to the allowed component list in the architecture and enforce in all future stories
- **Option B:** Map `OutputRouter` logging to `component: "mcp_server"` (as it is called from there in Phase 1)

Recommended: **Option A** — add `"output"` and `"config"` to the allowed set. The `CosConfig.load()` error logging will want `component: "config"`. Document the resolution in this story's Dev Agent Record.

### Config File Path in Tests

Tests should use `tmp_path` (pytest fixture) to write a temp `config.yaml` and pass its path to `CosConfig.load()` — never rely on a real `config.yaml` in the repo.

```python
def test_valid_config_loads(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(VALID_CONFIG_YAML)
    config = CosConfig.load(cfg_file)
    assert config.llm.provider == "anthropic"
```

### Anti-Patterns (must not appear in this story)

```python
# WRONG — reading config directly (config boundary violation)
import yaml; cfg = yaml.safe_load(open("config.yaml"))  # in any file other than config.py

# WRONG — logging a secret
logging.info(f"API key: {config.llm.api_key}")

# WRONG — logging the connection URL
logging.info(f"Connecting to {config.database.connection_url}")

# WRONG — constructing connection string outside DatabaseConfig
dsn = f"postgresql://{config.database.user}:{config.database.password}@..."
```

### Files to Create or Modify

| File | Action | Notes |
|---|---|---|
| `src/cos/config.py` | Modify | Replace stub with full implementation |
| `docker-compose.yml` | Modify | Add config.yaml bind mount to cos service |
| `pyproject.toml` | Modify | `uv add pyyaml` |
| `uv.lock` | Modify | Updated by uv |
| `config.yaml.example` | Modify | Add `embedding.api_key: null` with comment |
| `tests/test_config.py` | Create | Config loading tests (not in existing test scaffold) |

No other files should be modified. Do not touch `cos/rolepack/loader.py` — the naming collision is resolved in `config.py` only.

### References

- Config boundary rule: [Source: architecture.md#Config Boundary]
- Pydantic v2 settings model: [Source: architecture.md#Scaffold Approach]
- SecretStr / key security: [Source: architecture.md#Authentication & Security] (NFR5, NFR6)
- Anti-patterns: [Source: architecture.md#Enforcement Guidelines]
- Logging format: [Source: architecture.md#Format Patterns]
- Story requirements: [Source: epics.md#Story 1.2]
- Story 1.1 deferred item — no env vars for Postgres: [Source: 1-1-project-scaffold.md#Review Findings]
- Story 1.1 deferred item — component enum gap: [Source: 1-1-project-scaffold.md#Review Findings]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation proceeded without issues.

### Completion Notes List

- Replaced stub `CosConfig(BaseSettings)` with full `CosConfig(BaseModel)` using Pydantic v2. Switched from `pydantic_settings.BaseSettings` to `pydantic.BaseModel` as story specifies manual YAML loading via `yaml.safe_load()` + `model_validate()`, not env-var-based settings.
- Resolved naming collision per Dev Notes: used `RolePackRef` in `cos/config.py` (not `RolePackConfig`). `rolepack/loader.py` unchanged.
- Open decision from Story 1.1 resolved: chose **Option A** — `"output"` and `"config"` are valid logging component values. `mcp_server/server.py` logs `component: "mcp_server"` for the startup message; future config-level error logging will use `component: "config"`.
- `DatabaseConfig.connection_url` uses `postgresql+psycopg://` format for psycopg3.
- All `SecretStr` fields (`llm.api_key`, `embedding.api_key`, `database.password`) masked in repr/str by Pydantic v2 default.
- `CosConfig.load()` wraps `FileNotFoundError` and `ValidationError` in `SystemExit` with human-readable messages.
- MCP server startup logs structured JSON with `role_pack_path` only — no key values logged.
- 6 new tests in `tests/test_config.py`. All 22 tests pass. Ruff lint clean.

### File List

- `cos/src/cos/config.py` — modified (full implementation replacing stub)
- `cos/src/cos/mcp_server/server.py` — modified (wired CosConfig.load() at startup)
- `cos/docker-compose.yml` — modified (added config.yaml bind mount)
- `cos/pyproject.toml` — modified (added pyyaml>=6.0.3 dependency)
- `cos/uv.lock` — modified (updated by uv add pyyaml)
- `cos/config.yaml.example` — modified (added embedding.api_key: null with comment)
- `cos/tests/test_config.py` — created (6 config loading tests)

## Review Findings

- [x] [Review][Decision] Component enum resolution — resolved: added `LogComponent = Literal[...]` type alias to `config.py`; `_log_startup` now uses typed variable [`cos/src/cos/config.py`, `cos/src/cos/mcp_server/server.py`]
- [x] [Review][Decision] `.gitignore` AC 6 ambiguity — resolved: added `!config.yaml.example` negation rule with clarifying comment [`cos/.gitignore`]
- [x] [Review][Patch] `connection_url` resolves `SecretStr` to plaintext — skipped: spec explicitly permits `get_secret_value()` here; constraint is "must never be logged" (developer discipline) [`cos/src/cos/config.py:31-35`]
- [x] [Review][Patch] `test_database_connection_url` asserts plaintext secret appears in URL — skipped: test correctly verifies URL is well-formed; per spec this is the only acceptable exposure point [`cos/tests/test_config.py:92-96`]
- [x] [Review][Patch] `yaml.YAMLError` not caught — fixed: added `except yaml.YAMLError` with clean `SystemExit` message [`cos/src/cos/config.py`]
- [x] [Review][Patch] `yaml.safe_load` returns `None` on empty file — fixed: added `isinstance(data, dict)` guard with informative message [`cos/src/cos/config.py`]
- [x] [Review][Patch] `port` accepts out-of-range integers — fixed: added `Field(ge=1, le=65535)` constraint [`cos/src/cos/config.py`]
- [x] [Review][Patch] `_log_startup` calls `logging.info` before any handler is configured — fixed: added `logging.basicConfig(level=logging.INFO, format="%(message)s")` in `run()` [`cos/src/cos/mcp_server/server.py`]
- [x] [Review][Defer] Docker healthcheck tests only `import cos`, not config validity or service readiness [`cos/docker-compose.yml:40`] — deferred, pre-existing
- [x] [Review][Defer] `RolePackRef.path` unvalidated — no check it is relative, within bounds, or exists [`cos/src/cos/config.py:19-20`] — deferred, pre-existing
- [x] [Review][Defer] `channels`/`connectors` accept empty lists and arbitrary strings — no enum or minimum-length validation [`cos/src/cos/config.py:43-44`] — deferred, pre-existing
- [x] [Review][Defer] `config.yaml.example` has `password: postgres` with no `CHANGE_ME` warning [`cos/config.yaml.example:25`] — deferred, pre-existing
- [x] [Review][Defer] Default `CosConfig.load()` path resolves relative to process cwd — fragile outside Docker [`cos/src/cos/config.py:47`] — deferred, pre-existing

## Change Log

- 2026-04-20: Story 1.2 implemented — CosConfig with Pydantic v2, pyyaml dependency, docker-compose volume mount, MCP server wiring, 6 tests. All 22 suite tests pass, lint clean.
