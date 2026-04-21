# CoS Platform Setup

## Prerequisites

- Docker Desktop (includes Docker Compose)
- [uv](https://docs.astral.sh/uv/) package manager

## First-time configuration

Before starting the platform, create your local config file:

```bash
cp config.yaml.example config.yaml
```

Then open `config.yaml` and fill in:
- `llm.api_key` — your Anthropic API key
- `database.password` — a password of your choice (must match what Docker Compose uses for Postgres)

`config.yaml` is git-ignored and never committed. `config.yaml.example` is the safe template that stays in the repo.

## Start the Platform

```bash
docker compose up -d
```

All three services (postgres, tika, cos) will start and reach a healthy state within 60 seconds.

## Check Platform Status

```bash
cos status
```

Shows whether postgres, tika, and the cos service are running and healthy.

## Restart the Platform

Three-step restart procedure:

```bash
# Step 1 — stop all services
docker compose down

# Step 2 — wait a few seconds
sleep 3

# Step 3 — start again
docker compose up -d
```

No manual intervention is needed between steps.

## View Logs

```bash
cos logs
```

Streams structured JSON logs from all services.

## Ingest a Document

```bash
cos ingest /path/to/document.pdf
```
