# -*- coding: utf-8 -*-
"""各 tool_id 的调用说明，供 mtools_help 与 AI Agent 查阅。"""

from __future__ import annotations

from typing import Any

from mcp_server.schema_types import atomic_tool_name
from mcp_server.tool_ids import TOOL_ID_MAP

# 通用字段说明
_FIELD_DOCS: dict[str, str] = {
    "input_path": "本地文件绝对路径（输入）",
    "output_path": "输出文件绝对路径（可选，不填则自动生成到 MTools 输出目录）",
    "input_paths": "逗号分隔的多个输入路径（拼图合并）",
    "text": "文本内容",
    "quality": "画质：high / medium / low",
    "target_format": "目标格式扩展名，如 jpg / mp4 / mp3",
    "session_id": "WebSocket connect 返回的会话 ID",
    "ws_action": "WebSocket 操作：connect / send / receive / status / disconnect",
    "encoding_action": "dev.encoding 专用：detect（默认）或 convert",
    "json_action": "dev.json_viewer 专用：format（默认）或 minify",
    "windows_update_cmd": "status / disable / restore",
    "params_json": "JSON 字符串，字段见 mtools_help(tool_id) 的 example",
}


def _g(
    summary: str,
    required: list[str],
    optional: list[str] | None = None,
    example: dict[str, Any] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    opt = optional or []
    return {
        "summary": summary,
        "required_params": required,
        "optional_params": opt,
        "param_docs": {k: _FIELD_DOCS[k] for k in required + opt if k in _FIELD_DOCS},
        "example": example or {},
        "notes": notes,
    }


# 每个 tool_id 的调用指南
TOOL_GUIDES: dict[str, dict[str, Any]] = {
    "image.compress": _g("压缩图片", ["input_path"], ["output_path", "quality", "compress_mode_name"],
                        {"input_path": "C:/photos/a.jpg", "quality": "high", "compress_mode_name": "balanced"}),
    "image.format": _g("图片格式转换", ["input_path"], ["output_path", "target_format", "quality"],
                      {"input_path": "C:/a.png", "target_format": "jpg"}),
    "image.resize": _g("调整图片尺寸", ["input_path"], ["output_path", "width", "height", "keep_aspect"],
                      {"input_path": "C:/a.jpg", "width": 1920, "height": 1080}),
    "image.crop": _g("裁剪图片", ["input_path", "left", "top", "right", "bottom"], ["output_path"],
                    {"input_path": "C:/a.jpg", "left": 100, "top": 50, "right": 900, "bottom": 700}),
    "image.rotate": _g("旋转/翻转", ["input_path"], ["output_path", "rotate_mode", "angle"],
                      {"input_path": "C:/a.jpg", "rotate_mode": "rotate_90"},
                      "rotate_mode: rotate_90/rotate_180/rotate_270/flip_horizontal/flip_vertical/custom"),
    "image.background": _g("AI 抠图", ["input_path"], ["output_path", "model_key"],
                          {"input_path": "C:/a.jpg"}, "需已下载抠图模型"),
    "image.watermark": _g("添加文字水印", ["input_path", "text"], ["output_path", "watermark_position", "font_size", "color"],
                          {"input_path": "C:/a.jpg", "text": "© MTools"}),
    "image.watermark_remove": _g(
        "去水印", ["input_path"],
        ["output_path", "remove_mode", "left", "top", "right", "bottom", "model_key"],
        {"input_path": "C:/a.jpg", "remove_mode": "ai", "left": 0, "top": 800, "right": 1920, "bottom": 1080},
        "simple=区域修复；ai=模型修复。务必传 left/top/right/bottom 指定水印区域",
    ),
    "image.info": _g("查看图片信息", ["input_path"], [], {"input_path": "C:/a.jpg"}),
    "image.exif": _g("去除 EXIF", ["input_path"], ["output_path"], {"input_path": "C:/a.jpg"}),
    "image.qrcode": _g("生成二维码", ["text"], ["output_path", "qrcode_level"], {"text": "https://example.com"}),
    "image.to_base64": _g("图片转 Base64", ["input_path"], [], {"input_path": "C:/a.jpg"}),
    "image.gif": _g("GIF 调整", ["input_path"], ["output_path", "gif_speed", "gif_reverse"], {"input_path": "C:/a.gif", "gif_speed": 1.5}),
    "image.enhance": _g("AI 图像增强", ["input_path"], ["output_path", "model_key", "denoise_strength", "sharpen_strength"],
                        {"input_path": "C:/a.jpg"}, "需已下载增强模型"),
    "image.puzzle.merge": _g("拼图合并", ["input_paths"], ["output_path", "puzzle_direction", "puzzle_spacing", "grid_cols"],
                            {"input_paths": "C:/a.jpg,C:/b.jpg", "puzzle_direction": "horizontal"}),
    "image.puzzle.split": _g("拼图切分", ["input_path"], ["output_path", "puzzle_rows", "puzzle_cols", "puzzle_shuffle"],
                            {"input_path": "C:/a.jpg", "puzzle_rows": 3, "puzzle_cols": 3}),
    "image.search": _g("以图搜图", ["input_path"], [], {"input_path": "C:/a.jpg"}),
    "image.ocr": _g("OCR 文字识别", ["input_path"], ["model_key"], {"input_path": "C:/a.jpg"}, "需已下载 OCR 模型"),
    "image.color_space": _g("色彩空间转换", ["input_path"], ["output_path", "color_space", "binary_threshold"],
                            {"input_path": "C:/a.jpg", "color_space": "grayscale"},
                            "color_space: grayscale/rgba/rgb/cmyk/lab/hsv/invert/sepia/binary"),
    "image.border": _g("添加边框", ["input_path"], ["output_path", "border_top", "border_bottom", "border_left", "border_right", "color", "corner_radius"],
                       {"input_path": "C:/a.jpg", "border_top": 20, "color": "#FFFFFF"}),
    "audio.format": _g("音频格式转换", ["input_path"], ["output_path", "target_format", "bitrate", "sample_rate", "channels"],
                      {"input_path": "C:/a.wav", "target_format": "mp3", "bitrate": 192}),
    "audio.compress": _g("音频压缩", ["input_path"], ["output_path", "bitrate", "sample_rate", "channels"], {"input_path": "C:/a.wav", "bitrate": 128}),
    "audio.speed": _g("音频倍速", ["input_path"], ["output_path", "speed"], {"input_path": "C:/a.mp3", "speed": 1.5}),
    "audio.vocal_extraction": _g("人声分离", ["input_path"], ["output_path", "model_key", "vocal_output"],
                                {"input_path": "C:/a.mp3", "vocal_output": "both"}, "vocal_output: vocals/instrumental/both"),
    "audio.to_text": _g("语音转文字", ["input_path"], ["language", "model_key"], {"input_path": "C:/a.mp3", "language": "zh"},
                       "默认 SenseVoice INT8（sherpa-onnx），50+ 语言；需先在 GUI 下载模型"),
    "audio.text_to_speech": _g("文字转语音", ["text"], ["output_path", "model_key"], {"text": "你好世界"}),
    "video.compress": _g(
        "视频压缩", ["input_path"],
        ["output_path", "quality", "crf", "scale", "fps", "preset"],
        {"input_path": "C:/a.mp4", "quality": "medium", "scale": "720p"},
        "scale: original/4k/2k/1080p/720p/480p/360p；crf>0 时覆盖 quality；fps=0 保持原帧率",
    ),
    "video.convert": _g("视频格式转换", ["input_path"], ["output_path", "target_format", "vcodec", "acodec"],
                        {"input_path": "C:/a.avi", "target_format": "mp4"}),
    "video.extract_audio": _g("提取音频", ["input_path"], ["output_path", "target_format", "bitrate"], {"input_path": "C:/a.mp4", "target_format": "mp3"}),
    "video.speed": _g("视频倍速", ["input_path"], ["output_path", "speed"], {"input_path": "C:/a.mp4", "speed": 1.25}),
    "video.vocal_separation": _g("视频人声分离", ["input_path"], ["output_path", "model_key", "vocal_keep"], {"input_path": "C:/a.mp4"}),
    "video.watermark": _g(
        "视频文字水印", ["input_path", "watermark_text"],
        ["output_path", "watermark_position", "font_size", "watermark_opacity"],
        {"input_path": "C:/a.mp4", "watermark_text": "Demo", "watermark_position": "bottom_right"},
    ),
    "video.repair": _g("视频修复", ["input_path"], ["output_path"], {"input_path": "C:/broken.mp4"}),
    "video.enhance": _g(
        "AI 视频增强", ["input_path"],
        ["output_path", "model_key", "max_enhance_frames", "enhance_scale"],
        {"input_path": "C:/a.mp4"},
        "会保留音轨；max_enhance_frames=0 表示处理全部帧；耗时较长",
    ),
    "video.interpolation": _g("AI 视频插帧", ["input_path"], ["output_path", "multiplier", "model_key"],
                              {"input_path": "C:/a.mp4", "multiplier": 2.0}, "会保留音轨"),
    "video.subtitle_remove": _g(
        "去字幕/水印", ["input_path"],
        ["output_path", "model_key", "subtitle_region", "left", "top", "right", "bottom"],
        {"input_path": "C:/a.mp4", "left": 0, "top": 800, "right": 1920, "bottom": 1080},
        "优先用 left/top/right/bottom 精确区域；否则用 subtitle_region=top/bottom",
    ),
    "video.subtitle": _g(
        "生成字幕", ["input_path"],
        ["output_path", "language", "model_key", "target_lang", "bilingual", "burn_in"],
        {"input_path": "C:/a.mp4", "language": "zh", "target_lang": "en", "bilingual": True},
        "真实时间戳 SRT；可选翻译/双语/烧录到视频",
    ),
    "video.screen_record": _g("录屏", [], [], {}, "仅桌面 GUI，MCP 不可用"),
    "video.ts_merge": _g("TS 分片合并", ["input_paths"], ["output_path"],
                        {"input_paths": "C:/a.ts,C:/b.ts"}, "逗号分隔多个 TS/视频分片，copy 合并"),
    "dev.base64_to_image": _g("Base64 转图片", ["text"], ["output_path"], {"text": "iVBORw0KGgo..."}),
    "dev.encoding": _g("文件编码检测/转换", ["input_path"], ["target_encoding", "encoding_action"],
                      {"input_path": "C:/a.txt", "encoding_action": "detect"},
                      '转换时 encoding_action=convert 并指定 target_encoding'),
    "dev.json_viewer": _g("JSON 格式化/压缩", ["text"], ["json_action"],
                         {"text": "{\"a\":1}", "json_action": "format"}),
    "dev.http_client": _g("HTTP 请求", ["url"], ["method", "headers_json", "body", "body_type"],
                         {"method": "GET", "url": "https://httpbin.org/get"}),
    "dev.websocket_client": _g("WebSocket 客户端", [], ["url", "session_id", "message", "ws_action"], {},
                              '用 mtools_websocket 或 ws_action: connect→send→receive→disconnect。connect 示例: {"ws_action":"connect","url":"ws://localhost:8080"}'),
    "dev.encoder_decoder": _g("编码/解码", ["text"], ["encode_type", "decode_mode"],
                             {"text": "hello", "encode_type": "base64"}, "encode_type: base64/hex/url"),
    "dev.regex_tester": _g("正则测试", ["text", "pattern"], [], {"text": "abc123", "pattern": "\\d+"}),
    "dev.timestamp_tool": _g("时间戳转换", ["timestamp"], ["timestamp_unit"], {"timestamp": 1710000000, "timestamp_unit": "s"}),
    "dev.jwt_tool": _g("JWT 解析", ["text"], [], {"text": "eyJhbGciOiJIUzI1NiIs..."}),
    "dev.uuid_generator": _g("生成 UUID", [], [], {}),
    "dev.color_tool": _g("颜色转换", ["text"], ["color_source", "color_target"], {"text": "#438EDB", "color_source": "hex", "color_target": "rgb"}),
    "dev.dns_lookup": _g("DNS 查询", ["host"], ["dns_type", "dns_server"], {"host": "example.com", "dns_type": "A"}),
    "dev.port_scanner": _g("端口扫描", ["host"], ["ports"], {"host": "127.0.0.1", "ports": "80,443,8080"}),
    "dev.format_convert": _g("数据格式互转", ["text"], ["source_format", "target_format"],
                          {"text": "{\"a\":1}", "source_format": "json", "target_format": "yaml"}),
    "dev.text_diff": _g("文本对比", ["left_text", "right_text"], [], {"left_text": "a\nb", "right_text": "a\nc"}),
    "dev.crypto_tool": _g("加密/哈希", ["text"], ["crypto_algorithm", "crypto_encrypt", "crypto_key", "crypto_iv", "crypto_mode"],
                         {"text": "secret", "crypto_algorithm": "SHA256"}),
    "dev.sql_formatter": _g("SQL 格式化", ["text"], [], {"text": "select * from t"}),
    "dev.cron_tool": _g("Cron 解析", ["cron_expr"], ["cron_count"], {"cron_expr": "0 9 * * 1-5"}),
    "others.windows_update": _g("Windows 更新管理", [], ["windows_update_cmd"], {"windows_update_cmd": "status"}, "仅 Windows"),
    "others.image_to_url": _g("图片上传图床", ["input_path"], ["expires_in"], {"input_path": "C:/a.jpg", "expires_in": "7d"}),
    "others.file_to_url": _g("文件上传", ["input_path"], ["storage_type", "temp_hours"], {"input_path": "C:/a.zip"}),
    "others.icp_query": _g("ICP 备案查询", ["domain"], ["query_type"], {"domain": "example.com", "query_type": "web"}),
    "others.id_photo": _g("证件照", ["input_path"], ["output_path", "photo_width", "photo_height", "bg_color"], {"input_path": "C:/photo.jpg"}),
    "others.translate": _g("文本翻译", ["text"], ["target_lang", "source_lang"], {"text": "Hello", "target_lang": "zh-Hans"}),
}


def get_help(tool_id: str = "") -> dict[str, Any]:
    """返回调用帮助。"""
    if not tool_id:
        return {
            "usage": (
                "推荐流程: 1) mtools_tool_ids 查能力 "
                "2) mtools_help(tool_id) 查参数 "
                "3) 调用 atomic_tool（如 mtools_image_compress）或 mtools_run"
            ),
            "call_methods": {
                "atomic_tool": "首选。mtools_tool_ids 返回 atomic_tool 列，参数 schema 含 description",
                "mtools_run": "备选。tool_id + params_json",
                "mtools_websocket": "WebSocket：connect/send/receive/status/disconnect",
            },
            "common_rules": [
                "文件路径必须是本机绝对路径",
                "output_path 可省略，自动生成到 MTools 输出目录",
                "AI 类功能需先在 MTools 桌面版下载对应模型",
                "返回值为 JSON 字符串，含 ok 字段",
            ],
            "tool_count": len(TOOL_ID_MAP),
        }

    if tool_id not in TOOL_ID_MAP:
        return {"error": f"未知 tool_id: {tool_id}", "hint": "调用 mtools_tool_ids 查看全部"}

    mcp_tool, action = TOOL_ID_MAP[tool_id]
    guide = TOOL_GUIDES.get(tool_id, _g(tool_id, ["input_path"], ["output_path"]))
    atomic = atomic_tool_name(tool_id)
    example = guide.get("example", {})
    return {
        "tool_id": tool_id,
        "atomic_tool": atomic,
        "mcp_tool": mcp_tool,
        "action": action,
        **guide,
        "call_example": {
            "via_atomic": {"tool": atomic, **example},
            "via_run": {
                "tool_id": tool_id,
                "params_json": json_dumps(example),
            },
        },
    }


def json_dumps(obj: dict) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)
