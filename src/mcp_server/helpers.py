# -*- coding: utf-8 -*-
"""MCP 工具共享辅助函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from mcp_server.runtime import get_output_dir

QUALITY_MAP = {
    "high": 90,
    "medium": 80,
    "low": 65,
}

COMPRESS_MODE_MAP = {
    "fast": "fast",
    "balanced": "balanced",
    "max": "max",
}


def ok(data: Any) -> str:
    payload = {"ok": True, **data} if isinstance(data, dict) else {"ok": True, "result": data}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def fail(message: str, **extra: Any) -> str:
    payload = {"ok": False, "error": message, **extra}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def resolve_input(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"输入文件不存在: {p}")
    return p


def resolve_output(
    input_path: Path,
    output_path: Optional[str] = None,
    *,
    suffix: Optional[str] = None,
) -> Path:
    if output_path:
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    ext = suffix or input_path.suffix
    stem = input_path.stem
    out_dir = get_output_dir()
    candidate = out_dir / f"{stem}_mtools{ext}"
    n = 1
    while candidate.exists():
        candidate = out_dir / f"{stem}_mtools_{n}{ext}"
        n += 1
    return candidate


def quality_value(level: str, default: int = 80) -> int:
    return QUALITY_MAP.get(level.lower(), default)


def compress_mode(mode: str) -> str:
    return COMPRESS_MODE_MAP.get(mode.lower(), "balanced")


def convert_subtitle_file(input_path: Path, output_path: Path, target_format: str) -> None:
    from utils.subtitle_utils import (
        parse_subtitle_file,
        segments_to_ass,
        segments_to_lrc,
        segments_to_srt,
        segments_to_txt,
        segments_to_vtt,
    )

    segments, _, metadata = parse_subtitle_file(str(input_path))
    fmt = target_format.lower()
    if fmt == "srt":
        text = segments_to_srt(segments)
    elif fmt == "vtt":
        text = segments_to_vtt(segments)
    elif fmt == "lrc":
        text = segments_to_lrc(segments, metadata.get("title", ""), metadata.get("artist", ""))
    elif fmt == "ass":
        text = segments_to_ass(segments)
    elif fmt == "txt":
        text = segments_to_txt(segments)
    else:
        raise ValueError(f"不支持的字幕格式: {target_format}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
