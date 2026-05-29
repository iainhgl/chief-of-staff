# CoS Platform — Isolated Instance Guide

The CoS platform can run as multiple side-by-side instances, each with its own knowledge base, config, OAuth tokens, and Postgres storage. This is useful when you want a real-use knowledge base (for example, ingesting AI newsletter articles) completely isolated from your development and UAT data.

---

## Instance vs Repo

The **repo** is the build and development workspace. It contains the application source code, tests, and planning artifacts. Running the platform directly from the repo is fine for development, but it mixes your real knowledge base with test data and UAT runs.

An **instance** is a small, isolated folder that contains only runtime assets: a `compose.yaml` that references the prebuilt application image, an `.env` for project-specific settings, and your personal `config.yaml`, `role_packs/`, `data/`, and `tokens/`. All Compose resources (volumes, networks, container names) are namespaced by a unique project name so instances do not collide.

---

## Isolation Boundaries

| Resource | Repo (dev) | Isolated instance |
|---|---|---|
| Application source code | Present | Not copied — image only |
| `config.yaml` | `./config.yaml` | `<instance>/config.yaml` |
| Knowledge base files | `./data/` | `<instance>/data/` |
| OAuth tokens | `./tokens/` | `<instance>/tokens/` |
| TLS certificates | `./local/certs/` | `<instance>/local/certs/` |
| Postgres volume | `docker-compose.yml` project default | `cos-<name>_postgres_data` |
| Postgres host port | 5432 | computed from instance name (20000–55000) |
| Tika host port | 9998 | Postgres port + 1 |

---

## Creating an Instance

Run the initializer from the repo root:

```bash
scripts/init-instance.sh ~/cos-instances/ai-reading ai-reading
```

Arguments:
1. **Destination path** — where the instance folder will be created. May be anywhere; does not need to be inside the repo.
2. **Instance name** — a short identifier used in the Compose project name and `.env` file. Lowercase alphanumeric and hyphens. Other characters are sanitized automatically.

The script creates the instance folder with the following contents:

```
ai-reading/
├── compose.yaml        Docker Compose file (image reference, not build)
├── .env                COMPOSE_PROJECT_NAME, ports, DB settings
├── config.yaml         Copy of config.yaml.example — edit before starting
├── role_packs/         Role pack files copied from the repo
├── data/               Knowledge base files (written at runtime)
├── tokens/             OAuth tokens (written at auth time)
└── local/
    └── certs/          Optional TLS root certificates
```

Two instances created with different names automatically get distinct `COMPOSE_PROJECT_NAME` values and different host ports so they can run side by side.

---

## Build the Application Image

Build once from the repo. Rebuild when the application code changes.

```bash
cd /path/to/cos-repo
docker build -t cos-platform:local .
```

The generated `compose.yaml` uses `cos-platform:${COS_IMAGE_TAG:-local}`. To use a different tag, set `COS_IMAGE_TAG` in the instance `.env`.

---

## Start the Instance

```bash
cd ~/cos-instances/ai-reading
docker compose up -d
```

Check status after services start:

```bash
docker compose exec cos uv run cos status
```

All `docker compose` commands run from the instance folder. The Compose project name in `.env` ensures resources are isolated from the repo and from other instances.

---

## Gmail Ingestion — AI/Substack Reading Corpus

The recommended first real-use pattern is ingesting Substack and AI newsletter articles via Gmail labels. Paid Substack articles arrive as email body content, so Gmail ingestion covers both free and paid articles without a separate Substack connector.

### Recommended label-first rollout

1. In Gmail, create a label such as `cos-ai-reading`.
2. Apply the label to 10–20 representative Substack emails first.
3. Sync those into the instance and inspect quality before bulk-labelling.
4. Only then apply the label to the broader article set.

This is important because Gmail `text/plain` body content includes email chrome (unsubscribe links, navigation, share buttons) that can add retrieval noise. A small initial sample lets you assess quality before ingesting hundreds of articles.

### Instance config for Gmail

In the instance `config.yaml`:

```yaml
connectors:
  - gmail

gmail:
  query: "label:cos-ai-reading newer_than:365d"
  max_results: 100

google_oauth:
  client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
  client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET
```

See [setup.md — Google OAuth Setup](setup.md#google-oauth-setup-gmail-and-calendar-connectors) for how to obtain OAuth credentials.

### Authenticate Gmail (instance-local)

Run from the **instance folder on the host** so the browser can open and tokens are written to the instance-local `tokens/` directory:

```bash
cd ~/cos-instances/ai-reading
uv run --project /path/to/cos-repo cos auth gmail
```

This writes `tokens/gmail.json` into the instance folder — not into the repo. The `--project` flag points uv to the repo's installed `cos` package while running with the instance folder as the working directory.

### Sync Gmail into the instance

```bash
cd ~/cos-instances/ai-reading
docker compose exec cos uv run cos sync gmail
```

The worker service processes the queued jobs. Watch progress:

```bash
docker compose logs worker --tail=50
```

After the worker catches up, articles are searchable through the `retrieve` tool.

---

## Running Multiple Instances

Each call to `init-instance.sh` with a different name creates an independent instance with:

- A unique `COMPOSE_PROJECT_NAME` (e.g. `cos-ai-reading`, `cos-hr-knowledge`)
- Distinct host ports for Postgres and Tika
- Separate `data/`, `tokens/`, and Postgres named volumes

Both instances can run simultaneously. From each instance folder, standard `docker compose` commands operate on that instance only.

---

## Repo vs Instance Command Reference

| Task | Where to run | Command |
|---|---|---|
| Build application image | Repo root | `docker build -t cos-platform:local .` |
| Run tests | Repo root | `uv run pytest` |
| Create an instance | Repo root | `scripts/init-instance.sh <path> <name>` |
| Start an instance | Instance folder | `docker compose up -d` |
| Check status | Instance folder | `docker compose exec cos uv run cos status` |
| Ingest files | Instance folder | `docker compose exec cos uv run cos ingest /data/<path>` |
| List documents | Instance folder | `docker compose exec cos uv run cos docs` |
| Authenticate Gmail | Instance folder (host) | `uv run --project <repo> cos auth gmail` |
| Sync Gmail | Instance folder | `docker compose exec cos uv run cos sync gmail` |
| View logs | Instance folder | `docker compose logs <service>` |
| Stop instance | Instance folder | `docker compose down` |

---

## Upgrading an Instance

When application code changes, rebuild the image and recreate the instance services:

```bash
# From the repo
docker build -t cos-platform:local .

# From the instance folder
docker compose up -d --force-recreate
```

Data volumes (`data/`, `tokens/`, Postgres) are preserved across recreations — only the container images are replaced.

---

## Known Limitations

- `cos auth gmail` and `cos auth calendar` must run on the host (not in the container) because the OAuth consent flow opens a browser. Use `uv run --project <repo>` from the instance folder to route the command through the repo's installed package.
- `cos logs` (the platform CLI log export) filters only `postgres`, `tika`, and `cos` service names. For `worker` and `telegram-bot`, use `docker compose logs <service>` directly.
- Telegram OAuth is not needed — the bot token goes in `config.yaml` directly and is picked up from the instance-local config.
