# -*- coding: utf-8 -*-
"""图片格式转换视图模块。

提供图片格式转换功能的用户界面。
"""

from pathlib import Path
from typing import Callable, List, Optional, Dict

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils


class ImageFormatView(ft.Container):
    """图片格式转换视图类。
    
    提供图片格式转换功能，包括：
    - 单文件和批量转换
    - 多种格式支持（JPG、PNG、WebP、GIF等）
    - 质量调整
    - 批量处理
    """

    # 支持的图片格式
    SUPPORTED_FORMATS = [
        ("JPEG", ".jpg", "最常用的图片格式，有损压缩"),
        ("PNG", ".png", "无损压缩，支持透明通道"),
        ("WebP", ".webp", "现代格式，体积小质量好"),
        ("GIF", ".gif", "支持动画的格式"),
        ("BMP", ".bmp", "位图格式，无压缩"),
        ("TIFF", ".tiff", "专业图像格式"),
        ("ICO", ".ico", "图标格式"),
    ]

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片格式转换视图。
        
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
        # GIF 文件的帧选择映射：{文件路径: 帧索引}
        self.gif_frame_selection: Dict[str, int] = {}
        
        self.expand: bool = True
        # 右侧多留一些空间给滚动条
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 构建界面
        self._build_ui()
    
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
                ft.Text("图片格式转换", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.AUTO,
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
                                "支持格式: JPG, JFIF, PNG, WebP, GIF, TIFF, BMP, ICO 等",
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
                    height=300,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 格式选项 - 使用卡片式布局
        self.selected_format: str = ".jpg"
        self.format_cards: List[ft.Container] = []
        
        format_cards_row: ft.Row = ft.Row(
            controls=[],
            wrap=True,
            spacing=PADDING_MEDIUM // 2,
            run_spacing=PADDING_MEDIUM // 2,
        )
        
        for name, ext, desc in self.SUPPORTED_FORMATS:
            card: ft.Container = self._create_format_card(name, ext, desc)
            self.format_cards.append(card)
            format_cards_row.controls.append(card)
        
        # 质量滑块（仅对部分格式有效）
        self.quality_slider: ft.Slider = ft.Slider(
            min=50,
            max=100,
            value=85,
            divisions=50,
            label="{value}",
            on_change=self._on_quality_change,
        )
        
        self.quality_text: ft.Text = ft.Text("质量: 85", size=14)
        
        format_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("目标格式:", size=14, weight=ft.FontWeight.W_500),
                    format_cards_row,
                    ft.Container(height=PADDING_MEDIUM),
                    self.quality_text,
                    self.quality_slider,
                    # 提示信息
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "质量设置对JPG、WebP、TIFF格式有效",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=4),
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,
            height=340,
        )
        
        # 输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same_dir", label="保存到原目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="same_dir",
            on_change=self._on_output_mode_change,
        )
        
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
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
                            ft.Icon(ft.Icons.GIF_BOX, size=20, color=ft.Colors.PRIMARY),
                            ft.Text("GIF 帧选择", size=14, weight=ft.FontWeight.W_500),
                        ],
                        spacing=8,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "检测到 GIF 文件，转换为静态格式时请选择要导出的帧",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        margin=ft.margin.only(left=4, bottom=PADDING_SMALL),
                    ),
                    ft.Container(
                        content=self.gif_files_list,
                        height=200,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        padding=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.PRIMARY_CONTAINER),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        
        output_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    # 提示信息
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.TIPS_AND_UPDATES_OUTLINED, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "转换后的文件会自动添加新的扩展名",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=PADDING_MEDIUM),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,
            height=340,
        )
        
        # 进度显示
        self.progress_bar: ft.ProgressBar = ft.ProgressBar(visible=False)
        self.progress_text: ft.Text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 底部按钮
        self.convert_button: ft.Container = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TRANSFORM, size=24),
                        ft.Text("开始转换", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_convert,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
        )
        
        # 可滚动内容区域
        scrollable_content: ft.Column = ft.Column(
            controls=[
                file_select_area,
                self.gif_options,
                ft.Row(
                    controls=[
                        format_options,
                        output_options,
                    ],
                    spacing=PADDING_LARGE,
                ),
                self.progress_bar,
                self.progress_text,
                self.convert_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.HIDDEN,
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
        )
        
        # 初始化空状态
        self._init_empty_state()
    
    def _create_format_card(self, name: str, ext: str, desc: str) -> ft.Container:
        """创建格式选择卡片。
        
        Args:
            name: 格式名称
            ext: 文件扩展名
            desc: 格式描述
        
        Returns:
            格式卡片容器
        """
        is_selected: bool = ext == self.selected_format
        
        card: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        name,
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        ext,
                        size=11,
                        color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            width=85,
            height=65,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.PRIMARY if is_selected else None,
            border=ft.border.all(
                2 if is_selected else 1,
                ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
            ),
            padding=PADDING_MEDIUM // 2,
            alignment=ft.alignment.center,
            data=ext,  # 存储扩展名数据
            on_click=self._on_format_card_click,
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        
        return card
    
    def _on_format_card_click(self, e: ft.ControlEvent) -> None:
        """格式卡片点击事件。
        
        Args:
            e: 控件事件对象
        """
        clicked_format: str = e.control.data
        if clicked_format == self.selected_format:
            return  # 已选中，无需更新
        
        # 更新选中的格式
        self.selected_format = clicked_format
        
        # 更新所有卡片的样式
        for card in self.format_cards:
            is_selected: bool = card.data == self.selected_format
            
            # 更新背景和边框
            card.bgcolor = ft.Colors.PRIMARY if is_selected else None
            card.border = ft.border.all(
                2 if is_selected else 1,
                ft.Colors.PRIMARY if is_selected else ft.Colors.OUTLINE
            )
            
            # 更新文本颜色
            if card.content and isinstance(card.content, ft.Column):
                for control in card.content.controls:
                    if isinstance(control, ft.Text):
                        if control.size == 13:  # 名称
                            control.color = ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE
                        else:  # 扩展名
                            control.color = ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE_VARIANT
            
            card.update()
        
        # 更新 GIF 选项（如果目标格式变为 GIF，则隐藏 GIF 选项）
        self._update_gif_options()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
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
                height=252,
                alignment=ft.alignment.center,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        self._on_select_files(e)
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                new_files: List[Path] = [Path(f.path) for f in result.files]
                for new_file in new_files:
                    if new_file not in self.selected_files:
                        self.selected_files.append(new_file)
                self._update_file_list()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tiff", "tif", "ico"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder: Path = Path(result.path)
                # 获取文件夹中的所有图片
                extensions: List[str] = [".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".ico"]
                self.selected_files = []
                for ext in extensions:
                    self.selected_files.extend(folder.glob(f"*{ext}"))
                    self.selected_files.extend(folder.glob(f"*{ext.upper()}"))
                self._update_file_list()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择图片文件夹")
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
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
                    height=252,
                    alignment=ft.alignment.center,
                    on_click=self._on_empty_area_click,
                    ink=True,
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                # 获取文件信息
                file_info: dict = self.image_service.get_image_info(file_path)
                
                # 获取文件大小（使用 file_size 键而不是 size）
                file_size: int = file_info.get('file_size', 0)
                size_str: str = format_file_size(file_size)
                
                if 'error' not in file_info:
                    format_str: str = file_info.get('format', '未知')
                    width: int = file_info.get('width', 0)
                    height: int = file_info.get('height', 0)
                    dimension_str: str = f"{width} × {height}"
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
                                    alignment=ft.alignment.center,
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
                                    on_click=lambda e, i=idx: self._on_remove_file(i),
                                ),
                            ],
                            spacing=PADDING_MEDIUM // 2,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_MEDIUM,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if idx % 2 == 0 else None,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.OUTLINE)),
                    )
                )
        
        self.file_list_view.update()
        
        # 检查是否有 GIF 文件并更新 GIF 选项
        self._update_gif_options()
    
    def _update_gif_options(self) -> None:
        """更新 GIF 选项区域。"""
        # 检测动态 GIF 文件
        gif_files = [f for f in self.selected_files if GifUtils.is_animated_gif(f)]
        
        # 只有在目标格式不是 GIF 时才显示 GIF 选项
        is_target_static = self.selected_format != ".gif"
        
        if gif_files and is_target_static:
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
                    width=60,
                    text_align=ft.TextAlign.CENTER,
                    dense=True,
                    on_submit=lambda e, gf=gif_file, fc=frame_count: self._on_gif_frame_submit(e, gf, fc),
                )
                
                self.gif_files_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.GIF, size=20, color=ft.Colors.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(gif_file.name, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(f"共 {frame_count} 帧", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SKIP_PREVIOUS,
                                    icon_size=18,
                                    on_click=lambda e, gf=gif_file, fc=frame_count: self._on_gif_prev_frame(gf, fc),
                                    tooltip="上一帧",
                                ),
                                ft.Text("帧:", size=12),
                                frame_input,
                                ft.Text(f"/ {frame_count}", size=12),
                                ft.IconButton(
                                    icon=ft.Icons.SKIP_NEXT,
                                    icon_size=18,
                                    on_click=lambda e, gf=gif_file, fc=frame_count: self._on_gif_next_frame(gf, fc),
                                    tooltip="下一帧",
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_SMALL,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
                    )
                )
            
            self.gif_files_list.update()
        else:
            # 隐藏 GIF 选项
            self.gif_options.visible = False
        
        self.gif_options.update()
    
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
    
    def _on_remove_file(self, index: int) -> None:
        """移除单个文件。"""
        if 0 <= index < len(self.selected_files):
            removed_file = self.selected_files.pop(index)
            # 清理 GIF 帧选择记录
            if str(removed_file) in self.gif_frame_selection:
                del self.gif_frame_selection[str(removed_file)]
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_quality_change(self, e: ft.ControlEvent) -> None:
        """质量滑块变化事件。"""
        quality: int = int(e.control.value)
        self.quality_text.value = f"质量: {quality}"
        self.quality_text.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode: str = e.control.value
        is_custom: bool = mode == "custom"
        
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        self.custom_output_dir.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.custom_output_dir.update()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _on_convert(self, e: ft.ControlEvent) -> None:
        """开始转换按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择要转换的图片", ft.Colors.ORANGE)
            return
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备转换..."
        self.progress_bar.update()
        self.progress_text.update()
        
        # 获取参数
        target_format: str = self.selected_format
        quality: int = int(self.quality_slider.value)
        output_mode: str = self.output_mode_radio.value
        
        # 获取输出目录
        if output_mode == "custom":
            output_dir: Path = Path(self.custom_output_dir.value)
        else:
            output_dir = None
        
        # 转换文件
        total: int = len(self.selected_files)
        success_count: int = 0
        
        for i, input_path in enumerate(self.selected_files):
            # 检查是否是 GIF → 静态格式的转换
            is_gif = GifUtils.is_animated_gif(input_path)
            is_target_static = target_format != ".gif"
            
            # 更新进度（如果是 GIF 转换则显示帧信息）
            if is_gif and is_target_static:
                frame_index = self.gif_frame_selection.get(str(input_path), 0)
                self.progress_text.value = f"正在转换 GIF (帧 {frame_index + 1}) ({i+1}/{total}): {input_path.name}"
            else:
                self.progress_text.value = f"正在转换 ({i+1}/{total}): {input_path.name}"
            
            self.progress_bar.value = (i + 1) / total
            self.progress_text.update()
            self.progress_bar.update()
            
            # 确定输出路径
            if output_dir:
                output_path: Path = output_dir / f"{input_path.stem}{target_format}"
            else:
                output_path = input_path.parent / f"{input_path.stem}{target_format}"
            
            # 如果目标格式和源格式相同，跳过
            if input_path.suffix.lower() == target_format.lower():
                continue
            
            if is_gif and is_target_static:
                # GIF → 静态格式：提取指定帧后转换
                frame_index = self.gif_frame_selection.get(str(input_path), 0)
                frame_image = GifUtils.extract_frame(input_path, frame_index)
                
                if frame_image:
                    try:
                        # 保存提取的帧
                        if target_format in [".jpg", ".jpeg"]:
                            # JPG 不支持透明通道
                            frame_image = frame_image.convert("RGB")
                        
                        # 保存时应用质量设置
                        if target_format in [".jpg", ".jpeg", ".webp"]:
                            frame_image.save(output_path, quality=quality)
                        else:
                            frame_image.save(output_path)
                        
                        success_count += 1
                    except Exception as ex:
                        print(f"保存 GIF 帧失败: {ex}")
                else:
                    print(f"提取 GIF 帧失败: {input_path}")
            else:
                # 普通转换
                success: bool = self.image_service.convert_format(
                    input_path,
                    output_path,
                    quality=quality
                )
                
                if success:
                    success_count += 1
        
        # 显示结果
        self.progress_bar.visible = False
        self.progress_bar.update()
        
        result_message: str = f"转换完成！\n成功: {success_count}/{total}"
        self.progress_text.value = result_message
        self.progress_text.update()
        
        self._show_message("转换完成！", ft.Colors.GREEN)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

