#!/usr/bin/env bash
# init-instance.sh — Create an isolated CoS runtime instance folder.
#
# Usage:
#   scripts/init-instance.sh <dest-path> <instance-name>
#
# Example:
#   scripts/init-instance.sh ~/cos-instances/ai-reading ai-reading
#
# The generated folder contains:
#   compose.yaml   Docker Compose definition (image reference, not build)
#   .env           Project name, ports, DB settings
#   config.yaml    Copy of config.yaml.example — edit before starting
#   role_packs/    Role pack files copied from the repo
#   data/          Instance-local knowledge base files
#   tokens/        Instance-local OAuth tokens (Gmail, Calendar)
#   local/certs/   Optional TLS root certificates
#
# Run 'docker build -t cos-platform:local .' from the repo first.
# Then 'docker compose up -d' from the generated instance folder.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATES="${REPO_ROOT}/templates/instance"

# ── Argument validation ────────────────────────────────────────────────────────

DEST_PATH="${1:-}"
INSTANCE_NAME="${2:-}"

if [[ -z "$DEST_PATH" || -z "$INSTANCE_NAME" ]]; then
    echo "Usage: $0 <dest-path> <instance-name>" >&2
    echo "Example: $0 ~/cos-instances/ai-reading ai-reading" >&2
    exit 1
fi

# ── Sanitize instance name ────────────────────────────────────────────────────
# Compose project names must be lowercase alphanumeric+hyphens.

RAW_NAME="$INSTANCE_NAME"
SAFE_NAME="$(echo "$INSTANCE_NAME" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-' '-' | sed 's/^-*//;s/-*$//')"

if [[ -z "$SAFE_NAME" ]]; then
    echo "Error: instance name '${RAW_NAME}' produced an empty sanitized identifier." >&2
    exit 1
fi

if [[ "$SAFE_NAME" != "$RAW_NAME" ]]; then
    echo "Note: instance name sanitized from '${RAW_NAME}' to '${SAFE_NAME}'."
    INSTANCE_NAME="$SAFE_NAME"
fi

# ── Resolve destination path ──────────────────────────────────────────────────
# Create parent directory first (safe — we're about to create the instance there),
# then resolve to an absolute path using cd/pwd which works on macOS and Linux.

PARENT_PATH="$(dirname "$DEST_PATH")"
BASE_NAME="$(basename "$DEST_PATH")"
mkdir -p "$PARENT_PATH"
DEST_PATH="$(cd "$PARENT_PATH" && pwd)/${BASE_NAME}"

# ── Refuse to overwrite a non-empty destination ───────────────────────────────

if [[ -d "$DEST_PATH" ]] && [[ -n "$(ls -A "$DEST_PATH" 2>/dev/null)" ]]; then
    echo "Error: destination '${DEST_PATH}' already exists and is not empty." >&2
    echo "Remove or choose a different path." >&2
    exit 1
fi

# ── Compute unique host ports from instance name ──────────────────────────────
# Uses cksum (available on macOS and Linux) to get a deterministic numeric hash.
# Ports land in 20000–54999 (postgres) and 20001–55000 (tika).
# Probability of collision across a handful of instances is negligible.
# If two instances collide, edit POSTGRES_PORT and TIKA_PORT in the generated .env.

HASH=$(printf '%s' "$INSTANCE_NAME" | cksum | awk '{print $1}')
POSTGRES_PORT=$(( 20000 + (HASH % 35000) ))
TIKA_PORT=$(( POSTGRES_PORT + 1 ))

# ── Create instance folder structure ─────────────────────────────────────────

mkdir -p \
    "${DEST_PATH}/data" \
    "${DEST_PATH}/tokens" \
    "${DEST_PATH}/local/certs" \
    "${DEST_PATH}/role_packs"

# ── Copy role packs ───────────────────────────────────────────────────────────

cp -r "${REPO_ROOT}/role_packs/." "${DEST_PATH}/role_packs/"

# ── Generate config.yaml ──────────────────────────────────────────────────────
# Copy from config.yaml.example; the operator edits it before starting.

cp "${REPO_ROOT}/config.yaml.example" "${DEST_PATH}/config.yaml"

# ── Render .env from template ─────────────────────────────────────────────────

sed \
    -e "s|{{INSTANCE_NAME}}|${INSTANCE_NAME}|g" \
    -e "s|{{POSTGRES_PORT}}|${POSTGRES_PORT}|g" \
    -e "s|{{TIKA_PORT}}|${TIKA_PORT}|g" \
    "${TEMPLATES}/.env.template" \
    > "${DEST_PATH}/.env"

# ── Render compose.yaml from template ────────────────────────────────────────

sed \
    -e "s|{{INSTANCE_NAME}}|${INSTANCE_NAME}|g" \
    "${TEMPLATES}/compose.yaml.template" \
    > "${DEST_PATH}/compose.yaml"

# ── Print next steps ──────────────────────────────────────────────────────────

cat <<EOF

Instance '${INSTANCE_NAME}' created at:
  ${DEST_PATH}

Contents:
  compose.yaml    Docker Compose definition (uses cos-platform:local image)
  .env            Environment: project name, ports, DB settings
  config.yaml     Edit this: add llm.api_key and any connectors needed
  role_packs/     Loaded role packs copied from repo
  data/           Instance-local knowledge base files
  tokens/         Instance-local OAuth tokens (Gmail, Calendar)
  local/certs/    Optional TLS root certificates

NEXT STEPS
----------

1. Build the application image from the repo (run once; rebuild when code changes):

     cd ${REPO_ROOT}
     docker build -t cos-platform:local .

2. Edit the instance config:

     \${EDITOR:-nano} ${DEST_PATH}/config.yaml

   At minimum set:
     llm.api_key      — your Anthropic API key
     database.password — must match POSTGRES_PASSWORD in .env (default: postgres)

3. Start the instance:

     cd ${DEST_PATH}
     docker compose up -d

4. Check platform status (after services start):

     cd ${DEST_PATH}
     docker compose exec cos uv run cos status

5. (Optional) Enable Gmail for Substack/newsletter ingestion:

   In config.yaml, add:

     connectors:
       - gmail

     gmail:
       query: "label:cos-ai-reading newer_than:365d"
       max_results: 100

     google_oauth:
       client_id: YOUR_GOOGLE_OAUTH_CLIENT_ID.apps.googleusercontent.com
       client_secret: YOUR_GOOGLE_OAUTH_CLIENT_SECRET

   Authenticate (run from this instance folder on the host — browser opens on the host):

     cd ${DEST_PATH}
     uv run --project ${REPO_ROOT} cos auth gmail

   Sync Gmail into the instance knowledge base:

     cd ${DEST_PATH}
     docker compose exec cos uv run cos sync gmail

REPO vs INSTANCE COMMANDS
--------------------------
From the REPO directory (${REPO_ROOT}):
  docker build -t cos-platform:local .
  uv run pytest ...
  uv run ruff check

From the INSTANCE directory (${DEST_PATH}):
  docker compose up -d
  docker compose exec cos uv run cos status
  docker compose exec cos uv run cos ingest /data/<folder>
  docker compose exec cos uv run cos docs
  docker compose exec cos uv run cos sync gmail
  uv run --project ${REPO_ROOT} cos auth gmail   # for OAuth (host only)

See docs/instances.md in the repo for full isolation model details.

EOF
