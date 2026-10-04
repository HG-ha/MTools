# -*- coding: utf-8 -*-
"""深度估计视图。

图片、动态图和视频共用，图片工具与媒体工具都会打开这个界面。
"""

from pathlib import Path
from typing import Callable, List, Optional

import flet as ft

from constants import (
    BORDER_RADIUS_MEDIUM,
    DEFAULT_DEPTH_MODEL_KEY,
    DEPTH_MODELS,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services import ConfigService, ImageService
from services.depth_service import VIDEO_EXTENSIONS, DepthEstimator, is_animated_image, is_video_path
from utils import get_unique_path, logger
from utils.file_utils import format_file_size, get_directory_path, pick_files


class ImageDepthView(ft.Container):
    """用 Depth Anything V2 估计图片、动态图和视频的深度。"""

    SUPPORTED_EXTENSIONS = {
        ".jpg", ".jpeg", ".jfif", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".apng",
        *VIDEO_EXTENSIONS,
    }

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None,
    ) -> None:
        super().__init__()
        self._page = page
        self.config_service = config_service
        self.image_service = image_service
        self.on_back = on_back
        self.selected_files: List[Path] = []
        self.estimator: Optional[DepthEstimator] = None
        self.is_model_loading = False
        self.expand = True
        self.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM,
        )

        saved = self.config_service.get_config_value("depth_model_key", DEFAULT_DEPTH_MODEL_KEY)
        if saved not in DEPTH_MODELS:
            saved = DEFAULT_DEPTH_MODEL_KEY
        self.current_model_key = saved
        self._job_progress = (0, 1, "")
        self._build_ui()

    def _model(self):
        return DEPTH_MODELS[self.current_model_key]

    def _model_path(self) -> Path:
        model = self._model()
        return (
            self.config_service.get_data_dir()
            / "models"
            / "depth_anything"
            / model.version
            / model.filename
        )

    def _build_ui(self) -> None:
        header = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="返回", on_click=self._on_back),
                ft.Text("深度估计", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )

        self.file_list_view = ft.Column(spacing=PADDING_MEDIUM // 2, scroll=ft.ScrollMode.ADAPTIVE)
        file_select_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("选择文件:", size=14, weight=ft.FontWeight.W_500),
                        ft.Button("选择文件", icon=ft.Icons.FILE_UPLOAD, on_click=self._on_select_files),
                        ft.Button("选择文件夹", icon=ft.Icons.FOLDER_OPEN, on_click=self._on_select_folder),
                        ft.TextButton("清空列表", icon=ft.Icons.CLEAR_ALL, on_click=self._on_clear),
                    ],
                    spacing=PADDING_MEDIUM,
                    wrap=True,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "支持 JPG/PNG/WebP、GIF/动态 WebP/APNG，以及 MP4/MOV/MKV 等视频",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=8,
                    ),
                    margin=ft.Margin.only(left=4, bottom=4),
                ),
                ft.Container(
                    content=self.file_list_view,
                    expand=True,
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=BORDER_RADIUS_MEDIUM,
                    padding=PADDING_MEDIUM,
                ),
            ],
            spacing=PADDING_MEDIUM,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.model_selector = ft.Dropdown(
            options=[
                ft.dropdown.Option(key=key, text=f"{model.display_name}  |  {model.size_mb}MB")
                for key, model in DEPTH_MODELS.items()
            ],
            value=self.current_model_key,
            label="选择模型",
            hint_text="选择深度模型",
            on_select=self._on_model_change,
            width=320,
            dense=True,
            text_size=13,
        )
        self.model_info_text = ft.Text(
            self._model_info_label(),
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.model_status_icon = ft.Icon(ft.Icons.HOURGLASS_EMPTY, size=20, color=ft.Colors.ON_SURFACE_VARIANT)
        self.model_status_text = ft.Text("正在检查模型...", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.download_model_button = ft.Button(
            content="下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_download,
            visible=False,
        )
        self.load_model_button = ft.Button(
            content="加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model,
            visible=False,
        )
        self.unload_model_button = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型（释放内存）",
            on_click=self._on_unload_model,
            visible=False,
        )
        self.delete_model_button = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model,
            visible=False,
        )
        saved_color = bool(self.config_service.get_config_value("depth_colorize", False))
        self.color_switch = ft.Switch(
            label="彩色深度图（关闭为灰度）",
            value=saved_color,
            on_change=self._on_color_change,
        )
        self.output_mode_radio = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="new", label="保存为新文件（添加后缀 _depth）"),
                    ft.Radio(value="custom", label="自定义输出目录"),
                ],
                spacing=PADDING_MEDIUM // 2,
            ),
            value="new",
            on_change=self._on_output_mode_change,
        )
        self.custom_output_dir = ft.TextField(
            label="输出目录",
            value=str(self.config_service.get_data_dir() / "depth"),
            disabled=True,
            expand=True,
        )
        self.browse_output_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="浏览",
            on_click=self._on_browse_output,
            disabled=True,
        )

        process_options = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("处理选项:", size=14, weight=ft.FontWeight.W_500),
                    self.model_selector,
                    self.model_info_text,
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            self.model_status_icon,
                            self.model_status_text,
                            self.download_model_button,
                            self.load_model_button,
                            self.unload_model_button,
                            self.delete_model_button,
                        ],
                        spacing=PADDING_MEDIUM // 2,
                        wrap=True,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    self.color_switch,
                    ft.Text(
                        "相对深度适合预览；室内/室外模型输出近似米制距离。动态图保留帧间隔，视频保留原音轨。",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    self.output_mode_radio,
                    ft.Row(
                        controls=[self.custom_output_dir, self.browse_output_button],
                        spacing=PADDING_MEDIUM // 2,
                    ),
                ],
                spacing=PADDING_MEDIUM // 2,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )

        main_content = ft.Row(
            controls=[
                ft.Container(content=file_select_area, expand=3, height=420),
                ft.Container(content=process_options, expand=2, height=420),
            ],
            spacing=PADDING_LARGE,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        self.progress_bar = ft.ProgressBar(value=0, visible=False)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        self.process_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LAYERS, size=24),
                        ft.Text("开始估计", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_process,
                disabled=True,
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Column(
                    controls=[
                        main_content,
                        ft.Container(height=PADDING_LARGE),
                        self.progress_bar,
                        self.progress_text,
                        ft.Container(height=PADDING_MEDIUM),
                        self.process_button,
                    ],
                    spacing=0,
                    scroll=ft.ScrollMode.ADAPTIVE,
                    expand=True,
                ),
            ],
            spacing=0,
            expand=True,
        )
        self._update_file_list()
        self._page.run_task(self._check_model_status_async)

    def _model_info_label(self) -> str:
        model = self._model()
        return f"{model.quality} | {model.performance} | {model.license}"

    def _output_path(self, src: Path, suffix: str) -> Path:
        """与图像增强一致：默认放在源文件旁边，自定义时才写入指定目录。"""
        filename = f"{src.stem}_depth{suffix}"
        if self.output_mode_radio.value == "custom" and self.custom_output_dir.value:
            directory = Path(self.custom_output_dir.value)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / filename
        else:
            target = src.parent / filename
        add_sequence = self.config_service.get_config_value("output_add_sequence", False)
        return get_unique_path(target, add_sequence=add_sequence)

    def _on_output_mode_change(self, e) -> None:
        custom = self.output_mode_radio.value == "custom"
        self.custom_output_dir.disabled = not custom
        self.browse_output_button.disabled = not custom
        self.update()

    def _on_browse_output(self, e) -> None:
        self._page.run_task(self._browse_output_task)

    async def _browse_output_task(self) -> None:
        result = await get_directory_path(self._page, dialog_title="选择输出目录")
        if result:
            self.custom_output_dir.value = result
            self.update()

    def _on_color_change(self, e) -> None:
        self.config_service.set_config_value("depth_colorize", bool(self.color_switch.value))

    def _update_model_status(self, state: str, message: str) -> None:
        icons = {
            "need_download": (ft.Icons.CLOUD_DOWNLOAD, ft.Colors.ORANGE),
            "unloaded": (ft.Icons.DOWNLOAD_DONE, ft.Colors.PRIMARY),
            "loading": (ft.Icons.HOURGLASS_EMPTY, ft.Colors.ON_SURFACE_VARIANT),
            "loaded": (ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN),
            "error": (ft.Icons.ERROR_OUTLINE, ft.Colors.ERROR),
        }
        icon, color = icons.get(state, icons["loading"])
        self.model_status_icon.icon = icon
        self.model_status_icon.color = color
        self.model_status_text.value = message
        self.download_model_button.visible = state == "need_download"
        self.load_model_button.visible = state == "unloaded"
        loaded = state == "loaded"
        self.unload_model_button.visible = loaded
        self.delete_model_button.visible = state in {"unloaded", "loaded"}
        self._update_process_button()
        try:
            self.update()
        except Exception:
            pass

    def _update_process_button(self) -> None:
        ready = bool(self.selected_files) and self.estimator is not None and not self.is_model_loading
        self.process_button.content.disabled = not ready

    async def _check_model_status_async(self) -> None:
        import asyncio
        await asyncio.sleep(0.3)
        if self._model_path().exists():
            self._update_model_status("unloaded", "模型已下载，点击加载")
        else:
            self._update_model_status("need_download", f"需要下载 {self._model().filename}")

    def _on_model_change(self, e) -> None:
        key = e.control.value
        if key not in DEPTH_MODELS:
            return
        self.current_model_key = key
        self.config_service.set_config_value("depth_model_key", key)
        self.model_info_text.value = self._model_info_label()
        if self.estimator:
            self.estimator.unload_model()
            self.estimator = None
        self._page.run_task(self._check_model_status_async)

    def _on_back(self, e) -> None:
        if self.on_back:
            self.on_back(e)

    def add_files(self, files: List[Path]) -> None:
        for path in files:
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.suffix.lower() in self.SUPPORTED_EXTENSIONS and child not in self.selected_files:
                        self.selected_files.append(child)
            elif path.suffix.lower() in self.SUPPORTED_EXTENSIONS and path not in self.selected_files:
                self.selected_files.append(path)
        self._update_file_list()

    def _update_file_list(self) -> None:
        self.file_list_view.controls.clear()
        if not self.selected_files:
            self.file_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.PERM_MEDIA_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("未选择文件", color=ft.Colors.ON_SURFACE_VARIANT, size=14),
                            ft.Text("点击选择按钮或点击此处选择图片、动态图或视频", color=ft.Colors.ON_SURFACE_VARIANT, size=12),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=PADDING_MEDIUM // 2,
                    ),
                    height=280,
                    alignment=ft.Alignment.CENTER,
                    on_click=self._on_select_files,
                )
            )
        else:
            for index, file_path in enumerate(self.selected_files):
                try:
                    size_text = format_file_size(file_path.stat().st_size)
                except Exception:
                    size_text = "未知大小"
                if is_video_path(file_path):
                    kind = "视频"
                    icon = ft.Icons.MOVIE
                elif file_path.suffix.lower() in {".gif", ".webp", ".png", ".apng"}:
                    kind = "图片/动态图"
                    icon = ft.Icons.GIF_BOX
                else:
                    kind = "图片"
                    icon = ft.Icons.IMAGE
                self.file_list_view.controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(icon, size=20, color=ft.Colors.PRIMARY),
                                ft.Column(
                                    controls=[
                                        ft.Text(file_path.name, size=13, weight=ft.FontWeight.W_500, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(f"{kind} · {size_text}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=16,
                                    tooltip="移除",
                                    on_click=lambda e, i=index: self._remove_file(i),
                                ),
                            ],
                            spacing=PADDING_SMALL,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=BORDER_RADIUS_MEDIUM,
                    )
                )
        self._update_process_button()
        try:
            self.update()
        except Exception:
            pass

    def _remove_file(self, index: int) -> None:
        if 0 <= index < len(self.selected_files):
            self.selected_files.pop(index)
            self._update_file_list()

    def _on_select_files(self, e=None) -> None:
        self._page.run_task(self._select_files_task)

    async def _select_files_task(self) -> None:
        result = await pick_files(
            self._page,
            allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "apng", "mp4", "mov", "mkv", "avi", "webm", "m4v"],
            allow_multiple=True,
            dialog_title="选择图片、动态图或视频",
        )
        if result:
            self.add_files([Path(file.path) for file in result if getattr(file, "path", None)])

    def _on_select_folder(self, e) -> None:
        self._page.run_task(self._select_folder_task)

    async def _select_folder_task(self) -> None:
        result = await get_directory_path(self._page, dialog_title="选择包含图片或视频的文件夹")
        if result:
            self.add_files([Path(result)])

    def _on_clear(self, e) -> None:
        self.selected_files.clear()
        self._update_file_list()

    def _on_download(self, e=None) -> None:
        self._page.run_task(self._download_task)

    async def _download_task(self) -> None:
        import asyncio
        import httpx

        if self.is_model_loading:
            return
        model = self._model()
        dest = self._model_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.is_model_loading = True
        self.progress_bar.visible = True
        self.progress_bar.value = None
        self.progress_text.visible = True
        self.progress_text.value = f"正在下载 {model.filename}..."
        self._update_model_status("loading", "正在下载模型...")

        def _download() -> None:
            last_error = None
            for url in (model.url, model.fallback_url):
                tmp = dest.with_suffix(dest.suffix + ".part")
                try:
                    with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get("content-length", 0))
                        downloaded = 0
                        with open(tmp, "wb") as handle:
                            for chunk in response.iter_bytes(chunk_size=1024 * 256):
                                if chunk:
                                    handle.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size:
                                        self._job_progress = (downloaded, total_size, f"下载 {downloaded / 1048576:.1f}/{total_size / 1048576:.1f} MB")
                    if tmp.stat().st_size < 1024 * 1024:
                        raise ValueError("下载内容过小")
                    if dest.exists():
                        dest.unlink()
                    tmp.replace(dest)
                    return
                except Exception as exc:
                    last_error = exc
                    logger.warning("深度模型下载失败 %s: %s", url, exc)
                    if tmp.exists():
                        tmp.unlink(missing_ok=True)
            raise RuntimeError(f"模型下载失败: {last_error}")

        finished = False

        async def _poll() -> None:
            while not finished:
                done, total, label = self._job_progress
                if total:
                    self.progress_bar.value = done / total
                self.progress_text.value = label
                try:
                    self.update()
                except Exception:
                    pass
                await asyncio.sleep(0.3)

        poll_task = asyncio.create_task(_poll())
        try:
            await asyncio.to_thread(_download)
            self._update_model_status("unloaded", "模型已下载，点击加载")
            self.progress_text.value = "下载完成"
        except Exception as exc:
            self._update_model_status("error", str(exc))
        finally:
            finished = True
            self.is_model_loading = False
            await poll_task
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self.update()

    def _on_load_model(self, e=None) -> None:
        self._page.run_task(self._load_model_task)

    async def _load_model_task(self) -> None:
        import asyncio

        if not self._model_path().exists():
            self._update_model_status("need_download", "请先下载模型")
            return
        self._update_model_status("loading", "正在加载模型...")

        def _load() -> None:
            if self.estimator:
                self.estimator.unload_model()
            use_gpu = self.config_service.get_config_value("gpu_acceleration", True)
            device_id = int(self.config_service.get_config_value("gpu_device_id", 0) or 0)
            self.estimator = DepthEstimator(self._model_path(), use_gpu=use_gpu, gpu_device_id=device_id)

        try:
            await asyncio.to_thread(_load)
            device = getattr(self.estimator, "device_info", "ONNX Runtime")
            self._update_model_status("loaded", f"模型已加载 · {device}")
        except Exception as exc:
            self.estimator = None
            self._update_model_status("error", f"加载失败: {exc}")

    def _on_unload_model(self, e) -> None:
        if self.estimator:
            self.estimator.unload_model()
            self.estimator = None
        self._update_model_status("unloaded", "模型已卸载")

    def _on_delete_model(self, e) -> None:
        if self.estimator:
            self.estimator.unload_model()
            self.estimator = None
        path = self._model_path()
        if path.exists():
            path.unlink()
        self._update_model_status("need_download", f"已删除，需要重新下载 {self._model().filename}")

    def _on_process(self, e) -> None:
        self._page.run_task(self._process_task)

    async def _process_task(self) -> None:
        import asyncio

        if not self.selected_files:
            return
        if self.estimator is None:
            await self._load_model_task()
            if self.estimator is None:
                return

        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.visible = True
        self._job_progress = (0, 1, "准备中...")
        self.process_button.content.disabled = True
        self.update()
        grayscale = not bool(self.color_switch.value)
        finished = False

        def _report(done: int, total: int, label: str) -> None:
            self._job_progress = (done, total, label)

        def _run() -> int:
            count = len(self.selected_files)
            for index, src in enumerate(self.selected_files, start=1):
                if is_video_path(src):
                    out = self._output_path(src, ".mp4")

                    def _on_frames(frame_index: int, frame_total: int, src=src, index=index) -> None:
                        total = frame_total or frame_index
                        _report(frame_index, total, f"视频 {index}/{count}：{src.name} {frame_index}/{total} 帧")

                    self.estimator.estimate_video(
                        src, out, grayscale=grayscale, config_service=self.config_service, progress=_on_frames,
                    )
                elif is_animated_image(src):
                    out = self._output_path(src, src.suffix.lower())

                    def _on_anim(frame_index: int, frame_total: int, src=src, index=index) -> None:
                        total = frame_total or frame_index
                        _report(frame_index, total, f"动态图 {index}/{count}：{src.name} {frame_index}/{total} 帧")

                    self.estimator.estimate_animation(src, out, grayscale=grayscale, progress=_on_anim)
                else:
                    out = self._output_path(src, ".png")
                    _report(index, count, f"图片 {index}/{count}：{src.name}")
                    self.estimator.estimate_file(src, out, grayscale=grayscale)
            return count

        async def _poll() -> None:
            while not finished:
                done, total, label = self._job_progress
                self.progress_bar.value = done / total if total else None
                self.progress_text.value = label
                try:
                    self.update()
                except Exception:
                    pass
                await asyncio.sleep(0.3)

        poll_task = asyncio.create_task(_poll())
        try:
            count = await asyncio.to_thread(_run)
            if self.output_mode_radio.value == "custom":
                where = self.custom_output_dir.value
            else:
                where = "原文件所在目录"
            self.progress_text.value = f"完成 {count} 个文件，已保存到{where}"
            self.progress_bar.value = 1
        except Exception as exc:
            logger.exception("深度估计失败")
            self.progress_text.value = f"处理失败: {exc}"
        finally:
            finished = True
            await poll_task
            self._update_process_button()
            self.update()

    def cleanup(self) -> None:
        if self.estimator:
            self.estimator.unload_model()
            self.estimator = None
