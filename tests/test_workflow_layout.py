"""工作流布局引擎单元测试（无需启动应用）。"""
from pages import WorkflowLayoutEngine


class TestWorkflowLayoutEngine:
    def test_viewport_vertical_even_slots(self):
        keys = (
            "camera_data_source",
            "d3_circle_detection",
            "result_condition_tool",
            "communication_send",
        )
        plan = WorkflowLayoutEngine.compute_viewport_vertical_layout(
            1209, 270, 507, 600, keys, zoom_factor=1.0
        )
        assert plan.node_count == 4
        assert plan.fits_canvas
        assert plan.zoom_factor == 1.0
        ys = [p.y for p in plan.placements]
        assert ys == sorted(ys)
        steps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        assert max(steps) - min(steps) <= 1
        assert 60 <= steps[0] <= 160
        assert min(ys) >= 270 + WorkflowLayoutEngine.VIEWPORT_MARGIN
        assert max(ys) <= 270 + 600 - WorkflowLayoutEngine.VIEWPORT_MARGIN

    def test_viewport_fit_zoom_keeps_100_for_four_nodes(self):
        z = WorkflowLayoutEngine.compute_viewport_fit_zoom(4, 507, 600)
        assert z == 1.0

    def test_viewport_fit_zoom_not_too_small_for_eight(self):
        z = WorkflowLayoutEngine.compute_viewport_fit_zoom(8, 507, 600)
        assert z >= WorkflowLayoutEngine.MIN_ZOOM
        assert z >= 0.80

    def test_port_offsets_vertical_exec(self):
        out_x, out_y = WorkflowLayoutEngine.output_port_xy(
            500, 300, zoom_factor=1.0
        )
        in_x, in_y = WorkflowLayoutEngine.input_port_xy(
            500, 300, zoom_factor=1.0
        )
        assert out_x == in_x == 500
        assert out_y > 300 and in_y < 300
        assert out_y - 300 == WorkflowLayoutEngine.PORT_OUT_DY
        assert 300 - in_y == abs(WorkflowLayoutEngine.PORT_IN_DY)

    def test_result_condition_connection_ports(self):
        src = (500, 400)
        dst = (500, 600)
        out_pt, in_pt = WorkflowLayoutEngine.connection_endpoints(
            "result_condition_tool",
            "communication_send",
            src,
            dst,
            zoom_factor=1.0,
            src_branch="true",
        )
        assert out_pt[0] < src[0]
        assert out_pt[1] > src[1]
