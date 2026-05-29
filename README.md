# long-media-cli

Unified ingest for **long video + long podcast** on Apple Silicon.

One command: URL or local file → download (subtitle-first for YT/B站) → chunked mlx-whisper → `{slug}.transcript.txt`.

Split with ffmpeg → transcribe segments serially → **incremental append** + **`--resume`**. No more 90-minute jobs that look hung or write 0 bytes.

MIT · [Leo Labs](https://leolabs.me)

## Why

| Problem | This CLI |
|---------|----------|
| 90+ min single whisper run hangs / 0-byte output | 10 min segments, serial mlx |
| No progress visibility | Each segment **appends** to `--out` (`tail -f`) |
| Interrupt = start over | `manifest.json` + `--resume` |

## Install

**Required**

```bash
brew install ffmpeg yt-dlp
pipx install mlx-whisper
```

**Optional engines**

- `faster-whisper` — CPU fallback (`--engine faster`)
- OpenAI API — `--engine openai` + `OPENAI_API_KEY`

```bash
git clone https://github.com/runesleo/long-media-cli.git
cd long-media-cli
chmod +x ingest.sh space_pipeline.sh long_media.sh
```

## Quick start

### Unified ingest (recommended)

YouTube / B站 / 小宇宙 / X Space / Apple Podcasts / local file:

```bash
./ingest.sh "https://www.xiaoyuzhoufm.com/episode/EPISODE_ID" ~/out zh
./ingest.sh "https://www.youtube.com/watch?v=VIDEO_ID" ~/out zh
./ingest.sh "https://x.com/i/spaces/SPACE_ID" ~/out zh 480
./ingest.sh /path/to/episode.m4a ~/out zh 600
```

Or directly:

```bash
python3 ingest.py "URL_OR_FILE" --out-dir ~/out --language zh --resume
```

See [docs/ingest.md](docs/ingest.md) for flags (`--prefer-subs`, `--no-transcribe`, `--dry-run`).

### Legacy wrappers (still work)

```bash
./long_media.sh /path/to/episode.m4a ~/out zh
./space_pipeline.sh "https://x.com/i/spaces/SPACE_ID" ~/out zh 480
```

Low-level transcribe only:

```bash
python3 transcribe_chunked.py episode.m4a \
  --out episode.transcript.txt \
  --language zh \
  --engine mlx \
  --segment-sec 600 \
  --resume
```

## Verified benchmarks (2026-05-29)

Tested on MacBook Pro Apple Silicon · `mlx_whisper` · **not re-run for this release** — numbers from production runs.

### 小宇宙 podcast · 139 min

| | |
|---|---|
| Episode | [戴雨森 × 源码资本](https://www.xiaoyuzhoufm.com/episode/6a15a2cbff7b9a8c0a5b953f) |
| Duration | **8312 s (~138 min)** |
| Segments | **14** × 600 s |
| Command | `--language zh --segment-sec 600 --engine mlx --resume` |
| Result | 14/14 segments · incremental transcript |

### Twitter/X Space · 71 min

| | |
|---|---|
| Space | [Alkanes · $FIRE](https://x.com/i/spaces/1AKEmmPZoevKL) |
| Duration | **~71 min** |
| Segments | **9** × 480 s |
| Command | `space_pipeline.sh` → `--language zh --segment-sec 480` |
| Result | 9/9 segments · note: seg_0/seg_8 may need review (mlx hallucination on intro/outro) |

## Progress & resume

```bash
# Watch live output
tail -f episode.transcript.txt

# After interrupt
python3 transcribe_chunked.py episode.m4a \
  --out episode.transcript.txt \
  --resume --engine mlx

# Plan segments without transcribing
python3 transcribe_chunked.py episode.m4a \
  --out episode.transcript.txt \
  --dry-run
```

## Repo layout

```text
long-media-cli/
  ingest.py                  # unified: URL/file → download → transcript
  ingest.sh                  # shell wrapper
  transcribe_chunked.py      # core: split + transcribe + manifest
  download_twitter_space.py  # yt-dlp Space → m4a
  space_pipeline.sh          # → ingest.sh (compat)
  long_media.sh              # → ingest.sh (compat)
  docs/ingest.md
  docs/chunked-local.md
```

## Not in CLI

- Structured digest / shownotes generation (Agent + private skill)
- Web UI / hosted SaaS

## Sync with private skill

Development SSOT also lives in `~/.codex/skills/transcribe/`. This repo is the **public extract** for T303 Phase 1.

## License

MIT — see [LICENSE](LICENSE).
