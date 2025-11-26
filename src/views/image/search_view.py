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

from constants import PADDING_LARGE, PADDING_MEDIUM
from services.sogou_search_service import SogouSearchService


class ImageSearchView(ft.Container):
    """图片搜索视图
    
    提供以图搜图的完整界面，包括图片上传、结果展示、分页等功能。
    """
    
    def __init__(self, page: ft.Page, on_back: Optional[Callable] = None):
        super().__init__()
        self.page = page
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
            width=300,
            height=300,
            fit=ft.ImageFit.CONTAIN,
            border_radius=ft.border_radius.all(8),
            visible=False,
        )
        
        # 图片路径显示
        self.image_path_text = ft.Text(
            value="",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            width=400,
        )
        
        # 文件选择器
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        self.page.overlay.append(self.file_picker)
        
        # URL输入框
        self.url_input = ft.TextField(
            label="图片URL",
            hint_text="输入图片URL地址",
            width=400,
            height=60,
            on_submit=lambda e: self._upload_from_url(),
        )
        
        # 上传按钮
        self.upload_local_btn = ft.ElevatedButton(
            "选择本地图片",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.file_picker.pick_files(
                allowed_extensions=["jpg", "jpeg", "png", "gif", "bmp"],
                dialog_title="选择要搜索的图片"
            ),
        )
        
        self.upload_url_btn = ft.ElevatedButton(
            "从URL上传",
            icon=ft.Icons.LINK,
            on_click=lambda e: self._upload_from_url(),
        )
        
        # 搜索按钮
        self.search_btn = ft.ElevatedButton(
            "开始搜索",
            icon=ft.Icons.SEARCH,
            on_click=lambda e: self.page.run_task(self._perform_search),
            disabled=True,
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
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        # 分页控件
        self.page_prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            on_click=lambda e: self.page.run_task(self._go_to_prev_page),
            disabled=True,
        )
        
        self.page_next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            on_click=lambda e: self.page.run_task(self._go_to_next_page),
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
        
        # 主布局
        self.content = ft.Column(
            controls=[
                # 标题栏和返回按钮
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.ARROW_BACK,
                                tooltip="返回",
                                on_click=self._handle_back,
                            ) if self.on_back else ft.Container(),
                            ft.Icon(ft.Icons.IMAGE_SEARCH, size=28),
                            ft.Text("图片搜索", size=24, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.only(bottom=20),
                ),
                
                # 上传区域
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("上传图片", size=16, weight=ft.FontWeight.W_500),
                            ft.Divider(height=1),
                            
                            # 本地上传
                            ft.Row(
                                controls=[
                                    self.upload_local_btn,
                                    self.image_path_text,
                                ],
                                spacing=10,
                            ),
                            
                            # URL上传
                            ft.Row(
                                controls=[
                                    self.url_input,
                                    self.upload_url_btn,
                                ],
                                spacing=10,
                            ),
                            
                            # 图片预览
                            ft.Container(
                                content=self.image_preview,
                                alignment=ft.alignment.center,
                                padding=10,
                            ),
                            
                            # 搜索按钮
                            ft.Container(
                                content=self.search_btn,
                                alignment=ft.alignment.center,
                                padding=10,
                            ),
                        ],
                        spacing=10,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=15,
                ),
                
                # 进度提示
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self.progress_ring,
                            self.status_text,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    padding=10,
                ),
                
                # 搜索结果
                ft.Container(
                    content=self.results_container,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=15,
                    expand=True,
                ),
                
                # 分页控件
                self.pagination_row,
            ],
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        
        self.expand = True
        
    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        """处理文件选择"""
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            self.current_image_path = file_path
            self.image_path_text.value = os.path.basename(file_path)
            
            # 显示图片预览
            self.image_preview.src = file_path
            self.image_preview.visible = True
            
            # 启用搜索按钮
            self.search_btn.disabled = False
            
            # 清空URL输入
            self.url_input.value = ""
            
            self.page.update()
            
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
        self.image_preview.visible = True
        
        # 启用搜索按钮
        self.search_btn.disabled = False
        
        self.page.update()
        
    async def _perform_search(self):
        """执行搜索"""
        print("开始搜索...")  # 调试信息
        
        if not self.current_image_path:
            print("错误: 未选择图片")
            self._show_error("请先上传图片")
            return
            
        if self.is_searching:
            print("搜索中，跳过")
            return
            
        print(f"准备搜索图片: {self.current_image_path}")
        self.is_searching = True
        self.search_btn.disabled = True
        self.progress_ring.visible = True
        self.status_text.value = "正在上传图片..."
        self.page.update()
        
        try:
            # 上传图片
            print("开始上传图片...")
            result = await self.search_service.upload_image(self.current_image_path)
            print(f"上传结果: {result}")
            
            if not self.search_service.is_upload_success(result):
                self._show_error(f"图片上传失败: {result.get('message', '未知错误')}")
                return
                
            # 保存图片URL
            self.current_image_url = result["image_url"]
            print(f"图片URL: {self.current_image_url}")
            
            # 重置分页
            self.current_page = 1
            
            # 获取搜索结果
            self.status_text.value = "正在搜索相似图片..."
            self.page.update()
            
            await self._load_search_results()
            
        except Exception as e:
            print(f"搜索异常: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            self._show_error(f"搜索失败: {str(e)}")
        finally:
            self.is_searching = False
            self.search_btn.disabled = False
            self.progress_ring.visible = False
            self.status_text.value = ""
            self.page.update()
            
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
                ft.Text("未找到相关结果", size=16, color=ft.Colors.ON_SURFACE_VARIANT)
            )
            self.page.update()
            return
            
        # 创建结果卡片
        for item in items:
            card = self._create_result_card(item)
            if card:
                self.results_container.controls.append(card)
                
        # 更新分页信息
        has_more = search_result.get("has_more", False)
        self.page_info_text.value = f"第 {self.current_page} 页"
        self.page_prev_btn.disabled = self.current_page <= 1
        self.page_next_btn.disabled = not has_more
        self.pagination_row.visible = True
        
        self.page.update()
        
    def _create_result_card(self, item: Dict) -> Optional[ft.Container]:
        """创建结果卡片"""
        try:
            # 搜狗返回的数据结构
            # thumbUrl: 缩略图URL
            # picUrl: 原图URL
            # title: 标题
            # fromUrl: 来源URL
            
            # 提取图片URL
            img_url = item.get("thumbUrl", "") or item.get("picUrl", "")
            
            # 提取标题
            title = item.get("title", "无标题")
            
            # 提取链接
            link = item.get("fromUrl", "")
            
            # 提取尺寸信息
            width = item.get("width", "")
            height = item.get("height", "")
            size_text = f"{width}x{height}" if width and height else ""
            
            # 创建卡片
            return ft.Container(
                content=ft.Row(
                    controls=[
                        # 缩略图
                        ft.Container(
                            content=ft.Image(
                                src=img_url if img_url else None,
                                width=120,
                                height=120,
                                fit=ft.ImageFit.COVER,
                                border_radius=8,
                            ),
                            width=120,
                            height=120,
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
                                    
                                    # 尺寸信息
                                    ft.Text(
                                        value=size_text,
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ) if size_text else ft.Container(),
                                    
                                    # 链接按钮
                                    ft.Row(
                                        controls=[
                                            ft.TextButton(
                                                "查看来源",
                                                icon=ft.Icons.OPEN_IN_NEW,
                                                on_click=lambda e, url=link: self._open_url(url),
                                            ) if link else ft.Container(),
                                            ft.TextButton(
                                                "查看原图",
                                                icon=ft.Icons.IMAGE,
                                                on_click=lambda e, url=item.get("picUrl", ""): self._open_url(url),
                                            ) if item.get("picUrl") else ft.Container(),
                                        ],
                                        spacing=5,
                                    ),
                                ],
                                spacing=5,
                                expand=True,
                            ),
                            expand=True,
                            padding=10,
                        ),
                    ],
                    spacing=10,
                ),
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=8,
                padding=10,
            )
            
        except Exception as e:
            print(f"创建结果卡片失败: {str(e)}")
            return None
            
    def _open_url(self, url: str):
        """打开URL"""
        if url:
            self.page.launch_url(url)
    
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
            self.page.update()
            
        dialog = ft.AlertDialog(
            title=ft.Text("错误"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("确定", on_click=close_dialog),
            ],
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
