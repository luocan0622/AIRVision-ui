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

完整「项目 + 工作流」10 步流程见 test_full_workflow.py。
"""
import os
import re
import time

import pytest
from pywinauto.keyboard import SendKeys

from pages.main_page import MainPage
from utils.logger import logger


class TestProjectsFullFlow:
    """Projects 菜单完整业务流程（单条用例串联多步）。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_projects_full_flow(self):
        """Projects 菜单：新建 → 模板 → 保存 → 关闭 → 打开 → 关闭。"""
        self.page.prepare_clean_state()

        # 1. 新建项目
        logger.info("步骤 1/6: 新建项目")
        project_name = self.page.new_project()
        assert re.match(r"^test_\d+$", project_name, re.I)
        project_file = os.path.join(
            self.page.PROJECT_PATH, f"{project_name}.airvision"
        )
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"
        time.sleep(0.5)

        # 2. 设置默认模板图片（需已打开项目）
        logger.info("步骤 2/6: 设置默认模板图片")
        self.page.set_default_template_image()
        time.sleep(1)

        # 3. 保存项目
        logger.info("步骤 3/6: 保存项目")
        self.page.save_project()
        time.sleep(0.5)
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"

        # 4. 关闭项目
        logger.info("步骤 4/6: 关闭项目")
        self.page.close_project()
        time.sleep(1)

        # 5. 重新打开项目
        logger.info("步骤 5/6: 打开项目")
        self.page.open_project(filename=f"{project_name}.airvision")
        time.sleep(1)

        # 6. 再次关闭项目
        logger.info("步骤 6/6: 再次关闭项目")
        self.page.close_project()
        time.sleep(0.5)


class TestWorkflowFullFlow:
    """Workflows 菜单完整业务流程（需先有打开的项目）。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.integration
    def test_workflow_full_flow(self):
        """Workflows：新建 → 重命名 → 保存 → 关闭。"""
        self.page.prepare_clean_state()

        logger.info("前置: 新建并打开项目")
        project_name = self.page.new_project()
        time.sleep(0.5)

        logger.info("步骤 1/4: 新建 workflow")
        initial_name = self.page.new_workflow()
        assert re.match(r"^Untitled-\d+$", initial_name, re.I)

        logger.info("步骤 2/4: 重命名 workflow")
        workflow_name = self.page.rename_workflow()
        assert re.match(r"^test_\d+$", workflow_name, re.I)
        assert self.page.get_active_workflow_name() == workflow_name

        logger.info("步骤 3/4: 保存 workflow")
        self.page.save_workflow(workflow_name)
        json_path = self.page.get_workflow_json_path(workflow_name)
        assert os.path.isfile(json_path), f"工作流文件应存在: {json_path}"

        logger.info("步骤 4/4: 关闭 workflow")
        self.page.close_workflow()
        time.sleep(0.5)

        logger.info("清理: 关闭项目")
        self.page.close_project()
