# -*- coding: utf-8 -*-
"""图片处理服务模块。

提供图片格式转换、压缩、尺寸调整等功能。
"""

import gc
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from models import GifAdjustmentOptions
from utils import GifUtils


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
            - file_size: 文件大小（字节）
            如果读取失败，返回包含 'error' 键的字典
        """
        try:
            with Image.open(image_path) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'file_size': image_path.stat().st_size,
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
                ext = output_path.suffix.lower()
                save_kwargs = {}
                
                # 根据目标格式处理图片模式和参数
                if ext in ['.jpg', '.jpeg', '.jfif']:
                    # JPEG/JFIF 不支持透明通道
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    save_kwargs = {'quality': quality, 'optimize': True, 'progressive': True}
                
                elif ext == '.png':
                    save_kwargs = {'optimize': True, 'compress_level': 9}
                
                elif ext == '.webp':
                    save_kwargs = {'quality': quality, 'method': 6, 'optimize': True}
                
                elif ext == '.gif':
                    # GIF 需要调色板模式
                    if img.mode != 'P':
                        img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                    save_kwargs = {'optimize': True, 'save_all': True}
                
                elif ext in ['.tiff', '.tif']:
                    save_kwargs = {'quality': quality, 'compression': 'tiff_lzw', 'optimize': True}
                
                elif ext == '.bmp':
                    # BMP 通常不支持压缩
                    save_kwargs = {}
                
                elif ext == '.ico':
                    save_kwargs = {}
                
                elif ext in ['.avif', '.heic', '.heif']:
                    save_kwargs = {'quality': quality, 'optimize': True}
                
                else:
                    save_kwargs = {'quality': quality, 'optimize': True}
                
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
                if ext in ['.jpg', '.jpeg', '.jfif']:
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
                if ext in ['.jpg', '.jpeg', '.jfif'] and self._is_tool_available('mozjpeg'):
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
                ext = output_path.suffix.lower()
                save_kwargs = {}
                
                # 根据不同格式设置压缩参数
                if ext == '.png':
                    save_kwargs = {
                        'optimize': True,
                        'compress_level': 9
                    }
                elif ext in ['.jpg', '.jpeg', '.jfif']:
                    save_kwargs = {
                        'quality': quality,
                        'optimize': True,
                        'progressive': True
                    }
                    # JPEG/JFIF 不支持透明通道，需要转换
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                elif ext == '.webp':
                    save_kwargs = {
                        'quality': quality,
                        'method': 6,  # 最慢但最好的压缩
                        'optimize': True
                    }
                elif ext == '.gif':
                    # GIF 需要保持调色板模式
                    if img.mode != 'P':
                        img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                    save_kwargs = {
                        'optimize': True,
                        'save_all': True,  # 保存所有帧（动图）
                    }
                elif ext in ['.tiff', '.tif']:
                    save_kwargs = {
                        'quality': quality,
                        'compression': 'tiff_lzw',  # 使用 LZW 压缩
                        'optimize': True
                    }
                elif ext == '.ico':
                    # ICO 格式通常用于小图标
                    save_kwargs = {}
                elif ext in ['.avif', '.heic', '.heif']:
                    # 现代格式，高效压缩
                    save_kwargs = {
                        'quality': quality,
                        'optimize': True
                    }
                else:
                    # 默认设置
                    save_kwargs = {
                        'quality': quality,
                        'optimize': True
                    }
                
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
                encoding='utf-8',
                errors='replace',
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
                encoding='utf-8',
                errors='replace',
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
    
    def adjust_gif(
        self,
        input_path: Path,
        output_path: Path,
        options: GifAdjustmentOptions
    ) -> Tuple[bool, str]:
        """根据配置调整 GIF 动画。

        Args:
            input_path: 源 GIF 文件路径
            output_path: 输出 GIF 文件路径
            options: 调整配置

        Returns:
            (是否成功, 描述信息)
        """
        if input_path.suffix.lower() != ".gif":
            return False, "仅支持 GIF 格式文件"

        frames, durations, original_loop = GifUtils.load_frames_with_metadata(input_path)
        if not frames:
            return False, "未能读取 GIF 帧数据"

        total_frames = len(frames)
        # 处理截取范围
        start_index = max(0, options.trim_start or 0)
        end_index = options.trim_end if options.trim_end is not None else total_frames - 1
        end_index = max(start_index, min(total_frames - 1, end_index))

        frames = frames[start_index:end_index + 1]
        durations = durations[start_index:end_index + 1]

        if not frames:
            return False, "截取范围无有效帧"

        # 按步长保留帧
        if options.drop_every_n > 1:
            frames, durations = self._drop_frames_with_step(frames, durations, options.drop_every_n)
            if not frames:
                return False, "跳帧设置导致无有效帧"

        # 反转帧顺序
        if options.reverse_order:
            frames.reverse()
            durations.reverse()

        # 调整播放速度
        speed_factor = options.speed_factor if options.speed_factor > 0 else 1.0
        if abs(speed_factor - 1.0) > 0.001:
            # 计算新的帧持续时间
            # 注意：GIF 格式的帧延迟最小单位是 10ms (1/100秒)
            # 但我们仍然允许更小的值，由 GIF 编码器处理取整
            durations = [max(2, int(round(duration / speed_factor))) for duration in durations]

        # 设定封面帧（首帧）
        if options.cover_frame_index is not None and frames:
            relative_index = options.cover_frame_index
            relative_index = max(0, min(len(frames) - 1, relative_index))
            if relative_index != 0:
                frames = frames[relative_index:] + frames[:relative_index]
                durations = durations[relative_index:] + durations[:relative_index]

        loop_value = options.loop if options.loop is not None else original_loop
        loop_value = max(0, loop_value)

        success = GifUtils.save_frames_to_gif(frames, durations, output_path, loop=loop_value)
        if not success:
            return False, "保存 GIF 失败"

        return True, f"GIF 调整完成，共 {len(frames)} 帧"

    @staticmethod
    def _drop_frames_with_step(
        frames: List[Image.Image],
        durations: List[int],
        step: int
    ) -> Tuple[List[Image.Image], List[int]]:
        """按照指定步长保留帧并累加持续时间。

        Args:
            frames: 原始帧列表
            durations: 原始持续时间列表
            step: 保留步长

        Returns:
            (新的帧列表, 新的持续时间列表)
        """
        if step <= 1:
            return frames, durations

        new_frames: List[Image.Image] = []
        new_durations: List[int] = []
        accumulated = 0

        for index, (frame, duration) in enumerate(zip(frames, durations)):
            accumulated += duration
            if index % step == 0:
                new_frames.append(frame)
                new_durations.append(accumulated)
                accumulated = 0

        if accumulated > 0 and new_durations:
            new_durations[-1] += accumulated

        return new_frames, new_durations

    def get_detailed_image_info(self, image_path: Path) -> dict:
        """获取详细的图片信息，包括EXIF、DPI、色彩统计等专业数据。
        
        Args:
            image_path: 图片路径
        
        Returns:
            包含详细图片信息的字典
        """
        try:
            from datetime import datetime
            import hashlib
            
            # 获取文件统计信息
            file_stat = image_path.stat()
            
            # 计算文件哈希值
            with open(image_path, 'rb') as f:
                file_data = f.read()
                md5_hash = hashlib.md5(file_data).hexdigest()
                sha256_hash = hashlib.sha256(file_data).hexdigest()
            
            # 检测实况图信息
            live_photo_info = self._detect_live_photo(image_path, file_data)
            
            with Image.open(image_path) as img:
                # 基本信息
                info = {
                    'filename': image_path.name,
                    'filepath': str(image_path.absolute()),
                    'format': img.format or '未知',
                    'format_description': img.format_description if hasattr(img, 'format_description') else '',
                    'mode': img.mode,
                    'width': img.width,
                    'height': img.height,
                    'size': img.size,
                    'file_size': file_stat.st_size,
                    'aspect_ratio': f"{img.width}:{img.height}",
                }
                
                # 计算更精确的宽高比
                from math import gcd
                ratio_gcd = gcd(img.width, img.height)
                info['aspect_ratio_simplified'] = f"{img.width // ratio_gcd}:{img.height // ratio_gcd}"
                
                # 像素统计
                info['total_pixels'] = img.width * img.height
                info['megapixels'] = round(img.width * img.height / 1_000_000, 2)
                
                # 位深度信息
                mode_bits = {
                    '1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32,
                    'CMYK': 32, 'YCbCr': 24, 'LAB': 24, 'HSV': 24,
                    'I': 32, 'F': 32, 'LA': 16, 'PA': 16,
                    'RGBX': 32, 'RGBa': 32, 'La': 16
                }
                info['bit_depth'] = mode_bits.get(img.mode, '未知')
                info['bytes_per_pixel'] = len(img.mode) if img.mode in ['RGB', 'RGBA', 'CMYK'] else 1
                
                # 文件哈希
                info['md5'] = md5_hash
                info['sha256'] = sha256_hash
                
                # 获取 DPI 信息
                dpi = img.info.get('dpi', None)
                if dpi:
                    info['dpi'] = f"{dpi[0]} × {dpi[1]}"
                    info['dpi_x'] = dpi[0]
                    info['dpi_y'] = dpi[1]
                else:
                    info['dpi'] = '未指定'
                    info['dpi_x'] = None
                    info['dpi_y'] = None
                
                # 颜色信息
                info['color_mode_description'] = self._get_mode_description(img.mode)
                
                # 获取调色板信息
                if img.mode == 'P':
                    palette = img.getpalette()
                    if palette:
                        info['palette_size'] = len(palette) // 3
                    else:
                        info['palette_size'] = 0
                
                # 透明度信息
                info['has_transparency'] = img.mode in ('RGBA', 'LA', 'PA', 'P')
                if img.mode == 'P' and 'transparency' in img.info:
                    info['has_transparency'] = True
                
                # 压缩和质量信息
                if img.format == 'JPEG':
                    # JPEG 质量估算
                    if 'quality' in img.info:
                        info['jpeg_quality'] = img.info['quality']
                    if 'progressive' in img.info:
                        info['progressive'] = img.info['progressive']
                    elif 'progression' in img.info:
                        info['progressive'] = img.info['progression']
                
                if img.format == 'PNG':
                    if 'interlace' in img.info:
                        info['interlaced'] = img.info['interlace'] == 1
                
                # ICC配置文件
                if 'icc_profile' in img.info:
                    info['has_icc_profile'] = True
                    info['icc_profile_size'] = len(img.info['icc_profile'])
                else:
                    info['has_icc_profile'] = False
                
                # 色彩统计（对于RGB图像）
                try:
                    if img.mode in ('RGB', 'RGBA', 'L'):
                        import numpy as np
                        img_array = np.array(img)
                        
                        if img.mode == 'L':
                            # 灰度图
                            info['average_brightness'] = round(float(np.mean(img_array)), 2)
                            info['std_deviation'] = round(float(np.std(img_array)), 2)
                        elif img.mode in ('RGB', 'RGBA'):
                            # RGB图像
                            rgb_array = img_array[:, :, :3] if img.mode == 'RGBA' else img_array
                            info['average_color'] = {
                                'R': int(np.mean(rgb_array[:, :, 0])),
                                'G': int(np.mean(rgb_array[:, :, 1])),
                                'B': int(np.mean(rgb_array[:, :, 2])),
                            }
                            info['average_brightness'] = round(float(np.mean(rgb_array)), 2)
                            info['std_deviation'] = round(float(np.std(rgb_array)), 2)
                except:
                    pass
                
                # 动画信息（GIF）
                if hasattr(img, 'is_animated'):
                    info['is_animated'] = img.is_animated
                    if img.is_animated:
                        info['n_frames'] = getattr(img, 'n_frames', 1)
                else:
                    info['is_animated'] = False
                    info['n_frames'] = 1
                
                # 获取 EXIF 信息
                exif_data = {}
                gps_data = {}
                camera_data = {}
                
                try:
                    from PIL import ExifTags
                    exif = img._getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = ExifTags.TAGS.get(tag_id, tag_id)
                            # 转换特殊类型为字符串
                            if isinstance(value, bytes):
                                # 尝试多种编码方式解码字节数据
                                decoded_value = self._decode_exif_bytes(value)
                                value = decoded_value
                            exif_data[str(tag)] = value
                            
                            # 提取GPS信息
                            if tag == 'GPSInfo':
                                try:
                                    for gps_tag_id in value:
                                        gps_tag = ExifTags.GPSTAGS.get(gps_tag_id, gps_tag_id)
                                        gps_data[str(gps_tag)] = value[gps_tag_id]
                                    
                                    # 转换GPS坐标
                                    if 'GPSLatitude' in gps_data and 'GPSLongitude' in gps_data:
                                        lat = self._convert_gps_to_degrees(
                                            gps_data['GPSLatitude'],
                                            gps_data.get('GPSLatitudeRef', 'N')
                                        )
                                        lon = self._convert_gps_to_degrees(
                                            gps_data['GPSLongitude'],
                                            gps_data.get('GPSLongitudeRef', 'E')
                                        )
                                        info['gps_latitude'] = lat
                                        info['gps_longitude'] = lon
                                        info['gps_coordinates'] = f"{lat:.6f}, {lon:.6f}"
                                except:
                                    pass
                            
                            # 提取主要拍摄参数
                            if tag == 'Make':
                                camera_data['制造商'] = value
                            elif tag == 'Model':
                                camera_data['型号'] = value
                            elif tag == 'LensModel':
                                camera_data['镜头'] = value
                            elif tag == 'DateTime':
                                camera_data['拍摄时间'] = value
                            elif tag == 'ExposureTime':
                                try:
                                    if isinstance(value, tuple) and len(value) == 2:
                                        camera_data['曝光时间'] = f"{value[0]}/{value[1]}s"
                                    else:
                                        camera_data['曝光时间'] = f"{value}s"
                                except:
                                    camera_data['曝光时间'] = str(value)
                            elif tag == 'FNumber':
                                try:
                                    if isinstance(value, tuple) and len(value) == 2:
                                        camera_data['光圈'] = f"f/{value[0]/value[1]:.1f}"
                                    else:
                                        camera_data['光圈'] = f"f/{value:.1f}"
                                except:
                                    camera_data['光圈'] = str(value)
                            elif tag == 'ISOSpeedRatings':
                                camera_data['ISO'] = value
                            elif tag == 'FocalLength':
                                try:
                                    if isinstance(value, tuple) and len(value) == 2:
                                        camera_data['焦距'] = f"{value[0]/value[1]:.1f}mm"
                                    else:
                                        camera_data['焦距'] = f"{value:.1f}mm"
                                except:
                                    camera_data['焦距'] = str(value)
                except:
                    pass
                
                info['exif'] = exif_data
                info['gps'] = gps_data
                info['camera'] = camera_data
                
                # 文件时间信息
                info['created_time'] = datetime.fromtimestamp(file_stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                info['modified_time'] = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                
                # 其他元数据
                info['info'] = dict(img.info)
                
                # 添加实况图信息
                if live_photo_info:
                    info['live_photo'] = live_photo_info
                
                return info
        except Exception as e:
            return {'error': str(e)}
    
    def _decode_exif_bytes(self, data: bytes) -> str:
        """智能解码 EXIF 字节数据。
        
        尝试多种编码方式解码 EXIF 中的字节数据。
        
        Args:
            data: 字节数据
        
        Returns:
            解码后的字符串
        """
        if not data:
            return ''
        
        # 去除尾部的空字节
        data = data.rstrip(b'\x00')
        
        if not data:
            return ''
        
        # 尝试的编码列表（按优先级排序）
        encodings = [
            'utf-8',
            'ascii',
            'gbk',          # 中文 Windows 常用
            'gb2312',       # 简体中文
            'gb18030',      # 中文超集
            'big5',         # 繁体中文
            'shift_jis',    # 日文
            'euc-kr',       # 韩文
            'iso-8859-1',   # 西欧语言
            'cp1252',       # Windows 西欧
        ]
        
        # 尝试每种编码
        for encoding in encodings:
            try:
                decoded = data.decode(encoding)
                # 检查解码后的字符串是否包含有效字符
                # 过滤掉只包含控制字符的结果
                if decoded and any(c.isprintable() or c.isspace() for c in decoded):
                    # 清理字符串：移除首尾空白和不可打印字符
                    cleaned = ''.join(c for c in decoded if c.isprintable() or c.isspace())
                    cleaned = cleaned.strip()
                    if cleaned:
                        return cleaned
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 如果所有编码都失败，返回可打印的 ASCII 字符
        # 或者返回十六进制表示
        try:
            # 尝试只提取 ASCII 可打印字符
            ascii_chars = ''.join(chr(b) for b in data if 32 <= b < 127)
            if ascii_chars:
                return ascii_chars.strip()
        except:
            pass
        
        # 最后的选择：返回十六进制表示
        return f"<binary: {data[:20].hex()}...>" if len(data) > 20 else f"<binary: {data.hex()}>"
    
    def _get_mode_description(self, mode: str) -> str:
        """获取颜色模式描述。
        
        Args:
            mode: PIL 颜色模式
        
        Returns:
            模式描述
        """
        mode_descriptions = {
            '1': '1位像素，黑白',
            'L': '8位像素，灰度',
            'P': '8位像素，使用调色板',
            'RGB': '3×8位像素，真彩色',
            'RGBA': '4×8位像素，带透明通道的真彩色',
            'CMYK': '4×8位像素，印刷色彩分色',
            'YCbCr': '3×8位像素，彩色视频格式',
            'LAB': 'L*a*b 色彩空间',
            'HSV': 'HSV 色彩空间',
            'I': '32位整型像素',
            'F': '32位浮点型像素',
            'LA': '灰度 + Alpha',
            'PA': '调色板 + Alpha',
            'RGBX': 'RGB + 填充',
            'RGBa': 'RGB + Alpha (预乘)',
            'La': '灰度 + Alpha (预乘)',
        }
        return mode_descriptions.get(mode, f'未知模式 ({mode})')
    
    def _convert_gps_to_degrees(self, value: tuple, ref: str) -> float:
        """将GPS坐标从度分秒格式转换为十进制度数。
        
        Args:
            value: GPS坐标元组 (度, 分, 秒)
            ref: 方向参考 ('N', 'S', 'E', 'W')
        
        Returns:
            十进制度数
        """
        try:
            degrees = float(value[0])
            minutes = float(value[1]) if len(value) > 1 else 0
            seconds = float(value[2]) if len(value) > 2 else 0
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            if ref in ['S', 'W']:
                decimal = -decimal
            
            return decimal
        except:
            return 0.0
    
    def _detect_live_photo(self, image_path: Path, file_data: bytes) -> Optional[dict]:
        """检测是否为实况图（Live Photo / Motion Photo）。
        
        Args:
            image_path: 图片路径
            file_data: 图片文件数据
        
        Returns:
            实况图信息字典，如果不是实况图则返回None
        """
        live_info = {}
        
        # 检测 Android Motion Photo (Google Pixel 等)
        android_motion = self._detect_android_motion_photo(image_path, file_data)
        if android_motion:
            live_info.update(android_motion)
        
        # 检测 iPhone Live Photo
        iphone_live = self._detect_iphone_live_photo(image_path, file_data)
        if iphone_live:
            live_info.update(iphone_live)
        
        # 检测 Samsung Motion Photo
        samsung_motion = self._detect_samsung_motion_photo(file_data)
        if samsung_motion:
            live_info.update(samsung_motion)
        
        return live_info if live_info else None
    
    def _detect_android_motion_photo(self, image_path: Path, file_data: bytes) -> Optional[dict]:
        """检测 Android Motion Photo（Google Pixel 等设备）。
        
        Args:
            image_path: 图片路径
            file_data: 图片文件数据
        
        Returns:
            Motion Photo 信息字典，如果不是则返回None
        """
        try:
            import re
            
            # 方法1: 直接在文件数据中搜索 XMP 元数据
            # JPEG 文件中 XMP 数据通常在 APP1 段中
            xmp_data = None
            
            # 搜索 XMP 包标记
            xmp_start_marker = b'<x:xmpmeta'
            xmp_end_marker = b'</x:xmpmeta>'
            
            if xmp_start_marker in file_data:
                xmp_start_pos = file_data.find(xmp_start_marker)
                xmp_end_pos = file_data.find(xmp_end_marker, xmp_start_pos)
                
                if xmp_end_pos > xmp_start_pos:
                    xmp_data = file_data[xmp_start_pos:xmp_end_pos + len(xmp_end_marker)].decode('utf-8', errors='ignore')
            
            # 方法2: 使用 Pillow 读取 XMP（作为备选）
            if not xmp_data:
                try:
                    with Image.open(image_path) as img:
                        if hasattr(img, 'info') and 'XML:com.adobe.xmp' in img.info:
                            xmp_data_raw = img.info['XML:com.adobe.xmp']
                            if isinstance(xmp_data_raw, bytes):
                                xmp_data = xmp_data_raw.decode('utf-8', errors='ignore')
                            else:
                                xmp_data = xmp_data_raw
                except:
                    pass
            
            # 如果找到 XMP 数据，检查是否包含 MotionPhoto 标记
            if xmp_data and ('MotionPhoto' in xmp_data or 'MicroVideo' in xmp_data or 'GCamera' in xmp_data):
                info = {
                    'type': 'Android Motion Photo',
                    'is_live_photo': True,
                    'platform': 'Android (Google)',
                }
                
                # 查找 MicroVideo 偏移量
                micro_video_match = re.search(r'GCamera:MicroVideoOffset="(\d+)"', xmp_data)
                if micro_video_match:
                    offset = int(micro_video_match.group(1))
                    info['video_offset'] = offset
                    info['video_size'] = offset
                
                # 查找 MicroVideo 版本
                version_match = re.search(r'GCamera:MicroVideoVersion="(\d+)"', xmp_data)
                if version_match:
                    info['micro_video_version'] = version_match.group(1)
                
                # 查找 MotionPhoto 版本
                motion_version_match = re.search(r'GCamera:MotionPhotoVersion="(\d+)"', xmp_data)
                if motion_version_match:
                    info['motion_photo_version'] = motion_version_match.group(1)
                
                # 查找 MotionPhotoPresentationTimestampUs (用于同步)
                timestamp_match = re.search(r'GCamera:MotionPhotoPresentationTimestampUs="(\d+)"', xmp_data)
                if timestamp_match:
                    info['presentation_timestamp'] = timestamp_match.group(1)
                
                # 尝试检测嵌入的视频
                if 'video_offset' in info:
                    video_start = len(file_data) - info['video_offset']
                    if video_start > 0 and video_start < len(file_data):
                        video_data = file_data[video_start:]
                        # 检查是否是 MP4 视频
                        if (len(video_data) >= 8 and 
                            (video_data[:4] == b'\x00\x00\x00\x18' or 
                             video_data[:4] == b'\x00\x00\x00\x1c' or
                             video_data[4:8] == b'ftyp')):
                            info['has_embedded_video'] = True
                            info['embedded_video_format'] = 'MP4'
                else:
                    # 即使没有偏移量，也尝试搜索嵌入的视频
                    # 搜索 MP4 文件头
                    mp4_signature = b'ftyp'
                    last_ftyp_pos = file_data.rfind(mp4_signature)
                    
                    if last_ftyp_pos > 0 and last_ftyp_pos > len(file_data) * 0.5:  # 在文件后半部分
                        # 回退到大小字段（ftyp 前面4字节）
                        video_start = last_ftyp_pos - 4
                        if video_start > 0:
                            info['video_offset'] = len(file_data) - video_start
                            info['video_size'] = len(file_data) - video_start
                            info['has_embedded_video'] = True
                            info['embedded_video_format'] = 'MP4'
                            info['detection_method'] = 'File signature search'
                
                return info
            
            # 方法3: 检查 EXIF 中的 MakerNote
            try:
                with Image.open(image_path) as img:
                    from PIL import ExifTags
                    exif = img._getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = ExifTags.TAGS.get(tag_id, tag_id)
                            if tag == 'MakerNote' and isinstance(value, bytes):
                                value_str = value.decode('utf-8', errors='ignore')
                                if 'MotionPhoto' in value_str or 'MicroVideo' in value_str:
                                    return {
                                        'type': 'Android Motion Photo',
                                        'is_live_photo': True,
                                        'platform': 'Android',
                                        'detection_method': 'EXIF MakerNote'
                                    }
            except:
                pass
            
            return None
        except Exception as e:
            print(f"检测 Android Motion Photo 失败: {e}")
            return None
    
    def _detect_iphone_live_photo(self, image_path: Path, file_data: bytes) -> Optional[dict]:
        """检测 iPhone Live Photo。
        
        Args:
            image_path: 图片路径
            file_data: 图片文件数据
        
        Returns:
            Live Photo 信息字典，如果不是则返回None
        """
        try:
            with Image.open(image_path) as img:
                # 检查 HEIC/HEIF 格式（iPhone 常用）
                is_heic = img.format in ('HEIF', 'HEIC')
                
                # 检查是否有 Apple MakerNote
                try:
                    from PIL import ExifTags
                    exif = img._getexif()
                    if exif:
                        for tag_id, value in exif.items():
                            tag = ExifTags.TAGS.get(tag_id, tag_id)
                            
                            # 检查 MakerNote 中的 Apple 标记
                            if tag == 'MakerNote' and isinstance(value, bytes):
                                # Apple 的 MakerNote 包含特定标识
                                if b'Apple iOS' in value or b'Apple' in value[:20]:
                                    # 检查是否有 Live Photo 标识
                                    # Apple 在 MakerNote 中使用特定的标记
                                    info = {
                                        'type': 'iPhone Live Photo',
                                        'is_live_photo': True,
                                        'platform': 'iOS (iPhone/iPad)',
                                    }
                                    
                                    if is_heic:
                                        info['format'] = 'HEIC'
                                    else:
                                        info['format'] = 'JPEG'
                                    
                                    # Live Photo 通常有对应的 MOV 文件
                                    # 检查同目录下是否有对应的视频文件
                                    video_extensions = ['.MOV', '.mov', '.MP4', '.mp4']
                                    base_name = image_path.stem
                                    
                                    for ext in video_extensions:
                                        video_path = image_path.parent / (base_name + ext)
                                        if video_path.exists():
                                            info['has_companion_video'] = True
                                            info['companion_video_path'] = str(video_path)
                                            info['companion_video_size'] = video_path.stat().st_size
                                            break
                                    else:
                                        info['has_companion_video'] = False
                                    
                                    return info
                            
                            # 检查 QuickTime 相关标签（Live Photo 的标识）
                            if tag == 'Software' and isinstance(value, str):
                                if 'iOS' in value or 'iPhone' in value:
                                    # 可能是 iPhone 拍摄的照片，检查其他标记
                                    pass
                except:
                    pass
                
                # 检查文件元数据中的 QuickTime 标识
                # HEIC 文件内部包含 QuickTime 容器，Live Photo 会有特殊标记
                if is_heic:
                    # 搜索文件中的 Live Photo 标识符
                    # Apple 使用 "com.apple.quicktime.content.identifier" 作为 Live Photo 标识
                    if b'com.apple.quicktime' in file_data or b'LivePhoto' in file_data:
                        info = {
                            'type': 'iPhone Live Photo (Possible)',
                            'is_live_photo': True,
                            'platform': 'iOS (iPhone/iPad)',
                            'format': 'HEIC',
                            'detection_method': 'File metadata'
                        }
                        
                        # 检查对应的视频文件
                        video_extensions = ['.MOV', '.mov']
                        base_name = image_path.stem
                        
                        for ext in video_extensions:
                            video_path = image_path.parent / (base_name + ext)
                            if video_path.exists():
                                info['has_companion_video'] = True
                                info['companion_video_path'] = str(video_path)
                                info['companion_video_size'] = video_path.stat().st_size
                                break
                        else:
                            info['has_companion_video'] = False
                        
                        return info
            
            return None
        except Exception as e:
            print(f"检测 iPhone Live Photo 失败: {e}")
            return None
    
    def _detect_samsung_motion_photo(self, file_data: bytes) -> Optional[dict]:
        """检测 Samsung Motion Photo。
        
        Args:
            file_data: 图片文件数据
        
        Returns:
            Motion Photo 信息字典，如果不是则返回None
        """
        try:
            # Samsung Motion Photo 在 JPG 文件末尾嵌入视频
            # 通过搜索特定的标记来检测
            
            # Samsung 使用 SEFT (Samsung Embedded File Tags)
            if b'MotionPhoto_Data' in file_data or b'SEFT' in file_data:
                info = {
                    'type': 'Samsung Motion Photo',
                    'is_live_photo': True,
                    'platform': 'Android (Samsung)',
                }
                
                # 尝试查找视频部分
                # Samsung 通常在文件末尾嵌入 MP4
                # 搜索 MP4 文件头
                mp4_signature = b'\x00\x00\x00\x1cftyp'
                if mp4_signature in file_data:
                    video_start = file_data.rfind(mp4_signature)
                    if video_start > 0:
                        info['has_embedded_video'] = True
                        info['embedded_video_format'] = 'MP4'
                        info['video_offset'] = len(file_data) - video_start
                        info['video_size'] = len(file_data) - video_start
                else:
                    # 尝试其他 MP4 签名
                    mp4_signatures = [b'ftypisom', b'ftypmp42', b'ftypMSNV']
                    for sig in mp4_signatures:
                        if sig in file_data:
                            video_start = file_data.rfind(sig) - 4  # 减去前4字节的大小字段
                            if video_start > 0:
                                info['has_embedded_video'] = True
                                info['embedded_video_format'] = 'MP4'
                                info['video_offset'] = len(file_data) - video_start
                                info['video_size'] = len(file_data) - video_start
                                break
                
                return info
            
            return None
        except Exception as e:
            print(f"检测 Samsung Motion Photo 失败: {e}")
            return None
    
    def debug_live_photo_detection(self, image_path: Path) -> dict:
        """调试实况图检测（用于开发和测试）。
        
        Args:
            image_path: 图片路径
        
        Returns:
            包含调试信息的字典
        """
        debug_info = {
            'file_size': 0,
            'has_xmp_marker': False,
            'has_ftyp_marker': False,
            'xmp_content': '',
            'ftyp_positions': [],
            'file_end_preview': '',
        }
        
        try:
            with open(image_path, 'rb') as f:
                file_data = f.read()
            
            debug_info['file_size'] = len(file_data)
            
            # 检查 XMP 标记
            if b'<x:xmpmeta' in file_data:
                debug_info['has_xmp_marker'] = True
                xmp_start = file_data.find(b'<x:xmpmeta')
                xmp_end = file_data.find(b'</x:xmpmeta>', xmp_start)
                if xmp_end > xmp_start:
                    xmp_content = file_data[xmp_start:xmp_end + 12].decode('utf-8', errors='ignore')
                    debug_info['xmp_content'] = xmp_content[:1000]  # 前1000字符
            
            # 检查 ftyp 标记（MP4 视频）
            if b'ftyp' in file_data:
                debug_info['has_ftyp_marker'] = True
                # 查找所有 ftyp 位置
                pos = 0
                while True:
                    pos = file_data.find(b'ftyp', pos)
                    if pos == -1:
                        break
                    debug_info['ftyp_positions'].append(pos)
                    pos += 4
            
            # 文件末尾预览（最后1KB）
            if len(file_data) > 1024:
                end_preview = file_data[-1024:]
                # 检查是否包含视频标记
                if b'ftyp' in end_preview or b'mdat' in end_preview or b'moov' in end_preview:
                    debug_info['file_end_preview'] = f"末尾包含可能的视频数据标记"
            
            # 检查其他 Motion Photo 标记
            debug_info['has_motion_photo_marker'] = b'MotionPhoto' in file_data
            debug_info['has_micro_video_marker'] = b'MicroVideo' in file_data
            debug_info['has_gcamera_marker'] = b'GCamera' in file_data
            
        except Exception as e:
            debug_info['error'] = str(e)
        
        return debug_info
    
    def extract_live_photo_video(self, image_path: Path, output_path: Path) -> Tuple[bool, str]:
        """从实况图中提取嵌入的视频。
        
        Args:
            image_path: 实况图路径
            output_path: 输出视频路径
        
        Returns:
            (是否成功, 消息)
        """
        try:
            from utils import format_file_size
            
            # 首先检测是否是实况图
            with open(image_path, 'rb') as f:
                file_data = f.read()
            
            live_info = self._detect_live_photo(image_path, file_data)
            if not live_info:
                return False, "这不是实况图"
            
            # iPhone Live Photo - 复制配套视频文件
            if live_info.get('has_companion_video') and live_info.get('companion_video_path'):
                import shutil
                companion_path = Path(live_info['companion_video_path'])
                if companion_path.exists():
                    shutil.copy2(companion_path, output_path)
                    return True, f"成功导出配套视频 ({format_file_size(output_path.stat().st_size)})"
                else:
                    return False, "配套视频文件不存在"
            
            # Android/Samsung Motion Photo - 提取嵌入视频
            if live_info.get('has_embedded_video') and 'video_offset' in live_info:
                video_offset = live_info['video_offset']
                video_start = len(file_data) - video_offset
                
                if video_start < 0 or video_start >= len(file_data):
                    return False, "视频偏移量无效"
                
                video_data = file_data[video_start:]
                
                # 验证视频数据
                # MP4 通常以 ftyp 开始
                if not (video_data[:4] == b'\x00\x00\x00\x18' or 
                        video_data[:4] == b'\x00\x00\x00\x1c' or
                        b'ftyp' in video_data[:20]):
                    # 尝试查找正确的视频开始位置
                    mp4_signatures = [b'\x00\x00\x00\x1cftyp', b'ftyp']
                    found = False
                    for sig in mp4_signatures:
                        if sig in video_data:
                            sig_pos = video_data.find(sig)
                            if sig == b'ftyp':
                                sig_pos -= 4  # 回退到大小字段
                            video_data = video_data[sig_pos:]
                            found = True
                            break
                    
                    if not found:
                        return False, "无法找到有效的视频数据"
                
                # 写入视频文件
                with open(output_path, 'wb') as f:
                    f.write(video_data)
                
                return True, f"成功提取嵌入视频 ({format_file_size(len(video_data))})"
            
            return False, "此实况图不包含可提取的视频"
        
        except Exception as e:
            return False, f"提取视频失败: {e}"
    
    def create_motion_photo(
        self, 
        cover_image_path: Path, 
        video_data: bytes, 
        output_path: Path,
        photo_type: str = "Google Motion Photo"
    ) -> Tuple[bool, str]:
        """创建 Motion Photo（实况图）。
        
        支持 Google Motion Photo 和 Samsung Motion Photo 格式。
        
        Args:
            cover_image_path: 封面图片路径（JPEG）
            video_data: 视频数据（MP4格式）
            output_path: 输出实况图路径
            photo_type: 实况图类型 ("Google Motion Photo" 或 "Samsung Motion Photo")
        
        Returns:
            (是否成功, 消息)
        """
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            import io
            
            # 读取封面图片
            with Image.open(cover_image_path) as img:
                # 确保是 RGB 模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 保存原始 EXIF 数据
                exif_data = img.info.get('exif', b'')
                
                # 创建临时 JPEG
                jpeg_buffer = io.BytesIO()
                
                # 保存为 JPEG（不包含视频）
                save_kwargs = {'format': 'JPEG', 'quality': 95}
                if exif_data:
                    save_kwargs['exif'] = exif_data
                
                img.save(jpeg_buffer, **save_kwargs)
                jpeg_data = jpeg_buffer.getvalue()
            
            # 验证视频数据是 MP4 格式
            if not (b'ftyp' in video_data[:32] or 
                    video_data[:4] in [b'\x00\x00\x00\x18', b'\x00\x00\x00\x1c']):
                return False, "视频数据不是有效的 MP4 格式"
            
            # 计算视频偏移量
            video_offset = len(video_data)
            
            # 构建 XMP 元数据
            xmp_metadata = self._build_motion_photo_xmp(video_offset, photo_type)
            
            # 将 XMP 插入到 JPEG 中
            jpeg_with_xmp = self._inject_xmp_into_jpeg(jpeg_data, xmp_metadata)
            
            # 合并 JPEG 和视频数据
            final_data = jpeg_with_xmp + video_data
            
            # 写入输出文件
            with open(output_path, 'wb') as f:
                f.write(final_data)
            
            from utils import format_file_size
            file_size = format_file_size(len(final_data))
            
            return True, f"成功创建 {photo_type} ({file_size})"
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"创建实况图失败: {e}"
    
    def _build_motion_photo_xmp(self, video_offset: int, photo_type: str = "Google Motion Photo") -> str:
        """构建 Motion Photo 的 XMP 元数据。
        
        Args:
            video_offset: 视频数据偏移量（从文件末尾算起）
            photo_type: 实况图类型
        
        Returns:
            XMP 元数据字符串
        """
        import datetime
        
        # 生成时间戳（微秒）
        timestamp_us = int(datetime.datetime.now().timestamp() * 1000000)
        
        if photo_type == "Samsung Motion Photo":
            # Samsung Motion Photo XMP 格式
            xmp = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.0-jc003">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/"
        xmlns:Container="http://ns.google.com/photos/1.0/container/"
        xmlns:Item="http://ns.google.com/photos/1.0/container/item/"
        GCamera:MicroVideo="1"
        GCamera:MicroVideoVersion="1"
        GCamera:MicroVideoOffset="{video_offset}"
        GCamera:MicroVideoPresentationTimestampUs="{timestamp_us}"
        Container:Version="1"
        Container:Directory>
      <rdf:Seq>
        <rdf:li rdf:parseType="Resource">
          <Container:Item
            Item:Semantic="Primary"
            Item:Mime="image/jpeg"/>
        </rdf:li>
        <rdf:li rdf:parseType="Resource">
          <Container:Item
            Item:Semantic="MotionPhoto"
            Item:Mime="video/mp4"
            Item:Length="{video_offset}"/>
        </rdf:li>
      </rdf:Seq>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
        else:
            # Google Motion Photo XMP 格式（默认）
            xmp = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.0-jc003">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/"
        xmlns:Container="http://ns.google.com/photos/1.0/container/"
        xmlns:Item="http://ns.google.com/photos/1.0/container/item/"
        GCamera:MotionPhoto="1"
        GCamera:MotionPhotoVersion="1"
        GCamera:MotionPhotoPresentationTimestampUs="{timestamp_us}"
        GCamera:MicroVideo="1"
        GCamera:MicroVideoVersion="1"
        GCamera:MicroVideoOffset="{video_offset}"
        Container:Version="1">
      <Container:Directory>
        <rdf:Seq>
          <rdf:li rdf:parseType="Resource">
            <Container:Item
              Item:Semantic="Primary"
              Item:Mime="image/jpeg"/>
          </rdf:li>
          <rdf:li rdf:parseType="Resource">
            <Container:Item
              Item:Semantic="MotionPhoto"
              Item:Mime="video/mp4"
              Item:Length="{video_offset}"/>
          </rdf:li>
        </rdf:Seq>
      </Container:Directory>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
        
        return xmp
    
    def _inject_xmp_into_jpeg(self, jpeg_data: bytes, xmp_metadata: str) -> bytes:
        """将 XMP 元数据注入到 JPEG 文件中。
        
        Args:
            jpeg_data: 原始 JPEG 数据
            xmp_metadata: XMP 元数据字符串
        
        Returns:
            包含 XMP 的 JPEG 数据
        """
        # JPEG 文件结构：
        # SOI (FF D8) + [Segments] + EOI (FF D9)
        # APP1 段格式：FF E1 + 长度(2字节) + "http://ns.adobe.com/xap/1.0/\0" + XMP数据
        
        # 检查是否是有效的 JPEG
        if len(jpeg_data) < 2 or jpeg_data[:2] != b'\xff\xd8':
            raise ValueError("不是有效的 JPEG 文件")
        
        # XMP 命名空间标识符
        xmp_namespace = b'http://ns.adobe.com/xap/1.0/\x00'
        
        # 将 XMP 字符串转换为字节
        xmp_bytes = xmp_metadata.encode('utf-8')
        
        # 构建 APP1 段
        # APP1 标记 (FF E1) + 长度(2字节, 包括长度字段本身) + 命名空间 + XMP数据
        app1_data = xmp_namespace + xmp_bytes
        app1_length = len(app1_data) + 2  # +2 for length field itself
        
        if app1_length > 0xFFFF:
            raise ValueError("XMP 数据太大，超过 APP1 段最大长度")
        
        # 构建完整的 APP1 段
        app1_segment = b'\xff\xe1' + app1_length.to_bytes(2, 'big') + app1_data
        
        # 在 SOI 之后插入 APP1 段
        # 通常 APP1 段应该在 SOI 之后立即出现
        result = jpeg_data[:2] + app1_segment + jpeg_data[2:]
        
        return result


class BackgroundRemover:
    """背景移除器类。
    
    使用ONNX模型进行图像背景移除。
    """
    
    def __init__(self, model_path: Path) -> None:
        """初始化背景移除器。
        
        Args:
            model_path: ONNX模型路径
        """
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("需要安装 onnxruntime 库。请运行: pip install onnxruntime")
        
        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        # 设置日志级别为 ERROR，抑制警告信息
        ort.set_default_logger_severity(3)  # 0=Verbose, 1=Info, 2=Warning, 3=Error, 4=Fatal
        
        # 配置会话选项，启用内存优化
        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = True   # 启用内存模式优化
        sess_options.enable_mem_reuse = True     # 启用内存重用
        sess_options.enable_cpu_mem_arena = True # 启用CPU内存池
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.log_severity_level = 3      # 设置会话日志级别为 ERROR
        
        try:
            self.sess = ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=['CPUExecutionProvider']  # 只使用CPU
            )
        except Exception as e:
            raise RuntimeError(f"加载ONNX模型失败: {e}")
        
        self.input_name: str = self.sess.get_inputs()[0].name
        self.output_name: str = self.sess.get_outputs()[0].name
        self.model_input_size: Tuple[int, int] = (1024, 1024)
    
    def _preprocess_image(self, im: np.ndarray, model_input_size: Tuple[int, int]) -> np.ndarray:
        """预处理图像，优化内存使用和性能。
        
        Args:
            im: 输入图像数组
            model_input_size: 模型输入尺寸
        
        Returns:
            预处理后的图像张量
        """
        if len(im.shape) < 3:
            im = im[:, :, np.newaxis]
        
        # 直接使用 cv2.resize，避免多次转换
        resized_im = cv2.resize(im, (model_input_size[1], model_input_size[0]))
        
        # 一次性完成类型转换、归一化和维度变换
        im_tensor = resized_im.astype(np.float32).transpose(2, 0, 1) / 255.0
        
        # 归一化
        im_tensor = (im_tensor - 0.5) / 0.5
        
        # 添加批次维度
        return np.expand_dims(im_tensor, axis=0)
    
    def _postprocess_image(self, result: np.ndarray, im_size: Tuple[int, int]) -> np.ndarray:
        """后处理图像，优化性能。
        
        Args:
            result: 模型输出结果
            im_size: 原始图像尺寸
        
        Returns:
            处理后的掩码图像
        """
        # 如果是3维或4维，取第一个通道作为掩码
        if len(result.shape) > 2:
            if len(result.shape) == 4:  # [B, C, H, W]
                result = result[0, 0]  # 取第一个批次的第一个通道
            elif len(result.shape) == 3:  # [C, H, W]
                result = result[0]  # 取第一个通道
        
        # 确保结果在有效范围内并转换类型
        result_image = np.clip(result * 255, 0, 255).astype(np.uint8)
        
        # 调整图像大小 - 掩码应该是2D的
        if result_image.shape != im_size:
            result_image = cv2.resize(result_image, (im_size[1], im_size[0]))
        
        return result_image
    
    def _clear_memory(self) -> None:
        """清理内存。"""
        try:
            # 强制垃圾回收
            gc.collect()
        except Exception:
            pass  # 静默处理清理异常
    
    def remove_background(self, image: Image.Image) -> Image.Image:
        """处理图像并去除背景，返回RGBA格式的PIL图像。
        
        Args:
            image: 输入的PIL图像
        
        Returns:
            去除背景后的RGBA图像
        """
        try:
            if image.mode != "RGB":
                orig_im = image.convert("RGB")
            else:
                orig_im = image
            
            orig_im_size = orig_im.size[::-1]  # PIL size 是 (width, height)，需要反转为 (height, width)
            
            # 将 PIL 图像转换为 numpy 数组
            image_np = np.array(orig_im)
            
            # 预处理图像
            image_tensor = self._preprocess_image(image_np, self.model_input_size)
            
            # 模型推理
            try:
                result = self.sess.run([self.output_name], {self.input_name: image_tensor})[0]
            except Exception as e:
                raise RuntimeError(f"模型推理失败: {e}")
            
            # 后处理图像
            mask = self._postprocess_image(result, orig_im_size)
            
            # 创建RGBA图像
            rgba_image = Image.new("RGBA", orig_im.size)
            rgba_image.paste(orig_im, (0, 0))
            
            # 应用掩码
            mask_pil = Image.fromarray(mask, mode='L')
            rgba_image.putalpha(mask_pil)
            
            return rgba_image
        finally:
            # 确保每次处理后都清理内存
            self._clear_memory()
    
    def remove_background_batch(self, images: list[Image.Image]) -> list[Image.Image]:
        """批量处理多个图像。
        
        Args:
            images: 输入的PIL图像列表
        
        Returns:
            去除背景后的RGBA图像列表
        """
        results = []
        try:
            for img in images:
                # 单独处理每张图片
                if img.mode != "RGB":
                    orig_im = img.convert("RGB")
                else:
                    orig_im = img
                
                orig_im_size = orig_im.size[::-1]
                image_np = np.array(orig_im)
                image_tensor = self._preprocess_image(image_np, self.model_input_size)
                
                try:
                    result = self.sess.run([self.output_name], {self.input_name: image_tensor})[0]
                except Exception as e:
                    raise RuntimeError(f"模型推理失败: {e}")
                
                mask = self._postprocess_image(result, orig_im_size)
                rgba_image = Image.new("RGBA", orig_im.size)
                rgba_image.paste(orig_im, (0, 0))
                mask_pil = Image.fromarray(mask, mode='L')
                rgba_image.putalpha(mask_pil)
                results.append(rgba_image)
                
                # 每处理一张图片后进行一次轻量级清理
                gc.collect()
        finally:
            # 批量处理完成后进行完整的内存清理
            self._clear_memory()
        
        return results

