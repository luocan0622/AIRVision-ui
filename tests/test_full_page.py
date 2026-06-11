"""
AIRVision 主窗口流程化测试。

与 test_main_page.py 中单步测试不同，本文件按业务顺序串联多个操作，
模拟用户一次完整的 Projects 菜单使用流程。

流程概览（Projects 全流程）：
  1. 清理环境
  2. 新建项目
  3. 设置默认模板图片
  4. 保存项目
  5. 关闭项目
  6. 重新打开项目
  7. 再次关闭项目

完整「项目 + 工作流」15 步流程见 test_full_workflow.py。
"""
import time

import pytest

from tests import flow_steps as fs
from utils.logger import logger

PROJECTS_FLOW_STEPS = 6
WORKFLOW_FLOW_STEPS = 4


class TestProjectsFullFlow:
    """Projects 菜单完整业务流程（单条用例串联多步）。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_projects_full_flow(self):
        """Projects 菜单：新建 → 模板 → 保存 → 关闭 → 打开 → 关闭。"""
        self.page.prepare_clean_state()

        project_name, project_file = fs.step_new_project(
            self.page, step=1, total=PROJECTS_FLOW_STEPS
        )
        fs.step_set_default_template(
            self.page, step=2, total=PROJECTS_FLOW_STEPS
        )
        fs.step_save_project(
            self.page, project_file, step=3, total=PROJECTS_FLOW_STEPS
        )
        fs.step_close_project(
            self.page, step=4, total=PROJECTS_FLOW_STEPS
        )
        fs.step_open_project(
            self.page,
            filename=f"{project_name}.airvision",
            step=5,
            total=PROJECTS_FLOW_STEPS,
        )
        fs.step_close_project(
            self.page, step=6, total=PROJECTS_FLOW_STEPS, pause=0.5
        )


class TestWorkflowFullFlow:
    """Workflows 菜单完整业务流程（需先有打开的项目）。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_workflow_full_flow(self):
        """Workflows：新建 → 重命名 → 保存 → 关闭。"""
        self.page.prepare_clean_state()

        logger.info("前置: 新建并打开项目")
        fs.step_new_project(self.page)
        time.sleep(0.5)

        fs.step_new_workflow(
            self.page, step=1, total=WORKFLOW_FLOW_STEPS
        )
        workflow_name = fs.step_rename_workflow(
            self.page, step=2, total=WORKFLOW_FLOW_STEPS
        )
        fs.step_save_workflow(
            self.page, workflow_name, step=3, total=WORKFLOW_FLOW_STEPS
        )
        fs.step_close_workflow(
            self.page, step=4, total=WORKFLOW_FLOW_STEPS
        )

        logger.info("清理: 关闭项目")
        self.page.close_project()
