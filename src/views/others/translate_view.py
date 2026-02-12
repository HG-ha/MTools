# -*- coding: utf-8 -*-
"""翻译工具视图模块。

提供文本翻译功能的用户界面，支持 AI 翻译和 Bing 翻译。
"""

import asyncio
import threading
from typing import Optional, TYPE_CHECKING

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services.translate_service import TranslateService, SUPPORTED_LANGUAGES
from services.ai_subtitle_fix_service import AISubtitleFixService
from utils import logger

if TYPE_CHECKING:
    from services.config_service import ConfigService


class TranslateView(ft.Container):
    """翻译工具视图类。
    
    提供文本翻译功能，支持：
    - Bing 翻译（免费，无需配置）
    - AI 翻译（需要配置 API Key，翻译质量更高）
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: 'ConfigService',
        on_back: Optional[callable] = None
    ) -> None:
        """初始化翻译工具视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: 'ConfigService' = config_service
        self.on_back: Optional[callable] = on_back
        
        # 翻译服务
        self.bing_service: TranslateService = TranslateService()
        self.ai_service: AISubtitleFixService = AISubtitleFixService()
        
        # 加载 AI API Key
        api_key = self.config_service.get_config_value("ai_translate_api_key", "")
        self.ai_service.set_api_key(api_key)
        
        self.is_translating: bool = False
        
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
        # 返回按钮和标题
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=lambda _: self.on_back() if self.on_back else None,
                ),
                ft.Text(
                    "文本翻译",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 翻译引擎选择
        self.engine_selector: ft.RadioGroup = ft.RadioGroup(
            value="bing",
            content=ft.Row(
                controls=[
                    ft.Radio(value="bing", label="Bing 翻译（免费）"),
                    ft.Radio(value="ai", label="AI 翻译（更精准）"),
                ],
                spacing=PADDING_LARGE,
            ),
            on_change=self._on_engine_change,
        )
        
        # AI 配置区域
        self.ai_api_key_field: ft.TextField = ft.TextField(
            label="AI API Key",
            hint_text="输入心流开放平台 API Key",
            password=True,
            can_reveal_password=True,
            value=self.config_service.get_config_value("ai_translate_api_key", ""),
            on_change=self._on_api_key_change,
            expand=True,
        )
        
        self.ai_config_container: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            self.ai_api_key_field,
                            ft.TextButton(
                                "获取 API Key",
                                icon=ft.Icons.OPEN_IN_NEW,
                                on_click=lambda _: self._page.launch_url("https://platform.iflow.cn/"),
                            ),
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    ft.Text(
                        "AI 翻译使用心流开放平台的 qwen3-max 模型，翻译质量更高，支持上下文理解",
                        size=12,
                        color=ft.Colors.GREY_600,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            visible=False,
            padding=ft.padding.only(top=PADDING_SMALL),
        )
        
        # 语言选择
        # 源语言选项（包含自动检测）
        source_lang_options = [ft.dropdown.Option("", "自动检测")]
        for code, name in SUPPORTED_LANGUAGES.items():
            source_lang_options.append(ft.dropdown.Option(code, name))
        
        self.source_lang_dropdown: ft.Dropdown = ft.Dropdown(
            label="源语言",
            options=source_lang_options,
            value="",
            width=180,
        )
        
        # 目标语言选项
        target_lang_options = []
        for code, name in SUPPORTED_LANGUAGES.items():
            target_lang_options.append(ft.dropdown.Option(code, name))
        
        self.target_lang_dropdown: ft.Dropdown = ft.Dropdown(
            label="目标语言",
            options=target_lang_options,
            value="zh-Hans",
            width=180,
        )
        
        # 交换按钮
        swap_btn: ft.IconButton = ft.IconButton(
            icon=ft.Icons.SWAP_HORIZ,
            tooltip="交换语言",
            on_click=self._on_swap_lang,
        )
        
        lang_row: ft.Row = ft.Row(
            controls=[
                self.source_lang_dropdown,
                swap_btn,
                self.target_lang_dropdown,
            ],
            spacing=PADDING_SMALL,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 输入文本框
        self.input_text: ft.TextField = ft.TextField(
            label="输入文本",
            hint_text="在此输入或粘贴要翻译的文本...",
            multiline=True,
            expand=True,
            on_change=self._on_input_change,
        )
        
        # 字数统计
        self.char_count_text: ft.Text = ft.Text(
            "0 字符",
            size=12,
            color=ft.Colors.GREY_600,
        )
        
        # 翻译按钮
        self.translate_btn: ft.ElevatedButton = ft.ElevatedButton(
            content="翻译",
            icon=ft.Icons.TRANSLATE,
            on_click=self._on_translate,
            disabled=True,
        )
        
        # 清空按钮
        clear_btn: ft.TextButton = ft.TextButton(
            content="清空",
            icon=ft.Icons.CLEAR_ALL,
            on_click=self._on_clear,
        )
        
        # 进度指示器
        self.progress_ring: ft.ProgressRing = ft.ProgressRing(
            width=20,
            height=20,
            stroke_width=2,
            visible=False,
        )
        
        input_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.input_text,
                    ft.Row(
                        controls=[
                            self.char_count_text,
                            ft.Container(expand=True),
                            clear_btn,
                            self.progress_ring,
                            self.translate_btn,
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
                expand=True,
            ),
            padding=PADDING_MEDIUM,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
            expand=True,
        )
        
        # 输出文本框
        self.output_text: ft.TextField = ft.TextField(
            label="翻译结果",
            hint_text="翻译结果将显示在这里...",
            multiline=True,
            read_only=True,
            expand=True,
        )
        
        # 复制按钮
        self.copy_btn: ft.IconButton = ft.IconButton(
            icon=ft.Icons.COPY,
            tooltip="复制结果",
            on_click=self._on_copy,
            disabled=True,
        )
        
        output_area: ft.Container = ft.Container(
            content=ft.Column(
                controls=[
                    self.output_text,
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            self.copy_btn,
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=PADDING_SMALL,
                expand=True,
            ),
            padding=PADDING_MEDIUM,
            border_radius=BORDER_RADIUS_MEDIUM,
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
            expand=True,
        )
        
        # 翻译区域（左右布局）
        translate_area: ft.Row = ft.Row(
            controls=[
                ft.Container(content=input_area, expand=True),
                ft.Container(content=output_area, expand=True),
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )
        
        # 主内容
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(height=1),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("翻译引擎", weight=ft.FontWeight.W_500),
                            self.engine_selector,
                            self.ai_config_container,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    padding=ft.padding.only(bottom=PADDING_SMALL),
                ),
                lang_row,
                translate_area,
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )
    
    def _on_engine_change(self, e) -> None:
        """翻译引擎切换事件。"""
        is_ai = self.engine_selector.value == "ai"
        self.ai_config_container.visible = is_ai
        self._safe_update()
    
    def _on_api_key_change(self, e) -> None:
        """API Key 变更事件。"""
        api_key = self.ai_api_key_field.value.strip()
        self.ai_service.set_api_key(api_key)
        self.config_service.set_config_value("ai_translate_api_key", api_key)
    
    def _on_swap_lang(self, e) -> None:
        """交换源语言和目标语言。"""
        source = self.source_lang_dropdown.value
        target = self.target_lang_dropdown.value
        
        # 如果源语言是自动检测，不能交换
        if not source:
            self._show_message("源语言为自动检测时无法交换", is_error=True)
            return
        
        self.source_lang_dropdown.value = target
        self.target_lang_dropdown.value = source
        
        # 同时交换输入和输出文本
        input_val = self.input_text.value
        output_val = self.output_text.value
        
        if output_val:
            self.input_text.value = output_val
            self.output_text.value = input_val
            self._update_char_count()
        
        self._safe_update()
    
    def _on_input_change(self, e) -> None:
        """输入文本变更事件。"""
        self._update_char_count()
        has_text = bool(self.input_text.value and self.input_text.value.strip())
        self.translate_btn.disabled = not has_text or self.is_translating
        self._safe_update()
    
    def _update_char_count(self) -> None:
        """更新字数统计。"""
        text = self.input_text.value or ""
        self.char_count_text.value = f"{len(text)} 字符"
    
    def _on_clear(self, e) -> None:
        """清空输入和输出。"""
        self.input_text.value = ""
        self.output_text.value = ""
        self.copy_btn.disabled = True
        self.translate_btn.disabled = True
        self._update_char_count()
        self._safe_update()
    
    async def _on_translate(self, e) -> None:
        """执行翻译。"""
        text = self.input_text.value
        if not text or not text.strip():
            return
        
        engine = self.engine_selector.value
        
        # AI 翻译需要检查 API Key
        if engine == "ai" and not self.ai_service.is_configured():
            self._show_message("请先配置 AI API Key", is_error=True)
            return
        
        self.is_translating = True
        self.translate_btn.disabled = True
        self.progress_ring.visible = True
        self._safe_update()
        
        try:
            source_lang = self.source_lang_dropdown.value
            target_lang = self.target_lang_dropdown.value
            
            if engine == "bing":
                # Bing 翻译（异步，直接 await）
                result = await self.bing_service.translate(text, target_lang, source_lang)
                
                if result["code"] == 200:
                    translated = result["data"]["text"]
                else:
                    raise ValueError(result["message"])
            else:
                # AI 翻译（同步方法，用 asyncio.to_thread 在线程池中执行）
                ai_target = self._convert_lang_code(target_lang)
                ai_source = self._convert_lang_code(source_lang) if source_lang else "auto"
                translated = await asyncio.to_thread(
                    self.ai_service.translate_text, text, ai_target, ai_source
                )
            
            # 更新 UI（在主事件循环中，update 可以正常工作）
            self.output_text.value = translated
            self.copy_btn.disabled = False
            logger.info(f"翻译完成 ({engine}): {len(text)} -> {len(translated)} 字符")
            
        except Exception as ex:
            logger.error(f"翻译失败: {ex}")
            self._show_message(f"翻译失败: {ex}", is_error=True)
        
        finally:
            self.is_translating = False
            self.translate_btn.disabled = False
            self.progress_ring.visible = False
            self._safe_update()
    
    def _convert_lang_code(self, code: str) -> str:
        """转换语言代码为 AI 服务支持的格式。"""
        mapping = {
            "zh-Hans": "zh",
            "zh-Hant": "zh",
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "fr": "fr",
            "de": "de",
            "es": "es",
            "it": "it",
            "pt": "pt",
            "ru": "ru",
        }
        return mapping.get(code, code)
    
    async def _on_copy(self, e) -> None:
        """复制翻译结果。"""
        text = self.output_text.value
        if text:
            await ft.Clipboard().set(text)
            self._show_message("已复制到剪贴板")
    
    def _show_message(self, message: str, is_error: bool = False) -> None:
        """显示消息提示。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.ERROR if is_error else None,
            duration=3000,
        )
        self._page.open(snackbar)
    
    def _safe_update(self) -> None:
        """安全更新页面。"""
        try:
            self._page.update()
        except Exception:
            pass
    
    def cleanup(self) -> None:
        """清理资源。"""
        pass
    
    def add_files(self, files: list) -> None:
        """处理拖放的文件。
        
        支持文本文件：.txt, .md, .json, .xml, .html, .csv, .log 等
        
        Args:
            files: 文件路径列表
        """
        from pathlib import Path
        
        # 支持的文本文件扩展名
        text_exts = {
            '.txt', '.md', '.markdown', '.json', '.xml', '.html', '.htm',
            '.csv', '.log', '.ini', '.cfg', '.conf', '.yaml', '.yml',
            '.srt', '.vtt', '.ass', '.lrc',  # 字幕文件
            '.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.cs',  # 代码文件
            '.css', '.sql', '.sh', '.bat', '.ps1',
        }
        
        # 收集所有文件
        all_files = []
        for f in files:
            path = Path(f) if not isinstance(f, Path) else f
            if path.is_dir():
                for item in path.iterdir():
                    if item.is_file():
                        all_files.append(item)
            else:
                all_files.append(path)
        
        # 过滤支持的文件
        supported_files = [f for f in all_files if f.suffix.lower() in text_exts]
        
        if not supported_files:
            self._show_message("请拖放文本文件（.txt, .md 等）", is_error=True)
            return
        
        # 只处理第一个文件
        file_path = supported_files[0]
        
        try:
            # 尝试多种编码读取文件
            content = None
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if content is None:
                self._show_message(f"无法读取文件：编码不支持", is_error=True)
                return
            
            # 限制文本长度（避免翻译过长文本）
            max_chars = 10000
            if len(content) > max_chars:
                content = content[:max_chars]
                self._show_message(f"文件内容过长，已截取前 {max_chars} 字符")
            
            # 设置到输入框
            self.input_text.value = content
            self._update_char_count()
            self.translate_btn.disabled = False
            self._safe_update()
            
            self._show_message(f"已导入: {file_path.name}")
            
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            self._show_message(f"读取文件失败: {e}", is_error=True)

