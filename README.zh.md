# long-media-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

English: [README.md](./README.md)

把 **长播客、长视频、X Space 回放** 变成可断点续跑的全文转写 —— 不用对着 90 分钟的 whisper 任务干等，也不会等到结束才发现 0 字节。

一条命令：URL 或本地文件 → 下载（YouTube/B站 优先字幕）→ mlx 切段转写 → `{slug}.transcript.txt`。v0.2 起可选 digest stub，交给 Agent 写精华。

<p align="center">
  <a href="docs/architecture.svg">
    <img src="docs/architecture.png" alt="long-media-cli 架构：ingest、切段转写、可选 digest" width="920"/>
  </a>
</p>

## 你能得到什么

- **统一 ingest** — YouTube、B站、小宇宙、X Space、Apple Podcasts、本地音视频，一个入口。
- **切段转写** — ffmpeg 切 8–10 分钟段；mlx-whisper **串行**跑；每段完成就 **append** 到输出（可 `tail -f`）。
- **断点续跑** — `manifest.json` + `--resume`；60 分钟以上中断不用重来。
- **视频字幕优先** — 有 VTT/字幕则跳过 whisper。
- **Digest stub** — `digest.py prepare` 生成章节骨架 + Agent prompt；自动标 mlx 首尾段幻觉。

## 怎么工作

```text
URL 或本地文件
    ↓ ingest.py（识别平台 → 下载/字幕）
    ↓ transcribe_chunked.py（无可用字幕时）
    ↓ {slug}.transcript.txt + {slug}.ingest.json
    ↓ digest.py prepare（可选）
    ↓ Agent 填 {slug}-digest.md
```

**输入示例**（小宇宙）：

```bash
python3 ingest.py "https://www.xiaoyuzhoufm.com/episode/EPISODE_ID" \
  --out-dir ./output --language zh --resume
```

**输出示例**：

```text
output/
  episode-slug.m4a
  episode-slug.transcript.txt
  episode-slug.transcript.txt.chunks/
  episode-slug.ingest.json
```

## 安装

```bash
git clone https://github.com/runesleo/long-media-cli.git
cd long-media-cli
chmod +x ingest.sh ingest.py digest.py

brew install ffmpeg yt-dlp
pipx install mlx-whisper
```

任何 AI Agent 读 `docs/ingest.md` 即可接入，无框架绑定。

## 环境要求

- **Apple Silicon Mac** — 主要验证平台
- `ffmpeg`、`ffprobe`、`yt-dlp`
- `mlx_whisper`（`pipx install mlx-whisper`）
- 可选：`faster-whisper`（`--engine faster`）、OpenAI（`--engine openai` + API key）
- YouTube / Space 下载默认 `--cookies-from-browser chrome`

**隐私说明：** 默认情况下 `ingest.py` / `download_twitter_space.py` 会让 yt-dlp 读取**本机 Chrome** 的 Cookie（仅本机，CLI 不上传）。不需要时：`--cookies-from-browser ""`。

## 快速开始

```bash
# 小宇宙 / 播客
./ingest.sh "https://www.xiaoyuzhoufm.com/episode/..." ./output zh

# YouTube
./ingest.sh "https://www.youtube.com/watch?v=..." ./output zh

# X Space（480 秒切段）
./ingest.sh "https://x.com/i/spaces/SPACE_ID" ./output zh 480

# 本地 m4a
./ingest.sh ./episode.m4a ./output zh 600

# 转录完成后
python3 digest.py prepare ./output/episode.transcript.txt
```

## 已验证

MacBook Pro Apple Silicon · mlx · 生产跑通（非每次发版重跑）。

| 来源 | 时长 | 切段 | 结果 |
|------|------|------|------|
| 小宇宙播客 | ~139 min | 14 × 600 s | 14/14 完成 |
| X Space | ~71 min | 9 × 480 s | 9/9 · 首尾段可能有 mlx 幻觉 |

详见 [docs/chunked-local.md](docs/chunked-local.md)。

## 已知限制（v0.2）

- 面向 **>20 分钟** 长内容；短视频可能过度切段。
- Space/播客 **首尾段 mlx 幻觉**（重复歌词式文本）— `digest.py` 会标出，需人工跳过或重跑该段。
- B站走 API 绕过 yt-dlp 412，接口变更可能失效。
- 小宇宙从页面 HTML 抽 CDN，SPA 改版可能要修脚本。
- **Digest 正文** 不在 CLI 内 — 只出 stub，精华由 Agent 填。
- 主路径是 Apple Silicon + mlx；其他平台试 `--engine faster`。

## 路线图

- [ ] `pip install` 入口
- [ ] 按 segment index 单段重跑（修幻觉段）
- [ ] 可选 LLM digest（env 开关，默认关）

## 关于作者

*Leo（[@runes_leo](https://x.com/runes_leo)）— AI × Crypto 独立构建者。在 [Polymarket](https://polymarket.com/?via=runes-leo&r=runesleo&utm_source=github&utm_content=long-media-cli) 做量化，用 Claude Code 和 Codex 搭数据与内容管线。*

*[leolabs.me](https://leolabs.me) — 写作 · 社群 · 开源工具 · 独立项目*

*[X 订阅](https://x.com/runes_leo/creator-subscriptions/subscribe) — 付费内容周刊*

*Learn in public, Build in public.*

## License

MIT — 见 [LICENSE](LICENSE)。
