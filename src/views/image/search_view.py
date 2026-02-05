"""
图片搜索视图模块

提供以图搜图功能，支持：
- 本地图片文件上传
- 网络图片URL上传
- 搜索相似图片
- 分页浏览搜索结果
- 结果预览和详情查看
"""

import flet as ft
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable

from constants import PADDING_LARGE, PADDING_MEDIUM, PADDING_SMALL
from services.sogou_search_service import SogouSearchService
from utils import logger


class ImageSearchView(ft.Container):
    """图片搜索视图
    
    提供以图搜图的完整界面，包括图片上传、结果展示、分页等功能。
    """
    
    # 支持的图片格式
    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', 
        '.gif', '.tiff', '.tif', '.ico', '.avif', '.heic', '.heif'
    }
    
    def __init__(self, page: ft.Page, on_back: Optional[Callable] = None):
        super().__init__()
        self._page = page
        self.on_back = on_back
        
        # 初始化服务
        self.search_service = SogouSearchService()
        
        # 设置容器属性
        self.expand = True
        self.padding = ft.padding.all(PADDING_MEDIUM)
        
        # 状态变量
        self.current_image_path: Optional[str] = None
        self.current_image_url: Optional[str] = None  # 上传后的图片URL
        self.current_page: int = 1
        self.page_size: int = 20
        self.is_searching: bool = False
        
        # 初始化UI组件
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI组件"""
        
        # 图片预览
        self.image_preview = ft.Image(
            width=120,
            height=120,
            fit=ft.BoxFit.COVER,
            border_radius=ft.border_radius.all(8),
        )
        
        # 图片预览容器（控制显示/隐藏）
        self.image_preview_container = ft.Container(
            content=self.image_preview,
            width=120,
            height=120,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            visible=False,
            alignment=ft.Alignment.CENTER,
        )
        
        # 图片路径显示
        self.image_path_text = ft.Text(
            value="",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        
        # URL输入框
        self.url_input = ft.TextField(
            label="图片URL",
            hint_text="输入图片URL地址",
            height=60,
            on_submit=lambda e: self._upload_from_url(),
            expand=True,
        )
        
        # 上传按钮
        self.upload_local_btn = ft.Button(
            "选择本地图片",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_select_local_image,
        )
        
        self.upload_url_btn = ft.Button(
            "从URL上传",
            icon=ft.Icons.LINK,
            on_click=lambda e: self._upload_from_url(),
        )
        
        # 搜索按钮
        self.search_btn = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, size=18),
                    ft.Text("开始搜索", size=14, weight=ft.FontWeight.W_500),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            on_click=lambda e: self._page.run_task(self._perform_search),
            disabled=True,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )
        
        # 进度提示
        self.progress_ring = ft.ProgressRing(visible=False)
        self.status_text = ft.Text(
            value="",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 搜索结果容器
        self.results_container = ft.Column(
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
        )
        
        # 分页控件
        self.page_prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            on_click=lambda e: self._page.run_task(self._go_to_prev_page),
            disabled=True,
        )
        
        self.page_next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            on_click=lambda e: self._page.run_task(self._go_to_next_page),
            disabled=True,
        )
        
        self.page_info_text = ft.Text(
            value="",
            size=14,
            weight=ft.FontWeight.W_500,
        )
        
        self.pagination_row = ft.Row(
            controls=[
                self.page_prev_btn,
                self.page_info_text,
                self.page_next_btn,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False,
        )
        
        # 主布局 - 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                # 上传区域
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("上传图片", size=14, weight=ft.FontWeight.W_500),
                            ft.Divider(height=1),
                            
                            # 主要上传区域：左边预览图，右边控制面板
                            ft.Row(
                                controls=[
                                    # 左侧：预览图
                                    self.image_preview_container,
                                    
                                    # 右侧：控制面板
                                    ft.Column(
                                        controls=[
                                            # 本地上传
                                            ft.Row(
                                                controls=[
                                                    self.upload_local_btn,
                                                    ft.Container(
                                                        content=self.image_path_text,
                                                        expand=True,
                                                    ),
                                                ],
                                                spacing=PADDING_SMALL,
                                            ),
                                            
                                            # URL上传
                                            ft.Row(
                                                controls=[
                                                    self.url_input,
                                                    self.upload_url_btn,
                                                ],
                                                spacing=PADDING_SMALL,
                                            ),
                                            
                                            # 搜索按钮
                                            ft.Container(
                                                content=self.search_btn,
                                                alignment=ft.Alignment.CENTER,
                                            ),
                                        ],
                                        spacing=PADDING_SMALL,
                                        expand=True,
                                    ),
                                ],
                                spacing=PADDING_MEDIUM,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=8,
                    padding=PADDING_MEDIUM,
                ),
                
                # 进度提示
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self.progress_ring,
                            self.status_text,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM,
                    ),
                    padding=PADDING_SMALL,
                    visible=False,
                    ref=ft.Ref[ft.Container](),
                ),
                
                # 搜索结果和分页控件容器 - 占满剩余空间
                ft.Container(
                    content=ft.Column(
                        controls=[
                            # 搜索结果标题
                            ft.Text("搜索结果", size=14, weight=ft.FontWeight.W_500),
                            
                            # 搜索结果
                            ft.Container(
                                content=self.results_container,
                                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                                border_radius=8,
                                padding=PADDING_MEDIUM,
                                expand=True,
                            ),
                            
                            # 分页控件
                            self.pagination_row,
                        ],
                        spacing=PADDING_SMALL,
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )
        
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._handle_back,
                ) if self.on_back else ft.Container(),
                ft.Text("图片搜索", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 主内容
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
            expand=True,
        )
        
        # 保存进度容器的引用以便后续控制可见性
        self.progress_container = ft.Container(
            content=ft.Row(
                controls=[
                    self.progress_ring,
                    self.status_text,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            visible=False,
        )
        
        # 更新可滚动内容，使用保存的引用
        scrollable_content.controls[1] = self.progress_container
        
        self.expand = True
        
        # 初始化搜索结果为空状态
        self._init_empty_results()
    
    def _init_empty_results(self):
        """初始化空状态的搜索结果"""
        self.results_container.controls.clear()
        self.results_container.controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.IMAGE_SEARCH, size=64, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("上传图片开始搜索", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("支持本地图片或网络图片URL", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )
        
    async def _on_select_local_image(self, e: ft.ControlEvent):
        """选择本地图片"""
        result = await ft.FilePicker().pick_files(
            allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp", "webp"],
            dialog_title="选择要搜索的图片"
        )
        if result and len(result) > 0:
            file_path = result[0].path
            self.current_image_path = file_path
            self.image_path_text.value = os.path.basename(file_path)
            
            # 显示图片预览
            self.image_preview.src = file_path
            self.image_preview_container.visible = True
            
            # 启用搜索按钮
            self.search_btn.disabled = False
            
            # 清空URL输入
            self.url_input.value = ""
            
            self._page.update()
            
    def _upload_from_url(self):
        """从URL上传图片"""
        url = self.url_input.value.strip()
        if not url:
            self._show_error("请输入图片URL")
            return
            
        if not url.startswith(("http://", "https://")):
            self._show_error("请输入有效的图片URL")
            return
            
        self.current_image_path = url
        self.image_path_text.value = url
        
        # 显示图片预览
        self.image_preview.src = url
        self.image_preview_container.visible = True
        
        # 启用搜索按钮
        self.search_btn.disabled = False
        
        self._page.update()
        
    async def _perform_search(self):
        """执行搜索"""
        logger.debug("开始搜索...")
        
        if not self.current_image_path:
            logger.error("错误: 未选择图片")
            self._show_error("请先上传图片")
            return
            
        if self.is_searching:
            logger.debug("搜索中，跳过")
            return
            
        logger.debug(f"准备搜索图片: {self.current_image_path}")
        self.is_searching = True
        self.search_btn.disabled = True
        self.progress_container.visible = True
        self.progress_ring.visible = True
        self.status_text.value = "正在上传图片..."
        self._page.update()
        
        try:
            # 上传图片
            logger.debug("开始上传图片...")
            result = await self.search_service.upload_image(self.current_image_path)
            logger.debug(f"上传结果: {result}")
            
            if not self.search_service.is_upload_success(result):
                self._show_error(f"图片上传失败: {result.get('message', '未知错误')}")
                return
                
            # 保存图片URL
            self.current_image_url = result["image_url"]
            logger.debug(f"图片URL: {self.current_image_url}")
            
            # 重置分页
            self.current_page = 1
            
            # 获取搜索结果
            self.status_text.value = "正在搜索相似图片..."
            self._page.update()
            
            await self._load_search_results()
            
        except Exception as e:
            logger.exception(f"搜索异常: {type(e).__name__}: {str(e)}")
            self._show_error(f"搜索失败: {str(e)}")
        finally:
            self.is_searching = False
            self.search_btn.disabled = False
            self.progress_container.visible = False
            self.progress_ring.visible = False
            self.status_text.value = ""
            self._page.update()
            
    async def _load_search_results(self):
        """加载搜索结果"""
        if not self.current_image_url:
            return
            
        try:
            # 计算起始位置
            start = (self.current_page - 1) * self.page_size
            
            # 获取相似图片
            search_result = await self.search_service.search_similar_images(
                self.current_image_url,
                start=start,
                page_size=self.page_size
            )
            
            # 解析并显示结果
            self._display_results(search_result)
            
        except Exception as e:
            self._show_error(f"加载结果失败: {str(e)}")
            
    def _display_results(self, search_result: Dict):
        """显示搜索结果"""
        self.results_container.controls.clear()
        
        # 获取结果列表
        items = search_result.get("items", [])
            
        if not items:
            self.results_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未找到相关结果", size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    height=200,
                    alignment=ft.Alignment.CENTER,
                )
            )
            self._page.update()
            return
            
        # 创建结果卡片
        for idx, item in enumerate(items):
            card = self._create_result_card(item, idx)
            if card:
                self.results_container.controls.append(card)
                
        # 更新分页信息
        has_more = search_result.get("has_more", False)
        self.page_info_text.value = f"第 {self.current_page} 页"
        self.page_prev_btn.disabled = self.current_page <= 1
        self.page_next_btn.disabled = not has_more
        self.pagination_row.visible = True
        
        self._page.update()
        
    def _create_result_card(self, item: Dict, index: int) -> Optional[ft.Container]:
        """创建结果卡片"""
        try:
            # 搜狗返回的数据结构
            # thumbUrl: 缩略图URL
            # pic_url: 原图URL
            # title: 标题
            # page_url: 来源URL
            
            # 提取图片URL
            thumb_url = item.get("thumbUrl", "") or item.get("thumb_url", "")
            pic_url = item.get("pic_url", "") or item.get("picUrl", "")
            
            # 提取标题
            title = item.get("title", "无标题")
            
            # 提取链接
            page_url = item.get("page_url", "") or item.get("fromUrl", "")
            
            # 提取尺寸和大小信息
            width = item.get("width", "")
            height = item.get("height", "")
            size = item.get("size", "")
            
            # 创建卡片
            return ft.Container(
                content=ft.Row(
                    controls=[
                        # 序号
                        ft.Container(
                            content=ft.Text(
                                str(index + 1),
                                size=14,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            width=35,
                            alignment=ft.Alignment.CENTER,
                        ),
                        
                        # 缩略图
                        ft.Container(
                            content=ft.Image(
                                src=thumb_url if thumb_url else pic_url,
                                width=100,
                                height=100,
                                fit=ft.BoxFit.COVER,
                                border_radius=8,
                            ) if (thumb_url or pic_url) else ft.Icon(
                                ft.Icons.BROKEN_IMAGE,
                                size=100,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            width=100,
                            height=100,
                            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=8,
                        ),
                        
                        # 信息区
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    # 标题
                                    ft.Text(
                                        value=title,
                                        size=14,
                                        weight=ft.FontWeight.W_500,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    
                                    # 尺寸和文件大小信息
                                    ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.PHOTO_SIZE_SELECT_ACTUAL, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text(f"{width} × {height}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text("•", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Icon(ft.Icons.INSERT_DRIVE_FILE, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text(size if size else "未知", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                        spacing=4,
                                    ),
                                    
                                    # 操作按钮
                                    ft.Row(
                                        controls=[
                                            ft.Button(
                                                content=ft.Row(
                                                    controls=[
                                                        ft.Icon(ft.Icons.COPY, size=16),
                                                        ft.Text("复制图片URL", size=12),
                                                    ],
                                                    spacing=4,
                                                ),
                                                on_click=lambda e, url=pic_url: self._copy_to_clipboard(url, "图片URL"),
                                                style=ft.ButtonStyle(
                                                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                                ),
                                            ) if pic_url else ft.Container(),
                                            ft.Button(
                                                content=ft.Row(
                                                    controls=[
                                                        ft.Icon(ft.Icons.OPEN_IN_NEW, size=16),
                                                        ft.Text("打开网页", size=12),
                                                    ],
                                                    spacing=4,
                                                ),
                                                on_click=lambda e, url=page_url: self._open_url(url),
                                                style=ft.ButtonStyle(
                                                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                                ),
                                            ) if page_url else ft.Container(),
                                        ],
                                        spacing=8,
                                        wrap=True,
                                    ),
                                ],
                                spacing=8,
                                expand=True,
                            ),
                            expand=True,
                            padding=10,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=8,
                padding=PADDING_MEDIUM,
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE) if index % 2 == 0 else None,
            )
            
        except Exception as e:
            logger.error(f"创建结果卡片失败: {str(e)}")
            return None
            
    def _open_url(self, url: str):
        """打开URL"""
        if url:
            self._page.launch_url(url)
    
    def _copy_to_clipboard(self, text: str, label: str = "内容"):
        """复制文本到剪贴板"""
        if text:
            self._page.set_clipboard(text)
            self._show_snackbar(f"{label}已复制到剪贴板", ft.Colors.GREEN)
        else:
            self._show_snackbar(f"{label}为空，无法复制", ft.Colors.ORANGE)
    
    def _show_snackbar(self, message: str, color: str):
        """显示消息提示"""
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def _handle_back(self, e: ft.ControlEvent = None):
        """处理返回按钮点击"""
        if self.on_back:
            self.on_back(e)
        
    async def _go_to_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            await self._load_search_results()
            
    async def _go_to_next_page(self):
        """下一页"""
        self.current_page += 1
        await self._load_search_results()
        
    def _show_error(self, message: str):
        """显示错误消息"""
        def close_dialog(e):
            dialog.open = False
            self._page.update()
            
        dialog = ft.AlertDialog(
            title=ft.Text("错误"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("确定", on_click=close_dialog),
            ],
        )
        
        self._page.dialog = dialog
        dialog.open = True
        self._page.update()
    
    def add_files(self, files: list) -> None:
        """从拖放添加文件（只取第一个支持的文件）。"""
        import os
        all_files = []
        for path in files:
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        for path in all_files:
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                self.current_image_path = str(path)
                self.image_path_text.value = os.path.basename(str(path))
                self.image_preview.src = str(path)
                self.image_preview.visible = True
                self.image_preview_container.visible = True
                # 启用搜索按钮
                self.search_btn.disabled = False
                self._show_snackbar(f"已加载: {path.name}", ft.Colors.GREEN)
                self._page.update()
                return
        
        self._show_snackbar("图片搜索工具不支持该格式", ft.Colors.ORANGE)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()