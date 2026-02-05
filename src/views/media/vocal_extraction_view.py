# -*- coding: utf-8 -*-
"""人声提取视图模块。

提供人声/伴奏分离功能的用户界面。
"""

import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_VOCAL_MODEL_KEY,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    VOCAL_SEPARATION_MODELS,
)
from services import ConfigService, VocalSeparationService, FFmpegService
from utils import format_file_size, logger
from views.media.ffmpeg_install_view import FFmpegInstallView


class VocalExtractionView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.ape'}
    """人声提取视图类。
    
    提供人声/伴奏分离功能，包括：
    - 单文件处理
    - 批量处理
    - 人声和伴奏分离
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化人声提取视图。
        
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
        self.is_processing: bool = False
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "vocal_separation"
        self.vocal_service: VocalSeparationService = VocalSeparationService(
            model_dir,
            ffmpeg_service,
            config_service
        )
        self.model_loading: bool = False
        self.model_loaded: bool = False
        self.auto_load_model: bool = self.config_service.get_config_value("vocal_auto_load_model", True)
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            # 显示 FFmpeg 安装视图
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self._page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="人声提取"
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
                ft.Text("人声提取", size=28, weight=ft.FontWeight.BOLD),
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
                            on_click=lambda _: self._page.run_task(self._on_select_files),
                        ),
                        ft.Button(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda _: self._page.run_task(self._on_select_folder),
                        ),
                        ft.TextButton(
                            "清空列表",
                            icon=ft.Icons.CLEAR_ALL,
                            on_click=lambda _: self._clear_files(),
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持格式: MP3, WAV, FLAC, M4A, OGG, WMA 等",
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
                    height=220,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 模型选择区域
        model_options = []
        for model_key, model_info in VOCAL_SEPARATION_MODELS.items():
            # 添加模型类型标识
            prefix = "[伴奏]" if model_info.invert_output else "[人声]"
            option_text = f"{prefix} {model_info.display_name}  |  {model_info.size_mb}MB"
            
            model_options.append(
                ft.dropdown.Option(key=model_key, text=option_text)
            )
        
        self.model_dropdown = ft.Dropdown(
            options=model_options,
            value=DEFAULT_VOCAL_MODEL_KEY,
            label="选择模型",
            hint_text="选择分离模型",
            on_select=self._on_model_change,
            width=480,
            dense=True,
            text_size=13,
        )
        
        # 模型信息显示
        self.model_info_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 模型状态显示
        self.model_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD,
            size=20,
            color=ft.Colors.ORANGE,
        )
        
        self.model_status_text = ft.Text(
            "未下载",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 下载模型按钮
        self.download_model_button = ft.Button(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_model,
            visible=False,
        )
        
        self.load_model_button = ft.Button(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model_click,
            visible=False,
        )

        self.unload_model_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型",
            on_click=self._on_unload_model_click,
            visible=False,
        )

        # 删除模型按钮
        self.delete_model_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model,
            visible=False,
        )
        
        model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.download_model_button,
                self.load_model_button,
                self.unload_model_button,
                self.delete_model_button,
            ],
            spacing=PADDING_SMALL,
        )

        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=self.auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    self.model_dropdown,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    self.auto_load_checkbox,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 初始化模型状态
        self._init_model_status()
        if self.auto_load_model:
            self._try_auto_load_model()
        
        # 输出设置区域
        self.output_vocals_checkbox = ft.Checkbox(
            label="输出人声 (Vocals)",
            value=True,
        )
        
        self.output_instrumental_checkbox = ft.Checkbox(
            label="输出伴奏 (Instrumental)",
            value=True,
        )
        
        # 输出格式选择
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            options=[
                ft.dropdown.Option(key="original", text="跟随原文件"),
                ft.dropdown.Option(key="wav", text="WAV (无损)"),
                ft.dropdown.Option(key="flac", text="FLAC (无损压缩)"),
                ft.dropdown.Option(key="mp3", text="MP3"),
                ft.dropdown.Option(key="ogg", text="OGG Vorbis"),
            ],
            value="original",
            width=200,
            dense=True,
            text_size=13,
            on_select=self._on_format_change,
        )
        
        # 采样率设置
        self.sample_rate_dropdown = ft.Dropdown(
            label="采样率",
            options=[
                ft.dropdown.Option(key="original", text="跟随原文件"),
                ft.dropdown.Option(key="44100", text="44.1 kHz (CD质量)"),
                ft.dropdown.Option(key="48000", text="48 kHz (标准)"),
                ft.dropdown.Option(key="96000", text="96 kHz (高保真)"),
            ],
            value="original",
            width=200,
            dense=True,
            text_size=13,
        )
        
        # MP3 码率设置（默认隐藏）
        self.mp3_bitrate_dropdown = ft.Dropdown(
            label="MP3 码率",
            options=[
                ft.dropdown.Option(key="original", text="跟随原文件"),
                ft.dropdown.Option(key="128k", text="128 kbps (中等)"),
                ft.dropdown.Option(key="192k", text="192 kbps (良好)"),
                ft.dropdown.Option(key="256k", text="256 kbps (高质量)"),
                ft.dropdown.Option(key="320k", text="320 kbps (最高)"),
            ],
            value="original",
            width=200,
            dense=True,
            text_size=13,
            visible=False,
        )
        
        # OGG 质量设置（默认隐藏）
        self.ogg_quality_dropdown = ft.Dropdown(
            label="OGG 质量",
            options=[
                ft.dropdown.Option(key="original", text="跟随原文件"),
                ft.dropdown.Option(key="4", text="质量 4 (~128 kbps)"),
                ft.dropdown.Option(key="6", text="质量 6 (~192 kbps)"),
                ft.dropdown.Option(key="8", text="质量 8 (~256 kbps)"),
                ft.dropdown.Option(key="10", text="质量 10 (最高)"),
            ],
            value="original",
            width=200,
            dense=True,
            text_size=13,
            visible=False,
        )
        
        # 输出模式选择
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="source", label="保存到源文件目录"),
                    ft.Radio(value="custom", label="保存到自定义目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="source",
            on_change=self._on_output_mode_change,
        )
        
        # 输出目录设置
        default_output = self.config_service.get_output_dir() / "vocal_extraction"
        
        self.output_dir_field = ft.TextField(
            label="输出目录",
            value=str(default_output),
            read_only=True,
            dense=True,
            expand=True,
            disabled=True,  # 默认禁用
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: self._page.run_task(self._on_browse_output),
            disabled=True,  # 默认禁用
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Row(
                        controls=[
                            self.output_vocals_checkbox,
                            self.output_instrumental_checkbox,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Row(
                        controls=[
                            self.output_format_dropdown,
                            self.sample_rate_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Row(
                        controls=[
                            self.mp3_bitrate_dropdown,
                            self.ogg_quality_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    ft.Container(height=PADDING_SMALL // 2),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.output_dir_field,
                            self.browse_output_button,
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
        
        # 进度显示区域
        self.progress_bar = ft.ProgressBar(
            value=0,
            visible=False,
            bar_height=8,
        )
        
        self.progress_text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        self.current_file_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        progress_section = ft.Column(
            controls=[
                self.progress_text,
                self.progress_bar,
                self.current_file_text,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 底部大按钮 - 与背景移除工具样式一致
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.GRAPHIC_EQ, size=24),
                        ft.Text("开始提取人声", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process_click,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 取消按钮（保持原样式，处理时显示）
        self.cancel_button = ft.Button(
            "取消",
            icon=ft.Icons.STOP,
            on_click=self._on_cancel_click,
            visible=False,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=24, vertical=12),
            ),
        )
        
        button_row = ft.Row(
            controls=[
                self.cancel_button,
            ],
            spacing=PADDING_MEDIUM,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                model_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_LARGE),
                progress_section,
                ft.Container(height=PADDING_MEDIUM),
                button_row,
                ft.Container(height=PADDING_MEDIUM),
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
        """初始化空状态显示。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.MUSIC_NOTE, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "未选择文件",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "点击此处选择音频文件",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL // 2,
                ),
                height=188,
                alignment=ft.Alignment.CENTER,
                on_click=lambda _: self._page.run_task(self._on_empty_area_click),
                ink=True,
                tooltip="点击选择音频文件",
            )
        )
    
    async def _on_empty_area_click(self) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files()
    
    async def _on_select_files(self) -> None:
        """选择文件按钮点击事件。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择音频文件",
            allowed_extensions=["mp3", "wav", "flac", "m4a", "aac", "ogg", "wma", "opus"],
            allow_multiple=True,
        )
        if files:
            for file in files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
    
    async def _on_select_folder(self) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="选择包含音频的文件夹"
        )
        if folder_path:
            audio_extensions = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".opus"}
            for file_path in Path(folder_path).rglob("*"):
                if file_path.suffix.lower() in audio_extensions and file_path not in self.selected_files:
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
                self.file_list_view.controls.append(
                    self._create_file_item(file_path)
                )
            self.process_button.content.disabled = False
        
        self.file_list_view.update()
        self.process_button.update()
    
    def _create_file_item(self, file_path: Path) -> ft.Container:
        """创建文件列表项。"""
        try:
            file_size = file_path.stat().st_size
            size_text = format_file_size(file_size)
        except:
            size_text = "未知大小"
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUDIO_FILE, size=20),
                    ft.Column(
                        controls=[
                            ft.Text(
                                file_path.name,
                                size=13,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                f"{size_text}",
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
                        on_click=lambda _, fp=file_path: self._remove_file(fp),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_SMALL,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        )
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_process_click(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if not self.selected_files:
            return
        
        if not self.output_vocals_checkbox.value and not self.output_instrumental_checkbox.value:
            self._show_snackbar("请至少选择一种输出类型", ft.Colors.ERROR)
            return
        
        # 开始处理
        self.is_processing = True
        self.process_button.content.disabled = True
        self.cancel_button.visible = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.current_file_text.visible = True
        
        self._page.update()
        
        # 在后台线程中处理
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()
    
    def _on_cancel_click(self, e: ft.ControlEvent) -> None:
        """取消按钮点击事件。"""
        self.is_processing = False
        self._reset_ui()
    
    def _process_files(self) -> None:
        """处理文件（在后台线程中运行）。"""
        try:
            # 根据用户选择确定输出目录
            if self.output_mode_radio.value == "custom":
                output_dir = Path(self.output_dir_field.value)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                # 保存到源文件目录，每个文件单独处理
                output_dir = None  # 在循环中为每个文件设置
            
            # 加载模型
            model_key = self.model_dropdown.value
            model_info = VOCAL_SEPARATION_MODELS[model_key]
            model_path = self.vocal_service.model_dir / model_info.filename
            
            # 检查模型是否已下载
            if not model_path.exists():
                self._show_snackbar("请先下载模型!", ft.Colors.ERROR)
                self._reset_ui()
                return
            
            need_load = (
                not self.model_loaded
                or self.vocal_service.current_model != model_info.filename
            )

            if need_load:
                self._update_progress("正在加载模型...", 0.0)
                try:
                    self.vocal_service.load_model(
                        model_path,
                        invert_output=model_info.invert_output
                    )
                    device_info = self.vocal_service.get_device_info()
                    message = f"{model_info.display_name} 已加载 ({device_info})"
                    self._update_model_status("ready", message)
                except Exception as e:
                    self._show_snackbar(f"模型加载失败: {e}", ft.Colors.ERROR)
                    self._reset_ui()
                    return
            else:
                self._update_progress("模型已加载，开始处理...", 0.0)
            
            # 处理每个文件
            total_files = len(self.selected_files)
            for i, file_path in enumerate(self.selected_files):
                if not self.is_processing:
                    break
                
                self.current_file_text.value = f"正在处理: {file_path.name} ({i+1}/{total_files})"
                self.current_file_text.update()
                
                try:
                    # 如果是保存到源文件目录，使用文件所在目录
                    if self.output_mode_radio.value == "source":
                        current_output_dir = file_path.parent
                    else:
                        current_output_dir = output_dir
                    
                    def progress_callback(message: str, progress: float):
                        if self.is_processing:
                            overall_progress = (i + progress) / total_files
                            self._update_progress(message, overall_progress)
                    
                    # 获取输出设置
                    format_value = self.output_format_dropdown.value
                    # 如果选择跟随原文件，则使用原始文件的扩展名
                    if format_value == "original":
                        original_ext = file_path.suffix.lower().lstrip('.')
                        # 映射常见格式
                        format_map = {
                            'mp3': 'mp3',
                            'wav': 'wav',
                            'flac': 'flac',
                            'ogg': 'ogg',
                            'm4a': 'mp3',  # m4a转为mp3
                            'wma': 'wav',  # wma转为wav
                        }
                        output_format = format_map.get(original_ext, 'wav')
                    else:
                        output_format = format_value
                    
                    sample_rate_value = self.sample_rate_dropdown.value
                    output_sample_rate = None if sample_rate_value == "original" else int(sample_rate_value)
                    
                    # 获取比特率/质量设置（保持字符串格式，让服务层处理）
                    mp3_bitrate = self.mp3_bitrate_dropdown.value
                    ogg_quality_value = self.ogg_quality_dropdown.value
                    # 如果不是"original"，转换为整数
                    ogg_quality = ogg_quality_value if ogg_quality_value == "original" else int(ogg_quality_value)
                    
                    vocals_path, instrumental_path = self.vocal_service.separate(
                        file_path,
                        current_output_dir,
                        progress_callback,
                        output_format=output_format,
                        output_sample_rate=output_sample_rate,
                        mp3_bitrate=mp3_bitrate,
                        ogg_quality=ogg_quality
                    )
                    
                    # 验证输出文件是否存在
                    if not vocals_path.exists() and not instrumental_path.exists():
                        raise RuntimeError("输出文件未成功创建")
                    
                    # 根据用户选择删除不需要的输出
                    if not self.output_vocals_checkbox.value and vocals_path.exists():
                        vocals_path.unlink()
                    if not self.output_instrumental_checkbox.value and instrumental_path.exists():
                        instrumental_path.unlink()
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    logger.error(f"处理文件失败: {file_path.name}")
                    logger.error(error_detail)
                    self._show_snackbar(f"处理 {file_path.name} 失败: {e}", ft.Colors.ERROR)
                    continue
            
            if self.is_processing:
                self._update_progress("处理完成!", 1.0)
                self._show_snackbar(f"成功处理 {total_files} 个文件", ft.Colors.GREEN)
            
        except Exception as e:
            self._show_snackbar(f"处理失败: {e}", ft.Colors.ERROR)
        finally:
            self._reset_ui()
    
    def _update_progress(self, message: str, progress: float) -> None:
        """更新进度显示。"""
        self.progress_text.value = message
        self.progress_bar.value = progress
        self.progress_text.update()
        self.progress_bar.update()
    
    def _reset_ui(self) -> None:
        """重置UI状态。"""
        self.is_processing = False
        self.process_button.content.disabled = False
        self.cancel_button.visible = False
        self.progress_bar.visible = False
        self.progress_text.visible = False
        self.current_file_text.visible = False
        self._page.update()
    
    def _show_snackbar(self, message: str, bgcolor: str) -> None:
        """显示提示消息。"""
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=bgcolor,
        )
        self._page.snack_bar.open = True
        self._page.update()
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择变化事件。"""
        self._init_model_status()
        if self.auto_load_model:
            self._try_auto_load_model()
    
    def _init_model_status(self) -> None:
        """初始化模型状态（不调用 update）。"""
        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename
        
        # 更新模型信息显示
        self.model_info_text.value = f"质量: {model_info.quality} | 特点: {model_info.performance}"
        model_exists = model_path.exists()
        if model_exists:
            if self.vocal_service.current_model == model_info.filename and self.model_loaded:
                message = f"{model_info.display_name} 已加载 ({model_info.size_mb}MB)"
                self._update_model_status("ready", message)
            else:
                message = f"{model_info.display_name} 已下载 ({model_info.size_mb}MB)"
                self._update_model_status("unloaded", message)
        else:
            message = f"{model_info.display_name} 未下载 (需下载 {model_info.size_mb}MB)"
            self._update_model_status("need_download", message)

    def _try_auto_load_model(self) -> None:
        """尝试自动加载已下载的模型。"""
        if not self.auto_load_model or self.model_loading:
            return

        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename

        if not model_path.exists():
            return

        if self.vocal_service.current_model == model_info.filename and self.model_loaded:
            return

        self.model_loading = True
        self._update_model_status("loading", "自动加载模型...")

        def load_thread():
            try:
                self.vocal_service.load_model(
                    model_path,
                    invert_output=model_info.invert_output
                )
                device_info = self.vocal_service.get_device_info()
                message = f"{model_info.display_name} 已加载 ({device_info})"
                self._update_model_status("ready", message)
            except Exception as exc:
                self._update_model_status("error", f"自动加载失败: {exc}")
                self._show_snackbar(f"自动加载模型失败: {exc}", ft.Colors.ERROR)
            finally:
                self.model_loading = False

        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()

    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载复选框变化事件。"""
        self.auto_load_model = bool(e.control.value)
        self.config_service.set_config_value("vocal_auto_load_model", self.auto_load_model)
        if self.auto_load_model:
            self._try_auto_load_model()
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态图标和按钮显示。"""
        if status == "loading":
            self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "ready":
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = True
            self.delete_model_button.visible = True
        elif status == "unloaded":
            self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.model_status_icon.color = ft.Colors.GREY
            self.download_model_button.visible = False
            self.load_model_button.visible = True
            self.unload_model_button.visible = False
            self.delete_model_button.visible = True
        elif status == "need_download":
            self.model_status_icon.name = ft.Icons.WARNING
            self.model_status_icon.color = ft.Colors.ORANGE
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "error":
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.RED
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        else:
            self.model_status_icon.name = ft.Icons.HELP_OUTLINE
            self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False

        self.model_status_text.value = message
        self.model_loaded = (status == "ready")
        try:
            self.model_status_icon.update()
            self.model_status_text.update()
            self.download_model_button.update()
            self.load_model_button.update()
            self.unload_model_button.update()
            self.delete_model_button.update()
        except:
            pass
    
    def _on_download_model(self, e: ft.ControlEvent) -> None:
        """下载模型按钮点击事件。"""
        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        
        # 禁用按钮和模型选择
        self.download_model_button.disabled = True
        self.download_model_button.text = "下载中..."
        self.download_model_button.update()
        self.model_dropdown.disabled = True
        self.model_dropdown.update()
        
        # 显示进度条
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self.progress_text.value = "正在连接服务器..."
        self.progress_bar.update()
        self.progress_text.update()
        
        def download_thread():
            try:
                # 下载回调
                def progress_callback(progress: float, message: str):
                    self.progress_bar.value = progress
                    self.progress_text.value = message
                    self.progress_bar.update()
                    self.progress_text.update()
                
                # 下载模型
                model_path = self.vocal_service.download_model(
                    model_key,
                    model_info,
                    progress_callback
                )
                
                # 更新模型状态
                self._init_model_status()
                if self.auto_load_model:
                    self._try_auto_load_model()
                self._show_snackbar("模型下载成功!", ft.Colors.GREEN)
                
                # 隐藏进度条
                import time
                time.sleep(1)
                self.progress_bar.visible = False
                self.progress_text.visible = False
                self.progress_bar.update()
                self.progress_text.update()
                
            except Exception as ex:
                self._show_snackbar(f"模型下载失败: {ex}", ft.Colors.ERROR)
                self.progress_bar.visible = False
                self.progress_text.visible = False
                self.progress_bar.update()
                self.progress_text.update()
            
            finally:
                # 恢复按钮和下拉框状态
                self.download_model_button.disabled = False
                self.download_model_button.text = "下载模型"
                self.download_model_button.update()
                self.model_dropdown.disabled = False
                self.model_dropdown.update()
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _on_load_model_click(self, e: ft.ControlEvent) -> None:
        """加载模型按钮点击事件。"""
        if self.model_loading or self.model_loaded:
            return

        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename

        if not model_path.exists():
            self._show_snackbar("请先下载模型", ft.Colors.ERROR)
            return

        self.model_loading = True
        self._update_model_status("loading", "正在加载模型...")

        def load_thread():
            try:
                self.vocal_service.load_model(
                    model_path,
                    invert_output=model_info.invert_output
                )
                device_info = self.vocal_service.get_device_info()
                message = f"{model_info.display_name} 已加载 ({device_info})"
                self._update_model_status("ready", message)
                self._show_snackbar(f"模型加载完成，使用: {device_info}", ft.Colors.GREEN)
            except Exception as exc:
                self._update_model_status("error", f"加载失败: {exc}")
                self._show_snackbar(f"模型加载失败: {exc}", ft.Colors.ERROR)
            finally:
                self.model_loading = False

        threading.Thread(target=load_thread, daemon=True).start()

    def _on_unload_model_click(self, e: ft.ControlEvent) -> None:
        """卸载模型按钮点击事件。"""
        if not self.model_loaded:
            return

        self.vocal_service.unload_model()
        self._init_model_status()
        self._show_snackbar("模型已卸载", ft.Colors.GREEN)
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename
        
        def on_confirm(confirmed: bool):
            if confirmed and model_path.exists():
                try:
                    model_path.unlink()
                    self._init_model_status()
                    if self.auto_load_model:
                        self._try_auto_load_model()
                    self._show_snackbar("模型已删除", ft.Colors.GREEN)
                except Exception as ex:
                    self._show_snackbar(f"删除失败: {ex}", ft.Colors.ERROR)
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除模型 {model_info.display_name} 吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: setattr(dialog, 'open', False) or self._page.update()),
                ft.TextButton(
                    "删除",
                    on_click=lambda _: (
                        on_confirm(True),
                        setattr(dialog, 'open', False),
                        self._page.update()
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = e.control.value
        is_custom = mode == "custom"
        
        self.output_dir_field.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        self.output_dir_field.update()
        self.browse_output_button.update()
    
    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式变化事件。"""
        format_value = e.control.value
        
        # 根据格式显示/隐藏对应的质量设置
        # 如果是"跟随原文件"，则隐藏所有质量设置
        if format_value == "original":
            self.mp3_bitrate_dropdown.visible = False
            self.ogg_quality_dropdown.visible = False
        else:
            self.mp3_bitrate_dropdown.visible = (format_value == "mp3")
            self.ogg_quality_dropdown.visible = (format_value == "ogg")
        
        self.mp3_bitrate_dropdown.update()
        self.ogg_quality_dropdown.update()
    
    async def _on_browse_output(self) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.output_dir_field.value = folder_path
            self.output_dir_field.update()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
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
            self._page.overlay.append(snackbar)
            snackbar.open = True
        elif skipped_count > 0:
            snackbar = ft.SnackBar(content=ft.Text("人声分离不支持该格式"), bgcolor=ft.Colors.ORANGE)
            self._page.overlay.append(snackbar)
            snackbar.open = True
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载人声分离模型
            if self.vocal_service:
                self.vocal_service.unload_model()
            
            # 2. 清空文件列表
            if self.selected_files:
                self.selected_files.clear()
            
            # 3. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 4. 清除 UI 内容
            self.content = None
            
            # 5. 强制垃圾回收
            gc.collect()
            
            logger.info("人声提取视图资源已清理")
        except Exception as e:
            logger.warning(f"清理人声提取视图资源时出错: {e}")