"""MainPage 领域操作命名空间（可选 API，与 Mixin 方法并存）。"""
from pages.actions.canvas import CanvasActions
from pages.actions.projects import ProjectActions
from pages.actions.workflows import WorkflowActions

__all__ = ["ProjectActions", "WorkflowActions", "CanvasActions"]
