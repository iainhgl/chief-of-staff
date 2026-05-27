#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$ROOT_DIR/originals"
mkdir -p "$OUT_DIR"

download() {
  local url="$1"
  local name="$2"
  local dest="$OUT_DIR/$name"

  if [[ -f "$dest" ]]; then
    echo "skip  $name"
    return 0
  fi

  echo "fetch $name"
  curl -L --fail --silent --show-error \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36" \
    "$url" -o "$dest"
}

download "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf" \
  "nist-sp-800-61r2.pdf"
download "https://www.nist.gov/document/2026-nist-handbook-44-section-220" \
  "nist-hb44-section-2-20-scales.pdf"
download "https://www.nist.gov/document/2026-nist-handbook-44-section-220-word" \
  "nist-hb44-section-2-20-scales.docx"
download "https://www.nist.gov/system/files/documents/2023/02/10/2023%20NIST%20Handbook%20133.pdf" \
  "nist-hb133-2023-full.pdf"
download "https://files.gao.gov/assets/gao-22-105159.pdf" \
  "gao-22-105159-accessible.pdf"
download "https://files.gao.gov/assets/gao-24-105645.pdf" \
  "gao-24-105645-accessible.pdf"
download "https://www.govinfo.gov/content/pkg/BILLS-113hr803enr/pdf/BILLS-113hr803enr.pdf" \
  "govinfo-bills-113hr803enr.pdf"
download "https://www.govinfo.gov/content/pkg/BILLS-113hr803enr/html/BILLS-113hr803enr.htm" \
  "govinfo-bills-113hr803enr.html"

echo
echo "downloaded files:"
ls -lh "$OUT_DIR"
