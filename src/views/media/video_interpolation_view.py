# -*- coding: utf-8 -*-
"""视频插帧视图模块。

提供视频帧率提升（插帧）功能的用户界面。
"""

import gc
import queue
import subprocess
import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft
import ffmpeg
import numpy as np

from constants import (
    FRAME_INTERPOLATION_MODELS,
    BORDER_RADIUS_MEDIUM,
    DEFAULT_INTERPOLATION_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from constants.model_config import FrameInterpolationModelInfo
from services import ConfigService, FFmpegService
from services.frame_interpolation_service import FrameInterpolationService
from utils import format_file_size, logger, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoInterpolationView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    """视频插帧视图类。
    
    提供视频帧率提升功能，包括：
    - RIFE 模型插帧
    - 多种插帧倍率（2x, 3x, 4x）
    - GPU加速支持
    - 批量处理
    """
    
    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频插帧视图。
        
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
        self.interpolator: Optional[FrameInterpolationService] = None
        self.is_model_loading: bool = False
        self.is_processing: bool = False
        self.should_cancel: bool = False
        self.is_destroyed: bool = False
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value(
            "video_interpolation_model_key",
            DEFAULT_INTERPOLATION_MODEL_KEY
        )
        if saved_model_key not in FRAME_INTERPOLATION_MODELS:
            saved_model_key = DEFAULT_INTERPOLATION_MODEL_KEY
        self.current_model_key: str = saved_model_key
        self.current_model: FrameInterpolationModelInfo = FRAME_INTERPOLATION_MODELS[self.current_model_key]
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 获取模型路径
        self.model_path: Path = self._get_model_path()
        
        # 构建界面
        self._build_ui()
    
    def _get_model_path(self) -> Path:
        """获取模型文件路径。"""
        model_dir = self.config_service.get_data_dir() / "models" / "rife"
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir / self.current_model.filename
    
    def _init_empty_state(self) -> None:
        """初始化空文件列表状态。"""
        self.file_list_view.controls.clear()
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_LIBRARY, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("尚未选择文件", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("点击此处选择视频文件", size=12, color=ft.Colors.PRIMARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                alignment=ft.alignment.center,
                height=188,  # 220(父容器高度) - 32(padding) = 188
                on_click=self._on_select_files,
                ink=True,
            )
        )
    
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
                on_installed=self._on_ffmpeg_installed,
                on_back=self._on_back_click,
                tool_name="视频插帧"
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
                ft.Text("视频插帧", size=28, weight=ft.FontWeight.BOLD),
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
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        "支持格式: MP4, MKV, MOV, AVI, WebM 等 | 提升帧率，让视频更流畅",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=8,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINED, size=16, color=ft.Colors.BLUE),
                                    ft.Text(
                                        "提示：如需更快的处理速度，建议使用 ",
                                        size=11,
                                        color=ft.Colors.BLUE,
                                    ),
                                    ft.TextButton(
                                        "Video2X",
                                        url="https://github.com/k4yt3x/video2x/releases",
                                        style=ft.ButtonStyle(
                                            padding=0,
                                            color=ft.Colors.BLUE,
                                        ),
                                    ),
                                    ft.Text(
                                        "（目前我们的代码还未优化）",
                                        size=11,
                                        color=ft.Colors.BLUE,
                                    ),
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=4,
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
        
        # 模型选择器
        model_options = [
            ft.dropdown.Option(
                key=key,
                text=f"{model.display_name}  |  {model.size_mb}MB"
            )
            for key, model in FRAME_INTERPOLATION_MODELS.items()
        ]
        
        self.model_selector = ft.Dropdown(
            options=model_options,
            value=self.current_model_key,
            label="选择RIFE模型",
            hint_text="选择插帧模型",
            on_change=self._on_model_select,
            width=480,
            dense=True,
            text_size=13,
        )
        
        # 模型信息
        self.model_info_text = ft.Text(
            self._get_model_info_text(),
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
        
        # 加载模型按钮
        self.load_model_button = ft.ElevatedButton(
            "加载模型",
            icon=ft.Icons.UPLOAD,
            on_click=self._on_load_model,
            visible=False,
        )
        
        # 卸载模型按钮（与背景移除一致）
        self.unload_model_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            on_click=self._on_unload_model,
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
        
        # 自动加载模型设置
        auto_load_model = self.config_service.get_config_value("video_interpolation_auto_load_model", True)
        self.auto_load_checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        model_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    self.model_selector,
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
        
        # 初始化模型状态（异步检查）
        threading.Thread(target=self._check_model_status_async, daemon=True).start()
        
        # 插帧倍率选择
        saved_multiplier = self.config_service.get_config_value("video_interpolation_multiplier", 2.0)
        saved_mode = self.config_service.get_config_value("video_interpolation_mode", "preset")
        
        # 检查saved_multiplier是否是预设值
        if saved_multiplier in [2.0, 3.0, 4.0]:
            radio_value = str(int(saved_multiplier))
        else:
            radio_value = "custom"
        
        self.fps_multiplier_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="2", label="2倍帧率 (24fps→48fps, 30fps→60fps)"),
                    ft.Radio(value="3", label="3倍帧率 (24fps→72fps, 30fps→90fps)"),
                    ft.Radio(value="4", label="4倍帧率 (24fps→96fps, 30fps→120fps)"),
                    ft.Radio(value="custom", label="自定义倍数"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value=radio_value,
            on_change=self._on_multiplier_mode_change,
        )
        
        # 自定义倍数输入
        self.custom_multiplier_field = ft.TextField(
            label="自定义倍数 (例如: 1.5, 2.5, 5)",
            value=str(saved_multiplier) if radio_value == "custom" else "2.0",
            width=250,
            disabled=radio_value != "custom",
            on_change=self._on_custom_multiplier_change,
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
            text_size=13,
        )
        
        self.multiplier_hint_text = ft.Text(
            self._get_multiplier_hint(saved_multiplier),
            size=11,
            color=ft.Colors.PRIMARY,
            weight=ft.FontWeight.W_500,
        )
        
        # 插帧设置区域
        interpolation_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("插帧设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("帧率倍数:", size=13),
                    self.fps_multiplier_radio,
                    ft.Container(height=PADDING_SMALL // 2),
                    self.custom_multiplier_field,
                    self.multiplier_hint_text,
                    ft.Container(height=PADDING_SMALL // 2),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "帧率越高视频越流畅，但文件也越大",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 视频输出设置
        saved_quality = self.config_service.get_config_value("video_interpolation_quality", 20)
        self.quality_slider = ft.Slider(
            min=18,
            max=28,
            divisions=10,
            value=saved_quality,
            label="CRF: {value}",
            on_change=self._on_quality_change,
        )
        
        self.quality_value_text = ft.Text(
            f"CRF: {saved_quality} (推荐18-23，数值越小质量越好)",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 输出格式
        self.output_format_dropdown = ft.Dropdown(
            label="输出格式",
            options=[
                ft.dropdown.Option(key="same", text="保持原格式"),
                ft.dropdown.Option(key="mp4", text="MP4 (H.264)"),
                ft.dropdown.Option(key="mkv", text="MKV (H.264)"),
            ],
            value="same",
            width=300,
            dense=True,
            text_size=13,
        )
        
        # 输出模式
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
        default_output = self.config_service.get_output_dir() / "video_interpolation"
        
        self.output_dir_field = ft.TextField(
            label="输出目录",
            value=str(default_output),
            read_only=True,
            dense=True,
            expand=True,
            disabled=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("输出质量 (CRF):", size=13),
                    self.quality_slider,
                    self.quality_value_text,
                    ft.Container(height=PADDING_SMALL // 2),
                    self.output_format_dropdown,
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
        
        self.stage_text = ft.Text(
            "",
            size=12,
            color=ft.Colors.PRIMARY,
            visible=False,
        )
        
        progress_section = ft.Column(
            controls=[
                self.progress_text,
                self.progress_bar,
                self.current_file_text,
                self.stage_text,
            ],
            spacing=PADDING_SMALL,
        )
        
        # 底部大按钮
        self.process_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_SETTINGS, size=24),
                        ft.Text("开始插帧", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                on_click=self._on_process,
                height=60,
                disabled=True,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            margin=ft.margin.only(top=PADDING_MEDIUM, bottom=PADDING_SMALL),
        )
        
        self.cancel_button = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CANCEL),
                    ft.Text("取消处理"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            on_click=self._on_cancel,
            visible=False,
        )
        
        # 主布局（上下结构，类似人声分离）
        main_content = ft.Column(
            controls=[
                file_select_area,
                ft.Row(
                    controls=[
                        ft.Container(
                            content=model_section,
                            expand=True,
                            height=340,  # 固定高度让两边对齐
                        ),
                        ft.Container(
                            content=interpolation_section,
                            expand=True,
                            height=340,  # 固定高度让两边对齐
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                output_section,
                progress_section,
                self.process_button,
                self.cancel_button,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                main_content,
            ],
            spacing=0,
            expand=True,
        )
    
    def _on_ffmpeg_installed(self) -> None:
        """FFmpeg安装成功回调。"""
        # 重新构建UI
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        self._build_ui()
        try:
            self.update()
        except:
            pass
    
    def _get_model_info_text(self) -> str:
        """获取模型信息文本。"""
        return (
            f"{self.current_model.quality} | {self.current_model.performance}\n"
            f"优化场景: {self.current_model.optimized_for} | "
            f"精度: {self.current_model.precision.upper()} | "
            f"显存: {self.current_model.vram_usage}"
        )
    
    def _check_model_status_async(self) -> None:
        """异步检查模型状态。"""
        import time
        time.sleep(0.05)
        self._check_model_status()
    
    def _check_model_status(self) -> None:
        """检查模型状态并根据设置自动加载。"""
        auto_load = self.config_service.get_config_value("video_interpolation_auto_load_model", True)
        
        if self.model_path.exists():
            if auto_load and not self.interpolator:
                # 自动加载模型
                self._update_model_status("loading", "正在加载模型...")
                threading.Thread(target=self._load_model_async, daemon=True).start()
            elif self.interpolator:
                device_info = self.interpolator.get_device_info()
                self._update_model_status("ready", f"模型就绪 ({device_info})")
            else:
                self._update_model_status("downloaded", "模型已下载，未加载")
        else:
            self._update_model_status("need_download", "模型未下载")
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态显示。"""
        if self.is_destroyed:
            return
        
        if status == "loading":
            self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "downloading":
            self.model_status_icon.name = ft.Icons.DOWNLOAD
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
        elif status == "downloaded":
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
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        
        self.model_status_text.value = message
        try:
            self.page.update()
        except:
            pass
    
    def _on_model_select(self, e: ft.ControlEvent) -> None:
        """模型选择变化事件。"""
        new_model_key = e.control.value
        if new_model_key != self.current_model_key:
            # 卸载当前模型
            if self.interpolator:
                self.interpolator.unload_model()
                self.interpolator = None
            
            # 更新当前模型
            self.current_model_key = new_model_key
            self.current_model = FRAME_INTERPOLATION_MODELS[new_model_key]
            self.config_service.set_config_value("video_interpolation_model_key", new_model_key)
            
            # 更新模型路径和UI
            self.model_path = self._get_model_path()
            self.model_info_text.value = self._get_model_info_text()
            self._check_model_status()
            self._update_process_button()
    
    def _on_download_model(self, e: ft.ControlEvent) -> None:
        """下载模型按钮点击事件。"""
        self._update_model_status("downloading", "正在下载模型...")
        threading.Thread(target=self._download_model_async, daemon=True).start()
    
    def _download_model_async(self) -> None:
        """异步下载模型。"""
        try:
            import requests
            
            url = self.current_model.url
            logger.info(f"开始下载RIFE模型: {url}")
            
            # 确保目录存在
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 更新进度
                        if total_size > 0:
                            progress = downloaded / total_size
                            message = f"下载中... {progress*100:.1f}%"
                            self.model_status_text.value = message
                            try:
                                self.page.update()
                            except:
                                pass
            
            logger.info(f"✓ 模型下载完成: {self.model_path}")
            self._update_model_status("downloaded", "模型已下载，点击加载")
            self._show_snackbar(f"模型下载成功", ft.Colors.GREEN)
            
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            self._update_model_status("error", f"下载失败: {str(e)}")
            self._show_snackbar(f"下载失败: {str(e)}", ft.Colors.RED)
    
    def _on_load_model(self, e: ft.ControlEvent) -> None:
        """加载模型按钮点击事件。"""
        if self.model_path.exists() and not self.interpolator:
            self._update_model_status("loading", "正在加载模型...")
            threading.Thread(target=self._load_model_async, daemon=True).start()
        elif self.interpolator:
            self._show_snackbar("模型已加载", ft.Colors.ORANGE)
        else:
            self._show_snackbar("模型文件不存在", ft.Colors.RED)
    
    def _load_model_async(self) -> None:
        """异步加载模型。"""
        try:
            # 创建插帧服务（会自动使用config_service读取所有ONNX配置）
            self.interpolator = FrameInterpolationService(
                model_name=self.current_model_key,
                config_service=self.config_service
            )
            
            # 加载模型
            self.interpolator.load_model(self.model_path)
            
            # 更新UI
            device_info = self.interpolator.get_device_info()
            self._update_model_status("ready", f"模型就绪 ({device_info})")
            self._update_process_button()
            self._show_snackbar(f"模型加载成功，使用设备: {device_info}", ft.Colors.GREEN)
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            self.interpolator = None
            self._update_model_status("error", f"加载失败: {str(e)}")
            self._show_snackbar(f"加载失败: {str(e)}", ft.Colors.RED)
    
    def _on_unload_model(self, e: ft.ControlEvent) -> None:
        """卸载模型按钮点击事件。"""
        def confirm_unload(confirm_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
            
            if self.interpolator:
                self.interpolator.unload_model()
                self.interpolator = None
                gc.collect()
                self._show_snackbar("模型已卸载", ft.Colors.GREEN)
                self._update_model_status("downloaded", "模型已下载，未加载")
                self._update_process_button()
            else:
                self._show_snackbar("模型未加载", ft.Colors.ORANGE)
        
        def cancel_unload(cancel_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        estimated_memory = int(self.current_model.size_mb * 1.2)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认卸载模型"),
            content=ft.Column(
                controls=[
                    ft.Text("确定要卸载插帧模型吗？", size=14),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text(f"此操作将释放约{estimated_memory}MB内存，不会删除模型文件。", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("需要时可以重新加载。", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                tight=True,
                spacing=PADDING_SMALL,
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_unload),
                ft.ElevatedButton("卸载", icon=ft.Icons.POWER_SETTINGS_NEW, on_click=confirm_unload),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。"""
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("video_interpolation_auto_load_model", auto_load)
        
        # 如果启用自动加载且模型文件存在但未加载，则加载模型
        if auto_load and self.model_path.exists() and not self.interpolator:
            self._update_model_status("loading", "正在加载模型...")
            threading.Thread(target=self._load_model_async, daemon=True).start()
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(confirm_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
            
            # 如果模型已加载，先卸载
            if self.interpolator:
                self.interpolator.unload_model()
                self.interpolator = None
                gc.collect()
            
            # 删除模型文件
            try:
                if self.model_path.exists():
                    self.model_path.unlink()
                    self._show_snackbar("模型文件已删除", ft.Colors.GREEN)
                    self._update_model_status("need_download", "模型未下载")
                    self._update_process_button()
                else:
                    self._show_snackbar("模型文件不存在", ft.Colors.ORANGE)
            except Exception as ex:
                self._show_snackbar(f"删除模型失败: {ex}", ft.Colors.RED)
        
        def cancel_delete(cancel_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除模型文件"),
            content=ft.Column(
                controls=[
                    ft.Text("确定要删除插帧模型文件吗？", size=14),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("此操作将：", size=13, weight=ft.FontWeight.W_500),
                    ft.Text(f"• 删除模型文件（约{self.current_model.size_mb}MB）", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("• 如果模型已加载，将先卸载", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("删除后需要重新下载才能使用。", size=12, color=ft.Colors.ERROR),
                ],
                tight=True,
                spacing=PADDING_SMALL,
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.ElevatedButton(
                    "删除",
                    icon=ft.Icons.DELETE,
                    bgcolor=ft.Colors.ERROR,
                    color=ft.Colors.ON_ERROR,
                    on_click=confirm_delete,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                for file in result.files:
                    file_path = Path(file.path)
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择视频文件",
            allowed_extensions=["mp4", "mkv", "mov", "avi", "wmv", "flv", "webm"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder_path = Path(result.path)
                video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"}
                
                # 查找所有视频文件
                for ext in video_extensions:
                    for video_file in folder_path.glob(f"*{ext}"):
                        if video_file.is_file() and video_file not in self.selected_files:
                            self.selected_files.append(video_file)
                
                self._update_file_list()
                self._update_process_button()
                
                if not self.selected_files:
                    self._show_snackbar("文件夹中没有找到支持的视频文件", ft.Colors.ORANGE)
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.get_directory_path(dialog_title="选择包含视频文件的文件夹")
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
        self._update_process_button()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        if self.is_destroyed:
            return
        
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self._init_empty_state()
        else:
            for file_path in self.selected_files:
                try:
                    file_size = file_path.stat().st_size
                    size_str = format_file_size(file_size)
                    
                    # 获取视频信息
                    video_info = self.ffmpeg_service.safe_probe(str(file_path))
                    info_parts = [f"大小: {size_str}"]
                    
                    if video_info:
                        # 获取视频流信息
                        video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
                        if video_stream:
                            width = video_stream.get('width', '?')
                            height = video_stream.get('height', '?')
                            fps_str = video_stream.get('r_frame_rate', '?/1')
                            try:
                                fps_parts = fps_str.split('/')
                                fps = int(fps_parts[0]) / int(fps_parts[1])
                                info_parts.append(f"{width}x{height}")
                                info_parts.append(f"{fps:.2f}fps")
                            except:
                                info_parts.append(f"{width}x{height}")
                        
                        # 获取时长
                        duration = video_info.get('format', {}).get('duration')
                        if duration:
                            duration_sec = int(float(duration))
                            mins = duration_sec // 60
                            secs = duration_sec % 60
                            info_parts.append(f"{mins}:{secs:02d}")
                    
                    info_text = " | ".join(info_parts)
                    
                    self.file_list_view.controls.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.VIDEO_FILE, size=20, color=ft.Colors.PRIMARY),
                                    ft.Column(
                                        controls=[
                                            ft.Text(
                                                file_path.name,
                                                size=13,
                                                weight=ft.FontWeight.W_500,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Text(
                                                info_text,
                                                size=11,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE,
                                        icon_size=18,
                                        tooltip="移除",
                                        on_click=lambda e, f=file_path: self._remove_file(f),
                                    ),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                            padding=ft.padding.symmetric(vertical=4, horizontal=4),
                            border_radius=BORDER_RADIUS_MEDIUM,
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
                        )
                    )
                except Exception as e:
                    logger.error(f"获取文件信息失败 {file_path.name}: {e}")
                    # 出错时仍然显示文件
                    self.file_list_view.controls.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.VIDEO_FILE, size=20),
                                    ft.Column(
                                        controls=[
                                            ft.Text(file_path.name, size=13),
                                            ft.Text(
                                                str(file_path.parent),
                                                size=11,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE,
                                        icon_size=18,
                                        tooltip="移除",
                                        on_click=lambda e, f=file_path: self._remove_file(f),
                                    ),
                                ],
                                spacing=PADDING_SMALL,
                            ),
                            padding=ft.padding.symmetric(vertical=4, horizontal=4),
                        )
                    )
        
        try:
            self.page.update()
        except:
            pass
    
    def _remove_file(self, file_path: Path) -> None:
        """从列表中移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
            self._update_process_button()
    
    def _update_process_button(self) -> None:
        """更新处理按钮状态。"""
        if self.is_destroyed:
            return
        
        try:
            button = self.process_button.content
            button.disabled = not (self.selected_files and self.interpolator)
            self.page.update()
        except:
            pass
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        is_custom = e.control.value == "custom"
        self.output_dir_field.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        try:
            self.page.update()
        except:
            pass
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.page.update()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _get_multiplier_hint(self, multiplier: float) -> str:
        """获取倍数提示文本。"""
        examples = []
        for fps in [24, 25, 30, 60]:
            target = int(fps * multiplier)
            examples.append(f"{fps}→{target}")
        return f"⚡ {multiplier}x 倍率示例: {', '.join(examples)} fps"
    
    def _get_current_multiplier(self) -> float:
        """获取当前选择的倍数。"""
        mode = self.fps_multiplier_radio.value
        if mode == "custom":
            try:
                return float(self.custom_multiplier_field.value)
            except:
                return 2.0
        else:
            return float(mode)
    
    def _on_multiplier_mode_change(self, e: ft.ControlEvent) -> None:
        """插帧倍率模式变化事件。"""
        mode = e.control.value
        
        if mode == "custom":
            # 启用自定义输入
            self.custom_multiplier_field.disabled = False
            multiplier = self._get_current_multiplier()
        else:
            # 禁用自定义输入，使用预设值
            self.custom_multiplier_field.disabled = True
            multiplier = float(mode)
        
        # 更新提示文本
        self.multiplier_hint_text.value = self._get_multiplier_hint(multiplier)
        
        # 保存配置
        self.config_service.set_config_value("video_interpolation_multiplier", multiplier)
        self.config_service.set_config_value("video_interpolation_mode", mode)
        
        try:
            self.page.update()
        except:
            pass
    
    def _on_custom_multiplier_change(self, e: ft.ControlEvent) -> None:
        """自定义倍数输入变化事件。"""
        try:
            multiplier = float(e.control.value)
            
            # 验证范围
            if multiplier < 1.0:
                multiplier = 1.0
                self.custom_multiplier_field.value = "1.0"
            elif multiplier > 10.0:
                multiplier = 10.0
                self.custom_multiplier_field.value = "10.0"
            
            # 更新提示文本
            self.multiplier_hint_text.value = self._get_multiplier_hint(multiplier)
            
            # 保存配置
            self.config_service.set_config_value("video_interpolation_multiplier", multiplier)
            
            try:
                self.page.update()
            except:
                pass
        except ValueError:
            # 输入无效，显示错误
            self.multiplier_hint_text.value = "⚠️ 请输入有效的数字 (1.0 - 10.0)"
            self.multiplier_hint_text.color = ft.Colors.ERROR
            try:
                self.page.update()
            except:
                pass
    
    def _on_quality_change(self, e: ft.ControlEvent) -> None:
        """输出质量变化事件。"""
        quality = int(e.control.value)
        self.quality_value_text.value = f"CRF: {quality} (推荐18-23，数值越小质量越好)"
        self.config_service.set_config_value("video_interpolation_quality", quality)
        try:
            self.page.update()
        except:
            pass
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。"""
        if not self.selected_files:
            self._show_snackbar("请先选择视频文件", ft.Colors.ORANGE)
            return
        
        if not self.interpolator:
            self._show_snackbar("模型未加载", ft.Colors.RED)
            return
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.output_dir_field.value)
        else:
            output_dir = None  # 保存到源文件目录
        
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 开始处理
        self.is_processing = True
        self.should_cancel = False
        
        button = self.process_button.content
        button.disabled = True
        self.cancel_button.visible = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.current_file_text.visible = True
        self.stage_text.visible = True
        
        try:
            self.page.update()
        except:
            pass
        
        # 在后台线程处理
        threading.Thread(
            target=self._process_task,
            args=(self.selected_files[:], output_dir),
            daemon=True
        ).start()
    
    def _on_cancel(self, e: ft.ControlEvent) -> None:
        """取消处理。"""
        self.should_cancel = True
        self._show_snackbar("正在取消...", ft.Colors.ORANGE)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.is_processing:
            # 显示确认对话框
            def confirm_exit(confirm_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.page.update()
                self.cleanup()
                if self.on_back:
                    self.on_back()
            
            def cancel_exit(cancel_e: ft.ControlEvent) -> None:
                dialog.open = False
                self.page.update()
            
            dialog = ft.AlertDialog(
                title=ft.Text("确认退出"),
                content=ft.Text("任务正在进行中，确定要退出吗？这将取消当前任务。"),
                actions=[
                    ft.TextButton("取消", on_click=cancel_exit),
                    ft.TextButton("确定退出", on_click=confirm_exit),
                ],
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            if self.on_back:
                self.on_back()
    
    def _process_task(self, files: List[Path], output_dir: Optional[Path]) -> None:
        """处理任务（后台线程）。"""
        success_count = 0
        total_files = len(files)
        
        try:
            multiplier = self._get_current_multiplier()
            quality = int(self.quality_slider.value)
            output_format = self.output_format_dropdown.value
            
            for idx, input_path in enumerate(files, 1):
                if self.should_cancel:
                    break
                
                try:
                    # 更新进度
                    progress = (idx - 1) / total_files
                    self._update_progress(
                        progress,
                        f"正在处理 ({idx}/{total_files})",
                        input_path.name,
                        "准备中..."
                    )
                    
                    # 处理单个视频
                    self._process_single_video(
                        input_path,
                        output_dir,
                        multiplier,
                        quality,
                        output_format,
                        idx,
                        total_files
                    )
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"处理视频失败 {input_path.name}: {e}")
                    self._show_snackbar(f"处理失败: {input_path.name}", ft.Colors.RED)
            
        finally:
            self._on_process_complete(success_count, total_files, output_dir)
    
    def _process_single_video(
        self,
        input_path: Path,
        output_dir: Optional[Path],
        multiplier: float,
        quality: int,
        output_format: str,
        current_idx: int = 1,
        total_count: int = 1
    ) -> None:
        """处理单个视频。
        
        Args:
            input_path: 输入视频路径
            output_dir: 输出目录（None表示保存到源文件目录）
            multiplier: 插帧倍率
            quality: 输出质量(CRF)
            output_format: 输出格式
            current_idx: 当前文件索引
            total_count: 总文件数
        """
        logger.info(f"开始插帧: {input_path.name}")
        logger.info(f"  倍率: {multiplier}x")
        
        # 确定输出路径
        if output_dir is None:
            # 保存到源文件目录
            if output_format == "same":
                output_path = input_path.parent / f"{input_path.stem}_interpolated{input_path.suffix}"
            else:
                output_path = input_path.parent / f"{input_path.stem}_interpolated.{output_format}"
        else:
            # 保存到自定义目录
            if output_format == "same":
                output_path = output_dir / f"{input_path.stem}_interpolated{input_path.suffix}"
            else:
                output_path = output_dir / f"{input_path.stem}_interpolated.{output_format}"
        
        # 根据全局设置决定是否添加序号
        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
        output_path = get_unique_path(output_path, add_sequence=add_sequence)
        
        logger.info(f"  输出: {output_path}")
        
        # 阶段1: 获取视频信息
        self._update_progress(
            (current_idx - 1) / total_count,
            f"正在处理 ({current_idx}/{total_count})",
            input_path.name,
            "分析视频信息..."
        )
        
        # 获取FFmpeg路径
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        ffprobe_path = self.ffmpeg_service.get_ffprobe_path()
        
        # 获取视频信息
        probe_result = self.ffmpeg_service.safe_probe(str(input_path))
        if not probe_result:
            raise RuntimeError(f"无法获取视频信息: {input_path}")
        
        video_info = next((s for s in probe_result['streams'] if s['codec_type'] == 'video'), None)
        if not video_info:
            raise RuntimeError(f"视频中没有视频流: {input_path}")
        
        width = int(video_info['width'])
        height = int(video_info['height'])
        
        # 检查尺寸是否需要对齐（很多编码器要求是2的倍数）
        if width % 2 != 0 or height % 2 != 0:
            logger.warning(f"视频尺寸 {width}x{height} 不是偶数，将自动调整")
            # 调整为偶数（向下取整到最近的偶数）
            width = width - (width % 2)
            height = height - (height % 2)
            logger.info(f"调整后尺寸: {width}x{height}")
        
        fps_str = video_info.get('r_frame_rate', '30/1')
        fps_parts = fps_str.split('/')
        original_fps = int(fps_parts[0]) / int(fps_parts[1])
        target_fps = original_fps * multiplier
        
        # 获取总帧数
        duration = float(probe_result['format']['duration'])
        total_frames = int(duration * original_fps)
        
        logger.info(f"  视频信息: {width}x{height} @ {original_fps:.2f}fps")
        logger.info(f"  目标帧率: {target_fps:.2f}fps")
        logger.info(f"  预计总帧数: {total_frames}")
        
        # 阶段2: 检查是否有音频
        has_audio = any(s['codec_type'] == 'audio' for s in probe_result['streams'])
        if has_audio:
            logger.info("检测到音频流，将在处理完成后合并")
        
        # 阶段3: 启动解码器和编码器
        self._update_progress(
            (current_idx - 1 + 0.1) / total_count,
            f"正在处理 ({current_idx}/{total_count})",
            input_path.name,
            "启动视频解码器..."
        )
        
        # 解码器进程（输出原始RGB帧）
        decoder_process = None
        encoder_process = None
        
        try:
            logger.info("启动解码器...")
            
            # 构建解码器流
            decoder_stream = ffmpeg.input(str(input_path))
            
            # 先用idet检测交错，再用yadif去交错
            logger.info("应用去交错处理（idet+yadif）防止画面撕裂...")
            decoder_stream = (
                decoder_stream
                .filter('idet')  # 检测交错
                .filter('yadif', mode=0, parity=-1, deint=1)  # 强制去交错
            )
            
            # 如果尺寸需要调整，添加scale滤镜
            original_width = int(video_info['width'])
            original_height = int(video_info['height'])
            if width != original_width or height != original_height:
                logger.info(f"应用scale滤镜: {original_width}x{original_height} → {width}x{height}")
                decoder_stream = decoder_stream.filter('scale', width, height)
            
            # 构建解码器命令并启动
            # 注意：不能用 run_async(quiet=True)，因为它会设置 stderr=PIPE 而不是 DEVNULL
            decoder_cmd = (
                decoder_stream
                .output('pipe:', format='rawvideo', pix_fmt='rgb24')
                .compile(cmd=ffmpeg_path)
            )
            decoder_process = subprocess.Popen(
                decoder_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL  # 必须是 DEVNULL，避免缓冲区阻塞
            )
            
            # 启动编码器
            self._update_progress(
                (current_idx - 1 + 0.12) / total_count,
                f"正在处理 ({current_idx}/{total_count})",
                input_path.name,
                "启动视频编码器..."
            )
            
            logger.info("启动编码器...")
            encoder_input = ffmpeg.input(
                'pipe:',
                format='rawvideo',
                pix_fmt='rgb24',
                s=f'{width}x{height}',
                r=target_fps
            )
            
            # 检测并使用GPU编码器
            gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
            
            if gpu_encoder:
                logger.info(f"✓ 使用GPU编码器: {gpu_encoder}")
                # GPU编码器参数
                if 'nvenc' in gpu_encoder:
                    # NVIDIA NVENC
                    output_params = {
                        'vcodec': gpu_encoder,
                        'preset': 'p4',  # p1-p7, p4是平衡点
                        'cq': quality,  # NVENC使用cq而不是crf
                        'pix_fmt': 'yuv420p',
                        'g': 250,  # GOP大小
                        'bf': 0,  # 禁用B帧，避免帧序列问题
                        'flags': '+cgop',  # 关闭场景切换检测
                        'forced-idr': '1',  # 强制IDR帧
                    }
                elif 'amf' in gpu_encoder:
                    # AMD AMF
                    output_params = {
                        'vcodec': gpu_encoder,
                        'quality': 'balanced',
                        'rc': 'cqp',
                        'qp_p': quality,
                        'pix_fmt': 'yuv420p',
                        'g': 250,
                    }
                elif 'qsv' in gpu_encoder:
                    # Intel Quick Sync
                    output_params = {
                        'vcodec': gpu_encoder,
                        'preset': 'medium',
                        'global_quality': quality,
                        'pix_fmt': 'yuv420p',
                        'g': 250,
                    }
                else:
                    # 其他GPU编码器，使用通用参数
                    output_params = {
                        'vcodec': gpu_encoder,
                        'crf': quality,
                        'preset': 'medium',
                        'pix_fmt': 'yuv420p',
                        'g': 250,
                    }
            else:
                # CPU编码器（回退方案）
                logger.info("使用CPU编码器: libx264")
                output_params = {
                    'vcodec': 'libx264',
                    'crf': quality,
                    'preset': 'medium',
                    'pix_fmt': 'yuv420p',
                    'g': 250,  # GOP大小
                    'bf': 0,  # 禁用B帧，避免帧序列问题
                    'flags': '+cgop',  # 关闭场景切换检测
                }
            
            # 阶段4: 处理帧（插帧）- 先计算预期输出帧数
            logger.info("开始插帧处理...")
            frame_size = width * height * 3
            processed_frames = 0
            original_frames_read = 0
            
            # 计算预期的总输出帧数
            # 公式：原始帧数 + (原始帧数-1) * (插入帧数)
            n_interpolate = int(multiplier) - 1
            expected_total = total_frames + (total_frames - 1) * n_interpolate
            logger.info(f"预期输出帧数: {expected_total} 帧 (原始 {total_frames} + 插值 {(total_frames - 1) * n_interpolate})")
            
            # 构建编码器命令并启动
            # 注意：不能用 run_async(quiet=True)，因为它会设置 stderr=PIPE 而不是 DEVNULL
            encoder_cmd = (
                encoder_input
                .output(str(output_path), **output_params)
                .global_args('-fflags', '+genpts')  # 生成presentation时间戳
                .global_args('-vsync', 'cfr')  # 恒定帧率（Constant Frame Rate）
                .overwrite_output()
                .compile(cmd=ffmpeg_path)
            )
            
            logger.info(f"编码器命令: {' '.join(encoder_cmd)}")
            
            encoder_process = subprocess.Popen(
                encoder_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL  # 必须是 DEVNULL，避免缓冲区阻塞
            )
            
            # 🚀 使用队列和写入线程，避免 stdin.write() 阻塞主线程
            frame_queue: queue.Queue = queue.Queue(maxsize=30)  # 最多缓存30帧
            write_error = threading.Event()
            write_done = threading.Event()
            frames_written = [0]  # 使用列表以便在闭包中修改
            
            def writer_thread():
                """写入线程：从队列取帧写入FFmpeg stdin"""
                try:
                    while True:
                        try:
                            frame_data = frame_queue.get(timeout=0.5)
                        except queue.Empty:
                            if write_done.is_set() and frame_queue.empty():
                                logger.info("队列已空且处理完成，写入线程退出")
                                break
                            continue
                        
                        if frame_data is None:  # 结束信号
                            logger.info("收到结束信号，写入线程退出")
                            break
                        
                        try:
                            encoder_process.stdin.write(frame_data)
                            frames_written[0] += 1
                        except BrokenPipeError:
                            logger.error("编码器管道断开")
                            write_error.set()
                            break
                        except Exception as e:
                            logger.error(f"写入帧失败: {e}")
                            write_error.set()
                            break
                except Exception as e:
                    logger.error(f"写入线程异常: {e}")
                    write_error.set()
                finally:
                    try:
                        encoder_process.stdin.close()
                        logger.info("已关闭编码器stdin")
                    except Exception as e:
                        logger.warning(f"关闭stdin失败: {e}")
                    logger.info(f"写入线程结束，共写入 {frames_written[0]} 帧")
            
            # 启动写入线程
            writer = threading.Thread(target=writer_thread, daemon=True)
            writer.start()
            
            # 读取第一帧
            prev_frame_data = decoder_process.stdout.read(frame_size)
            if not prev_frame_data or len(prev_frame_data) != frame_size:
                write_done.set()
                frame_queue.put(None)
                raise RuntimeError("无法读取视频帧")
            
            prev_frame = np.frombuffer(prev_frame_data, dtype=np.uint8).reshape((height, width, 3))
            original_frames_read += 1
            
            # 写入第一帧到队列
            frame_queue.put(prev_frame.tobytes())
            processed_frames += 1
            
            # 初始进度更新
            base_progress = (current_idx - 1) / total_count
            self._update_progress(
                base_progress + 0.15,
                f"正在处理 ({current_idx}/{total_count})",
                input_path.name,
                f"插帧处理中... 1/{expected_total} 帧 (0%)"
            )
            
            # 主处理循环
            while not self.should_cancel and not write_error.is_set():
                # 读取下一帧
                curr_frame_data = decoder_process.stdout.read(frame_size)
                if not curr_frame_data or len(curr_frame_data) != frame_size:
                    logger.info(f"视频帧读取完成，共读取 {original_frames_read} 帧")
                    break
                
                curr_frame = np.frombuffer(curr_frame_data, dtype=np.uint8).reshape((height, width, 3))
                original_frames_read += 1
                
                # 在两帧之间插帧
                if n_interpolate > 0:
                    try:
                        # ✓✓✓ 关键优化：使用超高性能版本以最大化GPU利用率
                        interpolated_frames = self.interpolator.interpolate_n_times_highperf(
                            prev_frame,
                            curr_frame,
                            n_interpolate,
                            aggressive=True  # 启用激进模式
                        )
                        
                        # 将插值帧放入队列（非阻塞放置）
                        for interp_frame in interpolated_frames:
                            if write_error.is_set() or self.should_cancel:
                                break
                            try:
                                # ✓ 使用put_nowait避免阻塞GPU处理
                                frame_queue.put_nowait(interp_frame.tobytes())
                                processed_frames += 1
                            except queue.Full:
                                # 队列满时短暂等待而不是长时间阻塞
                                try:
                                    frame_queue.put(interp_frame.tobytes(), timeout=0.5)
                                    processed_frames += 1
                                except queue.Full:
                                    logger.debug("帧缓冲满，跳过以保持GPU流畅")
                    except Exception as e:
                        logger.error(f"插帧失败: {e}")

                
                if write_error.is_set() or self.should_cancel:
                    break
                
                # 将当前帧放入队列
                try:
                    frame_queue.put(curr_frame.tobytes(), timeout=5.0)
                    processed_frames += 1
                except queue.Full:
                    logger.warning("帧队列满，跳过当前帧")
                
                # 更新进度（不会被阻塞）
                base_progress = (current_idx - 1) / total_count
                frame_progress = (processed_frames / expected_total) * 0.7
                total_progress = base_progress + 0.15 + frame_progress
                percentage = min(processed_frames * 100 // expected_total, 99)
                
                self._update_progress(
                    total_progress,
                    f"正在处理 ({current_idx}/{total_count})",
                    input_path.name,
                    f"插帧处理中... {processed_frames}/{expected_total} 帧 ({percentage}%)"
                )
                
                # 准备下一轮
                prev_frame = curr_frame
            
            # 通知写入线程结束
            logger.info(f"✓ 帧处理完成，共输出 {processed_frames} 帧，等待写入完成...")
            write_done.set()
            
            self._update_progress(
                (current_idx - 1 + 0.85) / total_count,
                f"正在处理 ({current_idx}/{total_count})",
                input_path.name,
                "等待帧写入完成..."
            )
            
            # 发送结束信号（使用循环避免阻塞）
            for _ in range(100):  # 最多尝试100次
                try:
                    frame_queue.put(None, timeout=0.5)
                    break
                except queue.Full:
                    # 队列满，等待写入线程消费
                    if not writer.is_alive():
                        break
            
            # 等待写入线程结束
            writer.join(timeout=60.0)  # 最多等60秒
            if writer.is_alive():
                logger.warning("写入线程超时，强制终止")
            
            self._update_progress(
                (current_idx - 1 + 0.90) / total_count,
                f"正在处理 ({current_idx}/{total_count})",
                input_path.name,
                "FFmpeg编码收尾中，请稍候..."
            )
            
            # 等待编码器和解码器完成
            try:
                encoder_process.wait(timeout=120.0)  # 最多等2分钟
            except subprocess.TimeoutExpired:
                logger.warning("FFmpeg编码超时，强制终止")
                encoder_process.kill()
            
            try:
                decoder_process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                decoder_process.kill()
            
            logger.info(f"✓ 插帧完成，处理了 {processed_frames} 帧")
            
            self._update_progress(
                (current_idx - 1 + 0.95) / total_count,
                f"正在处理 ({current_idx}/{total_count})",
                input_path.name,
                "✓ 视频编码完成"
            )
            
            # 如果有音频，用FFmpeg快速合并
            if has_audio and not self.should_cancel:
                self._update_progress(
                    (current_idx - 1 + 0.96) / total_count,
                    f"正在处理 ({current_idx}/{total_count})",
                    input_path.name,
                    "正在合并音频..."
                )
                
                logger.info("使用FFmpeg快速合并音频...")
                temp_video = output_path.with_suffix('.temp.mp4')
                output_path.rename(temp_video)
                
                try:
                    # 使用copy模式快速合并，不重新编码
                    video_stream = ffmpeg.input(str(temp_video))
                    audio_stream = ffmpeg.input(str(input_path)).audio
                    
                    (
                        ffmpeg
                        .output(
                            video_stream,
                            audio_stream,
                            str(output_path),
                            vcodec='copy',  # 复制视频流
                            acodec='copy',  # 复制音频流
                        )
                        .overwrite_output()
                        .run(cmd=ffmpeg_path, capture_stdout=True, capture_stderr=True, quiet=True)
                    )
                    
                    temp_video.unlink()
                    logger.info("✓ 音频合并完成")
                except Exception as e:
                    logger.error(f"音频合并失败: {e}")
                    # 恢复临时文件
                    if temp_video.exists():
                        temp_video.rename(output_path)
            
            if not self.should_cancel:
                self._update_progress(
                    current_idx / total_count,
                    f"正在处理 ({current_idx}/{total_count})",
                    input_path.name,
                    "✓ 完成"
                )
                self._show_snackbar(f"插帧完成: {input_path.name}", ft.Colors.GREEN)
            
        except Exception as e:
            logger.error(f"视频处理失败: {e}", exc_info=True)
            raise
        
        finally:
            # 清理子进程
            if decoder_process and decoder_process.poll() is None:
                decoder_process.terminate()
                try:
                    decoder_process.kill()
                except:
                    pass
            
            if encoder_process and encoder_process.poll() is None:
                encoder_process.terminate()
                try:
                    encoder_process.kill()
                except:
                    pass
            
            # ✓ 无需清理临时音频文件（零临时文件架构）
            
            if self.should_cancel and output_path.exists():
                try:
                    output_path.unlink()
                    logger.info(f"已删除不完整的输出文件: {output_path}")
                except:
                    pass
    
    def _update_progress(self, value: float, text: str, current_file: str = "", stage: str = "") -> None:
        """更新进度显示。
        
        Args:
            value: 进度值 (0.0-1.0)
            text: 进度文本
            current_file: 当前处理的文件名
            stage: 当前阶段描述
        """
        if self.is_destroyed:
            return
        
        self.progress_bar.value = value
        self.progress_text.value = text
        
        if current_file:
            self.current_file_text.value = f"📁 {current_file}"
        
        if stage:
            self.stage_text.value = f"⚙️ {stage}"
        
        try:
            self.page.update()
        except:
            pass
    
    def _on_process_complete(self, success_count: int, total: int, output_dir: Optional[Path]) -> None:
        """处理完成回调。"""
        if self.is_destroyed:
            return
        
        self.is_processing = False
        self.progress_bar.value = 1.0
        
        if self.should_cancel:
            self.progress_text.value = f"处理已取消 - 已完成: {success_count}/{total}"
            self.stage_text.value = ""
        else:
            self.progress_text.value = f"✓ 处理完成 - 成功: {success_count}/{total}"
            self.stage_text.value = "所有文件处理完成"
        
        button = self.process_button.content
        button.disabled = False
        self.cancel_button.visible = False
        
        try:
            self.page.update()
        except:
            pass
        
        if self.should_cancel:
            self._show_snackbar(f"处理已取消，已完成 {success_count} 个文件", ft.Colors.ORANGE)
        elif output_dir is None:
            self._show_snackbar(
                f"插帧完成! 成功处理 {success_count} 个文件，保存在源文件目录",
                ft.Colors.GREEN
            )
        else:
            self._show_snackbar(
                f"插帧完成! 成功处理 {success_count} 个文件，保存到: {output_dir}",
                ft.Colors.GREEN
            )
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
        if self.is_destroyed or not self.page:
            return
        
        try:
            snackbar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=color,
                duration=3000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
        except:
            pass
    
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
            self._show_snackbar(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_snackbar("视频插帧不支持该格式", ft.Colors.ORANGE)
        self.page.update()
    
    def cleanup(self) -> None:
        """清理资源。"""
        logger.info("清理视频插帧视图...")
        self.is_destroyed = True
        
        if self.is_processing:
            self.should_cancel = True
        
        # 清理文件列表
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        
        if self.interpolator:
            self.interpolator.unload_model()
            self.interpolator = None
        
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        
        gc.collect()
        logger.info("✓ 视频插帧视图已清理")
