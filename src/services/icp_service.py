# -*- coding: utf-8 -*-
"""ICP备案查询服务模块。

提供ICP备案查询、验证码识别等功能。
基于 ibig(检测模型) + isma(相似度模型) 实现验证码识别。
"""

import asyncio
import io
import base64
import time
import numbers
import hashlib
import random
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING
from PIL import Image
import numpy as np
import cv2
import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from utils import logger, create_onnx_session

if TYPE_CHECKING:
    from services.config_service import ConfigService


class Siamese:
    """相似度对比模型类（isma模型）。"""

    def __init__(self, model_path: Path, config_service: Optional['ConfigService'] = None):
        """初始化相似度模型，保持与参考实现一致的推理流程。"""
        self.model_path = model_path
        self.input_shape = [32, 32]
        self.session = create_onnx_session(
            model_path=model_path,
            config_service=config_service
        )
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]

    @staticmethod
    def _crop(img: Image.Image, i: int, j: int, h: int, w: int) -> Image.Image:
        return img.crop((j, i, j + w, i + h))

    @staticmethod
    def _preprocess_input(x: np.ndarray) -> np.ndarray:
        return x / 255.0

    @staticmethod
    def _cvt_color(image: Image.Image) -> Image.Image:
        if len(np.shape(image)) == 3 and np.shape(image)[2] == 3:
            return image
        return image.convert('RGB')

    @staticmethod
    def _resize(img: Image.Image, size, interpolation=Image.BILINEAR) -> Image.Image:
        if isinstance(size, int):
            w, h = img.size
            if (w <= h and w == size) or (h <= w and h == size):
                return img
            if w < h:
                ow = size
                oh = int(size * h / w)
                return img.resize((ow, oh), interpolation)
            oh = size
            ow = int(size * w / h)
            return img.resize((ow, oh), interpolation)
        return img.resize(size[::-1], interpolation)

    @classmethod
    def _center_crop(cls, img: Image.Image, output_size) -> Image.Image:
        if isinstance(output_size, numbers.Number):
            output_size = (int(output_size), int(output_size))
        w, h = img.size
        th, tw = output_size
        i = int(round((h - th) / 2.0))
        j = int(round((w - tw) / 2.0))
        return cls._crop(img, i, j, th, tw)

    @classmethod
    def _letterbox_image(cls, image: Image.Image, size) -> Image.Image:
        w, h = size
        iw, ih = image.size
        '''resize image with unchanged aspect ratio using padding'''
        scale = min(w/iw, h/ih)
        nw = int(iw*scale)
        nh = int(ih*scale)

        image = image.resize((nw,nh), Image.BICUBIC)
        new_image = Image.new('RGB', size, (128,128,128))
        new_image.paste(image, ((w-nw)//2, (h-nh)//2))
        return new_image

    def detect_image(self, image_1: Image.Image, image_2: Image.Image) -> float:
        """检测两张图片的相似度，流程与原Siamese实现保持一致。"""
        image_1 = self._cvt_color(image_1)
        image_2 = self._cvt_color(image_2)

        target_size = (self.input_shape[1], self.input_shape[0])
        image_1 = self._letterbox_image(image_1, target_size)
        image_2 = self._letterbox_image(image_2, target_size)

        photo_1 = self._preprocess_input(np.array(image_1, np.float32))
        photo_2 = self._preprocess_input(np.array(image_2, np.float32))

        photo_1 = np.expand_dims(np.transpose(photo_1, (2, 0, 1)), axis=0).astype(np.float32)
        photo_2 = np.expand_dims(np.transpose(photo_2, (2, 0, 1)), axis=0).astype(np.float32)

        outputs = self.session.run(
            self.output_names,
            {
                self.input_names[0]: photo_1,
                self.input_names[1]: photo_2,
            }
        )
        similarity = outputs[0][0][0]
        return float(similarity)


class YOLODetector:
    """YOLO检测模型类（ibig模型），逻辑与detnate.YOLO_ONNX保持一致。"""

    def __init__(self, model_path: Path, config_service: Optional['ConfigService'] = None):
        self.session = create_onnx_session(
            model_path=model_path,
            config_service=config_service
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        self.input_height = input_shape[2]
        self.input_width = input_shape[3]
        self.debug_visualization = bool(
            config_service.get_config_value("icp_debug_visualization", False)
            if config_service else False
        )

    def extract_center_dominant_color_kmeans(
        self,
        image_input,
        output_path: Optional[str] = None,
        k: int = 2,
        color_tolerance: int = 30
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """对候选区域执行K-means颜色提取，复刻detnate实现。"""
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
            if img is None:
                raise ValueError(f"无法读取图像: {image_input}")
        elif isinstance(image_input, np.ndarray):
            img = image_input.copy()
            if img.ndim == 3 and img.shape[-1] == 4:
                img = img[..., :3]
        else:
            raise ValueError("image_input 必须是图片路径(str)或cv2图像数组(numpy.ndarray)")

        height, width = img.shape[:2]

        # 提取中心1/3区域
        center_x, center_y = width // 2, height // 2
        region_width, region_height = width // 3, height // 3

        x1 = center_x - region_width // 2
        y1 = center_y - region_height // 2
        x2 = center_x + region_width // 2
        y2 = center_y + region_height // 2

        center_region = img[y1:y2, x1:x2]
        if center_region.size == 0:
            raise ValueError("中心区域为空，请检查图像大小")

        # 使用K-means聚类找到主要颜色
        center_pixels = center_region.reshape(-1, 3).astype(np.float32)

        # 确保有足够的像素进行聚类
        if center_pixels.shape[0] < k:
            k = max(1, center_pixels.shape[0])  # 调整k值为像素数量

        # 使用K-means聚类找到主要颜色
        center_pixels = center_region.reshape(-1, 3).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(center_pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        # 找到最大的聚类（出现最多的颜色）
        unique_labels, counts = np.unique(labels, return_counts=True)
        dominant_cluster_idx = unique_labels[np.argmax(counts)]
        dominant_color = centers[dominant_cluster_idx].astype(int)
        # 创建掩码
        img_float = img.astype(np.float32)
        color_diff = np.sqrt(np.sum((img_float - dominant_color) ** 2, axis=2))
        mask = color_diff <= color_tolerance

        # === 噪点去除：形态学+小区域过滤 ===
        kernel = np.ones((1, 1), np.uint8)
        mask_clean = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel, iterations=1)
        mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_clean, connectivity=8)
        min_area = 20
        final_mask = np.zeros_like(mask_clean)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                final_mask[labels == i] = 1
        mask = final_mask.astype(bool)
        # === 噪点去除结束 ===

        # 根据图像通道数设置颜色
        if img.shape[2] == 4:  # RGBA或BGRA图像
            background_color = (255, 143, 0, 255)  # 添加alpha通道
            foreground_color = (255, 255, 255, 255)
        else:  # RGB或BGR图像
            background_color = (255, 143, 0)
            foreground_color = (255, 255, 255)

        # 创建结果图像
        result = np.full_like(img, background_color)
        result[mask] = foreground_color

        # 如果有两个以上的定点颜色不为background_color，则让前景色为白色，背景色为指定rgb色
        # 统计图像中的独特颜色
        unique_colors = np.unique(result.reshape(-1, result.shape[-1]), axis=0)

        # 统计不为background_color的颜色数量
        non_background_colors = []
        for color in unique_colors:
            if not np.array_equal(color, np.array(background_color)):
                non_background_colors.append(color)

        # 如果有两个以上的定点颜色不为background_color
        if len(non_background_colors) >= 2:
            # 重新设置颜色
            if img.shape[2] == 4:  # RGBA或BGRA图像
                new_foreground_color = (255, 255, 255, 255)  # 白色前景
                new_background_color = (255, 143, 0, 255)    # 指定RGB背景色
            else:  # RGB或BGR图像
                new_foreground_color = (255, 255, 255)       # 白色前景
                new_background_color = (255, 143, 0)         # 指定RGB背景色

            # 重新创建结果图像
            result = np.full_like(img, new_background_color)
            result[mask] = new_foreground_color

        # 轻度平滑抑制边缘毛刺
        result = cv2.medianBlur(result, 1)

        if output_path:
            cv2.imwrite(output_path, result)

        return result, dominant_color, mask

    def predict(self, source: np.ndarray, boxes_only: bool = False) -> Tuple[bool, Any]:
        """执行YOLO预测，返回布尔标记和结果，与detnate行为一致。"""
        confidence_thres = 0.5  # 定义置信度阈值
        iou_thres = 0.3  # 定义IOU阈值

        # 保持原始图像用于计算缩放比例
        img_height, img_width = source.shape[:2]

        # 预处理：BGR -> RGB -> resize -> normalize -> transpose -> expand_dims
        input_image = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
        res_image = cv2.resize(input_image, (512, 192))  # 注意：YOLO通常期望(width, height)

        # 标准化到0-1范围
        input_image = res_image.astype(np.float32) / 255.0
        # 转换为CHW格式 (channels, height, width)
        input_image = np.transpose(input_image, (2, 0, 1))
        # 添加batch维度
        input_image = np.expand_dims(input_image, axis=0)

        outputs = self.session.run([self.output_name], {self.input_name: input_image})

        output = np.transpose(np.squeeze(outputs[0]))
        rows = output.shape[0]
        boxes: List[List[int]] = []
        scores: List[float] = []

        x_factor = img_width / 512
        y_factor = img_height / 192

        for i in range(rows):
            classes_scores = output[i][4:]
            max_score = np.amax(classes_scores)
            if (max_score >= confidence_thres) and (output[i][2] > 0) and (output[i][3] > 0):
                x, y, w, h = output[i][0], output[i][1], output[i][2], output[i][3]
                left = int((x - w / 2) * x_factor)
                top = int((y - h / 2) * y_factor)
                width = int(w * x_factor)
                height = int(h * y_factor)

                boxes.append([left, top, width, height])
                scores.append(max_score)

        if len(boxes) == 0:
            return (False, "未检测到目标") if not boxes_only else (False, "未检测到目标")

        indices = cv2.dnn.NMSBoxes(boxes, scores, confidence_thres, iou_thres)

        if len(indices) == 0:
            return (False, "NMS后无有效检测结果") if not boxes_only else (False, "NMS后无有效检测结果")

        indices = indices.flatten().tolist()  # 解包索引

        new_boxes = [boxes[i] for i in indices]
        if len(new_boxes) < 4:
            logger.info(f"目标检测失败：检测到的框数量不足4个，实际数量为{len(new_boxes)}")
            return (False, "目标检测失败") if not boxes_only else (False, "目标检测失败")

        # 若只需要框，直接返回
        if boxes_only:
            return True, new_boxes

        cls_xy: List[Dict[str, Any]] = []
        for box in new_boxes:
            left, top, width, height = box
            right = left + width
            bottom = top + height
            try:
                box_mid_xy = [(left + width / 2) + 2,(top + height / 2)]
            except:
                box_mid_xy = [left + width / 2,top + height / 2]
            img = source[top:bottom, left:right]
            try:
                # 去干扰，去除失败则使用原图
                result, dominant_color, mask = self.extract_center_dominant_color_kmeans(
                    img,
                    k=8,
                    color_tolerance=40
                )

                # 确保result和source的通道数一致
                if result.shape[2] != source.shape[2]:
                    if result.shape[2] == 3 and source.shape[2] == 4:
                        # 将3通道图像转换为4通道
                        result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
                    elif result.shape[2] == 4 and source.shape[2] == 3:
                        # 将4通道图像转换为3通道
                        result = cv2.cvtColor(result, cv2.COLOR_BGRA2BGR)

                data = {
                    "box_mid_xy": box_mid_xy,
                    "img": Image.fromarray(result)
                }
            except Exception as exc:
                logger.debug(f"候选区域去噪失败，使用原图: {exc}")
                data = {
                    "box_mid_xy": box_mid_xy,
                    "img": Image.fromarray(img)
                }
            cls_xy.append(data)

        return True, cls_xy


class ICPService:
    """ICP备案查询服务类。
    
    提供以下功能：
    - 滑块验证码识别（ibig检测 + isma相似度对比）
    - ICP备案查询（域名、APP、小程序、快应用）
    - 批量查询
    """
    
    # ICP查询API配置（移除代理支持，直接访问官方API）
    HOME = "https://beian.miit.gov.cn/"
    AUTH_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/auth"
    GET_CAPTCHA = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/getCheckImagePoint"  # 使用getCheckImagePoint
    CHECK_CAPTCHA = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/checkImage"
    QUERY_URL = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryByCondition"
    
    # 查询类型映射
    QUERY_TYPES = {
        "web": {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 1},
        "app": {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 6},
        "mapp": {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 7},
        "kapp": {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 8},
    }

    SMALL_SLICE_FOUR_INDEX = [
        [
            {'x': 163, 'y': 9},
            {'x': 193, 'y': 41}
        ],
        [
            {'x': 198, 'y': 9},
            {'x': 225, 'y': 41}
        ],
        [
            {'x': 230, 'y': 9},
            {'x': 259, 'y': 41}
        ],
        [
            {'x': 263, 'y': 9},
            {'x': 294, 'y': 41}
        ]
    ]
    
    def __init__(self, config_service: Optional['ConfigService'] = None):
        """初始化ICP服务。
        
        Args:
            config_service: 配置服务实例（可选）
        """
        self.config_service = config_service
        
        # 获取模型目录
        if config_service:
            data_dir = config_service.get_data_dir()
        else:
            from utils.file_utils import get_app_root
            data_dir = get_app_root() / "storage" / "data"
        
        # 使用版本号组织模型目录（与其他服务保持一致）
        from constants.model_config import ICP_MODELS, DEFAULT_ICP_MODEL_KEY
        self.current_model = ICP_MODELS[DEFAULT_ICP_MODEL_KEY]
        self.models_dir = data_dir / "models" / "icp" / self.current_model.version
        
        self.detector = None  # ibig检测模型
        self.siamese = None   # isma相似度模型
        self.token = ""
        self.token_expire = 0
        self.session = None
    
    def _get_client_uid(self) -> str:
        """生成客户端唯一标识（与原始实现一致）。
        
        Returns:
            包含clientUid的JSON字符串
        """
        import random
        import json
        
        characters = "0123456789abcdef"
        unique_id = ["0"] * 36

        for i in range(36):
            unique_id[i] = random.choice(characters)

        unique_id[14] = "4"
        unique_id[19] = characters[(3 & int(unique_id[19], 16)) | 8]
        unique_id[8] = unique_id[13] = unique_id[18] = unique_id[23] = "-"

        point_id = "point-" + "".join(unique_id)
        return json.dumps({"clientUid": point_id})
    
    def get_model_paths(self) -> Tuple[Path, Path]:
        """获取模型文件路径。
        
        Returns:
            (ibig模型路径, isma模型路径)
        """
        return (
            self.models_dir / self.current_model.detector_filename,
            self.models_dir / self.current_model.siamese_filename
        )

    @staticmethod
    def _extract_sign(params: Any) -> str:
        """从验证响应的params字段中提取sign，保证始终返回字符串。"""
        if isinstance(params, dict):
            sign_value = params.get("sign", "")
            return sign_value if isinstance(sign_value, str) else ""
        if isinstance(params, str):
            return params
        return ""

    def check_models_exist(self) -> bool:
        """检查模型文件是否存在。
        
        Returns:
            模型文件是否都存在
        """
        detector_path, siamese_path = self.get_model_paths()
        return detector_path.exists() and siamese_path.exists()
    
    def download_models(
        self,
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, str]:
        """下载ICP验证码识别模型。
        
        Args:
            progress_callback: 进度回调函数 (progress: float 0-1, message: str)
            
        Returns:
            (是否成功, 消息)
        """
        from constants.model_config import ICP_MODELS, DEFAULT_ICP_MODEL_KEY
        
        try:
            # 确保目录存在
            self.models_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用推荐模型
            model_info = ICP_MODELS[DEFAULT_ICP_MODEL_KEY]
            detector_path, siamese_path = self.get_model_paths()
            
            # 检查是否已存在
            if detector_path.exists() and siamese_path.exists():
                return True, "模型已存在"
            
            # 需要下载的文件
            files_to_download = []
            if not detector_path.exists():
                files_to_download.append(('检测模型(ibig)', model_info.detector_url, detector_path))
            if not siamese_path.exists():
                files_to_download.append(('相似度模型(isma)', model_info.siamese_url, siamese_path))
            
            if not files_to_download:
                return True, "模型已存在"
            
            total_files = len(files_to_download)
            
            # 下载文件
            with httpx.Client(timeout=300.0, follow_redirects=True) as client:
                for idx, (file_name, url, path) in enumerate(files_to_download, 1):
                    if progress_callback:
                        progress_callback(
                            (idx - 1) / total_files,
                            f"正在下载{file_name}... ({idx}/{total_files})"
                        )
                    
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        
                        total_size = int(response.headers.get("content-length", 0))
                        downloaded = 0
                        
                        with open(path, "wb") as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0 and progress_callback:
                                    file_progress = downloaded / total_size
                                    overall_progress = ((idx - 1) + file_progress) / total_files
                                    progress_callback(
                                        overall_progress,
                                        f"正在下载{file_name}... {downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB"
                                    )
            
            if progress_callback:
                progress_callback(1.0, "模型下载完成！")
            
            return True, "模型下载成功"
        
        except Exception as e:
            logger.error(f"下载ICP模型失败: {e}")
            return False, f"下载失败: {str(e)}"
        
    async def load_models(self, detector_path: Path, siamese_path: Path) -> bool:
        """加载ONNX模型。
        
        Args:
            detector_path: 检测模型文件路径(ibig.onnx)
            siamese_path: 相似度模型文件路径(isma.onnx)
            
        Returns:
            是否加载成功
        """
        import asyncio

        try:
            if not detector_path.exists():
                logger.error(f"检测模型文件不存在: {detector_path}")
                return False
            if not siamese_path.exists():
                logger.error(f"相似度模型文件不存在: {siamese_path}")
                return False
            
            # 模型初始化是 CPU 密集型操作，放到线程池中避免阻塞 UI 事件循环
            def _do_load():
                self.detector = YOLODetector(detector_path, self.config_service)
                self.siamese = Siamese(siamese_path, self.config_service)

            await asyncio.to_thread(_do_load)
            logger.info(f"成功加载ICP模型: {detector_path.name}, {siamese_path.name}")
            
            # 记录使用的设备信息
            try:
                provider = self.detector.session.get_providers()[0]
                device_map = {
                    'CUDAExecutionProvider': 'CUDA GPU',
                    'DmlExecutionProvider': 'DirectML GPU',
                    'ROCMExecutionProvider': 'ROCm GPU',
                    'CPUExecutionProvider': 'CPU',
                }
                device_info = device_map.get(provider, provider)
                logger.info(f"ICP模型运行设备: {device_info}")
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"加载ICP模型失败: {e}")
            return False

    async def ensure_models_loaded(self) -> bool:
        """确保ibig/isma模型已经加载。"""
        if self.detector and self.siamese:
            return True
        if not self.check_models_exist():
            logger.error("ICP模型文件缺失，请先下载后再重试")
            return False
        detector_path, siamese_path = self.get_model_paths()
        return await self.load_models(detector_path, siamese_path)
    
    async def get_session(self) -> httpx.AsyncClient:
        """获取或创建HTTP会话（不使用代理，直接访问官方API）。"""
        if self.session is None or self.session.is_closed:
            timeout = httpx.Timeout(30.0)
            # 移除代理支持，直接访问
            self.session = httpx.AsyncClient(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话。"""
        if self.session and not self.session.is_closed:
            await self.session.aclose()

    def unload_model(self) -> None:
        """卸载当前加载的模型并释放推理会话。

        此方法会释放detector和siamese模型实例，清理GPU/CPU内存。
        下次使用时需要重新调用load_models方法加载模型。
        """
        import gc
        try:
            # 释放YOLO检测模型
            if self.detector:
                del self.detector
                self.detector = None
                logger.info("ICP检测模型(ibig)已卸载")

            # 释放相似度模型
            if self.siamese:
                del self.siamese
                self.siamese = None
                logger.info("ICP相似度模型(isma)已卸载")

            # 清理token缓存（可选）
            self.token = ""
            self.token_expire = 0

            # 强制垃圾回收
            gc.collect()
            logger.info("ICP模型卸载完成")
        except Exception as e:
            logger.error(f"卸载ICP模型时出错: {e}")

    async def get_auth_token(self) -> Optional[str]:
        """获取认证token。"""
        try:
            # 检查token是否过期
            if self.token and time.time() < self.token_expire:
                logger.debug(f"使用缓存的token（剩余有效期: {int(self.token_expire - time.time())}秒）")
                return self.token
            
            # 构建认证数据（与原始实现一致）
            import hashlib
            import uuid
            timeStamp = round(time.time() * 1000)
            authSecret = "testtest" + str(timeStamp)
            authKey = hashlib.md5(authSecret.encode(encoding="UTF-8")).hexdigest()
            auth_data = {"authKey": authKey, "timeStamp": timeStamp}
            
            logger.info(f"请求认证token: {self.AUTH_URL}")
            logger.info(f"认证参数: authKey={authKey[:10]}..., timeStamp={timeStamp}")
            
            session = await self.get_session()
            # 完整的请求头（与原始实现一致）
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32",
                "Origin": "https://beian.miit.gov.cn",
                "Referer": "https://beian.miit.gov.cn/",
                "Cookie": f"__jsluid_s={uuid.uuid4().hex}",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # 注意：auth接口使用POST请求，发送form数据
            response = await session.post(self.AUTH_URL, headers=headers, data=auth_data)
            logger.info(f"认证API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"认证API响应: success={data.get('success')}, msg={data.get('msg', 'N/A')}")
                except Exception as json_err:
                    logger.error(f"解析认证响应JSON失败: {json_err}")
                    logger.error(f"响应文本: {response.text[:500]}")
                    return None
                
                # 检查success字段
                if not data.get("success", False):
                    error_msg = data.get("msg", "未知错误")
                    logger.error(f"获取token失败 - API返回success=false: {error_msg}")
                    logger.error(f"完整响应: {data}")
                    return None
                
                # 提取token
                params = data.get("params", {})
                if not params:
                    logger.error(f"获取token失败 - 响应中没有params字段")
                    logger.error(f"完整响应: {data}")
                    return None
                
                self.token = params.get("bussiness", "")
                
                if not self.token:
                    logger.error(f"获取token失败 - params.bussiness为空")
                    logger.error(f"params内容: {params}")
                    return None
                
                # token有效期：从响应中获取expire（毫秒），或默认10分钟
                expire_ms = params.get("expire", 600000)  # 默认10分钟=600000毫秒
                self.token_expire = time.time() + (expire_ms / 1000)  # 转换为秒
                
                logger.info(f"✓ 成功获取ICP认证token（长度: {len(self.token)}, 有效期: {expire_ms/1000}秒）")
                return self.token
            else:
                logger.error(f"获取token失败 - HTTP状态码: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"错误响应: {error_data}")
                except:
                    logger.error(f"错误响应文本: {response.text[:500]}")
                return None
                    
        except Exception as e:
            logger.error(f"获取认证token时发生异常: {type(e).__name__}: {e}", exc_info=True)
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return None
    
    async def get_captcha_images(self) -> Optional[Tuple[Image.Image, Image.Image, str, str, str]]:
        """获取验证码图片。
        
        Returns:
            (大图, 小图, uuid, secretKey, clientUid) 或 None
        """
        try:
            logger.info("正在获取认证token...")
            token = await self.get_auth_token()
            if not token:
                logger.error("获取验证码失败 - 无法获取认证token（token为None）")
                return None
            
            logger.info(f"Token获取成功，准备请求验证码API")
            
            # 生成clientUid（与原始实现一致）
            client_uid_data = self._get_client_uid()
            import json
            import uuid
            client_uid = json.loads(client_uid_data)["clientUid"]
            logger.info(f"生成clientUid: {client_uid}")
            
            session = await self.get_session()
            # 完整的请求头（与原始实现一致）
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32",
                "Origin": "https://beian.miit.gov.cn",
                "Referer": "https://beian.miit.gov.cn/",
                "Cookie": f"__jsluid_s={uuid.uuid4().hex}",
                "Accept": "application/json, text/plain, */*",
                "Token": token,
                "Content-Type": "application/json",
                "Content-Length": str(len(client_uid_data.encode("utf-8")))
            }
            
            logger.info(f"准备请求验证码API: {self.GET_CAPTCHA}")
            logger.info(f"Token前10位: {token[:10] if len(token) >= 10 else token}...")
            
            # 发送包含clientUid的请求
            response = await session.post(self.GET_CAPTCHA, headers=headers, data=client_uid_data)
            logger.info(f"验证码API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"解析响应JSON失败: {json_err}")
                    logger.error(f"响应文本: {response.text[:500]}")
                    return None
                
                logger.info(f"验证码API响应成功字段: success={data.get('success')}, msg={data.get('msg', 'N/A')}")
                
                # 检查响应结构
                if not data.get("success", False):
                    error_msg = data.get("msg", "未知错误")
                    error_code = data.get("code", "未知代码")
                    logger.error(f"获取验证码失败 - API返回success=false")
                    logger.error(f"  错误代码: {error_code}")
                    logger.error(f"  错误消息: {error_msg}")
                    logger.error(f"  完整响应: {data}")
                    return None
                
                params = data.get("params", {})
                if not params:
                    logger.error("获取验证码失败 - 响应中没有params字段")
                    logger.error(f"  完整响应: {data}")
                    return None
                
                # 解码图片并获取secretKey（关键！）
                big_image_b64 = params.get("bigImage", "")
                small_image_b64 = params.get("smallImage", "")
                captcha_uuid = params.get("uuid", "")
                secret_key = params.get("secretKey", "")  # ★ 关键字段
                
                logger.info(f"params字段内容: bigImage长度={len(big_image_b64) if big_image_b64 else 0}, smallImage长度={len(small_image_b64) if small_image_b64 else 0}, uuid={captcha_uuid}, secretKey={'存在' if secret_key else '缺失'}")
                
                if not big_image_b64 or not small_image_b64 or not captcha_uuid or not secret_key:
                    logger.error("获取验证码失败 - 图片数据或必需字段缺失")
                    logger.error(f"  bigImage存在: {bool(big_image_b64)}")
                    logger.error(f"  smallImage存在: {bool(small_image_b64)}")
                    logger.error(f"  uuid存在: {bool(captcha_uuid)}")
                    logger.error(f"  secretKey存在: {bool(secret_key)}")
                    logger.error(f"  完整params: {params}")
                    return None
                
                try:
                    big_image_data = base64.b64decode(big_image_b64)
                    small_image_data = base64.b64decode(small_image_b64)
                    
                    big_image = Image.open(io.BytesIO(big_image_data))
                    small_image = Image.open(io.BytesIO(small_image_data))
                    
                    logger.info(f"✓ 成功获取并解码验证码图片")
                    logger.info(f"  UUID: {captcha_uuid}")
                    logger.info(f"  SecretKey: {secret_key[:10] if len(secret_key) >= 10 else secret_key}...")
                    logger.info(f"  大图尺寸: {big_image.size}")
                    logger.info(f"  小图尺寸: {small_image.size}")
                    # ★ 返回完整信息，包括secretKey和clientUid
                    return big_image, small_image, captcha_uuid, secret_key, client_uid
                    
                except Exception as decode_err:
                    logger.error(f"解码验证码图片失败: {decode_err}")
                    logger.error(f"  big_image_b64前50位: {big_image_b64[:50]}")
                    logger.error(f"  small_image_b64前50位: {small_image_b64[:50]}")
                    return None
            else:
                logger.error(f"获取验证码失败 - HTTP状态码异常: {response.status_code}")
                logger.error(f"  请求URL: {self.GET_CAPTCHA}")
                logger.error(f"  响应头: {dict(response.headers)}")
                try:
                    error_data = response.json()
                    logger.error(f"  响应JSON: {error_data}")
                except:
                    error_text = response.text[:500] if hasattr(response, 'text') else "无法读取响应文本"
                    logger.error(f"  响应文本(前500字符): {error_text}")
                return None
                    
        except Exception as e:
            logger.error(f"获取验证码图片时发生异常: {type(e).__name__}: {e}", exc_info=True)
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return None
    
    async def solve_captcha(self, big_image: Image.Image, small_image: Image.Image) -> Optional[List[Dict[str, int]]]:
        """识别滑块验证码（正确实现，参考源代码detnate.py）。
        
        流程：
        1. 从小图裁剪4个固定区域
        2. 用YOLO从大图检测所有候选框
        3. 每个小图区域与所有大图候选框对比相似度
        4. 为每个小图区域选择相似度最高且不重复的大图坐标
        
        Args:
            big_image: 大图（背景图）
            small_image: 小图（滑块图）
            
        Returns:
            点击坐标列表 [{"x": x, "y": y}, ...]，固定返回4个点
        """
        try:
            if not self.detector or not self.siamese:
                logger.error("模型未加载")
                return None

            big_cv = cv2.cvtColor(np.array(big_image.convert("RGB")), cv2.COLOR_RGB2BGR)
            small_cv = cv2.cvtColor(np.array(small_image.convert("RGB")), cv2.COLOR_RGB2BGR)

            success, det_results = self.detector.predict(big_cv)
            if not success:
                logger.info(f"目标检测失败：{det_results}")
                return None

            det_comp_result = []
            for i in self.SMALL_SLICE_FOUR_INDEX:
                undet_sim = small_cv[i[0]['y']:i[1]['y'],i[0]['x']:i[1]['x']]
                undet_sim = cv2.cvtColor(undet_sim, cv2.COLOR_BGR2RGB)
                undet_sim = Image.fromarray(undet_sim)
                sim_big_comp = []
                for bigimg in det_results:
                    undet_big = bigimg['img']
                    det = self.siamese.detect_image(undet_sim,undet_big)
                    sim_big_comp.append([det,bigimg['box_mid_xy']])

                max_value = float('-inf')
                max_coords = None
                save_max_coords = []
                de_coored = sim_big_comp.copy()
                for item in sim_big_comp:
                    if item[0] > max_value:
                        max_value = item[0]
                        max_coords = item[1]
                        save_max_coords.append(item)

                if max_coords in det_comp_result:
                    lbv = []
                    for bv in de_coored:
                        if bv[1] not in det_comp_result:
                            lbv.append(bv[1])
                    max_coords = lbv[0]

                det_comp_result.append(max_coords)

            data = [{'x':int(i[0]),'y':int(i[1])} for i in det_comp_result]

            if len(data) != 4:
                logger.error(f"验证码识别失败：需要4个点，实际得到 {len(data)} 个")
                return None

            logger.info("✓ 验证码识别完成")
            return data

        except Exception as e:
            logger.error(f"识别验证码失败: {e}")
            return None
    
    async def verify_captcha(self, uuid: str, secret_key: str, client_uid: str, points: List[Dict[str, int]]) -> Tuple[bool, str]:
        """验证验证码。
        
        Args:
            uuid: 验证码UUID
            secret_key: 加密密钥（从验证码响应中获取）
            client_uid: 客户端唯一标识
            points: 点击坐标列表
            
        Returns:
            (是否验证成功, 新的sign/token)
        """
        try:
            token = await self.get_auth_token()
            if not token:
                return False, ""
            
            # ★ 使用secretKey加密坐标（与源代码一致）
            import json
            points_json = json.dumps(points, ensure_ascii=False, separators=(',', ':'))
            cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_ECB)
            encrypted = cipher.encrypt(pad(points_json.encode('utf-8'), AES.block_size))
            encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
            
            session = await self.get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://beian.miit.gov.cn",
                "Referer": "https://beian.miit.gov.cn/",
                "Token": token,
                "Content-Type": "application/json"
            }
            
            # ★ 包含所有必需字段（与源代码一致）
            payload = {
                "token": uuid,              # 验证码UUID
                "secretKey": secret_key,    # 加密密钥
                "clientUid": client_uid,    # 客户端标识
                "pointJson": encrypted_b64  # 加密后的坐标
            }
            
            logger.debug(f"验证请求payload: token={uuid}, clientUid={client_uid}, pointJson前20位={encrypted_b64[:20]}...")
            
            response = await session.post(self.CHECK_CAPTCHA, headers=headers, json=payload)
            logger.debug(f"验证API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"验证API完整响应: {data}")
                
                success = data.get("success", False)
                msg = data.get("msg", "未知消息")
                params = data.get("params", "")

                logger.debug(f"验证结果解析: success={success}, msg={msg}, params={'存在' if params else '缺失'}")

                if success:
                    # ★ 更新token为新的sign（用于后续查询）
                    new_sign = self._extract_sign(params)

                    if new_sign:
                        logger.info(f"✓ 验证码验证成功，获得新sign（长度: {len(new_sign)}）")
                        return True, new_sign
                    else:
                        logger.warning(f"验证码验证成功，但未返回新sign（msg={msg}）")
                        logger.warning(f"  完整响应: {data}")
                        return True, ""
                else:
                    error_msg = msg
                    if isinstance(params, dict) and params.get("smallImage"):
                        logger.debug("验证失败返回了新的smallImage，可能需要重新获取验证码")
                    logger.error(f"验证码验证失败: {error_msg}")
                    logger.error(f"  完整响应: {data}")
                    return False, ""
            else:
                logger.error(f"验证码验证失败 - HTTP状态码: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"  错误响应: {error_data}")
                except:
                    logger.error(f"  响应文本: {response.text[:500]}")
                return False, ""
                    
        except Exception as e:
            logger.error(f"验证验证码失败: {e}")
            return False, ""
    
    async def query_icp(
        self,
        query_type: str,
        search: str,
        page_num: int = 1,
        page_size: int = 20,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """查询ICP备案信息。
        
        完整流程：获取验证码 -> 识别验证码 -> 验证验证码 -> 查询ICP
        
        Args:
            query_type: 查询类型（web/app/mapp/kapp）
            search: 查询关键词（域名/企业名/备案号等）
            page_num: 页码
            page_size: 每页数量
            max_retries: 最大重试次数
            
        Returns:
            查询结果字典，失败返回None
        """
        if not await self.ensure_models_loaded():
            logger.error("ICP模型未加载，终止查询")
            return None
        for retry in range(max_retries):
            try:
                logger.info(f"开始查询 ({retry+1}/{max_retries}): {search}")
                
                # 1. 获取验证码图片
                logger.debug("步骤1: 开始获取验证码图片...")
                captcha_data = await self.get_captcha_images()
                if not captcha_data:
                    logger.error("步骤1失败: 获取验证码图片返回None（详细错误见上方日志）")
                    await asyncio.sleep(1)
                    continue
                
                # ★ 解包完整返回值
                big_image, small_image, captcha_uuid, secret_key, client_uid = captcha_data
                
                # 2. 识别验证码（ibig检测 + isma相似度）
                logger.debug("步骤2: 开始识别验证码...")
                points = await self.solve_captcha(big_image, small_image)
                if not points:
                    logger.error("步骤2失败: 识别验证码失败")
                    await asyncio.sleep(1)
                    continue
                
                # 3. 验证验证码
                logger.debug(f"步骤3: 验证验证码，坐标数量: {len(points)}")
                verified, new_sign = await self.verify_captcha(captcha_uuid, secret_key, client_uid, points)
                if not verified:
                    logger.error(f"步骤3失败: 验证码验证失败，重试 {retry+1}/{max_retries}")
                    await asyncio.sleep(1)
                    continue
                
                # 4. 查询ICP信息
                logger.debug("步骤4: 开始查询ICP信息...")
                session = await self.get_session()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": "https://beian.miit.gov.cn",
                    "Referer": "https://beian.miit.gov.cn/",
                    "Token": self.token,     # 原始token
                    "Sign": new_sign,        # ★ 验证后获得的sign
                    "Uuid": captcha_uuid,    # ★ 验证码UUID
                    "Content-Type": "application/json"
                }
                
                # 构建查询参数
                query_params = self.QUERY_TYPES.get(query_type, self.QUERY_TYPES["web"]).copy()
                query_params["pageNum"] = str(page_num)
                query_params["pageSize"] = str(page_size)
                query_params["unitName"] = search
                
                logger.debug(f"查询参数: {query_params}")
                
                response = await session.post(self.QUERY_URL, headers=headers, json=query_params)
                logger.debug(f"查询API响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"查询API响应: success={data.get('success')}, msg={data.get('msg', 'N/A')}")
                    
                    if data.get("success"):
                        logger.info(f"✓ 查询成功: {search}")
                        return data.get("params", {})
                    else:
                        msg = data.get("msg", "未知错误")
                        logger.error(f"查询失败: {msg}")
                        logger.error(f"  完整响应: {data}")
                        await asyncio.sleep(1)
                        continue
                else:
                    logger.error(f"HTTP错误 {response.status_code}")
                    try:
                        error_data = response.json()
                        logger.error(f"  错误响应: {error_data}")
                    except:
                        logger.error(f"  响应文本: {response.text[:500]}")
                    await asyncio.sleep(1)
                    continue
                        
            except httpx.TimeoutException as e:
                logger.error(f"查询超时 (重试 {retry+1}/{max_retries}): {e}")
                await asyncio.sleep(2)  # 超时后等待更长时间
                continue
            except httpx.NetworkError as e:
                logger.error(f"网络错误 (重试 {retry+1}/{max_retries}): {e}")
                await asyncio.sleep(2)
                continue
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                logger.error(f"HTTP错误 {status_code} (重试 {retry+1}/{max_retries})")
                # 某些状态码不应该重试
                if status_code in [400, 401, 403, 404]:  # 客户端错误，重试无意义
                    logger.error(f"HTTP {status_code} 错误不可重试，终止查询")
                    return None
                await asyncio.sleep(1)
                continue
            except (KeyError, ValueError, TypeError) as e:
                # 数据解析错误，可能是API返回格式变化
                logger.error(f"数据解析错误 (重试 {retry+1}/{max_retries}): {e}", exc_info=True)
                await asyncio.sleep(1)
                continue
            except Exception as e:
                logger.error(f"查询ICP失败 (重试 {retry+1}/{max_retries}): {type(e).__name__}: {e}", exc_info=True)
                await asyncio.sleep(1)
                continue
        
        logger.error(f"查询失败，已达到最大重试次数 ({max_retries}次): {search}")
        return None
    
    async def get_detail_info(
        self, 
        data_id: str, 
        service_type: int
    ) -> Optional[Dict[str, Any]]:
        """获取APP/小程序/快应用的详细信息。
        
        Args:
            data_id: 数据ID
            service_type: 服务类型 (6=APP, 7=小程序, 8=快应用)
            
        Returns:
            详细信息字典，失败返回None
        """
        try:
            logger.info(f"开始获取详情: dataId={data_id}, serviceType={service_type}")
            
            session = await self.get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://beian.miit.gov.cn",
                "Referer": "https://beian.miit.gov.cn/",
                "Token": self.token,
                "Sign": "",  # 详情查询可能不需要sign
                "Content-Type": "application/json"
            }
            
            detail_params = {
                "dataId": data_id,
                "serviceType": service_type
            }
            
            detail_url = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryDetailByAppAndMiniId"
            
            response = await session.post(detail_url, headers=headers, json=detail_params)
            logger.debug(f"详情API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"详情API响应: success={data.get('success')}")
                
                if data.get("success"):
                    logger.info(f"✓ 获取详情成功: dataId={data_id}")
                    return data.get("params", {})
                else:
                    msg = data.get("msg", "未知错误")
                    logger.error(f"获取详情失败: {msg}")
                    return None
            else:
                logger.error(f"详情查询HTTP错误 {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"获取详情异常: {e}")
            return None
    
    def format_icp_result(self, result: Dict[str, Any]) -> str:
        """格式化ICP查询结果。
        
        Args:
            result: 查询结果字典
            
        Returns:
            格式化的文本
        """
        # 处理 ymicp 风格的数据结构
        if "params" in result and isinstance(result["params"], dict):
            # ymicp 风格：result["params"]["list"]
            data_list = result["params"].get("list", [])
            total = result["params"].get("total", 0)
            current_page = result["params"].get("pageNum", 1)
            total_pages = result["params"].get("pages", 1)
        else:
            # 标准风格：result["list"]
            data_list = result.get("list", [])
            total = result.get("total", 0)
            current_page = result.get("pageNum", 1)
            total_pages = result.get("pages", 1)
        
        if not data_list:
            return "未查询到相关备案信息"
        
        lines = []
        lines.append(f"共查询到 {total} 条结果")
        lines.append(f"当前第 {current_page} 页，共 {total_pages} 页")
        lines.append("-" * 60)
        
        for idx, item in enumerate(data_list, 1):
            lines.append(f"\n【记录 {idx}】")
            lines.append(f"主办单位: {item.get('unitName', 'N/A')}")
            lines.append(f"单位性质: {item.get('natureName', 'N/A')}")
            
            # 根据不同类型显示不同字段
            if "domain" in item:
                lines.append(f"域名: {item.get('domain', 'N/A')}")
            if "serviceName" in item:
                lines.append(f"服务名称: {item.get('serviceName', 'N/A')}")
            if "serviceHome" in item:
                lines.append(f"首页网址: {item.get('serviceHome', 'N/A')}")
            
            # 备案号显示
            main_licence = item.get('mainLicence', 'N/A')
            service_licence = item.get('serviceLicence', 'N/A')
            if main_licence != 'N/A':
                lines.append(f"主体备案号: {main_licence}")
            if service_licence != 'N/A':
                lines.append(f"服务备案号: {service_licence}")
            
            lines.append(f"审核通过日期: {item.get('updateRecordTime', 'N/A')}")
            
            # 详细信息（如果存在）
            if "mainUnitAddress" in item:
                lines.append(f"主体地址: {item.get('mainUnitAddress', 'N/A')}")
            if "serviceContent" in item:
                lines.append(f"服务内容: {item.get('serviceContent', 'N/A')}")
            if "serviceScope" in item:
                lines.append(f"服务范围: {item.get('serviceScope', 'N/A')}")
            
            lines.append("-" * 60)
        
        return '\n'.join(lines)
    
    def __del__(self):
        """清理资源。"""
        if self.session and not self.session.is_closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.aclose())
                else:
                    loop.run_until_complete(self.session.aclose())
            except:
                pass
