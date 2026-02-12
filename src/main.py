# -*- coding: utf-8 -*-
"""MTools应用程序入口。

多功能桌面应用程序，集成了图片处理、音视频处理、编码转换、代码格式化等功能。
遵循Material Design设计原则，使用Flet框架开发。

还未优化...
"""

# 补丁，请勿删除
from utils import patch  # noqa: F401
import sys
import flet as ft

from constants import (
    APP_TITLE,
    BACKGROUND_COLOR,
    BORDER_RADIUS_MEDIUM,
    CARD_BACKGROUND,
    DARK_BACKGROUND_COLOR,
    DARK_CARD_BACKGROUND,
    PADDING_SMALL,
    PRIMARY_COLOR,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from services import ConfigService, GlobalHotkeyService
from views.main_view import MainView
from utils import logger


def main(page: ft.Page) -> None:
    """应用主入口函数。
    
    配置页面属性并初始化主视图，使用路由系统管理页面导航。
    
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
    
    # Flet 1.0 中 window.icon 已移除，窗口图标由 assets_dir 中的图标文件和 app bundle 提供
    
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
    
    # 隐藏系统标题栏，使用自定义标题栏（必须在设置最大化之前）
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    
    # 最后应用最大化状态（如果上次是最大化）
    if saved_maximized:
        page.window.maximized = True
    
    # 设置浅色主题 - 使用用户选择的主题色或默认色
    page.theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        font_family=saved_font,  # 使用保存的字体
    )
    
    # 设置深色主题
    page.dark_theme = ft.Theme(
        color_scheme_seed=saved_theme_color,  # 使用用户设置的主题色
        font_family=saved_font,  # 使用保存的字体
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
    
    # 创建主视图实例（但不直接添加到页面）
    main_view: MainView = MainView(page)
    
    # 保存主视图引用到page，供路由处理器使用
    page._main_view_instance = main_view
    
    # 将主视图添加到页面（不使用 page.views，避免 page 引用丢失）
    page.add(main_view)
    
    # 设置路由变更处理器（仅用于管理内容切换逻辑）
    def route_change(e):
        """处理路由变更事件。"""
        if main_view._is_closing:
            return
        try:
            main_view.handle_route_change(page.route)
        except RuntimeError:
            pass  # Session closed
    
    page.on_route_change = route_change
    
    # 启动全局热键服务
    global_hotkey_service = GlobalHotkeyService(config_service, page)
    main_view.global_hotkey_service = global_hotkey_service  # 保存引用
    global_hotkey_service.start()
    
    # 导航到初始路由（根据配置决定显示推荐页还是图片处理页）
    show_recommendations = config_service.get_config_value("show_recommendations_page", True)
    initial_route = "/" if show_recommendations else "/image"
    
    async def push_initial_route():
        await page.push_route(initial_route)
    
    page.run_task(push_initial_route)
    
    # 应用窗口透明度（在首次路由后应用）
    if hasattr(main_view, '_pending_opacity'):
        page.window.opacity = main_view._pending_opacity
        page.update()
    
    # 应用背景图片（如果有配置）
    if hasattr(main_view, '_pending_bg_image') and main_view._pending_bg_image:
        main_view.apply_background(main_view._pending_bg_image, main_view._pending_bg_fit)
    
    # 检查是否以最小化模式启动（开机自启动时使用）
    if '--minimized' in sys.argv:
        # 延迟隐藏到托盘，确保窗口和托盘图标已初始化
        def hide_to_tray_delayed():
            import time
            time.sleep(0.5)  # 等待托盘图标初始化
            try:
                if hasattr(main_view, 'title_bar') and hasattr(main_view.title_bar, '_hide_to_tray'):
                    # 强制启用最小化到托盘功能
                    main_view.title_bar.minimize_to_tray = True
                    main_view.title_bar._hide_to_tray()
                    logger.info("开机自启动：已最小化到托盘")
            except Exception as e:
                logger.error(f"最小化到托盘失败: {e}")
        
        import threading
        threading.Thread(target=hide_to_tray_delayed, daemon=True).start()
    
    # 检查并修复开机自启动路径（仅编译后）
    _check_and_fix_auto_start(config_service)
    
    # 启动时检查更新，方法留存
    # 底部 snackbar
    # auto_check = config_service.get_config_value("auto_check_update", True)
    # if auto_check:
    #     _check_update_on_startup(page, config_service)
    
    # 检查桌面快捷方式（延迟执行，避免阻塞启动）
    _check_desktop_shortcut(page, config_service)
    
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
    from utils.file_utils import is_packaged_app
    
    # 开发环境跳过自动更新检查
    if not is_packaged_app():
        logger.debug("开发环境，跳过自动更新检查")
        return
    
    def check_update_task():
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
                        duration=3000,  # 3秒
                    )
                    page.overlay.append(snackbar)
                    snackbar.open = True
                    page.update()
                
                page.run_task(show_update_snackbar)
                
        except Exception as e:
            logger.error(f"启动时检查更新失败: {e}")
    
    thread = threading.Thread(target=check_update_task, daemon=True)
    thread.start()

def _show_startup_update_dialog(page: ft.Page, config_service: ConfigService, update_info) -> None:
    """显示启动时的更新对话框。
    
    Args:
        page: Flet页面对象
        config_service: 配置服务
        update_info: 更新信息
    """
    from services.auto_updater import AutoUpdater
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
        content="立即更新",
        icon=ft.Icons.SYSTEM_UPDATE,
    )
    
    skip_btn = ft.TextButton(
        content="跳过此版本",
    )
    
    later_btn = ft.TextButton(
        content="稍后提醒",
    )
    
    # 创建对话框
    dialog = ft.AlertDialog(
        title=ft.Text(f"发现新版本 {update_info.latest_version}"),
        content=ft.Column(
            controls=[
                ft.Text("更新说明:", weight=ft.FontWeight.BOLD, size=14),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Markdown(
                                value=release_notes,
                                selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                on_tap_link=lambda e: __import__('webbrowser').open(e.data),
                            ),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    height=300,
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
        
        def download_and_apply_update():
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
        
        threading.Thread(target=download_and_apply_update, daemon=True).start()
    
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


def _check_desktop_shortcut(page: ft.Page, config_service: ConfigService) -> None:
    """检查桌面快捷方式并提示用户。
    
    Args:
        page: Flet页面对象
        config_service: 配置服务实例
    """
    import threading
    import time
    from utils.file_utils import check_desktop_shortcut, create_desktop_shortcut
    
    def check_shortcut_task():
        try:
            # 等待界面完全加载
            time.sleep(2)
            
            # 检查桌面是否有快捷方式
            # 注意: check_desktop_shortcut() 在非 Windows 或开发环境下也会返回 True
            has_shortcut = check_desktop_shortcut()
            
            # 如果返回 True（有快捷方式或不需要检查），则不提示
            if has_shortcut:
                # 日志已在 check_desktop_shortcut 函数中输出，这里不再重复
                return
            
            # 检查用户是否选择了"不再提示"
            never_show = config_service.get_config_value("never_show_shortcut_prompt", False)
            if never_show:
                logger.debug("用户已选择不再提示快捷方式创建")
                return
            
            # 检查是否已经提示过（24小时内不重复提示）
            last_prompt_time = config_service.get_config_value("last_shortcut_prompt_time", 0)
            current_time = time.time()
            hours_24 = 24 * 60 * 60
            
            # 如果距离上次提示不到24小时，不再提示
            if current_time - last_prompt_time < hours_24:
                logger.debug("24小时内已提示过，跳过本次提示")
                return
            
            # 没有快捷方式，显示提示
            def show_shortcut_dialog():
                # 创建按钮
                create_btn = ft.ElevatedButton(
                    content="立即创建",
                    icon=ft.Icons.ADD_TO_HOME_SCREEN,
                )
                
                later_btn = ft.TextButton(
                    content="稍后创建",
                )
                
                never_btn = ft.TextButton(
                    content="不再提示",
                )
                
                # 创建对话框
                dialog = ft.AlertDialog(
                    title=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.BLUE, size=24),
                            ft.Text("创建桌面快捷方式"),
                        ],
                        spacing=10,
                    ),
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "检测到桌面上还没有 MTools 的快捷方式。\n"
                                "创建快捷方式可以让您更方便地启动应用。",
                                size=14,
                            ),
                        ],
                        tight=True,
                        spacing=10,
                    ),
                    actions=[
                        create_btn,
                        later_btn,
                        never_btn,
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                
                # 按钮事件处理
                def on_create(_):
                    success, message = create_desktop_shortcut()
                    
                    # 如果创建成功，不再记录提示时间（因为已经有快捷方式了）
                    # 如果创建失败，记录提示时间，24小时后再提示
                    if not success:
                        config_service.set_config_value("last_shortcut_prompt_time", time.time())
                    
                    dialog.open = False
                    page.update()
                    
                    # 显示结果提示
                    snackbar = ft.SnackBar(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE if success else ft.Icons.ERROR,
                                    color=ft.Colors.GREEN if success else ft.Colors.RED
                                ),
                                ft.Text(message),
                            ],
                            spacing=10,
                        ),
                        duration=3000,
                    )
                    page.overlay.append(snackbar)
                    snackbar.open = True
                    page.update()
                
                def on_later(_):
                    # 更新提示时间，24小时后再提示
                    config_service.set_config_value("last_shortcut_prompt_time", time.time())
                    dialog.open = False
                    page.update()
                
                def on_never(_):
                    # 设置为永不提示（使用一个很大的时间戳）
                    config_service.set_config_value("never_show_shortcut_prompt", True)
                    dialog.open = False
                    page.update()
                
                create_btn.on_click = on_create
                later_btn.on_click = on_later
                never_btn.on_click = on_never
                
                page.overlay.append(dialog)
                dialog.open = True
                page.update()
            
            # 直接调用显示对话框（已经在后台线程中）
            show_shortcut_dialog()

        except Exception as e:
            import traceback
            logger.error(f"检查桌面快捷方式失败: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
    
    # 在后台线程中执行检查
    thread = threading.Thread(target=check_shortcut_task, daemon=True)
    thread.start()


def _check_and_fix_auto_start(config_service: ConfigService) -> None:
    """检查并修复开机自启动路径。
    
    如果软件位置移动了，注册表中的路径会失效。
    此函数会检测并自动更新为当前路径。
    """
    import sys
    from pathlib import Path
    
    # 仅编译后生效
    if Path(sys.argv[0]).suffix.lower() != '.exe':
        return
    
    # 仅当用户开启了自启动时检查
    auto_start_enabled = config_service.get_config_value("auto_start", False)
    if not auto_start_enabled:
        return
    
    try:
        import winreg
        
        app_name = "MTools"
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        current_exe = sys.argv[0]
        expected_cmd = f'"{current_exe}" --minimized'
        
        # 读取注册表中的当前值
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_READ | winreg.KEY_SET_VALUE
            )
            
            try:
                reg_value, _ = winreg.QueryValueEx(key, app_name)
                
                # 检查路径是否匹配
                if reg_value != expected_cmd:
                    # 路径不匹配，更新注册表
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, expected_cmd)
                    logger.info(f"开机自启动路径已更新: {expected_cmd}")
                    
            except FileNotFoundError:
                # 注册表项不存在，但配置中显示已启用，重新创建
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, expected_cmd)
                logger.info(f"开机自启动已重新注册: {expected_cmd}")
            
            winreg.CloseKey(key)
            
        except FileNotFoundError:
            # 整个 Run 键不存在（极少情况）
            pass
            
    except Exception as e:
        logger.warning(f"检查开机自启动路径失败: {e}")


# 启动应用
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # 获取 assets 目录路径（兼容源码运行和 Nuitka 打包环境）
    # 开发环境: src/assets (相对于 main.py)
    # 打包环境: exe所在目录/src/assets
    assets_path = Path(__file__).parent / "assets"
    if not assets_path.exists():
        # 打包环境下 __file__ 可能不可靠，使用 sys.argv[0] 定位
        app_dir = Path(sys.argv[0]).parent
        for candidate in [app_dir / "src" / "assets", app_dir / "assets"]:
            if candidate.exists():
                assets_path = candidate
                break
    
    ft.run(main, assets_dir=str(assets_path))
