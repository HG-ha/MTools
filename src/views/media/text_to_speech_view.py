# -*- coding: utf-8 -*-
"""文字转语音视图模块。

提供 TTS 文字转语音功能的用户界面。
"""

import asyncio
import time
from pathlib import Path
from typing import Callable, Optional

import flet as ft
import flet_audio as fta

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_TTS_MODEL_KEY,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    TTS_MODELS,
)
from services import ConfigService, FFmpegService
from services.tts_service import TTSService
from utils import logger, get_unique_path
from utils.file_utils import pick_files, get_directory_path

_VOICE_PREFIX_LABELS: dict[str, str] = {
    "af": "美式英语·女", "am": "美式英语·男",
    "bf": "英式英语·女", "bm": "英式英语·男",
    "ef": "西班牙语·女", "em": "西班牙语·男",
    "ff": "法语·女",
    "hf": "印地语·女", "hm": "印地语·男",
    "if": "意大利语·女", "im": "意大利语·男",
    "jf": "日语·女", "jm": "日语·男",
    "pf": "葡萄牙语·女", "pm": "葡萄牙语·男",
    "zf": "中文·女", "zm": "中文·男",
}


def _format_speaker_name(name: str) -> str:
    prefix = name[:2] if len(name) >= 2 else ""
    label = _VOICE_PREFIX_LABELS.get(prefix, "")
    return f"{name}  ({label})" if label else name


class TextToSpeechView(ft.Container):
    """文字转语音视图类。"""

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        ffmpeg_service: FFmpegService,
        on_back: Optional[Callable] = None,
    ) -> None:
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.ffmpeg_service: FFmpegService = ffmpeg_service
        self.on_back: Optional[Callable] = on_back

        self.is_processing: bool = False
        self.is_downloading: bool = False

        self.expand = True
        self.padding = ft.Padding.only(
            left=PADDING_MEDIUM, right=PADDING_MEDIUM,
            top=PADDING_MEDIUM, bottom=PADDING_MEDIUM,
        )

        model_dir = self.config_service.get_data_dir() / "models" / "tts"
        self.tts_service = TTSService(
            model_dir=model_dir,
            ffmpeg_service=ffmpeg_service,
        )

        self._last_generated_file: Optional[Path] = None
        self.audio_player: Optional[fta.Audio] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _on_back_click(self, e=None) -> None:
        if self.on_back:
            self.on_back()

    def _build_ui(self) -> None:
        header = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="返回", on_click=self._on_back_click),
                ft.Text("文字转语音", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )

        # ── Text input area ──
        self.text_input = ft.TextField(
            label="输入要转换的文字（支持中英文混合）",
            multiline=True,
            min_lines=6,
            max_lines=12,
            expand=True,
            on_change=self._on_text_change,
        )
        self.char_count_text = ft.Text("0 字", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

        text_input_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("文本输入:", size=14, weight=ft.FontWeight.W_500),
                        ft.Container(expand=True),
                        self.char_count_text,
                    ],
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "长文本会自动分段合成，短文本可直接试听",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.Margin.only(left=4, bottom=4),
                ),
                self.text_input,
            ],
            spacing=PADDING_SMALL,
        )

        # ── Left: Model & Voice settings ──
        saved_model = self.config_service.get_config_value("tts_model_key", DEFAULT_TTS_MODEL_KEY)
        model_options = [
            ft.dropdown.Option(key=k, text=info.display_name)
            for k, info in TTS_MODELS.items()
        ]

        self.model_dropdown = ft.Dropdown(
            options=model_options,
            value=saved_model if saved_model in TTS_MODELS else DEFAULT_TTS_MODEL_KEY,
            label="TTS 模型",
            dense=True,
            on_select=self._on_model_select,
        )

        self.model_info_text = ft.Text("", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

        self.model_status_icon = ft.Icon(
            ft.Icons.CLOUD_DOWNLOAD, size=20, color=ft.Colors.ORANGE,
        )
        self.model_status_text = ft.Text(
            "未下载", size=13, color=ft.Colors.ON_SURFACE_VARIANT,
        )

        self.download_button = ft.Button(
            "下载模型", icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download_click,
            visible=False,
        )
        self.load_button = ft.Button(
            "加载模型", icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_click,
            visible=False,
        )
        self.unload_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型",
            on_click=self._on_unload_click,
            visible=False,
        )
        self.delete_model_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model,
            visible=False,
        )

        self.model_status_row = ft.Row(
            controls=[
                self.model_status_icon,
                self.model_status_text,
                self.download_button,
                self.load_button,
                self.unload_button,
                self.delete_model_button,
            ],
            spacing=PADDING_SMALL,
        )

        self._update_model_info()
        self._update_model_status()

        # Speaker - named dropdown (for models with speaker_names)
        self.speaker_dropdown = ft.Dropdown(
            label="说话人",
            dense=True,
            on_select=self._on_speaker_dropdown_change,
            visible=False,
        )
        # Speaker - numeric controls (for models without speaker_names)
        self.speaker_input = ft.TextField(
            label="说话人 ID",
            value="0",
            width=100,
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=self._on_speaker_input_change,
        )
        self.speaker_total_text = ft.Text("/ 0", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.speaker_slider = ft.Slider(
            min=0, max=0, divisions=1, value=0,
            label="{value}",
            on_change=self._on_speaker_slider_change,
        )
        self.speaker_prev_btn = ft.IconButton(
            icon=ft.Icons.SKIP_PREVIOUS, tooltip="上一个",
            on_click=self._on_speaker_prev, icon_size=18,
        )
        self.speaker_next_btn = ft.IconButton(
            icon=ft.Icons.SKIP_NEXT, tooltip="下一个",
            on_click=self._on_speaker_next, icon_size=18,
        )
        self.speaker_id_row = ft.Row(
            controls=[
                ft.Text("说话人:", size=13),
                self.speaker_input,
                self.speaker_total_text,
                self.speaker_prev_btn,
                self.speaker_next_btn,
            ],
            spacing=PADDING_SMALL,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False,
        )
        self.speaker_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.speaker_dropdown,
                    self.speaker_id_row,
                    self.speaker_slider,
                ],
                spacing=2,
            ),
            visible=False,
        )

        # Speed
        self.speed_slider = ft.Slider(
            min=0.5, max=2.0, divisions=15, value=1.0,
            label="{value}x",
            on_change=self._on_speed_change,
            expand=True,
        )
        self.speed_label = ft.Text("语速: 1.0x", size=13, width=80, no_wrap=True)

        model_settings_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("模型设置", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.model_dropdown,
                    self.model_info_text,
                    self.model_status_row,
                    ft.Divider(),
                    ft.Text("语音设置", size=14, weight=ft.FontWeight.W_500),
                    self.speaker_container,
                    ft.Row(
                        controls=[self.speed_label, self.speed_slider],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=PADDING_SMALL,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )

        # ── Right: Output settings ──
        self.format_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(key="wav", text="WAV（无损）"),
                ft.dropdown.Option(key="mp3", text="MP3（压缩）"),
            ],
            value=self.config_service.get_config_value("tts_output_format", "wav"),
            label="输出格式",
            dense=True,
            on_select=self._on_format_change,
        )

        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="default", label="默认输出目录"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_SMALL // 2,
            ),
            value=self.config_service.get_config_value("tts_output_mode", "default"),
            on_change=self._on_output_mode_change,
        )

        self._default_output_dir = self.config_service.get_output_dir() / "tts_output"
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self._default_output_dir),
            disabled=True,
            expand=True,
            dense=True,
        )
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )

        output_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("输出选项", size=14, weight=ft.FontWeight.W_500),
                    ft.Container(height=PADDING_SMALL),
                    self.format_dropdown,
                    ft.Container(height=PADDING_MEDIUM),
                    ft.Text("输出路径:", size=13),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[self.custom_output_dir, self.browse_output_button],
                        spacing=PADDING_SMALL,
                    ),
                ],
                spacing=PADDING_SMALL,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )

        # ── Progress ──
        self.progress_bar = ft.ProgressBar(value=0, bar_height=8)
        self.progress_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.progress_container = ft.Container(
            content=ft.Column(
                controls=[self.progress_bar, self.progress_text],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            visible=False,
        )

        # ── Bottom buttons ──
        self.generate_button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE_ALT, size=24),
                    ft.Text("生成语音文件", size=18, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=PADDING_MEDIUM,
            ),
            on_click=self._on_generate_click,
            disabled=True,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
            ),
        )
        self.preview_button = ft.Button(
            "试听结果", icon=ft.Icons.HEADPHONES,
            on_click=self._on_preview_click,
            disabled=True,
        )
        self.stop_button = ft.Button(
            "停止播放", icon=ft.Icons.STOP,
            on_click=self._on_stop_click,
            visible=False,
        )
        self.batch_button = ft.Button(
            "批量 TXT 转语音", icon=ft.Icons.FOLDER_OPEN,
            on_click=self._on_batch_click,
            disabled=True,
        )

        generate_container = ft.Container(
            content=self.generate_button,
            alignment=ft.Alignment.CENTER,
            margin=ft.Margin.only(top=PADDING_MEDIUM, bottom=PADDING_SMALL),
        )

        button_row = ft.Container(
            content=ft.Row(
                controls=[
                    self.preview_button,
                    self.stop_button,
                    ft.Container(expand=True),
                    self.batch_button,
                ],
                spacing=PADDING_MEDIUM,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            margin=ft.Margin.only(top=PADDING_SMALL),
        )

        # ── Main layout (vertical scroll) ──
        main_content = ft.Column(
            controls=[
                text_input_area,
                ft.Container(height=PADDING_LARGE),
                ft.Row(
                    controls=[
                        ft.Container(content=model_settings_section, expand=True, height=450),
                        ft.Container(content=output_section, expand=True, height=450),
                    ],
                    spacing=PADDING_LARGE,
                ),
                ft.Container(height=PADDING_MEDIUM),
                self.progress_container,
                generate_container,
                button_row,
                ft.Container(height=PADDING_LARGE),
            ],
            scroll=ft.ScrollMode.HIDDEN,
            spacing=0,
            expand=True,
        )

        self.content = ft.Column(
            controls=[header, ft.Divider(), main_content],
            spacing=0,
            expand=True,
        )

        self._refresh_button_states()
        self._update_output_controls()

    # ------------------------------------------------------------------
    # Model info
    # ------------------------------------------------------------------

    def _update_model_info(self, actual_num_speakers: int = 0) -> None:
        key = self.model_dropdown.value
        info = TTS_MODELS.get(key)
        if info:
            num_spk = actual_num_speakers if actual_num_speakers > 0 else info.num_speakers
            lines = [
                f"架构: {info.model_type.upper()}",
                f"语言: {info.language_support}",
                f"说话人: {num_spk}",
                f"大小: ~{info.size_mb} MB",
                f"说明: {info.quality}",
                f"性能: {info.performance}",
            ]
            self.model_info_text.value = "\n".join(lines)
        else:
            self.model_info_text.value = ""

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _check_model_downloaded(self, key: str) -> bool:
        info = TTS_MODELS.get(key)
        if not info:
            return False
        model_dir = self.tts_service.get_model_dir(key)
        model_path = model_dir / info.model_filename
        tokens_path = model_dir / info.tokens_filename
        return model_path.exists() and tokens_path.exists()

    def _update_model_status(self) -> None:
        key = self.model_dropdown.value
        info = TTS_MODELS.get(key)
        if not info:
            return

        if self.tts_service.is_loaded() and self.tts_service.current_model == key:
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已加载"
            self.download_button.visible = False
            self.load_button.visible = False
            self.unload_button.visible = True
            self.delete_model_button.visible = False
        elif self._check_model_downloaded(key):
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.model_status_text.value = f"已下载 (~{info.size_mb}MB)"
            self.download_button.visible = False
            self.load_button.visible = True
            self.unload_button.visible = False
            self.delete_model_button.visible = True
        else:
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.ORANGE
            self.model_status_text.value = "未下载"
            self.download_button.visible = True
            self.load_button.visible = False
            self.unload_button.visible = False
            self.delete_model_button.visible = False

    def _on_model_select(self, e) -> None:
        key = self.model_dropdown.value
        self.config_service.set_config_value("tts_model_key", key)
        self._update_model_info()
        self._update_model_status()
        self._refresh_button_states()
        self._page.update()

    def _on_format_change(self, e) -> None:
        self.config_service.set_config_value("tts_output_format", self.format_dropdown.value)

    def _on_speaker_dropdown_change(self, e) -> None:
        pass

    def _on_speaker_slider_change(self, e) -> None:
        val = int(self.speaker_slider.value)
        self.speaker_input.value = str(val)
        self._page.update()

    def _on_speaker_input_change(self, e) -> None:
        text = (self.speaker_input.value or "").strip()
        if not text:
            return
        try:
            val = int(text)
            max_val = int(self.speaker_slider.max)
            val = max(0, min(val, max_val))
            self.speaker_slider.value = val
            if str(val) != text:
                self.speaker_input.value = str(val)
            self._page.update()
        except ValueError:
            pass

    def _on_speaker_prev(self, e) -> None:
        val = max(0, int(self.speaker_slider.value) - 1)
        self.speaker_slider.value = val
        self.speaker_input.value = str(val)
        self._page.update()

    def _on_speaker_next(self, e) -> None:
        max_val = int(self.speaker_slider.max)
        val = min(max_val, int(self.speaker_slider.value) + 1)
        self.speaker_slider.value = val
        self.speaker_input.value = str(val)
        self._page.update()

    def _on_speed_change(self, e) -> None:
        val = round(self.speed_slider.value, 1)
        self.speed_label.value = f"语速: {val}x"
        self._page.update()

    def _on_text_change(self, e) -> None:
        text = self.text_input.value or ""
        self.char_count_text.value = f"{len(text)} 字"
        self._refresh_button_states()
        self._page.update()

    def _on_output_mode_change(self, e) -> None:
        mode = self.output_mode_radio.value
        self.config_service.set_config_value("tts_output_mode", mode)
        self._update_output_controls()
        self._page.update()

    def _update_output_controls(self) -> None:
        is_custom = self.output_mode_radio.value == "custom"
        self.custom_output_dir.disabled = not is_custom
        self.browse_output_button.disabled = not is_custom

    async def _on_browse_output(self, e) -> None:
        result = await get_directory_path(self._page, dialog_title="选择输出目录")
        if result:
            self.custom_output_dir.value = result
            self._page.update()

    def _get_output_dir(self) -> Path:
        if self.output_mode_radio.value == "custom":
            return Path(self.custom_output_dir.value)
        return self._default_output_dir

    # ------------------------------------------------------------------
    # Download / Load / Unload
    # ------------------------------------------------------------------

    async def _on_download_click(self, e) -> None:
        if self.is_downloading:
            return
        key = self.model_dropdown.value
        info = TTS_MODELS.get(key)
        if not info:
            return

        self.is_downloading = True
        self.download_button.visible = False
        self.model_status_icon.name = ft.Icons.DOWNLOADING
        self.model_status_icon.color = ft.Colors.BLUE
        self.model_status_text.value = "正在下载..."
        self.progress_container.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "准备下载..."
        self._page.update()

        try:
            def on_progress(progress: float, message: str):
                self.progress_bar.value = progress
                self.progress_text.value = message
                self._page.update()

            await asyncio.to_thread(
                self.tts_service.download_model, key, info, on_progress
            )

            self._show_snackbar("模型下载完成", ft.Colors.GREEN)
        except Exception as ex:
            logger.error(f"TTS 模型下载失败: {ex}")
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"下载失败: {str(ex)[:60]}"
            self.download_button.visible = True
            self._show_snackbar(f"下载失败: {ex}", ft.Colors.ERROR)
        finally:
            self.is_downloading = False
            self.progress_container.visible = False
            self._update_model_status()
            self._refresh_button_states()
            self._page.update()

    async def _on_load_click(self, e) -> None:
        key = self.model_dropdown.value
        info = TTS_MODELS.get(key)
        if not info:
            return

        self.load_button.visible = False
        self.delete_model_button.visible = False
        self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
        self.model_status_icon.color = ft.Colors.BLUE
        self.model_status_text.value = "正在加载..."
        self._page.update()

        try:
            await asyncio.to_thread(
                self.tts_service.load_model,
                key, info, None, 4,
            )

            num_speakers = self.tts_service.get_num_speakers()
            if num_speakers > 1 and info.speaker_names:
                options = [
                    ft.dropdown.Option(
                        key=str(sid),
                        text=_format_speaker_name(name),
                    )
                    for sid, name in sorted(info.speaker_names.items())
                ]
                self.speaker_dropdown.options = options
                self.speaker_dropdown.value = "0"
                self.speaker_dropdown.visible = True
                self.speaker_id_row.visible = False
                self.speaker_slider.visible = False
                self.speaker_container.visible = True
            elif num_speakers > 1:
                self.speaker_slider.max = num_speakers - 1
                self.speaker_slider.divisions = min(num_speakers - 1, 100)
                self.speaker_slider.value = 0
                self.speaker_input.value = "0"
                self.speaker_total_text.value = f"/ {num_speakers - 1}"
                self.speaker_dropdown.visible = False
                self.speaker_id_row.visible = True
                self.speaker_slider.visible = True
                self.speaker_container.visible = True
            else:
                self.speaker_container.visible = False

            self._update_model_info(actual_num_speakers=num_speakers)
            self._show_snackbar("模型加载成功", ft.Colors.GREEN)
        except Exception as ex:
            logger.error(f"TTS 模型加载失败: {ex}")
            self.model_status_icon.name = ft.Icons.ERROR
            self.model_status_icon.color = ft.Colors.ERROR
            self.model_status_text.value = f"加载失败: {str(ex)[:60]}"
            self._show_snackbar(f"加载失败: {ex}", ft.Colors.ERROR)
        finally:
            self._update_model_status()
            self._refresh_button_states()
            self._page.update()

    def _on_unload_click(self, e) -> None:
        self.tts_service.unload_model()
        self.speaker_container.visible = False
        self._update_model_status()
        self._refresh_button_states()
        self._page.update()

    async def _on_delete_model(self, e) -> None:
        key = self.model_dropdown.value
        info = TTS_MODELS.get(key)
        if not info:
            return
        import shutil
        model_dir = self.tts_service.get_model_dir(key)
        if model_dir.exists():
            try:
                shutil.rmtree(model_dir)
                self._show_snackbar("模型已删除", ft.Colors.GREEN)
            except Exception as ex:
                self._show_snackbar(f"删除失败: {ex}", ft.Colors.ERROR)
        self._update_model_status()
        self._refresh_button_states()
        self._page.update()

    # ------------------------------------------------------------------
    # Preview (play last generated file)
    # ------------------------------------------------------------------

    async def _on_preview_click(self, e) -> None:
        if not self._last_generated_file or not self._last_generated_file.exists():
            self._show_snackbar("请先生成语音文件", ft.Colors.ORANGE)
            return

        await self._stop_audio()

        self.audio_player = fta.Audio(
            src=str(self._last_generated_file),
            autoplay=True,
            volume=1.0,
        )
        self._page.services.append(self.audio_player)
        self.stop_button.visible = True
        self._page.update()

    async def _on_stop_click(self, e) -> None:
        await self._stop_audio()
        self.stop_button.visible = False
        self._page.update()

    async def _stop_audio(self) -> None:
        if self.audio_player is not None:
            try:
                await self.audio_player.pause()
                if self.audio_player in self._page.services:
                    self._page.services.remove(self.audio_player)
            except Exception:
                pass
            self.audio_player = None

    # ------------------------------------------------------------------
    # Generate file
    # ------------------------------------------------------------------

    async def _on_generate_click(self, e) -> None:
        text = (self.text_input.value or "").strip()
        if not text or not self.tts_service.is_loaded():
            return

        fmt = self.format_dropdown.value or "wav"
        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
        output_path = get_unique_path(output_dir / f"tts_output.{fmt}", add_sequence=add_sequence)
        await self._do_generate(text, output_path, fmt)

    async def _do_generate(self, text: str, output_path: Path, fmt: str) -> None:
        if self.is_processing:
            return
        self.is_processing = True
        self.generate_button.disabled = True
        self.progress_container.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "正在合成..."
        self._page.update()

        try:
            sid = self._get_speaker_id()
            speed = round(self.speed_slider.value, 1)

            last_ui_update = [0.0]

            def on_progress(current: int, total: int):
                if total > 0:
                    now = time.monotonic()
                    if current >= total or now - last_ui_update[0] > 0.5:
                        self.progress_bar.value = current / total
                        self.progress_text.value = f"合成中: {current}/{total} 段"
                        self._page.update()
                        last_ui_update[0] = now

            await asyncio.to_thread(
                self.tts_service.generate_to_file,
                text, output_path, sid, speed, fmt, on_progress,
            )

            self._last_generated_file = output_path
            self.progress_bar.value = 1.0
            self.progress_text.value = f"已保存: {output_path}"
            self._show_snackbar(f"已保存: {output_path.name}", ft.Colors.GREEN)
        except Exception as ex:
            logger.error(f"TTS 生成失败: {ex}")
            self.progress_text.value = f"生成失败: {str(ex)[:60]}"
            self._show_snackbar(f"生成失败: {ex}", ft.Colors.ERROR)
        finally:
            self.is_processing = False
            self._refresh_button_states()
            self._page.update()

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    async def _on_batch_click(self, e) -> None:
        if not self.tts_service.is_loaded() or self.is_processing:
            return

        result = await pick_files(
            self._page,
            dialog_title="选择 TXT 文件",
            allowed_extensions=["txt"],
            allow_multiple=True,
        )
        if not result:
            return

        txt_files = [Path(f.path) for f in result]
        if not txt_files:
            return

        output_dir = self._get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        fmt = self.format_dropdown.value or "wav"
        sid = self._get_speaker_id()
        speed = round(self.speed_slider.value, 1)

        self.is_processing = True
        self.batch_button.disabled = True
        self.progress_container.visible = True
        self._page.update()

        try:
            total_files = len(txt_files)
            for file_idx, txt_file in enumerate(txt_files):
                self.progress_bar.value = file_idx / total_files
                self.progress_text.value = f"处理文件 {file_idx + 1}/{total_files}: {txt_file.name}"
                self._page.update()

                try:
                    text = txt_file.read_text(encoding="utf-8").strip()
                except UnicodeDecodeError:
                    text = txt_file.read_text(encoding="gbk", errors="replace").strip()

                if not text:
                    continue

                output_name = txt_file.stem + f".{fmt}"
                add_sequence = self.config_service.get_config_value("output_add_sequence", False)
                output_path = get_unique_path(output_dir / output_name, add_sequence=add_sequence)

                batch_last_update = [0.0]

                def on_seg_progress(current: int, total: int, _fi=file_idx):
                    if total > 0:
                        now = time.monotonic()
                        if current >= total or now - batch_last_update[0] > 0.5:
                            file_progress = (_fi + current / total) / total_files
                            self.progress_bar.value = file_progress
                            self.progress_text.value = (
                                f"文件 {_fi + 1}/{total_files} | 段 {current}/{total}"
                            )
                            self._page.update()
                            batch_last_update[0] = now

                await asyncio.to_thread(
                    self.tts_service.generate_to_file,
                    text, output_path, sid, speed, fmt, on_seg_progress,
                )

            self.progress_bar.value = 1.0
            self.progress_text.value = f"批量完成: 共 {total_files} 个文件 → {output_dir}"
            self._show_snackbar(f"批量转换完成: {total_files} 个文件", ft.Colors.GREEN)
        except Exception as ex:
            logger.error(f"TTS 批量处理失败: {ex}")
            self._show_snackbar(f"批量处理失败: {ex}", ft.Colors.ERROR)
        finally:
            self.is_processing = False
            self._refresh_button_states()
            self._page.update()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_speaker_id(self) -> int:
        if not self.speaker_container.visible:
            return 0
        if self.speaker_dropdown.visible:
            return int(self.speaker_dropdown.value or "0")
        return int(self.speaker_slider.value)

    def _refresh_button_states(self) -> None:
        loaded = self.tts_service.is_loaded()
        has_text = bool((self.text_input.value or "").strip())
        has_file = (
            self._last_generated_file is not None
            and self._last_generated_file.exists()
        )

        self.model_dropdown.disabled = self.is_downloading or self.is_processing

        self.preview_button.disabled = not has_file or self.is_processing
        self.generate_button.disabled = not (loaded and has_text) or self.is_processing
        self.batch_button.disabled = not loaded or self.is_processing

    def _show_snackbar(self, message: str, color: str = None) -> None:
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE if color else None),
            bgcolor=color,
            duration=3000,
        )
        self._page.show_dialog(snackbar)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        import gc

        if self.audio_player is not None:
            try:
                if self.audio_player in self._page.services:
                    self._page.services.remove(self.audio_player)
            except Exception:
                pass
            self.audio_player = None

        self._last_generated_file = None
        self.tts_service.cleanup()
        self.on_back = None
        self.content = None
        gc.collect()
