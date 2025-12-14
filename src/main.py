# -*- coding: utf-8 -*-
"""MTools应用程序入口。

多功能桌面应用程序，集成了图片处理、音视频处理、编码转换、代码格式化等功能。
遵循Material Design设计原则，使用Flet框架开发。
"""

# 补丁
from utils import patch  # noqa: F401
# Nuitka 打包初始化（必须在导入 flet 之前执行）
from utils import nuitka_setup  # noqa: F401

import flet as ft

from constants import (
    APP_TITLE,
    BACKGROUND_COLOR,
    CARD_BACKGROUND,
    DARK_BACKGROUND_COLOR,
    DARK_CARD_BACKGROUND,
    PRIMARY_COLOR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from services import ConfigService
from views.main_view import MainView
from utils import logger


def main(page: ft.Page) -> None:
    """应用主入口函数。
    
    配置页面属性并初始化主视图。
    
    Args:
        page: Flet页面对象
    """
    # 加载配置
    config_service = ConfigService()
    
    # 初始化日志系统 - 根据配置决定是否启用文件日志
    save_logs = config_service.get_config_value("save_logs", False)
    if save_logs:
        logger.enable_file_logging()
    
    saved_font = config_service.get_config_value("font_family", "System")
    saved_theme_color = config_service.get_config_value("theme_color", PRIMARY_COLOR)
    saved_theme_mode = config_service.get_config_value("theme_mode", "system")
    saved_left = config_service.get_config_value("window_left")
    saved_top = config_service.get_config_value("window_top")
    saved_width = config_service.get_config_value("window_width")
    saved_height = config_service.get_config_value("window_height")
    saved_maximized = config_service.get_config_value("window_maximized", False)
    
    # 配置页面属性
    page.title = APP_TITLE
    
    # 设置窗口图标（任务栏图标）
    import sys
    from pathlib import Path
    
    # 判断是否为 Nuitka 打包后的环境（.exe 文件）
    is_compiled = Path(sys.argv[0]).suffix.lower() == '.exe'
    
    if is_compiled:
        # Nuitka 打包环境：从 exe 所在目录查找
        app_dir = Path(sys.argv[0]).parent
    else:
        # 开发环境：从源代码目录查找
        app_dir = Path(__file__).parent
    
    # 尝试多个可能的图标路径（优先使用 .ico 格式）
    possible_icon_paths = [
        # ICO 格式（Windows 任务栏最佳）
        app_dir / "src" / "assets" / "icon.ico",  # 打包后的标准路径
        app_dir / "assets" / "icon.ico",  # 开发环境
        Path(__file__).parent / "assets" / "icon.ico",  # 相对于源文件
        # PNG 格式（备用）
        app_dir / "src" / "assets" / "icon.png",
        app_dir / "assets" / "icon.png",
        Path(__file__).parent / "assets" / "icon.png",
    ]
    
    icon_path = None
    for path in possible_icon_paths:
        if path.exists():
            icon_path = path
            break
    
    if icon_path:
        page.window.icon = str(icon_path)
    
    # 设置窗口最小大小
    page.window.min_width = WINDOW_WIDTH
    page.window.min_height = WINDOW_HEIGHT
    
    # 先设置窗口大小（使用保存的大小或默认大小）
    page.window.width = saved_width if saved_width is not None else WINDOW_WIDTH
    page.window.height = saved_height if saved_height is not None else WINDOW_HEIGHT
    
    # 恢复窗口位置（如果有保存的位置）
    # 先移动到上次的位置，这样最大化时会在正确的显示器上
    if saved_left is not None and saved_top is not None:
        page.window.left = saved_left
        page.window.top = saved_top
    
    # 最后应用最大化状态（如果上次是最大化）
    if saved_maximized:
        page.window.maximized = True
    
    # 隐藏系统标题栏，使用自定义标题栏
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    
    # 设置浅色主题 - 使用用户选择的主题色或默认色
    page.theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 页面和组件颜色配置
        scaffold_bgcolor=BACKGROUND_COLOR,  # 浅灰背景
        card_color=CARD_BACKGROUND,         # 白色卡片
        # 导航栏主题 - 不设置固定背景色，使用容器的半透明背景
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=ft.Colors.TRANSPARENT,
        ),
    )
    
    # 设置深色主题
    page.dark_theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        use_material3=True,
        font_family=saved_font,  # 使用保存的字体
        # 深色模式颜色配置
        scaffold_bgcolor=DARK_BACKGROUND_COLOR,  # 深色背景
        card_color=DARK_CARD_BACKGROUND,        # 深色卡片
        # 深色导航栏主题 - 不设置固定背景色，使用容器的半透明背景
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=ft.Colors.TRANSPARENT,
        ),
    )
    
    # 应用用户设置的主题模式
    if saved_theme_mode == "light":
        page.theme_mode = ft.ThemeMode.LIGHT
    elif saved_theme_mode == "dark":
        page.theme_mode = ft.ThemeMode.DARK
    else:  # system 或其他
        page.theme_mode = ft.ThemeMode.SYSTEM
    
    # 设置页面布局
    page.padding = 0
    page.spacing = 0
    
    # 创建并添加主视图
    main_view: MainView = MainView(page)
    page.add(main_view)
    
    # 更新页面
    page.update()
    
    # 应用窗口透明度（必须在page.update()之后）
    if hasattr(main_view, '_pending_opacity'):
        page.window.opacity = main_view._pending_opacity
        page.update()
    
    # 应用背景图片（如果有配置）
    if hasattr(main_view, '_pending_bg_image') and main_view._pending_bg_image:
        main_view.apply_background(main_view._pending_bg_image, main_view._pending_bg_fit)
    
    # 启动时检查更新（如果启用）
    auto_check = config_service.get_config_value("auto_check_update", True)
    if auto_check:
        _check_update_on_startup(page, config_service)
    
    # 监听窗口事件（移动和调整大小时自动保存）
    def on_window_event(e):
        """处理窗口事件。"""
        # 窗口移动时保存位置（只在非最大化时保存）
        if e.data == "moved":
            if not page.window.maximized:
                if page.window.left is not None and page.window.top is not None:
                    config_service.set_config_value("window_left", page.window.left)
                    config_service.set_config_value("window_top", page.window.top)
        # 窗口大小改变时保存大小和最大化状态
        elif e.data == "resized":
            # 保存最大化状态
            config_service.set_config_value("window_maximized", page.window.maximized)
            
            # 只在非最大化时保存窗口大小
            if not page.window.maximized:
                if page.window.width is not None and page.window.height is not None:
                    config_service.set_config_value("window_width", page.window.width)
                    config_service.set_config_value("window_height", page.window.height)
    
    page.on_window_event = on_window_event
    
def _check_update_on_startup(page: ft.Page, config_service: ConfigService) -> None:
    """启动时检查更新。
    
    Args:
        page: Flet页面对象
        config_service: 配置服务实例
    """
    import threading
    from services import UpdateService, UpdateStatus
    
    def check_task():
        try:
            # 等待界面完全加载
            import time
            time.sleep(2)
            
            update_service = UpdateService()
            update_info = update_service.check_update()
            
            # 只在有新版本时提示
            if update_info.status == UpdateStatus.UPDATE_AVAILABLE:
                # 检查是否跳过了这个版本
                skipped_version = config_service.get_config_value("skipped_version", "")
                if skipped_version == update_info.latest_version:
                    logger.info(f"跳过版本 {update_info.latest_version} 的更新提示")
                    return
                
                # 在主线程中显示提示
                def show_update_snackbar():
                    snackbar = ft.SnackBar(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.NEW_RELEASES, color=ft.Colors.ORANGE),
                                ft.Text(f"发现新版本 {update_info.latest_version}"),
                            ],
                            spacing=10,
                        ),
                        action="查看",
                        action_color=ft.Colors.ORANGE,
                        on_action=lambda _: _show_startup_update_dialog(page, config_service, update_info),
                        duration=10000,  # 10秒
                    )
                    page.overlay.append(snackbar)
                    snackbar.open = True
                    page.update()
                
                page.run_task(show_update_snackbar)
                
        except Exception as e:
            logger.error(f"启动时检查更新失败: {e}")
    
    thread = threading.Thread(target=check_task, daemon=True)
    thread.start()

def _show_startup_update_dialog(page: ft.Page, config_service: ConfigService, update_info) -> None:
    """显示启动时的更新对话框。
    
    Args:
        page: Flet页面对象
        config_service: 配置服务
        update_info: 更新信息
    """
    from services.auto_updater import AutoUpdater
    from constants import BORDER_RADIUS_MEDIUM, PADDING_SMALL
    import threading
    import time
    
    release_notes = update_info.release_notes or "暂无更新说明"
    if len(release_notes) > 500:
        release_notes = release_notes[:500] + "..."
    
    # 创建进度条
    progress_bar = ft.ProgressBar(value=0, visible=False)
    progress_text = ft.Text("", size=12, visible=False)
    
    # 创建按钮
    auto_update_btn = ft.ElevatedButton(
        text="立即更新",
        icon=ft.Icons.SYSTEM_UPDATE,
    )
    
    skip_btn = ft.TextButton(
        text="跳过此版本",
    )
    
    later_btn = ft.TextButton(
        text="稍后提醒",
    )
    
    # 创建对话框
    dialog = ft.AlertDialog(
        title=ft.Text(f"发现新版本 {update_info.latest_version}"),
        content=ft.Column(
            controls=[
                ft.Text("更新说明:", weight=ft.FontWeight.BOLD, size=14),
                ft.Container(
                    content=ft.Text(release_notes, size=12),
                    padding=PADDING_SMALL,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    height=150,
                ),
                ft.Container(height=PADDING_SMALL),
                progress_bar,
                progress_text,
            ],
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            auto_update_btn,
            skip_btn,
            later_btn,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    
    # 定义按钮事件处理
    def on_auto_update(_):
        auto_update_btn.disabled = True
        skip_btn.disabled = True
        later_btn.disabled = True
        
        progress_bar.visible = True
        progress_text.visible = True
        progress_text.value = "正在下载更新..."
        page.update()
        
        def update_task():
            try:
                import asyncio
                updater = AutoUpdater()
                
                def progress_callback(downloaded: int, total: int):
                    if total > 0:
                        progress = downloaded / total
                        progress_bar.value = progress
                        downloaded_mb = downloaded / 1024 / 1024
                        total_mb = total / 1024 / 1024
                        progress_text.value = f"下载中: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({progress*100:.0f}%)"
                        page.update()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                download_path = loop.run_until_complete(
                    updater.download_update(update_info.download_url, progress_callback)
                )
                
                progress_text.value = "正在解压更新..."
                progress_bar.value = None
                page.update()
                
                extract_dir = updater.extract_update(download_path)
                
                progress_text.value = "正在应用更新，应用即将重启..."
                page.update()
                
                time.sleep(1)
                
                # 定义优雅退出回调
                def exit_callback():
                    """优雅退出应用"""
                    try:
                        # 直接关闭窗口（启动时没有标题栏实例）
                        page.window.close()
                    except Exception as e:
                        logger.warning(f"优雅退出失败: {e}")
                        # 如果失败，让 apply_update 使用强制退出
                        raise
                
                updater.apply_update(extract_dir, exit_callback)
                
            except Exception as ex:
                logger.error(f"自动更新失败: {ex}")
                auto_update_btn.disabled = False
                skip_btn.disabled = False
                later_btn.disabled = False
                progress_bar.visible = False
                progress_text.value = f"更新失败: {str(ex)}"
                progress_text.color = ft.Colors.RED
                progress_text.visible = True
                page.update()
        
        threading.Thread(target=update_task, daemon=True).start()
    
    def on_skip(_):
        config_service.set_config_value("skipped_version", update_info.latest_version)
        dialog.open = False
        page.update()
    
    def on_later(_):
        dialog.open = False
        page.update()
    
    auto_update_btn.on_click = on_auto_update
    skip_btn.on_click = on_skip
    later_btn.on_click = on_later
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


# 启动应用
if __name__ == "__main__":
    ft.app(target=main)
