# -*- coding: utf-8 -*-
"""图片转URL视图模块。

提供图片上传并生成分享URL功能的用户界面。
"""

import httpx
from pathlib import Path
from typing import List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from utils import format_file_size, logger


class ImageToUrlView(ft.Container):
    """图片转URL视图类。
    
    提供图片上传并生成分享URL功能，包括：
    - 支持多种图片格式上传
    - 支持批量上传
    - 可选择链接过期时间（1天、7天、30天）
    - 一键复制生成的URL
    """

    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[callable] = None
    ) -> None:
        """初始化图片转URL视图。
        
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
                ft.Text("图片转URL", size=28, weight=ft.FontWeight.BOLD),
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
                        "上传图片到 imagetourl.net 并获取分享链接，支持设置链接过期时间。",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CLOUD_UPLOAD, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持格式: JPEG, PNG, GIF, WebP, SVG | 单张最大: 10MB",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(2, ft.Colors.BLUE_200),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
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
                        ft.Button(
                            "选择文件",
                            icon=ft.Icons.FILE_UPLOAD,
                            on_click=self._on_select_files,
                        ),
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
        
        # 过期时间选项
        self.expires_radio = ft.RadioGroup(
            content=ft.Row(
                controls=[
                    ft.Radio(value="1d", label="1天"),
                    ft.Radio(value="7d", label="7天"),
                    ft.Radio(value="30d", label="30天"),
                ],
                spacing=PADDING_LARGE,
            ),
            value="7d",
        )
        
        expires_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("链接过期时间:", size=14, weight=ft.FontWeight.W_500),
                    self.expires_radio,
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 进度显示
        self.progress_bar = ft.ProgressBar(visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        
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
                file_select_area,
                expires_card,
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
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                        ft.Text("点击选择按钮或点击此处选择图片", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM // 2,
                ),
                padding=PADDING_LARGE * 2,
                alignment=ft.Alignment.CENTER,
                on_click=self._on_select_files,
                tooltip="点击选择图片",
            )
        )
    
    async def _on_select_files(self, e: ft.ControlEvent) -> None:
        """选择文件按钮点击事件。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择图片文件",
            allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg"],
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
                
                # 检查文件大小是否超过10MB
                max_size = 10 * 1024 * 1024  # 10MB
                is_oversized = file_size > max_size
                
                # 检查是否有上传结果
                upload_result = None
                for result in self.upload_results:
                    if result.get('filename') == file_path.name:
                        upload_result = result
                        break
                
                # 构建文件信息行
                info_controls = [
                    ft.Text(
                        size_str,
                        size=11,
                        color=ft.Colors.ORANGE if is_oversized else None
                    ),
                ]
                
                if is_oversized and not upload_result:
                    info_controls.append(
                        ft.Text(
                            "超过10MB限制",
                            size=11,
                            color=ft.Colors.ORANGE,
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
                            color=ft.Colors.ORANGE if is_oversized else None,
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
                        # 格式化过期时间
                        expires_text = ""
                        if upload_result.get('expiresAt'):
                            try:
                                from datetime import datetime
                                expires_dt = datetime.fromisoformat(upload_result['expiresAt'].replace('Z', '+00:00'))
                                expires_text = f" | 过期: {expires_dt.strftime('%Y-%m-%d %H:%M')}"
                            except:
                                pass
                        
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
                        if expires_text:
                            file_info_column.controls.append(
                                ft.Text(
                                    expires_text.strip(" | "),
                                    size=10,
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
                elif is_oversized:
                    icon = ft.Icons.WARNING
                    icon_color = ft.Colors.ORANGE
                    bg_color = ft.Colors.with_opacity(0.05, ft.Colors.ORANGE) if idx % 2 == 0 else None
                    border_color = ft.Colors.ORANGE
                else:
                    icon = ft.Icons.IMAGE
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
            self._show_message("请先选择要上传的图片", ft.Colors.ORANGE)
            return
        
        # 检查是否有超过大小限制的文件
        max_size = 10 * 1024 * 1024  # 10MB
        oversized_files = [f for f in self.selected_files if f.stat().st_size > max_size]
        if oversized_files:
            oversized_names = ', '.join([f.name for f in oversized_files[:3]])
            if len(oversized_files) > 3:
                oversized_names += f' 等{len(oversized_files)}个文件'
            self._show_message(f"以下文件超过10MB限制: {oversized_names}", ft.Colors.ORANGE)
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
        
        # 获取过期时间
        expires_in = self.expires_radio.value
        
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
            success, result = self._upload_image(file_path, expires_in)
            
            if success:
                success_count += 1
                self.upload_results.append({
                    'filename': file_path.name,
                    'url': result.get('url') if isinstance(result, dict) else result,
                    'size': result.get('size') if isinstance(result, dict) else None,
                    'expiresAt': result.get('expiresAt') if isinstance(result, dict) else None,
                    'success': True
                })
            else:
                self.upload_results.append({
                    'filename': file_path.name,
                    'error': result,
                    'success': False
                })
            
            # 实时更新文件列表显示
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
    
    def _upload_image(self, file_path: Path, expires_in: str) -> tuple[bool, str | dict]:
        """上传单个图片。
        
        Args:
            file_path: 图片文件路径
            expires_in: 过期时间 (1d, 7d, 30d)
        
        Returns:
            (是否成功, 完整响应数据或错误信息)
        """
        try:
            url = "https://imagetourl.net/api/upload/direct"
            
            # 检查文件大小（可选：对超大文件给出警告）
            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            if file_size_mb > 100:  # 超过 100MB 给出提示
                logger.warning(f"上传大文件: {file_path.name} ({file_size_mb:.1f}MB)")
            
            # 准备文件
            # 注意：httpx 的 files 参数会自动进行流式上传，不会一次性加载到内存
            with open(file_path, 'rb') as f:
                files = {
                    'file': (file_path.name, f, self._get_mime_type(file_path)),
                }
                data = {
                    'expiresIn': expires_in
                }
                
                headers = {
                    'accept': '*/*',
                    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'origin': 'https://imagetourl.net',
                    'referer': 'https://imagetourl.net/zh',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
                }
                
                # 发送请求（httpx 会自动流式上传）
                response = httpx.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=1800.0  # 30分钟，支持大图片上传
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # API返回格式: {"publicUrl": "...", "key": "...", "size": ..., "mimeType": "...", "expiresAt": "..."}
                    if 'publicUrl' in result:
                        return True, {
                            'url': result['publicUrl'],
                            'size': result.get('size'),
                            'expiresAt': result.get('expiresAt')
                        }
                    elif 'url' in result:
                        return True, {'url': result['url']}
                    else:
                        return False, "无法解析响应数据"
                else:
                    return False, f"上传失败: HTTP {response.status_code}"
        
        except httpx.TimeoutException:
            return False, "上传超时"
        except httpx.ConnectError:
            return False, "网络连接失败"
        except Exception as ex:
            return False, f"上传失败: {str(ex)}"
    
    def _get_mime_type(self, file_path: Path) -> str:
        """根据文件扩展名获取MIME类型。"""
        ext = file_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
        }
        return mime_types.get(ext, 'application/octet-stream')
    
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
        # 支持的图片扩展名
        supported_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
        
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
            if path.suffix.lower() in supported_exts:
                if path not in self.selected_files:
                    self.selected_files.append(path)
                    added_count += 1
        
        if added_count > 0:
            self._update_file_list()
            self._show_message(f"已添加 {added_count} 个图片文件", ft.Colors.GREEN)
        else:
            self._show_message("未找到支持的图片文件（支持 jpg, png, gif, webp, svg）", ft.Colors.ORANGE)
        
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