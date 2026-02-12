# -*- coding: utf-8 -*-
"""视频提取音频视图模块。

提供从视频文件中提取音频的用户界面。
"""

import asyncio
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


class VideoExtractAudioView(ft.Container):
    """视频提取音频视图类。
    
    提供视频提取音频功能，包括：
    - 单文件和批量提取
    - 多种音频格式支持（MP3, AAC, WAV, FLAC等）
    - 比特率调整
    - 实时进度显示
    - 自动检测视频是否包含音频流
    """
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg'}

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频提取音频视图。
        
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
        # 缓存：文件路径 -> 是否有音频流
        self._audio_stream_cache: dict = {}
        
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
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("提取音频", size=28, weight=ft.FontWeight.BOLD),
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
                        ft.Text("选择视频:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=lambda _: self._page.run_task(self._on_select_files),
                        ),
                        ft.Button(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda _: self._page.run_task(self._on_select_folder),
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
        
        # 音频设置区域
        # 输出格式
        self.format_dropdown = ft.Dropdown(
            width=200,
            value="mp3",
            options=[
                ft.dropdown.Option("mp3", "MP3"),
                ft.dropdown.Option("aac", "AAC (M4A)"),
                ft.dropdown.Option("wav", "WAV (无损)"),
                ft.dropdown.Option("flac", "FLAC (无损)"),
                ft.dropdown.Option("ogg", "OGG Vorbis"),
                ft.dropdown.Option("opus", "Opus"),
            ],
            dense=True,
            on_select=self._on_format_change,
        )
        
        format_row = ft.Row(
            controls=[
                ft.Text("输出格式:", size=13),
                self.format_dropdown,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 比特率设置
        self.bitrate_value_text = ft.Text(
            "192 kbps",
            size=13,
            text_align=ft.TextAlign.END,
            width=80,
        )
        
        self.bitrate_slider = ft.Slider(
            min=64,
            max=320,
            value=192,
            divisions=8,
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
        
        self.bitrate_container = ft.Column(
            controls=[
                bitrate_row,
                self.bitrate_slider,
            ],
            spacing=0,
        )
        
        # 采样率设置
        self.sample_rate_dropdown = ft.Dropdown(
            width=200,
            value="original",
            options=[
                ft.dropdown.Option("original", "保持原始"),
                ft.dropdown.Option("44100", "44.1 kHz (CD质量)"),
                ft.dropdown.Option("48000", "48 kHz"),
                ft.dropdown.Option("96000", "96 kHz (高品质)"),
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
                ft.dropdown.Option("original", "保持原始"),
                ft.dropdown.Option("1", "单声道 (Mono)"),
                ft.dropdown.Option("2", "立体声 (Stereo)"),
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
        
        audio_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("音频设置", size=16, weight=ft.FontWeight.W_600),
                    ft.Container(height=PADDING_SMALL),
                    format_row,
                    ft.Container(height=PADDING_SMALL),
                    self.bitrate_container,
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
            on_click=lambda _: self._page.run_task(self._select_output_dir),
            disabled=True,
        )
        
        self.output_mode = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value="same_dir",
                        label="保存到视频所在目录",
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
                        ft.Icon(ft.Icons.AUDIO_FILE, size=24),
                        ft.Text("开始提取", size=18, weight=ft.FontWeight.W_600),
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
                audio_settings,
                ft.Container(height=PADDING_MEDIUM),
                output_settings,
                ft.Container(height=PADDING_MEDIUM),
                progress_area,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Container(height=PADDING_SMALL),
                scrollable_content,
            ],
            spacing=0,
            expand=True,
        )
    
    def _init_empty_state(self) -> None:
        """初始化空状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                height=250,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._on_select_files(),
                ink=True,
                tooltip="点击选择视频文件",
            )
        )
    
    async def _on_select_files(self) -> None:
        """选择文件。"""
        files = await ft.FilePicker().pick_files(
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v", "mpg", "mpeg", "ts", "mts", "m2ts"],
            dialog_title="选择视频文件",
            allow_multiple=True,
        )
        if files:
            for file in files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
    
    async def _on_select_folder(self) -> None:
        """选择文件夹。"""
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择视频文件夹"
        )
        if folder_path:
            video_extensions = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts"}
            for file_path in Path(folder_path).rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    def _check_has_audio_stream(self, file_path: Path) -> bool:
        """检测视频文件是否包含音频流。
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            是否包含音频流
        """
        # 检查缓存
        cache_key = str(file_path)
        if cache_key in self._audio_stream_cache:
            return self._audio_stream_cache[cache_key]
        
        has_audio = True  # 默认假设有音频
        try:
            import ffmpeg
            ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
            if ffprobe_path:
                probe = ffmpeg.probe(str(file_path), cmd=ffprobe_path)
                has_audio = any(s.get('codec_type') == 'audio' for s in probe.get('streams', []))
        except Exception as e:
            logger.debug(f"检测音频流失败: {file_path.name}, {e}")
            # 检测失败时假设有音频，让后续处理来报错
            has_audio = True
        
        self._audio_stream_cache[cache_key] = has_audio
        return has_audio
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self._init_empty_state()
            self.process_button.content.disabled = True
        else:
            no_audio_count = 0
            for file_path in self.selected_files:
                file_size = format_file_size(file_path.stat().st_size)
                
                # 检测是否有音频流
                has_audio = self._check_has_audio_stream(file_path)
                if not has_audio:
                    no_audio_count += 1
                
                # 根据是否有音频流显示不同的图标和提示
                if has_audio:
                    icon = ft.Icon(ft.Icons.VIDEO_FILE, size=20)
                    subtitle = f"{file_path.parent} • {file_size}"
                else:
                    icon = ft.Icon(ft.Icons.VOLUME_OFF, size=20, color=ft.Colors.ORANGE)
                    subtitle = f"⚠️ 无音频流 • {file_size}"
                
                file_item = ft.Container(
                    content=ft.Row(
                        controls=[
                            icon,
                            ft.Column(
                                controls=[
                                    ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                    ft.Text(
                                        subtitle,
                                        size=11,
                                        color=ft.Colors.ORANGE if not has_audio else ft.Colors.ON_SURFACE_VARIANT,
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
                    border=ft.border.all(1, ft.Colors.ORANGE if not has_audio else ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                )
                
                self.file_list_view.controls.append(file_item)
            
            # 如果有无音频的文件，显示警告
            if no_audio_count > 0:
                warning_text = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER, size=16, color=ft.Colors.ORANGE),
                            ft.Text(
                                f"{no_audio_count} 个文件不包含音频流，将被跳过",
                                size=12,
                                color=ft.Colors.ORANGE,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                )
                self.file_list_view.controls.insert(0, warning_text)
            
            self.process_button.content.disabled = False
        
        self.file_list_view.update()
        self.process_button.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        # 同时从缓存中移除
        cache_key = str(file_path)
        if cache_key in self._audio_stream_cache:
            del self._audio_stream_cache[cache_key]
        
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """格式改变事件处理。"""
        format_value = e.control.value
        # 无损格式不显示比特率设置
        if format_value in ["wav", "flac"]:
            self.bitrate_container.visible = False
        else:
            self.bitrate_container.visible = True
        self.bitrate_container.update()
    
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
    
    async def _select_output_dir(self) -> None:
        """选择输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择输出目录"
        )
        if folder_path:
            self.output_dir_field.value = folder_path
            self.output_dir_field.update()
    
    def _on_process(self) -> None:
        """开始提取处理。"""
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
        """处理文件（异步）。"""
        total_files = len(self.selected_files)
        success_count = 0
        error_count = 0
        no_audio_count = 0
        
        for i, file_path in enumerate(self.selected_files):
            try:
                # 先检查是否有音频流（使用缓存，在线程中执行IO操作）
                has_audio = await asyncio.to_thread(self._check_has_audio_stream, file_path)
                if not has_audio:
                    self._update_progress(
                        (i + 1) / total_files,
                        f"跳过(无音频): {file_path.name} ({i + 1}/{total_files})"
                    )
                    no_audio_count += 1
                    logger.info(f"跳过无音频流文件: {file_path.name}")
                    continue
                
                # 更新进度
                progress = (i + 1) / total_files
                self._update_progress(
                    progress,
                    f"正在提取: {file_path.name} ({i + 1}/{total_files})"
                )
                
                # 确定输出路径
                if self.output_mode.value == "custom_dir":
                    output_dir = Path(self.output_dir_field.value)
                else:
                    output_dir = file_path.parent
                
                # 获取输出格式和扩展名
                output_format = self.format_dropdown.value
                if output_format == "aac":
                    output_ext = ".m4a"
                else:
                    output_ext = f".{output_format}"
                
                output_path = output_dir / f"{file_path.stem}{output_ext}"
                
                # 根据全局设置决定是否添加序号
                add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                output_path = get_unique_path(output_path, add_sequence=add_sequence)
                
                # 构建FFmpeg参数
                bitrate = int(self.bitrate_slider.value)
                sample_rate = self.sample_rate_dropdown.value
                channels = self.channel_dropdown.value
                
                # 执行提取（在线程中执行CPU/IO密集操作）
                success = await asyncio.to_thread(
                    self._extract_audio,
                    file_path,
                    output_path,
                    output_format,
                    bitrate,
                    sample_rate,
                    channels
                )
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"提取音频失败: {file_path}, 错误: {e}")
                error_count += 1
        
        # 完成处理
        self._on_processing_complete(success_count, error_count, no_audio_count)
    
    def _extract_audio(
        self,
        input_path: Path,
        output_path: Path,
        output_format: str,
        bitrate: int,
        sample_rate: str,
        channels: str
    ) -> bool:
        """提取音频。
        
        Args:
            input_path: 输入视频路径
            output_path: 输出音频路径
            output_format: 输出格式
            bitrate: 比特率（kbps）
            sample_rate: 采样率
            channels: 声道数
        
        Returns:
            是否成功
        """
        try:
            import ffmpeg
            
            # 先检测视频是否有音频流
            ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
            if ffprobe_path:
                try:
                    probe = ffmpeg.probe(str(input_path), cmd=ffprobe_path)
                    has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
                    if not has_audio:
                        logger.warning(f"视频文件不包含音频流: {input_path.name}")
                        return False
                except ffmpeg.Error:
                    # 如果探测失败，继续尝试提取（让 ffmpeg 报错）
                    pass
            
            # 构建输入流（只提取音频）
            stream = ffmpeg.input(str(input_path))
            
            # 构建输出参数
            output_kwargs = {
                'vn': None,  # 不包含视频
            }
            
            # 音频编码器映射
            codec_map = {
                "mp3": "libmp3lame",
                "aac": "aac",
                "wav": "pcm_s16le",
                "flac": "flac",
                "ogg": "libvorbis",
                "opus": "libopus",
            }
            
            # 设置音频编码器
            codec = codec_map.get(output_format)
            if codec:
                output_kwargs['acodec'] = codec
            
            # 设置比特率（无损格式不需要）
            if output_format not in ["wav", "flac"]:
                output_kwargs['audio_bitrate'] = f'{bitrate}k'
            
            # 采样率
            if sample_rate != "original":
                output_kwargs['ar'] = sample_rate
            
            # 声道
            if channels != "original":
                output_kwargs['ac'] = channels
            
            # 构建输出流
            stream = ffmpeg.output(stream, str(output_path), **output_kwargs)
            
            # 执行提取（覆盖已存在的文件）
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
            logger.error(f"提取音频失败: {e.stderr.decode() if e.stderr else str(e)}")
            return False
        except Exception as e:
            logger.error(f"提取音频失败: {e}")
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
    
    def _on_processing_complete(self, success_count: int, error_count: int, no_audio_count: int = 0) -> None:
        """处理完成。
        
        Args:
            success_count: 成功数量
            error_count: 失败数量
            no_audio_count: 无音频流跳过的数量
        """
        self._set_processing_state(False)
        
        # 显示结果
        if error_count == 0 and no_audio_count == 0:
            message = f"成功提取 {success_count} 个音频文件"
            color = ft.Colors.GREEN
        elif no_audio_count > 0 and error_count == 0:
            message = f"成功: {success_count} 个，跳过: {no_audio_count} 个(无音频流)"
            color = ft.Colors.ORANGE
        else:
            parts = [f"成功: {success_count}"]
            if error_count > 0:
                parts.append(f"失败: {error_count}")
            if no_audio_count > 0:
                parts.append(f"跳过: {no_audio_count}(无音频)")
            message = "，".join(parts)
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
            snackbar = ft.SnackBar(content=ft.Text("视频提取音频不支持该格式"), bgcolor=ft.Colors.ORANGE)
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
