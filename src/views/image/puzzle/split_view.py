# -*- coding: utf-8 -*-
"""单图切分视图模块。

提供单图切分（九宫格）功能的用户界面。
"""

import io
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import flet as ft
from PIL import Image

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils


class ImagePuzzleSplitView(ft.Container):
    """单图切分视图类。
    
    提供单图切分功能：
    - 九宫格切分
    - 自定义行列数
    - 随机打乱
    - 间距和背景色设置
    - 实时预览
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.bmp', '.webp', '.tiff', '.gif'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化单图切分视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_file: Optional[Path] = None
        self.preview_image: Optional[Image.Image] = None
        self.is_processing: bool = False
        
        # GIF 支持
        self.is_animated_gif: bool = False
        self.gif_frame_count: int = 0
        self.current_frame_index: int = 0
        
        # 实时预览支持
        self._last_update_time: float = 0.0
        self._update_timer: Optional[threading.Timer] = None
        self._auto_preview_enabled: bool = False  # 是否启用自动预览（默认关闭以提升性能）
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 顶部：标题和返回按钮
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("单图切分", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 左侧：文件选择和预览
        # 自动预览复选框（需要在 file_select_area 之前定义）
        self.auto_preview_switch: ft.Checkbox = ft.Checkbox(
            label="实时预览",
            value=False,
            on_change=self._on_auto_preview_toggle,
            tooltip="开启后，修改参数时将自动生成预览\n处理大图片时可能会占用较多系统性能",
        )
        
        # 随机打乱选项（需要在 file_select_area 之前定义）
        self.split_shuffle: ft.Checkbox = ft.Checkbox(
            label="随机打乱",
            value=False,
            on_change=self._on_option_change,
        )
        
        # 输出模式选择
        self.output_mode: ft.Dropdown = ft.Dropdown(
            label="输出模式",
            value="merged",
            options=[
                ft.dropdown.Option("merged", "拼接为单图"),
                ft.dropdown.Option("individual", "导出每个切块"),
            ],
            width=160,
            on_select=self._on_output_mode_change,
            tooltip="选择是输出拼接后的单张图片，还是导出所有切块为单独文件",
        )
        
        # 空状态提示
        self.empty_state_widget: ft.Column = ft.Column(
            controls=[
                ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                ft.Text("点击选择文件按钮或点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=PADDING_MEDIUM // 2,
            visible=True,
        )
        
        # 原图预览
        self.original_image_widget: ft.Image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("原图预览:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_file,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Row(
                    controls=[
                        self.auto_preview_switch,
                        self.split_shuffle,
                        self.output_mode,
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "选择一张图片进行切分拼接",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(left=4, bottom=4),
                ),
                ft.Container(
                    content=ft.Stack(
                        controls=[
                            ft.Container(
                                content=self.empty_state_widget,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Container(
                                content=self.original_image_widget,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                    ),
                    expand=True,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    bgcolor=ft.Colors.SURFACE,
                    on_click=self._on_select_file,
                    tooltip="点击选择图片",
                    ink=True,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # GIF 帧选择器
        self.gif_frame_input: ft.TextField = ft.TextField(
            value="1",
            width=60,
            text_align=ft.TextAlign.CENTER,
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=self._on_frame_input_submit,
            on_blur=self._on_frame_input_submit,  # 失去焦点时也触发
        )
        
        self.gif_total_frames_text: ft.Text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # GIF 动画保留选项（需要在 gif_frame_selector 之前定义）
        self.keep_gif_animation: ft.Checkbox = ft.Checkbox(
            label="保留 GIF 动画",
            value=False,
            on_change=self._on_option_change,
        )
        
        # 性能警告提示
        self.performance_warning: ft.Container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ORANGE),
                    ft.Text(
                        "切分数量较多，生成预览和导出可能需要较长时间",
                        size=12,
                        color=ft.Colors.ORANGE,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ORANGE),
            visible=False,
            margin=ft.margin.only(bottom=PADDING_MEDIUM),
        )
        
        self.gif_frame_selector: ft.Container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ORANGE),
                    ft.Text("GIF 文件 - 选择要切分的帧:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.IconButton(
                        icon=ft.Icons.SKIP_PREVIOUS,
                        icon_size=16,
                        on_click=self._on_gif_prev_frame,
                        tooltip="上一帧",
                    ),
                    self.gif_frame_input,
                    self.gif_total_frames_text,
                    ft.IconButton(
                        icon=ft.Icons.SKIP_NEXT,
                        icon_size=16,
                        on_click=self._on_gif_next_frame,
                        tooltip="下一帧",
                    ),
                    ft.Container(width=PADDING_MEDIUM),  # 间隔
                    self.keep_gif_animation,  # 添加到这一行
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM // 2,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ORANGE),
            visible=False,
            margin=ft.margin.only(bottom=PADDING_MEDIUM),
        )
        
        # 参数输入
        self.split_rows: ft.TextField = ft.TextField(
            label="行数",
            value="3",
            width=68,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="1-100",
            on_change=self._on_option_change,
        )
        
        self.split_cols: ft.TextField = ft.TextField(
            label="列数",
            value="3",
            width=68,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="1-100",
            on_change=self._on_option_change,
        )
        
        self.split_spacing_input: ft.TextField = ft.TextField(
            label="切块间距",
            value="5",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix="px",
            on_change=self._on_option_change,
        )
        
        self.corner_radius_input: ft.TextField = ft.TextField(
            label="切块圆角",
            value="0",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix="px",
            on_change=self._on_option_change,
        )
        
        self.overall_corner_radius_input: ft.TextField = ft.TextField(
            label="整体圆角",
            value="0",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix="px",
            on_change=self._on_option_change,
        )
        
        # 背景色选择（预设+自定义+背景图片）
        self.split_bg_color: ft.Dropdown = ft.Dropdown(
            label="背景",
            value="white",
            options=[
                ft.dropdown.Option("white", "白色"),
                ft.dropdown.Option("black", "黑色"),
                ft.dropdown.Option("gray", "灰色"),
                ft.dropdown.Option("transparent", "透明"),
                ft.dropdown.Option("custom", "自定义..."),
                ft.dropdown.Option("image", "选择图片"),
            ],
            width=100,
            on_select=self._on_bg_color_change,
        )
        
        # 背景图片选择按钮
        self.bg_image_button: ft.Button = ft.Button(
            "选择图片",
            icon=ft.Icons.IMAGE,
            on_click=self._on_select_bg_image,
            visible=False,
            height=40,
        )
        
        # 背景图片路径
        self.bg_image_path: Optional[Path] = None
        
        # RGB颜色输入
        self.custom_color_r: ft.TextField = ft.TextField(
            label="R",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        self.custom_color_g: ft.TextField = ft.TextField(
            label="G",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        self.custom_color_b: ft.TextField = ft.TextField(
            label="B",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        # 不透明度控制
        self.piece_opacity_input: ft.TextField = ft.TextField(
            label="切块不透明度",
            value="100",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix="%",
            on_change=self._on_option_change,
        )
        
        self.bg_opacity_input: ft.TextField = ft.TextField(
            label="背景不透明度",
            value="100",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix="%",
            on_change=self._on_option_change,
        )
        
        # 参数区域：自动换行
        options_area: ft.Row = ft.Row(
            controls=[
                self.split_rows,
                self.split_cols,
                self.split_spacing_input,
                self.corner_radius_input,
                self.overall_corner_radius_input,
                self.piece_opacity_input,
                self.split_bg_color,
                self.custom_color_r,
                self.custom_color_g,
                self.custom_color_b,
                self.bg_image_button,
                self.bg_opacity_input,
            ],
            wrap=True,
            spacing=PADDING_MEDIUM,
            run_spacing=PADDING_MEDIUM,
        )
        
        # 右侧：预览区域（可点击查看）
        self.preview_image_widget: ft.Image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
        )
        
        # 原图显示区域 - 使用Container居中
        self.original_image_container: ft.Container = ft.Container(
            content=self.original_image_widget,
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
        
        self.preview_info_text: ft.Text = ft.Text(
            "选择图片后将自动生成预览",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        
        # 将预览区域改为可点击的容器
        preview_content = ft.Stack(
            controls=[
                ft.Container(
                    content=self.preview_info_text,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    content=self.preview_image_widget,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
        )
        
        preview_area: ft.Container = ft.Container(
            content=preview_content,
            expand=1,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.SURFACE,
            on_click=self._on_preview_click,
            tooltip="点击用系统查看器打开",
        )
        
        # 上部：左右各一半显示原图和预览图
        top_row: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=file_select_area,
                    expand=1,
                    height=400,
                ),
                ft.Container(
                    content=preview_area,
                    expand=1,
                    height=400,
                ),
            ],
            spacing=PADDING_LARGE,
        )
        
        # 下部：参数设置
        bottom_content: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.gif_frame_selector,
                    self.performance_warning,
                    options_area,
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
        )
        
        # 底部：按钮行（生成预览 + 保存结果）
        self.preview_button: ft.Button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PREVIEW, size=20),
                    ft.Text("生成预览", size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=self._on_generate_preview,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )
        
        self.save_button: ft.Button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=20),
                    ft.Text("保存结果", size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=self._on_save_result,
            disabled=True,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )
        
        # 按钮行
        buttons_row: ft.Row = ft.Row(
            controls=[
                self.preview_button,
                self.save_button,
            ],
            spacing=PADDING_MEDIUM,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                ft.Container(height=PADDING_LARGE),
                top_row,
                ft.Container(height=PADDING_LARGE),
                bottom_content,
                ft.Container(height=PADDING_MEDIUM),
                buttons_row,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=0,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_option_change(self, e: ft.ControlEvent) -> None:
        """选项改变事件 - 支持实时预览。"""
        # 检查性能警告
        self._check_performance_warning()
        
        # 如果启用了自动预览且已选择文件，则自动更新预览
        if self._auto_preview_enabled and self.selected_file:
            self._schedule_auto_preview()
        else:
            # 清空预览（选项改变后需要重新生成）
            self._clear_preview()
    
    def _check_performance_warning(self) -> None:
        """检查并显示性能警告。"""
        try:
            rows = int(self.split_rows.value or 3)
            cols = int(self.split_cols.value or 3)
            
            # 如果行数或列数超过5，显示警告
            should_warn = rows > 5 or cols > 5
            
            if should_warn:
                total_pieces = rows * cols
                self.performance_warning.content.controls[1].value = (
                    f"切分数量较多（{rows}×{cols}={total_pieces}块），"
                    f"生成预览和导出可能需要较长时间"
                )
            
            self.performance_warning.visible = should_warn
            
            try:
                self._page.update()
            except Exception:
                pass
        except ValueError:
            # 输入无效时隐藏警告
            self.performance_warning.visible = False
            try:
                self._page.update()
            except Exception:
                pass
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        # 当切换到"导出每个切块"模式时，某些选项不适用
        is_individual_mode = self.output_mode.value == "individual"
        
        # 更新保存按钮文本
        if is_individual_mode:
            self.save_button.content.controls[1].value = "导出所有切块"
            self.save_button.tooltip = "将所有切块导出为单独的文件到指定目录"
        else:
            self.save_button.content.controls[1].value = "保存结果"
            self.save_button.tooltip = "保存拼接后的结果图片"
        
        # 在单独导出模式下，不需要预览也可以保存
        if is_individual_mode:
            self.save_button.disabled = False if self.selected_file else True
        else:
            self.save_button.disabled = not bool(self.preview_image)
        
        try:
            self._page.update()
        except Exception:
            pass
        
        # 触发实时预览
        if self._auto_preview_enabled and self.selected_file:
            self._schedule_auto_preview()
        else:
            self._clear_preview()
    
    def _schedule_auto_preview(self) -> None:
        """安排自动预览更新（使用防抖机制）。"""
        # 取消之前的定时器
        if self._update_timer is not None:
            self._update_timer.cancel()
        
        # 设置新的定时器，延迟500ms后生成预览
        self._update_timer = threading.Timer(0.5, self._auto_generate_preview)
        self._update_timer.daemon = True
        self._update_timer.start()
    
    def _auto_generate_preview(self) -> None:
        """自动生成预览（防抖后触发）。"""
        # 模拟点击生成预览按钮，传递 is_auto=True 标记
        class FakeEvent:
            is_auto = True
        
        self._on_generate_preview(FakeEvent())
    
    def _on_auto_preview_toggle(self, e: ft.ControlEvent) -> None:
        """自动预览开关切换事件。"""
        self._auto_preview_enabled = self.auto_preview_switch.value
        
        # 更新提示文本
        if not self.preview_image:
            if self._auto_preview_enabled:
                self.preview_info_text.value = "选择图片后将自动生成预览"
            else:
                self.preview_info_text.value = "选择图片后，点击「生成预览」查看效果"
            try:
                self._page.update()
            except Exception:
                pass
        
        # 如果打开了自动预览，立即生成一次预览
        if self._auto_preview_enabled and self.selected_file:
            self._schedule_auto_preview()
    
    
    def _on_bg_color_change(self, e: ft.ControlEvent) -> None:
        """背景色变化事件。"""
        is_custom = self.split_bg_color.value == "custom"
        is_image = self.split_bg_color.value == "image"
        
        self.custom_color_r.visible = is_custom
        self.custom_color_g.visible = is_custom
        self.custom_color_b.visible = is_custom
        self.bg_image_button.visible = is_image
        
        try:
            self._page.update()
        except Exception:
            pass
        
        # 触发实时预览
        if self._auto_preview_enabled and self.selected_file:
            self._schedule_auto_preview()
        else:
            self._clear_preview()
    
    async def _on_select_bg_image(self, e: ft.ControlEvent) -> None:
        """选择背景图片按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择背景图片",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "tiff", "gif"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            self.bg_image_path = Path(result[0].path)
            self.bg_image_button.text = f"背景: {self.bg_image_path.name[:15]}..."
            try:
                self._page.update()
            except Exception:
                pass
            
            # 触发实时预览
            if self._auto_preview_enabled and self.selected_file:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    
    async def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "tiff", "gif"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            self.selected_file = Path(result[0].path)
            self._update_file_info()
            
            # 更新保存按钮状态（单独导出模式下选择文件后即可保存）
            if self.output_mode.value == "individual":
                self.save_button.disabled = False
                try:
                    self._page.update()
                except Exception:
                    pass
            
            # 选择文件后自动生成首次预览
            if self._auto_preview_enabled:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _update_file_info(self) -> None:
        """更新文件信息显示（包括原图预览）。"""
        if not self.selected_file:
            self.empty_state_widget.visible = True
            self.original_image_widget.visible = False
        else:
            file_info = self.image_service.get_image_info(self.selected_file)
            
            if 'error' in file_info:
                # 错误时显示空状态
                self.empty_state_widget.visible = True
                self.empty_state_widget.controls[1].value = "加载失败"
                self.empty_state_widget.controls[2].value = f"错误: {file_info['error']}"
                self.original_image_widget.visible = False
            else:
                # 检测是否为动态 GIF
                self.is_animated_gif = GifUtils.is_animated_gif(self.selected_file)
                
                if self.is_animated_gif:
                    self.gif_frame_count = GifUtils.get_frame_count(self.selected_file)
                    self.current_frame_index = 0
                    
                    # 显示 GIF 帧选择器（包含动画保留选项）
                    self.gif_frame_selector.visible = True
                    self.gif_frame_input.value = "1"
                    self.gif_total_frames_text.value = f"/ {self.gif_frame_count}"
                    
                    # 提取第一帧并保存为临时文件
                    try:
                        frame_image = GifUtils.extract_frame(self.selected_file, 0)
                        if frame_image:
                            # 使用时间戳避免缓存问题
                            import time
                            timestamp = int(time.time() * 1000)
                            temp_dir = self.config_service.get_temp_dir()
                            temp_path = temp_dir / f"gif_frame_0_{timestamp}.png"
                            frame_image.save(temp_path)
                            
                            # 清理旧的GIF帧临时文件
                            try:
                                for old_file in temp_dir.glob("gif_frame_*.png"):
                                    if old_file != temp_path:
                                        try:
                                            old_file.unlink()
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            
                            self.original_image_widget.src = str(temp_path)
                            self.original_image_widget.visible = True
                            self.empty_state_widget.visible = False
                        else:
                            raise Exception("无法提取 GIF 帧")
                    except Exception as e:
                        self.empty_state_widget.visible = True
                        self.empty_state_widget.controls[1].value = "GIF 加载失败"
                        self.empty_state_widget.controls[2].value = f"无法提取 GIF 帧: {e}"
                        self.original_image_widget.visible = False
                        self.gif_frame_selector.visible = False
                else:
                    # 隐藏 GIF 帧选择器（包含动画保留选项）
                    self.gif_frame_selector.visible = False
                    # 显示原图预览
                    try:
                        self.original_image_widget.src = self.selected_file
                        self.original_image_widget.visible = True
                        self.empty_state_widget.visible = False
                    except Exception as e:
                        self.empty_state_widget.visible = True
                        self.empty_state_widget.controls[1].value = "加载失败"
                        self.empty_state_widget.controls[2].value = f"无法加载图片: {e}"
                        self.original_image_widget.visible = False
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _clear_preview(self) -> None:
        """清空预览。"""
        self.preview_image = None
        self.preview_image_widget.src = None  # 清空图片源
        self.preview_image_widget.visible = False
        
        # 根据是否启用实时预览，显示不同的提示文本
        if self._auto_preview_enabled:
            self.preview_info_text.value = "选择图片后将自动生成预览"
        else:
            self.preview_info_text.value = "选择图片后，点击「生成预览」查看效果"
        
        self.preview_info_text.visible = True
        self.save_button.disabled = True
        try:
            self._page.update()
        except Exception:
            pass
    
    def _on_generate_preview(self, e: ft.ControlEvent) -> None:
        """生成预览 - 支持自动预览模式。"""
        # 检测是否为自动预览
        is_auto = hasattr(e, 'is_auto') and e.is_auto
        
        if self.is_processing:
            # 如果正在处理中，显示提示（特别是自动预览时）
            if is_auto:
                self.preview_info_text.value = "正在处理中，请稍候..."
                self.preview_info_text.visible = True
                try:
                    self._page.update()
                except Exception:
                    pass
            return
        
        if not self.selected_file:
            # 只在手动点击时提示
            if not is_auto:
                self._show_snackbar("请先选择图片", ft.Colors.ORANGE)
            return
        
        try:
            rows = int(self.split_rows.value or 3)
            cols = int(self.split_cols.value or 3)
            shuffle = self.split_shuffle.value
            spacing = int(self.split_spacing_input.value or 5)
            corner_radius = int(self.corner_radius_input.value or 0)
            overall_corner_radius = int(self.overall_corner_radius_input.value or 0)
            bg_color = self.split_bg_color.value
            
            # 获取透明度值（0-100转换为0-255）
            piece_opacity = int(self.piece_opacity_input.value or 100)
            piece_opacity = max(0, min(100, piece_opacity))
            piece_opacity = int(piece_opacity * 255 / 100)
            
            bg_opacity = int(self.bg_opacity_input.value or 100)
            bg_opacity = max(0, min(100, bg_opacity))
            bg_opacity = int(bg_opacity * 255 / 100)
            
            # 获取自定义RGB值
            custom_rgb = None
            if bg_color == "custom":
                r = int(self.custom_color_r.value or 255)
                g = int(self.custom_color_g.value or 255)
                b = int(self.custom_color_b.value or 255)
                r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                custom_rgb = (r, g, b)
            
            # 检查背景图片
            if bg_color == "image" and not self.bg_image_path:
                if not is_auto:
                    self._show_snackbar("请先选择背景图片", ft.Colors.ORANGE)
                return
            
            if rows < 1 or cols < 1 or rows > 100 or cols > 100:
                if not is_auto:
                    self._show_snackbar("行数和列数必须在1-100之间", ft.Colors.RED)
                return
        except ValueError:
            if not is_auto:
                self._show_snackbar("请输入有效的数字", ft.Colors.RED)
            return
        
        self.is_processing = True
        
        # 隐藏预览图，显示处理中提示
        self.preview_image_widget.visible = False
        self.preview_info_text.value = "正在生成预览..."
        self.preview_info_text.visible = True
        
        try:
            self._page.update()
        except Exception:
            pass
        
        async def _process_task():
            import asyncio
            try:
                # 检查是否需要生成 GIF 动画预览
                keep_animation = self.is_animated_gif and self.keep_gif_animation.value
                
                if keep_animation:
                    # 生成 GIF 动画预览
                    if not is_auto:
                        self._show_snackbar(f"正在生成 GIF 动画预览 ({self.gif_frame_count} 帧)...", ft.Colors.BLUE)
                    
                    result_frames, durations = await asyncio.to_thread(
                        self._generate_gif_frames,
                        rows, cols, shuffle, spacing,
                        corner_radius, overall_corner_radius,
                        bg_color, custom_rgb, piece_opacity, bg_opacity
                    )
                    
                    if result_frames:
                        # 更新为 GIF 动画预览
                        self._update_preview_gif(result_frames, durations, bg_color, custom_rgb, bg_opacity)
                        if not is_auto:
                            self._show_snackbar(f"预览生成成功 (GIF动画, {len(result_frames)}帧)", ft.Colors.GREEN)
                    else:
                        raise Exception("生成GIF动画失败")
                else:
                    # 生成静态图片预览
                    def _do_split():
                        # 读取图片（如果是 GIF，使用提取的帧）
                        if self.is_animated_gif:
                            image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
                            if image is None:
                                raise Exception("无法提取 GIF 帧")
                        else:
                            image = Image.open(self.selected_file)
                        
                        # 切分并重新拼接
                        return self._split_and_reassemble(
                            image, rows, cols, shuffle, spacing, 
                            corner_radius, overall_corner_radius,
                            bg_color, custom_rgb, self.bg_image_path,
                            piece_opacity, bg_opacity
                        )
                    
                    result, _ = await asyncio.to_thread(_do_split)
                    
                    # 更新预览
                    self._update_preview(result)
                    
                    # 只在手动点击时显示成功提示
                    if not is_auto:
                        self._show_snackbar("预览生成成功", ft.Colors.GREEN)
            except Exception as ex:
                if not is_auto:
                    self._show_snackbar(f"生成预览失败: {ex}", ft.Colors.RED)
                self._clear_preview()
            finally:
                self.is_processing = False
        
        self._page.run_task(_process_task)
    
    def _split_and_reassemble(
        self,
        image: Image.Image,
        rows: int,
        cols: int,
        shuffle: bool,
        spacing: int = 0,
        corner_radius: int = 0,
        overall_corner_radius: int = 0,
        bg_color: str = "white",
        custom_rgb: tuple = None,
        bg_image_path: Optional[Path] = None,
        piece_opacity: int = 255,
        bg_opacity: int = 255,
        shuffle_indices: Optional[list] = None,
        bg_image: Optional[Image.Image] = None
    ) -> tuple:
        """切分并重新拼接图片。
        
        Args:
            image: 要切分的图片
            rows: 行数
            cols: 列数
            shuffle: 是否打乱
            spacing: 切块间距
            corner_radius: 切块圆角
            overall_corner_radius: 整体圆角
            bg_color: 背景颜色类型
            custom_rgb: 自定义RGB值
            bg_image_path: 背景图片路径
            piece_opacity: 切块不透明度
            bg_opacity: 背景不透明度
            shuffle_indices: 可选的打乱顺序索引列表，用于保持多帧动画的一致性
            bg_image: 可选的背景图片Image对象，用于GIF背景动画
        
        Returns:
            (result_image, shuffle_indices): 返回结果图片和使用的打乱索引
        """
        import random
        from PIL import ImageDraw
        
        width, height = image.size
        
        # 计算每个切块的实际位置（均匀分配余数）
        col_positions = []
        row_positions = []
        
        # 计算每列的起始位置
        for col in range(cols + 1):
            col_positions.append(int(width * col / cols))
        
        # 计算每行的起始位置
        for row in range(rows + 1):
            row_positions.append(int(height * row / rows))
        
        # 切分图片
        pieces = []
        for row in range(rows):
            for col in range(cols):
                left = col_positions[col]
                top = row_positions[row]
                right = col_positions[col + 1]
                bottom = row_positions[row + 1]
                
                piece = image.crop((left, top, right, bottom))
                
                # 转换为RGBA模式以支持透明度
                if piece.mode != 'RGBA':
                    piece = piece.convert('RGBA')
                
                # 应用切块透明度
                if piece_opacity < 255:
                    alpha = piece.split()[3]
                    alpha = alpha.point(lambda p: int(p * piece_opacity / 255))
                    piece.putalpha(alpha)
                
                # 如果有切块圆角，给切块添加圆角
                if corner_radius > 0:
                    piece = self._add_rounded_corners(piece, corner_radius)
                
                pieces.append(piece)
        
        # 打乱顺序
        used_indices = None
        if shuffle:
            if shuffle_indices is not None:
                # 使用提供的打乱顺序（用于多帧GIF保持一致）
                pieces = [pieces[i] for i in shuffle_indices]
                used_indices = shuffle_indices
            else:
                # 生成新的打乱顺序
                indices = list(range(len(pieces)))
                random.shuffle(indices)
                pieces = [pieces[i] for i in indices]
                used_indices = indices
        
        # 计算包含间距的新尺寸
        total_spacing_h = spacing * (cols - 1)
        total_spacing_v = spacing * (rows - 1)
        new_width = width + total_spacing_h
        new_height = height + total_spacing_v
        
        # 创建结果图片（根据背景类型）
        if bg_color == "image" and (bg_image is not None or (bg_image_path and bg_image_path.exists())):
            # 使用背景图片
            try:
                # 优先使用传入的bg_image，否则从路径加载
                if bg_image is not None:
                    bg_img = bg_image.copy()
                else:
                    bg_img = Image.open(bg_image_path)
                
                # 调整背景图片大小以适应结果尺寸
                bg_img = bg_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                if bg_img.mode != 'RGBA':
                    bg_img = bg_img.convert('RGBA')
                
                # 应用背景透明度
                if bg_opacity < 255:
                    # 获取当前 alpha 通道
                    r, g, b, a = bg_img.split()
                    # 创建新的 alpha 通道，直接设置为 bg_opacity
                    # 如果原图有透明区域，则保留原有的透明度信息
                    new_alpha = a.point(lambda p: min(int(p * bg_opacity / 255), bg_opacity))
                    bg_img = Image.merge('RGBA', (r, g, b, new_alpha))
                
                result = bg_img
            except Exception:
                # 背景图片加载失败，使用白色背景
                result = Image.new('RGBA', (new_width, new_height), (255, 255, 255, bg_opacity))
        else:
            # 确定背景色
            if bg_color == "custom" and custom_rgb:
                bg_rgb = custom_rgb
            else:
                bg_color_map = {
                    "white": (255, 255, 255),
                    "black": (0, 0, 0),
                    "gray": (128, 128, 128),
                    "transparent": None,
                }
                bg_rgb = bg_color_map.get(bg_color, (255, 255, 255))
            
            # 创建结果图片（应用背景透明度）
            if bg_color == "transparent":
                result = Image.new('RGBA', (new_width, new_height), (255, 255, 255, 0))
            elif corner_radius > 0 or overall_corner_radius > 0 or piece_opacity < 255 or bg_opacity < 255:
                result = Image.new('RGBA', (new_width, new_height), (*bg_rgb, bg_opacity))
            else:
                result = Image.new('RGB', (new_width, new_height), bg_rgb)
        
        # 重新拼接，考虑间距
        # 计算拼接位置（包含间距）
        paste_x_positions = []
        paste_y_positions = []
        
        for col in range(cols):
            # 累积每列的起始位置（包含间距）
            x_offset = sum([col_positions[c + 1] - col_positions[c] for c in range(col)])
            x_offset += col * spacing
            paste_x_positions.append(x_offset)
        
        for row in range(rows):
            # 累积每行的起始位置（包含间距）
            y_offset = sum([row_positions[r + 1] - row_positions[r] for r in range(row)])
            y_offset += row * spacing
            paste_y_positions.append(y_offset)
        
        for i, piece in enumerate(pieces):
            row = i // cols
            col = i % cols
            left = paste_x_positions[col]
            top = paste_y_positions[row]
            
            # 使用alpha合成（支持透明度和圆角）
            if piece.mode == 'RGBA':
                result.paste(piece, (left, top), piece)
            else:
                if result.mode == 'RGBA':
                    piece = piece.convert('RGBA')
                result.paste(piece, (left, top))
        
        # 如果有整体圆角，给整个结果图的四个角添加圆角（不覆盖内部切块圆角）
        if overall_corner_radius > 0:
            result = self._add_overall_rounded_corners(result, overall_corner_radius)
        
        return result, used_indices
    
    def _add_rounded_corners(self, image: Image.Image, radius: int) -> Image.Image:
        """给单个切块添加圆角，保留原有的透明度。"""
        from PIL import ImageDraw, ImageChops
        
        # 转换为RGBA模式
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # 创建圆角蒙版
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # 绘制圆角矩形
        draw.rounded_rectangle(
            [(0, 0), image.size],
            radius=radius,
            fill=255
        )
        
        # 获取原图的alpha通道
        original_alpha = image.split()[3]
        
        # 将圆角蒙版与原有alpha通道合并（取最小值，即同时满足两个条件）
        combined_alpha = ImageChops.darker(original_alpha, mask)
        
        # 应用合并后的alpha通道
        output = Image.new('RGBA', image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(combined_alpha)
        
        return output
    
    def _add_overall_rounded_corners(self, image: Image.Image, radius: int) -> Image.Image:
        """给整体图片的四个角添加圆角，保留内部切块的alpha通道。"""
        from PIL import ImageDraw, ImageChops
        
        # 转换为RGBA模式
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # 创建整体圆角蒙版
        overall_mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(overall_mask)
        
        # 绘制圆角矩形蒙版
        draw.rounded_rectangle(
            [(0, 0), image.size],
            radius=radius,
            fill=255
        )
        
        # 获取原图的alpha通道
        original_alpha = image.split()[3]
        
        # 将整体圆角蒙版与原有alpha通道合并（取最小值，即同时满足两个条件）
        combined_alpha = ImageChops.darker(original_alpha, overall_mask)
        
        # 创建新图片并应用合并后的alpha通道
        output = Image.new('RGBA', image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(combined_alpha)
        
        return output
    
    def _generate_gif_frames(
        self,
        rows: int,
        cols: int,
        shuffle: bool,
        spacing: int,
        corner_radius: int,
        overall_corner_radius: int,
        bg_color: str,
        custom_rgb: tuple,
        piece_opacity: int,
        bg_opacity: int
    ) -> tuple:
        """生成 GIF 所有帧的切分结果。
        
        Returns:
            (帧列表, 持续时间列表)
        """
        if not self.is_animated_gif or not self.selected_file:
            return [], []
        
        # 提取所有帧
        all_frames = GifUtils.extract_all_frames(self.selected_file)
        if not all_frames:
            return [], []
        
        # 获取原始帧持续时间
        durations = GifUtils.get_frame_durations(self.selected_file)
        
        # 检查背景图是否为GIF
        bg_frames = None
        if bg_color == "image" and self.bg_image_path and self.bg_image_path.exists():
            if GifUtils.is_animated_gif(self.bg_image_path):
                bg_frames = GifUtils.extract_all_frames(self.bg_image_path)
        
        # 处理每一帧
        result_frames = []
        shuffle_order = None
        
        for i, frame in enumerate(all_frames):
            # 获取当前帧对应的背景图（如果背景是GIF）
            current_bg_image = None
            if bg_frames:
                bg_index = i % len(bg_frames)
                current_bg_image = bg_frames[bg_index]
            
            # 对当前帧进行切分
            split_frame, indices = self._split_and_reassemble(
                frame, rows, cols, shuffle, spacing,
                corner_radius, overall_corner_radius,
                bg_color, custom_rgb, self.bg_image_path,
                piece_opacity, bg_opacity,
                shuffle_indices=shuffle_order,
                bg_image=current_bg_image
            )
            
            # 保存第一帧的打乱顺序
            if i == 0 and shuffle and indices is not None:
                shuffle_order = indices
            
            result_frames.append(split_frame)
        
        return result_frames, durations
    
    def _update_preview(self, image: Image.Image) -> None:
        """更新预览图片（静态图片）。"""
        self.preview_image = image
        
        # 保存临时预览图片，使用时间戳避免缓存
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳作为文件名，避免 Flet 缓存
        timestamp = int(time.time() * 1000)
        preview_path = temp_dir / f"puzzle_preview_{timestamp}.png"
        
        # 保存新图片
        image.save(str(preview_path))
        
        # 清理旧的预览文件（保留最新的）
        try:
            for old_file in temp_dir.glob("puzzle_preview_*.*"):
                if old_file != preview_path:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
        
        # 直接使用文件路径显示
        self.preview_image_widget.src = str(preview_path)
        self.preview_image_widget.visible = True
        self.preview_info_text.visible = False
        self.save_button.disabled = False
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _update_preview_gif(self, frames: list, durations: list, bg_color: str, custom_rgb: tuple, bg_opacity: int) -> None:
        """更新预览图片（GIF 动画）。
        
        Args:
            frames: 帧列表
            durations: 每帧持续时间
            bg_color: 背景颜色类型
            custom_rgb: 自定义RGB值
            bg_opacity: 背景不透明度 (0-255)
        """
        self.preview_image = frames
        
        # 保存临时预览 GIF，使用时间戳避免缓存
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳作为文件名，避免 Flet 缓存
        timestamp = int(time.time() * 1000)
        preview_path = temp_dir / f"puzzle_preview_{timestamp}.gif"
        
        # GIF 支持透明，但只支持 1-bit 透明（完全透明或完全不透明）
        # 处理每一帧
        processed_frames = []
        for frame in frames:
            if frame.mode == 'RGBA' and bg_color != "transparent":
                # 用户设置了非透明背景，需要合成
                if bg_color == "custom" and custom_rgb:
                    base_bg = custom_rgb
                else:
                    bg_color_map = {
                        "white": (255, 255, 255),
                        "black": (0, 0, 0),
                        "gray": (128, 128, 128),
                    }
                    base_bg = bg_color_map.get(bg_color, (255, 255, 255))
                
                # 如果背景有不透明度设置，与白色混合
                if bg_opacity < 255:
                    opacity_ratio = bg_opacity / 255.0
                    base_bg = tuple(int(base_bg[i] * opacity_ratio + 255 * (1 - opacity_ratio)) for i in range(3))
                
                # 创建背景并合成为 RGB
                rgb_frame = Image.new('RGB', frame.size, base_bg)
                rgb_frame.paste(frame, mask=frame.split()[3])
                processed_frames.append(rgb_frame)
            elif frame.mode == 'RGBA':
                # 透明背景：保持 RGBA，GIF 会自动处理（alpha < 128 为透明）
                # 但需要转换为 P 模式（调色板模式）以支持透明
                processed_frames.append(frame)
            elif frame.mode != 'RGB':
                processed_frames.append(frame.convert('RGB'))
            else:
                processed_frames.append(frame)
        
        rgb_frames = processed_frames
        
        # 保存为 GIF 动画
        if rgb_frames:
            # 如果帧是 RGBA 模式，需要指定 disposal 参数以保留透明度
            save_params = {
                "save_all": True,
                "append_images": rgb_frames[1:],
                "duration": durations if durations else 100,
                "loop": 0,
                "optimize": False,
            }
            
            # 如果有透明度，添加 disposal 参数
            if rgb_frames[0].mode == 'RGBA':
                save_params["disposal"] = 2  # 清除每帧后的背景，保留透明度
            
            rgb_frames[0].save(str(preview_path), **save_params)
        
        # 清理旧的预览文件（保留最新的）
        try:
            for old_file in temp_dir.glob("puzzle_preview_*.*"):
                if old_file != preview_path:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
        
        # 直接使用文件路径显示
        self.preview_image_widget.src = str(preview_path)
        self.preview_image_widget.visible = True
        self.preview_info_text.visible = False
        self.save_button.disabled = False
        
        try:
            self._page.update()
        except Exception:
            pass
    
    async def _on_save_result(self, e: ft.ControlEvent) -> None:
        """保存结果。"""
        if not self.selected_file:
            self._show_snackbar("请先选择图片", ft.Colors.ORANGE)
            return
        
        # 检查输出模式
        is_individual_mode = self.output_mode.value == "individual"
        
        if is_individual_mode:
            # 单独导出每个切块
            await self._save_individual_pieces()
            return
        
        # 拼接模式：需要预览图
        if not self.preview_image:
            self._show_snackbar("没有可保存的预览图片，请先生成预览", ft.Colors.ORANGE)
            return
        
        # 检查是否需要保存为 GIF 动画
        save_as_gif = self.is_animated_gif and self.keep_gif_animation.value
        
        # 检查是否使用了透明度效果
        has_transparency = (
            int(self.piece_opacity_input.value or 100) < 100 or
            int(self.bg_opacity_input.value or 100) < 100 or
            self.split_bg_color.value == "transparent"
        )
        
        # 生成默认文件名：原文件名_split.扩展名
        default_filename = "split_result.png"
        allowed_extensions = ["png", "jpg", "jpeg", "jfif"]
        
        if self.selected_file:
            original_stem = self.selected_file.stem
            if save_as_gif:
                default_filename = f"{original_stem}_split.gif"
                allowed_extensions = ["gif"]
            else:
                default_filename = f"{original_stem}_split.png"
                # 如果使用了透明度，只允许保存为 PNG
                if has_transparency:
                    allowed_extensions = ["png"]
        else:
            if save_as_gif:
                default_filename = "split_result.gif"
                allowed_extensions = ["gif"]
            elif has_transparency:
                allowed_extensions = ["png"]
        
        result_path = await ft.FilePicker().save_file(
            dialog_title="保存切分结果",
            file_name=default_filename,
            allowed_extensions=allowed_extensions,
        )
        
        if result_path:
            try:
                output_path = Path(result_path)
                
                # 确保有扩展名
                if not output_path.suffix:
                    if save_as_gif:
                        output_path = output_path.with_suffix('.gif')
                    else:
                        output_path = output_path.with_suffix('.png')
                
                # 如果使用了透明度，强制使用 PNG 格式
                if not save_as_gif and has_transparency and output_path.suffix.lower() in ['.jpg', '.jpeg']:
                    output_path = output_path.with_suffix('.png')
                    self._show_snackbar("检测到透明度效果，已自动转换为 PNG 格式", ft.Colors.BLUE)
                
                if save_as_gif:
                    # 保存为动态 GIF
                    self._save_as_gif(output_path)
                else:
                    # 保存为静态图片 - 重新生成以确保使用最新参数
                    self._save_static_image(output_path)
            except Exception as ex:
                self._show_snackbar(f"保存失败: {ex}", ft.Colors.RED)
    
    def _save_static_image(self, output_path: Path) -> None:
        """保存静态图片 - 重新生成以确保使用最新参数。"""
        if not self.selected_file:
            return
        
        try:
            # 获取切分参数
            rows = int(self.split_rows.value or 3)
            cols = int(self.split_cols.value or 3)
            shuffle = self.split_shuffle.value
            spacing = int(self.split_spacing_input.value or 5)
            corner_radius = int(self.corner_radius_input.value or 0)
            overall_corner_radius = int(self.overall_corner_radius_input.value or 0)
            bg_color = self.split_bg_color.value
            
            # 获取透明度值
            piece_opacity_percent = int(self.piece_opacity_input.value or 100)
            piece_opacity = max(0, min(100, piece_opacity_percent))
            piece_opacity = int(piece_opacity * 255 / 100)
            
            bg_opacity_percent = int(self.bg_opacity_input.value or 100)
            bg_opacity = max(0, min(100, bg_opacity_percent))
            bg_opacity = int(bg_opacity * 255 / 100)
            
            # 获取自定义RGB值
            custom_rgb = None
            if bg_color == "custom":
                r = int(self.custom_color_r.value or 255)
                g = int(self.custom_color_g.value or 255)
                b = int(self.custom_color_b.value or 255)
                r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                custom_rgb = (r, g, b)
            
            # 读取图片（如果是 GIF，使用当前选择的帧）
            if self.is_animated_gif:
                image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
                if image is None:
                    raise Exception("无法提取 GIF 帧")
            else:
                image = Image.open(self.selected_file)
            
            # 切分并重新拼接
            result, _ = self._split_and_reassemble(
                image, rows, cols, shuffle, spacing, 
                corner_radius, overall_corner_radius,
                bg_color, custom_rgb, self.bg_image_path,
                piece_opacity, bg_opacity
            )
            
            # 保存图片 - 使用与预览相同的方式
            if result.mode == 'RGBA' and output_path.suffix.lower() in ['.jpg', '.jpeg']:
                # RGBA 转 JPG：创建白色背景并合成
                rgb_image = Image.new('RGB', result.size, (255, 255, 255))
                rgb_image.paste(result, mask=result.split()[3])
                rgb_image.save(output_path, quality=95)
            elif output_path.suffix.lower() in ['.jpg', '.jpeg']:
                # RGB 保存为 JPG
                result.save(output_path, quality=95)
            else:
                # PNG 格式 - 完全保留透明度信息
                result.save(output_path)
            
            self._show_snackbar(f"保存成功: {output_path.name}", ft.Colors.GREEN)
            
        except Exception as e:
            self._show_snackbar(f"保存失败: {e}", ft.Colors.RED)
    
    async def _save_individual_pieces(self) -> None:
        """将所有切块导出为单独的文件。"""
        if not self.selected_file:
            return
        
        # 选择输出目录
        result_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择导出目录",
        )
        
        if result_path:
            try:
                output_dir = Path(result_path)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 获取切分参数
                rows = int(self.split_rows.value or 3)
                cols = int(self.split_cols.value or 3)
                shuffle = self.split_shuffle.value
                corner_radius = int(self.corner_radius_input.value or 0)
                
                # 获取透明度值
                piece_opacity = int(self.piece_opacity_input.value or 100)
                piece_opacity = max(0, min(100, piece_opacity))
                piece_opacity = int(piece_opacity * 255 / 100)
                
                # 检查是否需要处理 GIF 动画
                process_gif = self.is_animated_gif and self.keep_gif_animation.value
                
                if process_gif:
                    self._export_gif_pieces(output_dir, rows, cols, shuffle, corner_radius, piece_opacity)
                else:
                    self._export_static_pieces(output_dir, rows, cols, shuffle, corner_radius, piece_opacity)
                
            except Exception as ex:
                self._show_snackbar(f"导出失败: {ex}", ft.Colors.RED)
    
    def _export_static_pieces(
        self,
        output_dir: Path,
        rows: int,
        cols: int,
        shuffle: bool,
        corner_radius: int,
        piece_opacity: int
    ) -> None:
        """导出静态图片的切块。"""
        try:
            # 读取图片（如果是 GIF，使用当前选择的帧）
            if self.is_animated_gif:
                image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
                if image is None:
                    raise Exception("无法提取 GIF 帧")
            else:
                image = Image.open(self.selected_file)
            
            width, height = image.size
            
            # 计算每个切块的位置（均匀分配余数）
            col_positions = []
            row_positions = []
            
            for col in range(cols + 1):
                col_positions.append(int(width * col / cols))
            
            for row in range(rows + 1):
                row_positions.append(int(height * row / rows))
            
            # 切分图片
            pieces = []
            for row in range(rows):
                for col in range(cols):
                    left = col_positions[col]
                    top = row_positions[row]
                    right = col_positions[col + 1]
                    bottom = row_positions[row + 1]
                    
                    piece = image.crop((left, top, right, bottom))
                    
                    # 转换为RGBA模式以支持透明度
                    if piece.mode != 'RGBA':
                        piece = piece.convert('RGBA')
                    
                    # 应用切块透明度
                    if piece_opacity < 255:
                        alpha = piece.split()[3]
                        alpha = alpha.point(lambda p: int(p * piece_opacity / 255))
                        piece.putalpha(alpha)
                    
                    # 如果有切块圆角，给切块添加圆角
                    if corner_radius > 0:
                        piece = self._add_rounded_corners(piece, corner_radius)
                    
                    pieces.append(piece)
            
            # 如果需要打乱，打乱顺序
            if shuffle:
                import random
                indices = list(range(len(pieces)))
                random.shuffle(indices)
                pieces = [pieces[i] for i in indices]
            
            # 保存每个切块
            original_stem = self.selected_file.stem
            total_pieces = len(pieces)
            
            for i, piece in enumerate(pieces):
                # 文件名格式：原文件名_piece_001.png
                piece_filename = f"{original_stem}_piece_{i+1:03d}.png"
                piece_path = output_dir / piece_filename
                
                # 保存为 PNG 以保留透明度
                piece.save(piece_path)
            
            self._show_snackbar(f"成功导出 {total_pieces} 个切块到 {output_dir.name}", ft.Colors.GREEN)
            
        except Exception as e:
            self._show_snackbar(f"导出切块失败: {e}", ft.Colors.RED)
    
    def _export_gif_pieces(
        self,
        output_dir: Path,
        rows: int,
        cols: int,
        shuffle: bool,
        corner_radius: int,
        piece_opacity: int
    ) -> None:
        """导出 GIF 动画的切块（每个切块都是 GIF）。"""
        try:
            # 提取所有帧
            all_frames = GifUtils.extract_all_frames(self.selected_file)
            if not all_frames:
                raise Exception("无法提取 GIF 帧")
            
            # 获取原始帧持续时间
            durations = GifUtils.get_frame_durations(self.selected_file)
            
            # 获取原始 GIF 的 loop 参数
            with Image.open(self.selected_file) as gif:
                loop = gif.info.get('loop', 0)
            
            total_pieces = rows * cols
            self._show_snackbar(f"正在处理 GIF 动画（{len(all_frames)}帧×{total_pieces}块）...", ft.Colors.BLUE)
            
            # 为每个切块位置创建帧列表
            pieces_frames = [[] for _ in range(total_pieces)]
            shuffle_order = None
            
            # 处理每一帧
            for frame_idx, frame in enumerate(all_frames):
                width, height = frame.size
                
                # 计算每个切块的位置
                col_positions = []
                row_positions = []
                
                for col in range(cols + 1):
                    col_positions.append(int(width * col / cols))
                
                for row in range(rows + 1):
                    row_positions.append(int(height * row / rows))
                
                # 切分当前帧
                pieces = []
                for row in range(rows):
                    for col in range(cols):
                        left = col_positions[col]
                        top = row_positions[row]
                        right = col_positions[col + 1]
                        bottom = row_positions[row + 1]
                        
                        piece = frame.crop((left, top, right, bottom))
                        
                        # 转换为RGBA模式
                        if piece.mode != 'RGBA':
                            piece = piece.convert('RGBA')
                        
                        # 应用透明度
                        if piece_opacity < 255:
                            alpha = piece.split()[3]
                            alpha = alpha.point(lambda p: int(p * piece_opacity / 255))
                            piece.putalpha(alpha)
                        
                        # 应用圆角
                        if corner_radius > 0:
                            piece = self._add_rounded_corners(piece, corner_radius)
                        
                        # GIF 支持透明（1-bit），保持 RGBA 模式
                        # Pillow 会自动将 alpha < 128 的像素设为透明
                        # 单个切块通常需要保留透明度（圆角、透明度效果）
                        if piece.mode != 'RGBA' and piece.mode != 'RGB':
                            piece = piece.convert('RGBA')
                        
                        pieces.append(piece)
                
                # 第一帧时生成打乱顺序
                if frame_idx == 0 and shuffle:
                    import random
                    shuffle_order = list(range(len(pieces)))
                    random.shuffle(shuffle_order)
                
                # 应用打乱顺序
                if shuffle and shuffle_order:
                    pieces = [pieces[i] for i in shuffle_order]
                
                # 将每个切块添加到对应的帧列表中
                for piece_idx, piece in enumerate(pieces):
                    pieces_frames[piece_idx].append(piece)
            
            # 保存每个切块的 GIF
            original_stem = self.selected_file.stem
            
            for piece_idx, frames in enumerate(pieces_frames):
                if frames:
                    piece_filename = f"{original_stem}_piece_{piece_idx+1:03d}.gif"
                    piece_path = output_dir / piece_filename
                    
                    # 保存为 GIF 动画
                    save_params = {
                        "save_all": True,
                        "append_images": frames[1:],
                        "duration": durations,
                        "loop": loop,
                        "optimize": False,
                    }
                    
                    # 如果有透明度，添加 disposal 参数
                    if frames[0].mode == 'RGBA':
                        save_params["disposal"] = 2
                    
                    frames[0].save(piece_path, **save_params)
            
            self._show_snackbar(f"成功导出 {total_pieces} 个 GIF 切块到 {output_dir.name}", ft.Colors.GREEN)
            
        except Exception as e:
            self._show_snackbar(f"导出 GIF 切块失败: {e}", ft.Colors.RED)
    
    def _save_as_gif(self, output_path: Path) -> None:
        """将所有 GIF 帧切分并保存为动态 GIF。"""
        if not self.is_animated_gif or not self.selected_file:
            return
        
        try:
            # 获取切分参数
            rows = int(self.split_rows.value or 3)
            cols = int(self.split_cols.value or 3)
            shuffle = self.split_shuffle.value
            spacing = int(self.split_spacing_input.value or 5)
            corner_radius = int(self.corner_radius_input.value or 0)
            overall_corner_radius = int(self.overall_corner_radius_input.value or 0)
            bg_color = self.split_bg_color.value
            
            # 获取透明度值
            piece_opacity = int(self.piece_opacity_input.value or 100)
            piece_opacity = max(0, min(100, piece_opacity))
            piece_opacity = int(piece_opacity * 255 / 100)
            
            bg_opacity = int(self.bg_opacity_input.value or 100)
            bg_opacity = max(0, min(100, bg_opacity))
            bg_opacity = int(bg_opacity * 255 / 100)
            
            # 获取自定义RGB值
            custom_rgb = None
            if bg_color == "custom":
                r = int(self.custom_color_r.value or 255)
                g = int(self.custom_color_g.value or 255)
                b = int(self.custom_color_b.value or 255)
                r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                custom_rgb = (r, g, b)
            
            # 显示处理进度
            self._show_snackbar(f"正在处理 {self.gif_frame_count} 帧...", ft.Colors.BLUE)
            
            # 提取所有帧
            all_frames = GifUtils.extract_all_frames(self.selected_file)
            if not all_frames:
                raise Exception("无法提取 GIF 帧")
            
            # 获取原始帧持续时间
            durations = GifUtils.get_frame_durations(self.selected_file)
            
            # 检查背景图是否为GIF
            bg_frames = None
            if bg_color == "image" and self.bg_image_path and self.bg_image_path.exists():
                # 检测背景图是否为动态GIF
                if GifUtils.is_animated_gif(self.bg_image_path):
                    bg_frames = GifUtils.extract_all_frames(self.bg_image_path)
                    if bg_frames:
                        self._show_snackbar(f"检测到背景GIF动画（{len(bg_frames)}帧），将同步处理", ft.Colors.BLUE)
            
            # 处理每一帧
            result_frames = []
            shuffle_order = None  # 用于保存第一帧的打乱顺序
            
            for i, frame in enumerate(all_frames):
                # 获取当前帧对应的背景图（如果背景是GIF）
                current_bg_image = None
                if bg_frames:
                    # 如果背景图帧数较少，循环使用；如果较多，按顺序使用
                    bg_index = i % len(bg_frames)
                    current_bg_image = bg_frames[bg_index]
                
                # 对当前帧进行切分
                # 第一帧时生成打乱顺序，后续帧使用相同的顺序
                split_frame, indices = self._split_and_reassemble(
                    frame, rows, cols, shuffle, spacing,
                    corner_radius, overall_corner_radius,
                    bg_color, custom_rgb, self.bg_image_path,
                    piece_opacity, bg_opacity,
                    shuffle_indices=shuffle_order,  # 传入之前的顺序（第一帧时为None）
                    bg_image=current_bg_image  # 传入当前帧对应的背景图
                )
                
                # 保存第一帧的打乱顺序，供后续帧使用
                if i == 0 and shuffle and indices is not None:
                    shuffle_order = indices
                
                # GIF 支持透明，但只支持 1-bit 透明（完全透明或完全不透明）
                # Pillow 会自动将 alpha < 128 的像素设为透明，>= 128 的设为不透明
                # 如果背景不是透明的，需要合成到背景色上
                if split_frame.mode == 'RGBA' and bg_color != "transparent":
                    # 用户设置了非透明背景，需要合成
                    if bg_color == "custom" and custom_rgb:
                        base_bg = custom_rgb
                    else:
                        bg_color_map = {
                            "white": (255, 255, 255),
                            "black": (0, 0, 0),
                            "gray": (128, 128, 128),
                        }
                        base_bg = bg_color_map.get(bg_color, (255, 255, 255))
                    
                    # 如果背景有不透明度设置，与白色混合来模拟半透明效果
                    # （因为 GIF 不支持半透明，这是一个折衷方案）
                    if bg_opacity < 255:
                        opacity_ratio = bg_opacity / 255.0
                        base_bg = tuple(int(base_bg[i] * opacity_ratio + 255 * (1 - opacity_ratio)) for i in range(3))
                    
                    # 创建背景并合成为 RGB
                    rgb_frame = Image.new('RGB', split_frame.size, base_bg)
                    rgb_frame.paste(split_frame, mask=split_frame.split()[3])
                    split_frame = rgb_frame
                elif split_frame.mode == 'RGBA':
                    # 透明背景：保持 RGBA，Pillow 会自动处理透明度（alpha < 128 为透明）
                    pass
                elif split_frame.mode != 'RGB':
                    # 转换其他模式
                    split_frame = split_frame.convert('RGB')
                
                result_frames.append(split_frame)
            
            # 获取原始 GIF 的 loop 参数
            with Image.open(self.selected_file) as gif:
                loop = gif.info.get('loop', 0)
            
            # 保存为动态 GIF
            if result_frames:
                # 设置保存参数
                save_params = {
                    "save_all": True,
                    "append_images": result_frames[1:],
                    "duration": durations,
                    "loop": loop,
                    "optimize": False,
                }
                
                # 如果有透明度，添加 disposal 参数
                if result_frames[0].mode == 'RGBA':
                    save_params["disposal"] = 2
                
                result_frames[0].save(output_path, **save_params)
                self._show_snackbar(f"保存成功: {output_path.name}", ft.Colors.GREEN)
            else:
                raise Exception("没有生成任何帧")
                
        except Exception as e:
            self._show_snackbar(f"保存 GIF 失败: {e}", ft.Colors.RED)
    
    def _on_preview_click(self, e: ft.ControlEvent) -> None:
        """点击预览图片，用系统查看器打开。"""
        if not self.preview_image:
            return
        
        try:
            import tempfile
            import subprocess
            import platform
            
            # 检查是否为 GIF 动画（帧列表）
            is_gif_animation = isinstance(self.preview_image, list)
            
            if is_gif_animation:
                # 创建临时 GIF 文件
                with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                    # 转换帧为 RGB
                    rgb_frames = []
                    for frame in self.preview_image:
                        if frame.mode == 'RGBA':
                            rgb_frame = Image.new('RGB', frame.size, (255, 255, 255))
                            rgb_frame.paste(frame, mask=frame.split()[3])
                            rgb_frames.append(rgb_frame)
                        elif frame.mode != 'RGB':
                            rgb_frames.append(frame.convert('RGB'))
                        else:
                            rgb_frames.append(frame)
                    
                    # 获取帧持续时间
                    durations = GifUtils.get_frame_durations(self.selected_file) if self.selected_file else 100
                    
                    # 保存为 GIF
                    if rgb_frames:
                        rgb_frames[0].save(
                            tmp_path,
                            save_all=True,
                            append_images=rgb_frames[1:],
                            duration=durations if durations else 100,
                            loop=0,
                            optimize=False,
                        )
            else:
                # 创建临时 PNG 文件
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    self.preview_image.save(tmp_path, 'PNG')
            
            # 用系统默认程序打开
            system = platform.system()
            if system == "Windows":
                os.startfile(tmp_path)
            elif system == "Darwin":  # macOS
                subprocess.run(['open', tmp_path])
            else:  # Linux
                subprocess.run(['xdg-open', tmp_path])
        except Exception as ex:
            self._show_snackbar(f"打开图片失败: {ex}", ft.Colors.RED)
    
    def _on_gif_prev_frame(self, e: ft.ControlEvent) -> None:
        """切换到上一帧。"""
        if not self.is_animated_gif or self.gif_frame_count == 0:
            return
        
        self.current_frame_index = (self.current_frame_index - 1) % self.gif_frame_count
        self._update_gif_frame()
    
    def _on_gif_next_frame(self, e: ft.ControlEvent) -> None:
        """切换到下一帧。"""
        if not self.is_animated_gif or self.gif_frame_count == 0:
            return
        
        self.current_frame_index = (self.current_frame_index + 1) % self.gif_frame_count
        self._update_gif_frame()
    
    def _on_frame_input_submit(self, e: ft.ControlEvent) -> None:
        """手动输入帧号。"""
        if not self.is_animated_gif or self.gif_frame_count == 0:
            return
        
        try:
            frame_num = int(self.gif_frame_input.value)
            if 1 <= frame_num <= self.gif_frame_count:
                self.current_frame_index = frame_num - 1
                self._update_gif_frame()
            else:
                self._show_snackbar(f"帧号必须在 1-{self.gif_frame_count} 之间", ft.Colors.ORANGE)
                self.gif_frame_input.value = str(self.current_frame_index + 1)
                self._page.update()
        except ValueError:
            self._show_snackbar("请输入有效的帧号", ft.Colors.RED)
            self.gif_frame_input.value = str(self.current_frame_index + 1)
            self._page.update()
    
    def _update_gif_frame(self) -> None:
        """更新 GIF 当前帧的显示。"""
        if not self.is_animated_gif or not self.selected_file:
            return
        
        try:
            # 更新输入框显示
            self.gif_frame_input.value = str(self.current_frame_index + 1)
            
            # 提取并显示当前帧
            frame_image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
            if frame_image:
                # 使用时间戳避免缓存问题
                import time
                timestamp = int(time.time() * 1000)
                temp_dir = self.config_service.get_temp_dir()
                temp_path = temp_dir / f"gif_frame_{self.current_frame_index}_{timestamp}.png"
                frame_image.save(temp_path)
                
                # 清理旧的GIF帧临时文件
                try:
                    for old_file in temp_dir.glob("gif_frame_*.png"):
                        if old_file != temp_path:
                            try:
                                old_file.unlink()
                            except Exception:
                                pass
                except Exception:
                    pass
                
                self.original_image_widget.src = str(temp_path)
                
                # 更新界面
                self._page.update()
                
                # GIF 帧切换后自动更新预览
                if self._auto_preview_enabled:
                    self._schedule_auto_preview()
                else:
                    self._clear_preview()
            else:
                self._show_snackbar("无法提取 GIF 帧", ft.Colors.RED)
        except Exception as e:
            self._show_snackbar(f"更新 GIF 帧失败: {e}", ft.Colors.RED)
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self._page.open(snackbar)
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件（只取第一个支持的文件）。"""
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        # 只取第一个支持的文件
        for path in all_files:
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                self.selected_file = path
                self._update_file_info()
                self._show_snackbar(f"已加载: {path.name}", ft.Colors.GREEN)
                self._page.update()
                return
        
        self._show_snackbar("单图切分工具不支持该格式", ft.Colors.ORANGE)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        if hasattr(self, 'selected_file'):
            self.selected_file = None
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
