#!/usr/bin/env bash
# Unified: long video URL / podcast URL / local file → transcript
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
URL_OR_PATH="${1:?URL or audio/video file required}"
OUT_DIR="${2:-./output/$(date +%Y-%m-%d)}"
LANG="${3:-zh}"
SEG="${4:-}"   # empty = auto (space 480, else 600)

ARGS=( "$URL_OR_PATH" --out-dir "$OUT_DIR" --language "$LANG" --resume )
[[ -n "$SEG" ]] && ARGS+=( --segment-sec "$SEG" )

exec python3 "$ROOT/ingest.py" "${ARGS[@]}"
