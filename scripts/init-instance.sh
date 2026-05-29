#!/usr/bin/env bash
# init-instance.sh — Create an isolated CoS runtime instance folder.
#
# Usage:
#   scripts/init-instance.sh <dest-path> <instance-name> [--postgres-port PORT] [--tika-port PORT]
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
POSTGRES_PORT_OVERRIDE=""
TIKA_PORT_OVERRIDE=""

if [[ -z "$DEST_PATH" || -z "$INSTANCE_NAME" ]]; then
    echo "Usage: $0 <dest-path> <instance-name> [--postgres-port PORT] [--tika-port PORT]" >&2
    echo "Example: $0 ~/cos-instances/ai-reading ai-reading" >&2
    exit 1
fi

shift 2
while [[ $# -gt 0 ]]; do
    case "$1" in
        --postgres-port)
            POSTGRES_PORT_OVERRIDE="${2:-}"
            if [[ -z "$POSTGRES_PORT_OVERRIDE" ]]; then
                echo "Error: --postgres-port requires a value." >&2
                exit 1
            fi
            shift 2
            ;;
        --tika-port)
            TIKA_PORT_OVERRIDE="${2:-}"
            if [[ -z "$TIKA_PORT_OVERRIDE" ]]; then
                echo "Error: --tika-port requires a value." >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Error: unknown option '$1'." >&2
            exit 1
            ;;
    esac
done

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

if (( ${#INSTANCE_NAME} > 48 )); then
    TRUNCATED_NAME="${INSTANCE_NAME:0:48}"
    TRUNCATED_NAME="$(printf '%s' "$TRUNCATED_NAME" | sed 's/-*$//')"
    echo "Note: instance name truncated from '${INSTANCE_NAME}' to '${TRUNCATED_NAME}'."
    INSTANCE_NAME="$TRUNCATED_NAME"
fi

# ── Resolve destination path ──────────────────────────────────────────────────
# Create parent directory first (safe — we're about to create the instance there),
# then resolve to an absolute path using cd/pwd which works on macOS and Linux.

PARENT_PATH="$(dirname "$DEST_PATH")"
BASE_NAME="$(basename "$DEST_PATH")"
mkdir -p "$PARENT_PATH"
DEST_PATH="$(cd "$PARENT_PATH" && pwd)/${BASE_NAME}"

shell_quote() {
    local value="$1"
    printf "'%s'" "$(printf '%s' "$value" | sed "s/'/'\\\\''/g")"
}

validate_port() {
    local port="$1"
    local name="$2"
    if ! [[ "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
        echo "Error: ${name} must be an integer between 1 and 65535." >&2
        exit 1
    fi
}

port_in_use() {
    local port="$1"
    python3 - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.2)
    sys.exit(0 if sock.connect_ex(("127.0.0.1", port)) == 0 else 1)
PY
}

# ── Refuse to overwrite a non-empty destination ───────────────────────────────

if [[ -d "$DEST_PATH" ]] && [[ -n "$(ls -A "$DEST_PATH" 2>/dev/null)" ]]; then
    echo "Error: destination '${DEST_PATH}' already exists and is not empty." >&2
    echo "Remove or choose a different path." >&2
    exit 1
fi

# ── Compute unique host ports from instance name ──────────────────────────────
# Uses cksum (available on macOS and Linux) to get a deterministic numeric hash
# from the raw name and destination path. This avoids collisions when two raw names
# sanitize to the same slug but live in different instance folders.

HASH=$(printf '%s:%s' "$RAW_NAME" "$DEST_PATH" | cksum | awk '{print $1}')
COMPOSE_PROJECT_NAME="cos-${INSTANCE_NAME}-${HASH}"

if [[ -n "$POSTGRES_PORT_OVERRIDE" ]]; then
    validate_port "$POSTGRES_PORT_OVERRIDE" "--postgres-port"
    POSTGRES_PORT="$POSTGRES_PORT_OVERRIDE"
else
    POSTGRES_PORT=$(( 20000 + (HASH % 35000) ))
fi

if [[ -n "$TIKA_PORT_OVERRIDE" ]]; then
    validate_port "$TIKA_PORT_OVERRIDE" "--tika-port"
    TIKA_PORT="$TIKA_PORT_OVERRIDE"
else
    TIKA_PORT=$(( POSTGRES_PORT + 1 ))
fi

validate_port "$POSTGRES_PORT" "POSTGRES_PORT"
validate_port "$TIKA_PORT" "TIKA_PORT"

if [[ "$POSTGRES_PORT" == "$TIKA_PORT" ]]; then
    echo "Error: postgres and Tika ports must be different." >&2
    exit 1
fi

if [[ -z "$POSTGRES_PORT_OVERRIDE" || -z "$TIKA_PORT_OVERRIDE" ]]; then
    for _ in $(seq 1 100); do
        if ! port_in_use "$POSTGRES_PORT" && ! port_in_use "$TIKA_PORT"; then
            break
        fi
        POSTGRES_PORT=$(( POSTGRES_PORT + 2 ))
        TIKA_PORT=$(( TIKA_PORT + 2 ))
        if (( TIKA_PORT > 55000 )); then
            POSTGRES_PORT=20000
            TIKA_PORT=20001
        fi
    done
fi

if port_in_use "$POSTGRES_PORT"; then
    echo "Error: postgres port ${POSTGRES_PORT} is already in use. Pass --postgres-port." >&2
    exit 1
fi

if port_in_use "$TIKA_PORT"; then
    echo "Error: Tika port ${TIKA_PORT} is already in use. Pass --tika-port." >&2
    exit 1
fi

REPO_ROOT_Q="$(shell_quote "$REPO_ROOT")"
DEST_PATH_Q="$(shell_quote "$DEST_PATH")"

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
    -e "s|{{COMPOSE_PROJECT_NAME}}|${COMPOSE_PROJECT_NAME}|g" \
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

     cd ${REPO_ROOT_Q}
     docker build -t cos-platform:local .

2. Edit the instance config:

     \${EDITOR:-nano} ${DEST_PATH_Q}/config.yaml

   At minimum set:
     llm.api_key      — your Anthropic API key
     database.password — must match POSTGRES_PASSWORD in .env (default: postgres)

3. Start the instance:

     cd ${DEST_PATH_Q}
     docker compose up -d

4. Check platform status (after services start):

     cd ${DEST_PATH_Q}
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

     cd ${DEST_PATH_Q}
     uv run --project ${REPO_ROOT_Q} cos auth gmail

   Sync Gmail into the instance knowledge base:

     cd ${DEST_PATH_Q}
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
  uv run --project ${REPO_ROOT_Q} cos auth gmail   # for OAuth (host only)

See docs/instances.md in the repo for full isolation model details.

EOF
