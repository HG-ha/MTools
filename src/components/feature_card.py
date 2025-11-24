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
    """

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        on_click: Optional[Callable] = None,
        gradient_colors: Optional[tuple[str, str]] = None,
        margin: Optional[Union[int, float, ft.Margin]] = None,
    ) -> None:
        """初始化功能卡片。
        
        Args:
            icon: 图标名称
            title: 卡片标题
            description: 卡片描述
            on_click: 点击事件回调函数
            gradient_colors: 渐变色元组(起始色, 结束色)，为None则不使用渐变
            margin: 外边距，可以是整数或 ft.Margin 对象，默认四边外边距为8
        """
        super().__init__()
        self.icon_name: str = icon
        self.card_title: str = title
        self.card_description: str = description
        self.click_handler: Optional[Callable] = on_click
        self.gradient_colors: Optional[tuple[str, str]] = gradient_colors
        # 如果没有指定 margin，默认设置四边外边距为 8
        self.card_margin: Union[int, float, ft.Margin] = margin if margin is not None else ft.margin.only(left=5, right=0, top=5, bottom=10)
        
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
                icon_container,
                ft.Container(height=PADDING_MEDIUM),
                title_text,
                ft.Container(height=PADDING_MEDIUM // 2),
                description_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.START,  # 改为左对齐
            spacing=0,
        )
        
        # 配置容器属性
        self.content = card_content
        self.padding = PADDING_LARGE
        self.margin = self.card_margin  # 设置外边距
        self.width = 280
        self.height = 220
        self.border_radius = BORDER_RADIUS_LARGE
        # 不设置 bgcolor，使用主题的 card_color
        self.shadow = ft.BoxShadow(
            spread_radius=0,
            blur_radius=3,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        )
        self.animate = ft.Animation(200, ft.AnimationCurve.EASE_OUT)
        self.animate_scale = ft.Animation(200, ft.AnimationCurve.EASE_OUT)
        
        # 悬停和点击效果
        if self.click_handler:
            self.ink = True
            self.on_click = self.click_handler
            # 添加鼠标指针样式，使卡片看起来可点击
            # Flet 会自动在可点击的容器上显示手型光标
        
        self.on_hover = self._on_hover
    
    def _on_hover(self, e: ft.HoverEvent) -> None:
        """悬停事件处理。
        
        Args:
            e: 悬停事件对象
        """
        if e.data == "true":
            # 鼠标悬停
            self.scale = 1.02
            self.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=5,
                color=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            )
        else:
            # 鼠标离开
            self.scale = 1.0
            self.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=3,
                color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                offset=ft.Offset(0, 1),
            )
        self.update()

