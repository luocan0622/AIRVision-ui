"""领域操作基类。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pages.main_page import MainPage


class PageActionsBase:
    """将 MainPage Mixin 方法按业务域分组暴露，便于扩展与文档化。"""

    __slots__ = ("_page",)

    def __init__(self, page: MainPage) -> None:
        self._page = page

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return getattr(self._page, method)(*args, **kwargs)
