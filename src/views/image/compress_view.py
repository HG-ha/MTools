"""图片压缩视图模块。

提供图片压缩功能的用户界面。
"""

from pathlib import Path
from typing import List, Optional, Dict

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
from services import ConfigService, ImageService
from utils import format_file_size, GifUtils


class ImageCompressView(ft.Container):
    """图片压缩视图类。
    
    提供图片压缩功能，包括：
    - 单文件和批量压缩
    - 压缩模式选择
    - 质量调整
    - 实时预览
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[callable] = None
    ) -> None:
        """初始化图片压缩视图。
        
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
        self.on_back: Optional[callable] = on_back
        
        self.selected_files: List[Path] = []
        # GIF 文件集合
        self.gif_files: set = set()
        
        self.expand: bool = True
        # 右侧多留一些空间给滚动条
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,  # 右侧多留16px给滚动条
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
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
                ft.Text("图片压缩", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 文件选择区域
        self.file_list_view = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        file_select_area = ft.Column(
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
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=TEXT_SECONDARY),
                            ft.Text(
                                "支持格式: JPG, PNG, WebP, GIF, TIFF, BMP, ICO, AVIF, HEIC 等",
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
                    height=380,  # 文件列表高度
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # 让子元素水平拉伸填充
        )
        
        # 压缩选项
        self.mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="fast", label="快速模式 (Pillow)"),
                    ft.Radio(value="balanced", label="标准模式 (mozjpeg/pngquant) - 推荐"),
                    ft.Radio(value="max", label="极限模式 (最高压缩率)"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="balanced",
        )
        
        self.quality_slider = ft.Slider(
            min=50,
            max=100,
            value=85,
            divisions=50,
            label="{value}",
            on_change=self._on_quality_change,
        )
        
        self.quality_text = ft.Text("质量: 85", size=14)
        
        self.compress_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("压缩模式:", size=14, weight=ft.FontWeight.W_500),
                    self.mode_radio,
                    ft.Container(height=PADDING_MEDIUM),
                    self.quality_text,
                    self.quality_slider,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            expand=1,  # 平分宽度
            height=280,  # 固定高度
        )
        
        # 输出选项
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="overwrite", label="覆盖原文件"),
                    ft.Radio(value="new", label="保存为新文件（自定义后缀）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        
        # 文件后缀输入框
        self.file_suffix = ft.TextField(
            label="文件后缀",
            value="_compressed",
            hint_text="例如: _compressed, _optimized, _small",
            disabled=False,
            width=300,
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
            on_click=self._on_browse_output,
            disabled=True,
        )
        
        self.output_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项:", size=14, weight=ft.FontWeight.W_500),
                    self.output_mode_radio,
                    self.file_suffix,
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
            expand=1,  # 平分宽度
            height=280,  # 固定高度
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=TEXT_SECONDARY)
        
        # 底部按钮 - 大号主按钮
        self.compress_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.COMPRESS, size=24),
                        ft.Text("开始压缩", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_compress,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.alignment.center,
        )
        
        # 主内容 - 隐藏滚动条
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                file_select_area,
                ft.Row(
                    controls=[
                        self.compress_options,
                        self.output_options,
                    ],
                    spacing=PADDING_LARGE,
                ),
                self.progress_bar,
                self.progress_text,
                self.compress_button,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.HIDDEN,  # 隐藏滚动条，但仍可滚动
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
        
        # 初始化文件列表（显示空状态）- 直接添加控件，不调用update
        self._init_empty_state()
    
    def _init_empty_state(self) -> None:
        """初始化空状态显示（不调用update）。"""
        self.file_list_view.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=TEXT_SECONDARY),
                        ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                        ft.Text("点击此处选择图片", color=TEXT_SECONDARY, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,  # 垂直居中
                    spacing=PADDING_MEDIUM // 2,
                ),
                height=332,  # 380 - 2*24(padding) = 332
                alignment=ft.alignment.center,
                on_click=self._on_empty_area_click,
                ink=True,  # 添加水波纹效果
            )
        )
    
    def _on_empty_area_click(self, e: ft.ControlEvent) -> None:
        """点击空白区域，触发选择文件。"""
        self._on_select_files(e)
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.files:
                # 追加新文件，而不是替换
                new_files = [Path(f.path) for f in result.files]
                for new_file in new_files:
                    # 避免重复添加
                    if new_file not in self.selected_files:
                        self.selected_files.append(new_file)
                self._update_file_list()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "jfif", "png", "webp", "bmp", "gif", "tiff", "tif", "ico", "avif", "heic", "heif"],
            allow_multiple=True,
        )
    
    def _on_select_folder(self, e: ft.ControlEvent) -> None:
        """选择文件夹按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                folder = Path(result.path)
                # 获取文件夹中的所有图片
                extensions = [".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".ico", ".avif", ".heic", ".heif"]
                self.selected_files = []
                for ext in extensions:
                    self.selected_files.extend(folder.glob(f"*{ext}"))
                    self.selected_files.extend(folder.glob(f"*{ext.upper()}"))
                self._update_file_list()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择图片文件夹")
    
    def _update_file_list(self) -> None:
        """更新文件列表显示。"""
        self.file_list_view.controls.clear()
        self.gif_files.clear()  # 清除 GIF 文件记录
        
        if not self.selected_files:
            # 空状态 - 使用和文件列表相同的Container结构，确保宽度一致
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=TEXT_SECONDARY),
                            ft.Text("未选择文件", color=TEXT_SECONDARY, size=14),
                            ft.Text("点击此处选择图片", color=TEXT_SECONDARY, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,  # 垂直居中
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=332,  # 380 - 2*24(padding) = 332
                    alignment=ft.alignment.center,
                    on_click=self._on_empty_area_click,
                    ink=True,  # 添加水波纹效果
                )
            )
        else:
            for idx, file_path in enumerate(self.selected_files):
                # 获取文件信息
                file_size = file_path.stat().st_size
                size_str = format_file_size(file_size)
                
                # 获取图片信息
                img_info = self.image_service.get_image_info(file_path)
                
                # 构建详细信息
                if 'error' not in img_info:
                    format_str = img_info.get('format', '未知')
                    width = img_info.get('width', 0)
                    height = img_info.get('height', 0)
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
                                        color=TEXT_SECONDARY,
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
                                                ft.Icon(ft.Icons.PHOTO_SIZE_SELECT_ACTUAL, size=12, color=TEXT_SECONDARY),
                                                ft.Text(dimension_str, size=11, color=TEXT_SECONDARY),
                                                ft.Text("•", size=11, color=TEXT_SECONDARY),
                                                ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=TEXT_SECONDARY),
                                                ft.Text(size_str, size=11, color=TEXT_SECONDARY),
                                                ft.Text("•", size=11, color=TEXT_SECONDARY),
                                                ft.Text(format_str, size=11, color=TEXT_SECONDARY),
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
        """移除单个文件。
        
        Args:
            index: 文件索引
        """
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()
    
    def _on_clear_files(self, e: ft.ControlEvent) -> None:
        """清空文件列表。"""
        self.selected_files.clear()
        self._update_file_list()
    
    def _on_quality_change(self, e: ft.ControlEvent) -> None:
        """质量滑块变化事件。"""
        quality = int(e.control.value)
        self.quality_text.value = f"质量: {quality}"
        self.quality_text.update()
    
    def _on_output_mode_change(self, e: ft.ControlEvent) -> None:
        """输出模式变化事件。"""
        mode = e.control.value
        is_custom = mode == "custom"
        is_new = mode == "new"
        
        self.file_suffix.disabled = not is_new
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom
        
        self.file_suffix.update()
        self.custom_output_dir.update()
        self.browse_output_button.update()
    
    def _on_browse_output(self, e: ft.ControlEvent) -> None:
        """浏览输出目录按钮点击事件。"""
        def on_result(result: ft.FilePickerResultEvent) -> None:
            if result.path:
                self.custom_output_dir.value = result.path
                self.custom_output_dir.update()
        
        picker = ft.FilePicker(on_result=on_result)
        self.page.overlay.append(picker)
        self.page.update()
        picker.get_directory_path(dialog_title="选择输出目录")
    
    def _on_compress(self, e: ft.ControlEvent) -> None:
        """开始压缩按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择要压缩的图片", ft.Colors.ORANGE)
            return
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备压缩..."
        self.progress_bar.update()
        self.progress_text.update()
        
        # 获取参数
        mode = self.mode_radio.value
        quality = int(self.quality_slider.value)
        output_mode = self.output_mode_radio.value
        
        # 压缩文件
        total = len(self.selected_files)
        success_count = 0
        total_original = 0
        total_compressed = 0
        
        skipped_gifs = 0
        for i, input_path in enumerate(self.selected_files):
            # 更新进度
            self.progress_text.value = f"正在压缩 ({i+1}/{total}): {input_path.name}"
            self.progress_bar.value = (i + 1) / total
            self.progress_text.update()
            self.progress_bar.update()
            
            # 检查是否为 GIF，跳过
            if GifUtils.is_animated_gif(input_path):
                skipped_gifs += 1
                continue
            
            # 确定输出路径
            if output_mode == "overwrite":
                output_path = input_path
            elif output_mode == "new":
                suffix = self.file_suffix.value if self.file_suffix.value else "_compressed"
                output_path = input_path.parent / f"{input_path.stem}{suffix}{input_path.suffix}"
            else:  # custom
                output_dir = Path(self.custom_output_dir.value)
                output_path = output_dir / input_path.name
            
            # 执行压缩
            success, message = self.image_service.compress_image(
                input_path,
                output_path,
                mode=mode,
                quality=quality
            )
            
            if success:
                success_count += 1
                total_original += input_path.stat().st_size
                if output_path.exists():
                    total_compressed += output_path.stat().st_size
        
        # 显示结果
        self.progress_bar.visible = False
        self.progress_bar.update()
        
        if total_original > 0:
            total_ratio = (1 - total_compressed / total_original) * 100
            result_message = (
                f"压缩完成！\n"
                f"成功: {success_count}/{total}\n"
                f"原始大小: {format_file_size(total_original)}\n"
                f"压缩后: {format_file_size(total_compressed)}\n"
                f"减小: {total_ratio:.1f}%"
            )
            if skipped_gifs > 0:
                result_message += f"\n跳过 GIF: {skipped_gifs}个"
        else:
            result_message = f"压缩完成！成功: {success_count}/{total}"
            if skipped_gifs > 0:
                result_message += f" (跳过 GIF: {skipped_gifs}个)"
        
        self.progress_text.value = result_message
        self.progress_text.update()
        
        self._show_message("压缩完成！", ft.Colors.GREEN)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

