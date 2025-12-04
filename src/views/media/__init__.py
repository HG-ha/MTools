# -*- coding: utf-8 -*-
"""音视频处理视图模块。

提供音视频处理相关的所有视图组件。
"""

from views.media.audio_format_view import AudioFormatView
from views.media.ffmpeg_install_view import FFmpegInstallView
from views.media.media_view import MediaView
from views.media.video_enhance_view import VideoEnhanceView

__all__ = [
    'AudioFormatView',
    'FFmpegInstallView',
    'MediaView',
    'VideoEnhanceView',
]

