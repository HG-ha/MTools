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
        description="专业压缩工具，最高减小80%体积",
        category="图片处理",
        keywords=["压缩", "缩小", "优化", "减小", "瘦身", "图片", "照片", "image", "compress", "optimize", "jpg", "png", "webp"],
        icon="COMPRESS_ROUNDED",
        tool_id="image.compress",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="格式转换",
        description="支持JPG、PNG、WebP等格式互转",
        category="图片处理",
        keywords=["格式", "转换", "图片", "照片", "format", "convert", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"],
        icon="TRANSFORM_ROUNDED",
        tool_id="image.format",
        gradient_colors=("#4FACFE", "#00F2FE"),
    )
    
    register_tool_manual(
        name="尺寸调整",
        description="批量调整图片尺寸和分辨率",
        category="图片处理",
        keywords=["调整", "缩放", "尺寸", "大小", "分辨率", "宽度", "高度", "resize", "scale", "dimension"],
        icon="PHOTO_SIZE_SELECT_LARGE_ROUNDED",
        tool_id="image.resize",
        gradient_colors=("#F093FB", "#F5576C"),
    )
    
    register_tool_manual(
        name="图片裁剪",
        description="可视化裁剪，实时预览效果",
        category="图片处理",
        keywords=["裁剪", "剪切", "截取", "crop", "cut", "trim"],
        icon="CROP",
        tool_id="image.crop",
        gradient_colors=("#A8EDEA", "#FED6E3"),
    )
    
    register_tool_manual(
        name="旋转/翻转",
        description="支持GIF动图、实时预览、自定义角度、批量处理",
        category="图片处理",
        keywords=["旋转", "翻转", "镜像", "倒置", "rotate", "flip", "mirror", "90", "180", "270"],
        icon="ROTATE_90_DEGREES_CCW",
        tool_id="image.rotate",
        gradient_colors=("#F77062", "#FE5196"),
    )
    
    register_tool_manual(
        name="背景移除",
        description="AI智能抠图，一键去除背景",
        category="图片处理",
        keywords=["抠图", "背景", "去除", "删除", "透明", "AI", "智能", "background", "remove", "matting", "cutout"],
        icon="AUTO_FIX_HIGH",
        tool_id="image.background",
        gradient_colors=("#FA709A", "#FEE140"),
    )
    
    register_tool_manual(
        name="添加水印",
        description="支持单个水印和全屏平铺水印，批量处理，实时预览",
        category="图片处理",
        keywords=["水印", "批量", "文字", "logo", "标记", "watermark", "batch", "text", "overlay"],
        icon="BRANDING_WATERMARK",
        tool_id="image.watermark",
        gradient_colors=("#FF6FD8", "#3813C2"),
    )
    
    register_tool_manual(
        name="图片信息",
        description="查看图片详细信息和EXIF数据",
        category="图片处理",
        keywords=["信息", "查看", "EXIF", "元数据", "属性", "详情", "info", "metadata", "properties", "details"],
        icon="INFO",
        tool_id="image.info",
        gradient_colors=("#FFA8A8", "#FCFF82"),
    )
    
    register_tool_manual(
        name="去除EXIF",
        description="删除图片元数据，保护隐私",
        category="图片处理",
        keywords=["EXIF", "元数据", "隐私", "删除", "清除", "metadata", "remove", "privacy", "clean"],
        icon="SECURITY",
        tool_id="image.exif",
        gradient_colors=("#C471F5", "#FA71CD"),
    )
    
    register_tool_manual(
        name="二维码生成",
        description="生成二维码，支持自定义样式",
        category="图片处理",
        keywords=["二维码", "QR", "生成", "创建", "制作", "qrcode", "generate", "create", "扫码"],
        icon="QR_CODE_2",
        tool_id="image.qrcode",
        gradient_colors=("#20E2D7", "#F9FEA5"),
    )
    
    register_tool_manual(
        name="图片转Base64",
        description="将图片转换为Base64编码，支持Data URI格式",
        category="图片处理",
        keywords=["Base64", "编码", "转换", "图片", "encode", "data uri", "内联"],
        icon="CODE",
        tool_id="image.to_base64",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="GIF/Live Photo 编辑",
        description="调整 GIF / 实况图的速度、循环等参数，支持导出为视频",
        category="图片处理",
        keywords=["GIF", "动图", "动画", "调整", "速度", "实况图", "Live Photo", "实况照片", "动态照片", "帧数", "循环", "视频", "导出", "mp4"],
        icon="GIF_BOX",
        tool_id="image.gif",
        gradient_colors=("#FF9A9E", "#FAD0C4"),
    )
    
    register_tool_manual(
        name="图像增强",
        description="AI超分辨率，4倍放大清晰化",
        category="图片处理",
        keywords=["增强", "放大", "超分", "高清", "清晰", "AI", "Real-ESRGAN", "upscale", "enhance", "超分辨率", "降噪", "锐化", "画质"],
        icon="AUTO_AWESOME",
        tool_id="image.enhance",
        gradient_colors=("#30CFD0", "#330867"),
    )
    
    register_tool_manual(
        name="多图拼接",
        description="横向、纵向、网格拼接图片",
        category="图片处理",
        keywords=["拼接", "合并", "拼图", "组合", "长图", "merge", "concat", "stitch", "collage", "横向", "纵向", "网格"],
        icon="VIEW_MODULE",
        tool_id="image.puzzle.merge",
        gradient_colors=("#4ECDC4", "#44A08D"),
    )
    
    register_tool_manual(
        name="单图切分",
        description="单图切分为九宫格，可设置间距",
        category="图片处理",
        keywords=["切割", "分割", "拼图", "九宫格", "split", "slice", "divide"],
        icon="GRID_ON",
        tool_id="image.puzzle.split",
        gradient_colors=("#FF6B6B", "#FFE66D"),
    )
    
    register_tool_manual(
        name="图片搜索",
        description="以图搜图，搜索相似图片",
        category="图片处理",
        keywords=["搜索", "以图搜图", "识图",  "相似图片", "搜图", "查找", "识别", "search", "image search", "similar", "reverse image"],
        icon="IMAGE_SEARCH",
        tool_id="image.search",
        gradient_colors=("#FFA726", "#FB8C00"),
    )
    
    # ==================== 媒体处理工具 ====================
    
    register_tool_manual(
        name="音频格式转换",
        description="转换音频格式(MP3/WAV/AAC等)",
        category="媒体处理",
        keywords=["音频", "声音", "音乐", "格式", "转换", "audio", "sound", "music", "convert", "mp3", "wav", "aac", "flac", "ogg", "m4a"],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="audio.format",
        gradient_colors=("#a8edea", "#fed6e3"),
    )
    
    register_tool_manual(
        name="音频压缩",
        description="压缩音频文件大小",
        category="媒体处理",
        keywords=["音频", "声音", "音乐", "压缩", "减小", "比特率", "采样率", "compress", "bitrate", "quality"],
        icon="COMPRESS",
        tool_id="audio.compress",
        gradient_colors=("#fbc2eb", "#a6c1ee"),
    )
    
    register_tool_manual(
        name="音频倍速调整",
        description="调整音频播放速度(0.1x-10x)",
        category="媒体处理",
        keywords=["音频", "倍速", "速度", "快进", "慢放", "加速", "减速", "调整", "audio", "speed", "slow", "fast", "playback", "tempo"],
        icon="SPEED",
        tool_id="audio.speed",
        gradient_colors=("#f093fb", "#f5576c"),
    )
    
    register_tool_manual(
        name="人声提取",
        description="AI智能分离人声和伴奏",
        category="媒体处理",
        keywords=["人声", "伴奏", "分离", "提取", "vocal", "instrumental", "karaoke", "卡拉OK", "AI", "音轨"],
        icon="MUSIC_NOTE",
        tool_id="audio.vocal_extraction",
        gradient_colors=("#ffecd2", "#fcb69f"),
    )
    
    register_tool_manual(
        name="视频压缩",
        description="减小视频文件大小，支持CRF和分辨率调整",
        category="媒体处理",
        keywords=["视频", "压缩", "减小", "优化", "crf", "分辨率", "video", "compress", "reduce", "optimize"],
        icon="COMPRESS",
        tool_id="video.compress",
        gradient_colors=("#84fab0", "#8fd3f4"),
    )
    
    register_tool_manual(
        name="视频格式转换",
        description="支持MP4、AVI、MKV等格式互转",
        category="媒体处理",
        keywords=["视频", "格式", "转换", "video", "convert", "format", "mp4", "avi", "mkv", "mov", "flv", "wmv", "webm"],
        icon="VIDEO_FILE_ROUNDED",
        tool_id="video.convert",
        gradient_colors=("#a8edea", "#fed6e3"),
    )
    
    register_tool_manual(
        name="视频提取音频",
        description="从视频中提取音频轨道",
        category="媒体处理",
        keywords=["提取", "导出", "分离", "音频", "声音", "视频", "extract", "export", "audio", "sound", "mp3"],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="video.extract_audio",
        gradient_colors=("#ff9a9e", "#fad0c4"),
    )
    
    register_tool_manual(
        name="视频倍速调整",
        description="调整视频播放速度(0.1x-10x)",
        category="媒体处理",
        keywords=["倍速", "速度", "快进", "慢放", "加速", "减速", "视频", "调整", "speed", "slow", "fast", "playback", "time", "2x", "0.5x", "10x"],
        icon="SPEED",
        tool_id="video.speed",
        gradient_colors=("#667eea", "#764ba2"),
    )
    
    register_tool_manual(
        name="视频人声分离",
        description="分离视频中的人声和背景音",
        category="媒体处理",
        keywords=["人声", "伴奏", "背景音", "分离", "视频", "音频", "vocal", "instrumental", "separation", "AI", "消音", "卡拉OK", "伴唱"],
        icon="GRAPHIC_EQ",
        tool_id="video.vocal_separation",
        gradient_colors=("#fbc2eb", "#a6c1ee"),
    )
    
    register_tool_manual(
        name="视频添加水印",
        description="为视频添加文字或图片水印",
        category="媒体处理",
        keywords=["水印", "视频", "文字", "图片", "添加", "overlay", "logo", "stamp"],
        icon="BRANDING_WATERMARK",
        tool_id="video.watermark",
        gradient_colors=("#ffecd2", "#fcb69f"),
    )
    
    register_tool_manual(
        name="视频修复",
        description="修复损坏、卡顿、无法播放的视频",
        category="媒体处理",
        keywords=["修复", "损坏", "卡顿", "无法播放", "视频", "恢复", "repair", "fix", "corrupted", "broken", "索引", "音画不同步"],
        icon="HEALING",
        tool_id="video.repair",
        gradient_colors=("#fa709a", "#fee140"),
    )
    # ==================== 开发工具 ====================
    
    register_tool_manual(
        name="Base64转图片",
        description="将Base64编码转换为图片",
        category="开发工具",
        keywords=["Base64", "解码", "图片", "转换", "decode", "image", "data uri", "还原"],
        icon="IMAGE_OUTLINED",
        tool_id="dev.base64_to_image",
        gradient_colors=("#4FACFE", "#00F2FE"),
    )
    
    register_tool_manual(
        name="编码转换",
        description="文本编码格式转换",
        category="开发工具",
        keywords=["编码", "转换", "文本", "字符集", "encoding", "charset", "utf8", "gbk", "gb2312", "unicode", "乱码"],
        icon="TRANSFORM_ROUNDED",
        tool_id="dev.encoding",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="JSON 查看器",
        description="格式化并以树形结构查看 JSON",
        category="开发工具",
        keywords=["JSON", "格式化", "查看", "树形", "解析", "prettify", "format", "viewer", "tree"],
        icon="DATA_OBJECT",
        tool_id="dev.json_viewer",
        gradient_colors=("#FA8BFF", "#2BD2FF"),
    )

    # ==================== 其他工具 ====================
    register_tool_manual(
        name="Windows更新管理",
        description="管理Windows更新设置，禁用或恢复更新",
        category="其他工具",
        keywords=["Windows", "更新", "管理", "禁用", "恢复", "暂停", "升级", "windows update", "disable", "enable", "pause"],
        icon="UPDATE_DISABLED",
        tool_id="others.windows_update",
        gradient_colors=("#FF6B6B", "#FFA500"),
    )
    register_tool_manual(
        name="图片转URL",
        description="上传图片获取分享链接",
        category="其他工具",
        keywords=["图片", "上传", "分享", "链接", "url", "image", "upload", "share"],
        icon="LINK",
        tool_id="others.image_to_url",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    register_tool_manual(
        name="文件转URL",
        description="上传文件获取分享链接",
        category="其他工具",
        keywords=["文件", "上传", "分享", "链接", "url", "file", "upload", "share"],
        icon="UPLOAD_FILE",
        tool_id="others.file_to_url",
        gradient_colors=("#F093FB", "#F5576C"),
    )