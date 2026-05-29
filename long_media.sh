#!/usr/bin/env bash
# Existing audio → chunked transcript (low-level; use ingest.sh for URL workflows)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
AUDIO="${1:?audio file required}"
OUT="${2:-${AUDIO%.*}.transcript.txt}"
LANG="${3:-zh}"
ENGINE="${4:-mlx}"
SEG="${5:-600}"

python3 "$ROOT/transcribe_chunked.py" "$AUDIO" \
  --out "$OUT" \
  --language "$LANG" \
  --engine "$ENGINE" \
  --segment-sec "$SEG" \
  --resume

echo ""
echo "Transcript: $OUT"
echo "Manifest: ${OUT}.chunks/manifest.json"
echo "Tip: for URLs use ./ingest.sh instead"
