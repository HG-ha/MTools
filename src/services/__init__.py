# -*- coding: utf-8 -*-
"""业务服务模块初始化文件。"""

from .audio_service import AudioService
from .sogou_search_service import SogouSearchService
from .config_service import ConfigService
from .encoding_service import EncodingService
from .ffmpeg_service import FFmpegService
from .http_service import HttpService
from .image_service import ImageService
from .ocr_service import OCRService
from .vad_service import VADService
from .vocal_separation_service import VocalSeparationService
from .speech_recognition_service import SpeechRecognitionService
from .weather_service import WeatherService
from .websocket_service import WebSocketService
from .update_service import UpdateService, UpdateInfo, UpdateStatus
from .auto_updater import AutoUpdater
from .face_detection_service import FaceDetector, FaceDetectionResult
from .id_photo_service import IDPhotoService, IDPhotoParams, IDPhotoResult
from .subtitle_remove_service import SubtitleRemoveService
from .translate_service import TranslateService, SUPPORTED_LANGUAGES

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
]

