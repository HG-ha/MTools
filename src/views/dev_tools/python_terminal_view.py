"""Python终端视图模块。

提供交互式Python终端功能，可调用内嵌的Python解释器。
"""

import code
import io
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional
from queue import Queue, Empty
import contextlib

import flet as ft

from constants import PADDING_LARGE, PADDING_MEDIUM, PADDING_SMALL, PADDING_XLARGE
from services import ConfigService


class PythonTerminalView(ft.Container):
    """Python终端视图类。
    
    提供Python交互式终端功能，包括：
    - 交互式Python REPL
    - 保持会话状态
    - 命令历史记录
    - 调用内嵌Python解释器
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化Python终端视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        
        # 获取Python解释器路径
        self.python_exe = self._get_python_executable()
        
        # 交互式解释器相关
        self.interpreter: Optional[code.InteractiveConsole] = None
        self.output_queue: Queue = Queue()
        self.running: bool = False
        self.is_frozen = getattr(sys, 'frozen', False)
        
        # 命令历史
        self.command_history: list = []
        self.history_index: int = -1
        
        # 创建UI组件
        self._build_ui()
        
        # 初始化Python解释器
        self._init_interpreter()
    
    def _get_python_executable(self) -> str:
        """获取Python解释器路径。
        
        Returns:
            Python解释器路径
        """
        if getattr(sys, 'frozen', False):
            # 打包后的环境
            exe_dir = Path(sys.executable).parent
            
            # 尝试不同的可能位置
            possible_paths = [
                exe_dir / "python.exe",
                exe_dir / "python" / "python.exe",
                exe_dir / "Python" / "python.exe",
                exe_dir.parent / "python" / "python.exe",
            ]
            
            for path in possible_paths:
                if path.exists():
                    return str(path)
            
            return sys.executable
        else:
            return sys.executable
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 返回按钮
        back_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_size=24,
            tooltip="返回",
            on_click=self._go_back,
        )
        
        # 标题
        title = ft.Text(
            "Python 交互式终端",
            size=28,
            weight=ft.FontWeight.BOLD,
        )
        
        # 清屏按钮
        clear_button = ft.IconButton(
            icon=ft.Icons.CLEAR_ALL_ROUNDED,
            icon_size=20,
            tooltip="清屏",
            on_click=self._clear_terminal,
        )
        
        # 重启按钮
        restart_button = ft.IconButton(
            icon=ft.Icons.RESTART_ALT_ROUNDED,
            icon_size=20,
            tooltip="重启终端",
            on_click=self._restart_terminal,
        )
        
        # 标题栏
        title_bar = ft.Container(
            content=ft.Row(
                controls=[
                    back_button,
                    title,
                    ft.Container(expand=True),  # 弹性空间
                    clear_button,
                    restart_button,
                ],
                spacing=PADDING_SMALL,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.only(
                left=PADDING_LARGE,
                right=PADDING_XLARGE,
                top=PADDING_LARGE,
                bottom=PADDING_MEDIUM,
            ),
        )
        
        # Python环境信息卡片
        python_info = self._create_python_info_card()
        
        # 终端输出区域（使用ListView实现滚动）
        self.terminal_output = ft.Column(
            controls=[],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            expand=True,
        )
        
        # 终端输出容器
        terminal_container = ft.Container(
            content=self.terminal_output,
            bgcolor=ft.Colors.BLACK,
            padding=PADDING_MEDIUM,
            border_radius=8,
            expand=True,
            height=500,  # 固定高度
        )
        
        # 命令输入区域
        self.command_input = ft.TextField(
            hint_text="输入Python命令（支持多行）...",
            multiline=True,
            min_lines=1,
            max_lines=10,
            text_style=ft.TextStyle(
                font_family="Consolas" if sys.platform == "win32" else "Monaco",
                size=14,
            ),
            border_color=ft.Colors.BLUE_400,
            expand=True,
        )
        
        # 执行按钮
        execute_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            tooltip="执行 (Ctrl+Enter)",
            on_click=self._on_command_submit,
            icon_color=ft.Colors.GREEN_400,
            bgcolor=ft.Colors.GREEN_900,
        )
        
        # 清空输入按钮
        clear_input_button = ft.IconButton(
            icon=ft.Icons.CLEAR_ROUNDED,
            tooltip="清空输入",
            on_click=self._clear_input,
            icon_size=20,
        )
        
        # 提示符
        prompt = ft.Text(
            ">>>",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_400,
            font_family="Consolas" if sys.platform == "win32" else "Monaco",
        )
        
        # 输入行
        input_row = ft.Row(
            controls=[
                prompt,
                self.command_input,
                ft.Column(
                    controls=[execute_button, clear_input_button],
                    spacing=4,
                ),
            ],
            spacing=PADDING_SMALL,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )
        
        # 快捷键提示
        hints = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.GREY_500),
                    ft.Text(
                        "提示: 点击▶执行 | Enter换行 | 支持多行代码输入",
                        size=12,
                        color=ft.Colors.GREY_600,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.symmetric(vertical=PADDING_SMALL),
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                title_bar,
                ft.Container(
                    content=ft.Column(
                        controls=[
                            python_info,
                            ft.Divider(height=20),
                            terminal_container,
                            input_row,
                            hints,
                        ],
                        spacing=PADDING_MEDIUM,
                        expand=True,
                    ),
                    padding=ft.padding.only(
                        left=PADDING_XLARGE,
                        right=PADDING_XLARGE,
                        bottom=PADDING_XLARGE,
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
    
    def _create_python_info_card(self) -> ft.Card:
        """创建Python环境信息卡片。
        
        Returns:
            环境信息卡片
        """
        python_version = sys.version.split()[0]
        is_frozen = getattr(sys, 'frozen', False)
        
        # 使用紧凑的横向布局
        info_row = ft.Row(
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.CODE_ROUNDED, size=18, color=ft.Colors.BLUE_400),
                    ft.Text("Python版本:", size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(python_version, size=13),
                ], spacing=6),
                ft.VerticalDivider(width=1),
                ft.Row([
                    ft.Icon(ft.Icons.FOLDER_ROUNDED, size=18, color=ft.Colors.ORANGE_400),
                    ft.Text("解释器:", size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        self.python_exe,
                        size=11,
                        selectable=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                ], spacing=6, expand=True),
                ft.VerticalDivider(width=1),
                ft.Row([
                    ft.Icon(ft.Icons.INFO_ROUNDED, size=18, color=ft.Colors.GREEN_400),
                    ft.Text("模式:", size=13, weight=ft.FontWeight.BOLD),
                    ft.Text("打包" if is_frozen else "开发", size=13),
                ], spacing=6),
            ],
            spacing=PADDING_MEDIUM,
            wrap=False,
        )
        
        return ft.Card(
            content=ft.Container(
                content=info_row,
                padding=PADDING_SMALL,
            ),
        )
    
    def _init_interpreter(self) -> None:
        """初始化Python交互式解释器。"""
        try:
            # 创建交互式控制台
            self.interpreter = code.InteractiveConsole()
            self.running = True
            
            # 启动UI更新线程
            ui_thread = threading.Thread(target=self._update_ui, daemon=True)
            ui_thread.start()
            
            # 添加欢迎消息
            self._add_output(f"Python {sys.version.split()[0]} 交互式终端\n", ft.Colors.GREEN_400)
            if self.is_frozen:
                self._add_output("运行模式: 打包应用（内嵌解释器）\n", ft.Colors.BLUE_300)
            else:
                self._add_output("运行模式: 开发环境\n", ft.Colors.BLUE_300)
            self._add_output("输入 'help()' 获取帮助\n\n", ft.Colors.GREY_500)
            
        except Exception as e:
            self._add_output(f"初始化解释器失败: {e}\n", ft.Colors.RED_400)
    
    def _update_ui(self) -> None:
        """更新UI（在后台线程中运行）。"""
        while self.running:
            try:
                msg_type, content = self.output_queue.get(timeout=0.1)
                if msg_type == "stdout":
                    self._add_output(content, ft.Colors.WHITE)
                elif msg_type == "stderr":
                    self._add_output(content, ft.Colors.RED_300)
                
                if self.page:
                    try:
                        self.page.update()
                    except Exception:
                        pass
            except Empty:
                continue
            except Exception:
                break
    
    def _add_output(self, text: str, color: str = ft.Colors.WHITE) -> None:
        """添加输出到终端。
        
        Args:
            text: 输出文本
            color: 文本颜色
        """
        if not text:
            return
        
        output_text = ft.Text(
            text.rstrip("\n"),
            size=13,
            color=color,
            font_family="Consolas" if sys.platform == "win32" else "Monaco",
            selectable=True,
        )
        
        self.terminal_output.controls.append(output_text)
        
        # 限制输出行数，避免内存占用过大
        if len(self.terminal_output.controls) > 1000:
            self.terminal_output.controls = self.terminal_output.controls[-500:]
    
    def _on_command_submit(self, e: ft.ControlEvent) -> None:
        """命令提交事件处理。"""
        command = self.command_input.value
        if not command or not command.strip():
            return
        
        # 添加到历史记录
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # 显示命令（多行代码每行都显示）
        lines = command.split('\n')
        for i, line in enumerate(lines):
            if i == 0:
                self._add_output(f">>> {line}\n", ft.Colors.GREEN_400)
            else:
                self._add_output(f"... {line}\n", ft.Colors.GREEN_400)
        
        # 清空输入
        self.command_input.value = ""
        self.page.update()
        
        # 在后台线程中执行命令
        exec_thread = threading.Thread(target=self._execute_command, args=(command,), daemon=True)
        exec_thread.start()
    
    def _execute_command(self, command: str) -> None:
        """在后台线程中执行命令。
        
        Args:
            command: 要执行的Python代码
        """
        if not self.interpreter:
            self.output_queue.put(("stderr", "解释器未初始化\n"))
            return
        
        try:
            # 捕获stdout和stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                # 执行代码
                # runsource会自动处理单行和多行代码
                more = self.interpreter.runsource(command)
            
            # 获取输出
            stdout_output = stdout_buffer.getvalue()
            stderr_output = stderr_buffer.getvalue()
            
            # 发送输出到队列
            if stdout_output:
                self.output_queue.put(("stdout", stdout_output))
            if stderr_output:
                self.output_queue.put(("stderr", stderr_output))
            
            # 如果没有输出，可能是因为是表达式，尝试eval
            if not stdout_output and not stderr_output and not more:
                try:
                    # 检查是否是表达式
                    result = eval(command, self.interpreter.locals)
                    if result is not None:
                        self.output_queue.put(("stdout", f"{result}\n"))
                except:
                    pass
                    
        except Exception as ex:
            self.output_queue.put(("stderr", f"执行错误: {ex}\n"))
    
    def _clear_input(self, e: ft.ControlEvent) -> None:
        """清空输入框。"""
        self.command_input.value = ""
        self.page.update()
    
    def _clear_terminal(self, e: ft.ControlEvent) -> None:
        """清空终端。"""
        self.terminal_output.controls.clear()
        self._add_output("终端已清空\n\n", ft.Colors.GREY_500)
        self.page.update()
    
    def _restart_terminal(self, e: ft.ControlEvent) -> None:
        """重启终端。"""
        # 停止当前解释器
        self.running = False
        
        # 清空输出
        self.terminal_output.controls.clear()
        
        # 重新初始化
        self._init_interpreter()
        self.page.update()
    
    def _go_back(self, e: ft.ControlEvent) -> None:
        """返回上一级视图。"""
        # 停止解释器
        self.running = False
        self.interpreter = None
        
        if self.parent_container:
            from views.dev_tools import DevToolsView
            from services import EncodingService
            
            encoding_service = EncodingService()
            dev_tools_view = DevToolsView(
                self.page,
                self.config_service,
                encoding_service,
                self.parent_container
            )
            self.parent_container.content = dev_tools_view
            self.parent_container.update()
