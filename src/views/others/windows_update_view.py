# -*- coding: utf-8 -*-
"""Windows更新管理视图模块。

提供Windows更新禁用/恢复功能的用户界面。
"""

import platform
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
)


class WindowsUpdateView(ft.Container):
    """Windows更新管理视图类。
    
    提供Windows更新管理功能，包括：
    - 禁用Windows自动更新
    - 恢复Windows自动更新
    - 查看当前更新状态
    - 自定义暂停年份
    """

    # 恢复Windows更新的注册表内容
    RESTORE_UPDATE_REG = """Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings]
"FlightSettingsMaxPauseDays"=-
"PauseFeatureUpdatesStartTime"=-
"PauseFeatureUpdatesEndTime"=-
"PauseQualityUpdatesStartTime"=-
"PauseQualityUpdatesEndTime"=-
"PauseUpdatesStartTime"=-
"PauseUpdatesExpiryTime"=-
"""

    def __init__(
        self,
        page: ft.Page,
        on_back: Optional[callable] = None
    ) -> None:
        """初始化Windows更新管理视图。
        
        Args:
            page: Flet页面对象
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self.page: ft.Page = page
        self.on_back: Optional[callable] = on_back
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 构建界面
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 检测系统类型
        is_windows = platform.system() == "Windows"
        
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("Windows更新管理", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 如果不是 Windows 系统，显示提示信息
        if not is_windows:
            self.content = ft.Column(
                controls=[
                    header,
                    ft.Divider(),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Icon(
                                    ft.Icons.DESKTOP_WINDOWS_OUTLINED,
                                    size=64,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                ft.Container(height=PADDING_LARGE),
                                ft.Text(
                                    "此功能仅限 Windows 系统",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                ft.Container(height=PADDING_MEDIUM),
                                ft.Text(
                                    f"当前系统：{platform.system()} {platform.release()}",
                                    size=14,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                ft.Container(height=PADDING_MEDIUM // 2),
                                ft.Text(
                                    "Windows更新管理功能仅适用于 Windows 10/11 系统",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        expand=True,
                        alignment=ft.alignment.center,
                    ),
                ],
                spacing=0,
            )
            return
        
        # 年份设置区域
        self.year_input = ft.TextField(
            label="暂停更新至年份",
            value="2099",
            hint_text="例如: 2099, 2050, 2030",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_year_change,
        )
        
        year_setting_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=20, color=ft.Colors.PRIMARY),
                            ft.Text("更新暂停设置", size=14, weight=ft.FontWeight.W_500),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    ft.Row(
                        controls=[
                            self.year_input,
                            ft.Text("年", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "设置Windows更新暂停的截止年份（默认2099年）",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 说明文本
        info_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=24, color=ft.Colors.BLUE),
                            ft.Text("功能说明", size=18, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    ft.Text(
                        "通过修改注册表来管理Windows自动更新设置，可以暂停Windows更新至指定年份。",
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=PADDING_MEDIUM // 2),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=20, color=ft.Colors.ORANGE),
                            ft.Text(
                                "注意：需要管理员权限，操作将立即生效，建议重启电脑",
                                size=13,
                                color=ft.Colors.ORANGE,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(2, ft.Colors.BLUE_200),
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
        )
        
        # 当前状态显示
        self.status_text = ft.Text(
            "状态：未检测",
            size=14,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        status_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=20, color=ft.Colors.PRIMARY),
                            ft.Text("当前状态", size=14, weight=ft.FontWeight.W_500),
                        ],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    self.status_text,
                    ft.ElevatedButton(
                        "检查更新状态",
                        icon=ft.Icons.REFRESH,
                        on_click=self._on_check_status,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 操作按钮区域
        disable_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.BLOCK, size=24, color=ft.Colors.WHITE),
                        ft.Text("禁用Windows更新", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_disable_update,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                    bgcolor=ft.Colors.ORANGE_700,
                    color=ft.Colors.WHITE,
                ),
            ),
            expand=True,
        )
        
        restore_button = ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.RESTORE, size=24, color=ft.Colors.WHITE),
                        ft.Text("恢复Windows更新", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_restore_update,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                    bgcolor=ft.Colors.GREEN_700,
                    color=ft.Colors.WHITE,
                ),
            ),
            expand=True,
        )
        
        buttons_row = ft.Row(
            controls=[disable_button, restore_button],
            spacing=PADDING_LARGE,
        )
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                year_setting_card,
                info_card,
                status_card,
                buttons_row,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            spacing=PADDING_LARGE,
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                scrollable_content,
            ],
            spacing=0,
        )
    
    def _on_year_change(self, e: ft.ControlEvent) -> None:
        """年份输入框变化事件，进行输入验证。"""
        try:
            year = int(e.control.value)
            current_year = datetime.now().year
            
            if year < current_year:
                e.control.error_text = f"年份不能小于当前年份（{current_year}）"
            elif year > 9999:
                e.control.error_text = "年份不能超过9999"
            else:
                e.control.error_text = None
            
            e.control.update()
        except ValueError:
            e.control.error_text = "请输入有效的年份数字"
            e.control.update()
    
    def _generate_disable_reg_content(self) -> str:
        """生成禁用更新的注册表内容（使用用户输入的年份）。"""
        try:
            year = int(self.year_input.value)
            current_year = datetime.now().year
            
            # 验证年份
            if year < current_year or year > 9999:
                year = 2099  # 使用默认值
        except (ValueError, AttributeError):
            year = 2099  # 使用默认值
        
        return f"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings]
"FlightSettingsMaxPauseDays"=dword:0000a8c0
"PauseFeatureUpdatesStartTime"="2023-07-07T10:00:52Z"
"PauseFeatureUpdatesEndTime"="{year}-12-31T23:59:59Z"
"PauseQualityUpdatesStartTime"="2023-07-07T10:00:52Z"
"PauseQualityUpdatesEndTime"="{year}-12-31T23:59:59Z"
"PauseUpdatesStartTime"="2023-07-07T09:59:52Z"
"PauseUpdatesExpiryTime"="{year}-12-31T23:59:59Z"
"""
    
    def _on_check_status(self, e: ft.ControlEvent) -> None:
        """检查当前Windows更新状态。"""
        # 检测系统
        if platform.system() != "Windows":
            self._show_message("此功能仅限 Windows 系统", ft.Colors.ORANGE)
            return
        
        try:
            # 使用reg query命令查询注册表
            result = subprocess.run(
                ['reg', 'query', 
                 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings',
                 '/v', 'PauseUpdatesExpiryTime'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0 and 'PauseUpdatesExpiryTime' in result.stdout:
                # 检查是否设置了暂停，并提取年份
                year_match = re.search(r'(\d{4})-12-31', result.stdout)
                if year_match:
                    pause_year = year_match.group(1)
                    self.status_text.value = f"状态：Windows更新已禁用（暂停至{pause_year}年）"
                    self.status_text.color = ft.Colors.ORANGE
                else:
                    self.status_text.value = "状态：Windows更新已启用"
                    self.status_text.color = ft.Colors.GREEN
            else:
                self.status_text.value = "状态：Windows更新已启用（未检测到暂停设置）"
                self.status_text.color = ft.Colors.GREEN
            
            self.status_text.update()
            self._show_message("状态检查完成", ft.Colors.GREEN)
            
        except Exception as ex:
            self.status_text.value = f"状态：检测失败 ({str(ex)})"
            self.status_text.color = ft.Colors.RED
            self.status_text.update()
            self._show_message(f"检测失败：{str(ex)}", ft.Colors.RED)
    
    def _on_disable_update(self, e: ft.ControlEvent) -> None:
        """禁用Windows更新。"""
        # 检测系统
        if platform.system() != "Windows":
            self._show_message("此功能仅限 Windows 系统", ft.Colors.ORANGE)
            return
        
        try:
            # 验证年份输入
            try:
                year = int(self.year_input.value)
                current_year = datetime.now().year
                if year < current_year or year > 9999:
                    self._show_message(f"请输入有效的年份（{current_year}-9999）", ft.Colors.ORANGE)
                    return
            except ValueError:
                self._show_message("请输入有效的年份数字", ft.Colors.ORANGE)
                return
            
            # 创建临时注册表文件，使用动态生成的内容
            reg_content = self._generate_disable_reg_content()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False, encoding='utf-8') as f:
                f.write(reg_content)
                reg_file = f.name
            
            # 执行注册表导入（静默模式，不弹窗提示）
            result = subprocess.run(
                ['regedit', '/s', reg_file], 
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 删除临时文件
            try:
                Path(reg_file).unlink()
            except:
                pass
            
            # 检查是否执行成功
            if result.returncode == 0:
                self._show_message(
                    f"✓ Windows更新已禁用至{year}年！\n建议重启电脑使设置完全生效。", 
                    ft.Colors.GREEN
                )
                
                # 更新状态
                self.status_text.value = f"状态：Windows更新已禁用（暂停至{year}年）"
                self.status_text.color = ft.Colors.ORANGE
                self.status_text.update()
            else:
                self._show_message("操作失败，可能需要管理员权限", ft.Colors.RED)
            
        except Exception as ex:
            self._show_message(f"操作失败：{str(ex)}", ft.Colors.RED)
    
    def _on_restore_update(self, e: ft.ControlEvent) -> None:
        """恢复Windows更新。"""
        # 检测系统
        if platform.system() != "Windows":
            self._show_message("此功能仅限 Windows 系统", ft.Colors.ORANGE)
            return
        
        try:
            # 创建临时注册表文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.reg', delete=False, encoding='utf-8') as f:
                f.write(self.RESTORE_UPDATE_REG)
                reg_file = f.name
            
            # 执行注册表导入（静默模式，不弹窗提示）
            result = subprocess.run(
                ['regedit', '/s', reg_file],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 删除临时文件
            try:
                Path(reg_file).unlink()
            except:
                pass
            
            # 检查是否执行成功
            if result.returncode == 0:
                self._show_message(
                    "✓ Windows更新已恢复！\n建议重启电脑使设置完全生效。", 
                    ft.Colors.GREEN
                )
                
                # 更新状态
                self.status_text.value = "状态：Windows更新已启用"
                self.status_text.color = ft.Colors.GREEN
                self.status_text.update()
            else:
                self._show_message("操作失败，可能需要管理员权限", ft.Colors.RED)
            
        except Exception as ex:
            self._show_message(f"操作失败：{str(ex)}", ft.Colors.RED)
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=3000,
        )
        self.page.overlay.append(snackbar)
        snackbar.open = True
        self.page.update()
