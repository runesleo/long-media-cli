#!/usr/bin/env python3
"""Transcript status + structured digest stub for Agent completion."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SEGMENT_MARKER = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\] segment (\d+)\s*$", re.MULTILINE)
REPEAT_PHRASE = re.compile(r"(.{4,30}?)\1{4,}")


def _die(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def manifest_path(transcript: Path) -> Path:
    return Path(f"{transcript}.chunks/manifest.json")


def load_manifest(transcript: Path) -> dict[str, Any]:
    mp = manifest_path(transcript)
    if not mp.exists():
        _die(f"manifest not found: {mp}")
    return json.loads(mp.read_text(encoding="utf-8"))


def transcript_status(transcript: Path) -> dict[str, Any]:
    transcript = transcript.expanduser().resolve()
    if not transcript.exists():
        _die(f"transcript not found: {transcript}")
    mp = manifest_path(transcript)
    if not mp.exists():
        size = transcript.stat().st_size
        return {
            "transcript": str(transcript),
            "complete": size > 500,
            "segments_done": None,
            "segments_total": None,
            "duration_sec": None,
            "note": "no manifest; assuming subtitle or non-chunked transcript" if size > 500 else "empty or missing manifest",
        }
    manifest = load_manifest(transcript)
    segments = manifest.get("segments", [])
    done = sum(1 for s in segments if s.get("status") == "done")
    total = len(segments)
    return {
        "transcript": str(transcript),
        "manifest": str(mp),
        "complete": done >= total and total > 0,
        "segments_done": done,
        "segments_total": total,
        "duration_sec": manifest.get("duration_sec"),
        "engine": manifest.get("engine"),
        "language": manifest.get("language"),
    }


def _stem_slug(transcript: Path) -> str:
    name = transcript.name
    if name.endswith(".transcript.txt"):
        return name[: -len(".transcript.txt")]
    return transcript.stem


def _load_sidecar(transcript: Path, suffix: str) -> Optional[dict[str, Any]]:
    p = transcript.parent / f"{_stem_slug(transcript)}{suffix}"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _parse_segments(text: str) -> list[dict[str, Any]]:
    parts = SEGMENT_MARKER.split(text)
    if len(parts) < 3:
        return []
    segments: list[dict[str, Any]] = []
    i = 1
    while i + 2 < len(parts):
        ts, idx_s, body = parts[i], parts[i + 1], parts[i + 2]
        segments.append({"timestamp": ts, "index": int(idx_s), "text": body.strip()})
        i += 3
    return segments


def _format_duration(sec: Optional[float]) -> str:
    if not sec:
        return "unknown"
    m = int(sec // 60)
    return f"~{m} min ({sec:.0f}s)"


def _detect_hallucination_flags(segments: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for seg in segments:
        body = seg["text"]
        if len(body) < 100:
            continue
        if REPEAT_PHRASE.search(body):
            flags.append(f"segment {seg['index']} @ {seg['timestamp']}: high repetition (possible mlx hallucination)")
        # repeated short clause density
        words = body.split()
        if len(words) > 40:
            from collections import Counter

            bigrams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]
            top = Counter(bigrams).most_common(1)
            if top and top[0][1] >= 8:
                flags.append(f"segment {seg['index']} @ {seg['timestamp']}: repeated trigram ×{top[0][1]}")
    return flags


def _next_timestamp(segments: list[dict[str, Any]], i: int) -> str:
    if i + 1 < len(segments):
        return segments[i + 1]["timestamp"]
    return "end"


def prepare_digest(
    transcript: Path,
    *,
    out: Optional[Path] = None,
    title: Optional[str] = None,
    url: Optional[str] = None,
    shownotes: Optional[Path] = None,
    write_prompt: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    transcript = transcript.expanduser().resolve()
    status = transcript_status(transcript)
    if status.get("segments_total") and not status["complete"] and not force:
        _die(
            f"transcript incomplete: {status['segments_done']}/{status['segments_total']} segments "
            "(use --force to stub anyway)"
        )

    text = transcript.read_text(encoding="utf-8", errors="replace")
    segments = _parse_segments(text)
    ingest = _load_sidecar(transcript, ".ingest.json")
    download = _load_sidecar(transcript, ".download.json")

    meta_title = title
    meta_url = url
    if ingest:
        meta_title = meta_title or ingest.get("title")
        meta_url = meta_url or ingest.get("source")
    if download:
        meta_title = meta_title or download.get("title")
        meta_url = meta_url or download.get("source_url") or download.get("url")

    slug = _stem_slug(transcript)
    meta_title = meta_title or slug.replace("-", " ").title()
    duration = status.get("duration_sec") or (ingest or {}).get("duration_sec") or (download or {}).get("duration_sec")

    out_path = out or transcript.parent / f"{slug}-digest.md"
    flags = _detect_hallucination_flags(segments)

    chapter_lines = []
    for i, seg in enumerate(segments):
        end = _next_timestamp(segments, i)
        chapter_lines.append(f"### Segment {seg['index']} (~{seg['timestamp']}–{end})")
        chapter_lines.append("<!-- Agent: 2-3 句章节摘要 -->")
        chapter_lines.append("")

    quality_block = ""
    if flags:
        quality_block = "## 质量备注\n\n" + "\n".join(f"- {f}" for f in flags) + "\n\n"

    shownotes_block = ""
    if shownotes and shownotes.exists():
        sn = shownotes.read_text(encoding="utf-8", errors="replace").strip()
        shownotes_block = f"## Show notes（官方）\n\n{sn[:4000]}\n\n"

    body = f"""# {meta_title}

**来源**: {meta_url or "—"}
**时长**: {_format_duration(float(duration) if duration else None)}
**转写**: `{transcript.name}`
**段落**: {status.get('segments_done') or len(segments)}/{status.get('segments_total') or len(segments) or "—"}

## 概要
<!-- Agent: 2-3 句 — 谁、聊什么、结论倾向 -->

## 章节摘要
{chr(10).join(chapter_lines) if chapter_lines else "<!-- 无 segment marker；Agent 按话题分段 -->"}

## 核心观点
<!-- Agent: 5-8 条要点 -->

## 金句
> <!-- Agent -->

## 可引用素材（Quote / 长文）
- 

## 行动建议（可选）
- 

{quality_block}## 文件索引

| 文件 | 路径 |
|------|------|
| 转写 | `{transcript.name}` |
| manifest | `{manifest_path(transcript).name if manifest_path(transcript).exists() else "—"}` |
"""

    out_path.write_text(body, encoding="utf-8")
    result: dict[str, Any] = {
        "digest": str(out_path),
        "transcript": str(transcript),
        "complete": status.get("complete", True),
        "quality_flags": flags,
    }

    if write_prompt:
        prompt_path = out_path.with_suffix(".agent-prompt.md")
        excerpt_parts = []
        if segments:
            for seg in segments[:2] + segments[-2:]:
                excerpt_parts.append(f"### [{seg['timestamp']}] segment {seg['index']}\n{seg['text'][:2000]}")
        elif text:
            excerpt_parts.append(text[:4000])

        prompt = f"""# Digest agent prompt · {slug}

Fill `{out_path.name}` using template in long-media-cli `docs/digest-template.md`.

## Metadata
- title: {meta_title}
- url: {meta_url or "—"}
- duration: {_format_duration(float(duration) if duration else None)}
- quality_flags: {flags or "none"}

## Instructions
1. Read show notes (if any) + excerpts below for framing
2. Write 章节摘要 aligned to timestamps
3. 核心观点 must be verifiable from transcript; flag marketing claims
4. Skip or note hallucinated segments in 质量备注
5. Run anti-AI checks if publishing (leo-style)

{shownotes_block}
## Transcript excerpts

{chr(10).join(excerpt_parts)}

## Full transcript
`{transcript.name}` (in output dir)
"""
        prompt_path.write_text(prompt, encoding="utf-8")
        result["agent_prompt"] = str(prompt_path)

    _log(f"digest stub → {out_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcript status + digest stub")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Check transcript / manifest progress")
    p_status.add_argument("transcript")

    p_prep = sub.add_parser("prepare", help="Write digest stub + agent prompt")
    p_prep.add_argument("transcript")
    p_prep.add_argument("--out", type=Path)
    p_prep.add_argument("--title")
    p_prep.add_argument("--url")
    p_prep.add_argument("--shownotes", type=Path)
    p_prep.add_argument("--no-prompt", action="store_true")
    p_prep.add_argument("--force", action="store_true")

    args = parser.parse_args()
    transcript = Path(args.transcript)

    if args.cmd == "status":
        print(json.dumps(transcript_status(transcript), indent=2, ensure_ascii=False))
        return

    result = prepare_digest(
        transcript,
        out=args.out,
        title=args.title,
        url=args.url,
        shownotes=args.shownotes,
        write_prompt=not args.no_prompt,
        force=args.force,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
