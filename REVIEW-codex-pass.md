# long-media-cli 开源发布审查（Codex pass）

## 🔴 Blockers（发布前必改）

1. **ingest.py:83 — 小宇宙音频 URL 正则错误**  
   `[^\"'\\s]+` 在字符类里表示「排除 `\` 和字母 `s`」，不是 `\s` 空白。CDN URL 常在 `s` 处截断，导致匹配失败或 curl 到错误地址。  
   **修复**：`r"https://media\.xyzcdn\.net/[^\s\"']+\.(m4a|mp3)"`

2. **transcribe_chunked.py:451–520 + ingest.py:465 — `--no-resume` 会重复追加转写**  
   `resume=False` 时重建 manifest 为 pending，但不截断 `--out`；循环仍 `_append_segment` 追加。`ingest --no-resume` 会叠两段。  
   **修复**：`not args.resume` 且无 `--rebuild-out` 时警告并 truncate，或默认在 fresh run 时清空 `out_path`。

3. **README / 隐私 — 默认读取浏览器 Cookie**  
   `ingest.py:306,447` 与 `download_twitter_space.py:116` 默认 `--cookies-from-browser chrome`。MIT 公开仓库需在 README 显著说明：会访问本机浏览器 profile，用户应知情并可传空字符串禁用。

## 🟡 Warnings（建议修）

1. **ingest.py:333–384 — `--subs-only` 仍会先下载音频**  
   对 B 站/YouTube 在 `_die` 前已走完整下载路径，违背「仅字幕」语义。应在 `subs_only` 时提前分支，只调 `_try_subtitles`。

2. **ingest.py:152,181 — cookies 传参风格不一致**  
   使用 `--cookies-from-browser={cookies}` 单参数；`download_twitter_space.py:72` 用两参数。建议统一为 argv 分离，避免特殊字符歧义。

3. **digest.py:187,256 — 绝对路径写入 digest / prompt**  
   `` `{transcript}` `` 为 resolve 后的绝对路径，分享 stub 时可能泄露 home 目录。建议仅写相对名或 `$PWD` 相对路径。

4. **download_twitter_space.py:122–123 — Space URL 校验过宽**  
   子串匹配 `x.com` 可误接受非 Space 链接；失败时 yt-dlp 错误晦涩。应强制 `/i/spaces/<id>` 并与 `ingest` 一致。

5. **transcribe_chunked.py:488–492 — resume 跳过不重 append**  
   manifest 为 done 但 `.transcript.txt` 被删时，resume 跳过且无 `--rebuild-out` 会得到不完整输出。文档说明或检测 out 缺失时重跑该段。

6. **ingest.py:81–88 — 小宇宙依赖页面 HTML 刮取**  
   无官方 API，页面结构变更即坏；错误信息可注明「页面无 CDN 链接」。

7. **ingest.py:68 — 日志打印完整命令**  
   含本机绝对路径；调试可保留，文档注明勿粘贴公开日志。

## 🟢 OK

- 子进程均为 `subprocess.run` 列表形式，无 `shell=True`，无命令注入面。
- `slug` / `_slug()` 净化文件名；`bvid` 有格式约束。
- `OPENAI_API_KEY` 仅环境变量；`.gitignore` 含 `.env`。
- `transcribe_chunked.py` 分段、manifest、幻觉检测、OpenAI 25MB 检查逻辑清晰。
- `digest.py` 不完整转写默认拒绝 `prepare`（`--force` 可覆盖）；质量 flag 实用。
- Shell 包装脚本 `set -euo pipefail`，参数引用安全。

## 发布清单（非代码）

- 确认 `LICENSE` 为 MIT 且与 README 一致  
- README 写明依赖：ffmpeg、yt-dlp、可选 mlx_whisper / faster-whisper  
- 示例输出目录 `output/` 已在 `.gitignore`
