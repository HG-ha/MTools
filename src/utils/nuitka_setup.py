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
    则从打包的资源中解压到用户目录。
    
    支持的格式：
    - Windows: .flet.zip
    - macOS/Linux: .flet.tar.gz
    """
    is_compiled = _is_nuitka_compiled()
    
    if not is_compiled:
        return
        
    # 获取用户家目录
    home_dir = Path.home()
    flet_dir = home_dir / ".flet"
    
    # 如果 .flet 目录已存在，不需要做任何操作
    if flet_dir.exists():
        logger.info("[Flet Setup] .flet 目录已存在，跳过解压")
        return
        
    # 获取打包后程序的目录
    # 直接使用 sys.argv[0]，因为 Nuitka 打包不设置 sys.frozen
    app_dir = Path(sys.argv[0]).parent
    
    # 根据平台确定文件名和路径
    import platform as plat
    system = plat.system()
    
    if system == "Windows":
        file_names = [".flet.zip"]
        use_tar = False
    elif system in ["Darwin", "Linux"]:
        file_names = [".flet.tar.gz"]
        use_tar = True
    else:
        logger.warning(f"[Flet Setup] 不支持的平台: {system}")
        return
    
    # 尝试多个可能的位置
    flet_archive_path = None
    for file_name in file_names:
        possible_paths = [
            app_dir / "src" / "assets" / file_name,  # 标准路径
            app_dir / "assets" / file_name,  # 可能被提升到根目录
            app_dir / file_name,  # 直接在应用目录
        ]
        
        for path in possible_paths:
            if path.exists():
                flet_archive_path = path
                logger.info(f"[Flet Setup] 找到 Flet 打包文件: {path}")
                break
        
        if flet_archive_path:
            break
    
    if flet_archive_path is None:
        logger.warning("[Flet Setup] 未找到 Flet 打包文件，将从网络下载")
        return
    
    try:
        # 显示解压提示
        print("\n" + "="*60)
        print("🚀 MTools 首次启动 - 正在初始化 UI 引擎")
        print("="*60)
        print(f"📦 正在解压 Flet 客户端...")
        print(f"📂 目标位置: {flet_dir}")
        print("="*60)
        
        logger.info(f"[Flet Setup] 开始解压 {flet_archive_path} 到 {flet_dir}")
        
        # 创建 .flet 目录
        flet_dir.mkdir(parents=True, exist_ok=True)
        
        if use_tar:
            # 解压 tar.gz 文件（macOS/Linux）
            import tarfile
            with tarfile.open(flet_archive_path, 'r:gz') as tar_ref:
                # 获取文件总数
                members = tar_ref.getmembers()
                total_files = len(members)
                print(f"⏳ 解压中... (共 {total_files} 个文件)")
                
                # 解压所有文件
                for i, member in enumerate(members, 1):
                    tar_ref.extract(member, flet_dir)
                    # 每解压 100 个文件显示一次进度
                    if i % 100 == 0 or i == total_files:
                        percent = i * 100 / total_files
                        print(f"\r📥 进度: {percent:.1f}% ({i}/{total_files})", end='', flush=True)
                
                print("\n")
        else:
            # 解压 zip 文件（Windows）
            with zipfile.ZipFile(flet_archive_path, 'r') as zip_ref:
                # 获取文件总数
                total_files = len(zip_ref.namelist())
                print(f"⏳ 解压中... (共 {total_files} 个文件)")
                
                # 解压所有文件
                for i, member in enumerate(zip_ref.namelist(), 1):
                    zip_ref.extract(member, flet_dir)
                    # 每解压 100 个文件显示一次进度
                    if i % 100 == 0 or i == total_files:
                        percent = i * 100 / total_files
                        print(f"\r📥 进度: {percent:.1f}% ({i}/{total_files})", end='', flush=True)
                
                print("\n")
        
        print("="*60)
        print("✅ Flet 客户端解压完成！")
        print("="*60 + "\n")
        
        logger.info(f"[Flet Setup] 解压完成")
        
    except Exception as e:
        logger.error(f"[Flet Setup] 解压失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 如果解压失败，删除不完整的 .flet 目录
        if flet_dir.exists():
            try:
                import shutil
                shutil.rmtree(flet_dir)
                logger.info("[Flet Setup] 已清理不完整的 .flet 目录")
            except:
                pass


# 模块导入时自动执行初始化
_setup_flet_directory()
