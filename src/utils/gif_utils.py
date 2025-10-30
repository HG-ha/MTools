# -*- coding: utf-8 -*-
"""GIF 工具模块。

提供 GIF 动图处理的通用功能。
"""

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image


class GifUtils:
    """GIF 工具类。
    
    提供 GIF 动图相关的通用功能：
    - 检测是否为动态 GIF
    - 获取帧数和帧信息
    - 提取指定帧
    - 帧预览等
    """
    
    @staticmethod
    def is_animated_gif(image_path: Path) -> bool:
        """检测图片是否为动态 GIF。
        
        Args:
            image_path: 图片路径
        
        Returns:
            是否为动态 GIF
        """
        try:
            with Image.open(image_path) as img:
                # 检查是否为 GIF 格式且有多帧
                if img.format != 'GIF':
                    return False
                
                # 尝试跳到第二帧
                img.seek(1)
                return True
        except (EOFError, AttributeError):
            # EOFError: 只有一帧
            # AttributeError: 不支持 seek 操作
            return False
        except Exception:
            return False
    
    @staticmethod
    def get_frame_count(image_path: Path) -> int:
        """获取 GIF 的帧数。
        
        Args:
            image_path: 图片路径
        
        Returns:
            帧数，非 GIF 或静态 GIF 返回 1
        """
        try:
            with Image.open(image_path) as img:
                if img.format != 'GIF':
                    return 1
                
                frame_count = 0
                try:
                    while True:
                        img.seek(frame_count)
                        frame_count += 1
                except EOFError:
                    pass
                
                return max(frame_count, 1)
        except Exception:
            return 1
    
    @staticmethod
    def extract_frame(image_path: Path, frame_index: int = 0) -> Optional[Image.Image]:
        """提取 GIF 的指定帧。
        
        Args:
            image_path: 图片路径
            frame_index: 帧索引（从0开始）
        
        Returns:
            提取的帧（PIL Image），失败返回 None
        """
        try:
            img = Image.open(image_path)
            
            # 跳到指定帧
            try:
                img.seek(frame_index)
            except EOFError:
                # 帧索引超出范围，使用第一帧
                img.seek(0)
            
            # 转换为 RGBA 模式以保留透明度
            if img.mode != 'RGBA':
                frame = img.convert('RGBA')
            else:
                frame = img.copy()
            
            return frame
        except Exception as e:
            print(f"提取帧失败: {e}")
            return None
    
    @staticmethod
    def get_first_non_empty_frame(image_path: Path) -> Tuple[Optional[Image.Image], int]:
        """获取第一个不为空的帧。
        
        Args:
            image_path: 图片路径
        
        Returns:
            (帧图像, 帧索引)，失败返回 (None, 0)
        """
        try:
            with Image.open(image_path) as img:
                frame_count = GifUtils.get_frame_count(image_path)
                
                for i in range(frame_count):
                    try:
                        img.seek(i)
                        # 检查帧是否有实际内容（非全透明）
                        frame = img.convert('RGBA')
                        # 简单检查：获取边界框
                        bbox = frame.getbbox()
                        if bbox:  # 有内容
                            return frame.copy(), i
                    except Exception:
                        continue
                
                # 没找到非空帧，返回第一帧
                img.seek(0)
                return img.convert('RGBA').copy(), 0
        except Exception as e:
            print(f"获取第一个非空帧失败: {e}")
            return None, 0
    
    @staticmethod
    def extract_all_frames(image_path: Path) -> List[Image.Image]:
        """提取 GIF 的所有帧。
        
        Args:
            image_path: 图片路径
        
        Returns:
            所有帧的列表
        """
        frames = []
        try:
            with Image.open(image_path) as img:
                frame_count = GifUtils.get_frame_count(image_path)
                
                for i in range(frame_count):
                    try:
                        img.seek(i)
                        # 转换为 RGBA 并复制
                        frame = img.convert('RGBA').copy()
                        frames.append(frame)
                    except Exception:
                        continue
        except Exception as e:
            print(f"提取所有帧失败: {e}")
        
        return frames
    
    @staticmethod
    def get_frame_durations(image_path: Path) -> List[int]:
        """获取 GIF 每帧的持续时间（毫秒）。
        
        Args:
            image_path: 图片路径
        
        Returns:
            每帧持续时间的列表（毫秒）
        """
        durations = []
        try:
            with Image.open(image_path) as img:
                frame_count = GifUtils.get_frame_count(image_path)
                
                for i in range(frame_count):
                    try:
                        img.seek(i)
                        # 获取帧持续时间，默认 100ms
                        duration = img.info.get('duration', 100)
                        durations.append(duration)
                    except Exception:
                        durations.append(100)  # 默认值
        except Exception as e:
            print(f"获取帧持续时间失败: {e}")
        
        return durations
    
    @staticmethod
    def load_frames_with_metadata(image_path: Path) -> Tuple[List[Image.Image], List[int], int]:
        """加载 GIF 的所有帧及元数据。
        
        Args:
            image_path: GIF 图片路径
        
        Returns:
            (帧列表, 持续时间列表, 循环次数)
        """
        frames: List[Image.Image] = []
        durations: List[int] = []
        loop: int = 0
        try:
            with Image.open(image_path) as img:
                frame_count = GifUtils.get_frame_count(image_path)
                loop = int(img.info.get('loop', 0) or 0)
                for index in range(frame_count):
                    try:
                        img.seek(index)
                        frame = img.convert('RGBA').copy()
                        duration = int(img.info.get('duration', 100) or 100)
                        frames.append(frame)
                        # GIF 格式最小单位是 10ms，保持原始值
                        durations.append(max(duration, 10))
                    except Exception:
                        continue
        except Exception as exc:  # pragma: no cover - 日志输出
            print(f"加载 GIF 元数据失败: {exc}")
        return frames, durations, loop
    
    @staticmethod
    def save_frames_to_gif(
        frames: List[Image.Image],
        durations: List[int],
        output_path: Path,
        loop: int = 0
    ) -> bool:
        """将帧序列保存为 GIF 文件。
        
        Args:
            frames: 帧图像列表
            durations: 每帧持续时间（毫秒）
            output_path: 输出 GIF 路径
            loop: 循环次数（0 表示无限循环）
        
        Returns:
            是否保存成功
        """
        if not frames:
            return False
        # 确保持续时间数量与帧一致
        if len(durations) != len(frames):
            durations = [durations[0]] * len(frames) if durations else [100] * len(frames)
        try:
            first_frame = frames[0]
            append_frames = frames[1:]
            first_frame.save(
                output_path,
                save_all=True,
                append_images=append_frames,
                duration=durations,
                loop=loop,
                disposal=2,
                optimize=True,
            )
            return True
        except Exception as exc:  # pragma: no cover - 日志输出
            print(f"保存 GIF 失败: {exc}")
            return False
    
    @staticmethod
    def save_frame_as_image(
        image_path: Path,
        output_path: Path,
        frame_index: int = 0,
        quality: int = 95
    ) -> bool:
        """将 GIF 的指定帧保存为静态图片。
        
        Args:
            image_path: 源 GIF 路径
            output_path: 输出图片路径
            frame_index: 帧索引
            quality: 输出质量（仅适用于 JPEG）
        
        Returns:
            是否成功
        """
        try:
            frame = GifUtils.extract_frame(image_path, frame_index)
            if frame is None:
                return False
            
            # 根据输出格式处理
            ext = output_path.suffix.lower()
            
            if ext in ['.jpg', '.jpeg']:
                # JPEG 不支持透明度，转换为 RGB
                if frame.mode == 'RGBA':
                    # 创建白色背景
                    background = Image.new('RGB', frame.size, (255, 255, 255))
                    background.paste(frame, mask=frame.split()[-1])
                    frame = background
                frame.save(output_path, quality=quality, optimize=True)
            elif ext == '.png':
                frame.save(output_path, optimize=True)
            elif ext == '.webp':
                frame.save(output_path, quality=quality, optimize=True)
            else:
                frame.save(output_path)
            
            return True
        except Exception as e:
            print(f"保存帧失败: {e}")
            return False
    
    @staticmethod
    def create_gif_from_frames(
        frames: List[Image.Image],
        output_path: Path,
        duration: int = 100,
        loop: int = 0
    ) -> bool:
        """从帧列表创建 GIF。
        
        Args:
            frames: 帧图像列表
            output_path: 输出 GIF 路径
            duration: 每帧持续时间（毫秒）
            loop: 循环次数（0表示无限循环）
        
        Returns:
            是否成功
        """
        try:
            if not frames:
                return False
            
            # 保存为 GIF
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=loop,
                optimize=True
            )
            return True
        except Exception as e:
            print(f"创建 GIF 失败: {e}")
            return False

