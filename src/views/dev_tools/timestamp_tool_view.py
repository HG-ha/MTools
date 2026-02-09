# -*- coding: utf-8 -*-
"""时间工具视图模块。

提供时间戳转换、时区转换、时间计算等功能。
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import flet as ft

from constants import PADDING_MEDIUM, PADDING_SMALL


class TimestampToolView(ft.Container):
    """时间工具视图类。"""
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
        """初始化时间工具视图。
        
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
        self.timestamp_input = ft.Ref[ft.TextField]()
        self.timestamp_unit = ft.Ref[ft.Dropdown]()
        self.datetime_result = ft.Ref[ft.TextField]()
        
        self.datetime_input = ft.Ref[ft.TextField]()
        self.timestamp_result = ft.Ref[ft.TextField]()
        
        self.current_time_display = ft.Ref[ft.Text]()
        self.current_timestamp_display = ft.Ref[ft.Text]()
        
        self.calc_start_date = ft.Ref[ft.TextField]()
        self.calc_operation = ft.Ref[ft.Dropdown]()
        self.calc_value = ft.Ref[ft.TextField]()
        self.calc_unit = ft.Ref[ft.Dropdown]()
        self.calc_result = ft.Ref[ft.TextField]()
        
        self._build_ui()
        
        # 启动实时时钟
        self._page.run_task(self._update_current_time)
    
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
                ft.Text("时间工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 当前时间显示
        current_time_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("当前时间", weight=ft.FontWeight.BOLD, size=16),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("日期时间", size=12, color=ft.Colors.GREY),
                                    ft.Text(
                                        ref=self.current_time_display,
                                        value="",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLUE,
                                    ),
                                ],
                                spacing=2,
                            ),
                            ft.Container(width=40),
                            ft.Column(
                                controls=[
                                    ft.Text("时间戳 (秒)", size=12, color=ft.Colors.GREY),
                                    ft.Text(
                                        ref=self.current_timestamp_display,
                                        value="",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREEN,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
        )
        
        # 时间戳转日期时间
        timestamp_to_datetime_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("时间戳 → 日期时间", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.timestamp_input,
                                label="时间戳",
                                hint_text="例如: 1699999999",
                                expand=True,
                            ),
                            ft.Dropdown(
                                ref=self.timestamp_unit,
                                label="单位",
                                width=120,
                                options=[
                                    ft.dropdown.Option("秒"),
                                    ft.dropdown.Option("毫秒"),
                                ],
                                value="秒",
                            ),
                            ft.ElevatedButton(
                                content="转换",
                                icon=ft.Icons.ARROW_FORWARD,
                                on_click=self._convert_timestamp_to_datetime,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.TextField(
                        ref=self.datetime_result,
                        label="结果",
                        read_only=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.datetime_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 日期时间转时间戳
        datetime_to_timestamp_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("日期时间 → 时间戳", weight=ft.FontWeight.BOLD, size=15),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                ref=self.datetime_input,
                                label="日期时间",
                                hint_text="例如: 2024-12-08 15:30:00",
                                expand=True,
                            ),
                            ft.ElevatedButton(
                                content="转换",
                                icon=ft.Icons.ARROW_FORWARD,
                                on_click=self._convert_datetime_to_timestamp,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.TextField(
                        ref=self.timestamp_result,
                        label="结果 (秒)",
                        read_only=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.timestamp_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 时间计算
        time_calc_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("时间计算", weight=ft.FontWeight.BOLD, size=15),
                    ft.TextField(
                        ref=self.calc_start_date,
                        label="起始日期时间",
                        hint_text="例如: 2024-12-08 15:30:00 (留空使用当前时间)",
                    ),
                    ft.Row(
                        controls=[
                            ft.Dropdown(
                                ref=self.calc_operation,
                                label="操作",
                                width=100,
                                options=[
                                    ft.dropdown.Option("+", "+"),
                                    ft.dropdown.Option("-", "-"),
                                ],
                                value="+",
                            ),
                            ft.TextField(
                                ref=self.calc_value,
                                label="数值",
                                hint_text="例如: 30",
                                expand=True,
                            ),
                            ft.Dropdown(
                                ref=self.calc_unit,
                                label="单位",
                                width=120,
                                options=[
                                    ft.dropdown.Option("秒"),
                                    ft.dropdown.Option("分钟"),
                                    ft.dropdown.Option("小时"),
                                    ft.dropdown.Option("天"),
                                ],
                                value="天",
                            ),
                            ft.ElevatedButton(
                                content="计算",
                                icon=ft.Icons.CALCULATE,
                                on_click=self._calculate_time,
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.TextField(
                        ref=self.calc_result,
                        label="结果",
                        read_only=True,
                        suffix=ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.calc_result.current.value),
                        ),
                    ),
                ],
                spacing=5,
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 布局
        content_area = ft.Column(
            controls=[
                current_time_section,
                ft.Container(height=PADDING_SMALL),
                ft.Row(
                    controls=[
                        ft.Container(content=timestamp_to_datetime_section, expand=1),
                        ft.Container(content=datetime_to_timestamp_section, expand=1),
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Container(height=PADDING_SMALL),
                time_calc_section,
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
    
    async def _update_current_time(self):
        """更新当前时间显示。"""
        while True:
            try:
                if self.current_time_display.current and self.current_timestamp_display.current:
                    now = datetime.now()
                    timestamp = int(now.timestamp())
                    
                    self.current_time_display.current.value = now.strftime("%Y-%m-%d %H:%M:%S")
                    self.current_timestamp_display.current.value = str(timestamp)
                    
                    try:
                        self.update()
                    except (AssertionError, AttributeError):
                        # 视图可能已经不在页面上
                        break
                
                await asyncio.sleep(1)
            except Exception:
                break
    
    def _convert_timestamp_to_datetime(self, e):
        """将时间戳转换为日期时间。"""
        timestamp_str = self.timestamp_input.current.value
        
        if not timestamp_str:
            self._show_snack("请输入时间戳", error=True)
            return
        
        try:
            timestamp = float(timestamp_str)
            
            # 根据单位转换
            if self.timestamp_unit.current.value == "毫秒":
                timestamp = timestamp / 1000
            
            dt = datetime.fromtimestamp(timestamp)
            result = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            self.datetime_result.current.value = result
            self.update()
            
        except ValueError:
            self._show_snack("无效的时间戳格式", error=True)
        except Exception as e:
            self._show_snack(f"转换失败: {str(e)}", error=True)
    
    def _convert_datetime_to_timestamp(self, e):
        """将日期时间转换为时间戳。"""
        datetime_str = self.datetime_input.current.value
        
        if not datetime_str:
            self._show_snack("请输入日期时间", error=True)
            return
        
        try:
            # 尝试多种格式
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d",
            ]
            
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                self._show_snack("无法识别的日期时间格式", error=True)
                return
            
            timestamp = int(dt.timestamp())
            self.timestamp_result.current.value = str(timestamp)
            self.update()
            
        except Exception as e:
            self._show_snack(f"转换失败: {str(e)}", error=True)
    
    def _calculate_time(self, e):
        """计算时间。"""
        start_date_str = self.calc_start_date.current.value
        value_str = self.calc_value.current.value
        
        if not value_str:
            self._show_snack("请输入数值", error=True)
            return
        
        try:
            # 解析起始时间
            if start_date_str:
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d %H:%M",
                    "%Y/%m/%d",
                ]
                
                start_dt = None
                for fmt in formats:
                    try:
                        start_dt = datetime.strptime(start_date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if start_dt is None:
                    self._show_snack("无法识别的日期时间格式", error=True)
                    return
            else:
                start_dt = datetime.now()
            
            # 解析数值
            value = float(value_str)
            
            # 根据单位计算
            unit = self.calc_unit.current.value
            if unit == "秒":
                delta = timedelta(seconds=value)
            elif unit == "分钟":
                delta = timedelta(minutes=value)
            elif unit == "小时":
                delta = timedelta(hours=value)
            elif unit == "天":
                delta = timedelta(days=value)
            
            # 根据操作执行计算
            if self.calc_operation.current.value == "+":
                result_dt = start_dt + delta
            else:
                result_dt = start_dt - delta
            
            result = result_dt.strftime("%Y-%m-%d %H:%M:%S")
            self.calc_result.current.value = result
            self.update()
            
        except ValueError:
            self._show_snack("无效的数值", error=True)
        except Exception as e:
            self._show_snack(f"计算失败: {str(e)}", error=True)
    
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
**时间工具使用说明**

**功能模块：**

1. **当前时间**
   - 实时显示当前日期时间和时间戳
   - 每秒自动更新

2. **时间戳 → 日期时间**
   - 输入时间戳（秒或毫秒）
   - 转换为人类可读的日期时间格式
   - 示例: 1699999999 → 2023-11-15 07:59:59

3. **日期时间 → 时间戳**
   - 输入日期时间
   - 转换为 Unix 时间戳（秒）
   - 支持多种格式:
     - YYYY-MM-DD HH:MM:SS
     - YYYY-MM-DD HH:MM
     - YYYY-MM-DD
     - YYYY/MM/DD HH:MM:SS 等

4. **时间计算**
   - 对指定时间进行加减运算
   - 支持秒、分钟、小时、天
   - 示例: 2024-12-08 + 30天 = 2025-01-07

**使用技巧：**
- 所有结果都可以一键复制
- 时间计算的起始时间留空时，使用当前时间
- 支持正数和负数进行时间加减
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
        self._page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.snack_bar.open = True
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()


# 导入 asyncio
import asyncio
