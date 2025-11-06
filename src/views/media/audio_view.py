# -*- coding: utf-8 -*-
"""音频处理视图模块。

提供音频格式转换、编辑、批量处理等功能的用户界面。
"""

from typing import Callable, Optional

import flet as ft

from components import FeatureCard
from constants import (
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
    TEXT_SECONDARY,
)
from services import AudioService, ConfigService, FFmpegService
from views.media.audio_format_view import AudioFormatView
from views.media.ffmpeg_install_view import FFmpegInstallView


class AudioView(ft.Container):
    """音频处理视图类。
    
    提供音频处理相关功能的用户界面，包括：
    - 音频格式转换
    - 音频剪辑
    - 批量处理
    - 音频参数调整
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: Optional[ConfigService] = None,
        parent_container: Optional[ft.Container] = None
    ) -> None:
        """初始化音频处理视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            parent_container: 父容器（用于视图切换）
        """
        super().__init__()
        self.page: ft.Page = page
        self.config_service: ConfigService = config_service if config_service else ConfigService()
        self.parent_container: Optional[ft.Container] = parent_container
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_LARGE,
            right=PADDING_LARGE,
            top=PADDING_XLARGE,
            bottom=PADDING_XLARGE
        )
        
        # 创建服务
        self.ffmpeg_service: FFmpegService = FFmpegService(self.config_service)
        self.audio_service: AudioService = AudioService(self.ffmpeg_service)
        
        # 创建子视图（延迟创建）
        self.format_view: Optional[AudioFormatView] = None
        self.ffmpeg_install_view: Optional[FFmpegInstallView] = None
        
        # 记录当前显示的视图（用于状态恢复）
        self.current_sub_view: Optional[ft.Container] = None
        # 记录当前子视图的类型（用于销毁）
        self.current_sub_view_type: Optional[str] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 功能卡片区域
        feature_cards: ft.Row = ft.Row(
            controls=[
                FeatureCard(
                    icon=ft.Icons.TERMINAL,
                    title="FFmpeg终端",
                    description="不会安装FFmpeg？没关系，我们帮你配置好了。",
                    gradient_colors=("#667eea", "#764ba2"),
                    on_click=self._open_ffmpeg_terminal,
                ),
                FeatureCard(
                    icon=ft.Icons.AUDIO_FILE_ROUNDED,
                    title="格式转换",
                    description="支持MP3、WAV、AAC等格式互转",
                    gradient_colors=("#43E97B", "#38F9D7"),
                    on_click=self._open_format_dialog,
                ),
                FeatureCard(
                    icon=ft.Icons.CONTENT_CUT_ROUNDED,
                    title="音频剪辑",
                    description="裁剪、合并音频文件",
                    gradient_colors=("#FA709A", "#FEE140"),
                    on_click=self._open_audio_cut,
                ),
                FeatureCard(
                    icon=ft.Icons.TUNE_ROUNDED,
                    title="参数调整",
                    description="调整比特率、采样率等参数",
                    gradient_colors=("#30CFD0", "#330867"),
                    on_click=self._open_audio_tune,
                ),
            ],
            wrap=True,  # 自动换行
            spacing=PADDING_LARGE,
            run_spacing=PADDING_LARGE,
            alignment=ft.MainAxisAlignment.START,  # 从左开始排列
            vertical_alignment=ft.CrossAxisAlignment.START,  # 从上开始排列
        )
        
        # 组装视图
        self.content = ft.Column(
            controls=[
                feature_cards,
            ],
            spacing=PADDING_MEDIUM,
            scroll=ft.ScrollMode.AUTO,  # 允许滚动
            horizontal_alignment=ft.CrossAxisAlignment.START,  # 从左对齐
            alignment=ft.MainAxisAlignment.START,  # 从上对齐
            expand=True,
            width=float('inf'),
        )
    
    def _open_ffmpeg_terminal(self, e: ft.ControlEvent) -> None:
        """打开配置好FFmpeg的命令行窗口。
        
        Args:
            e: 控件事件对象
        """
        def open_func():
            """打开终端的实际逻辑。"""
            import subprocess
            import os
            import sys
            from pathlib import Path
            
            # 获取FFmpeg路径
            ffmpeg_path = self.ffmpeg_service.get_ffmpeg_path()
            
            # 确定命令行启动命令和环境变量
            if sys.platform == "win32":
                # Windows系统
                if ffmpeg_path and ffmpeg_path != "ffmpeg":
                    # 使用本地FFmpeg
                    ffmpeg_dir = str(Path(ffmpeg_path).parent)
                    
                    # 创建一个批处理文件来设置环境变量并打开cmd
                    temp_dir = self.config_service.get_temp_dir()
                    bat_file = temp_dir / "ffmpeg_terminal.bat"
                    
                    with open(bat_file, 'w', encoding='utf-8') as f:
                        f.write('@echo off\n')
                        f.write('chcp 65001 >nul\n')  # 设置UTF-8编码
                        f.write(f'set "PATH={ffmpeg_dir};%PATH%"\n')
                        f.write('echo =========================================\n')
                        f.write('echo  FFmpeg 命令行环境已配置\n')
                        f.write('echo =========================================\n')
                        f.write('echo.\n')
                        f.write('echo FFmpeg 路径: ' + ffmpeg_dir + '\n')
                        f.write('echo.\n')
                        f.write('echo 您现在可以直接使用以下命令:\n')
                        f.write('echo   - ffmpeg   (音视频处理)\n')
                        f.write('echo   - ffprobe  (媒体信息查看)\n')
                        f.write('echo   - ffplay   (媒体播放器)\n')
                        f.write('echo.\n')
                        f.write('echo 示例: ffmpeg -version\n')
                        f.write('echo =========================================\n')
                        f.write('echo.\n')
                        f.write('cd /d "%USERPROFILE%"\n')  # 切换到用户目录
                        f.write('cmd /k\n')  # 保持窗口打开
                    
                    # 启动命令行
                    subprocess.Popen(['cmd', '/c', 'start', str(bat_file)], shell=True)
                else:
                    # 使用系统FFmpeg
                    subprocess.Popen(['cmd', '/k', 'echo FFmpeg (系统版本) 已就绪 && echo. && ffmpeg -version'], shell=True)
            else:
                # Linux/macOS系统
                if ffmpeg_path and ffmpeg_path != "ffmpeg":
                    ffmpeg_dir = str(Path(ffmpeg_path).parent)
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                
                # 尝试打开终端
                if sys.platform == "darwin":
                    # macOS
                    subprocess.Popen(['open', '-a', 'Terminal'])
                else:
                    # Linux
                    try:
                        subprocess.Popen(['gnome-terminal'])
                    except:
                        try:
                            subprocess.Popen(['xterm'])
                        except:
                            pass
            
            # 显示成功提示
            snackbar = ft.SnackBar(
                content=ft.Text("命令行已打开，FFmpeg环境已配置"),
                bgcolor=ft.Colors.GREEN,
                duration=2000,
            )
            self.page.overlay.append(snackbar)
            snackbar.open = True
            self.page.update()
        
        # 使用通用方法检查FFmpeg并打开
        self._check_ffmpeg_and_open("FFmpeg终端", open_func)
    
    def _check_ffmpeg_and_open(self, tool_name: str, open_func: Callable) -> None:
        """检查FFmpeg并打开工具（通用方法）。
        
        Args:
            tool_name: 工具名称
            open_func: 打开工具的函数
        """
        if not self.parent_container:
            print("错误: 未设置父容器")
            return
        
        # 检查FFmpeg是否可用
        is_available, _ = self.ffmpeg_service.is_ffmpeg_available()
        
        if not is_available:
            # FFmpeg未安装，显示安装视图
            self._show_ffmpeg_install_view(tool_name)
        else:
            # FFmpeg已安装，执行打开函数
            open_func()
    
    def _open_format_dialog(self, e: ft.ControlEvent) -> None:
        """切换到音频格式转换工具界面。
        
        Args:
            e: 控件事件对象
        """
        def open_func():
            # 创建格式转换视图（如果还没创建）
            if not self.format_view:
                self.format_view = AudioFormatView(
                    self.page,
                    self.config_service,
                    self.audio_service,
                    self.ffmpeg_service,
                    on_back=self._back_to_main
                )
            
            # 记录当前子视图
            self.current_sub_view = self.format_view
            self.current_sub_view_type = "format"
            
            # 切换到格式转换视图
            self.parent_container.content = self.format_view
            self.parent_container.update()
        
        self._check_ffmpeg_and_open("音频格式转换", open_func)
    
    def _open_audio_cut(self, e: ft.ControlEvent) -> None:
        """打开音频剪辑工具（待实现）。
        
        Args:
            e: 控件事件对象
        """
        def open_func():
            # TODO: 实现音频剪辑功能
            self._show_coming_soon_dialog("音频剪辑")
        
        self._check_ffmpeg_and_open("音频剪辑", open_func)
    
    def _open_audio_tune(self, e: ft.ControlEvent) -> None:
        """打开参数调整工具（待实现）。
        
        Args:
            e: 控件事件对象
        """
        def open_func():
            # TODO: 实现参数调整功能
            self._show_coming_soon_dialog("参数调整")
        
        self._check_ffmpeg_and_open("参数调整", open_func)
    
    def _show_coming_soon_dialog(self, feature_name: str) -> None:
        """显示"即将推出"对话框。
        
        Args:
            feature_name: 功能名称
        """
        def close_dialog(dialog_e: ft.ControlEvent) -> None:
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{feature_name}功能"),
            content=ft.Column(
                controls=[
                    ft.Text(f"{feature_name}功能正在开发中，敬请期待！", size=14),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("FFmpeg环境已就绪，可以开始开发这个功能了。", size=12, color=TEXT_SECONDARY),
                ],
                tight=True,
                spacing=PADDING_SMALL,
            ),
            actions=[
                ft.TextButton("确定", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _show_ffmpeg_install_view(self, tool_name: str) -> None:
        """显示FFmpeg安装视图。
        
        Args:
            tool_name: 工具名称
        """
        if not self.parent_container:
            return
        
        # 创建FFmpeg安装视图
        self.ffmpeg_install_view = FFmpegInstallView(
            self.page,
            self.ffmpeg_service,
            on_installed=lambda: self._on_ffmpeg_installed(),
            on_back=self._back_to_main,
            tool_name=tool_name
        )
        
        # 记录当前子视图
        self.current_sub_view = self.ffmpeg_install_view
        self.current_sub_view_type = "ffmpeg_install"
        
        # 切换到安装视图
        self.parent_container.content = self.ffmpeg_install_view
        self.parent_container.update()
    
    def _on_ffmpeg_installed(self) -> None:
        """FFmpeg安装完成回调。"""
        # 返回主界面
        self._back_to_main()
    
    def _back_to_main(self) -> None:
        """返回主界面。"""
        # 销毁当前子视图（而不是保留）
        if self.current_sub_view_type:
            view_map = {
                "format": "format_view",
                "ffmpeg_install": "ffmpeg_install_view",
            }
            view_attr = view_map.get(self.current_sub_view_type)
            if view_attr:
                setattr(self, view_attr, None)
        
        # 清除子视图状态
        self.current_sub_view = None
        self.current_sub_view_type = None
        
        if self.parent_container:
            self.parent_container.content = self
            self.parent_container.update()
    
    def restore_state(self) -> bool:
        """恢复视图状态（从其他页面切换回来时调用）。
        
        Returns:
            是否恢复了子视图（True表示已恢复子视图，False表示需要显示主视图）
        """
        if self.parent_container and self.current_sub_view:
            # 如果之前在子视图中，恢复到子视图
            self.parent_container.content = self.current_sub_view
            self.parent_container.update()
            return True
        return False
