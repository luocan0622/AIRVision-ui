"""Projects 菜单领域操作。"""
from __future__ import annotations

from pages.actions.base import PageActionsBase


class ProjectActions(PageActionsBase):
    """Projects 相关操作的命名空间入口。"""

    def new_project(self, *args, **kwargs):
        return self._call("new_project", *args, **kwargs)

    def open_project(self, *args, **kwargs):
        return self._call("open_project", *args, **kwargs)

    def save_project(self, *args, **kwargs):
        return self._call("save_project", *args, **kwargs)

    def save_project_as(self, *args, **kwargs):
        return self._call("save_project_as", *args, **kwargs)

    def close_project(self, *args, **kwargs):
        return self._call("close_project", *args, **kwargs)

    def set_default_template_image(self, *args, **kwargs):
        return self._call("set_default_template_image", *args, **kwargs)

    def ensure_open(self, *args, **kwargs):
        return self._call("ensure_project_open", *args, **kwargs)

    def get_file_path(self, *args, **kwargs):
        return self._call("get_project_file_path", *args, **kwargs)
