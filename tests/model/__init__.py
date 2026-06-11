"""MainPage 业务 Mixin（已迁移至 pages/mixins，本包仅保留兼容 re-export）。"""
import warnings

from pages.mixins import (  # noqa: F401
    CommonMixin,
    FILTER_TOOL_COUNT,
    FILTER_TOOLS,
    HelpMixin,
    MenuBarMixin,
    ProjectMixin,
    ToolbarMixin,
    ToolsMixin,
    WorkflowMixin,
    get_filter_tool,
)

warnings.warn(
    "tests.model 已弃用，请改用 pages.mixins",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CommonMixin",
    "MenuBarMixin",
    "ToolbarMixin",
    "ProjectMixin",
    "WorkflowMixin",
    "ToolsMixin",
    "HelpMixin",
    "FILTER_TOOLS",
    "FILTER_TOOL_COUNT",
    "get_filter_tool",
]
