# -*- coding: utf-8 -*-
"""ONNX Runtime 辅助工具函数。

提供统一的SessionOptions配置和Provider配置功能，避免重复代码。

使用指南（从简单到复杂）:
---------
1. 最简单（推荐）：使用 create_onnx_session() - 一行代码搞定
   >>> session = create_onnx_session(
   ...     model_path=Path("model.onnx"),
   ...     config_service=config_service
   ... )
   >>> result = session.run(None, {'input': data})

2. 需要配置对象：使用 create_onnx_session_config()
   >>> sess_options, providers = create_onnx_session_config(
   ...     config_service=config_service,
   ...     model_path=model_path
   ... )
   >>> session = ort.InferenceSession(model_path, sess_options, providers)

3. 单独配置某一部分：分别使用 create_session_options() 和 create_provider_options()
   >>> sess_options = create_session_options(cpu_threads=4, execution_mode="parallel")
   >>> providers = create_provider_options(config_service=config_service)
   >>> session = ort.InferenceSession(model_path, sess_options, providers)

4. 完全自定义：直接手动配置 SessionOptions 和 Providers
"""

from pathlib import Path
from typing import Optional, Tuple, List, Union, TYPE_CHECKING, Any

try:
    import onnxruntime as ort
except ImportError:
    ort = None

if TYPE_CHECKING:
    from services import ConfigService


def create_session_options(
    enable_memory_arena: bool = True,
    enable_mem_pattern: bool = True,
    enable_mem_reuse: bool = True,
    cpu_threads: int = 0,
    execution_mode: str = "sequential",
    enable_model_cache: bool = False,
    model_path: Optional[Path] = None
) -> Any:  # ort.SessionOptions
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
    
    # 基础内存优化（可按需关闭以便更好释放）
    sess_options.enable_mem_pattern = enable_mem_pattern
    sess_options.enable_mem_reuse = enable_mem_reuse
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
    gpu_memory_limit: int = 2048,
    config_service: Optional['ConfigService'] = None
) -> List[Union[str, Tuple[str, dict]]]:
    """创建统一的Execution Provider配置。
    
    Args:
        use_gpu: 是否使用GPU加速（如果提供config_service，会优先读取gpu_acceleration配置）
        gpu_device_id: GPU设备ID
        gpu_memory_limit: GPU内存限制（MB）
            - 仅对 CUDA Provider 有效
            - DirectML (Windows) 不支持此参数，显存由系统自动管理
        config_service: 配置服务实例（可选，用于读取gpu_acceleration配置）
        
    Returns:
        Provider列表
    """
    if ort is None:
        raise ImportError("需要安装 onnxruntime 库")
    
    # 如果提供了config_service，优先读取gpu_acceleration配置
    if config_service is not None:
        use_gpu = config_service.get_config_value("gpu_acceleration", use_gpu)
    
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
        # 注意：DirectML 不支持 gpu_mem_limit 配置，显存由 Windows WDDM 自动管理
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


def create_onnx_session_config(
    config_service: Optional['ConfigService'] = None,
    gpu_device_id: Optional[int] = None,
    gpu_memory_limit: Optional[int] = None,
    enable_memory_arena: Optional[bool] = None,
    enable_mem_pattern: Optional[bool] = None,
    enable_mem_reuse: Optional[bool] = None,
    cpu_threads: Optional[int] = None,
    execution_mode: Optional[str] = None,
    enable_model_cache: Optional[bool] = None,
    model_path: Optional[Path] = None
) -> Tuple[Any, List[Union[str, Tuple[str, dict]]]]:
    """创建完整的ONNX Runtime会话配置（SessionOptions + Providers）。
    
    这是一个便捷函数，组合了 create_session_options 和 create_provider_options。
    如果提供 config_service，会自动从配置中读取相关参数。
    
    Args:
        config_service: 配置服务实例（可选，用于自动读取配置）
        gpu_device_id: GPU设备ID（None则从配置读取，默认0）
        gpu_memory_limit: GPU内存限制MB（None则从配置读取，默认2048）
        enable_memory_arena: 是否启用CPU内存池（None则从配置读取，默认True）
        cpu_threads: CPU推理线程数（None则从配置读取，默认0=自动）
        execution_mode: 执行模式sequential/parallel（None则从配置读取，默认sequential）
        enable_model_cache: 是否启用模型缓存（None则从配置读取，默认False）
        model_path: 模型路径（用于缓存）
        
    Returns:
        (sess_options, providers) 元组
        
    Example:
        >>> sess_options, providers = create_onnx_session_config(
        ...     config_service=config_service,
        ...     model_path=model_path
        ... )
        >>> session = ort.InferenceSession(
        ...     str(model_path),
        ...     sess_options=sess_options,
        ...     providers=providers
        ... )
    """
    if ort is None:
        raise ImportError("需要安装 onnxruntime 库")
    
    # 从配置服务读取参数（如果提供且参数为None）
    if config_service is not None:
        if gpu_device_id is None:
            gpu_device_id = config_service.get_config_value("gpu_device_id", 0)
        if gpu_memory_limit is None:
            gpu_memory_limit = config_service.get_config_value("gpu_memory_limit", 2048)
        if enable_memory_arena is None:
            enable_memory_arena = config_service.get_config_value("gpu_enable_memory_arena", True)
        if enable_mem_pattern is None:
            enable_mem_pattern = config_service.get_config_value("onnx_enable_mem_pattern", True)
        if enable_mem_reuse is None:
            enable_mem_reuse = config_service.get_config_value("onnx_enable_mem_reuse", True)
        if cpu_threads is None:
            cpu_threads = config_service.get_config_value("onnx_cpu_threads", 0)
        if execution_mode is None:
            execution_mode = config_service.get_config_value("onnx_execution_mode", "sequential")
        if enable_model_cache is None:
            enable_model_cache = config_service.get_config_value("onnx_enable_model_cache", False)
    
    # 设置默认值（如果仍为None）
    if gpu_device_id is None:
        gpu_device_id = 0
    if gpu_memory_limit is None:
        gpu_memory_limit = 2048
    if enable_memory_arena is None:
        enable_memory_arena = True
    if enable_mem_pattern is None:
        enable_mem_pattern = True
    if enable_mem_reuse is None:
        enable_mem_reuse = True
    if cpu_threads is None:
        cpu_threads = 0
    if execution_mode is None:
        execution_mode = "sequential"
    if enable_model_cache is None:
        enable_model_cache = False
    
    # 创建 SessionOptions
    sess_options = create_session_options(
        enable_memory_arena=enable_memory_arena,
        enable_mem_pattern=enable_mem_pattern,
        enable_mem_reuse=enable_mem_reuse,
        cpu_threads=cpu_threads,
        execution_mode=execution_mode,
        enable_model_cache=enable_model_cache,
        model_path=model_path
    )
    
    # 创建 Providers
    providers = create_provider_options(
        gpu_device_id=gpu_device_id,
        gpu_memory_limit=gpu_memory_limit,
        config_service=config_service
    )
    
    return sess_options, providers


def create_onnx_session(
    model_path: Path,
    config_service: Optional['ConfigService'] = None,
    gpu_device_id: Optional[int] = None,
    gpu_memory_limit: Optional[int] = None,
    enable_memory_arena: Optional[bool] = None,
    enable_mem_pattern: Optional[bool] = None,
    enable_mem_reuse: Optional[bool] = None,
    cpu_threads: Optional[int] = None,
    execution_mode: Optional[str] = None,
    enable_model_cache: Optional[bool] = None,
) -> Any:  # ort.InferenceSession
    """创建配置好的ONNX Runtime推理会话（一步到位）。
    
    这是最便捷的函数，直接返回配置好的InferenceSession对象。
    如果提供 config_service，会自动从配置中读取所有参数。
    
    Args:
        model_path: 模型文件路径
        config_service: 配置服务实例（可选，用于自动读取配置）
        gpu_device_id: GPU设备ID（None则从配置读取，默认0）
        gpu_memory_limit: GPU内存限制MB（None则从配置读取，默认2048）
        enable_memory_arena: 是否启用CPU内存池（None则从配置读取，默认True）
        cpu_threads: CPU推理线程数（None则从配置读取，默认0=自动）
        execution_mode: 执行模式sequential/parallel（None则从配置读取，默认sequential）
        enable_model_cache: 是否启用模型缓存（None则从配置读取，默认False）
        
    Returns:
        配置好的 InferenceSession 对象
        
    Raises:
        FileNotFoundError: 模型文件不存在
        ImportError: onnxruntime 未安装
        
    Example:
        >>> # 最简单的用法 - 一行代码搞定
        >>> session = create_onnx_session(
        ...     model_path=Path("model.onnx"),
        ...     config_service=config_service
        ... )
        >>> 
        >>> # 自定义部分参数
        >>> session = create_onnx_session(
        ...     model_path=Path("model.onnx"),
        ...     config_service=config_service,
        ...     cpu_threads=4,
        ...     execution_mode="parallel"
        ... )
    """
    if ort is None:
        raise ImportError("需要安装 onnxruntime 库")
    
    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    # 获取配置
    sess_options, providers = create_onnx_session_config(
        config_service=config_service,
        gpu_device_id=gpu_device_id,
        gpu_memory_limit=gpu_memory_limit,
        enable_memory_arena=enable_memory_arena,
        enable_mem_pattern=enable_mem_pattern,
        enable_mem_reuse=enable_mem_reuse,
        cpu_threads=cpu_threads,
        execution_mode=execution_mode,
        enable_model_cache=enable_model_cache,
        model_path=model_path
    )
    
    # 创建会话
    session = ort.InferenceSession(
        str(model_path),
        sess_options=sess_options,
        providers=providers
    )
    
    return session

