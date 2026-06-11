"""工作流流水线搭建：多工具链式放置与连线。"""
from __future__ import annotations

import time
from typing import Sequence

from pages.mixins.filter import get_filter_tool
from pages.mixins.filter_menu import FilterMenuMixin
from pages.mixins.workflow_builder import WorkflowBuilderMixin
from pages.mixins.workflow_layout import (
    LayoutPlan,
    NodePlacement,
    WorkflowLayoutEngine,
)
from pages.mixins.workflow_pipelines import (
    EXTENDED_DETECTION_PIPELINE,
    WorkflowPipelineDef,
    get_pipeline,
)
from utils.logger import logger


class WorkflowPipelineMixin(WorkflowBuilderMixin, FilterMenuMixin):
    """按链式步长批量添加工具并顺序连线。"""

    def build_workflow_pipeline(
        self,
        tool_keys: Sequence[str],
        *,
        connect: bool = False,
        verify_nodes: bool = True,
        node_timeout: int = 20,
        pause_between: float = 1.0,
        fresh_workflow: bool = True,
    ) -> LayoutPlan:
        """① 新建空白工作流 ② 适配缩放 ③ 链式放置 ④ 可选连线。"""
        keys = tuple(tool_keys)
        self.clear_workflow_node_positions()
        self.mouse_press_key("esc")
        time.sleep(0.3)

        if fresh_workflow:
            self.new_workflow()
            time.sleep(0.6)
            self._canvas_zoom = 1.0

        _zoom, plan = self.prepare_canvas_for_tools(keys)
        self.log_layout_plan(plan)

        chain_step = plan.v_gap or WorkflowLayoutEngine.MIN_CENTER_STEP
        _, rect = self.get_canvas_rect()
        origin_x, origin_y = self._canvas_node_origin(rect)
        last_x: int | None = None
        last_y: int | None = None

        for i, key in enumerate(keys):
            defn = get_filter_tool(key)
            if last_y is None:
                px, py = origin_x, origin_y
            else:
                px = origin_x
                py = int(last_y + chain_step)

            drag_from = (last_x, last_y) if last_x is not None else None
            use_drag = i > 0

            logger.info(
                f"放置 [{i + 1}/{len(keys)}] {defn.display_name!r} "
                f"screen=({px},{py}) 链式步长={chain_step}px "
                f"drag={use_drag} zoom={self.get_canvas_zoom():.0%}"
            )
            placement = NodePlacement(
                tool_key=key,
                index=i,
                x=px,
                y=py,
                row=i,
            )
            self.add_workflow_tool_from_placement(
                placement,
                timeout=10,
                use_drag_place=use_drag,
                drag_from=drag_from,
            )
            last_x, last_y = px, py

            if verify_nodes:
                assert self.has_workflow_tool_node_for_key(
                    key, timeout=node_timeout
                ), f"画布上应出现 {defn.display_name!r} 节点"
            time.sleep(pause_between)

        if connect and len(keys) > 1:
            linked = self.connect_workflow_pipeline(keys)
            logger.info(f"已完成 {linked} 条顺序连线")

        return plan

    def build_named_pipeline(
        self,
        pipeline_name: str,
        *,
        verify_nodes: bool = True,
    ) -> LayoutPlan:
        """搭建预注册流程（如圆形工件检测）。"""
        pipeline = get_pipeline(pipeline_name)
        logger.info(f"搭建流程: {pipeline.name} — {pipeline.description}")
        return self.build_workflow_pipeline(
            pipeline.tool_keys,
            connect=pipeline.connect_sequential,
            verify_nodes=verify_nodes,
        )

    def build_extended_detection_pipeline(
        self, *, verify_nodes: bool = True
    ) -> LayoutPlan:
        """扩展 8 工具检测链。"""
        return self.build_workflow_pipeline(
            EXTENDED_DETECTION_PIPELINE.tool_keys,
            connect=False,
            verify_nodes=verify_nodes,
        )
