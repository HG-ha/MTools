# -*- coding: utf-8 -*-
"""音频格式转换视图模块。

提供音频格式转换功能的用户界面。
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
    PADDING_XLARGE,
)
from services import AudioService, ConfigService, FFmpegService
from utils import format_file_size


class AudioFormatView(ft.Container):
    """音频格式转换视图类。
    
    提供音频格式转换功能，包括：
    - 多格式支持（MP3, WAV, AAC, FLAC, OGG, M4A等）
    - 批量转换
    - 比特率调整
    - 采样率调整
    - 声道调整
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        audio_service: AudioService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化音频格式转换视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            audio_service: 音频服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.audio_service: AudioService = audio_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        
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
                ft.Text("音频格式转换", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择音频:", size=14, weight=ft.FontWeight.W_500),
                        ft.ElevatedButton(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_files,
                        ),
                        ft.ElevatedButton(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=self._on_select_folder,
                        ),
                        ft.TextButton(
                            "清空列表",
                            icon=ft.Icons.CLEAR_ALL,
                            on_click=self._on_clear_files,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持格式: MP3, WAV, AAC, M4A, FLAC, OGG, WMA, OPUS 等",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(left=4, bottom=4),
                ),
                ft.Container(
                    content=self.file_list_view,
                    expand=True,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 右侧：转换选项
        # 1. 输出格式
        format_options = []
        for fmt in self.audio_service.get_supported_formats():
            format_options.append(
                ft.dropdown.Option(
                    key=fmt["extension"],
                    text=f"{fmt['name']}  |  {fmt['description']}"
                )
            )
        
        self.output_format_dropdown: ft.Dropdown = ft.Dropdown(
            options=format_options,
            value="mp3",
            label="输出格式",
            width=320,
            dense=True,
            on_change=self._on_format_change,
        )
        
        format_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出格式", size=14, weight=ft.FontWeight.W_500),
                    self.output_format_dropdown,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 2. 音质设置
        self.quality_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="auto", label="自动（保持原始质量）"),
                    ft.Radio(value="custom", label="自定义设置"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="auto",
            on_change=self._on_quality_mode_change,
        )
        
        # 比特率
        bitrate_options = []
        for preset in self.audio_service.get_bitrate_presets():
            bitrate_options.append(
                ft.dropdown.Option(
                    key=preset["value"],
                    text=f"{preset['name']}  |  {preset['description']}"
                )
            )
        
        self.bitrate_dropdown: ft.Dropdown = ft.Dropdown(
            options=bitrate_options,
            value="192k",
            label="比特率",
            width=280,
            dense=True,
            disabled=True,
        )
        
        # 采样率
        sample_rate_options = []
        for preset in self.audio_service.get_sample_rate_presets():
            sample_rate_options.append(
                ft.dropdown.Option(
                    key=str(preset["value"]),
                    text=f"{preset['name']}  |  {preset['description']}"
                )
            )
        
        self.sample_rate_dropdown: ft.Dropdown = ft.Dropdown(
            options=sample_rate_options,
            value="44100",
            label="采样率",
            width=280,
            dense=True,
            disabled=True,
        )
        
        # 声道
        self.channels_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="keep", label="保持原始"),
                    ft.Radio(value="1", label="单声道"),
                    ft.Radio(value="2", label="立体声"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="keep",
            disabled=True,
        )
        
        quality_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音质设置", size=14, weight=ft.FontWeight.W_500),
                    self.quality_mode_radio,
                    ft.Container(height=PADDING_SMALL),
                    self.bitrate_dropdown,
                    self.sample_rate_dropdown,
                    ft.Text("声道", size=13),
                    self.channels_radio,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 3. 输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "audio_converted"),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 选项可滚动区域
        options_scroll: ft.Column = ft.Column(
            controls=[
                format_section,
                quality_section,
                output_section,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 主内容区域 - 左右分栏
        main_content: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=file_select_area,
                    expand=3,
                    height=380,
                ),
                ft.Container(
                    content=options_scroll,
                    expand=2,
                    height=380,
                ),
            ],
            spacing=PADDING_LARGE,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 进度显示
        self.progress_bar: ft.ProgressBar = ft.ProgressBar(value=0, visible=False)
        self.progress_text: ft.Text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        progress_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
        )
        
        # 底部处理按钮
        self.process_button: ft.Container = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SYNC_ALT, size=24),
                        ft.Text("开始转换", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
        )
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                main_content,
                ft.Container(height=PADDING_MEDIUM),
                progress_container,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
            ],
            spacing=0,
            expand=True,
        )
        
        # 初始化文件列表空状态
        self._update_file_list()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                for file in result.files:
                    file_path = Path(file.path)
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择音频文件",
            allowed_extensions=["mp3", "wav", "aac", "m4a", "flac", "ogg", "wma", "opus", "ape", "alac"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder_path = Path(result.path)
                audio_extensions = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg", ".wma", ".opus", ".ape", ".alac"}
                for file_path in folder_path.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
                        if file_path not in self.selected_files:
                            self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
                
                if self.selected_files:
                    self._show_snackbar(f"已添加 {len(self.selected_files)} 个文件", ft.Colors.GREEN)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择包含音频的文件夹")
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        self.selected_files.clear()
        self._update_file_list()
        self._update_process_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.AUDIO_FILE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击选择按钮或点击此处选择音频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_SMALL,
                    ),
                    height=280,
                    alignment=ft.alignment.center,
                    on_click=self._on_select_files,
                    tooltip="点击选择音频",
                )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                # 获取音频信息
                info = self.audio_service.get_audio_info(file_path)
                
                if 'error' in info:
                    info_text = f"错误: {info['error']}"
                    icon_color = ft.Colors.RED
                else:
                    duration = info.get('duration', 0)
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    size_str = format_file_size(info.get('file_size', 0))
                    codec = info.get('codec', '未知')
                    bitrate = info.get('bit_rate', 0) // 1000  # 转换为 kbps
                    
                    info_text = f"{codec.upper()} · {bitrate}kbps · {minutes}:{seconds:02d} · {size_str}"
                    icon_color = ft.Colors.PRIMARY
                
                file_item: ft.Container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.AUDIO_FILE, size=20, color=icon_color),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        file_path.name,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(info_text, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=16,
                                tooltip="移除",
                                on_click=lambda e, idx=i: self._on_remove_file(idx),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=PADDING_SMALL,
                    border_radius=BORDER_RADIUS_MEDIUM,
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                )
                
                self.file_list_view.controls.append(file_item)
        
        try:
            self.file_list_view.update()
        except:
            pass
    
    def _on_remove_file(self, index: int) -> None:
        """移除文件列表中的文件。
        
        Args:
            index: 文件索引
        """
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
            self._update_process_button()
    
    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式改变事件。
        
        Args:
            e: 控件事件对象
        """
        output_format = self.output_format_dropdown.value
        
        # 无损格式不支持比特率设置
        if output_format in ["wav", "flac"]:
            if self.quality_mode_radio.value == "custom":
                self.bitrate_dropdown.disabled = True
                self.bitrate_dropdown.update()
    
    def _on_quality_mode_change(self, e: ft.ControlEvent) -> None:
        """音质模式改变事件。
        
        Args:
            e: 控件事件对象
        """
        is_custom = self.quality_mode_radio.value == "custom"
        output_format = self.output_format_dropdown.value
        
        # 无损格式不支持比特率
        bitrate_enabled = is_custom and output_format not in ["wav", "flac"]
        
        self.bitrate_dropdown.disabled = not bitrate_enabled
        self.sample_rate_dropdown.disabled = not is_custom
        self.channels_radio.disabled = not is_custom
        
        self.bitrate_dropdown.update()
        self.sample_rate_dropdown.update()
        self.channels_radio.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。
        
        Args:
            e: 控件事件对象
        """
        is_custom = self.output_mode_radio.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self.custom_output_dir.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.custom_output_dir.update()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _update_process_button(self) -> None:
        """更新处理按钮状态。"""
        button = self.process_button.content
        button.disabled = not self.selected_files
        self.process_button.update()
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if not self.selected_files:
            self._show_snackbar("请先选择音频文件", ft.Colors.ORANGE)
            return
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.custom_output_dir.value)
        else:
            output_dir = None  # 保存在原文件旁边
        
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取转换参数
        output_format = self.output_format_dropdown.value
        
        if self.quality_mode_radio.value == "custom":
            bitrate = self.bitrate_dropdown.value if output_format not in ["wav", "flac"] else None
            sample_rate = int(self.sample_rate_dropdown.value)
            channels = int(self.channels_radio.value) if self.channels_radio.value != "keep" else None
        else:
            bitrate = None
            sample_rate = None
            channels = None
        
        # 禁用处理按钮并显示进度
        button = self.process_button.content
        button.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备转换..."
        
        try:
            self.page.update()
        except:
            pass
        
        # 在后台线程处理
        def process_task():
            total_files = len(self.selected_files)
            success_count = 0
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    # 更新进度
                    progress = i / total_files
                    self._update_progress(progress, f"正在转换: {file_path.name} ({i+1}/{total_files})")
                    
                    # 生成输出文件名
                    if output_dir:
                        output_path = output_dir / f"{file_path.stem}.{output_format}"
                    else:
                        output_path = file_path.parent / f"{file_path.stem}_converted.{output_format}"
                    
                    # 转换音频
                    success, message = self.audio_service.convert_audio(
                        file_path,
                        output_path,
                        output_format=output_format,
                        bitrate=bitrate,
                        sample_rate=sample_rate,
                        channels=channels
                    )
                    
                    if success:
                        success_count += 1
                    else:
                        print(f"转换失败 {file_path.name}: {message}")
                
                except Exception as ex:
                    print(f"处理失败 {file_path.name}: {ex}")
            
            # 处理完成
            self._on_process_complete(success_count, total_files, output_dir)
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _update_progress(self, value: float, text: str) -> None:
        """更新进度显示。
        
        Args:
            value: 进度值 (0-1)
            text: 进度文本
        """
        self.progress_bar.value = value
        self.progress_text.value = text
        try:
            self.page.update()
        except:
            pass
    
    def _on_process_complete(self, success_count: int, total: int, output_dir: Optional[Path]) -> None:
        """处理完成回调。
        
        Args:
            success_count: 成功处理的数量
            total: 总数量
            output_dir: 输出目录
        """
        # 更新进度和按钮状态
        self.progress_bar.value = 1.0
        self.progress_text.value = f"转换完成! 成功: {success_count}/{total}"
        button = self.process_button.content
        button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
        
        # 显示成功消息
        if output_dir:
            self._show_snackbar(
                f"转换完成! 成功处理 {success_count} 个文件，保存到: {output_dir}",
                ft.Colors.GREEN
            )
        else:
            self._show_snackbar(
                f"转换完成! 成功处理 {success_count} 个文件，保存在原文件旁边",
                ft.Colors.GREEN
            )
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
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

