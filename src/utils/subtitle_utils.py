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


def format_timestamp_lrc(seconds: float) -> str:
    """将秒数转换为 LRC 时间戳格式。
    
    Args:
        seconds: 时间（秒）
        
    Returns:
        LRC 格式的时间戳，如 "[01:23.45]"
    """
    minutes = int(seconds // 60)
    secs = seconds % 60
    # LRC 格式：[mm:ss.xx] 分钟:秒.百分之一秒
    return f"[{minutes:02d}:{secs:05.2f}]"


def segments_to_lrc(segments: List[Dict[str, Any]], title: str = "", artist: str = "", album: str = "") -> str:
    """将分段结果转换为 LRC 歌词格式。
    
    LRC 是一种简单的歌词文件格式，每行包含时间戳和对应的歌词文本。
    格式示例：
    [ti:歌曲名]
    [ar:艺术家]
    [al:专辑名]
    [00:12.00]第一句歌词
    [00:17.20]第二句歌词
    
    Args:
        segments: 分段结果列表，每个元素包含 text, start, end
        title: 歌曲/音频标题（可选）
        artist: 艺术家/说话人（可选）
        album: 专辑名（可选）
        
    Returns:
        LRC 格式的歌词文本
    """
    if not segments:
        return ""
    
    lrc_lines = []
    
    # 添加元数据标签（如果提供）
    if title:
        lrc_lines.append(f"[ti:{title}]")
    if artist:
        lrc_lines.append(f"[ar:{artist}]")
    if album:
        lrc_lines.append(f"[al:{album}]")
    
    # 添加生成工具标识
    lrc_lines.append("[by:MTools]")
    
    # 添加空行分隔元数据和歌词
    if lrc_lines:
        lrc_lines.append("")
    
    # 转换每个分段为 LRC 格式
    for segment in segments:
        text = segment['text'].strip()
        if not text:
            continue
        
        start_time = format_timestamp_lrc(segment['start'])
        
        # LRC 格式：[mm:ss.xx]歌词文本
        lrc_lines.append(f"{start_time}{text}")
    
    return "\n".join(lrc_lines)