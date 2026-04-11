# MTools 编译指南

本指南将帮助您使用 `flet build` 编译 MTools 项目，生成独立的可执行文件。

> 💡 **说明**：自 v0.84.0 起，项目已切换为 `flet build` 打包方式。旧的 Nuitka 构建脚本 (`build.py`) 仍保留在项目中，但不再作为主要构建方式。

## 🚀 快速开始

### 标准版本（推荐大多数用户）
```bash
# 1. 安装依赖
uv sync

# 2. 安装 flet CLI
pip install flet-cli==0.84.0

# 3. 编译
python flet_build.py windows
# 或直接：flet build windows
```

**适用场景**：
- ✅ 跨平台通用（Windows/macOS/Linux）
- ✅ 自适应 GPU 加速（NVIDIA/AMD/Intel/Apple Silicon）
- ✅ 无需安装 CUDA 环境

### CUDA FULL 版本（NVIDIA GPU 极致性能）
```bash
# 1. 安装依赖
uv sync

# 2. 安装 flet CLI
pip install flet-cli==0.84.0

# 3. 切换为 CUDA FULL onnxruntime
python scripts/prepare_cuda_variant.py cuda_full

# 4. 编译
python flet_build.py windows
```

**适用场景**：
- ✅ NVIDIA 显卡用户追求最佳 AI 性能
- ✅ 内置完整 CUDA 库，用户无需安装 CUDA Toolkit
- ⚠️ 体积较大

## 📋 前置要求

| 工具 | 必需 | 说明 |
|------|------|------|
| **Python 3.11** | ✅ | 运行 `python --version` 验证 |
| **uv 包管理器** | ✅ | 推荐的依赖管理工具 |
| **flet-cli 0.84.0** | ✅ | `pip install flet-cli==0.84.0` |
| **Visual Studio Build Tools** | ✅ (Windows) | 需要 C++ 桌面开发工作负载 |
| **Flutter SDK** | ❌ | flet-cli 会自动下载并管理 |

### 安装步骤

**1. 安装 uv 包管理器**
```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

**2. 安装 flet-cli**
```bash
pip install flet-cli==0.84.0
```

**3. Visual Studio Build Tools（Windows）**

`flet build windows` 需要 MSVC 编译器。从 [Visual Studio 下载页面](https://visualstudio.microsoft.com/downloads/) 安装 **Build Tools for Visual Studio**，勾选 **"使用 C++ 的桌面开发"** 工作负载。

## 📦 编译流程

### 1. 克隆项目
```bash
git clone https://github.com/HG-ha/MTools.git
cd MTools
```

### 2. 安装依赖
```bash
uv sync
```

### 3. 执行编译

推荐使用包装脚本 `flet_build.py`，它会自动修补已知的上游构建问题：

```bash
# 基本用法
python flet_build.py windows

# 带详细输出和版本号
python flet_build.py windows --verbose --build-version=0.0.14-beta --build-number=42

# macOS
python flet_build.py macos

# Linux
python flet_build.py linux
```

也可以直接调用 `flet build`（不含自动修补）：

```bash
flet build windows --verbose
```

### `flet_build.py` 自动修补的问题

| 补丁 | 说明 |
|------|------|
| vcruntime DLL 路径 | 修复 `serious_python_windows` CMakeLists.txt 中 vcruntime140_1.dll 的复制源路径 |
| 平台图标选择 | 确保 Windows 构建不会选中 `.icns`、macOS 构建不会选中 `.ico` |

## ⚙️ 编译选项

### 常用参数

所有参数直接传递给 `flet build`：

| 参数 | 说明 | 示例 |
|------|------|------|
| `windows` / `macos` / `linux` | 目标平台 | `python flet_build.py windows` |
| `--verbose` / `-v` | 详细输出 | `python flet_build.py windows -v` |
| `--build-version` | 版本号 | `--build-version=0.0.14-beta` |
| `--build-number` | 构建号 | `--build-number=42` |
| `--no-rich-output` | 关闭富文本输出（CI 环境） | `--no-rich-output` |
| `--yes` | 自动确认提示 | `--yes` |

### 使用示例

```bash
# 本地开发构建（详细输出）
python flet_build.py windows -v

# CI 环境构建
python flet_build.py windows --verbose --no-rich-output --yes --build-version=0.0.14-beta --build-number=123

# CUDA 版本
python scripts/prepare_cuda_variant.py cuda
python flet_build.py windows -v

# CUDA FULL 版本
python scripts/prepare_cuda_variant.py cuda_full
python flet_build.py windows -v
```

## 📊 配置对比

### CUDA 版本对比

| 特性 | 标准版 | CUDA 版 | CUDA FULL 版 |
|------|--------|---------|--------------|
| **onnxruntime** | `onnxruntime-directml` (Win)<br>`onnxruntime` (Mac/Linux) | `onnxruntime-gpu` | `onnxruntime-gpu[cuda,cudnn]` |
| **sherpa-onnx** | `sherpa-onnx` (CPU) | `sherpa-onnx+cuda` | `sherpa-onnx+cuda` |
| **GPU 支持** | DirectML/CoreML | CUDA (NVIDIA) | CUDA (NVIDIA) |
| **用户依赖** | ✅ 无 | ⚠️ 需 CUDA Toolkit | ✅ 无（内置完整） |
| **部署难度** | 🟢 简单 | 🔴 困难 | 🟢 简单 |
| **AI 性能** | ⭐⭐ 中等 | ⭐⭐⭐ 最佳 | ⭐⭐⭐ 最佳 |
| **兼容性** | ⭐⭐⭐ 最广 | ⭐⭐ 需配置 | ⭐⭐⭐ 开箱即用 |
| **切换脚本** | 默认 | `prepare_cuda_variant.py cuda` | `prepare_cuda_variant.py cuda_full` |

> **注意**: CUDA 版的 `sherpa-onnx` 轮子托管在 [k2-fsa 自定义索引](https://k2-fsa.github.io/sherpa/onnx/cuda.html)。
> `prepare_cuda_variant.py` 会自动添加 `[[tool.uv.find-links]]`，`flet_build.py` 会自动设置 `PIP_FIND_LINKS`。

## 🗂️ 输出结构

```flet build``` 完成后的产物位于 `build/flutter` 目录下。Windows 平台的最终产物在：

```
build/flutter/build/windows/x64/runner/Release/
├── MTools.exe                   # 主程序
├── flutter_windows.dll          # Flutter 运行时
├── app_packages/                # Python 依赖
└── ...
```

## 🔄 CI/CD 自动构建

项目使用 GitHub Actions 自动构建。工作流配置在 `.github/workflows/build.yml`，支持：

- Windows (标准版 / CUDA / CUDA FULL)
- macOS (ARM64)
- Linux (标准版 / CUDA / CUDA FULL)

CI 使用 `python flet_build.py` 包装脚本进行构建，以确保自动修补生效。

## 🐛 常见问题

### Q1: `vcruntime140_1.dll` 复制失败
**症状**：CMake `file(INSTALL)` 错误，找不到 vcruntime140_1.dll

**解决方案**：使用 `python flet_build.py` 而非直接 `flet build`，脚本会自动修补此问题。

### Q2: `NoDecoderForImageFormatException` (图标问题)
**症状**：Windows 构建时 flutter_launcher_icons 无法解码 `.icns` 图标

**解决方案**：使用 `python flet_build.py`，脚本会自动移除不兼容的图标文件。

### Q3: `Unknown control: FilePicker`
**症状**：打包后运行界面显示 Unknown control: FilePicker

**原因**：Flet 0.84 中 `FilePicker` 从 overlay 控件变为 service，需注册到 `page.services` 而非 `page.overlay`。

### Q4: Python 模块未打包
**症状**：打包后运行提示找不到 Python 模块

**解决方案**：
1. 确认 `pyproject.toml` 中的依赖列表完整
2. 检查 `flet_build.py` 日志中是否有 `SERIOUS_PYTHON_SITE_PACKAGES` 设置
3. 如果是手动 `flet build`，需要确保 `build/site-packages` 存在

### Q5: CUDA FULL 版本编译
```bash
# 1. 运行 CUDA 变体准备脚本
python scripts/prepare_cuda_variant.py cuda_full

# 2. 编译
python flet_build.py windows -v

# 3. 构建完成后，恢复默认依赖（可选）
git checkout pyproject.toml
uv sync
```

### Q6: 验证 GPU 加速是否生效
```python
import onnxruntime as ort
print(ort.get_available_providers())
# Windows 标准版应包含: ['DmlExecutionProvider', 'CPUExecutionProvider']
# CUDA 版应包含: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

## 📚 旧版 Nuitka 构建（已弃用）

> ⚠️ 以下内容仅供参考。Nuitka 构建脚本 `build.py` 仍保留在项目中，但已不再作为主要构建方式。

```bash
# Nuitka Release 模式
python build.py

# Nuitka Dev 模式
python build.py --mode dev

# 更多参数
python build.py --help
```

Nuitka 构建需要额外的 C 编译器（MinGW 或 MSVC），编译时间也比 `flet build` 更长。

---

**文档版本**: v3.0
**最后更新**: 2026-04-05
