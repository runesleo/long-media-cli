# Digest template (播客 / Space / 长视频)

Agent completes `{slug}-digest.md` after `digest.py prepare` or manual stub.

## Inputs

| File | Role |
|------|------|
| `*.transcript.txt` | Master text with `[HH:MM:SS] segment N` markers |
| `*-shownotes.txt` | Optional official outline |
| `*.ingest.json` | URL, title, source_type from unified ingest |
| `{slug}-digest.agent-prompt.md` | Auto-generated prompt bundle |

## Output sections

1. **概要** — 2-3 句
2. **章节摘要** — per segment or topic, with timestamps
3. **核心观点** — 5-8 条；营销口径单独标注
4. **金句**
5. **可引用素材**
6. **行动建议**（可选）
7. **质量备注** — hallucination / 同音错字 / 需核实声称

## CLI

```bash
# Check progress before digest
python3 digest.py status episode.transcript.txt

# Stub + agent prompt (requires complete manifest)
python3 digest.py prepare episode.transcript.txt

# After ingest with --prepare-digest
python3 ingest.py URL --out-dir ~/out --prepare-digest
```

## Agent steps

1. Read `.agent-prompt.md` + show notes
2. Fill stub sections; align chapters to segment timestamps
3. Run anti-AI / FORAB if publishing project marketing content

See also: `docs/digest-template.md` in this repo for the public template.
