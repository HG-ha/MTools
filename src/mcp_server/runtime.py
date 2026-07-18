# -*- coding: utf-8 -*-
"""MCP 运行时：复用 MTools 已初始化的 ConfigService 与各业务服务。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from services.config_service import ConfigService
    from services.encoding_service import EncodingService
    from services.ffmpeg_service import FFmpegService
    from services.image_service import ImageService
    from services.translate_service import TranslateService

_config_service: Optional["ConfigService"] = None


def init_runtime(config_service: "ConfigService") -> None:
    """注入应用内 ConfigService，供 MCP 工具处理器使用。"""
    global _config_service
    _config_service = config_service
    get_image_service.cache_clear()
    get_ffmpeg_service.cache_clear()
    get_encoding_service.cache_clear()
    get_translate_service.cache_clear()


def get_config_service() -> "ConfigService":
    if _config_service is None:
        raise RuntimeError("MCP 运行时未初始化")
    return _config_service


@lru_cache(maxsize=1)
def get_image_service() -> "ImageService":
    from services.image_service import ImageService

    return ImageService(get_config_service())


@lru_cache(maxsize=1)
def get_ffmpeg_service() -> "FFmpegService":
    from services.ffmpeg_service import FFmpegService

    return FFmpegService(get_config_service())


@lru_cache(maxsize=1)
def get_encoding_service() -> "EncodingService":
    from services.encoding_service import EncodingService

    return EncodingService()


@lru_cache(maxsize=1)
def get_translate_service() -> "TranslateService":
    from services.translate_service import TranslateService

    return TranslateService()


def get_models_dir() -> Path:
    return get_config_service().get_data_dir() / "models"


def get_output_dir() -> Path:
    out = get_config_service().get_output_dir()
    out.mkdir(parents=True, exist_ok=True)
    return out
