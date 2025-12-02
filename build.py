#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTools 跨平台构建脚本
使用 Nuitka 将 Python 项目打包为可执行文件。
"""

import os
import sys
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
DIST_DIR = PROJECT_ROOT / "dist" / "release"
ASSETS_DIR = PROJECT_ROOT / "src" / "assets"
APP_CONFIG_FILE = PROJECT_ROOT / "src" / "constants" / "app_config.py"

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

OUTPUT_DIR = DIST_DIR / f"{APP_NAME}_x64"

def clean_dist():
    """清理构建目录"""
    print("🧹 清理旧的构建文件...")
    if DIST_DIR.exists():
        try:
            shutil.rmtree(DIST_DIR)
            print(f"   已删除: {DIST_DIR}")
        except Exception as e:
            print(f"   ❌ 清理失败: {e}")

def cleanup_incomplete_build():
    """清理未完成的构建文件"""
    try:
        # 清理 .dist 临时目录
        if DIST_DIR.exists():
            for item in DIST_DIR.glob("*.dist"):
                if item.is_dir():
                    print(f"   清理临时目录: {item.name}")
                    shutil.rmtree(item)
            
            # 清理 .build 临时目录
            for item in DIST_DIR.glob("*.build"):
                if item.is_dir():
                    print(f"   清理临时目录: {item.name}")
                    shutil.rmtree(item)
    except Exception as e:
        print(f"   清理临时文件时出错: {e}")

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

def check_dependencies():
    """检查并同步依赖"""
    print("🔍 检查依赖环境...")
    
    # 检查 pyproject.toml 是否存在
    if not (PROJECT_ROOT / "pyproject.toml").exists():
        print("⚠️  未找到 pyproject.toml，跳过依赖检查")
        return True

    try:
        # 尝试使用 uv sync 同步依赖
        # 这会确保环境与 uv.lock/pyproject.toml 一致
        print("   执行 uv sync...")
        subprocess.check_call(["uv", "sync"], cwd=PROJECT_ROOT)
        print("✅ 依赖已同步")
    except FileNotFoundError:
        print("⚠️  未找到 uv 命令，请确保已安装 uv (https://github.com/astral-sh/uv)")
        print("   将尝试使用当前 Python 环境继续构建...")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  依赖同步失败: {e}")
        print("   尝试继续构建...")
    
    # 检查 onnxruntime 版本
    print("\n🔍 检查 ONNX Runtime 版本...")
    return check_onnxruntime_version()

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

def get_nuitka_cmd(mode="release", enable_upx=False, upx_path=None, jobs=2):
    """获取 Nuitka 构建命令
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
        enable_upx: 是否启用 UPX 压缩
        upx_path: UPX 工具路径（可选）
        jobs: 并行编译进程数（默认 2）
    """
    system = platform.system()
    print(f"🖥️  检测到操作系统: {system}")
    print(f"📦 构建模式: {mode.upper()}")
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
        f"--output-dir={DIST_DIR}",
        "--assume-yes-for-downloads",
        "--follow-imports",
        # 资源控制 - 防止系统卡死
        f"--jobs={jobs}",  # 并行编译进程数
        # 数据文件
        f"--include-data-dir={ASSETS_DIR}=src/assets",
    ]
    
    # 根据模式设置优化参数
    if mode == "release":
        # Release 模式：完整优化
        cmd.extend([
            "--python-flag=-O",
            "--python-flag=no_site",
            "--python-flag=no_warnings",
            "--onefile-no-compression",
        ])
        print("   优化级别: 完整优化")
    else:  # dev 模式
        # Dev 模式：保留调试信息，快速编译
        cmd.extend([
            "--python-flag=no_site",
        ])
        print("   优化级别: 调试模式")
    
    # UPX 压缩插件
    if enable_upx:
        upx_available, upx_cmd = check_upx(upx_path)
        if upx_available:
            cmd.append("--enable-plugin=upx")
            if upx_path:
                cmd.append(f"--upx-binary={upx_cmd}")
            print("   UPX 压缩: 已启用")
        else:
            print("   UPX 压缩: 跳过（UPX 不可用）")
    else:
        print("   UPX 压缩: 未启用")
    
    # 排除不需要的包以减小体积
    excluded_packages = [
        "tkinter", "unittest", "test", "pytest", 
        "setuptools", "distutils", "wheel", "pip", 
        "IPython", "matplotlib", "pdb", "xml"
    ]
    for pkg in excluded_packages:
        cmd.append(f"--nofollow-import-to={pkg}")
    
    # Windows 特定配置
    if system == "Windows":
        # 控制台模式：dev 模式保留控制台，release 模式禁用
        console_mode = "attach" if mode == "dev" else "disable"
        cmd.extend([
            f"--windows-console-mode={console_mode}",
            f"--windows-icon-from-ico={ASSETS_DIR / 'icon.ico'}",
            f"--file-version={VERSION}.0",
            f"--product-version={VERSION}",
            f"--file-description={DESCRIPTION}",
            f"--company-name={COMPANY_NAME}",
            f"--copyright={COPYRIGHT}",
            f"--product-name={APP_NAME}",
            f"--output-filename={APP_NAME}.exe",
        ])
        if mode == "dev":
            print("   控制台窗口: 已启用（调试模式）")
        else:
            print("   控制台窗口: 已禁用")
    
    # Linux 特定配置
    elif system == "Linux":
        cmd.extend([
            f"--linux-icon={ASSETS_DIR / 'icon.png'}",
            f"--output-filename={APP_NAME}.bin",
        ])
        
    # macOS 特定配置
    elif system == "Darwin":
        cmd.extend([
            "--macos-create-app-bundle",
            f"--macos-app-icon={ASSETS_DIR / 'icon.icns'}",  # 需要 .icns 格式
            f"--macos-app-name={APP_NAME}",
            f"--macos-app-version={VERSION}",
            f"--output-filename={APP_NAME}",
        ])
    
    cmd.append(MAIN_SCRIPT)
    return cmd

def run_build(mode="release", enable_upx=False, upx_path=None, jobs=2, mingw64=None):
    """执行构建
    
    Args:
        mode: 构建模式 ('release' 或 'dev')
        enable_upx: 是否启用 UPX 压缩
        upx_path: UPX 工具路径（可选）
        jobs: 并行编译进程数（默认 2）
        mingw64: MinGW64 安装路径（可选）
    """
    clean_dist()
    
    # 注册清理处理器
    register_cleanup_handler(cleanup_incomplete_build)
    
    # 设置 MinGW 环境变量（如果指定）
    env = os.environ.copy()
    if mingw64 and platform.system() == "Windows":
        mingw_bin = Path(mingw64) / "bin"
        if mingw_bin.exists():
            print(f"   🔧 使用指定的 MinGW64: {mingw64}")
            env['PATH'] = f"{mingw_bin};{env.get('PATH', '')}"
        else:
            print(f"   ⚠️  指定的 MinGW64 路径不存在: {mingw64}")
    
    cmd = get_nuitka_cmd(mode, enable_upx, upx_path, jobs)
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

def organize_output():
    """整理输出文件"""
    print("\n📦 整理输出文件...")
    
    # Nuitka standalone 模式通常会生成 main.dist 文件夹（或类似名称）
    # 我们需要找到生成的文件夹并重命名
    
    dist_content = list(DIST_DIR.glob("*.dist"))
    if not dist_content:
        # 可能是 macOS app bundle
        app_bundles = list(DIST_DIR.glob("*.app"))
        if app_bundles:
            print(f"   发现应用包: {app_bundles[0].name}")
            return True
            
        print("❌ 未找到构建输出目录 (.dist)")
        return False
    
    source_dist = dist_content[0]
    
    # 如果目标目录已存在，先删除
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        
    # 重命名/移动到目标目录
    try:
        shutil.move(str(source_dist), str(OUTPUT_DIR))
        print(f"   已重命名: {source_dist.name} -> {OUTPUT_DIR.name}")
        return True
    except Exception as e:
        print(f"   ❌ 整理失败: {e}")
        return False

def compress_output():
    """压缩输出目录"""
    print("\n🗜️  正在压缩...")
    
    zip_filename = DIST_DIR / f"{APP_NAME}_{platform.system()}_{platform.machine()}.zip"
    
    try:
        # 如果是 macOS app bundle
        if platform.system() == "Darwin" and list(DIST_DIR.glob("*.app")):
            app_path = list(DIST_DIR.glob("*.app"))[0]
            # macOS 上通常使用 shutil.make_archive 或 tar 命令
            # 这里为了简单使用 zip
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(app_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(DIST_DIR)
                        zipf.write(file_path, arcname)
        else:
            # Windows/Linux 目录压缩
            if not OUTPUT_DIR.exists():
                print("   ❌ 找不到要压缩的目录")
                return
                
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 遍历目录并添加到 zip，保持相对路径结构
                for root, _, files in os.walk(OUTPUT_DIR):
                    for file in files:
                        file_path = Path(root) / file
                        # 计算在压缩包中的相对路径（例如 MTools_x64/MTools.exe）
                        arcname = file_path.relative_to(DIST_DIR)
                        zipf.write(file_path, arcname)
                        
        print(f"   ✅ 压缩完成: {zip_filename}")
        print(f"   文件大小: {os.path.getsize(zip_filename) / (1024*1024):.2f} MB")
        
    except Exception as e:
        print(f"   ❌ 压缩失败: {e}")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} 构建脚本 - 使用 Nuitka 打包 Python 应用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python build.py                           # 默认 release 模式
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
        
        if run_build(mode=args.mode, enable_upx=args.upx, upx_path=args.upx_path, jobs=args.jobs, mingw64=args.mingw64):
            if platform.system() != "Darwin":  # macOS app bundle 不需要重命名步骤
                if not organize_output():
                    print("\n❌ 构建未完成")
                    sys.exit(1)
            
            compress_output()
            
            print("\n" + "=" * 50)
            print("🎉 全部完成！构建文件位于 dist/release 目录")
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

