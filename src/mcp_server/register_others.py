# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from mcp_server import others_ops
from mcp_server.helpers import fail, ok, resolve_input, resolve_output
from mcp_server.media_ops import id_photo_process
from mcp_server.handlers import register_handler
from mcp_server.runtime import get_config_service, get_translate_service


def register_handlers_only() -> None:
    register_handler("mtools_others", _mtools_others_impl())


def register_ai_subtitle_only(mcp) -> None:
    mcp.tool()(_mtools_ai_subtitle_fix_impl())


def register(mcp) -> None:
    register_handlers_only()
    mcp.tool()(_mtools_others_impl())
    register_ai_subtitle_only(mcp)


def _mtools_others_impl():
    def mtools_others(
        action: Literal[
            "windows_update", "image_to_url", "file_to_url", "icp_query", "id_photo", "translate",
        ],
        input_path: str = "",
        output_path: str = "",
        text: str = "",
        target_lang: str = "zh-Hans",
        source_lang: str = "",
        expires_in: Literal["1d", "7d", "30d"] = "7d",
        storage_type: Literal["permanent", "temporary"] = "permanent",
        temp_hours: str = "24h",
        query_type: Literal["web", "app", "mapp", "kapp"] = "web",
        domain: str = "",
        windows_update_cmd: Literal["status", "disable", "restore"] = "status",
        photo_width: int = 413,
        photo_height: int = 295,
        bg_color: str = "#438EDB",
        base_url: str = "",
        api_key: str = "",
        ai_model: str = "",
        fix_language: str = "zh",
    ) -> str:
        """其他工具：图床/文件上传/ICP 查询/证件照/翻译/Windows 更新管理。"""
        try:
            cfg = get_config_service()
            if action == "translate":
                import asyncio
                svc = get_translate_service()
                result = asyncio.run(svc.translate(text, target_lang=target_lang, source_lang=source_lang))
                if result.get("code") != 200:
                    return fail(result.get("message", "翻译失败"))
                return ok({"translated": result.get("data", {}).get("text", ""), "source": text})
            if action == "image_to_url":
                ok2, data = others_ops.upload_image_to_url(resolve_input(input_path), expires_in)
                return ok(data) if ok2 else fail(str(data))
            if action == "file_to_url":
                ok2, data = others_ops.upload_file_to_url(resolve_input(input_path), storage_type, temp_hours)
                return ok(data) if ok2 else fail(str(data))
            if action == "windows_update":
                if windows_update_cmd == "status":
                    return ok(others_ops.windows_update_status())
                if windows_update_cmd == "disable":
                    ok2, msg = others_ops.windows_update_disable()
                    return ok({"message": msg}) if ok2 else fail(msg)
                ok2, msg = others_ops.windows_update_restore()
                return ok({"message": msg}) if ok2 else fail(msg)
            if action == "icp_query":
                import asyncio
                from services.icp_service import ICPService
                svc = ICPService(cfg)
                try:
                    result = asyncio.run(svc.query_icp(query_type, domain or text))
                    if not result:
                        return fail("查询失败")
                    return ok({"result": result, "formatted": svc.format_icp_result(result)})
                finally:
                    asyncio.run(svc.close())
            if action == "id_photo":
                src = resolve_input(input_path)
                out = resolve_output(src, output_path or None, suffix=".jpg")
                id_photo_process(cfg, src, out, photo_width, photo_height, bg_color)
                return ok({"output_path": str(out)})
            return fail(f"未知 action: {action}")
        except Exception as exc:
            return fail(str(exc))

    return mtools_others


def _mtools_ai_subtitle_fix_impl():
    async def mtools_ai_subtitle_fix(
        text: Annotated[str, Field(default="", description="待修复的纯文本（与 segments_json 二选一）")] = "",
        segments_json: Annotated[
            str,
            Field(default="", description='分段 JSON 数组，如 [{"text":"...","start":0,"end":1.2}]，保留时间轴'),
        ] = "",
        base_url: Annotated[str, Field(default="", description="OpenAI 兼容 API 地址，如 https://api.openai.com/v1")] = "",
        api_key: Annotated[str, Field(default="", description="API Key")] = "",
        model: Annotated[str, Field(default="", description="模型名称，如 gpt-4o-mini")] = "",
        language: Annotated[str, Field(default="zh", description="字幕语言，如 zh / en")] = "zh",
        output_path: Annotated[str, Field(default="", description="可选：写出修复后的 SRT 路径")] = "",
    ) -> str:
        """AI 字幕修复/润色。优先传 segments_json 以保留时间戳。"""
        try:
            import json
            from pathlib import Path
            from services.ai_subtitle_fix_service import AISubtitleFixService
            from utils.subtitle_utils import segments_to_srt

            ai = AISubtitleFixService(base_url, api_key, model)
            if not ai.is_configured():
                return fail("请提供 base_url、api_key、model")

            if segments_json.strip():
                segments = json.loads(segments_json)
                if not isinstance(segments, list):
                    return fail("segments_json 必须是数组")
                fixed_segs = ai.fix_segments(segments, language)
                srt = segments_to_srt(fixed_segs)
                result = {"segments": fixed_segs, "content": srt, "count": len(fixed_segs)}
                if output_path:
                    out = Path(output_path).expanduser().resolve()
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(srt, encoding="utf-8")
                    result["output_path"] = str(out)
                return ok(result)

            if not text.strip():
                return fail("请提供 text 或 segments_json")
            fixed = ai.fix_plain_text(text, language)
            return ok({"fixed": fixed})
        except Exception as exc:
            return fail(str(exc))

    return mtools_ai_subtitle_fix
