"""可复用的测试辅助函数。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Sequence

from utils.logger import logger

if TYPE_CHECKING:
    from pages.main_page import MainPage


def add_tool_and_assert(
    page: MainPage,
    tool_key: str,
    *,
    timeout: int = 15,
    pause: float = 0.5,
    message: str | None = None,
) -> None:
    """添加 Filter 工具并断言画布节点出现。"""
    tool = page.add_workflow_tool(tool_key)
    assert tool.key == tool_key
    detail = message or f"画布上应出现 {tool_key!r} 工具节点"
    assert page.has_workflow_tool_node_for_key(tool_key, timeout=timeout), detail
    time.sleep(pause)


def preview_pipeline_on_canvas(
    page: MainPage,
    tool_keys: Sequence[str],
    *,
    log_prefix: str = "",
) -> tuple[dict, object]:
    """读取当前画布尺寸并预览流水线布局。"""
    _, rect = page.get_canvas_rect()
    preview = page.preview_pipeline_layout(
        tool_keys,
        canvas_width=rect.width(),
        canvas_height=rect.height(),
    )
    prefix = f"{log_prefix} " if log_prefix else ""
    logger.info(
        f"{prefix}画布={rect.width()}x{rect.height()}px, "
        f"缩放={preview.get('target_zoom', 1):.0%}, "
        f"步长={preview.get('screen_step_px')}px"
    )
    return preview, rect
