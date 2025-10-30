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
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from models import GifAdjustmentOptions
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils


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

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化 GIF 调整视图。
        
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
        
        self.selected_file: Optional[Path] = None
        self.frame_count: int = 0
        self.original_durations: list = []
        self.original_loop: int = 0
        
        self.expand: bool = True
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
                ft.Text("GIF 调整工具", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_info_text: ft.Text = ft.Text(
            "未选择文件",
            size=13,
            color=TEXT_SECONDARY,
        )
        
        file_select_row: ft.Row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "选择 GIF 文件",
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
                    ft.Icon(ft.Icons.GIF_BOX_OUTLINED, size=80, color=TEXT_SECONDARY),
                    ft.Text("点击选择 GIF 文件", size=16, weight=ft.FontWeight.W_500, color=TEXT_PRIMARY),
                    ft.Text("支持调整首帧、速度、循环等", size=12, color=TEXT_SECONDARY),
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
        
        cover_frame_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("封面设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Text("设置未播放时显示的默认帧", size=12, color=TEXT_SECONDARY),
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
                    ft.Text("调整 GIF 播放速度 (0.25x - 4.0x)", size=12, color=TEXT_SECONDARY),
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
                    ft.Text("设置 GIF 循环播放次数", size=12, color=TEXT_SECONDARY),
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
                    ft.Text("截取指定范围的帧（包含起始和结束帧）", size=12, color=TEXT_SECONDARY),
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
                    ft.Text("减少帧数以降低文件大小", size=12, color=TEXT_SECONDARY),
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
        
        output_section: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=14, weight=ft.FontWeight.W_500),
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
        self.progress_text: ft.Text = ft.Text("", size=12, color=TEXT_SECONDARY, visible=False)
        
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
                        ft.Text("开始调整 GIF", size=18, weight=ft.FontWeight.W_600),
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
                if file_path.suffix.lower() == '.gif':
                    self._load_gif_file(file_path)
                else:
                    self._show_snackbar("请选择 GIF 格式文件", ft.Colors.ORANGE)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择 GIF 文件",
            allowed_extensions=["gif"],
            allow_multiple=False,
        )
    
    def _load_gif_file(self, file_path: Path) -> None:
        """加载 GIF 文件。
        
        Args:
            file_path: GIF 文件路径
        """
        self.selected_file = file_path
        
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
    
    def _on_cover_frame_change(self, e: ft.ControlEvent) -> None:
        """首帧滑块变化事件。
        
        Args:
            e: 控件事件对象
        """
        frame_index = int(self.cover_frame_slider.value)
        self.cover_frame_text.value = f"首帧: 第 {frame_index + 1} 帧"
        self.cover_frame_text.update()
    
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
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.save_file(
            dialog_title="保存 GIF 文件",
            file_name=f"{self.selected_file.stem}_adjusted.gif" if self.selected_file else "output.gif",
            allowed_extensions=["gif"],
        )
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """开始处理按钮点击事件。
        
        Args:
            e: 控件事件对象
        """
        if not self.selected_file:
            self._show_snackbar("请先选择 GIF 文件", ft.Colors.ORANGE)
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
        
        # 确定输出路径
        if self.output_mode_radio.value == "custom":
            if not self.custom_output_field.value:
                self._show_snackbar("请指定输出路径", ft.Colors.ORANGE)
                return
            output_path = Path(self.custom_output_field.value)
        else:
            output_path = self.selected_file.parent / f"{self.selected_file.stem}_adjusted.gif"
        
        # 禁用按钮并显示进度
        button = self.process_button.content
        button.disabled = True
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_bar.value = None  # 不确定进度
        self.progress_text.value = "正在处理 GIF..."
        
        try:
            self.page.update()
        except:
            pass
        
        # 在后台线程处理
        def process_task():
            success, message = self.image_service.adjust_gif(
                self.selected_file,
                output_path,
                options
            )
            self._on_process_complete(success, message, output_path)
        
        threading.Thread(target=process_task, daemon=True).start()
    
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

