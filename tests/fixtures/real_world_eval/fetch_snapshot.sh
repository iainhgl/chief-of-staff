#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ORIG_DIR="$ROOT_DIR/originals"
MANIFEST_FILE="$ROOT_DIR/snapshot-manifest.tsv"
VERIFY_SCRIPT="$ROOT_DIR/verify_originals.sh"

if [[ ! -f "$MANIFEST_FILE" ]]; then
  echo "missing snapshot-manifest.tsv"
  echo "copy snapshot-manifest.example.tsv to snapshot-manifest.tsv and fill the snapshot_url column first"
  exit 1
fi

mkdir -p "$ORIG_DIR"

tail -n +2 "$MANIFEST_FILE" | while IFS=$'\t' read -r filename snapshot_url sha256 bytes mime_type note; do
  [[ -z "${filename:-}" ]] && continue

  if [[ -z "${snapshot_url:-}" || "$snapshot_url" == "TBD" ]]; then
    echo "unresolved snapshot URL for $filename"
    exit 1
  fi

  dest="$ORIG_DIR/$filename"
  if [[ -f "$dest" ]]; then
    echo "skip  $filename"
    continue
  fi

  echo "fetch $filename"
  curl -L --fail --silent --show-error "$snapshot_url" -o "$dest"
done

"$VERIFY_SCRIPT"
