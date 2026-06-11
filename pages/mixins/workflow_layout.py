"""工作流画布布局：视口链式步长 + 端口坐标（用于连线）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


@dataclass(frozen=True)
class NodePlacement:
    """单个工具节点的屏幕放置坐标。"""

    tool_key: str
    index: int
    x: int
    y: int
    row: int = 0
    col: int = 0


@dataclass(frozen=True)
class LayoutPlan:
    """流水线布局摘要（步长与缩放，供链式放置使用）。"""

    placements: tuple[NodePlacement, ...]
    v_gap: int
    canvas_width: int
    canvas_height: int
    zoom_factor: float = 1.0
    fits_canvas: bool = True

    @property
    def node_count(self) -> int:
        return len(self.placements)


class WorkflowLayoutEngine:
    """视口链式布局 + Exec 端口偏移。"""

    NODE_WIDTH = 200
    NODE_HEIGHT = 80
    VIEWPORT_MARGIN = 40
    MIN_CENTER_STEP = 72

    MIN_ZOOM = 0.70
    MAX_ZOOM = 1.0
    ZOOM_STEP_RATIO = 1.12

    PORT_IN_DY = -48
    PORT_OUT_DY = 48
    PORT_CONDITION_IN_DY = -52
    PORT_TRUE_OUT_DX = -58
    PORT_TRUE_OUT_DY = 48
    PORT_FALSE_OUT_DX = 58

    @classmethod
    def compute_viewport_fit_zoom(
        cls,
        node_count: int,
        canvas_width: int,
        canvas_height: int,
    ) -> float:
        """视口适配缩放：优先 100%，仅当节点在视口内排不下时才缩小。"""
        n = max(0, node_count)
        if n <= 1:
            return 1.0
        margin = cls.VIEWPORT_MARGIN
        usable_h = max(1, canvas_height - 2 * margin)
        need_h = cls.NODE_HEIGHT + (n - 1) * cls.MIN_CENTER_STEP
        if need_h <= usable_h:
            return 1.0
        z = (usable_h / need_h) * 0.96
        return max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, z))

    @classmethod
    def zoom_steps_for_factor(cls, factor: float) -> int:
        if factor <= 0 or abs(factor - 1.0) < 0.04:
            return 0
        import math

        steps = int(round(math.log(factor) / math.log(cls.ZOOM_STEP_RATIO)))
        return max(-30, min(30, steps))

    @classmethod
    def compute_viewport_vertical_layout(
        cls,
        canvas_left: int,
        canvas_top: int,
        canvas_width: int,
        canvas_height: int,
        tool_keys: Sequence[str],
        *,
        zoom_factor: float = 1.0,
    ) -> LayoutPlan:
        """计算视口内纵向步长（链式放置用，槽位坐标仅供参考）。"""
        z = max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, zoom_factor))
        keys = tuple(tool_keys)
        n = len(keys)
        margin = cls.VIEWPORT_MARGIN
        cx = canvas_left + canvas_width // 2
        node_h_s = cls.NODE_HEIGHT * z
        usable_h = max(1, canvas_height - 2 * margin)

        if n == 0:
            return LayoutPlan(
                placements=(),
                v_gap=0,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                zoom_factor=z,
            )

        if n == 1:
            y_centers = [int(canvas_top + margin + usable_h // 2)]
        else:
            y_min = canvas_top + margin + node_h_s / 2
            y_max = canvas_top + canvas_height - margin - node_h_s / 2
            step = (y_max - y_min) / (n - 1)
            y_centers = [int(round(y_min + i * step)) for i in range(n)]

        placements = tuple(
            NodePlacement(tool_key=key, index=i, x=cx, y=y_centers[i], row=i)
            for i, key in enumerate(keys)
        )
        screen_step = int(y_centers[1] - y_centers[0]) if n > 1 else 0
        return LayoutPlan(
            placements=placements,
            v_gap=screen_step,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            zoom_factor=z,
        )

    @classmethod
    def plan_viewport_pipeline(
        cls,
        canvas_left: int,
        canvas_top: int,
        canvas_width: int,
        canvas_height: int,
        tool_keys: Sequence[str],
    ) -> tuple[float, LayoutPlan]:
        """一站式：视口适配缩放 + 链式步长。"""
        keys = tuple(tool_keys)
        z = cls.compute_viewport_fit_zoom(len(keys), canvas_width, canvas_height)
        plan = cls.compute_viewport_vertical_layout(
            canvas_left, canvas_top, canvas_width, canvas_height, keys, zoom_factor=z
        )
        return z, plan

    @classmethod
    def _is_result_condition(cls, tool_key: str) -> bool:
        return "result_condition" in tool_key

    @classmethod
    def input_port_xy_for(
        cls, tool_key: str, x: int, y: int, *, zoom_factor: float = 1.0
    ) -> tuple[int, int]:
        z = max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, zoom_factor))
        if cls._is_result_condition(tool_key):
            return x, y + int(cls.PORT_CONDITION_IN_DY * z)
        return cls.input_port_xy(x, y, zoom_factor=z)

    @classmethod
    def output_port_xy_for(
        cls,
        tool_key: str,
        x: int,
        y: int,
        *,
        zoom_factor: float = 1.0,
        branch: Literal["exec", "true", "false"] = "exec",
    ) -> tuple[int, int]:
        z = max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, zoom_factor))
        if cls._is_result_condition(tool_key):
            if branch == "false":
                return x + int(cls.PORT_FALSE_OUT_DX * z), y + int(
                    cls.PORT_TRUE_OUT_DY * z
                )
            return x + int(cls.PORT_TRUE_OUT_DX * z), y + int(
                cls.PORT_TRUE_OUT_DY * z
            )
        return cls.output_port_xy(x, y, zoom_factor=z)

    @classmethod
    def connection_endpoints(
        cls,
        src_tool_key: str,
        dst_tool_key: str,
        src_pos: tuple[int, int],
        dst_pos: tuple[int, int],
        *,
        zoom_factor: float = 1.0,
        src_branch: Literal["exec", "true", "false"] = "exec",
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        out_pt = cls.output_port_xy_for(
            src_tool_key, *src_pos, zoom_factor=zoom_factor, branch=src_branch
        )
        in_pt = cls.input_port_xy_for(
            dst_tool_key, *dst_pos, zoom_factor=zoom_factor
        )
        return out_pt, in_pt

    @classmethod
    def output_port_xy(
        cls, x: int, y: int, zoom_factor: float = 1.0
    ) -> tuple[int, int]:
        z = max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, zoom_factor))
        return x, y + int(cls.PORT_OUT_DY * z)

    @classmethod
    def input_port_xy(
        cls, x: int, y: int, zoom_factor: float = 1.0
    ) -> tuple[int, int]:
        z = max(cls.MIN_ZOOM, min(cls.MAX_ZOOM, zoom_factor))
        return x, y + int(cls.PORT_IN_DY * z)
