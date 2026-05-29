#!/usr/bin/env python3
"""Unified ingest: long video + long podcast → audio/subtitle → chunked transcript."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

SOURCE_SPACE = "space"
SOURCE_XIAOYUZHOU = "xiaoyuzhou"
SOURCE_BILIBILI = "bilibili"
SOURCE_YOUTUBE = "youtube"
SOURCE_APPLE = "apple_podcast"
SOURCE_FILE = "file"
SOURCE_GENERIC = "generic_url"


def _die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _slug(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip()).strip("-").lower()
    return (s or "media")[:max_len]


def _default_out_dir() -> Path:
    return Path.home() / "Projects" / "_inventory" / date.today().isoformat()


def detect_source(url_or_path: str) -> Tuple[str, str]:
    raw = url_or_path.strip()
    p = Path(raw).expanduser()
    if p.exists() and p.is_file():
        return SOURCE_FILE, str(p.resolve())

    u = raw.lower()
    if "/i/spaces/" in u or "twitter.com/i/spaces" in u or "x.com/i/spaces" in u:
        return SOURCE_SPACE, raw
    if "xiaoyuzhoufm.com" in u:
        return SOURCE_XIAOYUZHOU, raw
    if "bilibili.com" in u or "b23.tv" in u:
        return SOURCE_BILIBILI, raw
    if "youtube.com" in u or "youtu.be" in u:
        return SOURCE_YOUTUBE, raw
    if "podcasts.apple.com" in u:
        return SOURCE_APPLE, raw
    if re.match(r"^https?://", raw):
        return SOURCE_GENERIC, raw
    _die(f"Not a file or supported URL: {raw}")


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    _log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def _fetch_text(url: str, headers: Optional[dict[str, str]] = None) -> str:
    hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    if headers:
        hdrs.update(headers)
    req = Request(url, headers=hdrs)
    with urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _download_xiaoyuzhou(url: str, stem: Path) -> Path:
    html = _fetch_text(url)
    m = re.search(r"https://media\.xyzcdn\.net/[^\"'\\s]+\\.(m4a|mp3)", html)
    if not m:
        _die("xiaoyuzhou: audio URL not found in page (__NEXT_DATA__ / CDN)")
    audio_url = m.group(0)
    out = stem.with_suffix(".m4a")
    _run(["curl", "-fsSL", "-o", str(out), audio_url])
    return out


def _extract_bvid(url: str) -> str:
    if "/video/" in url:
        m = re.search(r"/video/(BV[a-zA-Z0-9]+)", url)
        if m:
            return m.group(1)
    if url.startswith("BV"):
        return url.split("?")[0]
    _die(f"bilibili: cannot extract BV from {url}")


def _download_bilibili(url: str, stem: Path) -> Tuple[Path, dict[str, Any]]:
    bvid = _extract_bvid(url)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
    meta_raw = _fetch_text(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers)
    meta = json.loads(meta_raw)["data"]
    cid = meta["cid"]
    title = meta.get("title")
    duration = meta.get("duration")
    play_raw = _fetch_text(
        f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16&qn=64",
        headers,
    )
    audio_url = json.loads(play_raw)["data"]["dash"]["audio"][0]["baseUrl"]
    m4s = stem.with_suffix(".m4s")
    _run(
        [
            "curl",
            "-fsSL",
            "-o",
            str(m4s),
            "-H",
            "User-Agent: Mozilla/5.0",
            "-H",
            "Referer: https://www.bilibili.com/",
            audio_url,
        ]
    )
    mp3 = stem.with_suffix(".mp3")
    _run(["ffmpeg", "-y", "-i", str(m4s), "-acodec", "libmp3lame", "-q:a", "5", str(mp3)])
    m4s.unlink(missing_ok=True)
    return mp3, {"title": title, "duration_sec": duration, "bvid": bvid}


def _yt_dlp_audio(url: str, stem: Path, cookies: Optional[str]) -> Path:
    template = str(stem) + ".%(ext)s"
    cmd = [
        "yt-dlp",
        "-f",
        "ba[ext=m4a]/ba/b",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "5",
        "-o",
        template,
        "--no-overwrites",
        url,
    ]
    if cookies:
        cmd = ["yt-dlp", f"--cookies-from-browser={cookies}", *cmd[1:]]
    _run(cmd)
    for ext in (".mp3", ".m4a", ".opus", ".webm"):
        p = stem.with_suffix(ext)
        if p.exists():
            return p
    matches = sorted(stem.parent.glob(f"{stem.name}.*"))
    for p in matches:
        if p.suffix in {".mp3", ".m4a", ".opus", ".webm"}:
            return p
    _die(f"yt-dlp produced no audio for {url}")


def _try_subtitles(url: str, stem: Path, cookies: Optional[str], langs: str) -> Optional[Path]:
    template = str(stem) + ".%(ext)s"
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang",
        langs,
        "--sub-format",
        "vtt/best",
        "-o",
        template,
        url,
    ]
    if cookies:
        cmd = ["yt-dlp", f"--cookies-from-browser={cookies}", *cmd[1:]]
    proc = _run(cmd, check=False)
    if proc.returncode != 0:
        _log(f"subtitle fetch failed: {(proc.stderr or proc.stdout or '').strip()[:200]}")
        return None
    vtts = sorted(stem.parent.glob(f"{stem.name}*.vtt"))
    if not vtts:
        vtts = sorted(stem.parent.glob(f"{stem.name}*.*"))
        vtts = [p for p in vtts if p.suffix.lower() in {".vtt", ".srt"}]
    return vtts[0] if vtts else None


def _vtt_to_text(vtt_path: Path) -> str:
    lines: list[str] = []
    for line in vtt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("WEBVTT") or s.isdigit() or "-->" in s:
            continue
        if re.match(r"^align:|^NOTE", s):
            continue
        lines.append(s)
    out: list[str] = []
    for ln in lines:
        if not out or out[-1] != ln:
            out.append(ln)
    return "\n".join(out).strip() + "\n"


def _download_space(url: str, out_dir: Path, slug: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "download_twitter_space.py"), url, "--out-dir", str(out_dir), "--slug", slug],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _default_segment_sec(
    source: str,
    duration: Optional[float],
    *,
    slug: Optional[str] = None,
    audio: Optional[Path] = None,
) -> int:
    if source == SOURCE_SPACE:
        return 480
    name = (slug or (audio.stem if audio else "")).lower()
    if name.startswith("space-") or name.startswith("space_"):
        return 480
    return 600


def _transcribe(
    audio: Path,
    transcript: Path,
    *,
    language: str,
    engine: str,
    segment_sec: int,
    resume: bool,
    dry_run: bool,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "transcribe_chunked.py"),
        str(audio),
        "--out",
        str(transcript),
        "--language",
        language,
        "--engine",
        engine,
        "--segment-sec",
        str(segment_sec),
    ]
    if resume:
        cmd.append("--resume")
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        _die((proc.stderr or proc.stdout or "transcribe failed").strip())
    if dry_run:
        return json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"dry_run": True}
    return json.loads(proc.stdout)


def ingest(
    url_or_path: str,
    *,
    out_dir: Path,
    slug: Optional[str] = None,
    language: str = "zh",
    engine: str = "mlx",
    segment_sec: Optional[int] = None,
    prefer_subs: bool = True,
    subs_only: bool = False,
    no_transcribe: bool = False,
    resume: bool = True,
    dry_run: bool = False,
    cookies: str = "chrome",
) -> dict[str, Any]:
    source, target = detect_source(url_or_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {"source_type": source, "source": target}
    audio: Optional[Path] = None
    title: Optional[str] = None
    duration: Optional[float] = None

    if source == SOURCE_FILE:
        audio = Path(target)
        slug = slug or _slug(audio.stem)
    elif source == SOURCE_SPACE:
        space_id = re.search(r"/i/spaces/([A-Za-z0-9]+)", target)
        slug = slug or _slug(f"space-{space_id.group(1) if space_id else 'unknown'}")
        dl = _download_space(target, out_dir, slug)
        audio = Path(dl["audio"])
        title = dl.get("title")
        duration = dl.get("duration_sec")
        meta["download"] = dl
    else:
        slug = slug or _slug(re.sub(r"https?://", "", target).split("/")[-1][:40])
        stem = out_dir / slug

        if source in (SOURCE_YOUTUBE, SOURCE_BILIBILI, SOURCE_GENERIC) and prefer_subs and not subs_only:
            vtt = _try_subtitles(
                target,
                stem,
                cookies if cookies else None,
                "zh-Hans,zh,en" if source == SOURCE_BILIBILI else "en,zh-Hans,zh",
            )
            if vtt:
                transcript = stem.with_suffix(".transcript.txt")
                text = _vtt_to_text(vtt)
                if len(text) > 200:
                    transcript.write_text(text, encoding="utf-8")
                    manifest = {
                        "source": target,
                        "source_type": source,
                        "slug": slug,
                        "transcript": str(transcript),
                        "transcript_source": "subtitle",
                        "subtitle_file": str(vtt),
                        "title": title,
                    }
                    manifest_path = stem.with_suffix(".ingest.json")
                    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    _log(f"used subtitles → {transcript}")
                    return manifest
                _log("subtitle too short, falling back to whisper")

        if source == SOURCE_XIAOYUZHOU:
            audio = _download_xiaoyuzhou(target, stem)
        elif source == SOURCE_BILIBILI:
            audio, bili_meta = _download_bilibili(target, stem)
            title = bili_meta.get("title")
            duration = float(bili_meta["duration_sec"]) if bili_meta.get("duration_sec") else None
            meta["bilibili"] = bili_meta
        elif source in (SOURCE_YOUTUBE, SOURCE_APPLE, SOURCE_GENERIC):
            audio = _yt_dlp_audio(target, stem, cookies if cookies else None)
        else:
            _die(f"unsupported source: {source}")

    assert audio is not None
    stem = out_dir / (slug or _slug(audio.stem))
    transcript = stem.with_suffix(".transcript.txt")

    if subs_only:
        _die("--subs-only requires youtube/bilibili URL with subtitles")

    if no_transcribe:
        result = {
            "source_type": source,
            "source": target,
            "slug": slug,
            "audio": str(audio),
            "transcript": str(transcript),
            "title": title,
            "duration_sec": duration,
        }
        stem.with_suffix(".ingest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    seg = segment_sec or _default_segment_sec(source, duration, slug=slug, audio=audio)
    tx = _transcribe(
        audio,
        transcript,
        language=language,
        engine=engine,
        segment_sec=seg,
        resume=resume,
        dry_run=dry_run,
    )

    result = {
        "source_type": source,
        "source": target,
        "slug": slug,
        "audio": str(audio),
        "transcript": str(transcript),
        "transcript_source": "whisper",
        "title": title,
        "duration_sec": duration,
        "segment_sec": seg,
        "transcribe": tx,
    }
    stem.with_suffix(".ingest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified long video + podcast ingest")
    parser.add_argument("url_or_path", help="URL or local audio/video file")
    parser.add_argument("--out-dir", type=Path, help="Output directory")
    parser.add_argument("--slug", help="Output filename slug")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--engine", default="mlx", choices=["mlx", "faster", "openai"])
    parser.add_argument("--segment-sec", type=int, help="Chunk size (default: space=480 else 600)")
    parser.add_argument("--prefer-subs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--subs-only", action="store_true", help="Only fetch subtitles, no whisper")
    parser.add_argument("--no-transcribe", action="store_true", help="Download only")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Plan chunks without transcribing")
    parser.add_argument("--cookies-from-browser", default="chrome", help="For yt-dlp (empty to disable)")
    args = parser.parse_args()

    out_dir = (args.out_dir or _default_out_dir()).expanduser().resolve()
    cookies = args.cookies_from_browser.strip() or ""

    result = ingest(
        args.url_or_path,
        out_dir=out_dir,
        slug=args.slug,
        language=args.language,
        engine=args.engine,
        segment_sec=args.segment_sec,
        prefer_subs=args.prefer_subs,
        subs_only=args.subs_only,
        no_transcribe=args.no_transcribe,
        resume=not args.no_resume,
        dry_run=args.dry_run,
        cookies=cookies,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
