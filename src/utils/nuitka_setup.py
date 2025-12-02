# -*- coding: utf-8 -*-
"""Flet 下载加速设置。

该模块会在导入时自动执行，为中国用户启用 GitHub 镜像加速下载。
"""

from pathlib import Path
from utils import logger


def _show_system_notification(title: str, message: str) -> None:
    """显示系统桌面通知（跨平台，不依赖 tkinter）。
    
    Args:
        title: 通知标题
        message: 通知内容
    """
    import platform
    import subprocess
    
    system = platform.system()
    
    try:
        if system == "Windows":
            # Windows: 使用 PowerShell Toast 通知
            try:
                ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">{title}</text>
            <text id="2">{message}</text>
        </binding>
    </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("MTools")
$notifier.Show($toast)
'''
                subprocess.Popen(
                    ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_script],
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except:
                pass
        
        elif system == "Darwin":
            # macOS: 使用 osascript 显示通知
            subprocess.Popen(
                ['osascript', '-e', f'display notification "{message}" with title "{title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        elif system == "Linux":
            # Linux: 使用 notify-send
            subprocess.Popen(
                ['notify-send', title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except:
        # 通知失败不影响主流程
        pass


def _is_china_user() -> bool:
    """检测是否为中国用户。
    
    通过多种方式检测：
    1. 系统时区
    2. 系统语言
    3. 环境变量
    
    Returns:
        bool: 如果可能是中国用户返回 True
    """
    import locale
    import time
    import os
    
    try:
        # 方法 1: 检查时区（检查中文字符串）
        timezone = time.tzname
        for tz in timezone:
            # 检查是否包含中文或中国相关关键词
            if '中国' in tz or 'China' in tz or 'CST' in tz or 'Asia/Shanghai' in tz:
                return True
        
        # 方法 2: 检查系统语言
        try:
            # 使用新 API: locale.getlocale()
            lang, encoding = locale.getlocale()
            if lang:
                lang_lower = lang.lower()
                # 支持多种格式：
                # - Windows: 'Chinese (Simplified)_China', 'Chinese_China'
                # - Linux/macOS: 'zh_CN', 'zh_Hans'
                if any(keyword in lang_lower for keyword in ['zh_cn', 'zh_hans', 'chinese', 'china']):
                    return True
        except:
            pass
        
        # 方法 3: 检查环境变量（LANG, LC_ALL）
        for env_var in ['LANG', 'LC_ALL', 'LANGUAGE']:
            lang_env = os.environ.get(env_var, '').lower()
            if 'zh_cn' in lang_env or 'zh_hans' in lang_env or 'chinese' in lang_env:
                return True
            
    except Exception:
        pass
    
    return False


def _patch_flet_download_for_china() -> None:
    """为中国用户修改 flet 下载函数，使用 gh-proxy.org 加速。
    
    通过 monkey patch 的方式，将 GitHub releases 的下载链接
    替换为 gh-proxy.org 代理链接，加速中国用户的下载，并显示桌面通知。
    """
    try:
        import flet_desktop
        import urllib.request
        import tempfile
        from pathlib import Path
        
        # 保存原始的下载函数
        original_download = None
        
        # 查找原始函数
        possible_names = [
            '__download_flet_client',
        ]
        
        for func_name in possible_names:
            if hasattr(flet_desktop, func_name):
                original_download = getattr(flet_desktop, func_name)
                break
        
        if not original_download:
            logger.warning("[Flet Patch] 未找到原始下载函数，跳过 patch")
            return
        
        # 定义替代下载函数
        def china_accelerated_download(file_name):
            """使用 gh-proxy.org 加速下载 flet 客户端（带桌面通知和进度）"""
            import flet_desktop.version
            
            ver = flet_desktop.version.version
            if not ver:
                import flet.version
                from flet.version import update_version
                ver = flet.version.version or update_version()
            
            temp_arch = Path(tempfile.gettempdir()).joinpath(file_name)
            
            # 原始 GitHub URL
            original_url = f"https://github.com/flet-dev/flet/releases/download/v{ver}/{file_name}"
            
            # 使用 gh-proxy.org 代理（中国加速）
            proxy_url = f"https://gh-proxy.org/{original_url}"
            
            # 显示开始通知
            _show_system_notification(
                "MTools - 首次启动",
                f"正在下载 UI 引擎 (v{ver})，预计 30-60 秒\n下载后将缓存，后续启动秒开"
            )
            
            logger.info(f"[Flet Download] 正在下载 Flet v{ver}")
            logger.info(f"[Flet Download] 使用中国镜像加速: {proxy_url}")
            
            # 控制台进度提示
            print("\n" + "="*60)
            print(f"🚀 MTools 首次启动 - 正在下载 UI 引擎 (v{ver})")
            print("="*60)
            print("💡 这是首次启动的一次性操作，下载后将缓存到系统")
            print("⏱️  预计时间：30-60 秒（使用中国镜像加速）")
            print("="*60)
            
            # 进度显示函数
            def show_progress(block_count, block_size, total_size):
                if total_size > 0:
                    downloaded = block_count * block_size
                    percent = min(100, downloaded * 100 / total_size)
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    
                    # 每隔一段时间更新一次（避免刷新太频繁）
                    if block_count % 20 == 0 or percent >= 100:
                        bar_length = 40
                        filled = int(bar_length * percent / 100)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        print(f"\r📥 [{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f}MB)", end='', flush=True)
            
            try:
                # 首先尝试使用代理下载
                urllib.request.urlretrieve(proxy_url, temp_arch, reporthook=show_progress)
                print("\n" + "="*60)
                print("✅ 下载完成！正在启动程序...")
                print("="*60 + "\n")
                logger.info(f"[Flet Download] ✅ 下载成功（使用镜像加速）")
                
                # 显示完成通知
                _show_system_notification(
                    "MTools - 下载完成",
                    "UI 引擎下载完成，正在启动程序..."
                )
                
            except Exception as e:
                # 如果代理失败，回退到原始 URL
                print(f"\n⚠️  镜像下载失败，尝试直连 GitHub...\n")
                logger.warning(f"[Flet Download] ⚠️  镜像下载失败: {e}")
                logger.info(f"[Flet Download] 尝试直接下载: {original_url}")
                
                urllib.request.urlretrieve(original_url, temp_arch, reporthook=show_progress)
                print("\n" + "="*60)
                print("✅ 下载完成！正在启动程序...")
                print("="*60 + "\n")
                logger.info(f"[Flet Download] ✅ 下载成功（直接下载）")
                
                # 显示完成通知
                _show_system_notification(
                    "MTools - 下载完成",
                    "UI 引擎下载完成，正在启动程序..."
                )
            
            return str(temp_arch)
        
        # 替换下载函数
        for func_name in possible_names:
            if hasattr(flet_desktop, func_name):
                setattr(flet_desktop, func_name, china_accelerated_download)
                logger.info(f"[Flet Patch] ✅ 已为中国用户启用下载加速 (gh-proxy.org)")
                break
                
    except ImportError:
        # flet_desktop 还未导入，稍后会在实际使用时自动触发
        logger.info("[Flet Patch] flet_desktop 尚未导入，将在首次使用时应用加速")
    except Exception as e:
        logger.error(f"[Flet Patch] ⚠️  Patch 失败: {e}")
        import traceback
        traceback.print_exc()

# 模块导入时自动执行：为中国用户启用 GitHub 下载加速
if _is_china_user():
    try:
        _patch_flet_download_for_china()
    except Exception as e:
        logger.warning(f"[Flet Patch] 启用下载加速失败: {e}")

