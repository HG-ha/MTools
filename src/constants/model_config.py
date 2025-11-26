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
        invert_output: 是否反转输出 (True=模型输出伴奏, False=模型输出人声)
    """
    name: str
    display_name: str
    url: str
    size_mb: int
    quality: str
    performance: str
    filename: str
    version: str = "1.4"
    invert_output: bool = False  # 默认模型输出人声


# 所有可用的背景移除模型
BACKGROUND_REMOVAL_MODELS: Final[dict[str, ModelInfo]] = {
    "rmbg_1.4_quantized": ModelInfo(
        name="rmbg_1.4_quantized",
        display_name="RMBG 1.4 量化版（推荐）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/1.4/model_quantized.onnx",
        size_mb=44,
        quality="中等质量",
        performance="速度快、内存占用低",
        filename="model_quantized.onnx",
        version="1.4"
    ),
    "rmbg_1.4_fp16": ModelInfo(
        name="rmbg_1.4_fp16",
        display_name="RMBG 1.4 半精度",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/1.4/model_fp16.onnx",
        size_mb=88,
        quality="良好质量",
        performance="速度较快、内存适中",
        filename="model_fp16.onnx",
        version="1.4"
    ),
    "rmbg_1.4_standard": ModelInfo(
        name="rmbg_1.4_standard",
        display_name="RMBG 1.4 标准版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/1.4/model.onnx",
        size_mb=176,
        quality="高质量",
        performance="速度中等、内存占用中",
        filename="model.onnx",
        version="1.4"
    ),
    "rmbg_2.0_q4": ModelInfo(
        name="rmbg_2.0_q4",
        display_name="RMBG 2.0 Q4",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/2.0/model_q4.onnx",
        size_mb=350,
        quality="优秀质量",
        performance="速度较快、内存占用适中",
        filename="model_q4.onnx",
        version="2.0"
    ),
    "rmbg_2.0_q4f16": ModelInfo(
        name="rmbg_2.0_q4f16",
        display_name="RMBG 2.0 Q4F16",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/2.0/model_q4f16.onnx",
        size_mb=234,
        quality="优秀质量",
        performance="速度较慢、内存占用高",
        filename="model_q4f16.onnx",
        version="2.0"
    ),
    "rmbg_2.0_int8": ModelInfo(
        name="rmbg_2.0_int8",
        display_name="RMBG 2.0 INT8",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/2.0/model_int8.onnx",
        size_mb=366,
        quality="极高质量",
        performance="速度慢、内存占用很高",
        filename="model_int8.onnx",
        version="2.0"
    ),
    "rmbg_2.0_standard": ModelInfo(
        name="rmbg_2.0_standard",
        display_name="RMBG 2.0 标准版（最佳质量）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/RMBG/2.0/model.onnx",
        size_mb=1024,
        quality="最佳质量",
        performance="速度很慢、内存占用非常高",
        filename="model.onnx",
        version="2.0"
    ),
    "birefnet_fp16": ModelInfo(
        name="birefnet_fp16",
        display_name="BiRefNet FP16（高精度）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/birefnet/1.0/model_fp16.onnx",
        size_mb=490,
        quality="极高质量",
        performance="速度较慢、内存占用高",
        filename="model_fp16.onnx",
        version="birefnet_1.0"
    ),
    "birefnet_standard": ModelInfo(
        name="birefnet_standard",
        display_name="BiRefNet 标准版（顶级质量）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/background_removal/birefnet/1.0/model.onnx",
        size_mb=973,
        quality="顶级质量",
        performance="速度很慢、内存占用极高",
        filename="model.onnx",
        version="birefnet_1.0"
    ),
}

# 默认模型（使用原本的 RMBG 1.4 量化版模型）
DEFAULT_MODEL_KEY: Final[str] = "rmbg_1.4_quantized"


# 人声分离模型配置
VOCAL_SEPARATION_MODELS: Final[dict[str, ModelInfo]] = {
    "kim_vocal_2": ModelInfo(
        name="kim_vocal_2",
        display_name="Kim Vocal 2（推荐）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/Kim_Vocal_2.onnx",
        size_mb=50,
        quality="高质量人声分离 - 专为人声优化",
        performance="速度快、人声清晰、乐器残留少",
        filename="Kim_Vocal_2.onnx",
        version="1.0"
    ),
    "uvr_mdx_net_voc_ft": ModelInfo(
        name="uvr_mdx_net_voc_ft",
        display_name="UVR MDX-NET Voc FT",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR_MDXNET_KARA_2.onnx",
        size_mb=50,
        quality="高质量卡拉OK伴奏制作",
        performance="适合提取清晰人声、制作卡拉OK",
        filename="UVR_MDXNET_KARA_2.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏，需要反转
    ),
    "uvr_mdx_net_inst_main": ModelInfo(
        name="uvr_mdx_net_inst_main",
        display_name="UVR MDX-NET Main",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR_MDXNET_Main.onnx",
        size_mb=50,
        quality="通用场景 - 稳定可靠",
        performance="适合各类音乐风格、兼容性强、不易出错",
        filename="UVR_MDXNET_Main.onnx",
        version="1.0"
    ),
    "uvr_mdx_net_inst_1": ModelInfo(
        name="uvr_mdx_net_inst_1",
        display_name="UVR MDX-NET Inst 1",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_1.onnx",
        size_mb=50,
        quality="纯伴奏提取 - 保留乐器细节",
        performance="伴奏质量高、适合音乐制作",
        filename="UVR-MDX-NET-Inst_1.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "uvr_mdx_net_inst_2": ModelInfo(
        name="uvr_mdx_net_inst_2",
        display_name="UVR MDX-NET Inst 2",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_2.onnx",
        size_mb=50,
        quality="伴奏提取 - 平衡版",
        performance="人声与伴奏分离均衡",
        filename="UVR-MDX-NET-Inst_2.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "uvr_mdx_net_inst_3": ModelInfo(
        name="uvr_mdx_net_inst_3",
        display_name="UVR MDX-NET Inst 3",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_3.onnx",
        size_mb=50,
        quality="伴奏提取 - 增强版",
        performance="更干净的伴奏分离",
        filename="UVR-MDX-NET-Inst_3.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "uvr_mdx_net_inst_hq_1": ModelInfo(
        name="uvr_mdx_net_inst_hq_1",
        display_name="UVR MDX-NET Inst HQ 1",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_HQ_1.onnx",
        size_mb=50,
        quality="高质量伴奏提取",
        performance="HQ版本、音质更佳",
        filename="UVR-MDX-NET-Inst_HQ_1.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "uvr_mdx_net_inst_hq_2": ModelInfo(
        name="uvr_mdx_net_inst_hq_2",
        display_name="UVR MDX-NET Inst HQ 2",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_HQ_2.onnx",
        size_mb=50,
        quality="高质量伴奏提取 - 改进版",
        performance="比 HQ 1 更好的分离效果",
        filename="UVR-MDX-NET-Inst_HQ_2.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "uvr_mdx_net_inst_hq_3": ModelInfo(
        name="uvr_mdx_net_inst_hq_3",
        display_name="UVR MDX-NET Inst HQ 3（高质量）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/UVR-MDX-NET-Inst_HQ_3.onnx",
        size_mb=50,
        quality="顶级伴奏提取质量",
        performance="最佳音质、伴奏最干净",
        filename="UVR-MDX-NET-Inst_HQ_3.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
    "kim_inst": ModelInfo(
        name="kim_inst",
        display_name="Kim Inst",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/vocal_separation/Kim_Inst.onnx",
        size_mb=50,
        quality="Kim系列 - 伴奏专用",
        performance="与Kim Vocal 2配套使用",
        filename="Kim_Inst.onnx",
        version="1.0",
        invert_output=True  # 此模型输出伴奏
    ),
}

# 默认人声分离模型
DEFAULT_VOCAL_MODEL_KEY: Final[str] = "kim_vocal_2"


# 图像增强模型配置（Real-ESRGAN）
@dataclass
class ImageEnhanceModelInfo(ModelInfo):
    """图像增强模型信息（扩展ModelInfo以支持多文件）。
    
    Attributes:
        data_url: 权重数据文件的下载链接（用于大型模型）
        data_filename: 权重数据文件名
        scale: 放大倍数
    """
    data_url: str = ""
    data_filename: str = ""
    scale: int = 4


IMAGE_ENHANCE_MODELS: Final[dict[str, ImageEnhanceModelInfo]] = {
    "realesrgan_x4plus": ImageEnhanceModelInfo(
        name="realesrgan_x4plus",
        display_name="Real-ESRGAN x4 Plus（推荐）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/Real-ESRGAN/x4-plus/model.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/Real-ESRGAN/x4-plus/model.data",
        size_mb=67,
        quality="高质量图像超分辨率",
        performance="4倍放大、适合真实照片",
        filename="model.onnx",
        data_filename="model.data",
        version="x4plus",
        scale=4
    ),
}

# 默认图像增强模型
DEFAULT_ENHANCE_MODEL_KEY: Final[str] = "realesrgan_x4plus"

