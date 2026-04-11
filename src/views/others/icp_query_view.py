# -*- coding: utf-8 -*-
"""ICP备案查询视图模块。

提供ICP备案查询功能的用户界面。
滑块验证码由服务端自动完成，无需模型文件。
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
    """ICP备案查询视图类。"""

    def __init__(
        self,
        page: ft.Page,
        config_service: 'ConfigService',
        on_back: Optional[callable] = None
    ) -> None:
        super().__init__()
        self._page: ft.Page = page
        self.config_service: 'ConfigService' = config_service
        self.on_back: Optional[callable] = on_back
        self.icp_service: ICPService = ICPService(config_service)

        self.is_querying: bool = False
        self.last_query_type: Optional[str] = None
        self.last_search_text: str = ""
        self.last_page_size: int = 10
        self._prev_window_event_handler = page.on_window_event

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
        self.padding: ft.padding = ft.Padding.only(
            left=PADDING_MEDIUM,
            right=PADDING_MEDIUM,
            top=PADDING_MEDIUM,
            bottom=PADDING_MEDIUM,
        )

        self._page_info_text = ft.Text(
            "暂无数据", size=12, color=ft.Colors.ON_SURFACE_VARIANT,
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

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
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
            label="页码", hint_text="1", value="1",
            width=100, dense=True, keyboard_type=ft.KeyboardType.NUMBER,
        )
        self._page_size_input = ft.TextField(
            label="每页数量", hint_text="10", value="10",
            width=120, dense=True, keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.query_button = ft.Button(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEARCH, size=20),
                    ft.Text("查询", size=16),
                ],
                spacing=8,
            ),
            on_click=self._on_query_click,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=PADDING_LARGE, vertical=PADDING_MEDIUM),
            ),
        )

        query_input_area = ft.Column(
            controls=[
                ft.Row(
                    controls=[self.query_type_dropdown, self.search_input, self.query_button],
                    spacing=PADDING_MEDIUM,
                ),
                ft.Row(
                    controls=[
                        self._page_num_input,
                        self._page_size_input,
                        ft.OutlinedButton("清空", icon=ft.Icons.CLEAR, on_click=self._on_clear_click),
                        ft.Container(expand=True),
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "支持域名、备案号、企业名称查询 | 数据来自工信部ICP备案管理系统，频繁查询会被风控",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=PADDING_MEDIUM,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=PADDING_MEDIUM,
        )

        header_row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Text(col["label"], weight=ft.FontWeight.W_500, size=13),
                        expand=col["flex"],
                        alignment=(
                            ft.Alignment.CENTER
                            if col["align"] == ft.MainAxisAlignment.CENTER
                            else ft.Alignment.CENTER_LEFT
                        ),
                        padding=ft.Padding.only(left=8) if col["align"] == ft.MainAxisAlignment.START else None,
                    )
                    for col in self.columns_config
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=ft.Padding.symmetric(vertical=10),
            border=ft.Border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        )

        self.result_list = ft.ListView(expand=True, spacing=0, padding=0)

        self.result_container = ft.Container(
            content=ft.Column(
                controls=[header_row, self.result_list],
                spacing=0, expand=True,
            ),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=BORDER_RADIUS_MEDIUM,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            expand=True,
        )

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

        query_settings_container = ft.Container(
            content=query_input_area,
            padding=PADDING_MEDIUM,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=BORDER_RADIUS_MEDIUM,
        )

        result_area = ft.Column(
            controls=[top_controls, self.result_container, pagination_controls],
            spacing=PADDING_SMALL,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                query_settings_container,
                result_area,
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------

    def _on_query_type_changed(self, e) -> None:
        self._page_num_input.value = "1"
        try:
            self._page_num_input.update()
        except Exception:
            pass

    async def _on_query_click(self, e=None):
        if self.is_querying:
            self._show_snack("正在查询中，请稍候...", error=True)
            return

        search_text = self.search_input.value.strip()
        if not search_text:
            self._show_snack("请输入查询关键词", error=True)
            return

        query_type = self.query_type_dropdown.value
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
                page_size=page_size,
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
            self.result_list.controls.clear()
            self._page_info_text.value = "查询超时"
            self._show_snack("查询超时，请检查网络连接后重试", error=True)
        except httpx.NetworkError:
            self.result_list.controls.clear()
            self._page_info_text.value = "网络错误"
            self._show_snack("网络连接失败，请检查网络设置", error=True)
        except httpx.HTTPStatusError as e:
            self.result_list.controls.clear()
            self._page_info_text.value = f"HTTP {e.response.status_code} 错误"
            self._show_snack(f"服务器返回错误 ({e.response.status_code})", error=True)
        except Exception as e:
            self.result_list.controls.clear()
            self._page_info_text.value = "查询出错"
            short_msg = str(e)[:50]
            self._show_snack(f"查询出错: {short_msg}", error=True)
        finally:
            self.is_querying = False
            self._page.update()

    async def _on_prev_page(self, e=None):
        try:
            cur = int(self._page_num_input.value or "1")
            if cur > 1:
                self._page_num_input.value = str(cur - 1)
                await self._on_query_click()
        except ValueError:
            pass

    async def _on_next_page(self, e=None):
        try:
            cur = int(self._page_num_input.value or "1")
            self._page_num_input.value = str(cur + 1)
            await self._on_query_click()
        except ValueError:
            pass

    def _on_clear_click(self, e=None):
        self.search_input.value = ""
        self.result_list.controls.clear()
        self._page_num_input.value = "1"
        self._page_info_text.value = "暂无数据"
        self.prev_page_btn.disabled = True
        self.next_page_btn.disabled = True
        self._page.update()

    def _on_back_click(self, e):
        if self._prev_window_event_handler:
            self._page.on_window_event = self._prev_window_event_handler
        if self.on_back:
            self.on_back()

    # ------------------------------------------------------------------
    # result table
    # ------------------------------------------------------------------

    def _extract_result_data(self, result: Dict[str, Any]):
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
        svc_map = {"app": 6, "mapp": 7, "kapp": 8}
        svc_type = svc_map.get(query_type)
        if not svc_type:
            return
        for item in data_list:
            data_id = item.get("dataId")
            if not data_id:
                continue
            try:
                detail = await self.icp_service.get_detail_info(data_id, svc_type)
                if detail:
                    item.update(detail)
            except Exception as exc:
                logger.error(f"获取详情失败 data_id={data_id}: {exc}")

    def _update_result_table(self, result: Dict[str, Any]) -> None:
        self.result_list.controls.clear()
        data_list, total, current_page, total_pages, page_size, _ = self._extract_result_data(result)
        self._last_result_data = result

        start_item = (current_page - 1) * page_size + 1
        end_item = min(current_page * page_size, total)
        self._page_info_text.value = f"第 {start_item}-{end_item} 项，共 {total} 项 | 第 {current_page}/{total_pages} 页"

        self.prev_page_btn.disabled = current_page <= 1
        self.next_page_btn.disabled = current_page >= total_pages

        for idx, item in enumerate(data_list, start_item):
            row_data = {
                "index": str(idx),
                "unit": item.get("unitName", "-"),
                "nature": item.get("natureName", "-"),
                "licence": item.get("serviceLicence") or item.get("mainLicence", "-"),
                "service": item.get("serviceName") or item.get("domain", "-"),
                "home": item.get("serviceHome") or item.get("domain", "-"),
                "time": item.get("updateRecordTime", "-"),
            }

            cells = []
            for col in self.columns_config:
                col_id = col["id"]
                value = row_data.get(col_id, "-")

                if col_id == "home" and value != "-":
                    content = ft.GestureDetector(
                        content=ft.Text(
                            value, size=12, color=ft.Colors.BLUE,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            tooltip=value, selectable=True,
                        ),
                        on_tap=lambda _, url=value: self._on_url_click(url),
                    )
                else:
                    max_lines = 2 if col_id in ("unit", "service", "time") else 1
                    content = ft.Text(
                        value, size=12, max_lines=max_lines,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=value, selectable=True,
                    )

                cells.append(
                    ft.Container(
                        content=content,
                        expand=col["flex"],
                        alignment=(
                            ft.Alignment.CENTER
                            if col["align"] == ft.MainAxisAlignment.CENTER
                            else ft.Alignment.CENTER_LEFT
                        ),
                        padding=ft.Padding.only(left=8) if col["align"] == ft.MainAxisAlignment.START else None,
                    )
                )

            row_container = ft.Container(
                content=ft.Row(controls=cells, spacing=0),
                padding=ft.Padding.symmetric(vertical=12, horizontal=4),
                border=ft.Border.only(bottom=ft.border.BorderSide(0.5, ft.Colors.OUTLINE_VARIANT)),
                bgcolor=(
                    ft.Colors.SURFACE if idx % 2 == 0
                    else ft.Colors.with_opacity(0.3, ft.Colors.SURFACE_CONTAINER_HIGHEST)
                ),
            )
            self.result_list.controls.append(row_container)

        self._page.update()

    def _on_url_click(self, url: str) -> None:
        if url and url != "-":
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception as e:
                self._show_snack(f"打开链接失败: {e}", error=True)

    async def _on_copy_result(self, e):
        if not self.result_list.controls:
            self._show_snack("没有可复制的内容", error=True)
            return

        lines = ["\t".join(col["label"] for col in self.columns_config)]

        if self._last_result_data:
            data_list, *_ = self._extract_result_data(self._last_result_data)
            for item in data_list:
                row_values = [
                    item.get("unitName", "-"),
                    item.get("natureName", "-"),
                    item.get("serviceLicence") or item.get("mainLicence", "-"),
                    item.get("serviceName") or item.get("domain", "-"),
                    item.get("serviceHome") or item.get("domain", "-"),
                    item.get("updateRecordTime", "-"),
                ]
                lines.append("\t".join(str(v) for v in row_values))

        await ft.Clipboard().set("\n".join(lines))
        self._show_snack("结果已复制到剪贴板")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _show_snack(self, message: str, error: bool = False):
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.RED_400 if error else ft.Colors.GREEN_400,
            duration=3000,
        )
        self._page.show_dialog(snackbar)

    def cleanup(self) -> None:
        try:
            if hasattr(self, "icp_service") and self.icp_service:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.icp_service.close())
                    else:
                        loop.run_until_complete(self.icp_service.close())
                except RuntimeError:
                    pass

            self.is_querying = False
            self.on_back = None
            self.content = None

            import gc
            gc.collect()
            logger.info("ICP查询视图资源已清理")
        except Exception as e:
            logger.error(f"清理ICP查询视图资源时出错: {e}")
