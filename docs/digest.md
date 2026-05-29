# Digest CLI

Phase 2: **status + prepare stub** — LLM digest still Agent-driven (no API key in CLI).

## Commands

```bash
# Progress (segments_done / segments_total)
python3 digest.py status path/to/foo.transcript.txt

# Write foo-digest.md + foo-digest.agent-prompt.md
python3 digest.py prepare path/to/foo.transcript.txt
```

## Flags

| Flag | Notes |
|------|-------|
| `--title` / `--url` | Override metadata |
| `--shownotes` | Inject official outline into agent prompt |
| `--force` | Stub even if manifest incomplete |
| `--no-prompt` | Skip `.agent-prompt.md` |

## End-to-end

```bash
python3 ingest.py "https://www.xiaoyuzhoufm.com/episode/..." \
  --out-dir ~/out --language zh --resume --prepare-digest

python3 digest.py status ~/out/episode.transcript.txt
# Agent reads ~/out/episode-digest.agent-prompt.md → fills digest
```

## Quality heuristics

`prepare` scans segments for mlx repetition hallucination (e.g. seg_0/seg_8 lyrics loops) and lists them under **质量备注**.
