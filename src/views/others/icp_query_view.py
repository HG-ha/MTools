# -*- coding: utf-8 -*-
"""ICP备案查询视图模块。

提供ICP备案查询功能的用户界面。
"""

from typing import Optional, List, Dict, Any, TYPE_CHECKING

import flet as ft
import httpx

from constants import (
    BORDER_RADIUS_MEDIUM,
    PADDING_LARGE,
    PADDING_MEDIUM,
    PADDING_SMALL,
)
from services.icp_service import ICPService
from utils import logger

if TYPE_CHECKING:
    from services.config_service import ConfigService


class ICPQueryView(ft.Container):
    """ICP备案查询视图类。
    
    提供ICP备案查询功能，包括：
    - 域名/企业名/备案号查询
    - 多种查询类型（网站、APP、小程序、快应用）
    - 分页查询支持
    - 批量查询支持
    - API地址配置
    """

    def __init__(
        self,
        page: ft.Page,
        config_service: 'ConfigService',
        on_back: Optional[callable] = None
    ) -> None:
        """初始化ICP备案查询视图。
        
        Args:
            page: Flet页面对象
            config_service: 配置服务实例
            on_back: 返回按钮回调函数
        """
        super().__init__()
        self._page: ft.Page = page
        self.config_service: 'ConfigService' = config_service
        self.on_back: Optional[callable] = on_back
        self.icp_service: ICPService = ICPService(config_service)
        
        self.is_querying: bool = False  # 查询状态标志
        self.models_loaded: bool = False  # 模型加载状态
        self.is_model_loading: bool = False  # 模型加载中标志
        self.last_query_type: Optional[str] = None  # 上一次查询类型
        self.last_search_text: str = ""  # 上一次查询关键词
        self.last_page_size: int = 10  # 上一次分页大小
        self._prev_window_event_handler = page.on_window_event
        
        # 定义列配置（使用 flex 权重实现自适应）
        self.columns_config = [
            {"id": "index", "label": "序号", "flex": 1, "align": ft.MainAxisAlignment.CENTER},
            {"id": "unit", "label": "主办单位名称", "flex": 3, "align": ft.MainAxisAlignment.START},
            {"id": "nature", "label": "单位性质", "flex": 2, "align": ft.MainAxisAlignment.CENTER},
            {"id": "licence", "label": "备案/许可证号", "flex": 3, "align": ft.MainAxisAlignment.START},
            {"id": "service", "label": "网站/APP名称", "flex": 3, "align": ft.MainAxisAlignment.START},
            {"id": "home", "label": "首页网址", "flex": 3, "align": ft.MainAxisAlignment.START},
            {"id": "time", "label": "审核时间", "flex": 2, "align": ft.MainAxisAlignment.CENTER},
        ]
        
        self._last_result_data: Optional[Dict[str, Any]] = None
        
        self.expand: bool = True
        self.padding: ft.padding = ft.padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM
        )
        
        # 分页信息和控件
        self._page_info_text = ft.Text(
            "暂无数据",
            size=12,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.prev_page_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_LEFT,
            tooltip="上一页",
            on_click=self._on_prev_page,
            disabled=True,
        )
        
        self.next_page_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_RIGHT,
            tooltip="下一页", 
            on_click=self._on_next_page,
            disabled=True,
        )

        # 模型状态显示
        self.model_status_icon: ft.Icon = ft.Icon(
            ft.Icons.HOURGLASS_EMPTY,
            size=20,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        self.model_status_text: ft.Text = ft.Text(
            "正在检查模型...",
            size=13,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        
        # 构建界面
        self._build_ui()
    
    def did_mount(self) -> None:
        """组件挂载时调用 - 检查模型状态。"""
        self._page.run_task(self._check_model_status_async)
    
    def _on_auto_load_changed(self, e) -> None:
        """自动加载开关变化事件。"""
        self.config_service.set_config_value("icp_auto_load_model", self.auto_load_checkbox.value)
        logger.info(f"ICP自动加载模型设置已更新: {self.auto_load_checkbox.value}")
    
    def _on_query_type_changed(self, e) -> None:
        """查询类型变化时重置页码。"""
        self._page_num_input.value = "1"
        try:
            self._page_num_input.update()
        except Exception:
            pass

    def _on_delete_model_click(self, e=None) -> None:
        """删除模型按钮点击事件。"""
        def confirm_delete(e):
            dialog.open = False
            self._page.update()
            self._page.run_task(self._delete_model_async)
        
        def cancel_delete(e):
            dialog.open = False
            self._page.update()
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text("确定要删除ICP模型文件吗？删除后需要重新下载。"),
            actions=[
                ft.TextButton("取消", on_click=cancel_delete),
                ft.TextButton("删除", on_click=confirm_delete),
            ],
        )
        
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
    
    async def _delete_model_async(self) -> None:
        """异步删除模型。"""
        import asyncio

        try:
            import shutil

            # 卸载模型（使用标准化的unload_model方法）
            await asyncio.to_thread(self.icp_service.unload_model)
            self.models_loaded = False

            # 删除模型目录
            models_dir = self.icp_service.models_dir
            if models_dir.exists():
                await asyncio.to_thread(shutil.rmtree, models_dir)
                logger.info(f"已删除模型目录: {models_dir}")
                self._update_model_status("need_download", "模型已删除，点击下载")
                self._show_snack("模型删除成功")
            else:
                logger.warning("模型目录不存在")
                self._update_model_status("need_download", "模型不存在")

        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            self._show_snack(f"删除模型失败: {e}", error=True)
    
    def _build_ui(self) -> None:
        """构建用户界面。"""
        # 顶部：标题和返回按钮
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="返回",
                    on_click=self._on_back_click,
                ),
                ft.Text("ICP备案查询", size=28, weight=ft.FontWeight.BOLD),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 下载模型按钮（初始隐藏）
        self.download_model_button: ft.ElevatedButton = ft.ElevatedButton(
            content="下载模型",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._start_download_model,
            visible=False,
        )
        
        # 加载模型按钮（初始隐藏）
        self.load_model_button: ft.ElevatedButton = ft.ElevatedButton(
            content="加载模型",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_load_model_click,
            visible=False,
        )
        
        # 删除模型按钮（初始隐藏）
        self.delete_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.ERROR,
            tooltip="删除模型文件",
            on_click=self._on_delete_model_click,
            visible=False,
        )

        # 卸载模型按钮（初始隐藏）
        self.unload_model_button: ft.IconButton = ft.IconButton(
            icon=ft.Icons.POWER_SETTINGS_NEW,
            icon_color=ft.Colors.ORANGE,
            tooltip="卸载模型",
            on_click=self._on_unload_model_click,
            visible=False,
        )

        # 自动加载模型设置
        self.auto_load_checkbox: ft.Checkbox = ft.Checkbox(
            label="自动加载模型",
            value=self.config_service.get_config_value("icp_auto_load_model", False),
            on_change=self._on_auto_load_changed,
        )
        
        # 模型设置区域
        model_settings_row = ft.Row(
            controls=[
                ft.Text("模型状态:", size=14, weight=ft.FontWeight.W_500),
                self.model_status_icon,
                self.model_status_text,
                self.download_model_button,
                self.load_model_button,
                self.unload_model_button,
                self.delete_model_button,
                ft.Container(expand=True),
                self.auto_load_checkbox,
            ],
            spacing=PADDING_MEDIUM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 查询控件定义
        self.query_type_dropdown = ft.Dropdown(
            label="查询类型",
            value="web",
            options=[
                ft.dropdown.Option("web", "网站"),
                ft.dropdown.Option("app", "APP"),
                ft.dropdown.Option("mapp", "小程序"),
                ft.dropdown.Option("kapp", "快应用"),
            ],
            width=150,
            on_select=self._on_query_type_changed,
        )
        
        self.search_input = ft.TextField(
            label="查询关键词",
            hint_text="输入域名、备案号或企业名称",
            multiline=False,
            on_submit=self._on_query_click,
            expand=True,
        )
        
        self._page_num_input = ft.TextField(
            label="页码",
            hint_text="1",
            value="1",
            width=100,
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        self._page_size_input = ft.TextField(
            label="每页数量",
            hint_text="10",
            value="10",
            width=120,
            dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        # 查询按钮（初始禁用，模型加载后启用）
        self.query_button = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, size=20),
                    ft.Text("查询", size=16),
                ],
                spacing=8,
            ),
            on_click=self._on_query_click,
            disabled=True,  # 初始禁用
            tooltip="请先加载模型",
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )

        # 查询输入区域
        query_input_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        self.query_type_dropdown,
                        self.search_input,
                        self.query_button,
                    ],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Row(
                    controls=[
                        self._page_num_input,
                        self._page_size_input,
                        ft.OutlinedButton(
                            "清空",
                            icon=ft.Icons.CLEAR,
                            on_click=self._on_clear_click,
                        ),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "支持域名、备案号、企业名称查询 | 数据来自工信部ICP备案管理系统，频繁查询会被风控",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )
        
        # 结果显示区
        # 表头
        header_row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(col["label"], weight=ft.FontWeight.W_500, size=13),
                        expand=col["flex"],
                        alignment=ft.Alignment.CENTER if col["align"] == ft.MainAxisAlignment.CENTER else ft.Alignment.CENTER_LEFT,
                        padding=ft.padding.only(left=8) if col["align"] == ft.MainAxisAlignment.START else None,
                    ) for col in self.columns_config
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=ft.padding.symmetric(vertical=10),
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

        # 数据列表
        self.result_list = ft.ListView(
            expand=True,
            spacing=0,
            padding=0,
        )

        # 使用 Container 包裹以支持边框
        self.result_container = ft.Container(
            content=ft.Column(
                controls=[
                    header_row,
                    self.result_list,
                ],
                spacing=0,
                expand=True,
            ),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            expand=True,
        )
        
        # 顶部控件行
        top_controls = ft.Row(
            controls=[
                ft.Text("查询结果:", size=14, weight=ft.FontWeight.W_500),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.COPY,
                    tooltip="复制结果到剪贴板",
                    on_click=self._on_copy_result,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # 底部分页控件行
        pagination_controls = ft.Row(
            controls=[
                self._page_info_text,
                ft.Container(expand=True),
                self.prev_page_btn,
                self.next_page_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # 固定的查询设置区域
        query_settings_container = ft.Container(
            content=query_input_area,
            padding=PADDING_MEDIUM,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 固定的模型设置区域
        model_settings_container = ft.Container(
            content=model_settings_row,
            padding=ft.padding.symmetric(horizontal=PADDING_MEDIUM, vertical=PADDING_SMALL),
            margin=ft.margin.only(top=PADDING_MEDIUM),
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
        )
        
        # 结果区域
        result_area = ft.Column(
            controls=[
                top_controls,
                self.result_container,
                pagination_controls,
            ],
            spacing=PADDING_SMALL,
            expand=True,  # 让结果区域占据剩余空间
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        
        # 组装主界面
        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                # 固定的顶部区域
                query_settings_container,
                model_settings_container,
                # 可滚动的结果区域
                result_area,
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    
    async def _check_model_status_async(self) -> None:
        """异步检查模型状态，避免阻塞界面初始化。"""
        import asyncio
        await asyncio.sleep(0.05)  # 短暂延迟，确保界面已经显示

        # 在线程池中检查模型文件是否存在（避免 IO 阻塞事件循环）
        exists = await asyncio.to_thread(self.icp_service.check_models_exist)

        if exists:
            # 模型存在，显示"加载模型"按钮
            self._update_model_status("unloaded", "模型已下载，点击加载")

            # 如果开启了自动加载，则自动加载模型
            if self.config_service.get_config_value("icp_auto_load_model", False):
                logger.info("自动加载ICP模型...")
                await self._load_models_only()
        else:
            # 模型不存在，显示"下载模型"按钮
            self._update_model_status("need_download", "需要下载模型才能使用")
    
    def _update_model_status(self, status: str, message: str) -> None:
        """更新模型状态显示。
        
        Args:
            status: 状态 ("loading", "downloading", "ready", "unloaded", "need_download")
            message: 状态消息
        """
        if status == "loading":
            self.model_status_icon.name = ft.Icons.HOURGLASS_EMPTY
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
            # loading 状态不改变 models_loaded，等待加载完成
            self.query_button.disabled = True
            self.query_button.tooltip = "模型加载中..."
        elif status == "downloading":
            self.model_status_icon.name = ft.Icons.DOWNLOAD
            self.model_status_icon.color = ft.Colors.BLUE
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
            self.models_loaded = False
            self.query_button.disabled = True
            self.query_button.tooltip = "模型下载中..."
        elif status == "ready":
            self.model_status_icon.name = ft.Icons.CHECK_CIRCLE
            self.model_status_icon.color = ft.Colors.GREEN
            self.download_model_button.visible = False
            self.load_model_button.visible = False
            self.unload_model_button.visible = True
            self.delete_model_button.visible = True
            self.models_loaded = True
            self.query_button.disabled = False
            self.query_button.tooltip = None
        elif status == "unloaded":
            self.model_status_icon.name = ft.Icons.CLOUD_DONE
            self.model_status_icon.color = ft.Colors.ORANGE
            self.download_model_button.visible = False
            self.load_model_button.visible = True
            self.unload_model_button.visible = False
            self.delete_model_button.visible = True
            self.models_loaded = False
            self.query_button.disabled = True
            self.query_button.tooltip = "请先加载模型"
        elif status == "need_download":
            self.model_status_icon.name = ft.Icons.CLOUD_DOWNLOAD
            self.model_status_icon.color = ft.Colors.RED
            self.download_model_button.visible = True
            self.load_model_button.visible = False
            self.unload_model_button.visible = False
            self.delete_model_button.visible = False
            self.models_loaded = False
            self.query_button.disabled = True
            self.query_button.tooltip = "请先下载并加载模型"

        self.model_status_text.value = message

        try:
            self._page.update()
        except Exception:
            pass
    
    def _start_download_model(self, e=None) -> None:
        """开始下载模型。"""
        if self.is_model_loading:
            return
        
        self.is_model_loading = True
        self._update_model_status("downloading", "正在下载模型...")
        self._page.run_task(self._download_model_async)
    
    async def _download_model_async(self) -> None:
        """异步下载模型。"""
        import asyncio

        try:
            def progress_callback(progress: float, message: str):
                """下载进度回调（从线程池内调用，只修改数据不刷新 UI）。"""
                self._pending_progress_message = message
                logger.info(f"下载进度: {progress*100:.1f}% - {message}")

            # 启动一个定时器协程，定期把进度刷新到 UI
            self._pending_progress_message = None
            self._download_finished = False

            async def _poll_progress():
                while not self._download_finished:
                    if self._pending_progress_message is not None:
                        self.model_status_text.value = self._pending_progress_message
                        self._pending_progress_message = None
                        try:
                            self._page.update()
                        except Exception:
                            pass
                    await asyncio.sleep(0.3)

            poll_task = asyncio.create_task(_poll_progress())

            # 在线程池中执行同步下载
            success, msg = await asyncio.to_thread(
                self.icp_service.download_models, progress_callback
            )

            self._download_finished = True
            await poll_task  # 等待轮询结束

            if success:
                logger.info(f"模型下载成功: {msg}")
                self._update_model_status("unloaded", "模型已下载，点击加载")
                self._show_snack("模型下载成功！")
            else:
                logger.error(f"模型下载失败: {msg}")
                self._update_model_status("need_download", "下载失败，请重试")
                self._show_snack(f"模型下载失败: {msg}", error=True)
        except Exception as e:
            self._download_finished = True
            logger.error(f"下载模型时出错: {e}")
            self._update_model_status("need_download", "下载失败，请重试")
            self._show_snack(f"下载失败: {e}", error=True)
        finally:
            self.is_model_loading = False
    
    def _on_load_model_click(self, e=None) -> None:
        """加载模型按钮点击事件。"""
        if self.is_model_loading:
            return

        # 使用page.run_task来运行异 asynchronous
        self._page.run_task(self._load_models_only)

    def _on_unload_model_click(self, e=None) -> None:
        """卸载模型按钮点击事件。"""
        if not self.models_loaded:
            self._show_snack("模型未加载，无需卸载", error=True)
            return

        try:
            # 卸载模型
            self.icp_service.unload_model()
            self.models_loaded = False

            # 更新状态显示
            self._update_model_status("unloaded", "模型已卸载，点击加载")

            self._show_snack("模型已卸载")
        except Exception as ex:
            logger.error(f"卸载模型时出错: {ex}")
            self._show_snack(f"卸载模型失败: {ex}", error=True)

    async def _load_models_only(self):
        """仅加载模型，不下载。"""
        try:
            self.is_model_loading = True
            self._update_model_status("loading", "正在加载模型...")
            
            # 加载模型
            detector_path, siamese_path = self.icp_service.get_model_paths()
            success = await self.icp_service.load_models(detector_path, siamese_path)
            
            if success:
                self.models_loaded = True
                logger.info("ICP模型加载成功")
                self._update_model_status("ready", "模型已就绪")
                self._show_snack("ICP模型加载成功")
            else:
                self.models_loaded = False
                logger.error("ICP模型加载失败")
                self._update_model_status("unloaded", "模型加载失败")
                self._show_snack("ICP模型加载失败", error=True)
        except Exception as e:
            logger.error(f"加载ICP模型时出错: {e}")
            self.models_loaded = False
            self._update_model_status("unloaded", "模型加载失败")
            self._show_snack(f"加载模型时出错: {e}", error=True)
        finally:
            self.is_model_loading = False
    
    def _extract_result_data(self, result: Dict[str, Any]):
        """解析查询结果，返回统一格式的数据。"""
        if "params" in result and isinstance(result["params"], dict):
            container = result["params"]
        else:
            container = result

        data_list = container.get("list", []) or []
        total = container.get("total", len(data_list))
        current_page = container.get("pageNum", 1)
        total_pages = container.get("pages", 1)
        page_size = container.get("pageSize", len(data_list) or 1)
        return data_list, total, current_page, total_pages, page_size, container

    async def _augment_records_with_detail(self, data_list: List[Dict[str, Any]], query_type: str) -> None:
        """为需要的记录补充详情信息。"""
        service_type_map = {
            "app": 6,
            "mapp": 7,
            "kapp": 8,
        }

        service_type = service_type_map.get(query_type)
        if not service_type:
            return

        for item in data_list:
            data_id = item.get("dataId")
            if not data_id:
                continue

            try:
                detail = await self.icp_service.get_detail_info(data_id, service_type)
                if detail:
                    item.update(detail)
            except Exception as exc:
                logger.error(f"获取详情失败 data_id={data_id}: {exc}")

    def _update_result_table(self, result: Dict[str, Any]) -> None:
        """更新结果表格。"""
        self.result_list.controls.clear()
        data_list, total, current_page, total_pages, page_size, _ = self._extract_result_data(result)
        self._last_result_data = result

        # 更新分页信息
        start_item = (current_page - 1) * page_size + 1
        end_item = min(current_page * page_size, total)
        self._page_info_text.value = f"第 {start_item}-{end_item} 项，共 {total} 项 | 第 {current_page}/{total_pages} 页"
        
        # 更新分页按钮状态
        self.prev_page_btn.disabled = current_page <= 1
        self.next_page_btn.disabled = current_page >= total_pages
        
        # 添加数据行
        for idx, item in enumerate(data_list, start_item):
            # 准备数据
            row_data = {
                "index": str(idx),
                "unit": item.get('unitName', '-'),
                "nature": item.get('natureName', '-'),
                "licence": item.get('serviceLicence') or item.get('mainLicence', '-'),
                "service": item.get('serviceName') or item.get('domain', '-'),
                "home": item.get('serviceHome') or item.get('domain', '-'),
                "time": item.get('updateRecordTime', '-'),
            }
            
            # 构建行控件
            cells = []
            for col in self.columns_config:
                col_id = col["id"]
                value = row_data.get(col_id, "-")
                
                # 特殊处理首页网址，添加链接点击
                content = None
                if col_id == "home" and value != "-":
                    content = ft.Text(
                        value,
                        size=12,
                        color=ft.Colors.BLUE,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=value,
                        selectable=True,
                    )
                    # 包装成可点击区域
                    content = ft.GestureDetector(
                        content=content,
                        on_tap=lambda e, url=value: self._on_url_click(url)
                    )
                else:
                    # 时间列允许换行
                    max_lines = 2 if col_id in ["unit", "service", "time"] else 1
                    content = ft.Text(
                        value,
                        size=12,
                        max_lines=max_lines,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=value,
                        selectable=True,
                    )
                
                cells.append(
                    ft.Container(
                        content=content,
                        expand=col["flex"],
                        alignment=ft.Alignment.CENTER if col["align"] == ft.MainAxisAlignment.CENTER else ft.Alignment.CENTER_LEFT,
                        padding=ft.padding.only(left=8) if col["align"] == ft.MainAxisAlignment.START else None,
                    )
                )
            
            # 创建行容器
            row_container = ft.Container(
                content=ft.Row(
                    controls=cells,
                    spacing=0,
                ),
                padding=ft.padding.symmetric(vertical=12, horizontal=4),
                border=ft.border.only(bottom=ft.border.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT)),
                bgcolor=ft.Colors.SURFACE if idx % 2 == 0 else ft.Colors.with_opacity(0.3, ft.Colors.SURFACE_CONTAINER_HIGHEST),  # 斑马纹
            )
            self.result_list.controls.append(row_container)
        
        self._page.update()

    def _on_url_click(self, url: str) -> None:
        """点击URL链接。"""
        if url and url != '-':
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception as e:
                logger.error(f"打开链接失败: {e}")
                self._show_snack(f"打开链接失败: {e}", error=True)

    async def _on_query_click(self, e=None):
        """查询按钮点击事件。"""
        logger.debug(f"查询点击: is_querying={self.is_querying}, models_loaded={self.models_loaded}")

        if self.is_querying:
            self._show_snack("正在查询中，请稍候...", error=True)
            return

        # 检查模型是否已加载（与其他工具保持一致的做法）
        if not self.models_loaded:
            logger.warning("查询时模型未加载，提示用户先加载模型")
            self._show_snack("请先加载模型后再进行查询", error=True)
            return

        # 获取查询参数
        query_type = self.query_type_dropdown.value
        search_text = self.search_input.value.strip()

        if not search_text:
            self._show_snack("请输入查询关键词", error=True)
            return
        
        try:
            page_num = int(self._page_num_input.value or "1")
            page_size = int(self._page_size_input.value or "10")
        except ValueError:
            self._show_snack("页码和每页数量必须是数字", error=True)
            return

        reset_page = (
            self.last_query_type != query_type
            or self.last_search_text != search_text
            or self.last_page_size != page_size
        )
        if reset_page and page_num != 1:
            page_num = 1
            self._page_num_input.value = "1"
        
        # 开始查询
        self.is_querying = True
        self.result_list.controls.clear()
        self._page_info_text.value = "正在查询..."
        self.prev_page_btn.disabled = True
        self.next_page_btn.disabled = True
        self._page.update()
        
        try:
            result = await self.icp_service.query_icp(
                query_type=query_type,
                search=search_text,
                page_num=page_num,
                page_size=page_size
            )
            
            if result:
                data_list, *_ = self._extract_result_data(result)
                if data_list:
                    await self._augment_records_with_detail(data_list, query_type)
                self._update_result_table(result)
                self.last_query_type = query_type
                self.last_search_text = search_text
                self.last_page_size = page_size
                self._show_snack("查询成功")
            else:
                self.result_list.controls.clear()
                self._page_info_text.value = "查询失败，无结果"
                self.prev_page_btn.disabled = True
                self.next_page_btn.disabled = True
                self._show_snack("查询失败", error=True)
            
        except httpx.TimeoutException:
            logger.error(f"查询超时: 网络请求超时")
            self.result_list.controls.clear()
            self._page_info_text.value = "查询超时"
            self.prev_page_btn.disabled = True
            self.next_page_btn.disabled = True
            self._show_snack("查询超时，请检查网络连接后重试", error=True)
        except httpx.NetworkError as e:
            logger.error(f"网络错误: {e}")
            self.result_list.controls.clear()
            self._page_info_text.value = "网络错误"
            self.prev_page_btn.disabled = True
            self.next_page_btn.disabled = True
            self._show_snack("网络连接失败，请检查网络设置", error=True)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误: {e.response.status_code}")
            self.result_list.controls.clear()
            self._page_info_text.value = f"HTTP {e.response.status_code} 错误"
            self.prev_page_btn.disabled = True
            self.next_page_btn.disabled = True
            self._show_snack(f"服务器返回错误 ({e.response.status_code})", error=True)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"查询失败: {e}", exc_info=True)
            self.result_list.controls.clear()
            self._page_info_text.value = "查询出错"
            self.prev_page_btn.disabled = True
            self.next_page_btn.disabled = True
            
            # 根据错误信息提供更友好的提示
            if "model" in error_msg.lower() or "onnx" in error_msg.lower():
                self._show_snack("模型加载失败，请重新下载模型", error=True)
            elif "timeout" in error_msg.lower():
                self._show_snack("查询超时，请重试", error=True)
            elif "connection" in error_msg.lower():
                self._show_snack("网络连接失败，请检查网络", error=True)
            else:
                # 显示部分错误信息（避免太长）
                short_msg = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
                self._show_snack(f"查询出错: {short_msg}", error=True)
        finally:
            self.is_querying = False
            self._page.update()
    
    async def _on_prev_page(self, e=None):
        """上一页。"""
        try:
            current_page = int(self._page_num_input.value or "1")
            if current_page > 1:
                self._page_num_input.value = str(current_page - 1)
                await self._on_query_click()
        except ValueError:
            pass
    
    async def _on_next_page(self, e=None):
        """下一页。"""
        try:
            current_page = int(self._page_num_input.value or "1")
            self._page_num_input.value = str(current_page + 1)
            await self._on_query_click()
        except ValueError:
            pass
    
    def _on_clear_click(self, e=None):
        """清空按钮点击事件。"""
        self.search_input.value = ""
        self.result_list.controls.clear()
        self._page_num_input.value = "1"
        self._page_info_text.value = "暂无数据"
        self.prev_page_btn.disabled = True
        self.next_page_btn.disabled = True
        self._page.update()
    
    async def _on_copy_result(self, e):
        """复制结果。"""
        if not self.result_list.controls:
            self._show_snack("没有可复制的内容", error=True)
            return

        lines = []
        # 表头
        headers = [col["label"] for col in self.columns_config]
        lines.append("\t".join(headers))
        
        # 内容
        # 注意：这里我们无法直接从控件中提取纯文本数据，因为控件结构比较复杂
        # 更好的做法是保存最后一次查询的数据，直接从数据中复制
        # 但为了保持现有逻辑，我们尝试从 _last_result_data 中提取
        
        if self._last_result_data:
            data_list, *_ = self._extract_result_data(self._last_result_data)
            for item in data_list:
                row_values = [
                    item.get('unitName', '-'),
                    item.get('natureName', '-'),
                    item.get('serviceLicence') or item.get('mainLicence', '-'),
                    item.get('serviceName') or item.get('domain', '-'),
                    item.get('serviceHome') or item.get('domain', '-'),
                    item.get('updateRecordTime', '-')
                ]
                # 注意：这里缺少序号，因为序号是动态生成的
                # 如果需要序号，可以在循环中添加
                lines.append("\t".join([str(v) for v in row_values]))
            
        result = "\n".join(lines)
        await ft.Clipboard().set(result)
        self._show_snack("结果已复制到剪贴板")
    
    def _on_back_click(self, e):
        """返回按钮点击事件。"""
        if self._prev_window_event_handler:
            self._page.on_window_event = self._prev_window_event_handler
        if self.on_back:
            self.on_back()
    
    def _show_snack(self, message: str, error: bool = False):
        """显示提示消息。"""
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
            duration=3000,
        )
        self._page.overlay.append(snackbar)
        snackbar.open = True
        self._page.update()

    def cleanup(self) -> None:
        """清理视图资源。

        当视图被切换走时调用，释放不需要的资源，包括：
        - 卸载已加载的ICP模型
        - 关闭HTTP会话
        - 清理其他资源
        """
        try:
            # 卸载ICP模型释放内存
            if hasattr(self, 'icp_service') and self.icp_service:
                self.icp_service.unload_model()

            # 异步关闭HTTP会话
            if hasattr(self, 'icp_service') and self.icp_service:
                import asyncio
                try:
                    # 尝试获取当前事件循环
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果循环正在运行，创建任务
                        loop.create_task(self.icp_service.close())
                    else:
                        # 如果循环未运行，直接运行
                        loop.run_until_complete(self.icp_service.close())
                except RuntimeError:
                    # 没有事件循环，跳过
                    pass

            # 清理其他资源
            self.models_loaded = False
            self.is_querying = False
            self.is_model_loading = False

            # 清除回调引用，打破循环引用
            self.on_back = None
            
            # 清除 UI 内容
            self.content = None

            import gc
            gc.collect()
            logger.info("ICP查询视图资源已清理")
        except Exception as e:
            logger.error(f"清理ICP查询视图资源时出错: {e}")
