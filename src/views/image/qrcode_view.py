# -*- coding: utf-8 -*-
"""二维码生成视图模块。

提供二维码生成功能，支持普通二维码、艺术二维码和动态 GIF 二维码。
"""

import base64
import io
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import flet as ft
from amzqr import amzqr
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


class QRCodeGeneratorView(ft.Container):
    """二维码生成视图类。
    
    提供二维码生成功能，包括：
    - 文本/网址转二维码
    - 艺术二维码（带背景图片）
    - 彩色二维码
    - 动态 GIF 二维码
    - 自定义对比度和亮度
    - 实时预览
    - 保存为图片
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化二维码生成视图。
        
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
        
        self.qr_image_path: Optional[Path] = None
        self.background_image_path: Optional[Path] = None
        
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
                ft.Text("二维码生成器", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 内容输入区域
        self.content_input = ft.TextField(
            label="输入内容",
            hint_text="输入文本、网址等内容",
            multiline=True,
            min_lines=3,
            max_lines=8,
            value="",
        )
        
        # 常用模板按钮
        template_buttons = ft.Row(
            controls=[
                ft.TextButton(
                    text="网址",
                    on_click=lambda e: self._set_template("https://"),
                ),
                ft.TextButton(
                    text="WiFi",
                    on_click=lambda e: self._set_template("WIFI:T:WPA;S:网络名称;P:密码;;"),
                ),
                ft.TextButton(
                    text="电话",
                    on_click=lambda e: self._set_template("tel:"),
                ),
                ft.TextButton(
                    text="邮箱",
                    on_click=lambda e: self._set_template("mailto:"),
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        input_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("二维码内容", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.content_input,
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("快速模板：", size=12, color=TEXT_SECONDARY),
                    template_buttons,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 基础设置
        self.version_slider = ft.Slider(
            min=1,
            max=40,
            divisions=39,
            value=1,
            label="{value}",
        )
        
        self.error_correction_dropdown = ft.Dropdown(
            label="纠错等级",
            width=150,
            options=[
                ft.dropdown.Option("L", "低 (7%)"),
                ft.dropdown.Option("M", "中 (15%)"),
                ft.dropdown.Option("Q", "高 (25%)"),
                ft.dropdown.Option("H", "最高 (30%)"),
            ],
            value="H",
        )
        
        basic_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("基础设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("版本大小 (1-40)", size=12),
                                    self.version_slider,
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            self.error_correction_dropdown,
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
        
        # 艺术二维码设置
        self.selected_image_text = ft.Text(
            "未选择图片",
            size=12,
            color=TEXT_SECONDARY,
        )
        
        select_image_button = ft.ElevatedButton(
            text="选择背景图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_image,
        )
        
        clear_image_button = ft.TextButton(
            text="清除",
            on_click=self._on_clear_image,
        )
        
        self.colorized_checkbox = ft.Checkbox(
            label="彩色二维码",
            value=False,
        )
        
        self.contrast_slider = ft.Slider(
            min=0.5,
            max=2.0,
            divisions=30,
            value=1.0,
            label="{value}",
        )
        
        self.brightness_slider = ft.Slider(
            min=0.5,
            max=2.0,
            divisions=30,
            value=1.0,
            label="{value}",
        )
        
        artistic_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("艺术二维码设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("背景图片（可选，支持 GIF 动态图）", size=12, color=TEXT_SECONDARY),
                    ft.Row(
                        controls=[
                            select_image_button,
                            clear_image_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    self.selected_image_text,
                    ft.Container(height=PADDING_SMALL),
                    self.colorized_checkbox,
                    ft.Container(height=PADDING_SMALL),
                    ft.Column(
                        controls=[
                            ft.Text("对比度", size=12),
                            self.contrast_slider,
                        ],
                        spacing=0,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("亮度", size=12),
                            self.brightness_slider,
                        ],
                        spacing=0,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 生成按钮和进度
        generate_button = ft.ElevatedButton(
            text="生成二维码",
            icon=ft.Icons.QR_CODE_2,
            on_click=self._on_generate,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
            ),
        )
        
        self.progress_bar = ft.ProgressBar(visible=False, value=0)
        self.progress_text = ft.Text("", size=12, color=TEXT_SECONDARY, visible=False)
        
        # 预览区域
        self.preview_image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
            width=400,
            height=400,
        )
        
        save_button = ft.ElevatedButton(
            text="保存图片",
            icon=ft.Icons.SAVE,
            on_click=self._on_save,
            visible=False,
        )
        
        self.save_button = save_button
        
        preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image,
                        alignment=ft.alignment.center,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_LARGE,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    save_button,
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.preview_section = preview_section
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Container(height=PADDING_MEDIUM),
                input_section,
                ft.Container(height=PADDING_MEDIUM),
                basic_section,
                ft.Container(height=PADDING_MEDIUM),
                artistic_section,
                ft.Container(height=PADDING_MEDIUM),
                generate_button,
                ft.Container(height=PADDING_SMALL),
                self.progress_bar,
                self.progress_text,
                ft.Container(height=PADDING_MEDIUM),
                preview_section,
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
    
    def _set_template(self, template: str) -> None:
        """设置快速模板。"""
        self.content_input.value = template
        self.content_input.update()
    
    def _on_select_image(self, e: ft.ControlEvent) -> None:
        """选择背景图片。"""
        def on_select_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                file_path = Path(result.files[0].path)
                self.background_image_path = file_path
                self.selected_image_text.value = f"已选择: {file_path.name}"
                self.selected_image_text.update()
        
        file_picker = ft.FilePicker(on_result=on_select_result)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="选择背景图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "gif"],
            allow_multiple=False,
        )
    
    def _on_clear_image(self, e: ft.ControlEvent) -> None:
        """清除背景图片。"""
        self.background_image_path = None
        self.selected_image_text.value = "未选择图片"
        self.selected_image_text.update()
    
    def _on_generate(self, e: ft.ControlEvent) -> None:
        """生成按钮点击事件。"""
        content = self.content_input.value.strip()
        
        if not content:
            self._show_message("请输入内容", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_text.value = "正在生成二维码..."
        self.progress_bar.value = None  # 不确定进度
        self.page.update()
        
        # 后台生成
        def generate_task():
            try:
                # 创建临时目录
                temp_dir = tempfile.mkdtemp()
                
                # 准备参数
                version = int(self.version_slider.value)
                level = self.error_correction_dropdown.value
                picture = str(self.background_image_path) if self.background_image_path else None
                colorized = self.colorized_checkbox.value
                contrast = self.contrast_slider.value
                brightness = self.brightness_slider.value
                
                # 确定输出文件名
                if picture and picture.lower().endswith('.gif'):
                    save_name = "qrcode.gif"
                else:
                    save_name = "qrcode.png"
                
                # 调用 amzqr 生成
                version_result, level_result, qr_name = amzqr.run(
                    words=content,
                    version=version,
                    level=level,
                    picture=picture,
                    colorized=colorized,
                    contrast=contrast,
                    brightness=brightness,
                    save_name=save_name,
                    save_dir=temp_dir,
                )
                
                self.qr_image_path = Path(temp_dir) / save_name
                
                # 更新UI
                self.page.run_task(self._update_preview)
                
            except Exception as ex:
                self.page.run_task(self._show_error, str(ex))
        
        thread = threading.Thread(target=generate_task, daemon=True)
        thread.start()
    
    def _update_preview(self) -> None:
        """更新预览（在主线程中调用）。"""
        try:
            if not self.qr_image_path or not self.qr_image_path.exists():
                self._show_message("生成失败：找不到输出文件", ft.Colors.ERROR)
                return
            
            # 读取生成的二维码
            with open(self.qr_image_path, "rb") as f:
                img_data = f.read()
            
            # 转换为base64显示
            img_base64 = base64.b64encode(img_data).decode()
            
            # 显示预览
            self.preview_image.src_base64 = img_base64
            self.preview_image.visible = True
            self.preview_image.update()
            
            # 显示保存按钮和预览区域
            self.preview_section.visible = True
            self.save_button.visible = True
            self.preview_section.update()
            
            # 隐藏进度
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self.page.update()
            
            self._show_message("二维码生成成功！", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"预览失败: {str(ex)}", ft.Colors.ERROR)
            # 隐藏进度
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self.page.update()
    
    def _show_error(self, error_msg: str) -> None:
        """显示错误（在主线程中调用）。"""
        self._show_message(f"生成失败: {error_msg}", ft.Colors.ERROR)
        # 隐藏进度
        self.progress_bar.visible = False
        self.progress_text.visible = False
        self.page.update()
    
    def _on_save(self, e: ft.ControlEvent) -> None:
        """保存按钮点击事件。"""
        if not self.qr_image_path or not self.qr_image_path.exists():
            self._show_message("请先生成二维码", ft.Colors.ERROR)
            return
        
        def on_save_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                try:
                    save_path = Path(result.path)
                    
                    # 复制文件
                    with open(self.qr_image_path, "rb") as src:
                        with open(save_path, "wb") as dst:
                            dst.write(src.read())
                    
                    self._show_message(f"二维码已保存到: {save_path}", ft.Colors.GREEN)
                except Exception as ex:
                    self._show_message(f"保存失败: {str(ex)}", ft.Colors.ERROR)
        
        save_picker = ft.FilePicker(on_result=on_save_result)
        self.page.overlay.append(save_picker)
        self.page.update()
        
        # 根据原文件类型确定保存格式
        if self.qr_image_path.suffix.lower() == '.gif':
            save_picker.save_file(
                dialog_title="保存二维码",
                file_name="qrcode.gif",
                allowed_extensions=["gif"],
            )
        else:
            save_picker.save_file(
                dialog_title="保存二维码",
                file_name="qrcode.png",
                allowed_extensions=["png", "jpg", "jpeg"],
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
