# -*- coding: utf-8 -*-
"""文件转URL视图模块。

提供文件上传并生成分享URL功能的用户界面，支持两种存储方式：
1. catbox.moe - 永久存储，最大200MB
2. litterbox.catbox.moe - 临时存储(1h/12h/24h/72h)，最大1GB

注意：不支持上传 .exe、.scr、.cpl、.doc*、.jar 文件
"""

import httpx
from pathlib import Path
from typing import List, Optional, Literal

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from utils import format_file_size, logger


# 禁止上传的文件扩展名
FORBIDDEN_EXTENSIONS = {'.exe', '.scr', '.cpl', '.jar', '.doc', '.docx', '.docm', '.dotx', '.dotm'}

# 存储类型
StorageType = Literal["permanent", "temporary"]

# 临时存储时长选项
TEMP_DURATIONS = ["1h", "12h", "24h", "72h"]


class FileToUrlView(ft.Container):
    """文件转URL视图类。
    
    提供文件上传并生成分享URL功能，包括：
    - 支持任意文件类型上传（除禁止类型外）
    - 支持批量上传
    - 永久存储：最大200MB
    - 临时存储：最大1GB，支持1h/12h/24h/72h
    - 一键复制生成的URL
    
    注意：不可用于商业服务
    """

    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[callable] = None
    ) -> None:
        """初始化文件转URL视图。
        
        Args:
            page: Flet页面对象
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.on_back: Optional[callable] = on_back
        
        self.selected_files: List[Path] = []
        self.upload_results: List[dict] = []  # 存储上传结果
        self.is_uploading: bool = False  # 上传状态标志
        
        # 存储选项
        self.storage_type: StorageType = "permanent"  # 默认永久存储
        self.temp_duration: str = "24h"  # 默认24小时
        
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
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("文件转URL", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 说明文本
        info_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=24, color=ft.Colors.BLUE),
                            ft.Text("功能说明", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    ft.Text(
                        "上传文件到 catbox.moe 系列服务并获取分享链接。",
                        size=14,
                    ),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=20, color=ft.Colors.GREEN),
                            ft.Text("永久存储：最大200MB，链接永久有效", size=13),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TIMER_OUTLINED, size=20, color=ft.Colors.ORANGE),
                            ft.Text("临时存储：最大1GB，支持1h/12h/24h/72h", size=13),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.BLOCK, size=20, color=ft.Colors.RED),
                            ft.Text("禁止类型：.exe、.scr、.cpl、.doc*、.jar", size=13),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER_OUTLINED, size=20, color=ft.Colors.AMBER),
                            ft.Text("⚠️ 仅供个人使用，不可用于商业服务，请勿上传敏感或非法内容", size=13, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
            border=ft.border.all(2, ft.Colors.BLUE_200),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 存储类型选择
        self.storage_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="permanent", label="永久存储 (最大200MB)"),
                    ft.Radio(value="temporary", label="临时存储 (最大1GB)"),
                ],
                spacing=PADDING_LARGE,
            ),
            value="permanent",
            on_change=self._on_storage_type_change,
        )
        
        # 临时存储时长选择（初始隐藏）
        self.duration_dropdown = ft.Dropdown(
            label="保存时长",
            options=[ft.dropdown.Option(d) for d in TEMP_DURATIONS],
            value="24h",
            width=150,
            visible=False,
            on_select=self._on_duration_change,
        )
        
        storage_config_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("存储选项", size=16, weight=ft.FontWeight.BOLD),
                    self.storage_radio,
                    self.duration_dropdown,
                ],
                spacing=PADDING_MEDIUM,
            ),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            border=ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            border_radius=BORDER_RADIUS_MEDIUM,
            padding=PADDING_MEDIUM,
        )
        
        # 文件选择按钮
        select_button = ft.Button(
            content="选择文件",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_select_files,
        )
        
        # 文件列表区域
        self.file_list_view = ft.Column(
            spacing=PADDING_MEDIUM // 2,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        select_button,
                        ft.TextButton(
                            "清空列表",
                            icon=ft.Icons.CLEAR_ALL,
                            on_click=self._on_clear_files,
                        ),
                        ft.TextButton(
                            "复制所有链接",
                            icon=ft.Icons.COPY_ALL,
                            on_click=self._on_copy_all_urls,
                            visible=True,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(
                    content=self.file_list_view,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                    height=300,  # 固定高度，内部可滚动
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12)
        
        # 上传按钮
        self.upload_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CLOUD_UPLOAD, size=24),
                        ft.Text("开始上传", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_upload,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                info_card,
                storage_config_card,
                file_select_area,
                self.progress_bar,
                self.progress_text,
                self.upload_button,
                ft.Container(height=PADDING_LARGE),
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.AUTO,
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
                        ft.Icon(ft.Icons.FILE_UPLOAD_OUTLINED, size=48),
                        ft.Text("未选择文件", size=14),
                        ft.Text("点击选择按钮或点击此处选择文件", size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                padding=PADDING_LARGE * 2,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_select_files,
                tooltip="点击选择文件",
            )
        )
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择文件",
            allow_multiple=True,
        )
        if result:
            new_files = [Path(f.path) for f in result]
            for new_file in new_files:
                if new_file not in self.selected_files:
                    self.selected_files.append(new_file)
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
                
                # 检查文件大小和类型
                max_size = (200 * 1024 * 1024) if self.storage_type == "permanent" else (1024 * 1024 * 1024)  # 200MB or 1GB
                is_oversized = file_size > max_size
                
                # 检查是否为禁止上传的文件类型
                ext_lower = file_path.suffix.lower()
                is_forbidden = ext_lower in FORBIDDEN_EXTENSIONS
                
                # 获取文件扩展名显示
                ext = file_path.suffix.upper().lstrip('.')
                ext_text = ext if ext else "FILE"
                
                # 确定警告状态
                has_warning = is_oversized or is_forbidden
                warning_text = ""
                if is_forbidden:
                    warning_text = "禁止上传此类型"
                elif is_oversized:
                    warning_text = f"超过{max_size // 1024 // 1024}MB限制"
                
                # 检查是否有上传结果
                upload_result = None
                for result in self.upload_results:
                    if result.get('filename') == file_path.name:
                        upload_result = result
                        break
                
                # 构建文件信息行
                info_controls = [
                    ft.Text(
                        f"{ext_text} • {size_str}",
                        size=11,
                        color=(ft.Colors.RED if is_forbidden else ft.Colors.ORANGE) if has_warning else None
                    ),
                ]
                
                if warning_text and not upload_result:
                    info_controls.append(
                        ft.Text(
                            warning_text,
                            size=11,
                            color=ft.Colors.RED if is_forbidden else ft.Colors.ORANGE,
                            weight=ft.FontWeight.W_500,
                        )
                    )
                
                # 文件名和基本信息列
                file_info_column = ft.Column(
                    controls=[
                        ft.Text(
                            file_path.name,
                            size=13,
                            weight=ft.FontWeight.W_500,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=(ft.Colors.RED if is_forbidden else ft.Colors.ORANGE) if has_warning else None,
                        ),
                        ft.Row(
                            controls=info_controls,
                            spacing=8,
                        ),
                    ],
                    spacing=4,
                    expand=True,
                )
                
                # 如果有上传结果，添加URL显示
                if upload_result:
                    if upload_result['success']:
                        file_info_column.controls.append(
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN),
                                    ft.Text(
                                        upload_result['url'],
                                        size=11,
                                        color=ft.Colors.BLUE,
                                        selectable=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        icon_size=14,
                                        tooltip="复制链接",
                                        on_click=lambda e, url=upload_result['url']: self._copy_url(url),
                                    ),
                                ],
                                spacing=4,
                            )
                        )
                    else:
                        file_info_column.controls.append(
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ERROR, size=14, color=ft.Colors.RED),
                                    ft.Text(
                                        upload_result['error'],
                                        size=11,
                                        color=ft.Colors.RED,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=4,
                            )
                        )
                
                # 确定图标和颜色
                if upload_result:
                    if upload_result['success']:
                        icon = ft.Icons.CHECK_CIRCLE
                        icon_color = ft.Colors.GREEN
                        bg_color = ft.Colors.with_opacity(0.05, ft.Colors.GREEN)
                        border_color = ft.Colors.GREEN_200
                    else:
                        icon = ft.Icons.ERROR
                        icon_color = ft.Colors.RED
                        bg_color = ft.Colors.with_opacity(0.05, ft.Colors.RED)
                        border_color = ft.Colors.RED_200
                elif has_warning:
                    icon = ft.Icons.WARNING
                    icon_color = ft.Colors.RED if is_forbidden else ft.Colors.ORANGE
                    bg_color = ft.Colors.with_opacity(0.05, icon_color) if idx % 2 == 0 else None
                    border_color = icon_color
                else:
                    icon = ft.Icons.INSERT_DRIVE_FILE
                    icon_color = ft.Colors.PRIMARY
                    bg_color = ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if idx % 2 == 0 else None
                    border_color = ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)
                
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(
                                        str(idx + 1),
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                    ),
                                    width=30,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                ft.Icon(
                                    icon,
                                    size=20,
                                    color=icon_color
                                ),
                                file_info_column,
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
                        bgcolor=bg_color,
                        border=ft.border.all(1, border_color),
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
    
    def _on_upload(self, e: ft.ControlEvent) -> None:
        """开始上传按钮点击事件。"""
        # 检查是否正在上传
        if self.is_uploading:
            self._show_message("正在上传中，请稍候...", ft.Colors.ORANGE)
            return
        
        if not self.selected_files:
            self._show_message("请先选择要上传的文件", ft.Colors.ORANGE)
            return
        
        # 检查文件大小和类型
        max_size = (200 * 1024 * 1024) if self.storage_type == "permanent" else (1024 * 1024 * 1024)
        
        # 检查超大文件
        oversized_files = [f for f in self.selected_files if f.stat().st_size > max_size]
        if oversized_files:
            limit_text = "200MB" if self.storage_type == "permanent" else "1GB"
            oversized_names = ', '.join([f.name for f in oversized_files[:3]])
            if len(oversized_files) > 3:
                oversized_names += f' 等{len(oversized_files)}个文件'
            self._show_message(f"以下文件超过{limit_text}限制: {oversized_names}", ft.Colors.ORANGE)
            return
        
        # 检查禁止的文件类型
        forbidden_files = [f for f in self.selected_files if f.suffix.lower() in FORBIDDEN_EXTENSIONS]
        if forbidden_files:
            forbidden_names = ', '.join([f.name for f in forbidden_files[:3]])
            if len(forbidden_files) > 3:
                forbidden_names += f' 等{len(forbidden_files)}个文件'
            self._show_message(f"以下文件类型不允许上传: {forbidden_names}", ft.Colors.RED)
            return
        
        # 设置上传状态
        self.is_uploading = True
        
        # 禁用上传按钮
        upload_btn = self.upload_button.content
        upload_btn.disabled = True
        self.upload_button.update()
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备上传..."
        self.progress_bar.update()
        self.progress_text.update()
        
        # 清空之前的结果
        self.upload_results.clear()
        
        # 上传文件
        total = len(self.selected_files)
        success_count = 0
        
        for i, file_path in enumerate(self.selected_files):
            # 更新进度
            self.progress_text.value = f"正在上传 ({i+1}/{total}): {file_path.name}"
            self.progress_bar.value = (i + 1) / total
            self.progress_text.update()
            self.progress_bar.update()
            
            # 执行上传
            success, result = self._upload_file(file_path)
            
            if success:
                success_count += 1
                self.upload_results.append({
                    'filename': file_path.name,
                    'url': result.get('url') if isinstance(result, dict) else result,
                    'size': file_path.stat().st_size,
                    'success': True
                })
            else:
                self.upload_results.append({
                    'filename': file_path.name,
                    'error': result,
                    'success': False
                })
            
            # 实时更新文件列表显示上传结果
            self._update_file_list()
        
        # 恢复上传状态
        self.is_uploading = False
        
        # 启用上传按钮
        upload_btn = self.upload_button.content
        upload_btn.disabled = False
        self.upload_button.update()
        
        # 隐藏进度条
        self.progress_bar.visible = False
        self.progress_bar.update()
        
        # 显示总结
        self.progress_text.value = f"上传完成！成功: {success_count}/{total}"
        self.progress_text.update()
        
        if success_count > 0:
            self._show_message("上传完成！", ft.Colors.GREEN)
        else:
            self._show_message("上传失败，请检查网络连接", ft.Colors.RED)
    
    def _upload_file(self, file_path: Path) -> tuple[bool, str | dict]:
        """上传单个文件。
        
        Args:
            file_path: 文件路径
        
        Returns:
            (是否成功, URL或错误信息)
        """
        try:
            # 根据存储类型选择API端点
            if self.storage_type == "permanent":
                # 永久存储：catbox.moe
                url = "https://catbox.moe/user/api.php"
                data = {
                    'reqtype': 'fileupload',
                }
            else:
                # 临时存储：litterbox.catbox.moe
                url = "https://litterbox.catbox.moe/resources/internals/api.php"
                data = {
                    'reqtype': 'fileupload',
                    'time': self.temp_duration,
                }
            
            # 检查文件大小
            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            if file_size_mb > 200:  # 超过 200MB 给出警告
                logger.warning(f"上传大文件: {file_path.name} ({file_size_mb:.1f}MB)")
            
            # 准备文件
            # 注意：httpx 的 files 参数会自动进行流式上传，不会一次性加载到内存
            with open(file_path, 'rb') as f:
                files = {
                    'fileToUpload': (file_path.name, f, 'application/octet-stream'),
                }
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                }
                
                # 发送请求（httpx 会自动流式上传）
                response = httpx.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=1800.0  # 30分钟，支持大文件上传
                )
                
                if response.status_code == 200:
                    # 两个端点都返回URL文本
                    result_url = response.text.strip()
                    if result_url and result_url.startswith('http'):
                        return True, {'url': result_url}
                    else:
                        return False, f"无法解析响应: {result_url}"
                else:
                    return False, f"上传失败: HTTP {response.status_code}"
        
        except httpx.TimeoutException:
            return False, "上传超时（文件可能过大）"
        except httpx.ConnectError:
            return False, "网络连接失败"
        except Exception as ex:
            return False, f"上传失败: {str(ex)}"
    
    def _copy_url(self, url: str) -> None:
        """复制单个URL到剪贴板。"""
        self._page.set_clipboard(url)
        self._show_message("链接已复制到剪贴板", ft.Colors.GREEN)
    
    def _on_copy_all_urls(self, e: ft.ControlEvent) -> None:
        """复制所有成功的URL到剪贴板。"""
        urls = [r['url'] for r in self.upload_results if r['success']]
        if urls:
            all_urls = '\n'.join(urls)
            self._page.set_clipboard(all_urls)
            self._show_message(f"已复制 {len(urls)} 个链接到剪贴板", ft.Colors.GREEN)
        else:
            self._show_message("没有可复制的链接", ft.Colors.ORANGE)
    
    def _on_storage_type_change(self, e: ft.ControlEvent) -> None:
        """存储类型切换事件。"""
        self.storage_type = e.control.value
        self.duration_dropdown.visible = (self.storage_type == "temporary")
        self.duration_dropdown.update()
    
    def _on_duration_change(self, e: ft.ControlEvent) -> None:
        """临时存储时长改变事件。"""
        self.temp_duration = e.control.value
    
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
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件。
        
        Args:
            files: 文件路径列表（Path 对象）
        """
        added_count = 0
        forbidden_count = 0
        all_files = []
        
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            ext_lower = path.suffix.lower()
            if ext_lower in FORBIDDEN_EXTENSIONS:
                forbidden_count += 1
                continue
            if path not in self.selected_files:
                self.selected_files.append(path)
                added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            msg = f"已添加 {added_count} 个文件"
            if forbidden_count > 0:
                msg += f"（跳过 {forbidden_count} 个禁止类型）"
            self._show_message(msg, ft.Colors.GREEN)
        elif forbidden_count > 0:
            self._show_message(f"跳过 {forbidden_count} 个禁止上传的文件类型", ft.Colors.ORANGE)
        else:
            self._show_message("未找到有效文件", ft.Colors.ORANGE)
        
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