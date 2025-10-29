"""Nuitka 打包程序的初始化设置。

该模块会在导入时自动执行，检测是否为 Nuitka 打包的程序，
如果是且用户目录下没有 .flet 目录，则从打包的资源中解压。
"""

import sys
import zipfile
from pathlib import Path


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
    
    # 调试信息
    print(f"[Nuitka Setup] Executable: {sys.argv[0]}")
    print(f"[Nuitka Setup] Is compiled: {is_compiled}")
    
    if not is_compiled:
        print("[Nuitka Setup] Not a nuitka compiled program, skip setup .flet directory")
        return
    
    print("[Nuitka Setup] Nuitka compiled program detected!")
    
    # 获取用户家目录
    home_dir = Path.home()
    flet_dir = home_dir / ".flet"
    
    # 如果 .flet 目录已存在，不需要做任何操作
    if flet_dir.exists():
        print(f"[Nuitka Setup] .flet directory already exists at {flet_dir}")
        return
    
    print(f"[Nuitka Setup] .flet directory not found, setting up...")
    
    # 获取打包后程序的目录
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包
        app_dir = Path(sys.executable).parent
    else:
        # Nuitka 打包
        app_dir = Path(sys.argv[0]).parent
    
    # .flet.zip 文件路径
    flet_zip_path = app_dir / "src" / "assets" / ".flet.zip"
    
    print(f"[Nuitka Setup] App directory: {app_dir}")
    print(f"[Nuitka Setup] Looking for .flet.zip at: {flet_zip_path}")
    
    # 检查 zip 文件是否存在
    if not flet_zip_path.exists():
        print(f"[Nuitka Setup] ERROR: .flet.zip not found at {flet_zip_path}")
        return
    
    try:
        # 创建 .flet 目录
        flet_dir.mkdir(parents=True, exist_ok=True)
        
        # 解压 zip 文件到用户目录
        with zipfile.ZipFile(flet_zip_path, 'r') as zip_ref:
            zip_ref.extractall(flet_dir)
        
        print(f"[Nuitka Setup] Successfully extracted .flet directory to {flet_dir}")
    except Exception as e:
        print(f"[Nuitka Setup] ERROR setting up .flet directory: {e}")


# 模块导入时自动执行初始化
_setup_flet_directory()

