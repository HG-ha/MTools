# -*- coding: utf-8 -*-
"""视频修复视图模块。

提供视频文件修复功能的用户界面。
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
from services import ConfigService, FFmpegService
from utils import format_file_size, get_unique_path
from views.media.ffmpeg_install_view import FFmpegInstallView


class VideoRepairView(ft.Container):
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.ts'}
    """视频修复视图类。
    
    提供视频文件修复功能，包括：
    - 单文件和批量修复
    - 多种修复模式
    - 实时进度显示
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化视频修复视图。
        
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
        is_ffmpeg_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        if not is_ffmpeg_available:
            self.padding = ft.padding.all(0)
            self.content = FFmpegInstallView(
                self._page,
                self.ffmpeg_service,
                on_back=self._on_back_click
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
                ft.Text("视频修复", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_SMALL,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        file_select_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text("文件选择", size=18, weight=ft.FontWeight.W_600),
                            ft.Container(expand=True),
                            ft.Button(
                                "选择文件",
                                icon=ft.Icons.FILE_UPLOAD,
                                on_click=lambda _: self._page.run_task(self._on_select_files),
                                height=36,
                            ),
                            ft.Button(
                                "选择文件夹",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _: self._page.run_task(self._on_select_folder),
                                height=36,
                            ),
                            ft.OutlinedButton(
                                "清空列表",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=self._on_clear_files,
                                height=36,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持修复: 播放卡顿、无法播放、音画不同步、索引损坏等问题",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=6,
                        ),
                        margin=ft.margin.only(bottom=PADDING_SMALL),
                    ),
                    ft.Container(
                        content=self.file_list_view,
                        height=220,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.PRIMARY),
        )
        
        # 修复模式选择
        self.repair_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="auto", label="自动修复 (推荐) - 快速尝试修复"),
                    ft.Radio(value="remux", label="重新封装 - 仅修复容器，速度最快"),
                    ft.Radio(value="reencode", label="重新编码 - 可修复更多问题，速度中等"),
                    ft.Radio(value="aggressive", label="激进修复 - 尽力恢复内容，速度较慢"),
                ],
                spacing=PADDING_SMALL,
            ),
            value="auto",
        )
        
        mode_description = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, size=16, color=ft.Colors.AMBER),
                            ft.Text("修复说明:", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.AMBER),
                        ],
                        spacing=6,
                    ),
                    ft.Text(
                        "• 自动修复: 适合大多数情况\n"
                        "• 重新封装: 修复播放问题，不改变画质\n"
                        "• 重新编码: 修复画面损坏，可能损失少量质量\n"
                        "• 激进修复: 处理严重损坏的视频",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.AMBER_200),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.AMBER),
            margin=ft.margin.only(top=PADDING_MEDIUM),
        )
        
        repair_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("修复模式", size=18, weight=ft.FontWeight.W_600),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.repair_mode_radio,
                                mode_description,
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 输出选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_repaired",
            disabled=False,
            width=200,
        )
        
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_output_dir()),
            disabled=True,
            expand=True,
        )
        
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=lambda _: self._page.run_task(self._on_browse_output),
            disabled=True,
        )
        
        output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=18, weight=ft.FontWeight.W_600),
                    self.output_mode_radio,
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                self.file_suffix,
                                ft.Row(
                                    controls=[self.custom_output_dir, self.browse_output_button],
                                    spacing=PADDING_SMALL,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                        ),
                        padding=PADDING_MEDIUM,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.PRIMARY),
                    ),
                ],
                spacing=PADDING_MEDIUM,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
        # 底部按钮
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.BUILD, size=24),
                        ft.Text("开始修复", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 进度显示容器
        progress_container = ft.Container(
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
        self.progress_container = progress_container
        
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Container(height=PADDING_MEDIUM),
                repair_settings,
                ft.Container(height=PADDING_MEDIUM),
                output_options,
                ft.Container(height=PADDING_MEDIUM),
                progress_container,
                ft.Container(height=PADDING_SMALL),
                self.process_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
        )
        
        self._init_empty_state()

    def _init_empty_state(self) -> None:
        """初始化空状态显示。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEOCAM_OFF, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击此处或选择按钮添加损坏的视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=190,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._on_select_files(e),
                ink=True,
                tooltip="点击选择视频文件",
            )
        )

    async def _on_select_files(self) -> None:
        """选择文件事件处理。"""
        files = await ft.FilePicker().pick_files(
            dialog_title="选择损坏的视频文件",
            allowed_extensions=[
                "mp4", "mkv", "mov", "avi", "wmv", "flv", "webm", 
                "m4v", "3gp", "ts", "m2ts", "f4v", "asf", "rm", "rmvb"
            ],
            allow_multiple=True,
        )
        if files:
            new_files = [Path(f.path) for f in files]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
            self._update_file_list()

    async def _on_select_folder(self) -> None:
        """选择文件夹事件处理。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择视频文件夹")
        if folder_path:
            folder = Path(folder_path)
            extensions = [
                ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
                ".m4v", ".3gp", ".ts", ".m2ts", ".f4v", ".asf", ".rm", ".rmvb"
            ]
            self.selected_files.clear()
            for ext in extensions:
                self.selected_files.extend(folder.glob(f"**/*{ext}"))
                self.selected_files.extend(folder.glob(f"**/*{ext.upper()}"))
            self._update_file_list()

    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        if not self.selected_files:
            self._init_empty_state()
        else:
            for idx, file_path in enumerate(self.selected_files):
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.HEALING, size=20, color=ft.Colors.ORANGE),
                                ft.Column(
                                    controls=[
                                        ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(f"大小: {size_str}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="移除",
                                    on_click=lambda e, i=idx: self._on_remove_file(i),
                                ),
                            ],
                            spacing=PADDING_MEDIUM,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=PADDING_MEDIUM,
                    )
                )
        self.file_list_view.update()

    def _on_remove_file(self, index: int) -> None:
        """移除文件。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()

    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()

    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式改变事件。"""
        mode = e.control.value
        self.file_suffix.disabled = mode != "new"
        self.custom_output_dir.disabled = mode != "custom"
        self.browse_output_button.disabled = mode != "custom"
        self._page.update()

    async def _on_browse_output(self) -> None:
        """浏览输出目录。"""
        folder_path = await ft.FilePicker().get_directory_path(dialog_title="选择输出目录")
        if folder_path:
            self.custom_output_dir.value = folder_path
            self.custom_output_dir.update()

    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始修复视频。"""
        if not self.selected_files:
            self._show_message("请先选择要修复的视频", ft.Colors.ORANGE)
            return

        repair_mode = self.repair_mode_radio.value
        output_mode = self.output_mode_radio.value

        self.progress_container.visible = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备修复..."
        self.progress_container.update()
        self._page.update()

        def process_task():
            total = len(self.selected_files)
            success_count = 0
            failed_files = []
            
            for i, input_path in enumerate(self.selected_files):
                try:
                    # 确定输出路径
                    if output_mode == "new":
                        suffix = self.file_suffix.value or "_repaired"
                        ext = input_path.suffix
                        output_path = input_path.parent / f"{input_path.stem}{suffix}{ext}"
                    else:
                        output_dir = Path(self.custom_output_dir.value)
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_path = output_dir / input_path.name
                    
                    # 根据全局设置决定是否添加序号
                    add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                    output_path = get_unique_path(output_path, add_sequence=add_sequence)
                    
                    def progress_handler(progress, speed_str, remaining_time):
                        # 计算总体进度
                        overall_progress = (i + progress) / total
                        self.progress_bar.value = overall_progress
                        
                        # 显示详细信息
                        percent = int(progress * 100)
                        self.progress_text.value = (
                            f"正在修复 ({i+1}/{total}): {input_path.name}\n"
                            f"进度: {percent}% | 速度: {speed_str} | 预计剩余: {remaining_time}"
                        )
                        self._page.update()
                    
                    # 显示开始处理
                    self.progress_text.value = f"开始修复 ({i+1}/{total}): {input_path.name}..."
                    self._page.update()
                    
                    result, message = self.ffmpeg_service.repair_video(
                        input_path, output_path, repair_mode, progress_handler
                    )
                    
                    if result:
                        success_count += 1
                    else:
                        failed_files.append(f"{input_path.name}: {message}")
                    
                except Exception as e:
                    failed_files.append(f"{input_path.name}: {str(e)}")

            # 完成后显示结果
            self.progress_bar.visible = False
            self.progress_container.visible = False
            
            if failed_files:
                self.progress_text.value = (
                    f"修复完成！成功: {success_count}/{total}\n"
                    f"失败: {len(failed_files)} 个文件\n"
                    f"提示: 失败的文件可尝试其他修复模式"
                )
                self._show_message(f"部分文件修复失败 ({len(failed_files)}个)", ft.Colors.ORANGE)
            else:
                self.progress_text.value = f"修复完成！成功修复 {total} 个文件。"
                self._show_message("全部修复完成！", ft.Colors.GREEN)
            
            self._page.update()

        threading.Thread(target=process_task, daemon=True).start()

    def _on_back_click(self, e: Optional[ft.ControlEvent] = None) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()

    def _show_message(self, message: str, color: str) -> None:
        """显示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
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
            self._show_message(f"已添加 {added_count} 个文件", ft.Colors.GREEN)
        elif skipped_count > 0:
            self._show_message("视频修复不支持该格式", ft.Colors.ORANGE)
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
