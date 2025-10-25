"""设置视图模块。

提供应用设置界面，包括数据目录设置、主题设置等。
"""

from pathlib import Path
from typing import Callable, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService


class SettingsView(ft.Container):
    """设置视图类。
    
    提供应用设置功能，包括：
    - 数据存储目录设置
    - 默认/自定义目录切换
    - 目录浏览和选择
    """

    def __init__(self, page: ft.Page, config_service: ConfigService) -> None:
        """初始化设置视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.expand: bool = True
        # 右侧多留一些空间给滚动条
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE + 16,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 页面标题
        title: ft.Text = ft.Text(
            "设置",
            size=32,
            weight=ft.FontWeight.BOLD,
            color=TEXT_PRIMARY,
        )
        
        # 数据目录设置部分
        data_dir_section: ft.Container = self._build_data_dir_section()
        
        # 字体设置部分
        font_section: ft.Container = self._build_font_section()
        
        # 关于部分
        about_section: ft.Container = self._build_about_section()
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                title,
                ft.Container(height=PADDING_LARGE),
                data_dir_section,
                ft.Container(height=PADDING_LARGE),
                font_section,
                ft.Container(height=PADDING_LARGE),
                about_section,
            ],
            spacing=0,
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条
        )
    
    def _build_data_dir_section(self) -> ft.Container:
        """构建数据目录设置部分。
        
        Returns:
            数据目录设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "数据存储",
            size=20,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
        )
        
        # 当前数据目录显示
        current_dir: Path = self.config_service.get_data_dir()
        is_custom: bool = self.config_service.get_config_value("use_custom_dir", False)
        
        self.data_dir_text: ft.Text = ft.Text(
            str(current_dir),
            size=14,
            color=TEXT_SECONDARY,
            selectable=True,
        )
        
        # 目录类型单选按钮
        self.dir_type_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="default",
                        label="使用默认目录（遵循系统规范）",
                    ),
                    ft.Radio(
                        value="custom",
                        label="使用自定义目录",
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="custom" if is_custom else "default",
            on_change=self._on_dir_type_change,
        )
        
        # 浏览按钮
        browse_button: ft.ElevatedButton = ft.ElevatedButton(
            text="浏览...",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._on_browse_click,
            disabled=not is_custom,
        )
        
        self.browse_button: ft.ElevatedButton = browse_button
        
        # 打开目录按钮
        open_dir_button: ft.OutlinedButton = ft.OutlinedButton(
            text="打开数据目录",
            icon=ft.Icons.FOLDER,
            on_click=self._on_open_dir_click,
        )
        
        # 按钮行
        button_row: ft.Row = ft.Row(
            controls=[browse_button, open_dir_button],
            spacing=PADDING_MEDIUM,
        )
        
        # 目录路径容器
        dir_path_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("当前数据目录:", size=14, weight=ft.FontWeight.W_500),
                    self.data_dir_text,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "数据目录用于存储应用的处理结果和临时文件",
            size=12,
            color=TEXT_SECONDARY,
            italic=True,
        )
        
        # 组装数据目录部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.dir_type_radio,
                    ft.Container(height=PADDING_MEDIUM),
                    dir_path_container,
                    ft.Container(height=PADDING_MEDIUM),
                    button_row,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _build_font_section(self) -> ft.Container:
        """构建字体设置部分。
        
        Returns:
            字体设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "字体设置",
            size=20,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
        )
        
        # 常用字体列表
        common_fonts = [
            ("System", "系统默认"),
            ("Microsoft YaHei", "微软雅黑"),
            ("SimSun", "宋体"),
            ("SimHei", "黑体"),
            ("KaiTi", "楷体"),
            ("FangSong", "仿宋"),
            ("Arial", "Arial"),
            ("Consolas", "Consolas"),
            ("Courier New", "Courier New"),
            ("Times New Roman", "Times New Roman"),
            ("Verdana", "Verdana"),
        ]
        
        # 获取当前字体
        current_font = self.config_service.get_config_value("font_family", "System")
        current_scale = self.config_service.get_config_value("font_scale", 1.0)
        
        # 字体下拉选择
        self.font_dropdown = ft.Dropdown(
            label="选择字体",
            options=[
                ft.dropdown.Option(key=font[0], text=font[1])
                for font in common_fonts
            ],
            value=current_font,
            on_change=self._on_font_change,
            width=300,
        )
        
        # 字体大小滑块
        self.font_scale_text = ft.Text(
            f"字体大小: {int(current_scale * 100)}%",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        
        self.font_scale_slider = ft.Slider(
            min=80,
            max=150,
            divisions=14,
            value=current_scale * 100,
            label="{value}%",
            on_change=self._on_font_scale_change,
        )
        
        # 字体大小容器
        font_size_container = ft.Column(
            controls=[
                self.font_scale_text,
                self.font_scale_slider,
                ft.Text(
                    "80% (较小) - 100% (标准) - 150% (特大)",
                    size=11,
                    color=TEXT_SECONDARY,
                    italic=True,
                ),
            ],
            spacing=PADDING_MEDIUM // 2,
        )
        
        # 预览文本
        base_preview_size = 16
        preview_size = int(base_preview_size * current_scale)
        self.font_preview_text = ft.Text(
            "字体预览文本 Font Preview Text 0123456789",
            size=preview_size,
            font_family=current_font,
        )
        
        # 预览容器
        preview_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预览:", size=14, weight=ft.FontWeight.W_500),
                    self.font_preview_text,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "更改字体和字体大小后需要重启应用才能完全生效",
            size=12,
            color=TEXT_SECONDARY,
            italic=True,
        )
        
        # 组装字体设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.font_dropdown,
                    ft.Container(height=PADDING_MEDIUM),
                    font_size_container,
                    ft.Container(height=PADDING_MEDIUM),
                    preview_container,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _build_about_section(self) -> ft.Container:
        """构建关于部分。
        
        Returns:
            关于部分容器
        """
        section_title: ft.Text = ft.Text(
            "关于",
            size=20,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
        )
        
        app_info: ft.Column = ft.Column(
            controls=[
                ft.Text("MyTools - 多功能工具箱", size=16, weight=ft.FontWeight.W_500),
                ft.Text("版本: 0.1.0", size=14, color=TEXT_SECONDARY),
                ft.Container(height=PADDING_MEDIUM // 2),
                ft.Text(
                    "一个集成了图片处理、音视频处理、编码转换、代码格式化等功能的桌面应用",
                    size=14,
                    color=TEXT_SECONDARY,
                ),
            ],
            spacing=PADDING_MEDIUM // 2,
        )
        
        # 重置窗口按钮
        reset_window_button: ft.OutlinedButton = ft.OutlinedButton(
            text="重置窗口位置和大小",
            icon=ft.Icons.RESTORE,
            on_click=self._on_reset_window_position,
            tooltip="将窗口位置和大小重置为默认值",
        )
        
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    app_info,
                    ft.Container(height=PADDING_MEDIUM),
                    reset_window_button,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_dir_type_change(self, e: ft.ControlEvent) -> None:
        """目录类型切换事件处理。
        
        Args:
            e: 控件事件对象
        """
        is_custom: bool = e.control.value == "custom"
        self.browse_button.disabled = not is_custom
        self.browse_button.update()
        
        if not is_custom:
            # 切换到默认目录
            if self.config_service.reset_to_default_dir():
                self.data_dir_text.value = str(self.config_service.get_data_dir())
                self.data_dir_text.update()
                self._show_snackbar("已切换到默认数据目录", ft.Colors.GREEN)
            else:
                self._show_snackbar("切换失败", ft.Colors.RED)
    
    def _on_browse_click(self, e: ft.ControlEvent) -> None:
        """浏览按钮点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        # 创建文件选择器
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                if self.config_service.set_data_dir(result.path, is_custom=True):
                    self.data_dir_text.value = result.path
                    self.data_dir_text.update()
                    self._show_snackbar("数据目录已更新", ft.Colors.GREEN)
                else:
                    self._show_snackbar("更新数据目录失败", ft.Colors.RED)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择数据存储目录")
    
    def _on_open_dir_click(self, e: ft.ControlEvent) -> None:
        """打开目录按钮点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        import subprocess
        import platform
        
        data_dir: Path = self.config_service.get_data_dir()
        
        try:
            system: str = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", str(data_dir)])
            elif system == "Darwin":
                subprocess.run(["open", str(data_dir)])
            else:
                subprocess.run(["xdg-open", str(data_dir)])
        except Exception as ex:
            self._show_snackbar(f"打开目录失败: {ex}", ft.Colors.RED)
    
    def _on_font_change(self, e: ft.ControlEvent) -> None:
        """字体更改事件处理。
        
        Args:
            e: 控件事件对象
        """
        selected_font = e.control.value
        
        # 保存字体设置
        if self.config_service.set_config_value("font_family", selected_font):
            # 更新预览文本字体
            self.font_preview_text.font_family = selected_font
            self.font_preview_text.update()
            
            # 尝试更新页面字体（部分生效）
            if self.page.theme:
                self.page.theme.font_family = selected_font
            if self.page.dark_theme:
                self.page.dark_theme.font_family = selected_font
            self.page.update()
            
            self._show_snackbar("字体已更新，重启应用后完全生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("字体更新失败", ft.Colors.RED)
    
    def _on_font_scale_change(self, e: ft.ControlEvent) -> None:
        """字体大小更改事件处理。
        
        Args:
            e: 控件事件对象
        """
        scale_percent = int(e.control.value)
        scale = scale_percent / 100.0
        
        # 更新文本显示
        self.font_scale_text.value = f"字体大小: {scale_percent}%"
        self.font_scale_text.update()
        
        # 保存字体大小设置
        if self.config_service.set_config_value("font_scale", scale):
            # 更新预览文本大小
            base_size = 16
            new_size = int(base_size * scale)
            self.font_preview_text.size = new_size
            self.font_preview_text.update()
            
            self._show_snackbar(f"字体大小已设置为 {scale_percent}%，重启应用后完全生效", ft.Colors.GREEN)
        else:
            self._show_snackbar("字体大小更新失败", ft.Colors.RED)
    
    def _on_reset_window_position(self, e: ft.ControlEvent) -> None:
        """重置窗口位置和大小事件处理。
        
        Args:
            e: 控件事件对象
        """
        from constants import WINDOW_WIDTH, WINDOW_HEIGHT
        
        # 清除保存的窗口位置和大小
        self.config_service.set_config_value("window_left", None)
        self.config_service.set_config_value("window_top", None)
        self.config_service.set_config_value("window_width", None)
        self.config_service.set_config_value("window_height", None)
        
        # 重置窗口大小为默认值
        self.page.window.width = WINDOW_WIDTH
        self.page.window.height = WINDOW_HEIGHT
        
        # 将窗口移动到屏幕中央
        self.page.window.center()
        self.page.update()
        
        self._show_snackbar("窗口位置和大小已重置为默认值", ft.Colors.GREEN)
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

