# -*- coding: utf-8 -*-
"""端口扫描工具视图模块。

提供端口检测、常用端口扫描、端口范围扫描等功能。
"""

import asyncio
import socket
from typing import Callable, Optional, List, Tuple

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class PortScannerView(ft.Container):
    """端口扫描工具视图类。"""
    
    # 常用端口定义
    COMMON_PORTS = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        5900: "VNC",
        6379: "Redis",
        8080: "HTTP-Proxy",
        8443: "HTTPS-Alt",
        27017: "MongoDB",
    }
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化端口扫描工具视图。
        
        Args:
            page: Flet 页面对象
            on_back: 返回回调函数（可选）
        """
        super().__init__()
        self._page = page
        self.on_back = on_back
        self.expand = True
        self.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 统一控件引用
        self.host_input = ft.Ref[ft.TextField]()
        self.mode_selector = ft.Ref[ft.Dropdown]()
        self.scan_btn = ft.Ref[ft.Button]()
        
        # 动态输入控件
        self.port_input = ft.Ref[ft.TextField]()      # 单个端口
        self.start_port_input = ft.Ref[ft.TextField]() # 范围起始
        self.end_port_input = ft.Ref[ft.TextField]()   # 范围结束
        self.port_list_input = ft.Ref[ft.TextField]()  # 自定义列表
        
        # 容器引用，用于控制显示隐藏
        self.single_input_container = ft.Ref[ft.Container]()
        self.range_input_container = ft.Ref[ft.Container]()
        self.custom_input_container = ft.Ref[ft.Container]()
        
        # 输出和进度
        self.progress_bar = ft.Ref[ft.ProgressBar]()
        self.log_output = ft.Ref[ft.TextField]()
        
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
                ft.Text("端口扫描工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 控制面板区域
        control_panel = ft.Container(
            content=ft.Column(
                controls=[
                    # 第一行：主机地址、模式选择、扫描按钮
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.host_input,
                                label="主机地址",
                                hint_text="example.com 或 192.168.1.1",
                                expand=True,
                                prefix_icon=ft.Icons.DNS,
                                height=45,
                                text_size=14,
                                content_padding=10,
                            ),
                            ft.Dropdown(
                                ref=self.mode_selector,
                                label="扫描模式",
                                width=180,
                                options=[
                                    ft.dropdown.Option("common", "常用端口 (快速)"),
                                    ft.dropdown.Option("single", "单个端口"),
                                    ft.dropdown.Option("range", "端口范围"),
                                    ft.dropdown.Option("custom", "自定义列表"),
                                ],
                                value="common",
                                on_select=self._on_mode_change,
                                text_size=14,
                                content_padding=10,
                            ),
                            ft.Button(
                                ref=self.scan_btn,
                                content="开始扫描",
                                icon=ft.Icons.PLAY_ARROW,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=20,
                                ),
                                on_click=lambda _: self._page.run_task(self._handle_scan),
                                height=45,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                    
                    # 第二行：动态输入区域
                    # 1. 单个端口输入
                    ft.Container(
                        ref=self.single_input_container,
                        visible=False,
                        content=ft.Row(
                            controls=[
                                ft.TextField(
                                    ref=self.port_input,
                                    label="目标端口",
                                    hint_text="例如: 80",
                                    width=150,
                                    keyboard_type=ft.KeyboardType.NUMBER,
                                    height=40,
                                    text_size=14,
                                    content_padding=10,
                                    prefix_icon=ft.Icons.TAG,
                                ),
                                ft.Text("请输入要检测的单个端口号", color=ft.Colors.OUTLINE),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    
                    # 2. 范围输入
                    ft.Container(
                        ref=self.range_input_container,
                        visible=False,
                        content=ft.Row(
                            controls=[
                                ft.TextField(
                                    ref=self.start_port_input,
                                    label="起始端口",
                                    value="1",
                                    width=120,
                                    keyboard_type=ft.KeyboardType.NUMBER,
                                    height=40,
                                    text_size=14,
                                    content_padding=10,
                                ),
                                ft.Text("-", size=20, weight=ft.FontWeight.BOLD),
                                ft.TextField(
                                    ref=self.end_port_input,
                                    label="结束端口",
                                    value="1000",
                                    width=120,
                                    keyboard_type=ft.KeyboardType.NUMBER,
                                    height=40,
                                    text_size=14,
                                    content_padding=10,
                                ),
                                ft.Text("建议范围不超过 1000 个端口", color=ft.Colors.OUTLINE),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                    
                    # 3. 自定义列表输入
                    ft.Container(
                        ref=self.custom_input_container,
                        visible=False,
                        content=ft.TextField(
                            ref=self.port_list_input,
                            label="端口列表",
                            hint_text="例如: 80, 443, 8080, 3306 (使用逗号或空格分隔)",
                            expand=True,
                            height=40,
                            text_size=14,
                            content_padding=10,
                            prefix_icon=ft.Icons.LIST_ALT,
                        ),
                    ),
                ],
                spacing=PADDING_MEDIUM,
            ),
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )

        # 输出区域
        output_area = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TERMINAL, size=20),
                            ft.Text("扫描日志", weight=ft.FontWeight.BOLD),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLEAR_ALL,
                                tooltip="清空日志",
                                icon_size=20,
                                on_click=self._clear_log,
                            ),
                        ],
                    ),
                    ft.ProgressBar(
                        ref=self.progress_bar,
                        value=0,
                        visible=False,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                    ),
                    ft.Container(
                        content=ft.TextField(
                            ref=self.log_output,
                            multiline=True,
                            read_only=True,
                            text_size=13,
                            border=ft.InputBorder.NONE,
                            text_style=ft.TextStyle(font_family="Consolas,Monaco,Courier New,monospace"),
                            cursor_color=ft.Colors.PRIMARY,
                        ),
                        expand=True,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=8,
                        padding=PADDING_SMALL,
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            expand=True,
        )

        # 主布局
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(height=1),
                control_panel,
                ft.Container(height=PADDING_SMALL),
                output_area,
            ],
            spacing=PADDING_SMALL,
            expand=True,
        )

    def _on_mode_change(self, e):
        """处理模式切换，显示对应的输入框。"""
        mode = self.mode_selector.current.value
        
        self.single_input_container.current.visible = (mode == "single")
        self.range_input_container.current.visible = (mode == "range")
        self.custom_input_container.current.visible = (mode == "custom")
        
        self.update()

    def _clear_log(self, e):
        """清空日志。"""
        if self.log_output.current:
            self.log_output.current.value = ""
            self.update()

    async def _handle_scan(self):
        """处理扫描按钮点击。"""
        mode = self.mode_selector.current.value
        
        # 禁用按钮防止重复点击
        self.scan_btn.current.disabled = True
        self.update()
        
        try:
            if mode == "single":
                await self._check_single_port()
            elif mode == "range":
                await self._scan_port_range()
            elif mode == "custom":
                await self._scan_custom_ports()
            elif mode == "common":
                await self._scan_common_ports()
        finally:
            # 恢复按钮
            if self.scan_btn.current:
                self.scan_btn.current.disabled = False
                self.update()

    async def _check_port(self, host: str, port: int, timeout: float = 3) -> Tuple[bool, float]:
        """检测单个端口。
        
        Returns:
            (是否开放, 响应时间ms)
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            # 使用异步方式连接，避免阻塞UI
            try:
                await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                end_time = asyncio.get_event_loop().time()
                response_time = (end_time - start_time) * 1000
                return (True, response_time)
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                return (False, 0)
        except Exception:
            return (False, 0)
    
    async def _check_single_port(self):
        """检测单个端口。"""
        host = self.host_input.current.value
        port_str = self.port_input.current.value
        
        if not host or not host.strip():
            self._show_snack("请输入主机地址", error=True)
            return
        
        if not port_str or not port_str.strip():
            self._show_snack("请输入端口号", error=True)
            return
        
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                self._show_snack("端口号必须在 1-65535 之间", error=True)
                return
        except ValueError:
            self._show_snack("请输入有效的端口号", error=True)
            return
        
        self.log_output.current.value = f"正在检测 {host}:{port}...\n"
        self.update()
        
        is_open, response_time = await self._check_port(host, port)
        
        result_lines = []
        result_lines.append(f"主机: {host}")
        result_lines.append(f"端口: {port}")
        
        # 尝试获取服务名称
        service_name = self.COMMON_PORTS.get(port, "")
        if not service_name:
            try:
                service_name = socket.getservbyport(port)
            except Exception:
                service_name = "未知服务"
        
        result_lines.append(f"服务: {service_name}\n")
        result_lines.append("="*50 + "\n")
        
        if is_open:
            result_lines.append("✅ 端口开放")
            result_lines.append(f"响应时间: {response_time:.2f} ms")
        else:
            result_lines.append("❌ 端口关闭或无法访问")
        
        self.log_output.current.value = '\n'.join(result_lines)
        self.update()
        self._show_snack("端口检测完成")
    
    async def _scan_custom_ports(self):
        """扫描批量指定的端口。"""
        host = self.host_input.current.value
        ports_str = self.port_list_input.current.value
        
        if not host or not host.strip():
            self._show_snack("请输入主机地址", error=True)
            return
        
        if not ports_str or not ports_str.strip():
            self._show_snack("请输入端口列表", error=True)
            return
        
        # 解析端口列表（支持逗号、空格分隔）
        ports_str = ports_str.replace(',', ' ')
        port_numbers = []
        
        try:
            for p in ports_str.split():
                p = p.strip()
                if p:
                    port = int(p)
                    if 1 <= port <= 65535:
                        port_numbers.append(port)
                    else:
                        self._show_snack(f"端口 {port} 超出范围 (1-65535)", error=True)
                        return
        except ValueError:
            self._show_snack("端口列表格式错误，请使用逗号或空格分隔", error=True)
            return
        
        if not port_numbers:
            self._show_snack("没有有效的端口号", error=True)
            return
        
        # 去重并排序
        port_numbers = sorted(set(port_numbers))
        
        self.log_output.current.value = f"正在扫描 {host} 的 {len(port_numbers)} 个端口...\n\n"
        self.progress_bar.current.value = 0
        self.progress_bar.current.visible = True
        self.update()
        
        open_ports = []
        closed_ports = []
        
        for i, port in enumerate(port_numbers, 1):
            is_open, response_time = await self._check_port(host, port, timeout=2)
            
            # 获取服务名
            service_name = self.COMMON_PORTS.get(port, "")
            if not service_name:
                try:
                    service_name = socket.getservbyport(port)
                except Exception:
                    service_name = "未知"
            
            if is_open:
                open_ports.append((port, service_name, response_time))
            else:
                closed_ports.append((port, service_name))
            
            # 更新进度
            self.progress_bar.current.value = i / len(port_numbers)
            
            # 实时更新日志
            result_lines = [f"扫描进度: {i}/{len(port_numbers)}\n"]
            
            if open_ports:
                result_lines.append("✅ 开放的端口:")
                for p, s, rt in open_ports:
                    result_lines.append(f"  • {p:5d} - {s:15s} ({rt:.0f}ms)")
            
            result_lines.append("")
            
            if closed_ports:
                result_lines.append(f"❌ 关闭的端口: ({len(closed_ports)}个)")
                for p, s in closed_ports[:5]:
                    result_lines.append(f"  • {p:5d} - {s}")
                if len(closed_ports) > 5:
                    result_lines.append(f"  ... 还有 {len(closed_ports) - 5} 个")
            
            self.log_output.current.value = '\n'.join(result_lines)
            self.update()
        
        self.progress_bar.current.visible = False
        
        # 添加统计
        result_lines.append("\n" + "="*50)
        result_lines.append(f"\n📊 统计: 开放 {len(open_ports)} / 关闭 {len(closed_ports)} / 总计 {len(port_numbers)}")
        
        self.log_output.current.value = '\n'.join(result_lines)
        self.update()
        self._show_snack(f"扫描完成: 发现 {len(open_ports)} 个开放端口")
    
    async def _scan_common_ports(self):
        """扫描常用端口。"""
        host = self.host_input.current.value
        
        if not host or not host.strip():
            self._show_snack("请输入主机地址", error=True)
            return
        
        self.log_output.current.value = f"正在扫描 {host} 的常用端口...\n\n"
        self.progress_bar.current.value = 0
        self.progress_bar.current.visible = True
        self.update()
        
        open_ports = []
        closed_ports = []
        
        total_ports = len(self.COMMON_PORTS)
        current_count = 0
        
        for port, service in sorted(self.COMMON_PORTS.items()):
            is_open, response_time = await self._check_port(host, port, timeout=2)
            
            current_count += 1
            self.progress_bar.current.value = current_count / total_ports
            
            if is_open:
                open_ports.append((port, service, response_time))
            else:
                closed_ports.append((port, service))
            
            # 实时更新结果
            result_lines = [f"扫描进度: {current_count}/{total_ports}\n"]
            
            if open_ports:
                result_lines.append("✅ 开放的端口:")
                for p, s, rt in open_ports:
                    result_lines.append(f"  • {p:5d} - {s:15s} ({rt:.0f}ms)")
            
            result_lines.append("")
            
            if closed_ports:
                result_lines.append(f"❌ 关闭的端口: ({len(closed_ports)}个)")
                # 只显示前5个关闭的端口
                for p, s in closed_ports[:5]:
                    result_lines.append(f"  • {p:5d} - {s}")
                if len(closed_ports) > 5:
                    result_lines.append(f"  ... 还有 {len(closed_ports) - 5} 个")
            
            self.log_output.current.value = '\n'.join(result_lines)
            self.update()
        
        self.progress_bar.current.visible = False
        
        # 添加统计
        result_lines.append("\n" + "="*50)
        result_lines.append(f"\n📊 统计: 开放 {len(open_ports)} / 关闭 {len(closed_ports)} / 总计 {total_ports}")
        
        self.log_output.current.value = '\n'.join(result_lines)
        self.update()
        self._show_snack(f"扫描完成: 发现 {len(open_ports)} 个开放端口")
    
    async def _scan_port_range(self):
        """扫描端口范围。"""
        host = self.host_input.current.value
        start_str = self.start_port_input.current.value
        end_str = self.end_port_input.current.value
        
        if not host or not host.strip():
            self._show_snack("请输入主机地址", error=True)
            return
        
        try:
            start_port = int(start_str)
            end_port = int(end_str)
            
            if start_port < 1 or end_port > 65535:
                self._show_snack("端口范围必须在 1-65535 之间", error=True)
                return
            
            if start_port > end_port:
                self._show_snack("起始端口不能大于结束端口", error=True)
                return
            
            if end_port - start_port > 1000:
                self._show_snack("端口范围不能超过 1000", error=True)
                return
        except ValueError:
            self._show_snack("请输入有效的端口号", error=True)
            return
        
        self.log_output.current.value = f"正在扫描 {host} 端口 {start_port}-{end_port}...\n\n"
        self.progress_bar.current.value = 0
        self.progress_bar.current.visible = True
        self.update()
        
        open_ports = []
        total_ports = end_port - start_port + 1
        scanned = 0
        
        for port in range(start_port, end_port + 1):
            is_open, response_time = await self._check_port(host, port, timeout=1)
            
            if is_open:
                # 尝试获取服务名
                service_name = self.COMMON_PORTS.get(port, "")
                if not service_name:
                    try:
                        service_name = socket.getservbyport(port)
                    except Exception:
                        service_name = "未知"
                
                open_ports.append((port, service_name, response_time))
            
            scanned += 1
            
            # 更新进度
            self.progress_bar.current.value = scanned / total_ports
            
            # 每10个端口更新一次显示，或者发现开放端口时立即更新
            if scanned % 10 == 0 or is_open:
                result_lines = [f"扫描进度: {scanned}/{total_ports}\n"]
                
                if open_ports:
                    result_lines.append("✅ 发现的开放端口:")
                    for p, s, rt in open_ports:
                        result_lines.append(f"  • {p:5d} - {s:15s} ({rt:.0f}ms)")
                else:
                    result_lines.append("未发现开放端口...")
                
                self.log_output.current.value = '\n'.join(result_lines)
                self.update()
        
        # 完成
        self.progress_bar.current.visible = False
        
        result_lines = []
        if open_ports:
            result_lines.append("✅ 开放的端口:")
            for p, s, rt in open_ports:
                result_lines.append(f"  • {p:5d} - {s:15s} ({rt:.0f}ms)")
        else:
            result_lines.append("❌ 未发现开放端口")
        
        result_lines.append("\n" + "="*50)
        result_lines.append(f"\n📊 扫描范围: {start_port}-{end_port} ({total_ports} 个端口)")
        result_lines.append(f"📊 开放端口: {len(open_ports)} 个")
        
        self.log_output.current.value = '\n'.join(result_lines)
        self.update()
        self._show_snack(f"扫描完成: 发现 {len(open_ports)} 个开放端口")
    
    def _on_back_click(self):
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**端口扫描工具使用说明**

**1. 单个端口检测**
- 检测指定端口是否开放
- 显示响应时间
- 识别服务名称

**2. 批量指定端口**
- 自定义要扫描的端口列表
- 支持逗号或空格分隔
- 示例: `80,443,3306` 或 `80 443 3306`
- 自动去重和排序

**3. 常用端口扫描**
- 快速扫描 18 个常用端口
- 包括: HTTP(80), HTTPS(443), SSH(22), MySQL(3306) 等
- 显示开放/关闭状态

**4. 端口范围扫描**
- 自定义扫描端口范围
- 最多支持 1000 个端口
- 实时显示扫描进度
- 推荐范围: 1-1024 (系统端口)

**常用端口说明：**
- **20-21**: FTP
- **22**: SSH
- **80**: HTTP
- **443**: HTTPS
- **3306**: MySQL
- **3389**: RDP (远程桌面)
- **5432**: PostgreSQL
- **6379**: Redis
- **27017**: MongoDB

**注意事项：**
- 请勿对未授权的主机进行扫描
- 大范围扫描可能需要较长时间
- 防火墙可能阻止扫描
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
                ft.TextButton("关闭", on_click=lambda _: self._page.pop_dialog()),
            ],
        )
        
        self._page.show_dialog(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.show_dialog(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()
