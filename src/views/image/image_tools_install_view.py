# -*- coding: utf-8 -*-
"""图片压缩工具安装视图模块。

提供mozjpeg和pngquant工具的自动下载和安装。
"""

from typing import Optional
import asyncio
import threading

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ImageService


class ImageToolsInstallView(ft.Container):
    """图片压缩工具安装视图类。
    
    提供压缩工具的自动下载和安装，包括：
    - mozjpeg 自动下载安装
    - pngquant 自动下载安装
    - 安装进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        image_service: ImageService,
        on_back: Optional[callable] = None,
        on_installed: Optional[callable] = None,
    ) -> None:
        """初始化工具安装视图。
        
        Args:
            page: Flet页面对象
            image_service: 图片服务实例
            on_back: 返回回调
            on_installed: 安装完成回调
        """
        super().__init__()
        self._page: ft.Page = page
        self.image_service: ImageService = image_service
        self.on_back: Optional[callable] = on_back
        self.on_installed: Optional[callable] = on_installed
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.all(PADDING_LARGE)
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题
        title_row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda e: self.on_back(e) if self.on_back else None,
                ),
                ft.Icon(ft.Icons.DOWNLOAD, size=32, color=ft.Colors.BLUE),
                ft.Text("安装图片压缩工具", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 说明文本
        description = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "标准模式需要安装专业的图片压缩工具以获得更好的压缩效果：",
                        size=16,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=20, color=ft.Colors.AMBER),
                            ft.Text("mozjpeg - 高效的JPEG压缩工具（约 5MB）", size=14),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=20, color=ft.Colors.GREEN),
                            ft.Text("pngquant - 高效的PNG压缩工具（约 300KB）", size=14),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text(
                        "点击下方「开始安装」按钮，软件将自动下载并安装这些工具。",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
        )
        
        # 进度条
        self.progress_bar = ft.ProgressBar(
            width=600,
            visible=False,
        )
        
        # 状态文本
        self.status_text = ft.Text(
            "",
            size=14,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )
        
        # 按钮
        self.install_button = ft.ElevatedButton(
            "开始安装",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_install_click,
        )
        
        self.back_button = ft.TextButton(
            "返回",
            on_click=lambda e: self.on_back(e) if self.on_back else None,
        )
        
        buttons_row = ft.Row(
            controls=[
                self.install_button,
                self.back_button,
            ],
            spacing=PADDING_MEDIUM,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # 提示信息
        tips = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ft.Colors.BLUE),
                            ft.Text("提示：", size=14, weight=ft.FontWeight.W_600),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Text(
                        "• 安装过程需要联网下载，请确保网络连接正常",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "• 下载速度取决于您的网络环境",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "• 安装完成后，这些工具将被保存到数据存储目录的 tools 文件夹",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "• 您可以在设置中查看和修改数据存储目录",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )
        
        # 组装内容
        content = ft.Column(
            controls=[
                title_row,
                ft.Divider(),
                description,
                ft.Container(height=PADDING_LARGE),
                self.progress_bar,
                self.status_text,
                ft.Container(height=PADDING_MEDIUM),
                buttons_row,
                ft.Container(height=PADDING_LARGE),
                tips,
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        self.content = content
    
    def _on_install_click(self, e) -> None:
        """点击安装按钮。"""
        # 禁用安装按钮
        self.install_button.disabled = True
        
        # 显示进度条
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        
        self.status_text.visible = True
        self.status_text.value = "准备下载..."
        self._page.update()
        
        # 启动异步下载任务
        self._page.run_task(self._download_and_install_async)
    
    async def _download_and_install_async(self) -> None:
        """异步下载并安装工具（轮询模式）。"""
        self._download_progress = 0.0
        self._download_status = "准备下载..."
        self._download_done = False
        self._download_result = None
        
        def progress_callback(progress: float, status: str) -> None:
            self._download_progress = progress
            self._download_status = status
        
        def do_download():
            result = self.image_service.download_and_install_tools(
                progress_callback=progress_callback
            )
            self._download_result = result
            self._download_done = True
        
        # 在后台线程执行下载
        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()
        
        # 轮询进度更新UI
        while not self._download_done:
            self.progress_bar.value = self._download_progress
            self.status_text.value = self._download_status
            self._page.update()
            await asyncio.sleep(0.1)
        
        # 下载完成
        self.progress_bar.visible = False
        success, message = self._download_result
        
        if success:
            self.status_text.value = "✅ " + message
            self.status_text.color = ft.Colors.GREEN
            self._page.update()
            
            await asyncio.sleep(1)
            
            if self.on_installed:
                self.on_installed()
        else:
            self.status_text.value = "❌ " + message
            self.status_text.color = ft.Colors.RED
            self.install_button.disabled = False
            self._page.update()
