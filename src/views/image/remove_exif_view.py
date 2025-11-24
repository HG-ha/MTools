# -*- coding: utf-8 -*-
"""图片去除EXIF视图模块。

提供图片EXIF元数据删除功能。
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional

import flet as ft
from PIL import Image
from PIL.ExifTags import TAGS

from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from services import ConfigService, ImageService


class ImageRemoveExifView(ft.Container):
    """图片去除EXIF视图类。
    
    提供图片EXIF元数据删除功能，包括：
    - 查看EXIF信息
    - 批量删除EXIF
    - 保护隐私
    - 减小文件大小
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化图片去除EXIF视图。
        
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
        self.expand: bool = True
        
        self.selected_files: List[Path] = []
        self.current_exif_data: Dict = {}
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题栏
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("去除EXIF元数据", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 说明文字
        info_text = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "📌 什么是EXIF？",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(
                        "EXIF（可交换图像文件格式）包含拍摄时间、地理位置、相机型号等信息。\n"
                        "删除EXIF可以保护隐私，并减小文件大小。",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
            border_radius=8,
        )
        
        # 文件选择区域
        self.file_list_text = ft.Text(
            "未选择文件",
            size=14,
            color=TEXT_SECONDARY,
        )
        
        select_button = ft.ElevatedButton(
            text="选择图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_files,
        )
        
        view_exif_button = ft.OutlinedButton(
            text="查看EXIF",
            icon=ft.Icons.INFO_OUTLINE,
            on_click=self._on_view_exif,
            visible=False,
        )
        
        self.view_exif_button = view_exif_button
        
        file_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("选择图片文件", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            select_button,
                            view_exif_button,
                            self.file_list_text,
                        ],
                        spacing=PADDING_MEDIUM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # EXIF信息显示区域
        self.exif_info_text = ft.Text(
            "",
            size=12,
            selectable=True,
        )
        
        exif_info_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("EXIF信息预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.exif_info_text,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                        border_radius=8,
                        height=200,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.exif_info_section = exif_info_section
        
        # 输出设置
        self.overwrite_checkbox = ft.Checkbox(
            label="覆盖原文件",
            value=False,
        )
        
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.overwrite_checkbox,
                    ft.Text(
                        "提示：不覆盖原文件时，将创建新文件（文件名添加\"_no_exif\"后缀）",
                        size=12,
                        color=TEXT_SECONDARY,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 处理按钮
        process_button = ft.ElevatedButton(
            text="删除EXIF",
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._on_process,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED,
            ),
        )
        
        # 进度显示
        self.progress_text = ft.Text(
            "",
            size=14,
            color=TEXT_SECONDARY,
            visible=False,
        )
        
        self.progress_bar = ft.ProgressBar(
            visible=False,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                info_text,
                ft.Container(height=PADDING_MEDIUM),
                file_section,
                ft.Container(height=PADDING_MEDIUM),
                exif_info_section,
                ft.Container(height=PADDING_MEDIUM),
                output_section,
                ft.Container(height=PADDING_MEDIUM),
                process_button,
                ft.Container(height=PADDING_SMALL),
                self.progress_text,
                self.progress_bar,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装视图 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_XLARGE,
            right=PADDING_XLARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        def on_files_picked(result: ft.FilePickerResultEvent) -> None:
            if result.files and len(result.files) > 0:
                self.selected_files = [Path(f.path) for f in result.files]
                count = len(self.selected_files)
                if count == 1:
                    self.file_list_text.value = self.selected_files[0].name
                    self.view_exif_button.visible = True
                else:
                    self.file_list_text.value = f"已选择 {count} 个文件"
                    self.view_exif_button.visible = False
                
                self.file_list_text.update()
                self.view_exif_button.update()
                
                # 隐藏EXIF信息区域
                self.exif_info_section.visible = False
                self.exif_info_section.update()
        
        file_picker = ft.FilePicker(on_result=on_files_picked)
        self.page.overlay.append(file_picker)
        self.page.update()
        
        file_picker.pick_files(
            dialog_title="选择图片",
            allowed_extensions=["jpg", "jpeg", "png", "tiff", "tif"],
            allow_multiple=True,
        )
    
    def _on_view_exif(self, e: ft.ControlEvent) -> None:
        """查看EXIF按钮点击事件。"""
        if not self.selected_files or len(self.selected_files) != 1:
            return
        
        file_path = self.selected_files[0]
        
        try:
            img = Image.open(file_path)
            exif_data = img._getexif()
            
            if exif_data:
                exif_info_lines = []
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    # 转换value为字符串，处理bytes类型
                    if isinstance(value, bytes):
                        try:
                            value_str = value.decode('utf-8', errors='ignore')
                        except:
                            value_str = str(value)
                    else:
                        value_str = str(value)
                    
                    # 限制长度
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    
                    exif_info_lines.append(f"{tag_name}: {value_str}")
                
                self.exif_info_text.value = "\n".join(exif_info_lines)
                self.exif_info_section.visible = True
                self.exif_info_section.update()
                self._show_message("EXIF信息加载成功", ft.Colors.GREEN)
            else:
                self.exif_info_text.value = "此图片没有EXIF信息"
                self.exif_info_section.visible = True
                self.exif_info_section.update()
        
        except Exception as ex:
            self._show_message(f"读取EXIF失败: {str(ex)}", ft.Colors.ERROR)
    
    def _on_process(self, e: ft.ControlEvent) -> None:
        """处理按钮点击事件。"""
        if not self.selected_files:
            self._show_message("请先选择图片文件", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_text.visible = True
        self.progress_bar.visible = True
        self.progress_text.value = "准备处理..."
        self.progress_bar.value = 0
        self.page.update()
        
        try:
            success_count = 0
            total = len(self.selected_files)
            
            for idx, file_path in enumerate(self.selected_files):
                if not file_path.exists():
                    continue
                
                # 更新进度
                self.progress_text.value = f"正在删除EXIF: {file_path.name} ({idx + 1}/{total})"
                self.progress_bar.value = idx / total
                self.page.update()
                
                try:
                    # 读取图片（不包含EXIF）
                    img = Image.open(file_path)
                    
                    # 获取图片数据（不包含EXIF）
                    data = list(img.getdata())
                    image_without_exif = Image.new(img.mode, img.size)
                    image_without_exif.putdata(data)
                    
                    # 确定输出路径
                    if self.overwrite_checkbox.value:
                        output_path = file_path
                    else:
                        ext = file_path.suffix
                        output_path = file_path.parent / f"{file_path.stem}_no_exif{ext}"
                        counter = 1
                        while output_path.exists():
                            output_path = file_path.parent / f"{file_path.stem}_no_exif_{counter}{ext}"
                            counter += 1
                    
                    # 保存（不包含EXIF）
                    image_without_exif.save(output_path)
                    success_count += 1
                
                except Exception as ex:
                    print(f"处理文件 {file_path.name} 失败: {str(ex)}")
                    continue
            
            # 完成进度显示
            self.progress_text.value = "处理完成！"
            self.progress_bar.value = 1.0
            self.page.update()
            
            # 延迟隐藏进度条，让用户看到完成状态
            import time
            time.sleep(0.5)
            
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            
            self._show_message(f"处理完成！成功处理 {success_count}/{total} 个文件", ft.Colors.GREEN)
        
        except Exception as ex:
            self.progress_text.visible = False
            self.progress_bar.visible = False
            self.page.update()
            self._show_message(f"处理失败: {str(ex)}", ft.Colors.ERROR)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()

