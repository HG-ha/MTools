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
        
        # 主题模式设置部分
        theme_mode_section: ft.Container = self._build_theme_mode_section()
        
        # 主题色设置部分
        theme_color_section: ft.Container = self._build_theme_color_section()
        
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
                theme_mode_section,
                ft.Container(height=PADDING_LARGE),
                theme_color_section,
                ft.Container(height=PADDING_LARGE),
                font_section,
                ft.Container(height=PADDING_LARGE),
                about_section,
            ],
            spacing=0,
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条
        )
    
    def _build_theme_mode_section(self) -> ft.Container:
        """构建主题模式设置部分。
        
        Returns:
            主题模式设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "主题模式",
            size=20,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
        )
        
        # 获取当前保存的主题模式
        saved_theme_mode = self.config_service.get_config_value("theme_mode", "system")
        
        # 主题模式单选按钮
        self.theme_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.BRIGHTNESS_AUTO, size=32, color=TEXT_PRIMARY),
                                ft.Text("跟随系统", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="system",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "system" else 1, ft.Colors.PRIMARY if saved_theme_mode == "system" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("system"),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.LIGHT_MODE, size=32, color=TEXT_PRIMARY),
                                ft.Text("浅色模式", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="light",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "light" else 1, ft.Colors.PRIMARY if saved_theme_mode == "light" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("light"),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.DARK_MODE, size=32, color=TEXT_PRIMARY),
                                ft.Text("深色模式", size=14, weight=ft.FontWeight.W_500),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        data="dark",
                        width=120,
                        height=100,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        border=ft.border.all(2 if saved_theme_mode == "dark" else 1, ft.Colors.PRIMARY if saved_theme_mode == "dark" else ft.Colors.OUTLINE),
                        padding=PADDING_MEDIUM,
                        ink=True,
                        on_click=lambda e: self._on_theme_mode_container_click("dark"),
                    ),
                ],
                spacing=PADDING_LARGE,
            ),
            value=saved_theme_mode,
        )
        
        # 保存主题模式容器的引用，用于更新样式
        self.theme_mode_containers: list = [
            self.theme_mode_radio.content.controls[0],
            self.theme_mode_radio.content.controls[1],
            self.theme_mode_radio.content.controls[2],
        ]
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "主题模式会立即生效",
            size=12,
            color=TEXT_SECONDARY,
        )
        
        # 组装主题模式设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    self.theme_mode_radio,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _on_theme_mode_container_click(self, mode: str) -> None:
        """主题模式容器点击事件处理。
        
        Args:
            mode: 主题模式 ("system", "light", "dark")
        """
        # 更新RadioGroup的值
        self.theme_mode_radio.value = mode
        
        # 保存到配置
        if self.config_service.set_config_value("theme_mode", mode):
            # 立即应用主题模式
            if mode == "system":
                self.page.theme_mode = ft.ThemeMode.SYSTEM
            elif mode == "light":
                self.page.theme_mode = ft.ThemeMode.LIGHT
            else:  # dark
                self.page.theme_mode = ft.ThemeMode.DARK
            
            # 更新所有容器的边框样式
            for container in self.theme_mode_containers:
                is_selected = container.data == mode
                container.border = ft.border.all(
                    2 if is_selected else 1,
                    ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
                )
                container.update()
            
            self.page.update()
            self._show_snackbar(f"已切换到{self._get_mode_name(mode)}", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题模式更新失败", ft.Colors.RED)
    
    def _get_mode_name(self, mode: str) -> str:
        """获取主题模式的中文名称。
        
        Args:
            mode: 主题模式
        
        Returns:
            中文名称
        """
        mode_names = {
            "system": "跟随系统",
            "light": "浅色模式",
            "dark": "深色模式",
        }
        return mode_names.get(mode, mode)
    
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
    
    def _build_theme_color_section(self) -> ft.Container:
        """构建主题色设置部分。
        
        Returns:
            主题色设置容器
        """
        # 分区标题
        section_title: ft.Text = ft.Text(
            "主题颜色",
            size=20,
            weight=ft.FontWeight.W_600,
            color=TEXT_PRIMARY,
        )
        
        # 预定义的主题色
        theme_colors = [
            ("#667EEA", "蓝紫色", "默认"),
            ("#6366F1", "靛蓝色", "科技感"),
            ("#8B5CF6", "紫色", "优雅"),
            ("#EC4899", "粉红色", "活力"),
            ("#F43F5E", "玫瑰红", "激情"),
            ("#EF4444", "红色", "热烈"),
            ("#F97316", "橙色", "温暖"),
            ("#F59E0B", "琥珀色", "明亮"),
            ("#10B981", "绿色", "清新"),
            ("#14B8A6", "青色", "自然"),
            ("#06B6D4", "天蓝色", "清爽"),
            ("#0EA5E9", "天空蓝", "开阔"),
            ("#6B7280", "灰色", "稳重"),
            ("#1F2937", "深灰", "专业"),
            ("#000000", "黑色", "经典"),
        ]
        
        # 获取当前主题色
        current_theme_color = self.config_service.get_config_value("theme_color", "#667EEA")
        
        # 创建主题色卡片
        self.theme_color_cards: list = []
        
        theme_cards_row: ft.Row = ft.Row(
            controls=[],
            wrap=True,
            spacing=PADDING_MEDIUM,
            run_spacing=PADDING_MEDIUM,
        )
        
        for color, name, desc in theme_colors:
            card = self._create_theme_color_card(color, name, desc, color == current_theme_color)
            self.theme_color_cards.append(card)
            theme_cards_row.controls.append(card)
        
        # 添加自定义颜色选项
        custom_color_card = self._create_custom_color_card(current_theme_color)
        self.theme_color_cards.append(custom_color_card)
        theme_cards_row.controls.append(custom_color_card)
        
        # 说明文字
        info_text: ft.Text = ft.Text(
            "主题色会立即生效，包括标题栏和所有界面元素。点击「自定义」可以使用调色盘选择任意颜色",
            size=12,
            color=TEXT_SECONDARY,
        )
        
        # 组装主题色设置部分
        return ft.Container(
            content=ft.Column(
                controls=[
                    section_title,
                    ft.Container(height=PADDING_MEDIUM),
                    theme_cards_row,
                    ft.Container(height=PADDING_MEDIUM // 2),
                    info_text,
                ],
                spacing=0,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
    
    def _create_theme_color_card(self, color: str, name: str, desc: str, is_selected: bool) -> ft.Container:
        """创建主题色选择卡片。
        
        Args:
            color: 颜色值
            name: 颜色名称
            desc: 颜色描述
            is_selected: 是否选中
        
        Returns:
            主题色卡片容器
        """
        # 颜色圆圈
        color_circle = ft.Container(
            width=40,
            height=40,
            border_radius=20,
            bgcolor=color,
            border=ft.border.all(3, ft.Colors.WHITE) if is_selected else ft.border.all(1, ft.Colors.OUTLINE),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.3, color),
                offset=ft.Offset(0, 2),
            ) if is_selected else None,
        )
        
        # 选中标记
        check_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE,
            size=16,
            color=color,
        ) if is_selected else None
        
        card = ft.Container(
            content=ft.Column(
                controls=[
                    color_circle,
                    ft.Container(height=4),
                    ft.Text(
                        name,
                        size=12,
                        weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                        color=TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        desc,
                        size=10,
                        color=TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    check_icon if check_icon else ft.Container(height=16),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            width=90,
            height=110,
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, color) if is_selected else None,
            border=ft.border.all(
                2 if is_selected else 1,
                color if is_selected else ft.Colors.OUTLINE
            ),
            data=color,  # 存储颜色值
            on_click=self._on_theme_color_click,
            ink=True,
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        
        return card
    
    def _create_custom_color_card(self, current_theme_color: str) -> ft.Container:
        """创建自定义颜色卡片。
        
        Args:
            current_theme_color: 当前主题色
        
        Returns:
            自定义颜色卡片容器
        """
        card: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.COLOR_LENS,
                        size=32,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        "自定义",
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=TEXT_PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "点击选择",
                        size=10,
                        color=TEXT_SECONDARY,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=90,
            height=110,
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            data="custom",
            on_click=self._open_color_picker,
            ink=True,
        )
        
        return card
    
    def _open_color_picker(self, e: ft.ControlEvent) -> None:
        """打开调色盘对话框。
        
        Args:
            e: 控件事件对象
        """
        # 当前主题色
        current_color = self.config_service.get_config_value("theme_color", "#667EEA")
        
        # 颜色预览框
        self.color_preview: ft.Container = ft.Container(
            width=80,
            height=80,
            border_radius=40,
            bgcolor=current_color,
            border=ft.border.all(2, ft.Colors.OUTLINE),
        )
        
        # 颜色输入框
        self.color_input: ft.TextField = ft.TextField(
            label="颜色代码",
            hint_text="#667EEA",
            value=current_color,
            width=200,
            on_change=self._on_color_input_change,
        )
        
        # 常用颜色网格
        common_colors = [
            "#EF4444", "#F97316", "#F59E0B", "#EAB308", "#84CC16", "#22C55E",
            "#10B981", "#14B8A6", "#06B6D4", "#0EA5E9", "#3B82F6", "#6366F1",
            "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E", "#667EEA",
            "#64748B", "#6B7280", "#71717A", "#78716C", "#57534E", "#44403C",
            "#1F2937", "#374151", "#4B5563", "#000000", "#FFFFFF", "#F3F4F6",
        ]
        
        color_grid_controls = []
        for color in common_colors:
            color_btn = ft.Container(
                width=32,
                height=32,
                bgcolor=color,
                border_radius=16,
                border=ft.border.all(1, ft.Colors.OUTLINE),
                tooltip=color,
                data=color,
                on_click=self._on_color_grid_click,
                ink=True,
            )
            color_grid_controls.append(color_btn)
        
        color_grid = ft.Row(
            controls=color_grid_controls,
            wrap=True,
            spacing=8,
            run_spacing=8,
            width=400,
        )
        
        # 对话框内容
        dialog_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.color_preview,
                        ft.Column(
                            controls=[
                                self.color_input,
                                ft.Text("输入#RRGGBB格式或点击下方颜色选择", size=11, color=TEXT_SECONDARY),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Container(height=PADDING_MEDIUM),
                ft.Text("常用颜色:", size=14, weight=ft.FontWeight.W_500),
                color_grid,
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 创建对话框
        def close_dialog(apply: bool = False):
            if apply:
                color_value = self.color_input.value.strip()
                if color_value:
                    self._apply_custom_color(color_value)
            self.color_picker_dialog.open = False
            self.page.update()
        
        self.color_picker_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("选择自定义颜色"),
            content=dialog_content,
            actions=[
                ft.TextButton("取消", on_click=lambda e: close_dialog(False)),
                ft.ElevatedButton("应用", on_click=lambda e: close_dialog(True)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(self.color_picker_dialog)
        self.color_picker_dialog.open = True
        self.page.update()
    
    def _on_color_input_change(self, e: ft.ControlEvent) -> None:
        """颜色输入框变化事件处理。
        
        Args:
            e: 控件事件对象
        """
        color_value = e.control.value.strip()
        
        # 确保以#开头
        if color_value and not color_value.startswith("#"):
            color_value = "#" + color_value
        
        # 验证颜色格式并更新预览
        import re
        if re.match(r'^#[0-9A-Fa-f]{6}$', color_value):
            self.color_preview.bgcolor = color_value
            self.color_preview.update()
    
    def _on_color_grid_click(self, e: ft.ControlEvent) -> None:
        """颜色网格点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        selected_color = e.control.data
        self.color_input.value = selected_color
        self.color_preview.bgcolor = selected_color
        self.color_input.update()
        self.color_preview.update()
    
    def _apply_custom_color(self, color_value: str) -> None:
        """应用自定义颜色。
        
        Args:
            color_value: 颜色值
        """
        # 确保以#开头
        if not color_value.startswith("#"):
            color_value = "#" + color_value
        
        # 验证颜色格式
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color_value):
            self._show_snackbar("颜色格式错误，请使用#RRGGBB格式（如#667EEA）", ft.Colors.RED)
            return
        
        # 保存并应用颜色
        if self.config_service.set_config_value("theme_color", color_value.upper()):
            # 立即更新页面主题色
            if self.page.theme:
                self.page.theme.color_scheme_seed = color_value
            if self.page.dark_theme:
                self.page.dark_theme.color_scheme_seed = color_value
            
            # 更新标题栏颜色
            self._update_title_bar_color(color_value)
            
            # 更新所有预定义颜色卡片为未选中状态
            for card in self.theme_color_cards:
                if card.data != "custom":
                    card.border = ft.border.all(1, ft.Colors.OUTLINE)
                    card.bgcolor = None
                    
                    if card.content and isinstance(card.content, ft.Column):
                        color_circle = card.content.controls[0]
                        if isinstance(color_circle, ft.Container):
                            color_circle.border = ft.border.all(1, ft.Colors.OUTLINE)
                            color_circle.shadow = None
                        
                        name_text = card.content.controls[2]
                        if isinstance(name_text, ft.Text):
                            name_text.weight = ft.FontWeight.NORMAL
                        
                        if len(card.content.controls) > 4:
                            card.content.controls[4] = ft.Container(height=16)
                    
                    card.update()
            
            # 更新整个页面
            self.page.update()
            self._show_snackbar(f"自定义主题色已应用: {color_value}", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题色更新失败", ft.Colors.RED)
    
    def _on_theme_color_click(self, e: ft.ControlEvent) -> None:
        """主题色卡片点击事件处理。
        
        Args:
            e: 控件事件对象
        """
        clicked_color: str = e.control.data
        current_color = self.config_service.get_config_value("theme_color", "#667EEA")
        
        if clicked_color == current_color:
            return  # 已选中，无需更新
        
        # 保存主题色设置
        if self.config_service.set_config_value("theme_color", clicked_color):
            # 立即更新页面主题色
            if self.page.theme:
                self.page.theme.color_scheme_seed = clicked_color
            if self.page.dark_theme:
                self.page.dark_theme.color_scheme_seed = clicked_color
            
            # 更新标题栏颜色（如果标题栏存在）
            self._update_title_bar_color(clicked_color)
            
            # 更新所有卡片的样式
            for card in self.theme_color_cards:
                # 跳过自定义颜色卡片（它的结构不同）
                if card.data == "custom":
                    continue
                
                is_selected = card.data == clicked_color
                color = card.data
                
                # 更新边框和背景
                card.border = ft.border.all(
                    2 if is_selected else 1,
                    color if is_selected else ft.Colors.OUTLINE
                )
                card.bgcolor = ft.Colors.with_opacity(0.05, color) if is_selected else None
                
                # 更新内容
                if card.content and isinstance(card.content, ft.Column):
                    # 更新颜色圆圈
                    color_circle = card.content.controls[0]
                    if isinstance(color_circle, ft.Container):
                        color_circle.border = ft.border.all(3, ft.Colors.WHITE) if is_selected else ft.border.all(1, ft.Colors.OUTLINE)
                        color_circle.shadow = ft.BoxShadow(
                            spread_radius=0,
                            blur_radius=8,
                            color=ft.Colors.with_opacity(0.3, color),
                            offset=ft.Offset(0, 2),
                        ) if is_selected else None
                    
                    # 更新名称文字粗细
                    name_text = card.content.controls[2]
                    if isinstance(name_text, ft.Text):
                        name_text.weight = ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL
                    
                    # 更新选中标记（只有预定义颜色卡片有这个元素）
                    if len(card.content.controls) > 4:
                        if is_selected:
                            card.content.controls[4] = ft.Icon(
                                ft.Icons.CHECK_CIRCLE,
                                size=16,
                                color=color,
                            )
                        else:
                            card.content.controls[4] = ft.Container(height=16)
                
                card.update()
            
            # 更新整个页面
            self.page.update()
            self._show_snackbar("主题色已更新", ft.Colors.GREEN)
        else:
            self._show_snackbar("主题色更新失败", ft.Colors.RED)
    
    def _update_title_bar_color(self, color: str) -> None:
        """更新标题栏颜色。
        
        Args:
            color: 新的主题色
        """
        # 尝试找到标题栏组件并更新颜色
        try:
            # 从页面的controls中查找标题栏
            for control in self.page.controls:
                if hasattr(control, 'controls'):
                    for sub_control in control.controls:
                        # 检查是否是标题栏（通过类名或属性判断）
                        if hasattr(sub_control, 'gradient'):
                            # 更新渐变色
                            sub_control.gradient = ft.LinearGradient(
                                begin=ft.alignment.center_left,
                                end=ft.alignment.center_right,
                                colors=[color, color],
                            )
                            sub_control.update()
                            break
        except Exception:
            pass  # 如果更新失败也不影响其他功能
    
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

