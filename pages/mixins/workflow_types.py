"""工作流流水线搭建相关的共享数据类型。"""
from __future__ import annotations

from dataclasses import dataclass

from pages.mixins.workflow_layout import LayoutPlan
from pages.mixins.workflow_pipelines import WorkflowPipelineDef


@dataclass(frozen=True)
class PipelineRunResult:
    """一次流水线放置的结果（低层 API）。"""

    plan: LayoutPlan
    connections: int = 0

    @property
    def node_count(self) -> int:
        return self.plan.node_count


@dataclass(frozen=True)
class WorkflowBuildResult:
    """一次完整检测流水线搭建的结果（高层 API）。"""

    plan: LayoutPlan
    connections: int
    pipeline: WorkflowPipelineDef | None = None

    @property
    def node_count(self) -> int:
        return self.plan.node_count
