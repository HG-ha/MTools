# -*- coding: utf-8 -*-
"""字幕格式化工具模块。

提供 SRT、VTT、LRC、ASS 等字幕格式的解析和转换功能。
"""

import re
from typing import List, Dict, Any, Optional, Tuple


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


# ==================== 字幕解析函数 ====================

def parse_srt_timestamp(timestamp: str) -> float:
    """解析 SRT 时间戳为秒数。
    
    Args:
        timestamp: SRT 格式的时间戳，如 "00:01:23,456"
        
    Returns:
        时间（秒）
    """
    # 支持逗号和点作为毫秒分隔符
    timestamp = timestamp.replace(',', '.')
    parts = timestamp.split(':')
    
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        return float(timestamp)


def parse_vtt_timestamp(timestamp: str) -> float:
    """解析 VTT 时间戳为秒数。
    
    Args:
        timestamp: VTT 格式的时间戳，如 "00:01:23.456"
        
    Returns:
        时间（秒）
    """
    return parse_srt_timestamp(timestamp)


def parse_lrc_timestamp(timestamp: str) -> float:
    """解析 LRC 时间戳为秒数。
    
    Args:
        timestamp: LRC 格式的时间戳，如 "[01:23.45]" 或 "01:23.45"
        
    Returns:
        时间（秒）
    """
    # 移除方括号
    timestamp = timestamp.strip('[]')
    parts = timestamp.split(':')
    
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    else:
        return float(timestamp)


def parse_srt(content: str) -> List[Dict[str, Any]]:
    """解析 SRT 字幕文件内容。
    
    Args:
        content: SRT 字幕文件内容
        
    Returns:
        分段列表，每个元素包含 text, start, end
    """
    segments = []
    
    # 按空行分割成块
    blocks = re.split(r'\n\s*\n', content.strip())
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        # 查找时间戳行（包含 -->）
        timestamp_line_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                timestamp_line_idx = i
                break
        
        if timestamp_line_idx == -1:
            continue
        
        # 解析时间戳
        timestamp_line = lines[timestamp_line_idx]
        match = re.match(r'([\d:,\.]+)\s*-->\s*([\d:,\.]+)', timestamp_line)
        if not match:
            continue
        
        start = parse_srt_timestamp(match.group(1))
        end = parse_srt_timestamp(match.group(2))
        
        # 文本是时间戳行之后的所有行
        text = '\n'.join(lines[timestamp_line_idx + 1:]).strip()
        
        if text:
            segments.append({
                'start': start,
                'end': end,
                'text': text
            })
    
    return segments


def parse_vtt(content: str) -> List[Dict[str, Any]]:
    """解析 VTT 字幕文件内容。
    
    Args:
        content: VTT 字幕文件内容
        
    Returns:
        分段列表，每个元素包含 text, start, end
    """
    segments = []
    
    # 移除 WEBVTT 头部和可能的 NOTE 注释
    lines = content.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().upper().startswith('WEBVTT'):
            start_idx = i + 1
            break
    
    content = '\n'.join(lines[start_idx:])
    
    # 按空行分割成块
    blocks = re.split(r'\n\s*\n', content.strip())
    
    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue
        
        # 跳过 NOTE 注释
        if lines[0].strip().upper().startswith('NOTE'):
            continue
        
        # 查找时间戳行
        timestamp_line_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                timestamp_line_idx = i
                break
        
        if timestamp_line_idx == -1:
            continue
        
        # 解析时间戳（可能包含位置信息如 line:0 position:50%）
        timestamp_line = lines[timestamp_line_idx]
        match = re.match(r'([\d:\.]+)\s*-->\s*([\d:\.]+)', timestamp_line)
        if not match:
            continue
        
        start = parse_vtt_timestamp(match.group(1))
        end = parse_vtt_timestamp(match.group(2))
        
        # 文本是时间戳行之后的所有行
        text = '\n'.join(lines[timestamp_line_idx + 1:]).strip()
        
        # 移除 VTT 样式标签如 <c.colorCCCCCC>
        text = re.sub(r'<[^>]+>', '', text)
        
        if text:
            segments.append({
                'start': start,
                'end': end,
                'text': text
            })
    
    return segments


def parse_lrc(content: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """解析 LRC 歌词文件内容。
    
    Args:
        content: LRC 歌词文件内容
        
    Returns:
        (分段列表, 元数据字典)
        分段列表每个元素包含 text, start, end（end 为下一行的开始时间）
    """
    segments = []
    metadata = {}
    
    lines = content.strip().split('\n')
    
    # 解析每一行
    timed_lines = []  # (start_time, text)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 匹配元数据标签 [ti:xxx], [ar:xxx], [al:xxx], [by:xxx]
        meta_match = re.match(r'\[(ti|ar|al|by|offset):([^\]]*)\]', line, re.IGNORECASE)
        if meta_match:
            key = meta_match.group(1).lower()
            value = meta_match.group(2).strip()
            metadata[key] = value
            continue
        
        # 匹配时间戳和歌词，支持多时间戳格式如 [00:12.00][00:24.00]歌词
        # 匹配所有时间戳
        timestamps = re.findall(r'\[(\d+:\d+(?:\.\d+)?)\]', line)
        
        if timestamps:
            # 获取歌词文本（去掉所有时间戳）
            text = re.sub(r'\[\d+:\d+(?:\.\d+)?\]', '', line).strip()
            
            if text:
                for ts in timestamps:
                    start = parse_lrc_timestamp(ts)
                    timed_lines.append((start, text))
    
    # 按时间排序
    timed_lines.sort(key=lambda x: x[0])
    
    # 转换为分段格式（end 为下一行的开始时间）
    for i, (start, text) in enumerate(timed_lines):
        if i + 1 < len(timed_lines):
            end = timed_lines[i + 1][0]
        else:
            # 最后一行，估计持续时间（默认 5 秒或根据文本长度）
            end = start + max(3.0, len(text) * 0.2)
        
        segments.append({
            'start': start,
            'end': end,
            'text': text
        })
    
    return segments, metadata


def parse_ass(content: str) -> List[Dict[str, Any]]:
    """解析 ASS/SSA 字幕文件内容。
    
    Args:
        content: ASS 字幕文件内容
        
    Returns:
        分段列表，每个元素包含 text, start, end
    """
    segments = []
    
    lines = content.split('\n')
    in_events = False
    format_fields = []
    
    for line in lines:
        line = line.strip()
        
        # 查找 [Events] 节
        if line.lower() == '[events]':
            in_events = True
            continue
        
        # 如果遇到新的节，退出 Events
        if line.startswith('[') and line.endswith(']') and in_events:
            in_events = False
            continue
        
        if not in_events:
            continue
        
        # 解析 Format 行
        if line.lower().startswith('format:'):
            format_str = line[7:].strip()
            format_fields = [f.strip().lower() for f in format_str.split(',')]
            continue
        
        # 解析 Dialogue 行
        if line.lower().startswith('dialogue:'):
            if not format_fields:
                # 默认格式
                format_fields = ['layer', 'start', 'end', 'style', 'name', 'marginl', 'marginr', 'marginv', 'effect', 'text']
            
            values = line[9:].split(',', len(format_fields) - 1)
            if len(values) < len(format_fields):
                continue
            
            data = dict(zip(format_fields, values))
            
            # 解析时间戳（ASS 格式: H:MM:SS.CC）
            start_str = data.get('start', '0:00:00.00')
            end_str = data.get('end', '0:00:00.00')
            
            start = parse_ass_timestamp(start_str)
            end = parse_ass_timestamp(end_str)
            
            text = data.get('text', '')
            
            # 移除 ASS 样式标签 {\xxx}
            text = re.sub(r'\{[^}]*\}', '', text)
            # 将 \N 和 \n 转换为换行
            text = text.replace('\\N', '\n').replace('\\n', '\n')
            text = text.strip()
            
            if text:
                segments.append({
                    'start': start,
                    'end': end,
                    'text': text
                })
    
    return segments


def parse_ass_timestamp(timestamp: str) -> float:
    """解析 ASS 时间戳为秒数。
    
    Args:
        timestamp: ASS 格式的时间戳，如 "0:01:23.45" 或 "1:23:45.67"
        
    Returns:
        时间（秒）
    """
    timestamp = timestamp.strip()
    parts = timestamp.split(':')
    
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        return float(timestamp)


def parse_subtitle_file(file_path: str) -> Tuple[List[Dict[str, Any]], str, Dict[str, str]]:
    """根据文件扩展名自动解析字幕文件。
    
    Args:
        file_path: 字幕文件路径
        
    Returns:
        (分段列表, 格式类型, 元数据)
    """
    import os
    
    ext = os.path.splitext(file_path)[1].lower()
    
    # 尝试多种编码读取文件
    content = None
    for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'utf-16', 'utf-16-le', 'utf-16-be']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if content is None:
        raise ValueError(f"无法读取文件，不支持的编码: {file_path}")
    
    metadata = {}
    
    if ext == '.srt':
        segments = parse_srt(content)
        format_type = 'srt'
    elif ext == '.vtt':
        segments = parse_vtt(content)
        format_type = 'vtt'
    elif ext == '.lrc':
        segments, metadata = parse_lrc(content)
        format_type = 'lrc'
    elif ext in ('.ass', '.ssa'):
        segments = parse_ass(content)
        format_type = 'ass'
    elif ext == '.txt':
        # 尝试检测格式
        if 'WEBVTT' in content[:100]:
            segments = parse_vtt(content)
            format_type = 'vtt'
        elif re.search(r'\d+:\d+:\d+[,\.]\d+\s*-->\s*\d+:\d+:\d+[,\.]\d+', content):
            segments = parse_srt(content)
            format_type = 'srt'
        elif re.search(r'\[\d+:\d+\.\d+\]', content):
            segments, metadata = parse_lrc(content)
            format_type = 'lrc'
        else:
            # 纯文本，每行作为一个分段
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            segments = []
            for i, line in enumerate(lines):
                segments.append({
                    'start': i * 3.0,  # 假设每行 3 秒
                    'end': (i + 1) * 3.0,
                    'text': line
                })
            format_type = 'txt'
    else:
        raise ValueError(f"不支持的字幕格式: {ext}")
    
    return segments, format_type, metadata


def segments_to_ass(
    segments: List[Dict[str, Any]],
    font_name: str = "Microsoft YaHei",
    font_size: int = 20,
    primary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000",
    back_color: str = "&H80000000",
    outline: int = 2,
    shadow: int = 1,
    margin_v: int = 30
) -> str:
    """将分段结果转换为 ASS 字幕格式。
    
    Args:
        segments: 分段结果列表
        font_name: 字体名称
        font_size: 字体大小
        primary_color: 主颜色（ASS 格式 &HAABBGGRR）
        outline_color: 描边颜色
        back_color: 背景颜色
        outline: 描边宽度
        shadow: 阴影深度
        margin_v: 垂直边距
        
    Returns:
        ASS 格式的字幕文本
    """
    if not segments:
        return ""
    
    # ASS 文件头
    header = f"""[Script Info]
Title: Converted by MTools
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{primary_color},{outline_color},{back_color},0,0,0,0,100,100,0,0,1,{outline},{shadow},2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    lines = [header.strip()]
    
    for segment in segments:
        text = segment['text'].strip()
        if not text:
            continue
        
        start = format_ass_timestamp(segment['start'])
        end = format_ass_timestamp(segment['end'])
        
        # 将换行转换为 ASS 的 \N
        text = text.replace('\n', '\\N')
        
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    
    return '\n'.join(lines)


def format_ass_timestamp(seconds: float) -> str:
    """将秒数转换为 ASS 时间戳格式。
    
    Args:
        seconds: 时间（秒）
        
    Returns:
        ASS 格式的时间戳，如 "0:01:23.45"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    return f"{hours}:{minutes:02d}:{secs:05.2f}"