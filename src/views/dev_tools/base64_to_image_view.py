# -*- coding: utf-8 -*-
"""Base64转图片视图模块。

提供Base64编码转换为图片的功能。
"""

import base64
import re
from pathlib import Path
from typing import Callable, Optional

import flet as ft

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService


class Base64ToImageView(ft.Container):
    """Base64转图片视图类。
    
    提供Base64编码转图片的功能，包括：
    - 支持纯Base64和Data URI格式
    - 自动识别图片格式（PNG/JPEG/GIF/BMP/WebP等）
    - 显示图片尺寸和文件大小信息
    - 保存为多种图片格式
    - 实时预览
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化Base64转图片视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.on_back: Optional[Callable] = on_back
        self.expand: bool = True
        
        self.image_data: Optional[bytes] = None
        self.image_format: str = "png"
        
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
                ft.Text("Base64转图片", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # Base64输入区域
        self.base64_input = ft.TextField(
            label="Base64编码",
            hint_text="粘贴Base64编码或Data URI格式 (data:image/...;base64,...)",
            multiline=True,
            min_lines=8,
            max_lines=15,
            value="",
        )
        
        input_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输入Base64编码", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.base64_input,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text(
                        "支持纯Base64编码和Data URI格式，自动识别图片格式",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 解码和预览按钮
        decode_button = ft.ElevatedButton(
            text="解码并预览",
            icon=ft.Icons.PREVIEW,
            on_click=self._on_decode,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
            ),
        )
        
        # 预览区域
        self.preview_image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
            width=400,
            height=400,
        )
        
        self.preview_info = ft.Text(
            "",
            size=12,
            color=TEXT_SECONDARY,
            visible=False,
        )
        
        preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("图片预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image,
                        alignment=ft.alignment.center,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_LARGE,
                    ),
                    self.preview_info,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.preview_section = preview_section
        
        # 保存区域
        self.format_dropdown = ft.Dropdown(
            label="保存格式",
            width=200,
            options=[
                ft.dropdown.Option("png", "PNG"),
                ft.dropdown.Option("jpg", "JPEG"),
                ft.dropdown.Option("gif", "GIF"),
                ft.dropdown.Option("bmp", "BMP"),
                ft.dropdown.Option("webp", "WebP"),
            ],
            value="png",
        )
        
        save_button = ft.ElevatedButton(
            text="保存图片",
            icon=ft.Icons.SAVE,
            on_click=self._on_save,
            visible=False,
        )
        
        self.save_button = save_button
        
        save_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("保存图片", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.format_dropdown,
                            save_button,
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
            visible=False,
        )
        
        self.save_section = save_section
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                input_section,
                ft.Container(height=PADDING_MEDIUM),
                decode_button,
                ft.Container(height=PADDING_MEDIUM),
                preview_section,
                ft.Container(height=PADDING_MEDIUM),
                save_section,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装视图 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
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
    
    def _on_decode(self, e: ft.ControlEvent) -> None:
        """解码按钮点击事件。"""
        base64_str = self.base64_input.value.strip()
        
        if not base64_str:
            self._show_message("请输入Base64编码", ft.Colors.ERROR)
            return
        
        try:
            # 检查是否是Data URI格式
            data_uri_pattern = r'^data:image/(\w+);base64,(.+)$'
            match = re.match(data_uri_pattern, base64_str, re.DOTALL)
            
            if match:
                # Data URI格式，提取Base64数据
                base64_data = match.group(2)
            else:
                # 纯Base64格式
                base64_data = base64_str
            
            # 解码Base64
            self.image_data = base64.b64decode(base64_data)
            
            # 使用PIL自动识别图片格式
            from PIL import Image
            import io
            
            img = Image.open(io.BytesIO(self.image_data))
            detected_format = img.format.lower() if img.format else "png"
            
            # 标准化格式名称
            format_map = {
                "jpeg": "jpg",
            }
            self.image_format = format_map.get(detected_format, detected_format)
            
            # 获取图片尺寸
            width, height = img.size
            
            # 显示预览
            self.preview_image.src_base64 = base64.b64encode(self.image_data).decode('utf-8')
            self.preview_image.visible = True
            self.preview_image.update()
            
            # 显示信息
            size_kb = len(self.image_data) / 1024
            self.preview_info.value = (
                f"图片大小: {size_kb:.2f} KB | "
                f"格式: {self.image_format.upper()} | "
                f"尺寸: {width}×{height} px"
            )
            self.preview_info.visible = True
            self.preview_info.update()
            
            # 显示预览和保存区域
            self.preview_section.visible = True
            self.preview_section.update()
            
            self.save_section.visible = True
            self.save_button.visible = True
            self.save_section.update()
            
            # 设置默认保存格式为检测到的格式
            if self.image_format in ["jpg", "jpeg"]:
                self.format_dropdown.value = "jpg"
            elif self.image_format in ["png", "gif", "bmp", "webp"]:
                self.format_dropdown.value = self.image_format
            else:
                # 如果是不支持的格式，默认为PNG
                self.format_dropdown.value = "png"
            self.format_dropdown.update()
            
            self._show_message(f"解码成功！检测到格式: {self.image_format.upper()}", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"解码失败: {str(ex)}", ft.Colors.ERROR)
            # 隐藏预览和保存区域
            self.preview_section.visible = False
            self.save_section.visible = False
            self.preview_section.update()
            self.save_section.update()
    
    def _on_save(self, e: ft.ControlEvent) -> None:
        """保存按钮点击事件。"""
        if not self.image_data:
            self._show_message("请先解码Base64", ft.Colors.ERROR)
            return
        
        def on_save_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                try:
                    save_path = Path(result.path)
                    
                    # 如果需要转换格式
                    selected_format = self.format_dropdown.value
                    if selected_format != self.image_format:
                        # 需要用PIL转换格式
                        from PIL import Image
                        import io
                        
                        img = Image.open(io.BytesIO(self.image_data))
                        
                        # 如果是JPEG，需要转换RGBA为RGB
                        if selected_format == "jpg" and img.mode in ("RGBA", "LA", "P"):
                            rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                            if img.mode == "P":
                                img = img.convert("RGBA")
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                            img = rgb_img
                        
                        # 保存转换后的图片
                        img.save(save_path, format=selected_format.upper())
                    else:
                        # 直接保存原始数据
                        with open(save_path, "wb") as f:
                            f.write(self.image_data)
                    
                    self._show_message(f"图片已保存到: {save_path}", ft.Colors.GREEN)
                
                except Exception as ex:
                    self._show_message(f"保存失败: {str(ex)}", ft.Colors.ERROR)
        
        save_picker = ft.FilePicker(on_result=on_save_result)
        self.page.overlay.append(save_picker)
        self.page.update()
        
        # 获取默认文件名和扩展名
        format_ext = self.format_dropdown.value
        default_name = f"image.{format_ext}"
        
        save_picker.save_file(
            dialog_title="保存图片",
            file_name=default_name,
            allowed_extensions=[format_ext],
        )
    
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

