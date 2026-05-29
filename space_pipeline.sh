#!/usr/bin/env bash
# Deprecated: use ingest.sh. Kept for backward compatibility.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
URL="${1:?Space URL required}"
OUT_DIR="${2:-$HOME/Projects/_inventory/$(date +%Y-%m-%d)}"
LANG="${3:-en}"
SEG="${4:-480}"
exec "$ROOT/ingest.sh" "$URL" "$OUT_DIR" "$LANG" "$SEG"
