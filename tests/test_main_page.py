"""
AIRVision 主窗口功能测试。

覆盖：菜单栏按钮、下拉菜单、工具栏、标题信息。
"""
import time
import pytest
from pywinauto.keyboard import SendKeys
from pages.main_page import MainPage


class TestMainPageMenuBar:
    """菜单栏按钮基础测试。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """初始化主页面对象。"""
        self.page = MainPage(app)

    @pytest.mark.smoke
    def test_title_text(self):
        """验证标题栏显示 'AIRVision'。"""
        title = self.page.get_title_text()
        assert "AIRVision" in title, f"标题应包含 'AIRVision'，实际为 '{title}'"

    @pytest.mark.smoke
    def test_menu_buttons_visible(self):
        """验证所有菜单栏按钮可见。"""
        assert self.page.is_visible(**self.page.BTN_PROJECTS), "Projects 按钮不可见"
        assert self.page.is_visible(**self.page.BTN_WORKFLOWS), "Workflows 按钮不可见"
        assert self.page.is_visible(**self.page.BTN_SETTINGS), "Settings 按钮不可见"
        assert self.page.is_visible(**self.page.BTN_TOOLS), "Tools 按钮不可见"
        assert self.page.is_visible(**self.page.BTN_HELP), "Help 按钮不可见"

    @pytest.mark.smoke
    def test_toolbar_buttons_visible(self):
        """验证工具栏 15 个按钮均可见（Name 为空，按 auto_id / 序号定位）。"""
        assert self.page.are_all_toolbar_buttons_visible(), (
            "部分工具栏按钮不可见，期望 15 个 QToolButton"
        )

    @pytest.mark.regression
    def test_click_camara(self):
        """模拟用户点击工具栏相机（camara）按钮。"""
        assert self.page.is_toolbar_button_visible("camara"), "相机按钮不可见"
        self.page.click_camara()
        time.sleep(0.5)

    @pytest.mark.regression
    def test_click_contrllor(self):
        """模拟用户点击工具栏控制器（contrllor）按钮。"""
        assert self.page.is_toolbar_button_visible("contrllor"), "控制器按钮不可见"
        self.page.click_contrllor()
        time.sleep(0.5)

    @pytest.mark.regression
    def test_click_global_variables(self):
        """模拟用户点击工具栏全局变量（Global_Variables）按钮。"""
        assert self.page.is_toolbar_button_visible("Global_Variables"), "全局变量按钮不可见"
        self.page.click_global_variables()
        time.sleep(0.5)

    @pytest.mark.regression
    def test_click_communication(self):
        """模拟用户点击工具栏通信（Communication）按钮。"""
        assert self.page.is_toolbar_button_visible("Communication"), "通信按钮不可见"
        self.page.click_communication()
        time.sleep(0.5)

    @pytest.mark.regression
    def test_click_global_trigger(self):
        """模拟用户点击工具栏全局触发（Global_Trigger）按钮。"""
        assert self.page.is_toolbar_button_visible("Global_Trigger"), "全局触发按钮不可见"
        self.page.click_global_trigger()
        time.sleep(0.5)


class TestLanguageSwitch:
    """语言切换测试。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    @pytest.mark.smoke
    def test_language_button_visible(self):
        """验证语言切换按钮可见。"""
        assert self.page.is_visible(**self.page.BTN_LANG), "语言切换按钮不可见"

    @pytest.mark.regression
    def test_switch_to_chinese(self):
        """模拟用户点击切换到中文。"""
        self.page.switch_language("CN")

    @pytest.mark.regression
    def test_switch_to_english(self):
        """模拟用户点击切换到英文。"""
        self.page.switch_language("EN")

    @pytest.mark.regression
    def test_toggle_language(self):
        """模拟用户在中英文之间切换（不依赖当前语言状态）。"""
        self.page.toggle_language()



class TestProjectsMenu:
    """Projects 下拉菜单测试。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """初始化主页面对象，测试完成后关闭任意弹出菜单。"""
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    @pytest.mark.regression
    def test_new_project(self):
        """验证点击 Projects → New Project 触发新建项目。"""
        self.page.new_project()
        time.sleep(1)

    # @pytest.mark.regression
    # def test_open_project(self):
    #     """验证点击 Projects → Open Project 触发打开项目。"""
    #     self.page.open_project()
    #     time.sleep(1)

    # @pytest.mark.regression
    # def test_save_project(self):
    #     """验证点击 Projects → Save Project 触发保存项目。"""
    #     self.page.save_project()
    #     time.sleep(1)

    @pytest.mark.regression
    def test_set_default_template_image(self):
        """验证点击 Projects → Set Default Template Image 触发设置默认模板图片。"""
        self.page.set_default_template_image()
        time.sleep(1)


class TestWorkflowCanvasTools:
    """工作流画布：右键 Filter 添加工具。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.page = MainPage(app)
        yield
        SendKeys("{ESC}")
        time.sleep(0.3)

    def _prepare_workflow_canvas(self):
        self.page.mouse_press_key("esc")
        time.sleep(0.3)
        self.page.ensure_project_open()
        time.sleep(0.5)
        self.page.ensure_workflow_tab_open()
        time.sleep(0.5)

    def _add_tool_and_assert(self, tool_key: str, message: str):
        tool = self.page.add_workflow_tool(tool_key)
        assert tool.key == tool_key
        assert self.page.has_workflow_tool_node_for_key(tool_key, timeout=15), message
        time.sleep(0.5)

    @pytest.mark.regression
    def test_add_d3_circle_detection_tool(self):
        """新建「3D 圆检测」（菜单靠前，可直接点选）。"""
        self._prepare_workflow_canvas()
        self._add_tool_and_assert(
            "d3_circle_detection",
            "画布上应出现 3D 圆检测 节点（如 Circle3DDetectorTool3D-01）",
        )

    @pytest.mark.regression
    def test_add_mold_cup_path_detection_tool(self):
        """新建「模杯路径检测」（自定义算法，Filter 搜索 + 滚动）。"""
        self._prepare_workflow_canvas()
        self._add_tool_and_assert(
            "mold_cup_path_detection",
            "画布上应出现模杯路径检测节点",
        )
