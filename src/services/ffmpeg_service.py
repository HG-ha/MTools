# -*- coding: utf-8 -*-
"""FFmpeg 安装和管理服务模块。

提供FFmpeg的检测、下载、安装功能。
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional, Tuple

import httpx


class FFmpegService:
    """FFmpeg 安装和管理服务类。
    
    提供FFmpeg的检测、下载、安装功能：
    - 检测系统ffmpeg和本地ffmpeg
    - 自动下载ffmpeg
    - 安装到应用程序目录
    """
    
    # FFmpeg Windows下载链接（使用gyan.dev提供的精简版本）
    FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    
    def __init__(self, config_service=None) -> None:
        """初始化FFmpeg服务。
        
        Args:
            config_service: 配置服务实例（可选）
        """
        self.config_service = config_service
        
        # 获取应用程序根目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            self.app_root = Path(sys.executable).parent
        else:
            # 如果是开发模式
            self.app_root = Path(__file__).parent.parent.parent
        
        # ffmpeg 本地安装目录
        self.ffmpeg_dir = self.app_root / "bin" / "windows" / "ffmpeg"
        self.ffmpeg_bin = self.ffmpeg_dir / "bin"
        self.ffmpeg_exe = self.ffmpeg_bin / "ffmpeg.exe"
        self.ffprobe_exe = self.ffmpeg_bin / "ffprobe.exe"
    
    def _get_temp_dir(self) -> Path:
        """获取临时目录。
        
        Returns:
            临时目录路径
        """
        if self.config_service:
            return self.config_service.get_temp_dir()
        
        # 回退到默认临时目录
        temp_dir = self.app_root / "storage" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def is_ffmpeg_available(self) -> Tuple[bool, str]:
        """检查FFmpeg是否可用。
        
        Returns:
            (是否可用, ffmpeg路径或错误信息)
        """
        # 首先检查本地ffmpeg
        if self.ffmpeg_exe.exists():
            try:
                result = subprocess.run(
                    [str(self.ffmpeg_exe), "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True, str(self.ffmpeg_exe)
            except Exception:
                pass
        
        # 检查系统环境变量中的ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, "系统ffmpeg"
        except Exception:
            pass
        
        return False, "未安装"
    
    def get_ffmpeg_path(self) -> Optional[str]:
        """获取可用的ffmpeg路径。
        
        Returns:
            ffmpeg可执行文件路径，如果不可用则返回None
        """
        # 优先使用本地ffmpeg
        if self.ffmpeg_exe.exists():
            return str(self.ffmpeg_exe)
        
        # 使用系统ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return "ffmpeg"  # 系统PATH中的ffmpeg
        except Exception:
            pass
        
        return None
    
    def get_ffprobe_path(self) -> Optional[str]:
        """获取可用的ffprobe路径。
        
        Returns:
            ffprobe可执行文件路径，如果不可用则返回None
        """
        # 优先使用本地ffprobe
        if self.ffprobe_exe.exists():
            return str(self.ffprobe_exe)
        
        # 使用系统ffprobe
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return "ffprobe"  # 系统PATH中的ffprobe
        except Exception:
            pass
        
        return None
    
    def download_ffmpeg(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, str]:
        """下载并安装FFmpeg到本地目录。
        
        Args:
            progress_callback: 进度回调函数，接收(进度0-1, 状态消息)
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 获取临时下载目录
            temp_dir = self._get_temp_dir()
            
            zip_path = temp_dir / "ffmpeg.zip"
            
            # 下载ffmpeg
            if progress_callback:
                progress_callback(0.0, "开始下载FFmpeg...")
            
            with httpx.stream("GET", self.FFMPEG_DOWNLOAD_URL, follow_redirects=True) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                progress = downloaded / total_size * 0.7  # 下载占70%进度
                                size_mb = downloaded / (1024 * 1024)
                                total_mb = total_size / (1024 * 1024)
                                progress_callback(
                                    progress,
                                    f"下载中: {size_mb:.1f}/{total_mb:.1f} MB"
                                )
            
            if progress_callback:
                progress_callback(0.7, "下载完成，开始解压...")
            
            # 解压到临时目录
            extract_dir = temp_dir / "ffmpeg_extracted"
            if extract_dir.exists():
                import shutil
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            if progress_callback:
                progress_callback(0.85, "解压完成，正在安装...")
            
            # 查找解压后的ffmpeg目录（通常在一个子目录中）
            ffmpeg_folders = list(extract_dir.glob("ffmpeg-*"))
            if not ffmpeg_folders:
                return False, "下载的文件格式不正确"
            
            source_dir = ffmpeg_folders[0]
            
            # 创建目标目录
            self.ffmpeg_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制文件到目标目录
            import shutil
            
            # 复制 bin 目录
            source_bin = source_dir / "bin"
            if source_bin.exists():
                if self.ffmpeg_bin.exists():
                    shutil.rmtree(self.ffmpeg_bin)
                shutil.copytree(source_bin, self.ffmpeg_bin)
            
            # 复制其他目录（可选）
            for item in source_dir.iterdir():
                if item.is_dir() and item.name not in ["bin"]:
                    dest = self.ffmpeg_dir / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                elif item.is_file():
                    shutil.copy2(item, self.ffmpeg_dir / item.name)
            
            if progress_callback:
                progress_callback(0.95, "清理临时文件...")
            
            # 清理临时文件
            try:
                zip_path.unlink()
                shutil.rmtree(extract_dir)
            except Exception:
                pass  # 清理失败不影响安装结果
            
            if progress_callback:
                progress_callback(1.0, "安装完成!")
            
            # 验证安装
            if self.ffmpeg_exe.exists() and self.ffprobe_exe.exists():
                return True, f"FFmpeg 已成功安装到: {self.ffmpeg_dir}"
            else:
                return False, "安装失败：文件未正确复制"
        
        except httpx.HTTPError as e:
            return False, f"下载失败: {str(e)}"
        except zipfile.BadZipFile:
            return False, "下载的文件损坏，请重试"
        except Exception as e:
            return False, f"安装失败: {str(e)}"
    
    def get_install_info(self) -> dict:
        """获取FFmpeg安装信息。
        
        Returns:
            包含安装状态、路径等信息的字典
        """
        is_available, location = self.is_ffmpeg_available()
        
        info = {
            "available": is_available,
            "location": location,
            "local_exists": self.ffmpeg_exe.exists(),
            "local_path": str(self.ffmpeg_dir) if self.ffmpeg_exe.exists() else None,
        }
        
        # 获取版本信息
        if is_available:
            try:
                ffmpeg_cmd = self.get_ffmpeg_path()
                if ffmpeg_cmd:
                    result = subprocess.run(
                        [ffmpeg_cmd, "-version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        # 提取版本号（第一行）
                        version_line = result.stdout.split('\n')[0]
                        info["version"] = version_line
            except Exception:
                pass
        
        return info

