# MTools 编译指南

本指南将帮助您使用 Nuitka 编译 MTools 项目，生成独立的可执行文件，我们不使用 **flet build** 打包，等官方有更好的优化版本再接入。

## 📌 须知

### Flet 客户端打包策略

Flet 在首次启动时需要 UI 客户端（约 95MB）。我们采用**预打包策略**，构建时自动打包：

**工作流程：**
1. ✅ **自动检测**：构建时自动检查 Flet 客户端是否已打包
2. ✅ **智能打包**：如果未打包或版本不匹配，自动从虚拟环境打包
3. ✅ **编译集成**：Nuitka 将 `.flet` 打包到可执行文件中
4. ✅ **首次启动**：程序自动解压到用户目录（仅首次，约 5-10 秒）
5. ✅ **后续秒开**：直接使用已解压的客户端，启动速度极快

**方案优势：**
- 📦 **离线可用**：不依赖网络，打包后即可离线使用
- 🚀 **首次快速**：解压比下载快得多（5-10 秒 vs 30-60 秒）
- 🤖 **全自动化**：无需手动操作，构建时自动处理
- 🔄 **版本同步**：自动检测版本变化，确保客户端与代码匹配
- 🌍 **跨平台**：Windows、macOS、Linux 统一处理

## 🚀 快速参考

### 标准版本（自适应NVIDIA、AMD、Intel GPU 以及 MacOS 加速，但性能不如 CUDA）
```bash
# 1. 安装依赖
uv sync

# 2. 编译
python build.py
```

### CUDA FULL 版本（完全释放 NVIDIA GPU性能，无需手动安装cuda环境）
```bash
# 1. 安装依赖
uv sync

# 2. 安装 CUDA FULL onnxruntime
uv remove onnxruntime-directml
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"

# 3. 编译
# Windows (Command Prompt)
set CUDA_VARIANT=cuda_full

# Windows (PowerShell)
$env:CUDA_VARIANT="cuda_full"
python build.py

# Linux/macOS
export CUDA_VARIANT=cuda_full
python build.py
```

### 验证 CUDA FULL 编译成功
编译时应该看到：
```
🎯 检测到 CUDA FULL 变体，正在包含 NVIDIA 库...
✅ 找到 NVIDIA 库: ...\site-packages\nvidia
📦 发现 7 个 NVIDIA 子包:
   • nvidia.cublas (3 DLLs)
   • nvidia.cuda_nvrtc (3 DLLs)
   • nvidia.cuda_runtime (1 DLLs)
   • nvidia.cudnn (8 DLLs)
   • nvidia.cufft (2 DLLs)
   • nvidia.curand (1 DLLs)
   • nvidia.nvjitlink (1 DLLs)
✅ 已包含 7 个包，共 21 个 DLL 文件
```

## 📋 前置要求

### 必需环境

1. **Python 3.11**
   ```bash
   python --version  # 应显示 3.11.x
   ```

2. **uv 包管理器** (推荐)
   ```bash
   # Windows (PowerShell)
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   
   # 或使用 pip
   pip install uv
   ```

3. **C 编译器**（Windows 用户可跳过，Nuitka 会自动下载）
   - **Windows**: 
     
     🎯 **自动安装（推荐，无需手动操作）**
     - Nuitka 会在首次编译时自动下载 MinGW
     - 无需任何配置，开箱即用
     - 编译器缓存在 Nuitka 数据目录，后续编译无需重复下载
     
     **手动安装（可选，编译速度可能更快）**
     
     *方案 1: MinGW (轻量级，~100MB)*
     - 下载 [WinLibs MinGW](https://winlibs.com/)
     - 选择 GCC 13+ 版本 (UCRT runtime)
     - 解压到 `C:\mingw64`
     - 添加 `C:\mingw64\bin` 到系统 PATH
     - 验证: `gcc --version`
     
     *方案 2: Visual Studio Build Tools (~6GB)*
     - [下载地址](https://visualstudio.microsoft.com/downloads/)
     - 勾选 "Desktop development with C++"
   
   - **Linux**: GCC (`sudo apt install build-essential`)
   - **macOS**: Xcode Command Line Tools (`xcode-select --install`)

### 可选工具

4. **UPX** (用于压缩可执行文件，可选)
   - [下载地址](https://github.com/upx/upx/releases)
   - Windows: 下载后解压到任意目录，并添加到系统 PATH 环境变量

## 🚀 快速开始

> 💡 **Windows 用户提示**：无需手动安装 C 编译器！Nuitka 会在首次编译时自动下载 MinGW（约 100MB）。

### 1. 安装依赖

```bash
# 克隆项目
git clone https://github.com/HG-ha/MTools.git
cd MTools

# 同步依赖（包括 Nuitka）
uv sync
```

### 2. 编译打包

> 💡 **自动化提示**：构建时会自动检测并打包 Flet 客户端，无需手动操作！

> ⏱️ **首次编译提示**：
> - Windows 用户首次编译时，Nuitka 会自动下载编译器（约 100MB，需 5-10 分钟）
> - 首次会自动打包 Flet 客户端（约 50-100MB，需 1-2 分钟）
> - 后续编译无需重复下载，速度显著提升

#### 标准版本（推荐）

**Release 模式（生产环境）**
```bash
python build.py
```
- ✅ 自动打包 Flet 客户端
- ✅ 完整优化
- ✅ 无控制台窗口
- ✅ 体积较小，性能最佳
- 🎮 Windows: 支持 DirectML (Intel/AMD/NVIDIA GPU)
- 🍎 macOS: 支持 CoreML (Apple Silicon)
- ⏱️ 编译时间：首次 15-35分钟，后续 10-30分钟

**Dev 模式（开发测试）**
```bash
python build.py --mode dev
```
- ✅ 自动打包 Flet 客户端
- ✅ 快速编译
- ✅ 保留控制台窗口（可查看日志）
- ✅ 保留调试信息
- ⏱️ 编译时间：首次 10-20分钟，后续 5-15分钟

#### CUDA 版本（NVIDIA GPU 加速）

> 🎯 **适用场景**：拥有 NVIDIA 显卡，需要最佳 AI 推理性能

MTools 支持三种 CUDA 变体，性能从左到右递增：

| 版本 | CUDA 依赖 | 体积 | 兼容性 | 性能 | 推荐场景 |
|------|----------|------|--------|------|---------|
| **标准版** | ❌ 无 | 小 | ⭐⭐⭐ | ⭐⭐ | 通用，无需安装CUDA环境也可使用GPU加速，AMD、Intel通用加速 |
| **CUDA** | ⚠️ 需自行安装 | 小 | ⭐⭐ | ⭐⭐⭐ | 已安装 CUDA Toolkit |
| **CUDA FULL** | ✅ 内置完整 | 大 | ⭐⭐⭐ | ⭐⭐⭐ | 一键部署，最佳性能，体积很大 |

##### 方案 1: CUDA 版本（需外部 CUDA）

**特点**：
- 📦 体积小（不含 CUDA 库）
- ⚠️ 需要用户系统已安装 CUDA Toolkit 12.x 和 cuDNN 9.x
- 🎯 适合已配置 CUDA 环境的开发者

**编译步骤**：
```bash
# 1. 替换 onnxruntime 为 GPU 版本
uv remove onnxruntime-directml  # Windows
uv remove onnxruntime           # Linux/macOS
uv add onnxruntime-gpu==1.22.0

# 2. 设置环境变量并编译
# Windows (Command Prompt)
set CUDA_VARIANT=cuda

# Windows (PowerShell)
$env:CUDA_VARIANT="cuda"
python build.py

# Linux/macOS
export CUDA_VARIANT=cuda
python build.py
```

##### 方案 2: CUDA FULL 版本（内置完整 CUDA，推荐）

**特点**：
- ✅ 一键部署，内置所有 NVIDIA 库（CUDA 12.x + cuDNN 9.x）
- ✅ 用户无需安装任何 CUDA 依赖，开箱即用
- 📦 体积较大（约增加 500MB-1GB）
- 🎯 最佳性能，最简单部署

**编译步骤**：
```bash
# 1. 安装带完整 CUDA 和 cuDNN 的 onnxruntime
uv remove onnxruntime-directml  # Windows
uv remove onnxruntime           # Linux/macOS
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"

# 2. 设置环境变量并编译
# Windows (Command Prompt)
set CUDA_VARIANT=cuda_full

# Windows (PowerShell)
$env:CUDA_VARIANT="cuda_full"
python build.py

# Linux/macOS
export CUDA_VARIANT=cuda_full
python build.py
```

**构建输出**：
```
🎯 检测到 CUDA FULL 变体，正在包含 NVIDIA 库...
✅ 找到 NVIDIA 库: C:\...\site-packages\nvidia
📦 发现 7 个 NVIDIA 子包:
   • nvidia.cublas (3 DLLs)
   • nvidia.cuda_nvrtc (3 DLLs)
   • nvidia.cuda_runtime (1 DLLs)
   • nvidia.cudnn (8 DLLs)
   • nvidia.cufft (2 DLLs)
   • nvidia.curand (1 DLLs)
   • nvidia.nvjitlink (1 DLLs)
✅ 已包含 7 个包，共 21 个 DLL 文件
```

**CUDA 版本对比**：
```bash
# 标准版（DirectML/CoreML）
dist/release/MTools_Windows_amd64.zip          # ~200MB

# CUDA 版本（需外部 CUDA）
dist/release/MTools_Windows_amd64_CUDA.zip     # ~200MB + 需要 CUDA Toolkit

# CUDA FULL 版本（内置完整）
dist/release/MTools_Windows_amd64_CUDA_FULL.zip # ~700-800MB
```

### 3. 高级选项

**启用 UPX 压缩**
```bash
python build.py --upx
```
- 自动检测系统 PATH 中的 UPX
- 进一步减小文件体积（约 30-50%）
- 可能会使启动速度变慢

**指定 UPX 路径**
```bash
python build.py --upx --upx-path "upx.exe"
```

**调整并行任务数**
```bash
# 使用 4 个并行任务（编译更快，但占用更多资源）
python build.py --jobs 4

# 使用 1 个任务（最安全，系统配置低时推荐）
python build.py --jobs 1
```

**指定 MinGW 路径** (Windows)
```bash
# 如果 MinGW 安装在非标准位置
python build.py --mingw64 "D:\Tools\mingw64"

# 临时使用特定版本的 MinGW
python build.py --mingw64 "C:\mingw-gcc14" --jobs 4
```

**组合使用**
```bash
# 完整优化 + UPX + 4 核并行
python build.py --mode release --upx --jobs 4

# 快速测试编译
python build.py --mode dev --jobs 1

# CUDA FULL 版本 + 完整优化
$env:CUDA_VARIANT="cuda_full"  # Windows
python build.py --mode release --jobs 4
```

## 📊 构建模式对比

### 基础模式对比

| 特性 | Dev 模式 | Release 模式 |
|------|---------|-------------|
| **编译速度** | 快 ⚡ (5-15分钟) | 慢 🐢 (10-30分钟) |
| **控制台窗口** | 显示 👁️ | 隐藏 🙈 |
| **优化级别** | 低 (保留调试) | 高 (完整优化) |
| **文件体积** | 较大 | 较小 |
| **启动速度** | 较慢 | 较快 |
| **适用场景** | 开发测试 | 正式发布 |
| **Python 标志** | `no_site` | `-O`, `no_site`, `no_warnings` |

### CUDA 变体对比

| 特性 | 标准版 | CUDA 版 | CUDA FULL 版 |
|------|--------|---------|--------------|
| **onnxruntime** | `onnxruntime-directml` (Win)<br>`onnxruntime` (Mac/Linux) | `onnxruntime-gpu` | `onnxruntime-gpu[cuda,cudnn]` |
| **打包体积** | ~200MB | ~200MB | ~700-800MB |
| **GPU 支持** | DirectML (Win)<br>CoreML (Mac) | CUDA (NVIDIA) | CUDA (NVIDIA) |
| **用户依赖** | ✅ 无 | ⚠️ 需 CUDA 12.x + cuDNN 9.x | ✅ 无（内置） |
| **包含 DLL** | ❌ 无 CUDA DLL | ❌ 无 CUDA DLL | ✅ 21 个 NVIDIA DLL |
| **部署难度** | 🟢 简单 | 🔴 困难 | 🟢 简单 |
| **AI 性能** | ⭐⭐ 中等 | ⭐⭐⭐ 最佳 | ⭐⭐⭐ 最佳 |
| **兼容性** | ⭐⭐⭐ 最广 | ⭐⭐ 需配置 | ⭐⭐⭐ 开箱即用 |
| **环境变量** | 无 | `CUDA_VARIANT=cuda` | `CUDA_VARIANT=cuda_full` |
| **推荐场景** | 通用部署 | 已配置 CUDA 环境 | NVIDIA GPU 一键部署 |

## 🛠️ C 编译器对比 (Windows)

| 特性 | Nuitka 自动下载 (推荐) | 手动安装 MinGW | MSVC |
|------|---------------------|------------|------|
| **安装大小** | ~100MB | ~100MB 🎯 | ~6GB 💾 |
| **安装方式** | 完全自动 🚀 | 解压即用 ✅ | 需要安装器 ⚙️ |
| **首次编译** | 稍慢（需下载） | 正常速度 ⚡ | 正常速度 |
| **后续编译** | 正常速度 | 正常速度 ⚡ | 较慢 🐢 |
| **配置复杂度** | 零配置 ✨ | 需配置 PATH | 需安装器 |
| **开源** | ✅ 是 | ✅ 是 | ❌ 否 |
| **推荐场景** | 快速开始，零配置 | 频繁编译 | 企业级、深度优化 |

**编译器选择逻辑**：
1. ✅ 优先使用系统已安装的 MinGW（如果在 PATH 中）
2. ✅ 其次使用 MSVC（如果已安装 Visual Studio）
3. ✅ 最后由 Nuitka 自动下载 MinGW（首次编译时）

**手动指定**（可选）：
```bash
# 使用特定 MinGW 版本
python build.py --mingw64 "C:\mingw64"
```

## ⚙️ 命令行参数详解

查看所有可用参数：
```bash
python build.py --help
```

### `--mode {release,dev}`
- **默认**: `release`
- **说明**: 构建模式
  - `release`: 生产环境，完整优化
  - `dev`: 开发环境，快速编译

### `--upx`
- **默认**: 不启用
- **说明**: 启用 UPX 压缩
- **前提**: 需要安装 UPX 工具

### `--upx-path PATH`
- **默认**: 无
- **说明**: 指定 UPX 可执行文件的完整路径
- **示例**: `--upx-path "C:\upx\upx.exe"`

### `--jobs N`
- **默认**: `2`
- **说明**: 并行编译任务数
- **建议**: 
  - 低配置电脑: `1`
  - 中等配置: `2-4`
  - 高配置: `4-8` (不要超过 CPU 核心数)

### `--mingw64 PATH`
- **平台**: Windows only
- **说明**: 指定 MinGW64 安装路径
- **示例**: `--mingw64 "C:\mingw64"` 或 `--mingw64 "D:\Tools\mingw-w64"`
- **用途**: 
  - 使用非标准路径的 MinGW
  - 临时使用特定版本的 GCC
  - 强制使用 MinGW 而非 MSVC
- **注意**: 路径应包含 `bin` 子目录（如 `C:\mingw64\bin\gcc.exe`）

## 🗂️ 输出结构

编译完成后，文件位于 `dist/release/` 目录：

```
dist/release/
├── MTools_x64/           # 可执行程序目录
│   ├── MTools.exe        # 主程序
│   ├── src/assets/       # 资源文件
│   └── *.dll             # 依赖库
└── MTools_Windows_AMD64.zip  # 压缩包（自动生成）
```

## 💡 优化建议

### 减小文件体积

1. **启用 UPX 压缩**
   ```bash
   python build.py --upx
   ```
   - 可减小 30-50% 体积
   - 略微增加启动时间（几毫秒）

2. **检查依赖**
   - 移除不必要的依赖包
   - 使用轻量级替代方案

### 加快编译速度

1. **增加并行任务数**
   ```bash
   python build.py --jobs 4
   ```
   - 充分利用多核 CPU
   - 注意内存占用

2. **使用 Dev 模式测试**
   ```bash
   python build.py --mode dev --jobs 4
   ```
   - 快速验证功能
   - 确认无误后再用 Release 编译

### 避免系统卡顿

1. **降低并行度**
   ```bash
   python build.py --jobs 1
   ```

2. **关闭其他程序**
   - 编译时关闭浏览器、IDE 等
   - 确保有足够的磁盘空间（至少 5GB）

3. **不要操作电脑**
   - 让编译过程在后台安静进行
   - 可能需要 10-30 分钟

## 🐛 常见问题

### Q1: 提示 "No module named nuitka"

**解决方案**:
```bash
uv sync  # 重新同步依赖
```

### Q2: 编译过程中电脑卡死

**原因**: 并行任务数过高，资源占用过大

**解决方案**:
```bash
python build.py --jobs 1  # 降低并行度
```

### Q3: UPX 压缩失败

**检查 UPX 安装**:
```bash
# 检查 UPX 是否在 PATH 中
upx --version

# 如果不在 PATH，指定完整路径
python build.py --upx --upx-path "C:\path\to\upx.exe"
```

### Q4: 找不到 C 编译器

**Windows 解决方案**:

**🎯 方案 0: 什么都不做（推荐）**
- Nuitka 会在首次编译时自动下载 MinGW
- 无需任何手动操作
- 直接运行 `python build.py` 即可

首次编译时会看到类似提示：
```
ℹ️  未检测到系统已安装的 C 编译器
🎯 好消息：Nuitka 会在首次编译时自动下载 MinGW！

构建过程中会：
   1. 自动下载 MinGW-w64 编译器（约 100MB）
   2. 缓存到 Nuitka 数据目录，后续编译无需重复下载
   3. 自动配置编译环境

✅ 继续构建，Nuitka 将自动处理编译器下载...
```

**方案 1: 手动安装 MinGW（可选，频繁编译推荐）**
1. 下载 [WinLibs MinGW](https://winlibs.com/)
2. 下载 GCC 13+ 版本（UCRT runtime, posix threads）
3. 解压到 `C:\mingw64`
4. 添加环境变量:
   - 右键"此电脑" → "属性" → "高级系统设置"
   - "环境变量" → "系统变量" → "Path" → "编辑"
   - 新建: `C:\mingw64\bin`
5. 重启终端，验证: `gcc --version`

**方案 2: 安装 Visual Studio Build Tools**
1. 下载 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/)
2. 勾选 "Desktop development with C++"
3. 等待安装完成（约 6GB）
4. 重启终端

**指定 MinGW 路径**（如果安装在其他位置）:
```bash
python build.py --mingw64 "D:\Tools\mingw64"
```

**Linux 解决方案**:
```bash
sudo apt install build-essential
```

### Q5: 编译成功但程序无法运行

**检查项**:
1. 确保 `src/assets/` 目录存在且包含必要文件
2. 检查 `dist/release/MTools_x64/src/assets/` 是否正确复制
3. 使用 Dev 模式查看错误信息:
   ```bash
   python build.py --mode dev
   ```

### Q6: 编译时间过长

**正常情况**:
- Dev 模式: 5-15 分钟
- Release 模式: 10-30 分钟

**如果超过 1 小时**:
1. 检查磁盘空间是否充足
2. 检查是否卡在某个步骤（查看输出日志）
3. 尝试 `Ctrl+C` 中断，重新编译

### Q7: CUDA FULL 版本未包含 NVIDIA 库

**症状**：
- 编译完成但打包的程序中没有 `nvidia` 目录
- 运行时提示缺少 CUDA DLL 文件

**检查步骤**：
```bash
# 1. 验证环境变量是否正确设置
# Windows (PowerShell)
echo $env:CUDA_VARIANT  # 应显示 "cuda_full"

# Linux/macOS
echo $CUDA_VARIANT  # 应显示 "cuda_full"

# 2. 验证 onnxruntime-gpu 是否正确安装
uv run python test_cuda_libs.py

# 3. 检查是否安装了完整的 CUDA 和 cuDNN
uv pip list | findstr onnxruntime  # Windows
uv pip list | grep onnxruntime     # Linux/macOS
```

**解决方案**：
```bash
# 1. 确保完全移除旧版本
uv remove onnxruntime-directml
uv remove onnxruntime
uv remove onnxruntime-gpu

# 2. 安装带完整 CUDA 和 cuDNN 的版本（注意引号）
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"

# 3. 设置环境变量并重新编译
# Windows (Command Prompt)
set CUDA_VARIANT=cuda_full

# Windows (PowerShell)
$env:CUDA_VARIANT="cuda_full"
python build.py

# Linux/macOS
export CUDA_VARIANT=cuda_full
python build.py
```

**预期输出**（编译时）：
```
🎯 检测到 CUDA FULL 变体，正在包含 NVIDIA 库...
✅ 找到 NVIDIA 库: ...\site-packages\nvidia
📦 发现 7 个 NVIDIA 子包:
   • nvidia.cublas (3 DLLs)
   • nvidia.cuda_nvrtc (3 DLLs)
   • nvidia.cuda_runtime (1 DLLs)
   • nvidia.cudnn (8 DLLs)
   • nvidia.cufft (2 DLLs)
   • nvidia.curand (1 DLLs)
   • nvidia.nvjitlink (1 DLLs)
✅ 已包含 7 个包，共 21 个 DLL 文件
```

### Q8: CUDA 版本和 CUDA FULL 版本的区别

| 特性 | CUDA 版本 | CUDA FULL 版本 |
|------|----------|---------------|
| **安装依赖** | `onnxruntime-gpu==1.22.0` | `onnxruntime-gpu[cuda,cudnn]==1.22.0` |
| **打包体积** | ~200MB | ~700-800MB |
| **用户要求** | 需安装 CUDA Toolkit 12.x + cuDNN 9.x | ✅ 无需安装任何依赖 |
| **兼容性** | ⭐⭐ 依赖系统 CUDA | ⭐⭐⭐ 开箱即用 |
| **部署难度** | 🔴 高（需自行配置环境） | 🟢 低（一键运行） |
| **环境变量** | `CUDA_VARIANT=cuda` | `CUDA_VARIANT=cuda_full` |

### Q9: 如何验证 CUDA 加速是否生效

**方法 1: 使用测试脚本**
```bash
# 在打包的程序目录中运行
.\test_cuda_libs.py
```

**方法 2: 检查 onnxruntime providers**
```python
import onnxruntime as ort
print(ort.get_available_providers())

# 应包含:
# ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

**方法 3: 运行 AI 功能并观察性能**
- CUDA 加速: 处理速度明显更快
- CPU 模式: 处理速度较慢，CPU 占用高

### Q10: macOS 打包失败 - sherpa-onnx 库冲突

**症状**:
编译时出现错误：
```
FATAL: Error, failed to find path @rpath/libonnxruntime.1.17.1.dylib
(resolved DLL to ...site-packages/sherpa_onnx/lib/libonnxruntime.1.17.1.dylib)
for ...site-packages/sherpa_onnx/lib/_sherpa_onnx.cpython-311-darwin.so
```

**根本原因**:
- sherpa-onnx 包自带了旧版本的 ONNX Runtime 库（1.17.1）
- 与系统安装的新版本（1.22.0）冲突
- macOS 上的符号链接处理导致 Nuitka 无法正确解析库路径

**自动修复**（推荐）:
```bash
# 使用最新的 build.py，已自动处理清理
# 只需重新运行构建
python build.py
```

新版本 `build.py` 会在编译前自动清理冲突的库文件：
```
🔍 检查 sherpa-onnx 库文件冲突...
   目录: ...site-packages/sherpa_onnx/lib
   ✅ 已删除 sherpa-onnx 自带的 onnxruntime 库:
      • libonnxruntime.1.17.1.dylib
      • libonnxruntime.dylib
   💡 这些库与系统安装的 onnxruntime 冲突，已自动清理
```

**手动修复**（如果自动修复失败）:
```bash
# 找到 sherpa-onnx 库目录
python -c "import site; import sys; 
sp = site.getsitepackages()[0]; 
print(sp + '/sherpa_onnx/lib')"

# 手动删除冲突的库文件（macOS）
rm -f ~/.venv/lib/python3.11/site-packages/sherpa_onnx/lib/libonnxruntime*.dylib

# 或使用 find 命令查找
find ~/.venv/lib/python3.11/site-packages/sherpa_onnx/lib -name "libonnxruntime*.dylib" -type f

# 删除找到的文件
find ~/.venv/lib/python3.11/site-packages/sherpa_onnx/lib -name "libonnxruntime*.dylib" -type f -delete
```

**升级 sherpa-onnx**（根本解决）:
```bash
# 检查当前版本
uv pip list | grep sherpa-onnx

# 升级到最新版本
uv add sherpa-onnx --upgrade

# 然后重新编译
python build.py
```

**验证修复**:
```bash
# 检查库文件是否已清理
ls ~/.venv/lib/python3.11/site-packages/sherpa_onnx/lib/

# 应该不再包含 libonnxruntime* 文件
```

**预防措施**:
- 定期更新依赖包: `uv sync --upgrade`
- 使用 Python 3.11+ (推荐使用 3.11+)
- 在 macOS 上编译前，确保有足够的磁盘空间和内存

## 📚 进阶主题

### 自定义编译选项

如需更多自定义选项，可直接修改 `build.py` 中的 `get_nuitka_cmd()` 函数。

Nuitka 官方文档: https://nuitka.net/doc/user-manual.html

### 跨平台编译

当前 `build.py` 支持：
- ✅ Windows
- ✅ Linux
- ✅ macOS (需要 .icns 图标)

在对应平台上运行 `python build.py` 即可。

---

**最后更新**: 2025-12-05
