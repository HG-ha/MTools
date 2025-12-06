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
    
    特别是在 Nuitka 打包后，需要正确设置库路径才能加载 CUDA。
    """
    import platform
    import site
    
    system = platform.system()
    
    # 检查是否启用调试模式
    debug_patch = os.environ.get('MYTOOLS_DEBUG_PATCH', '').lower() in ('1', 'true', 'yes')
    
    if debug_patch:
        print(f"DEBUG | 开始设置库路径... (平台: {system})")
    
    # 收集所有需要添加的库路径
    lib_paths = []
    
    # 1. 添加 ONNX Runtime 库路径（优先查找同目录或相对目录）
    try:
        # 先尝试找到 site-packages 中的 onnxruntime
        import onnxruntime
        onnxruntime_path = Path(onnxruntime.__file__).parent
        
        # 查找 ONNX Runtime 库文件目录
        ort_lib_path = onnxruntime_path / "capi"
        if not ort_lib_path.exists():
            ort_lib_path = onnxruntime_path
        
        if ort_lib_path.exists():
            lib_paths.append(ort_lib_path)
            if debug_patch:
                print(f"DEBUG | 找到 ONNX Runtime: {ort_lib_path}")
        
        # 对于打包后的程序，也检查相对路径
        if hasattr(sys, 'argv') and sys.argv[0]:
            app_dir = Path(sys.argv[0]).parent
            relative_ort_paths = [
                app_dir / "onnxruntime" / "capi",
                app_dir / "onnxruntime",
                app_dir / "src" / "onnxruntime" / "capi",
                app_dir / "src" / "onnxruntime",
            ]
            for relative_path in relative_ort_paths:
                if relative_path.exists() and relative_path not in lib_paths:
                    lib_paths.append(relative_path)
                    if debug_patch:
                        print(f"DEBUG | 找到本地 ONNX Runtime: {relative_path}")
    
    except ImportError:
        if debug_patch:
            print(f"DEBUG | onnxruntime 未安装")
        pass
    except Exception as e:
        if debug_patch:
            print(f"DEBUG | 查找 ONNX Runtime 出错: {e}")
        pass
    
    # 2. 添加 NVIDIA CUDA 库路径（用于 onnxruntime-gpu）
    try:
        site_packages = site.getsitepackages()
        if debug_patch:
            print(f"DEBUG | site-packages 路径数: {len(site_packages)}")
        
        for site_pkg in site_packages:
            nvidia_dir = Path(site_pkg) / "nvidia"
            if nvidia_dir.exists():
                if debug_patch:
                    print(f"DEBUG | 找到 NVIDIA 目录: {nvidia_dir}")
                
                # 查找所有 NVIDIA 子包的 bin 或 lib 目录
                for subdir in nvidia_dir.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith('_'):
                        # Windows 使用 bin/, Linux 使用 lib/
                        bin_dir = subdir / "bin" if system == "Windows" else subdir / "lib"
                        if bin_dir.exists():
                            lib_paths.append(bin_dir)
                            if debug_patch:
                                print(f"DEBUG | 找到 NVIDIA 库: {bin_dir}")
                break
    except Exception as e:
        if debug_patch:
            print(f"DEBUG | 查找 NVIDIA CUDA 库出错: {e}")
        pass
    
    # 3. 对于打包后的程序，也检查相对的 nvidia 目录
    if hasattr(sys, 'argv') and sys.argv[0]:
        try:
            app_dir = Path(sys.argv[0]).parent
            relative_nvidia_dir = app_dir / "nvidia"
            if relative_nvidia_dir.exists():
                if debug_patch:
                    print(f"DEBUG | 找到本地 NVIDIA 目录: {relative_nvidia_dir}")
                
                for subdir in relative_nvidia_dir.iterdir():
                    if subdir.is_dir() and not subdir.name.startswith('_'):
                        bin_dir = subdir / "bin" if system == "Windows" else subdir / "lib"
                        if bin_dir.exists() and bin_dir not in lib_paths:
                            lib_paths.append(bin_dir)
                            if debug_patch:
                                print(f"DEBUG | 找到本地 NVIDIA 库: {bin_dir}")
        except Exception as e:
            if debug_patch:
                print(f"DEBUG | 查找本地 NVIDIA 目录出错: {e}")
            pass
    
    # 3. 应用库路径
    if not lib_paths:
        if debug_patch:
            print(f"DEBUG | 未找到任何库路径，跳过配置")
        return
    
    if debug_patch:
        print(f"DEBUG | 共找到 {len(lib_paths)} 个库路径")
    
    if system == "Windows":
        # Windows: 设置 DLL 搜索路径
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            
            # Python 3.8+ 推荐使用 os.add_dll_directory
            if sys.version_info >= (3, 8):
                try:
                    os.add_dll_directory(lib_path_str)
                    if debug_patch:
                        print(f"DEBUG | DLL 目录已添加: {lib_path}")
                except Exception as e:
                    if debug_patch:
                        print(f"DEBUG | DLL 目录添加失败: {lib_path} - {e}")
            
            # 同时设置 PATH 环境变量（兼容旧版本 Python 和其他工具）
            if lib_path_str not in os.environ.get('PATH', ''):
                os.environ['PATH'] = lib_path_str + os.pathsep + os.environ.get('PATH', '')
                if debug_patch:
                    print(f"DEBUG | PATH 已更新: {lib_path}")
    
    elif system == "Linux":
        # Linux: 设置 LD_LIBRARY_PATH
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in ld_path:
                ld_path = lib_path_str + os.pathsep + ld_path
                if debug_patch:
                    print(f"DEBUG | LD_LIBRARY_PATH 已添加: {lib_path}")
        if ld_path != os.environ.get('LD_LIBRARY_PATH', ''):
            os.environ['LD_LIBRARY_PATH'] = ld_path
            if debug_patch:
                print(f"DEBUG | LD_LIBRARY_PATH 已设置")
    
    elif system == "Darwin":
        # macOS: 设置 DYLD_LIBRARY_PATH
        dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        for lib_path in lib_paths:
            lib_path_str = str(lib_path)
            if lib_path_str not in dyld_path:
                dyld_path = lib_path_str + os.pathsep + dyld_path
                if debug_patch:
                    print(f"DEBUG | DYLD_LIBRARY_PATH 已添加: {lib_path}")
        if dyld_path != os.environ.get('DYLD_LIBRARY_PATH', ''):
            os.environ['DYLD_LIBRARY_PATH'] = dyld_path
            if debug_patch:
                print(f"DEBUG | DYLD_LIBRARY_PATH 已设置")

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