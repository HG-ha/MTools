# -*- coding: utf-8 -*-
"""字幕格式转换视图模块。

提供字幕文件格式互转功能，支持 SRT、VTT、LRC、ASS 等格式。
"""

import threading
from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService
from utils import format_file_size, logger, get_unique_path
from utils.subtitle_utils import (
    parse_subtitle_file,
    segments_to_srt,
    segments_to_vtt,
    segments_to_lrc,
    segments_to_ass,
    segments_to_txt,
)


class SubtitleConvertView(ft.Container):
    """字幕格式转换视图类。
    
    提供字幕文件格式互转功能，包括：
    - SRT ↔ VTT ↔ LRC ↔ ASS 互转
    - 批量转换
    - 自定义输出目录
    """
    
    SUPPORTED_EXTENSIONS = {'.srt', '.vtt', '.lrc', '.ass', '.ssa', '.txt'}
    
    OUTPUT_FORMATS = [
        ("srt", "SRT  |  通用字幕格式，兼容性最好"),
        ("vtt", "VTT  |  Web 字幕格式，适用于 HTML5"),
        ("lrc", "LRC  |  歌词格式，适用于音乐播放器"),
        ("ass", "ASS  |  高级字幕格式，支持丰富样式"),
        ("txt", "TXT  |  纯文本，无时间信息"),
    ]

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化字幕转换视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.on_back: Optional[Callable] = on_back
        
        self.selected_files: List[Path] = []
        self.is_processing: bool = False
        
        # 输出格式
        self.output_format: str = self.config_service.get_config_value("subtitle_convert_format", "srt")
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
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
                ft.Text("字幕格式转换", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view: ft.Column = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        self.file_list_container: ft.Container = ft.Container(
            content=self.file_list_view,
            height=180,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            on_click=self._on_file_list_click,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择字幕:", size=14, weight=ft.FontWeight.W_500),
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
                                "支持格式: SRT, VTT, LRC, ASS/SSA, TXT",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.margin.only(left=4, bottom=4),
                ),
                self.file_list_container,
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 左侧：格式设置
        format_options = []
        for value, text in self.OUTPUT_FORMATS:
            format_options.append(ft.dropdown.Option(key=value, text=text))
        
        self.output_format_dropdown: ft.Dropdown = ft.Dropdown(
            options=format_options,
            value=self.output_format,
            label="目标格式",
            width=320,
            dense=True,
            on_select=self._on_format_change,
        )
        
        format_settings_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("格式设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.output_format_dropdown,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("格式说明", size=13),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("• SRT: 最通用的字幕格式，几乎所有播放器都支持", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• VTT: 网页视频标准格式，支持 HTML5 <video>", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• LRC: 歌词格式，可用于音乐播放器显示歌词", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• ASS: 高级字幕，支持字体、颜色、特效等样式", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• TXT: 纯文本，仅保留文字内容，无时间信息", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=4,
                        ),
                        padding=PADDING_SMALL,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 右侧：输出选项
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same", label="保存到原文件目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        default_output = self.config_service.get_output_dir() / "subtitle_converted"
        self.custom_output_dir: ft.TextField = ft.TextField(
            label="输出目录",
            value=str(default_output),
            disabled=True,
            expand=True,
            dense=True,
        )
        
        self.browse_output_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        output_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出路径", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[
                            self.custom_output_dir,
                            self.browse_output_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("转换说明", size=13),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("• 自动识别源文件编码（UTF-8、GBK等）", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• 输出统一使用 UTF-8 编码", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• LRC 转其他格式时会估算结束时间", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• ASS 样式信息在转换时会丢失", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=4,
                        ),
                        padding=PADDING_SMALL,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar: ft.ProgressBar = ft.ProgressBar(value=0, bar_height=8)
        self.progress_text: ft.Text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        
        self.progress_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    self.progress_text,
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )
        
        # 底部处理按钮
        self.process_button: ft.Container = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.SWAP_HORIZ, size=24),
                        ft.Text("开始转换", size=18, weight=ft.FontWeight.W_600),
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
            alignment=ft.Alignment.CENTER,
            margin=ft.margin.only(top=PADDING_MEDIUM, bottom=PADDING_SMALL),
        )
        
        # 主内容区域 - 垂直布局
        main_content: ft.Column = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_LARGE),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=format_settings_section,
                            expand=True,
                            height=320,
                        ),
                        ft.Container(
                            content=output_section,
                            expand=True,
                            height=320,
                        ),
                    ],
                    spacing=PADDING_LARGE,
                ),
                ft.Container(height=PADDING_MEDIUM),
                self.progress_container,
                ft.Container(height=PADDING_MEDIUM),
                self.process_button,
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
                main_content,
            ],
            spacing=0,
            expand=True,
        )
        
        # 初始化文件列表空状态
        self._update_file_list()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    async def _on_file_list_click(self, e: ft.ControlEvent) -> None:
        """文件列表区域点击事件，空状态时打开文件选择器。"""
        if not self.selected_files:
            await self._on_select_files(e)
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            allow_multiple=True,
            allowed_extensions=['srt', 'vtt', 'lrc', 'ass', 'ssa', 'txt'],
            dialog_title="选择字幕文件",
        )
        if result and result.files:
            for f in result.files:
                file_path = Path(f.path)
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择字幕文件夹")
        if result:
            folder = Path(result)
            for file_path in folder.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            # 空状态
            empty_state = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SUBTITLES_OUTLINED, size=48, color=ft.Colors.OUTLINE),
                        ft.Text("暂无文件", size=14, color=ft.Colors.OUTLINE),
                        ft.Text("点击上方按钮选择字幕文件", size=12, color=ft.Colors.OUTLINE),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.Alignment.CENTER,
                padding=PADDING_LARGE,
            )
            self.file_list_view.controls.append(empty_state)
            self.process_button.content.disabled = True
        else:
            for file_path in self.selected_files:
                try:
                    size = file_path.stat().st_size
                    size_str = format_file_size(size)
                except:
                    size_str = "未知"
                
                item = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=20, color=ft.Colors.PRIMARY),
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
                                        f"{file_path.suffix.upper()[1:]} · {size_str}",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=18,
                                tooltip="移除",
                                on_click=lambda e, p=file_path: self._remove_file(p),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=ft.padding.symmetric(horizontal=PADDING_SMALL, vertical=4),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                )
                self.file_list_view.controls.append(item)
            
            self.process_button.content.disabled = False
        
        self._page.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式变更事件。"""
        self.output_format = e.control.value
        self.config_service.set_config_value("subtitle_convert_format", self.output_format)
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变更事件。"""
        is_custom = e.control.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        self._page.update()
    
    async def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if result:
            self.custom_output_dir.value = result
            self._page.update()
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始转换。"""
        if self.is_processing or not self.selected_files:
            return
        
        self.is_processing = True
        self.process_button.content.disabled = True
        self.progress_container.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备转换..."
        self._page.update()
        
        # 在后台线程中处理
        threading.Thread(target=self._convert_thread, daemon=True).start()
    
    def _convert_thread(self) -> None:
        """转换处理线程。"""
        total = len(self.selected_files)
        success_count = 0
        fail_count = 0
        
        for i, file_path in enumerate(self.selected_files):
            try:
                self.progress_text.value = f"正在转换 ({i+1}/{total}): {file_path.name}"
                self.progress_bar.value = i / total
                self._page.update()
                
                # 解析源文件
                segments, source_format, metadata = parse_subtitle_file(str(file_path))
                
                if not segments:
                    logger.warning(f"字幕文件为空: {file_path}")
                    fail_count += 1
                    continue
                
                # 确定输出路径
                if self.output_mode_radio.value == "custom":
                    output_dir = Path(self.custom_output_dir.value)
                    output_dir.mkdir(parents=True, exist_ok=True)
                else:
                    output_dir = file_path.parent
                
                output_name = file_path.stem + '.' + self.output_format
                output_path = get_unique_path(output_dir / output_name)
                
                # 转换格式
                if self.output_format == 'srt':
                    content = segments_to_srt(segments)
                elif self.output_format == 'vtt':
                    content = segments_to_vtt(segments)
                elif self.output_format == 'lrc':
                    title = metadata.get('ti', file_path.stem)
                    artist = metadata.get('ar', '')
                    album = metadata.get('al', '')
                    content = segments_to_lrc(segments, title=title, artist=artist, album=album)
                elif self.output_format == 'ass':
                    content = segments_to_ass(segments)
                elif self.output_format == 'txt':
                    content = segments_to_txt(segments)
                else:
                    logger.error(f"不支持的输出格式: {self.output_format}")
                    fail_count += 1
                    continue
                
                # 保存文件
                with open(output_path, 'w', encoding='utf-8-sig') as f:
                    f.write(content)
                
                logger.info(f"转换成功: {file_path.name} -> {output_path.name}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"转换失败 {file_path.name}: {e}")
                fail_count += 1
        
        # 完成
        self.progress_bar.value = 1.0
        
        if fail_count == 0:
            self.progress_text.value = f"✓ 成功转换 {success_count} 个文件"
        else:
            self.progress_text.value = f"完成：成功 {success_count} 个，失败 {fail_count} 个"
        
        self.is_processing = False
        self.process_button.content.disabled = False
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。
        
        Args:
            files: 文件路径列表
        """
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
            self._show_snackbar("字幕格式转换不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def _show_snackbar(self, message: str, color: str = None) -> None:
        """显示提示消息。
        
        Args:
            message: 提示消息
            color: 颜色
        """
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE if color else None),
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
        self.on_back = None
        self.content = None
        gc.collect()
