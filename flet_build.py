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

3. Xcode 26 在拷贝 macOS 资源时 strip 失败：pyobjc 的 .dSYM
   报 string table not at the end。打包前会按 pyproject 清理；
   若仍失败，则删掉已 staging 的 .dSYM / PyObjCTest 后重编。

4. serious_python 5.0.0 先读完 stdout 再读 stderr。Windows 上
   compileall 把 stderr 管道写满后会死锁，直到 CI 6 小时超时。
   打包前改成同时排空两条管道，并给 compileall 加上 -q。

用法：
    python flet_build.py windows -v
    python flet_build.py windows --build-version=0.0.17-beta
    python flet_build.py windows -v --build-version=0.0.17-beta --build-number=42

所有参数原样传递给 flet build。
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
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
# Patch 4: macOS — Xcode 26 strip 无法处理 pyobjc 的 .dSYM
# ---------------------------------------------------------------------------
def _remove_macos_strip_blockers(root: Path) -> int:
    """删除 Xcode strip 会失败的调试符号，以及用不到的 PyObjC 测试模块。"""
    if not root.exists():
        return 0

    victims: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(root):
        kept: list[str] = []
        for name in dirnames:
            path = Path(dirpath) / name
            if name == "PyObjCTest" or name.endswith(".dSYM"):
                victims.append(path)
            else:
                kept.append(name)
        dirnames[:] = kept

    removed = 0
    for path in victims:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


@register_patch
def patch_macos_strip_blockers(build_dir: Path) -> bool:
    """
    Xcode 26 对已签名的 .so 只警告，但对 pyobjc 轮子里的 .dSYM 会直接失败。
    清理 build 产物和 pub-cache 里已 staging 的副本，再重跑 flutter build。
    """
    if sys.platform != "darwin":
        return False

    roots = [PROJECT_ROOT / "build", build_dir]
    pub_cache = Path.home() / ".pub-cache" / "hosted" / "pub.dev"
    if pub_cache.is_dir():
        roots.extend(
            path for path in pub_cache.glob("serious_python_darwin-*") if path.is_dir()
        )

    removed = 0
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        removed += _remove_macos_strip_blockers(root)

    if not removed:
        print("  [patch] macOS strip: 未找到 .dSYM / PyObjCTest")
        return False

    print(f"  [patch] macOS strip: 已移除 {removed} 个 .dSYM / PyObjCTest ✓")
    return True


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


# VC++ 运行时 DLL。flet build 打包后的产物在某些情况下：
#   - msvcp140.dll 可能是 32 位版本（serious_python 的 CMakeLists.txt 从
#     System32 复制时，若构建工具链以 32 位进程运行，会被 WoW64 重定向到
#     SysWOW64，拿到 32 位版本，导致 0xc000007b STATUS_INVALID_IMAGE_FORMAT）
#   - msvcp140_1/_2/_atomic_wait/_codecvt_ids.dll 根本不带，未装 VC++ Redist
#     的机器直接打不开
# 这里统一在打包阶段从可靠的 64 位来源（System32 或 Sysnative）强制覆盖/捆绑。
_VCRT_ALL_DLLS = (
    "msvcp140.dll",            # 覆盖 serious_python 可能放的 32 位版本
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
)


def _is_pe_x64(path: Path) -> bool | None:
    """判断 PE 文件是否为 x64 架构。None 表示解析失败。"""
    try:
        with path.open("rb") as f:
            # DOS header: e_lfanew at 0x3C
            f.seek(0x3C)
            pe_offset = int.from_bytes(f.read(4), "little")
            # PE signature "PE\0\0" (4 bytes) + IMAGE_FILE_HEADER.Machine (2 bytes)
            f.seek(pe_offset + 4)
            machine = int.from_bytes(f.read(2), "little")
        return machine == 0x8664
    except Exception:
        return None


def _find_x64_vcrt_source(name: str) -> Path | None:
    """找到指定 VC++ DLL 的可靠 64 位来源。

    64 位进程访问 C:\\Windows\\System32 直接拿到 64 位 DLL。
    本脚本通过 64 位 Python 运行，所以直接用 System32 即可。
    但为防止其他因素干扰，额外校验 PE 架构。
    """
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    # 候选路径按优先级：
    # 1) System32（64 位进程不受 WoW64 重定向影响）
    # 2) Sysnative（32 位进程专用绕过符号链接，64 位进程也能访问）
    for sub in ("System32", "Sysnative"):
        candidate = windir / sub / name
        if candidate.is_file():
            if _is_pe_x64(candidate):
                return candidate
    return None


def _bundle_vcrt_extra_dlls() -> None:
    """将 VC++ 运行时 DLL（x64）复制/覆盖到打包输出目录（与 MTools.exe 同级）。"""
    if sys.platform != "win32":
        return

    build_root = PROJECT_ROOT / "build" / "windows"
    if not build_root.exists():
        return

    # 定位 MTools.exe 所在目录
    exe_candidates = list(build_root.glob("MTools.exe")) or list(build_root.rglob("MTools.exe"))
    if not exe_candidates:
        exe_candidates = list(build_root.rglob("mtools.exe"))
    if not exe_candidates:
        print("  [post-build] ⚠️  未找到 MTools.exe，跳过 VC++ 运行时捆绑")
        return

    target_dirs = {exe.parent for exe in exe_candidates}

    copied, overwritten, missing = [], [], []
    for name in _VCRT_ALL_DLLS:
        src = _find_x64_vcrt_source(name)
        if src is None:
            missing.append(name)
            continue
        for target_dir in target_dirs:
            dst = target_dir / name
            is_replace = dst.is_file()
            # 若已存在且已是 x64，跳过（除了 msvcp140.dll 始终强制覆盖，
            # 因为上游可能放的是 32 位版本）
            if is_replace and name != "msvcp140.dll" and _is_pe_x64(dst):
                continue
            try:
                shutil.copy2(src, dst)
                rel = str(dst.relative_to(PROJECT_ROOT))
                if is_replace:
                    overwritten.append(rel)
                else:
                    copied.append(rel)
            except Exception as e:
                print(f"  [post-build] 复制 {name} 失败: {e}")

    if copied:
        print(f"  [post-build] 已捆绑 VC++ 运行时（新增 x64）:")
        for c in copied:
            print(f"    + {c}")
    if overwritten:
        print(f"  [post-build] 已覆盖 VC++ 运行时（替换为 x64）:")
        for c in overwritten:
            print(f"    ~ {c}")
    if missing:
        print(f"  [post-build] ⚠️  未找到 x64 版本: {', '.join(missing)}")
        print(f"               请确认本机已安装 VC++ 2015-2022 Redistributable (x64)")


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
def _ensure_macos_arm64_arch(args: list[str]) -> list[str]:
    """macOS 默认只构建 arm64，避免在 Apple Silicon 上交叉装 x86_64 依赖失败。"""
    if not args or args[0] != "macos":
        return args
    if "--arch" in args:
        return args
    # 插在平台名后，保持其余参数不变
    return [args[0], "--arch", "arm64", *args[1:]]


def _ensure_python_312(args: list[str]) -> list[str]:
    """Flet 1.0 打包运行时只有 3.12/3.13/3.14。固定 3.12，与 requires-python 一致。"""
    if any(arg == "--python-version" or arg.startswith("--python-version=") for arg in args):
        return args
    if args and not args[0].startswith("-"):
        return [args[0], "--python-version", "3.12", *args[1:]]
    return ["--python-version", "3.12", *args]


def run_flet_test(args: list[str]) -> int:
    """跑 flet test。先把本地扩展改成 pip 能安装的路径，结束再恢复。

    Windows 上这个测试把应用嵌进 Debug 版 Python（python312_d.dll）。
    Pillow、NumPy 的轮子链接正式版 python312.dll，嵌进去后会在导入时失败。
    """
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("FLET_CLI_NO_RICH_OUTPUT", "1")
    if "--yes" not in args and "-y" not in args:
        args = ["--yes", *args]

    flet_exe = shutil.which("flet")
    if flet_exe:
        cmd = [flet_exe, "test", *args]
    else:
        cmd = [sys.executable, "-m", "flet", "test", *args]

    original_pyproject = _resolve_pyproject_paths()
    _setup_sherpa_cuda_find_links()
    try:
        return subprocess.run(cmd, cwd=PROJECT_ROOT, env=os.environ.copy()).returncode
    finally:
        _restore_pyproject(original_pyproject)


# 与 flet-cli 1.0.3 模板里的 serious_python 版本一致。
_SERIOUS_PYTHON_VERSION = "5.0.0"
_SERIOUS_PYTHON_SHA256 = (
    "64af9e492f71189aff40459fc2c375c827e79647b1299f3bd304d1067f728c85"
)
_SERIOUS_PYTHON_ARCHIVE = (
    "https://pub.dev/api/archives/"
    f"serious_python-{_SERIOUS_PYTHON_VERSION}.tar.gz"
)

_OLD_RUN_EXEC = """\
  Future<int> runExec(String execPath, List<String> args,
      {Map<String, String>? environment}) async {
    final proc = await Process.start(execPath, args, environment: environment);

    await for (final line in proc.stdout.transform(utf8.decoder)) {
      verbose(line.trim());
    }

    if (await proc.exitCode != 0) {
      stderr.write(await proc.stderr.transform(utf8.decoder).join());
      exit(1);
    }
    return proc.exitCode;
  }
"""

_NEW_RUN_EXEC = """\
  Future<int> runExec(String execPath, List<String> args,
      {Map<String, String>? environment}) async {
    final proc = await Process.start(execPath, args, environment: environment);

    // Drain stdout and stderr together. Reading stderr only after exit deadlocks
    // when the child fills the stderr pipe (compileall / pip on Windows).
    final stderrBuf = StringBuffer();
    final stdoutDone = proc.stdout
        .transform(utf8.decoder)
        .forEach((line) => verbose(line.trim()));
    final stderrDone =
        proc.stderr.transform(utf8.decoder).forEach(stderrBuf.write);
    await Future.wait([stdoutDone, stderrDone]);

    final code = await proc.exitCode;
    if (code != 0) {
      stderr.write(stderrBuf.toString());
      exit(1);
    }
    return code;
  }
"""

_COMPILEALL_REPLACEMENTS = (
    (
        "await runPython(['-m', 'compileall', '-b', tempDir.path]);",
        "await runPython(['-m', 'compileall', '-q', '-b', tempDir.path]);",
    ),
    (
        "await runPython(['-m', 'compileall', '-b', sitePackagesDir]);",
        "await runPython(['-m', 'compileall', '-q', '-b', sitePackagesDir]);",
    ),
)


def _pub_cache_dir() -> Path:
    if os.environ.get("PUB_CACHE"):
        return Path(os.environ["PUB_CACHE"])
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "Pub" / "Cache"
    return Path.home() / ".pub-cache"


def _install_serious_python_cache(pkg_dir: Path, cache: Path) -> None:
    """把官方包放进 pub-cache。目录已存在时 pub get 不会重新解压。"""
    print(f"  [pre-build] 下载 serious_python {_SERIOUS_PYTHON_VERSION}")
    with urllib.request.urlopen(_SERIOUS_PYTHON_ARCHIVE, timeout=120) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != _SERIOUS_PYTHON_SHA256:
        raise RuntimeError(
            f"serious_python 压缩包校验失败: {digest} != {_SERIOUS_PYTHON_SHA256}"
        )

    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        archive.extractall(pkg_dir, filter="data")

    hash_path = (
        cache / "hosted-hashes" / "pub.dev" / f"serious_python-{_SERIOUS_PYTHON_VERSION}.sha256"
    )
    hash_path.parent.mkdir(parents=True, exist_ok=True)
    hash_path.write_text(_SERIOUS_PYTHON_SHA256, encoding="ascii")


def _patch_serious_python_compileall() -> None:
    """避免 Windows 打包在 compileall 阶段把 stderr 管道写满后卡死。"""
    cache = _pub_cache_dir()
    pkg_dir = cache / "hosted" / "pub.dev" / f"serious_python-{_SERIOUS_PYTHON_VERSION}"
    dart_file = pkg_dir / "bin" / "package_command.dart"
    if not dart_file.is_file():
        _install_serious_python_cache(pkg_dir, cache)
    if not dart_file.is_file():
        raise RuntimeError(f"未找到 {dart_file}")

    text = dart_file.read_text(encoding="utf-8")
    original = text
    if _OLD_RUN_EXEC in text:
        text = text.replace(_OLD_RUN_EXEC, _NEW_RUN_EXEC, 1)
    elif "Drain stdout and stderr together" not in text:
        raise RuntimeError("serious_python runExec 与预期不一致，无法修补")

    for old, new in _COMPILEALL_REPLACEMENTS:
        if old in text:
            text = text.replace(old, new, 1)

    if text == original:
        print("  [pre-build] serious_python compileall: 已是最新，跳过")
        return

    dart_file.write_text(text, encoding="utf-8", newline="\n")
    print("  [pre-build] serious_python compileall: 已修补管道死锁 ✓")


def run_flet_build(args: list[str]) -> int:
    """运行 flet build 并在失败时尝试修补后重试。"""
    args = _ensure_python_312(_ensure_macos_arm64_arch(list(args)))
    flet_exe = shutil.which("flet")
    if flet_exe:
        cmd = [flet_exe, "build"] + args
    else:
        cmd = [sys.executable, "-m", "flet", "build"] + args
    print(f"=== flet_build.py 包装脚本 ===")
    print(f"命令: flet build {' '.join(args)}")
    print()
    _patch_serious_python_compileall()

    # 清除上次构建残留，防止 flet build 误判 site-packages 已就绪而跳过安装
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        print("清除上次构建残留 build/ ...")
        shutil.rmtree(build_dir)

    original_pyproject = _resolve_pyproject_paths()
    _setup_sherpa_cuda_find_links()
    try:
        rc = _do_build(cmd, args)
    finally:
        _restore_pyproject(original_pyproject)

    if rc == 0:
        _bundle_vcrt_extra_dlls()
        _restore_opencv_loader_sources()
    return rc


def _restore_opencv_loader_sources() -> None:
    """OpenCV 的加载器按文件名读取 config.py，不能只留 .pyc。"""
    names = ("config.py", "config-3.py")
    src_dir = Path(sys.prefix) / "Lib" / "site-packages" / "cv2"
    if not (src_dir / "config.py").is_file():
        src_dir = (
            Path(sys.prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
            / "cv2"
        )
    if not (src_dir / "config.py").is_file():
        print("  [post-build] 未找到 OpenCV config.py，跳过恢复")
        return

    restored = 0
    for init_pyc in (PROJECT_ROOT / "build").rglob("cv2/__init__.pyc"):
        if init_pyc.parent.parent.name != "site-packages":
            continue
        for name in names:
            src = src_dir / name
            dest = init_pyc.parent / name
            if src.is_file() and not dest.is_file():
                shutil.copy2(src, dest)
                restored += 1
    if restored:
        print(f"  [post-build] 已恢复 OpenCV 加载脚本 {restored} 个")


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
    argv = sys.argv[1:]
    if argv and argv[0] == "test":
        sys.exit(run_flet_test(argv[1:]))
    sys.exit(run_flet_build(argv))
