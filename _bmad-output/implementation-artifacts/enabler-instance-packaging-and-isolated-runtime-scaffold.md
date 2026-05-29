# Story EN.1: Instance Packaging and Isolated Runtime Scaffold

Status: review

## Story

As Iain, the CoS operator and platform maintainer,
I want a lightweight initializer that creates isolated CoS runtime instance folders,
so that I can run real knowledge-base instances side by side without mixing config, files, tokens, or Postgres storage with test and UAT data.

## Acceptance Criteria

1. Running the initializer with a destination path and instance name creates a complete instance folder containing `compose.yaml`, `.env`, `config.yaml`, `role_packs/`, `data/`, `tokens/`, and `local/certs/`.
2. The generated instance runs from a prebuilt local app image such as `cos-platform:local`; it must not require copying the application source tree into the instance folder.
3. Two generated instances with different names use distinct Compose project names, host ports, named volumes, and runtime folders so they can run side by side without data collision.
4. Gmail-enabled operation uses instance-local `tokens/`, `data/`, and Postgres storage. The generated config or docs include an example suitable for Substack-style Gmail ingestion, such as `label:cos-ai-reading newer_than:365d`.
5. Generated docs or printed next steps clearly distinguish repo development commands from isolated instance runtime commands.
6. The generated Compose file validates with Docker Compose config validation from the generated instance folder.

## Tasks / Subtasks

- [x] Add instance template assets (AC: 1, 2, 3, 5, 6)
  - [x] Create `templates/instance/compose.yaml.template`.
  - [x] Create `templates/instance/.env.template`.
  - [x] Use an image reference, defaulting to `cos-platform:${COS_IMAGE_TAG:-local}`, instead of a repo-local `build:`.
  - [x] Preserve the relevant health checks, dependencies, service names, and runtime mounts from the existing Compose setup.
  - [x] Use instance-local bind mounts for config, role packs, data, tokens, and local certs.
  - [x] Parameterize Compose project name, host ports, Postgres database settings, and named volumes so separate instances do not collide.

- [x] Add the initializer script (AC: 1, 2, 3, 5, 6)
  - [x] Create `scripts/init-instance.sh`.
  - [x] Require destination path and instance name arguments.
  - [x] Validate or sanitize the instance name for Compose-safe identifiers.
  - [x] Refuse to overwrite a non-empty destination unless an explicit safe option is implemented.
  - [x] Create the expected folder structure.
  - [x] Copy `role_packs/` into the instance folder.
  - [x] Generate or copy `config.yaml` from `config.yaml.example` with instance-appropriate paths and database settings.
  - [x] Render `.env` and `compose.yaml` from templates.
  - [x] Print concise next steps for building the local image, starting the instance, and running Gmail auth/sync in the isolated context.

- [x] Document the isolated runtime workflow (AC: 4, 5)
  - [x] Add or update docs explaining the side-by-side instance model.
  - [x] Document the intended first real-use shape for AI/Substack article ingestion via Gmail labels.
  - [x] Explain that paid Substack articles should initially flow through Gmail body ingestion rather than a new Substack connector.
  - [x] Note that regular CLI commands currently load `config.yaml` from the working directory, so the isolated folder intentionally contains its own config file.
  - [x] Document what remains repo-dev-only versus instance-runtime-only.

- [x] Add validation coverage (AC: 1, 3, 6)
  - [x] Add a script smoke test or Python test that runs the initializer against a temporary destination.
  - [x] Assert that generated files and directories exist.
  - [x] Assert that two generated instances produce distinct project names, ports, and volume names.
  - [x] Validate the generated Compose file with `docker compose -f <generated>/compose.yaml config` where available.
  - [x] Keep tests isolated under a temporary directory and do not write to the user home directory.

- [x] Update manual testing notes (AC: 4, 5, 6)
  - [x] Add a manual test covering image build, instance initialization, Compose config validation, and startup.
  - [x] Add a manual test note for Gmail/Substack label ingestion using an instance-local token directory and data store.

## Dev Notes

This is a standalone operational enabler created after Epic 8 completion. It is intentionally not part of Epic 9 and should not pull Epic 9 planning work forward.

The preferred lightweight implementation is a prebuilt app image plus a generated instance folder. The instance folder is the operational boundary: config, runtime data, Gmail tokens, local certs, Postgres volume names, and host ports all belong to that instance.

Do not implement a Substack connector in this story. Current product guidance is to ingest Substack articles through Gmail first because paid Substack content is delivered as email body content, and no stable official subscriber-side Substack API has been identified for this use case.

Do not implement a general config-profile system in this story unless it becomes necessary to satisfy the acceptance criteria. Current CLI behavior expects a local `config.yaml` for normal operations, so generating a real per-instance `config.yaml` is the simpler path.

Avoid copying source code, `.git`, `.venv`, local test data, or developer secrets into generated instance folders.

The generated Compose setup should preserve the existing repo service topology where relevant, especially Postgres, Tika, app/API service, worker, and Telegram bot behavior. If a service is not needed for instance startup, document the reason for excluding it.

Keep implementation small and reversible. This story is about packaging and runtime isolation, not backups, migrations, hosted image publishing, role-pack redesign, or Gmail connector feature expansion.

The repository currently has unrelated untracked local files. Do not touch them as part of this story.

## References

- Source design note: `_bmad-output/planning-artifacts/instance-packaging-design-2026-05-29.md`
- Current Compose baseline: `docker-compose.yml`
- Config baseline: `config.yaml.example`
- CLI/config loading behavior: `src/cos/cli.py`, `src/cos/config.py`
- Connector docs: `docs/connectors.md`
- Manual testing register: `docs/manual-testing.md`
- Sprint tracker: `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- macOS `realpath -m` flag not supported: replaced with `mkdir -p parent && cd parent && pwd` pattern.

### Completion Notes List

- Standalone enabler EN.1 implemented 2026-05-29. Not tied to Epic 9.
- `templates/instance/.env.template` uses `{{PLACEHOLDER}}` markers; `compose.yaml.template` uses both `{{PLACEHOLDER}}` markers (substituted by init script) and `${ENV_VAR}` syntax (resolved by Docker Compose from `.env`).
- Ports computed deterministically from `cksum` hash of instance name (range 20000–54999 for postgres, +1 for tika). Low collision probability for a handful of instances; `.env` documents how to override if needed.
- `scripts/init-instance.sh` refuses to overwrite a non-empty destination (no `--force` flag — simplest safe default).
- `uv run --project <repo>` pattern documented for running `cos auth gmail` from the instance folder.
- Pre-existing test failure in `tests/services/test_retrieval_service.py::test_query_citations_match_pruned_evidence_set` confirmed pre-dates this branch (fails on `main` without any changes).
- 10 new tests pass; 590 existing tests pass. No regressions introduced.

### File List

- `_bmad-output/implementation-artifacts/enabler-instance-packaging-and-isolated-runtime-scaffold.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `templates/instance/.env.template` (created)
- `templates/instance/compose.yaml.template` (created)
- `scripts/init-instance.sh` (created)
- `docs/instances.md` (created)
- `docs/manual-testing.md`
- `tests/test_init_instance.py` (created)

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-29 | 1.0 | Initial standalone enabler story created from instance packaging design note. | Codex |
