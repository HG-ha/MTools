# -*- coding: utf-8 -*-
"""工具搜索组件。

提供全局工具搜索功能。
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional, TYPE_CHECKING

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_MEDIUM,
    PADDING_SMALL,
)

if TYPE_CHECKING:
    from services import ConfigService


@dataclass
class ToolInfo:
    """工具信息类。"""
    name: str  # 工具名称
    description: str  # 工具描述
    category: str  # 分类（图片处理、音频处理、视频处理、开发工具）
    keywords: List[str]  # 关键词（用于搜索）
    icon: str  # 图标
    on_click: Callable  # 点击回调


class ToolSearchDialog(ft.AlertDialog):
    """工具搜索对话框类。"""

    def __init__(
        self,
        page: ft.Page,
        tools: List[ToolInfo],
        config_service: Optional['ConfigService'] = None,
    ) -> None:
        """初始化工具搜索对话框。
        
        Args:
            page: Flet页面对象
            tools: 工具列表
            config_service: 配置服务(用于保存历史记录)
        """
        self._page = page
        self.tools = tools
        self.config_service = config_service
        self.filtered_tools = tools.copy()
        
        # 加载搜索历史和常用工具统计
        self._load_search_data()
        
        # 搜索框
        self.search_field = ft.TextField(
            hint_text="搜索工具... (输入工具名称或关键词)",
            prefix_icon=ft.Icons.SEARCH,
            autofocus=True,
            on_change=self._on_search_change,
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 结果列表
        self.results_list = ft.ListView(
            spacing=PADDING_SMALL,
            height=400,
            expand=True,
        )
        
        # 初始化对话框（不在这里调用 update）
        super().__init__(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, size=28),
                    ft.Text("搜索工具", size=20, weight=ft.FontWeight.W_600),
                ],
                spacing=PADDING_SMALL,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.search_field,
                        ft.Divider(),
                        self.results_list,
                    ],
                    spacing=PADDING_MEDIUM,
                    tight=True,
                ),
                width=600,
                height=500,
            ),
            actions=[
                ft.TextButton("关闭", on_click=self._on_close),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            on_dismiss=lambda e: None,  # 添加关闭回调
        )
        
        # 在对话框初始化后更新结果（此时controls已经创建但还未添加到页面）
        self._populate_initial_results()
    
    def _load_search_data(self) -> None:
        """加载搜索历史和常用工具数据。"""
        if self.config_service:
            # 加载搜索历史(最近10条)
            self.search_history: List[str] = self.config_service.get_config_value("search_history", [])
            # 加载工具使用统计 {tool_name: count}
            self.tool_usage_count: dict = self.config_service.get_config_value("tool_usage_count", {})
        else:
            self.search_history = []
            self.tool_usage_count = {}
    
    def _save_search_data(self) -> None:
        """保存搜索历史和常用工具数据。"""
        if self.config_service:
            self.config_service.set_config_value("search_history", self.search_history)
            self.config_service.set_config_value("tool_usage_count", self.tool_usage_count)
    
    def _add_to_search_history(self, query: str) -> None:
        """添加到搜索历史。
        
        Args:
            query: 搜索关键词
        """
        if not query or not query.strip():
            return
        
        query = query.strip()
        
        # 如果已存在,先移除
        if query in self.search_history:
            self.search_history.remove(query)
        
        # 添加到最前面
        self.search_history.insert(0, query)
        
        # 只保留最近10条
        self.search_history = self.search_history[:10]
        
        # 保存
        self._save_search_data()
    
    def _record_tool_usage(self, tool_name: str) -> None:
        """记录工具使用次数。
        
        Args:
            tool_name: 工具名称
        """
        if tool_name not in self.tool_usage_count:
            self.tool_usage_count[tool_name] = 0
        
        self.tool_usage_count[tool_name] += 1
        
        # 保存
        self._save_search_data()
    
    def _get_frequent_tools(self, limit: int = 5) -> List[ToolInfo]:
        """获取常用工具列表。
        
        Args:
            limit: 返回数量限制
            
        Returns:
            常用工具列表
        """
        if not self.tool_usage_count:
            return []
        
        # 按使用次数排序
        sorted_tools = sorted(
            self.tool_usage_count.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 获取对应的ToolInfo对象
        frequent_tools = []
        for tool_name, count in sorted_tools[:limit]:
            for tool in self.tools:
                if tool.name == tool_name:
                    frequent_tools.append(tool)
                    break
        
        return frequent_tools
    
    def _on_search_change(self, e: ft.ControlEvent) -> None:
        """搜索文本改变事件。"""
        query = e.control.value.lower().strip()
        
        if not query:
            self.filtered_tools = self.tools.copy()
        else:
            # 记录非空搜索到历史
            self._add_to_search_history(query)
            
            self.filtered_tools = []
            for tool in self.tools:
                # 搜索工具名称、描述和关键词
                if (query in tool.name.lower() or
                    query in tool.description.lower() or
                    any(query in kw.lower() for kw in tool.keywords)):
                    self.filtered_tools.append(tool)
        
        self._update_results()
    
    def _populate_initial_results(self) -> None:
        """填充初始结果（不调用update）。"""
        self._build_results()
    
    def _update_results(self) -> None:
        """更新搜索结果显示。"""
        self.results_list.controls.clear()
        self._build_results()
        self.results_list.update()
    
    def _build_results(self) -> None:
        """构建结果列表。"""
        
        # 判断是否为空搜索(显示历史和常用工具)
        is_empty_search = not hasattr(self.search_field, 'value') or not self.search_field.value or not self.search_field.value.strip()
        
        if is_empty_search:
            # 显示常用工具
            frequent_tools = self._get_frequent_tools(limit=5)
            if frequent_tools:
                self.results_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.STAR_ROUNDED, size=16, color=ft.Colors.AMBER),
                                ft.Text(
                                    "常用工具",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.PRIMARY,
                                ),
                            ],
                            spacing=PADDING_SMALL // 2,
                        ),
                        padding=ft.padding.only(top=PADDING_SMALL, bottom=PADDING_SMALL // 2),
                    )
                )
                
                for tool in frequent_tools:
                    self.results_list.controls.append(
                        self._create_tool_item(tool, show_usage_count=True)
                    )
            
            # 显示搜索历史
            if self.search_history:
                self.results_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.HISTORY_ROUNDED, size=16, color=ft.Colors.BLUE),
                                ft.Text(
                                    "最近搜索",
                                    size=14,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.PRIMARY,
                                ),
                            ],
                            spacing=PADDING_SMALL // 2,
                        ),
                        padding=ft.padding.only(top=PADDING_MEDIUM, bottom=PADDING_SMALL // 2),
                    )
                )
                
                for query in self.search_history[:5]:  # 只显示最近5条
                    self.results_list.controls.append(
                        self._create_history_item(query)
                    )
            
            # 如果既没有常用工具也没有搜索历史,显示所有工具
            if not frequent_tools and not self.search_history:
                self._build_all_tools()
        
        elif not self.filtered_tools:
            # 有搜索关键词但无结果
            self.results_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF, size=64, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "未找到匹配的工具",
                                size=16,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "试试其他关键词",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=PADDING_SMALL,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            )
        else:
            # 有搜索结果,按分类分组显示
            self._build_categorized_tools(self.filtered_tools)
    
    def _build_all_tools(self) -> None:
        """构建所有工具列表。"""
        self._build_categorized_tools(self.tools)
    
    def _build_categorized_tools(self, tools: List[ToolInfo]) -> None:
        """按分类构建工具列表。
        
        Args:
            tools: 工具列表
        """
        categories = {}
        for tool in tools:
            if tool.category not in categories:
                categories[tool.category] = []
            categories[tool.category].append(tool)
        
        for category, category_tools in categories.items():
            # 分类标题
            self.results_list.controls.append(
                ft.Container(
                    content=ft.Text(
                        category,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.PRIMARY,
                    ),
                    padding=ft.padding.only(top=PADDING_SMALL, bottom=PADDING_SMALL // 2),
                )
            )
            
            # 工具项
            for tool in category_tools:
                self.results_list.controls.append(
                    self._create_tool_item(tool)
                )
    
    def _create_tool_item(self, tool: ToolInfo, show_usage_count: bool = False) -> ft.Container:
        """创建工具项。
        
        Args:
            tool: 工具信息
            show_usage_count: 是否显示使用次数
        """
        # 描述行控件
        description_controls = [
            ft.Text(
                tool.description,
                size=12,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
        ]
        
        # 如果需要显示使用次数
        if show_usage_count and tool.name in self.tool_usage_count:
            count = self.tool_usage_count[tool.name]
            description_controls.append(
                ft.Text(
                    f" · 使用 {count} 次",
                    size=11,
                    color=ft.Colors.AMBER,
                    weight=ft.FontWeight.W_500,
                )
            )
        
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(tool.icon, size=24),
                    ft.Column(
                        controls=[
                            ft.Text(
                                tool.name,
                                size=14,
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Row(
                                controls=description_controls,
                                spacing=0,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            ink=True,
            on_click=lambda e, t=tool: self._on_tool_click(t),
        )
    
    def _create_history_item(self, query: str) -> ft.Container:
        """创建历史搜索项。
        
        Args:
            query: 搜索关键词
        """
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=20, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        query,
                        size=14,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_size=16,
                        tooltip="删除",
                        on_click=lambda e, q=query: self._remove_from_history(q),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
            ink=True,
            on_click=lambda e, q=query: self._on_history_click(q),
        )
    
    def _on_tool_click(self, tool: ToolInfo) -> None:
        """工具项点击事件。"""
        # 记录工具使用
        self._record_tool_usage(tool.name)
        
        # 关闭对话框
        self.open = False
        self._page.update()
        
        # 执行工具回调
        if tool.on_click:
            tool.on_click()
    
    def _on_history_click(self, query: str) -> None:
        """历史搜索项点击事件。
        
        Args:
            query: 搜索关键词
        """
        # 设置搜索框文本
        self.search_field.value = query
        
        # 手动触发搜索逻辑
        query_lower = query.lower().strip()
        self.filtered_tools = []
        for tool in self.tools:
            # 搜索工具名称、描述和关键词
            if (query_lower in tool.name.lower() or
                query_lower in tool.description.lower() or
                any(query_lower in kw.lower() for kw in tool.keywords)):
                self.filtered_tools.append(tool)
        
        self._update_results()
    
    def _remove_from_history(self, query: str) -> None:
        """从搜索历史中删除。
        
        Args:
            query: 搜索关键词
        """
        if query in self.search_history:
            self.search_history.remove(query)
            self._save_search_data()
            self._update_results()
    
    def _on_close(self, e: ft.ControlEvent) -> None:
        """关闭按钮点击事件。"""
        self.open = False
        self._page.update()


class ToolRegistry:
    """工具注册表类。
    
    用于管理所有可搜索的工具。
    """
    
    def __init__(self):
        """初始化工具注册表。"""
        self.tools: List[ToolInfo] = []
    
    def register(
        self,
        name: str,
        description: str,
        category: str,
        keywords: List[str],
        icon: str,
        on_click: Callable,
    ) -> None:
        """注册工具。
        
        Args:
            name: 工具名称
            description: 工具描述
            category: 分类
            keywords: 关键词列表
            icon: 图标
            on_click: 点击回调
        """
        tool = ToolInfo(
            name=name,
            description=description,
            category=category,
            keywords=keywords,
            icon=icon,
            on_click=on_click,
        )
        self.tools.append(tool)
    
    def get_tools(self) -> List[ToolInfo]:
        """获取所有工具。"""
        return self.tools.copy()
    
    def clear(self) -> None:
        """清空注册表。"""
        self.tools.clear()

