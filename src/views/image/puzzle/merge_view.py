"""多图合并视图模块。

提供多图合并功能的用户界面。
"""

import io
import os
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Dict

import flet as ft
from PIL import Image

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils


class ImagePuzzleMergeView(ft.Container):
    """多图合并视图类。
    
    提供多图合并功能：
    - 横向排列
    - 纵向排列
    - 网格排列
    - 间距和背景色设置
    - 实时预览
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化多图合并视图。
        
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
        self.preview_image: Optional[Image.Image] = None
        self.is_processing: bool = False
        
        # GIF 文件映射：{文件路径: (是否GIF, 帧数, 选择的帧索引)}
        self.gif_info: Dict[str, tuple] = {}
        
        # 实时预览支持
        self._last_update_time: float = 0.0
        self._update_timer: Optional[threading.Timer] = None
        self._auto_preview_enabled: bool = False  # 是否启用自动预览（默认关闭以提升性能）
        
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
                ft.Text("多图合并", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 实时预览复选框（需要在 file_select_area 之前定义）
        self.auto_preview_checkbox: ft.Checkbox = ft.Checkbox(
            label="实时预览",
            value=False,
            on_change=self._on_auto_preview_toggle,
            tooltip="开启后，修改参数时将自动生成预览\n处理大图片时可能会占用较多系统性能",
        )
        
        # GIF 动画保留选项（需要在 file_select_area 之前定义）
        self.keep_gif_animation: ft.Checkbox = ft.Checkbox(
            label="保留 GIF 动画",
            value=False,
            visible=False,  # 默认隐藏，只有选择了GIF时才显示
            on_change=self._on_option_change,
        )
        
        # 左侧：文件选择区域
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
                        ft.TextButton(
                            "清空",
                            icon=ft.Icons.CLEAR_ALL,
                            on_click=self._on_clear_files,
                        ),
                        ft.Container(width=PADDING_MEDIUM),  # 间隔
                        ft.Column(
                            controls=[
                                self.auto_preview_checkbox,
                                self.keep_gif_animation,
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_SECONDARY),
                            ft.Text(
                                "至少选择2张图片进行合并",
                                size=12,
                                color=TEXT_SECONDARY,
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
                    on_click=self._on_select_files,
                    tooltip="点击选择图片",
                    ink=True,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 中间：合并选项
        self.merge_direction: ft.RadioGroup = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="horizontal", label="横向排列"),
                    ft.Radio(value="vertical", label="纵向排列"),
                    ft.Radio(value="grid", label="网格排列"),
                ],
                spacing=PADDING_MEDIUM,
            ),
            value="horizontal",
            on_change=self._on_option_change,
        )
        
        self.merge_spacing_input: ft.TextField = ft.TextField(
            label="图片间距",
            value="10",
            width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix_text="px",
            on_change=self._on_option_change,
        )
        
        self.merge_cols: ft.TextField = ft.TextField(
            label="网格列数",
            value="3",
            width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        self.merge_bg_color: ft.Dropdown = ft.Dropdown(
            label="背景色",
            value="white",
            options=[
                ft.dropdown.Option("white", "白色"),
                ft.dropdown.Option("black", "黑色"),
                ft.dropdown.Option("gray", "灰色"),
                ft.dropdown.Option("custom", "自定义..."),
            ],
            width=120,
            on_change=self._on_bg_color_change,
        )
        
        # RGB颜色输入
        self.custom_color_r: ft.TextField = ft.TextField(
            label="R",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        self.custom_color_g: ft.TextField = ft.TextField(
            label="G",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        self.custom_color_b: ft.TextField = ft.TextField(
            label="B",
            value="255",
            width=60,
            keyboard_type=ft.KeyboardType.NUMBER,
            visible=False,
            on_change=self._on_option_change,
        )
        
        # 参数区域：横向排列（单行，可横向滚动）
        options_area: ft.Column = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.merge_direction,
                        self.merge_spacing_input,
                        self.merge_cols,
                        self.merge_bg_color,
                        self.custom_color_r,
                        self.custom_color_g,
                        self.custom_color_b,
                    ],
                    spacing=PADDING_MEDIUM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    scroll=ft.ScrollMode.ADAPTIVE,
                ),
            ],
            spacing=0,
        )
        
        # 右侧：预览区域
        self.preview_image_widget: ft.Image = ft.Image(
            visible=False,
            fit=ft.ImageFit.CONTAIN,
        )
        
        self.preview_info_text: ft.Text = ft.Text(
            "选择图片后将自动生成预览",
            size=13,
            color=TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )
        
        preview_area: ft.Container = ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(
                        content=self.preview_info_text,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=self.preview_image_widget,
                        alignment=ft.alignment.center,
                    ),
                ],
            ),
            expand=1,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.SURFACE,
            on_click=self._on_preview_click,
            tooltip="点击用系统查看器打开",
        )
        
        # 上部：左右各一半显示文件列表和预览图
        top_row: ft.Row = ft.Row(
            controls=[
                ft.Container(
                    content=file_select_area,
                    expand=1,
                    height=400,
                ),
                ft.Container(
                    content=preview_area,
                    expand=1,
                    height=400,
                ),
            ],
            spacing=PADDING_LARGE,
        )
        
        # 下部：参数设置
        bottom_content: ft.Container = ft.Container(
            content=options_area,
            padding=PADDING_MEDIUM,
        )
        
        # 底部：按钮行（生成预览 + 保存结果）
        self.preview_button: ft.ElevatedButton = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.PREVIEW, size=20),
                    ft.Text("生成预览", size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=self._on_generate_preview,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )
        
        self.save_button: ft.ElevatedButton = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE, size=20),
                    ft.Text("保存结果", size=14),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=self._on_save_result,
            disabled=True,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )
        
        # 按钮行
        buttons_row: ft.Row = ft.Row(
            controls=[
                self.preview_button,
                self.save_button,
            ],
            spacing=PADDING_MEDIUM,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                ft.Container(height=PADDING_LARGE),
                top_row,
                ft.Container(height=PADDING_LARGE),
                bottom_content,
                ft.Container(height=PADDING_MEDIUM),
                buttons_row,
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
        
        # 更新文件列表
        self._update_file_list()
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _schedule_auto_preview(self) -> None:
        """安排自动预览更新（使用防抖机制）。"""
        # 取消之前的定时器
        if self._update_timer is not None:
            self._update_timer.cancel()
        
        # 设置新的定时器，延迟500ms后生成预览
        self._update_timer = threading.Timer(0.5, self._auto_generate_preview)
        self._update_timer.daemon = True
        self._update_timer.start()
    
    def _auto_generate_preview(self) -> None:
        """自动生成预览（防抖后触发）。"""
        # 模拟点击生成预览按钮，传递 is_auto=True 标记
        class FakeEvent:
            is_auto = True
        
        self._on_generate_preview(FakeEvent())
    
    def _on_auto_preview_toggle(self, e: ft.ControlEvent) -> None:
        """自动预览开关切换事件。"""
        self._auto_preview_enabled = self.auto_preview_checkbox.value
        
        # 更新提示文本
        if not self.preview_image:
            if self._auto_preview_enabled:
                self.preview_info_text.value = "选择图片后将自动生成预览"
            else:
                self.preview_info_text.value = "选择图片后，点击「生成预览」查看效果"
            try:
                self.preview_info_text.update()
            except:
                pass
        
        # 如果打开了自动预览，立即生成一次预览
        if self._auto_preview_enabled and len(self.selected_files) >= 2:
            self._schedule_auto_preview()
    
    def _on_option_change(self, e: ft.ControlEvent) -> None:
        """选项改变事件 - 支持实时预览。"""
        # 网格排列时显示列数输入
        if hasattr(e.control, 'value') and e.control == self.merge_direction:
            self.merge_cols.visible = (self.merge_direction.value == "grid")
            self.merge_cols.update()
        
        # 如果启用了自动预览且已选择足够的文件，则自动更新预览
        if self._auto_preview_enabled and len(self.selected_files) >= 2:
            self._schedule_auto_preview()
        else:
            # 清空预览（选项改变后需要重新生成）
            self._clear_preview()
    
    def _on_bg_color_change(self, e: ft.ControlEvent) -> None:
        """背景色变化事件 - 支持实时预览。"""
        is_custom = self.merge_bg_color.value == "custom"
        self.custom_color_r.visible = is_custom
        self.custom_color_g.visible = is_custom
        self.custom_color_b.visible = is_custom
        try:
            self.custom_color_r.update()
            self.custom_color_g.update()
            self.custom_color_b.update()
        except:
            pass
        
        # 如果启用了自动预览且已选择足够的文件，则自动更新预览
        if self._auto_preview_enabled and len(self.selected_files) >= 2:
            self._schedule_auto_preview()
        else:
            self._clear_preview()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件 - 支持实时预览。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                for file in result.files:
                    file_path = Path(file.path)
                    if file_path not in self.selected_files:
                        self.selected_files.append(file_path)
                
                self._update_file_list()
                
                # 如果启用了自动预览且已选择足够的文件，则自动更新预览
                if self._auto_preview_enabled and len(self.selected_files) >= 2:
                    self._schedule_auto_preview()
                else:
                    self._clear_preview()
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "bmp", "webp", "tiff", "gif"],
            allow_multiple=True,
        )
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
        self._clear_preview()
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        self.gif_info.clear()  # 清除GIF信息
        
        # 检查是否有GIF文件，用于控制"保留 GIF 动画"选项的显示
        has_gif = False
        
        if not self.selected_files:
            # 空状态提示（明确设置高度以实现居中）
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=TEXT_SECONDARY),
                            ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                            ft.Text("点击选择文件按钮或点击此处选择图片", color=TEXT_SECONDARY, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=332,  # 400(父容器高度) - 2*34(标题+提示区域高度) = 332
                    alignment=ft.alignment.center,
                    on_click=self._on_select_files,
                    tooltip="点击选择图片",
                )
            )
        else:
            for i, file_path in enumerate(self.selected_files):
                file_info = self.image_service.get_image_info(file_path)
                
                # 检测是否为GIF
                is_gif = GifUtils.is_animated_gif(file_path)
                if is_gif:
                    frame_count = GifUtils.get_frame_count(file_path)
                    self.gif_info[str(file_path)] = (True, frame_count, 0)  # 默认使用第一帧
                    has_gif = True  # 标记有GIF文件
                
                if 'error' in file_info:
                    info_text = f"错误: {file_info['error']}"
                    icon_color = ft.Colors.RED
                else:
                    size_str = format_file_size(file_info['file_size'])
                    if is_gif:
                        info_text = f"{file_info['width']}×{file_info['height']} · {size_str} · GIF({frame_count}帧)"
                        icon_color = ft.Colors.ORANGE
                    else:
                        info_text = f"{file_info['width']}×{file_info['height']} · {size_str}"
                        icon_color = ft.Colors.PRIMARY
                
                # 构建文件项布局
                if is_gif:
                    # GIF文件：双行布局
                    current_frame = self.gif_info[str(file_path)][2]
                    
                    # 第一行：文件信息
                    first_row = ft.Row(
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
                                    ft.Text(info_text, size=11, color=TEXT_SECONDARY),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    )
                    
                    # 第二行：帧选择器和操作按钮
                    second_row = ft.Row(
                        controls=[
                            ft.Container(width=28),  # 占位，对齐图标位置
                            ft.Text("选帧:", size=11, color=TEXT_SECONDARY),
                            ft.IconButton(
                                icon=ft.Icons.SKIP_PREVIOUS,
                                icon_size=14,
                                on_click=lambda e, fp=file_path: self._on_gif_prev_frame(fp),
                                tooltip="上一帧",
                            ),
                            ft.TextField(
                                value=str(current_frame + 1),
                                width=60,
                                text_align=ft.TextAlign.CENTER,
                                dense=True,
                                on_submit=lambda e, fp=file_path, fc=frame_count: self._on_gif_frame_submit(e, fp, fc),
                                on_blur=lambda e, fp=file_path, fc=frame_count: self._on_gif_frame_submit(e, fp, fc),
                            ),
                            ft.Text(f"/{frame_count}", size=11, color=TEXT_SECONDARY),
                            ft.IconButton(
                                icon=ft.Icons.SKIP_NEXT,
                                icon_size=14,
                                on_click=lambda e, fp=file_path: self._on_gif_next_frame(fp),
                                tooltip="下一帧",
                            ),
                            ft.Container(expand=True),  # 弹性空间
                            ft.IconButton(
                                icon=ft.Icons.ARROW_UPWARD,
                                icon_size=16,
                                tooltip="上移",
                                on_click=lambda e, idx=i: self._on_move_up(idx),
                                disabled=(i == 0),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ARROW_DOWNWARD,
                                icon_size=16,
                                tooltip="下移",
                                on_click=lambda e, idx=i: self._on_move_down(idx),
                                disabled=(i == len(self.selected_files) - 1),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=16,
                                tooltip="移除",
                                on_click=lambda e, idx=i: self._on_remove_file(idx),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    )
                    
                    file_item: ft.Container = ft.Container(
                        content=ft.Column(
                            controls=[first_row, second_row],
                            spacing=PADDING_SMALL,
                        ),
                        padding=PADDING_MEDIUM // 2,
                        border_radius=BORDER_RADIUS_MEDIUM,
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                    )
                else:
                    # 普通图片：单行布局
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
                                        ft.Text(info_text, size=11, color=TEXT_SECONDARY),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.ARROW_UPWARD,
                                    icon_size=16,
                                    tooltip="上移",
                                    on_click=lambda e, idx=i: self._on_move_up(idx),
                                    disabled=(i == 0),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.ARROW_DOWNWARD,
                                    icon_size=16,
                                    tooltip="下移",
                                    on_click=lambda e, idx=i: self._on_move_down(idx),
                                    disabled=(i == len(self.selected_files) - 1),
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
        
        # 根据是否有GIF文件来控制"保留 GIF 动画"选项的显示
        self.keep_gif_animation.visible = has_gif
        
        try:
            self.file_list_view.update()
            self.keep_gif_animation.update()
        except:
            pass
    
    def _on_move_up(self, index: int) -> None:
        """上移文件 - 支持实时预览。"""
        if 1 <= index < len(self.selected_files):
            self.selected_files[index], self.selected_files[index - 1] = \
                self.selected_files[index - 1], self.selected_files[index]
            self._update_file_list()
            
            # 如果启用了自动预览且已选择足够的文件，则自动更新预览
            if self._auto_preview_enabled and len(self.selected_files) >= 2:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _on_move_down(self, index: int) -> None:
        """下移文件 - 支持实时预览。"""
        if 0 <= index < len(self.selected_files) - 1:
            self.selected_files[index], self.selected_files[index + 1] = \
                self.selected_files[index + 1], self.selected_files[index]
            self._update_file_list()
            
            # 如果启用了自动预览且已选择足够的文件，则自动更新预览
            if self._auto_preview_enabled and len(self.selected_files) >= 2:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _on_remove_file(self, index: int) -> None:
        """移除文件 - 支持实时预览。"""
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
            
            # 如果启用了自动预览且已选择足够的文件，则自动更新预览
            if self._auto_preview_enabled and len(self.selected_files) >= 2:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _on_gif_prev_frame(self, file_path: Path) -> None:
        """GIF 上一帧 - 支持实时预览。"""
        key = str(file_path)
        if key in self.gif_info:
            is_gif, frame_count, current_frame = self.gif_info[key]
            new_frame = (current_frame - 1) % frame_count
            self.gif_info[key] = (is_gif, frame_count, new_frame)
            self._update_file_list()
            
            # 如果启用了自动预览且已选择足够的文件，则自动更新预览
            if self._auto_preview_enabled and len(self.selected_files) >= 2:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _on_gif_next_frame(self, file_path: Path) -> None:
        """GIF 下一帧 - 支持实时预览。"""
        key = str(file_path)
        if key in self.gif_info:
            is_gif, frame_count, current_frame = self.gif_info[key]
            new_frame = (current_frame + 1) % frame_count
            self.gif_info[key] = (is_gif, frame_count, new_frame)
            self._update_file_list()
            
            # 如果启用了自动预览且已选择足够的文件，则自动更新预览
            if self._auto_preview_enabled and len(self.selected_files) >= 2:
                self._schedule_auto_preview()
            else:
                self._clear_preview()
    
    def _on_gif_frame_submit(self, e: ft.ControlEvent, file_path: Path, frame_count: int) -> None:
        """GIF 帧输入提交 - 支持实时预览。"""
        try:
            frame_num = int(e.control.value)
            if 1 <= frame_num <= frame_count:
                key = str(file_path)
                if key in self.gif_info:
                    is_gif, _, _ = self.gif_info[key]
                    self.gif_info[key] = (is_gif, frame_count, frame_num - 1)
                    self._update_file_list()
                    
                    # 如果启用了自动预览且已选择足够的文件，则自动更新预览
                    if self._auto_preview_enabled and len(self.selected_files) >= 2:
                        self._schedule_auto_preview()
                    else:
                        self._clear_preview()
            else:
                self._show_snackbar(f"帧号必须在 1 到 {frame_count} 之间", ft.Colors.ORANGE)
                self._update_file_list()
        except ValueError:
            self._show_snackbar("请输入有效的数字", ft.Colors.ORANGE)
            self._update_file_list()
    
    def _clear_preview(self) -> None:
        """清空预览。"""
        self.preview_image = None
        self.preview_image_widget.src = None  # 清空图片源
        self.preview_image_widget.visible = False
        
        # 根据是否启用自动预览更新提示文本
        if self._auto_preview_enabled:
            self.preview_info_text.value = "选择图片后将自动生成预览"
        else:
            self.preview_info_text.value = "选择图片后，点击「生成预览」查看效果"
        
        self.preview_info_text.visible = True
        self.save_button.disabled = True
        try:
            self.preview_image_widget.update()
            self.preview_info_text.update()
            self.save_button.update()
        except:
            pass
    
    def _on_generate_preview(self, e: ft.ControlEvent) -> None:
        """生成预览 - 支持自动预览模式。"""
        # 检查是否为自动触发
        is_auto = hasattr(e, 'is_auto') and e.is_auto
        
        if self.is_processing:
            # 如果正在处理中，显示提示（特别是自动预览时）
            if is_auto:
                self.preview_info_text.value = "正在处理中，请稍候..."
                self.preview_info_text.visible = True
                try:
                    self.preview_info_text.update()
                except:
                    pass
            return
        
        if len(self.selected_files) < 2:
            if not is_auto:  # 只在手动预览时显示提示
                self._show_snackbar("至少需要2张图片", ft.Colors.ORANGE)
            return
        
        direction = self.merge_direction.value
        spacing = int(self.merge_spacing_input.value or 10)
        bg_color = self.merge_bg_color.value
        
        # 获取自定义RGB值
        custom_rgb = None
        if bg_color == "custom":
            r = int(self.custom_color_r.value or 255)
            g = int(self.custom_color_g.value or 255)
            b = int(self.custom_color_b.value or 255)
            r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
            custom_rgb = (r, g, b)
        
        try:
            grid_cols = int(self.merge_cols.value or 3) if direction == "grid" else None
            if grid_cols and (grid_cols < 1 or grid_cols > 10):
                self._show_snackbar("网格列数必须在1-10之间", ft.Colors.RED)
                return
        except ValueError:
            self._show_snackbar("请输入有效的网格列数", ft.Colors.RED)
            return
        
        self.is_processing = True
        
        # 隐藏预览图，显示处理中提示
        self.preview_image_widget.visible = False
        self.preview_info_text.value = "正在生成预览..."
        self.preview_info_text.visible = True
        
        try:
            self.page.update()
        except:
            pass
        
        def process_task():
            try:
                # 检查是否保留GIF动画
                keep_animation = self.keep_gif_animation.value
                
                if keep_animation and self.gif_info:
                    # 获取总帧数（以最长的GIF为准）
                    max_frames = max(info[1] for info in self.gif_info.values())
                    if not is_auto:  # 只在手动预览时显示提示
                        self._show_snackbar(f"正在生成 GIF 动画 ({max_frames} 帧)...", ft.Colors.BLUE)
                    
                    # 生成GIF动画
                    result_frames, duration = self._merge_as_gif(direction, spacing, grid_cols, bg_color, custom_rgb)
                    if result_frames:
                        # 将 GIF 帧列表传递给预览，以显示动态 GIF
                        self._update_preview_gif(result_frames, duration)
                        # 保存完整GIF供后续保存使用
                        self.preview_image = result_frames  # 保存为帧列表
                        if not is_auto:  # 只在手动预览时显示提示
                            self._show_snackbar(f"预览生成成功 (GIF动画, {len(result_frames)}帧)", ft.Colors.GREEN)
                    else:
                        raise Exception("生成GIF动画失败")
                else:
                    # 读取所有图片（GIF使用选择的帧）
                    images = []
                    for f in self.selected_files:
                        if str(f) in self.gif_info:
                            # 是GIF，提取选择的帧
                            _, _, frame_idx = self.gif_info[str(f)]
                            frame = GifUtils.extract_frame(f, frame_idx)
                            if frame:
                                images.append(frame)
                            else:
                                raise Exception(f"无法提取GIF帧: {f.name}")
                        else:
                            # 普通图片
                            images.append(Image.open(f))
                    
                    # 合并图片
                    result = self._merge_images(images, direction, spacing, grid_cols, bg_color, custom_rgb)
                    
                    # 更新预览
                    self._update_preview(result)
                    if not is_auto:  # 只在手动预览时显示提示
                        self._show_snackbar("预览生成成功", ft.Colors.GREEN)
            except Exception as ex:
                if not is_auto:  # 只在手动预览时显示错误提示
                    self._show_snackbar(f"生成预览失败: {ex}", ft.Colors.RED)
                self._clear_preview()
            finally:
                self.is_processing = False
        
        threading.Thread(target=process_task, daemon=True).start()
    
    def _merge_images(
        self,
        images: List[Image.Image],
        direction: str,
        spacing: int,
        grid_cols: Optional[int] = None,
        bg_color: str = "white",
        custom_rgb: tuple = None
    ) -> Image.Image:
        """合并多张图片。"""
        if not images:
            raise ValueError("没有图片可合并")
        
        # 确定背景色
        if bg_color == "custom" and custom_rgb:
            bg_rgb = custom_rgb
        else:
            bg_color_map = {
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "gray": (128, 128, 128),
            }
            bg_rgb = bg_color_map.get(bg_color, (255, 255, 255))
        
        if direction == "horizontal":
            # 横向排列：统一高度，宽度按比例缩放
            max_height = max(img.height for img in images)
            
            # 缩放所有图片到统一高度
            resized_images = []
            for img in images:
                if img.height != max_height:
                    aspect_ratio = img.width / img.height
                    new_width = int(max_height * aspect_ratio)
                    img = img.resize((new_width, max_height), Image.Resampling.LANCZOS)
                resized_images.append(img)
            
            total_width = sum(img.width for img in resized_images) + spacing * (len(resized_images) - 1)
            
            result = Image.new('RGB', (total_width, max_height), bg_rgb)
            x_offset = 0
            
            for img in resized_images:
                result.paste(img, (x_offset, 0))
                x_offset += img.width + spacing
        
        elif direction == "vertical":
            # 纵向排列：统一宽度，高度按比例缩放
            max_width = max(img.width for img in images)
            
            # 缩放所有图片到统一宽度
            resized_images = []
            for img in images:
                if img.width != max_width:
                    aspect_ratio = img.height / img.width
                    new_height = int(max_width * aspect_ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                resized_images.append(img)
            
            total_height = sum(img.height for img in resized_images) + spacing * (len(resized_images) - 1)
            
            result = Image.new('RGB', (max_width, total_height), bg_rgb)
            y_offset = 0
            
            for img in resized_images:
                result.paste(img, (0, y_offset))
                y_offset += img.height + spacing
        
        else:  # grid
            # 网格排列：统一所有图片到最大尺寸
            cols = grid_cols or 3
            rows = (len(images) + cols - 1) // cols
            
            max_width = max(img.width for img in images)
            max_height = max(img.height for img in images)
            
            # 缩放所有图片到统一尺寸（保持比例，填充背景）
            resized_images = []
            for img in images:
                if img.width != max_width or img.height != max_height:
                    # 计算缩放比例（保持比例，填充整个区域）
                    scale_w = max_width / img.width
                    scale_h = max_height / img.height
                    scale = max(scale_w, scale_h)  # 使用较大的缩放比例，确保填充整个区域
                    
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # 居中裁剪到目标尺寸
                    left = (new_width - max_width) // 2
                    top = (new_height - max_height) // 2
                    img_resized = img_resized.crop((left, top, left + max_width, top + max_height))
                    resized_images.append(img_resized)
                else:
                    resized_images.append(img)
            
            total_width = max_width * cols + spacing * (cols - 1)
            total_height = max_height * rows + spacing * (rows - 1)
            
            result = Image.new('RGB', (total_width, total_height), bg_rgb)
            
            for i, img in enumerate(resized_images):
                row = i // cols
                col = i % cols
                x = col * (max_width + spacing)
                y = row * (max_height + spacing)
                result.paste(img, (x, y))
        
        return result
    
    def _merge_as_gif(
        self,
        direction: str,
        spacing: int,
        grid_cols: Optional[int] = None,
        bg_color: str = "white",
        custom_rgb: tuple = None
    ) -> tuple:
        """生成 GIF 动画合并结果。
        
        Returns:
            (帧列表, 持续时间)
        """
        # 收集所有文件的信息
        file_info_list = []
        max_frames = 1
        
        for f in self.selected_files:
            if str(f) in self.gif_info:
                is_gif, frame_count, selected_frame = self.gif_info[str(f)]
                file_info_list.append((f, True, frame_count, selected_frame))
                max_frames = max(max_frames, frame_count)
            else:
                file_info_list.append((f, False, 1, 0))
        
        # 生成每一帧
        result_frames = []
        duration = 100  # 默认100ms每帧
        
        for frame_idx in range(max_frames):
            # 为当前帧收集每个文件的图片
            images = []
            for file_path, is_gif, frame_count, selected_frame in file_info_list:
                if is_gif:
                    # GIF文件：循环使用帧
                    actual_frame_idx = frame_idx % frame_count
                    frame = GifUtils.extract_frame(file_path, actual_frame_idx)
                    if frame:
                        images.append(frame)
                    else:
                        raise Exception(f"无法提取GIF帧: {file_path.name}")
                else:
                    # 静态图片：每帧都用同一张
                    images.append(Image.open(file_path))
            
            # 合并当前帧
            merged_frame = self._merge_images(images, direction, spacing, grid_cols, bg_color, custom_rgb)
            result_frames.append(merged_frame)
        
        return result_frames, duration
    
    def _update_preview(self, image: Image.Image) -> None:
        """更新预览图片（静态图片）。"""
        self.preview_image = image
        
        # 保存临时预览图片，使用时间戳避免缓存
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳作为文件名，避免 Flet 缓存
        timestamp = int(time.time() * 1000)
        preview_path = temp_dir / f"merge_preview_{timestamp}.png"
        
        # 保存新图片
        image.save(str(preview_path))
        
        # 清理旧的预览文件（保留最新的）
        try:
            for old_file in temp_dir.glob("merge_preview_*.*"):
                if old_file != preview_path:
                    try:
                        old_file.unlink()
                    except:
                        pass
        except:
            pass
        
        # 直接使用文件路径显示
        self.preview_image_widget.src = str(preview_path)
        self.preview_image_widget.visible = True
        self.preview_info_text.visible = False
        self.save_button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
    
    def _update_preview_gif(self, frames: list, duration: int) -> None:
        """更新预览图片（GIF 动画）。"""
        self.preview_image = frames
        
        # 保存临时预览 GIF，使用时间戳避免缓存
        temp_dir = Path("storage/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用时间戳作为文件名，避免 Flet 缓存
        timestamp = int(time.time() * 1000)
        preview_path = temp_dir / f"merge_preview_{timestamp}.gif"
        
        # GIF 不支持半透明！转换为 RGB
        rgb_frames = []
        for frame in frames:
            if frame.mode == 'RGBA':
                # 创建白色背景并合成
                rgb_frame = Image.new('RGB', frame.size, (255, 255, 255))
                rgb_frame.paste(frame, mask=frame.split()[3])
                rgb_frames.append(rgb_frame)
            elif frame.mode != 'RGB':
                rgb_frames.append(frame.convert('RGB'))
            else:
                rgb_frames.append(frame)
        
        # 保存为 GIF 动画
        if rgb_frames:
            rgb_frames[0].save(
                str(preview_path),
                save_all=True,
                append_images=rgb_frames[1:],
                duration=duration,
                loop=0,
                optimize=False,
            )
        
        # 清理旧的预览文件（保留最新的）
        try:
            for old_file in temp_dir.glob("merge_preview_*.*"):
                if old_file != preview_path:
                    try:
                        old_file.unlink()
                    except:
                        pass
        except:
            pass
        
        # 直接使用文件路径显示
        self.preview_image_widget.src = str(preview_path)
        self.preview_image_widget.visible = True
        self.preview_info_text.visible = False
        self.save_button.disabled = False
        
        try:
            self.page.update()
        except:
            pass
    
    def _on_save_result(self, e: ft.ControlEvent) -> None:
        """保存结果。"""
        if not self.preview_image:
            self._show_snackbar("没有可保存的预览图片", ft.Colors.ORANGE)
            return
        
        # 检查是否是GIF动画（帧列表）
        is_gif_animation = isinstance(self.preview_image, list)
        
        # 生成默认文件名
        if is_gif_animation:
            default_filename = "merge_result.gif"
            allowed_extensions = ["gif"]
        else:
            default_filename = "merge_result.png"
            allowed_extensions = ["png", "jpg", "jpeg", "jfif"]
        
        if self.selected_files and len(self.selected_files) > 0:
            first_file = self.selected_files[0]
            original_stem = first_file.stem
            if is_gif_animation:
                default_filename = f"{original_stem}_merge.gif"
            else:
                default_filename = f"{original_stem}_merge.png"
        
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                try:
                    output_path = Path(result.path)
                    
                    # 确保有扩展名
                    if not output_path.suffix:
                        if is_gif_animation:
                            output_path = output_path.with_suffix('.gif')
                        else:
                            output_path = output_path.with_suffix('.png')
                    
                    # 保存图片或GIF
                    if is_gif_animation:
                        # 保存为GIF动画 - 重新生成
                        self._save_merged_gif(output_path)
                    else:
                        # 保存静态图片 - 重新生成
                        self._save_merged_image(output_path)
                except Exception as ex:
                    self._show_snackbar(f"保存失败: {ex}", ft.Colors.RED)
        
        picker: ft.FilePicker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        
        picker.save_file(
            dialog_title="保存合并结果",
            file_name=default_filename,
            allowed_extensions=allowed_extensions,
        )
    
    def _save_merged_image(self, output_path: Path) -> None:
        """保存合并后的静态图片 - 重新生成以确保使用最新参数。"""
        if not self.selected_files:
            return
        
        try:
            # 获取合并参数
            direction = self.merge_direction.value
            spacing = int(self.merge_spacing_input.value or 10)
            grid_cols = int(self.merge_cols.value or 3) if direction == "grid" else None
            bg_color = self.merge_bg_color.value
            
            # 获取自定义RGB值
            custom_rgb = None
            if bg_color == "custom":
                r = int(self.custom_color_r.value or 255)
                g = int(self.custom_color_g.value or 255)
                b = int(self.custom_color_b.value or 255)
                r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                custom_rgb = (r, g, b)
            
            # 读取所有选中的图片
            images = []
            for file_path in self.selected_files:
                # 如果是 GIF，提取选定的帧
                if str(file_path) in self.gif_info:
                    _, _, selected_frame = self.gif_info[str(file_path)]
                    img = GifUtils.extract_frame(file_path, selected_frame)
                    if img:
                        images.append(img)
                else:
                    img = Image.open(file_path)
                    images.append(img)
            
            # 合并图片
            result = self._merge_images(images, direction, spacing, grid_cols, bg_color, custom_rgb)
            
            # 保存图片 - 使用与预览相同的方式
            if result.mode == 'RGBA' and output_path.suffix.lower() in ['.jpg', '.jpeg']:
                # RGBA 转 JPG：创建白色背景并合成
                rgb_image = Image.new('RGB', result.size, (255, 255, 255))
                rgb_image.paste(result, mask=result.split()[3])
                rgb_image.save(output_path, quality=95)
            elif output_path.suffix.lower() in ['.jpg', '.jpeg']:
                # RGB 保存为 JPG
                result.save(output_path, quality=95)
            else:
                # PNG 格式 - 完全保留透明度信息
                result.save(output_path)
            
            self._show_snackbar(f"保存成功: {output_path.name}", ft.Colors.GREEN)
            
        except Exception as e:
            self._show_snackbar(f"保存失败: {e}", ft.Colors.RED)
    
    def _save_merged_gif(self, output_path: Path) -> None:
        """保存合并后的 GIF 动画 - 重新生成以确保使用最新参数。"""
        if not self.selected_files:
            return
        
        try:
            # 获取合并参数
            direction = self.merge_direction.value
            spacing = int(self.merge_spacing_input.value or 10)
            grid_cols = int(self.merge_cols.value or 3) if direction == "grid" else None
            bg_color = self.merge_bg_color.value
            
            # 获取自定义RGB值
            custom_rgb = None
            if bg_color == "custom":
                r = int(self.custom_color_r.value or 255)
                g = int(self.custom_color_g.value or 255)
                b = int(self.custom_color_b.value or 255)
                r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
                custom_rgb = (r, g, b)
            
            # 显示处理进度
            if self.gif_info:
                max_frames = max(info[1] for info in self.gif_info.values())
                self._show_snackbar(f"正在保存 GIF ({max_frames} 帧)...", ft.Colors.BLUE)
            
            # 重新生成 GIF 帧
            result_frames, duration = self._merge_as_gif(direction, spacing, grid_cols, bg_color, custom_rgb)
            
            # GIF 不支持半透明！如果结果是 RGBA，需要转换为 RGB
            rgb_frames = []
            for frame in result_frames:
                if frame.mode == 'RGBA':
                    # 创建白色背景并合成
                    rgb_frame = Image.new('RGB', frame.size, (255, 255, 255))
                    rgb_frame.paste(frame, mask=frame.split()[3])
                    rgb_frames.append(rgb_frame)
                elif frame.mode != 'RGB':
                    rgb_frames.append(frame.convert('RGB'))
                else:
                    rgb_frames.append(frame)
            
            # 保存为GIF动画
            if rgb_frames:
                rgb_frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=rgb_frames[1:],
                    duration=duration,
                    loop=0,
                    optimize=False,
                )
                self._show_snackbar(f"保存成功: {output_path.name} ({len(rgb_frames)}帧)", ft.Colors.GREEN)
            else:
                raise Exception("没有生成任何帧")
                
        except Exception as e:
            self._show_snackbar(f"保存 GIF 失败: {e}", ft.Colors.RED)
    
    def _on_preview_click(self, e: ft.ControlEvent) -> None:
        """点击预览图片，用系统查看器打开。"""
        if not self.preview_image:
            return
        
        try:
            import tempfile
            import subprocess
            import platform
            
            # 检查是否为 GIF 动画（帧列表）
            is_gif_animation = isinstance(self.preview_image, list)
            
            if is_gif_animation:
                # 创建临时 GIF 文件
                with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    
                    # 转换帧为 RGB
                    rgb_frames = []
                    for frame in self.preview_image:
                        if frame.mode == 'RGBA':
                            rgb_frame = Image.new('RGB', frame.size, (255, 255, 255))
                            rgb_frame.paste(frame, mask=frame.split()[3])
                            rgb_frames.append(rgb_frame)
                        elif frame.mode != 'RGB':
                            rgb_frames.append(frame.convert('RGB'))
                        else:
                            rgb_frames.append(frame)
                    
                    # 保存为 GIF
                    if rgb_frames:
                        rgb_frames[0].save(
                            tmp_path,
                            save_all=True,
                            append_images=rgb_frames[1:],
                            duration=100,
                            loop=0,
                            optimize=False,
                        )
            else:
                # 创建临时 PNG 文件
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    self.preview_image.save(tmp_path, 'PNG')
            
            # 用系统默认程序打开
            system = platform.system()
            if system == "Windows":
                os.startfile(tmp_path)
            elif system == "Darwin":  # macOS
                subprocess.run(['open', tmp_path])
            else:  # Linux
                subprocess.run(['xdg-open', tmp_path])
        except Exception as ex:
            self._show_snackbar(f"打开图片失败: {ex}", ft.Colors.RED)
    
    def _show_snackbar(self, message: str, color: str) -> None:
        """显示提示消息。"""
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

