"""工作流画布领域操作。"""
from __future__ import annotations

from pages.actions.base import PageActionsBase


class CanvasActions(PageActionsBase):
    """画布 Filter 工具与布局相关操作的命名空间入口。"""

    def add_tool(self, *args, **kwargs):
        return self._call("add_workflow_tool", *args, **kwargs)

    def has_tool_node(self, *args, **kwargs):
        return self._call("has_workflow_tool_node_for_key", *args, **kwargs)

    def get_node_position(self, *args, **kwargs):
        return self._call("get_workflow_node_position", *args, **kwargs)

    def preview_layout(self, *args, **kwargs):
        return self._call("preview_pipeline_layout", *args, **kwargs)

    def get_rect(self, *args, **kwargs):
        return self._call("get_canvas_rect", *args, **kwargs)

    def find(self, *args, **kwargs):
        return self._call("find_workflow_canvas", *args, **kwargs)
