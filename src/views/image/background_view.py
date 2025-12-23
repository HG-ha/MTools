# -*- coding: utf-8 -*-
"""图片背景移除视图模块。

提供图片背景移除功能的用户界面。
"""

import gc
import threading
import webbrowser
from pathlib import Path
from typing import Callable, List, Optional, Dict
from utils import logger

import flet as ft

from constants import (
    BACKGROUND_REMOVAL_MODELS,
    BORDER_RADIUS_MEDIUM,
    DEFAULT_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    ModelInfo,
)
from services import ConfigService, ImageService
from services.image_service import BackgroundRemover
from utils import format_file_size, GifUtils


class ImageBackgroundView(ft.Container):
    """图片背景移除视图类。
    
    提供图片背景移除功能，包括：
    - 单文件和批量处理
    - 多模型选择
    - 自动下载ONNX模型
    - 处理进度显示
    - 导出为PNG格式（保留透明通道）
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.bmp', '.webp', '.tiff', '.gif'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片背景移除视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.bg_remover: Optional[BackgroundRemover] = None
        self.is_model_loading: bool = False
        
        # GIF 文件的帧选择映射：{文件路径: 帧索引}
        self.gif_frame_selection: Dict[str, int] = {}
        
        # 当前选择的模型
        saved_model_key = self.config_service.get_config_value("background_model_key", DEFAULT_MODEL_KEY)
        if saved_model_key not in BACKGROUND_REMOVAL_MODELS:
            saved_model_key = DEFAULT_MODEL_KEY
        self.current_model_key: str = saved_model_key
        self.current_model: ModelInfo = BACKGROUND_REMOVAL_MODELS[self.current_model_key]
        
        self.expand: bool = True
        # 右侧多留一些空间给滚动条
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 获取模型路径
        self.model_path: Path = self._get_model_path()
        
        # 标记UI是否已构建
        self._ui_built: bool = False
        
        # 先创建一个简单的加载界面，真正的UI延迟构建
        self._build_loading_ui()
        
        # 延迟构建完整UI，避免阻塞初始化
        import threading
        threading.Thread(target=self._build_ui_async, daemon=True).start()
    
    def _get_model_path(self) -> Path:
        """获取当前选择的模型文件路径。
        
        Returns:
            模型文件路径
        """
        # 使用数据目录（可以是用户自定义的）
        data_dir = self.config_service.get_data_dir()
        
        # 模型存储在 models/background_removal/版本号 子目录
        models_dir = data_dir / "models" / "background_removal" / self.current_model.version
        # 不在初始化时创建目录，避免阻塞界面
        # 目录会在需要时（下载/加载模型）自动创建
        
        return models_dir / self.current_model.filename
    
    def _ensure_model_dir(self) -> None:
        """确保模型目录存在。"""
        model_dir = self.model_path.parent
        model_dir.mkdir(parents=True, exist_ok=True)
    
    def _build_loading_ui(self) -> None:
        """构建简单的加载界面（骨架屏）。"""
        # 创建一个简单的加载提示
        loading_content = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(),
                    ft.Text("正在加载背景移除功能...", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_LARGE,
            ),
            expand=True,
            alignment=ft.alignment.center,
        )
        
        self.content = loading_content
    
    def _build_ui_async(self) -> None:
        """异步构建完整UI。"""
        import time
        # 短暂延迟，确保加载界面先显示
        time.sleep(0.05)
        
        # 构建完整UI
        self._build_ui()
        self._ui_built = True
        
        # 更新界面
        try:
            self.update()
        except:
            pass
    
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
                ft.Text("背景移除", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择图片:", size=14, weight=ft.FontWeight.W_500),
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
                # 支持格式说明
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持格式: JPG, PNG, WebP, BMP, TIFF, GIF 等 | 处理结果将保存为PNG格式（保留透明背景）",
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
        
        # 模型选择下拉框
        model_options = []
        for key, model in BACKGROUND_REMOVAL_MODELS.items():
            # 格式化大小显示，统一宽度
            if model.size_mb < 100:
                size_text = f"{model.size_mb}MB  "
            elif model.size_mb < 1000:
                size_text = f"{model.size_mb}MB "
            else:
                size_text = f"{model.size_mb}MB"
            
            # 构建选项文本，使用更清晰的格式
            option_text = f"{model.display_name}  |  {size_text}"
            
            model_options.append(
                ft.dropdown.Option(
                    key=key,
                    text=option_text
                )
            )
        
        self.model_selector: ft.Dropdown = ft.Dropdown(
            options=model_options,
            value=self.current_model_key,
            label="选择模型",
            hint_text="选择背景移除模型",
            on_change=self._on_model_select_change,
            width=320,
            dense=True,
            text_size=13,
        )
        
        # 模型信息显示
        self.model_info_text: ft.Text = ft.Text(
            f"质量: {self.current_model.quality} | 性能: {self.current_model.performance}",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 模型状态显示
        self.model_status_icon: ft.Icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_status_text: ft.Text = ft.Text(
            "正在初始化...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 下载按钮（初始隐藏）
        self.download_model_button: ft.ElevatedButton = ft.ElevatedButton(
            text="下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._start_download_model,
            visible=False,
        )
        
        # 加载模型按钮（初始隐藏）
        self.load_model_button: ft.ElevatedButton = ft.ElevatedButton(
            text="加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model,
            visible=False,
        )
        
        # 卸载模型按钮（初始隐藏）
        self.unload_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            on_click=self._on_unload_model,
            visible=False,
        )
        
        # 删除模型按钮（初始隐藏）
        self.delete_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model,
            visible=False,
        )
        
        model_status_row: ft.Row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.download_model_button,
                self.load_model_button,
                self.unload_model_button,
                self.delete_model_button,
            ],
            spacing=PADDING_MEDIUM // 2,
        )
        
        # 自动加载模型设置
        auto_load_model = self.config_service.get_config_value("background_auto_load_model", True)
        self.auto_load_checkbox: ft.Checkbox = ft.Checkbox(
            label="自动加载模型",
            value=auto_load_model,
            on_change=self._on_auto_load_change,
        )
        
        # 处理选项（右侧区域）
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀 _no_bg）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "background_removed"),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        # GIF 选项（初始隐藏）
        self.gif_files_list: ft.Column = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.AUTO,
        )
        
        self.gif_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER, size=20, color=ft.Colors.ORANGE),
                            ft.Text("GIF 文件检测", size=14, weight=ft.FontWeight.W_500),
                        ],
                        spacing=8,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "⚠️ 背景移除对 GIF 处理较慢且消耗大量资源，仅支持单帧处理",
                            size=12,
                            color=ft.Colors.ORANGE,
                        ),
                        margin=ft.margin.only(left=4, bottom=PADDING_SMALL),
                    ),
                    self.gif_files_list,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.ORANGE),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ORANGE),
            visible=False,
        )
        
        process_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("处理选项:", size=14, weight=ft.FontWeight.W_500),
                    self.model_selector,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    model_status_row,
                    self.auto_load_checkbox,
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 左右分栏布局
        main_content: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=file_select_area,
                    expand=3,
                    height=380,
                ),
                ft.Container(
                    content=process_options,
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
                spacing=PADDING_MEDIUM // 2,
            ),
        )
        
        # 底部大按钮 - 与图片压缩页面样式一致
        self.process_button: ft.Container = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=24),
                        ft.Text("开始移除背景", size=18, weight=ft.FontWeight.W_600),
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
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                main_content,
                ft.Container(height=PADDING_MEDIUM),
                self.gif_options,
                ft.Container(height=PADDING_LARGE),
                progress_container,
                ft.Container(height=PADDING_MEDIUM),
                self.process_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=0,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 组装主界面 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
        
        # 初始化文件列表空状态
        self._update_file_list()
        
        # 延迟检查模型状态，避免阻塞界面初始化
        threading.Thread(target=self._check_model_status_async, daemon=True).start()
    
    def _check_model_status_async(self) -> None:
        """异步检查模型状态，避免阻塞界面初始化。"""
        # 在后台线程中执行文件系统操作
        import time
        time.sleep(0.05)  # 短暂延迟，确保界面已经显示
        
        self._check_model_status()
    
    def _check_model_status(self) -> None:
        """检查模型状态。"""
        auto_load = self.config_service.get_config_value("background_auto_load_model", True)
        
        if self.model_path.exists():
            # 模型存在
            if auto_load:
                # 自动加载模型
                self._update_model_status("loading", "正在加载模型...")
                threading.Thread(target=self._load_model_async, daemon=True).start()
            else:
                # 不自动加载，显示模型已存在但未加载
                self._update_model_status("unloaded", "模型已下载，未加载")
        else:
            # 模型不存在，显示下载按钮
            self._update_model_status("need_download", "需要下载模型才能使用")
    
    def _load_model_async(self) -> None:
        """异步加载模型。"""
        try:
            self.bg_remover = BackgroundRemover(
                self.model_path, 
                config_service=self.config_service
            )
            self._on_model_loaded(True, None)
        except Exception as e:
            self._on_model_loaded(False, str(e))
    
    def _start_download_model(self, e: ft.ControlEvent = None) -> None:
        """开始下载模型文件。
        
        Args:
            e: 控件事件对象
        """
        if self.is_model_loading:
            return
        
        self.is_model_loading = True
        self._update_model_status("downloading", f"正在下载模型（约{self.current_model.size_mb}MB），请稍候...")
        
        # 显示下载进度条
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self.progress_text.value = "准备下载..."
        try:
            self.progress_bar.update()
            self.progress_text.update()
        except:
            pass
        
        def download_task():
            try:
                # 确保模型目录存在
                self._ensure_model_dir()
                
                import httpx
                
                # 使用 httpx 流式下载
                with httpx.stream("GET", self.current_model.url, follow_redirects=True) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    with open(self.model_path, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = min(downloaded * 100 / total_size, 100)
                                    progress = percent / 100
                                    
                                    # 格式化文件大小
                                    downloaded_mb = downloaded / (1024 * 1024)
                                    total_mb = total_size / (1024 * 1024)
                                    
                                    # 更新进度条和文本
                                    self.progress_bar.value = progress
                                    self.progress_text.value = f"下载中: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({percent:.1f}%)"
                                    self.model_status_text.value = f"正在下载模型... {percent:.1f}%"
                                    
                                    try:
                                        self.progress_bar.update()
                                        self.progress_text.update()
                                        self.model_status_text.update()
                                    except:
                                        pass
                
                # 下载完成，隐藏进度条
                self.progress_bar.visible = False
                self.progress_text.visible = False
                try:
                    self.progress_bar.update()
                    self.progress_text.update()
                except:
                    pass
                
                # 加载模型
                self.bg_remover = BackgroundRemover(
                    self.model_path,
                    config_service=self.config_service
                )
                self._on_model_loaded(True, None)
            except Exception as e:
                # 下载失败，隐藏进度条
                self.progress_bar.visible = False
                self.progress_text.visible = False
                try:
                    self.progress_bar.update()
                    self.progress_text.update()
                except:
                    pass
                self._on_download_failed(str(e))
        
        threading.Thread(target=download_task, daemon=True).start()
    
    def _on_model_loaded(self, success: bool, error: Optional[str]) -> None:
        """模型加载完成回调。
        
        Args:
            success: 是否成功
            error: 错误信息
        """
        self.is_model_loading = False
        
        if not success:
            logger.error(f"模型加载失败: {error}")
        else:
            logger.info("模型加载成功")
        
        if success:
            # 获取设备信息
            device_info = "未知设备"
            if self.bg_remover:
                device_info = self.bg_remover.get_device_info()
            
            self._update_model_status("ready", f"模型就绪 ({device_info})")
            self._update_process_button()
            self._show_snackbar(f"模型加载成功，使用设备: {device_info}", ft.Colors.GREEN)
        else:
            self._update_model_status("error", f"模型加载失败: {error}")
            self._show_snackbar(f"模型加载失败: {error}", ft.Colors.RED)
    
    def _on_download_failed(self, error: str) -> None:
        """模型下载失败回调。
        
        Args:
            error: 错误信息
        """
        self.is_model_loading = False
        self._update_model_status("need_download", "下载失败，请重试")
        self._show_snackbar(f"模型下载失败: {error}", ft.Colors.RED)
        
        # 显示手动下载对话框
        self._show_manual_download_dialog(error)
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态显示。
        
        Args:
            status: 状态 ("loading", "downloading", "ready", "unloaded", "error", "need_download")
            message: 状态消息
        """
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
            self.unload_model_button.visible = True  # 模型就绪时显示卸载按钮
            self.delete_model_button.visible = True  # 模型就绪时显示删除按钮
        elif status == "unloaded":
            # 模型文件存在但未加载到内存
            self.model_status_icon.name = ft.Icons.DOWNLOAD_DONE
            self.model_status_icon.color = ft.Colors.GREY
            self.download_model_button.visible = False
            self.load_model_button.visible = True   # 显示加载按钮
            self.unload_model_button.visible = False
            self.delete_model_button.visible = True  # 显示删除按钮
        elif status == "error":
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.RED
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        elif status == "need_download":
            self.model_status_icon.name = ft.Icons.WARNING
            self.model_status_icon.color = ft.Colors.ORANGE
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
        
        self.model_status_text.value = message
        
        # 只有控件已添加到页面时才更新
        try:
            self.model_status_icon.update()
            self.model_status_text.update()
            self.download_model_button.update()
            self.load_model_button.update()
            self.unload_model_button.update()
            self.delete_model_button.update()
        except:
            pass  # 控件还未添加到页面，忽略
    
    def _show_manual_download_dialog(self, error: str) -> None:
        """显示手动下载对话框。
        
        Args:
            error: 错误信息
        """
        def close_dialog(e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        def open_url_and_close(e: ft.ControlEvent) -> None:
            webbrowser.open(self.current_model.url)
            close_dialog(e)
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("自动下载失败"),
            content=ft.Column(
                controls=[
                    ft.Text(f"自动下载模型失败: {error}", color=ft.Colors.RED),
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("请手动下载模型文件：", weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Text("1. 点击「打开下载链接」按钮"),
                    ft.Text(f"2. 在浏览器中下载模型文件 ({self.current_model.filename})"),
                    ft.Text("3. 将下载的文件移动到以下位置："),
                    ft.Container(
                        content=ft.Text(
                            str(self.model_path),
                            size=11,
                            selectable=True,
                        ),
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        border_radius=BORDER_RADIUS_MEDIUM,
                    ),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Text("4. 重新打开此界面即可使用", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                ],
                tight=True,
                spacing=PADDING_MEDIUM // 2,
            ),
            actions=[
                ft.TextButton("取消", on_click=close_dialog),
                ft.ElevatedButton("打开下载链接", icon=ft.Icons.OPEN_IN_BROWSER, on_click=open_url_and_close),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.on_back:
            self.on_back()
    
    def _on_model_select_change(self, e: ft.ControlEvent) -> None:
        """模型选择变化事件。
        
        Args:
            e: 控件事件对象
        """
        new_model_key = e.control.value
        if new_model_key == self.current_model_key:
            return
        
        # 如果当前有模型加载，提示用户切换模型会卸载当前模型
        if self.bg_remover:
            def confirm_switch(confirm_e: ft.ControlEvent) -> None:
                """确认切换模型。"""
                dialog.open = False
                self.page.update()
                self._switch_model(new_model_key)
            
            def cancel_switch(cancel_e: ft.ControlEvent) -> None:
                """取消切换，恢复原选择。"""
                dialog.open = False
                self.model_selector.value = self.current_model_key
                self.model_selector.update()
                self.page.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("确认切换模型"),
                content=ft.Column(
                    controls=[
                        ft.Text("切换模型将卸载当前已加载的模型。", size=14),
                        ft.Container(height=PADDING_SMALL),
                        ft.Text("是否继续？", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    tight=True,
                    spacing=PADDING_SMALL,
                ),
                actions=[
                    ft.TextButton("取消", on_click=cancel_switch),
                    ft.ElevatedButton("切换", on_click=confirm_switch),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
        else:
            # 没有加载模型，直接切换
            self._switch_model(new_model_key)
    
    def _switch_model(self, new_model_key: str) -> None:
        """切换到新模型。
        
        Args:
            new_model_key: 新模型的键
        """
        # 卸载旧模型
        if self.bg_remover:
            self.bg_remover = None
            gc.collect()
        
        # 更新当前模型
        self.current_model_key = new_model_key
        self.current_model = BACKGROUND_REMOVAL_MODELS[new_model_key]
        
        # 保存到配置
        self.config_service.set_config_value("background_model_key", new_model_key)
        
        # 更新模型路径
        self.model_path = self._get_model_path()
        
        # 更新模型信息显示
        self.model_info_text.value = f"质量: {self.current_model.quality} | 性能: {self.current_model.performance}"
        self.model_info_text.update()
        
        # 检查新模型状态
        self._check_model_status()
        
        # 更新处理按钮状态
        self._update_process_button()
        
        self._show_snackbar(f"已切换到: {self.current_model.display_name}", ft.Colors.GREEN)
    
    def _on_auto_load_change(self, e: ft.ControlEvent) -> None:
        """自动加载模型复选框变化事件。
        
        Args:
            e: 控件事件对象
        """
        auto_load = self.auto_load_checkbox.value
        self.config_service.set_config_value("background_auto_load_model", auto_load)
        
        # 如果启用自动加载且模型文件存在但未加载，则加载模型
        if auto_load and self.model_path.exists() and not self.bg_remover:
            self._update_model_status("loading", "正在加载模型...")
            threading.Thread(target=self._load_model_async, daemon=True).start()
    
    def _on_load_model(self, e: ft.ControlEvent) -> None:
        """加载模型按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if self.model_path.exists() and not self.bg_remover:
            self._update_model_status("loading", "正在加载模型...")
            threading.Thread(target=self._load_model_async, daemon=True).start()
        elif self.bg_remover:
            self._show_snackbar("模型已加载", ft.Colors.ORANGE)
        else:
            self._show_snackbar("模型文件不存在", ft.Colors.RED)
    
    def _on_unload_model(self, e: ft.ControlEvent) -> None:
        """卸载模型按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def confirm_unload(confirm_e: ft.ControlEvent) -> None:
            """确认卸载。"""
            dialog.open = False
            self.page.update()
            
            # 卸载模型（释放内存）
            if self.bg_remover:
                self.bg_remover = None
                gc.collect()
                self._show_snackbar("模型已卸载", ft.Colors.GREEN)
                
                # 更新状态为已下载但未加载
                self._update_model_status("unloaded", "模型已下载，未加载")
                self._update_process_button()
            else:
                self._show_snackbar("模型未加载", ft.Colors.ORANGE)
        
        def cancel_unload(cancel_e: ft.ControlEvent) -> None:
            """取消卸载。"""
            dialog.open = False
            self.page.update()
        
        # 显示确认对话框
        # 计算内存占用（模型文件大小的近似值，实际内存可能略大）
        estimated_memory = int(self.current_model.size_mb * 1.2)  # 估算内存为文件大小的1.2倍
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认卸载模型"),
            content=ft.Column(
                controls=[
                    ft.Text("确定要卸载背景移除模型吗？", size=14),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Text(f"此操作将释放约{estimated_memory}MB内存，不会删除模型文件。", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("需要时可以重新加载。", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                tight=True,
                spacing=PADDING_MEDIUM // 2,
            ),
            actions=[
                ft.TextButton("取消", on_click=cancel_unload),
                ft.ElevatedButton(
                    "卸载",
                    icon=ft.Icons.POWER_SETTINGS_NEW,
                    on_click=confirm_unload,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _on_delete_model(self, e: ft.ControlEvent) -> None:
        """删除模型按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        def confirm_delete(confirm_e: ft.ControlEvent) -> None:
            """确认删除。"""
            dialog.open = False
            self.page.update()
            
            # 如果模型已加载，先卸载
            if self.bg_remover:
                self.bg_remover = None
                gc.collect()
            
            # 删除模型文件
            try:
                if self.model_path.exists():
                    self.model_path.unlink()
                    self._show_snackbar("模型文件已删除", ft.Colors.GREEN)
                    
                    # 更新状态为需要下载
                    self._update_model_status("need_download", "需要下载模型才能使用")
                    self._update_process_button()
                else:
                    self._show_snackbar("模型文件不存在", ft.Colors.ORANGE)
            except Exception as ex:
                self._show_snackbar(f"删除模型失败: {ex}", ft.Colors.RED)
        
        def cancel_delete(cancel_e: ft.ControlEvent) -> None:
            """取消删除。"""
            dialog.open = False
            self.page.update()
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除模型文件"),
                content=ft.Column(
                    controls=[
                        ft.Text("确定要删除背景移除模型文件吗？", size=14),
                        ft.Container(height=PADDING_MEDIUM // 2),
                        ft.Text("此操作将：", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"• 删除模型文件（约{self.current_model.size_mb}MB）", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("• 如果模型已加载，将先卸载", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Container(height=PADDING_MEDIUM // 2),
                        ft.Text("删除后需要重新下载才能使用。", size=12, color=ft.Colors.ERROR),
                    ],
                    tight=True,
                    spacing=PADDING_MEDIUM // 2,
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
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "tiff", "gif"],
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
                # 遍历文件夹中的所有图片文件
                image_extensions = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".webp", ".tiff", ".tif", ".gif"}
                for file_path in folder_path.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                        if file_path not in self.selected_files:
                            self.selected_files.append(file_path)
                
                self._update_file_list()
                self._update_process_button()
                
                if self.selected_files:
                    self._show_snackbar(f"已添加 {len(self.selected_files)} 个文件", ft.Colors.GREEN)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择包含图片的文件夹")
    
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
            # 空状态提示（固定高度以实现居中）
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击选择按钮或点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=280,  # 380(父容器) - 52(标题行) - 48(padding) = 280
                    alignment=ft.alignment.center,
                    on_click=self._on_select_files,
                    tooltip="点击选择图片",
                )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                file_info = self.image_service.get_image_info(file_path)
                
                if 'error' in file_info:
                    info_text = f"错误: {file_info['error']}"
                    icon_color = ft.Colors.RED
                else:
                    size_str = format_file_size(file_info['file_size'])
                    info_text = f"{file_info['width']}×{file_info['height']} · {size_str}"
                    icon_color = ft.Colors.PRIMARY
                
                file_item: ft.Container = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE, size=20, color=icon_color),
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
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    padding=PADDING_MEDIUM // 2,
                    border_radius=BORDER_RADIUS_MEDIUM,
                    bgcolor=ft.Colors.SECONDARY_CONTAINER,
                )
                
                self.file_list_view.controls.append(file_item)
        
        try:
            self.file_list_view.update()
        except:
            pass
        
        # 更新 GIF 选项
        self._update_gif_options()
    
    def _on_remove_file(self, index: int) -> None:
        """移除文件列表中的文件。
        
        Args:
            index: 文件索引
        """
        if 0 <= index < len(self.selected_files):
            removed_file = self.selected_files.pop(index)
            # 清理 GIF 帧选择记录
            if str(removed_file) in self.gif_frame_selection:
                del self.gif_frame_selection[str(removed_file)]
            self._update_file_list()
            self._update_process_button()
    
    def _update_gif_options(self) -> None:
        """更新 GIF 选项区域。"""
        # 检测动态 GIF 文件
        gif_files = [f for f in self.selected_files if GifUtils.is_animated_gif(f)]
        
        if gif_files:
            # 显示 GIF 选项
            self.gif_options.visible = True
            self.gif_files_list.controls.clear()
            
            for gif_file in gif_files:
                frame_count = GifUtils.get_frame_count(gif_file)
                # 默认选择第一帧（索引 0）
                if str(gif_file) not in self.gif_frame_selection:
                    self.gif_frame_selection[str(gif_file)] = 0
                
                # 创建帧选择控件
                frame_input = ft.TextField(
                    value=str(self.gif_frame_selection[str(gif_file)] + 1),
                    width=50,
                    text_align=ft.TextAlign.CENTER,
                    dense=True,
                    on_submit=lambda e, gf=gif_file, fc=frame_count: self._on_gif_frame_submit(e, gf, fc),
                )
                
                self.gif_files_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.GIF, size=18, color=ft.Colors.ORANGE),
                                ft.Column(
                                    controls=[
                                        ft.Text(gif_file.name, size=12, weight=ft.FontWeight.W_500),
                                        ft.Text(f"{frame_count} 帧", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SKIP_PREVIOUS,
                                    icon_size=16,
                                    on_click=lambda e, gf=gif_file, fc=frame_count: self._on_gif_prev_frame(gf, fc),
                                    tooltip="上一帧",
                                ),
                                ft.Text("帧:", size=11),
                                frame_input,
                                ft.Text(f"/{frame_count}", size=11),
                                ft.IconButton(
                                    icon=ft.Icons.SKIP_NEXT,
                                    icon_size=16,
                                    on_click=lambda e, gf=gif_file, fc=frame_count: self._on_gif_next_frame(gf, fc),
                                    tooltip="下一帧",
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_SMALL,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ORANGE),
                    )
                )
            
            try:
                self.gif_files_list.update()
            except:
                pass
        else:
            # 隐藏 GIF 选项
            self.gif_options.visible = False
        
        try:
            self.gif_options.update()
        except:
            pass
    
    def _on_gif_prev_frame(self, gif_file: Path, frame_count: int) -> None:
        """GIF 上一帧按钮点击事件。"""
        key = str(gif_file)
        current = self.gif_frame_selection.get(key, 0)
        self.gif_frame_selection[key] = (current - 1) % frame_count
        self._update_gif_options()
    
    def _on_gif_next_frame(self, gif_file: Path, frame_count: int) -> None:
        """GIF 下一帧按钮点击事件。"""
        key = str(gif_file)
        current = self.gif_frame_selection.get(key, 0)
        self.gif_frame_selection[key] = (current + 1) % frame_count
        self._update_gif_options()
    
    def _on_gif_frame_submit(self, e: ft.ControlEvent, gif_file: Path, frame_count: int) -> None:
        """GIF 帧输入框提交事件。"""
        try:
            frame_num = int(e.control.value)
            if 1 <= frame_num <= frame_count:
                self.gif_frame_selection[str(gif_file)] = frame_num - 1
                self._update_gif_options()
            else:
                self._show_message(f"帧号必须在 1 到 {frame_count} 之间", ft.Colors.ORANGE)
                self._update_gif_options()
        except ValueError:
            self._show_message("请输入有效的数字", ft.Colors.ORANGE)
            self._update_gif_options()
    
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
        # 只有当有文件且模型已加载时才启用按钮
        button = self.process_button.content
        button.disabled = not (self.selected_files and self.bg_remover)
        self.process_button.update()
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if not self.selected_files:
            self._show_snackbar("请先选择图片文件", ft.Colors.ORANGE)
            return
        
        if not self.bg_remover:
            self._show_snackbar("模型未加载，请稍候", ft.Colors.RED)
            return
        
        # 确定输出目录
        if self.output_mode_radio.value == "custom":
            output_dir = Path(self.custom_output_dir.value)
        else:
            output_dir = self.config_service.get_data_dir() / "background_removed"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 禁用处理按钮并显示进度（一次性更新所有UI，减少刷新次数）
        button = self.process_button.content
        button.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备处理..."
        
        # 一次性更新页面，减少UI刷新次数，避免卡顿
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
                    # 检查是否是 GIF，如果是则显示帧信息
                    is_gif = GifUtils.is_animated_gif(file_path)
                    if is_gif:
                        frame_index = self.gif_frame_selection.get(str(file_path), 0)
                        progress = i / total_files
                        self._update_progress(progress, f"正在处理 GIF (帧 {frame_index + 1}): {file_path.name} ({i+1}/{total_files})")
                    else:
                        # 更新进度
                        progress = i / total_files
                        self._update_progress(progress, f"正在处理: {file_path.name} ({i+1}/{total_files})")
                    
                    # 读取图片
                    from PIL import Image
                    
                    # 检查是否是 GIF，如果是则提取指定帧
                    if is_gif:
                        image = GifUtils.extract_frame(file_path, frame_index)
                        if image is None:
                            logger.error(f"提取 GIF 帧失败: {file_path.name}")
                            continue
                    else:
                        image = Image.open(file_path)
                    
                    # 移除背景
                    result = self.bg_remover.remove_background(image)
                    
                    # 生成输出文件名
                    if self.output_mode_radio.value == "new":
                        output_filename = f"{file_path.stem}_no_bg.png"
                        output_path = file_path.parent / output_filename
                    else:
                        output_filename = f"{file_path.stem}_no_bg.png"
                        output_path = output_dir / output_filename
                    
                    # 保存为PNG格式（保留透明通道）
                    result.save(output_path, "PNG", optimize=True)
                    
                    success_count += 1
                    
                except Exception as ex:
                    logger.error(f"处理失败 {file_path.name}: {ex}")
            
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
            # 一次性更新整个页面，而不是分别更新两个控件
            self.page.update()
        except:
            pass
    
    def _on_process_complete(self, success_count: int, total: int, output_dir: Path) -> None:
        """处理完成回调。
        
        Args:
            success_count: 成功处理的数量
            total: 总数量
            output_dir: 输出目录
        """
        # 更新进度和按钮状态（一次性更新）
        self.progress_bar.value = 1.0
        self.progress_text.value = f"处理完成! 成功: {success_count}/{total}"
        button = self.process_button.content
        button.disabled = False
         
        try:
            # 一次性更新页面，提高响应速度
            self.page.update()
        except:
            pass
        
        # 显示成功消息
        if self.output_mode_radio.value == "new":
            self._show_snackbar(
                f"处理完成! 成功处理 {success_count} 个文件，保存在原文件旁边",
                ft.Colors.GREEN
            )
        else:
            self._show_snackbar(
                f"处理完成! 成功处理 {success_count} 个文件，保存到: {output_dir}",
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
            self._update_process_button()
            self._show_snackbar(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_snackbar("背景移除工具不支持该格式", ft.Colors.ORANGE)
        
        self.page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。
        
        在视图被销毁时调用，确保所有资源被正确释放。
        """
        import gc
        
        try:
            # 1. 卸载背景移除模型（使用 unload_model 更彻底地释放内存）
            if self.bg_remover:
                if hasattr(self.bg_remover, 'unload_model'):
                    self.bg_remover.unload_model()
                del self.bg_remover
                self.bg_remover = None
            
            # 2. 清空文件列表
            if self.selected_files:
                self.selected_files.clear()
            
            # 3. 清空 GIF 帧选择
            if self.gif_frame_selection:
                self.gif_frame_selection.clear()
            
            # 4. 清除回调引用，打破循环引用
            self.on_back = None
            
            # 5. 清除 UI 内容
            self.content = None
            
            # 6. 强制垃圾回收
            gc.collect()
            
            logger.info("背景移除视图资源已清理")
        except Exception as e:
            logger.warning(f"清理背景移除视图资源时出错: {e}")