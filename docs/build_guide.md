# MTools 编译指南

本指南将帮助您使用 Nuitka 编译 MTools 项目，生成独立的可执行文件，我们不使用 **flet build** 打包，等官方有更好的优化版本再接入。

## 📌 须知

### Flet 0.28.3 自动下载机制
当前 flet 版本在首次启动时会检测用户目录下是否存在 `.flet` 目录，如果不存在则自动从 GitHub 下载（所有平台：Windows、macOS、Linux）。

**优化方案：**
- ✅ **中国用户自动加速**：检测到中国用户后，自动使用 `ghproxy.cn` 镜像加速下载
- ✅ **首次启动优化**：首次运行时自动下载并缓存到用户目录
- ✅ **后续秒开**：下载后的启动速度恢复正常
- ✅ **跨平台支持**：Windows、macOS、Linux 统一处理

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

### 2. 基础编译

> ⏱️ **首次编译提示**：Windows 用户首次编译时，Nuitka 会自动下载编译器，整个过程可能需要额外 5-10 分钟。后续编译无需重复下载。

**Release 模式（生产环境）**
```bash
python build.py
```
- ✅ 完整优化
- ✅ 无控制台窗口
- ✅ 体积较小，性能最佳
- ⏱️ 编译时间较长 (10-30分钟)

**Dev 模式（开发测试）**
```bash
python build.py --mode dev
```
- ✅ 快速编译
- ✅ 保留控制台窗口（可查看日志）
- ✅ 保留调试信息
- ⏱️ 编译时间较短 (5-15分钟)

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
```

## 📊 构建模式对比

| 特性 | Dev 模式 | Release 模式 |
|------|---------|-------------|
| **编译速度** | 快 ⚡ (5-15分钟) | 慢 🐢 (10-30分钟) |
| **控制台窗口** | 显示 👁️ | 隐藏 🙈 |
| **优化级别** | 低 (保留调试) | 高 (完整优化) |
| **文件体积** | 较大 | 较小 |
| **启动速度** | 较慢 | 较快 |
| **适用场景** | 开发测试 | 正式发布 |
| **Python 标志** | `no_site` | `-O`, `no_site`, `no_warnings` |

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

**最后更新**: 2025-12-02
