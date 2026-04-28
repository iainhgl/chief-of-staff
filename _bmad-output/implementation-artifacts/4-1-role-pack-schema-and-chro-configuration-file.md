# Story 4.1: Role Pack Schema & CHRO Configuration File

Status: done

## Story

As an operator,
I want to define a role identity in a structured YAML file covering goals, tone, knowledge taxonomy, stakeholder map, retrieval priorities, and active workflows,
so that who the CoS is for and how it behaves is captured entirely in configuration — not in code.

## Acceptance Criteria

1. **Given** `RolePackConfig` is defined as a Pydantic v2 model in `cos/rolepack/loader.py`, **When** the model is inspected, **Then** it contains typed fields for: `role_name` (str), `goals` (list[str]), `tone` (str), `knowledge_taxonomy` (list[str]), `stakeholder_map` (dict[str, str]), `retrieval_priorities` (list[str] ordered by weight), `active_workflows` (list[str]), and `output_channels` (list[str]).

2. **Given** the CHRO role pack YAML file is created (`role_packs/chro.yaml`), **When** it is reviewed against `initial_docs/CoS - CHRO.md`, **Then** it accurately reflects the CHRO role: goals covering workforce strategy and executive advisory, tone defined as strategic and evidence-based, knowledge taxonomy covering HR frameworks and org design, stakeholder map including CEO and exco members, and retrieval priorities weighting HR frameworks above general documents.

3. **Given** `config.yaml.example` is reviewed, **When** the `role_pack` section is examined, **Then** it includes a comment explaining that `role_pack.path` points to a YAML file that defines the active role identity (goals, tone, stakeholder map, retrieval priorities) — and the note about the file being a stub (pre-Epic 4) is removed.

4. **Given** a role pack YAML file with a missing required field (e.g. no `tone`), **When** `RolePackConfig` attempts to parse it, **Then** a Pydantic `ValidationError` is raised with a clear message identifying the missing field — not a cryptic Python exception.

## Tasks / Subtasks

- [x] Task 1: Define `RolePackConfig` Pydantic v2 model (AC: #1, #4)
  - [x] Replace stub `RolePackConfig(BaseModel): pass` in `src/cos/rolepack/loader.py` with the full typed model
  - [x] Fields: `role_name: str`, `goals: list[str]`, `tone: str`, `knowledge_taxonomy: list[str]`, `stakeholder_map: dict[str, str]`, `retrieval_priorities: list[str]`, `active_workflows: list[str]`, `output_channels: list[str]`
  - [x] All fields required (no Optional, no defaults) — Pydantic will raise `ValidationError` on missing fields automatically
  - [x] Confirm that a missing required field raises `ValidationError` with a human-readable message (Pydantic v2 default behaviour)

- [x] Task 2: Implement `load()` function in `src/cos/rolepack/loader.py` (AC: #4)
  - [x] Replace `raise NotImplementedError` in `load(path: str) -> RolePackConfig`
  - [x] Open and parse the file at `path` using `yaml.safe_load()`
  - [x] Pass the parsed dict to `RolePackConfig.model_validate(data)` — Pydantic validates and raises `ValidationError` with clear messages on bad input
  - [x] Raise `FileNotFoundError` (re-raise as-is) if the file does not exist — caller (Story 4.2) will translate this to a startup error message
  - [x] Raise `yaml.YAMLError` (re-raise as-is) if the file contains invalid YAML syntax — caller handles the message
  - [x] Do NOT catch and suppress errors here — `load()` is a pure parse function; error handling belongs in the startup sequence (Story 4.2)

- [x] Task 3: Create `role_packs/chro.yaml` (AC: #2)
  - [x] Create `role_packs/` directory at `cos/role_packs/` (same level as `src/`, `docs/`, `tests/`)
  - [x] Create `role_packs/chro.yaml` with content drawn from `initial_docs/CoS - CHRO.md`
  - [x] All eight `RolePackConfig` fields must be present with meaningful CHRO-appropriate values (see Dev Notes for full YAML)
  - [x] `retrieval_priorities` must be ordered — HR frameworks and transformation work first, general documents last
  - [x] `output_channels` must be `["local"]` — only the local MCP channel is available in Phase 1

- [x] Task 4: Update `config.yaml.example` role pack comment (AC: #3)
  - [x] In `config.yaml.example`, update the comment block above the `role_pack:` key
  - [x] Remove the paragraph that says the role pack loader is a stub in Epic 1 and the file doesn't exist
  - [x] Replace with a comment explaining what `role_pack.path` controls: the YAML file that defines the active role identity (goals, tone, knowledge taxonomy, stakeholder map, retrieval priorities, active workflows, output channels)

- [x] Task 5: Update tests in `tests/rolepack/test_loader.py` (AC: #1, #4)
  - [x] Remove the existing stub test `test_load_not_implemented`
  - [x] Add `test_load_valid_role_pack`: create a minimal valid YAML (all 8 fields), call `load()`, assert `RolePackConfig` returned with correct field values
  - [x] Add `test_load_missing_required_field`: create YAML omitting `tone`, call `RolePackConfig.model_validate()`, assert `ValidationError` raised and error message references `tone`
  - [x] Add `test_load_file_not_found`: call `load("nonexistent/path.yaml")`, assert `FileNotFoundError` raised
  - [x] Add `test_load_invalid_yaml`: write invalid YAML to a temp file, call `load()`, assert `yaml.YAMLError` raised
  - [x] Use `tmp_path` pytest fixture to write real YAML files for tests — no mocking of the file system

## Dev Notes

### Current State of rolepack/loader.py

`src/cos/rolepack/loader.py` already exists with a stub:

```python
from pydantic import BaseModel


class RolePackConfig(BaseModel):
    """Role pack configuration — schema defined in Story 4.1."""
    pass


def load(path: str) -> RolePackConfig:
    raise NotImplementedError
```

Replace this file entirely. Keep the same module structure (`RolePackConfig` class + `load()` function in the same file).

### Required imports for loader.py

```python
import yaml
from pydantic import BaseModel
```

No other imports are needed for Task 1 and Task 2.

### RolePackConfig Field Types (Pydantic v2)

| Field | Python type | Notes |
|---|---|---|
| `role_name` | `str` | Short identifier, e.g. `"CHRO"` |
| `goals` | `list[str]` | 2–5 bullet-style goal statements |
| `tone` | `str` | One sentence describing voice and style |
| `knowledge_taxonomy` | `list[str]` | Ordered categories of knowledge the role cares about |
| `stakeholder_map` | `dict[str, str]` | `{"Name/Role": "relationship or context"}` |
| `retrieval_priorities` | `list[str]` | Categories ordered high-to-low weight |
| `active_workflows` | `list[str]` | Workflow identifiers (e.g. `"hr_diagnostic"`) |
| `output_channels` | `list[str]` | Permitted channels (Phase 1: `["local"]`) |

All fields are required — no `Optional`, no `default`. Pydantic v2 will auto-generate a clear `ValidationError` if any field is absent.

### load() Implementation Pattern

Follow the same defensive pattern used in `src/cos/config.py` for parsing YAML + Pydantic — but simpler (no `SystemExit` here; let errors propagate):

```python
def load(path: str) -> RolePackConfig:
    with open(path) as f:          # raises FileNotFoundError if path does not exist
        data = yaml.safe_load(f)   # raises yaml.YAMLError on invalid syntax
    return RolePackConfig.model_validate(data)  # raises ValidationError on bad schema
```

Do NOT catch or suppress errors. The startup sequence (Story 4.2) will catch and convert them to human-readable `SystemExit` messages.

### CHRO YAML — Reference Content

Create `role_packs/chro.yaml` with the following structure (drawn from `initial_docs/CoS - CHRO.md`):

```yaml
role_name: CHRO

goals:
  - Drive HR transformation focused on PE value creation levers (productivity, cost, talent)
  - Provide strategic advisory to the CEO and exec team on workforce decisions
  - Diagnose and redesign the HR operating model for a PE-backed growth business
  - Develop CHRO executive presence and improve quality and speed of decision-making
  - Build a data-driven HR function with clear metrics and accountability

tone: Strategic and evidence-based — translate HR concepts into business and financial impact; be direct, concise, and commercially-minded; challenge assumptions; avoid HR jargon that doesn't land with a CEO or PE audience

knowledge_taxonomy:
  - HR operating models and transformation frameworks
  - PE value creation playbooks and workforce productivity levers
  - Org design and workforce segmentation
  - Executive communication and board preparation
  - Talent acquisition, retention, and attrition analysis
  - HR technology landscape and automation
  - Internal company context (org charts, headcount, financials)
  - Stakeholder intelligence and political dynamics

stakeholder_map:
  CEO: Primary accountability partner — focused on execution, growth, and commercial outcomes; needs HR framed in business impact
  PE Sponsor: Demands speed and data; value-creation lens on every HR decision; benchmarks against portfolio companies
  Exec Team: Practical operators; want clarity on how HR decisions affect their teams; sceptical of HR complexity
  HR Leadership Team: Need direction, capability building, and clear priorities; early-stage transformation fatigue risk
  Board: High-level governance; interested in risk, culture, and succession at a strategic level

retrieval_priorities:
  - HR frameworks and transformation work
  - PE value creation and workforce productivity content
  - Internal company data (org, headcount, attrition, financials)
  - Stakeholder intelligence and exec communications
  - External HR best practice and benchmarks
  - General documents

active_workflows:
  - hr_diagnostic
  - ceo_board_prep
  - weekly_prioritisation
  - communication_drafting

output_channels:
  - local
```

### config.yaml.example Update — Exact Change

Replace the existing `role_pack` section comment block. Current text (in full):

```yaml
# ─────────────────────────────────────────────
# Role Pack
# Points to the YAML file that defines the active role identity (goals, tone, stakeholder map).
# path: relative path from the cos/ directory to the role pack file.
#
# NOTE: role_packs/chro.yaml does not exist yet. The role pack loader is a stub in Epic 1.
# The server will log "role pack: stub loaded" without reading this file.
# The actual role pack file and loader are implemented in Epic 4.
# ─────────────────────────────────────────────
role_pack:
  path: role_packs/chro.yaml
```

Replace with:

```yaml
# ─────────────────────────────────────────────
# Role Pack
# Points to the YAML file that defines the active role identity.
# The role pack controls: role_name, goals, tone, knowledge_taxonomy,
# stakeholder_map, retrieval_priorities, active_workflows, output_channels.
# path: path relative to the cos/ directory to the role pack YAML file.
# Example: role_packs/chro.yaml is the CHRO role pack provided with the platform.
# ─────────────────────────────────────────────
role_pack:
  path: role_packs/chro.yaml
```

### Architecture Boundaries — What This Story Does NOT Touch

- **`src/cos/services/rolepack.py`** — `RolePackService.get_active()` remains `raise NotImplementedError`. Wiring the loader to the service is Story 4.2.
- **`src/cos/mcp_server/server.py`** — startup sequence is not changed. The "role pack: stub loaded" log message remains. Startup integration is Story 4.2.
- **`src/cos/retrieval/search.py`** — no changes to retrieval ranking. Role pack applied to retrieval is Story 4.3.
- **`src/cos/llm/anthropic.py`** — no changes to synthesis prompt. Tone integration is Story 4.3.
- **`src/cos/mcp_server/tools.py`** — `get_role_context` still returns the stub response `"default — role pack not yet configured"`. That changes in Story 4.3.

Story 4.1 is purely: define schema → create CHRO YAML → update config example → write tests. Nothing else.

### Test File — Current State

`tests/rolepack/test_loader.py` currently contains only:

```python
import pytest

from cos.rolepack.loader import load


def test_load_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        load("path/to/role.yaml")
```

Replace entirely. Use `tmp_path` (pytest built-in fixture) to write real YAML files — no mocking.

### Test Pattern Using tmp_path

```python
def test_load_valid_role_pack(tmp_path: Path) -> None:
    yaml_file = tmp_path / "test_role.yaml"
    yaml_file.write_text("""
role_name: Test
goals:
  - Goal one
tone: Concise and direct
knowledge_taxonomy:
  - Category A
stakeholder_map:
  CEO: primary partner
retrieval_priorities:
  - Category A
active_workflows:
  - workflow_one
output_channels:
  - local
""")
    result = load(str(yaml_file))
    assert isinstance(result, RolePackConfig)
    assert result.role_name == "Test"
    assert result.tone == "Concise and direct"
    assert result.output_channels == ["local"]
```

### Existing Test Suite

All 116 tests (as of Story 3.6) must still pass after this story. Run `uv run pytest` before finalising. Linting: `uv run ruff check src/ tests/` — no new failures allowed.

### Project Structure Notes

- `role_packs/` directory is created at `cos/role_packs/` — same level as `src/`, `docs/`, `tests/`. This matches `config.yaml.example` which sets `role_pack.path: role_packs/chro.yaml` (relative to the `cos/` repo root).
- `src/cos/rolepack/loader.py` — this file exists; replace its contents, do not create a new file.
- `tests/rolepack/test_loader.py` — this file exists; replace its contents, do not create a new file.
- `tests/rolepack/__init__.py` — should already exist (pytest discovers tests without it, but check if other test subdirectories have one and follow the same pattern).

### References

- `RolePackConfig` stub: `src/cos/rolepack/loader.py`
- `RolePackService` stub: `src/cos/services/rolepack.py`
- CHRO reference document: `initial_docs/CoS - CHRO.md`
- Config model pattern: `src/cos/config.py` — shows YAML-load + Pydantic pattern; `load()` here should be simpler (no SystemExit)
- Architecture role pack boundary: `_bmad-output/planning-artifacts/architecture.md` — "Role Pack Management (FR21–24) → `cos/rolepack/`, `cos/services/rolepack.py`"
- Architecture FR21: "Operator can define a role pack in a configuration file specifying role goals, tone and style rules, knowledge taxonomy, active workflows, stakeholder map, and retrieval priorities"
- Epic 4 overview: `_bmad-output/planning-artifacts/epics.md` line 811

## Dev Agent Record

### Agent Model Used

Codex (GPT-5)

### Debug Log References

- `uv run pytest tests/rolepack/test_loader.py -q` (red): 4 failing tests against the stub loader and empty schema
- `uv run pytest tests/rolepack/test_loader.py -q` (green): 4 passed after implementing `RolePackConfig` and `load()`
- `uv run ruff check src/cos/rolepack/loader.py tests/rolepack/test_loader.py`: passed
- `uv run pytest`: 119 passed, 1 skipped
- `uv run ruff check src/ tests/`: existing unrelated Ruff failures remain in untouched files outside Story 4.1 scope

### Completion Notes List

- Replaced the stub role pack loader with a typed `RolePackConfig` Pydantic model and a pure YAML `load()` function that re-raises file, YAML, and validation errors cleanly.
- Added `role_packs/chro.yaml` with a complete CHRO role identity derived from the source brief, including ordered retrieval priorities and Phase 1 local output channels.
- Updated `config.yaml.example` so the role pack section now describes the active role identity contract instead of the old Epic 1 stub note.
- Replaced the stub role pack test with real filesystem-backed coverage for valid loading, missing required fields, missing files, and invalid YAML.
- Full regression suite passed with `uv run pytest`; targeted Ruff checks for touched files passed. Repo-wide Ruff still reports pre-existing issues in untouched files.

### File List

- src/cos/rolepack/loader.py
- role_packs/chro.yaml
- config.yaml.example
- tests/rolepack/test_loader.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/4-1-role-pack-schema-and-chro-configuration-file.md

### Change Log

- Implemented the Story 4.1 role pack schema and pure YAML loader in `src/cos/rolepack/loader.py`.
- Added the CHRO reference role pack at `role_packs/chro.yaml` and updated the example config commentary to document active role selection.
- Replaced the stub loader test with real YAML-backed validation coverage and confirmed the story with targeted Ruff plus a full pytest regression run.

### Review Findings

- [x] [Review][Patch] `open(path)` missing `encoding="utf-8"` — em-dashes in `chro.yaml` will be misread on non-UTF-8 platforms [`src/cos/rolepack/loader.py:19`]
- [x] [Review][Patch] `test_load_valid_role_pack` only asserts 4 of 8 required fields — `knowledge_taxonomy`, `stakeholder_map`, `retrieval_priorities`, `active_workflows` unverified [`tests/rolepack/test_loader.py`]
- [x] [Review][Defer] Empty file → `yaml.safe_load` returns `None` → confusing Pydantic ValidationError [`src/cos/rolepack/loader.py:20-21`] — deferred, Story 4.2 startup sequence handles error translation
- [x] [Review][Defer] Non-dict YAML (list/bare string) produces confusing ValidationError instead of a clear structure error [`src/cos/rolepack/loader.py:21`] — deferred, Story 4.2 handles
- [x] [Review][Defer] Empty lists accepted for all required `list[str]` fields (`goals: []` passes validation silently) — deferred, future Pydantic constraint addition
- [x] [Review][Defer] Empty strings accepted for `role_name` and `tone` fields — deferred, future `min_length=1` constraint
- [x] [Review][Defer] `active_workflows`/`output_channels` accept arbitrary strings with no enum or slug validation — deferred, out of scope for 4.1
- [x] [Review][Defer] No `model_config = ConfigDict(extra="forbid")` — typo'd YAML keys silently ignored — deferred, future enhancement
- [x] [Review][Defer] Relative `role_pack.path` resolved against process cwd — fragile if server not launched from `cos/` — deferred, Story 4.2 startup sequence concern
- [x] [Review][Defer] No schema version field in role pack YAML — no migration path when schema evolves — deferred, future concern
- [x] [Review][Defer] `stakeholder_map: dict[str, str]` silently coerces non-string YAML values (int/bool/null) to strings — deferred, acceptable for operator-supplied config
- [x] [Review][Defer] `retrieval_priorities` ordering contract (high-to-low weight) not documented in any user-facing comment or file — deferred, low-priority doc gap
