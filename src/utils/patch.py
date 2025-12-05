import subprocess
import sys
import warnings
import os
from pathlib import Path

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
    
    在程序启动时自动配置库路径，解决：
    1. sherpa-onnx 可能使用错误版本的 ONNX Runtime
    2. onnxruntime-gpu 找不到 CUDA 库（cudnn、cublas 等）
    """
    import platform
    import site
    
    system = platform.system()
    
    # 收集所有需要添加的库路径
    lib_paths = []
    
    # 1. 添加 ONNX Runtime 库路径
    try:
        import onnxruntime
        onnxruntime_path = Path(onnxruntime.__file__).parent
        
        # 查找 ONNX Runtime 库文件目录
        ort_lib_path = onnxruntime_path / "capi"
        if not ort_lib_path.exists():
            ort_lib_path = onnxruntime_path
        
        if ort_lib_path.exists():
            lib_paths.append(ort_lib_path)
    
    except ImportError:
        pass  # onnxruntime 未安装
    except Exception:
        pass
    
    # 2. 添加 NVIDIA CUDA 库路径（用于 onnxruntime-gpu）
    try:
        site_packages = site.getsitepackages()
        for site_pkg in site_packages:
            nvidia_dir = Path(site_pkg) / "nvidia"
            if nvidia_dir.exists():
                # 查找所有 NVIDIA 子包的 bin 或 lib 目录
                for subdir in nvidia_dir.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith('_'):
                        # Windows 使用 bin/, Linux 使用 lib/
                        bin_dir = subdir / "bin" if system == "Windows" else subdir / "lib"
                        if bin_dir.exists():
                            lib_paths.append(bin_dir)
                break
    except Exception:
        pass
    
    # 3. 应用库路径
    if not lib_paths:
        return
    
    try:
        if system == "Windows":
            # Windows: 设置 DLL 搜索路径
            for lib_path in lib_paths:
                # Python 3.8+ 推荐使用 os.add_dll_directory
                if sys.version_info >= (3, 8):
                    try:
                        os.add_dll_directory(str(lib_path))
                    except Exception:
                        pass
                
                # 同时设置 PATH 环境变量（兼容旧版本 Python）
                if str(lib_path) not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = str(lib_path) + os.pathsep + os.environ.get('PATH', '')
        
        elif system == "Linux":
            # Linux: 设置 LD_LIBRARY_PATH
            ld_path = os.environ.get('LD_LIBRARY_PATH', '')
            for lib_path in lib_paths:
                if str(lib_path) not in ld_path:
                    ld_path = str(lib_path) + os.pathsep + ld_path
            os.environ['LD_LIBRARY_PATH'] = ld_path
        
        elif system == "Darwin":
            # macOS: 设置 DYLD_LIBRARY_PATH
            dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
            for lib_path in lib_paths:
                if str(lib_path) not in dyld_path:
                    dyld_path = str(lib_path) + os.pathsep + dyld_path
            os.environ['DYLD_LIBRARY_PATH'] = dyld_path
    
    except Exception:
        pass

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