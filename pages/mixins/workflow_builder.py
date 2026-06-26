"""VisionMaster 式工作流搭建器：视口缩放 → 链式放置 → 顺序连线。"""
from __future__ import annotations

from typing import Sequence

from pages.mixins.workflow_layout import LayoutPlan
from pages.mixins.workflow_pipelines import (
    CIRCLE_WORKPIECE_DETECTION,
    EXTENDED_DETECTION_PIPELINE,
    WorkflowPipelineDef,
    get_pipeline,
)
from pages.mixins.workflow_types import WorkflowBuildResult
from utils.logger import logger


class WorkflowBuilderMixin:
    """高层 API：自动计算画布空间、放置工具、顺序连线。"""

    def build_detection_workflow(
        self,
        pipeline: str | WorkflowPipelineDef,
        *,
        connect: bool | None = None,
        fresh_workflow: bool = True,
        verify_nodes: bool = True,
        node_timeout: int = 20,
        pause_between: float = 0.5,
    ) -> WorkflowBuildResult:
        """搭建检测流水线（圆形工件等预定义流程）。"""
        if isinstance(pipeline, str):
            pipeline_def = get_pipeline(pipeline)
        else:
            pipeline_def = pipeline

        do_connect = (
            connect if connect is not None else pipeline_def.connect_sequential
        )
        logger.info(
            f"搭建检测流程: {pipeline_def.name} — {pipeline_def.description}"
        )

        run = self.build_workflow_pipeline(
            pipeline_def.tool_keys,
            connect=do_connect,
            verify_nodes=verify_nodes,
            fresh_workflow=fresh_workflow,
            node_timeout=node_timeout,
            pause_between=pause_between,
        )
        if do_connect:
            logger.info(
                f"流程 {pipeline_def.name!r} 已完成 {run.connections} 条连线"
            )

        return WorkflowBuildResult(
            plan=run.plan,
            connections=run.connections,
            pipeline=pipeline_def,
        )

    def build_circle_workpiece_detection(
        self,
        *,
        connect: bool = False,
        verify_nodes: bool = True,
    ) -> WorkflowBuildResult:
        """圆形工件检测：相机 → 3D圆检测 → 结果条件 → 通讯发送。"""
        return self.build_detection_workflow(
            CIRCLE_WORKPIECE_DETECTION,
            connect=connect,
            verify_nodes=verify_nodes,
        )

    def build_extended_detection_pipeline(
        self, *, verify_nodes: bool = True
    ) -> WorkflowBuildResult:
        """扩展 8 工具检测链。"""
        return self.build_detection_workflow(
            EXTENDED_DETECTION_PIPELINE,
            connect=False,
            verify_nodes=verify_nodes,
        )

    def preview_pipeline_layout(
        self,
        tool_keys: Sequence[str],
        *,
        canvas_width: int = 0,
        canvas_height: int = 0,
    ) -> dict:
        """仅计算布局（不操作 UI），供测试前置检查。"""
        from pages.mixins.workflow_layout import WorkflowLayoutEngine

        keys = tuple(tool_keys)
        result: dict = {"node_count": len(keys)}
        if canvas_width > 0 and canvas_height > 0:
            z, plan = WorkflowLayoutEngine.plan_viewport_pipeline(
                0, 0, canvas_width, canvas_height, keys
            )
            result["target_zoom"] = z
            result["screen_step_px"] = plan.v_gap
            result["fits_viewport"] = plan.fits_canvas
            result["canvas_width"] = canvas_width
            result["canvas_height"] = canvas_height
        return result
