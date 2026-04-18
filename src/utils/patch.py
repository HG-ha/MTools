import subprocess
import sys
import warnings
import os
from pathlib import Path

# ===== 设置 UTF-8 编码（解决 Windows GBK 编码问题）=====
# 必须最先设置，确保整个应用使用 UTF-8 编码
# PYTHONUTF8=1 启用 Python UTF-8 模式，影响文件 I/O、os.fsdecode 等
os.environ['PYTHONUTF8'] = '1'
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# 打包后的 GUI 应用没有控制台，stdout/stderr 可能为 None
# 必须在任何 print/logging 之前修复，否则写入 None 会直接崩溃
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
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

    诊断信息存储在 _patch_diagnostics 列表中，由 main.py 在日志系统初始化后输出。
    """
    global _patch_diagnostics
    import platform
    import site

    system = platform.system()
    debug_patch = os.environ.get('MYTOOLS_DEBUG_PATCH', '').lower() in ('1', 'true', 'yes')

    def _diag(msg: str):
        _patch_diagnostics.append(msg)
        if debug_patch:
            print(f"DEBUG | {msg}")

    _diag(f"开始设置库路径 (平台: {system})")
    _diag(f"SERIOUS_PYTHON_SITE_PACKAGES={os.environ.get('SERIOUS_PYTHON_SITE_PACKAGES', '<未设置>')}")
    _diag(f"FLET_ASSETS_DIR={os.environ.get('FLET_ASSETS_DIR', '<未设置>')}")
    _diag(f"FLET_APP_CONSOLE={os.environ.get('FLET_APP_CONSOLE', '<未设置>')}")
    _diag(f"sys.argv[0]={sys.argv[0] if sys.argv else '<空>'}")
    _diag(f"sys.executable={sys.executable}")

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

    _diag(f"site-packages 候选: {[str(p) for p in sp_dirs]}")

    # ── 1. 应用根目录（vcruntime140.dll 等 CRT 所在位置）──────
    _app_roots: list[Path] = []
    if _sp_env:
        _app_roots.append(Path(_sp_env).parent)
    if hasattr(sys, 'argv') and sys.argv and sys.argv[0]:
        _app_roots.append(Path(sys.argv[0]).parent)
    if sys.executable:
        _app_roots.append(Path(sys.executable).parent)

    for app_root in _app_roots:
        if app_root.is_dir() and app_root not in lib_paths:
            lib_paths.append(app_root)
            _diag(f"应用根目录: {app_root}")

    # ── 2. onnxruntime/capi 和 sherpa_onnx/lib（不 import，直接在文件系统中查找）
    _capi_found = False
    for sp in sp_dirs:
        capi = sp / "onnxruntime" / "capi"
        if capi.is_dir() and capi not in lib_paths:
            lib_paths.append(capi)
            _capi_found = True
            _capi_files = [f.name for f in capi.iterdir()
                           if f.suffix in ('.dll', '.pyd', '.so', '.dylib')]
            _diag(f"找到 onnxruntime/capi: {capi} ({len(_capi_files)} 个库文件)")
            _diag(f"  capi 库文件: {_capi_files}")
        sherpa_lib = sp / "sherpa_onnx" / "lib"
        if sherpa_lib.is_dir() and sherpa_lib not in lib_paths:
            lib_paths.append(sherpa_lib)
            _diag(f"找到 sherpa_onnx lib: {sherpa_lib}")
    if not _capi_found:
        _diag("警告: 未在任何 site-packages 中找到 onnxruntime/capi 目录!")

    # ── 3. NVIDIA CUDA 库（nvidia/*/bin 或 lib）────────────────
    for sp in sp_dirs:
        nvidia_dir = sp / "nvidia"
        if not nvidia_dir.is_dir():
            continue
        _diag(f"找到 NVIDIA 目录: {nvidia_dir}")
        try:
            for subdir in nvidia_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('_'):
                    bin_dir = subdir / ("bin" if system == "Windows" else "lib")
                    if bin_dir.is_dir() and bin_dir not in lib_paths:
                        lib_paths.append(bin_dir)
                        _diag(f"找到 NVIDIA 库: {bin_dir}")
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
                        _diag(f"找到本地 NVIDIA 库: {bin_dir}")
        except Exception:
            pass

    # ── 5. 系统安装的 CUDA Toolkit（cuda 变体，用户自装 CUDA）──
    if system == "Windows":
        cuda_path = os.environ.get("CUDA_PATH", "")
        if cuda_path:
            cuda_bin = Path(cuda_path) / "bin"
            if cuda_bin.is_dir() and cuda_bin not in lib_paths:
                lib_paths.append(cuda_bin)
                _diag(f"找到系统 CUDA: {cuda_bin}")
        else:
            cuda_base = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA")
            if cuda_base.is_dir():
                try:
                    versions = sorted(cuda_base.iterdir(), reverse=True)
                    for ver_dir in versions:
                        cuda_bin = ver_dir / "bin"
                        if cuda_bin.is_dir() and cuda_bin not in lib_paths:
                            lib_paths.append(cuda_bin)
                            _diag(f"找到系统 CUDA: {cuda_bin}")
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
                _diag(f"找到系统 CUDA: {cuda_candidate}")

    # ── 应用路径 ──────────────────────────────────────────────
    if not lib_paths:
        _diag("未找到任何库路径，跳过配置")
        return

    _diag(f"共找到 {len(lib_paths)} 个库路径: {[str(p) for p in lib_paths]}")

    if system == "Windows":
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if sys.version_info >= (3, 8):
                try:
                    os.add_dll_directory(lib_path_str)
                    _diag(f"DLL 目录已添加: {lib_path}")
                except Exception as e:
                    _diag(f"DLL 目录添加失败: {lib_path} - {e}")
            if lib_path_str not in os.environ.get('PATH', ''):
                os.environ['PATH'] = lib_path_str + os.pathsep + os.environ.get('PATH', '')

        # ── 预加载 ORT 核心 DLL ──────────────────────────────────────────
        # 在 serious_python 嵌入式环境中，os.add_dll_directory() 对 .pyd 文件的
        # 间接依赖加载不生效（LOAD_LIBRARY_SEARCH_DEFAULT_DIRS 上下文不继承）。
        # 必须用 ctypes.CDLL 按绝对路径预加载，使 DLL 进入进程模块缓存。
        #
        # ctypes.CDLL(绝对路径) 加载时，Windows 将该 DLL 所在目录（capi/）加入本次
        # 搜索路径，所以 onnxruntime.dll 的所有依赖（DirectML、cudart、cublas 等）
        # 都会从 capi/ 中被自动找到——不需要逐个预加载这些大型 DLL。
        #
        # 加载顺序：providers_shared → providers_cuda（可选）→ onnxruntime
        #   providers_cuda 会传递加载 CUDA/cuDNN DLL（仅 CUDA 构建中存在，
        #   DirectML 构建中不存在该文件，自动跳过）
        import ctypes as _ctypes
        _ort_preload = [
            # DirectML 构建：onnxruntime.dll 依赖 DirectML.dll，必须先加载进模块缓存，
            # 否则 Windows 按名称搜索 "DirectML.dll" 时因 PATH 缓存问题找不到。
            # CUDA 构建中不存在此文件，自动跳过。
            "DirectML.dll",
            "onnxruntime_providers_shared.dll",
            # CUDA 构建：providers_cuda.dll 会传递加载 cudart/cublas/cudnn（均在 capi/ 中）。
            # DirectML 构建中不存在此文件，自动跳过。
            "onnxruntime_providers_cuda.dll",
            "onnxruntime.dll",
        ]
        for _name in _ort_preload:
            for _lp in lib_paths:
                _fp = _lp / _name
                if _fp.is_file():
                    try:
                        _ctypes.CDLL(str(_fp))
                        _diag(f"ORT 核心 DLL 已加载: {_name}")
                    except Exception as _e:
                        _diag(f"ORT 核心 DLL 加载失败: {_name} - {_e}")
                    break


    elif system == "Linux":
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in ld_path:
                ld_path = lib_path_str + os.pathsep + ld_path
                _diag(f"LD_LIBRARY_PATH 已添加: {lib_path}")
        if ld_path != os.environ.get('LD_LIBRARY_PATH', ''):
            os.environ['LD_LIBRARY_PATH'] = ld_path

    elif system == "Darwin":
        dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in dyld_path:
                dyld_path = lib_path_str + os.pathsep + dyld_path
                _diag(f"DYLD_LIBRARY_PATH 已添加: {lib_path}")
        if dyld_path != os.environ.get('DYLD_LIBRARY_PATH', ''):
            os.environ['DYLD_LIBRARY_PATH'] = dyld_path

    # ── 为 Nuitka 打包设置 FLET_VIEW_PATH ────────────────────────
    # Flet 0.84.0+ 通过 FLET_VIEW_PATH 查找客户端可执行文件。
    # build.py 将客户端打包到 exe 同级的 flet_client/ 目录，
    # 需在此设置环境变量以便 flet_desktop 找到它。
    # 仅当该目录真实存在时才设置（开发环境下不存在该目录，自动跳过）。
    if not os.environ.get("FLET_VIEW_PATH"):
        _exe_dir: Path | None = None
        if hasattr(sys, 'argv') and sys.argv and sys.argv[0]:
            _exe_dir = Path(sys.argv[0]).parent
        elif sys.executable:
            _exe_dir = Path(sys.executable).parent
        if _exe_dir is not None:
            _flet_client_dir = _exe_dir / "flet_client"
            if _flet_client_dir.is_dir():
                os.environ["FLET_VIEW_PATH"] = str(_flet_client_dir)
                _diag(f"FLET_VIEW_PATH 已设置: {_flet_client_dir}")

_patch_diagnostics: list[str] = []

# 执行库路径设置（捕获所有异常，避免中文路径等问题导致启动崩溃）
try:
    _setup_library_paths()
except Exception as _exc:
    _patch_diagnostics.append(f"_setup_library_paths 异常: {_exc}")

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