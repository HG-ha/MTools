# -*- coding: utf-8 -*-
"""音频处理服务模块。

提供音频格式转换、剪辑、参数调整等功能。
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from utils import format_file_size


class AudioService:
    """音频处理服务类。
    
    提供音频处理相关功能，包括：
    - 格式转换（使用 ffmpeg）
    - 比特率调整
    - 采样率调整
    - 声道调整
    - 批量处理
    """
    
    def __init__(self, ffmpeg_service=None) -> None:
        """初始化音频处理服务。
        
        Args:
            ffmpeg_service: FFmpeg服务实例（可选）
        """
        self.ffmpeg_service = ffmpeg_service
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用。
        
        Returns:
            是否可用
        """
        if self.ffmpeg_service:
            is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
            return is_available
        
        # 回退到默认检查
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def is_ffmpeg_available(self) -> bool:
        """检查 ffmpeg 是否可用（公共方法）。
        
        Returns:
            是否可用
        """
        return self._check_ffmpeg()
    
    def _get_ffmpeg_cmd(self) -> str:
        """获取ffmpeg命令。
        
        Returns:
            ffmpeg可执行文件路径或命令
        """
        if self.ffmpeg_service:
            path = self.ffmpeg_service.get_ffmpeg_path()
            if path:
                return path
        return "ffmpeg"
    
    def _get_ffprobe_cmd(self) -> str:
        """获取ffprobe命令。
        
        Returns:
            ffprobe可执行文件路径或命令
        """
        if self.ffmpeg_service:
            path = self.ffmpeg_service.get_ffprobe_path()
            if path:
                return path
        return "ffprobe"
    
    def get_audio_info(self, audio_path: Path) -> dict:
        """获取音频文件信息。
        
        Args:
            audio_path: 音频文件路径
        
        Returns:
            包含音频信息的字典
        """
        try:
            ffprobe_cmd = self._get_ffprobe_cmd()
            result = subprocess.run(
                [
                    ffprobe_cmd,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(audio_path)
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                # 提取音频流信息
                audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
                if audio_streams:
                    stream = audio_streams[0]
                    format_info = data.get('format', {})
                    
                    return {
                        'format': format_info.get('format_name', '未知'),
                        'duration': float(format_info.get('duration', 0)),
                        'bit_rate': int(format_info.get('bit_rate', 0)),
                        'codec': stream.get('codec_name', '未知'),
                        'sample_rate': int(stream.get('sample_rate', 0)),
                        'channels': int(stream.get('channels', 0)),
                        'channel_layout': stream.get('channel_layout', '未知'),
                        'file_size': audio_path.stat().st_size,
                    }
            
            return {'error': '无法读取音频信息'}
        except Exception as e:
            return {'error': str(e)}
    
    def convert_audio(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str = "mp3",
        bitrate: Optional[str] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        quality: Optional[int] = None
    ) -> Tuple[bool, str]:
        """转换音频格式。
        
        Args:
            input_path: 输入音频路径
            output_path: 输出音频路径
            output_format: 输出格式 (mp3, wav, aac, flac, ogg, m4a)
            bitrate: 比特率 (如 "192k", "320k")
            sample_rate: 采样率 (如 44100, 48000)
            channels: 声道数 (1=单声道, 2=立体声)
            quality: 质量等级 (仅用于某些编码器，0-9，值越小质量越高)
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 构建 ffmpeg 命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            cmd = [ffmpeg_cmd, "-i", str(input_path), "-y"]  # -y 覆盖输出文件
            
            # 设置音频编码器
            codec_map = {
                "mp3": "libmp3lame",
                "aac": "aac",
                "m4a": "aac",
                "wav": "pcm_s16le",
                "flac": "flac",
                "ogg": "libvorbis",
                "opus": "libopus",
                "wma": "wmav2",
            }
            
            codec = codec_map.get(output_format.lower())
            if codec:
                cmd.extend(["-c:a", codec])
            
            # 设置比特率
            if bitrate and output_format not in ["wav", "flac"]:  # 无损格式不需要比特率
                cmd.extend(["-b:a", bitrate])
            
            # 设置采样率
            if sample_rate:
                cmd.extend(["-ar", str(sample_rate)])
            
            # 设置声道数
            if channels:
                cmd.extend(["-ac", str(channels)])
            
            # 设置质量
            if quality is not None:
                if output_format == "mp3":
                    # MP3 使用 VBR 质量 (0-9)
                    cmd.extend(["-q:a", str(quality)])
                elif output_format in ["ogg", "opus"]:
                    # Vorbis/Opus 使用质量等级
                    cmd.extend(["-q:a", str(quality)])
            
            # 添加输出文件
            cmd.append(str(output_path))
            
            # 执行转换
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                # 计算文件大小变化
                input_size = input_path.stat().st_size
                output_size = output_path.stat().st_size
                
                input_size_str = format_file_size(input_size)
                output_size_str = format_file_size(output_size)
                
                if output_size < input_size:
                    ratio = (1 - output_size / input_size) * 100
                    return True, f"转换成功: {input_size_str} → {output_size_str} (减小 {ratio:.1f}%)"
                else:
                    return True, f"转换成功: {input_size_str} → {output_size_str}"
            else:
                error_msg = result.stderr if result.stderr else "未知错误"
                return False, f"转换失败: {error_msg}"
        
        except subprocess.TimeoutExpired:
            return False, "转换超时（文件可能过大）"
        except Exception as e:
            return False, f"转换失败: {str(e)}"
    
    def get_supported_formats(self) -> List[dict]:
        """获取支持的音频格式列表。
        
        Returns:
            格式列表，每个格式包含 extension, name, description
        """
        return [
            {
                "extension": "mp3",
                "name": "MP3",
                "description": "通用格式，兼容性好",
                "lossy": True,
            },
            {
                "extension": "aac",
                "name": "AAC",
                "description": "高质量有损压缩",
                "lossy": True,
            },
            {
                "extension": "m4a",
                "name": "M4A",
                "description": "AAC容器，Apple设备优选",
                "lossy": True,
            },
            {
                "extension": "wav",
                "name": "WAV",
                "description": "无损格式，文件较大",
                "lossy": False,
            },
            {
                "extension": "flac",
                "name": "FLAC",
                "description": "无损压缩，高保真",
                "lossy": False,
            },
            {
                "extension": "ogg",
                "name": "OGG Vorbis",
                "description": "开源有损格式",
                "lossy": True,
            },
            {
                "extension": "opus",
                "name": "Opus",
                "description": "新一代音频编码",
                "lossy": True,
            },
            {
                "extension": "wma",
                "name": "WMA",
                "description": "Windows Media Audio",
                "lossy": True,
            },
        ]
    
    def get_bitrate_presets(self) -> List[dict]:
        """获取比特率预设列表。
        
        Returns:
            比特率预设列表
        """
        return [
            {"value": "64k", "name": "64 kbps", "description": "低质量（语音）"},
            {"value": "96k", "name": "96 kbps", "description": "较低质量"},
            {"value": "128k", "name": "128 kbps", "description": "标准质量"},
            {"value": "192k", "name": "192 kbps", "description": "高质量"},
            {"value": "256k", "name": "256 kbps", "description": "很高质量"},
            {"value": "320k", "name": "320 kbps", "description": "最高质量"},
        ]
    
    def get_sample_rate_presets(self) -> List[dict]:
        """获取采样率预设列表。
        
        Returns:
            采样率预设列表
        """
        return [
            {"value": 22050, "name": "22.05 kHz", "description": "低质量"},
            {"value": 44100, "name": "44.1 kHz", "description": "CD 音质（标准）"},
            {"value": 48000, "name": "48 kHz", "description": "专业音质"},
            {"value": 96000, "name": "96 kHz", "description": "高清音质"},
        ]

