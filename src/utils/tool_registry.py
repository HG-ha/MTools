# -*- coding: utf-8 -*-
"""工具注册中心。

集中注册所有可搜索的工具。
"""

from utils import register_tool_manual


def register_all_tools():
    """注册所有工具到搜索系统。
    
    此函数在应用启动时调用，注册所有可搜索的工具。
    """
    
    # ==================== 图片处理工具 ====================
    
    register_tool_manual(
        name="图片压缩",
        description="减小图片文件大小，支持多种格式",
        category="图片处理",
        keywords=["压缩", "缩小", "优化", "减小", "瘦身", "图片", "照片", "image", "compress", "optimize", "jpg", "png", "webp"],
        icon="COMPRESS",
        tool_id="image.compress",
    )
    
    register_tool_manual(
        name="格式转换",
        description="转换图片格式(PNG/JPG/WEBP等)",
        category="图片处理",
        keywords=["格式", "转换", "图片", "照片", "format", "convert", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"],
        icon="TRANSFORM",
        tool_id="image.format",
    )
    
    register_tool_manual(
        name="调整大小",
        description="调整图片尺寸和分辨率",
        category="图片处理",
        keywords=["调整", "缩放", "尺寸", "大小", "分辨率", "宽度", "高度", "resize", "scale", "dimension"],
        icon="ASPECT_RATIO",
        tool_id="image.resize",
    )
    
    register_tool_manual(
        name="裁剪图片",
        description="裁剪图片到指定区域",
        category="图片处理",
        keywords=["裁剪", "剪切", "截取", "crop", "cut", "trim"],
        icon="CROP",
        tool_id="image.crop",
    )
    
    register_tool_manual(
        name="旋转/翻转",
        description="旋转或翻转图片",
        category="图片处理",
        keywords=["旋转", "翻转", "镜像", "倒置", "rotate", "flip", "mirror", "90", "180", "270"],
        icon="ROTATE_90_DEGREES_CCW",
        tool_id="image.rotate",
    )
    
    register_tool_manual(
        name="去除背景",
        description="AI智能抠图，去除图片背景",
        category="图片处理",
        keywords=["抠图", "背景", "去除", "删除", "透明", "AI", "智能", "background", "remove", "matting", "cutout"],
        icon="AUTO_FIX_HIGH",
        tool_id="image.background",
    )
    
    register_tool_manual(
        name="添加水印",
        description="批量给图片添加文字或图片水印",
        category="图片处理",
        keywords=["水印", "批量", "文字", "logo", "标记", "watermark", "batch", "text", "overlay"],
        icon="BRANDING_WATERMARK",
        tool_id="image.watermark",
    )
    
    register_tool_manual(
        name="图片信息",
        description="查看和编辑图片EXIF信息",
        category="图片处理",
        keywords=["信息", "查看", "EXIF", "元数据", "属性", "详情", "info", "metadata", "properties", "details"],
        icon="INFO_OUTLINE",
        tool_id="image.info",
    )
    
    register_tool_manual(
        name="去除EXIF",
        description="删除图片的元数据信息",
        category="图片处理",
        keywords=["EXIF", "元数据", "隐私", "删除", "清除", "metadata", "remove", "privacy", "clean"],
        icon="PRIVACY_TIP",
        tool_id="image.exif",
    )
    
    register_tool_manual(
        name="二维码生成",
        description="生成二维码图片",
        category="图片处理",
        keywords=["二维码", "QR", "生成", "创建", "制作", "qrcode", "generate", "create", "扫码"],
        icon="QR_CODE_2",
        tool_id="image.qrcode",
    )
    
    register_tool_manual(
        name="图片转Base64",
        description="将图片转换为Base64编码",
        category="图片处理",
        keywords=["Base64", "编码", "转换", "图片", "encode", "data uri", "内联"],
        icon="CODE",
        tool_id="image.to_base64",
    )
    
    register_tool_manual(
        name="GIF/实况图编辑",
        description="调整GIF/Live Photo的速度、帧数，支持导出为视频",
        category="图片处理",
        keywords=["GIF", "动图", "动画", "调整", "速度", "实况图", "Live Photo", "实况照片", "动态照片", "帧数", "循环", "视频", "导出", "mp4"],
        icon="ANIMATION",
        tool_id="image.gif",
    )
    
    register_tool_manual(
        name="图像增强",
        description="AI智能放大增强图片，支持降噪和锐化",
        category="图片处理",
        keywords=["增强", "放大", "超分", "高清", "清晰", "AI", "Real-ESRGAN", "upscale", "enhance", "超分辨率", "降噪", "锐化", "画质"],
        icon="AUTO_AWESOME",
        tool_id="image.enhance",
    )
    
    register_tool_manual(
        name="图片拼接",
        description="将多张图片拼接成一张",
        category="图片处理",
        keywords=["拼接", "合并", "拼图", "组合", "长图", "merge", "concat", "stitch", "collage", "横向", "纵向", "网格"],
        icon="VIEW_COMFY",
        tool_id="image.puzzle.merge",
    )
    
    register_tool_manual(
        name="图片切割",
        description="将图片切割成多个部分",
        category="图片处理",
        keywords=["切割", "分割", "拼图", "九宫格", "split", "slice", "divide"],
        icon="GRID_ON",
        tool_id="image.puzzle.split",
    )
    
    register_tool_manual(
        name="图片搜索",
        description="以图搜图，搜索相似图片",
        category="图片处理",
        keywords=["搜索", "以图搜图", "识图",  "相似图片", "搜图", "查找", "识别", "search", "image search", "similar", "reverse image"],
        icon="IMAGE_SEARCH",
        tool_id="image.search",
    )
    
    # ==================== 音频处理工具 ====================
    
    register_tool_manual(
        name="音频格式转换",
        description="转换音频格式(MP3/WAV/AAC等)",
        category="音频处理",
        keywords=["音频", "声音", "音乐", "格式", "转换", "audio", "sound", "music", "convert", "mp3", "wav", "aac", "flac", "ogg", "m4a"],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="audio.format",
    )
    
    register_tool_manual(
        name="音频压缩",
        description="压缩音频文件大小",
        category="音频处理",
        keywords=["音频", "声音", "音乐", "压缩", "减小", "比特率", "采样率", "compress", "bitrate", "quality"],
        icon="COMPRESS",
        tool_id="audio.compress",
    )
    
    register_tool_manual(
        name="人声提取",
        description="AI智能分离人声和伴奏",
        category="音频处理",
        keywords=["人声", "伴奏", "分离", "提取", "vocal", "instrumental", "karaoke", "卡拉OK", "AI", "音轨"],
        icon="MUSIC_NOTE",
        tool_id="audio.vocal_extraction",
    )
    
    # ==================== 视频处理工具 ====================
    
    register_tool_manual(
        name="视频压缩",
        description="减小视频文件大小",
        category="视频处理",
        keywords=["视频", "压缩", "减小", "优化", "crf", "分辨率", "video", "compress", "reduce", "optimize"],
        icon="COMPRESS",
        tool_id="video.compress",
    )
    
    register_tool_manual(
        name="视频格式转换",
        description="转换视频格式(MP4/AVI/MKV等)",
        category="视频处理",
        keywords=["视频", "格式", "转换", "video", "convert", "format", "mp4", "avi", "mkv", "mov", "flv", "wmv", "webm"],
        icon="VIDEO_FILE_ROUNDED",
        tool_id="video.convert",
    )
    
    register_tool_manual(
        name="提取音频",
        description="从视频中提取音频轨道",
        category="视频处理",
        keywords=["提取", "导出", "分离", "音频", "声音", "视频", "extract", "export", "audio", "sound", "mp3"],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="video.extract_audio",
    )
    
    register_tool_manual(
        name="视频人声分离",
        description="分离视频中的人声和背景音",
        category="视频处理",
        keywords=["人声", "伴奏", "背景音", "分离", "视频", "音频", "vocal", "instrumental", "separation", "AI", "消音", "卡拉OK", "伴唱"],
        icon="GRAPHIC_EQ",
        tool_id="video.vocal_separation",
    )
    
    register_tool_manual(
        name="视频添加水印",
        description="为视频添加文字或图片水印",
        category="视频处理",
        keywords=["水印", "视频", "文字", "图片", "添加", "overlay", "logo", "stamp"],
        icon="BRANDING_WATERMARK",
        tool_id="video.watermark",
    )
    # ==================== 开发工具 ====================
    
    register_tool_manual(
        name="Base64转图片",
        description="将Base64编码转换为图片",
        category="开发工具",
        keywords=["Base64", "解码", "图片", "转换", "decode", "image", "data uri", "还原"],
        icon="IMAGE",
        tool_id="dev.base64_to_image",
    )
    
    register_tool_manual(
        name="编码转换",
        description="文本编码格式转换",
        category="开发工具",
        keywords=["编码", "转换", "文本", "字符集", "encoding", "charset", "utf8", "gbk", "gb2312", "unicode", "乱码"],
        icon="TEXT_FIELDS",
        tool_id="dev.encoding",
    )
    
    register_tool_manual(
        name="代码格式化",
        description="格式化代码(JSON/XML/SQL等)",
        category="开发工具",
        keywords=["代码", "格式化", "美化", "JSON", "XML", "SQL", "format", "beautify", "pretty", "indent"],
        icon="CODE",
        tool_id="dev.code_format",
    )

