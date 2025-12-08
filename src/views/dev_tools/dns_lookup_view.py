# -*- coding: utf-8 -*-
"""DNS查询工具视图模块。

提供多种DNS记录类型查询、批量查询、指定DNS服务器等功能。
"""

import asyncio
import socket
from typing import Callable, Optional, List, Dict, Any
import dns.resolver
import dns.reversename

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class DnsLookupView(ft.Container):
    """DNS查询工具视图类。"""
    
    # DNS记录类型
    # 将特殊操作也作为类型添加到列表中，方便统一处理
    RECORD_TYPES = [
        "A", "AAAA", "CNAME", "MX", "TXT", 
        "NS", "SOA", "PTR", "SRV", "CAA",
        "ALL", # 全记录查询
        "REVERSE" # 反向查询
    ]
    
    TYPE_LABELS = {
        "A": "A (IPv4)",
        "AAAA": "AAAA (IPv6)",
        "CNAME": "CNAME (别名)",
        "MX": "MX (邮件)",
        "TXT": "TXT (文本)",
        "NS": "NS (域名服务器)",
        "SOA": "SOA (起始授权)",
        "PTR": "PTR (反向解析)",
        "SRV": "SRV (服务)",
        "CAA": "CAA (证书授权)",
        "ALL": "全记录查询 (All Types)",
        "REVERSE": "IP反向查询 (Reverse)"
    }
    
    # 常用DNS服务器
    DNS_SERVERS = {
        "系统默认": "",
        "Google DNS": "8.8.8.8",
        "Cloudflare DNS": "1.1.1.1",
        "阿里DNS": "223.5.5.5",
        "腾讯DNS": "119.29.29.29",
        "114DNS": "114.114.114.114",
        "OpenDNS": "208.67.222.222",
        "Quad9": "9.9.9.9",
        "AdGuard": "94.140.14.14",
    }
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化DNS查询工具视图。"""
        super().__init__()
        self.page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 控件引用
        self.record_type = ft.Ref[ft.Dropdown]()
        self.dns_server_input = ft.Ref[ft.TextField]() # 改为输入框
        self.input_text = ft.Ref[ft.TextField]()
        self.output_text = ft.Ref[ft.TextField]()
        self.progress_bar = ft.Ref[ft.ProgressBar]()
        self.status_text = ft.Ref[ft.Text]()
        
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
                ft.Text("DNS 查询工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 构建DNS服务器选择菜单项
        dns_menu_items = []
        for name, ip in self.DNS_SERVERS.items():
            text = name
            if ip:
                text = f"{name} ({ip})"
            
            # 使用闭包捕获 ip
            def on_click_handler(e, ip_val=ip):
                self._on_dns_server_select(ip_val)
                
            dns_menu_items.append(
                ft.PopupMenuItem(
                    text=text,
                    on_click=on_click_handler
                )
            )

        # 控制栏
        controls_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CATEGORY, color=ft.Colors.PRIMARY, size=20),
                                ft.Dropdown(
                                    ref=self.record_type,
                                    label="查询类型",
                                    width=220,
                                    options=[
                                        ft.dropdown.Option(k, text=v) 
                                        for k, v in self.TYPE_LABELS.items()
                                    ],
                                    value="A",
                                    border=ft.InputBorder.OUTLINE,
                                    dense=True,
                                    on_change=self._on_type_change,
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.DNS, color=ft.Colors.PRIMARY, size=20),
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            ft.TextField(
                                                ref=self.dns_server_input,
                                                label="DNS服务器",
                                                hint_text="留空使用系统默认",
                                                width=200,
                                                border=ft.InputBorder.OUTLINE,
                                                dense=True,
                                            ),
                                            ft.PopupMenuButton(
                                                icon=ft.Icons.ARROW_DROP_DOWN,
                                                tooltip="常用DNS服务器",
                                                items=dns_menu_items,
                                            ),
                                        ],
                                        spacing=0,
                                    ),
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        text="开始查询",
                        icon=ft.Icons.PLAY_ARROW,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=24, vertical=20),
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                        ),
                        on_click=lambda _: self.page.run_task(self._on_query),
                    ),
                    ft.OutlinedButton(
                        text="清空",
                        icon=ft.Icons.CLEAR,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.padding.symmetric(horizontal=16, vertical=20),
                        ),
                        on_click=self._on_clear,
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=ft.padding.symmetric(vertical=10),
        )
        
        # 输入区域
        input_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INPUT, size=16, color=ft.Colors.OUTLINE),
                            ft.Text("输入列表 (每行一个)", weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                icon_size=16,
                                tooltip="复制输入",
                                on_click=lambda _: self._copy_text(self.input_text.current.value),
                            ),
                        ],
                    ),
                    ft.TextField(
                        ref=self.input_text,
                        multiline=True,
                        min_lines=20,
                        hint_text="请输入域名 (例如: google.com)\n支持批量输入，每行一个",
                        text_size=13,
                        border=ft.InputBorder.OUTLINE,
                        expand=True,
                        keyboard_type=ft.KeyboardType.MULTILINE,
                    ),
                ],
                spacing=5,
                expand=True,
            ),
            expand=1,
        )
        
        # 输出区域
        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.OUTPUT, size=16, color=ft.Colors.OUTLINE),
                            ft.Text("查询结果", weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            ft.Text(ref=self.status_text, size=12, color=ft.Colors.OUTLINE),
                            ft.IconButton(
                                icon=ft.Icons.COPY,
                                icon_size=16,
                                tooltip="复制结果",
                                on_click=lambda _: self._copy_text(self.output_text.current.value),
                            ),
                        ],
                    ),
                    ft.ProgressBar(
                        ref=self.progress_bar,
                        value=0,
                        visible=False,
                        bar_height=2,
                    ),
                    ft.TextField(
                        ref=self.output_text,
                        multiline=True,
                        min_lines=20,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.OUTLINE,
                        expand=True,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        text_style=ft.TextStyle(font_family="Consolas,Monospace"),
                    ),
                ],
                spacing=5,
                expand=True,
            ),
            expand=1,
        )
        
        # 内容区域
        content_area = ft.Row(
            controls=[
                input_section,
                ft.VerticalDivider(width=1, color=ft.Colors.OUTLINE_VARIANT),
                output_section,
            ],
            expand=True,
            spacing=PADDING_MEDIUM,
        )
        
        # 主布局
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                controls_bar,
                content_area,
            ],
            spacing=0,
            expand=True,
        )

    def _on_dns_server_select(self, ip: str):
        """当从菜单选择DNS服务器时。"""
        # 如果是None或空字符串，清空输入框
        self.dns_server_input.current.value = ip if ip else ""
        self.dns_server_input.current.update()

    def _on_type_change(self, e):
        """当查询类型改变时，更新提示文本。"""
        current_type = self.record_type.current.value
        if current_type == "REVERSE":
            self.input_text.current.hint_text = "请输入IP地址 (例如: 8.8.8.8)\n支持批量输入，每行一个"
        else:
            self.input_text.current.hint_text = "请输入域名 (例如: google.com)\n支持批量输入，每行一个"
        self.input_text.current.update()

    def _on_clear(self, e):
        """清空输入和输出。"""
        self.input_text.current.value = ""
        self.output_text.current.value = ""
        self.status_text.current.value = ""
        self.progress_bar.current.visible = False
        self.update()

    def _copy_text(self, text: str):
        """复制文本到剪贴板。"""
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        self.page.set_clipboard(text)
        self._show_snack("已复制到剪贴板")

    def _get_resolver(self, dns_server_ip: str) -> dns.resolver.Resolver:
        """获取DNS解析器。"""
        resolver = dns.resolver.Resolver()
        
        # 设置DNS服务器
        if dns_server_ip and dns_server_ip.strip():
            # 支持多个IP，用逗号或空格分隔
            ips = [ip.strip() for ip in dns_server_ip.replace(',', ' ').split() if ip.strip()]
            if ips:
                resolver.nameservers = ips
        
        # 设置超时
        resolver.timeout = 5
        resolver.lifetime = 5
        
        return resolver

    async def _query_dns(self, target: str, record_type: str, resolver: dns.resolver.Resolver) -> Dict[str, Any]:
        """执行单个DNS查询。"""
        result = {
            "success": False,
            "records": [],
            "error": None,
            "ttl": None,
        }
        
        try:
            # 特殊处理：反向查询
            query_target = target
            query_type = record_type
            
            if record_type == "REVERSE":
                try:
                    query_target = str(dns.reversename.from_address(target))
                    query_type = "PTR"
                except Exception:
                    result["error"] = "无效的IP地址"
                    return result
            
            # 在线程池中执行查询
            loop = asyncio.get_event_loop()
            answers = await loop.run_in_executor(
                None, 
                resolver.resolve, 
                query_target, 
                query_type
            )
            
            result["success"] = True
            result["ttl"] = answers.rrset.ttl if answers.rrset else None
            
            for rdata in answers:
                # 格式化不同类型的记录
                if query_type in ["A", "AAAA", "NS", "CNAME", "PTR"]:
                    result["records"].append(str(rdata.target) if hasattr(rdata, 'target') else str(rdata))
                elif query_type == "MX":
                    result["records"].append(f"{rdata.preference} {rdata.exchange}")
                elif query_type == "TXT":
                    txt_data = " ".join([s.decode() if isinstance(s, bytes) else str(s) for s in rdata.strings])
                    result["records"].append(txt_data)
                elif query_type == "SOA":
                    soa_info = (
                        f"主DNS: {rdata.mname} 管理员: {rdata.rname} "
                        f"序列号: {rdata.serial} TTL: {rdata.minimum}"
                    )
                    result["records"].append(soa_info)
                elif query_type == "SRV":
                    result["records"].append(f"{rdata.priority} {rdata.weight} {rdata.port} {rdata.target}")
                elif query_type == "CAA":
                    result["records"].append(f"{rdata.flags} {rdata.tag} {rdata.value}")
                else:
                    result["records"].append(str(rdata))
                    
        except dns.resolver.NXDOMAIN:
            result["error"] = "域名不存在"
        except dns.resolver.NoAnswer:
            result["error"] = "无记录"
        except dns.resolver.Timeout:
            result["error"] = "查询超时"
        except dns.resolver.NoNameservers:
            result["error"] = "DNS服务器无响应"
        except Exception as e:
            result["error"] = str(e)
            
        return result

    async def _on_query(self):
        """执行查询任务。"""
        input_val = self.input_text.current.value
        if not input_val or not input_val.strip():
            self._show_snack("请输入查询内容", error=True)
            return

        # 准备数据
        targets = [line.strip() for line in input_val.split('\n') if line.strip()]
        record_type = self.record_type.current.value
        dns_server = self.dns_server_input.current.value # 使用输入框的值
        
        try:
            resolver = self._get_resolver(dns_server)
        except Exception as e:
             self._show_snack(f"DNS服务器地址格式错误: {str(e)}", error=True)
             return
        
        # UI初始化
        self.output_text.current.value = f"正在查询 {len(targets)} 个目标...\n"
        self.output_text.current.value += "=" * 50 + "\n\n"
        self.progress_bar.current.visible = True
        self.progress_bar.current.value = 0
        self.update()
        
        results_log = []
        success_count = 0
        
        # 确定需要查询的类型列表
        types_to_query = []
        if record_type == "ALL":
            # 排除特殊类型
            types_to_query = [t for t in self.RECORD_TYPES if t not in ["ALL", "REVERSE"]]
        else:
            types_to_query = [record_type]

        # 执行查询
        for i, target in enumerate(targets):
            target_log = [f"[{target}]"]
            has_success = False
            
            for q_type in types_to_query:
                # 记录类型前缀（如果是全量查询）
                prefix = f"[{q_type}] " if record_type == "ALL" else ""
                
                # 执行查询
                res = await self._query_dns(target, q_type, resolver)
                
                if res["success"]:
                    has_success = True
                    for record in res["records"]:
                        target_log.append(f"  {prefix}{record}")
                else:
                    # 全量查询时，忽略"无记录"的错误，只显示其他错误
                    if record_type != "ALL" or res["error"] not in ["无记录", "域名不存在"]:
                        target_log.append(f"  Error: {prefix}{res['error']}")
            
            if has_success:
                success_count += 1
            
            target_log.append("") # 空行分隔
            results_log.extend(target_log)
            
            # 实时更新UI
            self.progress_bar.current.value = (i + 1) / len(targets)
            self.status_text.current.value = f"进度: {i + 1}/{len(targets)}"
            
            # 增量更新输出（避免文本过长导致卡顿，每5个或者结束时更新一次全文）
            # 注意：TextField不支持append，只能替换。对于大量文本，这可能有效率问题。
            # 优化：仅在必要时更新
            if i % 1 == 0 or i == len(targets) - 1:
                current_log = "\n".join(results_log)
                server_display = dns_server if dns_server else "系统默认"
                header = f"查询概览: 总计 {len(targets)} | 成功 {success_count}\n"
                header += f"配置信息: 类型={self.TYPE_LABELS.get(record_type, record_type)} | 服务器={server_display}\n"
                header += "=" * 50 + "\n\n"
                self.output_text.current.value = header + current_log
                self.update()
        
        self.progress_bar.current.visible = False
        self._show_snack("查询完成")
        self.update()

    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**DNS查询工具使用说明**

**1. 基础查询**
- 选择记录类型（如 A, CNAME, MX 等）
- 输入域名（每行一个）
- 点击"开始查询"

**2. 自定义DNS服务器**
- 默认使用系统DNS
- 可以在"DNS服务器"输入框中直接输入IP（如 1.1.1.1）
- 点击右侧的小箭头，可以快速选择常用DNS
- 支持输入多个DNS服务器IP（用空格或逗号分隔）

**3. 批量查询**
- 在输入框中粘贴多个域名
- 系统会自动逐个查询并显示结果
- 适合批量检查域名解析状态

**4. 全记录查询 (ALL)**
- 选择 "全记录查询 (All Types)"
- 系统会尝试查询所有常见的DNS记录类型
- 自动过滤掉无记录的类型，展示完整的DNS配置

**5. 反向查询 (REVERSE)**
- 选择 "IP反向查询 (Reverse)"
- 在输入框中输入IP地址（每行一个）
- 系统会查询对应的PTR记录（IP -> 域名）

**支持的记录类型：**
- **A**: IPv4地址
- **AAAA**: IPv6地址
- **CNAME**: 别名记录
- **MX**: 邮件服务器
- **TXT**: 文本记录（常用于SPF/验证）
- **NS**: 域名服务器
- **SOA**: 起始授权记录
- **PTR**: 反向解析
- **SRV**: 服务记录
- **CAA**: 证书授权

**提示：**
- 指定DNS服务器可以帮助您排查解析传播问题
- 结果支持一键复制，方便分享或记录
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
                width=550,
                height=500,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self.page.close(dialog)),
            ],
        )
        
        self.page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self.page.snack_bar.open = True
        self.page.update()
