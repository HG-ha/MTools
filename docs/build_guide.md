# MTools 编译指南

本指南将帮助您使用 Nuitka 编译 MTools 项目，生成独立的可执行文件。

> 💡 **说明**：我们不使用 `flet build` 打包，等官方有更好的优化版本再接入。

## 🚀 快速开始

### 标准版本（推荐大多数用户）
```bash
# 1. 安装依赖
uv sync

# 2. 编译（Release 模式）
python build.py

# 或使用 Dev 模式（快速测试）
python build.py --mode dev
```

**适用场景**：
- ✅ 跨平台通用（Windows/macOS/Linux）
- ✅ 自适应 GPU 加速（NVIDIA/AMD/Intel/Apple Silicon）
- ✅ 无需安装 CUDA 环境
- ✅ 体积小（120-175MB），兼容性好

### CUDA FULL 版本（NVIDIA GPU 极致性能）
```bash
# 1. 安装依赖
uv sync

# 2. 替换为 CUDA FULL onnxruntime
uv remove onnxruntime-directml
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"

# 3. 设置环境变量并编译
# Windows (PowerShell)
$env:CUDA_VARIANT="cuda_full"
python build.py

# Linux/macOS
export CUDA_VARIANT=cuda_full
python build.py
```

**适用场景**：
- ✅ NVIDIA 显卡用户追求最佳 AI 性能
- ✅ 内置完整 CUDA 库，用户无需安装 CUDA Toolkit
- ⚠️ 体积较大（1.76-1.91GB）

> 📖 **更多选项**：详见 [编译选项](#-编译选项) 和 [CUDA 版本说明](#cuda-版本对比)

## 📋 前置要求

| 工具 | 必需 | Windows | Linux | macOS | 说明 |
|------|------|---------|-------|-------|------|
| **Python 3.11** | ✅ | ✅ | ✅ | ✅ | 运行 `python --version` 验证 |
| **uv 包管理器** | ✅ | ✅ | ✅ | ✅ | 推荐的依赖管理工具 |
| **C 编译器** | ✅ | 🤖 自动 | 手动 | 手动 | Windows 自动下载 MinGW |
| **UPX** | ❌ | 可选 | 可选 | 可选 | 压缩可执行文件（减小 30-50% 体积） |

### 安装步骤

**1. 安装 uv 包管理器**
```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip
pip install uv
```

**2. C 编译器安装**

- **Windows**：🎯 **无需操作**，Nuitka 首次编译时自动下载 MinGW（~100MB）
  
- **Linux**：
  ```bash
  sudo apt install build-essential
  ```

- **macOS**：
  ```bash
  xcode-select --install
  ```

> 💡 **Windows 用户**：如需手动安装编译器或遇到问题，请参考 [C 编译器详解](#️-c-编译器选择-windows)

**3. UPX（可选）**
- 下载：[GitHub Releases](https://github.com/upx/upx/releases)
- 解压后添加到系统 PATH，或使用 `--upx-path` 参数指定路径

## 📦 编译流程

### 1. 克隆项目
```bash
git clone https://github.com/HG-ha/MTools.git
cd MTools
```

### 2. 安装依赖
```bash
uv sync  # 自动安装所有依赖，包括 Nuitka
```

### 3. 执行编译
```bash
# Release 模式（推荐）
python build.py

# Dev 模式（快速测试）
python build.py --mode dev
```

> ⏱️ **首次编译时间**：
> - Windows: 15-35 分钟（含自动下载 MinGW 编译器和 Flet 客户端）
> - 后续编译: 10-30 分钟（Release）/ 5-15 分钟（Dev）

> 💡 **自动化功能**：
> - ✅ 自动检测并打包 Flet UI 客户端（~95MB）
> - ✅ Windows 自动下载 MinGW 编译器（首次）
> - ✅ 自动适配目标平台（Windows/Linux/macOS）

## ⚙️ 编译选项

### 基础命令
```bash
python build.py [选项]
```

查看所有参数：
```bash
python build.py --help
```

### 常用参数

| 参数 | 默认值 | 说明 | 示例 |
|------|--------|------|------|
| `--mode {release,dev}` | `release` | 编译模式 | `--mode dev` |
| `--upx` | 关闭 | 启用 UPX 压缩 | `--upx` |
| `--upx-path PATH` | - | 指定 UPX 路径 | `--upx-path "C:\upx\upx.exe"` |
| `--jobs N` | `2` | 并行任务数 | `--jobs 4` |
| `--mingw64 PATH` | - | 指定 MinGW 路径 (Windows) | `--mingw64 "D:\mingw64"` |

### 使用示例

```bash
# 完整优化 + UPX 压缩 + 4核并行
python build.py --mode release --upx --jobs 4

# 快速测试（单核，保留控制台）
python build.py --mode dev --jobs 1

# CUDA FULL 版本 + 完整优化
$env:CUDA_VARIANT="cuda_full"  # Windows PowerShell
python build.py --mode release --jobs 4

# 指定自定义 MinGW 路径
python build.py --mingw64 "C:\mingw-gcc14" --jobs 4
```

## 📊 配置对比

### 编译模式对比

| 特性 | Dev 模式 | Release 模式 |
|------|---------|-------------|
| **编译速度** | ⚡ 5-15分钟 | 🐢 10-30分钟 |
| **控制台窗口** | 👁️ 显示 | 🙈 隐藏 |
| **优化级别** | 低（保留调试） | 高（完整优化） |
| **文件体积** | 较大 | 较小 |
| **适用场景** | 开发测试 | 正式发布 |

### CUDA 版本对比

| 特性 | 标准版 | CUDA 版 | CUDA FULL 版 |
|------|--------|---------|--------------|
| **依赖包** | `onnxruntime-directml` (Win)<br>`onnxruntime` (Mac/Linux) | `onnxruntime-gpu` | `onnxruntime-gpu[cuda,cudnn]` |
| **打包体积** | 120-175MB | 301-404MB | 1.76-1.91GB |
| **GPU 支持** | DirectML/CoreML | CUDA (NVIDIA) | CUDA (NVIDIA) |
| **用户依赖** | ✅ 无 | ⚠️ 需 CUDA Toolkit | ✅ 无（内置完整） |
| **部署难度** | 🟢 简单 | 🔴 困难 | 🟢 简单 |
| **AI 性能** | ⭐⭐ 中等 | ⭐⭐⭐ 最佳 | ⭐⭐⭐ 最佳 |
| **兼容性** | ⭐⭐⭐ 最广 | ⭐⭐ 需配置 | ⭐⭐⭐ 开箱即用 |
| **环境变量** | - | `CUDA_VARIANT=cuda` | `CUDA_VARIANT=cuda_full` |
| **推荐场景** | 通用部署 | 已配置 CUDA 环境 | NVIDIA GPU 极致性能 |

**CUDA 版本编译命令**：

```bash
# 标准版（DirectML/CoreML）
python build.py
# → Windows: 120MB | Linux: 149MB | macOS: 143-175MB

# CUDA 版本（需外部 CUDA Toolkit）
uv remove onnxruntime-directml
uv add onnxruntime-gpu==1.22.0
$env:CUDA_VARIANT="cuda"  # Windows PowerShell
python build.py
# → Windows: 301MB | Linux: 404MB

# CUDA FULL 版本（内置完整 CUDA）
uv remove onnxruntime-directml
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"
$env:CUDA_VARIANT="cuda_full"  # Windows PowerShell
python build.py
# → Windows: 1.76GB | Linux: 1.91GB
```

**CUDA FULL 构建输出示例**：
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

**实际文件大小对比**（基于 v0.0.2-beta）：

| 平台 | 标准版 | CUDA 版 | CUDA FULL 版 |
|------|--------|---------|--------------|
| **Windows** | 120 MB | 301 MB | 1.76 GB |
| **Linux** | 149 MB | 404 MB | 1.91 GB |
| **macOS (Intel)** | 175 MB | - | - |
| **macOS (Apple Silicon)** | 143 MB | - | - |

> 💡 **体积说明**：
> - 标准版最小，适合普通用户
> - CUDA 版需外部 CUDA 环境，体积中等
> - CUDA FULL 版包含完整 NVIDIA 库，体积最大但部署最简单

### 🛠️ C 编译器选择 (Windows)

| 特性 | Nuitka 自动下载 (推荐) | 手动 MinGW | MSVC |
|------|---------------------|------------|------|
| **安装大小** | ~100MB | ~100MB | ~6GB |
| **安装方式** | 🚀 完全自动 | ✅ 解压即用 | ⚙️ 需安装器 |
| **配置复杂度** | ✨ 零配置 | 需配置 PATH | 需安装器 |
| **编译速度** | 正常 | ⚡ 快 | 🐢 较慢 |
| **推荐场景** | 快速开始 | 频繁编译 | 企业级开发 |

**选择逻辑**：
1. ✅ 优先使用系统已安装的 MinGW
2. ✅ 其次使用 MSVC（如已安装 Visual Studio）
3. ✅ 最后由 Nuitka 自动下载 MinGW

**手动安装 MinGW**（可选）：
- 下载：[WinLibs MinGW](https://winlibs.com/) (GCC 13+ UCRT)
- 解压到 `C:\mingw64`
- 添加 `C:\mingw64\bin` 到 PATH
- 或使用 `--mingw64` 参数指定路径

## 🗂️ 输出结构

编译完成后的文件结构：

```
dist/release/
├── MTools_x64/                      # 可执行程序目录
│   ├── MTools.exe                   # 主程序
│   ├── src/assets/                  # 资源文件（图标等）
│   ├── *.dll                        # 依赖库
│   └── nvidia/                      # NVIDIA 库（仅 CUDA FULL 版本）
└── MTools_Windows_AMD64.zip         # 自动打包的压缩包
```

## 💡 性能优化技巧

### 🎯 减小体积
```bash
# 启用 UPX 压缩（减小 30-50%）
python build.py --upx

# 移除不必要的依赖包
uv remove <package-name>
```

### ⚡ 加快编译
```bash
# 使用 Dev 模式快速验证
python build.py --mode dev --jobs 4

# 增加并行任务（根据 CPU 核心数调整）
python build.py --jobs 4
```

### 🛡️ 避免卡顿
- 降低并行度：`--jobs 1`
- 确保磁盘空间充足（至少 5GB）
- 编译时关闭其他大型程序

## 🐛 常见问题

### Q1: 提示 "No module named nuitka"
```bash
uv sync  # 重新同步依赖
```

### Q2: 编译过程中电脑卡顿/卡死
**原因**：并行任务数过高，资源占用过大

**解决方案**：
```bash
python build.py --jobs 1  # 降低并行度
```

### Q3: 编译成功但程序无法运行
**检查步骤**：
1. 确保 `src/assets/` 目录完整
2. 检查 `dist/release/MTools_x64/src/assets/` 是否正确复制
3. 使用 Dev 模式查看详细错误：
   ```bash
   python build.py --mode dev
   ```

### Q4: 编译时间异常（超过 1 小时）
**正常时间**：Dev 5-15分钟，Release 10-30分钟

**解决方案**：
1. 检查磁盘空间（至少 5GB）
2. 查看日志确认卡在哪个步骤
3. `Ctrl+C` 中断后重新编译

### Q5: CUDA FULL 版本未包含 NVIDIA 库
**症状**：编译完成但缺少 `nvidia` 目录或运行时提示缺少 CUDA DLL

**解决方案**：
```bash
# 1. 完全移除旧版本
uv remove onnxruntime-directml onnxruntime onnxruntime-gpu

# 2. 安装完整版本（注意引号）
uv add "onnxruntime-gpu[cuda,cudnn]==1.22.0"

# 3. 验证环境变量
echo $env:CUDA_VARIANT  # Windows PowerShell，应显示 "cuda_full"
echo $CUDA_VARIANT      # Linux/macOS

# 4. 重新编译
$env:CUDA_VARIANT="cuda_full"  # Windows PowerShell
python build.py
```

**预期输出**（编译时应看到）：
```
🎯 检测到 CUDA FULL 变体，正在包含 NVIDIA 库...
📦 发现 7 个 NVIDIA 子包 (共 21 个 DLL)
```

### Q6: 验证 CUDA 加速是否生效
```python
# 方法 1: 检查 onnxruntime providers
import onnxruntime as ort
print(ort.get_available_providers())
# 应包含: ['CUDAExecutionProvider', 'CPUExecutionProvider']

# 方法 2: 观察性能
# CUDA 加速：处理速度快，GPU 占用高
# CPU 模式：处理速度慢，CPU 占用高
```

### Q7: macOS 编译失败 - sherpa-onnx 库冲突
**症状**：
```
FATAL: Error, failed to find path @rpath/libonnxruntime.1.17.1.dylib
```

**原因**：sherpa-onnx 自带旧版 ONNX Runtime (1.17.1) 与新版 (1.22.0) 冲突

**自动修复**（推荐）：
最新的 `build.py` 已自动处理，直接重新编译即可：
```bash
python build.py
```

**手动修复**（如果自动修复失败）：
```bash
# 1. 清理冲突库文件
rm -f $(python -c "import site; print(site.getsitepackages()[0])")/sherpa_onnx/lib/libonnxruntime*.dylib

# 2. 重新编译
python build.py

# 3. 如仍失败，升级 sherpa-onnx
uv add sherpa-onnx --upgrade
```

### Q8: UPX 压缩失败
```bash
# 检查 UPX 是否安装
upx --version

# 指定 UPX 完整路径
python build.py --upx --upx-path "C:\path\to\upx.exe"
```

### Q9: Windows 找不到 C 编译器
**推荐方案**：什么都不做，Nuitka 会自动下载 MinGW

首次编译会看到：
```
ℹ️  未检测到系统已安装的 C 编译器
🎯 好消息：Nuitka 会在首次编译时自动下载 MinGW！
✅ 继续构建，Nuitka 将自动处理编译器下载...
```

**手动安装**（可选，频繁编译推荐）：
1. 下载 [WinLibs MinGW](https://winlibs.com/) (GCC 13+ UCRT)
2. 解压到 `C:\mingw64`
3. 添加 `C:\mingw64\bin` 到系统 PATH
4. 验证：`gcc --version`

或使用 `--mingw64` 参数：
```bash
python build.py --mingw64 "D:\Tools\mingw64"
```

## 📚 进阶主题

### Flet 客户端自动打包

MTools 采用**预打包策略**，构建时自动处理 Flet UI 客户端（~95MB）：

**工作流程**：
1. 构建时自动检测 Flet 客户端版本
2. 如未打包或版本不匹配，自动从虚拟环境打包
3. Nuitka 将 `.flet` 目录打包到可执行文件
4. 首次运行时自动解压到用户目录（5-10秒）
5. 后续启动秒开，无需重复解压

**优势**：
- 📦 离线可用，无需下载
- 🚀 解压比下载快 5-10 倍
- 🤖 全自动化，无需手动操作
- 🔄 版本自动同步

### 自定义编译选项

如需深度定制，可修改 `build.py` 中的 `get_nuitka_cmd()` 函数。

**参考资源**：
- [Nuitka 官方文档](https://nuitka.net/doc/user-manual.html)
- [Flet 打包指南](https://flet.dev/docs/publish/)

### 跨平台支持

当前 `build.py` 支持：
- ✅ Windows (x64)
- ✅ Linux (x64)
- ✅ macOS (x64/ARM64)

在对应平台上运行 `python build.py` 即可自动适配。

---

**文档版本**: v2.0  
**最后更新**: 2025-12-08
