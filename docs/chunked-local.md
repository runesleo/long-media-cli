# Chunked local transcription

Use `transcribe_chunked.py` when **any** of:

- Duration **> 20 minutes**
- File size **> 25 MB**
- Source is podcast / 小宇宙 / Twitter(X) Space replay
- Whole-file whisper produced **0-byte** output or hung

Do **not** run whole-file whisper on 90+ minute audio.

## Command

```bash
python3 transcribe_chunked.py SOURCE_AUDIO \
  --out OUTPUT.txt \
  --language zh \
  --engine mlx \
  --resume
```

## Key flags

| Flag | Default | Notes |
|------|---------|-------|
| `--segment-sec` | 600 | Spaces often **480** (8 min) |
| `--engine` | mlx | `mlx` \| `faster` \| `openai` |
| `--resume` | off | Skip `done` segments in manifest |
| `--dry-run` | off | ffmpeg split + manifest only |

## Output layout

```text
OUTPUT.txt                    # master transcript (incremental append)
OUTPUT.txt.chunks/manifest.json
OUTPUT.txt.chunks/segments/seg_NNN.mp3
```

Transcript block format:

```text
[00:00:00] segment 0
<text>

[00:10:00] segment 1
<text>
```

## Resume

```bash
python3 transcribe_chunked.py SOURCE --out SAME.txt --resume --engine mlx
```

Monitor progress: `tail -f SAME.txt`
