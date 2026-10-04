# -*- coding: utf-8 -*-
"""Depth Anything V2 ONNX 深度估计。"""

from __future__ import annotations

import gc
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from utils import logger

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def round_to_14(value: float) -> int:
    return max(14, int(round(value / 14.0)) * 14)


def infer_hw(orig_h: int, orig_w: int, input_size: int = 518, static_hw=None):
    if static_hw is not None:
        return static_hw
    scale = float(input_size) / float(min(orig_h, orig_w))
    return round_to_14(orig_h * scale), round_to_14(orig_w * scale)


def _static_input_hw(shape) -> Optional[tuple[int, int]]:
    if len(shape) < 2:
        return None
    height, width = shape[-2], shape[-1]
    if isinstance(height, int) and isinstance(width, int) and height > 0 and width > 0:
        return height, width
    return None


def preprocess_bgr(bgr: np.ndarray, height: int, width: int) -> np.ndarray:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    image = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_CUBIC)
    image = (image - IMAGENET_MEAN) / IMAGENET_STD
    return np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32)


def colorize_depth(depth: np.ndarray, grayscale: bool = True) -> np.ndarray:
    data = np.asarray(depth, dtype=np.float32)
    lo = float(np.nanmin(data))
    hi = float(np.nanmax(data))
    if hi <= lo:
        norm = np.zeros_like(data, dtype=np.float32)
    else:
        norm = np.clip((data - lo) / (hi - lo), 0.0, 1.0)
    gray = (norm * 255.0).astype(np.uint8)
    if grayscale:
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return cv2.applyColorMap(gray, cv2.COLORMAP_MAGMA)


def imread_unicode(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片: {path}")
    return image


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_animated_image(path: Path) -> bool:
    """GIF、动态 WebP、APNG 等多帧图片。"""
    suffix = path.suffix.lower()
    if suffix not in {".gif", ".webp", ".png", ".apng"}:
        return False
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(getattr(image, "n_frames", 1) or 1) > 1
    except Exception:
        return False


def _remux_audio(config_service, silent_video: Path, source: Path, output_path: Path) -> None:
    """把源视频音轨合并到无声深度视频。没有 FFmpeg 或音轨时保留无声视频。"""
    import ffmpeg

    from services.ffmpeg_service import FFmpegService

    ffmpeg_service = FFmpegService(config_service) if config_service is not None else None
    ffmpeg_path = ffmpeg_service.get_ffmpeg_path() if ffmpeg_service else None
    if not ffmpeg_path:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        silent_video.replace(output_path)
        return

    has_audio = False
    probe_path = ffmpeg_service.get_ffprobe_path()
    if probe_path:
        try:
            probe = ffmpeg.probe(str(source), cmd=probe_path)
            has_audio = any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))
        except Exception:
            has_audio = False
    if not has_audio:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        silent_video.replace(output_path)
        return

    temp_out = output_path.with_name(output_path.stem + ".remux_tmp.mp4")
    try:
        (
            ffmpeg.output(
                ffmpeg.input(str(silent_video)).video,
                ffmpeg.input(str(source)).audio,
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
        logger.warning("深度视频合并音轨失败，保留无声视频")
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        if silent_video.exists():
            silent_video.replace(output_path)
    finally:
        if silent_video.exists() and silent_video != output_path:
            silent_video.unlink(missing_ok=True)
        if temp_out.exists() and temp_out != output_path:
            temp_out.unlink(missing_ok=True)


def imwrite_unicode(path: Path, bgr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix or ".png"
    ok, buf = cv2.imencode(ext, bgr)
    if not ok:
        raise RuntimeError(f"无法编码图片: {path}")
    buf.tofile(str(path))


class DepthEstimator:
    """加载 Depth Anything V2 ONNX 并输出可视化深度图。"""

    def __init__(self, model_path: Path, use_gpu: bool = True, gpu_device_id: int = 0) -> None:
        import onnxruntime as ort

        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.log_severity_level = 3

        providers = []
        if use_gpu:
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                providers.append(("CUDAExecutionProvider", {"device_id": gpu_device_id}))
            elif "DmlExecutionProvider" in available:
                providers.append("DmlExecutionProvider")
            elif "CoreMLExecutionProvider" in available:
                providers.append("CoreMLExecutionProvider")
        providers.append("CPUExecutionProvider")

        self.sess = ort.InferenceSession(str(model_path), sess_options=sess_options, providers=providers)
        self.input = self.sess.get_inputs()[0]
        self.device_info = self.sess.get_providers()[0]
        logger.info("Depth Anything 已加载: %s (%s)", model_path.name, self.device_info)

    def estimate(self, bgr: np.ndarray, input_size: int = 518) -> np.ndarray:
        orig_h, orig_w = bgr.shape[:2]
        height, width = infer_hw(orig_h, orig_w, input_size, _static_input_hw(self.input.shape))
        tensor = preprocess_bgr(bgr, height, width)
        if "float16" in str(self.input.type):
            tensor = tensor.astype(np.float16)
        raw = self.sess.run(None, {self.input.name: tensor})[0]
        depth = np.squeeze(np.asarray(raw))
        if depth.ndim != 2:
            raise ValueError(f"意外的深度输出形状: {getattr(raw, 'shape', None)}")
        return cv2.resize(depth.astype(np.float32), (orig_w, orig_h), interpolation=cv2.INTER_CUBIC)

    def estimate_file(self, src: Path, out: Path, grayscale: bool = True) -> Path:
        image = imread_unicode(src)
        depth = self.estimate(image)
        vis = colorize_depth(depth, grayscale=grayscale)
        imwrite_unicode(out, vis)
        return out

    def estimate_video(
        self,
        src: Path,
        out: Path,
        grayscale: bool = True,
        config_service=None,
        progress=None,
    ) -> Path:
        """逐帧估计深度并保留原视频音轨。"""
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频: {src}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if width <= 0 or height <= 0:
            cap.release()
            raise RuntimeError(f"无法读取视频尺寸: {src}")

        silent = out.with_name(out.stem + ".silent_tmp.mp4")
        writer = cv2.VideoWriter(
            str(silent),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("无法创建深度视频")

        index = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                vis = colorize_depth(self.estimate(frame), grayscale=grayscale)
                if vis.shape[1] != width or vis.shape[0] != height:
                    vis = cv2.resize(vis, (width, height), interpolation=cv2.INTER_LINEAR)
                writer.write(vis)
                index += 1
                if progress is not None and (index == 1 or index % 5 == 0):
                    progress(index, total)
        finally:
            cap.release()
            writer.release()

        if index == 0:
            silent.unlink(missing_ok=True)
            raise RuntimeError(f"视频没有可读帧: {src}")
        if progress is not None:
            progress(index, total or index)
        _remux_audio(config_service, silent, src, out)
        return out

    def estimate_animation(self, src: Path, out: Path, grayscale: bool = True, progress=None) -> Path:
        """逐帧估计 GIF / 动态 WebP / APNG，并保留原帧间隔和循环次数。"""
        from PIL import Image

        with Image.open(src) as image:
            total = int(getattr(image, "n_frames", 1) or 1)
            if total <= 1:
                return self.estimate_file(src, out, grayscale=grayscale)
            loop = int(image.info.get("loop", 0) or 0)
            source_format = (image.format or "").upper()
            frames = []
            durations = []
            base_size = None
            for index in range(total):
                image.seek(index)
                durations.append(int(image.info.get("duration") or 100) or 100)
                rgb = image.convert("RGB")
                bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
                vis = colorize_depth(self.estimate(bgr), grayscale=grayscale)
                if base_size is None:
                    base_size = (vis.shape[1], vis.shape[0])
                elif (vis.shape[1], vis.shape[0]) != base_size:
                    vis = cv2.resize(vis, base_size, interpolation=cv2.INTER_LINEAR)
                frames.append(Image.fromarray(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)))
                if progress is not None and (index == 0 or (index + 1) % 2 == 0):
                    progress(index + 1, total)

        out.parent.mkdir(parents=True, exist_ok=True)
        save_format = "GIF"
        suffix = out.suffix.lower()
        if suffix == ".webp" or source_format == "WEBP":
            save_format = "WEBP"
        elif suffix in {".png", ".apng"} or source_format == "PNG":
            save_format = "PNG"
        save_kwargs = {
            "save_all": True,
            "append_images": frames[1:],
            "duration": durations,
            "loop": loop,
            "format": save_format,
        }
        if save_format == "WEBP":
            save_kwargs["quality"] = 90
        frames[0].save(out, **save_kwargs)
        if progress is not None:
            progress(total, total)
        return out

    def unload_model(self) -> None:
        try:
            if getattr(self, "sess", None) is not None:
                del self.sess
                self.sess = None
            gc.collect()
        except Exception as exc:
            logger.error("卸载深度模型失败: %s", exc)
