"""Workflows 菜单与流水线领域操作。"""
from __future__ import annotations

from pages.actions.base import PageActionsBase


class WorkflowActions(PageActionsBase):
    """Workflows 与工作流流水线相关操作的命名空间入口。"""

    def new(self, *args, **kwargs):
        return self._call("new_workflow", *args, **kwargs)

    def open(self, *args, **kwargs):
        return self._call("open_workflow", *args, **kwargs)

    def save(self, *args, **kwargs):
        return self._call("save_workflow", *args, **kwargs)

    def close(self, *args, **kwargs):
        return self._call("close_workflow", *args, **kwargs)

    def rename(self, *args, **kwargs):
        return self._call("rename_workflow", *args, **kwargs)

    def ensure_tab_open(self, *args, **kwargs):
        return self._call("ensure_workflow_tab_open", *args, **kwargs)

    def get_active_name(self, *args, **kwargs):
        return self._call("get_active_workflow_name", *args, **kwargs)

    def build_pipeline(self, *args, **kwargs):
        return self._call("build_workflow_pipeline", *args, **kwargs)

    def build_detection(self, *args, **kwargs):
        return self._call("build_detection_workflow", *args, **kwargs)

    def build_circle_workpiece(self, *args, **kwargs):
        return self._call("build_circle_workpiece_detection", *args, **kwargs)

    def build_extended_detection(self, *args, **kwargs):
        return self._call("build_extended_detection_pipeline", *args, **kwargs)
