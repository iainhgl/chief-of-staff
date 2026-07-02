# Instance Packaging Design — Isolated Side-by-Side Runtime

Date: 2026-05-29

## Purpose

The operator wants to start using CoS for a real AI/software-architecture reading corpus while keeping that knowledge base cleanly isolated from test and UAT data. The immediate use case is ingesting Substack and Gmail-delivered AI articles into a running CoS instance, with separate Postgres state, file storage, token storage, and config.

This design note captures a lightweight installer/instance approach that can be implemented as a standalone story before bulk real-data ingestion.

## BMad Recommendation

This does **not** need a full course-correct.

Recommended path:

1. Create one standalone story for **Instance Packaging and Isolated Runtime Scaffold**.
2. Treat it as a small enablement story before continuing normal Epic 10 work.
3. Use this document as source context for `bmad-create-story`.

Why not course-correct:

- The platform roadmap remains valid.
- This is an operational packaging capability, not a change to product direction.
- It does not invalidate Epic 10, 11, or 12 sequencing.
- It is small enough to implement and validate independently.

A course-correct would only be warranted if we decide to make multi-instance packaging a major product theme with installers, upgrade management, instance registries, secrets migration, backup/restore, and user-facing distribution.

## Current Runtime Constraints

Current regular runtime commands load `config.yaml` by default:

- `cos auth gmail`
- `cos sync gmail`
- `cos status`
- `cos ingest`
- `cos docs`
- `cos restart`
- `cos logs`

Only `cos benchmark` currently has a `--config` option for host-side config selection.

Docker Compose also mounts fixed relative paths from the Compose directory:

- `./config.yaml:/app/config.yaml:ro`
- `./data:/data`
- `./role_packs:/app/role_packs:ro`
- `./local/certs:/certs:ro`
- `./tokens:/app/tokens`

Therefore, a separate config file alone is not enough for clean real-data isolation. A properly isolated real-use instance also needs separate `data/`, `tokens/`, Compose project name, and Postgres volume.

## Recommended Lightweight Shape

Use a **prebuilt local app image plus an isolated instance folder**.

The repo remains the build/debug workspace. Each real-use instance is a small folder containing only runtime assets and a Compose file that references the image.

Example instance:

```text
~/cos-instances/ai-reading/
├── compose.yaml
├── config.yaml
├── role_packs/
│   └── chro.yaml
├── data/
├── tokens/
├── local/
│   └── certs/
└── .env
```

The instance is started from its own folder:

```bash
cd ~/cos-instances/ai-reading
docker compose --project-name cos-ai-reading up -d
```

## Image Strategy

Build the application image from the repo:

```bash
docker build -t cos-platform:local .
```

The generated instance Compose file uses:

```yaml
image: cos-platform:${COS_IMAGE_TAG:-local}
```

This avoids copying source code into every instance. When code changes, rebuild the image and recreate the instance services.

## Generated Instance Compose Shape

The instance Compose file should be self-contained and use instance-local mounts:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - "127.0.0.1:${POSTGRES_PORT:-15432}:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-cos}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  tika:
    image: apache/tika
    ports:
      - "127.0.0.1:${TIKA_PORT:-19998}:9998"

  cos:
    image: cos-platform:${COS_IMAGE_TAG:-local}
    stdin_open: true
    depends_on:
      postgres:
        condition: service_healthy
      tika:
        condition: service_healthy
    volumes:
      - ./data:/data
      - ./config.yaml:/app/config.yaml:ro
      - ./role_packs:/app/role_packs:ro
      - ./local/certs:/certs:ro
      - ./tokens:/app/tokens

  worker:
    image: cos-platform:${COS_IMAGE_TAG:-local}
    command: ["uv", "run", "cos-worker"]
    depends_on:
      postgres:
        condition: service_healthy
      tika:
        condition: service_healthy
    volumes:
      - ./data:/data
      - ./config.yaml:/app/config.yaml:ro
      - ./role_packs:/app/role_packs:ro
      - ./local/certs:/certs:ro
      - ./tokens:/app/tokens
    restart: on-failure

  telegram-bot:
    image: cos-platform:${COS_IMAGE_TAG:-local}
    command: ["uv", "run", "cos-telegram-bot"]
    depends_on:
      postgres:
        condition: service_healthy
      tika:
        condition: service_healthy
    volumes:
      - ./data:/data
      - ./config.yaml:/app/config.yaml:ro
      - ./role_packs:/app/role_packs:ro
      - ./local/certs:/certs:ro
      - ./tokens:/app/tokens
    restart: on-failure

volumes:
  postgres_data:
```

The real implementation should preserve the healthchecks from the repo `docker-compose.yml`; the snippet above is illustrative.

## Installer / Initializer Shape

Minimum viable command shape:

```bash
scripts/init-instance.sh ~/cos-instances/ai-reading ai-reading
```

Possible future CLI shape:

```bash
uv run cos instance init ~/cos-instances/ai-reading --name ai-reading
```

The initializer should:

1. Validate that the destination does not already contain an instance unless `--force` is passed.
2. Create the destination folder structure:
   - `data/`
   - `tokens/`
   - `local/certs/`
   - `role_packs/`
3. Copy baseline role packs into `role_packs/`.
4. Generate `config.yaml` from `config.yaml.example` with instance-local defaults.
5. Generate `.env` with:
   - `COMPOSE_PROJECT_NAME=cos-ai-reading`
   - `COS_IMAGE_TAG=local`
   - `POSTGRES_PORT=<non-default host port>`
   - `TIKA_PORT=<non-default host port>`
   - `POSTGRES_DB=cos`
   - `POSTGRES_PASSWORD=postgres` or a generated local password
6. Generate `compose.yaml` using image references, not `build: .`.
7. Print next steps:
   - edit `config.yaml`
   - run `docker build -t cos-platform:local <repo>`
   - run `docker compose up -d`
   - authenticate Gmail if needed

## Optional Packaging Command

An explicit packaging command could create a reusable template artifact:

```bash
scripts/package-instance-template.sh
```

Output:

```text
dist/cos-instance-template/
├── compose.yaml.template
├── config.yaml.template
├── role_packs/
├── .env.template
└── init-instance.sh
```

This is optional for the first story. A direct `scripts/init-instance.sh` is probably enough.

## Gmail / Substack Use Case

For the AI-reading corpus, the first instance should use Gmail as the ingestion source:

```yaml
connectors:
  - gmail

gmail:
  query: "label:cos-ai-reading newer_than:365d"
  max_results: 100
  staging_dir: /data/connector-staging/gmail
```

Substack emails are expected to ingest as `gmail_message_body`, because Substack articles are normally delivered as email body content rather than attachments.

Known Gmail connector behavior:

- It fetches full Gmail messages via the Gmail API.
- It extracts `text/plain` body content first.
- It falls back to `text/html` if no plain-text body exists.
- It stages message bodies as Markdown files with email headers.
- It separately stages supported attachments.

Quality risk:

- HTML fallback is currently stored as raw HTML, not cleaned Markdown.
- Even plain-text Substack emails may include navigation, unsubscribe, comments, share links, and email chrome.

Recommended rollout:

1. Label 10-20 representative Substack emails with `cos-ai-reading`.
2. Sync them into the isolated instance.
3. Inspect `cos docs`, staged/markdown copies, and retrieval quality.
4. Only then bulk-label and sync the broader article set.
5. If retrieval is noisy, create a follow-up story for Gmail body cleanup / email-to-Markdown normalization.

## Why Not Build a Substack Connector First?

A Substack connector is not recommended as the first implementation.

Reasons:

- Substack provides RSS feeds for public publication posts, but paid subscriber content is more reliably available through the user's email copy.
- A reader/subscriber API for paid content is not part of the current platform assumptions.
- Gmail already preserves provenance and works for both free and paid email-delivered articles.
- A Substack connector risks duplicating Gmail ingestion while adding auth and access complexity.

Possible later supplement:

- Use publication RSS feeds for public/free post discovery or metadata reconciliation.
- Continue to use Gmail for paid article bodies.

## Acceptance Criteria For Standalone Story

Suggested story title:

**Instance Packaging and Isolated Runtime Scaffold**

Suggested acceptance criteria:

1. **Given** the operator wants a new isolated CoS instance,
   **When** they run the initializer with a destination path and instance name,
   **Then** a complete instance folder is created with `compose.yaml`, `.env`, `config.yaml`, `role_packs/`, `data/`, `tokens/`, and `local/certs/`.

2. **Given** the generated instance folder,
   **When** the operator runs `docker compose up -d` from that folder after building `cos-platform:local`,
   **Then** the instance starts with separate Postgres volume, file storage, token storage, and config from the repo dev/test instance.

3. **Given** two generated instances use different names,
   **When** both are started,
   **Then** they use distinct Compose project names, host ports, volumes, and instance-local runtime folders.

4. **Given** the operator enables Gmail in the generated config,
   **When** they authenticate and sync labelled mail,
   **Then** Gmail body and attachment ingestion use the instance-local `tokens/`, `data/`, and Postgres storage.

5. **Given** the generated docs or command output,
   **When** the operator follows the printed next steps,
   **Then** they can distinguish repo development commands from isolated instance runtime commands.

## Test / Verification Notes

Minimum tests:

- Unit test the instance-name sanitisation and port selection helpers if implemented in Python.
- Shell/script smoke test can run in a temp directory and assert expected files/directories exist.
- `docker compose -f <generated>/compose.yaml config` succeeds.
- The generated `.env` has a unique `COMPOSE_PROJECT_NAME`.

Manual validation:

- Build image: `docker build -t cos-platform:local .`
- Init instance: `scripts/init-instance.sh /tmp/cos-ai-reading ai-reading`
- Start instance: `cd /tmp/cos-ai-reading && docker compose up -d`
- Confirm data isolation:
  - generated `data/` remains instance-local
  - generated `tokens/` remains instance-local
  - `docker volume ls` shows project-namespaced Postgres volume

## Open Questions

- Should the first story implement this as shell scripts under `scripts/`, as a `cos instance` CLI command, or both?
- Should port selection be automatic, user-specified, or a simple deterministic offset from the instance name?
- Should `config.yaml` generation preserve all comments from `config.yaml.example`, or use a shorter runtime-focused template?
- Should the instance default enable only Gmail for the AI-reading use case, or remain connector-neutral?

## Recommendation For First Story Scope

Implement the smallest useful version:

- `scripts/init-instance.sh`
- `templates/instance/compose.yaml.template`
- `templates/instance/.env.template`
- copies current `config.yaml.example` and `role_packs/`
- creates instance-local folders
- validates `docker compose config`
- documents how to build the local image and start an instance

Defer:

- upgrade/migration management for existing instances
- automatic app image publishing
- backup/restore
- Substack-specific connector
- Gmail body cleanup
