# -*- coding: utf-8 -*-
"""ONNX Runtime 辅助工具函数。

提供统一的SessionOptions配置和Provider配置功能，避免重复代码。
"""

from pathlib import Path
from typing import Optional, Tuple, List, Union

try:
    import onnxruntime as ort
except ImportError:
    ort = None


def create_session_options(
    enable_memory_arena: bool = True,
    cpu_threads: int = 0,
    execution_mode: str = "sequential",
    enable_model_cache: bool = False,
    model_path: Optional[Path] = None
) -> 'ort.SessionOptions':
    """创建统一配置的SessionOptions。
    
    Args:
        enable_memory_arena: 是否启用CPU内存池
        cpu_threads: CPU推理线程数，0=自动检测
        execution_mode: 执行模式（sequential/parallel）
        enable_model_cache: 是否启用模型缓存优化
        model_path: 模型路径（用于缓存）
        
    Returns:
        配置好的SessionOptions对象
    """
    if ort is None:
        raise ImportError("需要安装 onnxruntime 库")
    
    sess_options = ort.SessionOptions()
    
    # 基础内存优化
    sess_options.enable_mem_pattern = True
    sess_options.enable_mem_reuse = True
    sess_options.enable_cpu_mem_arena = enable_memory_arena
    
    # 图优化
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    
    # 日志级别（ERROR）
    sess_options.log_severity_level = 3
    
    # CPU线程数
    if cpu_threads > 0:
        sess_options.intra_op_num_threads = cpu_threads
        sess_options.inter_op_num_threads = cpu_threads
    
    # 执行模式
    if execution_mode == "parallel":
        sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
    else:
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    
    # 模型缓存
    if enable_model_cache and model_path:
        cache_path = model_path.with_suffix('.optimized.onnx')
        sess_options.optimized_model_filepath = str(cache_path)
    
    return sess_options


def create_provider_options(
    use_gpu: bool = True,
    gpu_device_id: int = 0,
    gpu_memory_limit: int = 2048
) -> List[Union[str, Tuple[str, dict]]]:
    """创建统一的Execution Provider配置。
    
    Args:
        use_gpu: 是否使用GPU加速
        gpu_device_id: GPU设备ID
        gpu_memory_limit: GPU内存限制（MB）
        
    Returns:
        Provider列表
    """
    if ort is None:
        raise ImportError("需要安装 onnxruntime 库")
    
    providers = []
    
    if use_gpu:
        available_providers = ort.get_available_providers()
        
        # 1. CUDA (NVIDIA GPU)
        if 'CUDAExecutionProvider' in available_providers:
            providers.append(('CUDAExecutionProvider', {
                'device_id': gpu_device_id,
                'arena_extend_strategy': 'kNextPowerOfTwo',
                'gpu_mem_limit': gpu_memory_limit * 1024 * 1024,
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            }))
        # 2. DirectML (Windows 通用 GPU)
        elif 'DmlExecutionProvider' in available_providers:
            providers.append('DmlExecutionProvider')
        # 3. CoreML (macOS Apple Silicon)
        elif 'CoreMLExecutionProvider' in available_providers:
            providers.append('CoreMLExecutionProvider')
        # 4. ROCm (AMD)
        elif 'ROCMExecutionProvider' in available_providers:
            providers.append('ROCMExecutionProvider')
    
    # CPU作为后备
    providers.append('CPUExecutionProvider')
    
    return providers

