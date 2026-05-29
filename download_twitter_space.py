#!/usr/bin/env python3
"""Download Twitter/X Space audio via yt-dlp into inventory-style paths."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional


def _die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _slug(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip()).strip("-").lower()
    return (s or "space")[:max_len]


def _extract_space_id(url: str) -> Optional[str]:
    m = re.search(r"/i/spaces/([A-Za-z0-9]+)", url)
    return m.group(1) if m else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _transcribe_cmd_template(audio_path: Path, *, language: str = "en", segment_sec: int = 480) -> str:
    root = _repo_root()
    out = audio_path.with_suffix(".transcript.txt")
    return (
        f'python3 "{root / "transcribe_chunked.py"}" '
        f'"{audio_path}" '
        f'--out "{out}" '
        f"--language {language} --engine mlx --segment-sec {segment_sec} --resume"
    )


def _default_out_dir() -> Path:
    today = date.today().isoformat()
    return Path.cwd() / "output" / today


def _run_ytdlp(url: str, out_template: str, cookies_from_browser: Optional[str]) -> Path:
    cmd = [
        "yt-dlp",
        "-f",
        "ba[ext=m4a]/ba/b",
        "--extract-audio",
        "--audio-format",
        "m4a",
        "--audio-quality",
        "0",
        "-o",
        out_template,
        "--write-info-json",
        "--no-overwrites",
        url,
    ]
    if cookies_from_browser:
        cmd = ["yt-dlp", "--cookies-from-browser", cookies_from_browser, *cmd[1:]]
    _log(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        _die(f"yt-dlp failed: {err}")
    # yt-dlp prints final path sometimes in stdout; glob by template stem
    return Path(out_template)


def _pick_audio_file(stem_path: Path) -> Path:
    parent = stem_path.parent
    stem = stem_path.name
    for ext in (".m4a", ".mp3", ".opus", ".webm"):
        candidate = parent / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    matches = sorted(parent.glob(f"{stem}.*"))
    audio = [p for p in matches if p.suffix in {".m4a", ".mp3", ".opus", ".webm"}]
    if audio:
        return audio[0]
    _die(f"No audio file found for stem {stem_path}")


def _load_meta(info_json: Path) -> Dict[str, Any]:
    if not info_json.exists():
        return {}
    try:
        return json.loads(info_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Twitter/X Space audio.")
    parser.add_argument("url", help="Space URL (https://x.com/i/spaces/...)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory (default: ./output/YYYY-MM-DD)",
    )
    parser.add_argument("--slug", help="Filename slug override")
    parser.add_argument(
        "--cookies-from-browser",
        default="chrome",
        help="Browser for cookies (default: chrome). Use empty string to disable.",
    )
    args = parser.parse_args()

    url = args.url.strip()
    if "/i/spaces/" not in url and "twitter.com/i/spaces/" not in url and "x.com/i/spaces/" not in url:
        _die("URL must be a Twitter/X Space link (https://x.com/i/spaces/<id>)")

    out_dir = (args.out_dir or _default_out_dir()).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    space_id = _extract_space_id(url) or "unknown"
    slug = args.slug or f"space-{space_id}"
    slug = _slug(slug)

    stem = out_dir / slug
    template = str(stem) + ".%(ext)s"
    cookies = args.cookies_from_browser or None

    _run_ytdlp(url, template, cookies)
    audio_path = _pick_audio_file(stem)
    meta = _load_meta(stem.with_suffix(".info.json"))

    summary = {
        "url": url,
        "space_id": space_id,
        "audio": str(audio_path),
        "title": meta.get("title"),
        "duration_sec": meta.get("duration"),
        "uploader": meta.get("uploader") or meta.get("channel"),
        "transcribe_cmd": _transcribe_cmd_template(audio_path, language="en", segment_sec=480),
    }
    manifest_path = stem.with_suffix(".download.json")
    manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
