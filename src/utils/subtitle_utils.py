# -*- coding: utf-8 -*-
"""字幕格式化工具模块。

提供 SRT、VTT 等字幕格式的转换功能。
"""

from typing import List, Dict, Any


def format_timestamp_srt(seconds: float) -> str:
    """将秒数转换为 SRT 时间戳格式。
    
    Args:
        seconds: 时间（秒）
        
    Returns:
        SRT 格式的时间戳，如 "00:01:23,456"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """将秒数转换为 VTT 时间戳格式。
    
    Args:
        seconds: 时间（秒）
        
    Returns:
        VTT 格式的时间戳，如 "00:01:23.456"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """将分段结果转换为 SRT 字幕格式。
    
    Args:
        segments: 分段结果列表，每个元素包含 text, start, end
        
    Returns:
        SRT 格式的字幕文本
    """
    if not segments:
        return ""
    
    srt_lines = []
    
    for i, segment in enumerate(segments, start=1):
        text = segment['text'].strip()
        if not text:
            continue
        
        start_time = format_timestamp_srt(segment['start'])
        end_time = format_timestamp_srt(segment['end'])
        
        # SRT 格式：
        # 1
        # 00:00:00,000 --> 00:00:05,000
        # 字幕文本
        # (空行)
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(text)
        srt_lines.append("")  # 空行
    
    return "\n".join(srt_lines)


def segments_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """将分段结果转换为 VTT 字幕格式。
    
    Args:
        segments: 分段结果列表，每个元素包含 text, start, end
        
    Returns:
        VTT 格式的字幕文本
    """
    if not segments:
        return "WEBVTT\n\n"
    
    vtt_lines = ["WEBVTT", ""]  # VTT 文件必须以 "WEBVTT" 开头
    
    for i, segment in enumerate(segments, start=1):
        text = segment['text'].strip()
        if not text:
            continue
        
        start_time = format_timestamp_vtt(segment['start'])
        end_time = format_timestamp_vtt(segment['end'])
        
        # VTT 格式：
        # WEBVTT
        #
        # 1
        # 00:00:00.000 --> 00:00:05.000
        # 字幕文本
        # (空行)
        vtt_lines.append(f"{i}")
        vtt_lines.append(f"{start_time} --> {end_time}")
        vtt_lines.append(text)
        vtt_lines.append("")  # 空行
    
    return "\n".join(vtt_lines)


def segments_to_txt(segments: List[Dict[str, Any]]) -> str:
    """将分段结果转换为纯文本格式。
    
    Args:
        segments: 分段结果列表，每个元素包含 text, start, end
        
    Returns:
        纯文本格式的内容
    """
    if not segments:
        return ""
    
    return "\n".join(segment['text'].strip() for segment in segments if segment['text'].strip())
