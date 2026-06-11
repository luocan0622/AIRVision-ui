"""预定义检测流程（工具链）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class WorkflowPipelineDef:
    """一条可自动搭建的工作流流水线。"""

    name: str
    description: str
    tool_keys: tuple[str, ...]
    connect_sequential: bool = True


# 圆形工件 3D 检测：相机取图 → 3D 圆检测 → 结果判定 → 通讯输出
CIRCLE_WORKPIECE_DETECTION = WorkflowPipelineDef(
    name="circle_workpiece_detection",
    description="模拟圆形工件检测：相机数据源 → 3D圆检测 → 结果条件 → 通讯发送",
    tool_keys=(
        "camera_data_source",
        "d3_circle_detection",
        "result_condition_tool",
        "communication_send",
    ),
    connect_sequential=False,
)

# 带 ROI 预处理的扩展流程
CIRCLE_WORKPIECE_WITH_ROI = WorkflowPipelineDef(
    name="circle_workpiece_with_roi",
    description="圆形工件检测（含 ROI 裁剪）",
    tool_keys=(
        "camera_data_source",
        "d3_roi_crop_point_cloud",
        "d3_circle_detection",
        "result_condition_tool",
        "communication_send",
    ),
    connect_sequential=True,
)

# 扩展检测链：8 工具纵向
EXTENDED_DETECTION_PIPELINE = WorkflowPipelineDef(
    name="extended_detection",
    description=(
        "扩展检测链：相机 → ROI裁剪 → 圆检测 → 平面拟合 → 高度检测 "
        "→ 结果条件 → 点云可视化 → 通讯发送"
    ),
    tool_keys=(
        "camera_data_source",
        "d3_roi_crop_point_cloud",
        "d3_circle_detection",
        "d3_plane_fitting",
        "d3_height_detection",
        "result_condition_tool",
        "d3_point_cloud_visualization",
        "communication_send",
    ),
    connect_sequential=False,
)

PIPELINE_REGISTRY: dict[str, WorkflowPipelineDef] = {
    CIRCLE_WORKPIECE_DETECTION.name: CIRCLE_WORKPIECE_DETECTION,
    CIRCLE_WORKPIECE_WITH_ROI.name: CIRCLE_WORKPIECE_WITH_ROI,
    EXTENDED_DETECTION_PIPELINE.name: EXTENDED_DETECTION_PIPELINE,
}


def get_pipeline(name: str) -> WorkflowPipelineDef:
    if name not in PIPELINE_REGISTRY:
        raise KeyError(
            f"未知流程: {name!r}，可选: {list(PIPELINE_REGISTRY)}"
        )
    return PIPELINE_REGISTRY[name]


def list_pipelines() -> Sequence[WorkflowPipelineDef]:
    return tuple(PIPELINE_REGISTRY.values())
