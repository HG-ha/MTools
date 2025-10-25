# MyTools - 多功能桌面应用程序

## 项目简介

MyTools是一个集成了音视频处理、编程语言编码转换、图片处理等功能的多功能桌面应用程序。使用Python和Flet框架开发，遵循Material Design设计原则，提供现代化的用户界面和流畅的用户体验。

## 功能特性

### 图片处理
- 图片格式转换（JPG、PNG、WebP等）
- 尺寸调整和批量处理
- 滤镜效果应用

### 音视频处理
- 支持多种音视频格式转换
- 音频剪辑和合并
- 参数调整（比特率、采样率等）

### 编码转换
- 自动检测文件编码
- 支持UTF-8、GBK、GB2312等编码转换
- 批量编码转换

### 代码格式化
- 支持Python、Java、C++等多种语言
- 自动调整代码缩进和风格
- 批量格式化项目

### 应用设置
- 数据存储目录管理（遵循平台规范）
- 支持自定义数据存储位置
- 主题跟随系统设置

## 技术栈

- **核心语言**: Python 3.9+
- **UI框架**: Flet (遵循Material Design)
- **音视频处理**: ffmpeg-python
- **图片处理**: Pillow + mozjpeg + pngquant
- **编码转换**: chardet

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行应用

```bash
flet run src/main.py
```

## 打包应用

```bash
flet pack src/main.py
```

## 项目结构

```
mytools/
├── src/                    # 源代码目录
│   ├── main.py            # 应用入口点
│   ├── assets/            # 静态资源
│   ├── components/        # 可复用UI组件
│   │   ├── custom_title_bar.py   # 自定义标题栏
│   │   └── feature_card.py       # 功能卡片
│   ├── views/             # 页面视图
│   │   ├── main_view.py          # 主视图
│   │   ├── image_view.py         # 图片处理视图
│   │   ├── audio_view.py         # 音频处理视图
│   │   ├── video_view.py         # 视频处理视图
│   │   ├── encoding_view.py      # 编码转换视图
│   │   ├── code_format_view.py   # 代码格式化视图
│   │   └── settings_view.py      # 设置视图
│   ├── utils/             # 工具函数
│   │   └── file_utils.py         # 文件操作工具
│   ├── services/          # 业务逻辑服务
│   │   └── config_service.py     # 配置管理服务
│   ├── models/            # 数据模型
│   └── constants/         # 常量定义
│       └── app_config.py         # 应用配置常量
├── storage/               # 数据存储目录（可自定义）
│   ├── data/             # 数据文件
│   └── temp/             # 临时文件
├── requirements.txt       # 依赖列表
├── pyproject.toml         # 项目配置
├── README.md              # 项目说明
└── 开发准则.md            # 开发规范
```

## 数据存储

应用数据默认遵循各平台的规范存储：

- **Windows**: `%APPDATA%\MyTools`
- **macOS**: `~/Library/Application Support/MyTools`
- **Linux**: `~/.local/share/MyTools`

你也可以在设置页面中自定义数据存储位置。

## 图片压缩

本应用集成了专业的图片压缩工具：

- **JPEG 压缩**: mozjpeg - 可减小 50-70% 文件大小
- **PNG 压缩**: pngquant - 可减小 60-80% 文件大小

提供三种压缩模式：
- **快速模式**: 使用 Pillow，速度快
- **标准模式**: 使用 mozjpeg/pngquant，压缩率高
- **极限模式**: 最高压缩率，文件最小

## 开发准则

请参考[开发准则.md](开发准则.md)了解项目的开发规范和设计原则。
