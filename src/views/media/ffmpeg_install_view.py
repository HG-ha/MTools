# -*- coding: utf-8 -*-
"""FFmpeg安装提示视图模块。

为音频/视频处理工具提供统一的FFmpeg安装提示界面。
"""

import asyncio
import threading
from pathlib import Path
from typing import Callable, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import FFmpegService


class FFmpegInstallView(ft.Container):
    """FFmpeg安装提示视图类。
    
    为需要FFmpeg的工具提供统一的安装提示和自动安装界面。
    """

    def __init__(
        self,
        page: ft.Page,
        ffmpeg_service: FFmpegService,
        on_installed: Optional[Callable] = None,
        on_back: Optional[Callable] = None,
        tool_name: str = "此工具"
    ) -> None:
        """初始化FFmpeg安装提示视图。
        
        Args:
            page: Flet页面对象
            ffmpeg_service: FFmpeg服务实例
            on_installed: 安装成功后的回调函数
            on_back: 返回按钮回调函数
            tool_name: 工具名称（用于提示信息）
        """
        super().__init__()
        self._page: ft.Page = page
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_installed: Optional[Callable] = on_installed
        self.on_back: Optional[Callable] = on_back
        self.tool_name: str = tool_name
        
        self.expand: bool = True
        # 设置 padding，由视图自己管理间距
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
        # 顶部：标题和返回按钮（与 VideoCompressView 保持一致）
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ) if self.on_back else None,
                ft.Text("FFmpeg 安装", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        # 过滤掉 None 值
        header.controls = [c for c in header.controls if c is not None]
        
        # 下载进度控件
        self.download_progress_bar = ft.ProgressBar(value=0, visible=False, width=400)
        self.download_progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        # 自动安装按钮
        self.auto_install_button = ft.ElevatedButton(
            "自动安装 FFmpeg",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_auto_install_ffmpeg,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.WHITE,
            ),
        )
        
        # 手动安装按钮
        manual_install_button = ft.TextButton(
            "查看手动安装教程",
            icon=ft.Icons.OPEN_IN_BROWSER,
            on_click=lambda e: self._open_ffmpeg_guide(),
        )
        
        # 主要内容区域（居中显示）
        main_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, size=64, color=ft.Colors.ORANGE),
                    ft.Text("FFmpeg 未安装", size=24, weight=ft.FontWeight.BOLD, ),
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text(
                        f"{self.tool_name}需要 FFmpeg 支持",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "点击下方按钮自动下载并安装到软件目录（约100MB）",
                        size=13,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=PADDING_LARGE),
                    self.auto_install_button,
                    manual_install_button,
                    ft.Container(height=PADDING_MEDIUM),
                    self.download_progress_bar,
                    self.download_progress_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            expand=True,
            alignment=ft.Alignment.CENTER,
        )
        
        # 组装视图（与 VideoCompressView 结构一致）
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                main_content,
            ],
            spacing=0,
            expand=True,
        )
    
    def _open_ffmpeg_guide(self) -> None:
        """打开FFmpeg安装教程。"""
        import webbrowser
        webbrowser.open("https://ffmpeg.org/download.html")
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.on_back:
            self.on_back(e)
    
    def _on_auto_install_ffmpeg(self, e: ft.ControlEvent) -> None:
        """自动安装FFmpeg按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        # 禁用安装按钮
        self.auto_install_button.disabled = True
        self.download_progress_bar.visible = True
        self.download_progress_text.visible = True
        self.download_progress_bar.value = 0
        self.download_progress_text.value = "准备下载..."
        
        try:
            self._page.update()
        except Exception:
            pass
        
        # 启动异步下载任务
        self._page.run_task(self._download_ffmpeg_async)
    
    async def _download_ffmpeg_async(self) -> None:
        """异步下载FFmpeg（轮询模式）。"""
        self._download_progress = 0.0
        self._download_status = "准备下载..."
        self._download_done = False
        self._download_result = None
        
        def progress_callback(progress: float, message: str) -> None:
            self._download_progress = progress
            self._download_status = message
        
        def do_download():
            result = self.ffmpeg_service.download_ffmpeg(progress_callback)
            self._download_result = result
            self._download_done = True
        
        # 在后台线程执行下载
        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()
        
        # 轮询进度更新UI
        while not self._download_done:
            self.download_progress_bar.value = self._download_progress
            self.download_progress_text.value = self._download_status
            try:
                self._page.update()
            except Exception:
                pass
            await asyncio.sleep(0.1)
        
        # 下载完成
        success, message = self._download_result
        
        if success:
            self.download_progress_text.value = "✓ " + message
            self._show_snackbar("FFmpeg 安装成功！", ft.Colors.GREEN)
            
            await asyncio.sleep(1)
            
            if self.on_installed:
                self.on_installed()
        else:
            self.download_progress_text.value = "✗ " + message
            self.auto_install_button.disabled = False
            self._show_snackbar(f"安装失败: {message}", ft.Colors.RED)
            
            try:
                self._page.update()
            except Exception:
                pass
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self._page.open(snackbar)

