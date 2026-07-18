---
name: mtools
description: >-
  Use MTools desktop MCP for local image/audio/video processing, ASR/TTS,
  OCR, subtitle workflows, and developer utilities. Prefer when the user asks
  to compress/convert media, generate subtitles, remove watermarks, OCR images,
  translate text, or call local HTTP/WebSocket tools. Requires MTools app
  running with MCP enabled (default http://127.0.0.1:8765/mcp).
version: 1.0.0
license: MIT
platforms: [windows, macos, linux]
metadata:
  openclaw:
    emoji: "🧰"
    requires:
      config: ["mcp"]
  hermes:
    tags: [MTools, MCP, Media, Image, Video, Audio, Subtitle, OCR, Local]
---

# MTools MCP

MTools is a local desktop toolbox. Its **built-in MCP server** exposes ~63 tools
(plus helpers). This skill teaches when and how to call them.

## Prerequisites

1. User has **MTools desktop app running**
2. Settings → **MCP 服务** → enabled
3. Default endpoint: `http://127.0.0.1:8765/mcp`
4. AI/ONNX features need models already downloaded inside MTools GUI

If MCP is offline: tell the user to open MTools and enable MCP. Do not invent paths.

## Call rules (strict)

1. Prefer **atomic tools**: `mtools_image_compress`, `mtools_video_convert`, …
2. Unknown params → `mtools_help("image.compress")` first
3. List capabilities → `mtools_tool_ids()` or `mtools_help()`
4. Fallback entry → `mtools_run(tool_id, params_json)`
5. Paths must be **absolute local paths** on the user's machine
6. Responses are JSON strings — check `ok` before continuing
7. Markdown viewer is **not** exposed via MCP

## Quick map (user intent → tool)

| User says | Call |
|-----------|------|
| 压缩图片 | `mtools_image_compress` |
| 图片转 jpg/png/webp | `mtools_image_format` |
| 抠图 / 去背景 | `mtools_image_background` |
| OCR / 识字 | `mtools_image_ocr` |
| 去图片水印 | `mtools_image_watermark_remove` |
| 压缩视频 | `mtools_video_compress` |
| 视频转格式 | `mtools_video_convert` |
| 视频提取音频 | `mtools_video_extract_audio` |
| 视频去字幕 | `mtools_video_subtitle_remove` |
| 视频生成字幕 | `mtools_video_subtitle`（可 `target_lang`/`bilingual`/`burn_in`） |
| TS 分片合并 | `mtools_video_ts_merge` |
| 音频转文字 | `mtools_audio_to_text` |
| 文字转语音 | `mtools_audio_text_to_speech` |
| 人声分离 | `mtools_audio_vocal_extraction` / `mtools_video_vocal_separation` |
| 字幕格式互转 | `mtools_subtitle_convert` |
| AI 润色字幕 | `mtools_ai_subtitle_fix` |
| 翻译 | `mtools_others_translate` |
| 证件照 | `mtools_others_id_photo` |
| HTTP 请求 | `mtools_dev_http_client` |
| WebSocket | `mtools_websocket`（connect→send→receive→disconnect） |
| 录屏 | 仅 GUI，MCP 不可用 |

Naming: `tool_id` `image.compress` → atomic tool `mtools_image_compress`
(`mtools_` + dots → underscores).

## Workflows

### A. Compress a photo

```
mtools_image_compress(
  input_path="C:/photos/a.jpg",
  quality="high",          # high|medium|low
  compress_mode_name="balanced"  # fast|balanced|max
)
```

### B. Video → subtitles (timestamps / translate / burn-in)

```
mtools_video_subtitle(
  input_path="C:/a.mp4",
  language="zh",
  target_lang="en",   # optional translate
  bilingual=True,     # original + translation
  burn_in=False       # True = burn into video
)
```

Then optionally preserve timing with AI fix:

```
mtools_ai_subtitle_fix(
  segments_json='[{"text":"...","start":0,"end":1.2}, ...]',
  base_url=..., api_key=..., model=...
)
```

Need SenseVoice/Whisper model downloaded in MTools first.

### C. Audio → text

```
mtools_audio_to_text(input_path="C:/a.mp3", language="zh")
```

Default engine is SenseVoice (50+ languages) via sherpa-onnx.

### D. Remove hardsubs / watermarks

Prefer exact region:

```
mtools_video_subtitle_remove(
  input_path="C:/a.mp4",
  left=0, top=800, right=1920, bottom=1080
)
```

Or band: `subtitle_region="bottom"|"top"`. Needs subtitle-remove model in MTools.

### E. Compress video with controls

```
mtools_video_compress(input_path="C:/a.mp4", scale="720p", crf=23, fps=30)
```

### F. WebSocket session

```
1. mtools_websocket(action="connect", url="ws://127.0.0.1:8080")
   → save session_id
2. mtools_websocket(action="send", session_id=..., message="ping")
3. mtools_websocket(action="receive", session_id=...)
4. mtools_websocket(action="disconnect", session_id=...)
```

## Error handling

| Symptom | What to do |
|---------|------------|
| connection refused | Ask user to start MTools + enable MCP |
| `ok: false` + 模型未下载 | Ask user to download model in MTools GUI |
| path not found | Ask for a real absolute path |
| ffmpeg unavailable | Ask user to configure FFmpeg in MTools settings |

## Do / Don't

- **Do** call `mtools_status` once when unsure if MCP is healthy
- **Do** keep `output_path` empty when auto output is fine
- **Don't** expose or log API keys from `mtools_ai_subtitle_fix`
- **Don't** claim screen recording works over MCP
- **Don't** call fat legacy tools (`mtools_image` with action=…) — use atomics

## Install MCP client config

See [install.md](install.md) for OpenClaw / Hermes / Cursor snippets.
