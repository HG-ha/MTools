"""文件工具模块。

提供文件和目录操作相关的工具函数。
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional


def ensure_dir(path: Path) -> bool:
    """确保目录存在，如不存在则创建。
    
    Args:
        path: 目录路径
    
    Returns:
        是否成功
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"创建目录失败: {e}")
        return False


def get_file_size(path: Path) -> int:
    """获取文件大小（字节）。
    
    Args:
        path: 文件路径
    
    Returns:
        文件大小
    """
    try:
        return path.stat().st_size
    except Exception:
        return 0


def format_file_size(size: int) -> str:
    """格式化文件大小显示。
    
    Args:
        size: 文件大小（字节）
    
    Returns:
        格式化后的文件大小字符串
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def clean_temp_files(temp_dir: Path, max_age_days: int = 7) -> int:
    """清理临时文件。
    
    Args:
        temp_dir: 临时文件目录
        max_age_days: 最大保留天数
    
    Returns:
        删除的文件数量
    """
    import time
    
    count: int = 0
    current_time: float = time.time()
    max_age_seconds: float = max_age_days * 24 * 3600
    
    try:
        for file_path in temp_dir.iterdir():
            if file_path.is_file():
                file_age: float = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    count += 1
    except Exception as e:
        print(f"清理临时文件失败: {e}")
    
    return count


def copy_file(src: Path, dst: Path) -> bool:
    """复制文件。
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
    
    Returns:
        是否成功
    """
    try:
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"复制文件失败: {e}")
        return False


def move_file(src: Path, dst: Path) -> bool:
    """移动文件。
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
    
    Returns:
        是否成功
    """
    try:
        shutil.move(str(src), str(dst))
        return True
    except Exception as e:
        print(f"移动文件失败: {e}")
        return False


def get_file_extension(path: Path) -> str:
    """获取文件扩展名（不含点号）。
    
    Args:
        path: 文件路径
    
    Returns:
        文件扩展名
    """
    return path.suffix.lstrip(".")


def list_files_by_extension(directory: Path, extensions: List[str]) -> List[Path]:
    """列出指定扩展名的所有文件。
    
    Args:
        directory: 目录路径
        extensions: 扩展名列表（不含点号）
    
    Returns:
        文件路径列表
    """
    files: List[Path] = []
    
    try:
        for ext in extensions:
            pattern: str = f"*.{ext}"
            files.extend(directory.glob(pattern))
    except Exception as e:
        print(f"列出文件失败: {e}")
    
    return files

