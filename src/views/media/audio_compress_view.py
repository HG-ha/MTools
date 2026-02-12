# -*- coding: utf-8 -*-
"""音频压缩视图模块。

提供音频压缩功能的用户界面。
"""

import re
import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, FFmpegService
from utils import format_file_size, logger, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class AudioCompressView(ft.Container):
    """音频压缩视图类。
    
    提供音频压缩功能，包括："""
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.ape', '.opus'}
    
    """
    - 单文件和批量压缩
    - 比特率调整
    - 采样率调整
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化音频压缩视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        
        self.expand: bool = True
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
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self._page,
                self.ffmpeg_service,
                on_back=self._on_back_click
            )
            return

        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("音频压缩", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 初始化空状态
        self._init_empty_state()
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择音频:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_files,
                        ),
                        ft.Button(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self._on_select_folder,
                        ),
                        ft.Button(
                            "清空",
                            icon=ft.Icons.CLEAR,
                            on_click=lambda _: self._clear_files(),
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
                ft.Container(
                    content=self.file_list_view,
                    height=250,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 压缩设置区域
        # 比特率设置
        self.bitrate_value_text = ft.Text(
            "128 kbps",
            size=13,
            text_align=ft.TextAlign.END,
            width=80,
        )
        
        self.bitrate_slider = ft.Slider(
            min=32,
            max=320,
            value=128,
            divisions=9,
            label="{value} kbps",
            on_change=self._on_bitrate_change,
        )
        
        bitrate_row = ft.Row(
            controls=[
                ft.Text("比特率", size=13),
                self.bitrate_value_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # 采样率设置
        self.sample_rate_dropdown = ft.Dropdown(
            width=200,
            value="44100",
            options=[
                ft.dropdown.Option("8000", "8 kHz"),
                ft.dropdown.Option("11025", "11.025 kHz"),
                ft.dropdown.Option("16000", "16 kHz"),
                ft.dropdown.Option("22050", "22.05 kHz"),
                ft.dropdown.Option("44100", "44.1 kHz (CD质量)"),
                ft.dropdown.Option("48000", "48 kHz"),
                ft.dropdown.Option("96000", "96 kHz (高品质)"),
                ft.dropdown.Option("original", "保持原始"),
            ],
            dense=True,
        )
        
        sample_rate_row = ft.Row(
            controls=[
                ft.Text("采样率:", size=13),
                self.sample_rate_dropdown,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 声道设置
        self.channel_dropdown = ft.Dropdown(
            width=200,
            value="original",
            options=[
                ft.dropdown.Option("1", "单声道 (Mono)"),
                ft.dropdown.Option("2", "立体声 (Stereo)"),
                ft.dropdown.Option("original", "保持原始"),
            ],
            dense=True,
        )
        
        channel_row = ft.Row(
            controls=[
                ft.Text("声道:", size=13),
                self.channel_dropdown,
            ],
            spacing=PADDING_SMALL,
        )
        
        compress_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("压缩设置", size=16, weight=ft.FontWeight.W_600),
                    ft.Container(height=PADDING_SMALL),
                    bitrate_row,
                    self.bitrate_slider,
                    ft.Container(height=PADDING_SMALL),
                    sample_rate_row,
                    ft.Container(height=PADDING_SMALL),
                    channel_row,
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出设置
        self.output_dir_field = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            read_only=True,
            expand=True,
            dense=True,
            disabled=True,
        )
        
        self.output_dir_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="选择输出目录",
            on_click=self._select_output_dir,
            disabled=True,
        )
        
        self.output_mode = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="same_dir",
                        label="保存为新文件（原文件旁）",
                        fill_color=ft.Colors.PRIMARY,
                    ),
                    ft.Radio(
                        value="custom_dir",
                        label="自定义输出目录",
                        fill_color=ft.Colors.PRIMARY,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            value="same_dir",
            on_change=self._on_output_mode_change,
        )
        
        output_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.W_600),
                    ft.Container(height=PADDING_SMALL),
                    self.output_mode,
                    ft.Row(
                        controls=[
                            self.output_dir_field,
                            self.output_dir_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(
            value=0,
            visible=False,
            bar_height=8,
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        self.progress_text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        progress_area = ft.Column(
            controls=[
                self.progress_bar,
                self.progress_text,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 操作按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPRESS, size=24),
                        ft.Text("开始压缩", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=lambda _: self._on_process(),
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                compress_settings,
                ft.Container(height=PADDING_MEDIUM),
                output_settings,
                ft.Container(height=PADDING_MEDIUM),
                progress_area,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=0,
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条，但仍可滚动
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,  # 取消间距，让布局更紧凑
        )
    
    def _init_empty_state(self) -> None:
        """初始化空状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.MUSIC_NOTE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加音频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=250,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
                tooltip="点击选择音频文件",
            )
        )
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """空白区域点击事件处理。"""
        await self._on_select_files(e)

    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件。"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["mp3", "wav", "aac", "flac", "ogg", "m4a", "wma", "opus"],
            dialog_title="选择音频文件",
            allow_multiple=True,
        )
        if result:
            for file in result:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择音频文件夹")
        if folder_path:
            folder = Path(folder_path)
            audio_extensions = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"}
            for file_path in folder.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self._init_empty_state()
            self.process_button.content.disabled = True
        else:
            for file_path in self.selected_files:
                file_size = format_file_size(file_path.stat().st_size)
                
                file_item = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MUSIC_NOTE, size=20),
                            ft.Column(
                                controls=[
                                    ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                    ft.Text(
                                        f"{file_path.parent} • {file_size}",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=16,
                                tooltip="移除",
                                on_click=lambda e, f=file_path: self._remove_file(f),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=PADDING_SMALL,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                )
                
                self.file_list_view.controls.append(file_item)
            
            self.process_button.content.disabled = False
        
        self.file_list_view.update()
        self.process_button.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_bitrate_change(self, e: ft.ControlEvent) -> None:
        """比特率改变事件处理。"""
        value = int(e.control.value)
        self.bitrate_value_text.value = f"{value} kbps"
        self.bitrate_value_text.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件处理。"""
        is_custom = e.control.value == "custom_dir"
        self.output_dir_field.disabled = not is_custom
        self.output_dir_button.disabled = not is_custom
        self.output_dir_field.update()
        self.output_dir_button.update()
    
    async def _select_output_dir(self, e: ft.ControlEvent) -> None:
        """选择输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.output_dir_field.value = folder_path
            self.output_dir_field.update()
    
    def _on_process(self) -> None:
        """开始压缩处理。"""
        if not self.selected_files:
            return
        
        # 验证输出目录
        if self.output_mode.value == "custom_dir":
            if not self.output_dir_field.value:
                self._show_error("请选择输出目录")
                return
            
            output_dir = Path(self.output_dir_field.value)
            if not output_dir.exists():
                self._show_error("输出目录不存在")
                return
        
        # 禁用控件
        self._set_processing_state(True)
        
        # 异步处理
        self._page.run_task(self._process_files_async)

    async def _process_files_async(self) -> None:
        """异步处理音频压缩任务。"""
        import asyncio

        self._task_finished = False
        self._pending_progress = None

        # 在事件循环中捕获 UI 控件的值
        output_mode_value = self.output_mode.value
        output_dir_value = self.output_dir_field.value
        bitrate = int(self.bitrate_slider.value)
        sample_rate = self.sample_rate_dropdown.value
        channels = self.channel_dropdown.value

        async def _poll():
            while not self._task_finished:
                if self._pending_progress is not None:
                    bar_val, text_val = self._pending_progress
                    self.progress_bar.value = bar_val
                    self.progress_text.value = text_val
                    self._page.update()
                    self._pending_progress = None
                await asyncio.sleep(0.3)

        def _do_work():
            total_files = len(self.selected_files)
            success_count = 0
            error_count = 0

            for i, file_path in enumerate(self.selected_files):
                try:
                    # 更新进度
                    progress = (i + 1) / total_files
                    self._pending_progress = (
                        progress,
                        f"正在压缩: {file_path.name} ({i + 1}/{total_files})",
                    )

                    # 确定输出路径
                    if output_mode_value == "custom_dir":
                        output_dir = Path(output_dir_value)
                    else:
                        output_dir = file_path.parent

                    output_path = output_dir / f"{file_path.stem}_compressed{file_path.suffix}"

                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)

                    # 执行压缩
                    success = self._compress_audio(
                        file_path,
                        output_path,
                        bitrate,
                        sample_rate,
                        channels
                    )

                    if success:
                        success_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    error_count += 1

            return success_count, error_count

        poll = asyncio.create_task(_poll())
        try:
            success_count, error_count = await asyncio.to_thread(_do_work)
        finally:
            self._task_finished = True
            await poll

        # 在事件循环中更新最终 UI
        self._set_processing_state(False)

        if error_count == 0:
            message = f"成功压缩 {success_count} 个文件"
            color = ft.Colors.GREEN
        else:
            message = f"完成: {success_count} 成功, {error_count} 失败"
            color = ft.Colors.ORANGE

        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self._page.open(snackbar)
    
    def _compress_audio(
        self,
        input_path: Path,
        output_path: Path,
        bitrate: int,
        sample_rate: str,
        channels: str
    ) -> bool:
        """压缩音频文件。
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            bitrate: 比特率（kbps）
            sample_rate: 采样率
            channels: 声道数
        
        Returns:
            是否成功
        """
        try:
            import ffmpeg
            
            # 构建输入流
            stream = ffmpeg.input(str(input_path))
            
            # 构建输出参数
            output_kwargs = {
                'audio_bitrate': f'{bitrate}k',
            }
            
            # 采样率
            if sample_rate != "original":
                output_kwargs['ar'] = sample_rate
            
            # 声道
            if channels != "original":
                output_kwargs['ac'] = channels
            
            # 构建输出流
            stream = ffmpeg.output(stream, str(output_path), **output_kwargs)
            
            # 执行转换（覆盖已存在的文件）
            ffmpeg.run(
                stream,
                cmd=self.ffmpeg_service.get_ffmpeg_path(),
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
                quiet=True
            )
            
            return True
            
        except ffmpeg.Error as e:
            logger.error(f"压缩音频失败: {e.stderr.decode() if e.stderr else str(e)}")
            return False
        except Exception as e:
            logger.error(f"压缩音频失败: {e}")
            return False
    
    def _update_progress(self, value: float, text: str) -> None:
        """更新进度显示。"""
        self.progress_bar.value = value
        self.progress_text.value = text
        try:
            self._page.update()
        except Exception:
            pass
    
    def _set_processing_state(self, processing: bool) -> None:
        """设置处理状态。"""
        self.process_button.content.disabled = processing
        self.progress_bar.visible = processing
        self.progress_text.visible = processing
        
        if processing:
            self.progress_bar.value = 0
            self.progress_text.value = "准备中..."
        
        try:
            self._page.update()
        except Exception:
            pass
    
    def _on_processing_complete(self, success_count: int, error_count: int) -> None:
        """处理完成。"""
        self._set_processing_state(False)
        
        # 显示结果
        if error_count == 0:
            message = f"成功压缩 {success_count} 个文件"
            color = ft.Colors.GREEN
        else:
            message = f"完成: {success_count} 成功, {error_count} 失败"
            color = ft.Colors.ORANGE
        
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self._page.open(snackbar)
    
    def _show_error(self, message: str) -> None:
        """显示错误消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR,
            duration=3000,
        )
        self._page.open(snackbar)
    
    def _on_back_click(self, e: ft.ControlEvent = None) -> None:
        """返回按钮点击事件处理。"""
        if self.on_back:
            self.on_back()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。"""
        added_count = 0
        skipped_count = 0
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                skipped_count += 1
                continue
            if path not in self.selected_files:
                self.selected_files.append(path)
                added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            snackbar = ft.SnackBar(content=ft.Text(f"已添加 {added_count} 个文件"), bgcolor=ft.Colors.GREEN)
            self._page.open(snackbar)
        elif skipped_count > 0:
            snackbar = ft.SnackBar(content=ft.Text("音频压缩不支持该格式"), bgcolor=ft.Colors.ORANGE)
            self._page.open(snackbar)
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
