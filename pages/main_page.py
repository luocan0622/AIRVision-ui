"""
AIRVision 主窗口页面对象。

业务实现按模块拆分至 pages/mixins/，本文件通过 Mixin 组合保持对外 API 不变。
控件定位基于 Inspect.exe / print_control_identifiers() 获取的 AutomationId。
"""
from pywinauto import Application

from pages.base_page import BasePage
from pages.mixins import (
    CommonMixin,
    HelpMixin,
    MenuBarMixin,
    ProjectMixin,
    ToolbarMixin,
    ToolsMixin,
    WorkflowMixin,
)


class MainPage(
    ProjectMixin,
    WorkflowMixin,
    ToolsMixin,
    HelpMixin,
    ToolbarMixin,
    MenuBarMixin,
    CommonMixin,
    BasePage,
):
    """AIRVision 主窗口页面对象。"""

    OK = {"title": "OK", "control_type": "Button"}

    def __init__(self, app: Application):
        """
        Args:
            app: pywinauto Application 实例。
        """
        super().__init__(app)
        self._last_project_name: str | None = None
