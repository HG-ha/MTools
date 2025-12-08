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
        scale: 放大倍数（默认倍率）
        min_scale: 最小支持的放大倍率
        max_scale: 最大支持的放大倍率
        support_custom_scale: 是否支持自定义放大倍率
    """
    data_url: str = ""
    data_filename: str = ""
    scale: int = 4
    min_scale: float = 1.0
    max_scale: float = 4.0
    support_custom_scale: bool = True


IMAGE_ENHANCE_MODELS: Final[dict[str, ImageEnhanceModelInfo]] = {
    # Real-ESRGAN x4 系列
    "RealESRGAN_x4plus": ImageEnhanceModelInfo(
        name="RealESRGAN_x4plus",
        display_name="Real-ESRGAN x4plus（推荐）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x4plus.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x4plus.onnx.data",
        size_mb=67,
        quality="高质量真实照片超分辨率",
        performance="4倍放大、适合真实照片、通用场景",
        filename="RealESRGAN_x4plus.onnx",
        data_filename="RealESRGAN_x4plus.onnx.data",
        version="x4plus",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
    "RealESRGAN_x4plus_anime_6B": ImageEnhanceModelInfo(
        name="RealESRGAN_x4plus_anime_6B",
        display_name="Real-ESRGAN x4plus Anime（动漫专用）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x4plus_anime_6B.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x4plus_anime_6B.onnx.data",
        size_mb=18,
        quality="动漫/插画专用超分辨率",
        performance="4倍放大、针对动漫和插画优化",
        filename="RealESRGAN_x4plus_anime_6B.onnx",
        data_filename="RealESRGAN_x4plus_anime_6B.onnx.data",
        version="x4plus_anime",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
    # "RealESRGAN_x2plus": ImageEnhanceModelInfo(
    #     name="RealESRGAN_x2plus",
    #     display_name="Real-ESRGAN x2plus（2倍）",
    #     url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x2plus.onnx",
    #     data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRGAN_x2plus.onnx.data",
    #     size_mb=67,
    #     quality="2倍高质量超分辨率（暂时禁用：输入通道不兼容）",
    #     performance="2倍放大、速度更快、适合轻度增强",
    #     filename="RealESRGAN_x2plus.onnx",
    #     data_filename="RealESRGAN_x2plus.onnx.data",
    #     version="x2plus",
    #     scale=2,
    #     min_scale=1.0,
    #     max_scale=2.0,
    #     support_custom_scale=True
    # ),
    "RealESRNet_x4plus": ImageEnhanceModelInfo(
        name="RealESRNet_x4plus",
        display_name="Real-ESRNet x4plus（无GAN）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRNet_x4plus.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/RealESRNet_x4plus.onnx.data",
        size_mb=67,
        quality="4倍超分辨率（无GAN锐化）",
        performance="4倍放大、更自然柔和、适合保守增强",
        filename="RealESRNet_x4plus.onnx",
        data_filename="RealESRNet_x4plus.onnx.data",
        version="esrnet_x4plus",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
    
    # Real-ESRGAN V3 系列（轻量级）
    "realesr-general-x4v3": ImageEnhanceModelInfo(
        name="realesr-general-x4v3",
        display_name="Real-ESRGAN General x4 V3（通用）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-general-x4v3.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-general-x4v3.onnx.data",
        size_mb=5,
        quality="通用4倍超分辨率（轻量）",
        performance="4倍放大、速度快、体积小、通用场景",
        filename="realesr-general-x4v3.onnx",
        data_filename="realesr-general-x4v3.onnx.data",
        version="general_x4v3",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
    "realesr-general-wdn-x4v3": ImageEnhanceModelInfo(
        name="realesr-general-wdn-x4v3",
        display_name="Real-ESRGAN General WDN x4 V3（降噪）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-general-wdn-x4v3.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-general-wdn-x4v3.onnx.data",
        size_mb=5,
        quality="通用4倍超分+降噪（轻量）",
        performance="4倍放大、降噪处理、适合有噪点的图片",
        filename="realesr-general-wdn-x4v3.onnx",
        data_filename="realesr-general-wdn-x4v3.onnx.data",
        version="general_wdn_x4v3",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
    "realesr-animevideov3": ImageEnhanceModelInfo(
        name="realesr-animevideov3",
        display_name="Real-ESRGAN Anime Video V3（动漫视频）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-animevideov3.onnx",
        data_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/upscayl/realesr-animevideov3.onnx.data",
        size_mb=3,
        quality="动漫视频专用（超轻量）",
        performance="4倍放大、针对动漫视频优化、极速处理",
        filename="realesr-animevideov3.onnx",
        data_filename="realesr-animevideov3.onnx.data",
        version="animevideov3",
        scale=4,
        min_scale=1.0,
        max_scale=4.0,
        support_custom_scale=True
    ),
}

# 默认图像增强模型
DEFAULT_ENHANCE_MODEL_KEY: Final[str] = "RealESRGAN_x4plus"


# 视频插帧模型配置（RIFE）
@dataclass
class FrameInterpolationModelInfo(ModelInfo):
    """视频插帧模型信息。
    
    Attributes:
        precision: 精度类型（fp32/fp16）
        ensemble: 是否使用集成模式
        optimized_for: 优化场景（真人/动漫）
        recommended: 是否推荐
        vram_usage: 显存占用描述
    """
    precision: str = "fp32"
    ensemble: bool = False
    optimized_for: str = "通用"
    recommended: bool = False
    vram_usage: str = "中等"


FRAME_INTERPOLATION_MODELS: Final[dict[str, FrameInterpolationModelInfo]] = {
    # RIFE 4.9 - 真人视频优化
    "rife49_fast": FrameInterpolationModelInfo(
        name="rife49_fast",
        display_name="RIFE 4.9 快速版（推荐）",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife49_ensembleFalse_op18_fp16_clamp_sim.onnx",
        size_mb=11,
        quality="高质量",
        performance="极速 | 显存占用低",
        filename="rife49_ensembleFalse_op18_fp16_clamp_sim.onnx",
        version="v4.9",
        precision="fp16",
        ensemble=False,
        optimized_for="真人视频",
        recommended=True,
        vram_usage="低 (2-3GB)"
    ),
    "rife49_standard": FrameInterpolationModelInfo(
        name="rife49_standard",
        display_name="RIFE 4.9 标准版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife49_ensembleFalse_op18_clamp_sim.onnx",
        size_mb=21,
        quality="高质量",
        performance="快速 | 显存占用中等",
        filename="rife49_ensembleFalse_op18_clamp_sim.onnx",
        version="v4.9",
        precision="fp32",
        ensemble=False,
        optimized_for="真人视频",
        recommended=False,
        vram_usage="中等 (3-4GB)"
    ),
    "rife49_quality": FrameInterpolationModelInfo(
        name="rife49_quality",
        display_name="RIFE 4.9 高质量版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife49_ensembleTrue_op18_clamp_sim.onnx",
        size_mb=21,
        quality="极致质量",
        performance="较快 | 显存占用中等",
        filename="rife49_ensembleTrue_op18_clamp_sim.onnx",
        version="v4.9",
        precision="fp32",
        ensemble=True,
        optimized_for="真人视频",
        recommended=False,
        vram_usage="中等 (4-6GB)"
    ),
    "rife49_quality_fp16": FrameInterpolationModelInfo(
        name="rife49_quality_fp16",
        display_name="RIFE 4.9 高质量FP16版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife49_ensembleTrue_op18_fp16_clamp_sim.onnx",
        size_mb=11,
        quality="极致质量",
        performance="快速 | 显存占用低",
        filename="rife49_ensembleTrue_op18_fp16_clamp_sim.onnx",
        version="v4.9",
        precision="fp16",
        ensemble=True,
        optimized_for="真人视频",
        recommended=False,
        vram_usage="低 (3-4GB)"
    ),
    
    # RIFE 4.8 - 动漫视频优化
    "rife48_anime_fast": FrameInterpolationModelInfo(
        name="rife48_anime_fast",
        display_name="RIFE 4.8 动漫快速版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife48_ensembleFalse_op18_fp16_clamp_sim.onnx",
        size_mb=11,
        quality="高质量",
        performance="极速 | 显存占用低",
        filename="rife48_ensembleFalse_op18_fp16_clamp_sim.onnx",
        version="v4.8",
        precision="fp16",
        ensemble=False,
        optimized_for="动漫视频",
        recommended=False,
        vram_usage="低 (2-3GB)"
    ),
    "rife48_anime_standard": FrameInterpolationModelInfo(
        name="rife48_anime_standard",
        display_name="RIFE 4.8 动漫标准版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife48_ensembleFalse_op18_clamp_sim.onnx",
        size_mb=21,
        quality="高质量",
        performance="快速 | 显存占用中等",
        filename="rife48_ensembleFalse_op18_clamp_sim.onnx",
        version="v4.8",
        precision="fp32",
        ensemble=False,
        optimized_for="动漫视频",
        recommended=False,
        vram_usage="中等 (3-4GB)"
    ),
    "rife48_anime_quality": FrameInterpolationModelInfo(
        name="rife48_anime_quality",
        display_name="RIFE 4.8 动漫高质量版",
        url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/RIFE/rife48_ensembleTrue_op18_clamp_sim.onnx",
        size_mb=21,
        quality="极致质量",
        performance="较快 | 显存占用中等",
        filename="rife48_ensembleTrue_op18_clamp_sim.onnx",
        version="v4.8",
        precision="fp32",
        ensemble=True,
        optimized_for="动漫视频",
        recommended=False,
        vram_usage="中等 (4-6GB)"
    ),
}

# 默认插帧模型
DEFAULT_INTERPOLATION_MODEL_KEY: Final[str] = "rife49_fast"


@dataclass
class WhisperModelInfo:
    """Whisper 模型信息数据类。
    
    Attributes:
        name: 模型名称
        display_name: 显示名称
        encoder_url: 编码器模型下载链接
        decoder_url: 解码器模型下载链接
        config_url: tokens.txt 下载链接
        size_mb: 总文件大小(MB)
        quality: 质量描述
        performance: 性能描述
        encoder_filename: 编码器文件名
        decoder_filename: 解码器文件名
        config_filename: 配置文件名（通常是 tokens.txt）
        language_support: 支持的语言
        version: 版本号
        precision: 精度类型（fp32/int8）
        encoder_weights_url: 编码器外部权重文件URL（可选，用于 large-v3 等）
        decoder_weights_url: 解码器外部权重文件URL（可选，用于 large-v3 等）
        encoder_weights_filename: 编码器外部权重文件名（可选）
        decoder_weights_filename: 解码器外部权重文件名（可选）
    """
    name: str
    display_name: str
    encoder_url: str
    decoder_url: str
    config_url: str
    size_mb: int
    quality: str
    performance: str
    encoder_filename: str
    decoder_filename: str
    config_filename: str = "tokens.txt"
    language_support: str = "99种语言（中文、英文等）"
    version: str = "large-v3"
    precision: str = "int8"
    encoder_weights_url: str = ""
    decoder_weights_url: str = ""
    encoder_weights_filename: str = ""
    decoder_weights_filename: str = ""


# 所有可用的 Whisper 语音识别模型
# 使用 sherpa-onnx 推理引擎，兼容 opset <= 10 的模型
# 官方模型下载: https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
WHISPER_MODELS: Final[dict[str, WhisperModelInfo]] = {
    "whisper_tiny": WhisperModelInfo(
        name="whisper_tiny",
        display_name="Whisper Tiny（推荐，轻量）",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-tiny/tiny-encoder.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-tiny/tiny-decoder.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-tiny/tiny-tokens.txt",
        size_mb=75,
        quality="基础质量",
        performance="极速 | 内存占用 ~390MB",
        encoder_filename="tiny-encoder.onnx",
        decoder_filename="tiny-decoder.onnx",
        config_filename="tiny-tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="tiny",
        precision="fp32"
    ),
    "whisper_base": WhisperModelInfo(
        name="whisper_base",
        display_name="Whisper Base（平衡推荐）",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-base/base-encoder.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-base/base-decoder.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-base/base-tokens.txt",
        size_mb=145,
        quality="良好质量",
        performance="快速 | 内存占用 ~500MB",
        encoder_filename="base-encoder.onnx",
        decoder_filename="base-decoder.onnx",
        config_filename="base-tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="base",
        precision="fp32"
    ),
    "whisper_small": WhisperModelInfo(
        name="whisper_small",
        display_name="Whisper Small（高质量）",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-small/small-encoder.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-small/small-decoder.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-small/small-tokens.txt",
        size_mb=466,
        quality="优秀质量",
        performance="中速 | 内存占用 ~1.5GB",
        encoder_filename="small-encoder.onnx",
        decoder_filename="small-decoder.onnx",
        config_filename="small-tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="small",
        precision="fp32"
    ),
    "whisper_medium": WhisperModelInfo(
        name="whisper_medium",
        display_name="Whisper Medium（专业质量）",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-medium/medium-encoder.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-medium/medium-decoder.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-medium/medium-tokens.txt",
        size_mb=1464,
        quality="顶级质量",
        performance="较慢 | 内存占用 ~3GB",
        encoder_filename="medium-encoder.onnx",
        decoder_filename="medium-decoder.onnx",
        config_filename="medium-tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="medium",
        precision="fp32"
    ),
    "whisper_large_v3": WhisperModelInfo(
        name="whisper_large_v3",
        display_name="Whisper Large V3",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-encoder.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-decoder.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/tokens.txt",
        size_mb=6800,
        quality="最高质量",
        performance="很慢 | 内存占用 ~10GB",
        encoder_filename="large-v3-encoder.onnx",
        decoder_filename="large-v3-decoder.onnx",
        config_filename="tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="large-v3",
        precision="fp32",
        encoder_weights_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-encoder.weights",
        decoder_weights_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-decoder.weights",
        encoder_weights_filename="large-v3-encoder.weights",
        decoder_weights_filename="large-v3-decoder.weights"
    ),
    "whisper_large_v3_int8": WhisperModelInfo(
        name="whisper_large_v3_int8",
        display_name="Whisper Large V3 INT8（量化）",
        encoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-encoder.int8.onnx",
        decoder_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/large-v3-decoder.int8.onnx",
        config_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/whisper/sherpa-onnx-whisper-large-v3/tokens.txt",
        size_mb=1777,
        quality="极高质量",
        performance="较慢 | 内存占用 ~3GB",
        encoder_filename="large-v3-encoder.int8.onnx",
        decoder_filename="large-v3-decoder.int8.onnx",
        config_filename="tokens.txt",
        language_support="99种语言（中文、英文等）",
        version="large-v3",
        precision="int8"
    ),
}

# 默认 Whisper 模型（推荐使用 Tiny，轻量且支持多语言）
DEFAULT_WHISPER_MODEL_KEY: Final[str] = "whisper_tiny"


# OCR 模型配置（PaddleOCR v5）
@dataclass
class OCRModelInfo:
    """OCR 模型信息数据类。
    
    Attributes:
        name: 模型名称
        display_name: 显示名称
        det_url: 检测模型下载链接
        rec_url: 识别模型下载链接
        dict_url: 字典文件下载链接
        cls_url: 方向分类模型下载链接（可选）
        size_mb: 总文件大小(MB)
        quality: 质量描述
        performance: 性能描述
        det_filename: 检测模型文件名
        rec_filename: 识别模型文件名
        dict_filename: 字典文件名
        cls_filename: 方向分类模型文件名（可选）
        language_support: 支持的语言
        version: 版本号
        use_angle_cls: 是否使用方向分类
    """
    name: str
    display_name: str
    det_url: str
    rec_url: str
    dict_url: str
    cls_url: str
    size_mb: int
    quality: str
    performance: str
    det_filename: str
    rec_filename: str
    dict_filename: str
    cls_filename: str
    language_support: str = "中文、英文、数字、符号"
    version: str = "v5"
    use_angle_cls: bool = True


OCR_MODELS: Final[dict[str, OCRModelInfo]] = {
    "ppocr_v5": OCRModelInfo(
        name="ppocr_v5",
        display_name="PaddleOCR v5",
        det_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/PPOCR-v5/PP-OCRv5_server_det.onnx",
        rec_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/PPOCR-v5/PP-OCRv5_server_rec.onnx",
        dict_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/PPOCR-v5/PP-OCRv5_server_dict.txt",
        cls_url="https://www.modelscope.cn/models/yiminger/MyTools_Models/resolve/master/models/PPOCR-v5/PP-OCRv5_server_cls.onnx",
        size_mb=171,
        quality="高精度",
        performance="支持简体中文、繁体中文、英文、日文",
        det_filename="PP-OCRv5_server_det.onnx",
        rec_filename="PP-OCRv5_server_rec.onnx",
        dict_filename="PP-OCRv5_server_dict.txt",
        cls_filename="PP-OCRv5_server_cls.onnx",
        language_support="中文、英文、数字、标点符号",
        version="v5",
        use_angle_cls=True
    ),
}

# 默认 OCR 模型
DEFAULT_OCR_MODEL_KEY: Final[str] = "ppocr_v5"