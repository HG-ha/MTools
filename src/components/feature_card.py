# -*- coding: utf-8 -*-
"""功能卡片组件模块。

提供可复用的功能卡片组件，具有现代化的设计效果。
"""

from typing import Callable, Optional, Union

import flet as ft

from constants import (
    BORDER_RADIUS_LARGE,
    CARD_ELEVATION,
    CARD_HOVER_ELEVATION,
    GRADIENT_END,
    GRADIENT_START,
    ICON_SIZE_LARGE,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PRIMARY_COLOR,
)


class FeatureCard(ft.Container):
    """功能卡片组件类。
    
    提供美观的功能卡片，包含：
    - 图标和标题
    - 描述文本
    - 悬停效果
    - 点击事件支持
    - 右键菜单支持（置顶/取消置顶）
    """

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        on_click: Optional[Callable] = None,
        gradient_colors: Optional[tuple[str, str]] = None,
        margin: Optional[Union[int, float, ft.Margin]] = None,
        tool_id: Optional[str] = None,
        is_pinned: bool = False,
        on_pin_change: Optional[Callable[[str, bool], None]] = None,
    ) -> None:
        """初始化功能卡片。
        
        Args:
            icon: 图标名称
            title: 卡片标题
            description: 卡片描述
            on_click: 点击事件回调函数
            gradient_colors: 渐变色元组(起始色, 结束色)，为None则不使用渐变
            margin: 外边距，可以是整数或 ft.Margin 对象，默认四边外边距为8
            tool_id: 工具ID（用于置顶功能）
            is_pinned: 是否已置顶
            on_pin_change: 置顶状态变化回调 (tool_id, is_pinned) -> None
        """
        super().__init__()
        self.icon_name: str = icon
        self.card_title: str = title
        self.card_description: str = description
        self.click_handler: Optional[Callable] = on_click
        self.gradient_colors: Optional[tuple[str, str]] = gradient_colors
        # 如果没有指定 margin，默认设置四边外边距为 8
        self.card_margin: Union[int, float, ft.Margin] = margin if margin is not None else ft.margin.only(left=5, right=0, top=5, bottom=10)
        self.tool_id: Optional[str] = tool_id
        self.is_pinned: bool = is_pinned
        self.on_pin_change: Optional[Callable[[str, bool], None]] = on_pin_change
        
        # 构建卡片
        self._build_card()
    
    def _build_card(self) -> None:
        """构建卡片UI。"""
        # 图标容器（带渐变背景）
        icon_container: ft.Container = ft.Container(
            content=ft.Icon(
                name=self.icon_name,
                size=ICON_SIZE_LARGE,
                color=ft.Colors.WHITE if self.gradient_colors else PRIMARY_COLOR,
            ),
            width=80,
            height=80,
            border_radius=BORDER_RADIUS_LARGE,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=[
                    self.gradient_colors[0] if self.gradient_colors else PRIMARY_COLOR,
                    self.gradient_colors[1] if self.gradient_colors else PRIMARY_COLOR,
                ],
            ) if self.gradient_colors else None,
            bgcolor=None if self.gradient_colors else f"{PRIMARY_COLOR}20",
            alignment=ft.alignment.center,
        )
        
        # 置顶图标（如果已置顶则显示）
        self.pin_icon = ft.Icon(
            name=ft.Icons.PUSH_PIN,
            size=16,
            color=ft.Colors.AMBER,
            visible=self.is_pinned,
        )
        
        # 图标行（图标 + 置顶标记）
        icon_row = ft.Stack(
            controls=[
                icon_container,
                ft.Container(
                    content=self.pin_icon,
                    right=0,
                    top=0,
                ),
            ],
            width=80,
            height=80,
        )
        
        # 标题
        title_text: ft.Text = ft.Text(
            self.card_title,
            size=18,
            weight=ft.FontWeight.W_600,
            # color=TEXT_PRIMARY,  # 移除硬编码颜色，使用默认主题色(ON_SURFACE)
        )
        
        # 描述
        description_text: ft.Text = ft.Text(
            self.card_description,
            size=14,
            # color=TEXT_SECONDARY, # 移除硬编码颜色，使用默认次要颜色
            color=ft.Colors.ON_SURFACE_VARIANT, # 使用语义化颜色适应深色模式
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        
        # 卡片内容 - 左对齐布局
        card_content: ft.Column = ft.Column(
            controls=[
                icon_row,
                ft.Container(height=PADDING_MEDIUM),
                title_text,
                ft.Container(height=PADDING_MEDIUM // 2),
                description_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.START,  # 改为左对齐
            spacing=0,
        )
        
        # 内部卡片容器
        inner_card = ft.Container(
            content=card_content,
            padding=PADDING_LARGE,
            width=280,
            height=220,
            border_radius=BORDER_RADIUS_LARGE,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=3,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            ink=True if self.click_handler else False,
            on_click=self.click_handler,
            on_hover=self._on_hover,
        )
        self._inner_card = inner_card  # 保存引用用于悬停效果
        
        # 如果有 tool_id，用 GestureDetector 包装以支持右键菜单
        if self.tool_id:
            self.content = ft.GestureDetector(
                content=inner_card,
                on_secondary_tap_up=self._on_right_click,
            )
        else:
            self.content = inner_card
        
        # 配置外层容器属性
        self.margin = self.card_margin
        self.width = 280
        self.height = 220
    
    def _on_hover(self, e: ft.HoverEvent) -> None:
        """悬停事件处理。
        
        Args:
            e: 悬停事件对象
        """
        card = self._inner_card
        if e.data == "true":
            # 鼠标悬停
            card.scale = 1.02
            card.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=5,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            )
        else:
            # 鼠标离开
            card.scale = 1.0
            card.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=3,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 1),
            )
        
        # 安全更新：使用page.update()而不是self.update()
        if self.page:
            self.page.update()
    
    def _on_right_click(self, e: ft.TapEvent) -> None:
        """右键点击事件处理（显示上下文菜单）。
        
        Args:
            e: 点击事件对象
        """
        if not self.page or not self.tool_id:
            return
        
        # 显示上下文菜单
        self._show_context_menu(e)
    
    def _show_context_menu(self, e: ft.TapEvent) -> None:
        """显示上下文菜单。
        
        Args:
            e: 点击事件对象
        """
        if not self.page:
            return
        
        # 菜单项文本和图标
        if self.is_pinned:
            menu_text = "取消置顶"
            menu_icon = ft.Icons.PUSH_PIN_OUTLINED
        else:
            menu_text = "置顶到推荐"
            menu_icon = ft.Icons.PUSH_PIN
        
        # 获取点击位置
        local_x = e.local_x if hasattr(e, 'local_x') else 0
        local_y = e.local_y if hasattr(e, 'local_y') else 0
        
        def close_menu(ev):
            if menu_container in self.page.overlay:
                self.page.overlay.remove(menu_container)
                self.page.update()
        
        def on_menu_click(ev):
            close_menu(ev)
            self._toggle_pin(ev)
        
        # 创建菜单项
        menu_item = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(menu_icon, size=18, color=ft.Colors.AMBER if not self.is_pinned else ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(menu_text, size=14),
                ],
                spacing=10,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            on_click=on_menu_click,
            on_hover=lambda e: self._menu_item_hover(e, menu_item),
            border_radius=8,
        )
        
        # 菜单容器（定位在鼠标位置附近）
        menu_card = ft.Container(
            content=menu_item,
            bgcolor="#2d2d2d",  # 深色背景
            border_radius=12,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )
        
        # 透明遮罩层，点击关闭菜单
        menu_container = ft.Stack(
            controls=[
                ft.GestureDetector(
                    content=ft.Container(
                        expand=True,
                        bgcolor=ft.Colors.TRANSPARENT,
                    ),
                    on_tap=close_menu,
                    on_secondary_tap=close_menu,
                ),
                ft.Container(
                    content=menu_card,
                    left=e.global_x if hasattr(e, 'global_x') else 200,
                    top=e.global_y if hasattr(e, 'global_y') else 200,
                ),
            ],
            expand=True,
        )
        
        self.page.overlay.append(menu_container)
        self.page.update()
    
    def _menu_item_hover(self, e: ft.HoverEvent, item: ft.Container) -> None:
        """菜单项悬停效果。"""
        if e.data == "true":
            item.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
        else:
            item.bgcolor = None
        if self.page:
            self.page.update()
    
    def _toggle_pin(self, e) -> None:
        """切换置顶状态。"""
        if not self.tool_id:
            return
        
        self.is_pinned = not self.is_pinned
        self.pin_icon.visible = self.is_pinned
        
        # 调用回调通知父组件
        if self.on_pin_change:
            self.on_pin_change(self.tool_id, self.is_pinned)
        
        if self.page:
            self.page.update()

