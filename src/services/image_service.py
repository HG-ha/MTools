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
from typing import Optional, Tuple

import cv2
import numpy as np
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
                                try:
                                    value = value.decode('utf-8', errors='ignore')
                                except:
                                    value = str(value)
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
                
                return info
        except Exception as e:
            return {'error': str(e)}
    
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

