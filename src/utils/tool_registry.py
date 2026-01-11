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
        keywords=[
            "压缩", "缩小", "优化", "减小", "瘦身", "图片", "照片", "图像",
            "image", "compress", "optimize", "reduce", "shrink", "minify",
            "jpg", "png", "webp", "jpeg", "体积", "大小", "质量", "无损",
            "批量压缩", "tinypng", "图片变小", "文件变小"
        ],
        icon="COMPRESS_ROUNDED",
        tool_id="image.compress",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="格式转换",
        description="支持JPG、PNG、WebP等格式互转",
        category="图片处理",
        keywords=[
            "格式", "转换", "图片", "照片", "图像", "转格式",
            "format", "convert", "transform", "change",
            "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "ico", "heic", "heif", "avif",
            "png转jpg", "jpg转png", "webp转jpg", "heic转jpg", "批量转换", "格式互转"
        ],
        icon="TRANSFORM_ROUNDED",
        tool_id="image.format",
        gradient_colors=("#4FACFE", "#00F2FE"),
    )
    
    register_tool_manual(
        name="尺寸调整",
        description="批量调整图片尺寸和分辨率",
        category="图片处理",
        keywords=[
            "调整", "缩放", "尺寸", "大小", "分辨率", "宽度", "高度", "像素",
            "resize", "scale", "dimension", "size", "resolution", "pixel",
            "放大", "缩小", "等比缩放", "比例", "百分比", "宽高", "px",
            "改大小", "改尺寸", "批量调整"
        ],
        icon="PHOTO_SIZE_SELECT_LARGE_ROUNDED",
        tool_id="image.resize",
        gradient_colors=("#F093FB", "#F5576C"),
    )
    
    register_tool_manual(
        name="图片裁剪",
        description="可视化裁剪，实时预览效果",
        category="图片处理",
        keywords=[
            "裁剪", "剪切", "截取", "裁切", "剪裁", "切图",
            "crop", "cut", "trim", "clip", "slice",
            "自由裁剪", "比例裁剪", "选区", "截图", "抠图", "部分"
        ],
        icon="CROP",
        tool_id="image.crop",
        gradient_colors=("#A8EDEA", "#FED6E3"),
    )
    
    register_tool_manual(
        name="旋转/翻转",
        description="支持GIF动图、实时预览、自定义角度、批量处理",
        category="图片处理",
        keywords=[
            "旋转", "翻转", "镜像", "倒置", "颠倒", "转向",
            "rotate", "flip", "mirror", "turn", "reverse",
            "90", "180", "270", "左转", "右转", "上下翻转", "左右翻转",
            "水平翻转", "垂直翻转", "自定义角度", "任意角度", "顺时针", "逆时针"
        ],
        icon="ROTATE_90_DEGREES_CCW",
        tool_id="image.rotate",
        gradient_colors=("#F77062", "#FE5196"),
    )
    
    register_tool_manual(
        name="背景移除",
        description="AI智能抠图，一键去除背景",
        category="图片处理",
        keywords=[
            "抠图", "背景", "去除", "删除", "透明", "AI", "智能", "去背景",
            "background", "remove", "matting", "cutout", "transparent",
            "换背景", "去底", "扣图", "扣人", "扣物", "人物抠图", "商品抠图",
            "一键抠图", "自动抠图", "ps抠图", "photoshop", "rmbg", "rembg"
        ],
        icon="AUTO_FIX_HIGH",
        tool_id="image.background",
        gradient_colors=("#FA709A", "#FEE140"),
    )
    
    register_tool_manual(
        name="添加水印",
        description="支持单个水印和全屏平铺水印，批量处理，实时预览",
        category="图片处理",
        keywords=[
            "水印", "批量", "文字", "logo", "标记", "版权", "签名",
            "watermark", "batch", "text", "overlay", "stamp", "copyright",
            "平铺水印", "全屏水印", "图片水印", "文字水印", "加水印", "打水印",
            "防盗", "保护", "标识"
        ],
        icon="BRANDING_WATERMARK",
        tool_id="image.watermark",
        gradient_colors=("#FF6FD8", "#3813C2"),
    )
    
    register_tool_manual(
        name="去水印",
        description="AI智能去除图片水印，支持自定义区域",
        category="图片处理",
        keywords=[
            "去水印", "移除", "删除", "擦除", "修复", "AI", "智能", "水印",
            "remove", "watermark", "erase", "inpaint", "STTN", "clean",
            "去除水印", "消除水印", "水印去除", "图片去水印", "照片去水印",
            "去logo", "去文字", "去标记", "修复图片"
        ],
        icon="AUTO_FIX_HIGH",
        tool_id="image.watermark_remove",
        gradient_colors=("#11998E", "#38EF7D"),
    )
    
    register_tool_manual(
        name="图片信息",
        description="查看图片详细信息和EXIF数据",
        category="图片处理",
        keywords=[
            "信息", "查看", "EXIF", "元数据", "属性", "详情", "数据",
            "info", "metadata", "properties", "details", "view",
            "分辨率", "尺寸", "大小", "格式", "拍摄时间", "相机", "镜头",
            "GPS", "位置", "经纬度", "色彩空间", "位深度", "DPI"
        ],
        icon="INFO",
        tool_id="image.info",
        gradient_colors=("#FFA8A8", "#FCFF82"),
    )
    
    register_tool_manual(
        name="去除EXIF",
        description="删除图片元数据，保护隐私",
        category="图片处理",
        keywords=[
            "EXIF", "元数据", "隐私", "删除", "清除", "去除", "移除",
            "metadata", "remove", "privacy", "clean", "strip", "clear",
            "GPS", "位置信息", "拍摄信息", "相机信息", "保护隐私",
            "清理信息", "去定位", "去位置"
        ],
        icon="SECURITY",
        tool_id="image.exif",
        gradient_colors=("#C471F5", "#FA71CD"),
    )
    
    register_tool_manual(
        name="二维码生成",
        description="生成二维码，支持自定义样式",
        category="图片处理",
        keywords=[
            "二维码", "QR", "生成", "创建", "制作", "扫码",
            "qrcode", "generate", "create", "make", "scan",
            "链接", "网址", "文本", "URL", "条形码", "扫一扫",
            "微信二维码", "支付宝二维码", "名片", "分享"
        ],
        icon="QR_CODE_2",
        tool_id="image.qrcode",
        gradient_colors=("#20E2D7", "#F9FEA5"),
    )
    
    register_tool_manual(
        name="图片转Base64",
        description="将图片转换为Base64编码，支持Data URI格式",
        category="图片处理",
        keywords=[
            "Base64", "编码", "转换", "图片", "内联",
            "encode", "data uri", "convert", "base 64",
            "图片编码", "嵌入", "HTML", "CSS", "网页", "前端"
        ],
        icon="CODE",
        tool_id="image.to_base64",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="GIF/Live Photo 编辑",
        description="调整 GIF / 实况图的速度、循环等参数，支持导出为视频",
        category="图片处理",
        keywords=[
            "GIF", "动图", "动画", "调整", "速度", "帧数", "循环",
            "实况图", "Live Photo", "实况照片", "动态照片",
            "gif", "animate", "frame", "loop", "speed",
            "加速", "减速", "倒放", "导出视频", "mp4", "分解", "拆分"
        ],
        icon="GIF_BOX",
        tool_id="image.gif",
        gradient_colors=("#FF9A9E", "#FAD0C4"),
    )
    
    register_tool_manual(
        name="图像增强",
        description="AI超分辨率，4倍放大清晰化",
        category="图片处理",
        keywords=[
            "增强", "放大", "超分", "高清", "清晰", "AI", "画质",
            "Real-ESRGAN", "upscale", "enhance", "super resolution",
            "超分辨率", "降噪", "锐化", "4倍", "2倍", "无损放大",
            "图片放大", "照片放大", "提升画质", "老照片修复", "模糊变清晰"
        ],
        icon="AUTO_AWESOME",
        tool_id="image.enhance",
        gradient_colors=("#30CFD0", "#330867"),
    )
    
    register_tool_manual(
        name="多图拼接",
        description="横向、纵向、网格拼接图片",
        category="图片处理",
        keywords=[
            "拼接", "合并", "拼图", "组合", "长图", "拼合",
            "merge", "concat", "stitch", "collage", "combine", "join",
            "横向拼接", "纵向拼接", "网格拼接", "图片合并", "照片拼接",
            "多图合一", "九宫格", "朋友圈长图"
        ],
        icon="VIEW_MODULE",
        tool_id="image.puzzle.merge",
        gradient_colors=("#4ECDC4", "#44A08D"),
    )
    
    register_tool_manual(
        name="单图切分",
        description="单图切分为九宫格，可设置间距",
        category="图片处理",
        keywords=[
            "切割", "分割", "拼图", "九宫格", "切分", "拆分",
            "split", "slice", "divide", "grid", "cut",
            "图片分割", "切成小图", "3x3", "朋友圈九宫格", "ins九宫格"
        ],
        icon="GRID_ON",
        tool_id="image.puzzle.split",
        gradient_colors=("#FF6B6B", "#FFE66D"),
    )
    
    register_tool_manual(
        name="图片搜索",
        description="以图搜图，搜索相似图片",
        category="图片处理",
        keywords=[
            "搜索", "以图搜图", "识图", "相似图片", "搜图", "查找", "识别",
            "search", "image search", "similar", "reverse image", "find",
            "找图", "找原图", "找高清", "找来源", "图片识别", "图片查找",
            "百度识图", "谷歌识图", "相似", "出处"
        ],
        icon="IMAGE_SEARCH",
        tool_id="image.search",
        gradient_colors=("#FFA726", "#FB8C00"),
    )
    
    register_tool_manual(
        name="OCR 文字识别",
        description="AI识别图片中的文字，支持中英文",
        category="图片处理",
        keywords=[
            "OCR", "文字识别", "识别", "提取", "文本", "字符",
            "text", "recognition", "extract", "paddleocr", "read",
            "图片转文字", "扫描", "识字", "截图识字", "图片取字",
            "拍照识字", "复制文字", "提取文字", "中文识别", "英文识别"
        ],
        icon="TEXT_FIELDS",
        tool_id="image.ocr",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="颜色空间转换",
        description="批量转换图片颜色空间，灰度、反色、复古等",
        category="图片处理",
        keywords=[
            "颜色", "色彩", "空间", "转换", "灰度", "黑白", "反色",
            "color", "space", "convert", "grayscale", "invert", "sepia",
            "RGB", "CMYK", "HSV", "LAB", "RGBA", "二值化", "棕褐色",
            "复古", "滤镜", "批量", "颜色转换", "色彩空间", "印刷"
        ],
        icon="COLOR_LENS",
        tool_id="image.color_space",
        gradient_colors=("#00B4DB", "#0083B0"),
    )
    
    # ==================== 媒体处理工具 ====================
    
    register_tool_manual(
        name="音频格式转换",
        description="转换音频格式(MP3/WAV/AAC等)",
        category="媒体处理",
        keywords=[
            "音频", "声音", "音乐", "格式", "转换", "转格式",
            "audio", "sound", "music", "convert", "format", "transform",
            "mp3", "wav", "aac", "flac", "ogg", "m4a", "wma", "ape",
            "音频转换", "格式互转", "无损转换", "有损转换"
        ],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="audio.format",
        gradient_colors=("#a8edea", "#fed6e3"),
    )
    
    register_tool_manual(
        name="音频压缩",
        description="压缩音频文件大小",
        category="媒体处理",
        keywords=[
            "音频", "声音", "音乐", "压缩", "减小", "缩小",
            "compress", "bitrate", "quality", "reduce", "shrink",
            "比特率", "采样率", "音频变小", "文件变小", "mp3压缩"
        ],
        icon="COMPRESS",
        tool_id="audio.compress",
        gradient_colors=("#fbc2eb", "#a6c1ee"),
    )
    
    register_tool_manual(
        name="音频倍速调整",
        description="调整音频播放速度(0.1x-10x)",
        category="媒体处理",
        keywords=[
            "音频", "倍速", "速度", "快进", "慢放", "加速", "减速",
            "audio", "speed", "slow", "fast", "playback", "tempo", "rate",
            "2倍速", "0.5倍速", "变速", "调速", "播放速度"
        ],
        icon="SPEED",
        tool_id="audio.speed",
        gradient_colors=("#f093fb", "#f5576c"),
    )
    
    register_tool_manual(
        name="人声提取",
        description="AI智能分离人声和伴奏",
        category="媒体处理",
        keywords=[
            "人声", "伴奏", "分离", "提取", "AI", "音轨",
            "vocal", "instrumental", "karaoke", "separation", "extract",
            "卡拉OK", "消除人声", "去人声", "去伴奏", "唱歌", "KTV",
            "纯音乐", "纯人声", "背景音乐", "BGM", "伴唱"
        ],
        icon="MUSIC_NOTE",
        tool_id="audio.vocal_extraction",
        gradient_colors=("#ffecd2", "#fcb69f"),
    )
    
    register_tool_manual(
        name="音视频转文字",
        description="AI语音识别，音视频转文字字幕",
        category="媒体处理",
        keywords=[
            "语音识别", "转文字", "字幕", "语音", "文字", "AI",
            "Whisper", "SenseVoice", "speech", "recognition", "subtitle", "srt",
            "转录", "音频", "视频", "转文本", "听写", "录音转文字",
            "视频转文字", "会议记录", "采访转录", "语音转文字"
        ],
        icon="TRANSCRIBE",
        tool_id="audio.to_text",
        gradient_colors=("#a8c0ff", "#3f2b96"),
    )
    
    register_tool_manual(
        name="视频压缩",
        description="减小视频文件大小，支持CRF和分辨率调整",
        category="媒体处理",
        keywords=[
            "视频", "压缩", "减小", "优化", "缩小",
            "video", "compress", "reduce", "optimize", "shrink",
            "crf", "分辨率", "码率", "视频变小", "文件变小",
            "mp4压缩", "视频瘦身", "批量压缩"
        ],
        icon="COMPRESS",
        tool_id="video.compress",
        gradient_colors=("#84fab0", "#8fd3f4"),
    )
    
    register_tool_manual(
        name="视频格式转换",
        description="支持MP4、AVI、MKV等格式互转",
        category="媒体处理",
        keywords=[
            "视频", "格式", "转换", "转格式",
            "video", "convert", "format", "transform",
            "mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "ts", "m4v",
            "视频转换", "格式互转", "转mp4", "转avi"
        ],
        icon="VIDEO_FILE_ROUNDED",
        tool_id="video.convert",
        gradient_colors=("#a8edea", "#fed6e3"),
    )
    
    register_tool_manual(
        name="视频提取音频",
        description="从视频中提取音频轨道",
        category="媒体处理",
        keywords=[
            "提取", "导出", "分离", "音频", "声音", "视频",
            "extract", "export", "audio", "sound", "mp3", "separate",
            "视频转音频", "转mp3", "取音频", "只要声音", "提取声音"
        ],
        icon="AUDIO_FILE_ROUNDED",
        tool_id="video.extract_audio",
        gradient_colors=("#ff9a9e", "#fad0c4"),
    )
    
    register_tool_manual(
        name="视频倍速调整",
        description="调整视频播放速度(0.1x-10x)",
        category="媒体处理",
        keywords=[
            "倍速", "速度", "快进", "慢放", "加速", "减速", "视频",
            "speed", "slow", "fast", "playback", "time", "rate",
            "2x", "0.5x", "10x", "变速", "调速", "慢动作", "快放"
        ],
        icon="SPEED",
        tool_id="video.speed",
        gradient_colors=("#667eea", "#764ba2"),
    )
    
    register_tool_manual(
        name="视频人声分离",
        description="分离视频中的人声和背景音",
        category="媒体处理",
        keywords=[
            "人声", "伴奏", "背景音", "分离", "视频", "音频",
            "vocal", "instrumental", "separation", "AI", "extract",
            "消音", "卡拉OK", "伴唱", "去人声", "去背景音", "去BGM"
        ],
        icon="GRAPHIC_EQ",
        tool_id="video.vocal_separation",
        gradient_colors=("#fbc2eb", "#a6c1ee"),
    )
    
    register_tool_manual(
        name="视频添加水印",
        description="为视频添加文字或图片水印",
        category="媒体处理",
        keywords=[
            "水印", "视频", "文字", "图片", "添加", "版权",
            "overlay", "logo", "stamp", "watermark", "text",
            "视频水印", "加水印", "打水印", "签名", "标识"
        ],
        icon="BRANDING_WATERMARK",
        tool_id="video.watermark",
        gradient_colors=("#ffecd2", "#fcb69f"),
    )
    
    register_tool_manual(
        name="视频修复",
        description="修复损坏、卡顿、无法播放的视频",
        category="媒体处理",
        keywords=[
            "修复", "损坏", "卡顿", "无法播放", "视频", "恢复",
            "repair", "fix", "corrupted", "broken", "recover",
            "索引", "音画不同步", "视频打不开", "视频损坏", "修复视频"
        ],
        icon="HEALING",
        tool_id="video.repair",
        gradient_colors=("#fa709a", "#fee140"),
    )

    register_tool_manual(
        name="视频增强",
        description="AI视频超分辨率增强，提升画质清晰度",
        category="媒体处理",
        keywords=[
            "视频", "增强", "超分辨率", "清晰度", "AI", "画质",
            "Real-ESRGAN", "upscale", "enhance", "super resolution",
            "视频放大", "视频清晰", "4K", "高清", "修复画质"
        ],
        icon="AUTO_AWESOME",
        tool_id="video.enhance",
        gradient_colors=("#30CFD0", "#330867"),
    )
    
    register_tool_manual(
        name="视频插帧",
        description="AI帧率提升，让视频更流畅",
        category="媒体处理",
        keywords=[
            "视频", "插帧", "帧率", "提升", "流畅", "AI",
            "RIFE", "interpolation", "smooth", "frame", "rate", "fps",
            "60帧", "120帧", "补帧", "视频流畅", "丝滑", "慢动作"
        ],
        icon="SLOW_MOTION_VIDEO",
        tool_id="video.interpolation",
        gradient_colors=("#667eea", "#764ba2"),
    )
    
    register_tool_manual(
        name="视频去字幕/水印",
        description="AI智能移除视频字幕和水印",
        category="媒体处理",
        keywords=[
            "视频", "去除", "移除", "字幕", "水印", "AI",
            "subtitle", "watermark", "remove", "erase", "inpaint", "STTN",
            "去字幕", "去水印", "消除", "擦除", "修复", "去logo"
        ],
        icon="AUTO_FIX_HIGH",
        tool_id="video.subtitle_remove",
        gradient_colors=("#FA709A", "#FEE140"),
    )
    
    register_tool_manual(
        name="视频配字幕",
        description="AI语音识别自动生成字幕并烧录到视频",
        category="媒体处理",
        keywords=[
            "视频", "字幕", "配字幕", "语音识别", "AI",
            "subtitle", "caption", "burn", "embed", "speech", "srt", "ass",
            "加字幕", "嵌入字幕", "烧录字幕", "自动字幕", "硬字幕",
            "Whisper", "SenseVoice", "翻译字幕", "双语字幕", "中英字幕"
        ],
        icon="SUBTITLES",
        tool_id="video.subtitle",
        gradient_colors=("#4776E6", "#8E54E9"),
    )
    
    register_tool_manual(
        name="屏幕录制",
        description="使用 FFmpeg 录制屏幕，支持多种格式",
        category="媒体处理",
        keywords=[
            "屏幕", "录制", "录屏", "捕获", "截屏",
            "screen", "record", "capture", "recording", "screencast",
            "屏幕录像", "录制视频", "全屏录制", "区域录制", "桌面录制",
            "FFmpeg", "GDI", "X11", "AVFoundation"
        ],
        icon="VIDEOCAM",
        tool_id="video.screen_record",
        gradient_colors=("#FF416C", "#FF4B2B"),
    )
    
    # ==================== 开发工具 ====================
    
    register_tool_manual(
        name="Base64转图片",
        description="将Base64编码转换为图片",
        category="开发工具",
        keywords=[
            "Base64", "解码", "图片", "转换", "还原",
            "decode", "image", "data uri", "convert", "base 64",
            "base64转图片", "图片解码", "还原图片"
        ],
        icon="IMAGE_OUTLINED",
        tool_id="dev.base64_to_image",
        gradient_colors=("#4FACFE", "#00F2FE"),
    )
    
    register_tool_manual(
        name="编码转换",
        description="文本编码格式转换",
        category="开发工具",
        keywords=[
            "编码", "转换", "文本", "字符集", "乱码",
            "encoding", "charset", "convert", "text",
            "utf8", "gbk", "gb2312", "unicode", "big5", "iso-8859",
            "乱码修复", "编码转换", "字符编码"
        ],
        icon="TRANSFORM_ROUNDED",
        tool_id="dev.encoding",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="JSON 查看器",
        description="格式化并以树形结构查看 JSON",
        category="开发工具",
        keywords=[
            "JSON", "格式化", "查看", "树形", "解析", "美化",
            "prettify", "format", "viewer", "tree", "parse", "beautify",
            "json格式化", "json美化", "json查看", "json编辑", "json校验"
        ],
        icon="DATA_OBJECT",
        tool_id="dev.json_viewer",
        gradient_colors=("#FA8BFF", "#2BD2FF"),
    )
    
    register_tool_manual(
        name="HTTP 客户端",
        description="发送 HTTP 请求，测试 API 接口",
        category="开发工具",
        keywords=[
            "HTTP", "API", "请求", "测试", "客户端", "接口", "调试",
            "REST", "POST", "GET", "PUT", "DELETE", "PATCH",
            "request", "client", "debug", "postman", "curl", "insomnia",
            "接口测试", "api测试", "发送请求"
        ],
        icon="HTTP",
        tool_id="dev.http_client",
        gradient_colors=("#F093FB", "#F5576C"),
    )
    
    register_tool_manual(
        name="WebSocket 客户端",
        description="连接 WebSocket，实时收发消息",
        category="开发工具",
        keywords=[
            "WebSocket", "WS", "实时", "连接", "消息", "客户端", "测试", "调试",
            "socket", "realtime", "chat", "ws", "wss", "websocket",
            "长连接", "双向通信", "实时通信"
        ],
        icon="CABLE",
        tool_id="dev.websocket_client",
        gradient_colors=("#A8EDEA", "#FED6E3"),
    )
    
    register_tool_manual(
        name="编码/解码",
        description="Base64、URL、HTML、Unicode 编解码",
        category="开发工具",
        keywords=[
            "编码", "解码", "Base64", "URL", "HTML", "Unicode",
            "encode", "decode", "转换", "加密", "解密",
            "urlencode", "urldecode", "htmlencode", "htmldecode",
            "base64编码", "url编码", "unicode编码"
        ],
        icon="LOCK_OPEN",
        tool_id="dev.encoder_decoder",
        gradient_colors=("#FFD89B", "#19547B"),
    )
    
    register_tool_manual(
        name="正则表达式测试器",
        description="实时测试正则表达式，可视化匹配结果",
        category="开发工具",
        keywords=[
            "正则", "正则表达式", "匹配", "测试", "验证",
            "regex", "regexp", "pattern", "match", "test", "regular expression",
            "表达式", "提取", "替换", "正则测试"
        ],
        icon="PATTERN",
        tool_id="dev.regex_tester",
        gradient_colors=("#FC466B", "#3F5EFB"),
    )
    
    register_tool_manual(
        name="时间工具",
        description="时间戳转换、时间计算、格式转换",
        category="开发工具",
        keywords=[
            "时间", "时间戳", "日期", "转换", "计算",
            "timestamp", "date", "time", "unix", "convert",
            "格式化", "timezone", "时区", "毫秒", "秒",
            "时间戳转换", "日期转换", "unix时间戳"
        ],
        icon="ACCESS_TIME",
        tool_id="dev.timestamp_tool",
        gradient_colors=("#11998E", "#38EF7D"),
    )
    
    register_tool_manual(
        name="JWT 工具",
        description="解析 JWT Token，查看头部和载荷",
        category="开发工具",
        keywords=[
            "JWT", "Token", "解析", "验证", "认证", "授权",
            "Bearer", "decode", "parse", "auth", "json web token",
            "jwt解析", "token解析", "登录", "身份验证"
        ],
        icon="KEY",
        tool_id="dev.jwt_tool",
        gradient_colors=("#00C9FF", "#92FE9D"),
    )
    
    register_tool_manual(
        name="UUID/随机数生成器",
        description="生成 UUID、随机字符串、随机密码",
        category="开发工具",
        keywords=[
            "UUID", "GUID", "随机", "密码", "生成", "字符串",
            "random", "password", "generate", "string", "unique",
            "随机数", "随机密码", "uuid生成", "密码生成器", "强密码"
        ],
        icon="FINGERPRINT",
        tool_id="dev.uuid_generator",
        gradient_colors=("#F857A6", "#FF5858"),
    )
    
    register_tool_manual(
        name="颜色工具",
        description="颜色格式转换、图片取色器、调色板",
        category="开发工具",
        keywords=[
            "颜色", "色值", "取色", "吸管", "调色板", "图片",
            "color", "HEX", "RGB", "HSL", "HSV", "CMYK",
            "convert", "palette", "pick", "eyedropper", "picker",
            "颜色转换", "颜色选择", "配色", "色卡"
        ],
        icon="PALETTE",
        tool_id="dev.color_tool",
        gradient_colors=("#FF9A9E", "#FAD0C4"),
    )
    
    register_tool_manual(
        name="Markdown 编辑器",
        description="编辑 Markdown，实时预览，导出 HTML",
        category="开发工具",
        keywords=[
            "Markdown", "MD", "预览", "HTML", "格式化", "编辑器", "文档",
            "preview", "editor", "render", "export",
            "markdown预览", "md编辑", "文档编辑"
        ],
        icon="DESCRIPTION",
        tool_id="dev.markdown_viewer",
        gradient_colors=("#A8CABA", "#5D4E6D"),
    )
    
    register_tool_manual(
        name="DNS 查询",
        description="多种记录类型查询、反向查询、批量查询、指定服务器",
        category="开发工具",
        keywords=[
            "DNS", "域名", "解析", "查询", "IP", "反向",
            "domain", "lookup", "resolve", "nslookup", "dig",
            "A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA",
            "记录", "服务器", "dns查询", "域名解析"
        ],
        icon="DNS",
        tool_id="dev.dns_lookup",
        gradient_colors=("#4CA1AF", "#C4E0E5"),
    )
    
    register_tool_manual(
        name="端口扫描",
        description="端口检测、批量端口、常用端口、范围扫描",
        category="开发工具",
        keywords=[
            "端口", "扫描", "检测", "网络", "批量",
            "port", "scan", "check", "network", "probe",
            "HTTP", "SSH", "MySQL", "Redis", "开放端口", "端口检测"
        ],
        icon="ROUTER",
        tool_id="dev.port_scanner",
        gradient_colors=("#FC466B", "#3F5EFB"),
    )

    register_tool_manual(
        name="数据格式转换",
        description="JSON、YAML、XML、TOML 互转",
        category="开发工具",
        keywords=[
            "JSON", "YAML", "XML", "TOML", "格式", "转换",
            "convert", "format", "transform",
            "xml2json", "json2yaml", "yaml2json", "toml2json",
            "数据转换", "格式互转", "配置文件"
        ],
        icon="SWAP_HORIZ",
        tool_id="dev.format_convert",
        gradient_colors=("#11998E", "#38EF7D"),
    )

    register_tool_manual(
        name="文本对比",
        description="左右分栏对比，逐行高亮差异",
        category="开发工具",
        keywords=[
            "对比", "比较", "文本", "文件", "差异",
            "diff", "compare", "difference", "merge",
            "notepad++", "代码对比", "文本差异", "文件对比"
        ],
        icon="COMPARE",
        tool_id="dev.text_diff",
        gradient_colors=("#3A7BD5", "#00D2FF"),
    )

    register_tool_manual(
        name="加解密工具",
        description="AES, DES, RC4, MD5, SHA 等",
        category="开发工具",
        keywords=[
            "加密", "解密", "密码", "哈希",
            "encrypt", "decrypt", "hash", "crypto", "cipher",
            "md5", "sha", "sha1", "sha256", "sha512",
            "aes", "des", "rc4", "rsa", "base64",
            "加密解密", "哈希计算", "密码学"
        ],
        icon="SECURITY",
        tool_id="dev.crypto_tool",
        gradient_colors=("#2C3E50", "#4CA1AF"),
    )

    register_tool_manual(
        name="SQL 格式化",
        description="格式化/压缩 SQL，支持多种方言",
        category="开发工具",
        keywords=[
            "SQL", "格式化", "美化", "压缩", "数据库", "查询",
            "format", "prettify", "beautify", "minify",
            "MySQL", "PostgreSQL", "Oracle", "SQLite", "sql格式化"
        ],
        icon="CODE",
        tool_id="dev.sql_formatter",
        gradient_colors=("#1FA2FF", "#12D8FA"),
    )

    register_tool_manual(
        name="Cron 表达式",
        description="解析 Cron 表达式，预测执行时间",
        category="开发工具",
        keywords=[
            "Cron", "定时", "任务", "表达式", "时间", "执行",
            "schedule", "crontab", "timer", "job",
            "Linux", "Unix", "定时任务", "cron表达式", "计划任务"
        ],
        icon="SCHEDULE",
        tool_id="dev.cron_tool",
        gradient_colors=("#A770EF", "#CF8BF3"),
    )

    # ==================== 其他工具 ====================
    register_tool_manual(
        name="Windows更新管理",
        description="管理Windows更新设置，禁用或恢复更新",
        category="其他工具",
        keywords=[
            "Windows", "更新", "管理", "禁用", "恢复", "暂停", "升级",
            "windows update", "disable", "enable", "pause", "stop",
            "关闭更新", "停止更新", "系统更新", "自动更新"
        ],
        icon="UPDATE_DISABLED",
        tool_id="others.windows_update",
        gradient_colors=("#FF6B6B", "#FFA500"),
    )
    
    register_tool_manual(
        name="图片转URL",
        description="上传图片获取分享链接",
        category="其他工具",
        keywords=[
            "图片", "上传", "分享", "链接", "url", "图床",
            "image", "upload", "share", "hosting",
            "图片链接", "图片上传", "在线图片", "外链"
        ],
        icon="LINK",
        tool_id="others.image_to_url",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="文件转URL",
        description="上传文件获取分享链接",
        category="其他工具",
        keywords=[
            "文件", "上传", "分享", "链接", "url",
            "file", "upload", "share", "hosting",
            "文件链接", "文件上传", "在线文件", "外链", "网盘"
        ],
        icon="UPLOAD_FILE",
        tool_id="others.file_to_url",
        gradient_colors=("#F093FB", "#F5576C"),
    )
    
    register_tool_manual(
        name="ICP备案查询",
        description="查询域名、APP、小程序的ICP备案信息",
        category="其他工具",
        keywords=[
            "ICP", "备案", "查询", "域名", "企业",
            "APP", "小程序", "快应用", "beian",
            "domain", "query", "search", "网站备案", "备案查询"
        ],
        icon="SEARCH",
        tool_id="others.icp_query",
        gradient_colors=("#43E97B", "#38F9D7"),
    )
    
    register_tool_manual(
        name="AI证件照",
        description="智能抠图换底，一键生成证件照",
        category="其他工具",
        keywords=[
            "证件照", "抠图", "换底", "一寸", "二寸", "AI",
            "签证照", "护照照片", "身份证照", "蓝底", "白底", "红底",
            "id photo", "portrait", "background", "photo",
            "证件", "寸照", "照片", "换背景", "考试", "入学"
        ],
        icon="BADGE",
        tool_id="others.id_photo",
        gradient_colors=("#667EEA", "#764BA2"),
    )
    
    register_tool_manual(
        name="文本翻译",
        description="支持 AI 翻译和 Bing 翻译，多语言互译",
        category="其他工具",
        keywords=[
            "翻译", "translate", "英语", "日语", "韩语", "中文",
            "英文", "日文", "韩文", "法语", "德语", "西班牙语",
            "AI翻译", "Bing翻译", "机器翻译", "多语言", "互译",
            "translation", "language", "chinese", "english", "japanese"
        ],
        icon="TRANSLATE",
        tool_id="others.translate",
        gradient_colors=("#00C9FF", "#92FE9D"),
    )