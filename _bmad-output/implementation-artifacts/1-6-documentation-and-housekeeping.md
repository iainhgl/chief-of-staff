# Story 1.6: Documentation & Housekeeping

Status: done

## Story

As Iain (operator and platform maintainer),
I want all documentation to accurately reflect the platform as built at the end of Epic 1,
So that any technically competent person can provision, configure, and operate the platform foundation without assistance.

## Acceptance Criteria

1. **Given** `docs/setup.md` is reviewed,
   **When** a technically competent person follows it on a clean machine,
   **Then** it covers: prerequisites (Docker, uv), cloning the repo, copying `config.yaml.example` to `config.yaml` and filling in required values, running `docker compose up -d`, verifying health with `docker compose ps`, configuring Claude Desktop or Claude Code to connect to the MCP server, and the three-step restart procedure (`docker compose down` → `docker compose up -d` → verify).

2. **Given** `README.md` is reviewed,
   **When** it is read by a new visitor,
   **Then** it describes what the platform is, the **current Phase 1 capabilities** (accurate to what was actually built — not the full roadmap), how to get started (link to `docs/setup.md`), and the project structure at a high level.

3. **Given** any decisions or implementation details that deviated from `architecture.md` during Epic 1,
   **When** `architecture.md` is reviewed,
   **Then** those deviations are documented: either the architecture is updated to reflect the actual decision, or a note is added explaining why the spec was not followed and what was done instead.

4. **Given** the `config.yaml.example` template,
   **When** it is reviewed,
   **Then** every key required by `CosConfig` is present with a descriptive comment, the file is complete enough that a new operator can fill it in without reading source code, and it matches the actual `CosConfig` Pydantic model exactly.

5. **Given** all four documents (`docs/setup.md`, `README.md`, `architecture.md`, `config.yaml.example`) are reviewed together,
   **When** they are compared for consistency,
   **Then** there are no contradictions between them — file paths, command syntax, and capability descriptions are consistent across all four.

## Tasks / Subtasks

- [x] Task 1: Update `docs/setup.md` (AC: #1, #5)
  - [x] Add "Clone the repository" step before configuration
  - [x] Replace `cos status` with `docker compose ps` (CLI is a stub — `cos status` raises NotImplementedError)
  - [x] Replace `cos logs` with `docker compose logs cos` (CLI stub)
  - [x] Remove `cos ingest` section entirely (CLI stub — not available in Epic 1)
  - [x] Add MCP server configuration section: both Claude Code (`claude mcp add`) and Claude Desktop (`claude_desktop_config.json`) variants
  - [x] Verify restart procedure matches three steps: down → up -d → verify with `docker compose ps`

- [x] Task 2: Update `README.md` (AC: #2, #5)
  - [x] Fix capability description: remove "email, calendar" references (Phase 2 only); describe only what Phase 1 actually delivers
  - [x] Add "Current capabilities" section accurately reflecting Epic 1: containerised platform, MCP server with `get_status`, three stub tools (`retrieve`, `get_role_context`, `list_documents` return "not yet implemented")
  - [x] Add "Get started" section with a link to `docs/setup.md`
  - [x] Add project structure section (high-level directory overview matching actual `cos/` layout)

- [x] Task 3: Document Epic 1 deviations in `architecture.md` (AC: #3)
  - [x] Add an "Epic 1 Implementation Notes" section at the end of the document recording the following deviations:
    1. **`TikaConfig` added to `CosConfig`** — architecture spec did not include a `tika` sub-section in `CosConfig`; Story 1.4 added `TikaConfig(url: str = "http://tika:9998")` to support health checks and future extraction calls
    2. **Startup health checks duplicated** — `server.py` contains standalone `_check_postgres(dsn)` and `_check_tika(url)` functions used during `_startup_sequence`; `HealthService` in `cos/services/health.py` contains identical implementations used by `get_status`. The service layer boundary is partially violated at startup
    3. **`_config` module-level global in `server.py`** — config is held as `_config: CosConfig | None = None` (module-level mutable state) rather than being injected via dependency. Pragmatic choice given FastMCP's decorator-based tool registration pattern; deviates from the injection-preferred architecture
    4. **CLI commands are stubs** — `cos status`, `cos restart`, `cos logs`, `cos ingest` all raise `NotImplementedError`; will be implemented in a later epic
    5. **Role pack file not yet created** — `config.yaml.example` references `role_packs/chro.yaml`; this file does not exist; the server logs "role pack: stub loaded" without loading a file; Epic 4 will create the role pack and implement loading

- [x] Task 4: Improve `config.yaml.example` comments (AC: #4, #5)
  - [x] Add a descriptive comment above every key block explaining what it controls
  - [x] Add a note that `database.password` must match the value in `docker-compose.yml` (currently hardcoded to `postgres` in `docker-compose.yml`)
  - [x] Add a note that `role_pack.path` references a file that does not yet exist (`role_packs/chro.yaml` is created in Epic 4)
  - [x] Clarify `embedding.api_key`: explain when it must be set (if embedding provider uses a different API key than the LLM provider)
  - [x] Verify that the example file matches the actual `CosConfig` Pydantic model fields exactly: `llm`, `embedding`, `role_pack`, `channels`, `connectors`, `database`, `tika` — all present with sensible defaults

- [x] Task 5: Cross-check consistency (AC: #5)
  - [x] Verify command syntax is identical in all docs that mention the same commands
  - [x] Verify MCP setup instructions in `docs/setup.md` match the working commands confirmed in Story 1.5 (`T1.5.2`)
  - [x] Verify no document describes capabilities beyond what Epic 1 actually delivers

### Review Findings

- [x] [Review][Patch] Malformed JSON in Claude Desktop config block — flagged by reviewers but file on disk is correct (3 closing braces, valid JSON); display artifact in initial diff capture [docs/setup.md:Claude Desktop JSON block]
- [x] [Review][Patch] Database section header comment is wrong (copy-paste from LLM section) — flagged by reviewers but file on disk already reads "Connection settings for the Postgres instance managed by Docker Compose"; display artifact in initial diff capture [config.yaml.example:database section comment]
- [x] [Review][Defer] `claude mcp add` has no cwd equivalent — asymmetry with Claude Desktop `"cwd"` field; command was validated working in Story 1.5, Claude Code scopes command to project context [docs/setup.md:Claude Code MCP section] — deferred, pre-existing
- [x] [Review][Defer] Restart removes `sleep 3` without guarantee — `docker compose down` waits for containers to stop before returning so immediate port conflict is low probability; spec explicitly prescribed this procedure [docs/setup.md:Restart section] — deferred, pre-existing
- [x] [Review][Defer] Role pack path references file that doesn't exist — pre-existing, intentional, and now explicitly documented in the config.yaml.example comment itself [config.yaml.example:role_pack section] — deferred, pre-existing
- [x] [Review][Defer] `cd cos` assumes repo cloned to default directory name — minor; spec did not call for handling this edge case [docs/setup.md:Clone section] — deferred, pre-existing

## Dev Notes

### What Already Exists — Audit Before Touching

Read each file before editing. Several already have good content and only need targeted gaps filled.

| File | Current state | What's missing |
|---|---|---|
| `docs/setup.md` | Has prerequisites, config copy, start, restart | No clone step; `cos status`/`cos logs` are stubs; no MCP config section |
| `README.md` | Describes platform concept, design principles, stack | References "email, calendar" (Phase 2 only); no Get Started link; no project structure |
| `architecture.md` | Complete architecture spec | No Epic 1 deviation notes |
| `config.yaml.example` | Has all required keys with tika section | Comments are sparse — new operator cannot fill it in without reading source code |

### CLI Stubs — Critical

All CLI commands currently raise `NotImplementedError`:
```python
# cos/src/cos/cli.py
@app.command()
def status() -> None:
    raise NotImplementedError

@app.command()
def restart() -> None:
    raise NotImplementedError

@app.command()
def logs() -> None:
    raise NotImplementedError

@app.command()
def ingest(path: str = ...) -> None:
    raise NotImplementedError
```

**`docs/setup.md` must NOT reference `cos status`, `cos logs`, or `cos ingest`.** Use working alternatives:
- `cos status` → `docker compose ps`
- `cos logs` → `docker compose logs cos`
- `cos ingest` → not yet available; omit entirely

### MCP Server Configuration (from Story 1.5 T1.5.2)

The working MCP setup command for Claude Code (run from `cos/` directory):
```bash
claude mcp add cos -- docker compose exec -i cos uv run cos-mcp
```

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "cos": {
      "command": "docker",
      "args": ["compose", "exec", "-i", "cos", "uv", "run", "cos-mcp"],
      "cwd": "/absolute/path/to/cos"
    }
  }
}
```

The `cos` container runs `uv run cos-mcp` as its persistent process. The MCP client starts a *second* `cos-mcp` instance inside the same container via `docker compose exec -i` (stdio transport). Both instances share Postgres and config — this is safe and expected.

### CosConfig Model — Current Actual Fields

```python
class CosConfig(BaseModel):
    llm: LLMConfig          # provider, model, api_key
    embedding: EmbeddingConfig  # provider, model, api_key (optional)
    role_pack: RolePackRef  # path: str
    channels: list[str]
    connectors: list[str]
    database: DatabaseConfig  # host, port, user, password, dbname
    tika: TikaConfig = TikaConfig()  # url: str = "http://tika:9998"
```

`config.yaml.example` currently has all these keys. The gap is descriptive comments, not missing keys.

### docker-compose.yml Reality Check

- Postgres password hardcoded in `docker-compose.yml` as `POSTGRES_PASSWORD: postgres`
- `config.yaml.example` database.password must match this: `password: postgres`
- If operator changes the password in `config.yaml` they must also update `docker-compose.yml` — document this constraint
- `./data:/data` volume mounted for document storage (not yet used in Epic 1 but present)
- No host ports on the `cos` container — MCP uses stdio, not TCP

### README Phase 1 Capabilities (Accurate)

What Epic 1 actually delivers:
- Three-container platform (postgres/pgvector, Tika, cos) that starts with `docker compose up -d`
- Config validation at startup with human-readable errors for bad config
- Database schema applied automatically on startup (idempotent migrations)
- MCP server accessible via `docker compose exec` stdio transport
- **`get_status`** tool: returns JSON with health of all three components (cos, postgres, tika) and `ready` flag
- **`retrieve`**, **`get_role_context`**, **`list_documents`**: registered tools that return "Not yet implemented" error envelopes (not exceptions)

What Epic 1 does NOT deliver (do not mention in README):
- Document ingestion
- Knowledge retrieval
- Role pack loading from file
- CLI commands
- Connected sources (email, calendar, Telegram)

### architecture.md Deviations — Exact Wording Guidance

Add as a new section `## Epic 1 Implementation Notes` at the very end of `architecture.md`, before any trailing newline. Keep it concise — one paragraph or a short table per deviation. The audience is future dev agents and maintainers, not operators.

### Files to Create or Modify

| File | Action |
|---|---|
| `cos/docs/setup.md` | Modify — targeted gaps only (don't rewrite what's already correct) |
| `cos/README.md` | Modify — targeted additions only |
| `cos/_bmad-output/planning-artifacts/architecture.md` | Modify — append deviations section only |
| `cos/config.yaml.example` | Modify — add descriptive comments |

Do NOT touch any source code files. This story is documentation only.

### References

- Working MCP setup command: [Source: cos/docs/manual-testing.md#T1.5.2]
- CosConfig model: [Source: cos/src/cos/config.py]
- CLI stubs: [Source: cos/src/cos/cli.py]
- docker-compose.yml: [Source: cos/docker-compose.yml]
- Architecture: [Source: _bmad-output/planning-artifacts/architecture.md]
- Epic 1 deviations noted in code review: [Source: _bmad-output/implementation-artifacts/deferred-work.md]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Completion Notes List

- **Task 1 (`docs/setup.md`):** Added clone step; replaced `cos status` with `docker compose ps`; replaced `cos logs` with `docker compose logs cos`; removed `cos ingest` section; added full MCP configuration section covering both Claude Code (`claude mcp add`) and Claude Desktop (`claude_desktop_config.json`) variants; verified three-step restart procedure (down → up -d → verify).
- **Task 2 (`README.md`):** Replaced "email, calendar" capability description with accurate Epic 1 capabilities (`get_status`, three stub tools); added "Current Capabilities (Epic 1)" section with explicit disclaimer of what is not yet available; added "Get Started" section linking to `docs/setup.md`; added project structure directory overview.
- **Task 3 (`architecture.md`):** Appended `## Epic 1 Implementation Notes` section documenting all five deviations: `TikaConfig` addition, duplicated startup health checks, `_config` module-level global, CLI stubs, and missing role pack file.
- **Task 4 (`config.yaml.example`):** Added descriptive comment blocks above every key section; documented that `database.password` must match `POSTGRES_PASSWORD` in `docker-compose.yml`; added note that `role_packs/chro.yaml` does not exist until Epic 4; clarified `embedding.api_key` usage; verified all seven `CosConfig` fields are present (`llm`, `embedding`, `role_pack`, `channels`, `connectors`, `database`, `tika`).
- **Task 5 (cross-check):** Confirmed no CLI stub references remain in any doc; MCP command matches T1.5.2; no doc describes capabilities beyond Epic 1.

### File List

- `cos/docs/setup.md`
- `cos/README.md`
- `_bmad-output/planning-artifacts/architecture.md`
- `cos/config.yaml.example`

## Change Log

- 2026-04-22: Story created
- 2026-04-22: Implementation complete — all four documents updated, all five tasks checked, status set to review
