# -*- coding: utf-8 -*-
"""证件照处理服务模块。

提供 AI 证件照生成功能，整合背景移除、人脸检测、美颜等处理。
参考 HivisionIDPhotos 项目实现。
"""

import gc
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Callable, TYPE_CHECKING

import cv2
import numpy as np
from PIL import Image

from constants import (
    BACKGROUND_REMOVAL_MODELS,
    FACE_DETECTION_MODELS,
    DEFAULT_MODEL_KEY,
    DEFAULT_FACE_DETECTION_MODEL_KEY,
)
from utils import logger

if TYPE_CHECKING:
    from services import ConfigService
    from services.face_detection_service import FaceDetector


@dataclass
class IDPhotoParams:
    """证件照参数。
    
    Attributes:
        size: 输出尺寸 (高度, 宽度)
        change_bg_only: 是否只换底（不裁剪）
        head_measure_ratio: 头部面积占图像比例
        head_height_ratio: 头部中心在图像高度的比例
        head_top_range: 头顶距离范围 (max, min)
        whitening_strength: 美白强度 (0-30)
        brightness_strength: 亮度强度 (-20 to 20)
        contrast_strength: 对比度强度 (-100 to 100)
        sharpen_strength: 锐化强度 (0-5)
        saturation_strength: 饱和度强度 (-100 to 100)
        face_alignment: 是否进行人脸矫正
    """
    size: Tuple[int, int] = (413, 295)  # (height, width)
    change_bg_only: bool = False
    head_measure_ratio: float = 0.2
    head_height_ratio: float = 0.45
    head_top_range: Tuple[float, float] = (0.12, 0.1)
    whitening_strength: int = 0
    brightness_strength: int = 0
    contrast_strength: int = 0
    sharpen_strength: int = 0
    saturation_strength: int = 0
    face_alignment: bool = False


@dataclass
class IDPhotoResult:
    """证件照处理结果。
    
    Attributes:
        standard: 标准尺寸证件照 (RGBA)
        hd: 高清证件照 (RGBA)
        matting: 抠图结果 (RGBA)
        layout: 排版照 (RGB)，用于打印
    """
    standard: np.ndarray
    hd: np.ndarray
    matting: np.ndarray
    layout: Optional[np.ndarray] = None


class IDPhotoService:
    """证件照处理服务。
    
    整合背景移除、人脸检测和美颜功能，生成标准证件照。
    """
    
    def __init__(self, config_service: Optional['ConfigService'] = None) -> None:
        """初始化证件照服务。
        
        Args:
            config_service: 配置服务实例
        """
        self.config_service = config_service
        self.bg_remover = None
        self.face_detector: Optional['FaceDetector'] = None
        
        # 当前选择的背景移除模型
        self.current_bg_model_key: str = DEFAULT_MODEL_KEY
        
        # 美白 LUT
        self._whitening_lut = None
    
    def _get_model_path(self, model_type: str, model_key: str = None) -> Path:
        """获取模型文件路径。
        
        Args:
            model_type: 模型类型 ("background" 或 "face")
            model_key: 模型键名（仅对 background 有效）
        
        Returns:
            模型文件路径
        """
        if self.config_service:
            data_dir = self.config_service.get_data_dir()
        else:
            from utils.file_utils import get_app_root
            data_dir = get_app_root() / "storage" / "data"
        
        if model_type == "background":
            key = model_key or self.current_bg_model_key or DEFAULT_MODEL_KEY
            model_info = BACKGROUND_REMOVAL_MODELS[key]
            return data_dir / "models" / "background_removal" / model_info.version / model_info.filename
        elif model_type == "face":
            model_key = DEFAULT_FACE_DETECTION_MODEL_KEY
            model_info = FACE_DETECTION_MODELS[model_key]
            return data_dir / "models" / "face_detection" / model_info.version / model_info.filename
        else:
            raise ValueError(f"未知模型类型: {model_type}")
    
    def is_background_model_loaded(self) -> bool:
        """检查背景移除模型是否已加载。"""
        return self.bg_remover is not None
    
    def is_face_model_loaded(self) -> bool:
        """检查人脸检测模型是否已加载。"""
        return self.face_detector is not None
    
    def is_background_model_exists(self) -> bool:
        """检查背景移除模型文件是否存在。"""
        return self._get_model_path("background").exists()
    
    def is_face_model_exists(self) -> bool:
        """检查人脸检测模型文件是否存在。"""
        return self._get_model_path("face").exists()
    
    def load_background_model(self, model_key: str = None) -> None:
        """加载背景移除模型。
        
        Args:
            model_key: 模型键名，如果不指定则使用当前选择的模型
        """
        from services.image_service import BackgroundRemover
        
        if model_key:
            self.current_bg_model_key = model_key
        
        model_path = self._get_model_path("background", self.current_bg_model_key)
        if not model_path.exists():
            raise FileNotFoundError(f"背景移除模型不存在: {model_path}")
        
        self.bg_remover = BackgroundRemover(model_path, config_service=self.config_service)
        logger.info(f"背景移除模型已加载: {self.current_bg_model_key}")
    
    def load_face_model(self) -> None:
        """加载人脸检测模型。"""
        from services.face_detection_service import FaceDetector
        
        model_path = self._get_model_path("face")
        if not model_path.exists():
            raise FileNotFoundError(f"人脸检测模型不存在: {model_path}")
        
        self.face_detector = FaceDetector(model_path, config_service=self.config_service)
        logger.info("人脸检测模型已加载")
    
    def unload_background_model(self) -> None:
        """卸载背景移除模型。"""
        if self.bg_remover:
            del self.bg_remover
            self.bg_remover = None
            gc.collect()
            logger.info("背景移除模型已卸载")
    
    def unload_face_model(self) -> None:
        """卸载人脸检测模型。"""
        if self.face_detector:
            del self.face_detector
            self.face_detector = None
            gc.collect()
            logger.info("人脸检测模型已卸载")
    
    def unload_all_models(self) -> None:
        """卸载所有模型。"""
        self.unload_background_model()
        self.unload_face_model()
    
    def get_device_info(self) -> str:
        """获取设备信息。"""
        devices = []
        if self.bg_remover:
            devices.append(f"背景移除: {self.bg_remover.get_device_info()}")
        if self.face_detector:
            devices.append(f"人脸检测: {self.face_detector.get_device_info()}")
        return " | ".join(devices) if devices else "模型未加载"
    
    @staticmethod
    def resize_image_esp(image: np.ndarray, esp: int = 2000) -> np.ndarray:
        """将图像缩放到最大边长。
        
        Args:
            image: 输入图像
            esp: 最大边长
        
        Returns:
            缩放后的图像
        """
        height, width = image.shape[:2]
        max_dim = max(height, width)
        
        if max_dim > esp:
            if height >= width:
                new_height = esp
                new_width = int((esp / height) * width)
            else:
                new_width = esp
                new_height = int((esp / width) * height)
            
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        return image
    
    def remove_background(self, image: Image.Image) -> Image.Image:
        """移除图像背景。
        
        Args:
            image: PIL 图像
        
        Returns:
            带透明背景的 PIL 图像
        """
        if not self.bg_remover:
            raise RuntimeError("背景移除模型未加载")
        
        return self.bg_remover.remove_background(image)
    
    def detect_face(self, image: np.ndarray) -> Optional[dict]:
        """检测人脸。
        
        Args:
            image: BGR 格式的 numpy 数组
        
        Returns:
            人脸信息字典，包含 rectangle 和 roll_angle
        """
        if not self.face_detector:
            raise RuntimeError("人脸检测模型未加载")
        
        result = self.face_detector.detect_single(image)
        if result is None:
            return None
        
        return {
            "rectangle": result.rectangle,
            "roll_angle": result.roll_angle,
            "landmarks": result.landmarks,
            "confidence": result.confidence,
        }
    
    @staticmethod
    def apply_whitening(image: np.ndarray, strength: int) -> np.ndarray:
        """应用美白效果。
        
        Args:
            image: BGR 格式图像
            strength: 美白强度 (0-30)
        
        Returns:
            美白后的图像
        """
        if strength <= 0:
            return image
        
        # 使用简化的美白算法
        strength = min(strength, 30)
        
        # 转换到 LAB 色彩空间
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # 提高亮度通道
        l_float = l.astype(np.float32)
        l_enhanced = l_float + (strength / 30.0) * 20
        l_enhanced = np.clip(l_enhanced, 0, 255).astype(np.uint8)
        
        # 合并通道
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        
        # 混合原图和增强图
        alpha = strength / 30.0
        blended = cv2.addWeighted(image, 1 - alpha * 0.5, result, alpha * 0.5, 0)
        
        return blended
    
    @staticmethod
    def apply_brightness_contrast_sharpen_saturation(
        image: np.ndarray,
        brightness: int = 0,
        contrast: int = 0,
        sharpen: int = 0,
        saturation: int = 0
    ) -> np.ndarray:
        """应用亮度、对比度、锐化和饱和度调整。
        
        Args:
            image: BGR 格式图像
            brightness: 亮度 (-20 to 20)
            contrast: 对比度 (-100 to 100)
            sharpen: 锐化 (0-5)
            saturation: 饱和度 (-100 to 100)
        
        Returns:
            调整后的图像
        """
        if brightness == 0 and contrast == 0 and sharpen == 0 and saturation == 0:
            return image.copy()
        
        result = image.copy()
        
        # 饱和度调整
        if saturation != 0:
            hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            s = s.astype(np.float32)
            s = s + s * (saturation / 100.0)
            s = np.clip(s, 0, 255).astype(np.uint8)
            hsv = cv2.merge([h, s, v])
            result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # 亮度和对比度
        alpha = 1.0 + (contrast / 100.0)
        beta = brightness
        result = cv2.convertScaleAbs(result, alpha=alpha, beta=beta)
        
        # 锐化
        if sharpen > 0:
            sharpen_scaled = sharpen * 20
            kernel_strength = 1 + (sharpen_scaled / 500)
            kernel = np.array([[-0.5, -0.5, -0.5], [-0.5, 5, -0.5], [-0.5, -0.5, -0.5]]) * kernel_strength
            sharpened = cv2.filter2D(result, -1, kernel)
            sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
            alpha = sharpen_scaled / 200
            result = cv2.addWeighted(result, 1 - alpha, sharpened, alpha, 0)
        
        return result
    
    @staticmethod
    def get_box(
        image: np.ndarray,
        model: int = 1,
        thresh: int = 127
    ) -> Tuple[int, int, int, int]:
        """获取图像中最大连续非透明区域的边界。
        
        Args:
            image: RGBA 格式图像
            model: 返回模式 (1: 坐标, 2: 边距)
            thresh: 二值化阈值
        
        Returns:
            model=1: (y_up, y_down, x_left, x_right)
            model=2: (y_top_margin, y_bottom_margin, x_left_margin, x_right_margin)
        """
        if len(cv2.split(image)) != 4:
            raise ValueError("图像必须是 RGBA 格式")
        
        _, _, _, mask = cv2.split(image)
        _, mask = cv2.threshold(mask, thresh=thresh, maxval=255, type=0)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            height, width = image.shape[:2]
            if model == 1:
                return (0, height, 0, width)
            else:
                return (0, 0, 0, 0)
        
        # 找最大轮廓
        contours_area = [cv2.contourArea(cnt) for cnt in contours]
        idx = contours_area.index(max(contours_area))
        x, y, w, h = cv2.boundingRect(contours[idx])
        
        height, width = image.shape[:2]
        y_up = y
        y_down = y + h
        x_left = x
        x_right = x + w
        
        if model == 1:
            return (y_up, y_down, x_left, x_right)
        else:
            return (y_up, height - y_down, x_left, width - x_right)
    
    @staticmethod
    def detect_distance(value: int, crop_height: int, max_ratio: float = 0.12, min_ratio: float = 0.1) -> Tuple[int, int]:
        """检测头顶距离是否合适。
        
        Args:
            value: 头顶距离
            crop_height: 裁剪高度
            max_ratio: 最大比例
            min_ratio: 最小比例
        
        Returns:
            (status, move_value)
            status: 0=不动, 1=向上移动, -1=向下移动
        """
        ratio = value / crop_height
        if min_ratio <= ratio <= max_ratio:
            return 0, 0
        elif ratio > max_ratio:
            move_value = int((ratio - max_ratio) * crop_height)
            return 1, move_value
        else:
            move_value = int((min_ratio - ratio) * crop_height)
            return -1, move_value
    
    @staticmethod
    def idphoto_cut(x1: int, y1: int, x2: int, y2: int, img: np.ndarray) -> np.ndarray:
        """滑动裁剪。
        
        Args:
            x1, y1, x2, y2: 裁剪框坐标
            img: RGBA 图像
        
        Returns:
            裁剪后的图像
        """
        crop_size = (y2 - y1, x2 - x1)
        
        temp_x_1, temp_y_1, temp_x_2, temp_y_2 = 0, 0, 0, 0
        
        if y1 < 0:
            temp_y_1 = abs(y1)
            y1 = 0
        if y2 > img.shape[0]:
            temp_y_2 = y2 - img.shape[0]
            y2 = img.shape[0]
        if x1 < 0:
            temp_x_1 = abs(x1)
            x1 = 0
        if x2 > img.shape[1]:
            temp_x_2 = x2 - img.shape[1]
            x2 = img.shape[1]
        
        # 生成透明背景
        background_bgr = np.full((crop_size[0], crop_size[1]), 255, dtype=np.uint8)
        background_a = np.full((crop_size[0], crop_size[1]), 0, dtype=np.uint8)
        background = cv2.merge((background_bgr, background_bgr, background_bgr, background_a))
        
        background[
            temp_y_1:crop_size[0] - temp_y_2,
            temp_x_1:crop_size[1] - temp_x_2
        ] = img[y1:y2, x1:x2]
        
        return background
    
    @staticmethod
    def move_to_bottom(image: np.ndarray) -> Tuple[np.ndarray, int]:
        """将图像内容移动到底部。
        
        Args:
            image: RGBA 图像
        
        Returns:
            (移动后的图像, 移动的距离)
        """
        height, width, channels = image.shape
        y_low, y_high, _, _ = IDPhotoService.get_box(image, model=2)
        
        if y_high <= 0:
            return image, 0
        
        base = np.zeros((y_high, width, channels), dtype=np.uint8)
        result = image[0:height - y_high, :, :]
        result = np.concatenate((base, result), axis=0)
        
        return result, y_high
    
    @staticmethod
    def standard_photo_resize(image: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """调整到标准尺寸。
        
        Args:
            image: 输入图像
            size: 目标尺寸 (height, width)
        
        Returns:
            调整后的图像
        """
        resize_ratio = image.shape[0] / size[0]
        resize_item = int(round(resize_ratio))
        
        if resize_ratio >= 2:
            result = image
            for i in range(resize_item - 1):
                new_size = (size[1] * (resize_item - i - 1), size[0] * (resize_item - i - 1))
                result = cv2.resize(result, new_size, interpolation=cv2.INTER_AREA)
        else:
            result = cv2.resize(image, (size[1], size[0]), interpolation=cv2.INTER_AREA)
        
        return result
    
    @staticmethod
    def resize_image_by_min(image: np.ndarray, esp: int = 600) -> Tuple[np.ndarray, float]:
        """将图像缩放到最短边至少为 esp。
        
        Args:
            image: 输入图像
            esp: 最短边最小值
        
        Returns:
            (缩放后的图像, 缩放比例)
        """
        height, width = image.shape[:2]
        min_border = min(height, width)
        
        if min_border < esp:
            if height >= width:
                new_width = esp
                new_height = height * esp // width
            else:
                new_height = esp
                new_width = width * esp // height
            
            return (
                cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA),
                new_height / height
            )
        
        return image, 1.0
    
    def adjust_photo(
        self,
        matting_image: np.ndarray,
        face_rect: Tuple[float, float, float, float],
        params: IDPhotoParams
    ) -> Tuple[np.ndarray, np.ndarray]:
        """调整照片到证件照规格。
        
        Args:
            matting_image: 抠图结果 (RGBA)
            face_rect: 人脸矩形 (x, y, width, height)
            params: 证件照参数
        
        Returns:
            (高清照, 标准照)
        """
        standard_size = params.size
        x, y, w, h = face_rect
        height, width = matting_image.shape[:2]
        width_height_ratio = standard_size[0] / standard_size[1]
        
        # 计算裁剪参数
        face_center = (x + w / 2, y + h / 2)
        face_measure = w * h
        crop_measure = face_measure / params.head_measure_ratio
        resize_ratio = crop_measure / (standard_size[0] * standard_size[1])
        resize_ratio_single = math.sqrt(resize_ratio)
        crop_size = (
            int(standard_size[0] * resize_ratio_single),
            int(standard_size[1] * resize_ratio_single),
        )
        
        # 裁剪框定位
        x1 = int(face_center[0] - crop_size[1] / 2)
        y1 = int(face_center[1] - crop_size[0] * params.head_height_ratio)
        y2 = y1 + crop_size[0]
        x2 = x1 + crop_size[1]
        
        # 第一轮裁剪
        cut_image = self.idphoto_cut(x1, y1, x2, y2, matting_image)
        cut_image = cv2.resize(cut_image, (crop_size[1], crop_size[0]))
        
        # 获取边界信息
        y_top, y_bottom, x_left, x_right = self.get_box(cut_image.astype(np.uint8), model=2)
        
        # 调整位置
        if x_left > 0 or x_right > 0:
            cut_value_top = int(((x_left + x_right) * width_height_ratio) / 2)
        else:
            cut_value_top = 0
        
        status_top, move_value = self.detect_distance(
            y_top - cut_value_top,
            crop_size[0],
            max_ratio=params.head_top_range[0],
            min_ratio=params.head_top_range[1],
        )
        
        # 第二轮裁剪
        if x_left == 0 and x_right == 0 and status_top == 0:
            result_image = cut_image
        else:
            result_image = self.idphoto_cut(
                x1 + x_left,
                y1 + cut_value_top + status_top * move_value,
                x2 - x_right,
                y2 - cut_value_top + status_top * move_value,
                matting_image,
            )
        
        # 移动到底部
        result_image, _ = self.move_to_bottom(result_image.astype(np.uint8))
        
        # 生成标准照和高清照
        result_image_standard = self.standard_photo_resize(result_image, standard_size)
        result_image_hd, _ = self.resize_image_by_min(result_image, esp=max(600, standard_size[1]))
        
        return result_image_hd, result_image_standard
    
    @staticmethod
    def compress_image_to_kb(
        image: np.ndarray,
        target_kb: int = 50,
        dpi: int = 300
    ) -> bytes:
        """将图像压缩到指定KB大小。
        
        Args:
            image: 输入图像 (BGR 格式)
            target_kb: 目标文件大小（KB）
            dpi: 图像分辨率
        
        Returns:
            压缩后的图像字节数据（JPEG格式）
        """
        # 转换为RGB PIL图像
        if image.shape[2] == 4:
            # RGBA -> RGB（白色背景）
            b, g, r, a = cv2.split(image)
            alpha = a.astype(float) / 255
            white = np.ones_like(b) * 255
            r = (r * alpha + white * (1 - alpha)).astype(np.uint8)
            g = (g * alpha + white * (1 - alpha)).astype(np.uint8)
            b = (b * alpha + white * (1 - alpha)).astype(np.uint8)
            rgb_image = cv2.merge([r, g, b])
        else:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        pil_image = Image.fromarray(rgb_image)
        
        # 二分查找最佳质量值
        quality = 95
        
        while True:
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="JPEG", quality=quality, dpi=(dpi, dpi))
            img_size_kb = len(img_byte_arr.getvalue()) / 1024
            
            if img_size_kb <= target_kb or quality <= 1:
                # 如果图像小于目标大小，添加padding以精确匹配
                if img_size_kb < target_kb:
                    padding_size = int((target_kb * 1024) - len(img_byte_arr.getvalue()))
                    padding = b"\x00" * padding_size
                    img_byte_arr.write(padding)
                
                return img_byte_arr.getvalue()
            
            # 降低质量
            quality -= 5
            if quality < 1:
                quality = 1
    
    @staticmethod
    def generate_layout(
        image: np.ndarray,
        size: Tuple[int, int],
        layout_size: Tuple[int, int] = (1205, 1795)
    ) -> np.ndarray:
        """生成排版照。
        
        根据照片尺寸自动计算最优排列方式（横向或纵向），
        在六寸相纸上尽可能多地排列照片。
        
        Args:
            image: 标准证件照 (RGB 或 RGBA)
            size: 单张照片尺寸 (height, width)
            layout_size: 排版尺寸 (height, width)，默认为六寸照片
        
        Returns:
            排版后的图像 (RGB)
        """
        # 如果是 RGBA，转换为 RGB（白色背景）
        if image.shape[2] == 4:
            b, g, r, a = cv2.split(image)
            alpha = a.astype(float) / 255
            white = np.ones_like(b) * 255
            r = (r * alpha + white * (1 - alpha)).astype(np.uint8)
            g = (g * alpha + white * (1 - alpha)).astype(np.uint8)
            b = (b * alpha + white * (1 - alpha)).astype(np.uint8)
            image = cv2.merge([b, g, r])
        
        photo_height, photo_width = size
        layout_height, layout_width = layout_size
        
        # 调整图像尺寸
        if image.shape[0] != photo_height:
            image = cv2.resize(image, (photo_width, photo_height))
        
        # 计算排列参数
        photo_interval_h = 30  # 照片间垂直距离
        photo_interval_w = 30  # 照片间水平距离
        sides_interval_h = 50  # 照片与边缘垂直距离
        sides_interval_w = 70  # 照片与边缘水平距离
        
        limit_block_w = layout_width - 2 * sides_interval_w
        limit_block_h = layout_height - 2 * sides_interval_h
        
        # 方案1：不转置排列（正常方向）
        cols_no_transpose = 1
        rows_no_transpose = 1
        
        for i in range(1, 9):
            total_w = photo_width * i + photo_interval_w * (i - 1)
            if total_w <= limit_block_w:
                cols_no_transpose = i
            else:
                break
        
        for i in range(1, 4):
            total_h = photo_height * i + photo_interval_h * (i - 1)
            if total_h <= limit_block_h:
                rows_no_transpose = i
            else:
                break
        
        count_no_transpose = rows_no_transpose * cols_no_transpose
        
        # 方案2：转置排列（旋转90度）
        cols_transpose = 1
        rows_transpose = 1
        
        for i in range(1, 9):
            total_w = photo_height * i + photo_interval_w * (i - 1)  # 注意：宽度使用原高度
            if total_w <= limit_block_w:
                cols_transpose = i
            else:
                break
        
        for i in range(1, 4):
            total_h = photo_width * i + photo_interval_h * (i - 1)  # 注意：高度使用原宽度
            if total_h <= limit_block_h:
                rows_transpose = i
            else:
                break
        
        count_transpose = rows_transpose * cols_transpose
        
        # 选择能排列更多照片的方案
        # 如果数量相同，优先选择行列比更接近1的方案（更接近正方形布局）
        use_transpose = False
        if count_transpose > count_no_transpose:
            use_transpose = True
        elif count_transpose == count_no_transpose and count_transpose > 0:
            # 计算行列比的差异（越接近1越好）
            ratio_no_transpose = max(rows_no_transpose / cols_no_transpose, cols_no_transpose / rows_no_transpose)
            ratio_transpose = max(rows_transpose / cols_transpose, cols_transpose / rows_transpose)
            if ratio_transpose < ratio_no_transpose:
                use_transpose = True
        
        if use_transpose:
            # 使用转置排列
            cols, rows = cols_transpose, rows_transpose
            # 旋转图像90度（顺时针）
            image = cv2.transpose(image)
            image = cv2.flip(image, 1)  # 水平翻转以获得正确的旋转效果
            photo_height, photo_width = photo_width, photo_height  # 交换宽高
            logger.info(f"排版照使用转置排列: {cols}列 × {rows}行 = {cols * rows}张")
        else:
            # 使用正常排列
            cols, rows = cols_no_transpose, rows_no_transpose
            logger.info(f"排版照使用正常排列: {cols}列 × {rows}行 = {cols * rows}张")
        
        # 计算居中位置
        center_block_w = photo_width * cols + photo_interval_w * (cols - 1)
        center_block_h = photo_height * rows + photo_interval_h * (rows - 1)
        start_x = (layout_width - center_block_w) // 2
        start_y = (layout_height - center_block_h) // 2
        
        # 创建白色背景
        layout = np.ones((layout_height, layout_width, 3), dtype=np.uint8) * 255
        
        # 放置照片
        for r in range(rows):
            for c in range(cols):
                x = start_x + c * (photo_width + photo_interval_w)
                y = start_y + r * (photo_height + photo_interval_h)
                layout[y:y + photo_height, x:x + photo_width] = image
        
        return layout
    
    @staticmethod
    def add_background(
        matting_image: np.ndarray,
        bg_color: Tuple[int, int, int],
        render_mode: str = "solid"
    ) -> np.ndarray:
        """添加背景颜色。
        
        参考 HivisionIDPhotos 项目的渐变实现。
        
        Args:
            matting_image: RGBA 格式的抠图结果
            bg_color: 背景颜色 (R, G, B)
            render_mode: 渲染模式 ("solid", "gradient_up", "gradient_down", "gradient_center")
        
        Returns:
            添加背景后的图像 (RGBA)
        """
        height, width = matting_image.shape[:2]
        
        # 创建背景
        if render_mode == "solid":
            # 纯色背景
            background = np.zeros((height, width, 3), dtype=np.uint8)
            background[:] = bg_color[::-1]  # RGB to BGR
        elif render_mode == "gradient_up":
            # 向上渐变：从下到上，颜色从深到浅
            # 完全按照 HivisionIDPhotos 的实现
            background = np.zeros((height, width, 3), dtype=np.uint8)
            for i in range(height):
                # 从 0 (底部) 到 1 (顶部)
                ratio = i / (height - 1) if height > 1 else 0
                # 底部深色(原色)，顶部浅色(原色*1.3)
                color = tuple(int(min(c * (1.0 + 0.3 * ratio), 255)) for c in bg_color[::-1])
                background[i, :] = color
        elif render_mode == "gradient_down":
            # 向下渐变：从上到下，颜色从深到浅
            # 完全按照 HivisionIDPhotos 的实现
            background = np.zeros((height, width, 3), dtype=np.uint8)
            for i in range(height):
                # 从 1 (顶部) 到 0 (底部)
                ratio = 1 - (i / (height - 1) if height > 1 else 0)
                # 顶部深色(原色)，底部浅色(原色*1.3)
                color = tuple(int(min(c * (1.0 + 0.3 * ratio), 255)) for c in bg_color[::-1])
                background[i, :] = color
        elif render_mode == "gradient_center":
            # 中心渐变：从中心向外渐变
            # 完全按照 HivisionIDPhotos 的实现
            background = np.zeros((height, width, 3), dtype=np.uint8)
            center_y, center_x = height // 2, width // 2
            max_dist = math.sqrt(center_x ** 2 + center_y ** 2)
            for i in range(height):
                for j in range(width):
                    dist = math.sqrt((i - center_y) ** 2 + (j - center_x) ** 2)
                    # 中心深色，外围变浅
                    ratio = dist / max_dist if max_dist > 0 else 0
                    color = tuple(int(min(c * (1.0 + 0.3 * ratio), 255)) for c in bg_color[::-1])
                    background[i, j] = color
        else:
            # 默认纯色
            background = np.zeros((height, width, 3), dtype=np.uint8)
            background[:] = bg_color[::-1]
        
        # Alpha 混合合成
        b, g, r, a = cv2.split(matting_image)
        alpha = a.astype(float) / 255
        
        result = np.zeros((height, width, 4), dtype=np.uint8)
        for c_idx, (fg, bg) in enumerate(zip([b, g, r], cv2.split(background))):
            result[:, :, c_idx] = (fg * alpha + bg * (1 - alpha)).astype(np.uint8)
        result[:, :, 3] = 255  # 完全不透明
        
        return result
    
    def process(
        self,
        image: np.ndarray,
        params: IDPhotoParams,
        bg_color: Tuple[int, int, int] = (67, 142, 219),
        render_mode: str = "solid",
        generate_layout: bool = True,
        layout_size: Tuple[int, int] = (1205, 1795),
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> IDPhotoResult:
        """处理证件照。
        
        Args:
            image: 输入图像 (BGR 格式)
            params: 证件照参数
            bg_color: 背景颜色 (R, G, B)
            render_mode: 渲染模式
            generate_layout: 是否生成排版照
            layout_size: 排版尺寸 (height, width)
            progress_callback: 进度回调函数
        
        Returns:
            证件照处理结果
        """
        if not self.bg_remover:
            raise RuntimeError("背景移除模型未加载")
        
        if not params.change_bg_only and not self.face_detector:
            raise RuntimeError("人脸检测模型未加载")
        
        def update_progress(value: float, message: str):
            if progress_callback:
                progress_callback(value, message)
        
        # 1. 预处理：缩放到合适大小
        update_progress(0.05, "正在预处理图像...")
        processing_image = self.resize_image_esp(image, 2000)
        origin_image = processing_image.copy()
        
        # 2. 人像抠图
        update_progress(0.1, "正在移除背景...")
        pil_image = Image.fromarray(cv2.cvtColor(processing_image, cv2.COLOR_BGR2RGB))
        matting_pil = self.remove_background(pil_image)
        matting_image = cv2.cvtColor(np.array(matting_pil), cv2.COLOR_RGBA2BGRA)
        
        # 3. 美颜处理
        update_progress(0.4, "正在美颜处理...")
        if (params.whitening_strength > 0 or 
            params.brightness_strength != 0 or 
            params.contrast_strength != 0 or 
            params.sharpen_strength > 0 or
            params.saturation_strength != 0):
            
            # 美白
            if params.whitening_strength > 0:
                origin_image = self.apply_whitening(origin_image, params.whitening_strength)
            
            # 其他美颜
            if (params.brightness_strength != 0 or params.contrast_strength != 0 or 
                params.sharpen_strength > 0 or params.saturation_strength != 0):
                origin_image = self.apply_brightness_contrast_sharpen_saturation(
                    origin_image,
                    params.brightness_strength,
                    params.contrast_strength,
                    params.sharpen_strength,
                    params.saturation_strength
                )
            
            # 更新抠图结果（保留 alpha 通道）
            b, g, r = cv2.split(origin_image)
            _, _, _, a = cv2.split(matting_image)
            matting_image = cv2.merge([b, g, r, a])
        
        # 如果只换底，直接返回
        if params.change_bg_only:
            update_progress(0.9, "正在添加背景...")
            result_with_bg = self.add_background(matting_image, bg_color, render_mode)
            
            # 生成排版照
            layout = None
            if generate_layout:
                update_progress(0.95, "正在生成排版照...")
                layout = self.generate_layout(result_with_bg, params.size, layout_size)
            
            update_progress(1.0, "处理完成")
            return IDPhotoResult(
                standard=result_with_bg,
                hd=result_with_bg,
                matting=matting_image,
                layout=layout
            )
        
        # 4. 人脸检测
        update_progress(0.5, "正在检测人脸...")
        face_info = self.detect_face(origin_image)
        if face_info is None:
            raise ValueError("未检测到人脸，请使用包含清晰人脸的照片")
        
        # 5. 人脸矫正（可选）
        if params.face_alignment and abs(face_info["roll_angle"]) > 2:
            update_progress(0.6, "正在矫正人脸角度...")
            # 旋转图像
            angle = -face_info["roll_angle"]
            center = (origin_image.shape[1] // 2, origin_image.shape[0] // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            origin_image = cv2.warpAffine(origin_image, M, (origin_image.shape[1], origin_image.shape[0]))
            
            # 旋转抠图结果
            matting_image = cv2.warpAffine(matting_image, M, (matting_image.shape[1], matting_image.shape[0]))
            
            # 重新检测人脸
            face_info = self.detect_face(origin_image)
            if face_info is None:
                raise ValueError("人脸矫正后检测失败")
        
        # 6. 调整照片
        update_progress(0.7, "正在调整照片...")
        result_hd, result_standard = self.adjust_photo(
            matting_image, face_info["rectangle"], params
        )
        
        # 7. 添加背景
        update_progress(0.85, "正在添加背景...")
        result_hd_with_bg = self.add_background(result_hd, bg_color, render_mode)
        result_standard_with_bg = self.add_background(result_standard, bg_color, render_mode)
        
        # 8. 生成排版照
        layout = None
        if generate_layout:
            update_progress(0.95, "正在生成排版照...")
            layout = self.generate_layout(result_standard_with_bg, params.size, layout_size)
        
        update_progress(1.0, "处理完成")
        
        return IDPhotoResult(
            standard=result_standard_with_bg,
            hd=result_hd_with_bg,
            matting=matting_image,
            layout=layout
        )

