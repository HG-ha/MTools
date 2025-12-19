# -*- coding: utf-8 -*-
"""视频字幕/水印移除视图模块。

提供视频字幕/水印移除功能的用户界面。
"""

import threading
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
from utils import format_file_size, logger


class SubtitleRemoveView(ft.Container):
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
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        self.current_model_key: str = DEFAULT_SUBTITLE_REMOVE_MODEL_KEY
        self.file_regions: dict = {}  # 每个文件的区域设置 {file_path: [region_list]}
        self.visual_region: Optional[dict] = None  # 可视化选择的区域（兼容旧代码）
        
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
                self.page,
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
        
        self.model_download_btn = ft.ElevatedButton(
            "下载模型",
            icon=ft.Icons.DOWNLOAD,
            visible=False,
            on_click=lambda _: self._download_model(),
        )
        
        self.model_load_btn = ft.ElevatedButton(
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
        
        model_management_area = ft.Column(
            controls=[
                ft.Text("模型管理", size=14, weight=ft.FontWeight.W_500),
                model_status_row,
                self.model_info_text,
            ],
            spacing=PADDING_SMALL,
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
        
        self.output_dir_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            visible=False,
        )
        
        self.output_dir_btn = ft.ElevatedButton(
            "选择目录",
            icon=ft.Icons.FOLDER_OPEN,
            visible=False,
            on_click=lambda _: self._select_output_dir(),
        )
        
        self.output_dir_picker = ft.FilePicker(
            on_result=self._on_output_dir_selected
        )
        self.page.overlay.append(self.output_dir_picker)
        
        output_settings_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode,
                    ft.Row(
                        controls=[
                            self.output_dir_btn,
                            self.output_dir_text,
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
        
        # 开始处理按钮
        self.process_btn = ft.ElevatedButton(
            "开始处理",
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda _: self._start_processing(),
            disabled=True,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                model_management_area,
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
        empty_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.VIDEO_FILE_OUTLINED,
                        size=64,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "未选择文件",
                        size=16,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        "点击上方按钮选择视频文件或文件夹",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            alignment=ft.alignment.center,
            expand=True,
            on_click=lambda _: self._on_select_files(),
        )
        
        self.file_list_view.controls = [empty_container]
    
    def _on_back_click(self, e) -> None:
        """返回按钮点击处理。"""
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self) -> None:
        """选择文件。"""
        self.file_picker.pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "avi", "mov", "mkv", "flv", "wmv"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self) -> None:
        """选择文件夹。"""
        self.file_picker.get_directory_path(
            dialog_title="选择文件夹",
        )
    
    def _on_files_selected(self, e: ft.FilePickerResultEvent) -> None:
        """文件选择回调。"""
        if e.files:
            # 添加选中的文件
            for file in e.files:
                file_path = Path(file.path)
                if file_path not in self.selected_files:
                    self.selected_files.append(file_path)
        elif e.path:
            # 添加文件夹中的所有视频文件
            folder_path = Path(e.path)
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
            self.process_btn.disabled = True
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
            self.process_btn.disabled = not model_loaded
        
        self.page.update()
    
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
        
        # 计算预览尺寸（限制最大宽度600，保持比例）
        max_w = 600
        scale = min(max_w / frame_width, 1.0)
        display_width = int(frame_width * scale)
        display_height = int(frame_height * scale)
        
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
        
        # 预览图控件
        preview_image = ft.Image(
            src=initial_preview,
            width=display_width,
            height=display_height,
            fit=ft.ImageFit.CONTAIN,
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
            except:
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
                self.page.update()
        
        def on_pan_start(e: ft.DragStartEvent):
            draw_state['start_x'] = e.local_x
            draw_state['start_y'] = e.local_y
            selection_box.left = e.local_x
            selection_box.top = e.local_y
            selection_box.width = 0
            selection_box.height = 0
            selection_box.visible = True
            self.page.update()
        
        def on_pan_update(e: ft.DragUpdateEvent):
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
            self.page.update()
        
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
            
            self.page.update()
        
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
            
            self.page.update()
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()
        
        def on_confirm(e):
            if regions_list:
                self.file_regions[str(file_path)] = regions_list
            elif str(file_path) in self.file_regions:
                del self.file_regions[str(file_path)]
            
            dialog.open = False
            self.page.update()
            self._update_file_list()
            logger.info(f"已保存 {file_path.name} 的 {len(regions_list)} 个区域")
        
        def on_clear_all(e):
            regions_list.clear()
            refresh_preview()
            update_regions_display()
            status_text.value = "已清空所有区域"
            status_text.color = ft.Colors.ON_SURFACE_VARIANT
            self.page.update()
        
        # 初始化区域列表
        update_regions_display()
        
        # 创建对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"标注区域 - {file_path.name}", size=16),
            content=ft.Column(
                controls=[
                    # 预览图（可框选）
                    gesture_detector,
                    # 时间轴
                    ft.Row([
                        ft.Icon(ft.Icons.ACCESS_TIME, size=16),
                        time_slider,
                        time_text,
                    ], spacing=8),
                    ft.Divider(height=1),
                    # 已标注区域
                    ft.Row([
                        ft.Text("已标注区域:", size=12, weight=ft.FontWeight.W_500),
                        ft.TextButton("清空", icon=ft.Icons.DELETE_SWEEP, on_click=on_clear_all),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(content=regions_column, height=80),
                    status_text,
                ],
                spacing=8,
                tight=True,
            ),
            actions=[
                ft.TextButton("取消", on_click=close_dialog),
                ft.ElevatedButton("保存", on_click=on_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_snackbar(self, message: str) -> None:
        """显示 snackbar 提示。"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()
    
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
        
        # 更新处理按钮状态
        model_loaded = self.subtitle_service.is_model_loaded()
        has_files = len(self.selected_files) > 0
        self.process_btn.disabled = not (model_loaded and has_files)
        
        self.page.update()
    
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
        self.page.update()
        
        def download_task():
            try:
                import httpx
                
                for file_idx, (file_name, url, save_path) in enumerate(files_to_download):
                    self.progress_text.value = f"正在下载 {file_name} ({file_idx + 1}/{total_files})..."
                    self.page.update()
                    
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
                                        
                                        self.progress_bar.value = overall_progress
                                        self.progress_text.value = (
                                            f"下载 {file_name}: {downloaded_mb:.1f}MB / {total_mb:.1f}MB "
                                            f"({file_idx + 1}/{total_files}) - 总进度: {percent:.1f}%"
                                        )
                                        self.model_status_text.value = f"正在下载... {percent:.1f}%"
                                        
                                        try:
                                            self.progress_bar.update()
                                            self.progress_text.update()
                                            self.model_status_text.update()
                                        except:
                                            pass
                    
                    logger.info(f"下载完成: {file_name}")
                
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
                self._load_model()
                
            except Exception as e:
                logger.error(f"下载模型失败: {e}", exc_info=True)
                self.model_status_icon.name = ft.Icons.ERROR
                self.model_status_icon.color = ft.Colors.ERROR
                self.model_status_text.value = f"下载失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self.progress_bar.visible = False
                self.progress_text.visible = False
                self.model_download_btn.disabled = False
                self.page.update()
        
        threading.Thread(target=download_task, daemon=True).start()
    
    def _load_model(self) -> None:
        """加载模型。"""
        def load_task():
            try:
                model_info = SUBTITLE_REMOVE_MODELS[self.current_model_key]
                
                # 更新状态
                self.model_status_text.value = "正在加载模型..."
                self.model_load_btn.disabled = True
                self.page.update()
                
                # 加载模型
                encoder_path = self.model_dir / model_info.encoder_filename
                infer_path = self.model_dir / model_info.infer_filename
                decoder_path = self.model_dir / model_info.decoder_filename
                
                self.subtitle_service.load_model(
                    str(encoder_path),
                    str(infer_path),
                    str(decoder_path),
                    neighbor_stride=model_info.neighbor_stride,
                    ref_length=model_info.ref_length
                )
                
                # 更新状态
                self._check_model_status()
                
            except Exception as e:
                logger.error(f"加载模型失败: {e}")
                self.model_status_text.value = f"加载失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self.model_load_btn.disabled = False
                self.page.update()
        
        threading.Thread(target=load_task, daemon=True).start()
    
    def _unload_model(self) -> None:
        """卸载模型。"""
        self.subtitle_service.unload_model()
        self._check_model_status()
    
    def _delete_model(self) -> None:
        """删除模型文件。"""
        def delete_task():
            try:
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
                
                # 更新状态
                self._check_model_status()
                
            except Exception as e:
                logger.error(f"删除模型失败: {e}")
                self.model_status_text.value = f"删除失败: {str(e)}"
                self.model_status_text.color = ft.Colors.ERROR
                self.page.update()
        
        # 确认对话框
        def confirm_delete(e):
            dlg.open = False
            self.page.update()
            threading.Thread(target=delete_task, daemon=True).start()
        
        def cancel_delete(e):
            dlg.open = False
            self.page.update()
        
        dlg = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text("确定要删除模型文件吗？此操作无法撤销。"),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.TextButton("删除", on_click=confirm_delete),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
    
    def _on_output_mode_change(self) -> None:
        """输出模式变更。"""
        is_custom = self.output_mode.value == "custom"
        self.output_dir_btn.visible = is_custom
        self.output_dir_text.visible = is_custom
        self.page.update()
    
    def _select_output_dir(self) -> None:
        """选择输出目录。"""
        self.output_dir_picker.get_directory_path(
            dialog_title="选择输出目录",
        )
    
    def _on_output_dir_selected(self, e: ft.FilePickerResultEvent) -> None:
        """输出目录选择回调。"""
        if e.path:
            self.output_dir_text.value = e.path
            self.page.update()
    
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
    
    def _start_processing(self) -> None:
        """开始处理。"""
        if self.is_processing or not self.selected_files:
            return
        
        # 检查输出目录
        output_dir = None
        if self.output_mode.value == "custom":
            if not self.output_dir_text.value:
                logger.warning("请选择输出目录")
                return
            output_dir = Path(self.output_dir_text.value)
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_processing = True
        self.process_btn.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.page.update()
        
        def process_task():
            import ffmpeg
            temp_audio_file = None
            temp_video_file = None
            
            try:
                total = len(self.selected_files)
                
                for idx, file_path in enumerate(self.selected_files):
                    # 更新进度
                    self.progress_text.value = f"处理中: {file_path.name} ({idx + 1}/{total})"
                    self.progress_bar.value = idx / total
                    self.page.update()
                    
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
                    
                    # 创建mask回调函数（支持按时间动态创建mask）
                    current_file_path = file_path  # 捕获当前文件路径
                    def mask_callback(h: int, w: int, current_time: float) -> np.ndarray:
                        return self._create_mask(h, w, current_file_path, current_time)
                    
                    # 步骤3：流式处理视频并直接输出到临时文件
                    temp_video_file = Path(tempfile.gettempdir()) / f"temp_video_{file_path.stem}.mp4"
                    
                    def update_progress(current, total_f):
                        progress = (idx + current / total_f) / total
                        self.progress_bar.value = progress
                        self.page.update()
                    
                    success = self.subtitle_service.process_video_streaming(
                        video_path=str(file_path),
                        output_path=str(temp_video_file),
                        mask_callback=mask_callback,
                        fps=fps,
                        progress_callback=update_progress,
                        batch_size=10  # 每批处理10帧，可根据内存情况调整
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
                self.progress_text.value = "处理完成！"
                self.progress_bar.value = 1.0
                
            except Exception as e:
                logger.error(f"处理失败: {e}", exc_info=True)
                self.progress_text.value = f"处理失败: {str(e)}"
                self.progress_text.color = ft.Colors.ERROR
            finally:
                # 确保清理临时文件
                if temp_audio_file and Path(temp_audio_file).exists():
                    try:
                        Path(temp_audio_file).unlink()
                    except:
                        pass
                if temp_video_file and Path(temp_video_file).exists():
                    try:
                        Path(temp_video_file).unlink()
                    except:
                        pass
                
                self.is_processing = False
                self.process_btn.disabled = False
                self.page.update()
        
        threading.Thread(target=process_task, daemon=True).start()
