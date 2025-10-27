"""单图切分视图模块。

提供单图切分（九宫格）功能的用户界面。
"""

import io
import os
import threading
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
        self.page: ft.Page = page
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
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
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
                ft.Text("单图切分", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 左侧：文件选择和预览
        # 空状态提示
        self.empty_state_widget: ft.Column = ft.Column(
            controls=[
                ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=TEXT_SECONDARY),
                ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                ft.Text("点击选择文件按钮或点击此处选择图片", color=TEXT_SECONDARY, size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=PADDING_MEDIUM // 2,
            visible=True,
        )
        
        # 原图预览
        self.original_image_widget: ft.Image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("原图预览:", size=14, weight=ft.FontWeight.W_500),
                        ft.ElevatedButton(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_file,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_SECONDARY),
                            ft.Text(
                                "选择一张图片进行切分拼接",
                                size=12,
                                color=TEXT_SECONDARY,
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
                                alignment=ft.alignment.center,
                            ),
                            ft.Container(
                                content=self.original_image_widget,
                                alignment=ft.alignment.center,
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
        )
        
        self.gif_total_frames_text: ft.Text = ft.Text("", size=12, color=TEXT_SECONDARY)
        
        self.gif_frame_selector: ft.Container = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ORANGE),
                    ft.Text("GIF 文件 - 选择要切分的帧:", size=12, color=TEXT_SECONDARY),
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
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_option_change,
        )
        
        self.split_cols: ft.TextField = ft.TextField(
            label="列数",
            value="3",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_option_change,
        )
        
        self.split_spacing_input: ft.TextField = ft.TextField(
            label="切块间距",
            value="5",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
            on_change=self._on_option_change,
        )
        
        self.corner_radius_input: ft.TextField = ft.TextField(
            label="切块圆角",
            value="0",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
            on_change=self._on_option_change,
        )
        
        self.overall_corner_radius_input: ft.TextField = ft.TextField(
            label="整体圆角",
            value="0",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
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
                ft.dropdown.Option("image", "背景图片"),
            ],
            width=120,
            on_change=self._on_bg_color_change,
        )
        
        # 背景图片选择按钮
        self.bg_image_button: ft.ElevatedButton = ft.ElevatedButton(
            "选择背景图",
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
        
        self.split_shuffle: ft.Checkbox = ft.Checkbox(
            label="随机打乱",
            value=False,
            on_change=self._on_option_change,
        )
        
        # GIF 动画保留选项
        self.keep_gif_animation: ft.Checkbox = ft.Checkbox(
            label="保留 GIF 动画",
            value=False,
            visible=False,
            on_change=self._on_option_change,
        )
        
        # 不透明度控制
        self.piece_opacity_input: ft.TextField = ft.TextField(
            label="切块不透明度",
            value="100",
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="%",
            on_change=self._on_option_change,
        )
        
        self.bg_opacity_input: ft.TextField = ft.TextField(
            label="背景不透明度",
            value="100",
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="%",
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
                self.split_shuffle,
                self.keep_gif_animation,
            ],
            wrap=True,
            spacing=PADDING_MEDIUM,
            run_spacing=PADDING_MEDIUM,
        )
        
        # 右侧：预览区域（可点击查看）
        self.preview_image_widget: ft.Image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
        )
        
        # 原图显示区域 - 使用Container居中
        self.original_image_container: ft.Container = ft.Container(
            content=self.original_image_widget,
            alignment=ft.alignment.center,
            expand=True,
        )
        
        self.preview_info_text: ft.Text = ft.Text(
            "选择图片后，点击「生成预览」查看效果",
            size=13,
            color=TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )
        
        # 将预览区域改为可点击的容器
        preview_content = ft.Stack(
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
                    options_area,
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
        )
        
        # 底部：按钮行（生成预览 + 保存结果）
        self.preview_button: ft.ElevatedButton = ft.ElevatedButton(
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
        
        self.save_button: ft.ElevatedButton = ft.ElevatedButton(
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
        """选项改变事件。"""
        # 清空预览（选项改变后需要重新生成）
        self._clear_preview()
    
    
    def _on_bg_color_change(self, e: ft.ControlEvent) -> None:
        """背景色变化事件。"""
        is_custom = self.split_bg_color.value == "custom"
        is_image = self.split_bg_color.value == "image"
        
        self.custom_color_r.visible = is_custom
        self.custom_color_g.visible = is_custom
        self.custom_color_b.visible = is_custom
        self.bg_image_button.visible = is_image
        
        try:
            self.custom_color_r.update()
            self.custom_color_g.update()
            self.custom_color_b.update()
            self.bg_image_button.update()
        except:
            pass
        self._clear_preview()
    
    def _on_select_bg_image(self, e: ft.ControlEvent) -> None:
        """选择背景图片按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                self.bg_image_path = Path(result.files[0].path)
                self.bg_image_button.text = f"背景: {self.bg_image_path.name[:15]}..."
                try:
                    self.bg_image_button.update()
                except:
                    pass
                self._clear_preview()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择背景图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp", "tiff"],
            allow_multiple=False,
        )
    
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                self.selected_file = Path(result.files[0].path)
                self._update_file_info()
                self._clear_preview()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "gif"],
            allow_multiple=False,
        )
    
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
                    
                    # 显示 GIF 帧选择器和动画保留选项
                    self.gif_frame_selector.visible = True
                    self.gif_frame_input.value = "1"
                    self.gif_total_frames_text.value = f"/ {self.gif_frame_count}"
                    self.keep_gif_animation.visible = True
                    
                    # 提取第一帧并保存为临时文件
                    try:
                        frame_image = GifUtils.extract_frame(self.selected_file, 0)
                        if frame_image:
                            temp_path = self.config_service.get_temp_dir() / f"gif_frame_0.png"
                            frame_image.save(temp_path)
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
                        self.keep_gif_animation.visible = False
                else:
                    # 隐藏 GIF 帧选择器和动画保留选项
                    self.gif_frame_selector.visible = False
                    self.keep_gif_animation.visible = False
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
            self.empty_state_widget.update()
            self.original_image_widget.update()
        except:
            pass
    
    def _clear_preview(self) -> None:
        """清空预览。"""
        self.preview_image = None
        self.preview_image_widget.src = None  # 清空图片源
        self.preview_image_widget.visible = False
        self.preview_info_text.value = "选择图片后，点击「生成预览」查看效果"  # 重置提示文本
        self.preview_info_text.visible = True
        self.save_button.disabled = True
        try:
            self.preview_image_widget.update()
            self.preview_info_text.update()
            self.save_button.update()
        except:
            pass
    
    def _on_generate_preview(self, e: ft.ControlEvent) -> None:
        """生成预览。"""
        if self.is_processing:
            return
        
        if not self.selected_file:
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
                self._show_snackbar("请先选择背景图片", ft.Colors.ORANGE)
                return
            
            if rows < 1 or cols < 1 or rows > 10 or cols > 10:
                self._show_snackbar("行数和列数必须在1-10之间", ft.Colors.RED)
                return
        except ValueError:
            self._show_snackbar("请输入有效的数字", ft.Colors.RED)
            return
        
        self.is_processing = True
        self.preview_info_text.value = "正在生成预览..."
        self.preview_info_text.visible = True
        try:
            self.page.update()
        except:
            pass
        
        def process_task():
            try:
                # 读取图片（如果是 GIF，使用提取的帧）
                if self.is_animated_gif:
                    image = GifUtils.extract_frame(self.selected_file, self.current_frame_index)
                    if image is None:
                        raise Exception("无法提取 GIF 帧")
                else:
                    image = Image.open(self.selected_file)
                
                # 切分并重新拼接
                result = self._split_and_reassemble(
                    image, rows, cols, shuffle, spacing, 
                    corner_radius, overall_corner_radius,
                    bg_color, custom_rgb, self.bg_image_path,
                    piece_opacity, bg_opacity
                )
                
                # 更新预览
                self._update_preview(result)
                self._show_snackbar("预览生成成功", ft.Colors.GREEN)
            except Exception as ex:
                self._show_snackbar(f"生成预览失败: {ex}", ft.Colors.RED)
                self._clear_preview()
            finally:
                self.is_processing = False
        
        threading.Thread(target=process_task, daemon=True).start()
    
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
        bg_opacity: int = 255
    ) -> Image.Image:
        """切分并重新拼接图片。"""
        import random
        from PIL import ImageDraw
        
        width, height = image.size
        piece_width = width // cols
        piece_height = height // rows
        
        # 切分图片
        pieces = []
        for row in range(rows):
            for col in range(cols):
                left = col * piece_width
                top = row * piece_height
                right = left + piece_width
                bottom = top + piece_height
                
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
        if shuffle:
            random.shuffle(pieces)
        
        # 计算包含间距的新尺寸
        total_spacing_h = spacing * (cols - 1)
        total_spacing_v = spacing * (rows - 1)
        new_width = width + total_spacing_h
        new_height = height + total_spacing_v
        
        # 创建结果图片（根据背景类型）
        if bg_color == "image" and bg_image_path and bg_image_path.exists():
            # 使用背景图片
            try:
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
        for i, piece in enumerate(pieces):
            row = i // cols
            col = i % cols
            left = col * (piece_width + spacing)
            top = row * (piece_height + spacing)
            
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
        
        return result
    
    def _add_rounded_corners(self, image: Image.Image, radius: int) -> Image.Image:
        """给单个切块添加圆角。"""
        from PIL import ImageDraw
        
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
        
        # 应用蒙版
        output = Image.new('RGBA', image.size, (0, 0, 0, 0))
        output.paste(image, (0, 0))
        output.putalpha(mask)
        
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
    
    def _update_preview(self, image: Image.Image) -> None:
        """更新预览图片。"""
        import time
        
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
            for old_file in temp_dir.glob("puzzle_preview_*.png"):
                if old_file != preview_path:
                    try:
                        old_file.unlink()
                    except:
                        pass
        except:
            pass
        
        # 直接使用文件路径显示
        self.preview_image_widget.src = str(preview_path)
        self.preview_image_widget.visible = True
        self.preview_info_text.visible = False
        self.save_button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
    
    def _on_save_result(self, e: ft.ControlEvent) -> None:
        """保存结果。"""
        if not self.preview_image:
            self._show_snackbar("没有可保存的预览图片", ft.Colors.ORANGE)
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
        allowed_extensions = ["png", "jpg", "jpeg"]
        
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
        
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                try:
                    output_path = Path(result.path)
                    
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
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.save_file(
            dialog_title="保存切分结果",
            file_name=default_filename,
            allowed_extensions=allowed_extensions,
        )
    
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
            result = self._split_and_reassemble(
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
            
            # 处理每一帧
            result_frames = []
            for i, frame in enumerate(all_frames):
                # 对当前帧进行切分
                split_frame = self._split_and_reassemble(
                    frame, rows, cols, shuffle, spacing,
                    corner_radius, overall_corner_radius,
                    bg_color, custom_rgb, self.bg_image_path,
                    piece_opacity, bg_opacity
                )
                
                # GIF 不支持半透明！如果结果是 RGBA，需要转换为 RGB
                # 将半透明效果合成到白色背景上
                if split_frame.mode == 'RGBA':
                    # 创建白色背景
                    rgb_frame = Image.new('RGB', split_frame.size, (255, 255, 255))
                    # 使用 alpha 通道合成
                    rgb_frame.paste(split_frame, mask=split_frame.split()[3])
                    split_frame = rgb_frame
                elif split_frame.mode != 'RGB':
                    # 转换其他模式为 RGB
                    split_frame = split_frame.convert('RGB')
                
                result_frames.append(split_frame)
            
            # 获取原始 GIF 的 loop 参数
            with Image.open(self.selected_file) as gif:
                loop = gif.info.get('loop', 0)
            
            # 保存为动态 GIF
            if result_frames:
                result_frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=result_frames[1:],
                    duration=durations,
                    loop=loop,
                    optimize=False
                )
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
            
            # 创建临时文件
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
                self.gif_frame_input.update()
        except ValueError:
            self._show_snackbar("请输入有效的帧号", ft.Colors.RED)
            self.gif_frame_input.value = str(self.current_frame_index + 1)
            self.gif_frame_input.update()
    
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
                temp_path = self.config_service.get_temp_dir() / f"gif_frame_{self.current_frame_index}.png"
                frame_image.save(temp_path)
                self.original_image_widget.src = str(temp_path)
                
                # 清除预览（因为帧变了）
                self._clear_preview()
                
                # 更新界面
                self.gif_frame_input.update()
                self.original_image_widget.update()
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
        self.page.overlay.append(snackbar)
        snackbar.open = True
        try:
            self.page.update()
        except:
            pass

