# -*- coding: utf-8 -*-
"""图片裁剪视图模块。

提供可视化的图片裁剪功能，支持拖动裁剪框。
"""

import logging
import os
import subprocess
import warnings
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
    PRIMARY_COLOR,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    BORDER_RADIUS_SMALL,
)
from services import ConfigService, ImageService
from utils import GifUtils

# 屏蔽 libpng 的 iCCP 警告
warnings.filterwarnings("ignore", message=".*iCCP.*")
warnings.filterwarnings("ignore", "(Possibly )?corrupt EXIF data", UserWarning)
warnings.filterwarnings("ignore", "Palette images with Transparency", UserWarning)

# 屏蔽 PIL 的日志警告
logging.getLogger('PIL').setLevel(logging.ERROR)


class ImageCropView(ft.Container):
    """图片裁剪视图类。
    
    提供可拖动的裁剪框功能。
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable[[], None]] = None,
    ) -> None:
        """初始化图片裁剪视图。"""
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable[[], None]] = on_back
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 选中的文件
        self.selected_file: Optional[Path] = None
        self.original_image: Optional[Image.Image] = None
        
        # 预览文件路径（用于清理）
        self._last_preview_path: Optional[str] = None
        
        # GIF 相关
        self.is_animated_gif: bool = False
        self.gif_frame_count: int = 1
        self.current_frame_index: int = 0
        
        # 裁剪参数（像素值）
        self.crop_x: int = 0
        self.crop_y: int = 0
        self.crop_width: int = 200
        self.crop_height: int = 200
        
        # 显示尺寸（动态调整，适配图片大小）
        # 最大尺寸限制（考虑窗口大小 1090x730，左侧区域约 700x650，减去内边距 PADDING_LARGE*2）
        # PADDING_LARGE = 24，所以左右上下各减少24px，实际可用空间减少48px
        self.max_canvas_width: int = 602  # 650 - 48
        self.max_canvas_height: int = 552  # 600 - 48
        # 初始尺寸（空状态时的默认大小，加载图片后会动态调整）
        self.canvas_width: int = 500
        self.canvas_height: int = 400
        
        # 拖动状态
        self.is_dragging: bool = False
        self.drag_start_x: float = 0
        self.drag_start_y: float = 0
        self.crop_start_x: int = 0
        self.crop_start_y: int = 0
        
        # 调整大小状态
        self.resize_mode: Optional[str] = None  # 'se', 'sw', 'ne', 'nw'
        self.crop_start_width: int = 0
        self.crop_start_height: int = 0
        
        # 更新控制
        self._update_pending: bool = False
        self._last_update_time: float = 0
        
        # 预览更新控制
        self._preview_update_timer: Optional[object] = None
        
        # 精调步长（WASD 键移动的像素数）
        self.fine_tune_step: int = 1
        
        # 创建UI组件
        self._build_ui()
        
        # 注册键盘事件
        self.page.on_keyboard_event = self._on_keyboard
        
        # 注册窗口大小变化事件
        self.page.on_resize = self._on_window_resize
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题栏（参考压缩页面风格）
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=self._on_back_click,
                    tooltip="返回",
                ),
                ft.Text("图片裁剪", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        self.fine_tune_input: ft.TextField = ft.TextField(
            value=str(self.fine_tune_step),
            width=60,
            height=32,
            text_size=12,
            content_padding=8,
            border_color=ft.Colors.OUTLINE_VARIANT,
            bgcolor=ft.Colors.WHITE,
            on_change=self._on_fine_tune_step_change,
            tooltip="WASD键每次移动的像素数（1-100）",
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
 
        def create_tip_badge(icon_name: str, label: str) -> ft.Container:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon_name, size=14, color=ft.Colors.WHITE),
                        ft.Text(label, size=12, color=ft.Colors.WHITE),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
            )

        # 指南卡片 - 保存引用以便动态更新主题色
        self.instruction_card: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CROP, size=18, color=ft.Colors.WHITE),
                            ft.Text("裁剪操作指南", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Text(
                        "点击左侧画布选择图片，拖动蓝色框移动位置，拖动四角调整范围，使用 W / A / S / D 键进行精确微调。",
                        size=11,
                        color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
                    ),
                    ft.Row(
                        controls=[
                            create_tip_badge(ft.Icons.PAN_TOOL_ALT, "拖动蓝框移动"),
                            create_tip_badge(ft.Icons.CROP_FREE, "拖动角点缩放"),
                            create_tip_badge(ft.Icons.KEYBOARD_ALT, "WASD 精调"),
                            create_tip_badge(ft.Icons.MOVIE_FILTER, "支持 GIF"),
                        ],
                        spacing=6,
                        wrap=False,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text("WASD 精调步长:", size=11, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
                            self.fine_tune_input,
                            ft.Text("px", size=11, color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE)),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL + 4),
            border_radius=BORDER_RADIUS_SMALL,
            margin=ft.margin.only(bottom=PADDING_MEDIUM - 4),
        )
        # 更新指南卡片的渐变色
        self._update_instruction_card_gradient()
        
        # 空状态（占满画布）
        primary_color: str = self._get_theme_primary_color()
        self.empty_state_widget: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, size=72, color=primary_color),
                    ft.Text("点击或拖拽图片到这里开始裁剪", size=16, weight=ft.FontWeight.W_500, ),
                    ft.Text("支持 JPG · PNG · GIF · BMP · WebP", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            alignment=ft.alignment.center,
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.05, primary_color),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 原图显示（居中保持比例，占满整个 Stack）
        self.original_image_widget: ft.Image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            visible=False,
            width=self.canvas_width,
            height=self.canvas_height,
        )
        
        # 图片在画布中的实际显示位置和大小
        self.img_display_x: float = 0
        self.img_display_y: float = 0
        self.img_display_width: float = 0
        self.img_display_height: float = 0
        
        # 裁剪框的四个角控制点
        handle_size = 12
        
        # 裁剪框容器（可拖动）- 包装在 Container 中以支持绝对定位
        self.crop_box_container: ft.Container = ft.Container(
            content=ft.GestureDetector(
                content=ft.Container(
                    border=ft.border.all(3, ft.Colors.PRIMARY),
                    bgcolor="#40FFFFFF",  # 半透明白色
                ),
                on_pan_start=self._on_crop_pan_start,
                on_pan_update=self._on_crop_pan_update,
                on_pan_end=self._on_crop_pan_end,
            ),
            top=0,
            left=0,
            width=200,
            height=200,
            visible=False,  # 初始不可见，加载图片后显示
        )
        
        # 四个角的控制点（调整大小）
        # 右下角 (SE - South East)
        self.handle_se: ft.Container = ft.Container(
            content=ft.GestureDetector(
                content=ft.Container(
                    width=handle_size,
                    height=handle_size,
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=handle_size // 2,
                ),
                on_pan_start=lambda e: self._on_resize_start(e, 'se'),
                on_pan_update=lambda e: self._on_resize_update(e, 'se'),
                on_pan_end=self._on_resize_end,
            ),
            top=0,
            left=0,
            visible=False,
        )
        
        # 左下角 (SW - South West)
        self.handle_sw: ft.Container = ft.Container(
            content=ft.GestureDetector(
                content=ft.Container(
                    width=handle_size,
                    height=handle_size,
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=handle_size // 2,
                ),
                on_pan_start=lambda e: self._on_resize_start(e, 'sw'),
                on_pan_update=lambda e: self._on_resize_update(e, 'sw'),
                on_pan_end=self._on_resize_end,
            ),
            top=0,
            left=0,
            visible=False,
        )
        
        # 右上角 (NE - North East)
        self.handle_ne: ft.Container = ft.Container(
            content=ft.GestureDetector(
                content=ft.Container(
                    width=handle_size,
                    height=handle_size,
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=handle_size // 2,
                ),
                on_pan_start=lambda e: self._on_resize_start(e, 'ne'),
                on_pan_update=lambda e: self._on_resize_update(e, 'ne'),
                on_pan_end=self._on_resize_end,
            ),
            top=0,
            left=0,
            visible=False,
        )
        
        # 左上角 (NW - North West)
        self.handle_nw: ft.Container = ft.Container(
            content=ft.GestureDetector(
                content=ft.Container(
                    width=handle_size,
                    height=handle_size,
                    bgcolor=ft.Colors.PRIMARY,
                    border_radius=handle_size // 2,
                ),
                on_pan_start=lambda e: self._on_resize_start(e, 'nw'),
                on_pan_update=lambda e: self._on_resize_update(e, 'nw'),
                on_pan_end=self._on_resize_end,
            ),
            top=0,
            left=0,
            visible=False,
        )
        
        # 刻度尺容器（水平和垂直）
        self.ruler_horizontal: ft.Row = ft.Row(
            controls=[],
            spacing=0,
            visible=False,
        )
        self.ruler_vertical: ft.Column = ft.Column(
            controls=[],
            spacing=0,
            visible=False,
        )
        
        # 使用 Stack 叠加（设置初始尺寸）
        self.crop_canvas: ft.Stack = ft.Stack(
            controls=[
                self.original_image_widget,
                self.crop_box_container,
                # 四个角的控制点
                self.handle_nw,  # 左上
                self.handle_ne,  # 右上
                self.handle_sw,  # 左下
                self.handle_se,  # 右下
            ],
            width=self.canvas_width,
            height=self.canvas_height,
        )
        
        # 裁剪区域（动态尺寸，带内边距让图片居中）
        # Stack 需要明确设置尺寸，容器的尺寸需要加上 padding
        self.canvas_stack: ft.Stack = ft.Stack(
            controls=[self.empty_state_widget, self.crop_canvas],
            width=self.canvas_width,
            height=self.canvas_height,
        )
        
        # 画布内容（可点击选择图片）
        self.canvas_clickable: ft.Container = ft.Container(
            content=self.canvas_stack,
            on_click=self._on_canvas_click,  # 点击选择图片
            tooltip="点击或拖拽图片到此区域",
        )
        
        # 画布与刻度尺的组合布局
        self.canvas_with_rulers: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.ruler_horizontal,  # 顶部水平刻度尺
                    ft.Row(
                        controls=[
                            self.ruler_vertical,  # 左侧垂直刻度尺
                            self.canvas_clickable,  # 画布
                        ],
                        spacing=0,
                    ),
                ],
                spacing=0,
            ),
        )
        
        self.canvas_container: ft.Container = ft.Container(
            content=self.canvas_with_rulers,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            alignment=ft.alignment.center,
            padding=PADDING_LARGE,  # 添加内边距让图片居中显示
        )
        
        # 左侧裁剪区域
        crop_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("裁剪区域", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.canvas_container,
                        alignment=ft.alignment.top_left,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
                scroll=ft.ScrollMode.AUTO,  # 添加滚动以防内容超出
            ),
            expand=2,  # 占据更多空间（2:1 比例）
            padding=ft.padding.only(left=PADDING_LARGE, right=PADDING_MEDIUM),
        )
        
        # 右侧预览区域
        self.preview_image_widget: ft.Image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        # 裁剪尺寸显示(移到预览标题旁边)
        self.crop_size_text: ft.Text = ft.Text(
            "",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.W_500,
        )
        
        self.preview_info_text: ft.Text = ft.Text(
            "选择图片后拖动裁剪框查看效果",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        
        # 预览区域（占据上半部分，1:1 平分）
        preview_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    # 标题行:包含"裁剪预览"和尺寸信息
                    ft.Row(
                        controls=[
                            ft.Text("裁剪预览", size=14, weight=ft.FontWeight.W_500),
                            self.crop_size_text,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=ft.Stack(
                            controls=[
                                ft.Container(
                                    content=self.preview_info_text,
                                    alignment=ft.alignment.center,
                                ),
                                ft.Container(
                                    content=self.preview_image_widget,
                                    alignment=ft.alignment.center,
                                ),
                            ],
                        ),
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        alignment=ft.alignment.center,
                        height=300,  # 固定高度
                        on_click=self._on_preview_click,
                        tooltip="点击用系统默认应用打开",
                        ink=True,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # 拉伸以适应行宽度
                spacing=0,
            ),
            expand=1,  # 占据上半部分（1:1 比例）
        )
        
        # GIF 帧选择器（初始隐藏）
        self.gif_frame_input: ft.TextField = ft.TextField(
            value="1",
            width=60,
            text_align=ft.TextAlign.CENTER,
            on_submit=self._on_frame_input_submit,
            on_blur=self._on_frame_input_submit,  # 失去焦点时也触发
            dense=True,
        )
        
        self.gif_total_frames_text: ft.Text = ft.Text("/ 1", size=14)
        
        self.gif_frame_selector: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("GIF 帧选择", size=14, weight=ft.FontWeight.W_500),
                            ft.Icon(
                                ft.Icons.INFO_OUTLINE,
                                size=16,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="选择要裁剪的 GIF 帧\n可以输入帧号或使用左右按钮切换",
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.SKIP_PREVIOUS,
                                on_click=self._on_prev_frame,
                                tooltip="上一帧",
                            ),
                            ft.Text("帧:", size=14),
                            self.gif_frame_input,
                            self.gif_total_frames_text,
                            ft.IconButton(
                                icon=ft.Icons.SKIP_NEXT,
                                on_click=self._on_next_frame,
                                tooltip="下一帧",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        
        # GIF 导出选项（初始隐藏）
        self.gif_export_mode: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="current_frame",
                        label="当前帧（静态图片）",
                    ),
                    ft.Radio(
                        value="all_frames",
                        label="所有帧（保留动画）",
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            value="current_frame",
        )
        
        self.gif_export_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("导出选项", size=14, weight=ft.FontWeight.W_500),
                            ft.Icon(
                                ft.Icons.INFO_OUTLINE,
                                size=16,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="当前帧：导出为静态图片（PNG/JPG）\n所有帧：保留动画效果（GIF）",
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    self.gif_export_mode,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        
        # 控制按钮（垂直排列，更紧凑）
        select_button = ft.ElevatedButton(
            text="选择图片",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_select_file,
            width=280,
            tooltip="选择要裁剪的图片（支持 GIF 动画）",
        )
        reset_button = ft.OutlinedButton(
            text="重置裁剪",
            icon=ft.Icons.REFRESH,
            on_click=self._on_reset,
            width=280,
            tooltip="将裁剪框重置到图片中央",
        )
        
        self.save_button = ft.FilledButton(
            text="导出裁剪结果",
            icon=ft.Icons.SAVE,
            on_click=self._on_save_result,
            disabled=True,
            width=280,
            tooltip="导出裁剪后的图片",
        )
        
        # 按钮区域（占据下半部分，1:1 平分）
        button_area = ft.Container(
            content=ft.Column(
                controls=[
                    self.gif_frame_selector,
                    self.gif_export_options,
                    select_button,
                    reset_button,
                    self.save_button,
                ],
                spacing=PADDING_MEDIUM,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=1,  # 占据下半部分（1:1 比例）
            margin=ft.margin.only(top=-4),  # 向上移动减小与预览区域的距离
        )
        
        # 右侧区域（预览 + 按钮，上下平分）
        right_side = ft.Container(
            content=ft.Column(
                controls=[
                    preview_area,  # 上半部分：预览
                    button_area,   # 下半部分：GIF选项 + 按钮
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,  # 居中对齐
                spacing=20,  # 减小间距
            ),
            expand=1,  # 动态调整宽度，与左侧裁剪区域按比例分配
            padding=ft.padding.only(right=PADDING_LARGE),
        )
        
        # 组装 - 左右布局
        main_row = ft.Row(
            controls=[
                crop_area,
                right_side,
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                self.instruction_card,
                main_row,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
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
            expand=True,
        )

        # 初始化画布尺寸约束
        self._update_max_canvas_constraints()
        self._apply_canvas_dimensions()

    def _get_theme_primary_color(self) -> str:
        """根据当前主题返回主颜色。"""
        try:
            theme = None
            if self.page.theme_mode == ft.ThemeMode.DARK and self.page.dark_theme:
                theme = self.page.dark_theme
            elif self.page.theme:
                theme = self.page.theme

            if theme and getattr(theme, "color_scheme_seed", None):
                return theme.color_scheme_seed
        except Exception:
            pass
        return PRIMARY_COLOR
    
    def _update_instruction_card_gradient(self) -> None:
        """更新指南卡片的渐变色（响应主题色变化）。"""
        primary_color: str = self._get_theme_primary_color()
        self.instruction_card.gradient = ft.LinearGradient(
            begin=ft.alignment.center_left,
            end=ft.alignment.center_right,
            colors=[
                ft.Colors.with_opacity(0.85, primary_color),
                ft.Colors.with_opacity(0.65, primary_color),
            ],
        )
        # 更新空状态的背景色
        if hasattr(self, 'empty_state_widget'):
            self.empty_state_widget.bgcolor = ft.Colors.with_opacity(0.05, primary_color)
    
    def did_mount(self) -> None:
        """组件挂载时调用 - 确保主题色正确。"""
        self._update_instruction_card_gradient()
        try:
            self.page.update()
        except:
            pass

    def _update_max_canvas_constraints(self) -> None:
        """根据窗口大小更新画布的最大宽高限制。"""
        window_width: int = int(self.page.width or WINDOW_WIDTH)
        window_height: int = int(self.page.height or WINDOW_HEIGHT)

        # 左侧区域大约占比 62%，减去外边距和安全余量
        available_width: int = int(window_width * 0.62)
        available_width -= (PADDING_XLARGE * 2 + PADDING_LARGE * 2 + 60)
        available_width = max(360, min(available_width, 900))

        # 垂直方向扣除上下边距、标题和按钮区域
        available_height: int = window_height - (PADDING_XLARGE * 2 + 220)
        available_height = max(320, min(available_height, 720))

        self.max_canvas_width = available_width
        self.max_canvas_height = available_height

    def _apply_canvas_dimensions(self) -> None:
        """将当前画布尺寸应用到相关组件，并确保不超界。"""
        self.canvas_width = max(240, min(self.canvas_width, self.max_canvas_width))
        self.canvas_height = max(200, min(self.canvas_height, self.max_canvas_height))

        # 更新画布及相关容器尺寸
        self.canvas_stack.width = self.canvas_width
        self.canvas_stack.height = self.canvas_height
        self.crop_canvas.width = self.canvas_width
        self.crop_canvas.height = self.canvas_height
        self.original_image_widget.width = self.canvas_width
        self.original_image_widget.height = self.canvas_height

        # 尺寸包含刻度尺占用空间
        self.canvas_with_rulers.width = self.canvas_width + 30
        self.canvas_with_rulers.height = self.canvas_height + 20

        # 包裹容器需要考虑 padding
        self.canvas_container.width = self.canvas_width + PADDING_LARGE * 2 + 30
        self.canvas_container.height = self.canvas_height + PADDING_LARGE * 2 + 20
    
    def _calculate_canvas_size(self, img_width: int, img_height: int) -> tuple[int, int]:
        """计算合适的画布尺寸（适配图片大小但不超出最大限制）。
        
        Args:
            img_width: 图片宽度
            img_height: 图片高度
        
        Returns:
            (画布宽度, 画布高度)
        """
        # 如果图片小于最大限制，使用图片实际尺寸
        if img_width <= self.max_canvas_width and img_height <= self.max_canvas_height:
            return img_width, img_height
        
        # 如果图片超出限制，按比例缩放
        width_ratio = self.max_canvas_width / img_width
        height_ratio = self.max_canvas_height / img_height
        scale = min(width_ratio, height_ratio)
        
        return int(img_width * scale), int(img_height * scale)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回。"""
        if self.on_back:
            self.on_back()
    
    def _on_canvas_click(self, e: ft.ControlEvent) -> None:
        """点击裁剪区域，如果未选择图片则打开选择文件对话框。"""
        if not self.selected_file:
            self._on_select_file(e)
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件。"""
        file_picker = ft.FilePicker(on_result=self._on_file_selected)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "gif"],
            allow_multiple=False,
        )
    
    def _on_file_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择完成。"""
        if not e.files:
            return
        
        try:
            file_path = Path(e.files[0].path)
            self.selected_file = file_path
            
            # 检测是否为动态 GIF
            self.is_animated_gif = GifUtils.is_animated_gif(file_path)
            if self.is_animated_gif:
                self.gif_frame_count = GifUtils.get_frame_count(file_path)
                self.current_frame_index = 0
                # 提取第一帧
                self.original_image = GifUtils.extract_frame(file_path, 0)
                # 显示 GIF 帧选择器和导出选项
                self.gif_frame_selector.visible = True
                self.gif_export_options.visible = True
                self.gif_frame_input.value = "1"
                self.gif_total_frames_text.value = f"/ {self.gif_frame_count}"
            else:
                self.original_image = Image.open(file_path)
                # 隐藏 GIF 帧选择器和导出选项
                self.gif_frame_selector.visible = False
                self.gif_export_options.visible = False
            
            # 获取图片尺寸
            img_w, img_h = self.original_image.width, self.original_image.height
 
            # 根据当前窗口更新画布限制
            self._update_max_canvas_constraints()
            # 计算合适的画布尺寸
            self.canvas_width, self.canvas_height = self._calculate_canvas_size(img_w, img_h)
            self._apply_canvas_dimensions()
 
            # 显示原图（GIF 需要保存临时帧）
            if self.is_animated_gif:
                # 保存当前帧为临时文件
                temp_frame_path = self.config_service.get_temp_dir() / f"gif_frame_{self.current_frame_index}.png"
                self.original_image.save(temp_frame_path)
                self.original_image_widget.src = str(temp_frame_path)
            else:
                self.original_image_widget.src = str(file_path)
            
            self.original_image_widget.visible = True
            self.empty_state_widget.visible = False
            
            # 更新画布容器提示（已选择图片后）
            self.canvas_clickable.tooltip = "拖动蓝框移动位置，拖动四个角调整大小"
            
            # 初始化裁剪框（居中，1/2大小）
            self.crop_width = min(img_w // 2, 400)
            self.crop_height = min(img_h // 2, 400)
            self.crop_x = (img_w - self.crop_width) // 2
            self.crop_y = (img_h - self.crop_height) // 2
            
            # 更新裁剪框显示
            self._update_crop_box_position()
            self._update_preview()
            
            self.save_button.disabled = False
            self.page.update()
            
        except Exception as ex:
            print(f"加载失败: {ex}")
    
    def _calculate_image_display_bounds(self) -> None:
        """计算图片在画布中的实际显示位置和大小。"""
        if not self.original_image:
            return
        
        img_w, img_h = self.original_image.width, self.original_image.height
        img_ratio = img_w / img_h
        canvas_ratio = self.canvas_width / self.canvas_height
        
        # 根据 CONTAIN 模式计算实际显示大小
        if img_ratio > canvas_ratio:
            # 图片更宽，以画布宽度为准
            self.img_display_width = self.canvas_width
            self.img_display_height = self.canvas_width / img_ratio
            self.img_display_x = 0
            self.img_display_y = (self.canvas_height - self.img_display_height) / 2
        else:
            # 图片更高，以画布高度为准
            self.img_display_width = self.canvas_height * img_ratio
            self.img_display_height = self.canvas_height
            self.img_display_x = (self.canvas_width - self.img_display_width) / 2
            self.img_display_y = 0
    
    def _throttled_update_position(self) -> None:
        """节流更新裁剪框位置,减少page.update()调用频率"""
        import time
        current_time = time.time()
        
        # 节流时间间隔(秒) - 30ms更新一次,约33fps
        throttle_interval = 0.03
        
        # 更新位置数据(不刷新UI)
        self._update_crop_box_position_data()
        
        # 只有距离上次更新超过节流间隔才真正刷新UI
        if current_time - self._last_update_time >= throttle_interval:
            try:
                self.page.update()
                self._last_update_time = current_time
            except:
                pass
    
    def _update_crop_box_position_data(self) -> None:
        """只更新裁剪框位置数据,不调用page.update()"""
        if not self.original_image:
            return
        
        # 计算图片在画布中的实际显示区域
        self._calculate_image_display_bounds()
        
        # 计算缩放比例
        img_w, img_h = self.original_image.width, self.original_image.height
        scale_x = self.img_display_width / img_w
        scale_y = self.img_display_height / img_h
        
        # 设置裁剪框位置和大小（加上图片偏移量）
        box_left = self.img_display_x + self.crop_x * scale_x
        box_top = self.img_display_y + self.crop_y * scale_y
        box_w = self.crop_width * scale_x
        box_h = self.crop_height * scale_y
        
        self.crop_box_container.top = box_top
        self.crop_box_container.left = box_left
        self.crop_box_container.width = box_w
        self.crop_box_container.height = box_h
        self.crop_box_container.visible = True
        
        # 设置四个角控制点位置
        handle_offset = 6
        self.handle_nw.top = box_top - handle_offset
        self.handle_nw.left = box_left - handle_offset
        self.handle_nw.visible = True
        
        self.handle_ne.top = box_top - handle_offset
        self.handle_ne.left = box_left + box_w - handle_offset
        self.handle_ne.visible = True
        
        self.handle_sw.top = box_top + box_h - handle_offset
        self.handle_sw.left = box_left - handle_offset
        self.handle_sw.visible = True
        
        self.handle_se.top = box_top + box_h - handle_offset
        self.handle_se.left = box_left + box_w - handle_offset
        self.handle_se.visible = True
        
        # 更新刻度尺
        self._update_rulers()
    
    def _update_crop_box_position(self, skip_update: bool = False) -> None:
        """更新裁剪框在画布上的位置。
        
        Args:
            skip_update: 是否跳过page.update()调用,用于拖动时减少刷新次数
        """
        if not self.original_image:
            return
        
        # 计算图片在画布中的实际显示区域
        self._calculate_image_display_bounds()
        
        # 计算缩放比例
        img_w, img_h = self.original_image.width, self.original_image.height
        scale_x = self.img_display_width / img_w
        scale_y = self.img_display_height / img_h
        
        # 设置裁剪框位置和大小（加上图片偏移量）
        box_left = self.img_display_x + self.crop_x * scale_x
        box_top = self.img_display_y + self.crop_y * scale_y
        box_w = self.crop_width * scale_x
        box_h = self.crop_height * scale_y
        
        self.crop_box_container.top = box_top
        self.crop_box_container.left = box_left
        self.crop_box_container.width = box_w
        self.crop_box_container.height = box_h
        self.crop_box_container.visible = True  # 显示裁剪框
        
        # 设置四个角控制点位置（6 是控制点半径）
        handle_offset = 6
        # 左上角 (NW)
        self.handle_nw.top = box_top - handle_offset
        self.handle_nw.left = box_left - handle_offset
        self.handle_nw.visible = True
        # 右上角 (NE)
        self.handle_ne.top = box_top - handle_offset
        self.handle_ne.left = box_left + box_w - handle_offset
        self.handle_ne.visible = True
        # 左下角 (SW)
        self.handle_sw.top = box_top + box_h - handle_offset
        self.handle_sw.left = box_left - handle_offset
        self.handle_sw.visible = True
        # 右下角 (SE)
        self.handle_se.top = box_top + box_h - handle_offset
        self.handle_se.left = box_left + box_w - handle_offset
        self.handle_se.visible = True
        
        # 更新刻度尺
        self._update_rulers()
        
        # 只在非拖动时更新页面
        if not skip_update:
            try:
                self.page.update()
            except:
                pass
    
    def _update_rulers(self) -> None:
        """更新刻度尺显示。"""
        if not self.original_image:
            self.ruler_horizontal.visible = False
            self.ruler_vertical.visible = False
            return
        
        # 获取图片尺寸
        img_w, img_h = self.original_image.width, self.original_image.height
        
        # 计算刻度间隔（根据图片大小自动调整）
        def get_ruler_interval(size: int) -> int:
            """根据尺寸自动选择合适的刻度间隔。"""
            if size <= 200:
                return 20
            elif size <= 500:
                return 50
            elif size <= 1000:
                return 100
            elif size <= 2000:
                return 200
            else:
                return 500
        
        h_interval = get_ruler_interval(img_w)
        v_interval = get_ruler_interval(img_h)
        
        # 生成水平刻度尺（顶部）
        h_ruler_controls = []
        # 添加起始占位符（对齐垂直刻度尺的宽度）
        h_ruler_controls.append(ft.Container(width=30, height=20))
        
        scale_x = self.img_display_width / img_w
        for i in range(0, img_w + 1, h_interval):
            if i > img_w:
                break
            pixel_pos = i * scale_x
            h_ruler_controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                width=1,
                                height=6,
                                bgcolor=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                str(i),
                                size=9,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    width=pixel_pos if i == 0 else (h_interval * scale_x),
                )
            )
        
        self.ruler_horizontal.controls = h_ruler_controls
        self.ruler_horizontal.visible = True
        
        # 生成垂直刻度尺（左侧）
        v_ruler_controls = []
        # 添加起始占位符（对齐水平刻度尺的高度）
        v_ruler_controls.append(ft.Container(width=30, height=20))
        
        scale_y = self.img_display_height / img_h
        for i in range(0, img_h + 1, v_interval):
            if i > img_h:
                break
            pixel_pos = i * scale_y
            v_ruler_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(
                                str(i),
                                size=9,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.RIGHT,
                                width=24,
                            ),
                            ft.Container(
                                width=6,
                                height=1,
                                bgcolor=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=pixel_pos if i == 0 else (v_interval * scale_y),
                )
            )
        
        self.ruler_vertical.controls = v_ruler_controls
        self.ruler_vertical.visible = True
    
    def _on_crop_pan_start(self, e: ft.DragStartEvent) -> None:
        """开始拖动裁剪框。"""
        self.is_dragging = True
        self.drag_start_x = e.global_x
        self.drag_start_y = e.global_y
        self.crop_start_x = self.crop_x
        self.crop_start_y = self.crop_y
    
    def _on_crop_pan_update(self, e: ft.DragUpdateEvent) -> None:
        """拖动裁剪框中。"""
        if not self.is_dragging or not self.original_image:
            return
        
        # 计算移动距离
        dx = e.global_x - self.drag_start_x
        dy = e.global_y - self.drag_start_y
        
        # 计算缩放比例（显示尺寸到图片尺寸）
        img_w, img_h = self.original_image.width, self.original_image.height
        
        if self.img_display_width > 0:
            scale_x = self.img_display_width / img_w
            scale_y = self.img_display_height / img_h
        else:
            scale_x = scale_y = 1
        
        # 转换为图片坐标
        dx_img = int(dx / scale_x)
        dy_img = int(dy / scale_y)
        
        # 更新裁剪坐标
        new_x = self.crop_start_x + dx_img
        new_y = self.crop_start_y + dy_img
        
        # 边界检查（确保不超出图片）
        new_x = max(0, min(new_x, img_w - self.crop_width))
        new_y = max(0, min(new_y, img_h - self.crop_height))
        
        self.crop_x = new_x
        self.crop_y = new_y
        
        # 使用节流更新,提升拖动流畅度
        self._throttled_update_position()
    
    def _on_crop_pan_end(self, e: ft.DragEndEvent) -> None:
        """拖动结束。"""
        self.is_dragging = False
        # 拖动结束后更新预览
        self._update_preview()
    
    def _on_resize_start(self, e: ft.DragStartEvent, mode: str) -> None:
        """开始调整大小。"""
        self.resize_mode = mode
        self.drag_start_x = e.global_x
        self.drag_start_y = e.global_y
        self.crop_start_x = self.crop_x
        self.crop_start_y = self.crop_y
        # 记录初始宽高（用于计算调整量）
        self.crop_start_width = self.crop_width
        self.crop_start_height = self.crop_height
    
    def _on_resize_update(self, e: ft.DragUpdateEvent, mode: str) -> None:
        """调整大小中。"""
        if not self.resize_mode or not self.original_image:
            return
        
        # 计算移动距离
        dx = e.global_x - self.drag_start_x
        dy = e.global_y - self.drag_start_y
        
        # 计算缩放比例（显示尺寸到图片尺寸）
        img_w, img_h = self.original_image.width, self.original_image.height
        
        if self.img_display_width > 0:
            scale_x = self.img_display_width / img_w
            scale_y = self.img_display_height / img_h
        else:
            scale_x = scale_y = 1
        
        # 转换为图片坐标
        dx_img = int(dx / scale_x)
        dy_img = int(dy / scale_y)
        
        # 根据不同角落调整裁剪框（基于初始值计算，避免累积误差）
        if mode == 'se':
            # 右下角：增加宽高
            new_w = self.crop_start_width + dx_img
            new_h = self.crop_start_height + dy_img
            new_w = max(1, min(new_w, img_w - self.crop_x))
            new_h = max(1, min(new_h, img_h - self.crop_y))
            self.crop_width = new_w
            self.crop_height = new_h
            
        elif mode == 'sw':
            # 左下角：调整左边界和高度
            new_x = self.crop_start_x + dx_img
            new_h = self.crop_start_height + dy_img
            new_x = max(0, min(new_x, self.crop_start_x + self.crop_start_width - 1))
            new_h = max(1, min(new_h, img_h - self.crop_y))
            self.crop_width = self.crop_start_width + (self.crop_start_x - new_x)
            self.crop_height = new_h
            self.crop_x = new_x
            
        elif mode == 'ne':
            # 右上角：调整上边界和宽度
            new_y = self.crop_start_y + dy_img
            new_w = self.crop_start_width + dx_img
            new_y = max(0, min(new_y, self.crop_start_y + self.crop_start_height - 1))
            new_w = max(1, min(new_w, img_w - self.crop_x))
            self.crop_height = self.crop_start_height + (self.crop_start_y - new_y)
            self.crop_width = new_w
            self.crop_y = new_y
            
        elif mode == 'nw':
            # 左上角：调整左边界和上边界
            new_x = self.crop_start_x + dx_img
            new_y = self.crop_start_y + dy_img
            new_x = max(0, min(new_x, self.crop_start_x + self.crop_start_width - 1))
            new_y = max(0, min(new_y, self.crop_start_y + self.crop_start_height - 1))
            self.crop_width = self.crop_start_width + (self.crop_start_x - new_x)
            self.crop_height = self.crop_start_height + (self.crop_start_y - new_y)
            self.crop_x = new_x
            self.crop_y = new_y
        
        # 使用节流更新,提升调整大小时的流畅度
        self._throttled_update_position()
    
    def _on_resize_end(self, e: ft.DragEndEvent) -> None:
        """调整大小结束。"""
        self.resize_mode = None
        # 调整大小结束后更新预览
        self._update_preview()
    
    def _schedule_preview_update(self) -> None:
        """延迟更新预览,避免快速操作时出现空白。"""
        import threading
        
        # 取消之前的定时器(如果存在)
        if self._preview_update_timer is not None:
            try:
                self._preview_update_timer.cancel()
            except:
                pass
        
        # 设置新的定时器,200ms后更新预览
        self._preview_update_timer = threading.Timer(0.2, self._update_preview)
        self._preview_update_timer.start()
    
    def _update_preview(self) -> None:
        """更新预览。"""
        if not self.original_image:
            return
        
        try:
            # 裁剪图片
            cropped = self.original_image.crop((
                self.crop_x, self.crop_y,
                self.crop_x + self.crop_width,
                self.crop_y + self.crop_height,
            ))
            
            import time
            timestamp = int(time.time() * 1000)
            preview_path = Path("storage/temp") / f"crop_preview_{timestamp}.png"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存新预览
            cropped.save(preview_path)
            
            # 删除当前预览的旧文件（在设置新路径之后,避免时序问题）
            old_preview_path = self._last_preview_path
            self._last_preview_path = str(preview_path)
            
            # 先更新UI显示新预览
            self.preview_image_widget.src = str(preview_path)
            self.preview_image_widget.visible = True
            
            # 更新尺寸显示到标题旁边
            self.crop_size_text.value = f"{self.crop_width} × {self.crop_height} px"
            # 隐藏预览区域的提示文字
            self.preview_info_text.visible = False
            
            try:
                self.page.update()
            except:
                pass
            
            # UI更新完成后再删除旧文件
            if old_preview_path:
                try:
                    old_path = Path(old_preview_path)
                    if old_path.exists() and old_path != preview_path:
                        old_path.unlink()
                except:
                    pass
                    
        except Exception as ex:
            print(f"预览失败: {ex}")
    
    def _on_preview_click(self, e: ft.ControlEvent) -> None:
        """点击预览。"""
        if not self.preview_image_widget.src:
            return
        preview_path = Path(self.preview_image_widget.src)
        if preview_path.exists():
            if os.name == 'nt':
                os.startfile(preview_path)
            elif os.name == 'posix':
                subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', str(preview_path)])
    
    def _on_reset(self, e: ft.ControlEvent) -> None:
        """重置。"""
        if not self.original_image:
            return
        
        img_w, img_h = self.original_image.width, self.original_image.height
        self.crop_width = min(img_w // 2, 400)
        self.crop_height = min(img_h // 2, 400)
        self.crop_x = (img_w - self.crop_width) // 2
        self.crop_y = (img_h - self.crop_height) // 2
        
        self._update_crop_box_position()
        self._update_preview()
    
    def _on_save_result(self, e: ft.ControlEvent) -> None:
        """保存。"""
        if not self.original_image or not self.selected_file:
            return
        
        try:
            # 根据 GIF 导出模式决定默认文件名和扩展名
            if self.is_animated_gif and self.gif_export_mode.value == "all_frames":
                default_filename = f"{self.selected_file.stem}_cropped.gif"
                allowed_extensions = ["gif"]
            else:
                default_filename = f"{self.selected_file.stem}_cropped.png"
                allowed_extensions = ["png", "jpg", "jpeg", "jfif", "webp"]
            
            file_picker = ft.FilePicker(on_result=self._on_save_file_selected)
            self.page.overlay.append(file_picker)
            self.page.update()
            file_picker.save_file(
                dialog_title="保存裁剪结果",
                file_name=default_filename,
                allowed_extensions=allowed_extensions,
            )
        except Exception as ex:
            print(f"保存失败: {ex}")
    
    def _on_save_file_selected(self, e: ft.FilePickerResultEvent) -> None:
        """保存文件选择完成。"""
        if not e.path:
            return
        
        try:
            output_path = Path(e.path)
            
            # 如果是 GIF 且选择导出所有帧
            if self.is_animated_gif and self.gif_export_mode.value == "all_frames":
                self._save_as_gif(output_path)
            else:
                # 保存当前帧（或静态图片）
                cropped = self.original_image.crop((
                    self.crop_x, self.crop_y,
                    self.crop_x + self.crop_width,
                    self.crop_y + self.crop_height,
                ))
                cropped.save(output_path)
            
            # 显示保存成功提示
            snackbar = ft.SnackBar(
                content=ft.Text(f"已保存: {output_path.name}"),
                bgcolor=ft.Colors.GREEN,
                duration=2000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
        except Exception as ex:
            print(f"保存失败: {ex}")
            self._show_snackbar(f"保存失败: {str(ex)}", ft.Colors.RED)
    
    def _save_as_gif(self, output_path: Path) -> None:
        """保存为 GIF 动画（裁剪所有帧）。
        
        Args:
            output_path: 输出路径
        """
        if not self.selected_file or not self.is_animated_gif:
            return
        
        try:
            # 显示处理进度
            self._show_snackbar(f"正在处理 {self.gif_frame_count} 帧...", ft.Colors.BLUE)
            
            # 打开原始 GIF
            with Image.open(self.selected_file) as gif:
                # 获取 GIF 参数
                duration = gif.info.get('duration', 100)
                loop = gif.info.get('loop', 0)
                
                # 裁剪所有帧
                cropped_frames = []
                for frame_idx in range(self.gif_frame_count):
                    # 提取帧
                    frame = GifUtils.extract_frame(self.selected_file, frame_idx)
                    if frame is None:
                        continue
                    
                    # 裁剪
                    cropped = frame.crop((
                        self.crop_x, self.crop_y,
                        self.crop_x + self.crop_width,
                        self.crop_y + self.crop_height,
                    ))
                    cropped_frames.append(cropped)
                
                # 保存为 GIF
                if cropped_frames:
                    cropped_frames[0].save(
                        output_path,
                        save_all=True,
                        append_images=cropped_frames[1:],
                        duration=duration,
                        loop=loop,
                        optimize=False,
                    )
        except Exception as ex:
            raise Exception(f"导出 GIF 失败: {str(ex)}")
    
    def _on_prev_frame(self, e: ft.ControlEvent) -> None:
        """切换到上一帧。"""
        if not self.is_animated_gif or not self.selected_file:
            return
        
        # 切换帧索引
        self.current_frame_index = (self.current_frame_index - 1) % self.gif_frame_count
        self._load_gif_frame()
    
    def _on_next_frame(self, e: ft.ControlEvent) -> None:
        """切换到下一帧。"""
        if not self.is_animated_gif or not self.selected_file:
            return
        
        # 切换帧索引
        self.current_frame_index = (self.current_frame_index + 1) % self.gif_frame_count
        self._load_gif_frame()
    
    def _on_frame_input_submit(self, e: ft.ControlEvent) -> None:
        """手动输入帧号并回车时的事件。"""
        if not self.is_animated_gif or self.gif_frame_count <= 1:
            return
        
        try:
            frame_num = int(self.gif_frame_input.value)
            if 1 <= frame_num <= self.gif_frame_count:
                self.current_frame_index = frame_num - 1
                self._load_gif_frame()
            else:
                self._show_snackbar(f"帧号必须在 1 到 {self.gif_frame_count} 之间", ft.Colors.ORANGE)
                self.gif_frame_input.value = str(self.current_frame_index + 1)
                self.page.update()
        except ValueError:
            self._show_snackbar("请输入有效的数字", ft.Colors.ORANGE)
            self.gif_frame_input.value = str(self.current_frame_index + 1)
            self.page.update()
    
    def _load_gif_frame(self) -> None:
        """加载指定帧。"""
        if not self.selected_file or not self.is_animated_gif:
            return
        
        try:
            # 提取指定帧
            self.original_image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
            if self.original_image is None:
                return
            
            # 保存当前帧为临时文件
            temp_frame_path = self.config_service.get_temp_dir() / f"gif_frame_{self.current_frame_index}.png"
            self.original_image.save(temp_frame_path)
            self.original_image_widget.src = str(temp_frame_path)
            
            # 更新帧输入框
            self.gif_frame_input.value = str(self.current_frame_index + 1)
            
            # 更新裁剪框和预览
            self._update_crop_box_position()
            self._update_preview()
            
            self.page.update()
        except Exception as ex:
            print(f"加载帧失败: {ex}")
    
    def _on_keyboard(self, e: ft.KeyboardEvent) -> None:
        """键盘事件处理（支持 WASD 精调裁剪框位置）。
        
        Args:
            e: 键盘事件对象
        """
        # 必须有图片加载才能处理键盘事件
        if not self.original_image:
            return
        
        # 获取图片尺寸用于边界检查
        img_w, img_h = self.original_image.width, self.original_image.height
        
        # 判断按键并移动（步长由用户指定，默认1px）
        moved = False
        key = e.key.lower() if hasattr(e.key, 'lower') else str(e.key)
        step = self.fine_tune_step
        
        # W：向上移动
        if key == 'w':
            if self.crop_y > 0:
                self.crop_y = max(0, self.crop_y - step)
                moved = True
        
        # S：向下移动
        elif key == 's':
            if self.crop_y + self.crop_height < img_h:
                self.crop_y = min(img_h - self.crop_height, self.crop_y + step)
                moved = True
        
        # A：向左移动
        elif key == 'a':
            if self.crop_x > 0:
                self.crop_x = max(0, self.crop_x - step)
                moved = True
        
        # D：向右移动
        elif key == 'd':
            if self.crop_x + self.crop_width < img_w:
                self.crop_x = min(img_w - self.crop_width, self.crop_x + step)
                moved = True
        
        # 如果移动了，更新显示
        if moved:
            self._update_crop_box_position()
            # 使用延迟更新预览，避免快速按键时出现空白
            self._schedule_preview_update()
    
    def _on_fine_tune_step_change(self, e: ft.ControlEvent) -> None:
        """精调步长输入框变化事件。"""
        try:
            value = int(self.fine_tune_input.value)
            if value >= 1 and value <= 100:
                self.fine_tune_step = value
            else:
                # 超出范围，恢复为当前值
                self.fine_tune_input.value = str(self.fine_tune_step)
                self.page.update()
        except ValueError:
            # 输入非数字，恢复为当前值
            self.fine_tune_input.value = str(self.fine_tune_step)
            self.page.update()
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        try:
            self.page.update()
        except:
            pass
    
    def _on_window_resize(self, e: ft.ControlEvent) -> None:
        """窗口大小变化时的处理。"""
        # 更新最大画布尺寸
        self._update_max_canvas_constraints()
        try:
            if self.original_image:
                img_w, img_h = self.original_image.width, self.original_image.height
                self.canvas_width, self.canvas_height = self._calculate_canvas_size(img_w, img_h)
            # 无论是否有图片都需要应用尺寸以限制占位
            self._apply_canvas_dimensions()

            if self.original_image:
                self._update_crop_box_position()

            self.page.update()
        except Exception:
            # 静默处理，避免影响用户体验
            pass

