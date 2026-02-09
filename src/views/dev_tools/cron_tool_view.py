# -*- coding: utf-8 -*-
"""Cron表达式工具视图模块。

提供Cron表达式解析、生成和执行时间预测功能。
"""

from datetime import datetime
from typing import Callable, Optional

import flet as ft
from croniter import croniter

from constants import PADDING_MEDIUM, PADDING_SMALL


class CronToolView(ft.Container):
    """Cron表达式工具视图类。"""
    
    # 常用的Cron表达式模板
    TEMPLATES = {
        "每分钟": "* * * * *",
        "每小时": "0 * * * *",
        "每天凌晨": "0 0 * * *",
        "每天中午": "0 12 * * *",
        "每周一": "0 0 * * 1",
        "每月1号": "0 0 1 * *",
        "每年1月1号": "0 0 1 1 *",
        "工作日9点": "0 9 * * 1-5",
        "每15分钟": "*/15 * * * *",
        "每6小时": "0 */6 * * *",
    }
    
    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[Callable] = None
    ):
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
        self.cron_input = ft.Ref[ft.TextField]()
        self.template_dropdown = ft.Ref[ft.Dropdown]()
        self.output_text = ft.Ref[ft.TextField]()
        
        self._build_ui()
    
    def _build_ui(self):
        # 标题栏
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self._on_back_click(),
                ),
                ft.Text("Cron 表达式工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 操作栏
        operation_bar = ft.Row(
            controls=[
                ft.TextField(
                    ref=self.cron_input,
                    label="Cron 表达式",
                    hint_text="* * * * *",
                    width=250,
                    text_style=ft.TextStyle(font_family="Consolas,Monospace"),
                ),
                ft.Dropdown(
                    ref=self.template_dropdown,
                    label="常用模板",
                    width=180,
                    options=[ft.dropdown.Option(k) for k in self.TEMPLATES.keys()],
                    hint_text="选择模板...",
                    on_select=self._on_template_select,
                ),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content="解析",
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=self._parse,
                ),
                ft.OutlinedButton(
                    content="清空",
                    icon=ft.Icons.CLEAR,
                    on_click=self._clear,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # Cron字段说明卡片
        info_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Cron 表达式格式", size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(height=5),
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text("分钟", size=12, text_align=ft.TextAlign.CENTER),
                                width=60,
                                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                padding=5,
                                border_radius=4,
                            ),
                            ft.Container(
                                content=ft.Text("小时", size=12, text_align=ft.TextAlign.CENTER),
                                width=60,
                                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                                padding=5,
                                border_radius=4,
                            ),
                            ft.Container(
                                content=ft.Text("日期", size=12, text_align=ft.TextAlign.CENTER),
                                width=60,
                                bgcolor=ft.Colors.TERTIARY_CONTAINER,
                                padding=5,
                                border_radius=4,
                            ),
                            ft.Container(
                                content=ft.Text("月份", size=12, text_align=ft.TextAlign.CENTER),
                                width=60,
                                bgcolor=ft.Colors.ERROR_CONTAINER,
                                padding=5,
                                border_radius=4,
                            ),
                            ft.Container(
                                content=ft.Text("星期", size=12, text_align=ft.TextAlign.CENTER),
                                width=60,
                                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                                padding=5,
                                border_radius=4,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=5),
                    ft.Text("示例: 0 9 * * 1-5 (每个工作日早上9点)", size=11, color=ft.Colors.OUTLINE),
                ],
            ),
            padding=PADDING_SMALL,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE),
        )
        
        # 输出区域
        output_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("解析结果", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            icon_size=16,
                            on_click=lambda _: self._copy_text(self.output_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.output_text,
                        multiline=True,
                        min_lines=18,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
                        text_style=ft.TextStyle(font_family="Consolas,Monospace"),
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    expand=True,
                ),
            ],
            spacing=5,
            expand=True,
        )
        
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Container(height=PADDING_SMALL),
                operation_bar,
                ft.Container(height=PADDING_SMALL),
                info_card,
                ft.Container(height=PADDING_SMALL),
                output_section,
            ],
            spacing=0,
            expand=True,
        )
    
    def _on_template_select(self, e):
        """选择模板时自动填充表达式。"""
        template_name = self.template_dropdown.current.value
        if template_name and template_name in self.TEMPLATES:
            self.cron_input.current.value = self.TEMPLATES[template_name]
            self.cron_input.current.update()
    
    def _parse(self, e):
        """解析Cron表达式。"""
        cron_expr = self.cron_input.current.value
        
        if not cron_expr:
            self._show_snack("请输入 Cron 表达式", error=True)
            return
        
        try:
            # 验证并解析表达式
            base_time = datetime.now()
            cron = croniter(cron_expr, base_time)
            
            # 生成描述
            result = f"Cron 表达式: {cron_expr}\n"
            result += "=" * 50 + "\n\n"
            
            # 解析字段
            fields = cron_expr.split()
            if len(fields) >= 5:
                result += "字段解析：\n"
                result += f"  分钟: {fields[0]}\n"
                result += f"  小时: {fields[1]}\n"
                result += f"  日期: {fields[2]}\n"
                result += f"  月份: {fields[3]}\n"
                result += f"  星期: {fields[4]}\n"
                result += "\n"
            
            # 计算未来10次执行时间
            result += "未来 10 次执行时间：\n"
            result += "-" * 50 + "\n"
            
            for i in range(10):
                next_time = cron.get_next(datetime)
                result += f"{i+1:2d}. {next_time.strftime('%Y-%m-%d %H:%M:%S %A')}\n"
            
            # 简单的人类可读描述
            result += "\n" + "=" * 50 + "\n"
            result += self._generate_description(cron_expr)
            
            self.output_text.current.value = result
            self.output_text.current.update()
            self._show_snack("解析成功")
            
        except Exception as e:
            error_msg = f"❌ 解析失败\n\n"
            error_msg += f"Cron 表达式: {cron_expr}\n"
            error_msg += f"错误信息: {str(e)}\n\n"
            error_msg += "提示：\n"
            error_msg += "- Cron 表达式格式: 分 时 日 月 周\n"
            error_msg += "- 每个字段用空格分隔\n"
            error_msg += "- 支持: * , - / 等符号\n"
            error_msg += "- 示例: 0 9 * * 1-5 (工作日早上9点)\n"
            
            self.output_text.current.value = error_msg
            self.output_text.current.update()
            self._show_snack(f"错误: {str(e)}", error=True)
    
    def _generate_description(self, cron_expr: str) -> str:
        """生成Cron表达式的人类可读描述。"""
        fields = cron_expr.split()
        if len(fields) < 5:
            return "表达式格式不完整"
        
        minute, hour, day, month, weekday = fields[:5]
        
        desc = "执行规则: "
        
        # 简单的规则识别
        if cron_expr == "* * * * *":
            return "执行规则: 每分钟执行一次"
        elif minute == "0" and hour == "*":
            return "执行规则: 每小时整点执行"
        elif minute == "0" and hour == "0":
            return "执行规则: 每天凌晨0点执行"
        elif minute == "0" and hour == "12":
            return "执行规则: 每天中午12点执行"
        elif "*/15" in minute:
            return "执行规则: 每15分钟执行一次"
        elif weekday == "1-5" and day == "*":
            return f"执行规则: 每个工作日 {hour}:{minute} 执行"
        elif weekday != "*":
            return f"执行规则: 每周{weekday} {hour}:{minute} 执行"
        else:
            return f"执行规则: 自定义时间规则"
    
    def _clear(self, e):
        self.cron_input.current.value = ""
        self.output_text.current.value = ""
        self.template_dropdown.current.value = None
        self.update()
    
    async def _copy_text(self, text: str):
        if not text:
            self._show_snack("没有可复制的内容", error=True)
            return
        await ft.Clipboard().set(text)
        self._show_snack("已复制到剪贴板")
    
    def _on_back_click(self):
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**Cron 表达式工具使用说明**

**功能说明：**
- 解析 Cron 表达式
- 预测未来执行时间
- 提供常用模板快速生成

**Cron 表达式格式：**

```
* * * * *
│ │ │ │ │
│ │ │ │ └─ 星期 (0-7, 0和7都表示周日)
│ │ │ └─── 月份 (1-12)
│ │ └───── 日期 (1-31)
│ └─────── 小时 (0-23)
└───────── 分钟 (0-59)
```

**特殊字符：**
- ***** : 任意值
- **,** : 列举值，如 1,3,5
- **-** : 范围，如 1-5
- **/** : 间隔，如 */15（每15分钟）

**使用步骤：**
1. 输入 Cron 表达式，或从模板中选择
2. 点击"解析"
3. 查看执行规则和未来执行时间

**常用示例：**

- `* * * * *` - 每分钟
- `0 * * * *` - 每小时
- `0 0 * * *` - 每天凌晨0点
- `0 9 * * 1-5` - 工作日早上9点
- `*/15 * * * *` - 每15分钟
- `0 0 1 * *` - 每月1号凌晨
- `0 0 * * 0` - 每周日凌晨

**提示：**
- Linux/Unix 标准 Cron 格式为 5 个字段
- 某些系统支持 6 个字段（增加秒）或 7 个字段（增加年份）
- 本工具支持标准 5 字段格式
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
                            code_theme="atom-one-dark",
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=550,
                height=500,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda _: self._page.close(dialog)),
            ],
        )
        
        self._page.open(dialog)
    
    def _show_snack(self, message: str, error: bool = False):
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
