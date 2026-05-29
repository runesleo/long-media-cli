#!/usr/bin/env python3
"""Chunk long audio with ffmpeg, transcribe segments serially, append incrementally."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_SEGMENT_SEC = 600
CHUNK_DURATION_THRESHOLD_SEC = 20 * 60
CHUNK_SIZE_THRESHOLD_BYTES = 25 * 1024 * 1024
DEFAULT_MLX_MODEL = "mlx-community/whisper-small-mlx"
DEFAULT_FASTER_MODEL = "small"
HALLUCINATION_PHRASE = "I'm going to do this"
HALLUCINATION_MIN_REPEATS = 4

ENGINES = ("mlx", "faster", "openai")


def _die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    _log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _which(name: str) -> Optional[str]:
    return shutil.which(name)


def _require_tools(*names: str) -> None:
    missing = [n for n in names if not _which(n)]
    if missing:
        _die(f"Missing required tools: {', '.join(missing)}")


def _ffprobe_duration(path: Path) -> float:
    proc = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        _die(f"Could not read duration for {path}")
    return float(raw)


def _format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _chunks_dir(out_path: Path) -> Path:
    return Path(f"{out_path}.chunks")


def _manifest_path(out_path: Path) -> Path:
    return _chunks_dir(out_path) / "manifest.json"


def _load_manifest(path: Path) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_manifest(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _should_chunk(
    duration_sec: float,
    size_bytes: int,
    *,
    force_chunk: bool,
    no_chunk: bool,
) -> bool:
    if no_chunk:
        return False
    if force_chunk:
        return True
    return (
        duration_sec > CHUNK_DURATION_THRESHOLD_SEC
        or size_bytes > CHUNK_SIZE_THRESHOLD_BYTES
    )


def _segment_paths(work_dir: Path, count: int) -> List[Path]:
    seg_dir = work_dir / "segments"
    return [seg_dir / f"seg_{i:03d}.mp3" for i in range(count)]


def _split_audio(
    source: Path,
    work_dir: Path,
    duration_sec: float,
    segment_sec: int,
) -> List[Dict[str, Any]]:
    seg_dir = work_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    count = max(1, math.ceil(duration_sec / segment_sec))
    entries: List[Dict[str, Any]] = []
    for i in range(count):
        start = i * segment_sec
        out = seg_dir / f"seg_{i:03d}.mp3"
        if out.exists() and out.stat().st_size > 0:
            _log(f"segment {i} exists, skip ffmpeg: {out}")
        else:
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(start),
                    "-t",
                    str(segment_sec),
                    "-i",
                    str(source),
                    "-acodec",
                    "libmp3lame",
                    "-q:a",
                    "5",
                    str(out),
                ]
            )
        entries.append(
            {
                "index": i,
                "start_sec": start,
                "path": str(out.relative_to(work_dir)),
                "status": "pending",
                "chars": 0,
                "error": None,
            }
        )
    return entries


def _detect_hallucination(text: str) -> bool:
    if text.count(HALLUCINATION_PHRASE) >= HALLUCINATION_MIN_REPEATS:
        return True
    # repeated 6+ char phrase >= 4 times
    for m in re.finditer(r"(.{6,}?)\1{3,}", text, flags=re.DOTALL):
        if len(m.group(1).strip()) >= 6:
            return True
    return False


def _parse_mlx_json(json_path: Path) -> str:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "text" in data and isinstance(data["text"], str):
            return data["text"].strip()
        segs = data.get("segments")
        if isinstance(segs, list):
            return "".join(
                s.get("text", "") for s in segs if isinstance(s, dict)
            ).strip()
    return ""


def _transcribe_mlx(
    segment_path: Path,
    *,
    language: Optional[str],
    model: str,
    work_dir: Path,
    index: int,
) -> str:
    mlx = _which("mlx_whisper")
    if not mlx:
        _die("mlx_whisper not found (pipx install mlx-whisper)")

    out_dir = work_dir / "mlx_out" / f"seg_{index:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*"):
        if old.is_file():
            old.unlink()

    cmd = [
        mlx,
        str(segment_path),
        "--model",
        model,
        "--output-format",
        "json",
        "--output-dir",
        str(out_dir),
        "--condition-on-previous-text",
        "False",
        "--temperature",
        "0.2",
    ]
    if language:
        cmd.extend(["--language", language])

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        _die(f"mlx_whisper failed on {segment_path.name}: {err}")

    json_files = sorted(out_dir.glob("*.json"))
    if not json_files:
        _die(f"mlx_whisper produced no json in {out_dir}")
    text = _parse_mlx_json(json_files[0])
    if not text:
        _die(f"mlx_whisper empty transcript for {segment_path.name}")
    if _detect_hallucination(text):
        _log(f"warning: possible hallucination in segment {index}, review or re-run")
    return text


def _transcribe_faster(
    segment_path: Path,
    *,
    language: Optional[str],
    model: str,
) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        _die("faster_whisper not installed")

    whisper = WhisperModel(model, device="cpu", compute_type="int8")
    kwargs: Dict[str, Any] = {}
    if language:
        kwargs["language"] = language
    segments, _info = whisper.transcribe(str(segment_path), **kwargs)
    text = "".join(s.text for s in segments).strip()
    if not text:
        _die(f"faster_whisper empty transcript for {segment_path.name}")
    return text


def _transcribe_openai(
    segment_path: Path,
    *,
    language: Optional[str],
    model: str,
    prompt: Optional[str],
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        _die("OPENAI_API_KEY is not set for --engine openai")
    try:
        from openai import OpenAI
    except ImportError:
        _die("openai SDK not installed")

    client = OpenAI()
    size = segment_path.stat().st_size
    if size > CHUNK_SIZE_THRESHOLD_BYTES:
        _die(f"Segment still exceeds 25MB: {segment_path} ({size} bytes)")

    with segment_path.open("rb") as f:
        payload: Dict[str, Any] = {
            "model": model,
            "file": f,
            "response_format": "text",
        }
        if language:
            payload["language"] = language
        if prompt:
            payload["prompt"] = prompt
        result = client.audio.transcriptions.create(**payload)

    text = getattr(result, "text", None)
    if not isinstance(text, str) or not text.strip():
        _die(f"OpenAI empty transcript for {segment_path.name}")
    return text.strip()


def _append_segment(
    out_path: Path,
    *,
    start_sec: float,
    index: int,
    text: str,
) -> None:
    header = f"\n[{_format_timestamp(start_sec)}] segment {index}\n"
    block = header + text.strip() + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(block)
    _log(f"appended segment {index} ({len(text)} chars) -> {out_path}")


def _transcribe_one(
    segment_path: Path,
    *,
    engine: str,
    language: Optional[str],
    mlx_model: str,
    faster_model: str,
    openai_model: str,
    prompt: Optional[str],
    work_dir: Path,
    index: int,
) -> str:
    if engine == "mlx":
        return _transcribe_mlx(
            segment_path,
            language=language,
            model=mlx_model,
            work_dir=work_dir,
            index=index,
        )
    if engine == "faster":
        return _transcribe_faster(
            segment_path, language=language, model=faster_model
        )
    if engine == "openai":
        return _transcribe_openai(
            segment_path,
            language=language,
            model=openai_model,
            prompt=prompt,
        )
    _die(f"Unknown engine: {engine}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe long audio via ffmpeg chunks + serial whisper."
    )
    parser.add_argument("audio", type=Path, help="Source audio/video file")
    parser.add_argument("--out", required=True, type=Path, help="Master transcript path")
    parser.add_argument(
        "--engine",
        choices=ENGINES,
        default="mlx",
        help="Transcription backend (default: mlx)",
    )
    parser.add_argument("--language", help="Language hint, e.g. zh or en")
    parser.add_argument(
        "--segment-sec",
        type=int,
        default=DEFAULT_SEGMENT_SEC,
        help=f"Chunk length in seconds (default: {DEFAULT_SEGMENT_SEC})",
    )
    parser.add_argument(
        "--mlx-model",
        default=DEFAULT_MLX_MODEL,
        help=f"mlx_whisper model (default: {DEFAULT_MLX_MODEL})",
    )
    parser.add_argument(
        "--faster-model",
        default=DEFAULT_FASTER_MODEL,
        help=f"faster_whisper model size (default: {DEFAULT_FASTER_MODEL})",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o-mini-transcribe",
        help="OpenAI transcription model",
    )
    parser.add_argument("--prompt", help="OpenAI prompt (openai engine only)")
    parser.add_argument(
        "--force-chunk",
        action="store_true",
        help="Always split even if short",
    )
    parser.add_argument(
        "--no-chunk",
        action="store_true",
        help="Single segment (short audio only)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip segments marked done in manifest.json",
    )
    parser.add_argument(
        "--rebuild-out",
        action="store_true",
        help="Truncate --out and re-append from done segments only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Split + write manifest only, no transcription",
    )
    parser.add_argument(
        "--sleep-between",
        type=float,
        default=0.0,
        help="Seconds to sleep between segments (API rate limits)",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=0,
        help="Stop after N segments (0 = all)",
    )
    args = parser.parse_args()

    source = args.audio.expanduser().resolve()
    if not source.exists():
        _die(f"Audio not found: {source}")

    _require_tools("ffmpeg", "ffprobe")
    if args.engine == "mlx" and not args.dry_run:
        if not _which("mlx_whisper"):
            _die("mlx_whisper not found")

    out_path = args.out.expanduser().resolve()
    work_dir = _chunks_dir(out_path)
    manifest_path = _manifest_path(out_path)

    duration = _ffprobe_duration(source)
    size_bytes = source.stat().st_size
    use_chunks = _should_chunk(
        duration,
        size_bytes,
        force_chunk=args.force_chunk,
        no_chunk=args.no_chunk,
    )
    segment_sec = args.segment_sec if use_chunks else int(math.ceil(duration)) or 1
    seg_count = max(1, math.ceil(duration / segment_sec)) if use_chunks else 1

    _log(
        f"source={source.name} duration={duration:.1f}s size={size_bytes} "
        f"chunked={use_chunks} segments={seg_count} segment_sec={segment_sec}"
    )

    if args.rebuild_out and out_path.exists():
        out_path.unlink()

    manifest = _load_manifest(manifest_path)
    if not manifest or not args.resume:
        manifest = {
            "version": 1,
            "source": str(source),
            "out": str(out_path),
            "engine": args.engine,
            "language": args.language,
            "segment_sec": segment_sec,
            "duration_sec": duration,
            "size_bytes": size_bytes,
            "chunked": use_chunks,
            "segments": [],
        }

    existing = {s["index"]: s for s in manifest.get("segments", []) if "index" in s}
    planned = _split_audio(source, work_dir, duration, segment_sec)
    merged_segments: List[Dict[str, Any]] = []
    for entry in planned:
        idx = entry["index"]
        if args.resume and idx in existing and existing[idx].get("status") == "done":
            entry = {**existing[idx], "status": "done"}
        merged_segments.append(entry)
    manifest["segments"] = merged_segments
    _save_manifest(manifest_path, manifest)

    if args.dry_run:
        _log(f"dry-run complete: {manifest_path}")
        print(json.dumps({"manifest": str(manifest_path), "segments": seg_count}, indent=2))
        return

    done_count = 0
    limit = args.max_segments if args.max_segments > 0 else len(merged_segments)

    for entry in merged_segments[:limit]:
        idx = entry["index"]
        if args.resume and entry.get("status") == "done":
            _log(f"segment {idx} done (resume skip)")
            done_count += 1
            continue

        seg_path = work_dir / entry["path"]
        if not seg_path.exists():
            _die(f"Missing segment file: {seg_path}")

        start = time.time()
        try:
            text = _transcribe_one(
                seg_path,
                engine=args.engine,
                language=args.language,
                mlx_model=args.mlx_model,
                faster_model=args.faster_model,
                openai_model=args.openai_model,
                prompt=args.prompt,
                work_dir=work_dir,
                index=idx,
            )
            entry["status"] = "done"
            entry["chars"] = len(text)
            entry["error"] = None
            entry["elapsed_sec"] = round(time.time() - start, 1)
            _append_segment(
                out_path,
                start_sec=float(entry["start_sec"]),
                index=idx,
                text=text,
            )
            done_count += 1
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "failed"
            entry["error"] = str(exc)
            _save_manifest(manifest_path, manifest)
            _die(f"segment {idx} failed: {exc}")

        _save_manifest(manifest_path, manifest)
        if args.sleep_between > 0 and idx < len(merged_segments) - 1:
            time.sleep(args.sleep_between)

    summary = {
        "out": str(out_path),
        "manifest": str(manifest_path),
        "segments_total": len(merged_segments),
        "segments_done": sum(1 for s in merged_segments if s.get("status") == "done"),
        "resume": args.resume,
        "bytes_written": out_path.stat().st_size if out_path.exists() else 0,
    }
    print(json.dumps(summary, indent=2))
    if summary["segments_done"] < summary["segments_total"]:
        _die(
            f"Incomplete: {summary['segments_done']}/{summary['segments_total']} segments"
        )


if __name__ == "__main__":
    main()
