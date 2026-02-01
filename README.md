<div align="center">

<img src="./src/assets/icon.png" alt="MTools Logo" width="128" height="128">

# MTools
一款功能强大、界面精美的现代化桌面工具集

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/Flet-0.28.3-brightgreen.svg)](https://flet.dev/)
[![License](https://img.shields.io/badge/License-MIT-orange.svg)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![Downloads](https://img.shields.io/github/downloads/HG-ha/MTools/total?style=flat-square)](https://github.com/HG-ha/MTools/releases)



集成图片处理、音视频编辑、AI 智能工具、开发辅助等功能，支持跨平台GPU加速


</div>

---

## 快速开始

### 方式一：下载发布版（推荐）

直接下载已编译好的可执行文件，**无需安装 Python**：

- **[Releases 下载](https://github.com/HG-ha/MTools/releases)**
- **[国内用户下载](https://openlist.wer.plus/MTools)**

支持平台及预编译版本说明：
- ✅ Windows 10/11 (x64)
  - MTools_Windows_amd64：体积最小，并且支持nvidia、amd、intel显卡加速，但不支持手动管理显存，如果您的显存低于8GB或发布时间早于nvidia30系，尽量使用此版本
  - MTools_Windows_amd64_CUDA：体积中等，使用CUDA进行加速，但需要手动安装CUDA 12.x + cuDNN 9.x
  - MTools_Windows_amd64_CUDA_FULL：体积最大，内置完整的CUDA加速环境，无需手动安装CUDA和cuDNN

- ⚠️ macOS (实验性支持)
  - MTools_Darwin_arm64：只支M系列芯片，支持Core ML加速

- ⚠️ Linux (实验性支持)
  - MTools_Linux_amd64：体积最小，不支持GPU加速
  - MTools_Linux_amd64_CUDA：体积中等，使用CUDA进行加速，但需要手动安装CUDA 12.x + cuDNN 9.x
  - MTools_Linux_amd64_CUDA_FULL：体积最大，内置完整的CUDA加速环境，无需手动安装CUDA和cuDNN

下载后解压即可使用！

### 方式二：从源码运行

#### 环境要求
- **操作系统**: Windows 10/11、macOS 或 Linux
- **Python**: 3.11+
- **包管理器**: [uv](https://github.com/astral-sh/uv) - 推荐使用的 Python 包管理器

#### 一键安装依赖

```bash
# 1. 克隆仓库
git clone https://github.com/HG-ha/MTools.git
cd MTools

# 2. 一键同步依赖（自动创建虚拟环境）
uv sync

# 3. 运行程序
uv run flet run
```

启用 CUDA GPU 加速（默认已启用平台通用加速）：

```bash
# 使用此方式可完全榨干NVIDIA GPU性能
# 替换为 GPU 版本（需要 NVIDIA GPU 和 CUDA 环境）
uv remove onnxruntime-directml onnxruntime
uv add onnxruntime-gpu==1.22.0
# 需要免去配置cuda和cudnn环境的话请更改为此依赖
# 会导致体积增大数倍
# uv add onnxruntime-gpu[cuda,cudnn]==1.22.0
```

> 📘 **版本说明**：
> - **普通版本**：支持NVIDIA、AMD、Intel显卡加速，支持coreml加速，对 NVIDIA GPU 的性能释放可能不如CUDA系列
> - **CUDA 版本**：使用系统安装的 CUDA 和 cuDNN，体积小但需要预先配置 CUDA 环境（CUDA 12.x + cuDNN 9.x）
> - **CUDA_FULL 版本**：内置完整的 CUDA 和 cuDNN 运行时库，无需额外配置，开箱即用，但体积较大（+2GB）

> 💡 **编译和版本说明**：如需将项目编译为独立可执行文件，请参考 📘 **[完整编译指南](./docs/build_guide.md)**

---

## 性能优化

### GPU 加速支持

本项目的 AI 功能支持 GPU 加速，可大幅提升处理速度，并且提供 `CUDA` 以及 `CUDA_FULL` 编译版本

### 平台特定说明

#### AI 功能（ONNX Runtime）

| 平台 | 默认版本 | GPU 支持 | 说明 |
|------|---------|---------|------|
| **Windows** | `onnxruntime-directml==1.22.0` | ✅ DirectML | 自动支持 Intel/AMD/NVIDIA GPU |
| **macOS (Apple Silicon)** | `onnxruntime==1.22.0` | ✅ CoreML | 内置硬件加速 |
| **macOS (Intel)** | `onnxruntime==1.22.0` | ⚠️ CPU | 无 GPU 加速 |
| **Linux** | `onnxruntime==1.22.0` | ⚠️ CPU | 可选 `onnxruntime-gpu` (CUDA) |

> 💡 **提示**：DirectML 版本不支持限制显存，只有CUDA可限制显存大小

---


## 致谢

### 代码参考

本项目在开发过程中参考和使用了以下开源项目的代码：

- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)** - 语音识别与合成框架，提供高性能的离线语音处理能力
- **[PPOCR_v5](https://github.com/Nnow2024/PPOCR_v5)** - 高精度OCR识别引擎
- **[FunASR](https://github.com/modelscope/FunASR)** - 语音识别工具包
- **[ICP_Query](https://github.com/HG-ha/ICP_Query)** - ICP备案查询功能实现
- **[HivisionIDPhotos](https://github.com/Zeyi-Lin/HivisionIDPhotos)** - AI证件照
- **[video-subtitle-remover](https://github.com/YaoFANGUK/video-subtitle-remover)** - AI去水印


### 外部服务

本项目使用了以下外部服务：

- **[ModelScope](https://www.modelscope.cn/)** - AI模型托管与分享平台
- **[imagetourl.net](https://imagetourl.net/)** - 图片转URL服务
- **[catbox.moe](https://catbox.moe/)** - 文件上传服务
- **[gh-proxy.com](https://gh-proxy.com/)** - GitHub加速代理

### 服务器赞助

感谢以下赞助商为本项目提供服务器支持：

- **[林枫云 www.dkdun.cn](https://www.dkdun.cn/)** - 提供稳定的云服务器资源

---

<div align="center">

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=HG-ha/MTools&type=Date)](https://star-history.com/#HG-ha/MTools&Date)

---

## 支持项目

如果这个项目对你有帮助，欢迎通过以下方式支持：

- 给项目一个 ⭐ Star
- 分享给更多需要的人
- 提交 Issue 和 Pull Request
- 请作者喝杯咖啡 ☕

<details>
<summary>打赏支持</summary>

<br/>

你的支持是项目持续维护的动力！

<div align="center">
  <img src="./assets/wechat_reward.jpg" alt="微信赞赏码" width="300"/>
  <p><b>微信赞赏</b></p>
</div>

</details>

---

**Made with ❤️ using Python & Flet**

👨‍💻 **作者**：[HG-ha](https://github.com/HG-ha) · [加入Q群 1029212047](https://qm.qq.com/q/gHf7f0R3zy)

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>
