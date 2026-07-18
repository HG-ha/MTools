# -*- coding: utf-8 -*-
"""MTools 全部 MCP 能力清单（对应 tool_registry 全部注册工具）。"""

from __future__ import annotations

CAPABILITIES = {
    "mtools_image": {
        "description": "图片处理（20 项）",
        "actions": {
            "compress": "image.compress — 图片压缩",
            "format": "image.format — 格式转换",
            "resize": "image.resize — 尺寸调整",
            "crop": "image.crop — 裁剪",
            "rotate": "image.rotate — 旋转/翻转",
            "background": "image.background — AI 抠图",
            "watermark": "image.watermark — 添加文字水印",
            "watermark_remove": "image.watermark_remove — 去水印/修复",
            "info": "image.info — 图片信息",
            "exif": "image.exif — 去除 EXIF",
            "qrcode": "image.qrcode — 生成二维码",
            "to_base64": "image.to_base64 — 转 Base64",
            "gif": "image.gif — GIF 调整",
            "enhance": "image.enhance — AI 图像增强",
            "puzzle_merge": "image.puzzle.merge — 拼图合并",
            "puzzle_split": "image.puzzle.split — 拼图切分",
            "search": "image.search — 以图搜图",
            "ocr": "image.ocr — OCR 识别",
            "color_space": "image.color_space — 色彩空间转换",
            "border": "image.border — 添加边框",
        },
    },
    "mtools_audio": {
        "description": "音频处理（6 项）",
        "actions": {
            "format": "audio.format — 格式转换",
            "compress": "audio.compress — 音频压缩",
            "speed": "audio.speed — 倍速",
            "vocal_extraction": "audio.vocal_extraction — 人声分离",
            "to_text": "audio.to_text — 语音转文字",
            "text_to_speech": "audio.text_to_speech — 文字转语音",
        },
    },
    "mtools_video": {
        "description": "视频处理（13 项）",
        "actions": {
            "compress": "video.compress — 视频压缩",
            "convert": "video.convert — 格式转换",
            "extract_audio": "video.extract_audio — 提取音频",
            "speed": "video.speed — 倍速",
            "vocal_separation": "video.vocal_separation — 人声分离",
            "watermark": "video.watermark — 文字水印",
            "repair": "video.repair — 视频修复",
            "enhance": "video.enhance — AI 视频增强",
            "interpolation": "video.interpolation — AI 插帧",
            "subtitle_remove": "video.subtitle_remove — 去字幕",
            "subtitle": "video.subtitle — AI 生成字幕（可翻译/烧录）",
            "ts_merge": "video.ts_merge — TS 分片合并",
            "screen_record": "video.screen_record — 录屏（仅 GUI）",
        },
    },
    "mtools_dev": {
        "description": "开发工具（17 项，不含 Markdown 查看器）",
        "actions": {
            "base64_to_image": "dev.base64_to_image",
            "encoding_detect": "dev.encoding — 检测编码",
            "encoding_convert": "dev.encoding — 转换编码",
            "json_format": "dev.json_viewer — 格式化 JSON",
            "json_minify": "dev.json_viewer — 压缩 JSON",
            "http_request": "dev.http_client",
            "encoder_decoder": "dev.encoder_decoder",
            "regex_test": "dev.regex_tester",
            "timestamp_convert": "dev.timestamp_tool",
            "jwt_parse": "dev.jwt_tool",
            "uuid_generate": "dev.uuid_generator",
            "color_convert": "dev.color_tool",
            "dns_lookup": "dev.dns_lookup",
            "port_scan": "dev.port_scanner",
            "format_convert": "dev.format_convert",
            "text_diff": "dev.text_diff",
            "crypto": "dev.crypto_tool",
            "sql_format": "dev.sql_formatter",
            "cron_parse": "dev.cron_tool",
        },
    },
    "mtools_websocket": {
        "description": "WebSocket 客户端（dev.websocket_client）— 会话生命周期",
        "actions": {
            "connect": "建立连接，返回 session_id",
            "send": "发送消息",
            "receive": "拉取收到的消息（后台持续监听）",
            "status": "查看会话状态",
            "disconnect": "断开并销毁会话",
            "list_sessions": "列出所有活跃会话",
            "disconnect_all": "断开全部会话",
        },
    },
    "mtools_others": {
        "description": "其他工具（6 项）",
        "actions": {
            "windows_update": "others.windows_update",
            "image_to_url": "others.image_to_url",
            "file_to_url": "others.file_to_url",
            "icp_query": "others.icp_query",
            "id_photo": "others.id_photo",
            "translate": "others.translate",
        },
    },
}


def all_tool_count() -> int:
    from mcp_server.tool_ids import TOOL_ID_MAP
    return len(TOOL_ID_MAP)
