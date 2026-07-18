# -*- coding: utf-8 -*-
"""FFmpeg 通用操作（从 MTools 视图逻辑抽取）。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import ffmpeg

from utils import logger


def _ffmpeg_cmd(ffmpeg_service) -> str:
    path = ffmpeg_service.get_ffmpeg_path()
    if not path:
        raise RuntimeError("FFmpeg 不可用，请先在 MTools 中安装 FFmpeg")
    return path


def _ffprobe_cmd(ffmpeg_service) -> str:
    path = ffmpeg_service.get_ffprobe_path()
    if not path:
        raise RuntimeError("FFprobe 不可用")
    return path


def extract_audio_from_video(
    ffmpeg_service,
    input_path: Path,
    output_path: Path,
    output_format: str = "mp3",
    bitrate: int = 192,
    sample_rate: str = "original",
    channels: str = "original",
) -> Tuple[bool, str]:
    try:
        ffprobe_path = ffmpeg_service.get_ffprobe_path()
        if ffprobe_path:
            probe = ffmpeg.probe(str(input_path), cmd=ffprobe_path)
            if not any(s.get("codec_type") == "audio" for s in probe.get("streams", [])):
                return False, "视频不包含音频流"
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
            "flac": "flac",
            "ogg": "libvorbis",
            "opus": "libopus",
        }
        output_kwargs = {"vn": None}
        codec = codec_map.get(output_format)
        if codec:
            output_kwargs["acodec"] = codec
        if output_format not in ("wav", "flac"):
            output_kwargs["audio_bitrate"] = f"{bitrate}k"
        if sample_rate != "original":
            output_kwargs["ar"] = sample_rate
        if channels != "original":
            output_kwargs["ac"] = channels
        stream = ffmpeg.output(ffmpeg.input(str(input_path)), str(output_path), **output_kwargs)
        ffmpeg.run(
            stream,
            cmd=_ffmpeg_cmd(ffmpeg_service),
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True,
            quiet=True,
        )
        return True, "提取成功"
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        logger.error("提取音频失败: %s", err)
        return False, err
    except Exception as e:
        return False, str(e)


def compress_audio(
    ffmpeg_service,
    input_path: Path,
    output_path: Path,
    bitrate: int = 128,
    sample_rate: str = "original",
    channels: str = "original",
) -> Tuple[bool, str]:
    try:
        output_kwargs = {"audio_bitrate": f"{bitrate}k"}
        if sample_rate != "original":
            output_kwargs["ar"] = sample_rate
        if channels != "original":
            output_kwargs["ac"] = channels
        stream = ffmpeg.output(ffmpeg.input(str(input_path)), str(output_path), **output_kwargs)
        ffmpeg.run(
            stream,
            cmd=_ffmpeg_cmd(ffmpeg_service),
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True,
            quiet=True,
        )
        return True, "压缩成功"
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return False, err
    except Exception as e:
        return False, str(e)


def convert_video(
    ffmpeg_service,
    input_path: Path,
    output_path: Path,
    output_format: str = "mp4",
    vcodec: str = "copy",
    acodec: str = "copy",
) -> Tuple[bool, str]:
    try:
        ffprobe_path = _ffprobe_cmd(ffmpeg_service)
        probe = ffmpeg.probe(str(input_path), cmd=ffprobe_path)
        has_audio = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        output_params = {}
        if vcodec == "copy":
            output_params["vcodec"] = "copy"
        else:
            output_params["vcodec"] = vcodec
            if vcodec in ("libx264", "libx265"):
                output_params.update({"crf": 23, "preset": "medium", "pix_fmt": "yuv420p"})
        if has_audio:
            output_params["acodec"] = acodec if acodec != "copy" else "copy"
        else:
            output_params["an"] = None
        stream = ffmpeg.output(ffmpeg.input(str(input_path)), str(output_path), **output_params)
        ffmpeg.run(
            stream,
            cmd=_ffmpeg_cmd(ffmpeg_service),
            overwrite_output=True,
            capture_stdout=True,
            capture_stderr=True,
            quiet=True,
        )
        return True, f"已转换为 {output_format}"
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return False, err
    except Exception as e:
        return False, str(e)


_WATERMARK_POS = {
    "top_left": ("10", "10"),
    "top_right": ("w-tw-10", "10"),
    "bottom_left": ("10", "h-th-10"),
    "bottom_right": ("w-tw-10", "h-th-10"),
    "center": ("(w-tw)/2", "(h-th)/2"),
}


def add_video_text_watermark(
    ffmpeg_service,
    input_path: Path,
    output_path: Path,
    text: str,
    font_size: int = 24,
    position: str = "bottom_right",
    font_color: str = "white",
    opacity: float = 1.0,
) -> Tuple[bool, str]:
    try:
        x, y = _WATERMARK_POS.get(position, _WATERMARK_POS["bottom_right"])
        alpha = max(0.0, min(1.0, opacity))
        color = font_color
        if alpha < 1.0 and not font_color.startswith("0x"):
            # drawtext 用 fontcolor@alpha
            color = f"{font_color}@{alpha}"
        stream = ffmpeg.output(
            ffmpeg.input(str(input_path)).filter(
                "drawtext",
                text=text,
                fontsize=font_size,
                fontcolor=color,
                x=x,
                y=y,
            ),
            str(output_path),
            vcodec="libx264",
            acodec="copy",
        )
        ffmpeg.run(stream, cmd=_ffmpeg_cmd(ffmpeg_service), overwrite_output=True, quiet=True)
        return True, "水印添加成功"
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return False, err
    except Exception as e:
        return False, str(e)


def burn_subtitles(
    ffmpeg_service,
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
) -> Tuple[bool, str]:
    """将 SRT/ASS 字幕烧录进视频。"""
    try:
        ffmpeg_path = _ffmpeg_cmd(ffmpeg_service)
        sub = str(subtitle_path).replace("\\", "/").replace(":", "\\:")
        ext = subtitle_path.suffix.lower()
        if ext == ".ass":
            vf = f"ass='{sub}'"
        else:
            vf = f"subtitles='{sub}'"
        stream = ffmpeg.output(
            ffmpeg.input(str(video_path)),
            str(output_path),
            vf=vf,
            acodec="copy",
            vcodec="libx264",
            preset="medium",
            crf=23,
        )
        ffmpeg.run(stream, cmd=ffmpeg_path, overwrite_output=True, quiet=True)
        return True, "字幕烧录成功"
    except ffmpeg.Error as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        return False, err
    except Exception as e:
        return False, str(e)
