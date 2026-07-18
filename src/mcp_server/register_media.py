# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from mcp_server import ffmpeg_ops
from mcp_server.helpers import convert_subtitle_file, fail, ok, quality_value, resolve_input, resolve_output
from mcp_server.media_ops import (
    generate_subtitle_srt,
    load_asr_model,
    merge_ts_files,
    subtitle_remove_video,
    video_enhance,
    video_interpolate,
    vocal_separate_audio,
    vocal_separate_video,
)
from mcp_server.handlers import register_handler
from mcp_server.runtime import get_config_service, get_ffmpeg_service, get_output_dir


def register_handlers_only() -> None:
    register_handler("mtools_audio", _mtools_audio_impl())
    register_handler("mtools_video", _mtools_video_impl())
    register_handler("mtools_subtitle_convert", _mtools_subtitle_convert_impl())


def register_subtitle_only(mcp) -> None:
    """仅注册字幕转换 MCP 工具（handler 需已由 register_handlers_only 注册）。"""
    fn = _mtools_subtitle_convert_impl()
    register_handler("mtools_subtitle_convert", fn)
    mcp.tool()(fn)


def register(mcp) -> None:
    register_handlers_only()
    mcp.tool()(_mtools_audio_impl())
    mcp.tool()(_mtools_video_impl())
    mcp.tool()(_mtools_subtitle_convert_impl())


def _mtools_audio_impl():
    def mtools_audio(
        action: Literal["format", "compress", "speed", "vocal_extraction", "to_text", "text_to_speech"],
        input_path: str = "",
        output_path: str = "",
        text: str = "",
        speed: float = 1.0,
        quality: Literal["high", "medium", "low"] = "medium",
        target_format: str = "mp3",
        bitrate: int = 128,
        sample_rate: str = "original",
        channels: str = "original",
        language: str = "zh",
        model_key: str = "",
        vocal_output: Literal["vocals", "instrumental", "both"] = "both",
    ) -> str:
        """音频处理：格式转换/压缩/倍速/人声分离/语音转文字/文字转语音。"""
        try:
            cfg = get_config_service()
            ff = get_ffmpeg_service()
            if action == "text_to_speech":
                if not text.strip():
                    return fail("需要 text")
                from services.tts_service import TTSService
                tts = TTSService(cfg)
                key = model_key or cfg.get_config_value("tts_model_key", "vits-zh-hf-fanchen")
                if not tts.load_model(key):
                    return fail("TTS 模型未下载")
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "tts.wav"
                out.parent.mkdir(parents=True, exist_ok=True)
                ok2, msg = tts.synthesize_to_file(text, out)
                tts.unload_model()
                return ok({"output_path": str(out), "message": msg}) if ok2 else fail(msg)
            src = resolve_input(input_path)
            if action == "format":
                from services.audio_service import AudioService
                out = resolve_output(src, output_path or None, suffix=f".{target_format}")
                sr = None if sample_rate in ("", "original") else int(sample_rate)
                ch = None if channels in ("", "original") else int(channels)
                br = f"{bitrate}k" if bitrate else None
                success, message = AudioService(ff).convert_audio(
                    src, out, output_format=target_format, bitrate=br, sample_rate=sr, channels=ch,
                )
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "compress":
                out = resolve_output(src, output_path or None, suffix=".mp3")
                q = quality_value(quality)
                br = 192 if q >= 90 else 128 if q >= 80 else 96
                success, message = ffmpeg_ops.compress_audio(ff, src, out, br, sample_rate, channels)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "speed":
                out = resolve_output(src, output_path or None)
                success, message = ff.adjust_audio_speed(src, out, speed)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "vocal_extraction":
                out_dir = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "vocal_sep"
                vocals, inst = vocal_separate_audio(cfg, ff, src, out_dir, model_key or "kim_vocal_2")
                data = {"vocals": str(vocals), "instrumental": str(inst)}
                if vocal_output == "vocals":
                    return ok({"output_path": str(vocals)})
                if vocal_output == "instrumental":
                    return ok({"output_path": str(inst)})
                return ok(data)
            if action == "to_text":
                from services.speech_recognition_service import SpeechRecognitionService
                svc = SpeechRecognitionService(cfg, ff)
                engine = load_asr_model(svc, cfg, model_key, language)
                result = svc.recognize(src, language=language)
                svc.unload_model()
                return ok({"text": result, "engine": engine})
            return fail(f"未知 action: {action}")
        except Exception as exc:
            return fail(str(exc))

    return mtools_audio


def _mtools_video_impl():
    def mtools_video(
        action: Literal[
            "compress", "convert", "extract_audio", "speed", "vocal_separation", "watermark",
            "repair", "enhance", "interpolation", "subtitle_remove", "subtitle", "screen_record",
            "ts_merge",
        ],
        input_path: str = "",
        output_path: str = "",
        input_paths: str = "",
        speed: float = 1.0,
        quality: Literal["high", "medium", "low"] = "medium",
        target_format: str = "mp4",
        vcodec: str = "copy",
        acodec: str = "copy",
        watermark_text: str = "",
        watermark_position: str = "bottom_right",
        font_size: int = 24,
        watermark_opacity: int = 128,
        language: str = "zh",
        model_key: str = "",
        bitrate: int = 192,
        multiplier: float = 2.0,
        subtitle_region: str = "bottom",
        vocal_keep: Literal["vocals", "instrumental"] = "vocals",
        max_enhance_frames: int = 0,
        enhance_scale: int = 0,
        crf: int = 0,
        scale: str = "original",
        fps: float = 0.0,
        preset: str = "medium",
        left: int = 0,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        target_lang: str = "",
        bilingual: bool = False,
        burn_in: bool = False,
    ) -> str:
        """视频处理：压缩/转格式/提取音频/倍速/人声分离/水印/修复/增强/插帧/去字幕/生成字幕/TS合并。"""
        try:
            if action == "screen_record":
                return fail("录屏请使用 MTools 桌面版全局热键或录屏界面")
            cfg = get_config_service()
            ff = get_ffmpeg_service()

            if action == "ts_merge":
                paths = [resolve_input(p.strip()) for p in input_paths.split(",") if p.strip()]
                if not paths and input_path:
                    paths = [resolve_input(input_path)]
                if not paths:
                    return fail("ts_merge 需要 input_paths（逗号分隔）")
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "ts_merged.mp4"
                out.parent.mkdir(parents=True, exist_ok=True)
                success, message = merge_ts_files(ff, paths, out)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)

            src = resolve_input(input_path)
            if action == "compress":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                q = quality_value(quality)
                use_crf = crf if crf > 0 else {90: 18, 80: 23, 65: 28}.get(q, 23)
                params = {
                    "mode": "simple",
                    "crf": use_crf,
                    "scale": scale or "original",
                    "fps_mode": "original" if fps <= 0 else "custom",
                    "fps": fps if fps > 0 else None,
                    "preset": preset or "medium",
                }
                success, message = ff.compress_video(src, out, params)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "convert":
                out = resolve_output(src, output_path or None, suffix=f".{target_format}")
                success, message = ffmpeg_ops.convert_video(ff, src, out, target_format, vcodec, acodec)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "extract_audio":
                out = resolve_output(src, output_path or None, suffix=f".{target_format}")
                success, message = ffmpeg_ops.extract_audio_from_video(ff, src, out, target_format, bitrate)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "speed":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                success, message = ff.adjust_video_speed(src, out, speed)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "repair":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                success, message = ff.repair_video(src, out)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "watermark":
                if not watermark_text.strip():
                    return fail("需要 watermark_text")
                out = resolve_output(src, output_path or None, suffix=".mp4")
                opacity = watermark_opacity / 255.0 if watermark_opacity > 1 else float(watermark_opacity)
                success, message = ffmpeg_ops.add_video_text_watermark(
                    ff, src, out, watermark_text,
                    font_size=font_size,
                    position=watermark_position,
                    opacity=opacity,
                )
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "vocal_separation":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                path = vocal_separate_video(cfg, ff, src, out, model_key or "kim_vocal_2", vocal_keep)
                return ok({"output_path": str(path)})
            if action == "subtitle_remove":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                ok2 = subtitle_remove_video(
                    cfg, src, out, model_key or "sttn_v1", subtitle_region,
                    left=left, top=top, right=right, bottom=bottom,
                )
                return ok({"output_path": str(out)}) if ok2 else fail("去字幕失败")
            if action == "interpolation":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                video_interpolate(cfg, ff, src, out, multiplier, model_key or "rife49_standard")
                return ok({"output_path": str(out)})
            if action == "enhance":
                out = resolve_output(src, output_path or None, suffix=".mp4")
                video_enhance(
                    cfg, ff, src, out,
                    model_key or "realesrgan_x4plus",
                    max_enhance_frames,
                    enhance_scale,
                )
                return ok({"output_path": str(out)})
            if action == "subtitle":
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / f"{src.stem}.srt"
                import asyncio
                result = asyncio.run(generate_subtitle_srt(
                    cfg, ff, src, out, language, model_key,
                    target_lang=target_lang,
                    bilingual=bilingual,
                    burn_in=burn_in,
                ))
                return ok(result)
            return fail(f"未知 action: {action}")
        except Exception as exc:
            return fail(str(exc))

    return mtools_video


def _mtools_subtitle_convert_impl():
    def mtools_subtitle_convert(
        input_path: Annotated[str, Field(default="", description="字幕文件绝对路径（与 subtitle_text 二选一）")] = "",
        subtitle_text: Annotated[str, Field(default="", description="SRT 格式字幕文本（与 input_path 二选一）")] = "",
        output_path: Annotated[str, Field(default="", description="输出路径；留空则自动生成到 MTools 输出目录")] = "",
        target_format: Annotated[
            Literal["srt", "vtt", "lrc", "ass", "txt"],
            Field(default="srt", description="目标字幕格式：srt / vtt / lrc / ass / txt"),
        ] = "srt",
    ) -> str:
        """字幕格式互转（文件或文本 → srt/vtt/lrc/ass/txt）。"""
        try:
            ext = f".{target_format}"
            if input_path:
                src = resolve_input(input_path)
                out = resolve_output(src, output_path or None, suffix=ext)
                convert_subtitle_file(src, out, target_format)
                return ok({"output_path": str(out)})
            if subtitle_text.strip():
                from utils.subtitle_utils import parse_srt, segments_to_ass, segments_to_lrc, segments_to_srt, segments_to_txt, segments_to_vtt
                segments = parse_srt(subtitle_text)
                converters = {"srt": segments_to_srt, "vtt": segments_to_vtt, "lrc": lambda s: segments_to_lrc(s), "ass": segments_to_ass, "txt": segments_to_txt}
                text = converters[target_format](segments)
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / f"subtitle.{target_format}"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                return ok({"output_path": str(out), "content": text})
            return fail("请提供 input_path 或 subtitle_text")
        except Exception as exc:
            return fail(str(exc))

    return mtools_subtitle_convert
