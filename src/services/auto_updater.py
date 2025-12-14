# -*- coding: utf-8 -*-
"""自动更新模块。

提供完整的自动更新功能，包括下载、解压和应用更新。
"""

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

import httpx

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .update_service import UpdateService, UpdateInfo, UpdateStatus
from utils import logger


def _is_packaged_app() -> bool:
    """判断当前是否为打包后的应用程序。
    
    Returns:
        True 表示是打包后的应用，False 表示是开发环境
    """
    exe_name = os.path.basename(sys.executable).lower()
    
    # Windows: 检查是否为 .exe 且不是 python.exe
    if sys.executable.endswith('.exe'):
        return exe_name not in ['python.exe', 'python3.exe', 'pythonw.exe']
    
    # Unix/Linux/macOS: 检查是否不是 python 解释器
    return exe_name not in ['python', 'python3', 'python2']


class AutoUpdater:
    """自动更新器。
    
    负责下载更新包、解压并应用更新。
    支持 Windows (.zip) 和 Linux/macOS (.tar.gz) 格式。
    """
    
    # 下载超时时间（秒）
    DOWNLOAD_TIMEOUT = 300
    # 下载块大小
    CHUNK_SIZE = 8192
    
    def __init__(self) -> None:
        """初始化自动更新器。"""
        self.update_service = UpdateService()
        # 启动时清理旧的临时文件
        self._cleanup_old_temp_files()
    
    async def download_update(
        self,
        download_url: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """下载更新包。
        
        Args:
            download_url: 下载地址
            progress_callback: 进度回调函数，接收 (已下载字节数, 总字节数)
        
        Returns:
            下载文件的路径
        
        Raises:
            Exception: 下载失败时抛出异常
        """
        # 创建临时目录
        temp_dir = Path(tempfile.mkdtemp(prefix="mtools_update_"))
        
        # 从 URL 提取文件名
        filename = download_url.split('/')[-1]
        if not filename.endswith(('.zip', '.tar.gz')):
            # 根据平台设置默认扩展名
            ext = '.zip' if platform.system() == 'Windows' else '.tar.gz'
            filename = f"update{ext}"
        
        download_path = temp_dir / filename
        
        try:
            async with httpx.AsyncClient(timeout=self.DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
                async with client.stream('GET', download_url) as response:
                    response.raise_for_status()
                    
                    # 获取文件总大小
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    # 下载文件
                    with open(download_path, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=self.CHUNK_SIZE):
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 调用进度回调
                            if progress_callback:
                                progress_callback(downloaded_size, total_size)
            
            return download_path
        
        except Exception as e:
            # 清理临时文件
            if download_path.exists():
                download_path.unlink()
            raise Exception(f"下载更新失败: {str(e)}")
    
    def extract_update(self, archive_path: Path, extract_dir: Optional[Path] = None) -> Path:
        """解压更新包。
        
        Args:
            archive_path: 压缩包路径
            extract_dir: 解压目标目录，默认为压缩包所在目录
        
        Returns:
            解压后的目录路径
        
        Raises:
            Exception: 解压失败时抛出异常
        """
        if extract_dir is None:
            extract_dir = archive_path.parent / "extracted"
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if archive_path.suffix == '.zip':
                # 解压 ZIP 文件
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive_path.name.endswith('.tar.gz'):
                # 解压 tar.gz 文件
                import tarfile
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                raise Exception(f"不支持的压缩格式: {archive_path.suffix}")
            
            # 解压成功后立即删除压缩包以节省空间
            try:
                archive_path.unlink()
            except Exception:
                pass  # 删除失败也不影响后续流程
            
            return extract_dir
        
        except Exception as e:
            raise Exception(f"解压更新包失败: {str(e)}")
    
    def apply_update(self, extract_dir: Path, exit_callback: Optional[Callable[[], None]] = None) -> None:
        """应用更新。
        
        创建更新脚本并重启应用以应用更新。
        
        Args:
            extract_dir: 解压后的更新文件目录
            exit_callback: 自定义退出回调函数，用于优雅关闭应用（如果不提供则使用强制退出）
        
        Raises:
            Exception: 应用更新失败时抛出异常
        """
        try:
            # 获取当前应用目录
            if _is_packaged_app():
                # 打包后的应用：使用可执行文件所在目录
                app_dir = Path(sys.executable).parent
            else:
                # 开发环境（Python 解释器）：使用当前工作目录
                app_dir = Path(os.getcwd())
            
            # 创建更新脚本
            if platform.system() == 'Windows':
                self._create_windows_update_script(extract_dir, app_dir, exit_callback)
            else:
                self._create_unix_update_script(extract_dir, app_dir, exit_callback)
            
        except Exception as e:
            raise Exception(f"应用更新失败: {str(e)}")
    
    def _create_windows_update_script(self, source_dir: Path, target_dir: Path, exit_callback: Optional[Callable[[], None]] = None) -> None:
        """创建 Windows 更新脚本。
        
        Args:
            source_dir: 更新文件源目录
            target_dir: 应用安装目录
            exit_callback: 自定义退出回调函数
        """
        script_path = source_dir.parent / "update.bat"
        
        # 查找解压后的实际文件夹（可能有嵌套）
        update_files = list(source_dir.rglob("*.exe"))
        
        if not update_files:
            # 如果没找到 exe，说明可能是嵌套目录结构
            # 尝试在子目录中查找
            subdirs = [d for d in source_dir.iterdir() if d.is_dir()]
            if subdirs:
                # 可能解压后有嵌套目录，如 MTools_Windows_amd64/
                for subdir in subdirs:
                    update_files = list(subdir.rglob("*.exe"))
                    if update_files:
                        break
        
        if update_files:
            # 找到主程序 exe 的实际所在目录（包含所有需要的文件）
            main_exe = update_files[0]
            
            # 向上查找，直到找到包含所有必要文件的根目录
            # 通常是包含 .exe、assets、data 等的目录
            actual_source = main_exe.parent
            
            # 检查是否还有父目录只包含这一个子目录（说明是嵌套结构）
            # 如果父目录只有一个子目录，那么实际源就是这个子目录，而不是父目录
            parent = actual_source.parent
            if parent != source_dir:
                # 如果父目录就是 source_dir，检查 source_dir 是否只有一个子目录
                if parent == source_dir and len(list(source_dir.iterdir())) == 1:
                    # source_dir 只有一个子目录，说明是嵌套的，使用子目录
                    pass  # actual_source 已经是正确的
                elif len(list(parent.iterdir())) == 1:
                    # 父目录只有一个子目录，说明 actual_source 是正确的
                    pass
            
            if not _is_packaged_app():
                logger.debug(f"找到更新程序: {main_exe}")
                logger.debug(f"实际源目录: {actual_source}")
        else:
            actual_source = source_dir
            # 尝试找到主程序（根据当前运行的程序名）
            exe_name = Path(sys.executable).name if _is_packaged_app() else "MTools.exe"
            main_exe = target_dir / exe_name
            if not _is_packaged_app():
                logger.warning(f"未在更新包中找到 exe 文件，使用默认: {exe_name}")
        
        # 获取所有需要终止的进程名
        # 对于 Flet 应用，需要同时终止主程序和 flet.exe
        process_names = set()
        
        if HAS_PSUTIL:
            try:
                current_process = psutil.Process()
                # 添加当前进程名
                process_names.add(current_process.name())
                
                # 获取所有子进程（Flet 渲染进程等）
                for child in current_process.children(recursive=True):
                    process_names.add(child.name())
                
                # 如果当前进程有父进程，也添加父进程名（可能是 flet.exe）
                try:
                    parent_process = current_process.parent()
                    if parent_process and parent_process.name().lower() in ['flet.exe', 'pythonw.exe', 'python.exe']:
                        process_names.add(parent_process.name())
                except:
                    pass
            except Exception as e:
                if not _is_packaged_app():
                    logger.warning(f"获取进程信息失败: {e}")
                # 后备方案
                process_names.add(Path(sys.executable).name)
        else:
            # 后备方案：使用可执行文件名
            process_names.add(Path(sys.executable).name)
        
        # 添加常见的 Flet 相关进程名
        process_names.add("flet.exe")
        process_names.add("fletd.exe")
        
        # 目标主程序路径和名称
        exe_name = main_exe.name
        
        # 生成终止进程的命令
        kill_commands = []
        for pname in process_names:
            kill_commands.append(f'taskkill /f /im "{pname}" >nul 2>&1')
        kill_commands_str = '\n'.join(kill_commands)
        
        script_content = f'''@echo off
chcp 936 >nul
echo ========================================
echo MTools 自动更新程序
echo ========================================
echo.
echo 源目录: {actual_source}
echo 目标目录: {target_dir}
echo 程序名称: {exe_name}
echo.

echo [1/5] 等待主程序退出 (3秒)...
timeout /t 3 /nobreak >nul

echo [2/4] 强制终止所有相关进程...
{kill_commands_str}
echo 等待进程完全退出...
timeout /t 2 /nobreak >nul

echo [3/4] 安装新版本...
REM 删除旧文件
for /d %%i in ("{target_dir}\\*") do rmdir /s /q "%%i" >nul 2>&1
del /f /q "{target_dir}\\*" >nul 2>&1

REM 复制新版本文件
xcopy /s /e /i /y /q "{actual_source}\\*" "{target_dir}\\" >nul
if errorlevel 1 (
    echo 错误：复制文件失败！更新中止。
    echo 请手动下载更新包并解压到应用目录。或尝试以管理员方式重新运行程序。
    pause
    exit /b 1
)

echo [4/4] 清理临时文件...
rmdir /s /q "{source_dir.parent}" 2>nul

echo.
echo ========================================
echo 更新完成！正在启动新版本...
echo ========================================
timeout /t 1 /nobreak >nul

REM 切换到目标目录
cd /d "{target_dir}"
if errorlevel 1 (
    echo 切换目录失败！
    pause
    exit /b 1
)

REM 检查程序是否存在
if not exist "{exe_name}" (
    echo 错误：找不到程序文件 {exe_name}
    pause
    exit /b 1
)

echo 正在启动: %CD%\\{exe_name}

REM 启动新版本
start "" "{exe_name}"

REM 等待程序启动
timeout /t 2 /nobreak >nul

REM 自删除脚本
(goto) 2>nul & del /f /q "%~f0" 2>nul

exit /b 0
'''
        
        with open(script_path, 'w', encoding='gbk') as f:  # 使用 GBK 编码避免乱码
            f.write(script_content)
        
        # 打印调试信息（开发环境）
        if not _is_packaged_app():
            logger.debug(f"更新脚本已创建: {script_path}")
            logger.debug(f"目标目录: {target_dir}")
            logger.debug(f"程序名称: {exe_name}")
            logger.debug(f"需要终止的进程: {', '.join(process_names)}")
        
        # 执行更新脚本 - 使用后台方式启动，延迟3秒后执行
        # 这样主程序可以立即退出，不会被脚本阻塞
        try:
            if not _is_packaged_app():
                # 开发环境：显示窗口便于调试
                subprocess.Popen(
                    ['cmd', '/c', 'start', 'cmd', '/c', str(script_path)],
                    cwd=str(script_path.parent)
                )
            else:
                # 生产环境：完全后台运行
                subprocess.Popen(
                    ['cmd', '/c', str(script_path)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    cwd=str(script_path.parent),
                    close_fds=True
                )
            logger.info("更新脚本已启动，主程序即将退出")
        except Exception as e:
            logger.error(f"启动更新脚本失败: {e}")
            raise
        
        # 退出当前应用
        if exit_callback:
            # 使用自定义退出回调（优雅关闭）
            try:
                exit_callback()
            except Exception as e:
                logger.warning(f"自定义退出回调失败: {e}，使用强制退出")
                self._force_exit_application()
        else:
            # 对于 Flet 应用，需要强制终止所有相关进程
            self._force_exit_application()
    
    def _force_exit_application(self) -> None:
        """强制退出应用程序（包括所有子进程）。
        
        对于 Flet 应用，需要终止主进程和所有渲染进程。
        使用多种方法确保应用完全退出。
        """
        import os
        
        if HAS_PSUTIL:
            try:
                current_process = psutil.Process()
                
                # 1. 先尝试终止所有子进程
                children = current_process.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # 等待子进程退出
                gone, alive = psutil.wait_procs(children, timeout=1)
                
                # 2. 强制杀死还活着的子进程
                for p in alive:
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # 3. 如果有父进程且是 flet.exe，也终止它
                try:
                    parent = current_process.parent()
                    if parent and parent.name().lower() in ['flet.exe', 'fletd.exe']:
                        parent.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                
            except Exception as e:
                if not _is_packaged_app():
                    logger.warning(f"清理子进程失败: {e}")
        
        # 4. 最后强制退出当前进程
        # 使用 os._exit 而不是 sys.exit，确保立即退出，不执行清理
        os._exit(0)
    
    def _create_unix_update_script(self, source_dir: Path, target_dir: Path, exit_callback: Optional[Callable[[], None]] = None) -> None:
        """创建 Unix/Linux/macOS 更新脚本。
        
        Args:
            source_dir: 更新文件源目录
            target_dir: 应用安装目录
            exit_callback: 自定义退出回调函数
        """
        script_path = source_dir.parent / "update.sh"
        
        # 查找解压后的实际文件夹（可能有嵌套）
        update_files = list(source_dir.rglob("*"))
        executables = [f for f in update_files if f.is_file() and os.access(f, os.X_OK)]
        if executables:
            actual_source = executables[0].parent
            main_exe = executables[0]
        else:
            actual_source = source_dir
            main_exe = target_dir / "main"
        
        # 获取当前进程名
        if HAS_PSUTIL:
            current_process = psutil.Process()
            process_name = current_process.name()
        else:
            # 后备方案：使用可执行文件名
            process_name = Path(sys.executable).name
        
        # 目标主程序路径
        target_exe = target_dir / main_exe.name
        
        script_content = f'''#!/bin/bash
echo "========================================"
echo "MTools 自动更新程序"
echo "========================================"
echo ""
echo "[1/5] 等待主程序退出..."
sleep 3

echo "[2/4] 强制终止主程序进程..."
pkill -9 -f "{process_name}" || true
sleep 2

echo "[3/4] 安装新版本..."
REM 删除旧文件
rm -rf "{target_dir}"/* 2>/dev/null || true

REM 复制新版本文件
cp -rf "{actual_source}"/* "{target_dir}/" || {{
    echo "错误：复制文件失败！更新中止。"
    echo "请手动下载更新包并解压到应用目录。"
    exit 1
}}

chmod +x "{target_exe}"

echo "[4/4] 清理临时文件..."
rm -rf "{source_dir.parent}" 2>/dev/null || true

echo ""
echo "========================================"
echo "更新完成！正在启动新版本..."
echo "========================================"
echo "目标程序: {target_exe}"
sleep 2

# 切换到目标目录
cd "{target_dir}" || exit 1
echo "当前目录: $(pwd)"
echo "启动程序: {target_exe.name}"

# 确保程序有执行权限
chmod +x "{target_exe.name}"

# 使用 nohup 后台启动程序
nohup "./{target_exe.name}" > /dev/null 2>&1 &
LAUNCH_PID=$!
echo "程序 PID: $LAUNCH_PID"

# 等待应用启动
sleep 3

# 删除更新脚本自身
rm -f "$0" 2>/dev/null || true

exit 0
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 添加执行权限
        os.chmod(script_path, 0o755)
        
        # 执行更新脚本
        subprocess.Popen(['/bin/bash', str(script_path)], start_new_session=True)
        
        # 退出当前应用
        if exit_callback:
            # 使用自定义退出回调（优雅关闭）
            try:
                exit_callback()
            except Exception as e:
                logger.warning(f"自定义退出回调失败: {e}，使用强制退出")
                self._force_exit_application()
        else:
            # 对于 Flet 应用，需要强制终止所有相关进程
            self._force_exit_application()
    
    async def check_and_download_update(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> tuple[UpdateInfo, Optional[Path]]:
        """检查更新并下载。
        
        Args:
            progress_callback: 下载进度回调函数
        
        Returns:
            (更新信息, 下载文件路径)，如果没有更新则返回 (更新信息, None)
        """
        # 检查更新
        update_info = await self.update_service.check_update_async()
        
        if update_info.status != UpdateStatus.UPDATE_AVAILABLE:
            return update_info, None
        
        if not update_info.download_url:
            return update_info, None
        
        # 下载更新
        try:
            download_path = await self.download_update(
                update_info.download_url,
                progress_callback
            )
            return update_info, download_path
        except Exception as e:
            # 下载失败，更新错误信息
            update_info.status = UpdateStatus.ERROR
            update_info.error_message = str(e)
            return update_info, None
    
    async def full_update_process(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        extract_callback: Optional[Callable[[], None]] = None,
        apply_callback: Optional[Callable[[], None]] = None,
        exit_callback: Optional[Callable[[], None]] = None
    ) -> UpdateInfo:
        """完整的更新流程：检查 -> 下载 -> 解压 -> 应用。
        
        Args:
            progress_callback: 下载进度回调
            extract_callback: 解压开始回调
            apply_callback: 应用更新开始回调
            exit_callback: 自定义退出回调函数，用于优雅关闭应用
        
        Returns:
            更新信息
        """
        # 检查并下载
        update_info, download_path = await self.check_and_download_update(progress_callback)
        
        if not download_path:
            return update_info
        
        try:
            # 解压
            if extract_callback:
                extract_callback()
            
            extract_dir = self.extract_update(download_path)
            
            # 应用更新
            if apply_callback:
                apply_callback()
            
            self.apply_update(extract_dir, exit_callback)
            
            # 注意：apply_update 会退出应用，下面的代码不会执行
            return update_info
        
        except Exception as e:
            update_info.status = UpdateStatus.ERROR
            update_info.error_message = str(e)
            return update_info
    
    def _cleanup_old_temp_files(self) -> None:
        """清理旧的更新临时文件。
        
        在应用启动时调用，清理之前失败的更新留下的临时文件。
        """
        try:
            temp_base = Path(tempfile.gettempdir())
            
            # 查找所有以 mtools_update_ 开头的临时目录
            for temp_dir in temp_base.glob("mtools_update_*"):
                if temp_dir.is_dir():
                    try:
                        # 检查目录是否超过1天
                        import time
                        dir_age = time.time() - temp_dir.stat().st_mtime
                        if dir_age > 86400:  # 超过24小时
                            shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass  # 忽略单个目录清理失败
            
            # 清理旧的更新脚本（Windows）
            if platform.system() == 'Windows':
                for script in temp_base.glob("update*.bat"):
                    try:
                        script_age = time.time() - script.stat().st_mtime
                        if script_age > 86400:
                            script.unlink()
                    except Exception:
                        pass
            
            # 清理旧的更新脚本（Unix）
            else:
                for script in temp_base.glob("update*.sh"):
                    try:
                        script_age = time.time() - script.stat().st_mtime
                        if script_age > 86400:
                            script.unlink()
                    except Exception:
                        pass
        
        except Exception:
            # 清理失败不影响应用启动
            pass


# 便捷函数
async def check_for_updates() -> UpdateInfo:
    """检查更新的便捷函数。"""
    updater = AutoUpdater()
    return await updater.update_service.check_update_async()


async def auto_update(
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> UpdateInfo:
    """自动更新的便捷函数。
    
    Args:
        progress_callback: 下载进度回调
    
    Returns:
        更新信息
    """
    updater = AutoUpdater()
    return await updater.full_update_process(progress_callback)
