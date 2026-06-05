"""
AIRVision 单轮全流程端到端测试。

按固定顺序模拟用户完成一次完整的项目与工作流操作：
  1. 新建项目
  2. 设置默认模板图片
  3. 新建 workflow
  4. 重命名 workflow
  5. 保存 workflow
  6. 保存项目
  7. 关闭项目
  8. 打开项目
  9. 打开 workflow
 10. 再次关闭项目
"""
import os
import re
import time

import pytest
from pywinauto.keyboard import SendKeys

from pages.main_page import MainPage
from utils.logger import logger


class TestFullWorkflowRound:
    """单轮完整业务流程测试（需 AIRVision 已启动）。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    @pytest.mark.slow
    @pytest.mark.regression
    def test_full_workflow_round(self):
        """按顺序执行 10 步完整项目与工作流流程。"""
        project_name = None
        project_file = None
        workflow_name = None

        # 前置：清理残留对话框与已打开项目
        self.page.prepare_clean_state()

        # 1. 新建项目（Projects → New Project，非 Workflows）
        logger.info("步骤 1/10: 新建项目")
        project_name = self.page.new_project()
        assert re.match(r"^test_\d+$", project_name, re.I)
        project_file = os.path.join(self.page.PROJECT_PATH, f"{project_name}.airvision")
        assert os.path.isdir(self.page.PROJECT_PATH)
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"
        time.sleep(0.5)

        # 2. 设置默认模板图片
        logger.info("步骤 2/10: 设置默认模板图片")
        self.page.set_default_template_image()
        time.sleep(1)

        # 3. 新建 workflow
        logger.info("步骤 3/10: 新建 workflow")
        initial_name = self.page.new_workflow()
        assert re.match(r"^Untitled-\d+$", initial_name, re.I)
        time.sleep(0.5)

        # 4. 重命名 workflow（test_数字）
        logger.info("步骤 4/10: 重命名 workflow")
        workflow_name = self.page.rename_workflow()
        assert re.match(r"^test_\d+$", workflow_name, re.I)
        assert self.page.get_active_workflow_name() == workflow_name

        # 5. 保存 workflow
        logger.info("步骤 5/10: 保存 workflow")
        self.page.save_workflow(workflow_name)
        time.sleep(1)
        json_path = self.page.get_workflow_json_path(workflow_name)
        assert os.path.isfile(json_path), f"工作流文件应存在: {json_path}"

        # 6. 保存项目
        logger.info("步骤 6/10: 保存项目")
        self.page.save_project()
        time.sleep(1)
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"

        # 7. 关闭项目
        logger.info("步骤 7/10: 关闭项目")
        self.page.close_project()
        time.sleep(1)

        # 8. 打开项目（打开步骤 1 创建的 test_数字 项目）
        logger.info("步骤 8/10: 打开项目")
        self.page.open_project(filename=f"{project_name}.airvision")
        time.sleep(1)

        # 9. 打开 workflow（打开步骤 5 保存的重命名文件）
        logger.info("步骤 9/10: 打开 workflow")
        opened_name = self.page.open_workflow(filename=f"{workflow_name}.json")
        assert opened_name == workflow_name
        assert self.page.get_active_workflow_name() == workflow_name
        time.sleep(0.5)

        # 10. 再次关闭项目
        logger.info("步骤 10/10: 再次关闭项目")
        self.page.close_project()
        time.sleep(0.5)
