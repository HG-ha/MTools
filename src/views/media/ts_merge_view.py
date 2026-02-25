# -*- coding: utf-8 -*-
"""TS 视频合成视图模块。

提供 TS 分片视频合并和格式转换功能。
"""

import os
import re
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
from services import ConfigService, FFmpegService
from utils import format_file_size, logger, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class TSMergeView(ft.Container):
    """TS 视频合成视图类。
    
    提供 TS 分片视频合并功能，包括：
    - 多个 .ts 文件合并
    - 自动按文件名排序
    - 输出为 MP4/MKV/TS 格式
    """
    
    SUPPORTED_EXTENSIONS = {'.ts', '.m2ts', '.mts'}
    
    OUTPUT_FORMATS = [
        ("mp4", "MP4  |  通用格式，兼容性最好"),
        ("mkv", "MKV  |  支持更多编码和字幕"),
        ("ts", "TS   |  保持原格式，无损合并"),
    ]

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化 TS 合成视图。
        
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
        
        # 输出格式
        self.output_format: str = self.config_service.get_config_value("ts_merge_format", "mp4")
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        self._build_ui()
    
    def _on_back_click(self, e: ft.ControlEvent = None) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检查 FFmpeg 是否可用
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self._page,
                self.ffmpeg_service,
                on_back=self._on_back_click,
                tool_name="TS 视频合成"
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
                ft.Text("TS 视频合成", size=28, weight=ft.FontWeight.BOLD),
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
            height=200,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
            on_click=self._on_file_list_click,
        )
        
        file_select_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择 TS 文件:", size=14, weight=ft.FontWeight.W_500),
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
                                "支持格式: TS, M2TS, MTS（文件将按名称自动排序后合并）",
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
            label="输出格式",
            width=320,
            dense=True,
            on_select=self._on_format_change,
        )
        
        # 输出文件名
        self.output_name_field: ft.TextField = ft.TextField(
            label="输出文件名（不含扩展名）",
            value="merged_video",
            dense=True,
            expand=True,
        )
        
        format_settings_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.output_format_dropdown,
                    ft.Container(height=PADDING_MEDIUM),
                    self.output_name_field,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("合并说明", size=13),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("• 文件按名称自然排序后依次合并", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• TS→MP4/MKV 使用流复制，无损转换", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• 适用于 m3u8 下载、IPTV 录制等场景", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("• 确保所有分片编码格式一致", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
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
        
        # 右侧：输出路径
        self.output_mode_radio: ft.RadioGroup = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="same", label="保存到第一个文件所在目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value="same",
            on_change=self._on_output_mode_change,
        )
        
        default_output = self.config_service.get_output_dir() / "ts_merged"
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
                    ft.Text("常见问题", size=13),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("Q: 合并后没有声音？", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("A: 可能是音频编码不兼容，尝试输出为 MKV", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Container(height=4),
                                ft.Text("Q: 合并后视频花屏？", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("A: 分片编码不一致，需确保来源相同", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ],
                            spacing=2,
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
                        ft.Icon(ft.Icons.MERGE, size=24),
                        ft.Text("开始合成", size=18, weight=ft.FontWeight.W_600),
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
        
        # 主内容区域
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
        
        self._update_file_list()
    
    def _natural_sort_key(self, path: Path) -> list:
        """自然排序键，让 file1, file2, file10 正确排序。"""
        def convert(text):
            return int(text) if text.isdigit() else text.lower()
        return [convert(c) for c in re.split(r'(\d+)', path.name)]
    
    async def _on_file_list_click(self, e: ft.ControlEvent) -> None:
        """文件列表区域点击事件。"""
        if not self.selected_files:
            await self._on_select_files(e)
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            allow_multiple=True,
            allowed_extensions=['ts', 'm2ts', 'mts'],
            dialog_title="选择 TS 文件",
        )
        if result and result.files:
            for f in result.files:
                file_path = Path(f.path)
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            # 自然排序
            self.selected_files.sort(key=self._natural_sort_key)
            self._update_file_list()
    
    async def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        result = await ft.FilePicker().get_directory_path(dialog_title="选择包含 TS 文件的文件夹")
        if result:
            folder = Path(result)
            for file_path in folder.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
            # 自然排序
            self.selected_files.sort(key=self._natural_sort_key)
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        
        if not self.selected_files:
            empty_state = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE_OUTLINED, size=48, color=ft.Colors.OUTLINE),
                        ft.Text("暂无文件", size=14, color=ft.Colors.OUTLINE),
                        ft.Text("点击上方按钮选择 TS 文件", size=12, color=ft.Colors.OUTLINE),
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
            # 计算总大小
            total_size = sum(f.stat().st_size for f in self.selected_files if f.exists())
            
            # 添加统计信息
            stats = ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(
                            f"共 {len(self.selected_files)} 个文件，总大小 {format_file_size(total_size)}",
                            size=12,
                            color=ft.Colors.PRIMARY,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.only(bottom=8),
            )
            self.file_list_view.controls.append(stats)
            
            for i, file_path in enumerate(self.selected_files):
                try:
                    size = file_path.stat().st_size
                    size_str = format_file_size(size)
                except Exception:
                    size_str = "未知"
                
                item = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(f"{i+1}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, width=24),
                            ft.Icon(ft.Icons.VIDEO_FILE_OUTLINED, size=20, color=ft.Colors.PRIMARY),
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
                                        size_str,
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
            
            self.process_button.content.disabled = len(self.selected_files) < 2
        
        self._page.update()
    
    def _remove_file(self, file_path: Path) -> None:
        """移除文件。"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()
    
    def _on_format_change(self, e: ft.ControlEvent) -> None:
        """输出格式变更事件。"""
        self.output_format = e.control.value
        self.config_service.set_config_value("ts_merge_format", self.output_format)
    
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
        """开始合成。"""
        if self.is_processing or len(self.selected_files) < 2:
            return
        
        self.is_processing = True
        self.process_button.content.disabled = True
        self.progress_container.visible = True
        self.progress_bar.value = None  # 不确定进度
        self.progress_text.value = "正在合成..."
        self._page.update()
        
        self._page.run_task(self._async_merge)
    
    async def _async_merge(self) -> None:
        """异步合成处理。"""
        import asyncio
        try:
            # 在主线程读取 UI 值
            output_mode = self.output_mode_radio.value
            output_dir_value = self.custom_output_dir.value
            output_name = self.output_name_field.value.strip() or "merged_video"
            files = list(self.selected_files)
            output_format = self.output_format
            
            if output_mode == "custom":
                output_dir = Path(output_dir_value)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = files[0].parent
            
            output_path = get_unique_path(output_dir / f"{output_name}.{output_format}")
            
            self.progress_text.value = f"正在合成 {len(files)} 个文件..."
            self._page.update()
            
            # 在后台线程执行 FFmpeg
            await asyncio.to_thread(self._merge_work, files, output_path)
            
            self.progress_bar.value = 1.0
            self.progress_text.value = f"✓ 合成完成: {output_path.name}"
            logger.info(f"TS 合成完成: {output_path}")
            
        except Exception as e:
            logger.error(f"TS 合成失败: {e}")
            self.progress_bar.value = 0
            self.progress_text.value = f"✗ 合成失败: {str(e)[:50]}"
        
        self.is_processing = False
        self.process_button.content.disabled = False
        self._page.update()
    
    def _merge_work(self, files: list, output_path: Path) -> None:
        """合成同步工作（在后台线程执行）。"""
        import tempfile
        import subprocess
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for file_path in files:
                # 使用 file 协议，转义单引号
                escaped_path = str(file_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            concat_list_path = f.name
        
        try:
            # FFmpeg 命令
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c', 'copy',  # 流复制，无损
                str(output_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg 错误: {result.stderr}")
                raise Exception(f"合成失败: {result.stderr[:200]}")
            
        finally:
            # 清理临时文件
            try:
                os.unlink(concat_list_path)
            except Exception:
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
            self.selected_files.sort(key=self._natural_sort_key)
            self._update_file_list()
            self._show_snackbar(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_snackbar("TS 合成不支持该格式", ft.Colors.ORANGE)
        
        self._page.update()
    
    def _show_snackbar(self, message: str, color: str = None) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE if color else None),
            bgcolor=color,
            duration=2000,
        )
        self._page.open(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源。"""
        import gc
        if hasattr(self, 'selected_files'):
            self.selected_files.clear()
        self.on_back = None
        self.content = None
        gc.collect()

