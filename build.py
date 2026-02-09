#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTools 跨平台构建脚本
使用 Nuitka 将 Python 项目打包为可执行文件。
"""

import os
import sys

# 设置 stdout/stderr 编码为 UTF-8（解决 Windows CI 环境的编码问题）
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import shutil
import platform
import subprocess
from pathlib import Path
import zipfile
import importlib.util
import argparse
import signal
import atexit

# 路径配置
PROJECT_ROOT = Path(__file__).parent.absolute()
ASSETS_DIR = PROJECT_ROOT / "src" / "assets"
APP_CONFIG_FILE = PROJECT_ROOT / "src" / "constants" / "app_config.py"

def write_cuda_variant_to_config():
    """将 CUDA 变体信息写入 app_config.py
    
    在构建时读取 CUDA_VARIANT 环境变量，并将其写入到
    app_config.py 的 BUILD_CUDA_VARIANT 常量中，使得编译后的
    程序能够知道自己的 CUDA 变体类型。
    """
    cuda_variant = os.environ.get('CUDA_VARIANT', 'none').lower()
    
    # 验证值是否合法
    if cuda_variant not in ('none', 'cuda', 'cuda_full'):
        print(f"   ⚠️  无效的 CUDA_VARIANT 值: {cuda_variant}，使用默认值 'none'")
        cuda_variant = 'none'
    
    print(f"   📝 写入 CUDA 变体信息: {cuda_variant}")
    
    try:
        # 读取配置文件
        with open(APP_CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换 BUILD_CUDA_VARIANT 的值
        import re
        pattern = r'BUILD_CUDA_VARIANT:\s*Final\[str\]\s*=\s*"[^"]*"'
        replacement = f'BUILD_CUDA_VARIANT: Final[str] = "{cuda_variant}"'
        
        new_content = re.sub(pattern, replacement, content)
        
        # 写回文件
        with open(APP_CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   ✅ 已将 BUILD_CUDA_VARIANT 设置为: {cuda_variant}")
        
    except Exception as e:
        print(f"   ⚠️  写入 CUDA 变体信息失败: {e}")
        print(f"   ⚠️  将继续构建，但程序可能无法正确检测 CUDA 变体")

def get_dist_dir(mode="release"):
    """根据构建模式获取输出目录
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
        
    Returns:
        Path: 输出目录路径
    """
    return PROJECT_ROOT / "dist" / mode


def get_platform_name():
    """获取平台相关的输出名称（统一目录和 zip 命名）
    
    支持通过环境变量 CUDA_VARIANT 指定 CUDA 版本后缀：
    - 无环境变量或 'none': 标准版本，无后缀
    - 'cuda': CUDA 版本，添加 '_CUDA' 后缀
    - 'cuda_full': CUDA Full 版本，添加 '_CUDA_FULL' 后缀
    
    Returns:
        str: 平台名称，例如 "Windows_amd64", "Windows_amd64_CUDA", "Linux_amd64_CUDA_FULL"
    """
    system = platform.system()
    machine = platform.machine().upper()
    
    # 统一机器架构名称
    arch_map = {
        'X86_64': 'amd64',  # Linux/macOS 常用
        'AMD64': 'amd64',   # Windows 常用
        'ARM64': 'arm64',   # Apple Silicon
        'AARCH64': 'arm64', # Linux ARM64
        'I386': 'x86',
        'I686': 'x86',
    }
    
    arch = arch_map.get(machine, machine)
    base_name = f"{system}_{arch}"
    
    # 检查 CUDA 变体环境变量
    cuda_variant = os.environ.get('CUDA_VARIANT', 'none').lower()
    if cuda_variant == 'cuda':
        return f"{base_name}_CUDA"
    elif cuda_variant == 'cuda_full':
        return f"{base_name}_CUDA_FULL"
    else:
        return base_name

# 全局状态标记
_build_interrupted = False
_cleanup_handlers = []

def signal_handler(signum, frame):
    """处理中断信号（Ctrl+C）"""
    global _build_interrupted
    if _build_interrupted:
        # 如果已经中断过一次，强制退出
        print("\n\n❌ 强制退出")
        sys.exit(1)
    
    _build_interrupted = True
    print("\n\n⚠️  检测到中断信号，正在清理...")
    print("   (再次按 Ctrl+C 强制退出)")
    
    # 执行清理
    cleanup_on_exit()
    
    print("\n✅ 清理完成，已退出构建")
    sys.exit(130)  # 标准的 SIGINT 退出码

def register_cleanup_handler(handler):
    """注册清理处理函数
    
    Args:
        handler: 清理函数，无参数
    """
    if handler not in _cleanup_handlers:
        _cleanup_handlers.append(handler)

def cleanup_on_exit():
    """执行所有清理处理器"""
    for handler in _cleanup_handlers:
        try:
            handler()
        except Exception as e:
            print(f"   清理时出错: {e}")

def get_app_config():
    """从配置文件中导入应用信息"""
    config = {
        "APP_TITLE": "MTools",
        "APP_VERSION": "0.1.0",
        "APP_DESCRIPTION": "MTools Desktop App"
    }
    
    if not APP_CONFIG_FILE.exists():
        print(f"⚠️  警告: 未找到配置文件 {APP_CONFIG_FILE}")
        return config
        
    try:
        # 动态导入模块，无需将 src 加入 sys.path
        spec = importlib.util.spec_from_file_location("app_config", APP_CONFIG_FILE)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 获取常量
            if hasattr(module, "APP_TITLE"):
                full_title = module.APP_TITLE
                config["APP_TITLE"] = full_title.split(" - ")[0] if " - " in full_title else full_title
            
            if hasattr(module, "APP_VERSION"):
                config["APP_VERSION"] = module.APP_VERSION
                
            if hasattr(module, "APP_DESCRIPTION"):
                config["APP_DESCRIPTION"] = module.APP_DESCRIPTION
                
    except Exception as e:
        print(f"⚠️  导入配置文件失败: {e}")
        
    return config

# 加载配置
APP_CONFIG = get_app_config()

# 项目配置
APP_NAME = APP_CONFIG["APP_TITLE"]
MAIN_SCRIPT = "src/main.py"
VERSION = APP_CONFIG["APP_VERSION"]
COMPANY_NAME = "HG-ha"
COPYRIGHT = f"Copyright (C) 2025 by {COMPANY_NAME}"
DESCRIPTION = APP_CONFIG["APP_DESCRIPTION"]

def get_variant_suffix():
    """获取变体后缀（用于版本信息显示）
    
    Returns:
        str: 变体后缀，例如 " (CUDA)", " (CUDA FULL)", 或空字符串（标准版）
    """
    cuda_variant = os.environ.get('CUDA_VARIANT', 'none').lower()
    if cuda_variant == 'cuda':
        return " (CUDA)"
    elif cuda_variant == 'cuda_full':
        return " (CUDA FULL)"
    else:
        return ""  # 标准版不添加后缀


def get_file_version(version: str) -> str:
    """将版本号转换为 Windows 文件版本格式（4 段纯数字）。
    
    Args:
        version: 版本号，如 "0.0.1-beta", "1.2.3"
    
    Returns:
        4 段数字格式，如 "0.0.1.0", "1.2.3.0"
    """
    import re
    # 移除预发布标签（如 -beta, -alpha, -rc1 等）
    clean_version = re.split(r'[-+]', version)[0]
    
    # 分割版本号
    parts = clean_version.split('.')
    
    # 确保有 4 段数字
    while len(parts) < 4:
        parts.append('0')
    
    # 只取前 4 段，确保都是数字
    return '.'.join(parts[:4])

def clean_dist(mode="release"):
    """清理构建目录
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
    """
    dist_dir = get_dist_dir(mode)
    print(f"🧹 清理旧的构建文件 ({mode} 模式)...")
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
            print(f"   已删除: {dist_dir}")
        except Exception as e:
            print(f"   ❌ 清理失败: {e}")

def cleanup_incomplete_build(mode="release"):
    """清理未完成的构建文件
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
    """
    dist_dir = get_dist_dir(mode)
    try:
        # 清理 .dist 临时目录
        if dist_dir.exists():
            for item in dist_dir.glob("*.dist"):
                if item.is_dir():
                    print(f"   清理临时目录: {item.name}")
                    shutil.rmtree(item)
            
            # 清理 .build 临时目录
            for item in dist_dir.glob("*.build"):
                if item.is_dir():
                    print(f"   清理临时目录: {item.name}")
                    shutil.rmtree(item)
    except Exception as e:
        print(f"   清理临时文件时出错: {e}")


def cleanup_build_cache():
    """清理构建缓存目录（dist/.build_cache）
    
    这个目录包含 flet_client 等缓存文件，可在多次构建之间复用。
    如果需要节省磁盘空间，可以在构建完成后清理。
    """
    cache_dir = PROJECT_ROOT / "dist" / ".build_cache"
    if cache_dir.exists():
        try:
            print("🧹 清理构建缓存目录...")
            shutil.rmtree(cache_dir)
            print(f"   已删除: {cache_dir}")
        except Exception as e:
            print(f"   ❌ 清理缓存失败: {e}")

def check_upx(upx_path=None):
    """检查 UPX 是否可用
    
    Args:
        upx_path: 自定义 UPX 路径（可选）
        
    Returns:
        tuple: (是否可用, UPX路径或None)
    """
    # 如果指定了路径，优先使用
    if upx_path:
        upx_exe = Path(upx_path)
        if upx_exe.exists() and upx_exe.is_file():
            try:
                result = subprocess.run([str(upx_exe), "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"✅ 找到 UPX: {upx_exe}")
                    return True, str(upx_exe)
            except Exception as e:
                print(f"⚠️  指定的 UPX 路径无效: {e}")
        else:
            print(f"⚠️  指定的 UPX 路径不存在: {upx_path}")
    
    # 检查环境变量 PATH
    try:
        result = subprocess.run(["upx", "--version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ 在系统 PATH 中找到 UPX")
            return True, "upx"
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  检查 UPX 时出错: {e}")
    
    print("⚠️  未找到 UPX 工具")
    print("   提示: 下载 UPX https://github.com/upx/upx/releases")
    return False, None

def check_onnxruntime_version():
    """检查 onnxruntime 版本并给出建议
    
    支持的版本（所有平台都接受以下任一版本）：
    - onnxruntime==1.22.0 (Windows/macOS/Linux CPU，macOS Apple Silicon 内置 CoreML 加速)
    - onnxruntime-gpu==1.22.0 (Linux/Windows NVIDIA CUDA加速)
    - onnxruntime-directml==1.22.0 (Windows DirectML加速，推荐)
    
    注意：仅显示提示信息，不会阻断构建过程
    
    Returns:
        bool: 始终返回 True，不阻断构建
    """
    system = platform.system()
    machine = platform.machine().lower()
    
    try:
        # 检查已安装的 onnxruntime 包
        # 优先使用 uv pip list，如果失败则回退到 python -m pip list
        result = None
        
        # 尝试使用 uv pip list
        try:
            result = subprocess.run(
                ["uv", "pip", "list"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=PROJECT_ROOT
            )
        except FileNotFoundError:
            # uv 命令不存在，使用传统 pip
            pass
        
        # 如果 uv 失败或不存在，使用 python -m pip list
        if not result or result.returncode != 0:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode != 0:
            print("⚠️  无法检查已安装的包，跳过 onnxruntime 版本检查")
            return True
        
        installed_packages = result.stdout.lower()
        
        # 检测安装的 onnxruntime 变体
        installed_variant = None
        installed_version = None
        
        for line in installed_packages.split('\n'):
            if 'onnxruntime' in line:
                parts = line.split()
                if len(parts) >= 2:
                    installed_variant = parts[0]
                    installed_version = parts[1]
                    break
        
        if not installed_variant:
            print("⚠️  未检测到 onnxruntime，某些 AI 功能可能无法使用")
            print("   提示：安装 onnxruntime 以启用 AI 功能（背景移除、图像增强等）")
            return True
        
        # 显示当前安装的版本
        print(f"📦 ONNX Runtime: {installed_variant} {installed_version}")
        
        # 检查版本号
        if installed_version != "1.22.0":
            print(f"   ⚠️  推荐版本: 1.22.0（当前: {installed_version}）")
            print("   ⚠️  使用非推荐版本可能导致兼容性问题")
        
        # 根据平台给出建议
        is_apple_silicon = "arm" in machine or "aarch64" in machine
        
        if system == "Windows":
            if installed_variant == "onnxruntime-directml":
                print("   ✅ 使用 DirectML 加速版本（推荐，支持 Intel/AMD/NVIDIA GPU）")
            elif installed_variant == "onnxruntime-gpu":
                print("   ✅ 使用 CUDA 加速版本（需要 NVIDIA GPU 和 CUDA Toolkit）")
                print("   💡 提示：Windows 推荐使用 onnxruntime-directml（兼容性更好）")
            elif installed_variant == "onnxruntime":
                print("   ℹ️  使用 CPU 版本")
                print("   💡 推荐：uv add onnxruntime-directml==1.22.0（启用 GPU 加速）")
            else:
                print(f"   ⚠️  {installed_variant} 在 Windows 上可能不受支持")
                print("   💡 推荐：uv add onnxruntime-directml==1.22.0")
        
        elif system == "Darwin":
            if installed_variant == "onnxruntime":
                if is_apple_silicon:
                    print("   ✅ 使用标准版本（已内置 CoreML 加速，推荐）")
                else:
                    print("   ℹ️  使用 CPU 版本（Intel Mac）")
            elif installed_variant == "onnxruntime-silicon":
                print("   ⚠️  onnxruntime-silicon 已被弃用")
                print("   💡 推荐：uv remove onnxruntime-silicon && uv add onnxruntime==1.22.0")
                print("   ℹ️  说明：新版 onnxruntime 已内置 CoreML 支持，无需单独安装 silicon 版本")
            elif installed_variant == "onnxruntime-gpu":
                print("   ⚠️  macOS 不支持 CUDA")
                print("   💡 推荐：uv remove onnxruntime-gpu && uv add onnxruntime==1.22.0")
            elif installed_variant == "onnxruntime-directml":
                print("   ⚠️  macOS 不支持 DirectML")
                print("   💡 推荐：uv remove onnxruntime-directml && uv add onnxruntime==1.22.0")
        
        elif system == "Linux":
            if installed_variant == "onnxruntime-gpu":
                print("   ✅ 使用 CUDA 加速版本（需要 NVIDIA GPU、CUDA Toolkit 和 cuDNN）")
            elif installed_variant == "onnxruntime":
                print("   ℹ️  使用 CPU 版本")
                print("   💡 提示：如有 NVIDIA GPU，可使用 onnxruntime-gpu==1.22.0（需配置 CUDA）")
            elif installed_variant == "onnxruntime-directml":
                print("   ⚠️  Linux 不支持 DirectML")
                print("   💡 推荐：uv remove onnxruntime-directml && uv add onnxruntime==1.22.0")
            elif installed_variant == "onnxruntime-silicon":
                print("   ⚠️  onnxruntime-silicon 已被弃用且不支持 Linux")
                print("   💡 推荐：uv remove onnxruntime-silicon && uv add onnxruntime==1.22.0")
        
        return True
        
    except Exception as e:
        print(f"⚠️  检查 onnxruntime 版本时出错: {e}")
        return True

def prepare_flet_client(enable_upx_compression=False, upx_path=None, output_base_dir=None):
    """准备 Flet 客户端目录（动态生成到构建输出目录）
    
    新策略：不再放在源码目录，而是构建时动态准备到 dist/.build_cache/flet_client/，
    然后通过 Nuitka 的 --include-data-dir 参数包含到最终程序中。
    
    优点：
    - 不污染源码目录
    - 支持多版本并存（不同 flet 版本）
    - 构建缓存可重用
    
    Args:
        enable_upx_compression: 是否对 flet 客户端的 exe/dll 进行 UPX 压缩
        upx_path: UPX 可执行文件路径（可选）
        output_base_dir: 输出基础目录，默认为 PROJECT_ROOT/dist/.build_cache
    
    Returns:
        Path: flet_client 目录路径，失败返回 None
    """
    system = platform.system()
    
    # 默认输出到 dist/.build_cache/flet_client/
    if output_base_dir is None:
        output_base_dir = PROJECT_ROOT / "dist" / ".build_cache"
    
    # 获取 flet 版本
    try:
        import flet.version
        flet_version = flet.version.flet_version
    except ImportError:
        print("❌ 错误: 未找到 flet 模块")
        return None
    
    # 目标目录：dist/.build_cache/flet_client-{version}/
    flet_client_output = output_base_dir / f"flet_client-{flet_version}"
    
    print("\n" + "="*60)
    print(f"📦 准备 Flet 客户端 ({system})")
    print("="*60)
    
    # 查找 flet_desktop 包的位置
    try:
        import flet_desktop
        flet_desktop_path = Path(flet_desktop.__file__).parent
        
        # Windows 的客户端在 app/flet/ 目录下
        # macOS 和 Linux 也在 app/ 下，但可能是 .app 或其他格式
        if system == "Windows":
            flet_client_dir = flet_desktop_path / "app" / "flet"
        else:
            # macOS 和 Linux: 检查 app/ 目录
            flet_client_dir = flet_desktop_path / "app"
        
        if not flet_client_dir.exists():
            print("❌ 错误: 未找到 Flet 客户端目录")
            print(f"   预期位置: {flet_client_dir}")
            print("\n请先安装依赖：")
            print("   uv sync")
            return None
        
        # 检查客户端目录是否有内容
        if not any(flet_client_dir.iterdir()):
            print("❌ 错误: Flet 客户端目录为空")
            return None
        
        print(f"源目录: {flet_client_dir}")
        print(f"目标目录: {flet_client_output}")
        print(f"版本: {flet_version}")
        print("="*60)
        
    except ImportError:
        print("❌ 错误: 未找到 flet_desktop 模块")
        print("\n请先安装依赖：")
        print("   uv sync")
        return None
    
    # 如果目标目录已存在且完整，直接返回
    if flet_client_output.exists():
        # 检查是否完整（至少有 flet.exe 或主要文件）
        if system == "Windows":
            flet_exe = flet_client_output / "flet" / "flet.exe"
            if flet_exe.exists():
                file_count = len(list(flet_client_output.rglob('*')))
                total_size = sum(f.stat().st_size for f in flet_client_output.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                print(f"✅ 找到缓存: {flet_client_output.name} ({size_mb:.2f} MB)")
                return flet_client_output
        
        # 目录存在但不完整，删除重建
        print(f"   清理不完整的缓存...")
        shutil.rmtree(flet_client_output)
    
    # 确保输出目录存在
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 创建输出目录
        flet_client_output.mkdir(parents=True, exist_ok=True)
        
        # 复制 Flet 客户端文件
        print(f"⏳ 正在复制 Flet 客户端...")
        
        if system == "Windows":
            # Windows: 复制 flet/ 目录下的所有文件
            target_dir = flet_client_output / "flet"
            shutil.copytree(flet_client_dir, target_dir, dirs_exist_ok=True)
        else:
            # macOS/Linux: 复制整个 app/ 目录
            shutil.copytree(flet_client_dir, flet_client_output, dirs_exist_ok=True)
        
        # 统计文件数量和大小
        all_files = list(flet_client_output.rglob('*'))
        file_count = len([f for f in all_files if f.is_file()])
        total_size = sum(f.stat().st_size for f in all_files if f.is_file())
        size_mb = total_size / (1024 * 1024)
        
        # UPX 压缩（如果启用）
        compressed_count = 0
        if enable_upx_compression:
            upx_available, upx_cmd = check_upx(upx_path)
            if upx_available:
                print("\n🗜️  正在对 Flet 客户端进行 UPX 压缩...")
                print("   ⚠️  注意: 跳过 Flutter 核心引擎文件")
                
                # 跳过 Flutter 核心引擎和 OpenGL 相关文件（这些文件压缩后可能无法运行）
                skip_files = {
                    "flet.exe",              # Flet 主程序
                    "flutter_windows.dll",   # Flutter 引擎
                    "libEGL.dll",            # OpenGL ES 库
                    "libGLESv2.dll",         # OpenGL ES 2.0 库
                    "app.so",                # Flutter 应用主体（不能压缩）
                }
                
                compressed_files = []
                skipped_files = []
                
                for file in all_files:
                    if file.is_file() and file.suffix.lower() in ['.dll', '.exe', '.so']:
                        if file.name in skip_files:
                            skipped_files.append(file.name)
                            continue
                        
                        try:
                            # 获取压缩前大小
                            before_size = file.stat().st_size
                            
                            result = subprocess.run(
                                [upx_cmd, "--best", "--lzma", str(file)],
                                capture_output=True,
                                timeout=60,
                                check=False
                            )
                            
                            # 获取压缩后大小
                            after_size = file.stat().st_size
                            saved = before_size - after_size
                            
                            if result.returncode == 0:
                                compressed_files.append((file.name, before_size, after_size, saved))
                                compressed_count += 1
                            else:
                                # UPX 失败（可能文件已压缩或不兼容）
                                pass
                        except subprocess.TimeoutExpired:
                            print(f"   ⚠️  {file.name}: 压缩超时，跳过")
                        except Exception as e:
                            print(f"   ⚠️  {file.name}: {e}")
                
                # 重新计算总大小
                compressed_size = sum(f.stat().st_size for f in all_files if f.is_file())
                compressed_size_mb = compressed_size / (1024 * 1024)
                saved_mb = size_mb - compressed_size_mb
                
                print(f"\n   ✅ 已压缩 {compressed_count} 个文件")
                if compressed_files:
                    print(f"   📊 压缩详情（前 10 个）:")
                    for name, before, after, saved in sorted(compressed_files, key=lambda x: x[3], reverse=True)[:10]:
                        ratio = (1 - after/before) * 100 if before > 0 else 0
                        print(f"      • {name}: {before/1024/1024:.2f}MB → {after/1024/1024:.2f}MB (-{ratio:.1f}%)")
                
                if skipped_files:
                    print(f"   ⏭️  跳过 {len(skipped_files)} 个核心文件: {', '.join(skipped_files[:5])}")
                
                print(f"   💾 总节省: {saved_mb:.2f} MB ({saved_mb/size_mb*100:.1f}%)")
                size_mb = compressed_size_mb
        
        print("="*60)
        print("✅ Flet 客户端准备完成！")
        print("="*60)
        print(f"缓存目录: {flet_client_output}")
        print(f"文件数: {file_count}")
        print(f"大小: {size_mb:.2f} MB")
        if compressed_count > 0:
            print(f"UPX 压缩: {compressed_count} 个文件")
        print("="*60 + "\n")
        
        return flet_client_output
        
    except Exception as e:
        print(f"\n❌ 准备失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_and_prepare_flet_client(enable_upx=False, upx_path=None):
    """检查并自动准备 Flet 客户端目录（到构建缓存）
    
    新策略：动态生成到 dist/.build_cache/flet_client-{version}/，
    避免污染源码目录。
    
    Args:
        enable_upx: 是否对 flet 客户端进行 UPX 压缩
        upx_path: UPX 可执行文件路径（可选）
    
    Returns:
        Path: flet_client 目录路径，失败返回 None
    """
    print("\n🔍 检查 Flet 客户端...")
    
    # 调用 prepare_flet_client，它会自动检查缓存
    flet_client_path = prepare_flet_client(
        enable_upx_compression=enable_upx,
        upx_path=upx_path
    )
    
    if not flet_client_path:
        print("\n❌ Flet 客户端准备失败")
        return None
    
    return flet_client_path


def check_dependencies():
    """检查并同步依赖"""
    print("🔍 检查依赖环境...")
    
    # 检查 pyproject.toml 是否存在
    if not (PROJECT_ROOT / "pyproject.toml").exists():
        print("⚠️  未找到 pyproject.toml，跳过依赖检查")
        return True

    try:
        # 尝试使用 uv sync 同步依赖（包含 dev 依赖以获取 flet_desktop 和 nuitka）
        # 这会确保环境与 uv.lock/pyproject.toml 一致
        print("   执行 uv sync --all-groups...")
        subprocess.check_call(["uv", "sync", "--all-groups"], cwd=PROJECT_ROOT)
        print("✅ 依赖已同步")
    except FileNotFoundError:
        print("⚠️  未找到 uv 命令，请确保已安装 uv (https://github.com/astral-sh/uv)")
        print("   将尝试使用当前 Python 环境继续构建...")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  依赖同步失败: {e}")
        print("   尝试继续构建...")
    
    # 检查 onnxruntime 版本
    print("\n🔍 检查 ONNX Runtime 版本...")
    if not check_onnxruntime_version():
        return False
    
    # Linux 上检查 patchelf
    if platform.system() == "Linux":
        print("\n🔍 检查 Linux 构建依赖...")
        if not check_patchelf():
            return False
    
    return True

def check_patchelf():
    """检查 patchelf 是否已安装（仅 Linux）
    
    patchelf 是 Nuitka 在 Linux 上修改 ELF 二进制文件所必需的工具。
    
    Returns:
        bool: 如果已安装或非 Linux 系统返回 True
    """
    if platform.system() != "Linux":
        return True
    
    try:
        result = subprocess.run(
            ["patchelf", "--version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip() or result.stderr.decode().strip()
            print(f"   ✅ 找到 patchelf: {version}")
            return True
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"⚠️  检查 patchelf 时出错: {e}")
    
    print("\n" + "=" * 60)
    print("❌ 未找到 patchelf")
    print("=" * 60)
    print("patchelf 是 Nuitka 在 Linux 上构建所必需的工具。")
    print("\n请安装 patchelf：")
    print("   Ubuntu/Debian: sudo apt-get install patchelf")
    print("   Fedora/RHEL:   sudo dnf install patchelf")
    print("   Arch Linux:    sudo pacman -S patchelf")
    print("=" * 60)
    return False


def check_compiler():
    """检查并推荐编译器（Windows）
    
    Returns:
        tuple: (是否找到编译器, 编译器类型)
    """
    if platform.system() != "Windows":
        return True, "system"
    
    # 检查 MinGW
    mingw_found = False
    try:
        result = subprocess.run(
            ["gcc", "--version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            mingw_found = True
            gcc_version = result.stdout.decode().split('\n')[0]
            print(f"   ✅ 找到 MinGW: {gcc_version}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # 检查 MSVC
    msvc_found = False
    try:
        result = subprocess.run(
            ["cl"],
            capture_output=True,
            timeout=5
        )
        # cl 命令存在就认为 MSVC 可用（即使返回错误也是因为没有参数）
        msvc_found = True
        print("   ✅ 找到 MSVC (Visual Studio)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    if mingw_found:
        return True, "mingw"
    elif msvc_found:
        return True, "msvc"
    else:
        print("\n" + "=" * 60)
        print("ℹ️  未检测到系统已安装的 C 编译器")
        print("=" * 60)
        print("🎯 好消息：Nuitka 会在首次编译时自动下载 MinGW！")
        print("\n构建过程中会：")
        print("   1. 自动下载 MinGW-w64 编译器（约 100MB）")
        print("   2. 缓存到 Nuitka 数据目录，后续编译无需重复下载")
        print("   3. 自动配置编译环境")
        print("\n如果您想手动安装编译器（可选）：")
        print("   • MinGW: https://winlibs.com/")
        print("   • MSVC: https://visualstudio.microsoft.com/downloads/")
        print("=" * 60)
        print("\n✅ 继续构建，Nuitka 将自动处理编译器下载...\n")
        return True, "nuitka-auto"  # Nuitka 会自动下载

def get_nuitka_cmd(mode="release", enable_upx=False, upx_path=None, jobs=2, flet_client_path=None):
    """获取 Nuitka 构建命令
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
        enable_upx: 是否启用 UPX 压缩
        upx_path: UPX 工具路径（可选）
        jobs: 并行编译进程数（默认 2）
    """
    dist_dir = get_dist_dir(mode)
    system = platform.system()
    print(f"🖥️  检测到操作系统: {system}")
    print(f"📦 构建模式: {mode.upper()}")
    print(f"📂 输出目录: {dist_dir}")
    print(f"⚙️  并行任务数: {jobs}")
    
    # Windows 上检查编译器
    if system == "Windows":
        compiler_found, compiler_type = check_compiler()
        # Nuitka 会自动下载编译器，所以总是返回 True
        
        if compiler_type == "mingw":
            print("   🔧 使用编译器: MinGW (GCC)")
        elif compiler_type == "msvc":
            print("   🔧 使用编译器: MSVC (Visual Studio)")
        elif compiler_type == "nuitka-auto":
            print("   🔧 使用编译器: Nuitka 自动下载的 MinGW")
    
    # 基础命令
    # 优先使用 uv run 来执行 nuitka，确保环境正确
    try:
        subprocess.check_call(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # uv 可用，使用 uv run
        executable_cmd = ["uv", "run", "python"]
    except (FileNotFoundError, subprocess.CalledProcessError):
        # uv 不可用，回退到当前 python
        executable_cmd = [sys.executable]

    cmd = executable_cmd + [
        "-m", "nuitka",
        "--standalone",
        f"--output-dir={dist_dir}",
        "--assume-yes-for-downloads",
        "--follow-imports",
        # 资源控制 - 防止系统卡死
        f"--jobs={jobs}",  # 并行编译进程数
        # 显式包含 Flet 相关包（避免被 Nuitka 忽略）
        "--include-package=flet",
        "--include-package=flet_desktop",
        "--include-package=flet.controls",
        # 数据文件
        f"--include-data-dir={ASSETS_DIR}=src/assets",
    ]
    
    # 特别包含 Flet 客户端到 flet_desktop 包的 app 目录
    # flet_desktop 会从 flet_desktop/app/flet/ 查找客户端
    if flet_client_path and flet_client_path.exists():
        print(f"   🔧 包含 Flet 客户端到 flet_desktop/app/: {flet_client_path.name}")
        # 递归包含所有文件，包括 .exe 和 .dll
        # 打包到 flet_desktop/app/ 目录下
        for flet_file in flet_client_path.rglob('*'):
            if flet_file.is_file():
                # 计算相对于 flet_client_path 的路径
                rel_path = flet_file.relative_to(flet_client_path)
                # 打包到 flet_desktop/app/flet/...
                cmd.append(f"--include-data-files={flet_file}=flet_desktop/app/{rel_path}")
        print("   ✅ Flet 客户端已添加到 flet_desktop 包")
    else:
        print("   ⚠️  未找到 Flet 客户端，flet_desktop 将从网络下载")
    
    # 根据模式设置优化参数
    if mode == "release":
        # Release 模式：完整优化
        cmd.extend([
            "--python-flag=-O",
            "--python-flag=no_site",
            "--python-flag=no_warnings",
        ])
        print("   优化级别: 完整优化")
    else:  # dev 模式
        # Dev 模式：保留调试信息，快速编译
        cmd.extend([
            "--python-flag=no_site",
        ])
        print("   优化级别: 调试模式")
    
    # Tkinter 插件 - 用于快捷功能的区域选择
    if sys.platform == "win32":
        cmd.append("--enable-plugin=tk-inter")
        print("   Tkinter 插件: 已启用（用于快捷功能区域选择）")
    
    # UPX 压缩插件
    if enable_upx:
        upx_available, upx_cmd = check_upx(upx_path)
        if upx_available:
            cmd.append("--enable-plugin=upx")
            # 禁用 onefile 内置压缩，避免与 UPX 双重压缩
            # 参考: https://nuitka.net/doc/user-manual.html#upx-binary-compression
            cmd.append("--onefile-no-compression")
            if upx_path:
                cmd.append(f"--upx-binary={upx_cmd}")
            print("   UPX 压缩: 已启用（已禁用 onefile 内置压缩以避免双重压缩）")
        else:
            print("   UPX 压缩: 跳过（UPX 不可用）")
    else:
        print("   UPX 压缩: 未启用")
    
    # 排除不需要的包以减小体积
    # 注意：tkinter 用于快捷功能的区域选择，不能排除
    excluded_packages = [
        "unittest", "test", "pytest", 
        "setuptools", "distutils", "wheel", "pip", 
        "IPython", "matplotlib", "pdb"
    ]
    for pkg in excluded_packages:
        cmd.append(f"--nofollow-import-to={pkg}")
    
    # macOS 特殊处理：解决 sherpa-onnx 与 onnxruntime 库冲突问题
    if system == "Darwin":
        print("   🔧 macOS 特殊处理: 排除 sherpa-onnx 的嵌入式库文件")
        # 在 macOS 上，sherpa-onnx 包含的 _sherpa_onnx.cpython-311-darwin.so 
        # 会尝试加载其 lib 目录中的 dylib 文件，导致 Nuitka 打包时出错
        # 解决方案：让 Nuitka 不复制 sherpa_onnx/lib 目录
        cmd.append("--nofollow-import-to=sherpa_onnx.lib")
    
    # 检查 CUDA FULL 版本，包含 nvidia DLL
    cuda_variant = os.environ.get('CUDA_VARIANT', 'none').lower()
    if cuda_variant == 'cuda_full':
        print("   🎯 检测到 CUDA FULL 变体，正在包含 NVIDIA 库...")
        
        # 定义需要包含的 NVIDIA CUDA 包列表（对应 pip 包名）
        # 这些包安装后会在 site-packages/nvidia/ 目录下创建子目录
        nvidia_cuda_packages = [
            'nvidia-cublas-cu12',
            'nvidia-cuda-nvrtc-cu12',
            'nvidia-cuda-runtime-cu12',
            'nvidia-cudnn-cu12',
            'nvidia-cufft-cu12',
            'nvidia-curand-cu12',
            'nvidia-nvjitlink-cu12',
        ]
        
        # 根据平台确定库文件扩展名
        system = platform.system()
        if system == "Windows":
            lib_pattern = "*.dll"
            lib_type = "DLL"
        elif system == "Linux":
            lib_pattern = "*.so*"  # 匹配 .so 和 .so.12 等
            lib_type = "SO"
        elif system == "Darwin":
            lib_pattern = "*.dylib"
            lib_type = "DYLIB"
        else:
            print(f"   ⚠️  不支持的平台: {system}")
            lib_pattern = None
            lib_type = "LIB"
        
        try:
            import site
            site_packages = site.getsitepackages()
            
            nvidia_found = False
            total_packages = 0
            total_libs = 0
            
            for site_pkg in site_packages:
                nvidia_dir = Path(site_pkg) / "nvidia"
                if nvidia_dir.exists():
                    print(f"   ✅ 找到 NVIDIA 库: {nvidia_dir}")
                    
                    print(f"   📦 包含 NVIDIA CUDA 包:")
                    
                    # 遍历每个 NVIDIA 包
                    for pip_pkg_name in nvidia_cuda_packages:
                        # pip 包名转换为目录名：nvidia-cublas-cu12 -> cublas
                        # 规则：去掉 nvidia- 前缀和 -cu12 后缀
                        dir_name = pip_pkg_name.replace('nvidia-', '').replace('-cu12', '').replace('-', '_')
                        pkg_dir = nvidia_dir / dir_name
                        
                        if pkg_dir.exists():
                            # 包含 bin 目录下的所有库文件（Windows: DLL, Linux: SO, macOS: DYLIB）
                            bin_dir = pkg_dir / "bin" if system == "Windows" else pkg_dir / "lib"
                            lib_count = 0
                            
                            # 如果 bin 目录不存在，尝试 lib 目录（跨平台兼容）
                            if not bin_dir.exists():
                                alt_dir = pkg_dir / "lib" if system == "Windows" else pkg_dir / "bin"
                                if alt_dir.exists():
                                    bin_dir = alt_dir
                            
                            if bin_dir.exists() and lib_pattern:
                                # 逐个包含库文件，避免 Nuitka 过滤
                                lib_files = list(bin_dir.glob(lib_pattern))
                                for lib_file in lib_files:
                                    if lib_file.is_file():  # 确保是文件而不是符号链接的目标
                                        # --include-data-files=源文件=目标路径
                                        target_subdir = "bin" if system == "Windows" else "lib"
                                        cmd.append(f"--include-data-files={lib_file}=nvidia/{dir_name}/{target_subdir}/{lib_file.name}")
                                lib_count = len(lib_files)
                                total_libs += lib_count
                            
                            # 包含 include 目录（头文件）- 使用 data-dir 即可
                            include_dir = pkg_dir / "include"
                            if include_dir.exists():
                                cmd.append(f"--include-data-dir={include_dir}=nvidia/{dir_name}/include")
                            
                            total_packages += 1
                            lib_info = f" ({lib_count} {lib_type}s)" if lib_count > 0 else ""
                            print(f"      • {pip_pkg_name} -> nvidia/{dir_name}{lib_info}")
                        else:
                            print(f"      ⚠️  未找到: {pip_pkg_name} (预期目录: {dir_name})")
                    
                    nvidia_found = True
                    print(f"   ✅ 已包含 {total_packages}/{len(nvidia_cuda_packages)} 个包，共 {total_libs} 个 {lib_type} 文件")
                    break
            
            if not nvidia_found:
                print("   ⚠️  警告: 未找到 NVIDIA 库，CUDA FULL 版本可能无法正常运行")
                print("      请确保已安装: uv add 'onnxruntime-gpu[cuda,cudnn]==1.22.0'")
                print("      或: pip install 'onnxruntime-gpu[cuda,cudnn]==1.22.0'")
        except Exception as e:
            print(f"   ⚠️  检查 NVIDIA 库时出错: {e}")
            import traceback
            if mode == "dev":
                traceback.print_exc()
    
    # Windows 特定配置
    if system == "Windows":
        # 控制台模式：dev 模式保留控制台，release 模式禁用
        console_mode = "attach" if mode == "dev" else "disable"
        
        # 获取变体后缀
        variant_suffix = get_variant_suffix()
        product_name = f"{APP_NAME}{variant_suffix}"  # 产品名称：MTools (CUDA)
        file_description = f"{APP_NAME} - 多功能工具箱{variant_suffix}"  # 简短描述
        
        cmd.extend([
            f"--windows-console-mode={console_mode}",
            f"--windows-icon-from-ico={ASSETS_DIR / 'icon.ico'}",
            f"--file-version={get_file_version(VERSION)}",
            f"--product-version={get_file_version(VERSION)}",
            f"--file-description={file_description}",
            f"--company-name={COMPANY_NAME}",
            f"--copyright={COPYRIGHT}",
            f"--product-name={product_name}",
            f"--output-filename={APP_NAME}.exe",
        ])
        if mode == "dev":
            print("   控制台窗口: 已启用（调试模式）")
        else:
            print("   控制台窗口: 已禁用")
        print(f"   产品名称: {product_name}")
    
    # Linux 特定配置
    elif system == "Linux":
        # 获取变体后缀（用于文件名区分）
        variant_suffix = get_variant_suffix()
        
        cmd.extend([
            f"--linux-icon={ASSETS_DIR / 'icon.png'}",
            f"--output-filename={APP_NAME}.bin",
        ])
        if variant_suffix:
            print(f"   版本变体: {variant_suffix.strip()}")
        
    # macOS 特定配置
    elif system == "Darwin":
        # 检测目标架构（Intel 或 Apple Silicon）
        import platform as platform_module
        machine = platform_module.machine()  # 'x86_64' 或 'arm64'
        
        # 获取变体后缀
        variant_suffix = get_variant_suffix()
        app_version = f"{VERSION}{variant_suffix}" if variant_suffix else VERSION
        
        cmd.extend([
            "--macos-create-app-bundle",
            f"--macos-app-icon={ASSETS_DIR / 'icon.icns'}",  # 需要 .icns 格式
            f"--macos-app-name={APP_NAME}",
            f"--macos-app-version={app_version}",
            f"--output-filename={APP_NAME}",
            # 自动检测目标架构
            f"--macos-target-arch={machine}",
        ])
        if variant_suffix:
            print(f"   应用版本: {app_version}")
    
    cmd.append(MAIN_SCRIPT)
    return cmd

def cleanup_sherpa_onnx_libs():
    """清理 sherpa-onnx 自带的 onnxruntime 库文件
    
    sherpa-onnx 包自带了旧版本的 onnxruntime 动态库（1.17.1），
    与系统安装的新版本（1.22.0）冲突，导致 Nuitka 打包时出现路径解析错误。
    
    macOS 上的特殊问题：
    - sherpa_onnx/lib 目录包含 libonnxruntime.1.17.1.dylib 等文件
    - Nuitka 无法正确处理这些旧版本库文件的路径引用
    - 必须完全删除这些库，让程序使用系统安装的新版本
    
    需要删除的文件：
    - Windows: sherpa_onnx/lib/onnxruntime.dll, onnxruntime_*.dll
    - Linux: sherpa_onnx/lib/libonnxruntime.so*
    - macOS: sherpa_onnx/lib/libonnxruntime*.dylib (包括 libonnxruntime.1.17.1.dylib)
    """
    system = platform.system()
    
    try:
        import site
        site_packages = site.getsitepackages()
        
        for site_pkg in site_packages:
            sherpa_lib_dir = Path(site_pkg) / "sherpa_onnx" / "lib"
            if not sherpa_lib_dir.exists():
                continue
            
            print("\n🔍 检查 sherpa-onnx 库文件冲突...")
            print(f"   目录: {sherpa_lib_dir}")
            
            # 根据平台查找并删除 onnxruntime 库文件
            patterns = []
            if system == "Windows":
                patterns = ["onnxruntime.dll", "onnxruntime_*.dll"]
            elif system == "Linux":
                patterns = ["libonnxruntime.so*"]
            elif system == "Darwin":
                # macOS: 使用更宽松的模式来匹配所有 libonnxruntime 变体
                # libonnxruntime.dylib, libonnxruntime.1.dylib, libonnxruntime.1.17.1.dylib 等
                patterns = ["libonnxruntime*dylib"]
            
            deleted_files = []
            for pattern in patterns:
                try:
                    for lib_file in sherpa_lib_dir.glob(pattern):
                        # 过滤掉非库文件的相关项
                        if lib_file.is_file() or lib_file.is_symlink():
                            try:
                                lib_file.unlink()
                                deleted_files.append(lib_file.name)
                            except Exception as e:
                                print(f"   ⚠️  无法删除 {lib_file.name}: {e}")
                except Exception as e:
                    print(f"   ⚠️  搜索模式 {pattern} 时出错: {e}")
            
            if deleted_files:
                print(f"   ✅ 已删除 sherpa-onnx 自带的 onnxruntime 库:")
                for filename in deleted_files:
                    print(f"      • {filename}")
                print("   💡 这些库与系统安装的 onnxruntime 冲突，已自动清理")
            else:
                print("   ℹ️  未发现冲突的 onnxruntime 库文件")
            
            return True
            
    except Exception as e:
        print(f"   ⚠️  检查 sherpa-onnx 库时出错: {e}")
        # 不是致命错误，继续构建
        return False

def run_build(mode="release", enable_upx=False, upx_path=None, jobs=2, mingw64=None, flet_client_path=None):
    """执行构建
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
        enable_upx: 是否启用 UPX 压缩
        upx_path: UPX 工具路径（可选）
        jobs: 并行编译进程数（默认 2）
        mingw64: MinGW64 安装路径（可选）
        flet_client_path: Flet 客户端目录路径（可选）
    """
    clean_dist(mode)
    
    # 在构建前写入 CUDA 变体信息到 app_config.py
    write_cuda_variant_to_config()
    
    # 清理 sherpa-onnx 自带的 onnxruntime 库（避免版本冲突）
    cleanup_sherpa_onnx_libs()
    
    # 注册清理处理器（使用 lambda 捕获 mode）
    register_cleanup_handler(lambda: cleanup_incomplete_build(mode))
    
    # 设置 MinGW 环境变量（如果指定）
    env = os.environ.copy()
    if mingw64 and platform.system() == "Windows":
        mingw_bin = Path(mingw64) / "bin"
        if mingw_bin.exists():
            print(f"   🔧 使用指定的 MinGW64: {mingw64}")
            env['PATH'] = f"{mingw_bin};{env.get('PATH', '')}"
        else:
            print(f"   ⚠️  指定的 MinGW64 路径不存在: {mingw64}")
    
    cmd = get_nuitka_cmd(mode, enable_upx, upx_path, jobs, flet_client_path)
    cmd_str = " ".join(cmd)
    
    print("\n🚀 开始 Nuitka 构建...")
    print(f"   命令: {cmd_str}\n")
    print("   提示: 按 Ctrl+C 可随时中断构建\n")
    
    try:
        subprocess.check_call(cmd, env=env)
        print("\n✅ Nuitka 构建成功！")
        return True
    except KeyboardInterrupt:
        print("\n\n⚠️  构建已被用户中断")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 构建失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False

def organize_output(mode="release"):
    """整理输出文件
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
    """
    dist_dir = get_dist_dir(mode)
    platform_name = get_platform_name()
    output_dir = dist_dir / f"{APP_NAME}_{platform_name}"
    
    print("\n📦 整理输出文件...")
    print(f"   目标目录: {output_dir.name}")
    
    # Nuitka standalone 模式通常会生成 main.dist 文件夹（或类似名称）
    # 我们需要找到生成的文件夹并重命名
    
    dist_content = list(dist_dir.glob("*.dist"))
    if not dist_content:
        # 可能是 macOS app bundle
        app_bundles = list(dist_dir.glob("*.app"))
        if app_bundles:
            print(f"   发现应用包: {app_bundles[0].name}")
            # macOS app bundle 清理资源文件
            cleanup_assets_in_output(app_bundles[0])
            # 不再需要复制库文件，程序启动时自动设置路径
            return True
            
        print("❌ 未找到构建输出目录 (.dist)")
        return False
    
    source_dist = dist_content[0]
    
    # 如果目标目录已存在，先删除
    if output_dir.exists():
        shutil.rmtree(output_dir)
        
    # 重命名/移动到目标目录
    try:
        shutil.move(str(source_dist), str(output_dir))
        print(f"   已重命名: {source_dist.name} -> {output_dir.name}")
        
        # 清理多余的资源文件
        cleanup_assets_in_output(output_dir)
        
        # 注意：不再需要复制 ONNX Runtime 库文件
        # 程序启动时会通过 _setup_onnxruntime_path() 自动设置 DLL 搜索路径
        
        return True
    except Exception as e:
        print(f"   ❌ 整理失败: {e}")
        return False


def cleanup_assets_in_output(output_dir: Path):
    """清理输出目录中多余的资源文件
    
    注意：flet_client/ 目录必须保留！程序运行时需要通过 FLET_VIEW_PATH 使用。
    
    Args:
        output_dir: 输出目录路径
    """
    system = platform.system()
    assets_dir = output_dir / "src" / "assets"
    
    if not assets_dir.exists():
        return
    
    print("   🧹 清理多余的资源文件...")
    
    # 根据平台删除不需要的图标文件
    # 注意：不要删除 flet_client/ 目录，程序运行时需要！
    files_to_remove = []
    
    if system == "Windows":
        files_to_remove = ["icon.icns"]  # Windows 不需要 macOS 图标
    elif system == "Darwin":
        files_to_remove = ["icon.ico"]   # macOS 不需要 Windows 图标
    elif system == "Linux":
        files_to_remove = ["icon.ico", "icon.icns"]  # Linux 只需要 PNG
    
    removed_count = 0
    for filename in files_to_remove:
        file_path = assets_dir / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"      已删除: {filename}")
                removed_count += 1
            except Exception as e:
                print(f"      ⚠️ 删除 {filename} 失败: {e}")
    
    if removed_count > 0:
        print(f"   ✅ 清理完成，共删除 {removed_count} 个文件")

def compress_output(mode="release"):
    """压缩输出目录
    
    根据平台使用不同的压缩格式：
    - Windows: .zip
    - macOS: .tar.gz
    - Linux: .tar.gz
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
    """
    import tarfile
    
    dist_dir = get_dist_dir(mode)
    platform_name = get_platform_name()
    output_dir = dist_dir / f"{APP_NAME}_{platform_name}"
    system = platform.system()
    
    print("\n🗜️  正在压缩...")
    
    # 根据平台选择压缩格式
    if system == "Windows":
        archive_filename = dist_dir / f"{APP_NAME}_{platform_name}.zip"
        use_zip = True
        format_name = "ZIP"
    else:
        archive_filename = dist_dir / f"{APP_NAME}_{platform_name}.tar.gz"
        use_zip = False
        format_name = "TAR.GZ"
    
    print(f"   压缩格式: {format_name}")
    
    try:
        # 如果是 macOS app bundle
        if system == "Darwin" and list(dist_dir.glob("*.app")):
            app_path = list(dist_dir.glob("*.app"))[0]
            # macOS 使用 tar.gz 格式
            with tarfile.open(archive_filename, 'w:gz') as tar:
                for root, _, files in os.walk(app_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(dist_dir)
                        tar.add(file_path, arcname=str(arcname))
        elif use_zip:
            # Windows 目录压缩（使用 ZIP）
            if not output_dir.exists():
                print("   ❌ 找不到要压缩的目录")
                return
                
            with zipfile.ZipFile(archive_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 遍历目录并添加到 zip，保持相对路径结构
                for root, _, files in os.walk(output_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # 计算在压缩包中的相对路径（例如 MTools_Windows_amd64/MTools.exe）
                        arcname = file_path.relative_to(dist_dir)
                        zipf.write(file_path, arcname)
        else:
            # Linux 目录压缩（使用 TAR.GZ）
            if not output_dir.exists():
                print("   ❌ 找不到要压缩的目录")
                return
                
            with tarfile.open(archive_filename, 'w:gz') as tar:
                # 遍历目录并添加到 tar.gz，保持相对路径结构
                for root, _, files in os.walk(output_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # 计算在压缩包中的相对路径（例如 MTools_Linux_amd64/MTools.bin）
                        arcname = file_path.relative_to(dist_dir)
                        tar.add(file_path, arcname=str(arcname))
                        
        print(f"   ✅ 压缩完成: {archive_filename}")
        print(f"   文件大小: {os.path.getsize(archive_filename) / (1024*1024):.2f} MB")
        
    except Exception as e:
        print(f"   ❌ 压缩失败: {e}")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} 构建脚本 - 使用 Nuitka 打包 Python 应用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python build.py                           # 默认 release 模式（自动打包 Flet）
  python build.py --mode dev                # 开发模式（快速编译）
  python build.py --mode release --upx      # release 模式 + UPX 压缩
  python build.py --upx --upx-path "C:\\upx\\upx.exe"  # 指定 UPX 路径
  python build.py --jobs 4                  # 使用 4 个并行任务编译
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["release", "dev"],
        default="release",
        help="构建模式: release (完整优化) 或 dev (快速编译，保留调试信息)"
    )
    
    parser.add_argument(
        "--upx",
        action="store_true",
        help="启用 UPX 压缩（需要安装 UPX）"
    )
    
    parser.add_argument(
        "--upx-path",
        type=str,
        help="指定 UPX 可执行文件的路径（例如: C:\\upx\\upx.exe）"
    )
    
    parser.add_argument(
        "--jobs",
        type=int,
        default=2,
        help="并行编译任务数 (默认: 2)。值越大编译越快，但占用资源越多。建议不超过 CPU 核心数"
    )
    
    parser.add_argument(
        "--mingw64",
        type=str,
        help="指定 MinGW64 安装路径（例如: C:\\mingw64）。Nuitka 会优先使用该编译器"
    )
    
    return parser.parse_args()

def main():
    """主入口"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # 注册退出时的清理函数
    atexit.register(cleanup_on_exit)
    
    try:
        args = parse_args()
        
        print("=" * 50)
        print(f"🔨 {APP_NAME} v{VERSION} 构建工具")
        print("=" * 50)
        
        # 检查依赖（包括 onnxruntime 版本检查）
        if not check_dependencies():
            print("\n❌ 依赖检查失败，已取消构建")
            sys.exit(1)
        
        # 自动检查并准备 Flet 客户端（支持 UPX 压缩）
        flet_client_path = check_and_prepare_flet_client(enable_upx=args.upx, upx_path=args.upx_path)
        if not flet_client_path:
            print("❌ Flet 客户端准备失败，已取消构建")
            sys.exit(1)
        
        if run_build(mode=args.mode, enable_upx=args.upx, upx_path=args.upx_path, jobs=args.jobs, mingw64=args.mingw64, flet_client_path=flet_client_path):
            if platform.system() != "Darwin":  # macOS app bundle 不需要重命名步骤
                if not organize_output(args.mode):
                    print("\n❌ 构建未完成")
                    sys.exit(1)
            
            compress_output(args.mode)
            
            # 编译完成后自动清理构建缓存
            cleanup_build_cache()
            
            print("\n" + "=" * 50)
            print(f"🎉 全部完成！构建文件位于 dist/{args.mode} 目录")
            print("=" * 50)
            sys.exit(0)
        else:
            print("\n❌ 构建失败")
            sys.exit(1)
    
    except KeyboardInterrupt:
        # 已经在 signal_handler 中处理
        pass
    except Exception as e:
        print(f"\n❌ 构建过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

