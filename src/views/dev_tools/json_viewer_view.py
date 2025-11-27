# -*- coding: utf-8 -*-
"""JSON 查看器视图模块。

提供 JSON 格式化和树形查看功能。
"""

import ast
import json
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL
from services import ConfigService


class JsonTreeNode(ft.Container):
    """JSON 树形节点组件。
    
    可展开/收起的 JSON 节点。
    """
    
    def __init__(self, key: str, value: Any, level: int = 0, is_last: bool = True, parent_path: str = ""):
        """初始化 JSON 树形节点。
        
        Args:
            key: 节点键名
            value: 节点值
            level: 缩进层级
            is_last: 是否是最后一个节点
            parent_path: 父节点路径
        """
        super().__init__()
        self.key = key
        self.value = value
        self.level = level
        self.is_last = is_last
        self.parent_path = parent_path
        
        # 计算完整路径
        if not parent_path:
            self.full_path = key
        else:
            if str(key).startswith("["):
                self.full_path = f"{parent_path}{key}"
            else:
                self.full_path = f"{parent_path}.{key}"

        self.expanded = True
        self.icon_ref = ft.Ref[ft.Icon]()
        self.content_ref = ft.Ref[ft.Column]()
        
        self.content = self._build_view()
        
    def toggle_expand(self, e):
        """切换展开/收起状态。"""
        self.expanded = not self.expanded
        self.icon_ref.current.name = (
            ft.Icons.KEYBOARD_ARROW_DOWN if self.expanded 
            else ft.Icons.KEYBOARD_ARROW_RIGHT
        )
        self.content_ref.current.visible = self.expanded
        self.update()
    
    def _get_value_preview(self, value: Any, truncate: bool = True) -> str:
        """获取值的预览文本。
        
        Args:
            value: 要预览的值
            truncate: 是否截断长字符串
            
        Returns:
            预览文本
        """
        if isinstance(value, dict):
            count = len(value)
            return f"{{...}} ({count} {'key' if count == 1 else 'keys'})"
        elif isinstance(value, list):
            count = len(value)
            return f"[...] ({count} {'item' if count == 1 else 'items'})"
        elif isinstance(value, str):
            if truncate and len(value) > 50:
                return f'"{value[:47]}..."'
            return f'"{value}"'
        elif value is None:
            return "null"
        elif isinstance(value, bool):
            return "true" if value else "false"
        else:
            return str(value)
    
    def _get_value_color(self, value: Any) -> str:
        """根据值类型返回颜色。
        
        Args:
            value: 值
            
        Returns:
            颜色代码
        """
        if isinstance(value, (dict, list)):
            return ft.Colors.BLUE_400
        elif isinstance(value, str):
            return ft.Colors.GREEN_400
        elif isinstance(value, (int, float)):
            return ft.Colors.ORANGE_400
        elif isinstance(value, bool):
            return ft.Colors.PURPLE_400
        elif value is None:
            return ft.Colors.GREY_400
        else:
            return ft.Colors.WHITE
    
    def _build_view(self):
        """构建节点视图。"""
        indent = self.level * 20
        
        # 如果是字典
        if isinstance(self.value, dict):
            children = []
            items = list(self.value.items())
            
            for idx, (k, v) in enumerate(items):
                is_last_child = idx == len(items) - 1
                children.append(JsonTreeNode(k, v, self.level + 1, is_last_child, parent_path=self.full_path))
            
            return ft.Container(
                content=ft.Column(
                    controls=[
                        # 头部（可点击展开/收起）
                        ft.GestureDetector(
                            content=ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ref=self.icon_ref,
                                            name=ft.Icons.KEYBOARD_ARROW_DOWN,
                                            size=16,
                                            color=ft.Colors.GREY_400,
                                        ),
                                        ft.Text(
                                            f'"{self.key}": ',
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            self._get_value_preview(self.value),
                                            color=self._get_value_color(self.value),
                                        ),
                                    ],
                                    spacing=5,
                                ),
                                padding=ft.padding.only(left=indent),
                                on_click=self.toggle_expand,
                                ink=True,
                            ),
                            on_secondary_tap=self._on_right_click,
                        ),
                        # 子节点
                        ft.Column(
                            ref=self.content_ref,
                            controls=children,
                            spacing=2,
                            visible=self.expanded,
                        ),
                    ],
                    spacing=2,
                ),
            )
        
        # 如果是数组
        elif isinstance(self.value, list):
            children = []
            
            for idx, item in enumerate(self.value):
                is_last_child = idx == len(self.value) - 1
                children.append(JsonTreeNode(f"[{idx}]", item, self.level + 1, is_last_child, parent_path=self.full_path))
            
            return ft.Container(
                content=ft.Column(
                    controls=[
                        # 头部
                        ft.GestureDetector(
                            content=ft.Container(
                                content=ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ref=self.icon_ref,
                                            name=ft.Icons.KEYBOARD_ARROW_DOWN,
                                            size=16,
                                            color=ft.Colors.GREY_400,
                                        ),
                                        ft.Text(
                                            f'"{self.key}": ',
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            self._get_value_preview(self.value),
                                            color=self._get_value_color(self.value),
                                        ),
                                    ],
                                    spacing=5,
                                ),
                                padding=ft.padding.only(left=indent),
                                on_click=self.toggle_expand,
                                ink=True,
                            ),
                            on_secondary_tap=self._on_right_click,
                        ),
                        # 子节点
                        ft.Column(
                            ref=self.content_ref,
                            controls=children,
                            spacing=2,
                            visible=self.expanded,
                        ),
                    ],
                    spacing=2,
                ),
            )
        
        # 如果是基本类型
        else:
            return ft.GestureDetector(
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(width=16),  # 占位符，对齐
                            ft.Text(
                                f'"{self.key}": ',
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                self._get_value_preview(self.value, truncate=False),
                                color=self._get_value_color(self.value),
                                selectable=False,
                                expand=True,  # 允许自动换行
                            ),
                        ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    padding=ft.padding.only(left=indent, top=2, bottom=2),
                ),
                on_secondary_tap=self._on_right_click,
            )

    def _on_right_click(self, e):
        """右键点击事件处理。"""
        e.page.dialog = ft.AlertDialog(
            title=ft.Text("操作"),
            content=ft.Column([
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.COPY),
                    title=ft.Text("复制路径"),
                    subtitle=ft.Text(self.full_path, size=12, color=ft.Colors.GREY_400),
                    on_click=lambda _: self._copy_to_clipboard(e.page, self.full_path)
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.COPY),
                    title=ft.Text("复制键 (Key)"),
                    subtitle=ft.Text(str(self.key), size=12, color=ft.Colors.GREY_400),
                    on_click=lambda _: self._copy_to_clipboard(e.page, str(self.key))
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.COPY),
                    title=ft.Text("复制值 (Value)"),
                    subtitle=ft.Text(self._get_value_preview(self.value), size=12, color=ft.Colors.GREY_400),
                    on_click=lambda _: self._copy_value_to_clipboard(e.page)
                ),
            ], tight=True, width=400),
            actions=[ft.TextButton("关闭", on_click=lambda _: self._close_dialog(e.page))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        e.page.dialog.open = True
        e.page.update()

    def _copy_to_clipboard(self, page, text):
        """复制文本到剪贴板。"""
        page.set_clipboard(text)
        page.show_snack_bar(ft.SnackBar(content=ft.Text(f"已复制: {text[:50]}...")))
        self._close_dialog(page)

    def _copy_value_to_clipboard(self, page):
        """复制值到剪贴板。"""
        if isinstance(self.value, (dict, list)):
            text = json.dumps(self.value, ensure_ascii=False, indent=2)
        else:
            text = str(self.value)
        self._copy_to_clipboard(page, text)

    def _close_dialog(self, page):
        """关闭对话框。"""
        page.dialog.open = False
        page.update()


class JsonViewerView(ft.Container):
    """JSON 查看器视图类。
    
    提供 JSON 格式化和树形查看功能。
    """
    
    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        on_back: Optional[Callable] = None
    ):
        """初始化 JSON 查看器视图。
        
        Args:
            page: Flet 页面对象
            config_service: 配置服务实例（可选）
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self.page = page
        self.config_service = config_service
        self.on_back = on_back
        self.expand = True
        # 设置合适的内边距
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 输入文本框引用
        self.input_text = ft.Ref[ft.TextField]()
        # 树形视图引用
        self.tree_view = ft.Ref[ft.Column]()
        # 错误提示引用
        self.error_text = ft.Ref[ft.Text]()
        # 错误容器引用
        self.error_container = ft.Ref[ft.Container]()
        
        # 面板宽度控制
        self.left_panel_ref = ft.Ref[ft.Container]()
        self.right_panel_ref = ft.Ref[ft.Container]()
        self.divider_ref = ft.Ref[ft.Container]()
        self.ratio = 0.4  # 初始比例 4:6
        self.left_flex = 400  # 左侧面板flex值 (使用大整数以支持平滑调整)
        self.right_flex = 600  # 右侧面板flex值
        self.is_dragging = False
        
        self._build_ui()
    
    def _on_divider_pan_start(self, e: ft.DragStartEvent):
        """开始拖动分隔条。"""
        self.is_dragging = True
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = ft.Colors.PRIMARY
            self.divider_ref.current.update()
    
    def _on_divider_pan_update(self, e: ft.DragUpdateEvent):
        """拖动分隔条时更新面板宽度。"""
        if not self.is_dragging:
            return
        
        # 获取容器宽度（估算值，基于页面宽度）
        # 减去 padding (left + right) 和 divider width (8)
        container_width = self.page.width - PADDING_MEDIUM * 2 - 8
        if container_width <= 0:
            return
        
        # 计算拖动产生的比例变化
        # e.delta_x 是像素变化
        delta_ratio = e.delta_x / container_width
        
        # 更新比例
        self.ratio += delta_ratio
        
        # 限制比例范围 (0.1 到 0.9)
        self.ratio = max(0.1, min(0.9, self.ratio))
        
        # 更新 flex 值 (使用整数)
        # 保持总和为 1000
        new_total_flex = 1000
        self.left_flex = int(self.ratio * new_total_flex)
        self.right_flex = new_total_flex - self.left_flex
        
        # 更新面板
        if self.left_panel_ref.current and self.right_panel_ref.current:
            self.left_panel_ref.current.expand = self.left_flex
            self.right_panel_ref.current.expand = self.right_flex
            self.left_panel_ref.current.update()
            self.right_panel_ref.current.update()
    
    def _on_divider_pan_end(self, e: ft.DragEndEvent):
        """结束拖动分隔条。"""
        self.is_dragging = False
        if self.divider_ref.current:
            self.divider_ref.current.bgcolor = None
            self.divider_ref.current.update()
    
    def _build_ui(self):
        """构建用户界面。"""
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self.on_back() if self.on_back else None,
                ),
                ft.Text("JSON 查看器", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 操作按钮组
        action_buttons = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "格式化",
                    icon=ft.Icons.AUTO_AWESOME,
                    on_click=self._on_format_click,
                    tooltip="格式化JSON并显示树形结构",
                ),
                ft.ElevatedButton(
                    "压缩",
                    icon=ft.Icons.COMPRESS,
                    on_click=self._on_compress_click,
                    tooltip="压缩JSON为单行",
                ),
                ft.ElevatedButton(
                    "全部展开",
                    icon=ft.Icons.UNFOLD_MORE,
                    on_click=self._on_expand_all_click,
                    tooltip="展开所有树节点",
                ),
                ft.ElevatedButton(
                    "全部收起",
                    icon=ft.Icons.UNFOLD_LESS,
                    on_click=self._on_collapse_all_click,
                    tooltip="收起所有树节点",
                ),
                ft.ElevatedButton(
                    "加载示例",
                    icon=ft.Icons.LIGHTBULB_OUTLINE,
                    on_click=self._on_load_example_click,
                    tooltip="加载示例JSON",
                ),
                ft.ElevatedButton(
                    "清空",
                    icon=ft.Icons.CLEAR,
                    on_click=self._on_clear_click,
                    tooltip="清空所有内容",
                ),
            ],
            spacing=PADDING_SMALL,
            wrap=True,
        )
        
        # 错误提示
        error_section = ft.Container(
            ref=self.error_container,
            content=ft.Text(
                ref=self.error_text,
                color=ft.Colors.RED_400,
                size=13,
            ),
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL),
            visible=False,  # 默认隐藏容器
        )
        
        # 左侧：JSON 输入区域
        left_panel = ft.Container(
            ref=self.left_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Text(
                        "JSON 输入",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=ft.TextField(
                            ref=self.input_text,
                            multiline=True,
                            min_lines=25,
                            hint_text='粘贴或输入 JSON 数据...\n\n✅ 支持标准 JSON: {"name": "value"}\n✅ 支持单引号: {\'name\': \'value\'}\n✅ 支持 Python 字典格式',
                            text_size=13,
                            expand=True,
                            border=ft.InputBorder.NONE,
                        ),
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=8,
                        padding=PADDING_SMALL,
                        expand=True,
                    ),
                ],
                spacing=PADDING_SMALL,
                expand=True,
            ),
            padding=PADDING_MEDIUM,
            expand=self.left_flex,
        )
        
        # 可拖动的分隔条
        divider = ft.GestureDetector(
            content=ft.Container(
                ref=self.divider_ref,
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                        ft.Icon(ft.Icons.CIRCLE, size=4, color=ft.Colors.GREY_500),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=3,
                ),
                width=12,
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                border_radius=6,
                alignment=ft.alignment.center,
            ),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_start=self._on_divider_pan_start,
            on_pan_update=self._on_divider_pan_update,
            on_pan_end=self._on_divider_pan_end,
            drag_interval=10,
        )
        
        # 右侧：树形视图区域
        right_panel = ft.Container(
            ref=self.right_panel_ref,
            content=ft.Column(
                controls=[
                    ft.Text(
                        "树形视图",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        content=ft.Column(
                            ref=self.tree_view,
                            controls=[
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.ACCOUNT_TREE,
                                                size=48,
                                                color=ft.Colors.GREY_400,
                                            ),
                                            ft.Text(
                                                "格式化后将在此处显示树形结构",
                                                color=ft.Colors.GREY_500,
                                                size=14,
                                                text_align=ft.TextAlign.CENTER,
                                            ),
                                            ft.Text(
                                                "右键点击节点可复制路径和值",
                                                color=ft.Colors.GREY_500,
                                                size=12,
                                                text_align=ft.TextAlign.CENTER,
                                                italic=True,
                                            ),
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        alignment=ft.MainAxisAlignment.CENTER,
                                        spacing=PADDING_SMALL,
                                    ),
                                    expand=True,
                                    alignment=ft.alignment.center,
                                ),
                            ],
                            spacing=2,
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=8,
                        padding=PADDING_MEDIUM,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                        expand=True,
                    ),
                ],
                spacing=PADDING_SMALL,
                expand=True,
            ),
            padding=PADDING_MEDIUM,
            expand=self.right_flex,
        )
        
        # 主内容区域（左右分栏，中间加分隔条）
        content_area = ft.Row(
            controls=[left_panel, divider, right_panel],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 组装整个视图
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Container(
                    content=action_buttons,
                    padding=ft.padding.only(top=PADDING_SMALL, bottom=PADDING_SMALL),
                ),
                error_section,
                content_area,
            ],
            spacing=0,
            expand=True,
        )
    
    def _parse_json_smart(self, input_value: str) -> Any:
        """智能解析 JSON，支持多种格式。
        
        Args:
            input_value: 输入的 JSON 字符串
            
        Returns:
            解析后的 Python 对象
            
        Raises:
            ValueError: 解析失败时抛出
        """
        # 先尝试标准 JSON 解析
        try:
            return json.loads(input_value)
        except json.JSONDecodeError as e1:
            # 如果是单引号问题，尝试用 ast.literal_eval
            try:
                result = ast.literal_eval(input_value)
                # 确保结果是可以序列化为 JSON 的类型
                if isinstance(result, (dict, list, str, int, float, bool, type(None))):
                    return result
                raise ValueError("不支持的数据类型")
            except (ValueError, SyntaxError) as e2:
                # 尝试替换单引号为双引号
                try:
                    fixed_input = input_value.replace("'", '"')
                    return json.loads(fixed_input)
                except json.JSONDecodeError:
                    # 所有方法都失败，抛出原始错误
                    raise ValueError(f"JSON 解析失败 (行 {e1.lineno}, 列 {e1.colno}): {e1.msg}")
    
    def _on_format_click(self, e):
        """格式化按钮点击事件。"""
        input_value = self.input_text.current.value
        
        if not input_value or not input_value.strip():
            self._show_error("请输入 JSON 数据")
            return
        
        try:
            # 使用智能解析
            data = self._parse_json_smart(input_value)
            
            # 格式化并替换输入框内容
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            self.input_text.current.value = formatted
            
            # 构建树形视图
            self._build_tree_view(data)
            
            # 隐藏错误提示
            if self.error_container.current:
                self.error_container.current.visible = False
            
            self.update()
            
        except ValueError as ex:
            error_msg = str(ex)
            
            # 提供常见错误的提示
            if "Expecting property name" in error_msg:
                error_msg += "\n💡 已自动尝试修复单引号，但仍然失败。请检查格式。"
            elif "Expecting value" in error_msg:
                error_msg += "\n💡 提示：检查是否有多余的逗号或缺少值"
            elif "Extra data" in error_msg:
                error_msg += "\n💡 提示：JSON 末尾有多余的内容"
            
            self._show_error(error_msg)
        except Exception as ex:
            self._show_error(f"发生错误: {str(ex)}")
    
    def _on_compress_click(self, e):
        """压缩按钮点击事件。"""
        input_value = self.input_text.current.value
        
        if not input_value or not input_value.strip():
            self._show_error("请输入 JSON 数据")
            return
        
        try:
            # 使用智能解析
            data = self._parse_json_smart(input_value)
            compressed = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            
            # 替换输入框内容
            self.input_text.current.value = compressed
            
            # 隐藏错误提示
            if self.error_container.current:
                self.error_container.current.visible = False
            
            self.update()
            
        except ValueError as ex:
            self._show_error(str(ex))
        except Exception as ex:
            self._show_error(f"发生错误: {str(ex)}")
    
    def _on_expand_all_click(self, e):
        """全部展开按钮点击事件。"""
        self._toggle_all_nodes(True)
    
    def _on_collapse_all_click(self, e):
        """全部收起按钮点击事件。"""
        self._toggle_all_nodes(False)
    
    def _toggle_all_nodes(self, expand: bool):
        """递归展开/收起所有节点。
        
        Args:
            expand: True 为展开，False 为收起
        """
        def toggle_recursive(controls):
            for control in controls:
                if isinstance(control, JsonTreeNode):
                    control.expanded = expand
                    if hasattr(control, 'icon_ref') and control.icon_ref.current:
                        control.icon_ref.current.name = (
                            ft.Icons.KEYBOARD_ARROW_DOWN if expand 
                            else ft.Icons.KEYBOARD_ARROW_RIGHT
                        )
                    if hasattr(control, 'content_ref') and control.content_ref.current:
                        control.content_ref.current.visible = expand
                        toggle_recursive(control.content_ref.current.controls)
                    # 不要对单个控件调用 update，最后统一更新
                elif hasattr(control, 'controls'):
                    toggle_recursive(control.controls)
        
        if self.tree_view.current and self.tree_view.current.controls:
            toggle_recursive(self.tree_view.current.controls)
            # 统一更新整个树形视图
            self.tree_view.current.update()
    
    def _on_clear_click(self, e):
        """清空按钮点击事件。"""
        self.input_text.current.value = ""
        self.tree_view.current.controls = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(
                            ft.Icons.ACCOUNT_TREE,
                            size=48,
                            color=ft.Colors.GREY_400,
                        ),
                        ft.Text(
                            "格式化后将在此处显示树形结构",
                            color=ft.Colors.GREY_500,
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "右键点击节点可复制路径和值",
                            color=ft.Colors.GREY_500,
                            size=12,
                            text_align=ft.TextAlign.CENTER,
                            italic=True,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_SMALL,
                ),
                expand=True,
                alignment=ft.alignment.center,
            ),
        ]
        if self.error_container.current:
            self.error_container.current.visible = False
        self.update()
    
    def _on_load_example_click(self, e):
        """加载示例 JSON 点击事件。"""
        example_json = {
            "name": "张三",
            "age": 25,
            "email": "zhangsan@example.com",
            "isActive": True,
            "tags": ["开发", "Python", "前端"],
            "address": {
                "country": "中国",
                "province": "北京",
                "city": "北京市",
                "detail": "朝阳区xxx街道"
            },
            "projects": [
                {
                    "name": "项目A",
                    "status": "进行中",
                    "progress": 75
                },
                {
                    "name": "项目B",
                    "status": "已完成",
                    "progress": 100
                }
            ]
        }
        
        # 将示例填充到输入框
        self.input_text.current.value = json.dumps(example_json, indent=2, ensure_ascii=False)
        
        # 构建树形视图
        self._build_tree_view(example_json)
        
        # 隐藏错误提示
        if self.error_container.current:
            self.error_container.current.visible = False
        
        self.update()
    
    def _build_tree_view(self, data: Any):
        """构建树形视图。
        
        Args:
            data: JSON 数据
        """
        self.tree_view.current.controls.clear()
        
        if isinstance(data, dict):
            for key, value in data.items():
                node = JsonTreeNode(key, value, level=0)
                self.tree_view.current.controls.append(node)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                node = JsonTreeNode(f"[{idx}]", item, level=0)
                self.tree_view.current.controls.append(node)
        else:
            self.tree_view.current.controls.append(
                ft.Text(f"值: {json.dumps(data, ensure_ascii=False)}")
            )
        
        # 更新树形视图
        self.tree_view.current.update()
    
    def _show_error(self, message: str):
        """显示错误提示。
        
        Args:
            message: 错误消息
        """
        if self.error_text.current:
            self.error_text.current.value = message
        if self.error_container.current:
            self.error_container.current.visible = True
        self.update()
