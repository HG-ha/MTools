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
from utils import format_file_size


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
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE + 16,
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
        self.file_info_text: ft.Text = ft.Text(
            "还没有选择文件",
            size=13,
            color=TEXT_SECONDARY,
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
                                content=self.file_info_text,
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
                ft.ElevatedButton(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PREVIEW, size=20),
                            ft.Text("生成预览", size=14),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    on_click=self._on_generate_preview,
                ),
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
            content=options_area,
            padding=PADDING_MEDIUM,
        )
        
        # 底部：保存按钮
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
            height=48,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=PADDING_LARGE),
                top_row,
                ft.Container(height=PADDING_LARGE),
                bottom_content,
                ft.Container(height=PADDING_MEDIUM),
                self.save_button,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
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
            self.file_info_text.value = "还没有选择文件"
            self.file_info_text.visible = True
            self.original_image_widget.visible = False
        else:
            file_info = self.image_service.get_image_info(self.selected_file)
            
            if 'error' in file_info:
                self.file_info_text.value = f"错误: {file_info['error']}"
                self.file_info_text.visible = True
                self.original_image_widget.visible = False
            else:
                # 显示原图预览
                try:
                    self.original_image_widget.src = self.selected_file
                    self.original_image_widget.visible = True
                    self.file_info_text.visible = False
                except Exception as e:
                    self.file_info_text.value = f"无法加载图片: {e}"
                    self.file_info_text.visible = True
                    self.original_image_widget.visible = False
        
        try:
            self.file_info_text.update()
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
                # 读取图片
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
                    alpha = bg_img.split()[3]
                    alpha = alpha.point(lambda p: int(p * bg_opacity / 255))
                    bg_img.putalpha(alpha)
                
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
        
        # 生成默认文件名：原文件名_split.png
        default_filename = "split_result.png"
        if self.selected_file:
            original_stem = self.selected_file.stem  # 获取不含扩展名的文件名
            default_filename = f"{original_stem}_split.png"
        
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                try:
                    output_path = Path(result.path)
                    
                    # 确保有扩展名
                    if not output_path.suffix:
                        output_path = output_path.with_suffix('.png')
                    
                    # 保存图片
                    self.preview_image.save(output_path, quality=95, optimize=True)
                    self._show_snackbar(f"保存成功: {output_path.name}", ft.Colors.GREEN)
                except Exception as ex:
                    self._show_snackbar(f"保存失败: {ex}", ft.Colors.RED)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.save_file(
            dialog_title="保存切分结果",
            file_name=default_filename,
            allowed_extensions=["png", "jpg", "jpeg"],
        )
    
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

