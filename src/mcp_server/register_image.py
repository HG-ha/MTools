# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp_server import image_ops
from mcp_server.helpers import (
    compress_mode,
    convert_subtitle_file,
    fail,
    ok,
    quality_value,
    resolve_input,
    resolve_output,
)
from mcp_server.media_ops import image_search_similar, watermark_remove_ai
from mcp_server.handlers import register_handler
from mcp_server.runtime import get_config_service, get_image_service, get_output_dir
from services.image_service import ImageService


def register_handlers_only() -> None:
    register_handler("mtools_image", _mtools_image_impl())


def register(mcp) -> None:
    fn = _mtools_image_impl()
    register_handler("mtools_image", fn)
    mcp.tool()(fn)


def _mtools_image_impl():
    def mtools_image(
        action: Literal[
            "compress", "format", "resize", "crop", "rotate", "background", "watermark",
            "watermark_remove", "info", "exif", "qrcode", "to_base64", "gif", "enhance",
            "puzzle_merge", "puzzle_split", "search", "ocr", "color_space", "border",
        ],
        input_path: str = "",
        output_path: str = "",
        input_paths: str = "",
        text: str = "",
        quality: Literal["high", "medium", "low"] = "medium",
        compress_mode_name: Literal["fast", "balanced", "max"] = "balanced",
        target_format: str = "png",
        width: int = 0,
        height: int = 0,
        keep_aspect: bool = True,
        left: int = 0,
        top: int = 0,
        right: int = 0,
        bottom: int = 0,
        rotate_mode: Literal["rotate_90", "rotate_180", "rotate_270", "flip_horizontal", "flip_vertical", "custom"] = "rotate_90",
        angle: float = 0,
        model_key: str = "",
        watermark_position: str = "bottom_right",
        watermark_opacity: int = 128,
        font_size: int = 36,
        color: str = "#FFFFFF",
        qrcode_level: Literal["L", "M", "Q", "H"] = "M",
        color_space: str = "grayscale",
        binary_threshold: int = 128,
        border_top: int = 10,
        border_bottom: int = 10,
        border_left: int = 10,
        border_right: int = 10,
        corner_radius: int = 0,
        puzzle_rows: int = 3,
        puzzle_cols: int = 3,
        puzzle_spacing: int = 0,
        puzzle_shuffle: bool = False,
        puzzle_direction: Literal["horizontal", "vertical", "grid"] = "horizontal",
        grid_cols: int = 3,
        gif_speed: float = 1.0,
        gif_reverse: bool = False,
        denoise_strength: int = 0,
        sharpen_strength: int = 0,
        remove_mode: Literal["simple", "ai"] = "simple",
    ) -> str:
        """图片处理全能力：压缩/格式/裁剪/旋转/水印/抠图/增强/OCR/拼图/搜图/GIF/边框等。"""
        try:
            cfg = get_config_service()
            svc = get_image_service()
            q = quality_value(quality)

            if action == "info":
                return ok({"info": svc.get_detailed_image_info(resolve_input(input_path))})
            if action == "to_base64":
                return ok(image_ops.image_to_base64(resolve_input(input_path)))
            if action == "qrcode":
                if not text.strip():
                    return fail("qrcode 需要 text 参数")
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "qrcode.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                image_ops.generate_qrcode(text, out, level=qrcode_level)
                return ok({"output_path": str(out)})

            src = resolve_input(input_path) if input_path else None

            if action == "compress":
                out = resolve_output(src, output_path or None)
                success, message = svc.compress_image(src, out, mode=compress_mode(compress_mode_name), quality=q)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "format":
                ext = target_format if target_format.startswith(".") else f".{target_format}"
                out = resolve_output(src, output_path or None, suffix=ext)
                return ok({"output_path": str(out)}) if svc.convert_format(src, out, quality=q) else fail("格式转换失败")
            if action == "resize":
                out = resolve_output(src, output_path or None)
                if not svc.resize_image(src, out, width=width or None, height=height or None, keep_aspect=keep_aspect):
                    return fail("缩放失败")
                return ok({"output_path": str(out)})
            if action == "crop":
                out = resolve_output(src, output_path or None)
                image_ops.crop_image(src, out, left, top, right, bottom)
                return ok({"output_path": str(out)})
            if action == "rotate":
                out = resolve_output(src, output_path or None)
                image_ops.rotate_image(src, out, rotate_mode, angle, color)
                return ok({"output_path": str(out)})
            if action == "watermark":
                if not text.strip():
                    return fail("watermark 需要 text")
                out = resolve_output(src, output_path or None)
                image_ops.add_text_watermark(src, out, text, watermark_position, watermark_opacity, font_size, color)
                return ok({"output_path": str(out)})
            if action == "watermark_remove":
                out = resolve_output(src, output_path or None)
                if remove_mode == "ai":
                    watermark_remove_ai(
                        cfg, src, out, model_key or "sttn_v1",
                        left=left, top=top, right=right, bottom=bottom,
                    )
                else:
                    image_ops.remove_watermark_simple(src, out, left, top, right, bottom)
                return ok({"output_path": str(out)})
            if action == "exif":
                from PIL import Image
                out = resolve_output(src, output_path or None)
                with Image.open(src) as img:
                    clean = Image.new(img.mode, img.size)
                    clean.putdata(list(img.getdata()))
                    clean.save(out)
                return ok({"output_path": str(out)})
            if action == "color_space":
                out = resolve_output(src, output_path or None)
                image_ops.convert_color_space(src, out, color_space, binary_threshold)
                return ok({"output_path": str(out)})
            if action == "border":
                out = resolve_output(src, output_path or None)
                image_ops.add_border(src, out, border_top, border_bottom, border_left, border_right, color, corner_radius)
                return ok({"output_path": str(out)})
            if action == "puzzle_split":
                out = resolve_output(src, output_path or None, suffix=".png")
                image_ops.puzzle_split(src, out, puzzle_rows, puzzle_cols, puzzle_spacing, puzzle_shuffle)
                return ok({"output_path": str(out)})
            if action == "puzzle_merge":
                paths = [Path(p.strip()) for p in input_paths.split(",") if p.strip()]
                if not paths:
                    return fail("puzzle_merge 需要 input_paths（逗号分隔）")
                out = Path(output_path).expanduser().resolve() if output_path else get_output_dir() / "puzzle_merged.png"
                image_ops.puzzle_merge(paths, out, puzzle_direction, puzzle_spacing, grid_cols)
                return ok({"output_path": str(out)})
            if action == "gif":
                from models.gif_adjustment import GifAdjustmentOptions
                out = resolve_output(src, output_path or None, suffix=".gif")
                opts = GifAdjustmentOptions(speed_factor=gif_speed, reverse_order=gif_reverse)
                success, message = svc.adjust_gif(src, out, opts)
                return ok({"output_path": str(out), "message": message}) if success else fail(message)
            if action == "search":
                result = image_search_similar(cfg, src)
                return ok({"results": result})
            if action == "background":
                from constants.model_config import BACKGROUND_REMOVAL_MODELS
                from services.image_service import BackgroundRemover
                from PIL import Image
                key = model_key or cfg.get_config_value("background_model_key", "rmbg_1.4_quantized")
                model = BACKGROUND_REMOVAL_MODELS[key]
                mp = cfg.get_data_dir() / "models" / "background_removal" / model.version / model.filename
                remover = BackgroundRemover(mp, cfg)
                with Image.open(src) as img:
                    result = remover.remove_background(img)
                out = resolve_output(src, output_path or None, suffix=".png")
                result.save(out)
                remover.unload_model()
                return ok({"output_path": str(out)})
            if action == "enhance":
                from constants.model_config import IMAGE_ENHANCE_MODELS
                from services.image_service import ImageEnhancer
                from PIL import Image
                import numpy as np
                key = model_key or cfg.get_config_value("enhance_model_key", "realesrgan_x4plus")
                model = IMAGE_ENHANCE_MODELS[key]
                mp = cfg.get_data_dir() / "models" / "image_enhance" / model.version / model.filename
                enhancer = ImageEnhancer(mp, cfg)
                with Image.open(src) as img:
                    result = enhancer.enhance_image(img)
                from PIL import Image as PILImage
                if denoise_strength > 0:
                    arr = np.array(result.convert("RGB"))
                    arr = ImageService.apply_denoise(arr, denoise_strength)
                    result = PILImage.fromarray(arr)
                if sharpen_strength > 0:
                    arr = np.array(result.convert("RGB"))
                    arr = ImageService.apply_sharpen(arr, sharpen_strength)
                    result = PILImage.fromarray(arr)
                out = resolve_output(src, output_path or None, suffix=".png")
                result.save(out)
                enhancer.unload_model()
                return ok({"output_path": str(out)})
            if action == "ocr":
                import cv2
                import numpy as np
                from services.ocr_service import OCRService
                ocr = OCRService(cfg)
                key = model_key or cfg.get_config_value("ocr_model_key", "ppocr_v5_mobile")
                if not ocr.load_model(key):
                    return fail("OCR 模型加载失败")
                img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
                boxes, _ = ocr.detect_text(img)
                lines = ocr.recognize_text(img, boxes)
                text_out = "\n".join(t for t, _ in lines)
                ocr.unload_model()
                return ok({"text": text_out, "lines": [{"text": t, "score": s} for t, s in lines]})
            return fail(f"未知 action: {action}")
        except Exception as exc:
            return fail(str(exc))

    return mtools_image
