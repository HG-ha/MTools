# -*- coding: utf-8 -*-
"""音视频 AI / 复杂媒体 MCP 实现。"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np


def load_asr_model(svc, cfg, model_key: str = "", language: str = "zh") -> str:
    """按 model_key 加载 SenseVoice/Whisper，返回实际使用的引擎名。"""
    from constants import (
        DEFAULT_SENSEVOICE_MODEL_KEY,
        DEFAULT_WHISPER_MODEL_KEY,
        SENSEVOICE_MODELS,
        WHISPER_MODELS,
    )

    key = (model_key or "").strip()
    if not key or key == "sensevoice":
        key = cfg.get_config_value("sensevoice_model_key", DEFAULT_SENSEVOICE_MODEL_KEY)
    if key not in SENSEVOICE_MODELS and key not in WHISPER_MODELS:
        if key in ("whisper",):
            key = cfg.get_config_value("whisper_model_key", DEFAULT_WHISPER_MODEL_KEY)
        else:
            key = cfg.get_config_value("sensevoice_model_key", DEFAULT_SENSEVOICE_MODEL_KEY)

    lang = language if language and language != "auto" else "auto"

    if key in SENSEVOICE_MODELS:
        info = SENSEVOICE_MODELS[key]
        model_dir = svc.get_model_dir(key)
        model_path = model_dir / info.model_filename
        tokens_path = model_dir / info.tokens_filename
        if not model_path.exists() or not tokens_path.exists():
            raise FileNotFoundError(f"语音识别模型未下载: {key}（请在 MTools GUI 下载）")
        svc.load_sensevoice_model(
            model_path=model_path,
            tokens_path=tokens_path,
            language=lang,
            model_type=info.model_type,
        )
        return info.model_type

    info = WHISPER_MODELS[key]
    model_dir = svc.get_model_dir(key)
    encoder = model_dir / info.encoder_filename
    decoder = model_dir / info.decoder_filename
    config = model_dir / info.config_filename
    if not encoder.exists():
        raise FileNotFoundError(f"Whisper 模型未下载: {key}")
    svc.load_model(encoder, decoder, config, language=lang)
    return "whisper"


def remux_audio_from_source(ff, silent_video: Path, source_with_audio: Path, output_path: Path) -> None:
    """把源视频音轨合并到无声视频上。"""
    import ffmpeg

    ffmpeg_path = ff.get_ffmpeg_path()
    if not ffmpeg_path:
        silent_video.replace(output_path) if silent_video != output_path else None
        return
    probe_path = ff.get_ffprobe_path()
    has_audio = False
    if probe_path:
        try:
            probe = ffmpeg.probe(str(source_with_audio), cmd=probe_path)
            has_audio = any(s.get("codec_type") == "audio" for s in probe.get("streams", []))
        except Exception:
            has_audio = False
    if not has_audio:
        if silent_video != output_path:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            silent_video.replace(output_path)
        return

    temp_out = output_path.with_suffix(".remux_tmp.mp4")
    try:
        video_stream = ffmpeg.input(str(silent_video))
        audio_stream = ffmpeg.input(str(source_with_audio)).audio
        (
            ffmpeg.output(
                video_stream.video,
                audio_stream,
                str(temp_out),
                vcodec="copy",
                acodec="aac",
                shortest=None,
            )
            .overwrite_output()
            .run(cmd=ffmpeg_path, capture_stdout=True, capture_stderr=True, quiet=True)
        )
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        temp_out.replace(output_path)
    except Exception:
        if silent_video != output_path and silent_video.exists():
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            try:
                silent_video.replace(output_path)
            except Exception:
                pass
        raise
    finally:
        if silent_video.exists() and silent_video != output_path:
            silent_video.unlink(missing_ok=True)
        if temp_out.exists() and temp_out != output_path:
            temp_out.unlink(missing_ok=True)


def vocal_separate_audio(
    cfg,
    ff,
    input_path: Path,
    output_dir: Path,
    model_key: str = "kim_vocal_2",
    output: str = "vocals",
) -> Tuple[Path, Path]:
    from constants import VOCAL_SEPARATION_MODELS
    from services.vocal_separation_service import VocalSeparationService

    if model_key not in VOCAL_SEPARATION_MODELS:
        raise ValueError(f"未知模型: {model_key}")
    model = VOCAL_SEPARATION_MODELS[model_key]
    model_dir = cfg.get_data_dir() / "models" / "vocal_separation"
    model_path = model_dir / model.filename
    if not model_path.exists():
        raise FileNotFoundError(f"模型未下载: {model_path}")
    svc = VocalSeparationService(model_dir, ff, cfg)
    svc.load_model(model_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    vocals, inst = svc.separate(input_path, output_dir)
    svc.unload_model()
    return vocals, inst


def vocal_separate_video(
    cfg,
    ff,
    input_path: Path,
    output_path: Path,
    model_key: str = "kim_vocal_2",
    keep: str = "vocals",
) -> Path:
    from mcp_server.ffmpeg_ops import extract_audio_from_video

    with tempfile.TemporaryDirectory() as td:
        audio = Path(td) / "audio.wav"
        ok, msg = extract_audio_from_video(ff, input_path, audio, "wav")
        if not ok:
            raise RuntimeError(msg)
        vocals, inst = vocal_separate_audio(cfg, ff, audio, Path(td), model_key)
        chosen = vocals if keep == "vocals" else inst
        import ffmpeg
        ffmpeg_path = ff.get_ffmpeg_path()
        stream = ffmpeg.output(
            ffmpeg.input(str(input_path)).video,
            ffmpeg.input(str(chosen)).audio,
            str(output_path),
            vcodec="copy",
            acodec="aac",
            shortest=None,
        )
        ffmpeg.run(stream, cmd=ffmpeg_path, overwrite_output=True, quiet=True)
    return output_path


def _build_region_mask(
    h: int,
    w: int,
    region: str = "bottom",
    region_height_ratio: float = 0.15,
    left: int = 0,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
) -> np.ndarray:
    mask = np.zeros((h, w), np.uint8)
    if right > left and bottom > top:
        l = max(0, min(left, w - 1))
        t = max(0, min(top, h - 1))
        r = max(l + 1, min(right, w))
        b = max(t + 1, min(bottom, h))
        mask[t:b, l:r] = 255
        return mask
    rh = max(1, int(h * region_height_ratio))
    if region == "top":
        mask[0:rh, :] = 255
    else:
        mask[h - rh : h, :] = 255
    return mask


def subtitle_remove_video(
    cfg,
    input_path: Path,
    output_path: Path,
    model_key: str = "sttn_v1",
    region: str = "bottom",
    region_height_ratio: float = 0.15,
    left: int = 0,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
) -> bool:
    from constants import SUBTITLE_REMOVE_MODELS
    from services.subtitle_remove_service import SubtitleRemoveService

    if model_key not in SUBTITLE_REMOVE_MODELS:
        raise ValueError(f"未知模型: {model_key}")
    info = SUBTITLE_REMOVE_MODELS[model_key]
    data_dir = cfg.get_data_dir() / "models" / "subtitle_remove"
    encoder = data_dir / info.encoder_filename
    infer = data_dir / info.infer_filename
    decoder = data_dir / info.decoder_filename
    if not all(p.exists() for p in (encoder, infer, decoder)):
        raise FileNotFoundError("字幕移除模型未下载")
    svc = SubtitleRemoveService()
    svc.load_model(str(encoder), str(infer), str(decoder), info.neighbor_stride, info.ref_length)
    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()

    def mask_fn(h: int, w: int, _t: float) -> np.ndarray:
        return _build_region_mask(h, w, region, region_height_ratio, left, top, right, bottom)

    ok = svc.process_video_streaming(str(input_path), str(output_path), mask_fn, fps)
    svc.unload_model()
    return ok


async def generate_subtitle_srt(
    cfg,
    ff,
    input_path: Path,
    output_path: Path,
    language: str = "zh",
    model_key: str = "",
    target_lang: str = "",
    bilingual: bool = False,
    burn_in: bool = False,
    burn_output: Optional[Path] = None,
) -> dict[str, Any]:
    from services.speech_recognition_service import SpeechRecognitionService
    from utils.subtitle_utils import segments_to_ass, segments_to_srt

    svc = SpeechRecognitionService(cfg, ff)
    load_asr_model(svc, cfg, model_key, language)
    segments = svc.recognize_with_timestamps(input_path, language=language)
    svc.unload_model()
    if not segments:
        raise RuntimeError("未识别到语音内容")

    translated: List[str] = []
    if target_lang:
        from mcp_server.runtime import get_translate_service
        translate_svc = get_translate_service()
        texts = [s.get("text", "") for s in segments]
        translated = await translate_svc.translate_batch(texts, target_lang=target_lang)
        if bilingual:
            for i, seg in enumerate(segments):
                tr = translated[i] if i < len(translated) else ""
                src = seg.get("text", "")
                seg["text"] = f"{src}\n{tr}" if tr else src
        else:
            for i, seg in enumerate(segments):
                if i < len(translated) and translated[i]:
                    seg["text"] = translated[i]

    srt = segments_to_srt(segments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt, encoding="utf-8")

    result: dict[str, Any] = {
        "output_path": str(output_path),
        "content": srt,
        "segments": segments,
        "count": len(segments),
    }

    if burn_in:
        from mcp_server.ffmpeg_ops import burn_subtitles

        ass_path = output_path.with_suffix(".ass")
        ass_path.write_text(segments_to_ass(segments), encoding="utf-8")
        burned = burn_output or output_path.with_name(f"{input_path.stem}_subtitled.mp4")
        ok, msg = burn_subtitles(ff, input_path, ass_path, burned)
        if not ok:
            raise RuntimeError(f"烧录字幕失败: {msg}")
        result["burned_video"] = str(burned)
        result["ass_path"] = str(ass_path)

    return result


def video_interpolate(
    cfg,
    ff,
    input_path: Path,
    output_path: Path,
    multiplier: float = 2.0,
    model_key: str = "rife49_standard",
) -> None:
    from constants import FRAME_INTERPOLATION_MODELS
    from services.frame_interpolation_service import FrameInterpolationService

    if model_key not in FRAME_INTERPOLATION_MODELS:
        raise ValueError(f"未知插帧模型: {model_key}")
    info = FRAME_INTERPOLATION_MODELS[model_key]
    model_path = cfg.get_data_dir() / "models" / "rife" / info.filename
    if not model_path.exists():
        raise FileNotFoundError(f"插帧模型未下载: {model_path}")
    svc = FrameInterpolationService(model_name=model_key, config_service=cfg)
    svc.load_model(model_path)
    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ret, prev = cap.read()
    if not ret:
        cap.release()
        svc.unload_model()
        raise RuntimeError("无法读取视频")

    silent = output_path.with_suffix(".silent_tmp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_fps = fps * multiplier
    writer = cv2.VideoWriter(str(silent), fourcc, out_fps, (w, h))
    writer.write(prev)
    n_insert = max(1, int(multiplier) - 1)
    while True:
        ret, nxt = cap.read()
        if not ret:
            break
        for i in range(n_insert):
            t = (i + 1) / (n_insert + 1)
            mid = svc.interpolate(prev, nxt, timestep=t)
            writer.write(mid)
        writer.write(nxt)
        prev = nxt
    cap.release()
    writer.release()
    svc.unload_model()
    remux_audio_from_source(ff, silent, input_path, output_path)


def video_enhance(
    cfg,
    ff,
    input_path: Path,
    output_path: Path,
    model_key: str = "realesrgan_x4plus",
    max_frames: int = 0,
    scale: int = 0,
) -> None:
    from constants.model_config import IMAGE_ENHANCE_MODELS
    from services.image_service import ImageEnhancer
    from PIL import Image

    if model_key not in IMAGE_ENHANCE_MODELS:
        raise ValueError(f"未知增强模型: {model_key}")
    model = IMAGE_ENHANCE_MODELS[model_key]
    model_path = cfg.get_data_dir() / "models" / "image_enhance" / model.version / model.filename
    if not model_path.exists():
        raise FileNotFoundError(f"增强模型未下载: {model_path}")
    enhancer = ImageEnhancer(model_path, cfg)
    out_scale = scale if scale > 0 else int(getattr(model, "scale", 4) or 4)

    cap = cv2.VideoCapture(str(input_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    silent = output_path.with_suffix(".silent_tmp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(silent), fourcc, fps, (w * out_scale, h * out_scale))
    count = 0
    limit = max_frames if max_frames and max_frames > 0 else 10**9
    while count < limit:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        enhanced = enhancer.enhance_image(Image.fromarray(rgb))
        out = cv2.cvtColor(np.array(enhanced.convert("RGB")), cv2.COLOR_RGB2BGR)
        if out.shape[1] != w * out_scale or out.shape[0] != h * out_scale:
            out = cv2.resize(out, (w * out_scale, h * out_scale), interpolation=cv2.INTER_CUBIC)
        writer.write(out)
        count += 1
    cap.release()
    writer.release()
    enhancer.unload_model()
    if count == 0:
        silent.unlink(missing_ok=True)
        raise RuntimeError("未处理到任何视频帧")
    remux_audio_from_source(ff, silent, input_path, output_path)


def image_search_similar(cfg, image_path: Path, page_size: int = 20) -> dict:
    from services.sogou_search_service import SogouSearchService

    async def _run():
        svc = SogouSearchService()
        upload = await svc.upload_image(str(image_path))
        if not svc.is_upload_success(upload):
            raise RuntimeError("图片上传失败")
        url = upload.get("data", {}).get("url") or upload.get("url")
        return await svc.search_similar_images(url, page_size=page_size)

    return asyncio.run(_run())


def id_photo_process(
    cfg,
    input_path: Path,
    output_path: Path,
    width: int = 413,
    height: int = 295,
    bg_color: str = "#438EDB",
) -> None:
    from services.id_photo_service import IDPhotoParams, IDPhotoService

    svc = IDPhotoService(cfg)
    svc.load_background_model()
    svc.load_face_model()
    bgr = cv2.imdecode(np.fromfile(str(input_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    r, g, b = int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16)
    result = svc.process(bgr, IDPhotoParams(size=(width, height)), bg_color=(r, g, b))
    cv2.imencode(".jpg", result.standard)[1].tofile(str(output_path))
    svc.unload_all_models()


def watermark_remove_ai(
    cfg,
    input_path: Path,
    output_path: Path,
    model_key: str = "sttn_v1",
    left: int = 0,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
) -> None:
    import tempfile

    tmp = Path(tempfile.mkdtemp()) / "out.mp4"
    try:
        if input_path.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            subtitle_remove_video(
                cfg, input_path, tmp, model_key=model_key,
                left=left, top=top, right=right, bottom=bottom,
            )
            tmp.replace(output_path)
        else:
            from constants import SUBTITLE_REMOVE_MODELS
            from services.subtitle_remove_service import SubtitleRemoveService

            info = SUBTITLE_REMOVE_MODELS.get(model_key) or list(SUBTITLE_REMOVE_MODELS.values())[0]
            data_dir = cfg.get_data_dir() / "models" / "subtitle_remove"
            svc = SubtitleRemoveService()
            svc.load_model(
                str(data_dir / info.encoder_filename),
                str(data_dir / info.infer_filename),
                str(data_dir / info.decoder_filename),
            )
            img = cv2.imdecode(np.fromfile(str(input_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            h, w = img.shape[:2]
            mask = _build_region_mask(h, w, "bottom", 0.15, left, top, right, bottom)
            mask3 = np.stack([mask] * 3, axis=-1)
            _ = svc.get_inpaint_area_by_mask(h, h, mask3)
            frames = [img]
            out_frames = svc.inpaint(frames)
            cv2.imencode(output_path.suffix or ".png", out_frames[0])[1].tofile(str(output_path))
            svc.unload_model()
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def merge_ts_files(ff, input_paths: List[Path], output_path: Path) -> Tuple[bool, str]:
    import os
    import subprocess
    import tempfile

    ffmpeg_path = ff.get_ffmpeg_path()
    if not ffmpeg_path:
        return False, "FFmpeg 不可用"
    if not input_paths:
        return False, "需要至少一个 TS/视频分片"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for p in input_paths:
            escaped = str(p.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        list_path = f.name
    try:
        cmd = [
            ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return False, proc.stderr[-500:] if proc.stderr else "TS 合并失败"
        return True, "合并成功"
    finally:
        try:
            os.unlink(list_path)
        except Exception:
            pass


async def translate_subtitle_segments(
    segments: List[dict],
    target_lang: str,
    bilingual: bool = False,
) -> List[dict]:
    from mcp_server.runtime import get_translate_service

    svc = get_translate_service()
    texts = [s.get("text", "") for s in segments]
    translated = await svc.translate_batch(texts, target_lang=target_lang)
    out = []
    for i, seg in enumerate(segments):
        item = dict(seg)
        tr = translated[i] if i < len(translated) else ""
        if bilingual:
            src = seg.get("text", "")
            item["text"] = f"{src}\n{tr}" if tr else src
        elif tr:
            item["text"] = tr
        out.append(item)
    return out
