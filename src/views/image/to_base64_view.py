# -*- coding: utf-8 -*-
"""图片转Base64视图模块。

提供图片转换为Base64编码的功能。
"""

import base64
from pathlib import Path
from typing import Callable, Optional

import flet as ft

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService


class ImageToBase64View(ft.Container):
    """图片转Base64视图类。
    
    提供图片转Base64编码的功能，包括：
    - 单图片选择和转换
    - 多种Base64格式输出
    - 一键复制到剪贴板
    - Data URI格式支持
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片转Base64视图。
        
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
        
        self.selected_file: Optional[Path] = None
        self.base64_result: str = ""
        
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
                ft.Text("图片转Base64", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_text = ft.Text(
            "未选择文件",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        select_button = ft.ElevatedButton(
            text="选择图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_file,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            select_button,
                            self.file_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    # 支持格式说明
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: JPG, PNG, WebP, GIF, BMP, TIFF, ICO 等",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=8),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 格式选择区域
        self.format_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="plain", label="纯Base64编码"),
                    ft.Radio(value="data_uri", label="Data URI格式 (data:image/...;base64,...)"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="plain",
        )
        
        format_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出格式", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.format_radio,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 转换按钮
        convert_button = ft.ElevatedButton(
            text="转换为Base64",
            icon=ft.Icons.TRANSFORM,
            on_click=self._on_convert,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE,
            ),
        )
        
        # 结果显示区域
        self.result_text = ft.TextField(
            label="Base64结果",
            multiline=True,
            min_lines=10,
            max_lines=20,
            read_only=True,
            value="",
        )
        
        copy_button = ft.ElevatedButton(
            text="复制到剪贴板",
            icon=ft.Icons.COPY,
            on_click=self._on_copy,
            visible=False,
        )
        
        self.copy_button = copy_button
        
        result_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("转换结果", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.result_text,
                    ft.Container(height=PADDING_SMALL),
                    copy_button,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                format_section,
                ft.Container(height=PADDING_MEDIUM),
                convert_button,
                ft.Container(height=PADDING_MEDIUM),
                result_section,
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
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_file_picked(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                file_path = Path(result.files[0].path)
                self.selected_file = file_path
                self.file_text.value = file_path.name
                self.file_text.update()
        
        file_picker = ft.FilePicker(on_result=on_file_picked)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp", "webp", "ico"],
            allow_multiple=False,
        )
    
    def _on_convert(self, e: ft.ControlEvent) -> None:
        """转换按钮点击事件。"""
        if not self.selected_file:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        if not self.selected_file.exists():
            self._show_message("文件不存在", ft.Colors.ERROR)
            return
        
        try:
            # 读取图片文件
            with open(self.selected_file, "rb") as f:
                image_data = f.read()
            
            # 转换为Base64
            base64_str = base64.b64encode(image_data).decode('utf-8')
            
            # 根据选择的格式输出
            if self.format_radio.value == "data_uri":
                # 获取MIME类型
                mime_type = self._get_mime_type(self.selected_file)
                self.base64_result = f"data:{mime_type};base64,{base64_str}"
            else:
                self.base64_result = base64_str
            
            # 显示结果
            self.result_text.value = self.base64_result
            self.result_text.update()
            
            # 显示复制按钮
            self.copy_button.visible = True
            self.copy_button.update()
            
            self._show_message("转换成功！", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"转换失败: {str(ex)}", ft.Colors.ERROR)
    
    def _get_mime_type(self, file_path: Path) -> str:
        """获取文件的MIME类型。
        
        Args:
            file_path: 文件路径
            
        Returns:
            MIME类型字符串
        """
        ext = file_path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".ico": "image/x-icon",
        }
        return mime_map.get(ext, "image/jpeg")
    
    def _on_copy(self, e: ft.ControlEvent) -> None:
        """复制到剪贴板按钮点击事件。"""
        if self.base64_result:
            self.page.set_clipboard(self.base64_result)
            self._show_message("已复制到剪贴板", ft.Colors.GREEN)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
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

