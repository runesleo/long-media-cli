# Unified ingest · long video + long podcast

One entry for **YouTube / B站 / 小宇宙 / X Space / Apple Podcasts / local file**.

## Flow

```text
URL or local file
    ↓ detect source
    ↓ download (or subtitle-first for YT/B站)
    ↓ transcribe_chunked.py (if no usable subs)
    ↓ {slug}.transcript.txt + {slug}.ingest.json
```

## Command

```bash
python3 ingest.py "URL_OR_FILE" --out-dir ~/out --language zh --resume
```

Shell wrapper:

```bash
./ingest.sh "https://www.xiaoyuzhoufm.com/episode/..." ~/out zh
./ingest.sh "https://www.youtube.com/watch?v=..." ~/out zh
./ingest.sh "https://x.com/i/spaces/..." ~/out zh 480
./ingest.sh ./episode.m4a ~/out zh 600
```

## Flags

| Flag | Default | Notes |
|------|---------|-------|
| `--prefer-subs` | on | YouTube/B站：有字幕则跳过 whisper |
| `--no-prefer-subs` | | 强制 whisper |
| `--no-transcribe` | | 只下载音频 |
| `--dry-run` | | 只规划切段 |
| `--segment-sec` | auto | Space 480，其他 600 |

## Output files

| File | Meaning |
|------|---------|
| `{slug}.m4a` / `.mp3` | Source audio |
| `{slug}.transcript.txt` | Transcript or subtitle text |
| `{slug}.ingest.json` | Run metadata |
| `{slug}.transcript.txt.chunks/` | Resume state |

## Source routing

| Input | Downloader |
|-------|------------|
| 小宇宙 | CDN from page HTML |
| B站 | bilibili API + ffmpeg |
| YouTube / Apple | yt-dlp audio |
| X Space | `download_twitter_space.py` |
| Local file | direct |

## vs old scripts

| Old | New |
|-----|-----|
| `space_pipeline.sh` | `ingest.sh SPACE_URL ...` |
| `long_media.sh` | `ingest.sh file.m4a ...` |
| media-digest Step 1–2 | **`ingest.py`** (Step 3 digest still Agent) |

## Digest (not in CLI)

After transcript complete → Agent reads `structured-digest.md` (private skill).
