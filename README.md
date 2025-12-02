<div align="center">

# MTools - 多功能桌面工具箱

**一款功能强大、界面精美的现代化桌面工具集**

集成图片处理、音视频编辑、AI 工具等，正在不断添加更多功能

*初次运行需要下载依赖环境，请耐心等待*

</div>

---

## 🚀 快速开始

### 环境要求
- **操作系统**: Windows 10/11、macOS (实验性支持) 或 Linux
- **Python**: 3.11+
- **包管理器**: [uv](https://github.com/astral-sh/uv) - 推荐使用的 Python 包管理器

### 一键安装依赖

使用 uv 可以快速同步所有依赖（包括开发依赖）：

```bash
# 克隆仓库
git clone https://github.com/HG-ha/MTools
cd MTools

# 一键同步依赖（自动创建虚拟环境）
uv sync

# 运行程序
uv run flet run
```

**⚠️ Linux 用户（可选 GPU 加速）：**
```bash
# 如需 CUDA 加速，可更换为 GPU 版本（需要 NVIDIA GPU 和 CUDA 环境）
uv remove onnxruntime-directml onnxruntime
uv add onnxruntime-gpu==1.22.0
```

---

## 📦 打包编译

如需将项目编译为独立的可执行文件（无需 Python 环境即可运行），请查看：

📘 **[完整编译指南](./docs/build_guide.md)**

### 快速编译

```bash
# Release 模式（生产环境）
python build.py

# Dev 模式（开发测试，保留控制台）
python build.py --mode dev

# 启用 UPX 压缩
python build.py --upx

# 查看所有选项
python build.py --help
```

编译完成后，可执行文件位于 `dist/release/` 目录。

---

## ✨ 核心特性

### 🤖 AI 智能处理
- **AI 智能抠图** - 一键移除图片背景，支持人像、动漫、通用场景等多种模型
- **AI 人声分离** - 专业级人声/伴奏分离，支持多种 UVR MDX-Net 模型，轻松制作卡拉OK伴奏
- **视频人声分离** - 直接处理视频，分离人声或背景音，保留原视频画面

### 📷 图片处理
- **专业压缩** - 集成 mozjpeg、pngquant 专业引擎，支持 12+ 种格式，提供快速/标准/极限三种模式
- **格式转换** - 主流格式互转，保留 EXIF 信息
- **智能编辑** - 尺寸调整、图片裁剪、旋转翻转、水印添加、去除 EXIF
- **拼图制作** - 支持九宫格、横向、纵向拼接
- **GIF 调整** - 速度调整、帧数优化、导出为视频

### 🎵 音频处理
- **格式转换** - 支持 MP3、WAV、FLAC、AAC、OGG 等格式
- **音频压缩** - 自定义比特率和采样率
- **人声分离** - AI 驱动，提取纯人声或伴奏

### 🎬 视频处理
- **格式转换** - MP4、AVI、MKV、MOV 等格式互转
- **视频压缩** - H.264/H.265 编码，CRF 质量控制
- **提取音频** - 从视频中提取音轨
- **人声分离** - 分离视频中的人声和背景音

### 🛠️ 开发工具
- **编码转换** - 自动检测编码，解决乱码问题，支持 UTF-8、GBK、Big5 等
- **Base64 工具** - 图片与 Base64 互转
- **代码格式化** - JSON、XML、SQL 格式化/美化

### 🔧 更多实用工具
- **二维码生成** - 支持文本、链接转二维码，自定义颜色和大小
- **图片信息查看** - 查看图片详细信息（尺寸、格式、DPI、EXIF 等）
- **图片切割/合并** - 将大图切割为小图，或将多张小图合并为一张

---

## ⚡ 性能优化

### GPU 加速支持
本项目的 AI 功能支持 GPU 加速，可大幅提升处理速度：

**AI 智能抠图**
- 支持 NVIDIA CUDA、AMD DirectML、Apple Metal
- GPU 加速可提速 **3-10 倍**

**AI 人声分离**
- 支持 NVIDIA CUDA、AMD DirectML、Apple Silicon
- 长音频处理速度提升显著

### 平台特定说明

#### AI 功能 (ONNX Runtime)

| 平台 | ONNX Runtime 版本 | GPU 支持 |
|------|------------------|---------|
| **Windows (Intel/AMD GPU)** | `onnxruntime-directml==1.22.0` | ✅ DirectML |
| **Windows (NVIDIA GPU)** | `onnxruntime-directml==1.22.0` 或 `onnxruntime-gpu` | ✅ DirectML / CUDA |
| **macOS (Apple Silicon)** | `onnxruntime==1.22.0` | ✅ CoreML (内置) |
| **macOS (Intel)** | `onnxruntime==1.22.0` | ⚠️ CPU |
| **Linux** | `onnxruntime==1.22.0` 或 `onnxruntime-gpu` | ⚠️ CPU / CUDA |

> 💡 **提示**：
> - **Windows 用户**：使用默认配置即可（已包含 `onnxruntime-directml==1.22.0`），自动支持 DirectML GPU 加速
> - **macOS 用户**：使用默认配置即可（已包含 `onnxruntime==1.22.0`），Apple Silicon 自动支持 CoreML 加速
> - **Linux 用户**：默认 CPU 模式，如需 GPU 加速请安装 `onnxruntime-gpu`（需要 NVIDIA GPU 和 CUDA 环境）
> - 程序会自动检测并使用可用的 GPU 加速，无需额外配置
> - 如果没有 GPU，程序会自动回退到 CPU 模式

#### 图片压缩工具

| 平台 | JPEG 压缩 | PNG 压缩 | 说明 |
|------|----------|---------|------|
| **Windows** | mozjpeg + Pillow | pngquant + Pillow | 支持自动下载安装 |
| **macOS** | Pillow | pngquant + Pillow | mozjpeg 暂不支持，使用 Pillow 替代 |
| **Linux** | Pillow | pngquant + Pillow | mozjpeg 暂不支持，使用 Pillow 替代 |

#### 音视频处理工具

| 平台 | FFmpeg | 说明 |
|------|--------|------|
| **Windows** | ✅ 自动下载 | 使用 gyan.dev 提供的精简版 |
| **macOS** | ✅ 自动下载 | 使用 evermeet.cx 提供的官方版本 |
| **Linux** | ✅ 自动下载 | 使用 johnvansickle.com 提供的静态编译版 |

---

## 🎨 界面特色

- **Material Design 3** - 遵循最新设计规范，界面精美流畅
- **深色模式** - 自动跟随系统主题，保护视力
- **毛玻璃效果** - 现代化的视觉体验
- **自定义主题** - 支持多种主题颜色和字体选择
- **全局搜索** - `Ctrl+K` 快速查找任何功能
- **批量处理** - 所有功能均支持批量操作，提高工作效率

---

<div align="center">

**Made with ❤️ using Python & Flet**

👨‍💻 **作者**：[HG-ha](https://github.com/HG-ha)

[查看更多项目](https://github.com/HG-ha) · [加入Q群 1029212047](https://qm.qq.com/q/vxxxgHGELu)
</div>