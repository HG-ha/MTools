"""图片处理服务模块。

提供图片格式转换、压缩、尺寸调整等功能。
"""

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image


class ImageService:
    """图片处理服务类。
    
    提供图片处理相关功能，包括：
    - 格式转换
    - 图片压缩（Pillow、mozjpeg、pngquant）
    - 尺寸调整
    - 批量处理
    """
    
    def __init__(self) -> None:
        """初始化图片处理服务。"""
        self._init_tools_path()
    
    def _init_tools_path(self) -> None:
        """初始化压缩工具路径。"""
        # 获取项目根目录
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件
            base_path = Path(sys._MEIPASS)
        else:
            # 开发环境
            base_path = Path(__file__).parent.parent.parent
        
        system = platform.system()
        
        if system == "Windows":
            bin_dir = base_path / "bin" / "windows"
            self.mozjpeg_path = bin_dir / "mozjpeg" / "shared" / "Release" / "cjpeg.exe"
            self.pngquant_path = bin_dir / "pngquant" / "pngquant" / "pngquant.exe"
        elif system == "Darwin":
            bin_dir = base_path / "bin" / "macos"
            self.mozjpeg_path = bin_dir / "mozjpeg" / "cjpeg"
            self.pngquant_path = bin_dir / "pngquant" / "pngquant"
        else:  # Linux
            bin_dir = base_path / "bin" / "linux"
            self.mozjpeg_path = bin_dir / "mozjpeg" / "cjpeg"
            self.pngquant_path = bin_dir / "pngquant" / "pngquant"
    
    def _is_tool_available(self, tool_name: str) -> bool:
        """检查压缩工具是否可用。
        
        Args:
            tool_name: 工具名称（'mozjpeg' 或 'pngquant'）
        
        Returns:
            是否可用
        """
        if tool_name == "mozjpeg":
            return self.mozjpeg_path.exists()
        elif tool_name == "pngquant":
            return self.pngquant_path.exists()
        return False
    
    def get_image_info(self, image_path: Path) -> dict:
        """获取图片信息。
        
        Args:
            image_path: 图片路径
        
        Returns:
            包含图片信息的字典，包括：
            - width: 宽度
            - height: 高度
            - format: 格式
            - mode: 颜色模式
            - size: 文件大小（字节）
            如果读取失败，返回包含 'error' 键的字典
        """
        try:
            with Image.open(image_path) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size': image_path.stat().st_size,
                }
                return info
        except Exception as e:
            return {'error': str(e)}
    
    def convert_format(
        self,
        input_path: Path,
        output_path: Path,
        quality: int = 85
    ) -> bool:
        """转换图片格式。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            quality: 输出质量（1-100）
        
        Returns:
            是否成功
        """
        try:
            with Image.open(input_path) as img:
                # 转换为 RGB（如果输出格式不支持透明度）
                if output_path.suffix.lower() in ['.jpg', '.jpeg']:
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # 创建白色背景
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                
                # 保存图片
                save_kwargs = {'quality': quality, 'optimize': True}
                
                if output_path.suffix.lower() == '.png':
                    save_kwargs['compress_level'] = 9
                elif output_path.suffix.lower() == '.webp':
                    save_kwargs['method'] = 6
                
                img.save(output_path, **save_kwargs)
            
            return True
        except Exception as e:
            print(f"格式转换失败: {e}")
            return False
    
    def compress_image(
        self,
        input_path: Path,
        output_path: Path,
        mode: str = 'balanced',
        quality: int = 85
    ) -> Tuple[bool, str]:
        """压缩图片。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            mode: 压缩模式 ('fast', 'balanced', 'max')
            quality: 质量参数（1-100）
        
        Returns:
            (是否成功, 消息)
        """
        ext = input_path.suffix.lower()
        
        try:
            if mode == 'fast':
                # 快速压缩 - 使用 Pillow
                return self._compress_with_pillow(input_path, output_path, quality)
            
            elif mode == 'balanced':
                # 标准压缩 - 使用专业工具
                if ext in ['.jpg', '.jpeg']:
                    if self._is_tool_available('mozjpeg'):
                        return self._compress_with_mozjpeg(input_path, output_path, quality)
                    else:
                        return self._compress_with_pillow(input_path, output_path, quality)
                
                elif ext == '.png':
                    if self._is_tool_available('pngquant'):
                        return self._compress_with_pngquant(input_path, output_path, quality)
                    else:
                        return self._compress_with_pillow(input_path, output_path, quality)
                
                else:
                    return self._compress_with_pillow(input_path, output_path, quality)
            
            elif mode == 'max':
                # 极限压缩 - 两次压缩
                if ext in ['.jpg', '.jpeg'] and self._is_tool_available('mozjpeg'):
                    return self._compress_with_mozjpeg(input_path, output_path, quality - 5)
                elif ext == '.png' and self._is_tool_available('pngquant'):
                    return self._compress_with_pngquant(input_path, output_path, quality - 10)
                else:
                    return self._compress_with_pillow(input_path, output_path, quality - 10)
            
            else:
                return False, f"未知的压缩模式: {mode}"
        
        except Exception as e:
            return False, f"压缩失败: {e}"
    
    def _compress_with_pillow(
        self,
        input_path: Path,
        output_path: Path,
        quality: int
    ) -> Tuple[bool, str]:
        """使用 Pillow 压缩图片。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            quality: 质量参数
        
        Returns:
            (是否成功, 消息)
        """
        try:
            with Image.open(input_path) as img:
                save_kwargs = {'quality': quality, 'optimize': True}
                
                if output_path.suffix.lower() == '.png':
                    save_kwargs['compress_level'] = 9
                
                img.save(output_path, **save_kwargs)
            
            # 计算压缩率
            original_size = input_path.stat().st_size
            compressed_size = output_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            
            return True, f"压缩成功 (Pillow): 减小 {ratio:.1f}%"
        
        except Exception as e:
            return False, f"Pillow 压缩失败: {e}"
    
    def _compress_with_mozjpeg(
        self,
        input_path: Path,
        output_path: Path,
        quality: int
    ) -> Tuple[bool, str]:
        """使用 mozjpeg 压缩 JPEG 图片。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            quality: 质量参数
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 构建命令
            cmd = [
                str(self.mozjpeg_path),
                '-quality', str(quality),
                '-optimize',
                '-progressive',
                '-outfile', str(output_path),
                str(input_path)
            ]
            
            # 执行压缩
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            if result.returncode != 0:
                return False, f"mozjpeg 执行失败: {result.stderr}"
            
            # 计算压缩率
            original_size = input_path.stat().st_size
            compressed_size = output_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            
            return True, f"压缩成功 (mozjpeg): 减小 {ratio:.1f}%"
        
        except Exception as e:
            return False, f"mozjpeg 压缩失败: {e}"
    
    def _compress_with_pngquant(
        self,
        input_path: Path,
        output_path: Path,
        quality: int
    ) -> Tuple[bool, str]:
        """使用 pngquant 压缩 PNG 图片。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            quality: 质量参数
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # pngquant 的质量范围
            min_quality = max(0, quality - 15)
            max_quality = quality
            
            # 构建命令
            cmd = [
                str(self.pngquant_path),
                '--quality', f'{min_quality}-{max_quality}',
                '--speed', '3',  # 1=最慢最好, 11=最快
                '--force',
                '--output', str(output_path),
                str(input_path)
            ]
            
            # 执行压缩
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            # pngquant 在质量不满足时会返回 99
            if result.returncode not in [0, 99]:
                # 如果失败，尝试用 Pillow 兜底
                return self._compress_with_pillow(input_path, output_path, quality)
            
            # 计算压缩率
            original_size = input_path.stat().st_size
            compressed_size = output_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100
            
            return True, f"压缩成功 (pngquant): 减小 {ratio:.1f}%"
        
        except Exception as e:
            return False, f"pngquant 压缩失败: {e}"
    
    def resize_image(
        self,
        input_path: Path,
        output_path: Path,
        width: Optional[int] = None,
        height: Optional[int] = None,
        keep_aspect: bool = True
    ) -> bool:
        """调整图片尺寸。
        
        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            width: 目标宽度
            height: 目标高度
            keep_aspect: 是否保持宽高比
        
        Returns:
            是否成功
        """
        try:
            with Image.open(input_path) as img:
                original_width, original_height = img.size
                
                if keep_aspect:
                    # 保持宽高比
                    if width and not height:
                        height = int(original_height * width / original_width)
                    elif height and not width:
                        width = int(original_width * height / original_height)
                    elif width and height:
                        # 按照最小缩放比例
                        ratio = min(width / original_width, height / original_height)
                        width = int(original_width * ratio)
                        height = int(original_height * ratio)
                
                if not width or not height:
                    return False
                
                # 使用高质量重采样
                resized = img.resize((width, height), Image.Resampling.LANCZOS)
                resized.save(output_path, quality=95, optimize=True)
            
            return True
        except Exception as e:
            print(f"尺寸调整失败: {e}")
            return False
    
    def get_image_info(self, image_path: Path) -> dict:
        """获取图片信息。
        
        Args:
            image_path: 图片路径
        
        Returns:
            图片信息字典
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height,
                    'file_size': image_path.stat().st_size,
                }
        except Exception as e:
            return {'error': str(e)}

