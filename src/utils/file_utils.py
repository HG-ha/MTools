# -*- coding: utf-8 -*-
"""文件工具模块。

提供文件和目录操作相关的工具函数。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from utils import logger

if TYPE_CHECKING:
    import flet as ft


def is_packaged_app() -> bool:
    """判断当前程序是否为打包后的可执行文件。
    
    检测方式（满足任一即为打包环境）：
    - Nuitka / PyInstaller: sys.frozen == True
    - flet build (serious_python): SERIOUS_PYTHON_SITE_PACKAGES 环境变量已设置
    - Windows: sys.argv[0] 以 .exe 结尾
    - macOS: 可执行文件位于 .app bundle 内
    
    Returns:
        如果是打包的程序返回 True，否则返回 False
    """
    if getattr(sys, 'frozen', False):
        return True
    if os.environ.get("SERIOUS_PYTHON_SITE_PACKAGES"):
        return True
    exe_path = Path(sys.argv[0])
    if exe_path.suffix.lower() == '.exe':
        return True
    if sys.platform == "darwin" and ".app/" in str(Path(sys.executable).resolve()):
        return True
    return False


def get_app_root() -> Path:
    """获取应用程序根目录。
    
    - 如果是打包程序(.exe)：返回可执行文件所在目录
    - 如果是开发模式：返回项目根目录（src的父目录）
    
    Returns:
        应用程序根目录路径
    """
    if is_packaged_app():
        # 打包后的可执行文件，返回 exe 所在目录
        return Path(sys.argv[0]).parent
    else:
        # 开发模式，返回项目根目录（假设当前文件在 src/utils/file_utils.py）
        return Path(__file__).parent.parent.parent


def ensure_dir(path: Path) -> bool:
    """确保目录存在，如不存在则创建。
    
    Args:
        path: 目录路径
    
    Returns:
        是否成功
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {e}")
        return False


def get_file_size(path: Path) -> int:
    """获取文件大小（字节）。
    
    Args:
        path: 文件路径
    
    Returns:
        文件大小
    """
    try:
        return path.stat().st_size
    except Exception:
        return 0


def format_file_size(size: int) -> str:
    """格式化文件大小显示。
    
    Args:
        size: 文件大小（字节）
    
    Returns:
        格式化后的文件大小字符串
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def clean_temp_files(temp_dir: Path, max_age_days: int = 7) -> int:
    """清理临时文件。
    
    Args:
        temp_dir: 临时文件目录
        max_age_days: 最大保留天数
    
    Returns:
        删除的文件数量
    """
    import time
    
    count: int = 0
    current_time: float = time.time()
    max_age_seconds: float = max_age_days * 24 * 3600
    
    try:
        for file_path in temp_dir.iterdir():
            if file_path.is_file():
                file_age: float = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    count += 1
    except Exception as e:
        logger.error(f"清理临时文件失败: {e}")
    
    return count


def copy_file(src: Path, dst: Path) -> bool:
    """复制文件。
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
    
    Returns:
        是否成功
    """
    try:
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        logger.error(f"复制文件失败: {e}")
        return False


def move_file(src: Path, dst: Path) -> bool:
    """移动文件。
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
    
    Returns:
        是否成功
    """
    try:
        shutil.move(str(src), str(dst))
        return True
    except Exception as e:
        logger.error(f"移动文件失败: {e}")
        return False


def get_file_extension(path: Path) -> str:
    """获取文件扩展名（不含点号）。
    
    Args:
        path: 文件路径
    
    Returns:
        文件扩展名
    """
    return path.suffix.lstrip(".")


def list_files_by_extension(directory: Path, extensions: List[str]) -> List[Path]:
    """列出指定扩展名的所有文件。
    
    Args:
        directory: 目录路径
        extensions: 扩展名列表（不含点号）
    
    Returns:
        文件路径列表
    """
    files: List[Path] = []
    
    try:
        for ext in extensions:
            pattern: str = f"*.{ext}"
            files.extend(directory.glob(pattern))
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
    
    return files


def get_system_fonts() -> List[Tuple[str, str]]:
    """获取系统已安装的所有字体列表。
    
    返回格式为 [(字体名称, 显示名称), ...] 的列表。
    字体名称用于设置字体，显示名称用于在界面上展示。
    
    Returns:
        字体列表，每项为 (字体名称, 显示名称) 元组
    """
    fonts: List[Tuple[str, str]] = []
    
    # 添加系统默认字体
    fonts.append(("System", "系统默认"))
    
    try:
        system = platform.system()
        
        if system == "Windows":
            fonts.extend(_get_windows_fonts())
        elif system == "Darwin":  # macOS
            fonts.extend(_get_macos_fonts())
        elif system == "Linux":
            fonts.extend(_get_linux_fonts())
        else:
            logger.warning(f"未知系统类型: {system}")
            
    except Exception as e:
        logger.error(f"获取系统字体失败: {e}")
    
    # 去重并排序（保持"系统默认"在最前面）
    seen = {"System"}
    unique_fonts = [fonts[0]]  # 保留系统默认
    for font in fonts[1:]:
        if font[0] not in seen:
            seen.add(font[0])
            unique_fonts.append(font)
    
    # 常用中文字体推荐顺序（优先级最高）
    priority_fonts = [
        "微软雅黑", "Microsoft YaHei",
        "微软雅黑 UI", "Microsoft YaHei UI",
        "黑体", "SimHei", "Heiti SC", "STHeiti",
        "宋体", "SimSun", "STSong",
        "楷体", "KaiTi", "STKaiti",
        "仿宋", "FangSong", "STFangsong",
        "新宋体", "NSimSun",
        "苹方-简", "PingFang SC",
        "思源黑体-简", "Noto Sans CJK SC",
        "思源宋体-简", "Noto Serif CJK SC",
        "文泉驿微米黑", "WenQuanYi Micro Hei",
    ]

    def sort_key(font_tuple):
        name, display_name = font_tuple
        
        # 1. 优先级最高：在推荐列表中的字体
        if display_name in priority_fonts:
            return (0, priority_fonts.index(display_name))
        if name in priority_fonts:
            return (0, priority_fonts.index(name))
            
        # 2. 其次：包含中文的字体（认为中文字体对用户更重要）
        # 判断显示名称是否包含中文字符
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in display_name)
        if is_chinese:
            return (1, display_name)
            
        # 3. 最后：其他字体（主要是英文），按名称排序
        return (2, display_name)
    
    # 对除第一个之外的字体应用自定义排序
    unique_fonts[1:] = sorted(unique_fonts[1:], key=sort_key)
    
    return unique_fonts


def _get_windows_fonts() -> List[Tuple[str, str]]:
    """获取 Windows 系统字体。
    
    Returns:
        字体列表
    """
    fonts: List[Tuple[str, str]] = []
    
    try:
        # Windows 字体目录
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        fonts_dir = Path(system_root) / "Fonts"
        
        if not fonts_dir.exists():
            return fonts
        
        # 常见字体文件扩展名
        font_extensions = {".ttf", ".otf", ".ttc", ".fon"}
        
        # 遍历字体文件
        for font_file in fonts_dir.iterdir():
            if font_file.is_file() and font_file.suffix.lower() in font_extensions:
                font_name = font_file.stem
                
                # 处理常见中文字体名称映射
                display_name = _get_font_display_name(font_name)
                
                fonts.append((font_name, display_name))
        
        # 添加常见 Windows 字体（即使未在目录中找到）
        common_windows_fonts = [
            ("Microsoft YaHei", "微软雅黑"),
            ("Microsoft YaHei UI", "微软雅黑 UI"),
            ("SimSun", "宋体"),
            ("SimHei", "黑体"),
            ("KaiTi", "楷体"),
            ("FangSong", "仿宋"),
            ("NSimSun", "新宋体"),
            ("Arial", "Arial"),
            ("Calibri", "Calibri"),
            ("Consolas", "Consolas"),
            ("Courier New", "Courier New"),
            ("Georgia", "Georgia"),
            ("Times New Roman", "Times New Roman"),
            ("Trebuchet MS", "Trebuchet MS"),
            ("Verdana", "Verdana"),
            ("Segoe UI", "Segoe UI"),
        ]
        
        fonts.extend(common_windows_fonts)
        
    except Exception as e:
        logger.error(f"获取 Windows 字体失败: {e}")
    
    return fonts


def _get_macos_fonts() -> List[Tuple[str, str]]:
    """获取 macOS 系统字体。
    
    Returns:
        字体列表
    """
    fonts: List[Tuple[str, str]] = []
    
    try:
        # macOS 字体目录
        font_dirs = [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path.home() / "Library" / "Fonts",
        ]
        
        font_extensions = {".ttf", ".otf", ".ttc", ".dfont"}
        
        for fonts_dir in font_dirs:
            if not fonts_dir.exists():
                continue
            
            for font_file in fonts_dir.rglob("*"):
                if font_file.is_file() and font_file.suffix.lower() in font_extensions:
                    font_name = font_file.stem
                    display_name = _get_font_display_name(font_name)
                    fonts.append((font_name, display_name))
        
        # 添加常见 macOS 字体
        common_macos_fonts = [
            ("PingFang SC", "苹方-简"),
            ("PingFang TC", "苹方-繁"),
            ("Heiti SC", "黑体-简"),
            ("Heiti TC", "黑体-繁"),
            ("STHeiti", "华文黑体"),
            ("STKaiti", "华文楷体"),
            ("STSong", "华文宋体"),
            ("STFangsong", "华文仿宋"),
            ("Helvetica", "Helvetica"),
            ("Helvetica Neue", "Helvetica Neue"),
            ("Arial", "Arial"),
            ("Times New Roman", "Times New Roman"),
            ("Courier New", "Courier New"),
            ("Monaco", "Monaco"),
            ("Menlo", "Menlo"),
            ("San Francisco", "San Francisco"),
        ]
        
        fonts.extend(common_macos_fonts)
        
    except Exception as e:
        logger.error(f"获取 macOS 字体失败: {e}")
    
    return fonts


def _get_linux_fonts() -> List[Tuple[str, str]]:
    """获取 Linux 系统字体。
    
    Returns:
        字体列表
    """
    fonts: List[Tuple[str, str]] = []
    
    try:
        # 尝试使用 fc-list 命令获取字体列表
        try:
            result = subprocess.run(
                ["fc-list", ":", "family"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if line:
                        # fc-list 输出格式可能包含多个字体名，用逗号分隔
                        font_names = [f.strip() for f in line.split(",")]
                        for font_name in font_names:
                            if font_name:
                                display_name = _get_font_display_name(font_name)
                                fonts.append((font_name, display_name))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # fc-list 不可用，尝试遍历字体目录
            font_dirs = [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
                Path.home() / ".local" / "share" / "fonts",
            ]
            
            font_extensions = {".ttf", ".otf", ".ttc"}
            
            for fonts_dir in font_dirs:
                if not fonts_dir.exists():
                    continue
                
                for font_file in fonts_dir.rglob("*"):
                    if font_file.is_file() and font_file.suffix.lower() in font_extensions:
                        font_name = font_file.stem
                        display_name = _get_font_display_name(font_name)
                        fonts.append((font_name, display_name))
        
        # 添加常见 Linux 字体
        common_linux_fonts = [
            ("Noto Sans CJK SC", "思源黑体-简"),
            ("Noto Serif CJK SC", "思源宋体-简"),
            ("WenQuanYi Micro Hei", "文泉驿微米黑"),
            ("WenQuanYi Zen Hei", "文泉驿正黑"),
            ("Droid Sans Fallback", "Droid Sans Fallback"),
            ("Ubuntu", "Ubuntu"),
            ("DejaVu Sans", "DejaVu Sans"),
            ("DejaVu Serif", "DejaVu Serif"),
            ("DejaVu Sans Mono", "DejaVu Sans Mono"),
            ("Liberation Sans", "Liberation Sans"),
            ("Liberation Serif", "Liberation Serif"),
            ("Liberation Mono", "Liberation Mono"),
        ]
        
        fonts.extend(common_linux_fonts)
        
    except Exception as e:
        logger.error(f"获取 Linux 字体失败: {e}")
    
    return fonts


def _get_font_display_name(font_name: str) -> str:
    """获取字体的显示名称。
    
    对于中文字体，返回中文名称；对于英文字体，保持原名。
    
    Args:
        font_name: 字体名称
    
    Returns:
        显示名称
    """
    # 常见字体名称映射
    font_name_map = {
        # Windows 中文字体
        "Microsoft YaHei": "微软雅黑",
        "Microsoft YaHei UI": "微软雅黑 UI",
        "SimSun": "宋体",
        "SimHei": "黑体",
        "KaiTi": "楷体",
        "FangSong": "仿宋",
        "NSimSun": "新宋体",
        "MingLiU": "细明体",
        "PMingLiU": "新细明体",
        
        # macOS 中文字体
        "PingFang SC": "苹方-简",
        "PingFang TC": "苹方-繁",
        "Heiti SC": "黑体-简",
        "Heiti TC": "黑体-繁",
        "STHeiti": "华文黑体",
        "STKaiti": "华文楷体",
        "STSong": "华文宋体",
        "STFangsong": "华文仿宋",
        "STXihei": "华文细黑",
        "STZhongsong": "华文中宋",
        
        # Linux 中文字体
        "Noto Sans CJK SC": "思源黑体-简",
        "Noto Serif CJK SC": "思源宋体-简",
        "WenQuanYi Micro Hei": "文泉驿微米黑",
        "WenQuanYi Zen Hei": "文泉驿正黑",
    }
    
    # 如果在映射表中找到，返回对应的中文名
    if font_name in font_name_map:
        return font_name_map[font_name]
    
    # 否则返回原名
    return font_name


def get_desktop_path() -> Optional[Path]:
    """获取用户桌面路径。
    
    Returns:
        桌面路径，如果无法获取则返回 None
    """
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            )
            desktop_path = winreg.QueryValueEx(key, "Desktop")[0]
            winreg.CloseKey(key)
            return Path(desktop_path)
        elif platform.system() == "Darwin":  # macOS
            return Path.home() / "Desktop"
        else:  # Linux
            return Path.home() / "Desktop"
    except Exception as e:
        logger.error(f"获取桌面路径失败: {e}")
        return None


def check_macos_applications_install() -> bool:
    """检查 macOS app 是否在 /Applications 或 ~/Applications 下运行。

    非 macOS 或非打包环境返回 True（表示不需要提示）。

    Returns:
        在 Applications 目录内返回 True，否则返回 False
    """
    if sys.platform != "darwin" or not is_packaged_app():
        return True

    try:
        exe_resolved = str(Path(sys.executable).resolve())
        home_apps = str(Path.home() / "Applications")
        if exe_resolved.startswith("/Applications/") or exe_resolved.startswith(home_apps):
            logger.debug(f"macOS: 应用在 Applications 内运行: {exe_resolved}")
            return True
        logger.info(f"macOS: 应用不在 Applications 目录: {exe_resolved}")
        return False
    except Exception as e:
        logger.error(f"检查 macOS Applications 安装位置失败: {e}")
        return True


def check_desktop_shortcut() -> bool:
    """检查桌面是否存在应用快捷方式。
    
    Returns:
        如果存在快捷方式或不需要检查返回 True，否则返回 False
    """
    try:
        # 只在 Windows 打包环境下检测
        system = platform.system()
        is_packaged = is_packaged_app()
        
        logger.debug(f"检查快捷方式 - 系统: {system}, 是否打包: {is_packaged}")
        
        if system != "Windows":
            logger.debug("非 Windows 系统，跳过快捷方式检查")
            return True  # 非 Windows 系统，返回 True 表示不需要提示
        
        if not is_packaged:
            logger.debug("开发环境，跳过快捷方式检查")
            return True  # 开发环境，返回 True 表示不需要提示
        
        desktop_path = get_desktop_path()
        logger.debug(f"桌面路径: {desktop_path}")
        
        if not desktop_path:
            logger.warning("无法获取桌面路径")
            return True  # 无法获取桌面路径，不提示
        
        # 检查快捷方式文件（所有版本都使用 MTools.lnk）
        shortcut_path = desktop_path / "MTools.lnk"
        
        logger.debug(f"检查快捷方式文件: {shortcut_path}")
        
        if shortcut_path.exists():
            logger.info(f"找到快捷方式: {shortcut_path}")
            return True
        
        logger.info("未找到桌面快捷方式")
        return False
    except Exception as e:
        import traceback
        logger.error(f"检查桌面快捷方式失败: {e}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        return True  # 发生错误时不提示


def create_desktop_shortcut() -> Tuple[bool, str]:
    """创建桌面快捷方式。
    
    Returns:
        (成功/失败, 消息)
    """
    # 只在 Windows 打包环境下支持
    if platform.system() != "Windows":
        return False, "当前系统不支持此功能"
    
    if not is_packaged_app():
        return False, "开发环境不支持创建快捷方式"
    
    try:
        desktop_path = get_desktop_path()
        if not desktop_path:
            return False, "无法获取桌面路径"
        
        shortcut_path = desktop_path / "MTools.lnk"
        
        # 检查快捷方式是否已存在
        if shortcut_path.exists():
            return False, "桌面快捷方式已存在"
        
        # 获取程序路径和图标
        exe_path = Path(sys.argv[0]).resolve()
        app_dir = exe_path.parent
        
        # 查找图标
        icon_path = None
        for icon_name in ["icon.ico", "assets/icon.ico", "src/assets/icon.ico"]:
            test_path = app_dir / icon_name
            if test_path.exists():
                icon_path = test_path
                break
        
        # 使用 PowerShell 创建快捷方式
        ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{exe_path}"
$Shortcut.WorkingDirectory = "{app_dir}"
$Shortcut.Description = "MTools"
"""
        if icon_path:
            ps_script += f'$Shortcut.IconLocation = "{icon_path}"\n'
        ps_script += "$Shortcut.Save()"
        
        # 执行 PowerShell 命令
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"已创建桌面快捷方式: {shortcut_path}")
            return True, "桌面快捷方式创建成功！"
        else:
            logger.error(f"创建快捷方式失败: {result.stderr}")
            return False, f"创建失败: {result.stderr}"
    
    except Exception as ex:
        logger.error(f"创建桌面快捷方式失败: {ex}")
        return False, f"创建失败: {str(ex)}"


def get_unique_path(path: Path, add_sequence: bool = True) -> Path:
    """获取唯一的文件路径，避免覆盖已存在的文件。
    
    如果文件不存在，直接返回原路径。
    如果文件存在且 add_sequence=True，则添加序号（如 file_1.txt, file_2.txt）。
    如果文件存在且 add_sequence=False，直接返回原路径（覆盖模式）。
    
    Args:
        path: 原始文件路径
        add_sequence: 是否添加序号（True=添加序号，False=覆盖）
        
    Returns:
        唯一的文件路径
        
    Examples:
        >>> get_unique_path(Path("video.mp4"), add_sequence=True)
        Path("video.mp4")  # 如果不存在
        
        >>> get_unique_path(Path("video.mp4"), add_sequence=True)
        Path("video_1.mp4")  # 如果 video.mp4 已存在
        
        >>> get_unique_path(Path("video.mp4"), add_sequence=False)
        Path("video.mp4")  # 直接覆盖
    """
    if not add_sequence or not path.exists():
        return path
    
    # 文件存在，需要添加序号
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
        
        # 防止无限循环
        if counter > 9999:
            logger.warning(f"文件序号超过 9999，直接覆盖: {path}")
            return path


def _get_shared_file_picker(page: ft.Page) -> Any:
    """获取注册在 page 上的共享 FilePicker 实例。"""
    fp = getattr(page, "_shared_file_picker", None)
    if fp is None:
        import flet as ft_mod
        fp = ft_mod.FilePicker()
        page.services.append(fp)
        page._shared_file_picker = fp
    return fp


async def pick_files(
    page: ft.Page,
    *,
    dialog_title: Optional[str] = None,
    initial_directory: Optional[str] = None,
    allowed_extensions: Optional[list[str]] = None,
    allow_multiple: bool = False,
) -> list:
    """通过共享 FilePicker 打开文件选择对话框。"""
    fp = _get_shared_file_picker(page)
    return await fp.pick_files(
        dialog_title=dialog_title,
        initial_directory=initial_directory,
        allowed_extensions=allowed_extensions,
        allow_multiple=allow_multiple,
    )


async def get_directory_path(
    page: ft.Page,
    *,
    dialog_title: Optional[str] = None,
    initial_directory: Optional[str] = None,
) -> Optional[str]:
    """通过共享 FilePicker 打开目录选择对话框。"""
    fp = _get_shared_file_picker(page)
    return await fp.get_directory_path(
        dialog_title=dialog_title,
        initial_directory=initial_directory,
    )


async def save_file(
    page: ft.Page,
    *,
    dialog_title: Optional[str] = None,
    file_name: Optional[str] = None,
    initial_directory: Optional[str] = None,
    allowed_extensions: Optional[list[str]] = None,
) -> Optional[str]:
    """通过共享 FilePicker 打开文件保存对话框。"""
    fp = _get_shared_file_picker(page)
    return await fp.save_file(
        dialog_title=dialog_title,
        file_name=file_name,
        initial_directory=initial_directory,
        allowed_extensions=allowed_extensions,
    )
