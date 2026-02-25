# -*- coding: utf-8 -*-
"""JWT 工具视图模块。

提供 JWT 解析、验证功能。
"""

import base64
import json
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class JwtToolView(ft.Container):
    """JWT 工具视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化 JWT 工具视图。
        
        Args:
            page: Flet 页面对象
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self._page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 控件引用
        self.jwt_input = ft.Ref[ft.TextField]()
        self.header_output = ft.Ref[ft.TextField]()
        self.payload_output = ft.Ref[ft.TextField]()
        self.signature_output = ft.Ref[ft.TextField]()
        
        self._build_ui()
    
    def _build_ui(self):
        """构建用户界面。"""
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self._on_back_click(),
                ),
                ft.Text("JWT 工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # JWT 输入区
        jwt_input_section = ft.Column(
            controls=[
                ft.Text("JWT Token", weight=ft.FontWeight.BOLD, size=16),
                ft.Container(
                    content=ft.TextField(
                        ref=self.jwt_input,
                        multiline=True,
                        min_lines=4,
                        hint_text='粘贴 JWT Token 到这里...\n例如: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c',
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            content="解析 JWT",
                            icon=ft.Icons.LOCK_OPEN,
                            on_click=self._parse_jwt,
                        ),
                        ft.OutlinedButton(
                            content="清空",
                            icon=ft.Icons.CLEAR,
                            on_click=self._clear_all,
                        ),
                    ],
                    spacing=PADDING_SMALL,
                ),
            ],
            spacing=5,
        )
        
        # Header 显示
        header_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Header (头部)", weight=ft.FontWeight.BOLD, size=15),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.header_output.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.header_output,
                        multiline=True,
                        min_lines=6,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                ),
            ],
            spacing=5,
        )
        
        # Payload 显示
        payload_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Payload (载荷)", weight=ft.FontWeight.BOLD, size=15),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.payload_output.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.payload_output,
                        multiline=True,
                        min_lines=8,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                ),
            ],
            spacing=5,
        )
        
        # Signature 显示
        signature_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Signature (签名)", weight=ft.FontWeight.BOLD, size=15),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.signature_output.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.signature_output,
                        multiline=True,
                        min_lines=3,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                ),
            ],
            spacing=5,
        )
        
        # 布局
        content_area = ft.Column(
            controls=[
                jwt_input_section,
                ft.Container(height=PADDING_SMALL),
                header_section,
                ft.Container(height=PADDING_SMALL),
                payload_section,
                ft.Container(height=PADDING_SMALL),
                signature_section,
            ],
            spacing=0,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        
        # 主列
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(),
                content_area,
            ],
            spacing=0,
            expand=True,
        )
        
        self.content = main_column
    
    def _parse_jwt(self, e):
        """解析 JWT Token。"""
        jwt_token = self.jwt_input.current.value
        if not jwt_token or not jwt_token.strip():
            self._show_snack("请输入 JWT Token", error=True)
            return
        
        try:
            # JWT 由三部分组成，用点分隔
            parts = jwt_token.strip().split('.')
            if len(parts) != 3:
                self._show_snack("无效的 JWT 格式（应该有三部分）", error=True)
                return
            
            # 解析 Header
            header_decoded = self._decode_base64url(parts[0])
            header_json = json.loads(header_decoded)
            header_formatted = json.dumps(header_json, indent=2, ensure_ascii=False)
            self.header_output.current.value = header_formatted
            
            # 解析 Payload
            payload_decoded = self._decode_base64url(parts[1])
            payload_json = json.loads(payload_decoded)
            
            # 格式化 Payload，并解析时间戳
            payload_formatted = self._format_payload(payload_json)
            self.payload_output.current.value = payload_formatted
            
            # 显示 Signature（Base64 编码）
            self.signature_output.current.value = parts[2]
            
            self.update()
            self._show_snack("JWT 解析成功")
            
        except Exception as e:
            self._show_snack(f"解析失败: {str(e)}", error=True)
    
    def _decode_base64url(self, data: str) -> str:
        """解码 Base64URL 编码的数据。"""
        # JWT 使用 Base64URL 编码，需要添加填充
        padding = 4 - len(data) % 4
        if padding != 4:
            data += '=' * padding
        
        # Base64URL 使用 - 和 _ 代替 + 和 /
        data = data.replace('-', '+').replace('_', '/')
        
        return base64.b64decode(data).decode('utf-8')
    
    def _format_payload(self, payload: dict) -> str:
        """格式化 Payload，解析时间戳等。"""
        from datetime import datetime
        
        formatted_lines = []
        formatted_lines.append(json.dumps(payload, indent=2, ensure_ascii=False))
        formatted_lines.append("\n" + "="*50)
        formatted_lines.append("时间戳解析:")
        formatted_lines.append("="*50 + "\n")
        
        # 常见的时间戳字段
        time_fields = ['iat', 'exp', 'nbf', 'auth_time']
        
        for field in time_fields:
            if field in payload:
                try:
                    timestamp = int(payload[field])
                    dt = datetime.fromtimestamp(timestamp)
                    field_name = {
                        'iat': 'Issued At (签发时间)',
                        'exp': 'Expiration Time (过期时间)',
                        'nbf': 'Not Before (生效时间)',
                        'auth_time': 'Auth Time (认证时间)',
                    }.get(field, field)
                    
                    formatted_lines.append(f"{field_name}:")
                    formatted_lines.append(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 检查是否过期
                    if field == 'exp':
                        now = datetime.now()
                        if dt < now:
                            formatted_lines.append(f"  ⚠️ 已过期")
                        else:
                            delta = dt - now
                            hours = delta.total_seconds() / 3600
                            if hours < 24:
                                formatted_lines.append(f"  ✓ 剩余 {hours:.1f} 小时")
                            else:
                                days = hours / 24
                                formatted_lines.append(f"  ✓ 剩余 {days:.1f} 天")
                    formatted_lines.append("")
                except Exception:
                    pass
        
        return '\n'.join(formatted_lines)
    
    def _clear_all(self, e):
        """清空所有内容。"""
        self.jwt_input.current.value = ""
        self.header_output.current.value = ""
        self.payload_output.current.value = ""
        self.signature_output.current.value = ""
        self.update()
    
    async def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        
        await ft.Clipboard().set(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**JWT 工具使用说明**

**功能：**
- 解析 JWT Token
- 查看 Header、Payload、Signature
- 自动解析时间戳字段
- 检查 Token 是否过期

**JWT 结构：**
JWT 由三部分组成，用点 (.) 分隔：
```
Header.Payload.Signature
```

**常见字段：**
- **iat**: Issued At - 签发时间
- **exp**: Expiration Time - 过期时间
- **nbf**: Not Before - 生效时间
- **sub**: Subject - 主题（用户 ID）
- **iss**: Issuer - 签发者
- **aud**: Audience - 受众

**使用步骤：**
1. 粘贴 JWT Token
2. 点击"解析 JWT"
3. 查看解析结果

**注意：**
此工具仅用于解析和查看 JWT 内容，
不进行签名验证。请勿在生产环境中
仅依赖客户端验证。
        """
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("使用说明"),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Markdown(
                            help_text,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=500,
                height=450,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self._page.close(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.open(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
