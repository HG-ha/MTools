# -*- coding: utf-8 -*-
"""视频格式转换视图模块。

提供视频格式转换功能的用户界面。
"""

import threading
from pathlib import Path
from typing import List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_LARGE,
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, FFmpegService
from utils import format_file_size, logger, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoConvertView(ft.Container):
    """视频格式转换视图类。
    
    提供视频格式转换功能，支持多种常见格式之间的转换。"""
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'}
    
    """
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: callable,
    ) -> None:
        """初始化视频格式转换视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            ffmpeg_service: FFmpeg服务实例
            on_back: 返回回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: callable = on_back
        
        self.expand: bool = True
        
        # 状态变量
        self.selected_files: List[Path] = []
        self.is_converting: bool = False
        
        # 创建UI组件
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
                on_back=lambda e=None: self.on_back() if self.on_back else None
            )
            return
        
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda e: self.on_back(),
                ),
                ft.Text("视频格式转换", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件列表视图
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("选择视频:", size=14, weight=ft.FontWeight.W_500),
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
                                    "支持格式: MP4, AVI, MKV, MOV, FLV, WMV, WebM, M4V, MPG, MPEG, TS 等",
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
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        padding=PADDING_MEDIUM,
                        height=280,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 格式选择
        self.format_dropdown = ft.Dropdown(
            label="输出格式",
            options=[
                ft.dropdown.Option("mp4", "MP4 - 最常用的视频格式 (推荐)"),
                ft.dropdown.Option("mkv", "MKV - 多媒体容器格式"),
                ft.dropdown.Option("avi", "AVI - 经典视频格式"),
                ft.dropdown.Option("mov", "MOV - QuickTime格式"),
                ft.dropdown.Option("webm", "WebM - 网页视频格式"),
                ft.dropdown.Option("flv", "FLV - Flash视频格式"),
                ft.dropdown.Option("m4v", "M4V - iTunes视频格式"),
            ],
            value="mp4",
            width=350,
        )
        
        # 输出选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（原文件旁）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "video_converted"),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        self.output_custom_path: Optional[Path] = None
        
        format_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出格式:", size=14, weight=ft.FontWeight.W_500),
                    self.format_dropdown,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,
            height=280,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
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
            expand=1,
            height=280,
        )
        
        # 转换选项开关
        self.reencode_switch = ft.Switch(
            label="重新编码 (默认仅改变容器格式)",
            value=False,
            tooltip="关闭时仅改变容器格式,速度快;开启时重新编码,可选择编码器",
        )
        
        # 检测GPU编码器并设置默认值（会检查配置开关）
        gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
        default_vcodec = "libx264"
        if gpu_encoder:
            default_vcodec = gpu_encoder
        
        # 构建视频编码器选项
        video_encoder_options = [
            ft.dropdown.Option("libx264", "H.264 (libx264) - 广泛兼容 (推荐)"),
            ft.dropdown.Option("libx265", "H.265 (libx265) - 更高压缩率"),
            ft.dropdown.Option("libvpx-vp9", "VP9 (libvpx-vp9) - 开源编码"),
            ft.dropdown.Option("libaom-av1", "AV1 (libaom-av1) - 下一代编码"),
        ]
        
        # 添加GPU编码器选项（如果硬件可用，总是显示，但默认值会根据GPU开关设置）
        gpu_info = self.ffmpeg_service.detect_gpu_encoders()
        if gpu_info.get("available"):
            encoders = gpu_info.get("encoders", [])
            if "h264_nvenc" in encoders:
                video_encoder_options.append(ft.dropdown.Option("h264_nvenc", "H.264 (NVENC) - NVIDIA加速 ⚡"))
            if "hevc_nvenc" in encoders:
                video_encoder_options.append(ft.dropdown.Option("hevc_nvenc", "H.265 (NVENC) - NVIDIA加速 ⚡"))
            if "h264_amf" in encoders:
                video_encoder_options.append(ft.dropdown.Option("h264_amf", "H.264 (AMF) - AMD加速 ⚡"))
            if "hevc_amf" in encoders:
                video_encoder_options.append(ft.dropdown.Option("hevc_amf", "H.265 (AMF) - AMD加速 ⚡"))
            if "av1_amf" in encoders:
                video_encoder_options.append(ft.dropdown.Option("av1_amf", "AV1 (AMF) - AMD加速 ⚡"))
            if "h264_qsv" in encoders:
                video_encoder_options.append(ft.dropdown.Option("h264_qsv", "H.264 (QSV) - Intel加速 ⚡"))
            if "hevc_qsv" in encoders:
                video_encoder_options.append(ft.dropdown.Option("hevc_qsv", "H.265 (QSV) - Intel加速 ⚡"))
        
        self.video_codec_dropdown = ft.Dropdown(
            label="视频编码器",
            options=video_encoder_options,
            value=default_vcodec,
            width=300,
            disabled=True,
        )
        
        self.audio_codec_dropdown = ft.Dropdown(
            label="音频编码器",
            options=[
                ft.dropdown.Option("copy", "保留原始音频"),
                ft.dropdown.Option("aac", "AAC - 推荐"),
                ft.dropdown.Option("mp3", "MP3 - 兼容性好"),
                ft.dropdown.Option("libvorbis", "Vorbis - 开源编码"),
                ft.dropdown.Option("libopus", "Opus - 高质量"),
            ],
            value="copy",
            width=300,
            disabled=True,
        )
        
        # 重新编码开关事件处理
        def on_reencode_changed(e):
            need_reencode = self.reencode_switch.value
            self.video_codec_dropdown.disabled = not need_reencode
            self.audio_codec_dropdown.disabled = not need_reencode
            self._page.update()
        
        self.reencode_switch.on_change = on_reencode_changed
        
        advanced_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("编码选项", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.reencode_switch,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Row(
                        controls=[
                            self.video_codec_dropdown,
                            self.audio_codec_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                        wrap=True,
                    ),
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 转换进度
        self.progress_bar = ft.ProgressBar(
            value=0,
            bar_height=8,
            visible=False,
        )
        
        self.progress_text = ft.Text(
            "",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        self.speed_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        progress_section = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.progress_text,
                            self.speed_text,
                        ],
                        spacing=PADDING_LARGE,
                    ),
                ],
                spacing=0,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        
        self.progress_section = progress_section
        
        # 转换按钮
        self.convert_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TRANSFORM, size=24),
                        ft.Text("开始转换", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._start_convert,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 可滚动内容
        scrollable_content = ft.Column(
            controls=[
                file_section,
                ft.Container(height=PADDING_LARGE),
                ft.Row(
                    controls=[
                        format_section,
                        output_section,
                    ],
                    spacing=PADDING_LARGE,
                ),
                ft.Container(height=PADDING_LARGE),
                advanced_section,
                ft.Container(height=PADDING_MEDIUM),
                progress_section,
                ft.Container(height=PADDING_MEDIUM),
                self.convert_button,
                ft.Container(height=PADDING_LARGE),
            ],
            scroll=ft.ScrollMode.HIDDEN,
            spacing=0,
            expand=True,
        )
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
            expand=True,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM,
        )
        
        # 初始化文件列表空状态
        self._update_file_list()
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["mp4", "avi", "mkv", "mov", "flv", "wmv", "webm", "m4v", "mpg", "mpeg", "ts", "mts", "m2ts"],
            dialog_title="选择视频文件",
            allow_multiple=True,
        )
        if result and result.files:
            for file in result.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            
            self._update_file_list()
            self._update_convert_button()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择包含视频的文件夹")
        if result:
            folder_path = Path(result)
            video_extensions = {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts"}
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            
            self._update_file_list()
            self._update_convert_button()
            
            if self.selected_files:
                self._show_success(f"已添加 {len(self.selected_files)} 个视频文件")
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
        self._update_convert_button()
    
    def _on_remove_file(self, index: int) -> None:
        """移除单个文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
            self._update_convert_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
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
                        alignment=ft.Alignment.CENTER,
                        height=250,  # 固定高度以确保填满显示区域
                        on_click=self._on_select_files,
                        tooltip="点击选择视频文件",
                        ink=True,
                    )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                # 获取文件大小
                try:
                    file_size = file_path.stat().st_size
                    size_str = format_file_size(file_size)
                except Exception:
                    size_str = "未知大小"
                
                # 获取文件扩展名
                ext = file_path.suffix.upper().replace(".", "")
                
                file_item = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.VIDEO_FILE, size=20, color=ft.Colors.PRIMARY),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        file_path.name,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(f"{ext} · {size_str}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
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
    
    def _update_convert_button(self) -> None:
        """更新转换按钮状态。"""
        self.convert_button.content.disabled = not self.selected_files
        try:
            self.convert_button.update()
        except:
            pass
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        is_custom = self.output_mode_radio.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        try:
            self.custom_output_dir.update()
            self.browse_output_button.update()
        except:
            pass
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if result:
            self.custom_output_dir.value = result
            self.output_custom_path = Path(result)
            try:
                self.custom_output_dir.update()
            except:
                pass
    
    def _start_convert(self, e: ft.ControlEvent) -> None:
        """开始转换。"""
        if not self.selected_files:
            self._show_error("请先选择视频文件")
            return
        
        if self.is_converting:
            self._show_error("正在转换中，请稍候")
            return
        
        # 获取输出格式
        output_format = self.format_dropdown.value
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.custom_output_dir.value)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = None  # 保存在原文件旁边
        
        # 禁用按钮
        self.convert_button.content.disabled = True
        self.is_converting = True
        
        # 显示进度区域
        self.progress_section.visible = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.speed_text.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备转换..."
        self.speed_text.value = ""
        self._page.update()
        
        # 启动异步转换任务
        async def convert_task():
            import asyncio
            total_files = len(self.selected_files)
            success_count = 0
            
            try:
                # 构建参数
                params = {
                    "output_format": output_format,
                    "mode": "simple",  # 简单模式
                }
                
                # 根据重新编码选项设置编解码器
                if self.reencode_switch.value:
                    # 重新编码
                    params["vcodec"] = self.video_codec_dropdown.value
                    params["acodec"] = self.audio_codec_dropdown.value
                else:
                    # 仅封装格式转换(默认)
                    params["vcodec"] = "copy"
                    params["acodec"] = "copy"
                
                # 处理每个文件
                for i, input_file in enumerate(self.selected_files):
                    try:
                        # 更新进度
                        overall_progress = i / total_files
                        self.progress_bar.value = overall_progress
                        self.progress_text.value = f"正在转换: {input_file.name} ({i+1}/{total_files})"
                        self.speed_text.value = ""
                        self._page.update()
                        
                        # 构建输出路径
                        if output_dir:
                            output_path = output_dir / f"{input_file.stem}.{output_format}"
                        else:
                            output_path = input_file.parent / f"{input_file.stem}.{output_format}"
                        
                        # 根据全局设置决定是否添加序号
                        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                        output_path = get_unique_path(output_path, add_sequence=add_sequence)
                        
                        # 执行转换 - 进度回调通过 run_task 安全地更新UI
                        def progress_callback(progress: float, speed: str, remaining: str, _i=i, _input_file=input_file):
                            # 计算总体进度
                            file_progress = (_i + progress) / total_files
                            async def _update_progress():
                                self.progress_bar.value = file_progress
                                self.progress_text.value = f"转换中: {_input_file.name} ({_i+1}/{total_files}) - {int(progress * 100)}%"
                                self.speed_text.value = f"速度: {speed} | 剩余: {remaining}"
                                self._page.update()
                            try:
                                self._page.run_task(_update_progress)
                            except Exception:
                                pass
                        
                        success, message = await asyncio.to_thread(
                            self._convert_video,
                            input_file,
                            output_path,
                            params,
                            progress_callback,
                        )
                        
                        if success:
                            success_count += 1
                        else:
                            logger.error(f"转换失败 {input_file.name}: {message}")
                    
                    except Exception as ex:
                        logger.error(f"处理失败 {input_file.name}: {ex}")
                
                # 更新UI
                self.is_converting = False
                self.convert_button.content.disabled = False
                
                self.progress_bar.value = 1.0
                self.progress_text.value = f"转换完成! 成功: {success_count}/{total_files}"
                
                if output_dir:
                    self.speed_text.value = f"输出: {output_dir}"
                    self._show_success(f"转换完成! 成功处理 {success_count} 个文件，保存到: {output_dir}")
                else:
                    self.speed_text.value = "输出: 原文件同目录"
                    self._show_success(f"转换完成! 成功处理 {success_count} 个文件，保存在原文件旁边")
                
                self._page.update()
                
            except Exception as ex:
                self.is_converting = False
                self.convert_button.content.disabled = False
                self.progress_bar.value = 0
                self.progress_text.value = "转换失败"
                self.speed_text.value = ""
                self._show_error(f"转换失败: {str(ex)}")
                self._page.update()
        
        self._page.run_task(convert_task)
    
    def _convert_video(
        self,
        input_path: Path,
        output_path: Path,
        params: dict,
        progress_callback: Optional[callable] = None,
    ) -> tuple[bool, str]:
        """执行视频转换。
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            params: 转换参数
            progress_callback: 进度回调函数 (progress, speed, remaining_time)
        
        Returns:
            (是否成功, 消息)
        """
        import ffmpeg
        
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        if not ffmpeg_path:
            return False, "未找到 FFmpeg"
        
        ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
        if not ffprobe_path:
            return False, "未找到 FFprobe"
        
        try:
            # 检测视频是否有音频流
            probe = ffmpeg.probe(str(input_path), cmd=ffprobe_path)
            has_audio = any(stream['codec_type'] == 'audio' for stream in probe['streams'])
            
            # 获取视频时长用于进度显示
            duration = self.ffmpeg_service.get_video_duration(input_path)
            
            # 构建ffmpeg命令
            stream = ffmpeg.input(str(input_path))
            
            output_params = {}
            
            # 视频编码器
            vcodec = params.get("vcodec", "copy")
            if vcodec == "copy":
                output_params['vcodec'] = 'copy'
            else:
                output_params['vcodec'] = vcodec
                # 根据编码器类型设置不同的参数
                if vcodec in ["libx264", "libx265"]:
                    # CPU编码器 - 使用CRF和preset
                    output_params['crf'] = 23
                    output_params['preset'] = 'medium'
                    output_params['pix_fmt'] = 'yuv420p'
                elif vcodec.startswith("h264_nvenc") or vcodec.startswith("hevc_nvenc"):
                    # NVIDIA GPU编码器
                    output_params['preset'] = 'p4'  # 平衡预设
                    output_params['cq'] = 23  # 质量参数(类似CRF)
                    output_params['pix_fmt'] = 'yuv420p'
                elif vcodec.startswith("h264_amf") or vcodec.startswith("hevc_amf") or vcodec.startswith("av1_amf"):
                    # AMD GPU编码器
                    output_params['quality'] = 'balanced'
                    output_params['rc'] = 'vbr_peak'
                    output_params['qmin'] = 18
                    output_params['qmax'] = 28
                elif vcodec.startswith("h264_qsv") or vcodec.startswith("hevc_qsv"):
                    # Intel QSV编码器
                    output_params['preset'] = 'medium'
                    output_params['global_quality'] = 23
                elif vcodec in ["libvpx-vp9", "libaom-av1"]:
                    # VP9/AV1编码器
                    output_params['crf'] = 30
                    output_params['b:v'] = '0'  # 使用CRF模式
            
            # 音频编码器（仅当视频有音频流时才处理）
            if has_audio:
                acodec = params.get("acodec", "copy")
                if acodec == "copy":
                    output_params['acodec'] = 'copy'
                else:
                    output_params['acodec'] = acodec
                    if acodec != "copy":
                        output_params['b:a'] = '192k'
            # 如果没有音频流，不添加任何音频相关参数（ffmpeg会自动处理）
            
            # 输出格式 - 映射文件扩展名到FFmpeg格式名称
            output_format = params.get("output_format")
            if output_format:
                # 格式名称映射（某些扩展名需要特殊处理）
                format_mapping = {
                    'mkv': 'matroska',
                    'ts': 'mpegts',
                    'mts': 'mpegts',
                    'm2ts': 'mpegts',
                    'mpg': 'mpeg',
                    'mpeg': 'mpeg',
                    'm4v': 'mp4',
                }
                # 使用映射的格式名称，如果没有映射则使用原始值
                ffmpeg_format = format_mapping.get(output_format, output_format)
                output_params['format'] = ffmpeg_format
            
            stream = ffmpeg.output(stream, str(output_path), **output_params)
            
            # 添加全局参数以确保进度输出
            stream = stream.global_args('-stats', '-loglevel', 'info', '-progress', 'pipe:2')
            
            # 运行转换
            process = ffmpeg.run_async(
                stream,
                cmd=ffmpeg_path,
                pipe_stderr=True,
                pipe_stdout=True,
                overwrite_output=True
            )
            
            # 实时读取进度
            stderr_lines = []  # 收集所有stderr输出用于错误报告
            
            if duration > 0 and progress_callback:
                import re
                
                def read_stderr():
                    for line in iter(process.stderr.readline, b''):
                        try:
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            stderr_lines.append(line_str)  # 保存所有输出
                            
                            # 解析时间进度
                            time_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2})\.\d{2}", line_str)
                            speed_match = re.search(r"speed=\s*([\d.]+)x", line_str)
                            
                            if time_match:
                                hours = int(time_match.group(1))
                                minutes = int(time_match.group(2))
                                seconds = int(time_match.group(3))
                                current_time = hours * 3600 + minutes * 60 + seconds
                                
                                progress = min(current_time / duration, 0.99) if duration > 0 else 0
                                
                                speed_str = f"{speed_match.group(1)}x" if speed_match else "N/A"
                                
                                if speed_match and float(speed_match.group(1)) > 0:
                                    remaining_seconds = (duration - current_time) / float(speed_match.group(1))
                                    remaining_time_str = f"{int(remaining_seconds // 60)}m {int(remaining_seconds % 60)}s"
                                else:
                                    remaining_time_str = "计算中..."
                                
                                progress_callback(progress, speed_str, remaining_time_str)
                        except Exception:
                            pass
                    process.stderr.close()
                
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stderr_thread.start()
                
                # 等待进程结束
                process.wait()
                stderr_thread.join(timeout=1)
            else:
                # 没有时长信息或回调时直接等待，但仍收集stderr
                def read_stderr_simple():
                    for line in iter(process.stderr.readline, b''):
                        try:
                            line_str = line.decode('utf-8', errors='ignore').strip()
                            stderr_lines.append(line_str)
                        except Exception:
                            pass
                    process.stderr.close()
                
                stderr_thread = threading.Thread(target=read_stderr_simple, daemon=True)
                stderr_thread.start()
                process.wait()
                stderr_thread.join(timeout=1)
            
            # 检查返回码
            if process.returncode != 0:
                # 获取最后50行错误信息
                error_output = "\n".join(stderr_lines[-50:]) if stderr_lines else "无详细错误信息"
                logger.error(f"FFmpeg转换失败，完整输出:\n{error_output}")
                return False, f"FFmpeg 执行失败，退出码: {process.returncode}\n{error_output}"
            
            return True, "转换成功"
            
        except ffmpeg.Error as e:
            return False, f"FFmpeg 错误: {e.stderr.decode()}"
        except Exception as e:
            return False, f"转换失败: {str(e)}"
    
    def _show_error(self, message: str) -> None:
        """显示错误消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR,
        )
        self._page.open(snackbar)
    
    def _show_success(self, message: str) -> None:
        """显示成功消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.GREEN,
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
            self._show_success(f"已添加 {added_count} 个文件")
        elif skipped_count > 0:
            self._show_error("视频格式转换不支持该格式")
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
