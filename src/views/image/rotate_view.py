# -*- coding: utf-8 -*-
"""图片旋转/翻转视图模块。

提供图片旋转和翻转功能。
"""

from pathlib import Path
from typing import Callable, List, Optional

import flet as ft
from PIL import Image

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService


class ImageRotateView(ft.Container):
    """图片旋转/翻转视图类。
    
    提供图片旋转和翻转功能，包括：
    - 90°/180°/270°旋转
    - 自定义角度旋转（0-360°）
    - 水平/垂直翻转
    - 自定义填充颜色
    - 实时预览效果
    - 批量处理
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片旋转/翻转视图。
        
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
        self.expand: bool = True
        
        self.selected_files: List[Path] = []
        self.current_operation: str = "rotate_90"  # 当前操作
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题栏
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("图片旋转/翻转", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_text = ft.Text(
            "未选择文件",
            size=14,
            color=TEXT_SECONDARY,
        )
        
        select_button = ft.ElevatedButton(
            text="选择图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_files,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            select_button,
                            self.file_list_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 操作选择区域
        self.operation_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Radio(value="rotate_90", label="顺时针旋转90°"),
                            ft.Radio(value="rotate_180", label="旋转180°"),
                            ft.Radio(value="rotate_270", label="逆时针旋转90°"),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Row(
                        controls=[
                            ft.Radio(value="flip_horizontal", label="水平翻转"),
                            ft.Radio(value="flip_vertical", label="垂直翻转"),
                            ft.Radio(value="rotate_custom", label="自定义角度"),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            value="rotate_90",
            on_change=self._on_operation_change,
        )
        
        # 自定义角度设置（默认隐藏）
        self.custom_angle_field = ft.TextField(
            label="旋转角度（度）",
            hint_text="输入0-360的角度值，正值为逆时针",
            value="45",
            width=200,
        )
        
        self.fill_color_field = ft.TextField(
            label="填充颜色（RGB格式）",
            hint_text="例如: 255,255,255",
            value="255,255,255",
            width=200,
        )
        
        self.custom_angle_section = ft.Container(
            content=ft.Row(
                controls=[
                    self.custom_angle_field,
                    self.fill_color_field,
                ],
                spacing=PADDING_MEDIUM,
            ),
            visible=False,
        )
        
        operation_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择操作", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.operation_radio,
                    ft.Container(height=PADDING_SMALL),
                    self.custom_angle_section,
                    ft.Text(
                        "提示：自定义角度旋转时，空白区域将使用填充颜色",
                        size=12,
                        color=TEXT_SECONDARY,
                        visible=False,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        self.custom_angle_hint = operation_section.content.controls[-1]
        
        # 输出设置
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            width=200,
            options=[
                ft.dropdown.Option("same", "保持原格式"),
                ft.dropdown.Option("jpg", "JPEG"),
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("webp", "WebP"),
            ],
            value="same",
        )
        
        self.overwrite_checkbox = ft.Checkbox(
            label="覆盖原文件",
            value=False,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.output_format_dropdown,
                            self.overwrite_checkbox,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 预览区域
        self.preview_image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
            width=400,
            height=400,
        )
        
        preview_button = ft.OutlinedButton(
            text="预览效果",
            icon=ft.Icons.PREVIEW,
            on_click=self._on_preview,
        )
        
        self.preview_button = preview_button
        
        preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("预览", size=16, weight=ft.FontWeight.BOLD),
                            preview_button,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image,
                        alignment=ft.alignment.center,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_MEDIUM,
                    ),
                    ft.Text(
                        "提示：预览仅显示第一张图片的效果",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.preview_section = preview_section
        
        # 处理按钮
        process_button = ft.ElevatedButton(
            text="开始处理",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_process,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
            ),
        )
        
        # 进度显示
        self.progress_text = ft.Text(
            "",
            size=14,
            color=TEXT_SECONDARY,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            visible=False,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=PADDING_MEDIUM),
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                operation_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_MEDIUM),
                preview_section,
                ft.Container(height=PADDING_MEDIUM),
                process_button,
                ft.Container(height=PADDING_SMALL),
                self.progress_text,
                self.progress_bar,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_files_picked(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                self.selected_files = [Path(f.path) for f in result.files]
                count = len(self.selected_files)
                if count == 1:
                    self.file_list_text.value = self.selected_files[0].name
                else:
                    self.file_list_text.value = f"已选择 {count} 个文件"
                self.file_list_text.update()
        
        file_picker = ft.FilePicker(on_result=on_files_picked)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp", "webp"],
            allow_multiple=True,
        )
    
    def _on_operation_change(self, e: ft.ControlEvent) -> None:
        """操作选择改变事件。"""
        self.current_operation = e.control.value
        
        # 显示或隐藏自定义角度设置
        if self.current_operation == "rotate_custom":
            self.custom_angle_section.visible = True
            self.custom_angle_hint.visible = True
        else:
            self.custom_angle_section.visible = False
            self.custom_angle_hint.visible = False
        
        self.custom_angle_section.update()
        self.custom_angle_hint.update()
    
    def _on_preview(self, e: ft.ControlEvent) -> None:
        """预览按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        # 只预览第一张图片
        file_path = self.selected_files[0]
        
        if not file_path.exists():
            self._show_message("文件不存在", ft.Colors.ERROR)
            return
        
        try:
            # 读取图片
            img = Image.open(file_path)
            
            # 执行操作
            if self.current_operation == "rotate_90":
                preview_img = img.rotate(-90, expand=True)
            elif self.current_operation == "rotate_180":
                preview_img = img.rotate(180, expand=True)
            elif self.current_operation == "rotate_270":
                preview_img = img.rotate(90, expand=True)
            elif self.current_operation == "flip_horizontal":
                preview_img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif self.current_operation == "flip_vertical":
                preview_img = img.transpose(Image.FLIP_TOP_BOTTOM)
            elif self.current_operation == "rotate_custom":
                # 自定义角度旋转
                try:
                    angle = float(self.custom_angle_field.value)
                except:
                    angle = 0
                
                # 解析填充颜色
                try:
                    color_parts = [int(x.strip()) for x in self.fill_color_field.value.split(',')]
                    if len(color_parts) != 3:
                        raise ValueError("颜色格式错误")
                    fill_color = tuple(color_parts)
                except:
                    fill_color = (255, 255, 255)
                
                preview_img = img.rotate(angle, expand=True, fillcolor=fill_color)
            else:
                preview_img = img
            
            # 调整预览图片大小（最大400x400）
            preview_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # 转换为base64显示
            import io
            import base64
            buffer = io.BytesIO()
            preview_img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # 显示预览
            self.preview_image.src_base64 = img_base64
            self.preview_image.visible = True
            self.preview_section.visible = True
            self.preview_image.update()
            self.preview_section.update()
            
            self._show_message("预览生成成功", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"预览失败: {str(ex)}", ft.Colors.ERROR)
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_text.value = "准备处理..."
        self.progress_bar.value = 0
        self.page.update()
        
        try:
            success_count = 0
            total = len(self.selected_files)
            
            for idx, file_path in enumerate(self.selected_files):
                if not file_path.exists():
                    continue
                
                # 更新进度
                self.progress_text.value = f"正在处理: {file_path.name} ({idx + 1}/{total})"
                self.progress_bar.value = idx / total
                self.page.update()
                
                try:
                    # 读取图片
                    img = Image.open(file_path)
                    
                    # 执行操作
                    if self.current_operation == "rotate_90":
                        img = img.rotate(-90, expand=True)
                    elif self.current_operation == "rotate_180":
                        img = img.rotate(180, expand=True)
                    elif self.current_operation == "rotate_270":
                        img = img.rotate(90, expand=True)
                    elif self.current_operation == "flip_horizontal":
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    elif self.current_operation == "flip_vertical":
                        img = img.transpose(Image.FLIP_TOP_BOTTOM)
                    elif self.current_operation == "rotate_custom":
                        # 自定义角度旋转
                        try:
                            angle = float(self.custom_angle_field.value)
                        except:
                            angle = 0
                        
                        # 解析填充颜色
                        try:
                            color_parts = [int(x.strip()) for x in self.fill_color_field.value.split(',')]
                            if len(color_parts) != 3:
                                raise ValueError("颜色格式错误")
                            fill_color = tuple(color_parts)
                        except:
                            fill_color = (255, 255, 255)
                        
                        # 旋转图片
                        # expand=True 会自动扩展画布以容纳旋转后的图片
                        img = img.rotate(angle, expand=True, fillcolor=fill_color)
                    
                    # 确定输出路径和格式
                    if self.overwrite_checkbox.value:
                        output_path = file_path
                        output_format = file_path.suffix[1:].upper()
                    else:
                        # 确定输出格式
                        if self.output_format_dropdown.value == "same":
                            output_format = file_path.suffix[1:].upper()
                            ext = file_path.suffix
                        else:
                            output_format = self.output_format_dropdown.value.upper()
                            ext = f".{self.output_format_dropdown.value}"
                        
                        # 生成新文件名
                        output_path = file_path.parent / f"{file_path.stem}_rotated{ext}"
                        counter = 1
                        while output_path.exists():
                            output_path = file_path.parent / f"{file_path.stem}_rotated_{counter}{ext}"
                            counter += 1
                    
                    # 处理JPEG格式的RGBA图片
                    if output_format == "JPEG" or output_format == "JPG":
                        if img.mode in ("RGBA", "LA", "P"):
                            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == "P":
                                img = img.convert("RGBA")
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                            img = rgb_img
                        output_format = "JPEG"
                    
                    # 保存
                    img.save(output_path, format=output_format)
                    success_count += 1
                
                except Exception as ex:
                    print(f"处理文件 {file_path.name} 失败: {str(ex)}")
                    continue
            
            # 完成进度显示
            self.progress_text.value = "处理完成！"
            self.progress_bar.value = 1.0
            self.page.update()
            
            # 延迟隐藏进度条，让用户看到完成状态
            import time
            time.sleep(0.5)
            
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            
            self._show_message(f"处理完成！成功处理 {success_count}/{total} 个文件", ft.Colors.GREEN)
        
        except Exception as ex:
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            self._show_message(f"处理失败: {str(ex)}", ft.Colors.ERROR)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
        )
        self.page.snack_bar.open = True
        self.page.update()

