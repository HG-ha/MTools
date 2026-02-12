# -*- coding: utf-8 -*-
"""加解密工具视图模块。

提供对称加密（AES, DES, RC4）和哈希计算（MD5, SHA）功能。
"""

import base64
import hashlib
from typing import Callable, Optional

import flet as ft
from Crypto.Cipher import AES, DES, DES3, ARC4
from Crypto.Util.Padding import pad, unpad

from constants import PADDING_MEDIUM, PADDING_SMALL


class CryptoToolView(ft.Container):
    """加解密工具视图类。"""
    
    ALGORITHMS = {
        "Hash (哈希)": ["MD5", "SHA1", "SHA256", "SHA512"],
        "Symmetric (对称加密)": ["AES", "DES", "3DES", "RC4"]
    }
    
    MODES = ["ECB", "CBC"]
    
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
        self.category = ft.Ref[ft.Dropdown]()
        self.algorithm = ft.Ref[ft.Dropdown]()
        self.mode = ft.Ref[ft.Dropdown]()
        self.key_input = ft.Ref[ft.TextField]()
        self.iv_input = ft.Ref[ft.TextField]()
        self.input_text = ft.Ref[ft.TextField]()
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
                ft.Text("加解密工具", size=28, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE,
                    tooltip="使用说明",
                    on_click=self._show_help,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 操作栏 - 整合所有控制项
        operation_bar = ft.Row(
            controls=[
                ft.Dropdown(
                    ref=self.category,
                    label="算法类别",
                    width=150,
                    options=[ft.dropdown.Option(c) for c in self.ALGORITHMS.keys()],
                    value="Hash (哈希)",
                    on_select=self._on_category_change,
                ),
                ft.Dropdown(
                    ref=self.algorithm,
                    label="算法",
                    width=120,
                    options=[ft.dropdown.Option(a) for a in self.ALGORITHMS["Hash (哈希)"]],
                    value="MD5",
                    on_select=self._on_algo_change,
                ),
                ft.Dropdown(
                    ref=self.mode,
                    label="模式",
                    width=100,
                    options=[ft.dropdown.Option(m) for m in self.MODES],
                    value="ECB",
                    on_select=self._on_mode_change,
                    visible=False,
                ),
                ft.TextField(
                    ref=self.key_input,
                    label="密钥",
                    width=200,
                    password=True,
                    can_reveal_password=True,
                    visible=False,
                    dense=True,
                ),
                ft.TextField(
                    ref=self.iv_input,
                    label="IV偏移量",
                    width=150,
                    visible=False,
                    dense=True,
                ),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    content="加密/计算",
                    icon=ft.Icons.LOCK,
                    on_click=lambda _: self._process(True),
                ),
                ft.ElevatedButton(
                    content="解密",
                    icon=ft.Icons.LOCK_OPEN,
                    on_click=lambda _: self._process(False),
                ),
                ft.OutlinedButton(
                    content="清空",
                    icon=ft.Icons.CLEAR,
                    on_click=self._clear,
                ),
            ],
            spacing=PADDING_SMALL,
        )
        
        # 输入区域
        input_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("输入", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.input_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.input_text,
                        multiline=True,
                        min_lines=20,
                        hint_text="输入要加密/解密的文本...",
                        text_size=13,
                        border=ft.InputBorder.NONE,
                    ),
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=PADDING_SMALL,
                    expand=True,
                ),
            ],
            spacing=5,
            expand=True,
        )
        
        # 输出区域
        output_section = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("输出", weight=ft.FontWeight.BOLD, size=16),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="复制",
                            on_click=lambda _: self._copy_text(self.output_text.current.value),
                        ),
                    ],
                ),
                ft.Container(
                    content=ft.TextField(
                        ref=self.output_text,
                        multiline=True,
                        min_lines=20,
                        read_only=True,
                        text_size=13,
                        border=ft.InputBorder.NONE,
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
        
        # 左右分栏
        content_area = ft.Row(
            controls=[
                ft.Container(content=input_section, expand=1),
                ft.Container(content=output_section, expand=1),
            ],
            spacing=PADDING_MEDIUM,
            expand=True,
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Container(height=PADDING_SMALL),
                operation_bar,
                ft.Container(height=PADDING_SMALL),
                content_area,
            ],
            spacing=0,
            expand=True,
        )

    def _on_category_change(self, e):
        """类别改变时更新算法列表和UI状态。"""
        cat = self.category.current.value
        self.algorithm.current.options = [ft.dropdown.Option(a) for a in self.ALGORITHMS[cat]]
        self.algorithm.current.value = self.ALGORITHMS[cat][0]
        
        # 只有对称加密需要显示参数
        is_symmetric = "Symmetric" in cat
        self.mode.current.visible = is_symmetric
        self.key_input.current.visible = is_symmetric
        
        # 初始化时隐藏IV
        if is_symmetric:
            self._on_mode_change(None)
        else:
            self.iv_input.current.visible = False
        
        self.update()

    def _on_algo_change(self, e):
        self._on_mode_change(None)
        
    def _on_mode_change(self, e):
        """模式改变时更新IV输入框的可见性。"""
        if not self.mode.current.visible:
            return
            
        mode = self.mode.current.value
        algo = self.algorithm.current.value
        # ECB模式不需要IV，RC4也不需要
        needs_iv = mode != "ECB" and algo != "RC4"
        
        self.iv_input.current.visible = needs_iv
        self.update()

    def _process(self, is_encrypt: bool):
        """执行处理。"""
        cat = self.category.current.value
        algo = self.algorithm.current.value
        text = self.input_text.current.value
        
        if not text:
            self._show_snack("请输入内容", error=True)
            return

        try:
            result = ""
            if "Hash" in cat:
                if not is_encrypt:
                    self._show_snack("哈希算法不支持解密", error=True)
                    return
                
                data = text.encode('utf-8')
                if algo == "MD5":
                    result = hashlib.md5(data).hexdigest()
                elif algo == "SHA1":
                    result = hashlib.sha1(data).hexdigest()
                elif algo == "SHA256":
                    result = hashlib.sha256(data).hexdigest()
                elif algo == "SHA512":
                    result = hashlib.sha512(data).hexdigest()
            
            else:  # Symmetric
                key = self.key_input.current.value
                iv = self.iv_input.current.value
                mode_str = self.mode.current.value
                
                if not key:
                    self._show_snack("请输入密钥", error=True)
                    return
                
                # 密钥处理
                key_bytes = key.encode('utf-8')
                
                def fit_key(k, length):
                    return k.ljust(length, b'\0')[:length]
                
                cipher = None
                
                if algo == "AES":
                    k = fit_key(key_bytes, 16)
                    if len(key_bytes) >= 32: k = fit_key(key_bytes, 32)
                    elif len(key_bytes) >= 24: k = fit_key(key_bytes, 24)
                    
                    if mode_str == "ECB":
                        cipher = AES.new(k, AES.MODE_ECB)
                    elif mode_str == "CBC":
                        if not iv: raise ValueError("CBC模式需要IV")
                        i = fit_key(iv.encode('utf-8'), 16)
                        cipher = AES.new(k, AES.MODE_CBC, i)
                        
                elif algo == "DES":
                    k = fit_key(key_bytes, 8)
                    if mode_str == "ECB":
                        cipher = DES.new(k, DES.MODE_ECB)
                    elif mode_str == "CBC":
                        if not iv: raise ValueError("CBC模式需要IV")
                        i = fit_key(iv.encode('utf-8'), 8)
                        cipher = DES.new(k, DES.MODE_CBC, i)
                
                elif algo == "3DES":
                    k = fit_key(key_bytes, 24)
                    if mode_str == "ECB":
                        cipher = DES3.new(k, DES3.MODE_ECB)
                    elif mode_str == "CBC":
                        if not iv: raise ValueError("CBC模式需要IV")
                        i = fit_key(iv.encode('utf-8'), 8)
                        cipher = DES3.new(k, DES3.MODE_CBC, i)
                        
                elif algo == "RC4":
                    cipher = ARC4.new(key_bytes)
                
                if not cipher:
                    raise ValueError(f"暂不支持 {algo} 的 {mode_str} 模式")

                # 加密/解密
                if is_encrypt:
                    data = text.encode('utf-8')
                    if algo != "RC4":
                        data = pad(data, cipher.block_size)
                    encrypted = cipher.encrypt(data)
                    result = base64.b64encode(encrypted).decode('ascii')
                else:
                    try:
                        data = base64.b64decode(text)
                        decrypted = cipher.decrypt(data)
                        if algo != "RC4":
                            decrypted = unpad(decrypted, cipher.block_size)
                        result = decrypted.decode('utf-8')
                    except Exception:
                        raise ValueError("解密失败，请检查密钥/IV或密文格式")

            self.output_text.current.value = result
            self.output_text.current.update()
            self._show_snack("操作成功")

        except Exception as e:
            # 在输出框显示详细错误信息
            error_msg = f"❌ 操作失败\n\n"
            error_msg += f"错误类型: {type(e).__name__}\n"
            error_msg += f"错误信息: {str(e)}\n\n"
            
            if "Hash" in cat:
                error_msg += "提示：\n"
                error_msg += "- 请检查输入内容是否为有效文本\n"
            else:
                error_msg += "提示：\n"
                error_msg += "- 加密时：请确保输入了有效的明文\n"
                error_msg += "- 解密时：请确保输入了正确的Base64密文\n"
                error_msg += "- 请检查密钥是否正确\n"
                if self.iv_input.current.visible:
                    error_msg += "- 请检查IV偏移量是否正确\n"
            
            self.output_text.current.value = error_msg
            self.output_text.current.update()
            self._show_snack(f"错误: {str(e)}", error=True)

    def _clear(self, e):
        self.input_text.current.value = ""
        self.output_text.current.value = ""
        self.update()

    async def _copy_text(self, text: str):
        if not text: return
        await ft.Clipboard().set(text)
        self._show_snack("已复制")
        
    def _on_back_click(self):
        if self.on_back:
            self.on_back()
    
    def _show_help(self, e):
        """显示使用说明。"""
        help_text = """
**加解密工具使用说明**

**1. Hash（哈希）模式**
- 选择哈希算法：MD5、SHA1、SHA256、SHA512
- 输入文本，点击"加密/计算"得到哈希值
- 哈希是单向的，不可逆

**2. Symmetric（对称加密）模式**
- 支持算法：AES、DES、3DES、RC4
- 支持模式：ECB、CBC
- **密钥**：加密和解密必须使用相同的密钥
- **IV偏移量**：CBC模式需要，ECB模式不需要

**使用步骤：**
1. 选择算法类别和具体算法
2. 如果是对称加密，选择模式并输入密钥
3. 在左侧输入框输入内容
4. 点击"加密/计算"或"解密"
5. 在右侧查看结果

**注意事项：**
- 加密结果为Base64格式
- 解密时需要输入Base64格式的密文
- 请妥善保管密钥
- 密钥长度不足时会自动填充
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
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
        )
        self._page.open(snackbar)
    
    def cleanup(self) -> None:
        """清理视图资源，释放内存。"""
        import gc
        # 清除回调引用，打破循环引用
        self.on_back = None
        # 清除 UI 内容
        self.content = None
        gc.collect()