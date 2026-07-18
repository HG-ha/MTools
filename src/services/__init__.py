# -*- coding: utf-8 -*-
"""业务服务模块初始化文件。

依赖重量级原生库（onnxruntime / cv2 等）的服务用 try/except 保护，
避免某个 DLL 缺失导致整个应用无法启动。
"""

import logging as _logging

_logger = _logging.getLogger(__name__)

# ── 核心服务（纯 Python 或仅依赖轻量级库，必须可用）──────────
from .audio_service import AudioService
from .sogou_search_service import SogouSearchService
from .config_service import ConfigService
from .encoding_service import EncodingService
from .ffmpeg_service import FFmpegService
from .http_service import HttpService
from .weather_service import WeatherService
from .websocket_service import WebSocketService
from .update_service import UpdateService, UpdateInfo, UpdateStatus
from .auto_updater import AutoUpdater
from .translate_service import TranslateService, SUPPORTED_LANGUAGES
from .global_hotkey_service import GlobalHotkeyService
from .mcp_server_service import McpServerService

# ── 可选服务（依赖 onnxruntime / cv2 / numpy 等原生库）────────
try:
    from .image_service import ImageService
except Exception as _e:
    _logger.warning("服务模块 image_service 导入失败: %s", _e)

try:
    from .ocr_service import OCRService
except Exception as _e:
    _logger.warning("服务模块 ocr_service 导入失败: %s", _e)

try:
    from .vad_service import VADService
except Exception as _e:
    _logger.warning("服务模块 vad_service 导入失败: %s", _e)

try:
    from .vocal_separation_service import VocalSeparationService
except Exception as _e:
    _logger.warning("服务模块 vocal_separation_service 导入失败: %s", _e)

try:
    from .speech_recognition_service import SpeechRecognitionService
except Exception as _e:
    _logger.warning("服务模块 speech_recognition_service 导入失败: %s", _e)

try:
    from .face_detection_service import FaceDetector, FaceDetectionResult
except Exception as _e:
    _logger.warning("服务模块 face_detection_service 导入失败: %s", _e)

try:
    from .id_photo_service import IDPhotoService, IDPhotoParams, IDPhotoResult
except Exception as _e:
    _logger.warning("服务模块 id_photo_service 导入失败: %s", _e)

try:
    from .subtitle_remove_service import SubtitleRemoveService
except Exception as _e:
    _logger.warning("服务模块 subtitle_remove_service 导入失败: %s", _e)

try:
    from .tts_service import TTSService
except Exception as _e:
    _logger.warning("服务模块 tts_service 导入失败: %s", _e)

try:
    from .ai_subtitle_fix_service import AISubtitleFixService
except Exception as _e:
    _logger.warning("服务模块 ai_subtitle_fix_service 导入失败: %s", _e)

__all__ = [
    "AudioService",
    "SogouSearchService",
    "ConfigService",
    "EncodingService",
    "FFmpegService",
    "HttpService",
    "ImageService",
    "OCRService",
    "VADService",
    "VocalSeparationService",
    "SpeechRecognitionService",
    "WeatherService",
    "WebSocketService",
    "UpdateService",
    "UpdateInfo",
    "UpdateStatus",
    "AutoUpdater",
    "FaceDetector",
    "FaceDetectionResult",
    "IDPhotoService",
    "IDPhotoParams",
    "IDPhotoResult",
    "SubtitleRemoveService",
    "TranslateService",
    "SUPPORTED_LANGUAGES",
    "AISubtitleFixService",
    "GlobalHotkeyService",
    "McpServerService",
    "TTSService",
]
