# Story 4.6: Documentation & Housekeeping

Status: done

## Story

As Iain (operator and platform maintainer),
I want complete documentation on how to author and activate role packs,
So that a new operator can configure the platform for a different role without needing to read source code.

## Acceptance Criteria

1. **Given** a new `docs/role-packs.md` guide is created, **When** it is reviewed, **Then** it covers: the purpose of a role pack, every field in `RolePackConfig` with an explanation and example value, how to create a new role pack YAML file, how to activate it by updating `config.yaml`, and how to verify it loaded correctly using `get_role_context`.

2. **Given** `docs/setup.md` is updated, **When** it is reviewed, **Then** it includes a reference to `docs/role-packs.md` for role configuration, and notes that the CHRO role pack is the default example.

3. **Given** the root `README.md` is updated, **When** it is reviewed, **Then** it describes that role identity is configuration-only, the `get_role_context` tool returns real role data (not a stub), and it links to `docs/role-packs.md` for authoring guidance. The current capabilities heading must reflect Epic 4.

4. **Given** any deviations from `architecture.md` that occurred during Epic 4, **When** `architecture.md` is reviewed, **Then** the role pack section accurately reflects what was built — the real `RolePackConfig` fields, loader behaviour, startup log changes, and the provider portability additions (`make_llm_adapter`, embedder registry).

5. **Given** all Epic 4 documents are reviewed together, **When** cross-checked, **Then** field names, file paths, and YAML structure are consistent across `docs/role-packs.md`, `config.yaml.example`, `role_packs/chro.yaml`, and `architecture.md`.

## Tasks / Subtasks

- [x] Task 1: Create `docs/role-packs.md` (AC: #1, #5)
  - [x] Write purpose section explaining what a role pack is and what it controls
  - [x] Document all 8 `RolePackConfig` fields with type, description, and example value
  - [x] Write "Create a role pack" section with complete YAML template
  - [x] Write "Activate a role pack" section — how to update `config.yaml role_pack.path`
  - [x] Write "Verify it loaded" section — call `get_role_context` and interpret the response

- [x] Task 2: Update `docs/setup.md` (AC: #2)
  - [x] Add "Configure the Role Pack" section that links to `docs/role-packs.md`

- [x] Task 3: Update `README.md` (AC: #3)
  - [x] Change heading from `## Current Capabilities (Epic 3)` to `## Current Capabilities (Epic 4)`
  - [x] Update `get_role_context` bullet to describe real role data (not stub)
  - [x] Add role-identity-as-configuration note and link to `docs/role-packs.md`
  - [x] Add `role_packs/` to project structure block and update `docs/` entry

- [x] Task 4: Add Epic 4 implementation notes to `architecture.md` (AC: #4, #5)
  - [x] Add `## Epic 4 Implementation Notes` section after Epic 3 notes
  - [x] Document the five deviations identified during Epic 4 (see Dev Notes)

## Dev Notes

### What This Story Is

Story 4.6 is the Epic 4 documentation and housekeeping story. **There are no code changes.** All changes are limited to:

| File | Action |
|------|--------|
| `docs/role-packs.md` | CREATE — new role pack authoring guide |
| `docs/setup.md` | ADD section — "Configure the Role Pack" referencing `role-packs.md` |
| `README.md` | UPDATE — Epic 4 capabilities heading, `get_role_context` bullet, project structure |
| `_bmad-output/planning-artifacts/architecture.md` | ADD — Epic 4 implementation notes section |

Do NOT modify: any file in `src/`, `tests/`, `role_packs/`, `test-docs/`, `docker-compose.yml`, `config.yaml.example`, or `docs/manual-testing.md`.

`docs/manual-testing.md` was fully updated in Story 4.5. Do not touch it.

---

### Task 1 — Exact content for `docs/role-packs.md`

Create the file at `docs/role-packs.md` with this exact content:

```markdown
# Role Packs

A role pack is a YAML file that defines who the CoS platform is for. It controls the role's name, goals, tone, knowledge focus, stakeholders, retrieval priorities, workflows, and output channels. Swapping the role pack changes the platform's identity without touching any code.

The CHRO role pack (`role_packs/chro.yaml`) and the Enterprise Architect role pack (`role_packs/enterprise_architect.yaml`) are provided as ready-to-use examples.

## Fields

Every role pack must include all eight fields. All fields are required — the platform will refuse to start if any are missing or the wrong type.

| Field | Type | Description |
|-------|------|-------------|
| `role_name` | string | Short display name for the role. Returned by `get_role_context` as `data.role_name`. |
| `goals` | list of strings | Strategic objectives the CoS assists with. Used to frame synthesis prompts. |
| `tone` | string | Single paragraph describing voice, style, and communication approach. Injected into every synthesis prompt. |
| `knowledge_taxonomy` | list of strings | Categories of domain knowledge the role relies on. Used to shape retrieval context. |
| `stakeholder_map` | map of string → string | Key stakeholders and one-sentence descriptions of their priorities. Injected into synthesis as stakeholder context. |
| `retrieval_priorities` | list of strings | Ordered list of document categories. Higher entries are weighted more heavily during hybrid search ranking. |
| `active_workflows` | list of strings | Workflow identifiers active for this role (e.g. `hr_diagnostic`, `ceo_board_prep`). Reserved for future workflow engine use. |
| `output_channels` | list of strings | Channels the platform is permitted to deliver output through. Use `["local"]` for MCP-only (Claude Code / Claude Desktop). |

## Create a role pack

Copy this template and fill in every field:

```yaml
role_name: My Role

goals:
  - First strategic objective
  - Second strategic objective

tone: Describe the voice and style here — one paragraph is enough. Be specific about what to avoid as well as what to aim for.

knowledge_taxonomy:
  - Domain knowledge category 1
  - Domain knowledge category 2

stakeholder_map:
  Stakeholder Name: One sentence describing their priorities and what lens they apply.
  Another Stakeholder: What they care about and how they judge success.

retrieval_priorities:
  - Most important document category
  - Second priority category
  - General documents

active_workflows:
  - workflow_identifier

output_channels:
  - local
```

Save the file anywhere inside the `cos/` directory (convention: `role_packs/<slug>.yaml`).

## Activate a role pack

Open `config.yaml` and set `role_pack.path` to the path of your new file, relative to the `cos/` directory:

```yaml
role_pack:
  path: role_packs/my-role.yaml
```

Then restart the platform for the change to take effect:

```bash
docker compose down
docker compose up -d
```

## Verify it loaded

Call `get_role_context` from a connected Claude session:

```text
Call get_role_context and show me the raw JSON response.
```

A successful load returns all eight fields:

```json
{
  "status": "ok",
  "data": {
    "role_name": "My Role",
    "goals": ["First strategic objective", ...],
    "tone": "...",
    "knowledge_taxonomy": [...],
    "stakeholder_map": {"Stakeholder Name": "..."},
    "retrieval_priorities": [...],
    "active_workflows": [...],
    "output_channels": ["local"]
  },
  "citations": []
}
```

If the file cannot be found or a required field is missing, the platform will log an error at startup and `get_role_context` will return an error envelope.
```

---

### Task 2 — Exact `docs/setup.md` addition

Add a new "Configure the Role Pack" section after the "Configure the MCP Server" section and before the "Restart the Platform" section. Insert the following block:

```markdown
## Configure the Role Pack

The platform ships with two example role packs: `role_packs/chro.yaml` (CHRO) and `role_packs/enterprise_architect.yaml` (Enterprise Architect). The active role pack is set in `config.yaml`:

```yaml
role_pack:
  path: role_packs/chro.yaml
```

To use a different role or author your own, see [docs/role-packs.md](role-packs.md) for the full authoring guide and field reference.
```

The anchor point for this insertion — find the heading `## Restart the Platform` and insert the new section immediately before it.

---

### Task 3 — Exact `README.md` changes

**Change 1 — heading:**

Find:
```
## Current Capabilities (Epic 3)
```
Replace with:
```
## Current Capabilities (Epic 4)
```

**Change 2 — `get_role_context` bullet (find and replace the entire bullet):**

Find:
```
- **`get_role_context`** — returns stub role context: `default — role pack not yet configured`; role-specific tone and retrieval weighting arrive in Epic 4
```

Replace with:
```
- **`get_role_context`** — returns the active role identity from the loaded role pack; `data.role_name` is the role's display name; the full response includes all eight `RolePackConfig` fields (`role_name`, `goals`, `tone`, `knowledge_taxonomy`, `stakeholder_map`, `retrieval_priorities`, `active_workflows`, `output_channels`)
```

**Change 3 — closing note (find and replace):**

Find:
```
Knowledge retrieval and Q&A with citations are now working. Role pack loading (tone, retrieval weighting, stakeholder context) is planned for Epic 4. Connected sources (email, calendar) are planned for Epic 6.
```

Replace with:
```
Knowledge retrieval and Q&A with citations are working. Role identity is fully configuration-driven — author a YAML file and point `config.yaml` at it; no code changes required. See [docs/role-packs.md](docs/role-packs.md) for the authoring guide. Connected sources (email, calendar) are planned for Epic 6.
```

**Change 4 — project structure `docs/` entry (find and replace):**

Find:
```
├── docs/
│   ├── setup.md              # setup, operations, and querying guide
│   └── manual-testing.md     # end-to-end operator validation tests
```

Replace with:
```
├── docs/
│   ├── setup.md              # setup, operations, and querying guide
│   ├── role-packs.md         # role pack authoring guide and field reference
│   └── manual-testing.md     # end-to-end operator validation tests
```

**Change 5 — add `role_packs/` to project structure (find and replace):**

Find:
```
├── config.yaml.example       # config template — copy to config.yaml and fill in
├── docker-compose.yml        # postgres, tika, cos services
├── Dockerfile                # cos container image
├── docs/
```

Replace with:
```
├── config.yaml.example       # config template — copy to config.yaml and fill in
├── docker-compose.yml        # postgres, tika, cos services
├── Dockerfile                # cos container image
├── role_packs/               # role pack YAML files — define who the platform serves
│   ├── chro.yaml             # CHRO example (default)
│   └── enterprise_architect.yaml  # Enterprise Architect example
├── docs/
```

---

### Task 4 — Epic 4 implementation notes for `architecture.md`

Add the following block after the Epic 3 Implementation Notes section (after line 780 or wherever the Epic 3 block ends):

```markdown
## Epic 4 Implementation Notes

The following deviations from the architecture spec occurred during Epic 4. Future agents should treat these as the actual state of the codebase.

| # | Deviation | Detail |
|---|-----------|--------|
| 1 | **`get_role_context` returns 8 fields under `data.role_name`, not a stub `data.role`** | Prior to Epic 4, `get_role_context` returned `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}`. After Epic 4, the real role pack is loaded at startup and `get_role_context` returns all eight `RolePackConfig` fields: `role_name`, `goals`, `tone`, `knowledge_taxonomy`, `stakeholder_map`, `retrieval_priorities`, `active_workflows`, `output_channels`. The top-level key inside `data` changed from `role` to `role_name`. Any code or tests that check `data.role` must be updated to `data.role_name`. |
| 2 | **Startup log: `"Role pack loaded"` replaces `"role pack: stub loaded"`; connection pool now opens after role pack** | Before Epic 4 the startup sequence logged `"role pack: stub loaded"` (component: `"mcp_server"`). After Epic 4, a structured log `{"level": "info", "component": "rolepack", "event": "Role pack loaded", "role_name": "<name>"}` is emitted when the role pack is successfully read. The connection pool log (`"connection pool: open"`) now appears after the role pack log — startup order changed from Epic 3. |
| 3 | **`OutputRouter` receives `output_channels` from the loaded role pack, not from `config.channels`** | The architecture spec described `channels` as a top-level config list. In the Epic 4 implementation, `OutputRouter` is initialised with `_loaded_role_pack.output_channels` rather than `config.channels`. For the CHRO role pack both values are `["local"]`, so behaviour is identical; but the authoritative source for permitted output channels is now the role pack, not the top-level config. |
| 4 | **`make_llm_adapter(config)` factory in `src/cos/llm/factory.py`** | The architecture spec described a provider-agnostic LLM interface without specifying a factory location. Epic 4 introduced `make_llm_adapter(config: CosConfig) -> LLMAdapter` in `src/cos/llm/factory.py`. `server.py` calls this factory at startup and no longer imports `AnthropicAdapter` directly. This is the correct extension point for adding new LLM providers. |
| 5 | **Embedder provider registry `_EMBED_PROVIDERS` in `src/cos/ingestion/embedder.py`** | The embedder now selects the embedding backend from a module-level registry `_EMBED_PROVIDERS: dict[str, Any]` keyed by provider name string. Adding a new embedding provider requires registering it in this dict; no changes to `CosConfig` or the ingestion pipeline are needed. |
```

Also update the Epic 3 envelope summary block (lines immediately after the Epic 3 table) to reflect the correct Epic 4 state. Find and replace:

```markdown
For clarity, the Epic 3 MCP envelopes in the running implementation are:
- `retrieve` → `{"status": "ok", "data": {"answer": "...", "citations": [...]}, "citations": [...]}`
- `list_documents` → `{"status": "ok", "data": {"documents": [...]}, "citations": []}`
- `get_role_context` → `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}`
- `get_status` → `{"status": "ok", "data": {"components": [...], "ready": true}, "citations": []}`
```

Replace with:

```markdown
For clarity, the Epic 3 MCP envelopes in the running implementation are:
- `retrieve` → `{"status": "ok", "data": {"answer": "...", "citations": [...]}, "citations": [...]}`
- `list_documents` → `{"status": "ok", "data": {"documents": [...]}, "citations": []}`
- `get_role_context` → `{"status": "ok", "data": {"role": "default — role pack not yet configured"}, "citations": []}` (Epic 3 only — see Epic 4 Implementation Notes for the updated shape)
- `get_status` → `{"status": "ok", "data": {"components": [...], "ready": true}, "citations": []}`
```

---

### Consistency Checklist (run before marking done)

Cross-check these values are identical across all affected files after making changes:

| Value | Correct form |
|-------|-------------|
| Role pack field: role identifier | `role_name` (not `role`) |
| `get_role_context` data key | `data.role_name` |
| Full field list | `role_name`, `goals`, `tone`, `knowledge_taxonomy`, `stakeholder_map`, `retrieval_priorities`, `active_workflows`, `output_channels` |
| CHRO role pack path | `role_packs/chro.yaml` |
| EA role pack path | `role_packs/enterprise_architect.yaml` |
| Role pack config key in `config.yaml` | `role_pack.path` |
| Startup log component | `"rolepack"` |
| Startup log event | `"Role pack loaded"` |
| New docs file | `docs/role-packs.md` |

### Previous Story Context (Story 4.5 completion)

Story 4.5 (operator validation) is done. The following is confirmed working and does not need to be validated again:
- `get_role_context` returns a real CHRO role pack with `data.role_name: "CHRO"` (not the old stub `data.role`)
- Startup log sequence: role pack loaded → connection pool open → server ready
- Both role packs (`chro.yaml` and `enterprise_architect.yaml`) are present in `role_packs/`
- `docs/manual-testing.md` is fully updated through Epic 4 — do not touch it

### Key File References

- Role pack schema: `src/cos/rolepack/loader.py` — `RolePackConfig` (8 required fields)
- Role pack loader: `src/cos/rolepack/loader.py:18-21` — `load(path: str) -> RolePackConfig`
- CHRO example: `role_packs/chro.yaml`
- Enterprise Architect example: `role_packs/enterprise_architect.yaml`
- Config key: `config.yaml.example:58-59` — `role_pack.path`
- LLM factory: `src/cos/llm/factory.py` — `make_llm_adapter(config)`
- Embedder registry: `src/cos/ingestion/embedder.py` — `_EMBED_PROVIDERS`
- MCP tool: `src/cos/mcp_server/tools.py` — `get_role_context`

## Dev Agent Record

### Agent Model Used

gpt-5

### Debug Log References

- 2026-04-29: User confirmed docs should follow the live implementation, not the original story wording that described `get_role_context` as returning all 8 role-pack fields.
- 2026-04-29: Cross-checked `src/cos/mcp_server/tools.py`, `src/cos/rolepack/loader.py`, `src/cos/mcp_server/server.py`, `config.yaml.example`, and both example role packs before updating docs.
- 2026-04-29: Validation run: `uv run pytest -q` → `142 passed, 1 skipped`.

### Completion Notes List

- Created `docs/role-packs.md` with the role-pack purpose, all 8 required `RolePackConfig` fields, a complete YAML template, activation steps via `role_pack.path`, and verification guidance for the live `get_role_context` response shape.
- Updated `docs/setup.md` and `README.md` so Epic 4 setup and capability docs consistently point operators to role-pack authoring and explain that role identity is configuration-only.
- Added Epic 4 implementation notes to `architecture.md`, including the actual 5-field `get_role_context` summary contract, startup log changes, role-pack-driven output channels, `make_llm_adapter(config)`, and `_EMBED_PROVIDERS`.
- Cross-checked field names, file paths, YAML examples, and startup-log references against the live repo files rather than the outdated story wording.

### File List

- README.md
- _bmad-output/implementation-artifacts/4-6-documentation-and-housekeeping.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/planning-artifacts/architecture.md
- docs/role-packs.md
- docs/setup.md

### Review Findings

- [x] [Review][Decision] Architecture Epic 3 envelope table — kept annotation approach; parenthetical `(Epic 3 only — see Epic 4 Implementation Notes)` is sufficient; historical shape preserved intentionally as baseline for the deviation notes
- [x] [Review][Patch] Link display/href mismatch in `docs/setup.md` — `[docs/role-packs.md](role-packs.md)` shows a repo-root path as link text but resolves as a same-directory relative href; inconsistent with README.md style [`docs/setup.md`]
- [x] [Review][Patch] Missing restart-loop warning in `docs/role-packs.md` — "the platform will refuse to start" does not warn operators that in Docker this means a container restart loop; should mention checking `docker compose logs cos` [`docs/role-packs.md`]
- [x] [Review][Patch] Log level case mismatch in `architecture.md` Deviation 2 — documents `"level": "info"` but `_emit()` emits `"INFO"` (uppercase); any log filter on lowercase `info` will miss the event [`_bmad-output/planning-artifacts/architecture.md`]
- [x] [Review][Defer] `active_workflows` no authoritative list of valid values — inherent to field being reserved for future use; defer until workflow engine is implemented
- [x] [Review][Defer] `output_channels` no valid values documented beyond `["local"]` — no other values currently exist in the platform; defer
- [x] [Review][Defer] `config.yaml.example` stale `channels` key contradicts Deviation 3 — explicitly out of scope per Dev Notes; pre-existing
- [x] [Review][Defer] `get_role_context` missing error envelope on unexpected exception — pre-existing code issue, not introduced by this story
- [x] [Review][Defer] Startup log at line 121 (`server.py`) still logs `config.channels` after switch to role-pack-driven channels — pre-existing code bug, not introduced by this story
- [x] [Review][Defer] Architecture note 5 partial truth about embedder transport type constraint — pre-existing design detail; the note accurately describes the public extension interface

### Change Log

- 2026-04-29: Completed Story 4.6 documentation updates for Epic 4 role-pack authoring and implementation notes; aligned docs with the live 5-field `get_role_context` contract after user confirmation.
