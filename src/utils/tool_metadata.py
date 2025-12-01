# -*- coding: utf-8 -*-
"""工具元数据系统。

提供工具自动注册和搜索功能。
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class ToolMetadata:
    """工具元数据。"""
    name: str  # 工具名称
    description: str  # 工具描述
    category: str  # 分类（图片处理、音频处理、视频处理、开发工具）
    keywords: List[str]  # 搜索关键词
    icon: str  # 图标名称
    tool_id: str  # 工具ID
    gradient_colors: tuple = ("#e0e0e0", "#f5f5f5")  # 渐变色（默认灰色）
    view_class: Optional[type] = None  # 视图类（用于延迟加载）


# 全局工具注册表
_TOOL_REGISTRY: Dict[str, ToolMetadata] = {}


def register_tool(
    name: str,
    description: str,
    category: str,
    keywords: List[str],
    icon: str,
    tool_id: str,
):
    """工具注册装饰器。
    
    用法:
        @register_tool(
            name="图片压缩",
            description="减小图片文件大小",
            category="图片处理",
            keywords=["压缩", "优化"],
            icon="COMPRESS",
            tool_id="image.compress"
        )
        class CompressView(ft.Container):
            pass
    """
    def decorator(cls):
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            keywords=keywords,
            icon=icon,
            tool_id=tool_id,
            view_class=cls,
        )
        _TOOL_REGISTRY[tool_id] = metadata
        return cls
    return decorator


def register_tool_manual(
    name: str,
    description: str,
    category: str,
    keywords: List[str],
    icon: str,
    tool_id: str,
    gradient_colors: tuple = ("#e0e0e0", "#f5f5f5"),
):
    """手动注册工具（不使用装饰器）。
    
    用于那些不是独立视图类的工具。
    """
    metadata = ToolMetadata(
        name=name,
        description=description,
        category=category,
        keywords=keywords,
        icon=icon,
        tool_id=tool_id,
        gradient_colors=gradient_colors,
    )
    _TOOL_REGISTRY[tool_id] = metadata


def get_all_tools() -> List[ToolMetadata]:
    """获取所有已注册的工具。"""
    return list(_TOOL_REGISTRY.values())


def get_tool(tool_id: str) -> Optional[ToolMetadata]:
    """根据ID获取工具元数据。"""
    return _TOOL_REGISTRY.get(tool_id)


def clear_registry():
    """清空注册表（主要用于测试）。"""
    _TOOL_REGISTRY.clear()

