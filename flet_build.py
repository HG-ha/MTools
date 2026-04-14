#!/usr/bin/env python3
"""
flet build 包装脚本 — 自动修补已知的上游构建问题。

已修补的问题：
1. serious_python_windows CMakeLists.txt 从 %WINDIR%/System32 复制
   vcruntime140_1.dll 时 CMake file(INSTALL) 失败。
   修补方式：改为从 Python 包自带的副本获取。

2. flet_cli find_platform_image 在 Windows 上可能选中 .icns 图标。
   修补方式：按目标平台优先级排序候选图标。
   （此问题已在 .venv 中修补，这里做双重保障。）

用法：
    python flet_build.py windows -v
    python flet_build.py windows --build-version=0.0.16-beta
    python flet_build.py windows -v --build-version=0.0.16-beta --build-number=42

所有参数原样传递给 flet build。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.absolute()
BUILD_FLUTTER_DIR = PROJECT_ROOT / "build" / "flutter"

PATCHES = []

_LOCAL_EXTENSIONS = {
    "flet-gpt-markdown": "extensions/flet-gpt-markdown",
}


def register_patch(fn):
    PATCHES.append(fn)
    return fn


# ---------------------------------------------------------------------------
# Patch 1: serious_python_windows — vcruntime DLL 路径
# ---------------------------------------------------------------------------
@register_patch
def patch_serious_python_vcruntime(build_dir: Path) -> bool:
    """
    将 vcruntime140.dll / vcruntime140_1.dll 的复制源
    从 %WINDIR%/System32 改为 ${PYTHON_PACKAGE}（Python 包自带副本）。
    msvcp140.dll 在 Python 包中不存在，保留从 System32 获取。
    """
    if sys.platform != "win32":
        return False

    cmake_file = _find_serious_python_cmake(build_dir)
    if cmake_file is None:
        return False

    text = cmake_file.read_text(encoding="utf-8")

    old_block = (
        '  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140.dll"\n'
        '  "${SERIOUS_PYTHON_WINDIR}/System32/vcruntime140_1.dll"'
    )
    new_block = (
        '  "${PYTHON_PACKAGE}/vcruntime140.dll"\n'
        '  "${PYTHON_PACKAGE}/vcruntime140_1.dll"'
    )

    if old_block not in text:
        print("  [patch] serious_python vcruntime: 已是最新，跳过")
        return False

    text = text.replace(old_block, new_block)
    cmake_file.write_text(text, encoding="utf-8")
    print("  [patch] serious_python vcruntime: 已修补 ✓")
    return True


def _find_serious_python_cmake(build_dir: Path) -> Path | None:
    """定位 serious_python_windows 的 CMakeLists.txt（通过 plugin_symlinks）。"""
    candidates = [
        build_dir
        / "windows"
        / "flutter"
        / "ephemeral"
        / ".plugin_symlinks"
        / "serious_python_windows"
        / "windows"
        / "CMakeLists.txt",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Patch 2: flet_cli — 平台图标优先级（双重保障）
# ---------------------------------------------------------------------------
@register_patch
def patch_icon_selection(build_dir: Path) -> bool:
    """
    确保 build/flutter 中只保留当前平台适用的图标文件。
    Windows 构建时删除 .icns，macOS 构建时删除 .ico。
    """
    assets_dir = build_dir / "src" / "assets"
    if not assets_dir.exists():
        return False

    removed = False
    if sys.platform == "win32":
        for icns in assets_dir.glob("*.icns"):
            icns.unlink()
            print(f"  [patch] 移除不兼容图标: {icns.name} ✓")
            removed = True
    elif sys.platform == "darwin":
        for ico in assets_dir.glob("*.ico"):
            ico.unlink()
            print(f"  [patch] 移除不兼容图标: {ico.name} ✓")
            removed = True

    if not removed:
        print("  [patch] 图标文件: 无需处理")
    return removed


# ---------------------------------------------------------------------------
# Patch 3: 修复扩展包 Flutter 代码缺失
# ---------------------------------------------------------------------------
@register_patch
def patch_flutter_packages(build_dir: Path) -> bool:
    """
    serious_python 的 cleanup-packages 可能删除扩展包中的 Dart 源文件。
    如果 build/flutter-packages/ 下的扩展目录缺少 lib/ 文件，
    从本地扩展源码重新复制。
    """
    flutter_pkgs_dir = build_dir.parent / "flutter-packages"
    if not flutter_pkgs_dir.exists():
        return False

    any_fixed = False
    for pkg_name, rel_path in _LOCAL_EXTENSIONS.items():
        pkg_dart_name = pkg_name.replace("-", "_")
        target_dir = flutter_pkgs_dir / pkg_dart_name
        source_dir = PROJECT_ROOT / rel_path / "src" / "flutter" / pkg_dart_name

        if not source_dir.exists():
            continue

        dart_entry = target_dir / "lib" / f"{pkg_dart_name}.dart"
        if target_dir.exists() and dart_entry.exists():
            print(f"  [patch] {pkg_dart_name} Flutter 代码: 完整，跳过")
            continue

        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        # 验证复制结果
        copied_files = [str(p.relative_to(target_dir)) for p in target_dir.rglob("*") if p.is_file()]
        print(f"  [patch] {pkg_dart_name} Flutter 代码: 已从源码复制 ✓ ({len(copied_files)} 个文件)")
        for f in copied_files:
            print(f"    - {f}")
        any_fixed = True

    return any_fixed


# ---------------------------------------------------------------------------
# Pre-build: 解析 pyproject.toml 中的路径变量
# ---------------------------------------------------------------------------
def _resolve_pyproject_paths() -> str | None:
    """
    将 pyproject.toml 中的本地扩展包名替换为 pip 可识别的 file:/// 绝对路径。
    uv 通过 [tool.uv.sources] 解析本地路径，但 flet build 通过 pip 安装依赖时需要绝对路径。
    返回原始文件内容（用于构建后恢复），若无需替换则返回 None。
    """
    pyproject = PROJECT_ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    original = text
    changed = False
    for pkg_name, rel_path in _LOCAL_EXTENSIONS.items():
        abs_uri = (PROJECT_ROOT / rel_path).as_uri()
        old = f'"{pkg_name}"'
        new = f'"{pkg_name} @ {abs_uri}"'
        if old in text:
            text = text.replace(old, new)
            print(f"  [pre-build] {pkg_name} → {abs_uri}")
            changed = True

    if not changed:
        return None

    pyproject.write_text(text, encoding="utf-8")
    return original


def _restore_pyproject(original: str | None):
    """恢复 pyproject.toml 原始内容。"""
    if original is None:
        return
    pyproject = PROJECT_ROOT / "pyproject.toml"
    pyproject.write_text(original, encoding="utf-8")
    print("  [post-build] pyproject.toml 已恢复")


SHERPA_CUDA_FIND_LINKS = "https://k2-fsa.github.io/sherpa/onnx/cuda.html"


def _setup_sherpa_cuda_find_links():
    """如果 pyproject.toml 中包含 sherpa-onnx+cuda，自动设置 PIP_FIND_LINKS。"""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if "+cuda" not in text:
        return
    existing = os.environ.get("PIP_FIND_LINKS", "")
    if SHERPA_CUDA_FIND_LINKS in existing:
        return
    sep = " " if existing else ""
    os.environ["PIP_FIND_LINKS"] = existing + sep + SHERPA_CUDA_FIND_LINKS
    print(f"  [pre-build] 已设置 PIP_FIND_LINKS（sherpa-onnx CUDA 轮子索引）")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_flet_build(args: list[str]) -> int:
    """运行 flet build 并在失败时尝试修补后重试。"""
    flet_exe = shutil.which("flet")
    if flet_exe:
        cmd = [flet_exe, "build"] + args
    else:
        cmd = [sys.executable, "-m", "flet", "build"] + args
    print(f"=== flet_build.py 包装脚本 ===")
    print(f"命令: flet build {' '.join(args)}")
    print()

    # 清除上次构建残留，防止 flet build 误判 site-packages 已就绪而跳过安装
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        print("清除上次构建残留 build/ ...")
        shutil.rmtree(build_dir)

    original_pyproject = _resolve_pyproject_paths()
    _setup_sherpa_cuda_find_links()
    try:
        return _do_build(cmd, args)
    finally:
        _restore_pyproject(original_pyproject)


def _do_build(cmd: list[str], args: list[str]) -> int:
    """执行构建流程（首次 + 修补重试）。"""
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        print("\n✅ 构建成功（首次）")
        return 0

    # 构建失败 — 检查 build/flutter 是否存在，尝试修补
    if not BUILD_FLUTTER_DIR.exists():
        print("\n❌ 构建失败，且 build/flutter 目录不存在，无法修补")
        return result.returncode

    print("\n⚠️  构建失败，尝试自动修补...")
    any_patched = apply_patches(BUILD_FLUTTER_DIR)

    if not any_patched:
        print("❌ 没有可用的修补，构建失败")
        return result.returncode

    # 修补后重试：直接用 Flutter 重新编译，避免重复准备阶段
    print("\n🔄 修补完成，重新触发 Flutter 编译...")
    return retry_flutter_build(BUILD_FLUTTER_DIR, args)


def apply_patches(build_dir: Path) -> bool:
    """应用所有已注册的补丁。"""
    any_patched = False
    for patch_fn in PATCHES:
        try:
            if patch_fn(build_dir):
                any_patched = True
        except Exception as e:
            print(f"  [patch] {patch_fn.__name__} 出错: {e}")
    return any_patched


def retry_flutter_build(build_dir: Path, original_args: list[str]) -> int:
    """修补后直接调用 flutter build 重新编译。"""
    flutter_bin = _find_flutter_bin()
    if not flutter_bin:
        print("❌ 未找到 Flutter SDK，尝试完整重新运行 flet build...")
        flet_exe = shutil.which("flet")
        if flet_exe:
            cmd = [flet_exe, "build"] + original_args
        else:
            cmd = [sys.executable, "-m", "flet", "build"] + original_args
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        return result.returncode

    target = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"

    # 提取 build-version
    build_name_args = []
    for arg in original_args:
        if arg.startswith("--build-version="):
            build_name_args.extend(["--build-name", arg.split("=", 1)[1]])

    cmd = [
        str(flutter_bin),
        "build",
        target,
        "--release",
        "--no-version-check",
        "--suppress-analytics",
    ] + build_name_args

    # flet build 在调 flutter 之前会设置这个环境变量，
    # 告诉 serious_python 的 CMakeLists.txt 把 site-packages 复制到产物中。
    env = os.environ.copy()
    site_packages_dir = PROJECT_ROOT / "build" / "site-packages"
    if site_packages_dir.exists():
        env["SERIOUS_PYTHON_SITE_PACKAGES"] = str(site_packages_dir)
        print(f"设置 SERIOUS_PYTHON_SITE_PACKAGES={site_packages_dir}")
    else:
        print("⚠️  build/site-packages 不存在，Python 依赖可能不会被打包！")

    # 清除构建缓存，否则编译器可能使用旧的缓存结果
    cache_dirs = [
        build_dir / "build" / "windows" / "x64",          # Windows CMake 缓存
        build_dir / "build" / "macos" / "Build",           # macOS Xcode 构建缓存
        build_dir / "build" / "linux" / "x64",             # Linux CMake 缓存
    ]
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            print(f"清除构建缓存: {cache_dir.name}...")
            shutil.rmtree(cache_dir)

    # 重新获取 Flutter 依赖以确保扩展包被正确解析
    # --no-version-check 和 --suppress-analytics 是 flutter 顶级参数，必须放在子命令之前
    pub_get_cmd = [str(flutter_bin), "--no-version-check", "--suppress-analytics", "pub", "get"]
    print(f"命令: {' '.join(pub_get_cmd)}")
    subprocess.run(pub_get_cmd, cwd=str(build_dir), env=env)

    print(f"命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(build_dir), env=env)

    if result.returncode == 0:
        print("\n✅ 修补后重新编译成功！")
    else:
        print("\n❌ 修补后重新编译仍然失败")

    return result.returncode


def _find_flutter_bin() -> Path | None:
    """查找 flet 使用的 Flutter SDK 路径。"""
    # flet 在 ~/flutter/{version} 下缓存 Flutter SDK
    flutter_home = Path.home() / "flutter"
    if flutter_home.exists():
        for sdk_dir in sorted(flutter_home.iterdir(), reverse=True):
            flutter_exe = sdk_dir / "bin" / ("flutter.bat" if sys.platform == "win32" else "flutter")
            if flutter_exe.exists():
                return flutter_exe

    # 回退：使用 PATH 中的 flutter
    flutter_in_path = shutil.which("flutter")
    if flutter_in_path:
        return Path(flutter_in_path)

    return None


if __name__ == "__main__":
    sys.exit(run_flet_build(sys.argv[1:]))
