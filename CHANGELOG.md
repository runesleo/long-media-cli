# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.1] - 2026-05-30

### Fixed
- Xiaoyuzhou CDN URL regex (`ingest.py`)
- `--no-resume` no longer appends duplicate transcript text (`transcribe_chunked.py`)
- `--subs-only` skips audio download
- Space URL validation tightened
- Digest stub uses basename paths only
- Codex cross-review: see `REVIEW-codex-pass.md`

### Added
- `CHANGELOG.md`
- Opensource release checklist evidence in maintainer inventory

## [0.2.0] - 2026-05-29

### Added
- `digest.py` — `status` + `prepare` (stub + agent prompt + hallucination flags)
- `ingest.py --prepare-digest`
- `docs/digest.md`, `docs/digest-template.md`

## [0.1.0] - 2026-05-29

### Added
- `ingest.py` / `ingest.sh` — unified long video + podcast ingest
- `transcribe_chunked.py` — ffmpeg split + mlx serial transcribe + `--resume`
- `download_twitter_space.py` — X Space audio via yt-dlp
- `space_pipeline.sh`, `long_media.sh` — compatibility wrappers
- Verified benchmarks: 139 min podcast (14 segments), 71 min Space (9 segments)
