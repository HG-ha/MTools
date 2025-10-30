# -*- coding: utf-8 -*-
"""背景移除模型配置。

定义所有可用的背景移除模型及其参数。
"""

from dataclasses import dataclass
from typing import Final


@dataclass
class ModelInfo:
    """模型信息数据类。
    
    Attributes:
        name: 模型名称
        display_name: 显示名称
        url: 下载链接
        size_mb: 文件大小(MB)
        quality: 质量描述
        performance: 性能描述
        filename: 文件名
        version: 版本号
    """
    name: str
    display_name: str
    url: str
    size_mb: int
    quality: str
    performance: str
    filename: str
    version: str = "1.4"


# 所有可用的背景移除模型
BACKGROUND_REMOVAL_MODELS: Final[dict[str, ModelInfo]] = {
    "rmbg_1.4_quantized": ModelInfo(
        name="rmbg_1.4_quantized",
        display_name="RMBG 1.4 量化版（推荐）",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-1.4/resolve/master/onnx/model_quantized.onnx",
        size_mb=44,
        quality="中等质量",
        performance="速度快、内存占用低",
        filename="model_quantized.onnx",
        version="1.4"
    ),
    "rmbg_1.4_fp16": ModelInfo(
        name="rmbg_1.4_fp16",
        display_name="RMBG 1.4 半精度",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-1.4/resolve/master/onnx/model_fp16.onnx",
        size_mb=88,
        quality="良好质量",
        performance="速度较快、内存适中",
        filename="model_fp16.onnx",
        version="1.4"
    ),
    "rmbg_1.4_standard": ModelInfo(
        name="rmbg_1.4_standard",
        display_name="RMBG 1.4 标准版",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-1.4/resolve/master/onnx/model.onnx",
        size_mb=176,
        quality="高质量",
        performance="速度中等、内存占用中",
        filename="model.onnx",
        version="1.4"
    ),
    "rmbg_2.0_q4": ModelInfo(
        name="rmbg_2.0_q4",
        display_name="RMBG 2.0 Q4",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0/resolve/master/onnx/model_q4.onnx",
        size_mb=350,
        quality="优秀质量",
        performance="速度较快、内存占用适中",
        filename="model_q4.onnx",
        version="2.0"
    ),
    "rmbg_2.0_q4f16": ModelInfo(
        name="rmbg_2.0_q4f16",
        display_name="RMBG 2.0 Q4F16",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0/resolve/master/onnx/model_q4f16.onnx",
        size_mb=234,
        quality="优秀质量",
        performance="速度较慢、内存占用高",
        filename="model_q4f16.onnx",
        version="2.0"
    ),
    "rmbg_2.0_int8": ModelInfo(
        name="rmbg_2.0_int8",
        display_name="RMBG 2.0 INT8",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0/resolve/master/onnx/model_int8.onnx",
        size_mb=366,
        quality="极高质量",
        performance="速度慢、内存占用很高",
        filename="model_int8.onnx",
        version="2.0"
    ),
    "rmbg_2.0_standard": ModelInfo(
        name="rmbg_2.0_standard",
        display_name="RMBG 2.0 标准版（最佳质量）",
        url="https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0/resolve/master/onnx/model.onnx",
        size_mb=1024,
        quality="最佳质量",
        performance="速度很慢、内存占用非常高",
        filename="model.onnx",
        version="2.0"
    ),
}

# 默认模型（使用原本的 RMBG 2.0 Q4 模型）
DEFAULT_MODEL_KEY: Final[str] = "rmbg_1.4_quantized"

