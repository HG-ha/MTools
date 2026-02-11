# -*- coding: utf-8 -*-
"""推荐视图模块。

基于用户使用历史智能推荐工具。
"""

from pathlib import Path
from typing import Optional, List

import flet as ft
import flet_dropzone as ftd  # type: ignore[import-untyped]

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    BORDER_RADIUS_MEDIUM,
)
from services import ConfigService
from utils import get_all_tools, get_tool


class RecommendationsView(ft.Container):
    """推荐视图类。
    
    基于用户使用历史智能推荐工具，包括：
    - 根据使用频率推荐
    - 智能推荐常用工具
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        on_tool_click: Optional[callable] = None,
    ) -> None:
        """初始化推荐视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_tool_click: 工具点击回调
        """
        super().__init__()
        # 使用 _saved_page 保存传入的 page，避免与 Flet 控件的 page 属性冲突
        self._saved_page: ft.Page = page
        self.config_service: ConfigService = config_service if config_service else ConfigService()
        self.on_tool_click_handler: Optional[callable] = on_tool_click
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 获取推荐的工具ID列表（置顶优先）
        recommended_tool_ids = self._get_recommended_tool_ids()
        
        # 构建工具卡片
        recommended_cards = self._build_tool_cards(recommended_tool_ids)
        
        # 组装内容 - 只显示工具卡片
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=recommended_cards if recommended_cards else [
                        ft.Text("暂无推荐工具，右键点击任意工具卡片可置顶", color=ft.Colors.ON_SURFACE_VARIANT)
                    ],
                    wrap=True,
                    spacing=PADDING_LARGE,
                    run_spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
            expand=True,
            width=float('inf'),  # 占满可用宽度
            spacing=0,
        )
    
    def _get_recommended_tool_ids(self) -> List[str]:
        """获取推荐的工具ID列表（置顶优先）。
        
        Returns:
            工具ID列表
        """
        # 获取置顶工具
        pinned_tools = self.config_service.get_pinned_tools()
        
        # 获取使用历史
        tool_usage_count = self.config_service.get_config_value("tool_usage_count", {})
        
        # 推荐的工具ID（不包括已置顶的）
        recommended_tool_ids = []
        
        if tool_usage_count:
            # 有使用历史，显示基于历史的推荐
            sorted_tools = sorted(tool_usage_count.items(), key=lambda x: x[1], reverse=True)
            recommended_tool_names = [name for name, count in sorted_tools[:8]]
            
            # 根据工具名称找到对应的tool_id
            all_tools_meta = get_all_tools()
            for tool_meta in all_tools_meta:
                if tool_meta.name in recommended_tool_names:
                    if tool_meta.tool_id not in pinned_tools:
                        recommended_tool_ids.append(tool_meta.tool_id)
        else:
            # 没有使用历史，显示智能推荐
            smart_recommended = [
                "image.compress",    # 图片压缩
                "video.compress",    # 视频压缩
                "video.convert",     # 视频格式转换
                "audio.format",      # 音频格式转换
                "dev.json_viewer",   # JSON查看器
                "dev.encoding",      # 编码转换
                "image.format",      # 图片格式转换
                "video.speed",       # 视频倍速
            ]
            recommended_tool_ids = [tid for tid in smart_recommended if tid not in pinned_tools]
        
        # 置顶的放在最前面
        return pinned_tools + recommended_tool_ids
    
    def _build_tool_cards(self, tool_ids: list) -> list:
        """构建工具卡片列表。
        
        Args:
            tool_ids: 工具ID列表
        
        Returns:
            工具卡片列表
        """
        # 获取置顶工具列表
        pinned_tools = self.config_service.get_pinned_tools()
        
        cards = []
        for tool_id in tool_ids:
            tool_meta = get_tool(tool_id)
            if not tool_meta:
                continue
            
            # 获取图标
            icon = getattr(ft.Icons, tool_meta.icon, ft.Icons.HELP_OUTLINE)
            
            # 使用工具自己的渐变色
            gradient_colors = tool_meta.gradient_colors
            
            # 检查是否已置顶
            is_pinned = tool_id in pinned_tools
            
            card = FeatureCard(
                icon=icon,
                title=tool_meta.name,
                description=tool_meta.description,
                on_click=lambda e, tid=tool_id: self._on_tool_click(tid),
                gradient_colors=gradient_colors,
                tool_id=tool_id,
                is_pinned=is_pinned,
                on_pin_change=self._on_pin_change,
            )
            wrapped = ftd.Dropzone(
                content=card,
                on_dropped=lambda e, tid=tool_id: self._on_card_drop(e, tid),
            )
            
            cards.append(wrapped)
        
        return cards
    
    def _on_pin_change(self, tool_id: str, is_pinned: bool) -> None:
        """处理置顶状态变化。
        
        Args:
            tool_id: 工具ID
            is_pinned: 是否置顶
        """
        if is_pinned:
            self.config_service.pin_tool(tool_id)
            self._show_snackbar("已置顶到推荐")
        else:
            self.config_service.unpin_tool(tool_id)
            self._show_snackbar("已取消置顶")
        
        # 刷新视图
        self.refresh()
    
    def _get_gradient_for_category(self, category: str) -> tuple:
        """根据分类获取渐变色。"""
        gradient_map = {
            "图片处理": ("#a8edea", "#fed6e3"),
            "媒体处理": ("#84fab0", "#8fd3f4"),
            "开发工具": ("#fbc2eb", "#a6c1ee"),
            "其他工具": ("#ffecd2", "#fcb69f"),
        }
        return gradient_map.get(category, ("#e0e0e0", "#f5f5f5"))
    
    def _on_card_drop(self, e, tool_id: str) -> None:
        """处理卡片上的文件拖放：通过 _pending_drop_files 机制传递文件并跳转工具。"""
        files = [Path(f) for f in e.files]
        if not files or not self.on_tool_click_handler:
            return
        self._saved_page._pending_drop_files = files
        self._saved_page._pending_tool_id = tool_id
        self.on_tool_click_handler(tool_id)

    def _on_tool_click(self, tool_id: str) -> None:
        """工具点击事件。"""
        if self.on_tool_click_handler:
            self.on_tool_click_handler(tool_id)
    
    def refresh(self) -> None:
        """刷新推荐列表。"""
        # 获取推荐的工具ID列表（置顶优先）
        recommended_tool_ids = self._get_recommended_tool_ids()
        
        # 构建工具卡片
        recommended_cards = self._build_tool_cards(recommended_tool_ids)
        
        # 更新内容
        if hasattr(self, 'content') and self.content and isinstance(self.content, ft.Column):
            # 获取现有的 Column 中的 Row
            if len(self.content.controls) > 0:
                row = self.content.controls[0]
                if isinstance(row, ft.Row):
                    # 更新 Row 中的卡片
                    row.controls = recommended_cards if recommended_cards else [
                        ft.Text("暂无推荐工具，右键点击任意工具卡片可置顶", color=ft.Colors.ON_SURFACE_VARIANT)
                    ]
                    
                    # 更新页面
                    try:
                        if self._saved_page:
                            self._saved_page.update()
                    except Exception:
                        # 如果更新失败，静默处理
                        pass
    
    def handle_dropped_files_at(self, files: list, x: int, y: int) -> None:
        """处理拖放到推荐视图的文件。
        
        根据拖放位置找到对应的工具卡片，跳转到对应分类视图处理。
        
        Args:
            files: 文件路径列表（Path 对象）
            x: 鼠标 X 坐标
            y: 鼠标 Y 坐标
        """
        if not files or not self.on_tool_click_handler or not self._saved_page:
            return
        
        # 获取当前推荐的工具ID列表
        tool_ids = self._get_current_tool_ids()
        if not tool_ids:
            self._show_snackbar("暂无推荐工具")
            return
        
        # 计算点击的是哪个工具卡片
        nav_width = 100  # 导航栏宽度
        title_height = 32  # 系统标题栏高度
        
        # 调整坐标
        local_x = x - nav_width - PADDING_MEDIUM
        local_y = y - title_height - PADDING_MEDIUM
        
        if local_x < 0 or local_y < 0:
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        # 卡片布局参数
        card_margin_left = 5
        card_margin_top = 5
        card_margin_bottom = 10
        card_width = 280
        card_height = 220
        card_step_x = card_margin_left + card_width + 0 + PADDING_LARGE
        card_step_y = card_margin_top + card_height + card_margin_bottom + PADDING_LARGE
        
        # 计算行列
        col = int(local_x // card_step_x)
        row = int(local_y // card_step_y)
        
        # 根据窗口宽度计算每行卡片数
        window_width = getattr(self._saved_page.window, 'width', None) or 1000
        content_width = window_width - nav_width - PADDING_MEDIUM * 2
        cols_per_row = max(1, int(content_width // card_step_x))
        
        index = row * cols_per_row + col
        
        if index < 0 or index >= len(tool_ids):
            self._show_snackbar("请将文件拖放到工具卡片上")
            return
        
        tool_id = tool_ids[index]
        
        # 保存待处理的文件到 page 属性（供分类视图使用）
        self._saved_page._pending_drop_files = files
        self._saved_page._pending_tool_id = tool_id
        
        # 跳转到对应工具
        self.on_tool_click_handler(tool_id)
    
    def _get_current_tool_ids(self) -> List[str]:
        """获取当前推荐的工具ID列表。"""
        return self._get_recommended_tool_ids()
    
    def _show_snackbar(self, message: str) -> None:
        """显示提示消息。"""
        if not self._saved_page:
            return
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            duration=3000,
        )
        self._saved_page.overlay.append(snackbar)
        snackbar.open = True
        self._saved_page.update()
