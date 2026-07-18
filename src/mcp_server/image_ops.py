# -*- coding: utf-8 -*-
"""图片处理 MCP 实现。"""

from __future__ import annotations

import base64
import io
import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence


def crop_image(src: Path, out: Path, left: int, top: int, right: int, bottom: int) -> None:
    with Image.open(src) as img:
        cropped = img.crop((left, top, right, bottom))
        cropped.save(out)


def rotate_image(
    src: Path,
    out: Path,
    mode: str = "rotate_90",
    angle: float = 0,
    fillcolor: str = "#FFFFFF",
) -> None:
    with Image.open(src) as img:
        is_gif = getattr(img, "is_animated", False) and img.n_frames > 1
        if is_gif:
            frames = []
            for frame in ImageSequence.Iterator(img):
                frames.append(_apply_rotate(frame, mode, angle, fillcolor))
            frames[0].save(
                out,
                save_all=True,
                append_images=frames[1:],
                duration=img.info.get("duration", 100),
                loop=img.info.get("loop", 0),
            )
        else:
            _apply_rotate(img, mode, angle, fillcolor).save(out)


def _apply_rotate(img: Image.Image, mode: str, angle: float, fillcolor: str) -> Image.Image:
    if mode == "rotate_90":
        return img.rotate(-90, expand=True)
    if mode == "rotate_180":
        return img.rotate(180, expand=True)
    if mode == "rotate_270":
        return img.rotate(90, expand=True)
    if mode == "flip_horizontal":
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if mode == "flip_vertical":
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if mode == "custom":
        r, g, b = _parse_color(fillcolor)
        return img.rotate(angle, expand=True, fillcolor=(r, g, b))
    raise ValueError(f"未知旋转模式: {mode}")


def _parse_color(color: str) -> Tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 6:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return 255, 255, 255


def add_text_watermark(
    src: Path,
    out: Path,
    text: str,
    position: str = "bottom_right",
    opacity: int = 128,
    font_size: int = 36,
    color: str = "#FFFFFF",
) -> None:
    with Image.open(src) as img:
        base = img.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
        r, g, b = _parse_color(color)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = 20
        positions = {
            "top_left": (margin, margin),
            "top_right": (base.width - tw - margin, margin),
            "bottom_left": (margin, base.height - th - margin),
            "bottom_right": (base.width - tw - margin, base.height - th - margin),
            "center": ((base.width - tw) // 2, (base.height - th) // 2),
        }
        xy = positions.get(position, positions["bottom_right"])
        draw.text(xy, text, fill=(r, g, b, opacity), font=font)
        result = Image.alpha_composite(base, overlay)
        if out.suffix.lower() in (".jpg", ".jpeg"):
            result = result.convert("RGB")
        result.save(out)


def remove_watermark_simple(src: Path, out: Path, left: int, top: int, right: int, bottom: int) -> None:
    import cv2
    img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
    mask = np.zeros(img.shape[:2], np.uint8)
    mask[top:bottom, left:right] = 255
    result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    ext = out.suffix or ".png"
    cv2.imencode(ext, result)[1].tofile(str(out))


def generate_qrcode(content: str, out: Path, version: int = 1, level: str = "M") -> None:
    qr = qrcode.QRCode(
        version=version,
        error_correction={
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }[level.upper()],
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(out)


def image_to_base64(src: Path) -> dict:
    data = src.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return {"base64": b64, "mime": f"image/{src.suffix.lstrip('.').lower()}"}


def base64_to_image(b64_str: str, out: Path) -> None:
    raw = b64_str.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    data = base64.b64decode(raw)
    img = Image.open(io.BytesIO(data))
    img.save(out)


def convert_color_space(src: Path, out: Path, target: str, threshold: int = 128) -> None:
    with Image.open(src) as img:
        if target == "grayscale":
            result = img.convert("L")
        elif target == "rgba":
            result = img.convert("RGBA")
        elif target == "rgb":
            result = img.convert("RGB")
        elif target == "cmyk":
            result = img.convert("CMYK")
        elif target == "invert":
            result = _invert(img)
        elif target == "sepia":
            result = _sepia(img)
        elif target == "binary":
            result = img.convert("L").point(lambda p: 255 if p > threshold else 0)
        elif target in ("lab", "hsv"):
            import cv2
            rgb = np.array(img.convert("RGB"))
            code = cv2.COLOR_RGB2LAB if target == "lab" else cv2.COLOR_RGB2HSV
            converted = cv2.cvtColor(rgb, code)
            if target == "lab":
                converted = cv2.cvtColor(converted, cv2.COLOR_LAB2RGB)
            result = Image.fromarray(converted)
        else:
            raise ValueError(f"不支持的色彩空间: {target}")
        result.save(out)


def _invert(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        r, g, b, a = img.split()
        inv = ImageOps.invert(Image.merge("RGB", (r, g, b)))
        r2, g2, b2 = inv.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    return ImageOps.invert(img.convert("RGB"))


def _sepia(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            tr = min(255, int(r * 0.393 + g * 0.769 + b * 0.189))
            tg = min(255, int(r * 0.349 + g * 0.686 + b * 0.168))
            tb = min(255, int(r * 0.272 + g * 0.534 + b * 0.131))
            pixels[x, y] = (tr, tg, tb)
    return img


def add_border(
    src: Path,
    out: Path,
    top: int = 10,
    bottom: int = 10,
    left: int = 10,
    right: int = 10,
    color: str = "#FFFFFF",
    corner_radius: int = 0,
) -> None:
    r, g, b = _parse_color(color)
    with Image.open(src) as img:
        ow, oh = img.size
        nw, nh = ow + left + right, oh + top + bottom
        if corner_radius > 0 or img.mode == "RGBA":
            canvas = Image.new("RGBA", (nw, nh), (r, g, b, 255))
            layer = img.convert("RGBA")
            canvas.paste(layer, (left, top))
            if corner_radius > 0:
                mask = Image.new("L", (nw, nh), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle((0, 0, nw, nh), radius=corner_radius, fill=255)
                canvas.putalpha(mask)
            canvas.save(out)
        else:
            canvas = Image.new("RGB", (nw, nh), (r, g, b))
            canvas.paste(img.convert("RGB"), (left, top))
            canvas.save(out)


def puzzle_split(
    src: Path,
    out: Path,
    rows: int = 3,
    cols: int = 3,
    spacing: int = 0,
    shuffle: bool = False,
) -> None:
    with Image.open(src) as image:
        w, h = image.size
        pieces = []
        for row in range(rows):
            for col in range(cols):
                left = int(w * col / cols)
                top = int(h * row / rows)
                right = int(w * (col + 1) / cols)
                bottom = int(h * (row + 1) / rows)
                pieces.append(image.crop((left, top, right, bottom)))
        if shuffle:
            random.shuffle(pieces)
        ncol = cols
        nrow = rows
        pw, ph = pieces[0].size
        result = Image.new("RGB", (ncol * pw + spacing * (ncol - 1), nrow * ph + spacing * (nrow - 1)), "white")
        for i, piece in enumerate(pieces):
            x = (i % ncol) * (pw + spacing)
            y = (i // ncol) * (ph + spacing)
            result.paste(piece.convert("RGB"), (x, y))
        result.save(out)


def puzzle_merge(
    input_paths: List[Path],
    out: Path,
    direction: str = "horizontal",
    spacing: int = 0,
    grid_cols: int = 3,
) -> None:
    images = [Image.open(p) for p in input_paths]
    try:
        if direction == "horizontal":
            max_h = max(i.height for i in images)
            resized = []
            for img in images:
                if img.height != max_h:
                    ar = img.width / img.height
                    img = img.resize((int(max_h * ar), max_h), Image.Resampling.LANCZOS)
                resized.append(img)
            total_w = sum(i.width for i in resized) + spacing * (len(resized) - 1)
            result = Image.new("RGB", (total_w, max_h), "white")
            x = 0
            for img in resized:
                result.paste(img, (x, 0))
                x += img.width + spacing
        elif direction == "vertical":
            max_w = max(i.width for i in images)
            resized = []
            for img in images:
                if img.width != max_w:
                    ar = img.height / img.width
                    img = img.resize((max_w, int(max_w * ar)), Image.Resampling.LANCZOS)
                resized.append(img)
            total_h = sum(i.height for i in resized) + spacing * (len(resized) - 1)
            result = Image.new("RGB", (max_w, total_h), "white")
            y = 0
            for img in resized:
                result.paste(img, (0, y))
                y += img.height + spacing
        else:
            cols = grid_cols
            max_w = max(i.width for i in images)
            max_h = max(i.height for i in images)
            resized = [i.resize((max_w, max_h), Image.Resampling.LANCZOS) for i in images]
            rows = (len(resized) + cols - 1) // cols
            result = Image.new("RGB", (cols * max_w + spacing * (cols - 1), rows * max_h + spacing * (rows - 1)), "white")
            for idx, img in enumerate(resized):
                x = (idx % cols) * (max_w + spacing)
                y = (idx // cols) * (max_h + spacing)
                result.paste(img, (x, y))
        result.save(out)
    finally:
        for img in images:
            img.close()
