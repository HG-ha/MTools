# -*- coding: utf-8 -*-
"""视频插帧服务。

使用 RIFE (Real-Time Intermediate Flow Estimation) 模型进行视频帧插值。
"""

import gc
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import onnxruntime as ort
from PIL import Image

from constants.model_config import (
    DEFAULT_INTERPOLATION_MODEL_KEY,
    FRAME_INTERPOLATION_MODELS,
    FrameInterpolationModelInfo,
)

logger = logging.getLogger(__name__)


class FrameInterpolationService:
    """视频插帧服务类。
    
    使用 RIFE 模型在两帧之间生成中间帧，实现帧率提升。
    """
    
    def __init__(
        self,
        model_name: str = DEFAULT_INTERPOLATION_MODEL_KEY,
        execution_provider: str = "CUDAExecutionProvider",
        gpu_device_id: int = 0,
        gpu_memory_limit: int = 2048,
        cpu_threads: int = 0,
        execution_mode: str = "sequential",
        enable_model_cache: bool = False
    ) -> None:
        """初始化插帧服务。
        
        Args:
            model_name: 模型名称
            execution_provider: 执行提供者（CUDA/DirectML/CPU）
            gpu_device_id: GPU设备ID，默认0（第一个GPU）
            gpu_memory_limit: GPU内存限制（MB），默认2048MB
            cpu_threads: CPU推理线程数，0=自动检测
            execution_mode: 执行模式（sequential/parallel）
            enable_model_cache: 是否启用模型缓存优化
        """
        self.model_name: str = model_name
        self.execution_provider: str = execution_provider
        self.gpu_device_id: int = gpu_device_id
        self.gpu_memory_limit: int = gpu_memory_limit
        self.cpu_threads: int = cpu_threads
        self.execution_mode: str = execution_mode
        self.enable_model_cache: bool = enable_model_cache
        self.sess: Optional[ort.InferenceSession] = None
        self.model_info: Optional[FrameInterpolationModelInfo] = None
        self.inference_lock = threading.Lock()  # 线程安全锁
        self._first_inference = True  # 标记是否是首次推理（用于调试日志）
        
        logger.info(f"初始化 RIFE 插帧服务: {model_name}")
    
    def load_model(self, model_path: Path) -> None:
        """加载 RIFE 模型。
        
        Args:
            model_path: 模型文件路径
            
        Raises:
            FileNotFoundError: 模型文件不存在
            RuntimeError: 模型加载失败
        """
        if not model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        try:
            # 显示可用的执行提供者
            available_providers = ort.get_available_providers()
            logger.info(f"系统可用的执行提供者: {', '.join(available_providers)}")
            
            # 获取模型信息
            if self.model_name in FRAME_INTERPOLATION_MODELS:
                self.model_info = FRAME_INTERPOLATION_MODELS[self.model_name]
                logger.info(f"加载模型: {self.model_info.display_name}")
                logger.info(f"  版本: {self.model_info.version}")
                logger.info(f"  精度: {self.model_info.precision}")
                logger.info(f"  集成模式: {'是' if self.model_info.ensemble else '否'}")
                logger.info(f"  优化场景: {self.model_info.optimized_for}")
            
            # 配置 ONNX Runtime
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # 应用性能优化参数
            if self.cpu_threads > 0:
                sess_options.intra_op_num_threads = self.cpu_threads
                sess_options.inter_op_num_threads = self.cpu_threads
                logger.info(f"设置CPU线程数: {self.cpu_threads}")
            
            # 执行模式
            if self.execution_mode == "parallel":
                sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
                logger.info("使用并行执行模式 (适合多核CPU)")
            else:
                sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                logger.info("使用顺序执行模式 (节省内存)")
            
            # 模型缓存优化
            if self.enable_model_cache:
                cache_path = model_path.with_suffix('.optimized.onnx')
                sess_options.optimized_model_filepath = str(cache_path)
                logger.info(f"启用模型缓存: {cache_path.name}")
            
            # 检查请求的执行提供者是否可用
            available_providers = ort.get_available_providers()
            
            # 根据执行提供者配置选项
            providers = []
            if self.execution_provider == "CUDAExecutionProvider":
                if "CUDAExecutionProvider" in available_providers:
                    providers = [
                        ("CUDAExecutionProvider", {
                            "device_id": self.gpu_device_id,
                            "arena_extend_strategy": "kNextPowerOfTwo",
                            "gpu_mem_limit": self.gpu_memory_limit * 1024 * 1024,  # 转换为字节
                            "cudnn_conv_algo_search": "EXHAUSTIVE",
                            "do_copy_in_default_stream": True,
                        }),
                        "CPUExecutionProvider"
                    ]
                    logger.info(f"RIFE 使用 CUDA GPU (设备 {self.gpu_device_id}，内存限制 {self.gpu_memory_limit}MB)")
                else:
                    logger.warning("CUDA不可用，自动切换到可用的执行提供者")
                    # 自动回退到DirectML或CPU
                    if "DmlExecutionProvider" in available_providers:
                        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                    else:
                        providers = ["CPUExecutionProvider"]
            elif self.execution_provider == "DmlExecutionProvider":
                if "DmlExecutionProvider" in available_providers:
                    providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                else:
                    logger.warning("DirectML不可用，使用CPU")
                    providers = ["CPUExecutionProvider"]
            else:
                providers = ["CPUExecutionProvider"]
            
            # 加载模型
            self.sess = ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=providers
            )
            
            # 获取实际使用的执行提供者
            actual_providers = self.sess.get_providers()
            logger.info(f"✓ RIFE 模型加载成功")
            logger.info(f"  实际使用的执行提供者: {actual_providers[0]}")
            
            # 友好的提示信息
            provider_info = {
                "CUDAExecutionProvider": "CUDA (NVIDIA GPU 专用加速)",
                "DmlExecutionProvider": "DirectML (通用GPU加速，支持NVIDIA/AMD/Intel)",
                "CPUExecutionProvider": "CPU"
            }
            friendly_name = provider_info.get(actual_providers[0], actual_providers[0])
            logger.info(f"  加速方式: {friendly_name}")
            
            # 显示输入输出信息
            input_info = self.sess.get_inputs()
            output_info = self.sess.get_outputs()
            logger.info(f"  输入: {[inp.name for inp in input_info]}")
            logger.info(f"  输出: {[out.name for out in output_info]}")
            
            # 显示数据类型信息
            if input_info:
                input_type = str(input_info[0].type)
                logger.info(f"  输入数据类型: {input_type}")
                if 'float16' in input_type:
                    logger.info(f"  ✓ 模型使用 FP16 精度（显存占用减半，速度更快）")
                else:
                    logger.info(f"  ✓ 模型使用 FP32 精度（标准精度）")
            
        except Exception as e:
            logger.error(f"加载 RIFE 模型失败: {e}")
            raise RuntimeError(f"模型加载失败: {e}")
    
    def unload_model(self) -> None:
        """卸载模型并释放内存。"""
        if self.sess:
            self.sess = None
            self._first_inference = True  # 重置标志
            gc.collect()
            logger.info("RIFE 模型已卸载")
    
    def get_device_info(self) -> str:
        """获取设备信息。"""
        if not self.sess:
            return "未加载模型"
        
        providers = self.sess.get_providers()
        if "CUDAExecutionProvider" in providers:
            return "CUDA (NVIDIA专用)"
        elif "DmlExecutionProvider" in providers:
            return "DirectML (通用GPU)"
        else:
            return "CPU"
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """预处理帧数据。
        
        Args:
            frame: RGB 格式的帧 (H, W, 3)，值范围 0-255
            
        Returns:
            预处理后的帧 (1, 3, H, W)，值范围 0-1
        """
        # 转换为浮点并归一化到 [0, 1]
        frame = frame.astype(np.float32) / 255.0
        
        # 转换为 CHW 格式并添加 batch 维度
        frame = np.transpose(frame, (2, 0, 1))  # HWC -> CHW
        frame = np.expand_dims(frame, axis=0)   # CHW -> 1CHW
        
        # 根据模型精度转换数据类型
        if self.sess and self.model_info:
            if self.model_info.precision == "fp16":
                frame = frame.astype(np.float16)
        
        return frame
    
    def postprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """后处理帧数据。
        
        Args:
            frame: 模型输出 (1, 3, H, W)，值范围 0-1，可能是 float16 或 float32
            
        Returns:
            RGB 格式的帧 (H, W, 3)，值范围 0-255
        """
        # 如果是 FP16，先转换为 FP32（用于后续计算）
        if frame.dtype == np.float16:
            frame = frame.astype(np.float32)
        
        # 移除 batch 维度并转换为 HWC 格式
        frame = frame[0]  # 1CHW -> CHW
        frame = np.transpose(frame, (1, 2, 0))  # CHW -> HWC
        
        # 钳制到 [0, 1] 并转换为 uint8
        frame = np.clip(frame, 0, 1)
        frame = (frame * 255).astype(np.uint8)
        
        return frame
    
    def interpolate(
        self,
        frame0: np.ndarray,
        frame1: np.ndarray,
        timestep: float = 0.5,
        pad_to_multiple: int = 32
    ) -> np.ndarray:
        """在两帧之间插值生成中间帧。
        
        Args:
            frame0: 第一帧 RGB 图像 (H, W, 3)，值范围 0-255
            frame1: 第二帧 RGB 图像 (H, W, 3)，值范围 0-255
            timestep: 时间步长，0.5 表示生成正中间的帧，范围 [0, 1]
            pad_to_multiple: 填充到的倍数（RIFE 通常需要32的倍数）
            
        Returns:
            插值后的帧 (H, W, 3)，值范围 0-255
        """
        if self.sess is None:
            raise RuntimeError("模型未加载，请先调用 load_model()")
        
        # 获取原始尺寸（保存用于最后裁剪）
        orig_h, orig_w = frame0.shape[:2]
        
        # 计算填充后的尺寸
        pad_h = ((orig_h - 1) // pad_to_multiple + 1) * pad_to_multiple
        pad_w = ((orig_w - 1) // pad_to_multiple + 1) * pad_to_multiple
        
        # 如果需要填充
        if orig_h != pad_h or orig_w != pad_w:
            # 创建填充后的帧
            frame0_padded = np.zeros((pad_h, pad_w, 3), dtype=frame0.dtype)
            frame1_padded = np.zeros((pad_h, pad_w, 3), dtype=frame1.dtype)
            
            # 复制原始帧到填充帧
            frame0_padded[:orig_h, :orig_w] = frame0
            frame1_padded[:orig_h, :orig_w] = frame1
            
            frame0 = frame0_padded
            frame1 = frame1_padded
        
        # 预处理
        img0 = self.preprocess_frame(frame0)
        img1 = self.preprocess_frame(frame1)
        
        # 准备输入
        # RIFE 模型的输入格式
        input_names = [inp.name for inp in self.sess.get_inputs()]
        input_shapes = [inp.shape for inp in self.sess.get_inputs()]
        
        # 构建输入字典
        inputs = {}
        
        if len(input_names) == 1:
            # 单输入模式：检查期望的通道数
            expected_channels = input_shapes[0][1] if len(input_shapes[0]) > 1 else None
            
            if expected_channels == 8:
                # 需要 8 通道：img0 (3) + img1 (3) + timestep_map (2)
                # 创建 timestep 通道（两个通道，值都是 timestep）
                h, w = img0.shape[2], img0.shape[3]
                timestep_map = np.full((1, 2, h, w), timestep, dtype=img0.dtype)
                concatenated = np.concatenate([img0, img1, timestep_map], axis=1)
                
                if self._first_inference:
                    logger.info(f"✓ 使用8通道模式 (6ch frames + 2ch timestep): {input_names[0]}")
                    logger.info(f"  shape: {concatenated.shape}, dtype: {concatenated.dtype}")
            
            elif expected_channels == 7:
                # 需要 7 通道：img0 (3) + img1 (3) + timestep (1)
                h, w = img0.shape[2], img0.shape[3]
                timestep_map = np.full((1, 1, h, w), timestep, dtype=img0.dtype)
                concatenated = np.concatenate([img0, img1, timestep_map], axis=1)
                
                if self._first_inference:
                    logger.info(f"✓ 使用7通道模式 (6ch frames + 1ch timestep): {input_names[0]}")
                    logger.info(f"  shape: {concatenated.shape}, dtype: {concatenated.dtype}")
            
            else:
                # 标准 6 通道：img0 (3) + img1 (3)
                concatenated = np.concatenate([img0, img1], axis=1)
                
                if self._first_inference:
                    logger.info(f"✓ 使用6通道模式 (标准): {input_names[0]}")
                    logger.info(f"  shape: {concatenated.shape}, dtype: {concatenated.dtype}")
            
            inputs[input_names[0]] = concatenated
        
        elif len(input_names) >= 2:
            # 多输入模式：分别输入img0和img1
            inputs[input_names[0]] = img0
            inputs[input_names[1]] = img1
            
            if self._first_inference:
                logger.info(f"✓ 使用多输入模式: {input_names[0]}, {input_names[1]}, dtype: {img0.dtype}")
            
            # 某些 RIFE 版本需要 timestep 参数
            if len(input_names) >= 3:
                timestep_input = np.array([timestep], dtype=np.float32)
                if self.model_info and self.model_info.precision == "fp16":
                    timestep_input = timestep_input.astype(np.float16)
                inputs[input_names[2]] = timestep_input
                
                if self._first_inference:
                    logger.info(f"✓ 添加 timestep 参数: {input_names[2]}")
        
        if self._first_inference:
            self._first_inference = False
        
        # 推理（加锁以支持 DirectML）
        with self.inference_lock:
            outputs = self.sess.run(None, inputs)
        
        # 后处理
        output_frame = self.postprocess_frame(outputs[0])
        
        # 如果进行了填充，裁剪回原始尺寸
        if output_frame.shape[0] != orig_h or output_frame.shape[1] != orig_w:
            output_frame = output_frame[:orig_h, :orig_w]
        
        return output_frame
    
    def interpolate_n_times(
        self,
        frame0: np.ndarray,
        frame1: np.ndarray,
        n: int = 1
    ) -> list[np.ndarray]:
        """在两帧之间生成 n 个中间帧。
        
        Args:
            frame0: 第一帧
            frame1: 第二帧
            n: 要生成的中间帧数量
            
        Returns:
            中间帧列表，长度为 n
        """
        frames = []
        for i in range(1, n + 1):
            timestep = i / (n + 1)
            frame = self.interpolate(frame0, frame1, timestep)
            frames.append(frame)
        
        return frames
    
    def increase_fps(
        self,
        frames: list[np.ndarray],
        target_fps_multiplier: float = 2.0
    ) -> list[np.ndarray]:
        """提升帧率。
        
        Args:
            frames: 原始帧列表
            target_fps_multiplier: 目标帧率倍数（2.0 = 2倍帧率）
            
        Returns:
            插帧后的帧列表
        """
        if target_fps_multiplier <= 1.0:
            return frames
        
        # 计算每对帧之间需要插入的帧数
        n_frames_between = int(target_fps_multiplier) - 1
        
        output_frames = []
        for i in range(len(frames) - 1):
            # 添加当前帧
            output_frames.append(frames[i])
            
            # 插入中间帧
            if n_frames_between > 0:
                interpolated = self.interpolate_n_times(
                    frames[i],
                    frames[i + 1],
                    n_frames_between
                )
                output_frames.extend(interpolated)
        
        # 添加最后一帧
        output_frames.append(frames[-1])
        
        return output_frames

