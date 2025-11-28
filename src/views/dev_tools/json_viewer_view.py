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
    
    def __init__(self, key: str, value: Any, level: int = 0, is_last: bool = True, parent_path: str = "", page: Optional[ft.Page] = None, view: Optional['JsonViewerView'] = None):
        """初始化 JSON 树形节点。
        
        Args:
            key: 节点键名
            value: 节点值
            level: 缩进层级
            is_last: 是否是最后一个节点
            parent_path: 父节点路径
            page: 页面对象
            view: JsonViewerView 实例
        """
        super().__init__()
        self.key = key
        self.value = value
        self.level = level
        self.is_last = is_last
        self.parent_path = parent_path
        self.page = page
        self.view = view
        
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
    
    def get_path_formats(self) -> Dict[str, str]:
        """获取不同语言格式的路径。
        
        Returns:
            包含不同格式路径的字典（去重后）
        """
        # 先生成所有格式
        all_formats = {}
        
        # 简单点号格式: key.subkey (原始格式)
        all_formats['简单格式'] = self.full_path
        
        # JavaScript 点号格式: data.key[0].subkey
        js_dot_path = self._to_javascript_dot_path()
        all_formats['JS/TS (点号)'] = js_dot_path
        
        # Python/Ruby 单引号括号格式: data['key'][0]['subkey']
        python_path = self._to_python_path()
        all_formats['Python/Ruby'] = python_path
        
        # JavaScript 括号格式: data['key'][0]['subkey']
        js_bracket_path = self._to_javascript_bracket_path()
        all_formats['JavaScript (括号)'] = js_bracket_path
        
        # C#/Go/Rust/Swift/Kotlin 双引号格式: data["key"][0]["subkey"]
        csharp_path = self._to_csharp_path()
        all_formats['C#/Go/Rust/Swift/Kotlin'] = csharp_path
        
        # PHP 格式: $data['key'][0]['subkey']
        php_path = self._to_php_path()
        all_formats['PHP'] = php_path
        
        # Java 格式: data.get("key").get(0).get("subkey")
        java_path = self._to_java_path()
        all_formats['Java'] = java_path
        
        # Ruby dig 格式: data.dig('key', 0, 'subkey')
        ruby_dig_path = self._to_ruby_dig_path()
        all_formats['Ruby (dig)'] = ruby_dig_path
        
        # JSONPath 格式: $.key[0].subkey
        jsonpath = self._to_jsonpath()
        all_formats['JSONPath'] = jsonpath
        
        # JSON Pointer 格式: /key/0/subkey
        json_pointer = self._to_json_pointer()
        all_formats['JSON Pointer'] = json_pointer
        
        # jq 格式: .key[0].subkey
        jq_path = self._to_jq_path()
        all_formats['jq'] = jq_path
        
        # 去重：只保留不同的路径值
        unique_formats = {}
        seen_values = {}
        
        for name, path_value in all_formats.items():
            if path_value not in seen_values:
                unique_formats[name] = path_value
                seen_values[path_value] = name
            else:
                # 如果值已存在，合并名称
                existing_name = seen_values[path_value]
                if existing_name in unique_formats:
                    # 合并名称（如果还没合并过）
                    if '/' not in existing_name:
                        # 只在第一次遇到重复时合并
                        pass
        
        return unique_formats
        formats['简单格式'] = self.full_path
        
        return formats
    
    def _to_python_path(self) -> str:
        """转换为Python访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                # 检查键名是否需要引号
                key = part['value']
                if key.isidentifier():
                    path += f"['{key}']"
                else:
                    path += f"['{key}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_javascript_dot_path(self) -> str:
        """转换为JavaScript点号访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                key = part['value']
                # 检查是否可以用点号访问
                if key.replace('_', '').replace('$', '').isalnum() and not key[0].isdigit():
                    path += f".{key}"
                else:
                    path += f"['{key}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_javascript_bracket_path(self) -> str:
        """转换为JavaScript括号访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"['{part['value']}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_jsonpath(self) -> str:
        """转换为JSONPath格式。"""
        if not self.full_path:
            return "$"
        
        parts = self._parse_path_parts()
        path = "$"
        for part in parts:
            if part['type'] == 'key':
                key = part['value']
                # JSONPath 可以用点号或括号
                if key.replace('_', '').isalnum() and not key[0].isdigit():
                    path += f".{key}"
                else:
                    path += f"['{key}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_json_pointer(self) -> str:
        """转换为JSON Pointer格式 (RFC 6901)。"""
        if not self.full_path:
            return "/"
        
        parts = self._parse_path_parts()
        path = ""
        for part in parts:
            if part['type'] == 'key':
                # JSON Pointer 需要转义 ~ 和 /
                key = part['value'].replace('~', '~0').replace('/', '~1')
                path += f"/{key}"
            else:  # index
                path += f"/{part['value']}"
        return path
    
    def _parse_path_parts(self) -> List[Dict[str, str]]:
        """解析路径为部分列表。
        
        Returns:
            部分列表，每个部分包含 type ('key' 或 'index') 和 value
        """
        parts = []
        current = ""
        i = 0
        path = self.full_path
        
        while i < len(path):
            if path[i] == '[':
                # 保存之前的键名
                if current:
                    parts.append({'type': 'key', 'value': current})
                    current = ""
                
                # 找到匹配的 ]
                j = i + 1
                while j < len(path) and path[j] != ']':
                    j += 1
                
                # 提取数组索引
                index = path[i+1:j]
                parts.append({'type': 'index', 'value': index})
                i = j + 1
                
                # 跳过后续的点号
                if i < len(path) and path[i] == '.':
                    i += 1
            elif path[i] == '.':
                # 保存之前的键名
                if current:
                    parts.append({'type': 'key', 'value': current})
                    current = ""
                i += 1
            else:
                current += path[i]
                i += 1
        
        # 保存最后的键名
        if current:
            parts.append({'type': 'key', 'value': current})
        
        return parts
    
    def _to_ruby_path(self) -> str:
        """转换为Ruby括号访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"['{part['value']}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_ruby_dig_path(self) -> str:
        """转换为Ruby dig方法路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        if not parts:
            return "data"
        
        args = []
        for part in parts:
            if part['type'] == 'key':
                args.append(f"'{part['value']}'")
            else:  # index
                args.append(part['value'])
        
        return f"data.dig({', '.join(args)})"
    
    def _to_php_path(self) -> str:
        """转换为PHP访问路径格式。"""
        if not self.full_path:
            return "$data"
        
        parts = self._parse_path_parts()
        path = "$data"
        for part in parts:
            if part['type'] == 'key':
                path += f"['{part['value']}']"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_java_path(self) -> str:
        """转换为Java访问路径格式（假设使用JSONObject/JSONArray）。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                # Java通常使用 get() 或 getJSONObject() 等方法
                path += f".get(\"{part['value']}\")"
            else:  # index
                path += f".get({part['value']})"
        return path
    
    def _to_csharp_path(self) -> str:
        """转换为C#访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"[\"{part['value']}\"]"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_go_path(self) -> str:
        """转换为Go访问路径格式（简化版）。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"[\"{part['value']}\"]"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_rust_path(self) -> str:
        """转换为Rust访问路径格式（假设使用serde_json）。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"[\"{part['value']}\"]"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_swift_path(self) -> str:
        """转换为Swift访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"[\"{part['value']}\"]"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_kotlin_path(self) -> str:
        """转换为Kotlin访问路径格式。"""
        if not self.full_path:
            return "data"
        
        parts = self._parse_path_parts()
        path = "data"
        for part in parts:
            if part['type'] == 'key':
                path += f"[\"{part['value']}\"]"
            else:  # index
                path += f"[{part['value']}]"
        return path
    
    def _to_jq_path(self) -> str:
        """转换为jq命令行工具路径格式。"""
        if not self.full_path:
            return "."
        
        parts = self._parse_path_parts()
        path = ""
        for part in parts:
            if part['type'] == 'key':
                key = part['value']
                # jq 可以用点号或括号
                if key.replace('_', '').isalnum() and not key[0].isdigit():
                    path += f".{key}"
                else:
                    path += f'.["{key}"]'
            else:  # index
                path += f"[{part['value']}]"
        return path
        
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
                children.append(JsonTreeNode(k, v, self.level + 1, is_last_child, parent_path=self.full_path, page=self.page, view=self.view))
            
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
                                bgcolor=ft.Colors.TRANSPARENT,
                            ),
                            on_tap=self.toggle_expand,
                            on_secondary_tap_up=self._on_right_click,
                            mouse_cursor=ft.MouseCursor.CLICK,
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
                children.append(JsonTreeNode(f"[{idx}]", item, self.level + 1, is_last_child, parent_path=self.full_path, page=self.page, view=self.view))
            
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
                                bgcolor=ft.Colors.TRANSPARENT,
                            ),
                            on_tap=self.toggle_expand,
                            on_secondary_tap_up=self._on_right_click,
                            mouse_cursor=ft.MouseCursor.CLICK,
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
                    bgcolor=ft.Colors.TRANSPARENT,
                ),
                on_secondary_tap_up=self._on_right_click,
            )

    def _resolve_page(self, event: Optional[ft.ControlEvent] = None) -> Optional[ft.Page]:
        """从事件或控件自身解析 Page 对象。"""
        # 优先使用存储的 page
        if self.page is not None:
            return self.page
        
        # 尝试从事件中获取
        if event is not None:
            page = getattr(event, "page", None)
            if page:
                return page
            control = getattr(event, "control", None)
            if control is not None:
                control_page = getattr(control, "page", None)
                if control_page:
                    return control_page
        
        # 尝试从自身获取（通过遍历父节点）
        try:
            current = self
            while current is not None:
                if hasattr(current, 'page') and current.page is not None:
                    return current.page
                current = getattr(current, 'parent', None)
        except:
            pass
            
        return None

    def _on_right_click(self, e):
        """右键点击事件处理。"""
        try:
            # 如果有 view 引用，使用浮动菜单
            if self.view:
                # 获取全局坐标
                global_x = getattr(e, 'global_x', 100)
                global_y = getattr(e, 'global_y', 100)
                
                # 直接使用 global 坐标，但稍微调整一下
                # 偏右下说明坐标太大了，需要减小
                # 通常右键菜单应该在鼠标右下方一点点
                x = global_x - 100
                y = global_y - 60
                
                self.view.show_context_menu(x, y, self)
                return
            
            # 否则使用对话框（降级方案）
            page = self._resolve_page(e)
            if page is None:
                return
            
            # 关闭可能存在的旧对话框
            if hasattr(page, 'dialog') and page.dialog:
                try:
                    page.close(page.dialog)
                except:
                    pass
            
            # 创建小型弹出菜单
            def close_menu():
                dialog.open = False
                page.update()
            
            def copy_and_close(text):
                self._copy_to_clipboard(page, text)
                close_menu()
            
            def copy_value_and_close():
                if isinstance(self.value, (dict, list)):
                    text = json.dumps(self.value, ensure_ascii=False, indent=2)
                else:
                    text = str(self.value)
                self._copy_to_clipboard(page, text)
                close_menu()
            
            dialog = ft.AlertDialog(
                modal=False,  # 非模态，允许点击外部关闭
                content=ft.Container(
                    content=ft.Column([
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.COPY, size=20),
                            title=ft.Text("复制路径", size=14),
                            subtitle=ft.Text(
                                self.full_path if len(self.full_path) <= 40 else self.full_path[:37] + "...", 
                                size=11, 
                                color=ft.Colors.GREY_400
                            ),
                            on_click=lambda _: copy_and_close(self.full_path),
                            dense=True,
                        ),
                        ft.Divider(height=1, thickness=1),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.COPY, size=20),
                            title=ft.Text("复制键", size=14),
                            subtitle=ft.Text(str(self.key), size=11, color=ft.Colors.GREY_400),
                            on_click=lambda _: copy_and_close(str(self.key)),
                            dense=True,
                        ),
                        ft.Divider(height=1, thickness=1),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.COPY, size=20),
                            title=ft.Text("复制值", size=14),
                            subtitle=ft.Text(
                                self._get_value_preview(self.value) if len(self._get_value_preview(self.value)) <= 40 
                                else self._get_value_preview(self.value)[:37] + "...", 
                                size=11, 
                                color=ft.Colors.GREY_400
                            ),
                            on_click=lambda _: copy_value_and_close(),
                            dense=True,
                        ),
                    ], tight=True, spacing=0),
                    width=300,
                    padding=ft.padding.symmetric(vertical=8),
                ),
            )
            
            page.open(dialog)
        except Exception as ex:
            print(f"右键菜单错误: {ex}")
            import traceback
            traceback.print_exc()

    def _copy_to_clipboard(self, page, text):
        """复制文本到剪贴板。"""
        try:
            if page is None:
                return
            page.set_clipboard(text)
            
            # 显示提示
            snack_bar = ft.SnackBar(
                content=ft.Text(f"已复制: {text[:50]}..." if len(str(text)) > 50 else str(text))
            )
            page.snack_bar = snack_bar
            snack_bar.open = True
            page.update()
        except Exception as ex:
            print(f"复制失败: {ex}")

    def _copy_value_to_clipboard(self, page):
        """复制值到剪贴板。"""
        try:
            if page is None:
                return
            if isinstance(self.value, (dict, list)):
                text = json.dumps(self.value, ensure_ascii=False, indent=2)
            else:
                text = str(self.value)
            self._copy_to_clipboard(page, text)
        except Exception as ex:
            print(f"复制值失败: {ex}")

    def _close_dialog(self, page):
        """关闭对话框。"""
        try:
            if page is None:
                return
            if hasattr(page, 'dialog') and page.dialog is not None:
                page.dialog.open = False
                page.update()
        except Exception as ex:
            print(f"关闭对话框失败: {ex}")


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
        
        # 主内容列
        main_column = ft.Column(
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
        
        # 浮动菜单容器（初始隐藏，将直接放在 Stack 中）
        self.floating_menu_ref = ft.Ref[ft.Container]()
        
        # 使用 Stack 包裹，添加浮动菜单层
        self.content = ft.Stack(
            controls=[
                main_column,
                ft.Container(
                    ref=self.floating_menu_ref,
                    visible=False,
                    expand=True,  # 确保容器占满整个空间
                ),
            ],
            expand=True,
        )
    
    def show_context_menu(self, x: float, y: float, node: 'JsonTreeNode'):
        """在指定位置显示右键菜单。
        
        Args:
            x: 鼠标 X 坐标（相对于窗口）
            y: 鼠标 Y 坐标（相对于窗口）
            node: 触发菜单的节点
        """
        if not self.floating_menu_ref.current:
            return
        
        # 用于跟踪当前显示的子菜单
        self.current_submenu_ref = ft.Ref[ft.Container]()
        
        # 获取可用空间（更保守的计算，考虑标题栏、按钮栏等）
        # 标题栏约40px，操作按钮栏约60px，上下padding共40px
        header_and_controls_height = 140
        view_width = self.page.width - PADDING_MEDIUM * 2 - 20  # 额外减去20px安全边距
        view_height = self.page.height - header_and_controls_height - PADDING_MEDIUM * 2 - 20  # 额外减去20px安全边距
        
        # 主菜单尺寸和位置预计算
        main_menu_width = 180
        main_menu_height = 120  # 3个菜单项，每个约40px
        main_menu_left = x
        main_menu_top = y
        
        # 检查主菜单是否超出右边界
        if main_menu_left + main_menu_width > view_width:
            main_menu_left = max(10, view_width - main_menu_width - 10)
        
        # 检查主菜单是否超出底部边界
        if main_menu_top + main_menu_height > view_height:
            main_menu_top = max(10, view_height - main_menu_height - 10)
        
        # 确保不超出左边和顶部
        main_menu_left = max(10, main_menu_left)
        main_menu_top = max(10, main_menu_top)
        
        def close_menu(e=None):
            if self.floating_menu_ref.current:
                self.floating_menu_ref.current.visible = False
                self.floating_menu_ref.current.update()
        
        def copy_and_close(text):
            node._copy_to_clipboard(self.page, text)
            close_menu()
        
        def copy_value_and_close():
            if isinstance(node.value, (dict, list)):
                text = json.dumps(node.value, ensure_ascii=False, indent=2)
            else:
                text = str(node.value)
            node._copy_to_clipboard(self.page, text)
            close_menu()
        
        def show_path_submenu(e):
            """显示路径格式子菜单。"""
            # 获取不同格式的路径
            path_formats = node.get_path_formats()
            
            # 创建子菜单项
            submenu_items = []
            for format_name, path_value in path_formats.items():
                submenu_items.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(format_name, size=12, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                path_value if len(path_value) <= 60 else path_value[:57] + "...",
                                size=11,
                                color=ft.Colors.GREY_400,
                            ),
                        ], spacing=2, tight=True),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        on_click=lambda _, p=path_value: copy_and_close(p),
                        ink=True,
                        border_radius=4,
                        on_hover=lambda e: self._on_menu_item_hover(e),
                    )
                )
                if format_name != list(path_formats.keys())[-1]:
                    submenu_items.append(ft.Container(height=1, bgcolor=ft.Colors.OUTLINE_VARIANT))
            
            # 计算子菜单的智能位置
            submenu_width = 280
            # 更精确的高度估算：标题行(20) + 路径行(18) + padding(16) + 分隔线(1)
            item_height = 55
            submenu_height = len(path_formats) * item_height + 8  # +8 是容器padding
            
            # 默认在主菜单右侧显示（使用调整后的主菜单位置）
            submenu_left = main_menu_left + main_menu_width + 10
            submenu_top = main_menu_top - 5
            
            # 检查是否超出右边界
            if submenu_left + submenu_width > view_width:
                # 超出右边界，显示在主菜单左侧
                submenu_left = main_menu_left - submenu_width - 10
                # 如果左侧也不够，就尽量靠右但不超出
                if submenu_left < 0:
                    submenu_left = max(10, view_width - submenu_width - 10)
            
            # 计算可用的垂直空间
            available_height = view_height - 60  # 留出上下边距
            need_scroll = submenu_height > available_height
            
            # 检查是否超出底部边界
            if submenu_top + submenu_height > view_height - 20:
                if need_scroll:
                    # 需要滚动时，调整到合适的位置
                    submenu_top = max(20, min(submenu_top, view_height - available_height - 20))
                else:
                    # 不需要滚动，向上调整到能完整显示的位置
                    submenu_top = max(20, view_height - submenu_height - 20)
            
            # 确保不超出顶部
            if submenu_top < 20:
                submenu_top = 20
            
            # 如果计算后的高度仍然可能超出，强制限制
            max_allowed_height = view_height - submenu_top - 20
            if submenu_height > max_allowed_height:
                need_scroll = True
                available_height = max_allowed_height
            
            # 创建子菜单容器
            submenu = ft.Container(
                ref=self.current_submenu_ref,
                content=ft.Column(
                    submenu_items, 
                    spacing=0, 
                    tight=True,
                    scroll=ft.ScrollMode.AUTO if need_scroll else ft.ScrollMode.HIDDEN,  # 只在需要时启用滚动
                ),
                bgcolor=ft.Colors.SURFACE,
                border=ft.border.all(1, ft.Colors.OUTLINE),
                border_radius=8,
                padding=4,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                ),
                width=submenu_width,
                height=min(submenu_height, available_height) if need_scroll else None,  # 只在需要时限制高度
                left=submenu_left,
                top=submenu_top,
                visible=True,
            )
            
            # 添加子菜单到 Stack
            if self.floating_menu_ref.current and self.floating_menu_ref.current.content:
                stack = self.floating_menu_ref.current.content
                if isinstance(stack, ft.Stack):
                    # 移除旧的子菜单（如果存在）
                    stack.controls = [c for c in stack.controls if not (hasattr(c, 'ref') and c.ref == self.current_submenu_ref)]
                    # 添加新的子菜单
                    stack.controls.append(submenu)
                    self.floating_menu_ref.current.update()
        
        def hide_path_submenu(e):
            """隐藏路径格式子菜单。"""
            if self.floating_menu_ref.current and self.floating_menu_ref.current.content:
                stack = self.floating_menu_ref.current.content
                if isinstance(stack, ft.Stack):
                    # 移除子菜单
                    stack.controls = [c for c in stack.controls if not (hasattr(c, 'ref') and c.ref == self.current_submenu_ref)]
                    self.floating_menu_ref.current.update()
        
        # 创建主菜单项
        menu_items = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.COPY, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text("复制路径", size=13, expand=True),
                    ft.Icon(ft.Icons.ARROW_RIGHT, size=16, color=ft.Colors.GREY_500),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                on_click=lambda _: copy_and_close(node.full_path),  # 点击直接复制简单格式
                ink=True,
                border_radius=4,
                on_hover=lambda e: (self._on_menu_item_hover(e), show_path_submenu(e) if e.data == "true" else hide_path_submenu(e)),
            ),
            ft.Container(height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.COPY, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text("复制键", size=13),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                on_click=lambda _: copy_and_close(str(node.key)),
                ink=True,
                border_radius=4,
                on_hover=lambda e: (self._on_menu_item_hover(e), hide_path_submenu(e)),
            ),
            ft.Container(height=1, bgcolor=ft.Colors.OUTLINE_VARIANT),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.COPY, size=16, color=ft.Colors.ON_SURFACE),
                    ft.Text("复制值", size=13),
                ], spacing=8),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                on_click=lambda _: copy_value_and_close(),
                ink=True,
                border_radius=4,
                on_hover=lambda e: (self._on_menu_item_hover(e), hide_path_submenu(e)),
            ),
        ], spacing=0, tight=True)
        
        # 创建菜单容器（使用预计算的位置）
        menu_container = ft.Container(
            content=menu_items,
            bgcolor=ft.Colors.SURFACE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            padding=4,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=8,
                color=ft.Colors.with_opacity(0.2, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            width=main_menu_width,
            left=main_menu_left,
            top=main_menu_top,
        )
        
        # 创建透明背景覆盖层（点击关闭菜单）
        overlay = ft.GestureDetector(
            content=ft.Container(expand=True),
            on_tap=close_menu,  # 左键关闭
            on_secondary_tap_up=close_menu,  # 右键关闭
        )
        
        # 更新浮动菜单的内容为 Stack，包含覆盖层和菜单
        self.floating_menu_ref.current.content = ft.Stack([
            overlay,
            menu_container,
        ])
        self.floating_menu_ref.current.visible = True
        self.floating_menu_ref.current.update()
    
    def _on_menu_item_hover(self, e):
        """菜单项悬停效果。"""
        if e.data == "true":
            e.control.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
        else:
            e.control.bgcolor = None
        e.control.update()
    
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
                node = JsonTreeNode(key, value, level=0, page=self.page, view=self)
                self.tree_view.current.controls.append(node)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                node = JsonTreeNode(f"[{idx}]", item, level=0, page=self.page, view=self)
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
