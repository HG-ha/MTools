# -*- coding: utf-8 -*-
"""二维码生成视图模块。

提供二维码生成功能，支持普通二维码、带背景图二维码和动态 GIF 二维码。
"""

import base64
import io
import tempfile
import threading
from pathlib import Path
from typing import Callable, Optional

import flet as ft
import qrcode
from PIL import Image, ImageDraw, ImageEnhance, ImageSequence

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
    PADDING_XLARGE,
)
from services import ConfigService, ImageService


class QRCodeGeneratorView(ft.Container):
    """二维码生成视图类。
    
    提供二维码生成功能，包括：
    - 文本/网址转二维码
    - 艺术二维码（带背景图片）
    - 彩色二维码
    - 动态 GIF 二维码
    - 自定义对比度和亮度
    - 实时预览
    - 保存为图片
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: ConfigService,
        image_service: ImageService,
        on_back: Optional[Callable] = None
    ) -> None:
        """初始化二维码生成视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            image_service: 图片服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: ConfigService = config_service
        self.image_service: ImageService = image_service
        self.on_back: Optional[Callable] = on_back
        self.expand: bool = True
        
        self.qr_image_path: Optional[Path] = None
        self.background_image_path: Optional[Path] = None
        
        # 创建UI组件
        self._build_ui()
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 标题栏
        header: ft.Row = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("二维码生成器", size=28, weight=ft.FontWeight.BOLD, ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 内容输入区域
        self.content_input = ft.TextField(
            label="输入内容",
            hint_text="输入文本、网址等内容",
            multiline=True,
            min_lines=3,
            max_lines=8,
            value="",
        )
        
        # 常用模板按钮
        template_buttons = ft.Row(
            controls=[
                ft.TextButton(
                    content="网址",
                    on_click=lambda e: self._set_template("https://example.com"),
                    tooltip="网址模板",
                ),
                ft.TextButton(
                    content="WiFi",
                    on_click=lambda e: self._set_template("WIFI:T:WPA;S:我的WiFi;P:密码123456;;"),
                    tooltip="WiFi配置模板",
                ),
                ft.TextButton(
                    content="电话",
                    on_click=lambda e: self._set_template("tel:13800138000"),
                    tooltip="电话号码模板",
                ),
                ft.TextButton(
                    content="邮箱",
                    on_click=lambda e: self._set_template("mailto:user@example.com"),
                    tooltip="邮箱地址模板",
                ),
                ft.TextButton(
                    content="短信",
                    on_click=lambda e: self._set_template("SMSTO:13800138000:Message here"),
                    tooltip="短信模板",
                ),
            ],
            spacing=PADDING_SMALL,
            wrap=True,
        )
        
        input_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("二维码内容", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    self.content_input,
                    # 功能说明
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "支持生成普通二维码、带背景图的艺术二维码和动态GIF二维码 | 支持中文、表情符号等所有字符",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=8,
                        ),
                        margin=ft.margin.only(left=4, top=8, bottom=8),
                    ),
                    ft.Text("快速模板：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    template_buttons,
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("WiFi 格式说明：", size=11, weight=ft.FontWeight.W_500, ),
                                ft.Text(
                                    "WIFI:T:WPA;S:网络名称;P:密码;;\n"
                                    "• T: 加密类型 (WPA, WEP, nopass)\n"
                                    "• S: 网络名称 (支持中文)\n"
                                    "• P: 密码",
                                    size=10,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.all(8),
                        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE),
                        border_radius=8,
                        margin=ft.margin.only(top=8),
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 基础设置
        self.version_slider = ft.Slider(
            min=1,
            max=40,
            divisions=39,
            value=1,
            label="{value}",
        )
        
        self.error_correction_dropdown = ft.Dropdown(
            label="纠错等级",
            width=150,
            options=[
                ft.dropdown.Option("L", "低 (7%)"),
                ft.dropdown.Option("M", "中 (15%)"),
                ft.dropdown.Option("Q", "高 (25%)"),
                ft.dropdown.Option("H", "最高 (30%)"),
            ],
            value="H",
        )
        
        basic_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("基础设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text("版本大小 (1-40)", size=12),
                                    self.version_slider,
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            self.error_correction_dropdown,
                        ],
                        spacing=PADDING_MEDIUM,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 艺术二维码设置
        self.selected_image_text = ft.Text(
            "未选择图片",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        select_image_button = ft.Button(
            content="选择背景图片",
            icon=ft.Icons.IMAGE_OUTLINED,
            on_click=self._on_select_image,
        )
        
        clear_image_button = ft.TextButton(
            content="清除",
            on_click=self._on_clear_image,
        )
        
        self.colorized_checkbox = ft.Checkbox(
            label="彩色二维码",
            value=False,
        )
        
        self.contrast_slider = ft.Slider(
            min=0.5,
            max=2.0,
            divisions=30,
            value=1.0,
            label="{value}",
        )
        
        self.brightness_slider = ft.Slider(
            min=0.5,
            max=2.0,
            divisions=30,
            value=1.0,
            label="{value}",
        )
        
        artistic_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("艺术二维码设置", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Text("背景图片（可选，支持 GIF 动态图）", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Row(
                        controls=[
                            select_image_button,
                            clear_image_button,
                        ],
                        spacing=PADDING_SMALL,
                    ),
                    self.selected_image_text,
                    ft.Container(height=PADDING_SMALL),
                    self.colorized_checkbox,
                    ft.Container(height=PADDING_SMALL),
                    ft.Column(
                        controls=[
                            ft.Text("对比度", size=12),
                            self.contrast_slider,
                        ],
                        spacing=0,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("亮度", size=12),
                            self.brightness_slider,
                        ],
                        spacing=0,
                    ),
                ],
                spacing=PADDING_SMALL,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )
        
        # 生成按钮和进度
        self.generate_button = ft.Container(
            content=ft.Button(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.QR_CODE_2, size=24),
                        ft.Text("生成二维码", size=18, weight=ft.FontWeight.W_600),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=PADDING_MEDIUM,
                ),
                on_click=self._on_generate,
                style=ft.ButtonStyle(
                    padding=ft.padding.symmetric(horizontal=PADDING_LARGE * 2, vertical=PADDING_LARGE),
                    shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS_MEDIUM),
                ),
            ),
            alignment=ft.Alignment.CENTER,
        )
        
        self.progress_bar = ft.ProgressBar(visible=False, value=0)
        self.progress_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, visible=False)
        
        # 预览区域
        self.preview_image = ft.Image(
            "",
            visible=False,
            fit=ft.BoxFit.CONTAIN,
            width=400,
            height=400,
        )
        
        save_button = ft.Button(
            content="保存图片",
            icon=ft.Icons.SAVE,
            on_click=self._on_save,
            visible=False,
        )
        
        self.save_button = save_button
        
        preview_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("预览", size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(height=PADDING_SMALL),
                    ft.Container(
                        content=self.preview_image,
                        alignment=ft.Alignment.CENTER,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=PADDING_LARGE,
                    ),
                    ft.Container(height=PADDING_SMALL),
                    save_button,
                ],
                spacing=PADDING_SMALL,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=PADDING_LARGE,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
            visible=False,
        )
        
        self.preview_section = preview_section
        
        # 可滚动内容区域
        scrollable_content = ft.Column(
            controls=[
                input_section,
                ft.Container(height=PADDING_MEDIUM),
                basic_section,
                ft.Container(height=PADDING_MEDIUM),
                artistic_section,
                ft.Container(height=PADDING_SMALL),
                self.progress_bar,
                self.progress_text,
                ft.Container(height=PADDING_SMALL),
                self.generate_button,
                ft.Container(height=PADDING_MEDIUM),
                preview_section,
                ft.Container(height=PADDING_LARGE),  # 底部间距
            ],
            scroll=ft.ScrollMode.HIDDEN,
            expand=True,
        )
        
        # 组装视图 - 标题固定，分隔线固定，内容可滚动
        self.content = ft.Column(
            controls=[
                header,  # 固定在顶部
                ft.Divider(),  # 固定的分隔线
                scrollable_content,  # 可滚动内容
            ],
            spacing=0,
        )
        
        self.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM,
        )
    
    def _on_back_click(self, e: ft.ControlEvent) -> None:
        """返回按钮点击事件。"""
        if self.on_back:
            self.on_back()
    
    def _set_template(self, template: str) -> None:
        """设置快速模板。"""
        self.content_input.value = template
        self.content_input.update()
    
    async def _on_select_image(self, e: ft.ControlEvent) -> None:
        """选择背景图片。"""
        result = await ft.FilePicker().pick_files(
            dialog_title="选择背景图片",
            allowed_extensions=["jpg", "jpeg", "png", "bmp", "gif"],
            allow_multiple=False,
        )
        if result and len(result) > 0:
            file_path = Path(result[0].path)
            self.background_image_path = file_path
            self.selected_image_text.value = f"已选择: {file_path.name}"
            self.selected_image_text.update()
    
    def _on_clear_image(self, e: ft.ControlEvent) -> None:
        """清除背景图片。"""
        self.background_image_path = None
        self.selected_image_text.value = "未选择图片"
        self.selected_image_text.update()
    
    def _generate_base_qr(self, content: str, version: int, level: str) -> Image.Image:
        """生成基础二维码图像。
        
        Args:
            content: 二维码内容
            version: 版本号 (1-40)
            level: 纠错级别 (L/M/Q/H)
            
        Returns:
            PIL Image对象
        """
        # 创建二维码对象
        qr = qrcode.QRCode(
            version=version,
            error_correction={
                'L': qrcode.constants.ERROR_CORRECT_L,
                'M': qrcode.constants.ERROR_CORRECT_M,
                'Q': qrcode.constants.ERROR_CORRECT_Q,
                'H': qrcode.constants.ERROR_CORRECT_H,
            }[level],
            box_size=10,
            border=4,
        )
        
        # 添加数据
        qr.add_data(content)
        qr.make(fit=True)
        
        # 生成图像
        img = qr.make_image(fill_color="black", back_color="white")
        
        return img.convert('RGB')
    
    def _apply_background(self, qr_img: Image.Image, bg_path: Path, colorized: bool) -> Image.Image:
        """将二维码叠加到背景图片上。
        
        Args:
            qr_img: 二维码图像
            bg_path: 背景图片路径
            colorized: 是否彩色化
            
        Returns:
            合成后的图像
        """
        # 打开背景图
        bg_img = Image.open(bg_path).convert('RGBA')
        
        # 调整二维码大小以匹配背景
        qr_size = min(bg_img.size)
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        
        # 转换为RGBA
        qr_img = qr_img.convert('RGBA')
        
        if colorized:
            # 彩色模式：保留背景颜色，二维码黑色部分变透明
            qr_data = qr_img.getdata()
            new_data = []
            
            for item in qr_data:
                # 如果是黑色（二维码部分），设置为半透明黑色
                # 如果是白色（背景部分），设置为完全透明
                if item[:3] == (0, 0, 0):  # 黑色
                    new_data.append((0, 0, 0, 180))
                else:  # 白色
                    new_data.append((255, 255, 255, 0))
            
            qr_img.putdata(new_data)
            
            # 将二维码叠加到背景上
            result = bg_img.copy()
            
            # 居中叠加
            x = (bg_img.width - qr_size) // 2
            y = (bg_img.height - qr_size) // 2
            result.paste(qr_img, (x, y), qr_img)
        else:
            # 黑白模式：使用背景亮度信息
            bg_gray = bg_img.convert('L')
            bg_gray = bg_gray.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
            
            # 创建新图像
            result = Image.new('RGB', (qr_size, qr_size), 'white')
            
            qr_binary = qr_img.convert('L')
            
            for y in range(qr_size):
                for x in range(qr_size):
                    qr_pixel = qr_binary.getpixel((x, y))
                    bg_pixel = bg_gray.getpixel((x, y))
                    
                    # 如果是二维码的黑色部分，使用背景的暗色
                    # 如果是二维码的白色部分，使用背景的亮色
                    if qr_pixel < 128:  # 黑色
                        color_value = int(bg_pixel * 0.3)  # 变暗
                    else:  # 白色
                        color_value = 255 - int((255 - bg_pixel) * 0.3)  # 变亮
                    
                    result.putpixel((x, y), (color_value, color_value, color_value))
        
        return result.convert('RGB')
    
    def _apply_adjustments(self, img: Image.Image, contrast: float, brightness: float) -> Image.Image:
        """应用对比度和亮度调整。
        
        Args:
            img: 输入图像
            contrast: 对比度 (0.0-2.0)
            brightness: 亮度 (0.0-2.0)
            
        Returns:
            调整后的图像
        """
        # 调整对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast)
        
        # 调整亮度
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness)
        
        return img
    
    def _generate_gif_qr(self, content: str, version: int, level: str, 
                        gif_path: Path, colorized: bool, 
                        contrast: float, brightness: float) -> Path:
        """生成动态 GIF 二维码。
        
        Args:
            content: 二维码内容
            version: 版本号
            level: 纠错级别
            gif_path: GIF背景路径
            colorized: 是否彩色化
            contrast: 对比度
            brightness: 亮度
            
        Returns:
            输出文件路径
        """
        # 生成基础二维码
        qr_img = self._generate_base_qr(content, version, level)
        
        # 打开GIF
        gif = Image.open(gif_path)
        
        frames = []
        durations = []
        
        try:
            for frame_idx in range(gif.n_frames):
                gif.seek(frame_idx)
                frame = gif.convert('RGB')
                
                # 保存当前帧到临时文件
                temp_frame = Path(tempfile.mkdtemp()) / f"frame_{frame_idx}.png"
                frame.save(temp_frame)
                
                # 叠加二维码
                result = self._apply_background(qr_img, temp_frame, colorized)
                
                # 应用调整
                result = self._apply_adjustments(result, contrast, brightness)
                
                frames.append(result)
                
                # 获取帧延迟
                duration = gif.info.get('duration', 100)
                durations.append(duration)
                
        except EOFError:
            pass
        
        # 保存为GIF
        output_path = Path(tempfile.mkdtemp()) / "qrcode.gif"
        
        if frames:
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=gif.info.get('loop', 0),
                optimize=False,
            )
        
        return output_path
    
    def _on_generate(self, e: ft.ControlEvent) -> None:
        """生成按钮点击事件。"""
        content = self.content_input.value.strip()
        
        if not content:
            self._show_message("请输入内容", ft.Colors.ERROR)
            return
        
        # 显示进度
        self.progress_bar.visible = True
        self.progress_text.visible = True
        self.progress_text.value = "正在生成二维码..."
        self.progress_bar.value = None  # 不确定进度
        self._page.update()
        
        # 后台生成
        def generate_task():
            try:
                # 准备参数
                version = int(self.version_slider.value)
                level = self.error_correction_dropdown.value
                colorized = self.colorized_checkbox.value
                contrast = self.contrast_slider.value
                brightness = self.brightness_slider.value
                
                # 生成基础二维码
                qr_img = self._generate_base_qr(content, version, level)
                
                # 如果有背景图片
                if self.background_image_path:
                    bg_path = self.background_image_path
                    
                    # 如果是GIF
                    if bg_path.suffix.lower() == '.gif':
                        self.qr_image_path = self._generate_gif_qr(
                            content, version, level, bg_path,
                            colorized, contrast, brightness
                        )
                    else:
                        # 静态图片
                        result = self._apply_background(qr_img, bg_path, colorized)
                        result = self._apply_adjustments(result, contrast, brightness)
                        
                        # 保存
                        temp_dir = Path(tempfile.mkdtemp())
                        self.qr_image_path = temp_dir / "qrcode.png"
                        result.save(self.qr_image_path, quality=95)
                else:
                    # 纯二维码
                    result = self._apply_adjustments(qr_img, contrast, brightness)
                    
                    # 保存
                    temp_dir = Path(tempfile.mkdtemp())
                    self.qr_image_path = temp_dir / "qrcode.png"
                    result.save(self.qr_image_path, quality=95)
                
                # 更新UI
                self._page.run_task(self._update_preview)
                
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self._page.run_task(self._show_error, str(ex))
        
        thread = threading.Thread(target=generate_task, daemon=True)
        thread.start()
    
    async def _update_preview(self) -> None:
        """更新预览（在主线程中调用）。"""
        try:
            if not self.qr_image_path or not self.qr_image_path.exists():
                self._show_message("生成失败：找不到输出文件", ft.Colors.ERROR)
                return
            
            # 读取生成的二维码
            with open(self.qr_image_path, "rb") as f:
                img_data = f.read()
            
            # 转换为base64显示
            img_base64 = base64.b64encode(img_data).decode()
            
            # 显示预览
            self.preview_image.src = img_base64
            self.preview_image.visible = True
            self.preview_image.update()
            
            # 显示保存按钮和预览区域
            self.preview_section.visible = True
            self.save_button.visible = True
            self.preview_section.update()
            
            # 隐藏进度
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self._page.update()
            
            self._show_message("二维码生成成功！", ft.Colors.GREEN)
        
        except Exception as ex:
            self._show_message(f"预览失败: {str(ex)}", ft.Colors.ERROR)
            # 隐藏进度
            self.progress_bar.visible = False
            self.progress_text.visible = False
            self._page.update()
    
    async def _show_error(self, error_msg: str) -> None:
        """显示错误（在主线程中调用）。"""
        self._show_message(f"生成失败: {error_msg}", ft.Colors.ERROR)
        # 隐藏进度
        self.progress_bar.visible = False
        self.progress_text.visible = False
        self._page.update()
    
    async def _on_save(self, e: ft.ControlEvent) -> None:
        """保存按钮点击事件。"""
        if not self.qr_image_path or not self.qr_image_path.exists():
            self._show_message("请先生成二维码", ft.Colors.ERROR)
            return
        
        # 根据原文件类型确定保存格式
        if self.qr_image_path.suffix.lower() == '.gif':
            save_path = await ft.FilePicker().save_file(
                dialog_title="保存二维码",
                file_name="qrcode.gif",
                allowed_extensions=["gif"],
            )
        else:
            save_path = await ft.FilePicker().save_file(
                dialog_title="保存二维码",
                file_name="qrcode.png",
                allowed_extensions=["png", "jpg", "jpeg"],
            )
        
        if save_path:
            try:
                save_path = Path(save_path)
                
                # 复制文件
                with open(self.qr_image_path, "rb") as src:
                    with open(save_path, "wb") as dst:
                        dst.write(src.read())
                
                self._show_message(f"二维码已保存到: {save_path}", ft.Colors.GREEN)
            except Exception as ex:
                self._show_message(f"保存失败: {str(ex)}", ft.Colors.ERROR)
    
    def _show_message(self, message: str, color: str) -> None:
        """显示消息提示。
        
        Args:
            message: 消息内容
            color: 消息颜色
        """
        snackbar: ft.SnackBar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
            duration=2000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()