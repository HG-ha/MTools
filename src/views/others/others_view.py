# -*- coding: utf-8 -*-
"""其他工具视图模块。

提供其他类别工具的用户界面。
"""

from typing import Optional

import flet as ft
import flet_dropzone as ftd  # type: ignore[import-untyped]

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
)
from services import ConfigService


class OthersView(ft.Container):
    """其他工具视图类。
    
    提供其他工具相关功能的用户界面。
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化其他工具视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self._page: ft.Page = page
        self._saved_page: ft.Page = page  # 保存页面引用
        self.config_service: ConfigService = config_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 滚动偏移量（用于拖放位置计算）
        self._scroll_offset_y: float = 0
        
        # 卡片布局参数（与 FeatureCard 的尺寸匹配）
        # FeatureCard: width=280, height=220, margin=only(left=5, right=0, top=5, bottom=10)
        # Row: spacing=PADDING_LARGE(24), run_spacing=PADDING_LARGE(24)
        self._card_margin_left = 5
        self._card_margin_top = 5
        self._card_margin_bottom = 10
        self._card_width = 280
        self._card_height = 220
        # 卡片间的实际步进距离：margin_left + width + margin_right + spacing
        self._card_step_x = self._card_margin_left + self._card_width + 0 + PADDING_LARGE  # 5+280+0+24=309
        self._card_step_y = self._card_margin_top + self._card_height + self._card_margin_bottom + PADDING_LARGE  # 5+220+10+24=259
        self._content_padding = PADDING_MEDIUM
        
        # 工具拖放映射表：(工具名称, 支持的扩展名, 打开方法, 视图属性名)
        # None 表示不支持文件拖放
        self._drop_tool_map = [
            ("Windows更新管理", None, None, None),
            ("图片转URL", {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}, self._open_image_to_url_view, "image_to_url"),
            ("文件转URL", True, self._open_file_to_url_view, "file_to_url"),  # True 表示接受任何文件
            ("ICP备案查询", None, None, None),
            ("AI证件照", {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.heic', '.heif'}, self._open_id_photo_view, "id_photo"),
            ("文本翻译", {'.txt', '.md', '.markdown', '.json', '.xml', '.html', '.htm', '.csv', '.log', '.ini', '.cfg', '.conf', '.yaml', '.yml', '.srt', '.vtt', '.ass', '.lrc', '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.cs', '.css', '.sql', '.sh', '.bat', '.ps1'}, self._open_translate_view, "translate"),
        ]
        
        # 创建UI组件
        self._build_ui()
    
    def _safe_page_update(self) -> None:
        """安全地更新页面。"""
        page = getattr(self, '_saved_page', self._page)
        if page:
            page.update()
    
    def _hide_search_button(self) -> None:
        """隐藏主视图的搜索按钮。"""
        if hasattr(self._page, '_main_view'):
            self._page._main_view.hide_search_button()
    
    def _show_search_button(self) -> None:
        """显示主视图的搜索按钮。"""
        if hasattr(self._page, '_main_view'):
            self._page._main_view.show_search_button()
    
    def _on_pin_change(self, tool_id: str, is_pinned: bool) -> None:
        """处理置顶状态变化。"""
        if is_pinned:
            self.config_service.pin_tool(tool_id)
            self._show_snackbar("已置顶到推荐")
        else:
            self.config_service.unpin_tool(tool_id)
            self._show_snackbar("已取消置顶")
        
        # 刷新推荐视图
        if hasattr(self._page, '_main_view') and self._page._main_view.recommendations_view:
            self._page._main_view.recommendations_view.refresh()
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        snackbar = ft.SnackBar(content=ft.Text(message), duration=2000)
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def _create_card(self, icon, title, description, gradient_colors, on_click, tool_id):
        """创建带置顶功能的卡片，外层包裹 Dropzone 支持拖放。"""
        card = FeatureCard(
            icon=icon,
            title=title,
            description=description,
            gradient_colors=gradient_colors,
            on_click=on_click,
            tool_id=tool_id,
            is_pinned=self.config_service.is_tool_pinned(tool_id),
            on_pin_change=self._on_pin_change,
        )
        return ftd.Dropzone(
            content=card,
            on_dropped=lambda e, oc=on_click: self._on_card_drop(e, oc),
        )

    def _on_card_drop(self, e, on_click) -> None:
        """处理卡片上的文件拖放：打开工具并导入文件。"""
        from pathlib import Path

        files = [Path(f) for f in e.files]
        if not files:
            return
        # 1. 打开工具
        on_click(None)

        # 2. 延迟导入文件（等待工具 UI 加载）
        async def import_files():
            import asyncio
            await asyncio.sleep(0.3)
            if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
                self.current_sub_view.add_files(files)

        self._page.run_task(import_files)
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                self._create_card(
                    icon=ft.Icons.UPDATE_DISABLED,
                    title="Windows更新管理",
                    description="禁用或恢复Windows自动更新",
                    gradient_colors=("#FF6B6B", "#FFA500"),
                    on_click=lambda _: self._open_windows_update_view(),
                    tool_id="others.windows_update",
                ),
                self._create_card(
                    icon=ft.Icons.LINK,
                    title="图片转URL",
                    description="上传图片生成分享链接",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=lambda _: self._open_image_to_url_view(),
                    tool_id="others.image_to_url",
                ),
                self._create_card(
                    icon=ft.Icons.UPLOAD_FILE,
                    title="文件转URL",
                    description="上传文件获取分享链接",
                    gradient_colors=("#F093FB", "#F5576C"),
                    on_click=lambda _: self._open_file_to_url_view(),
                    tool_id="others.file_to_url",
                ),
                self._create_card(
                    icon=ft.Icons.SEARCH,
                    title="ICP备案查询",
                    description="查询域名、APP、小程序的备案信息",
                    gradient_colors=("#43E97B", "#38F9D7"),
                    on_click=lambda _: self._open_icp_query_view(),
                    tool_id="others.icp_query",
                ),
                self._create_card(
                    icon=ft.Icons.BADGE,
                    title="AI证件照",
                    description="智能抠图换底，一键生成证件照",
                    gradient_colors=("#667EEA", "#764BA2"),
                    on_click=lambda _: self._open_id_photo_view(),
                    tool_id="others.id_photo",
                ),
                self._create_card(
                    icon=ft.Icons.TRANSLATE,
                    title="文本翻译",
                    description="支持 AI 翻译和 Bing 翻译，多语言互译",
                    gradient_colors=("#00C9FF", "#92FE9D"),
                    on_click=lambda _: self._open_translate_view(),
                    tool_id="others.translate",
                ),
            ],
            wrap=True,
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
            width=float('inf'),  # 占满可用宽度
            on_scroll=self._on_scroll,
        )
    
    def _on_scroll(self, e: ft.OnScrollEvent) -> None:
        """跟踪滚动位置。"""
        self._scroll_offset_y = e.pixels
    
    def _open_windows_update_view(self) -> None:
        """打开Windows更新管理视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.windows_update")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.windows_update_view import WindowsUpdateView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建Windows更新视图
        windows_update_view = WindowsUpdateView(
            page=self._saved_page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = windows_update_view
        self.current_sub_view_type = "windows_update"
        
        # 切换到子视图
        self.parent_container.content = windows_update_view
        self._safe_page_update()
    
    def _open_image_to_url_view(self) -> None:
        """打开图片转URL视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.image_to_url")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.image_to_url_view import ImageToUrlView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建图片转URL视图
        image_to_url_view = ImageToUrlView(
            page=self._saved_page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = image_to_url_view
        self.current_sub_view_type = "image_to_url"
        
        # 切换到子视图
        self.parent_container.content = image_to_url_view
        self._safe_page_update()
    
    def _open_file_to_url_view(self) -> None:
        """打开文件转URL视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.file_to_url")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.file_to_url_view import FileToUrlView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建文件转URL视图
        file_to_url_view = FileToUrlView(
            page=self._saved_page,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = file_to_url_view
        self.current_sub_view_type = "file_to_url"
        
        # 切换到子视图
        self.parent_container.content = file_to_url_view
        self._safe_page_update()
    
    def _open_icp_query_view(self) -> None:
        """打开ICP备案查询视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.icp_query")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.icp_query_view import ICPQueryView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建ICP查询视图
        icp_query_view = ICPQueryView(
            page=self._saved_page,
            config_service=self.config_service,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = icp_query_view
        self.current_sub_view_type = "icp_query"
        
        # 切换到子视图
        self.parent_container.content = icp_query_view
        self._safe_page_update()
    
    def _open_id_photo_view(self) -> None:
        """打开AI证件照视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.id_photo")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.id_photo_view import IDPhotoView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建AI证件照视图
        id_photo_view = IDPhotoView(
            page=self._saved_page,
            config_service=self.config_service,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = id_photo_view
        self.current_sub_view_type = "id_photo"
        
        # 切换到子视图
        self.parent_container.content = id_photo_view
        self._safe_page_update()
    
    def _open_translate_view(self) -> None:
        """打开文本翻译视图。"""
        # 记录工具使用次数
        from utils import get_tool
        tool_meta = get_tool("others.translate")
        if tool_meta:
            self.config_service.record_tool_usage(tool_meta.name)
        
        # 隐藏搜索按钮
        self._hide_search_button()
        
        from views.others.translate_view import TranslateView
        
        if not self.parent_container:
            self._show_message("无法打开视图")
            return
        
        # 创建翻译视图
        translate_view = TranslateView(
            page=self._saved_page,
            config_service=self.config_service,
            on_back=lambda: self._restore_main_view(),
        )
        
        # 保存当前子视图
        self.current_sub_view = translate_view
        self.current_sub_view_type = "translate"
        
        # 切换到子视图
        self.parent_container.content = translate_view
        self._safe_page_update()
    
    def open_tool(self, tool_name: str) -> None:
        """根据工具名称打开对应的工具。
        
        Args:
            tool_name: 工具名称，如 "windows_update", "image_to_url", "file_to_url", "icp_query", "id_photo" 等
        """
        # 如果当前已经打开了该工具，直接返回现有视图，不创建新实例
        if self.current_sub_view_type == tool_name and self.current_sub_view is not None:
            # 确保当前视图显示在容器中
            if self.parent_container and self.parent_container.content != self.current_sub_view:
                self.parent_container.content = self.current_sub_view
                self._safe_page_update()
            return
        
        # 工具名称到方法的映射
        tool_map = {
            "windows_update": self._open_windows_update_view,
            "image_to_url": self._open_image_to_url_view,
            "file_to_url": self._open_file_to_url_view,
            "icp_query": self._open_icp_query_view,
            "id_photo": self._open_id_photo_view,
            "translate": self._open_translate_view,
        }
        
        # 查找并调用对应的方法
        if tool_name in tool_map:
            tool_map[tool_name]()
    
    def _restore_main_view(self) -> None:
        """恢复到主视图（使用路由导航）。"""
        import gc
        
        # 销毁当前子视图并清理资源
        if self.current_sub_view:
            view_instance = self.current_sub_view
            
            # 统一调用 cleanup 方法（每个视图自己负责清理资源和卸载模型）
            if hasattr(view_instance, 'cleanup'):
                try:
                    view_instance.cleanup()
                except Exception:
                    pass
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        # 强制垃圾回收释放内存
        gc.collect()
        
        # 直接恢复主界面（不依赖路由，因为打开工具时也是直接切换内容的）
        if self.parent_container:
            self.parent_container.content = self
            self._show_search_button()
            self._safe_page_update()
    
    def _show_message(self, message: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
        """
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=3000,
        )
        self._saved_page.overlay.append(snackbar)
        snackbar.open = True
        self._saved_page.update()
    
    def restore_state(self) -> bool:
        """恢复视图状态。
        
        当用户从其他类型视图返回时，恢复之前的状态。
        
        Returns:
            是否恢复了子视图（True表示已恢复子视图，False表示需要显示主视图）
        """
        if self.current_sub_view and self.parent_container:
            # 恢复到子视图
            self.parent_container.content = self.current_sub_view
            self._safe_page_update()
            return True
        return False
    
    def handle_dropped_files_at(self, files: list, x: int, y: int) -> None:
        """处理拖放到指定位置的文件。
        
        Args:
            files: 文件路径列表（Path 对象）
            x: 鼠标 X 坐标（相对于窗口客户区）
            y: 鼠标 Y 坐标（相对于窗口客户区）
        """
        # 如果当前显示的是子视图，让子视图处理
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(files)
            return
        
        # 计算点击的是哪个工具卡片
        nav_width = 100  # 导航栏宽度
        title_height = 32  # 系统标题栏高度
        
        # 调整坐标（减去导航栏、标题栏，加上滚动偏移量）
        local_x = x - nav_width - self._content_padding
        local_y = y - title_height - self._content_padding + self._scroll_offset_y
        
        if local_x < 0 or local_y < 0:
            self._show_message("请将文件拖放到工具卡片上")
            return
        
        # 计算行列
        col = int(local_x // self._card_step_x)
        row = int(local_y // self._card_step_y)
        
        # 根据实际窗口宽度计算每行卡片数
        window_width = self._saved_page.window.width or 1000
        content_width = window_width - nav_width - self._content_padding * 2
        cols_per_row = max(1, int(content_width // self._card_step_x))
        
        index = row * cols_per_row + col
        
        if index < 0 or index >= len(self._drop_tool_map):
            self._show_message("请将文件拖放到工具卡片上")
            return
        
        tool_name, supported_exts, open_func, view_attr = self._drop_tool_map[index]
        
        if not open_func:
            self._show_message(f"「{tool_name}」不支持文件拖放")
            return
        
        # 展开文件夹
        all_files = []
        for f in files:
            if f.is_dir():
                for item in f.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(f)
        
        if not all_files:
            self._show_message("未检测到有效文件")
            return
        
        # 检查文件类型
        if supported_exts is True:
            # 接受任何文件
            valid_files = all_files
        else:
            valid_files = [f for f in all_files if f.suffix.lower() in supported_exts]
        
        if not valid_files:
            ext = all_files[0].suffix.lower() if all_files else ""
            self._show_message(f"「{tool_name}」不支持 {ext} 类型的文件")
            return
        
        # 打开对应工具并导入文件
        open_func()
        if self.current_sub_view and hasattr(self.current_sub_view, 'add_files'):
            self.current_sub_view.add_files(valid_files)
    
    def cleanup(self) -> None:
        """清理视图资源。
        
        当视图被切换走时调用，释放不需要的资源。
        """
        import gc
        # 清除回调引用，打破循环引用（如果有的话）
        if hasattr(self, 'on_back'):
            self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
