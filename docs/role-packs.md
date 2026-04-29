# Role Packs

A role pack is a YAML file that defines who the CoS platform is for. It controls the role's name, goals, tone, knowledge focus, stakeholders, retrieval priorities, workflows, and output channels. Swapping the role pack changes the platform's identity without touching any code.

The CHRO role pack (`role_packs/chro.yaml`) and the Enterprise Architect role pack (`role_packs/enterprise_architect.yaml`) are provided as ready-to-use examples.

## Fields

Every role pack must include all eight fields. All fields are required — the platform will refuse to start if any are missing or the wrong type.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `role_name` | string | Short display name for the role. Returned by `get_role_context` as `data.role_name`. | `CHRO` |
| `goals` | list of strings | Strategic objectives the CoS assists with. Used to frame synthesis prompts. | `["Drive HR transformation", "Support workforce decisions"]` |
| `tone` | string | Single paragraph describing voice, style, and communication approach. Injected into every synthesis prompt. | `Strategic and evidence-based; direct, concise, and commercially-minded.` |
| `knowledge_taxonomy` | list of strings | Categories of domain knowledge the role relies on. Used to shape retrieval context. | `["Org design", "Workforce productivity"]` |
| `stakeholder_map` | map of string to string | Key stakeholders and one-sentence descriptions of their priorities. Stored in the active role pack even though `get_role_context` does not expose this field directly. | `{"CEO": "Focused on execution and growth"}` |
| `retrieval_priorities` | list of strings | Ordered list of document categories. Higher entries are weighted more heavily during hybrid search ranking. | `["HR frameworks", "Internal company data", "General documents"]` |
| `active_workflows` | list of strings | Workflow identifiers active for this role (for example `hr_diagnostic`, `ceo_board_prep`). Reserved for future workflow engine use. | `["hr_diagnostic", "weekly_prioritisation"]` |
| `output_channels` | list of strings | Channels the platform is permitted to deliver output through. Use `["local"]` for MCP-only operation. | `["local"]` |

## Create a role pack

Copy this template and fill in every field:

```yaml
role_name: My Role

goals:
  - First strategic objective
  - Second strategic objective

tone: Describe the voice and style here. Be specific about what to avoid as well as what to aim for.

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

Save the file anywhere inside the `cos/` directory. The project convention is `role_packs/<slug>.yaml`.

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

A successful load returns the active role summary from the loaded pack:

```json
{
  "status": "ok",
  "data": {
    "role_name": "My Role",
    "goals": ["First strategic objective", "Second strategic objective"],
    "tone": "Describe the voice and style here.",
    "knowledge_taxonomy": ["Domain knowledge category 1", "Domain knowledge category 2"],
    "active_workflows": ["workflow_identifier"]
  },
  "citations": []
}
```

`get_role_context` confirms which role pack is active and exposes the fields currently returned by the MCP tool. The remaining required fields (`stakeholder_map`, `retrieval_priorities`, and `output_channels`) still live in the role-pack YAML and are enforced at startup even though they are not included in this response.

If the file cannot be found or a required field is missing, the platform logs an error at startup and exits. In Docker this causes a container restart loop — run `docker compose logs cos` before restarting to read the error.
