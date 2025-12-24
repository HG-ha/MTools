# -*- coding: utf-8 -*-
"""OCR服务模块。

提供OCR文字识别功能，使用PaddleOCR v5模型。
"""

import gc
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import httpx
import numpy as np
from PIL import Image

from constants import DEFAULT_OCR_MODEL_KEY, OCR_MODELS, OCRModelInfo
from utils import logger, create_onnx_session


class OCRService:
    """OCR服务类。
    
    提供文字识别功能，包括：
    - 文本检测
    - 文本识别
    - 模型下载和管理
    """
    
    def __init__(self, config_service=None) -> None:
        """初始化OCR服务。
        
        Args:
            config_service: 配置服务实例
        """
        self.config_service = config_service
        self.det_session = None  # 检测模型会话
        self.cls_session = None  # 方向分类模型会话
        self.rec_session = None  # 识别模型会话
        self.char_dict = None    # 字符字典
        self.current_model_key = None
        self.rec_image_height = 32  # 识别模型输入高度（动态获取）
        self.use_angle_cls = True  # 是否使用方向分类
    
    def get_available_models(self) -> list[str]:
        """获取可用的OCR模型列表。
        
        Returns:
            模型键列表
        """
        return list(OCR_MODELS.keys())
    
    def get_model_dir(self, model_key: str) -> Path:
        """获取模型存储目录。
        
        Args:
            model_key: 模型键
        
        Returns:
            模型目录路径
        """
        if self.config_service:
            data_dir = self.config_service.get_data_dir()
        else:
            from utils.file_utils import get_app_root
            data_dir = get_app_root() / "storage" / "data"
        
        model_info = OCR_MODELS[model_key]
        model_dir = data_dir / "models" / "PPOCR-v5" / model_info.version
        return model_dir
    
    def download_model(
        self,
        model_key: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, str]:
        """下载OCR模型。
        
        Args:
            model_key: 模型键
            progress_callback: 进度回调函数
        
        Returns:
            (是否成功, 消息)
        """
        try:
            model_info = OCR_MODELS[model_key]
            model_dir = self.get_model_dir(model_key)
            model_dir.mkdir(parents=True, exist_ok=True)
            
            det_path = model_dir / model_info.det_filename
            rec_path = model_dir / model_info.rec_filename
            dict_path = model_dir / model_info.dict_filename
            cls_path = model_dir / model_info.cls_filename if model_info.use_angle_cls else None
            
            # 检查是否已存在
            required_files = [det_path, rec_path, dict_path]
            if cls_path:
                required_files.append(cls_path)
            
            if all(p.exists() for p in required_files):
                return True, "模型已存在"
            
            # 需要下载的文件
            files_to_download = []
            if not det_path.exists():
                files_to_download.append(('检测模型', model_info.det_url, det_path))
            if not rec_path.exists():
                files_to_download.append(('识别模型', model_info.rec_url, rec_path))
            if cls_path and not cls_path.exists():
                files_to_download.append(('方向分类模型', model_info.cls_url, cls_path))
            if not dict_path.exists():
                files_to_download.append(('字典文件', model_info.dict_url, dict_path))
            
            total_files = len(files_to_download)
            
            # 下载文件
            for idx, (file_name, url, path) in enumerate(files_to_download, 1):
                if progress_callback:
                    progress_callback(
                        (idx - 1) / total_files,
                        f"正在下载{file_name}... ({idx}/{total_files})"
                    )
                
                with httpx.Client(timeout=300.0, follow_redirects=True) as client:
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
            logger.error(f"下载OCR模型失败: {e}")
            return False, f"下载失败: {str(e)}"
    
    def load_model(
        self,
        model_key: str,
        use_gpu: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, str]:
        """加载OCR模型。
        
        Args:
            model_key: 模型键
            use_gpu: 是否使用GPU（已弃用，会自动从config_service读取gpu_acceleration配置）
            progress_callback: 进度回调
        
        Returns:
            (是否成功, 消息)
        """
        try:
            import onnxruntime as ort
            
            # 如果已加载相同模型，直接返回
            if self.current_model_key == model_key and self.det_session and self.rec_session:
                return True, "模型已加载"
            
            # 卸载旧模型
            if self.det_session or self.rec_session:
                self.unload_model()
            
            if progress_callback:
                progress_callback(0.1, "正在准备加载模型...")
            
            model_info = OCR_MODELS[model_key]
            model_dir = self.get_model_dir(model_key)
            
            det_path = model_dir / model_info.det_filename
            rec_path = model_dir / model_info.rec_filename
            dict_path = model_dir / model_info.dict_filename
            cls_path = model_dir / model_info.cls_filename if model_info.use_angle_cls else None
            
            # 检查模型文件是否存在
            required_files = [det_path, rec_path, dict_path]
            if cls_path:
                required_files.append(cls_path)
            
            if not all(p.exists() for p in required_files):
                return False, "模型文件不存在，请先下载"
            
            # 保存配置
            self.use_angle_cls = model_info.use_angle_cls
            
            if progress_callback:
                progress_callback(0.2, "正在加载检测模型...")
            
            # 使用统一的工具函数加载检测模型
            self.det_session = create_onnx_session(
                model_path=det_path,
                config_service=self.config_service
            )
            
            # 加载方向分类模型（如果启用）
            if self.use_angle_cls and cls_path:
                if progress_callback:
                    progress_callback(0.4, "正在加载方向分类模型...")
                
                self.cls_session = create_onnx_session(
                    model_path=cls_path,
                    config_service=self.config_service
                )
                logger.info("  方向分类模型已加载 ✓")
            
            if progress_callback:
                progress_callback(0.6, "正在加载识别模型...")
            
            # 加载识别模型
            self.rec_session = create_onnx_session(
                model_path=rec_path,
                config_service=self.config_service
            )
            
            if progress_callback:
                progress_callback(0.9, "正在加载字典...")
            
            # 加载字典（PaddleOCR标准格式）
            with open(dict_path, 'rb') as f:
                lines = f.readlines()
                char_list = []
                for line in lines:
                    char = line.decode('utf-8').strip('\n').strip('\r\n')
                    if char:  # 跳过空行
                        char_list.append(char)
                
                # PaddleOCR字典格式：blank + 字典字符 + 空格
                self.char_dict = ['blank'] + char_list + [' ']
            
            # 获取识别模型的输入输出信息
            rec_input = self.rec_session.get_inputs()[0]
            rec_output = self.rec_session.get_outputs()[0]
            
            # 验证字典前几个字符（用于调试）
            if len(self.char_dict) > 10:
                logger.info(f"  字典前10个字符: {self.char_dict[1:11]}")
            
            # 检查是否包含常见中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in ''.join(self.char_dict[:100]))
            if has_chinese:
                logger.info(f"  字典类型: 包含中文字符 ✓")
            else:
                logger.warning(f"  字典类型: 未检测到中文字符（前100个字符中）")
            
            # 动态获取识别模型的输入高度
            input_shape = rec_input.shape
            if input_shape and len(input_shape) >= 3:
                # 输入格式: (batch, channels, height, width)
                # input_shape[2] 是高度
                if isinstance(input_shape[2], int):
                    self.rec_image_height = input_shape[2]
                    logger.info(f"  识别模型输入高度: {self.rec_image_height} 像素")
                else:
                    # 如果是动态维度，使用默认值
                    logger.warning(f"  识别模型输入高度是动态的: {input_shape[2]}，使用默认值32")
                    self.rec_image_height = 32
            
            # 检查识别模型的输出维度
            output_shape = rec_output.shape
            if output_shape and len(output_shape) >= 3:
                num_classes = output_shape[2]  # 输出类别数
                
                # 如果模型输出类别数大于字典长度，补齐
                while len(self.char_dict) < num_classes:
                    self.char_dict.append(f'<unk_{len(self.char_dict)}>')
                    logger.debug(f"补充字典占位符: <unk_{len(self.char_dict)-1}>")
            
            self.current_model_key = model_key
            
            # 获取实际使用的执行提供者
            actual_providers = self.det_session.get_providers()
            logger.info(f"✓ OCR模型加载成功: {model_key}")
            logger.info(f"  检测模型执行提供者: {actual_providers[0]}")
            logger.info(f"  字符字典大小: {len(self.char_dict)} 个字符（含blank）")
            
            # 友好的提示信息
            provider_info = {
                "CUDAExecutionProvider": "CUDA (NVIDIA GPU 专用加速)",
                "DmlExecutionProvider": "DirectML (通用GPU加速，支持NVIDIA/AMD/Intel)",
                "CoreMLExecutionProvider": "CoreML (Apple Silicon)",
                "CPUExecutionProvider": "CPU"
            }
            friendly_name = provider_info.get(actual_providers[0], actual_providers[0])
            logger.info(f"  加速方式: {friendly_name}")
            
            if progress_callback:
                progress_callback(1.0, "模型加载完成！")
            
            return True, "模型加载成功"
        
        except Exception as e:
            logger.error(f"加载OCR模型失败: {e}")
            self.unload_model()
            return False, f"加载失败: {str(e)}"
    
    def unload_model(self) -> None:
        """卸载模型，释放资源。"""
        try:
            if self.det_session:
                del self.det_session
                self.det_session = None
            
            if self.cls_session:
                del self.cls_session
                self.cls_session = None
            
            if self.rec_session:
                del self.rec_session
                self.rec_session = None
            
            if self.char_dict:
                del self.char_dict
                self.char_dict = None
            
            self.current_model_key = None
            self.rec_image_height = 32  # 重置为默认值
            self.use_angle_cls = True  # 重置为默认值
            
            # 强制垃圾回收
            gc.collect()
            
            logger.info("OCR模型已卸载")
        except Exception as e:
            logger.error(f"卸载OCR模型失败: {e}")
    
    def get_device_info(self) -> str:
        """获取当前使用的设备信息。
        
        Returns:
            设备信息字符串
        """
        if not self.det_session:
            return "未加载"
        
        providers = self.det_session.get_providers()
        if not providers:
            return "未知设备"
        
        provider = providers[0]
        provider_map = {
            'CUDAExecutionProvider': 'NVIDIA GPU (CUDA)',
            'DmlExecutionProvider': 'DirectML GPU',
            'CoreMLExecutionProvider': 'Apple Neural Engine',
            'ROCMExecutionProvider': 'AMD GPU (ROCm)',
            'CPUExecutionProvider': 'CPU',
        }
        return provider_map.get(provider, provider)
    
    def detect_text(self, image: np.ndarray) -> List[np.ndarray]:
        """检测图像中的文本区域。
        
        Args:
            image: 输入图像(BGR格式)
        
        Returns:
            文本框列表，每个框是4个点的坐标
        """
        if not self.det_session:
            raise RuntimeError("检测模型未加载")
        
        # 预处理
        img_resized, ratio_h, ratio_w = self._preprocess_det(image)
        
        # 推理
        input_name = self.det_session.get_inputs()[0].name
        outputs = self.det_session.run(None, {input_name: img_resized})
        
        # 后处理
        boxes = self._postprocess_det(outputs[0], ratio_h, ratio_w, image.shape[:2])
        
        return boxes
    
    def recognize_text(self, image: np.ndarray, boxes: List[np.ndarray]) -> List[Tuple[str, float]]:
        """识别文本框中的文字。
        
        Args:
            image: 输入图像(BGR格式)
            boxes: 文本框列表
        
        Returns:
            识别结果列表 [(文本, 置信度), ...]
        """
        if not self.rec_session or not self.char_dict:
            raise RuntimeError("识别模型未加载")
        
        results = []
        
        for i, box in enumerate(boxes):
            try:
                # 裁剪文本区域
                text_img = self._crop_text_region(image, box)
                
                if text_img is None or text_img.size == 0:
                    logger.debug(f"文本区域 {i+1} 裁剪失败，跳过")
                    results.append(("", 0.0))
                    continue
                
                # 方向分类和旋转（如果启用）
                if self.use_angle_cls and self.cls_session:
                    angle_idx, angle_conf = self._classify_text_angle(text_img)
                    # 如果是180度（angle_idx=1）且置信度>0.9，旋转图像
                    if angle_idx == 1 and angle_conf > 0.9:
                        text_img = self._rotate_image_180(text_img)
                        logger.debug(f"区域 {i+1}: 检测到180度旋转 (置信度: {angle_conf:.3f})")
                
                # 预处理
                img_preprocessed = self._preprocess_rec(text_img)
                
                # 推理
                input_name = self.rec_session.get_inputs()[0].name
                outputs = self.rec_session.run(None, {input_name: img_preprocessed})
                
                # 解码
                text, confidence = self._decode_text(outputs[0])
                
                # 日志记录识别结果（用于调试）
                if text:
                    logger.debug(f"区域 {i+1}: '{text}' (置信度: {confidence:.3f})")
                
                results.append((text, confidence))
                
            except Exception as e:
                logger.warning(f"识别文本区域 {i+1} 失败: {e}，跳过此区域")
                results.append(("", 0.0))
                continue
        
        return results
    
    def ocr(
        self,
        image_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, List[Tuple[List, str, float]]]:
        """执行完整的OCR流程。
        
        Args:
            image_path: 图像路径
            progress_callback: 进度回调
        
        Returns:
            (是否成功, 结果列表) 结果格式: [(box, text, confidence), ...]
        """
        try:
            if not self.det_session or not self.rec_session:
                return False, []
            
            if progress_callback:
                progress_callback(0.1, "正在读取图像...")
            
            # 读取图像 - 支持中文路径
            image = self._read_image_unicode(image_path)
            if image is None:
                logger.error(f"无法读取图像: {image_path}")
                return False, []
            
            if progress_callback:
                progress_callback(0.3, "正在检测文本区域...")
            
            # 检测
            boxes = self.detect_text(image)
            
            if not boxes:
                return True, []  # 没有检测到文本
            
            if progress_callback:
                progress_callback(0.6, f"正在识别文本... (共{len(boxes)}个区域)")
            
            # 识别
            texts = self.recognize_text(image, boxes)
            
            # 在最后统一过滤 score >= 0.5
            all_results = []
            filtered_results = []
            
            for box, (text, conf) in zip(boxes, texts):
                all_results.append((box.tolist(), text, conf))
                
                # 最终过滤：score >= 0.5
                if conf >= 0.5:
                    filtered_results.append((box.tolist(), text, conf))
                    logger.debug(f"✓ '{text}' (置信度: {conf:.3f})")
                elif text:
                    logger.debug(f"✗ 过滤: '{text}' (置信度: {conf:.3f})")
            
            if progress_callback:
                progress_callback(1.0, f"识别完成！有效结果: {len(filtered_results)}/{len(boxes)}")
            
            logger.info(f"OCR检测到 {len(boxes)} 个区域，识别后过滤保留 {len(filtered_results)} 个有效结果（置信度>=0.5）")
            
            return True, filtered_results
        
        except Exception as e:
            logger.error(f"OCR识别失败: {e}")
            return False, []
    
    def ocr_image(
        self,
        image: np.ndarray,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[bool, List[Tuple[List, str, float]]]:
        """对内存中的图像执行OCR。
        
        Args:
            image: BGR格式的numpy图像数组
            progress_callback: 进度回调
        
        Returns:
            (是否成功, 结果列表) 结果格式: [(box, text, confidence), ...]
        """
        try:
            if not self.det_session or not self.rec_session:
                return False, []
            
            if image is None or image.size == 0:
                logger.error("输入图像为空")
                return False, []
            
            if progress_callback:
                progress_callback(0.3, "正在检测文本区域...")
            
            # 检测
            boxes = self.detect_text(image)
            
            if not boxes:
                return True, []  # 没有检测到文本
            
            if progress_callback:
                progress_callback(0.6, f"正在识别文本... (共{len(boxes)}个区域)")
            
            # 识别
            texts = self.recognize_text(image, boxes)
            
            # 过滤 score >= 0.5
            filtered_results = []
            for box, (text, conf) in zip(boxes, texts):
                if conf >= 0.5:
                    filtered_results.append((box.tolist(), text, conf))
            
            if progress_callback:
                progress_callback(1.0, f"识别完成！有效结果: {len(filtered_results)}/{len(boxes)}")
            
            logger.info(f"OCR图像检测到 {len(boxes)} 个区域，过滤保留 {len(filtered_results)} 个有效结果")
            
            return True, filtered_results
        
        except Exception as e:
            logger.error(f"OCR图像识别失败: {e}")
            return False, []
    
    def _preprocess_det(self, image: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """预处理检测输入（PaddleOCR v5 DBNet标准）。
        
        输入要求:
        - 形状: (batch, 3, H, W)
        - H和W必须是32的倍数
        - 归一化: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        - 注意：PaddleOCR使用RGB顺序
        """
        h, w = image.shape[:2]
        
        # 调整大小到32的倍数
        target_h = (h // 32) * 32
        target_w = (w // 32) * 32
        
        if target_h < 32:
            target_h = 32
        if target_w < 32:
            target_w = 32
        
        max_size = 960
        if target_h > max_size:
            target_h = max_size
        if target_w > max_size:
            target_w = max_size
        
        ratio_h = target_h / h
        ratio_w = target_w / w
        
        # 调整大小
        img_resized = cv2.resize(image, (target_w, target_h))
        
        # BGR -> RGB（PaddleOCR标准）
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        
        # 归一化 (PaddleOCR DBNet标准)
        # scale=1.0/255.0, mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
        img_float = img_rgb.astype(np.float32) / 255.0
        
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)
        
        img_normalized = (img_float - mean) / std
        
        # HWC -> CHW: (H, W, 3) -> (3, H, W)
        img_chw = np.transpose(img_normalized, (2, 0, 1))
        
        # 添加batch维度: (3, H, W) -> (1, 3, H, W)
        img_batch = np.expand_dims(img_chw, axis=0).astype(np.float32)
        
        return img_batch, ratio_h, ratio_w
    
    def _postprocess_det(
        self,
        pred: np.ndarray,
        ratio_h: float,
        ratio_w: float,
        orig_shape: Tuple[int, int]
    ) -> List[np.ndarray]:
        """后处理检测结果（PaddleOCR DBNet标准后处理）。
        
        参数（PaddleOCR默认值）:
        - thresh: 0.3 (二值化阈值)
        - box_thresh: 0.6 (框置信度阈值)
        - max_candidates: 1000 (最大候选框数)
        - unclip_ratio: 1.5 (框扩展比例)
        """
        # 二值化阈值
        thresh = 0.3  # 二值化阈值
        box_thresh = 0.6  # 框置信度阈值
        unclip_ratio = 1.5  # 框扩展比例
        min_size = 3  # 最小尺寸
        
        # 获取概率图
        pred = pred[0, 0]
        
        # 二值化
        bitmap = pred > thresh
        mask_uint8 = (bitmap * 255).astype(np.uint8)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        orig_h, orig_w = orig_shape
        
        for contour in contours:
            # 轮廓点数检查
            if len(contour) < 4:
                continue
            
            # 获取最小外接矩形和点
            points, sside = self._get_mini_boxes(contour)
            
            # 最小尺寸过滤
            if sside < min_size:
                continue
            
            points = np.array(points)
            
            # 计算框的得分
            score = self._box_score_fast(pred, points.reshape(-1, 2))
            
            # 置信度过滤
            if score < box_thresh:
                continue
            
            # 框扩展（unclip）
            try:
                from shapely.geometry import Polygon
                import pyclipper
                
                poly = Polygon(points)
                distance = poly.area * unclip_ratio / poly.length
                
                pco = pyclipper.PyclipperOffset()
                pco.AddPath(points.astype(np.int32).tolist(), pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
                expanded = pco.Execute(distance)
                
                if len(expanded) > 0 and expanded[0] is not None:
                    expanded_contour = np.array(expanded[0]).reshape(-1, 1, 2)
                    # 再次调用get_mini_boxes获取最终box
                    box, sside = self._get_mini_boxes(expanded_contour)
                    
                    # 最小尺寸检查（unclip后）
                    if sside < min_size + 2:
                        continue
                    
                    box = np.array(box)
                else:
                    # unclip失败，使用原始points
                    box = points
            except ImportError:
                # pyclipper未安装，使用原始points
                box = points
            except Exception as e:
                logger.debug(f"Unclip失败: {e}，使用原始框")
                box = points
            
            # 坐标clip和round
            box = np.array(box)
            box[:, 0] = np.clip(np.round(box[:, 0]), 0, pred.shape[1])
            box[:, 1] = np.clip(np.round(box[:, 1]), 0, pred.shape[0])
            
            # 检查尺寸（在resize后的图像上）
            rect_width = int(np.linalg.norm(box[0] - box[1]))
            rect_height = int(np.linalg.norm(box[0] - box[3]))
            if rect_width <= min_size or rect_height <= min_size:
                continue
            
            # 还原到原图坐标
            box[:, 0] = box[:, 0] / ratio_w
            box[:, 1] = box[:, 1] / ratio_h
            
            # 确保框在图像范围内
            box[:, 0] = np.clip(box[:, 0], 0, orig_w)
            box[:, 1] = np.clip(box[:, 1], 0, orig_h)
            
            boxes.append(box.astype(np.int32))
        
        return boxes
    
    def _crop_text_region(self, image: np.ndarray, box: np.ndarray) -> Optional[np.ndarray]:
        """裁剪文本区域。
        
        Args:
            image: 原始图像
            box: 文本框坐标（4个点，按顺序）
        
        Returns:
            裁剪后的图像，如果失败返回None
        """
        try:
            # 将box转为float32（保持原始点的顺序）
            points = box.astype(np.float32)
            
            # 计算裁剪区域的宽度和高度（使用欧氏距离）
            img_crop_width = int(max(
                np.linalg.norm(points[0] - points[1]),
                np.linalg.norm(points[2] - points[3])
            ))
            img_crop_height = int(max(
                np.linalg.norm(points[0] - points[3]),
                np.linalg.norm(points[1] - points[2])
            ))
            
            # 检查尺寸有效性
            if img_crop_width <= 0 or img_crop_height <= 0:
                logger.warning(f"无效的文本框尺寸: width={img_crop_width}, height={img_crop_height}")
                return None
            
            # 定义目标矩形的四个角点（标准矩形）
            pts_std = np.array([
                [0, 0],
                [img_crop_width, 0],
                [img_crop_width, img_crop_height],
                [0, img_crop_height]
            ], dtype=np.float32)
            
            # 透视变换（使用PaddleOCR标准参数）
            M = cv2.getPerspectiveTransform(points, pts_std)
            dst_img = cv2.warpPerspective(
                image, 
                M, 
                (img_crop_width, img_crop_height),
                borderMode=cv2.BORDER_REPLICATE,  # 边界复制模式
                flags=cv2.INTER_CUBIC  # 三次插值
            )
            
            # 如果高度明显大于宽度，旋转90度（PaddleOCR标准）
            if dst_img.shape[0] > dst_img.shape[1] * 1.5:
                dst_img = np.rot90(dst_img)
            
            return dst_img
            
        except Exception as e:
            logger.warning(f"裁剪文本区域失败: {e}")
            return None
    
    def _preprocess_rec(self, image: np.ndarray) -> np.ndarray:
        """预处理识别输入（PaddleOCR标准，使用padding保持宽高比）。
        
        输入要求:
        - 形状: (batch, 3, H, W)
        - 固定高度（从模型获取，mobile=32, server=48）
        - 宽度可变（保持宽高比，使用padding）
        - 归一化: (x/255.0 - 0.5) / 0.5
        - 颜色空间: RGB（PaddleOCR标准）
        """
        import math
        
        # 确保是3通道格式
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        
        # BGR -> RGB 转换（PaddleOCR标准）
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        imgC = 3
        imgH = self.rec_image_height  # 动态获取（32或48）
        imgW = 320  # 最大宽度
        max_wh_ratio = imgW / imgH
        
        h, w = image.shape[:2]
        ratio = w / float(h)
        
        # 计算resize后的宽度（保持宽高比）
        if math.ceil(imgH * ratio) > imgW:
            resized_w = imgW
        else:
            resized_w = int(math.ceil(imgH * ratio))
        
        # Resize图像
        resized_image = cv2.resize(image, (resized_w, imgH))
        
        # 转换为CHW格式
        resized_image = resized_image.transpose((2, 0, 1))
        resized_image = resized_image.astype(np.float32)
        
        # 归一化
        resized_image /= 255.0
        resized_image -= 0.5
        resized_image /= 0.5
        
        # 创建padding图像
        padding_im = np.zeros((imgC, imgH, imgW), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        
        # 添加batch维度
        img_batch = np.expand_dims(padding_im, axis=0)
        
        return img_batch
    
    def _decode_text(self, pred: np.ndarray) -> Tuple[str, float]:
        """解码识别结果（CTC解码，参考PaddleOCR标准）。
        
        Args:
            pred: 模型输出 (1, T, num_classes)
        
        Returns:
            (文本, 置信度)
        """
        # 获取预测索引和概率
        pred_idx = np.argmax(pred, axis=2)[0]
        pred_prob = np.max(pred, axis=2)[0]
        
        # CTC解码：去除重复和blank（索引0）
        char_list = []
        conf_list = []
        
        # 创建选择掩码
        selection = np.ones(len(pred_idx), dtype=bool)
        
        # 去除重复（is_remove_duplicate=True）
        selection[1:] = pred_idx[1:] != pred_idx[:-1]
        
        # 去除blank（ignored_tokens=[0]）
        selection &= pred_idx != 0
        
        # 提取字符和置信度
        for idx, conf in zip(pred_idx[selection], pred_prob[selection]):
            if 0 <= idx < len(self.char_dict):
                char_list.append(self.char_dict[idx])
                conf_list.append(float(conf))
            else:
                logger.debug(f"字符索引 {idx} 超出字典范围 (0-{len(self.char_dict)-1})")
        
        text = ''.join(char_list)
        confidence = np.mean(conf_list) if conf_list else 0.0
        
        return text, confidence
    
    def _classify_text_angle(self, image: np.ndarray) -> Tuple[int, float]:
        """分类文本方向。
        
        Args:
            image: 文本图像(BGR格式)
        
        Returns:
            (角度索引, 置信度) - 角度索引: 0=0°, 1=180°
        """
        if not self.cls_session:
            return 0, 1.0  # 如果没有分类模型，假设是0度
        
        try:
            # 预处理
            img_preprocessed = self._preprocess_cls(image)
            
            # 推理
            input_name = self.cls_session.get_inputs()[0].name
            outputs = self.cls_session.run(None, {input_name: img_preprocessed})
            
            # 后处理
            prob = outputs[0][0]
            angle_idx = np.argmax(prob)
            confidence = prob[angle_idx]
            
            return int(angle_idx), float(confidence)
            
        except Exception as e:
            logger.warning(f"方向分类失败: {e}")
            return 0, 1.0
    
    def _preprocess_cls(self, image: np.ndarray) -> np.ndarray:
        """预处理方向分类输入（PaddleOCR标准）。
        
        输入要求:
        - 形状: (batch, 3, 80, 160)
        - 固定高度80，宽度160
        - 保持宽高比，使用padding
        - 归一化: (x/255.0 - 0.5) / 0.5
        - 颜色空间: RGB（PaddleOCR标准）
        """
        import math
        
        # 确保是3通道格式
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        
        # BGR -> RGB 转换（PaddleOCR标准）
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 模型输入尺寸
        imgC, imgH, imgW = 3, 80, 160
        
        h, w = image.shape[:2]
        ratio = w / float(h)
        
        # 计算resize后的宽度（保持宽高比）
        if math.ceil(imgH * ratio) > imgW:
            resized_w = imgW
        else:
            resized_w = int(math.ceil(imgH * ratio))
        
        # Resize图像
        resized_image = cv2.resize(image, (resized_w, imgH))
        
        # 转换为CHW格式
        resized_image = resized_image.transpose((2, 0, 1))
        resized_image = resized_image.astype(np.float32)
        
        # 归一化
        resized_image /= 255.0
        resized_image -= 0.5
        resized_image /= 0.5
        
        # 创建padding图像
        padding_im = np.zeros((imgC, imgH, imgW), dtype=np.float32)
        padding_im[:, :, 0:resized_w] = resized_image
        
        # 添加batch维度
        img_batch = np.expand_dims(padding_im, axis=0)
        
        return img_batch
    
    def _rotate_image_180(self, image: np.ndarray) -> np.ndarray:
        """旋转图像180度。"""
        return cv2.rotate(image, cv2.ROTATE_180)
    
    def _get_mini_boxes(self, contour: np.ndarray) -> Tuple[list, float]:
        """获取最小外接矩形的点。
        
        对点进行特定的排序，确保一致性。
        
        Args:
            contour: 轮廓
        
        Returns:
            (box_points, min_side_length)
        """
        bounding_box = cv2.minAreaRect(contour)
        points = sorted(list(cv2.boxPoints(bounding_box)), key=lambda x: x[0])
        
        index_1, index_2, index_3, index_4 = 0, 1, 2, 3
        if points[1][1] > points[0][1]:
            index_1 = 0
            index_4 = 1
        else:
            index_1 = 1
            index_4 = 0
        if points[3][1] > points[2][1]:
            index_2 = 2
            index_3 = 3
        else:
            index_2 = 3
            index_3 = 2
        
        box = [
            points[index_1], points[index_2], points[index_3], points[index_4]
        ]
        return box, min(bounding_box[1])
    
    def _box_score_fast(self, bitmap: np.ndarray, box: np.ndarray) -> float:
        """快速计算框的得分。
        
        使用bbox的平均得分作为总得分
        """
        h, w = bitmap.shape[:2]
        box_copy = box.copy()
        
        xmin = int(np.clip(np.floor(box_copy[:, 0].min()), 0, w - 1))
        xmax = int(np.clip(np.ceil(box_copy[:, 0].max()), 0, w - 1))
        ymin = int(np.clip(np.floor(box_copy[:, 1].min()), 0, h - 1))
        ymax = int(np.clip(np.ceil(box_copy[:, 1].max()), 0, h - 1))
        
        # 创建mask
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        box_copy[:, 0] = box_copy[:, 0] - xmin
        box_copy[:, 1] = box_copy[:, 1] - ymin
        cv2.fillPoly(mask, box_copy.reshape(1, -1, 2).astype(np.int32), 1)
        
        # 计算平均得分
        return cv2.mean(bitmap[ymin:ymax + 1, xmin:xmax + 1], mask)[0]
    
    def _box_area(self, box: np.ndarray) -> float:
        """计算框的面积。"""
        return cv2.contourArea(box)
    
    def _read_image_unicode(self, image_path: str) -> Optional[np.ndarray]:
        """读取图像，支持Unicode/中文路径。
        
        Args:
            image_path: 图像路径
        
        Returns:
            图像数组，如果读取失败返回None
        """
        try:
            # 使用 numpy 和 cv2.imdecode 来支持中文路径
            # cv2.imread 在 Windows 上不支持 Unicode 路径
            image_path_obj = Path(image_path)
            
            if not image_path_obj.exists():
                logger.error(f"文件不存在: {image_path}")
                return None
            
            # 读取文件为字节流
            with open(image_path_obj, 'rb') as f:
                file_data = f.read()
            
            # 转换为numpy数组
            file_array = np.frombuffer(file_data, dtype=np.uint8)
            
            # 使用cv2.imdecode解码图像
            image = cv2.imdecode(file_array, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error(f"无法解码图像: {image_path}")
                return None
            
            return image
            
        except Exception as e:
            logger.error(f"读取图像失败: {image_path}, 错误: {e}")
            return None
