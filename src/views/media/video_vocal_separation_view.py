# -*- coding: utf-8 -*-
"""视频人声分离视图模块。

提供视频人声/背景音处理功能的用户界面。
"""

import threading
import tempfile
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
from views.media.ffmpeg_install_view import FFmpegInstallView
from utils import format_file_size, logger


class VideoVocalSeparationView(ft.Container):
    """视频人声分离视图类。
    
    提供视频人声/背景音处理功能，包括：
    - 单文件处理
    - 批量处理
    - 保留人声/保留背景音
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频人声分离视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
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
                self.page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="视频人声分离"
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
                ft.Text("视频人声分离", size=28, weight=ft.FontWeight.BOLD),
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
        
        # 文件选择器
        self.file_picker = ft.FilePicker(
            on_result=self._on_files_selected
        )
        self.page.overlay.append(self.file_picker)
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择视频:", size=14, weight=ft.FontWeight.W_500),
                        ft.ElevatedButton(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=lambda _: self._on_select_files(),
                        ),
                        ft.ElevatedButton(
                            "选择文件夹",
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda _: self._on_select_folder(),
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
                                "支持格式: MP4, AVI, MKV, MOV, FLV, WMV, WEBM 等",
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
            on_change=self._on_model_change,
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
        self.download_model_button = ft.ElevatedButton(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_model,
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
                self.delete_model_button,
            ],
            spacing=PADDING_SMALL,
        )
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    self.model_dropdown,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 初始化模型状态
        self._init_model_status()
        
        # 输出设置区域
        # 音频模式选择
        self.audio_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="vocals", label="仅保留人声"),
                    ft.Radio(value="instrumental", label="仅保留背景音"),
                    ft.Radio(value="both", label="输出两个版本（人声+背景音）"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="vocals",
        )
        
        # 视频编码设置
        self.video_codec_dropdown = ft.Dropdown(
            label="视频编码",
            options=[
                ft.dropdown.Option(key="copy", text="复制视频流 (最快，推荐)"),
                ft.dropdown.Option(key="h264", text="H.264 (兼容性最好)"),
                ft.dropdown.Option(key="h265", text="H.265/HEVC (体积更小)"),
            ],
            value="copy",
            width=300,
            dense=True,
            text_size=13,
        )
        
        # 音频格式设置
        self.audio_codec_dropdown = ft.Dropdown(
            label="音频编码",
            options=[
                ft.dropdown.Option(key="aac", text="AAC (推荐)"),
                ft.dropdown.Option(key="mp3", text="MP3"),
                ft.dropdown.Option(key="opus", text="Opus (高质量)"),
            ],
            value="aac",
            width=300,
            dense=True,
            text_size=13,
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
        default_output = self.config_service.get_output_dir() / "video_vocal_separation"
        
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
            on_click=self._on_browse_output,
            disabled=True,  # 默认禁用
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("音频模式:", size=13),
                    self.audio_mode_radio,
                    ft.Container(height=PADDING_SMALL // 2),
                    ft.Row(
                        controls=[
                            self.video_codec_dropdown,
                            self.audio_codec_dropdown,
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
        
        # 底部大按钮
        self.process_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_LIBRARY, size=24),
                        ft.Text("开始处理", size=18, weight=ft.FontWeight.W_600),
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
            alignment=ft.alignment.center,
        )
        
        # 取消按钮
        self.cancel_button = ft.ElevatedButton(
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
                        ft.Icon(ft.Icons.VIDEO_FILE, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "未选择文件",
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "点击此处选择视频文件",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL // 2,
                ),
                height=188,
                alignment=ft.alignment.center,
                on_click=self._on_empty_area_click,
                ink=True,
                tooltip="点击选择视频文件",
            )
        )
    
    def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        self._on_select_files()
    
    def _on_select_files(self) -> None:
        """选择文件按钮点击事件。"""
        self.file_picker.pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v", "mpg", "mpeg"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self) -> None:
        """选择文件夹按钮点击事件。"""
        self.file_picker.get_directory_path(
            dialog_title="选择包含视频的文件夹"
        )
    
    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择完成事件。"""
        if e.files:
            for file in e.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
        elif e.path:
            folder_path = Path(e.path)
            video_extensions = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg"}
            for file_path in folder_path.rglob("*"):
                if file_path.suffix.lower() in video_extensions and file_path not in self.selected_files:
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
                    ft.Icon(ft.Icons.VIDEO_FILE, size=20),
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
        
        # 开始处理
        self.is_processing = True
        self.process_button.content.disabled = True
        self.cancel_button.visible = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.current_file_text.visible = True
        
        self.page.update()
        
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
            
            self._update_progress("正在加载模型...", 0.0)
            
            try:
                self.vocal_service.load_model(
                    model_path, 
                    invert_output=model_info.invert_output
                )
                device_info = self.vocal_service.get_device_info()
                logger.info(f"视频人声分离模型已加载，使用: {device_info}")
            except Exception as e:
                self._show_snackbar(f"模型加载失败: {e}", ft.Colors.ERROR)
                self._reset_ui()
                return
            
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
                    
                    # 处理视频
                    self._process_single_video(
                        file_path,
                        current_output_dir,
                        progress_callback
                    )
                    
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
    
    def _process_single_video(
        self,
        video_path: Path,
        output_dir: Path,
        progress_callback: Callable[[str, float], None]
    ) -> None:
        """处理单个视频文件。
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            progress_callback: 进度回调函数
        """
        import ffmpeg
        
        # 先检测视频是否有音频流
        ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
        if not ffprobe_path:
            raise RuntimeError("未找到 FFprobe")
        
        try:
            probe = ffmpeg.probe(str(video_path), cmd=ffprobe_path)
            has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
            if not has_audio:
                raise RuntimeError("视频文件不包含音频流，无法进行人声分离")
        except ffmpeg.Error as e:
            raise RuntimeError(f"无法读取视频信息: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. 提取音频
            progress_callback("提取音频...", 0.1)
            audio_file = temp_path / "audio.wav"
            
            try:
                stream = ffmpeg.input(str(video_path))
                stream = ffmpeg.output(stream, str(audio_file), acodec='pcm_s16le', ac=2, ar=44100)
                ffmpeg.run(
                    stream,
                    cmd=self.ffmpeg_service.get_ffmpeg_path(),
                    overwrite_output=True,
                    capture_stdout=True,
                    capture_stderr=True,
                    quiet=True
                )
            except ffmpeg.Error as e:
                raise RuntimeError(f"提取音频失败: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
            
            # 2. 分离人声
            progress_callback("分离人声...", 0.2)
            
            def vocal_progress_callback(message: str, progress: float):
                # 将 0.2-0.8 的进度映射到人声分离
                overall_progress = 0.2 + progress * 0.6
                progress_callback(f"分离人声: {message}", overall_progress)
            
            vocals_path, instrumental_path = self.vocal_service.separate(
                audio_file,
                temp_path,
                vocal_progress_callback,
                output_format='wav',
                output_sample_rate=None,
            )
            
            # 3. 根据用户选择合并视频
            progress_callback("合并视频...", 0.85)
            
            audio_mode = self.audio_mode_radio.value
            video_codec = self.video_codec_dropdown.value
            audio_codec = self.audio_codec_dropdown.value
            
            # 生成输出文件名
            stem = video_path.stem
            ext = video_path.suffix
            
            if audio_mode == "vocals":
                # 仅保留人声
                output_path = output_dir / f"{stem}_vocals{ext}"
                self._merge_video_audio(
                    video_path,
                    vocals_path,
                    output_path,
                    video_codec,
                    audio_codec
                )
            elif audio_mode == "instrumental":
                # 仅保留背景音
                output_path = output_dir / f"{stem}_instrumental{ext}"
                self._merge_video_audio(
                    video_path,
                    instrumental_path,
                    output_path,
                    video_codec,
                    audio_codec
                )
            else:  # both
                # 输出两个版本
                vocals_output = output_dir / f"{stem}_vocals{ext}"
                instrumental_output = output_dir / f"{stem}_instrumental{ext}"
                
                self._merge_video_audio(
                    video_path,
                    vocals_path,
                    vocals_output,
                    video_codec,
                    audio_codec
                )
                
                self._merge_video_audio(
                    video_path,
                    instrumental_path,
                    instrumental_output,
                    video_codec,
                    audio_codec
                )
            
            progress_callback("完成!", 1.0)
    
    def _merge_video_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        video_codec: str,
        audio_codec: str
    ) -> None:
        """合并视频和音频。
        
        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_path: 输出文件路径
            video_codec: 视频编码器
            audio_codec: 音频编码器
        """
        import ffmpeg
        
        try:
            # 读取视频和音频流
            video_stream = ffmpeg.input(str(video_path))
            audio_stream = ffmpeg.input(str(audio_path))
            
            # 视频编码设置
            if video_codec == "copy":
                v_codec = "copy"
            elif video_codec == "h264":
                v_codec = "libx264"
            elif video_codec == "h265":
                v_codec = "libx265"
            else:
                v_codec = "copy"
            
            # 音频编码设置
            if audio_codec == "aac":
                a_codec = "aac"
                audio_bitrate = "192k"
            elif audio_codec == "mp3":
                a_codec = "libmp3lame"
                audio_bitrate = "192k"
            elif audio_codec == "opus":
                a_codec = "libopus"
                audio_bitrate = "128k"
            else:
                a_codec = "aac"
                audio_bitrate = "192k"
            
            # 合并视频和音频
            output_kwargs = {
                'vcodec': v_codec,
                'acodec': a_codec,
            }
            
            # 如果不是复制音频，设置比特率
            if audio_codec != "copy":
                output_kwargs['audio_bitrate'] = audio_bitrate
            
            stream = ffmpeg.output(
                video_stream.video,
                audio_stream.audio,
                str(output_path),
                **output_kwargs
            )
            
            ffmpeg.run(
                stream,
                cmd=self.ffmpeg_service.get_ffmpeg_path(),
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
                quiet=True
            )
            
        except ffmpeg.Error as e:
            raise RuntimeError(f"合并视频失败: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else str(e)}")
    
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
        self.page.update()
    
    def _show_snackbar(self, message: str, bgcolor: str) -> None:
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=bgcolor,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _on_model_change(self, e: ft.ControlEvent) -> None:
        """模型选择变化事件。"""
        self._update_model_status()
    
    def _init_model_status(self) -> None:
        """初始化模型状态（不调用 update）。"""
        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename
        
        # 更新模型信息显示
        self.model_info_text.value = f"质量: {model_info.quality} | 特点: {model_info.performance}"
        
        if model_path.exists():
            # 模型已下载
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            file_size = model_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            self.model_status_text.value = f"已下载 ({size_mb:.1f}MB)"
            self.download_model_button.visible = False
            self.delete_model_button.visible = True
        else:
            # 模型未下载
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = f"未下载 (需下载 {model_info.size_mb}MB)"
            self.download_model_button.visible = True
            self.delete_model_button.visible = False
    
    def _update_model_status(self) -> None:
        """更新模型状态显示（已添加到页面后调用）。"""
        self._init_model_status()
        
        # 只有在已添加到页面后才调用 update
        try:
            self.model_info_text.update()
            self.model_status_icon.update()
            self.model_status_text.update()
            self.download_model_button.update()
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
                self._update_model_status()
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
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        model_key = self.model_dropdown.value
        model_info = VOCAL_SEPARATION_MODELS[model_key]
        model_path = self.vocal_service.model_dir / model_info.filename
        
        def on_confirm(confirmed: bool):
            if confirmed and model_path.exists():
                try:
                    model_path.unlink()
                    self._update_model_status()
                    self._show_snackbar("模型已删除", ft.Colors.GREEN)
                except Exception as ex:
                    self._show_snackbar(f"删除失败: {ex}", ft.Colors.ERROR)
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除模型 {model_info.display_name} 吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: setattr(dialog, 'open', False) or self.page.update()),
                ft.TextButton(
                    "删除",
                    on_click=lambda _: (
                        on_confirm(True),
                        setattr(dialog, 'open', False),
                        self.page.update()
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = e.control.value
        is_custom = mode == "custom"
        
        self.output_dir_field.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        self.output_dir_field.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent):
            if result.path:
                self.output_dir_field.value = result.path
                self.output_dir_field.update()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()

