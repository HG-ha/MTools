"""图片裁剪视图模块。

提供可视化的图片裁剪功能，支持拖动裁剪框。
"""

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
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService

# 屏蔽 libpng 的 iCCP 警告
warnings.filterwarnings("ignore", message=".*iCCP.*", category=UserWarning)


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
            right=PADDING_XLARGE + 16,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 选中的文件
        self.selected_file: Optional[Path] = None
        self.original_image: Optional[Image.Image] = None
        
        # 预览文件路径（用于清理）
        self._last_preview_path: Optional[str] = None
        
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
        
        # 创建UI组件
        self._build_ui()
        
        # 注册键盘事件
        self.page.on_keyboard_event = self._on_keyboard
    
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
                ft.Text("图片裁剪", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 说明文本
        description_text: ft.Container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_SECONDARY),
                    ft.Text(
                        "拖动蓝框移动位置 | 拖动四个角调整大小 | WASD键精确微调1px",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
                spacing=8,
            ),
            margin=ft.margin.only(left=4, top=4, bottom=PADDING_MEDIUM),
        )
        
        # 空状态（占满画布）
        self.empty_state_widget: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, size=64, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("点击下方「选择图片」按钮开始裁剪", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=PADDING_MEDIUM,
            ),
            alignment=ft.alignment.center,
            expand=True,  # 占满整个 Stack
        )
        
        # 原图显示（居中保持比例）
        self.original_image_widget: ft.Image = ft.Image(
            fit=ft.ImageFit.CONTAIN,
            visible=False,
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
        
        # 裁剪信息显示
        self.crop_info_text: ft.Text = ft.Text(
            "",
            size=14,
            color=ft.Colors.PRIMARY,
            weight=ft.FontWeight.BOLD,
            bgcolor="#FFFFFFFF",
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
                ft.Container(content=self.crop_info_text, padding=8, top=10, left=10),
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
        
        self.canvas_container: ft.Container = ft.Container(
            content=self.canvas_stack,
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
                    self.canvas_container,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            ),
            expand=True,  # 占据剩余空间
            padding=ft.padding.only(left=PADDING_LARGE, right=PADDING_MEDIUM),
        )
        
        # 右侧预览区域（缩小尺寸）
        self.preview_image_widget: ft.Image = ft.Image(
            width=300,
            height=300,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        self.preview_info_text: ft.Text = ft.Text(
            "选择图片后拖动裁剪框查看效果",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.CENTER,
        )
        
        preview_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("裁剪预览", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image_widget,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        alignment=ft.alignment.center,
                        width=300,
                        height=300,
                        on_click=self._on_preview_click,
                        tooltip="点击用系统默认应用打开",
                        ink=True,
                        padding=PADDING_MEDIUM,  # 添加内边距
                    ),
                    ft.Container(height=PADDING_SMALL),
                    self.preview_info_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 控制按钮（垂直排列，更紧凑）
        select_button = ft.ElevatedButton(
            text="选择图片",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_select_file,
            width=280,
        )
        reset_button = ft.OutlinedButton(
            text="重置裁剪",
            icon=ft.Icons.REFRESH,
            on_click=self._on_reset,
            width=280,
        )
        
        self.save_button = ft.FilledButton(
            text="导出裁剪结果",
            icon=ft.Icons.SAVE,
            on_click=self._on_save_result,
            disabled=True,
            width=280,
        )
        
        button_area = ft.Column(
            controls=[
                select_button,
                reset_button,
                self.save_button,
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 右侧区域（预览 + 按钮）
        right_side = ft.Container(
            content=ft.Column(
                controls=[
                    preview_area,
                    ft.Container(height=PADDING_MEDIUM),
                    button_area,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.START,
                spacing=0,
            ),
            width=380,
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
        
        self.content = ft.Column(
            controls=[
                header,
                description_text,
                main_row,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    
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
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件。"""
        file_picker = ft.FilePicker(on_result=self._on_file_selected)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp"],
            allow_multiple=False,
        )
    
    def _on_file_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择完成。"""
        if not e.files:
            return
        
        try:
            file_path = Path(e.files[0].path)
            self.selected_file = file_path
            self.original_image = Image.open(file_path)
            
            # 获取图片尺寸
            img_w, img_h = self.original_image.width, self.original_image.height
            
            # 计算合适的画布尺寸
            self.canvas_width, self.canvas_height = self._calculate_canvas_size(img_w, img_h)
            
            # 更新 Stack 尺寸（确保裁剪框可以正确定位）
            self.canvas_stack.width = self.canvas_width
            self.canvas_stack.height = self.canvas_height
            self.crop_canvas.width = self.canvas_width
            self.crop_canvas.height = self.canvas_height
            
            # 显示原图
            self.original_image_widget.src = str(file_path)
            self.original_image_widget.visible = True
            self.empty_state_widget.visible = False
            
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
    
    def _update_crop_box_position(self) -> None:
        """更新裁剪框在画布上的位置。"""
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
        
        # 更新信息
        self.crop_info_text.value = f"{self.crop_width} × {self.crop_height} px"
        self.crop_info_text.visible = True
        
        try:
            self.page.update()
        except:
            pass
    
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
        
        # 拖动时只更新裁剪框位置，不更新预览（避免CPU飙升）
        self._update_crop_box_position()
    
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
            new_w = max(50, min(new_w, img_w - self.crop_x))
            new_h = max(50, min(new_h, img_h - self.crop_y))
            self.crop_width = new_w
            self.crop_height = new_h
            
        elif mode == 'sw':
            # 左下角：调整左边界和高度
            new_x = self.crop_start_x + dx_img
            new_h = self.crop_start_height + dy_img
            new_x = max(0, min(new_x, self.crop_start_x + self.crop_start_width - 50))
            new_h = max(50, min(new_h, img_h - self.crop_y))
            self.crop_width = self.crop_start_width + (self.crop_start_x - new_x)
            self.crop_height = new_h
            self.crop_x = new_x
            
        elif mode == 'ne':
            # 右上角：调整上边界和宽度
            new_y = self.crop_start_y + dy_img
            new_w = self.crop_start_width + dx_img
            new_y = max(0, min(new_y, self.crop_start_y + self.crop_start_height - 50))
            new_w = max(50, min(new_w, img_w - self.crop_x))
            self.crop_height = self.crop_start_height + (self.crop_start_y - new_y)
            self.crop_width = new_w
            self.crop_y = new_y
            
        elif mode == 'nw':
            # 左上角：调整左边界和上边界
            new_x = self.crop_start_x + dx_img
            new_y = self.crop_start_y + dy_img
            new_x = max(0, min(new_x, self.crop_start_x + self.crop_start_width - 50))
            new_y = max(0, min(new_y, self.crop_start_y + self.crop_start_height - 50))
            self.crop_width = self.crop_start_width + (self.crop_start_x - new_x)
            self.crop_height = self.crop_start_height + (self.crop_start_y - new_y)
            self.crop_x = new_x
            self.crop_y = new_y
        
        # 调整大小时只更新裁剪框位置，不更新预览（避免CPU飙升）
        self._update_crop_box_position()
    
    def _on_resize_end(self, e: ft.DragEndEvent) -> None:
        """调整大小结束。"""
        self.resize_mode = None
        # 调整大小结束后更新预览
        self._update_preview()
    
    def _update_preview(self) -> None:
        """更新预览。"""
        if not self.original_image:
            return
        
        try:
            cropped = self.original_image.crop((
                self.crop_x, self.crop_y,
                self.crop_x + self.crop_width,
                self.crop_y + self.crop_height,
            ))
            
            import time
            timestamp = int(time.time() * 1000)
            preview_path = Path("storage/temp") / f"crop_preview_{timestamp}.png"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 删除当前预览的旧文件（如果存在）
            if hasattr(self, '_last_preview_path') and self._last_preview_path:
                try:
                    old_path = Path(self._last_preview_path)
                    if old_path.exists():
                        old_path.unlink()
                except:
                    pass
            
            # 保存新预览
            cropped.save(preview_path)
            self._last_preview_path = str(preview_path)
            
            self.preview_image_widget.src = str(preview_path)
            self.preview_image_widget.visible = True
            self.preview_info_text.value = f"裁剪尺寸: {self.crop_width} × {self.crop_height} 像素"
            
            try:
                self.page.update()
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
            default_filename = f"{self.selected_file.stem}_cropped.png"
            file_picker = ft.FilePicker(on_result=self._on_save_file_selected)
            self.page.overlay.append(file_picker)
            self.page.update()
            file_picker.save_file(
                dialog_title="保存裁剪结果",
                file_name=default_filename,
                allowed_extensions=["png", "jpg", "jpeg", "webp"],
            )
        except Exception as ex:
            print(f"保存失败: {ex}")
    
    def _on_save_file_selected(self, e: ft.FilePickerResultEvent) -> None:
        """保存文件选择完成。"""
        if not e.path:
            return
        
        try:
            cropped = self.original_image.crop((
                self.crop_x, self.crop_y,
                self.crop_x + self.crop_width,
                self.crop_y + self.crop_height,
            ))
            output_path = Path(e.path)
            cropped.save(output_path)
            
            if hasattr(self.page, 'snack_bar'):
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"已保存: {output_path.name}"))
                self.page.snack_bar.open = True
                self.page.update()
        except Exception as ex:
            print(f"保存失败: {ex}")
    
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
        
        # 判断按键并移动 1px（只支持 WASD）
        moved = False
        key = e.key.lower() if hasattr(e.key, 'lower') else str(e.key)
        
        # W：向上移动
        if key == 'w':
            if self.crop_y > 0:
                self.crop_y -= 1
                moved = True
        
        # S：向下移动
        elif key == 's':
            if self.crop_y + self.crop_height < img_h:
                self.crop_y += 1
                moved = True
        
        # A：向左移动
        elif key == 'a':
            if self.crop_x > 0:
                self.crop_x -= 1
                moved = True
        
        # D：向右移动
        elif key == 'd':
            if self.crop_x + self.crop_width < img_w:
                self.crop_x += 1
                moved = True
        
        # 如果移动了，更新显示
        if moved:
            self._update_crop_box_position()
            # 精调时也更新预览，但不会频繁（因为是单次按键）
            self._update_preview()

