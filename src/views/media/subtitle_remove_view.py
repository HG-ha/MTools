# -*- coding: utf-8 -*-
"""视频字幕/水印移除视图模块。

提供视频字幕/水印移除功能的用户界面。
"""

import tempfile
from pathlib import Path
from typing import Callable, List, Optional

import cv2
import flet as ft
import numpy as np

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_SUBTITLE_REMOVE_MODEL_KEY,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_LARGE,
    SUBTITLE_REMOVE_MODELS,
)
from services import ConfigService, FFmpegService
from services.subtitle_remove_service import SubtitleRemoveService
from views.media.ffmpeg_install_view import FFmpegInstallView
from utils import format_file_size, logger, get_unique_path


class SubtitleRemoveView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    """视频字幕/水印移除视图类。
    
    提供视频字幕/水印移除功能，包括：
    - 单文件/批量处理
    - 自定义遮罩区域
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频字幕/水印移除视图。
        
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
        self.current_model_key: str = DEFAULT_SUBTITLE_REMOVE_MODEL_KEY
        self.file_regions: dict = {}  # 每个文件的区域设置 {file_path: [region_list]}
        self.visual_region: Optional[dict] = None  # 可视化选择的区域（兼容旧代码）
        
        # 处理模式: "ai" = AI修复, "mask" = 遮挡模式
        self.process_mode: str = self.config_service.get_config_value("video_subtitle_process_mode", "ai")
        # 遮挡类型: "blur" = 模糊, "color" = 纯色
        self.mask_type: str = self.config_service.get_config_value("video_subtitle_mask_type", "blur")
        # 遮挡颜色 (RGB)
        self.mask_color: str = self.config_service.get_config_value("video_subtitle_mask_color", "#000000")
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 初始化服务
        model_dir = self.config_service.get_data_dir() / "models" / "subtitle_remove"
        self.subtitle_service: SubtitleRemoveService = SubtitleRemoveService()
        self.model_dir = model_dir
        
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
                tool_name="视频去字幕/水印"
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
                ft.Text("视频去字幕/水印", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
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
                                "支持 MP4、AVI、MOV、MKV 等常见视频格式",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=ft.padding.only(top=PADDING_SMALL),
                ),
                ft.Container(
                    content=self.file_list_view,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                    height=200,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 模型管理区域
        self.model_status_icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_status_text = ft.Text(
            "正在初始化...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_download_btn = ft.Button(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            visible=False,
            on_click=lambda _: self._download_model(),
        )
        
        self.model_load_btn = ft.Button(
            "加载模型",
            icon=ft.Icons.PLAY_ARROW,
            visible=False,
            on_click=lambda _: self._load_model(),
        )
        
        self.model_unload_btn = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            visible=False,
            on_click=lambda _: self._unload_model(),
        )
        
        self.model_delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            visible=False,
            on_click=lambda _: self._delete_model(),
        )
        
        model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.model_download_btn,
                self.model_load_btn,
                self.model_unload_btn,
                self.model_delete_btn,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 模型信息
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        self.model_info_text = ft.Text(
            f"{model_info.quality} | {model_info.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 自动加载模型选项
        auto_load_model = self.config_service.get_config_value("subtitle_remove_auto_load_model", False)
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        self.model_management_area = ft.Column(
            controls=[
                ft.Text("模型管理", size=14, weight=ft.FontWeight.W_500),
                model_status_row,
                self.model_info_text,
                self.auto_load_checkbox,
            ],
            spacing=PADDING_SMALL,
            visible=self.process_mode == "ai",
        )
        
        # 处理模式选择
        self.process_mode_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="ai", label="AI修复"),
                ft.Radio(value="mask", label="遮挡模式"),
            ], spacing=PADDING_MEDIUM),
            value=self.process_mode,
            on_change=self._on_process_mode_change,
        )
        
        # 遮挡类型选择
        self.mask_type_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="blur", label="模糊"),
                ft.Radio(value="color", label="纯色填充"),
            ], spacing=PADDING_MEDIUM),
            value=self.mask_type,
            on_change=self._on_mask_type_change,
        )
        
        # 颜色选择
        self.mask_color_btn = ft.Container(
            content=ft.Row([
                ft.Container(
                    width=24,
                    height=24,
                    bgcolor=self.mask_color,
                    border_radius=4,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                ),
                ft.Text("选择颜色", size=12),
            ], spacing=PADDING_SMALL),
            on_click=self._show_color_picker,
            ink=True,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
        )
        
        self.mask_options_row = ft.Row(
            controls=[
                ft.Text("遮挡方式:", size=13),
                self.mask_type_radio,
                self.mask_color_btn,
            ],
            spacing=PADDING_MEDIUM,
            visible=self.process_mode == "mask",
        )
        
        # 更新颜色按钮可见性
        self.mask_color_btn.visible = self.mask_type == "color"
        
        process_mode_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("处理模式:", size=14, weight=ft.FontWeight.W_500),
                        self.process_mode_radio,
                    ], spacing=PADDING_MEDIUM),
                    self.mask_options_row,
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 区域标注说明
        mask_settings_area = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        "默认去除底部25%区域，点击文件后的 [标注] 按钮可自定义区域",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        # 输出设置
        self.output_mode = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="same", label="输出到源文件目录"),
                ft.Radio(value="custom", label="自定义输出目录"),
            ]),
            value="same",
            on_change=lambda e: self._on_output_mode_change(),
        )
        
        # 使用配置服务的默认输出目录
        default_output_dir = str(self.config_service.get_output_dir())
        
        self.output_dir_field = ft.TextField(
            label="输出目录",
            value=default_output_dir,
            disabled=True,
            expand=True,
            read_only=True,
        )
        
        self.output_dir_btn = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="选择目录",
            disabled=True,
            on_click=self._select_output_dir,
        )
        
        output_settings_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode,
                    ft.Row(
                        controls=[
                            self.output_dir_field,
                            self.output_dir_btn,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 处理进度
        self.progress_text = ft.Text(
            "",
            size=14,
            weight=ft.FontWeight.W_500,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            value=0,
            visible=False,
        )
        
        # 开始处理按钮 - 与背景移除页面样式一致
        self.process_btn: ft.Container = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PLAY_ARROW, size=24),
                        ft.Text("开始处理", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=lambda _: self._start_processing(),
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
                process_mode_area,
                self.model_management_area,
                mask_settings_area,
                output_settings_area,
                self.progress_text,
                self.progress_bar,
                ft.Container(
                    content=self.process_btn,
                    padding=ft.padding.only(top=PADDING_MEDIUM),
                ),
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 主布局
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
            expand=True,
        )
        
        # 检查模型状态
        self._check_model_status()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.VIDEO_FILE_OUTLINED,
                            size=48,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
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
                height=168,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_select_files,
                ink=True,
            )
        )
    
    def _on_back_click(self, e) -> None:
        """返回按钮点击处理。"""
        if self.on_back:
            self.on_back()
    
    def _on_process_mode_change(self, e: ft.ControlEvent) -> None:
        """处理模式变化事件。"""
        self.process_mode = e.control.value
        self.config_service.set_config_value("video_subtitle_process_mode", self.process_mode)
        
        # 切换模式时更新UI
        is_ai_mode = self.process_mode == "ai"
        self.model_management_area.visible = is_ai_mode
        self.mask_options_row.visible = not is_ai_mode
        
        # 更新处理按钮状态
        self._update_process_button_state()
        self._page.update()
    
    def _on_mask_type_change(self, e: ft.ControlEvent) -> None:
        """遮挡类型变化事件。"""
        self.mask_type = e.control.value
        self.config_service.set_config_value("video_subtitle_mask_type", self.mask_type)
        
        # 只有纯色模式才显示颜色选择
        self.mask_color_btn.visible = self.mask_type == "color"
        self._page.update()
    
    def _show_color_picker(self, e: ft.ControlEvent) -> None:
        """显示颜色选择器。"""
        def on_color_selected(color: str):
            self.mask_color = color
            self.config_service.set_config_value("video_subtitle_mask_color", color)
            # 更新颜色预览
            self.mask_color_btn.content.controls[0].bgcolor = color
            self._page.close(dialog)
        
        # 预设颜色
        colors = [
            "#000000", "#FFFFFF", "#808080", "#C0C0C0",
            "#FF0000", "#00FF00", "#0000FF", "#FFFF00",
            "#FF00FF", "#00FFFF", "#FFA500", "#800080",
        ]
        
        color_grid = ft.GridView(
            runs_count=4,
            spacing=8,
            run_spacing=8,
            max_extent=50,
            controls=[
                ft.Container(
                    width=40,
                    height=40,
                    bgcolor=c,
                    border_radius=4,
                    border=ft.border.all(2, ft.Colors.OUTLINE if c != self.mask_color else ft.Colors.PRIMARY),
                    on_click=lambda e, color=c: on_color_selected(color),
                    ink=True,
                )
                for c in colors
            ],
        )
        
        dialog = ft.AlertDialog(
            title=ft.Text("选择遮挡颜色"),
            content=ft.Container(
                content=color_grid,
                width=250,
                height=150,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self._close_dialog(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _close_dialog(self, dialog: ft.AlertDialog) -> None:
        """关闭对话框。"""
        self._page.close(dialog)
    
    async def _on_select_files(self, e: ft.ControlEvent = None) -> None:
        """选择文件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "avi", "mov", "mkv", "flv", "wmv"],
            allow_multiple=True,
        )
        if result and result.files:
            for file in result.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent = None) -> None:
        """选择文件夹。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择文件夹")
        if result:
            folder_path = Path(result)
            video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv"}
            for ext in video_extensions:
                for file_path in folder_path.glob(f"*{ext}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                # 大写扩展名
                for file_path in folder_path.glob(f"*{ext.upper()}"):
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if not self.selected_files:
            self._init_empty_state()
            self.process_btn.content.disabled = True
        else:
            self.file_list_view.controls = []
            for file_path in self.selected_files:
                # 检查是否有自定义区域
                regions = self.file_regions.get(str(file_path), [])
                region_count = len(regions)
                
                if region_count > 0:
                    region_info = f"{region_count}个区域"
                    region_color = ft.Colors.GREEN
                    region_tooltip = "\n".join([f"区域{i+1}: ({r['left']},{r['top']})-({r['right']},{r['bottom']})" for i, r in enumerate(regions)])
                else:
                    region_info = "默认"
                    region_color = ft.Colors.ON_SURFACE_VARIANT
                    region_tooltip = "使用默认底部25%区域"
                
                file_item = ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE, size=20),
                        ft.Text(
                            file_path.name,
                            size=12,
                            expand=True,
                            tooltip=str(file_path),
                        ),
                        ft.Text(
                            region_info,
                            size=11,
                            color=region_color,
                            tooltip=region_tooltip,
                        ),
                        ft.Text(
                            format_file_size(file_path.stat().st_size),
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.TextButton(
                            "标注",
                            icon=ft.Icons.CROP_FREE,
                            tooltip="标注字幕/水印区域",
                            on_click=lambda _, p=file_path: self._open_region_selector(p),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=16,
                            tooltip="移除",
                            on_click=lambda _, p=file_path: self._remove_file(p),
                        ),
                    ],
                    spacing=PADDING_SMALL,
                )
                self.file_list_view.controls.append(file_item)
            
            # 更新按钮状态
            model_loaded = self.subtitle_service.is_model_loaded()
            self.process_btn.content.disabled = not model_loaded
        
        self._page.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            # 同时移除区域设置
            if str(file_path) in self.file_regions:
                del self.file_regions[str(file_path)]
            self._update_file_list()
    
    def _open_region_selector(self, file_path: Path) -> None:
        """打开区域选择器对话框。
        
        Args:
            file_path: 视频文件路径
        """
        try:
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                logger.error(f"无法打开视频: {file_path}")
                self._show_snackbar(f"无法打开视频: {file_path.name}")
                return
            
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            # 读取第一帧
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error("无法读取视频帧")
                self._show_snackbar("无法读取视频帧")
                return
            
            # 显示对话框
            self._show_region_dialog(file_path, frame, total_frames, fps, frame_width, frame_height, duration)
            
        except Exception as e:
            logger.error(f"读取视频帧失败: {e}", exc_info=True)
            self._show_snackbar(f"读取视频帧失败: {str(e)}")
    
    def _show_region_dialog(self, file_path: Path, frame: np.ndarray, 
                             total_frames: int, fps: float, 
                             frame_width: int, frame_height: int, duration: float) -> None:
        """显示区域选择对话框。
        
        Args:
            file_path: 视频文件路径
            frame: 视频帧
            total_frames: 总帧数
            fps: 帧率
            frame_width: 视频宽度
            frame_height: 视频高度
            duration: 视频时长（秒）
        """
        import uuid
        
        # 临时文件目录
        temp_dir = self.config_service.get_temp_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(uuid.uuid4())[:8]
        
        # 根据页面大小计算预览尺寸
        page_width = self._page.width or 1000
        page_height = self._page.height or 700
        
        # 对话框可用高度（预留标题50px、按钮50px、时间轴40px、状态栏20px）
        available_height = page_height - 160
        available_height = max(available_height, 350)  # 最小350
        
        # 视频预览最大尺寸
        max_video_width = min(page_width - 380, 700)  # 预留右侧面板
        max_video_height = available_height - 80  # 预留时间轴和状态栏
        
        # 按比例缩放视频
        scale_w = max_video_width / frame_width
        scale_h = max_video_height / frame_height
        scale = min(scale_w, scale_h, 1.0)  # 不放大
        
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
        # 确保最小尺寸
        display_width = max(display_width, 200)
        display_height = max(display_height, 150)
        
        # 时间轴宽度（至少400px，确保拖动条可用）
        slider_width = max(display_width, 400)
        
        # 预览图路径
        preview_path = temp_dir / f"region_preview_{session_id}.jpg"
        
        # 获取已有区域列表
        existing_regions = self.file_regions.get(str(file_path), [])
        regions_list = [r.copy() for r in existing_regions]
        
        # 状态变量
        current_frame = [frame.copy()]
        update_counter = [0]  # 用于生成唯一文件名
        
        def save_preview_with_regions():
            """保存带区域标注的预览图，返回新路径"""
            update_counter[0] += 1
            new_path = temp_dir / f"region_preview_{session_id}_{update_counter[0]}.jpg"
            
            img = current_frame[0].copy()
            
            # 绘制已有区域（绿色，加粗）
            for r in regions_list:
                cv2.rectangle(img, 
                    (r['left'], r['top']), 
                    (r['right'], r['bottom']), 
                    (0, 255, 0), 3)
                # 半透明填充
                overlay = img.copy()
                cv2.rectangle(overlay, (r['left'], r['top']), (r['right'], r['bottom']), (0, 255, 0), -1)
                cv2.addWeighted(overlay, 0.2, img, 0.8, 0, img)
            
            # 缩放并保存
            img_resized = cv2.resize(img, (display_width, display_height))
            cv2.imwrite(str(new_path), img_resized)
            return str(new_path)
        
        # 初始保存预览
        initial_preview = save_preview_with_regions()
        
        # 预览图控件 - 使用 FILL 确保完全填充，避免上下边距
        preview_image = ft.Image(
            src=initial_preview,
            width=display_width,
            height=display_height,
            fit=ft.BoxFit.FILL,
        )
        
        # 选择框覆盖层（用于显示正在绘制的区域）
        selection_box = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.RED),
            border=ft.border.all(2, ft.Colors.RED),
            visible=False,
            top=0, left=0, width=0, height=0,
        )
        
        # 区域列表显示
        regions_column = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)
        
        status_text = ft.Text(
            f"在视频上拖动鼠标框选区域 | 视频: {frame_width}x{frame_height}",
            size=11, color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        time_text = ft.Text(
            f"00:00 / {int(duration//60):02d}:{int(duration%60):02d}",
            size=11,
        )
        
        # 绘制状态
        draw_state = {'start_x': 0, 'start_y': 0, 'end_x': 0, 'end_y': 0}
        
        def refresh_preview():
            """刷新预览图"""
            new_path = save_preview_with_regions()
            preview_image.src = new_path
        
        def format_time(seconds: float) -> str:
            """格式化时间为 MM:SS"""
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m:02d}:{s:02d}"
        
        def parse_time(time_str: str) -> float:
            """解析时间字符串 MM:SS 为秒"""
            try:
                parts = time_str.strip().split(':')
                if len(parts) == 2:
                    return int(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 1:
                    return float(parts[0])
            except Exception:
                pass
            return 0.0
        
        def make_time_change_handler(idx: int, field: str):
            """创建时间变化处理器"""
            def handler(e):
                if 0 <= idx < len(regions_list):
                    t = parse_time(e.control.value)
                    t = max(0, min(duration, t))
                    regions_list[idx][field] = t
            return handler
        
        def update_regions_display():
            """更新区域列表显示"""
            regions_column.controls.clear()
            for i, r in enumerate(regions_list):
                start_t = r.get('start_time', 0.0)
                end_t = r.get('end_time', duration)
                
                regions_column.controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Container(width=10, height=10, bgcolor=ft.Colors.GREEN, border_radius=2),
                                        ft.Text(f"区域{i+1}: ({r['left']},{r['top']})-({r['right']},{r['bottom']})", 
                                                size=11, expand=True),
                                        ft.IconButton(
                                            icon=ft.Icons.CLOSE, icon_size=14,
                                            tooltip="删除",
                                            on_click=lambda _, idx=i: delete_region(idx),
                                        ),
                                    ],
                                    spacing=4,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("时间:", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.TextField(
                                            value=format_time(start_t),
                                            width=60, height=28,
                                            text_size=10,
                                            content_padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                            on_blur=make_time_change_handler(i, 'start_time'),
                                            tooltip="开始时间 (MM:SS)",
                                        ),
                                        ft.Text("-", size=10),
                                        ft.TextField(
                                            value=format_time(end_t),
                                            width=60, height=28,
                                            text_size=10,
                                            content_padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                            on_blur=make_time_change_handler(i, 'end_time'),
                                            tooltip="结束时间 (MM:SS)",
                                        ),
                                        ft.Text(f"/ {format_time(duration)}", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=4,
                                ),
                            ],
                            spacing=2,
                        ),
                        padding=4,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=4,
                        margin=ft.margin.only(bottom=4),
                    )
                )
            if not regions_list:
                regions_column.controls.append(
                    ft.Text("拖动鼠标在视频上框选区域", size=11, 
                            color=ft.Colors.ON_SURFACE_VARIANT, italic=True)
                )
        
        def delete_region(idx):
            if 0 <= idx < len(regions_list):
                regions_list.pop(idx)
                refresh_preview()
                update_regions_display()
                status_text.value = f"已删除区域，剩余 {len(regions_list)} 个"
                self._page.update()
        
        def on_pan_start(e: ft.DragStartEvent):
            # 限制在有效范围内
            x = max(0, min(display_width, e.local_x))
            y = max(0, min(display_height, e.local_y))
            draw_state['start_x'] = x
            draw_state['start_y'] = y
            selection_box.left = x
            selection_box.top = y
            selection_box.width = 0
            selection_box.height = 0
            selection_box.visible = True
            self._page.update()
        
        def on_pan_update(e: ft.DragUpdateEvent):
            # 限制范围
            end_x = max(0, min(display_width, e.local_x))
            end_y = max(0, min(display_height, e.local_y))
            
            # 保存当前位置
            draw_state['end_x'] = end_x
            draw_state['end_y'] = end_y
            
            # 更新选择框
            selection_box.left = min(draw_state['start_x'], end_x)
            selection_box.top = min(draw_state['start_y'], end_y)
            selection_box.width = abs(end_x - draw_state['start_x'])
            selection_box.height = abs(end_y - draw_state['start_y'])
            self._page.update()
        
        def on_pan_end(e: ft.DragEndEvent):
            selection_box.visible = False
            
            # 使用保存的最后位置（DragEndEvent 没有 local_x/local_y）
            end_x = draw_state['end_x']
            end_y = draw_state['end_y']
            
            # 计算实际坐标（转换回原始尺寸）
            x1 = int(min(draw_state['start_x'], end_x) / scale)
            y1 = int(min(draw_state['start_y'], end_y) / scale)
            x2 = int(max(draw_state['start_x'], end_x) / scale)
            y2 = int(max(draw_state['start_y'], end_y) / scale)
            
            # 确保在边界内
            x1 = max(0, min(frame_width, x1))
            x2 = max(0, min(frame_width, x2))
            y1 = max(0, min(frame_height, y1))
            y2 = max(0, min(frame_height, y2))
            
            # 最小区域限制
            if x2 - x1 > 20 and y2 - y1 > 20:
                regions_list.append({
                    'left': x1, 'top': y1, 'right': x2, 'bottom': y2,
                    'height': frame_height, 'width': frame_width,
                    'start_time': 0.0,  # 开始时间（秒），0表示从头
                    'end_time': duration,  # 结束时间（秒），默认到结尾
                })
                status_text.value = f"✓ 已添加区域{len(regions_list)}: ({x1},{y1})-({x2},{y2})"
                status_text.color = ft.Colors.GREEN
                refresh_preview()
                update_regions_display()
            else:
                status_text.value = "区域太小（至少20x20像素），请重新框选"
                status_text.color = ft.Colors.ORANGE
            
            self._page.update()
        
        # 手势检测器 + Stack（用于叠加选择框）
        preview_stack = ft.Stack(
            controls=[
                preview_image,
                selection_box,
            ],
            width=display_width,
            height=display_height,
        )
        
        gesture_detector = ft.GestureDetector(
            content=ft.Container(
                content=preview_stack,
                border=ft.border.all(2, ft.Colors.PRIMARY),
                border_radius=4,
            ),
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
        )
        
        time_slider = ft.Slider(
            min=0, max=max(1, total_frames - 1), value=0, expand=True,
            on_change_end=lambda e: on_time_change(e),
        )
        
        def on_time_change(e):
            frame_idx = int(e.control.value)
            time_sec = frame_idx / fps if fps > 0 else 0
            time_text.value = f"{int(time_sec//60):02d}:{int(time_sec%60):02d} / {int(duration//60):02d}:{int(duration%60):02d}"
            
            try:
                cap = cv2.VideoCapture(str(file_path))
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, new_frame = cap.read()
                cap.release()
                
                if ret:
                    current_frame[0] = new_frame.copy()
                    refresh_preview()
                    status_text.value = f"已跳转到 {time_text.value.split('/')[0].strip()}"
                    status_text.color = ft.Colors.ON_SURFACE_VARIANT
            except Exception as ex:
                logger.error(f"读取帧失败: {ex}")
                status_text.value = f"读取帧失败"
                status_text.color = ft.Colors.ERROR
            
            self._page.update()
        
        def close_dialog(e):
            self._page.close(dialog)
        
        def on_confirm(e):
            if regions_list:
                self.file_regions[str(file_path)] = regions_list
            elif str(file_path) in self.file_regions:
                del self.file_regions[str(file_path)]
            
            self._page.close(dialog)
            self._update_file_list()
            logger.info(f"已保存 {file_path.name} 的 {len(regions_list)} 个区域")
        
        def on_apply_to_all(e):
            """应用到所有文件"""
            if not regions_list:
                status_text.value = "请先标注区域"
                status_text.color = ft.Colors.ORANGE
                self._page.update()
                return
            
            # 保存当前文件的区域
            self.file_regions[str(file_path)] = regions_list
            
            # 应用到所有其他文件（注意：时间范围可能需要根据视频时长调整）
            applied_count = 0
            for other_file in self.selected_files:
                if other_file != file_path:
                    # 复制区域设置（需要深拷贝）
                    self.file_regions[str(other_file)] = [r.copy() for r in regions_list]
                    applied_count += 1
            
            self._page.close(dialog)
            self._update_file_list()
            self._show_snackbar(f"已将区域设置应用到所有 {applied_count + 1} 个文件")
            logger.info(f"已将 {len(regions_list)} 个区域应用到 {applied_count + 1} 个文件")
        
        def on_clear_all(e):
            regions_list.clear()
            refresh_preview()
            update_regions_display()
            status_text.value = "已清空所有区域"
            status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self._page.update()
        
        # 初始化区域列表
        update_regions_display()
        
        # 左侧面板宽度（取视频宽度和时间轴最小宽度的较大值）
        left_panel_width = max(display_width, slider_width)
        
        # 左侧：视频预览 + 时间轴
        left_panel = ft.Container(
            content=ft.Column(
                controls=[
                    # 预览图（可框选）- 居中显示
                    ft.Container(
                        content=gesture_detector,
                        alignment=ft.Alignment.CENTER,
                    ),
                    # 时间轴
                    ft.Row([
                        ft.Icon(ft.Icons.ACCESS_TIME, size=16),
                        time_slider,
                        time_text,
                    ], spacing=8),
                    status_text,
                ],
                spacing=8,
            ),
            width=left_panel_width,
            padding=ft.padding.only(right=12),
        )
        
        # 右侧：已标注区域列表
        right_panel = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Text("已标注区域", size=13, weight=ft.FontWeight.W_500),
                        ft.TextButton("清空", icon=ft.Icons.DELETE_SWEEP, 
                                      icon_color=ft.Colors.ERROR,
                                      on_click=on_clear_all),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=1),
                    ft.Container(
                        content=regions_column, 
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "提示：每个区域可设置独立的时间范围",
                            size=10, 
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.padding.only(top=8),
                    ),
                ],
                spacing=4,
            ),
            width=260,
            padding=ft.padding.only(left=12),
            border=ft.border.only(left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )
        
        # 主布局：左右分栏
        main_content = ft.Row(
            controls=[left_panel, right_panel],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=0,
        )
        
        # 创建对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.CROP, size=20),
                ft.Text(f"标注水印/字幕区域", size=16, weight=ft.FontWeight.W_500),
                ft.Text(f" - {file_path.name}", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=8),
            content=ft.Container(
                content=main_content,
                width=left_panel_width + 285,  # 左侧面板 + 右侧面板(260) + 边距
                height=display_height + 70,  # 视频 + 时间轴 + 状态栏
            ),
            actions=[
                ft.TextButton("取消", on_click=close_dialog),
                ft.OutlinedButton(
                    "应用到所有文件", 
                    icon=ft.Icons.COPY_ALL, 
                    on_click=on_apply_to_all,
                    tooltip="将当前区域设置应用到列表中所有文件",
                ),
                ft.ElevatedButton("保存", icon=ft.Icons.SAVE, on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self._page.open(dialog)
    
    def _show_snackbar(self, message: str, color: str = None) -> None:
        """显示 snackbar 提示。"""
        snackbar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        self._page.open(snackbar)
    
    def _clear_files(self) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _check_model_status(self) -> None:
        """检查模型状态。"""
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 检查模型文件是否存在
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        all_exist = all([
            encoder_path.exists(),
            infer_path.exists(),
            decoder_path.exists()
        ])
        
        if not all_exist:
            # 模型未下载
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"模型未下载 ({model_info.size_mb}MB)"
            self.model_status_text.color = ft.Colors.ERROR
            self.model_download_btn.visible = True
            self.model_load_btn.visible = False
            self.model_unload_btn.visible = False
            self.model_delete_btn.visible = False
        elif self.subtitle_service.is_model_loaded():
            # 模型已加载
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = "模型已加载"
            self.model_status_text.color = ft.Colors.GREEN
            self.model_download_btn.visible = False
            self.model_load_btn.visible = False
            self.model_unload_btn.visible = True
            self.model_delete_btn.visible = True
        else:
            # 模型已下载，未加载
            self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
            self.model_status_text.value = "模型已下载，未加载"
            self.model_status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self.model_download_btn.visible = False
            self.model_load_btn.visible = True
            self.model_unload_btn.visible = False
            self.model_delete_btn.visible = True
            
            # 检查是否启用自动加载
            if self.auto_load_checkbox.value:
                self._page.update()
                self._try_auto_load_model()
                return
        
        # 更新处理按钮状态
        self._update_process_button_state()
        
        self._page.update()
    
    def _update_process_button_state(self) -> None:
        """更新处理按钮状态。"""
        has_files = len(self.selected_files) > 0
        
        if self.process_mode == "mask":
            # 遮挡模式不需要模型
            self.process_btn.content.disabled = not has_files
        else:
            # AI模式需要模型已加载
            model_loaded = self.subtitle_service.is_model_loaded()
            self.process_btn.content.disabled = not (model_loaded and has_files)
    
    def _download_model(self) -> None:
        """下载模型。"""
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 创建模型目录
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # 确定需要下载的文件
        files_to_download = []
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        if not encoder_path.exists():
            files_to_download.append(("Encoder", model_info.encoder_url, encoder_path))
        if not infer_path.exists():
            files_to_download.append(("Infer", model_info.infer_url, infer_path))
        if not decoder_path.exists():
            files_to_download.append(("Decoder", model_info.decoder_url, decoder_path))
        
        if not files_to_download:
            logger.warning("模型文件已存在")
            self._check_model_status()
            return
        
        total_files = len(files_to_download)
        
        # 显示进度
        self.model_status_icon.name = ft.Icons.DOWNLOADING
        self.model_status_icon.color = ft.Colors.ON_SURFACE_VARIANT
        self.model_status_text.value = f"正在下载 {total_files} 个文件..."
        self.model_status_text.color = ft.Colors.ON_SURFACE_VARIANT
        self.model_download_btn.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self.progress_text.value = "准备下载..."
        self._page.update()
        
        self._download_files_to_download = files_to_download
        self._download_total_files = total_files
        self._page.run_task(self._async_download_model)
    
    async def _async_download_model(self) -> None:
        """异步下载模型。"""
        import asyncio
        
        files_to_download = self._download_files_to_download
        total_files = self._download_total_files
        
        self._task_finished = False
        self._pending_progress = None
        
        async def _poll():
            while not self._task_finished:
                if self._pending_progress is not None:
                    bar_val, text_val, status_val = self._pending_progress
                    if bar_val is not None:
                        self.progress_bar.value = bar_val
                    if text_val is not None:
                        self.progress_text.value = text_val
                    if status_val is not None:
                        self.model_status_text.value = status_val
                    self._page.update()
                    self._pending_progress = None
                await asyncio.sleep(0.3)
        
        def _do_download():
            import httpx
            
            for file_idx, (file_name, url, save_path) in enumerate(files_to_download):
                self._pending_progress = (
                    None,
                    f"正在下载 {file_name} ({file_idx + 1}/{total_files})...",
                    None,
                )
                
                logger.info(f"开始下载: {file_name} from {url}")
                
                with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    file_progress = downloaded / total_size
                                    overall_progress = (file_idx + file_progress) / total_files
                                    percent = overall_progress * 100
                                    
                                    downloaded_mb = downloaded / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)
                                    
                                    self._pending_progress = (
                                        overall_progress,
                                        f"下载 {file_name}: {downloaded_mb:.1f}MB / {total_mb:.1f}MB "
                                        f"({file_idx + 1}/{total_files}) - 总进度: {percent:.1f}%",
                                        f"正在下载... {percent:.1f}%",
                                    )
                
                logger.info(f"下载完成: {file_name}")
        
        poll = asyncio.create_task(_poll())
        try:
            await asyncio.to_thread(_do_download)
        except Exception as e:
            logger.error(f"下载模型失败: {e}", exc_info=True)
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"下载失败: {str(e)}"
            self.model_status_text.color = ft.Colors.ERROR
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self.model_download_btn.disabled = False
            self._page.update()
            return
        finally:
            self._task_finished = True
            await poll
        
        # 下载完成
        self.progress_bar.visible = False
        self.progress_text.visible = False
        self.progress_bar.value = 0
        self.progress_text.value = ""
        logger.info("所有模型文件下载完成")
        
        # 更新状态
        self._check_model_status()
        
        # 自动加载模型
        logger.info("开始自动加载模型...")
        await self._async_load_model()
    
    def _load_model(self) -> None:
        """加载模型。"""
        self._page.run_task(self._async_load_model)
    
    async def _async_load_model(self) -> None:
        """异步加载模型。"""
        import asyncio
        await asyncio.sleep(0.3)
        try:
            model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
            
            # 更新状态
            self.model_status_text.value = "正在加载模型..."
            self.model_load_btn.disabled = True
            self._page.update()
            
            # 在后台线程加载模型
            encoder_path = self.model_dir / model_info.encoder_filename
            infer_path = self.model_dir / model_info.infer_filename
            decoder_path = self.model_dir / model_info.decoder_filename
            
            neighbor_stride = model_info.neighbor_stride
            ref_length = model_info.ref_length
            
            def _do_load():
                self.subtitle_service.load_model(
                    str(encoder_path),
                    str(infer_path),
                    str(decoder_path),
                    neighbor_stride=neighbor_stride,
                    ref_length=ref_length
                )

            await asyncio.to_thread(_do_load)
            
            # 更新状态
            self._check_model_status()
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            self.model_status_text.value = f"加载失败: {str(e)}"
            self.model_status_text.color = ft.Colors.ERROR
            self.model_load_btn.disabled = False
            self._page.update()
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。
        
        Args:
            e: 控件事件对象
        """
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("subtitle_remove_auto_load_model", auto_load)
        
        # 如果启用自动加载，尝试加载模型
        if auto_load:
            self._try_auto_load_model()
    
    def _try_auto_load_model(self) -> None:
        """尝试自动加载已下载的模型。"""
        if self.subtitle_service.is_model_loaded():
            return
        
        model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
        
        # 检查模型文件是否都存在
        encoder_path = self.model_dir / model_info.encoder_filename
        infer_path = self.model_dir / model_info.infer_filename
        decoder_path = self.model_dir / model_info.decoder_filename
        
        all_exist = all([
            encoder_path.exists(),
            infer_path.exists(),
            decoder_path.exists()
        ])
        
        if not all_exist:
            return
        
        # 自动加载模型
        self._load_model()
    
    def _unload_model(self) -> None:
        """卸载模型。"""
        self.subtitle_service.unload_model()
        self._check_model_status()
    
    def _delete_model(self) -> None:
        """删除模型文件。"""
        # 确认对话框
        def confirm_delete(e):
            self._page.close(dlg)
            self._page.run_task(self._async_delete_model)
        
        def cancel_delete(e):
            self._page.close(dlg)
        
        dlg = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text("确定要删除模型文件吗？此操作无法撤销。"),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.TextButton("删除", on_click=confirm_delete),
            ],
        )
        self._page.open(dlg)
    
    async def _async_delete_model(self) -> None:
        """异步删除模型文件。"""
        import asyncio
        try:
            def _do_delete():
                model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
                
                encoder_path = self.model_dir / model_info.encoder_filename
                infer_path = self.model_dir / model_info.infer_filename
                decoder_path = self.model_dir / model_info.decoder_filename
                
                # 先卸载模型
                if self.subtitle_service.is_model_loaded():
                    self.subtitle_service.unload_model()
                
                # 删除文件
                deleted = []
                if encoder_path.exists():
                    encoder_path.unlink()
                    deleted.append("encoder")
                if infer_path.exists():
                    infer_path.unlink()
                    deleted.append("infer")
                if decoder_path.exists():
                    decoder_path.unlink()
                    deleted.append("decoder")
                
                if deleted:
                    logger.info(f"已删除模型文件: {', '.join(deleted)}")
                else:
                    logger.warning("没有找到要删除的模型文件")
            
            await asyncio.to_thread(_do_delete)
            self._check_model_status()
            
        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            self.model_status_text.value = f"删除失败: {str(e)}"
            self.model_status_text.color = ft.Colors.ERROR
            self._page.update()
    
    def _on_output_mode_change(self) -> None:
        """输出模式变更。"""
        is_custom = self.output_mode.value == "custom"
        self.output_dir_field.disabled = not is_custom
        self.output_dir_btn.disabled = not is_custom
        self._page.update()
    
    async def _select_output_dir(self, e: ft.ControlEvent = None) -> None:
        """选择输出目录。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if result:
            self.output_dir_field.value = result
            self._page.update()
    
    def _create_mask(self, height: int, width: int, file_path: Optional[Path] = None, 
                     current_time: Optional[float] = None) -> np.ndarray:
        """创建遮罩。
        
        Args:
            height: 视频高度
            width: 视频宽度
            file_path: 视频文件路径，用于获取文件特定的区域设置
            current_time: 当前帧的时间（秒），用于过滤时间范围内的区域
        
        Returns:
            遮罩数组
        """
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # 检查是否有该文件的自定义区域列表
        regions = []
        if file_path and str(file_path) in self.file_regions:
            regions = self.file_regions[str(file_path)]
        
        if regions:
            # 使用文件特定的多个区域设置
            active_count = 0
            for region in regions:
                # 检查时间范围
                if current_time is not None:
                    start_time = region.get('start_time', 0.0)
                    end_time = region.get('end_time', float('inf'))
                    if current_time < start_time or current_time > end_time:
                        continue  # 跳过不在时间范围内的区域
                
                # 如果视频尺寸与标注时不同，需要缩放
                if region.get('height', height) != height or region.get('width', width) != width:
                    scale_h = height / region.get('height', height)
                    scale_w = width / region.get('width', width)
                    
                    top = int(region['top'] * scale_h)
                    bottom = int(region['bottom'] * scale_h)
                    left = int(region['left'] * scale_w)
                    right = int(region['right'] * scale_w)
                else:
                    top = region['top']
                    bottom = region['bottom']
                    left = region['left']
                    right = region['right']
                
                # 确保边界有效
                top = max(0, min(height - 1, top))
                bottom = max(0, min(height, bottom))
                left = max(0, min(width - 1, left))
                right = max(0, min(width, right))
                
                mask[top:bottom, left:right] = 255
                active_count += 1
            
            if active_count > 0:
                logger.debug(f"时间 {current_time:.2f}s: 使用 {active_count} 个区域")
        else:
            # 默认模式：底部25%区域
            top = int(height * 0.75)
            mask[top:height, :] = 255
        
        return mask
    
    def _apply_mask_to_frame(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """使用遮挡模式处理单帧。
        
        Args:
            frame: 输入帧 (BGR格式)
            mask: 遮罩数组
        
        Returns:
            处理后的帧
        """
        result = frame.copy()
        height, width = frame.shape[:2]
        
        if self.mask_type == "blur":
            # 模糊遮挡
            blur_strength = max(width, height) // 15
            blur_strength = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
            blur_strength = max(21, blur_strength)
            blurred = cv2.GaussianBlur(frame, (blur_strength, blur_strength), 0)
            
            # 使用遮罩合成
            mask_3d = mask[:, :, np.newaxis] / 255.0
            result = (mask_3d * blurred + (1 - mask_3d) * result).astype(np.uint8)
        else:
            # 纯色填充
            color_hex = self.mask_color.lstrip('#')
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
            
            # 创建纯色图层
            color_layer = np.zeros_like(frame)
            color_layer[:, :] = (b, g, r)  # OpenCV使用BGR格式
            
            # 使用遮罩合成
            mask_3d = mask[:, :, np.newaxis] / 255.0
            result = (mask_3d * color_layer + (1 - mask_3d) * result).astype(np.uint8)
        
        return result
    
    def _process_video_mask_mode(
        self,
        file_path: Path,
        temp_video_file: Path,
        idx: int,
        total: int
    ) -> bool:
        """使用遮挡模式处理视频。
        
        Args:
            file_path: 输入视频路径
            temp_video_file: 临时输出视频路径
            idx: 当前文件索引
            total: 总文件数
        
        Returns:
            处理是否成功
        """
        try:
            # 打开视频
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                logger.error(f"无法打开视频: {file_path}")
                return False
            
            # 获取视频信息
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(temp_video_file), fourcc, fps, (width, height))
            
            if not out.isOpened():
                logger.error(f"无法创建输出视频: {temp_video_file}")
                cap.release()
                return False
            
            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 计算当前时间
                current_time = frame_idx / fps if fps > 0 else 0
                
                # 创建遮罩
                mask = self._create_mask(height, width, file_path, current_time)
                
                # 应用遮挡效果
                if np.any(mask > 0):
                    frame = self._apply_mask_to_frame(frame, mask)
                
                out.write(frame)
                frame_idx += 1
                
                # 更新进度
                if frame_idx % 30 == 0:  # 每30帧更新一次
                    progress = (idx + frame_idx / total_frames) / total
                    self._pending_progress = (progress, None)
            
            cap.release()
            out.release()
            
            logger.info(f"遮挡模式处理完成: {file_path.name}, 共 {frame_idx} 帧")
            return True
            
        except Exception as e:
            logger.error(f"遮挡模式处理失败: {e}", exc_info=True)
            return False
    
    def _start_processing(self) -> None:
        """开始处理。"""
        if self.is_processing or not self.selected_files:
            return
        
        # 检查输出目录
        output_dir = None
        if self.output_mode.value == "custom":
            if not self.output_dir_field.value:
                logger.warning("请选择输出目录")
                return
            output_dir = Path(self.output_dir_field.value)
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_processing = True
        self.process_btn.content.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self._page.update()
        
        self._process_output_dir = output_dir
        self._page.run_task(self._async_process)
    
    async def _async_process(self) -> None:
        """异步处理视频。"""
        import asyncio
        
        self._task_finished = False
        self._pending_progress = None
        self._process_error = False
        output_dir = self._process_output_dir
        process_mode = self.process_mode
        files = list(self.selected_files)
        
        async def _poll():
            while not self._task_finished:
                if self._pending_progress is not None:
                    bar_val, text_val = self._pending_progress
                    if bar_val is not None:
                        self.progress_bar.value = bar_val
                    if text_val is not None:
                        self.progress_text.value = text_val
                    self._page.update()
                    self._pending_progress = None
                await asyncio.sleep(0.3)
        
        def _do_process():
            import ffmpeg
            temp_audio_file = None
            temp_video_file = None
            
            try:
                total = len(files)
                
                for idx, file_path in enumerate(files):
                    # 更新进度
                    self._pending_progress = (idx / total, f"处理中: {file_path.name} ({idx + 1}/{total})")
                    
                    # 获取视频信息
                    video_info = self.ffmpeg_service.safe_probe(str(file_path))
                    if not video_info:
                        logger.error(f"无法获取视频信息: {file_path}")
                        continue
                    
                    # 检查是否有音频流
                    has_audio = any(
                        s.get('codec_type') == 'audio' 
                        for s in video_info.get('streams', [])
                    )
                    
                    # 步骤1：如果有音频，先提取音频
                    if has_audio:
                        temp_audio_file = Path(tempfile.gettempdir()) / f"temp_audio_{file_path.stem}.aac"
                        logger.info(f"提取音频到: {temp_audio_file}")
                        
                        try:
                            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
                            audio_stream = ffmpeg.input(str(file_path)).output(
                                str(temp_audio_file),
                                acodec='copy',
                                vn=None
                            ).global_args('-hide_banner', '-loglevel', 'error')
                            
                            ffmpeg.run(audio_stream, cmd=ffmpeg_path, overwrite_output=True)
                        except Exception as e:
                            logger.error(f"提取音频失败: {e}")
                            temp_audio_file = None
                    
                    # 步骤2：处理视频（流式处理，减少内存使用）
                    # 读取视频信息
                    cap = cv2.VideoCapture(str(file_path))
                    if not cap.isOpened():
                        logger.error(f"无法打开视频: {file_path}")
                        continue
                    
                    # 获取视频信息
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.release()
                    
                    logger.info(f"视频信息: {width}x{height}, {fps}fps, {total_frames}帧")
                    
                    # 步骤3：处理视频
                    temp_video_file = Path(tempfile.gettempdir()) / f"temp_video_{file_path.stem}.mp4"
                    
                    if process_mode == "mask":
                        # 遮挡模式：不使用AI模型
                        success = self._process_video_mask_mode(
                            file_path=file_path,
                            temp_video_file=temp_video_file,
                            idx=idx,
                            total=total
                        )
                    else:
                        # AI修复模式
                        current_file_path = file_path  # 捕获当前文件路径
                        def mask_callback(h: int, w: int, current_time: float) -> np.ndarray:
                            return self._create_mask(h, w, current_file_path, current_time)
                        
                        def update_progress(current, total_f):
                            progress = (idx + current / total_f) / total
                            self._pending_progress = (progress, None)
                        
                        success = self.subtitle_service.process_video_streaming(
                            video_path=str(file_path),
                            output_path=str(temp_video_file),
                            mask_callback=mask_callback,
                            fps=fps,
                            progress_callback=update_progress,
                            batch_size=10
                        )
                    
                    if not success:
                        logger.error(f"视频处理失败: {file_path}")
                        continue
                    
                    logger.info(f"临时视频保存到: {temp_video_file}")
                    
                    # 步骤4：确定最终输出路径
                    if output_dir:
                        output_path = output_dir / f"{file_path.stem}_no_subtitle{file_path.suffix}"
                    else:
                        output_path = file_path.parent / f"{file_path.stem}_no_subtitle{file_path.suffix}"
                    
                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    # 步骤5：如果有音频，使用FFmpeg合并视频和音频
                    if has_audio and temp_audio_file and temp_audio_file.exists():
                        logger.info("合并视频和音频...")
                        try:
                            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
                            
                            # 使用FFmpeg合并视频和音频
                            video_input = ffmpeg.input(str(temp_video_file))
                            audio_input = ffmpeg.input(str(temp_audio_file))
                            
                            # 获取GPU编码器（如果可用）
                            use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
                            gpu_encoder = None
                            if use_gpu:
                                gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
                            
                            # 选择编码器
                            if gpu_encoder:
                                vcodec = gpu_encoder
                                logger.info(f"使用GPU编码器: {vcodec}")
                            else:
                                vcodec = 'libx264'
                                logger.info("使用CPU编码器: libx264")
                            
                            output_stream = ffmpeg.output(
                                video_input,
                                audio_input,
                                str(output_path),
                                vcodec=vcodec,
                                acodec='copy',
                                crf=23,
                                preset='medium'
                            ).global_args('-hide_banner', '-loglevel', 'error')
                            
                            ffmpeg.run(output_stream, cmd=ffmpeg_path, overwrite_output=True)
                            logger.info(f"保存完成: {output_path}")
                        except Exception as e:
                            logger.error(f"合并音视频失败: {e}")
                            # 如果合并失败，直接使用无音频的视频
                            import shutil
                            shutil.copy(temp_video_file, output_path)
                            logger.info(f"保存无音频视频: {output_path}")
                    else:
                        # 没有音频，直接复制临时视频文件
                        import shutil
                        shutil.copy(temp_video_file, output_path)
                        logger.info(f"保存完成: {output_path}")
                    
                    # 清理临时文件
                    if temp_audio_file and temp_audio_file.exists():
                        temp_audio_file.unlink()
                    if temp_video_file and temp_video_file.exists():
                        temp_video_file.unlink()
                
                # 完成
                self._pending_progress = (1.0, "处理完成！")
                
            except Exception as e:
                logger.error(f"处理失败: {e}", exc_info=True)
                self._pending_progress = (None, f"处理失败: {str(e)}")
                self._process_error = True
            finally:
                # 确保清理临时文件
                if temp_audio_file and Path(temp_audio_file).exists():
                    try:
                        Path(temp_audio_file).unlink()
                    except Exception:
                        pass
                if temp_video_file and Path(temp_video_file).exists():
                    try:
                        Path(temp_video_file).unlink()
                    except Exception:
                        pass
        
        poll = asyncio.create_task(_poll())
        try:
            await asyncio.to_thread(_do_process)
        finally:
            self._task_finished = True
            await poll
        
        if self._process_error:
            self.progress_text.color = ft.Colors.ERROR
        
        self.is_processing = False
        self.process_btn.content.disabled = False
        self._page.update()
    
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
            snackbar = ft.SnackBar(content=ft.Text("字幕去除不支持该格式"), bgcolor=ft.Colors.ORANGE)
            self._page.open(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载字幕移除模型
            if self.subtitle_service:
                self.subtitle_service.unload_model()
            
            # 2. 清空文件路径
            self.selected_file = None
            
            # 3. 清空区域数据
            if hasattr(self, 'mask_regions'):
                self.mask_regions.clear()
            
            # 4. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 5. 清除 UI 内容
            self.content = None
            
            # 6. 强制垃圾回收
            gc.collect()
            
            logger.info("视频去字幕视图资源已清理")
        except Exception as e:
            logger.warning(f"清理视频去字幕视图资源时出错: {e}")