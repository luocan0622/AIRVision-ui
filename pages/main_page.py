"""
AIRVision 主窗口页面对象。

业务实现按模块拆分至 pages/mixins/，本文件通过 Mixin 组合保持对外 API 不变。
可选命名空间：page.projects / page.workflows / page.canvas（见 pages/actions/）。
"""
from pywinauto import Application

from pages.actions import CanvasActions, ProjectActions, WorkflowActions
from pages.base_page import BasePage
from pages.mixins import (
    CommonMixin,
    CommunicationMixin,
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
    CommunicationMixin,
    MenuBarMixin,
    CommonMixin,
    BasePage,
):
    """AIRVision 主窗口页面对象。"""

    def __init__(self, app: Application):
        """
        Args:
            app: pywinauto Application 实例。
        """
        super().__init__(app)
        self._last_project_name: str | None = None
        self.projects = ProjectActions(self)
        self.workflows = WorkflowActions(self)
        self.canvas = CanvasActions(self)
