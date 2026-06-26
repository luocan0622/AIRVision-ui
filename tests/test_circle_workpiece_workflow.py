"""
圆形工件检测工作流 Demo（VisionMaster 式）。

视口槽位布局 → 批量放置工具（连线暂不测）。
"""
import pytest

from pages import WorkflowLayoutEngine
from pages.mixins.workflow_pipelines import (
    CIRCLE_WORKPIECE_DETECTION,
    EXTENDED_DETECTION_PIPELINE,
)
from tests import flow_steps as fs
from tests.support.helpers import preview_pipeline_on_canvas
from utils.logger import logger


class TestCircleWorkpieceWorkflow:
    """模拟 VisionMaster 检测流程：多工具布局 + 放置。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    @pytest.mark.demo
    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_circle_workpiece_detection_pipeline(self):
        """圆形工件检测：相机 → 3D圆检测 → 结果条件 → 通讯发送。"""
        fs.prepare_workflow_canvas(self.page)
        keys = CIRCLE_WORKPIECE_DETECTION.tool_keys

        def _preview_layout():
            preview, rect = preview_pipeline_on_canvas(self.page, keys)
            assert preview.get("target_zoom", 1) >= 0.98, "4 节点在视口内应保持 100% 缩放"
            return preview, rect

        preview, rect = fs.run_step(
            "布局预览",
            "preview_pipeline_layout",
            _preview_layout,
            args={"tool_keys": keys},
        )

        result = fs.step_build_circle_workpiece_pipeline(self.page)
        plan = result.plan

        def _verify_result():
            assert result.node_count == len(keys)
            assert result.connections == 0
            assert plan.fits_canvas
            assert plan.zoom_factor >= 0.98
            assert 60 <= plan.v_gap <= 180, f"步长应紧凑: {plan.v_gap}px"
            ys = [p.y for p in plan.placements]
            assert ys == sorted(ys)
            assert ys[0] >= rect.top + WorkflowLayoutEngine.VIEWPORT_MARGIN
            assert ys[-1] <= rect.bottom - WorkflowLayoutEngine.VIEWPORT_MARGIN
            for key in keys:
                assert self.page.get_workflow_node_position(key) is not None

        fs.run_step(
            "验证圆形工件检测流程",
            "verify_circle_workpiece_pipeline",
            _verify_result,
            args={"target_zoom": preview.get("target_zoom", 1)},
            pause=1.0,
        )
        logger.info("圆形工件检测流程搭建完成")

    @pytest.mark.demo
    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_extended_detection_pipeline(self):
        """扩展 8 工具链：验证视口缩放与紧凑槽位。"""
        fs.prepare_workflow_canvas(self.page)
        keys = EXTENDED_DETECTION_PIPELINE.tool_keys

        def _preview_layout():
            preview, _rect = preview_pipeline_on_canvas(
                self.page, keys, log_prefix="[8工具]"
            )
            assert preview.get("target_zoom", 1) >= WorkflowLayoutEngine.MIN_ZOOM
            return preview

        fs.run_step(
            "8 工具布局预览",
            "preview_extended_pipeline_layout",
            _preview_layout,
            args={"tool_count": len(keys)},
        )

        def _build_and_verify():
            result = self.page.build_extended_detection_pipeline(verify_nodes=True)
            plan = result.plan
            assert result.node_count == len(keys)
            assert plan.fits_canvas
            assert plan.zoom_factor >= WorkflowLayoutEngine.MIN_ZOOM
            ys = [p.y for p in plan.placements]
            steps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
            assert len(set(steps)) == 1
            assert min(steps) >= 50, f"8 工具步长应紧凑: {steps}"
            return result

        fs.run_step(
            "搭建并验证 8 工具检测流程",
            "build_extended_detection_pipeline",
            _build_and_verify,
            pause=1.0,
        )
        logger.info("扩展 8 工具检测流程搭建完成")
