# -*- coding: utf-8 -*-
"""视频倍速调整视图模块。

提供视频播放速度调整功能的用户界面。
"""

import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, FFmpegService
from utils import format_file_size, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoSpeedView(ft.Container):
    """视频倍速调整视图类。"""
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'}
    
    """提供视频播放速度调整功能，包括：
    - 单文件和批量处理
    - 0.25x-4x倍速调整
    - 音频同步调整
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频倍速调整视图。
        
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
                ft.Text("视频倍速调整", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        file_select_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("文件选择", size=18, weight=ft.FontWeight.W_600),
                            ft.Container(expand=True),
                            ft.Button(
                                "选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=lambda _: self._page.run_task(self._on_select_files),
                                height=36,
                            ),
                            ft.Button(
                                "选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _: self._page.run_task(self._on_select_folder),
                                height=36,
                            ),
                            ft.OutlinedButton(
                                "清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                                height=36,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持格式: MP4, MKV, MOV, AVI, WMV, FLV, WebM, M4V, 3GP, TS 等",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=6,
                        ),
                        margin=ft.margin.only(bottom=PADDING_SMALL),
                    ),
                    ft.Container(
                        content=self.file_list_view,
                        height=220,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # 速度设置区域
        self.speed_slider = ft.Slider(
            min=0.1,
            max=10.0,
            value=1.0,
            divisions=99,
            label="{value}x",
            on_change=self._on_speed_change,
        )
        
        self.speed_text = ft.Text("播放速度: 1.0x (原速)", size=14, weight=ft.FontWeight.W_500)
        
        # GPU加速状态提示
        gpu_status_row = []
        gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
        if gpu_encoder:
            gpu_encoder_name = gpu_encoder.replace("_", " ").upper()
            gpu_status_row.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SPEED, size=16, color=ft.Colors.GREEN),
                            ft.Text(
                                f"GPU加速已启用: {gpu_encoder_name}",
                                size=12,
                                color=ft.Colors.GREEN,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=6,
                    ),
                    margin=ft.margin.only(top=PADDING_SMALL),
                )
            )
        
        # 预设速度按钮
        preset_speeds = [
            ("0.1x", 0.1),
            ("0.25x", 0.25),
            ("0.5x", 0.5),
            ("0.75x", 0.75),
            ("1.0x", 1.0),
            ("1.25x", 1.25),
            ("1.5x", 1.5),
            ("2.0x", 2.0),
            ("3.0x", 3.0),
            ("4.0x", 4.0),
            ("5.0x", 5.0),
            ("8.0x", 8.0),
            ("10.0x", 10.0),
        ]
        
        preset_buttons = []
        for label, speed in preset_speeds:
            btn = ft.OutlinedButton(
                content=label,
                on_click=lambda e, s=speed: self._set_speed(s),
                height=32,
            )
            preset_buttons.append(btn)
        
        # 构建速度设置的控件列表
        speed_controls = [self.speed_text, self.speed_slider]
        speed_controls.extend(gpu_status_row)  # 添加GPU状态（如果有）
        speed_controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("快速选择:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Row(
                            controls=preset_buttons,
                            wrap=True,
                            spacing=PADDING_SMALL,
                            run_spacing=PADDING_SMALL,
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
                margin=ft.margin.only(top=PADDING_MEDIUM),
            )
        )
        
        speed_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("速度设置", size=18, weight=ft.FontWeight.W_600),
                    ft.Container(
                        content=ft.Column(
                            controls=speed_controls,
                            spacing=PADDING_SMALL,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 音频选项
        self.audio_adjust_switch = ft.Switch(
            label="同步调整音频速度",
            value=True,
            tooltip="关闭则保留原始音频（可能导致音画不同步）",
        )
        
        audio_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音频选项", size=18, weight=ft.FontWeight.W_600),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.audio_adjust_switch,
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text(
                                                "开启时，音频会按相同倍数调整速度，保持音画同步",
                                                size=11,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                        spacing=4,
                                    ),
                                    margin=ft.margin.only(left=48),
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_speed",
            disabled=False,
            width=200,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: self._page.run_task(self._on_browse_output),
            disabled=True,
        )
        
        output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=18, weight=ft.FontWeight.W_600),
                    self.output_mode_radio,
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.file_suffix,
                                ft.Row(
                                    controls=[self.custom_output_dir, self.browse_output_button],
                                    spacing=PADDING_SMALL,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 底部按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SPEED, size=24),
                        ft.Text("开始处理", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 进度显示容器
        progress_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        self.progress_container = progress_container
        
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                speed_settings,
                ft.Container(height=PADDING_MEDIUM),
                audio_options,
                ft.Container(height=PADDING_MEDIUM),
                output_options,
                ft.Container(height=PADDING_MEDIUM),
                progress_container,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
        )
        
        self._init_empty_state()

    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.MOVIE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=190,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._on_select_files(e),
                ink=True,
                tooltip="点击选择视频文件",
            )
        )

    async def _on_select_files(self) -> None:
        """选择文件事件处理。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=[
                "mp4", "mkv", "mov", "avi", "wmv", "flv", "webm", 
                "m4v", "3gp", "ts", "m2ts", "f4v", "asf", "rm", "rmvb"
            ],
            allow_multiple=True,
        )
        if files:
            new_files = [Path(f.path) for f in files]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()

    async def _on_select_folder(self) -> None:
        """选择文件夹事件处理。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择视频文件夹")
        if folder_path:
            folder = Path(folder_path)
            extensions = [
                ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
                ".m4v", ".3gp", ".ts", ".m2ts", ".f4v", ".asf", ".rm", ".rmvb"
            ]
            self.selected_files.clear()
            for ext in extensions:
                self.selected_files.extend(folder.glob(f"**/*{ext}"))
                self.selected_files.extend(folder.glob(f"**/*{ext.upper()}"))
            self._update_file_list()

    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        if not self.selected_files:
            self._init_empty_state()
        else:
            for idx, file_path in enumerate(self.selected_files):
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.VIDEOCAM, size=20, color=ft.Colors.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(f"大小: {size_str}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, i=idx: self._on_remove_file(i),
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_MEDIUM,
                    )
                )
        self._page.update()

    def _on_remove_file(self, index: int) -> None:
        """移除文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()

    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()

    def _on_speed_change(self, e: ft.ControlEvent) -> None:
        """速度滑块改变事件。"""
        speed = e.control.value
        self._update_speed_text(speed)

    def _set_speed(self, speed: float) -> None:
        """设置速度值。"""
        self.speed_slider.value = speed
        self._update_speed_text(speed)
        self._page.update()

    def _update_speed_text(self, speed: float) -> None:
        """更新速度文本。"""
        if speed == 1.0:
            self.speed_text.value = f"播放速度: {speed:.2f}x (原速)"
        elif speed < 1.0:
            self.speed_text.value = f"播放速度: {speed:.2f}x (慢放)"
        else:
            self.speed_text.value = f"播放速度: {speed:.2f}x (快放)"
        self._page.update()

    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        mode = e.control.value
        self.file_suffix.disabled = mode != "new"
        self.custom_output_dir.disabled = mode != "custom"
        self.browse_output_button.disabled = mode != "custom"
        self._page.update()

    async def _on_browse_output(self) -> None:
        """浏览输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self._page.update()

    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理视频。"""
        if not self.selected_files:
            self._show_message("请先选择要处理的视频", ft.Colors.ORANGE)
            return

        speed = self.speed_slider.value
        adjust_audio = self.audio_adjust_switch.value
        output_mode = self.output_mode_radio.value

        self.progress_container.visible = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备处理..."
        self._page.update()

        self._page.run_task(lambda: self._process_task(speed, adjust_audio, output_mode))

    async def _process_task(self, speed: float, adjust_audio: bool, output_mode: str) -> None:
        import asyncio

        self._task_finished = False
        self._pending_progress = None

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
            total = len(self.selected_files)
            success_count = 0
            failed_files = []

            for i, input_path in enumerate(self.selected_files):
                try:
                    # 确定输出路径
                    if output_mode == "new":
                        suffix = self.file_suffix.value or "_speed"
                        ext = input_path.suffix
                        output_path = input_path.parent / f"{input_path.stem}{suffix}{ext}"
                    else:
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / input_path.name

                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)

                    def progress_handler(progress, speed_str, remaining_time):
                        # 计算总体进度
                        overall_progress = (i + progress) / total
                        percent = int(progress * 100)
                        self._pending_progress = (
                            overall_progress,
                            f"正在处理 ({i+1}/{total}): {input_path.name}\n"
                            f"进度: {percent}% | 速度: {speed_str} | 预计剩余: {remaining_time}"
                        )

                    # 显示开始处理
                    self._pending_progress = (
                        i / total,
                        f"开始处理 ({i+1}/{total}): {input_path.name}..."
                    )

                    result, message = self.ffmpeg_service.adjust_video_speed(
                        input_path, output_path, speed, adjust_audio, progress_handler
                    )

                    if result:
                        success_count += 1
                    else:
                        failed_files.append(f"{input_path.name}: {message}")

                except Exception as e:
                    failed_files.append(f"{input_path.name}: {str(e)}")

            return success_count, failed_files, total

        poll = asyncio.create_task(_poll())
        try:
            success_count, failed_files, total = await asyncio.to_thread(_do_work)
        finally:
            self._task_finished = True
            await poll

        # 完成后显示结果
        self.progress_bar.visible = False
        self.progress_container.visible = False

        if failed_files:
            self.progress_text.value = (
                f"处理完成！成功: {success_count}/{total}\n"
                f"失败: {len(failed_files)} 个文件"
            )
            self._show_message(f"部分文件处理失败 ({len(failed_files)}个)", ft.Colors.ORANGE)
        else:
            self.progress_text.value = f"处理完成！成功处理 {total} 个文件。"
            self._show_message("全部处理完成！", ft.Colors.GREEN)

        self._page.update()

    def _on_back_click(self, e: Optional[ft.ControlEvent] = None) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()

    def _show_message(self, message: str, color: str) -> None:
        """显示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.open(snackbar)
    
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
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_message("视频倍速不支持该格式", ft.Colors.ORANGE)
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
