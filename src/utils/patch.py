import subprocess
import sys
import warnings
import os
from pathlib import Path

# ===== 设置 UTF-8 编码（解决 Windows GBK 编码问题）=====
# 这个必须在最前面设置，确保整个应用使用 UTF-8 编码
# 特别是在 Windows 系统上，默认使用 GBK 编码会导致 Unicode 字符输出失败
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
try:
    # Python 3.7+ 支持直接设置 UTF-8 模式
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    # Python < 3.7 或其他环境不支持 reconfigure
    pass

# 屏蔽 libpng 警告
warnings.filterwarnings("ignore", message=".*iCCP.*")

# ===== 设置 ONNX Runtime 环境变量（必须在导入 onnxruntime 之前） =====
# 设置日志级别，避免程序退出时的 "DefaultLogger has not been registered" 错误
os.environ['ORT_LOG_LEVEL'] = '3'  # 3 = Error (只显示错误)
# 禁用 ONNX Runtime 日志（更激进的方案）
os.environ['ORT_DISABLE_LOGGING'] = '1'

# ===== 设置 ONNX Runtime 和 NVIDIA CUDA 库路径 =====
def _setup_library_paths():
    """设置 ONNX Runtime 和 NVIDIA CUDA 库搜索路径。

    **必须在 import onnxruntime 之前完成**，否则在纯净 Windows 上
    onnxruntime_pybind11_state.pyd 找不到 vcruntime140.dll 等 DLL 会直接崩溃。

    路径查找策略（不依赖 import onnxruntime）：
    1. 应用根目录（vcruntime140.dll 所在位置）
    2. site-packages/onnxruntime/capi（onnxruntime.dll 所在位置）
    3. site-packages/nvidia/*/bin（CUDA 库）
    """
    import platform
    import site

    system = platform.system()
    debug_patch = os.environ.get('MYTOOLS_DEBUG_PATCH', '').lower() in ('1', 'true', 'yes')

    if debug_patch:
        print(f"DEBUG | 开始设置库路径... (平台: {system})")

    lib_paths: list[Path] = []

    # ── 收集 site-packages 目录列表 ──────────────────────────
    sp_dirs: list[Path] = []
    try:
        sp_dirs.extend(Path(p) for p in site.getsitepackages())
    except Exception:
        pass
    # flet build 通过环境变量指定 site-packages
    _sp_env = os.environ.get("SERIOUS_PYTHON_SITE_PACKAGES")
    if _sp_env:
        sp_dirs.append(Path(_sp_env))
    # 从 sys.path 兜底查找 site-packages（防止环境变量未设置）
    for p in sys.path:
        pp = Path(p)
        if pp.name == "site-packages" and pp.is_dir() and pp not in sp_dirs:
            sp_dirs.append(pp)

    if debug_patch:
        print(f"DEBUG | site-packages 候选: {[str(p) for p in sp_dirs]}")

    # ── 1. 应用根目录（vcruntime140.dll 等 CRT 所在位置）──────
    _app_roots: list[Path] = []
    if _sp_env:
        # flet build: site-packages 与 exe 在同一层级
        _app_roots.append(Path(_sp_env).parent)
    if hasattr(sys, 'argv') and sys.argv and sys.argv[0]:
        _app_roots.append(Path(sys.argv[0]).parent)
    if sys.executable:
        _app_roots.append(Path(sys.executable).parent)

    for app_root in _app_roots:
        if app_root.is_dir() and app_root not in lib_paths:
            lib_paths.append(app_root)
            if debug_patch:
                print(f"DEBUG | 应用根目录: {app_root}")

    # ── 2. onnxruntime/capi 和 sherpa_onnx/lib（不 import，直接在文件系统中查找）
    for sp in sp_dirs:
        capi = sp / "onnxruntime" / "capi"
        if capi.is_dir() and capi not in lib_paths:
            lib_paths.append(capi)
            if debug_patch:
                print(f"DEBUG | 找到 ONNX Runtime capi: {capi}")
        sherpa_lib = sp / "sherpa_onnx" / "lib"
        if sherpa_lib.is_dir() and sherpa_lib not in lib_paths:
            lib_paths.append(sherpa_lib)
            if debug_patch:
                print(f"DEBUG | 找到 sherpa_onnx lib: {sherpa_lib}")

    # ── 3. NVIDIA CUDA 库（nvidia/*/bin 或 lib）────────────────
    for sp in sp_dirs:
        nvidia_dir = sp / "nvidia"
        if not nvidia_dir.is_dir():
            continue
        if debug_patch:
            print(f"DEBUG | 找到 NVIDIA 目录: {nvidia_dir}")
        try:
            for subdir in nvidia_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    bin_dir = subdir / ("bin" if system == "Windows" else "lib")
                    if bin_dir.is_dir() and bin_dir not in lib_paths:
                        lib_paths.append(bin_dir)
                        if debug_patch:
                            print(f"DEBUG | 找到 NVIDIA 库: {bin_dir}")
        except Exception:
            pass

    # ── 4. 打包后相对目录中的 nvidia ──────────────────────────
    for app_root in _app_roots:
        nvidia_rel = app_root / "nvidia"
        if not nvidia_rel.is_dir():
            continue
        try:
            for subdir in nvidia_rel.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    bin_dir = subdir / ("bin" if system == "Windows" else "lib")
                    if bin_dir.is_dir() and bin_dir not in lib_paths:
                        lib_paths.append(bin_dir)
                        if debug_patch:
                            print(f"DEBUG | 找到本地 NVIDIA 库: {bin_dir}")
        except Exception:
            pass

    # ── 5. 系统安装的 CUDA Toolkit（cuda 变体，用户自装 CUDA）──
    if system == "Windows":
        cuda_path = os.environ.get("CUDA_PATH", "")
        if cuda_path:
            cuda_bin = Path(cuda_path) / "bin"
            if cuda_bin.is_dir() and cuda_bin not in lib_paths:
                lib_paths.append(cuda_bin)
                if debug_patch:
                    print(f"DEBUG | 找到系统 CUDA: {cuda_bin}")
        else:
            cuda_base = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
            if cuda_base.is_dir():
                try:
                    versions = sorted(cuda_base.iterdir(), reverse=True)
                    for ver_dir in versions:
                        cuda_bin = ver_dir / "bin"
                        if cuda_bin.is_dir() and cuda_bin not in lib_paths:
                            lib_paths.append(cuda_bin)
                            if debug_patch:
                                print(f"DEBUG | 找到系统 CUDA: {cuda_bin}")
                            break
                except Exception:
                    pass
    elif system == "Linux":
        for cuda_candidate in [
            Path("/usr/local/cuda/lib64"),
            Path("/usr/lib/x86_64-linux-gnu"),
        ]:
            if cuda_candidate.is_dir() and cuda_candidate not in lib_paths:
                lib_paths.append(cuda_candidate)
                if debug_patch:
                    print(f"DEBUG | 找到系统 CUDA: {cuda_candidate}")

    # ── 应用路径 ──────────────────────────────────────────────
    if not lib_paths:
        if debug_patch:
            print("DEBUG | 未找到任何库路径，跳过配置")
        return

    if debug_patch:
        print(f"DEBUG | 共找到 {len(lib_paths)} 个库路径")

    if system == "Windows":
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if sys.version_info >= (3, 8):
                try:
                    os.add_dll_directory(lib_path_str)
                    if debug_patch:
                        print(f"DEBUG | DLL 目录已添加: {lib_path}")
                except Exception as e:
                    if debug_patch:
                        print(f"DEBUG | DLL 目录添加失败: {lib_path} - {e}")
            if lib_path_str not in os.environ.get('PATH', ''):
                os.environ['PATH'] = lib_path_str + os.pathsep + os.environ.get('PATH', '')
                if debug_patch:
                    print(f"DEBUG | PATH 已更新: {lib_path}")

    elif system == "Linux":
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in ld_path:
                ld_path = lib_path_str + os.pathsep + ld_path
                if debug_patch:
                    print(f"DEBUG | LD_LIBRARY_PATH 已添加: {lib_path}")
        if ld_path != os.environ.get('LD_LIBRARY_PATH', ''):
            os.environ['LD_LIBRARY_PATH'] = ld_path

    elif system == "Darwin":
        dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in dyld_path:
                dyld_path = lib_path_str + os.pathsep + dyld_path
                if debug_patch:
                    print(f"DEBUG | DYLD_LIBRARY_PATH 已添加: {lib_path}")
        if dyld_path != os.environ.get('DYLD_LIBRARY_PATH', ''):
            os.environ['DYLD_LIBRARY_PATH'] = dyld_path

# 执行库路径设置
_setup_library_paths()

# ===== Windows 子进程窗口隐藏 =====
if sys.platform == "win32":
    # 保存原始 Popen
    _original_popen = subprocess.Popen

    class NoWindowPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            # 如果用户没有显式传入 creationflags，则设置为 CREATE_NO_WINDOW
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                # 如果已有 creationflags，确保合并 CREATE_NO_WINDOW
                kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    # 替换 subprocess.Popen
    subprocess.Popen = NoWindowPopen