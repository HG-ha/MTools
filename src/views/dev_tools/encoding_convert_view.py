# -*- coding: utf-8 -*-
"""编码转换详细视图模块。

提供完整的编码检测和转换功能界面。
"""

from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_XLARGE,
)
from services import ConfigService, EncodingService
from utils import format_file_size


class EncodingConvertView(ft.Container):
    """编码转换详细视图类。
    
    提供编码转换功能，包括：
    - 单文件和批量转换
    - 自动编码检测
    - 源编码和目标编码选择
    - 递归扫描目录
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        encoding_service: EncodingService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化编码转换视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            encoding_service: 编码服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.encoding_service: EncodingService = encoding_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        
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
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("编码转换", size=28, weight=ft.FontWeight.BOLD, ),
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
                        ft.Text("选择文件:", size=14, weight=ft.FontWeight.W_500),
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
                # 支持格式说明
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持常见文本文件: .txt, .py, .java, .c, .cpp, .js, .html, .css, .json, .xml, .md 等",
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
        
        # 编码选项
        self.auto_detect_checkbox: ft.Checkbox = ft.Checkbox(
            label="自动检测源编码",
            value=True,
            on_change=self._on_auto_detect_change,
        )
        
        self.source_encoding_dropdown: ft.Dropdown = ft.Dropdown(
            label="源编码",
            options=[
                ft.dropdown.Option(enc) for enc in self.encoding_service.SUPPORTED_ENCODINGS
            ],
            value="UTF-8",
            disabled=True,
            expand=True,
        )
        
        self.target_encoding_dropdown: ft.Dropdown = ft.Dropdown(
            label="目标编码",
            options=[
                ft.dropdown.Option(enc) for enc in self.encoding_service.SUPPORTED_ENCODINGS
            ],
            value="UTF-8",
            expand=True,
        )
        
        encoding_options: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("编码选项:", size=14, weight=ft.FontWeight.W_500),
                    self.auto_detect_checkbox,
                    ft.Row(
                        controls=[
                            self.source_encoding_dropdown,
                            ft.Icon(ft.Icons.ARROW_FORWARD, size=24),
                            self.target_encoding_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    # 提示信息
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.TIPS_AND_UPDATES_OUTLINED, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "推荐使用UTF-8编码，具有最好的兼容性和通用性",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=4),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,
        )
        
        # 输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="overwrite", label="覆盖原文件（会自动备份为.bak）"),
                    ft.Radio(value="new", label="保存为新文件（添加.converted后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
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
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,
        )
        
        # 进度显示
        self.progress_bar: ft.ProgressBar = ft.ProgressBar(visible=False)
        self.progress_text: ft.Text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 底部按钮
        self.convert_button: ft.Container = ft.Container(
            content=ft.Button(
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
            alignment=ft.Alignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content: ft.Column = ft.Column(
            controls=[
                file_select_area,
                ft.Row(
                    controls=[
                        encoding_options,
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
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处选择文本文件", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=252,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_empty_area_click,
                ink=True,
            )
        )
    
    async def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        await self._on_select_files(e)
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        # 文本文件扩展名（去掉点号）
        extensions: List[str] = [ext.lstrip('.') for ext in self.encoding_service.TEXT_FILE_EXTENSIONS]
        
        result = await ft.FilePicker().pick_files(
            dialog_title="选择文本文件",
            allowed_extensions=extensions,
            allow_multiple=True,
        )
        
        if result and result.files:
            new_files: List[Path] = [Path(f.path) for f in result.files]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择文本文件夹")
        
        if result:
            folder: Path = Path(result)
            # 扫描文件夹中的文本文件
            self.selected_files = self.encoding_service.scan_directory(folder, recursive=False)
            self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击此处选择文本文件", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=252,
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_empty_area_click,
                    ink=True,
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                # 获取文件信息
                file_info: dict = self.encoding_service.get_file_info(file_path)
                
                file_size: int = file_info.get('size', 0)
                size_str: str = format_file_size(file_size)
                encoding: str = file_info.get('encoding', '未知')
                confidence: float = file_info.get('confidence', 0.0)
                
                # 编码置信度颜色
                if confidence >= 0.9:
                    confidence_color: str = ft.Colors.GREEN
                elif confidence >= 0.7:
                    confidence_color = ft.Colors.ORANGE
                else:
                    confidence_color = ft.Colors.RED
                
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
                                ft.Icon(ft.Icons.DESCRIPTION, size=20, color=ft.Colors.PRIMARY),
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
                                                ft.Icon(ft.Icons.CODE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(encoding, size=11, color=confidence_color, weight=ft.FontWeight.W_500),
                                                ft.Text(f"({confidence:.0%})", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(size_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
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
    
    def _on_remove_file(self, index: int) -> None:
        """移除单个文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_auto_detect_change(self, e: ft.ControlEvent) -> None:
        """自动检测变化事件。"""
        auto_detect: bool = e.control.value
        self.source_encoding_dropdown.disabled = auto_detect
        self.source_encoding_dropdown.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode: str = e.control.value
        is_custom: bool = mode == "custom"
        
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        self.custom_output_dir.update()
        self.browse_output_button.update()
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        
        if result:
            self.custom_output_dir.value = result
            self.custom_output_dir.update()
    
    def _on_convert(self, e: ft.ControlEvent) -> None:
        """开始转换按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择要转换的文件", ft.Colors.ORANGE)
            return
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备转换..."
        self.progress_bar.update()
        self.progress_text.update()
        
        # 获取参数
        auto_detect: bool = self.auto_detect_checkbox.value
        source_encoding: Optional[str] = None if auto_detect else self.source_encoding_dropdown.value
        target_encoding: str = self.target_encoding_dropdown.value
        output_mode: str = self.output_mode_radio.value
        
        # 获取输出目录
        output_dir: Optional[Path] = None
        if output_mode == "custom":
            output_dir = Path(self.custom_output_dir.value)
        
        # 进度回调
        def progress_callback(current: int, total: int, file_name: str) -> None:
            self.progress_text.value = f"正在转换 ({current}/{total}): {file_name}"
            self.progress_bar.value = current / total
            self.progress_text.update()
            self.progress_bar.update()
        
        # 批量转换
        result: dict = self.encoding_service.batch_convert(
            file_paths=self.selected_files,
            target_encoding=target_encoding,
            source_encoding=source_encoding,
            output_mode=output_mode,
            output_dir=output_dir,
            callback=progress_callback
        )
        
        # 显示结果
        self.progress_bar.visible = False
        self.progress_bar.update()
        
        success_count: int = result['success_count']
        failed_count: int = result['failed_count']
        total: int = len(self.selected_files)
        
        result_message: str = f"转换完成！\n成功: {success_count}/{total}"
        if failed_count > 0:
            result_message += f"\n失败: {failed_count}"
        
        self.progress_text.value = result_message
        self.progress_text.update()
        
        # 显示通知
        if failed_count == 0:
            self._show_message("转换完成！", ft.Colors.GREEN)
        else:
            self._show_message(f"转换完成，但有{failed_count}个文件失败", ft.Colors.ORANGE)
    
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
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        added_count = 0
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path not in self.selected_files:
                self.selected_files.append(path)
                added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
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
