"""
AIRVision 单轮全流程端到端测试。

按固定顺序模拟用户完成一次完整的项目与工作流操作：
  1. 检查软件是否已打开，未打开则启动（由 session 级 app_manager 负责）
  2. 新建项目
  3. 设置默认模板图片
  4. 新建 workflow
  5. 重命名 workflow
  6. Filter 添加工具
  7. 保存 workflow
  8. 保存项目
  9. 另存为项目（Save Project As）
 10. 关闭项目
 11. 打开项目（步骤 2 创建的原始项目，非另存为副本）
 12. 打开 workflow（步骤 5 重命名并保存的 workflow，非新建 Untitled）
 13. 保存 workflow
 14. 关闭 workflow
 15. 再次关闭项目
"""
import os
import time

import pytest

from tests import flow_steps as fs
from utils.logger import logger

TOTAL_STEPS = 15
FILTER_TOOL_KEY = "d3_circle_detection"


class TestFullWorkflowRound:
    """单轮完整业务流程测试（需 AIRVision 已启动或可自动连接）。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_full_workflow_round(self):
        """按顺序执行 15 步完整项目与工作流流程。"""
        fs.run_step(
            "检查 AIRVision 是否已打开",
            "assert_app_ready",
            lambda: fs.assert_app_ready(self.page),
            step=1,
            total=TOTAL_STEPS,
            pause=0.3,
        )

        self.page.prepare_clean_state()

        project_name, project_file = fs.step_new_project(
            self.page, step=2, total=TOTAL_STEPS
        )
        fs.step_set_default_template(
            self.page, step=3, total=TOTAL_STEPS
        )
        initial_name = fs.step_new_workflow(
            self.page, step=4, total=TOTAL_STEPS
        )
        workflow_name = fs.step_rename_workflow(
            self.page, step=5, total=TOTAL_STEPS
        )
        fs.step_add_filter_tool(
            self.page,
            FILTER_TOOL_KEY,
            step=6,
            total=TOTAL_STEPS,
        )
        json_path = fs.step_save_workflow(
            self.page, workflow_name, step=7, total=TOTAL_STEPS
        )
        fs.step_save_project(
            self.page, project_file, step=8, total=TOTAL_STEPS
        )
        save_as_name, _ = fs.step_save_project_as(
            self.page, step=9, total=TOTAL_STEPS
        )
        fs.step_close_project(
            self.page, step=10, total=TOTAL_STEPS
        )
        fs.step_open_project(
            self.page,
            path=self.page.PROJECT_PATH,
            filename=f"{project_name}.airvision",
            title=f"打开项目 (原始 {project_name!r}，非另存为 {save_as_name!r})",
            step=11,
            total=TOTAL_STEPS,
            pause=1.0,
        )
        fs.step_open_workflow(
            self.page,
            filename=f"{workflow_name}.json",
            expected_name=workflow_name,
            title=f"打开 workflow ({workflow_name}.json，非 {initial_name})",
            step=12,
            total=TOTAL_STEPS,
        )
        assert self.page.get_active_workflow_name() != initial_name
        fs.step_save_workflow(
            self.page,
            workflow_name,
            step=13,
            total=TOTAL_STEPS,
            pause=0.5,
        )
        assert os.path.isfile(json_path), f"工作流文件应仍存在: {json_path}"
        fs.step_close_workflow(
            self.page,
            workflow_name=workflow_name,
            step=14,
            total=TOTAL_STEPS,
            after_task=True,
        )
        fs.step_close_project(
            self.page, step=15, total=TOTAL_STEPS, pause=0.5
        )
