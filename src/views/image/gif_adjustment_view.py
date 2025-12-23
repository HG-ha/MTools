# -*- coding: utf-8 -*-
"""GIF 调整视图模块。

提供 GIF 动画调整功能的用户界面。
"""

import threading
from pathlib import Path
from typing import Callable, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from models import GifAdjustmentOptions
from services import ConfigService, ImageService, FFmpegService
from utils import format_file_size, GifUtils, logger
from views.media.ffmpeg_install_view import FFmpegInstallView


class GifAdjustmentView(ft.Container):
    """GIF 调整视图类。
    
    提供 GIF 动画调整功能，包括：
    - 调整首帧（封面）
    - 调整播放速度
    - 设置循环次数
    - 截取帧范围
    - 跳帧处理
    - 反转播放
    """
    
    # 支持的格式
    SUPPORTED_EXTENSIONS = {'.gif', '.mov', '.mp4'}
    
    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化 GIF 调整视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
            parent_container: 父容器（用于跳转到 FFmpeg 安装界面）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        self.parent_container: Optional[ft.Container] = parent_container
        
        self.selected_file: Optional[Path] = None
        self.frame_count: int = 0
        self.original_durations: list = []
        self.original_loop: int = 0
        self.is_live_photo: bool = False  # 标记是否为实况图
        self.live_photo_info: Optional[dict] = None  # 实况图信息
        self.temp_video_path: Optional[Path] = None  # 实况图临时视频路径（用于预览）
        self.video_duration: float = 0.0  # 实况图视频时长（秒）
        
        # 封面预览防抖定时器
        self.cover_preview_timer: Optional[threading.Timer] = None
        self.cover_preview_lock: threading.Lock = threading.Lock()
        self.current_preview_frame: int = -1  # 当前正在预览的帧索引
        self.current_file_id: str = ""  # 当前文件的唯一标识符（防止显示旧文件的帧）
        
        # 获取 FFmpeg 服务
        self.ffmpeg_service: FFmpegService = FFmpegService(config_service)
        
        # FFmpeg 安装视图（延迟创建）
        self.ffmpeg_install_view = None
        self.pending_file: Optional[Path] = None  # 等待 FFmpeg 安装后要加载的文件
        
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
        is_ffmpeg_available, ffmpeg_message = self.ffmpeg_service.is_ffmpeg_available()
        
        # 如果 FFmpeg 不可用，显示安装视图
        if not is_ffmpeg_available:
            # 只有当有父容器时才显示安装视图，否则显示常规界面但禁用实况图功能
            if self.parent_container:
                self.padding = ft.padding.all(0)
                self.content = FFmpegInstallView(
                    self.page,
                    self.ffmpeg_service,
                    on_installed=self._on_ffmpeg_installed_rebuild,
                    on_back=self._on_back_click,
                    tool_name="GIF / 实况图调整"
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
                ft.Text("GIF / 实况图调整", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_info_text: ft.Text = ft.Text(
            "未选择文件",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        file_select_row: ft.Row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "选择 GIF / 实况图",
                    icon=ft.Icons.FILE_UPLOAD,
                    on_click=self._on_select_file,
                ),
                self.file_info_text,
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 左侧：预览区域
        self.gif_preview: ft.Image = ft.Image(
            src="",
            width=400,
            height=400,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        self.preview_placeholder: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.GIF_BOX_OUTLINED, size=80, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("点击选择 GIF 或实况图", size=16, weight=ft.FontWeight.W_500, ),
                    ft.Text("支持调整首帧、速度、循环等", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("实况图将自动提取视频部分", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_SMALL,
            ),
            alignment=ft.alignment.center,
            visible=True,
        )
        
        preview_stack: ft.Stack = ft.Stack(
            controls=[
                self.preview_placeholder,
                self.gif_preview,
            ],
        )
        
        preview_container: ft.Container = ft.Container(
            content=preview_stack,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            alignment=ft.alignment.center,
            height=420,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            ink=True,
            on_click=self._on_select_file,
            tooltip="点击选择或更换 GIF 文件",
        )
        
        # 右侧：调整选项
        # 1. 首帧设置
        self.cover_frame_slider: ft.Slider = ft.Slider(
            min=0,
            max=1,
            value=0,
            divisions=1,
            label="{value}",
            disabled=True,
            on_change=self._on_cover_frame_change,
        )
        
        self.cover_frame_text: ft.Text = ft.Text("首帧: 第 1 帧", size=14)
        
        # 封面预览图
        self.cover_preview_image: ft.Image = ft.Image(
            src="",
            width=200,
            height=200,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )
        
        self.cover_preview_placeholder: ft.Container = ft.Container(
            content=ft.Text(
                "预览将在拖动时显示",
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.alignment.center,
            visible=True,
        )
        
        cover_preview_stack: ft.Stack = ft.Stack(
            controls=[
                self.cover_preview_placeholder,
                self.cover_preview_image,
            ],
        )
        
        cover_preview_container: ft.Container = ft.Container(
            content=cover_preview_stack,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_SMALL,
            alignment=ft.alignment.center,
            height=220,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.PRIMARY),
        )
        
        cover_frame_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("封面设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("设置未播放时显示的默认帧", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    cover_preview_container,
                    self.cover_frame_text,
                    self.cover_frame_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 2. 速度调整
        self.speed_slider: ft.Slider = ft.Slider(
            min=0.25,
            max=4.0,
            value=1.0,
            divisions=15,
            label="{value}x",
            disabled=True,
            on_change=self._on_speed_change,
        )
        
        self.speed_text: ft.Text = ft.Text("播放速度: 1.0x (原速)", size=14)
        
        speed_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("播放速度", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("调整 GIF 播放速度 (0.25x - 4.0x)", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ORANGE),
                                ft.Text(
                                    "提示: 超过 3x 速度时建议配合跳帧使用以获得更好效果",
                                    size=11,
                                    color=ft.Colors.ORANGE,
                                ),
                            ],
                            spacing=4,
                        ),
                        margin=ft.margin.only(bottom=PADDING_SMALL),
                    ),
                    self.speed_text,
                    self.speed_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 3. 循环设置
        self.loop_checkbox: ft.Checkbox = ft.Checkbox(
            label="无限循环",
            value=True,
            disabled=True,
            on_change=self._on_loop_checkbox_change,
        )
        
        self.loop_count_field: ft.TextField = ft.TextField(
            label="循环次数",
            value="0",
            width=120,
            disabled=True,
            dense=True,
            on_change=self._on_loop_count_change,
        )
        
        loop_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("循环设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("设置 GIF 循环播放次数", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Row(
                        controls=[
                            self.loop_checkbox,
                            self.loop_count_field,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 4. 帧范围截取
        self.trim_start_field: ft.TextField = ft.TextField(
            label="起始帧",
            value="1",
            width=100,
            disabled=True,
            dense=True,
            text_align=ft.TextAlign.CENTER,
        )
        
        self.trim_end_field: ft.TextField = ft.TextField(
            label="结束帧",
            value="1",
            width=100,
            disabled=True,
            dense=True,
            text_align=ft.TextAlign.CENTER,
        )
        
        trim_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("帧范围截取", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("截取指定范围的帧（包含起始和结束帧）", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Row(
                        controls=[
                            self.trim_start_field,
                            ft.Text("-", size=16),
                            self.trim_end_field,
                        ],
                        spacing=PADDING_SMALL,
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 5. 跳帧设置
        self.drop_frame_slider: ft.Slider = ft.Slider(
            min=1,
            max=10,
            value=1,
            divisions=9,
            label="{value}",
            disabled=True,
            on_change=self._on_drop_frame_change,
        )
        
        self.drop_frame_text: ft.Text = ft.Text("保留所有帧 (每 1 帧保留)", size=14)
        
        drop_frame_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("跳帧设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("减少帧数以降低文件大小", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    self.drop_frame_text,
                    self.drop_frame_slider,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 6. 其他选项
        self.reverse_checkbox: ft.Checkbox = ft.Checkbox(
            label="反转播放顺序",
            value=False,
            disabled=True,
        )
        
        other_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("其他选项", size=14, weight=ft.FontWeight.W_500),
                    self.reverse_checkbox,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀 _adjusted）"),
                    ft.Radio(value="custom", label="自定义输出路径"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_field: ft.TextField = ft.TextField(
            label="输出路径",
            value="",
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        # 输出格式选择（动态显示，根据输入文件类型）
        self.output_format_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="gif", label="GIF 动图 - 兼容性最好，适合分享"),
                    ft.Radio(value="video", label="视频（MP4）- 文件更小，画质更好"),
                    ft.Radio(value="live_photo", label="实况图（Motion Photo）- 保持原格式", visible=False),
                ],
                spacing=PADDING_SMALL,
            ),
            value="gif",
            on_change=self._on_output_format_change,
        )
        
        self.output_format_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出格式", size=13, weight=ft.FontWeight.W_500),
                    self.output_format_radio,
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,  # 初始隐藏，选择文件后显示
        )
        
        output_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=14, weight=ft.FontWeight.W_500),
                    self.output_format_container,
                    ft.Divider(height=1, visible=False),  # 分隔线，动态显示
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_field,
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
        
        # 保存分隔线引用，便于动态控制
        self.format_divider = output_section.content.controls[2]
        
        # 调整选项可滚动区域
        options_scroll: ft.Column = ft.Column(
            controls=[
                cover_frame_section,
                speed_section,
                loop_section,
                trim_section,
                drop_frame_section,
                other_section,
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
                    content=preview_container,
                    expand=2,
                ),
                ft.Container(
                    content=options_scroll,
                    expand=3,
                ),
            ],
            spacing=PADDING_LARGE,
            expand=True,
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
                        ft.Icon(ft.Icons.AUTO_AWESOME, size=24),
                        ft.Text("开始调整并导出", size=18, weight=ft.FontWeight.W_600),
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
                file_select_row,
                ft.Container(height=PADDING_SMALL),
                main_content,
                ft.Container(height=PADDING_MEDIUM),
                progress_container,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
            ],
            spacing=0,
            expand=True,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.on_back:
            self.on_back()
    
    def _on_select_file(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                file_path = Path(result.files[0].path)
                ext = file_path.suffix.lower()
                
                if ext == '.gif':
                    # GIF 文件
                    self._load_gif_file(file_path)
                elif ext in ['.jpg', '.jpeg', '.jfif', '.heic', '.heif']:
                    # 可能是实况图
                    self._load_live_photo_file(file_path)
                else:
                    self._show_snackbar("请选择 GIF 或实况图文件", ft.Colors.ORANGE)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择 GIF 或实况图文件",
            allowed_extensions=["gif", "jpg", "jpeg", "jfif", "heic", "heif"],
            allow_multiple=False,
        )
    
    def _load_gif_file(self, file_path: Path) -> None:
        """加载 GIF 文件。
        
        Args:
            file_path: GIF 文件路径
        """
        # 清除旧的预览任务
        self._clear_preview_tasks()
        
        self.selected_file = file_path
        
        # 生成新的文件ID
        import time
        self.current_file_id = f"{file_path}_{time.time()}"
        
        # 检查是否为动态 GIF
        if not GifUtils.is_animated_gif(file_path):
            self._show_snackbar("所选文件不是动态 GIF", ft.Colors.ORANGE)
            return
        
        # 获取帧数和元数据
        self.frame_count = GifUtils.get_frame_count(file_path)
        self.original_durations = GifUtils.get_frame_durations(file_path)
        
        # 加载循环信息
        from PIL import Image
        try:
            with Image.open(file_path) as img:
                self.original_loop = int(img.info.get('loop', 0) or 0)
        except:
            self.original_loop = 0
        
        # 更新文件信息
        file_size = format_file_size(file_path.stat().st_size)
        self.file_info_text.value = f"{file_path.name} ({self.frame_count} 帧, {file_size})"
        self.file_info_text.update()
        
        # 显示预览
        self.gif_preview.src = str(file_path.absolute())
        self.gif_preview.visible = True
        self.preview_placeholder.visible = False
        self.gif_preview.update()
        self.preview_placeholder.update()
        
        # 启用控件
        self._enable_controls()
        
        # 初始化控件值
        self.cover_frame_slider.max = self.frame_count - 1
        self.cover_frame_slider.divisions = self.frame_count - 1
        self.cover_frame_slider.value = 0
        self.cover_frame_slider.update()
        
        self.trim_start_field.value = "1"
        self.trim_end_field.value = str(self.frame_count)
        self.trim_start_field.update()
        self.trim_end_field.update()
        
        self.loop_checkbox.value = (self.original_loop == 0)
        self.loop_count_field.value = str(self.original_loop)
        self.loop_count_field.disabled = self.loop_checkbox.value
        self.loop_checkbox.update()
        self.loop_count_field.update()
        
        # 启用处理按钮
        button = self.process_button.content
        button.disabled = False
        self.process_button.update()
        
        # 重置实况图标记
        self.is_live_photo = False
        self.live_photo_info = None
        self.temp_video_path = None
        
        # 显示格式选择（GIF 可导出为 GIF 或视频）
        self._update_format_options(is_live_photo=False)
        
        # 保存当前文件ID用于延迟预览
        saved_file_id = self.current_file_id
        
        # 延迟显示第一帧的预览（确保UI已更新）
        def delayed_preview():
            import time
            time.sleep(0.3)  # 等待300ms，确保清除和UI更新都完成
            # 确认还是当前文件（双重检查）
            if self.current_file_id == saved_file_id:
                self._update_cover_preview(0, saved_file_id)
        
        thread = threading.Thread(target=delayed_preview, daemon=True)
        thread.start()
    
    def _load_live_photo_file(self, file_path: Path) -> None:
        """加载实况图文件。
        
        Args:
            file_path: 实况图文件路径
        """
        
        # 清除旧的预览任务
        self._clear_preview_tasks()
        
        # 生成新的文件ID
        import time
        self.current_file_id = f"{file_path}_{time.time()}"
        
        # 显示加载提示
        self._show_snackbar("正在检测实况图...", ft.Colors.BLUE)
        
        # 在后台线程中处理，避免阻塞UI
        def process():
            try:
                # 读取文件数据
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                
                # 检测实况图
                live_info = self.image_service._detect_live_photo(file_path, file_data)
                
                if not live_info:
                    self._show_snackbar("所选文件不是实况图", ft.Colors.ORANGE)
                    return
                
                # 检查是否有可提取的视频
                has_video = (live_info.get('has_embedded_video') or 
                           live_info.get('has_companion_video'))
                
                if not has_video:
                    self._show_snackbar("此实况图不包含视频数据", ft.Colors.ORANGE)
                    return
                
                # 提取视频到临时文件
                import tempfile
                temp_dir = Path(tempfile.mkdtemp())
                temp_video = temp_dir / "live_photo_video.mp4"
                
                success, message = self.image_service.extract_live_photo_video(
                    file_path, temp_video
                )
                
                if not success:
                    self._show_snackbar(f"提取视频失败: {message}", ft.Colors.RED)
                    return
                
                # 保存临时视频路径，用于封面预览
                self.temp_video_path = temp_video
                
                # 获取视频信息（使用 ffmpeg-python）
                import ffmpeg
                
                try:
                    # 设置 ffmpeg 环境
                    self._setup_ffmpeg_env()
                    
                    # 使用 ffmpeg.probe 获取视频信息
                    probe = ffmpeg.probe(str(temp_video))
                    
                    # 获取视频流信息
                    video_stream = None
                    for stream in probe.get('streams', []):
                        if stream.get('codec_type') == 'video':
                            video_stream = stream
                            break
                    
                    
                    if video_stream:
                        # 计算帧数和 FPS
                        r_frame_rate = video_stream.get('r_frame_rate', '30/1')
                        duration = float(video_stream.get('duration', 0))
                        nb_frames = int(video_stream.get('nb_frames', 0))
                        
                        # 正确解析帧率（格式如 "30000/1001" 或 "30/1"）
                        try:
                            if '/' in r_frame_rate:
                                num, den = r_frame_rate.split('/')
                                fps = float(num) / float(den)
                            else:
                                fps = float(r_frame_rate)
                        except:
                            fps = 30.0
                        
                        
                        if nb_frames == 0 and duration > 0:
                            nb_frames = int(duration * fps)
                        
                        self.frame_count = max(1, nb_frames)
                        self.video_duration = duration  # 保存视频时长
                        
                        # 估算每帧持续时间（毫秒）
                        frame_duration = int(1000 / fps) if fps > 0 else 100
                        frame_duration = max(10, frame_duration)  # 至少 10ms
                        self.original_durations = [frame_duration] * self.frame_count
                        
                    else:
                        # 默认值
                        self.frame_count = 30
                        self.original_durations = [100] * self.frame_count
                        
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    # 使用默认值
                    self.frame_count = 30
                    self.original_durations = [100] * self.frame_count
                
                # 保存实况图信息
                self.selected_file = file_path
                self.is_live_photo = True
                self.live_photo_info = live_info
                self.original_loop = 0  # 实况图默认不循环
                
                
                # 更新UI（在主线程）
                async def update_ui():
                    # 更新文件信息
                    file_size = format_file_size(file_path.stat().st_size)
                    live_type = live_info.get('type', '实况图')
                    self.file_info_text.value = f"{file_path.name} ({live_type}, {self.frame_count} 帧, {file_size})"
                    self.file_info_text.update()
                    
                    # 显示预览（显示原图）
                    self.gif_preview.src = str(file_path.absolute())
                    self.gif_preview.visible = True
                    self.preview_placeholder.visible = False
                    self.gif_preview.update()
                    self.preview_placeholder.update()
                    
                    # 启用控件
                    self._enable_controls()
                    
                    # 初始化控件值
                    self.cover_frame_slider.max = self.frame_count - 1
                    self.cover_frame_slider.divisions = self.frame_count - 1
                    self.cover_frame_slider.value = 0
                    self.cover_frame_slider.update()
                    
                    self.trim_start_field.value = "1"
                    self.trim_end_field.value = str(self.frame_count)
                    self.trim_start_field.update()
                    self.trim_end_field.update()
                    
                    self.loop_checkbox.value = True  # 默认无限循环
                    self.loop_count_field.value = "0"
                    self.loop_count_field.disabled = True
                    self.loop_checkbox.update()
                    self.loop_count_field.update()
                    
                    # 启用处理按钮
                    button = self.process_button.content
                    button.disabled = False
                    self.process_button.update()
                    
                    # 显示格式选择（实况图可导出为实况图、GIF 或视频）
                    self._update_format_options(is_live_photo=True)
                    
                    self._show_snackbar("✓ 实况图加载成功", ft.Colors.GREEN)
                
                self.page.run_task(update_ui)
                
                # 保存当前文件ID用于延迟预览
                saved_file_id = self.current_file_id
                
                # 在UI更新后，延迟显示第一帧的预览
                def delayed_preview():
                    import time
                    time.sleep(0.3)  # 等待300ms，确保UI更新完成
                    # 检查当前文件ID用于检查
                    current_id = self.current_file_id
                    if current_id == saved_file_id:  # 确保还是当前文件
                        self._update_cover_preview(0, saved_file_id)
                
                preview_thread = threading.Thread(target=delayed_preview, daemon=True)
                preview_thread.start()
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._show_snackbar(f"加载失败: {str(e)}", ft.Colors.RED)
        
        # 在后台线程运行
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    def _enable_controls(self) -> None:
        """启用所有控件。"""
        self.cover_frame_slider.disabled = False
        self.speed_slider.disabled = False
        self.loop_checkbox.disabled = False
        self.loop_count_field.disabled = not self.loop_checkbox.value
        self.trim_start_field.disabled = False
        self.trim_end_field.disabled = False
        self.drop_frame_slider.disabled = False
        self.reverse_checkbox.disabled = False
        
        self.cover_frame_slider.update()
        self.speed_slider.update()
        self.loop_checkbox.update()
        self.loop_count_field.update()
        self.trim_start_field.update()
        self.trim_end_field.update()
        self.drop_frame_slider.update()
        self.reverse_checkbox.update()
    
    def _setup_ffmpeg_env(self) -> None:
        """设置 ffmpeg 环境变量，使 ffmpeg-python 可以找到我们的 ffmpeg。"""
        import os
        
        ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
        if ffmpeg_path and ffmpeg_path != "ffmpeg":
            # 如果是完整路径，将其目录添加到PATH
            ffmpeg_dir = str(Path(ffmpeg_path).parent)
            if 'PATH' in os.environ:
                # 只在PATH中还没有这个目录时添加
                if ffmpeg_dir not in os.environ['PATH']:
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ['PATH']
            else:
                os.environ['PATH'] = ffmpeg_dir
    
    def _update_format_options(self, is_live_photo: bool) -> None:
        """更新输出格式选项。
        
        Args:
            is_live_photo: 是否为实况图
        """
        # 获取格式选择的 Radio 按钮
        radio_controls = self.output_format_radio.content.controls
        gif_radio = radio_controls[0]  # GIF
        video_radio = radio_controls[1]  # 视频
        live_photo_radio = radio_controls[2]  # 实况图
        
        if is_live_photo:
            # 实况图：显示所有三个选项
            gif_radio.visible = True
            video_radio.visible = True
            live_photo_radio.visible = True
            self.output_format_radio.value = "live_photo"  # 默认保持实况图格式
        else:
            # GIF：只显示 GIF 和视频选项
            gif_radio.visible = True
            video_radio.visible = True
            live_photo_radio.visible = False
            self.output_format_radio.value = "gif"  # 默认 GIF 格式
        
        # 显示格式选择容器
        self.output_format_container.visible = True
        self.format_divider.visible = True
        
        # 更新UI
        self.output_format_radio.update()
        self.output_format_container.update()
        self.format_divider.update()
    
    def _on_cover_frame_change(self, e: ft.ControlEvent) -> None:
        """首帧滑块变化事件。
        
        Args:
            e: 控件事件对象
        """
        frame_index = int(self.cover_frame_slider.value)
        self.cover_frame_text.value = f"首帧: 第 {frame_index + 1} 帧"
        self.cover_frame_text.update()
        
        # 使用防抖机制更新封面预览（等待用户停止拖动）
        self._debounced_update_cover_preview(frame_index)
    
    def _on_speed_change(self, e: ft.ControlEvent) -> None:
        """速度滑块变化事件。
        
        Args:
            e: 控件事件对象
        """
        speed = self.speed_slider.value
        speed_desc = "原速" if abs(speed - 1.0) < 0.01 else ("加速" if speed > 1.0 else "减速")
        self.speed_text.value = f"播放速度: {speed:.2f}x ({speed_desc})"
        self.speed_text.update()
    
    def _on_loop_checkbox_change(self, e: ft.ControlEvent) -> None:
        """循环复选框变化事件。
        
        Args:
            e: 控件事件对象
        """
        is_infinite = self.loop_checkbox.value
        self.loop_count_field.disabled = is_infinite
        if is_infinite:
            self.loop_count_field.value = "0"
        self.loop_count_field.update()
    
    def _on_loop_count_change(self, e: ft.ControlEvent) -> None:
        """循环次数输入框变化事件。
        
        Args:
            e: 控件事件对象
        """
        try:
            count = int(self.loop_count_field.value)
            if count < 0:
                self.loop_count_field.value = "0"
                self.loop_count_field.update()
        except ValueError:
            self.loop_count_field.value = "0"
            self.loop_count_field.update()
    
    def _on_drop_frame_change(self, e: ft.ControlEvent) -> None:
        """跳帧滑块变化事件。
        
        Args:
            e: 控件事件对象
        """
        step = int(self.drop_frame_slider.value)
        if step == 1:
            self.drop_frame_text.value = "保留所有帧 (每 1 帧保留)"
        else:
            estimated_frames = self.frame_count // step
            self.drop_frame_text.value = f"每 {step} 帧保留 1 帧 (约 {estimated_frames} 帧)"
        self.drop_frame_text.update()
    
    def _on_output_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式改变事件。
        
        Args:
            e: 控件事件对象
        """
        # 可以在这里添加格式改变时的额外逻辑
        pass
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。
        
        Args:
            e: 控件事件对象
        """
        is_custom = self.output_mode_radio.value == "custom"
        self.custom_output_field.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self.custom_output_field.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出路径按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_field.value = result.path
                self.custom_output_field.update()
        
        # 根据选择的格式确定文件扩展名和对话框标题
        output_format = self.output_format_radio.value
        
        if output_format == "video":
            dialog_title = "保存视频文件"
            file_ext = ".mp4"
            allowed_exts = ["mp4"]
        elif output_format == "live_photo":
            dialog_title = "保存实况图"
            file_ext = self.selected_file.suffix if self.selected_file else ".jpg"
            allowed_exts = ["jpg", "jpeg", "heic", "heif"]
        else:  # gif
            dialog_title = "保存 GIF 文件"
            file_ext = ".gif"
            allowed_exts = ["gif"]
        
        default_name = f"{self.selected_file.stem}_adjusted{file_ext}" if self.selected_file else f"output{file_ext}"
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.save_file(
            dialog_title=dialog_title,
            file_name=default_name,
            allowed_extensions=allowed_exts,
        )
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if not self.selected_file:
            self._show_snackbar("请先选择文件", ft.Colors.ORANGE)
            return
        
        # 验证输入
        try:
            trim_start = int(self.trim_start_field.value) - 1  # 转换为0索引
            trim_end = int(self.trim_end_field.value) - 1
            
            if trim_start < 0 or trim_end >= self.frame_count or trim_start > trim_end:
                self._show_snackbar(f"帧范围无效，请输入 1-{self.frame_count} 之间的值", ft.Colors.RED)
                return
        except ValueError:
            self._show_snackbar("帧范围必须为数字", ft.Colors.RED)
            return
        
        # 构建调整选项
        options = GifAdjustmentOptions(
            cover_frame_index=int(self.cover_frame_slider.value),
            speed_factor=self.speed_slider.value,
            loop=0 if self.loop_checkbox.value else int(self.loop_count_field.value),
            trim_start=trim_start,
            trim_end=trim_end,
            drop_every_n=int(self.drop_frame_slider.value),
            reverse_order=self.reverse_checkbox.value,
        )
        
        # 获取输出格式
        output_format = self.output_format_radio.value
        
        # 确定文件扩展名
        if output_format == "video":
            file_ext = ".mp4"
        elif output_format == "live_photo":
            file_ext = self.selected_file.suffix if self.selected_file else ".jpg"
        else:  # gif
            file_ext = ".gif"
        
        # 确定输出路径
        if self.output_mode_radio.value == "custom":
            if not self.custom_output_field.value:
                self._show_snackbar("请指定输出路径", ft.Colors.ORANGE)
                return
            output_path = Path(self.custom_output_field.value)
        else:
            output_path = self.selected_file.parent / f"{self.selected_file.stem}_adjusted{file_ext}"
        
        # 禁用按钮并显示进度
        button = self.process_button.content
        button.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_bar.value = None  # 不确定进度
        
        if self.is_live_photo:
            self.progress_text.value = "正在处理实况图..."
        else:
            self.progress_text.value = "正在处理 GIF..."
        
        try:
            self.page.update()
        except:
            pass
        
        # 在后台线程处理
        def process_task():
            if self.is_live_photo:
                # 处理实况图
                if output_format == "live_photo":
                    # 实况图 -> 实况图
                    success, message = self._process_live_photo_to_live_photo(output_path, options)
                elif output_format == "video":
                    # 实况图 -> 视频
                    success, message = self._process_live_photo_to_video(output_path, options)
                else:  # gif
                    # 实况图 -> GIF
                    success, message = self._process_live_photo_to_gif(output_path, options)
            else:
                # 处理 GIF
                if output_format == "video":
                    # GIF -> 视频
                    success, message = self._process_gif_to_video(output_path, options)
                else:  # gif
                    # GIF -> GIF
                    success, message = self.image_service.adjust_gif(
                        self.selected_file,
                        output_path,
                        options
                    )
            self._on_process_complete(success, message, output_path)
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _process_live_photo_to_gif(self, output_path: Path, options: GifAdjustmentOptions) -> tuple[bool, str]:
        """处理实况图并导出为 GIF。
        
        Args:
            output_path: 输出路径
            options: 调整选项
        
        Returns:
            (是否成功, 消息)
        """
        # 再次确认 FFmpeg 可用（以防万一）
        is_available, message = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            return False, "FFmpeg 不可用，请先安装 FFmpeg"
        
        try:
            import tempfile
            import shutil
            from PIL import Image
            
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # 1. 提取视频
                temp_video = temp_dir / "live_photo_video.mp4"
                success, message = self.image_service.extract_live_photo_video(
                    self.selected_file, temp_video
                )
                
                if not success:
                    return False, f"提取视频失败: {message}"
                
                # 2. 使用 ffmpeg-python 提取视频帧
                import ffmpeg
                
                frames_dir = temp_dir / "frames"
                frames_dir.mkdir()
                
                frame_pattern = str(frames_dir / "frame_%04d.png")
                
                # 计算速度调整
                speed_factor = options.speed_factor
                setpts_value = 1.0 / speed_factor if speed_factor > 0 else 1.0
                
                try:
                    # 设置 ffmpeg 环境
                    self._setup_ffmpeg_env()
                    
                    # 使用 ffmpeg-python 提取帧
                    stream = ffmpeg.input(str(temp_video))
                    
                    # 应用速度调整
                    stream = ffmpeg.filter(stream, 'setpts', f'{setpts_value}*PTS')
                    
                    # 应用反转
                    if options.reverse_order:
                        stream = ffmpeg.filter(stream, 'reverse')
                    
                    stream = ffmpeg.output(stream, frame_pattern)
                    ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                except ffmpeg.Error as e:
                    return False, f"提取帧失败: {e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)}"
                
                # 3. 读取所有帧
                frame_files = sorted(frames_dir.glob("frame_*.png"))
                
                if not frame_files:
                    return False, "未找到视频帧"
                
                frames = []
                for frame_file in frame_files:
                    img = Image.open(frame_file).convert('RGB')
                    frames.append(img)
                
                # 4. 应用截取范围
                if options.trim_start is not None and options.trim_end is not None:
                    start_idx = max(0, options.trim_start)
                    end_idx = min(len(frames) - 1, options.trim_end)
                    frames = frames[start_idx:end_idx + 1]
                
                if not frames:
                    return False, "截取范围无效，没有可用的帧"
                
                # 5. 应用跳帧
                if options.drop_every_n > 1:
                    new_frames = []
                    for i, frame in enumerate(frames):
                        if i % options.drop_every_n == 0:
                            new_frames.append(frame)
                    frames = new_frames
                
                if not frames:
                    return False, "跳帧设置导致没有可用的帧"
                
                # 6. 应用封面帧设置
                if options.cover_frame_index is not None and frames:
                    cover_idx = max(0, min(len(frames) - 1, options.cover_frame_index))
                    if cover_idx != 0:
                        frames = frames[cover_idx:] + frames[:cover_idx]
                
                # 7. 计算帧延迟（毫秒）
                # 原始帧率已经被速度因子调整过了，所以这里使用固定值
                base_duration = 100  # 默认 100ms
                frame_durations = [base_duration] * len(frames)
                
                # 8. 保存为 GIF
                loop_value = options.loop if options.loop is not None else 0
                
                if frames:
                    frames[0].save(
                        output_path,
                        save_all=True,
                        append_images=frames[1:],
                        duration=frame_durations,
                        loop=loop_value,
                        optimize=True,
                    )
                    
                    from utils import format_file_size
                    gif_size = format_file_size(output_path.stat().st_size)
                    return True, f"成功处理实况图，共 {len(frames)} 帧 ({gif_size})"
                else:
                    return False, "没有可用的帧"
            
            finally:
                # 清理临时目录
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        except Exception as e:
            return False, f"处理失败: {e}"
    
    def _process_live_photo_to_video(self, output_path: Path, options: GifAdjustmentOptions) -> tuple[bool, str]:
        """处理实况图并导出为视频。
        
        Args:
            output_path: 输出路径
            options: 调整选项
        
        Returns:
            (是否成功, 消息)
        """
        # 再次确认 FFmpeg 可用
        is_available, message = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            return False, "FFmpeg 不可用，请先安装 FFmpeg"
        
        try:
            import tempfile
            import shutil
            
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # 1. 提取视频
                temp_video = temp_dir / "live_photo_video.mp4"
                success, message = self.image_service.extract_live_photo_video(
                    self.selected_file, temp_video
                )
                
                if not success:
                    return False, f"提取视频失败: {message}"
                
                # 2. 使用 ffmpeg-python 处理视频
                import ffmpeg
                
                # 计算参数
                speed_factor = options.speed_factor
                setpts_value = 1.0 / speed_factor if speed_factor > 0 else 1.0
                
                try:
                    # 设置 ffmpeg 环境
                    self._setup_ffmpeg_env()
                    
                    # 使用 ffmpeg-python 处理视频
                    stream = ffmpeg.input(str(temp_video))
                    
                    # 截取（使用 trim）
                    if options.trim_start is not None and options.trim_end is not None:
                        fps = 30.0  # 默认帧率
                        start_time = options.trim_start / fps
                        end_time = (options.trim_end + 1) / fps
                        stream = ffmpeg.filter(stream, 'trim', start=start_time, end=end_time)
                        stream = ffmpeg.filter(stream, 'setpts', 'PTS-STARTPTS')
                    
                    # 速度调整
                    stream = ffmpeg.filter(stream, 'setpts', f'{setpts_value}*PTS')
                    
                    # 反转
                    if options.reverse_order:
                        stream = ffmpeg.filter(stream, 'reverse')
                    
                    # 跳帧（使用 select）
                    if options.drop_every_n > 1:
                        stream = ffmpeg.filter(stream, 'select', f'not(mod(n,{options.drop_every_n}))')
                        stream = ffmpeg.filter(stream, 'setpts', 'N/FRAME_RATE/TB')
                    
                    # 尝试使用GPU加速编码器
                    vcodec = 'libx264'
                    preset = 'medium'
                    gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
                    if gpu_encoder:
                        vcodec = gpu_encoder
                        # GPU编码器可能需要不同的预设
                        if gpu_encoder.startswith("h264_nvenc") or gpu_encoder.startswith("hevc_nvenc"):
                            preset = "p4"  # NVIDIA的平衡预设
                        elif gpu_encoder.startswith("h264_amf") or gpu_encoder.startswith("hevc_amf"):
                            preset = "balanced"  # AMD的平衡预设
                    
                    stream = ffmpeg.output(stream, str(output_path), vcodec=vcodec, preset=preset, crf=23)
                    ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                except ffmpeg.Error as e:
                    return False, f"处理视频失败: {e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)}"
                
                from utils import format_file_size
                video_size = format_file_size(output_path.stat().st_size)
                return True, f"成功处理实况图并导出为视频 ({video_size})"
            
            finally:
                # 清理临时目录
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"处理失败: {e}"
    
    def _process_live_photo_to_live_photo(self, output_path: Path, options: GifAdjustmentOptions) -> tuple[bool, str]:
        """处理实况图并保持实况图格式。
        
        Args:
            output_path: 输出路径
            options: 调整选项
        
        Returns:
            (是否成功, 消息)
        """
        # 再次确认 FFmpeg 可用
        is_available, message = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            return False, "FFmpeg 不可用，请先安装 FFmpeg"
        
        try:
            import tempfile
            import shutil
            from PIL import Image
            
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # 1. 处理视频部分（生成调整后的视频）
                temp_adjusted_video = temp_dir / "adjusted_video.mp4"
                success, message = self._process_live_photo_to_video(temp_adjusted_video, options)
                
                if not success:
                    return False, f"处理视频失败: {message}"
                
                # 2. 处理封面图片
                temp_cover = temp_dir / "cover.jpg"
                
                # 如果需要调整封面帧，从调整后的视频中提取指定帧
                if options.cover_frame_index and options.cover_frame_index > 0:
                    import ffmpeg
                    
                    try:
                        # 设置 ffmpeg 环境
                        self._setup_ffmpeg_env()
                        
                        # 计算时间点
                        fps = 30.0
                        timestamp = options.cover_frame_index / fps
                        
                        # 使用 ffmpeg-python 提取封面帧
                        stream = ffmpeg.input(str(temp_adjusted_video), ss=timestamp)
                        stream = ffmpeg.output(stream, str(temp_cover), vframes=1, **{'q:v': 2})
                        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                        
                        if not temp_cover.exists():
                            raise Exception("提取封面帧失败")
                    except:
                        # 使用原图作为封面
                        with Image.open(self.selected_file) as img:
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            img.save(temp_cover, 'JPEG', quality=95)
                else:
                    # 使用原图作为封面
                    with Image.open(self.selected_file) as img:
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        img.save(temp_cover, 'JPEG', quality=95)
                
                # 3. 读取调整后的视频数据
                with open(temp_adjusted_video, 'rb') as f:
                    video_data = f.read()
                
                # 4. 确定实况图类型（保持原格式）
                photo_type = self.live_photo_info.get('type', 'Android Motion Photo')
                if 'Samsung' in photo_type:
                    photo_type = 'Samsung Motion Photo'
                else:
                    photo_type = 'Google Motion Photo'
                
                # 5. 创建实况图
                success, message = self.image_service.create_motion_photo(
                    temp_cover,
                    video_data,
                    output_path,
                    photo_type
                )
                
                if not success:
                    return False, f"创建实况图失败: {message}"
                
                return True, message
            
            finally:
                # 清理临时目录
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"处理失败: {e}"
    
    def _process_gif_to_video(self, output_path: Path, options: GifAdjustmentOptions) -> tuple[bool, str]:
        """处理 GIF 并导出为视频。
        
        Args:
            output_path: 输出路径
            options: 调整选项
        
        Returns:
            (是否成功, 消息)
        """
        # 检查 FFmpeg 是否可用
        is_available, message = self.ffmpeg_service.is_ffmpeg_available()
        if not is_available:
            return False, "FFmpeg 不可用，请先安装 FFmpeg。GIF 转视频需要 FFmpeg 支持。"
        
        try:
            import tempfile
            import shutil
            from PIL import Image
            
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # 1. 先生成调整后的 GIF
                temp_gif = temp_dir / "adjusted.gif"
                success, message = self.image_service.adjust_gif(
                    self.selected_file,
                    temp_gif,
                    options
                )
                
                if not success:
                    return False, f"调整 GIF 失败: {message}"
                
                # 2. 使用 ffmpeg-python 将 GIF 转换为 MP4
                import ffmpeg
                
                try:
                    # 设置 ffmpeg 环境
                    self._setup_ffmpeg_env()
                    
                    # 使用 ffmpeg-python 转换 GIF 为 MP4
                    stream = ffmpeg.input(str(temp_gif))
                    stream = ffmpeg.filter(stream, 'scale', 'trunc(iw/2)*2:trunc(ih/2)*2')  # 确保宽高为偶数
                    # 尝试使用GPU加速编码器
                    vcodec = 'libx264'
                    preset = 'medium'
                    gpu_encoder = self.ffmpeg_service.get_preferred_gpu_encoder()
                    if gpu_encoder:
                        vcodec = gpu_encoder
                        # GPU编码器可能需要不同的预设
                        if gpu_encoder.startswith("h264_nvenc") or gpu_encoder.startswith("hevc_nvenc"):
                            preset = "p4"  # NVIDIA的平衡预设
                        elif gpu_encoder.startswith("h264_amf") or gpu_encoder.startswith("hevc_amf"):
                            preset = "balanced"  # AMD的平衡预设
                    
                    stream = ffmpeg.output(
                        stream, 
                        str(output_path), 
                        movflags='faststart',
                        pix_fmt='yuv420p',
                        vcodec=vcodec,
                        preset=preset,
                        crf=23
                    )
                    ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                except ffmpeg.Error as e:
                    return False, f"GIF 转视频失败: {e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)}"
                
                from utils import format_file_size
                video_size = format_file_size(output_path.stat().st_size)
                return True, f"成功将 GIF 转换为视频 ({video_size})"
            
            finally:
                # 清理临时目录
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"处理失败: {e}"
    
    def _on_process_complete(self, success: bool, message: str, output_path: Path) -> None:
        """处理完成回调。
        
        Args:
            success: 是否成功
            message: 消息
            output_path: 输出路径
        """
        # 隐藏进度
        self.progress_bar.visible = False
        self.progress_text.visible = False
        
        # 启用按钮
        button = self.process_button.content
        button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
        
        if success:
            self._show_snackbar(f"处理成功! 保存到: {output_path}", ft.Colors.GREEN)
        else:
            self._show_snackbar(f"处理失败: {message}", ft.Colors.RED)
    
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
    
    def _show_ffmpeg_install_view(self) -> None:
        """显示 FFmpeg 安装视图。"""
        if not self.parent_container:
            # 如果没有父容器，显示错误提示
            self._show_snackbar(
                "请前往【音频处理】或【视频处理】页面安装 FFmpeg",
                ft.Colors.ORANGE
            )
            return
        
        # 创建 FFmpeg 安装视图
        self.ffmpeg_install_view = FFmpegInstallView(
            self.page,
            self.ffmpeg_service,
            on_installed=self._on_ffmpeg_installed,
            on_back=self._on_ffmpeg_install_back,
            tool_name="实况图调整"
        )
        
        # 切换到安装视图
        self.parent_container.content = self.ffmpeg_install_view
        try:
            self.page.update()
        except:
            pass
    
    def _on_ffmpeg_installed(self) -> None:
        """FFmpeg 安装完成回调。"""
        
        # 返回到 GIF 调整视图
        if self.parent_container:
            self.parent_container.content = self
            try:
                self.page.update()
            except:
                pass
        
        # 如果有待处理的文件，自动加载
        if self.pending_file:
            file_to_load = self.pending_file
            self.pending_file = None  # 清除待处理文件
            
            
            # 使用 Timer 延迟加载，让界面先更新
            def delayed_load():
                try:
                    self._load_live_photo_file(file_to_load)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self._show_snackbar(f"自动加载失败: {str(e)}", ft.Colors.RED)
            
            import threading
            timer = threading.Timer(0.5, delayed_load)
            timer.daemon = True
            timer.start()
    
    def _on_ffmpeg_installed_rebuild(self) -> None:
        """FFmpeg 安装完成后重建界面。"""
        
        # 重置 padding
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 重新构建界面
        self._build_ui()
        
        # 更新显示
        if self.parent_container:
            self.parent_container.content = self
            try:
                self.page.update()
                self._show_snackbar("FFmpeg 安装成功！可以使用实况图功能了", ft.Colors.GREEN)
            except Exception as ex:
                import traceback
                traceback.print_exc()
    
    def _on_ffmpeg_install_back(self, e: ft.ControlEvent = None) -> None:
        """从 FFmpeg 安装视图返回。
        
        Args:
            e: 控件事件对象（可选）
        """
        
        # 清除待处理文件
        self.pending_file = None
        
        # 直接返回到上一级（图片工具主界面）
        if self.on_back:
            self.on_back()
    
    def _clear_preview_tasks(self) -> None:
        """清除所有预览相关的任务。"""
        with self.cover_preview_lock:
            # 取消定时器
            if self.cover_preview_timer is not None:
                self.cover_preview_timer.cancel()
                self.cover_preview_timer = None
            
            # 重置预览状态
            self.current_preview_frame = -1
        
        # 异步隐藏预览图
        if hasattr(self, 'cover_preview_image'):
            async def clear_preview_ui():
                try:
                    self.cover_preview_image.src = ""  # 清空图片源
                    self.cover_preview_image.visible = False
                    self.cover_preview_placeholder.visible = True
                    self.cover_preview_image.update()
                    self.cover_preview_placeholder.update()
                except Exception as e:
                    logger.error(f"[_clear_preview_tasks] 清除UI失败: {e}")
            
            try:
                self.page.run_task(clear_preview_ui)
            except:
                # 如果异步失败，尝试同步更新
                try:
                    self.cover_preview_image.src = ""
                    self.cover_preview_image.visible = False
                    self.cover_preview_placeholder.visible = True
                    self.cover_preview_image.update()
                    self.cover_preview_placeholder.update()
                except:
                    pass
    
    def _debounced_update_cover_preview(self, frame_index: int) -> None:
        """防抖更新封面预览图（延迟更新，避免频繁触发）。
        
        Args:
            frame_index: 帧索引
        """
        with self.cover_preview_lock:
            # 取消之前的定时器
            if self.cover_preview_timer is not None:
                self.cover_preview_timer.cancel()
            
            # 保存当前文件ID，传递给定时器
            current_file_id = self.current_file_id
            
            # 设置新的定时器，300ms 后执行
            self.cover_preview_timer = threading.Timer(
                0.3,  # 300ms 延迟
                self._update_cover_preview,
                args=(frame_index, current_file_id)
            )
            self.cover_preview_timer.daemon = True
            self.cover_preview_timer.start()
    
    def _update_cover_preview(self, frame_index: int, file_id: str = "") -> None:
        """更新封面预览图。
        
        Args:
            frame_index: 帧索引
            file_id: 文件ID，用于防止显示旧文件的帧
        """
        # 检查文件ID是否匹配（防止显示旧文件的帧）
        if file_id and file_id != self.current_file_id:
            return
        
        if not self.selected_file:
            return
        
        # 避免重复提取同一帧
        if self.current_preview_frame == frame_index:
            return
        
        self.current_preview_frame = frame_index
        
        # 在后台线程中提取帧
        def extract_frame():
            try:
                import tempfile
                from PIL import Image
                
                # 再次检查文件ID
                if file_id and file_id != self.current_file_id:
                    return
                
                # 再次检查是否已经有更新的请求
                if self.current_preview_frame != frame_index:
                    return
                
                if self.is_live_photo and self.temp_video_path:
                    # 对于实况图，从视频中提取帧
                    self._extract_frame_from_video(frame_index, file_id)
                else:
                    # 对于 GIF，从 GIF 中提取帧
                    self._extract_frame_from_gif(frame_index, file_id)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        thread = threading.Thread(target=extract_frame, daemon=True)
        thread.start()
    
    def _extract_frame_from_gif(self, frame_index: int, file_id: str = "") -> None:
        """从 GIF 中提取指定帧。
        
        Args:
            frame_index: 帧索引
            file_id: 文件ID，用于防止显示旧文件的帧
        """
        try:
            from PIL import Image
            import tempfile
            
            # 检查文件ID
            if file_id and file_id != self.current_file_id:
                return
            
            # 检查是否已经有更新的请求
            if self.current_preview_frame != frame_index:
                return
            
            # 打开 GIF
            with Image.open(self.selected_file) as img:
                # 跳转到指定帧
                img.seek(frame_index)
                
                # 再次检查
                if file_id and file_id != self.current_file_id:
                    return
                if self.current_preview_frame != frame_index:
                    return
                
                # 转换为 RGB（避免透明度问题）
                frame = img.convert('RGB')
                
                # 保存到临时文件（使用唯一文件名避免缓存冲突）
                import time
                unique_id = str(int(time.time() * 1000))  # 毫秒级时间戳
                temp_file = Path(tempfile.gettempdir()) / f"cover_preview_{unique_id}_{frame_index}.png"
                frame.save(temp_file, 'PNG')
                
                # 最后一次检查
                if file_id and file_id != self.current_file_id:
                    return
                if self.current_preview_frame != frame_index:
                    return
                
                # 更新UI
                async def update_preview():
                    # UI 更新时最后检查一次
                    if file_id and file_id != self.current_file_id:
                        return
                    self.cover_preview_image.src = str(temp_file.absolute())
                    self.cover_preview_image.visible = True
                    self.cover_preview_placeholder.visible = False
                    self.cover_preview_image.update()
                    self.cover_preview_placeholder.update()
                
                self.page.run_task(update_preview)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def _extract_frame_from_video(self, frame_index: int, file_id: str = "") -> None:
        """从视频中提取指定帧。
        
        Args:
            frame_index: 帧索引
            file_id: 文件ID，用于防止显示旧文件的帧
        """
        try:
            import tempfile
            
            # 检查文件ID
            if file_id and file_id != self.current_file_id:
                return
            
            # 检查是否已经有更新的请求
            if self.current_preview_frame != frame_index:
                return
            
            if not self.temp_video_path or not self.temp_video_path.exists():
                return
            
            # 计算时间点（秒）
            # 使用帧索引和视频时长计算
            if self.video_duration > 0 and self.frame_count > 0:
                timestamp = (frame_index / self.frame_count) * self.video_duration
            else:
                # 使用默认 FPS 估算
                fps = 30.0
                timestamp = frame_index / fps
            
            # 再次检查
            if file_id and file_id != self.current_file_id:
                return
            if self.current_preview_frame != frame_index:
                return
            
            # 输出文件（使用唯一文件名避免缓存冲突）
            import time
            import ffmpeg
            unique_id = str(int(time.time() * 1000))  # 毫秒级时间戳
            temp_file = Path(tempfile.gettempdir()) / f"cover_preview_{unique_id}_{frame_index}.png"
            
            # 使用 ffmpeg-python 提取帧
            try:
                # 设置 ffmpeg 环境
                self._setup_ffmpeg_env()
                
                stream = ffmpeg.input(str(self.temp_video_path), ss=timestamp)
                stream = ffmpeg.output(stream, str(temp_file), vframes=1)
                ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                return
            
            # 最后一次检查
            if file_id and file_id != self.current_file_id:
                return
            if self.current_preview_frame != frame_index:
                return
            
            if temp_file.exists():
                # 更新UI
                async def update_preview():
                    # UI 更新时最后检查一次
                    if file_id and file_id != self.current_file_id:
                        return
                    self.cover_preview_image.src = str(temp_file.absolute())
                    self.cover_preview_image.visible = True
                    self.cover_preview_placeholder.visible = False
                    self.cover_preview_image.update()
                    self.cover_preview_placeholder.update()
                
                self.page.run_task(update_preview)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件（只取第一个支持的文件）。"""
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                self._load_file(path)
                self._show_snackbar(f"已加载: {path.name}", ft.Colors.GREEN)
                return
        
        self._show_snackbar("GIF编辑工具不支持该格式", ft.Colors.ORANGE)
    
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
