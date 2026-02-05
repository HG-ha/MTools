# -*- coding: utf-8 -*-
"""图片尺寸调整视图模块。

提供图片尺寸调整功能的用户界面。
"""

from pathlib import Path
from typing import List, Optional, Dict

import flet as ft
from PIL import Image

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils, get_unique_path


class ImageResizeView(ft.Container):
    """图片尺寸调整视图类。
    
    提供图片尺寸调整功能，包括：
    - 按百分比缩放
    - 按固定宽度/高度调整
    - 保持宽高比
    - 批量处理
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', 
        '.gif', '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[callable] = None
    ) -> None:
        """初始化图片尺寸调整视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[callable] = on_back
        
        self.selected_files: List[Path] = []
        # GIF 文件映射：{文件路径: (是否GIF, 帧数)}
        self.gif_info: Dict[str, tuple] = {}
        
        self.expand: bool = True
        # 右侧多留一些空间给滚动条
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
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("尺寸调整", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.AUTO,
        )
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择图片:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button(
                            content="选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_files,
                        ),
                        ft.Button(
                            content="选择文件夹",
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
                                "支持格式: JPG, PNG, WebP, GIF, TIFF, BMP, ICO, AVIF, HEIC 等",
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
                    height=280,  # 文件列表高度
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 调整模式选项
        self.resize_mode = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="percentage", label="按百分比缩放"),
                    ft.Radio(value="width", label="按宽度调整（保持宽高比）"),
                    ft.Radio(value="height", label="按高度调整（保持宽高比）"),
                    ft.Radio(value="custom", label="自定义宽度和高度"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="percentage",
            on_change=self._on_resize_mode_change,
        )
        
        # 百分比输入
        self.percentage_slider = ft.Slider(
            min=10,
            max=200,
            value=100,
            divisions=19,
            label="{value}%",
            on_change=self._on_percentage_change,
        )
        
        self.percentage_text = ft.Text("缩放比例: 100%", size=14)
        
        # 宽度输入
        self.width_field = ft.TextField(
            label="宽度 (px)",
            hint_text="例如: 1920",
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            width=200,
        )
        
        # 高度输入
        self.height_field = ft.TextField(
            label="高度 (px)",
            hint_text="例如: 1080",
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            width=200,
        )
        
        # 保持宽高比选项
        self.keep_aspect_checkbox = ft.Checkbox(
            label="保持宽高比",
            value=True,
            visible=False,
        )
        
        self.resize_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("调整模式:", size=14, weight=ft.FontWeight.W_500),
                    self.resize_mode,
                    ft.Container(height=PADDING_MEDIUM),
                    self.percentage_text,
                    self.percentage_slider,
                    ft.Row(
                        controls=[
                            self.width_field,
                            self.height_field,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    self.keep_aspect_checkbox,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            expand=1,  # 平分宽度
            height=320,  # 固定高度
        )
        
        # 输出选项
        self.output_mode = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="overwrite", label="覆盖原文件"),
                    ft.Radio(value="new_file", label="保存为新文件"),
                    ft.Radio(value="custom_dir", label="保存到指定目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new_file",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            hint_text="例如: _resized",
            value="_resized",
            width=200,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            hint_text="选择输出目录",
            value=str(self.config_service.get_output_dir()),
            read_only=True,
            expand=True,
            visible=False,
        )
        
        self.browse_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            visible=False,
        )
        
        self.output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode,
                    self.file_suffix,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_button,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            expand=1,  # 平分宽度
            height=320,  # 固定高度
        )
        
        # GIF 信息提示（初始隐藏）
        self.gif_info_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.GIF_BOX, size=20, color=ft.Colors.PRIMARY),
                    ft.Text(
                        "检测到 GIF 文件，将自动调整所有帧的尺寸",
                        size=13,
                    ),
                ],
                spacing=8,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.PRIMARY),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            visible=False,
        )
        
        # 底部按钮 - 大号主按钮
        self.resize_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PHOTO_SIZE_SELECT_LARGE, size=24),
                        ft.Text("开始调整", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_resize,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                self.gif_info_banner,
                ft.Row(
                    controls=[
                        self.resize_options,
                        self.output_options,
                    ],
                    spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self.progress_bar,
                self.progress_text,
                self.resize_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.HIDDEN,
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
        
        # 初始化文件列表
        self._init_empty_state()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示（不调用update）。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=232,  # 280 - 2*24(padding) = 232
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    def _resize_gif(self, input_path: Path, output_path: Path, width: Optional[int], height: Optional[int], keep_aspect: bool) -> bool:
        """调整 GIF 所有帧的尺寸。
        
        Args:
            input_path: 输入 GIF 路径
            output_path: 输出 GIF 路径
            width: 目标宽度
            height: 目标高度
            keep_aspect: 是否保持宽高比
            
        Returns:
            是否成功
        """
        try:
            with Image.open(input_path) as gif:
                # 获取 GIF 参数
                duration = gif.info.get('duration', 100)
                loop = gif.info.get('loop', 0)
                
                # 获取所有帧
                frames = GifUtils.extract_all_frames(input_path)
                if not frames:
                    return False
                
                # 计算目标尺寸
                first_frame = frames[0]
                orig_width, orig_height = first_frame.size
                
                if width and height:
                    if keep_aspect:
                        # 保持宽高比，以最小的缩放比例为准
                        ratio = min(width / orig_width, height / orig_height)
                        target_width = int(orig_width * ratio)
                        target_height = int(orig_height * ratio)
                    else:
                        target_width = width
                        target_height = height
                elif width:
                    ratio = width / orig_width
                    target_width = width
                    target_height = int(orig_height * ratio)
                elif height:
                    ratio = height / orig_height
                    target_width = int(orig_width * ratio)
                    target_height = height
                else:
                    return False
                
                # 调整所有帧的尺寸
                resized_frames = []
                for frame in frames:
                    resized = frame.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    resized_frames.append(resized)
                
                # 保存为 GIF
                if resized_frames:
                    resized_frames[0].save(
                        output_path,
                        save_all=True,
                        append_images=resized_frames[1:],
                        duration=duration,
                        loop=loop,
                        optimize=False,
                    )
                    return True
                
                return False
        except Exception as e:
            return False
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files(e)
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tiff", "tif", "ico", "avif", "heic", "heif"],
            allow_multiple=True,
        )
        if files:
            # 追加新文件，过滤掉 path 为 None 的文件（Web 模式下 path 为 None）
            new_files = []
            web_mode_count = 0
            for f in files:
                if f.path:
                    new_files.append(Path(f.path))
                else:
                    web_mode_count += 1
            
            # 如果所有文件都没有路径（Web 模式），显示提示
            if web_mode_count > 0 and not new_files:
                self._show_message("Web 模式不支持本地文件处理，请使用桌面客户端", ft.Colors.ORANGE)
                return
            
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择图片文件夹")
        if folder_path:
            folder = Path(folder_path)
            extensions = [".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".ico", ".avif", ".heic", ".heif"]
            self.selected_files = []
            for ext in extensions:
                self.selected_files.extend(folder.glob(f"*{ext}"))
                self.selected_files.extend(folder.glob(f"*{ext.upper()}"))
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        self.gif_info.clear()  # 清除 GIF 信息
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=232,
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_empty_area_click,
                    ink=True,
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                img_info = self.image_service.get_image_info(file_path)
                
                # 检测是否为 GIF
                is_gif = GifUtils.is_animated_gif(file_path)
                if is_gif:
                    frame_count = GifUtils.get_frame_count(file_path)
                    self.gif_info[str(file_path)] = (True, frame_count)
                
                if 'error' not in img_info:
                    format_str = img_info.get('format', '未知')
                    width = img_info.get('width', 0)
                    height = img_info.get('height', 0)
                    if is_gif:
                        dimension_str = f"{width} × {height} · {frame_count}帧"
                    else:
                        dimension_str = f"{width} × {height}"
                else:
                    format_str = file_path.suffix.upper().lstrip('.')
                    dimension_str = "无法读取"
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                # 序号
                                ft.Container(
                                    content=ft.Text(
                                        str(idx + 1),
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    width=30,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                # 文件图标
                                ft.Icon(ft.Icons.IMAGE, size=20, color=ft.Colors.PRIMARY),
                                # 文件详细信息
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            file_path.name,
                                            size=13,
                                            weight=ft.FontWeight.W_500,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            controls=[
                                                ft.Icon(ft.Icons.PHOTO_SIZE_SELECT_ACTUAL, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(dimension_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(size_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(format_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                # 删除按钮
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, path=file_path: self._remove_file(path),
                                ),
                            ],
                            spacing=PADDING_MEDIUM // 2,
                        ),
                        padding=ft.padding.symmetric(vertical=8, horizontal=PADDING_MEDIUM),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        ink=True,
                    )
                )
        
        self.file_list_view.update()
        
        # 更新 GIF 提示横幅
        if self.gif_info:
            gif_count = len(self.gif_info)
            total_frames = sum(info[1] for info in self.gif_info.values())
            self.gif_info_banner.content.controls[1].value = (
                f"检测到 {gif_count} 个 GIF 文件（共 {total_frames} 帧），将自动调整所有帧的尺寸"
            )
            self.gif_info_banner.visible = True
        else:
            self.gif_info_banner.visible = False
        
        try:
            self.gif_info_banner.update()
        except:
            pass
    
    def _remove_file(self, file_path: Path) -> None:
        """移除单个文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _on_resize_mode_change(self, e: ft.ControlEvent) -> None:
        """调整模式变化事件。"""
        mode = self.resize_mode.value
        
        # 显示/隐藏相应的控件
        if mode == "percentage":
            self.percentage_text.visible = True
            self.percentage_slider.visible = True
            self.width_field.visible = False
            self.height_field.visible = False
            self.keep_aspect_checkbox.visible = False
        elif mode == "width":
            self.percentage_text.visible = False
            self.percentage_slider.visible = False
            self.width_field.visible = True
            self.height_field.visible = False
            self.keep_aspect_checkbox.visible = False
        elif mode == "height":
            self.percentage_text.visible = False
            self.percentage_slider.visible = False
            self.width_field.visible = False
            self.height_field.visible = True
            self.keep_aspect_checkbox.visible = False
        elif mode == "custom":
            self.percentage_text.visible = False
            self.percentage_slider.visible = False
            self.width_field.visible = True
            self.height_field.visible = True
            self.keep_aspect_checkbox.visible = True
        
        self.resize_options.update()
    
    def _on_percentage_change(self, e: ft.ControlEvent) -> None:
        """百分比滑块变化事件。"""
        self.percentage_text.value = f"缩放比例: {int(self.percentage_slider.value)}%"
        self.percentage_text.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = self.output_mode.value
        
        if mode == "new_file":
            self.file_suffix.visible = True
            self.custom_output_dir.visible = False
            self.browse_button.visible = False
        elif mode == "custom_dir":
            self.file_suffix.visible = False
            self.custom_output_dir.visible = True
            self.browse_button.visible = True
        else:  # overwrite
            self.file_suffix.visible = False
            self.custom_output_dir.visible = False
            self.browse_button.visible = False
        
        self.output_options.update()
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self.custom_output_dir.update()
    
    def _on_resize(self, e: ft.ControlEvent) -> None:
        """开始调整按钮点击事件。"""
        if not self.selected_files:
            self.progress_text.value = "❌ 请先选择图片文件"
            self.progress_text.update()
            return
        
        # 获取调整参数
        mode = self.resize_mode.value
        width = None
        height = None
        keep_aspect = True
        
        try:
            if mode == "percentage":
                # 百分比模式将在处理时针对每个文件计算
                pass
            elif mode == "width":
                width = int(self.width_field.value) if self.width_field.value else None
                if not width:
                    raise ValueError("请输入宽度")
            elif mode == "height":
                height = int(self.height_field.value) if self.height_field.value else None
                if not height:
                    raise ValueError("请输入高度")
            elif mode == "custom":
                width = int(self.width_field.value) if self.width_field.value else None
                height = int(self.height_field.value) if self.height_field.value else None
                keep_aspect = self.keep_aspect_checkbox.value
                if not width and not height:
                    raise ValueError("请至少输入宽度或高度")
        except ValueError as e:
            self.progress_text.value = f"❌ {str(e)}"
            self.progress_text.update()
            return
        
        # 显示进度条
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.resize_button.visible = False
        self.progress_text.value = "开始处理..."
        self.update()
        
        # 处理文件
        success_count = 0
        fail_count = 0
        total = len(self.selected_files)
        
        for idx, file_path in enumerate(self.selected_files):
            try:
                # 确定输出路径
                output_mode = self.output_mode.value
                if output_mode == "overwrite":
                    output_path = file_path
                elif output_mode == "new_file":
                    suffix = self.file_suffix.value or "_resized"
                    output_path = file_path.parent / f"{file_path.stem}{suffix}{file_path.suffix}"
                else:  # custom_dir
                    output_dir = Path(self.custom_output_dir.value) if self.custom_output_dir.value else file_path.parent
                    output_path = output_dir / file_path.name
                
                # 根据全局设置决定是否添加序号（覆盖模式除外）
                if output_mode != "overwrite":
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)
                
                # 检查是否为 GIF
                is_gif = str(file_path) in self.gif_info
                
                # 如果是百分比模式，计算实际尺寸
                if mode == "percentage":
                    img_info = self.image_service.get_image_info(file_path)
                    if 'error' not in img_info:
                        original_width = img_info['width']
                        original_height = img_info['height']
                        percentage = self.percentage_slider.value / 100
                        width = int(original_width * percentage)
                        height = int(original_height * percentage)
                        keep_aspect = False  # 已经计算好了宽高
                
                # 调整尺寸
                if is_gif:
                    # GIF 处理：调整所有帧
                    gif_data = self.gif_info.get(str(file_path))
                    frame_count = gif_data[1] if gif_data else 0
                    if frame_count > 0:
                        self.progress_text.value = f"正在处理 GIF ({frame_count} 帧)..."
                        self.progress_text.update()
                    result = self._resize_gif(file_path, output_path, width, height, keep_aspect)
                else:
                    # 普通图片处理
                    result = self.image_service.resize_image(
                        file_path,
                        output_path,
                        width=width,
                        height=height,
                        keep_aspect=keep_aspect
                    )
                
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                
            except Exception as e:
                fail_count += 1
            
            # 更新进度
            progress = (idx + 1) / total
            self.progress_bar.value = progress
            self.progress_text.value = f"处理中... {idx + 1}/{total}"
            self.update()
        
        # 完成
        self.progress_bar.visible = False
        self.resize_button.visible = True
        self.progress_text.value = f"✅ 完成！成功: {success_count}, 失败: {fail_count}"
        self.update()
        
        # 3秒后清除消息
        import time
        time.sleep(3)
        self.progress_text.value = ""
        self.update()
    
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
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_message("尺寸调整工具不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
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
