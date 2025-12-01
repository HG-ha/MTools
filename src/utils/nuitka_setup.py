# -*- coding: utf-8 -*-
"""Nuitka 打包程序的初始化设置。

该模块会在导入时自动执行，检测是否为 Nuitka 打包的程序，
如果是且用户目录下没有 .flet 目录，则从打包的资源中解压。
"""

import sys
import zipfile
from pathlib import Path
from utils import logger


def _is_nuitka_compiled() -> bool:
    """检测是否是 nuitka 打包的程序。
    
    直接判断 sys.argv[0] 是否为 .exe 可执行文件。
    
    Returns:
        bool: 如果是打包的程序返回 True，否则返回 False
    """
    # sys.argv[0] 为可执行文件的路径，扩展名是 .exe
    exe_path = Path(sys.argv[0])
    return exe_path.suffix.lower() == '.exe'


def _setup_flet_directory() -> None:
    """设置 Flet 目录。
    
    如果是 nuitka 打包的程序且用户目录下没有 .flet 目录，
    则从 src/assets/.flet.zip 解压到用户目录。
    """
    is_compiled = _is_nuitka_compiled()
    
    
    if not is_compiled:
        return
        
    # 获取用户家目录
    home_dir = Path.home()
    flet_dir = home_dir / ".flet"
    
    # 如果 .flet 目录已存在，不需要做任何操作
    if flet_dir.exists():
        return
        
    # 获取打包后程序的目录
    # 直接使用 sys.argv[0]，因为 Nuitka 打包不设置 sys.frozen
    app_dir = Path(sys.argv[0]).parent
    
    # .flet.zip 文件路径 - 尝试多个可能的位置
    possible_paths = [
        app_dir / "src" / "assets" / ".flet.zip",  # 标准路径
        app_dir / "assets" / ".flet.zip",  # 可能被提升到根目录
        app_dir / ".flet.zip",  # 直接在应用目录
    ]
    
    flet_zip_path = None
    for path in possible_paths:
        if path.exists():
            flet_zip_path = path
            break
    
    if flet_zip_path is None:
        return
    
    try:
        # 创建 .flet 目录
        flet_dir.mkdir(parents=True, exist_ok=True)
        
        # 解压 zip 文件到用户目录
        with zipfile.ZipFile(flet_zip_path, 'r') as zip_ref:
            zip_ref.extractall(flet_dir)
        
    except Exception as e:
        import traceback
        traceback.print_exc()

def _disable_flet_auto_download() -> None:
    """禁用 flet 的自动下载功能。
    
    通过 monkey patch 的方式，让 flet_desktop 的下载函数失效，
    强制使用本地打包的 flet 可执行文件。
    """
    try:
        import flet_desktop
        import sys
        
        # 定义一个替代函数，永远抛出异常阻止下载
        def blocked_download(file_name):
            error_msg = (
                f"\n{'='*60}\n"
                f"🚫 BLOCKED: Attempt to download {file_name}\n"
                f"{'='*60}\n"
                f"This application should use pre-packaged flet executable.\n"
                f"If you see this error, the .flet directory setup failed.\n"
                f"Please check:\n"
                f"  1. .flet.zip was correctly packaged in the build\n"
                f"  2. .flet.zip was successfully extracted to ~/.flet\n"
                f"  3. flet version matches the packaged version\n"
                f"{'='*60}\n"
            )
            raise RuntimeError(
                "Flet auto-download is disabled in packaged application. "
                "Please ensure .flet directory is properly set up."
            )
        
        # 替换下载函数 - 需要处理 name mangling
        # Python 会将 __download_flet_client 改名为 _ClassName__download_flet_client
        # 但这里是模块级函数，所以直接替换模块中的函数
        module_name = flet_desktop.__name__
        
        # 尝试多种可能的函数名
        possible_names = [
            '__download_flet_client',
            '_flet_desktop__download_flet_client',
            'download_flet_client',
        ]
        
        patched = False
        for func_name in possible_names:
            if hasattr(flet_desktop, func_name):
                setattr(flet_desktop, func_name, blocked_download)
                patched = True
        
        if not patched:
            logger.error("[Nuitka Setup] ⚠️  Could not find download function to patch")
            logger.error(f"[Nuitka Setup] Available functions: {[x for x in dir(flet_desktop) if 'download' in x.lower()]}")
            
    except ImportError:
        # flet_desktop 还未导入，使用 import hook
        _install_import_hook()
    except Exception as e:
        import traceback
        traceback.print_exc()


def _install_import_hook() -> None:
    """安装导入钩子，在 flet_desktop 被导入时自动 patch。"""
    import sys
    from importlib.abc import MetaPathFinder, Loader
    from importlib.util import spec_from_loader
    
    class FletDesktopPatcher(MetaPathFinder):
        """flet_desktop 导入拦截器"""
        
        def find_spec(self, fullname, path, target=None):
            if fullname == 'flet_desktop':
                # 先让正常导入完成，然后再 patch
                return None  # 让正常的导入机制处理
            return None
        
        def find_module(self, fullname, path=None):
            return None
    
    # 实际上，更简单的方法是使用 sys.modules 的 hook
    # 但由于 flet_desktop 可能已经被导入，我们采用延迟 patch
    # 这里先注册，稍后在真正使用时再 patch
    
    original_import = __builtins__.__import__
    
    def hooked_import(name, *args, **kwargs):
        module = original_import(name, *args, **kwargs)
        if name == 'flet_desktop' and _is_nuitka_compiled():
            # 导入后立即 patch
            try:
                _disable_flet_auto_download()
            except:
                pass
        return module
    
    __builtins__.__import__ = hooked_import

# 模块导入时自动执行初始化
_setup_flet_directory()

# 禁用 flet 自动下载（仅在编译模式下）
if _is_nuitka_compiled():
    _disable_flet_auto_download()

