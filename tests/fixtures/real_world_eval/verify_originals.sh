#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ORIG_DIR="$ROOT_DIR/originals"
CHECKSUM_FILE="$ROOT_DIR/checksums.sha256"

status=0

while IFS=' ' read -r expected_hash filename; do
  [[ -z "${expected_hash:-}" ]] && continue

  path="$ORIG_DIR/$filename"
  if [[ ! -f "$path" ]]; then
    echo "missing  $filename"
    status=1
    continue
  fi

  actual_hash="$(shasum -a 256 "$path" | awk '{print $1}')"
  if [[ "$actual_hash" == "$expected_hash" ]]; then
    echo "ok      $filename"
  else
    echo "mismatch $filename"
    echo "  expected: $expected_hash"
    echo "  actual:   $actual_hash"
    status=1
  fi
done < "$CHECKSUM_FILE"

exit "$status"
