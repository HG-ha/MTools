# -*- coding: utf-8 -*-
"""推荐视图模块。

基于用户使用历史智能推荐工具。
"""

from typing import Optional

import flet as ft

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
        self.page: ft.Page = page
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
        # 获取使用历史
        tool_usage_count = self.config_service.get_config_value("tool_usage_count", {})
        
        # 推荐的工具卡片
        recommended_cards = []
        
        if tool_usage_count:
            # 有使用历史，显示基于历史的推荐
            # 获取最常用的8个工具
            sorted_tools = sorted(tool_usage_count.items(), key=lambda x: x[1], reverse=True)
            recommended_tool_names = [name for name, count in sorted_tools[:8]]
            
            # 根据工具名称找到对应的tool_id
            all_tools_meta = get_all_tools()
            recommended_tool_ids = []
            for tool_meta in all_tools_meta:
                if tool_meta.name in recommended_tool_names:
                    recommended_tool_ids.append(tool_meta.tool_id)
            
            recommended_cards = self._build_tool_cards(recommended_tool_ids)
        else:
            # 没有使用历史，显示智能推荐
            # 推荐一些常用工具
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
            
            recommended_cards = self._build_tool_cards(smart_recommended)
        
        # 组装内容 - 只显示工具卡片
        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=recommended_cards if recommended_cards else [
                        ft.Text("暂无推荐工具", color=ft.Colors.ON_SURFACE_VARIANT)
                    ],
                    wrap=True,
                    spacing=PADDING_LARGE,
                    run_spacing=PADDING_LARGE,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )
    
    def _build_tool_cards(self, tool_ids: list) -> list:
        """构建工具卡片列表。
        
        Args:
            tool_ids: 工具ID列表
        
        Returns:
            工具卡片列表
        """
        cards = []
        for tool_id in tool_ids:
            tool_meta = get_tool(tool_id)
            if not tool_meta:
                continue
            
            # 获取图标
            icon = getattr(ft.Icons, tool_meta.icon, ft.Icons.HELP_OUTLINE)
            
            # 使用工具自己的渐变色
            gradient_colors = tool_meta.gradient_colors
            
            card = FeatureCard(
                icon=icon,
                title=tool_meta.name,
                description=tool_meta.description,
                on_click=lambda e, tid=tool_id: self._on_tool_click(tid),
                gradient_colors=gradient_colors,
            )
            
            cards.append(card)
        
        return cards
    
    def _get_gradient_for_category(self, category: str) -> tuple:
        """根据分类获取渐变色。"""
        gradient_map = {
            "图片处理": ("#a8edea", "#fed6e3"),
            "媒体处理": ("#84fab0", "#8fd3f4"),
            "开发工具": ("#fbc2eb", "#a6c1ee"),
            "其他工具": ("#ffecd2", "#fcb69f"),
        }
        return gradient_map.get(category, ("#e0e0e0", "#f5f5f5"))
    
    def _on_tool_click(self, tool_id: str) -> None:
        """工具点击事件。"""
        if self.on_tool_click_handler:
            self.on_tool_click_handler(tool_id)
    
    def refresh(self) -> None:
        """刷新界面。"""
        self._build_ui()
        if self.page:
            self.page.update()

