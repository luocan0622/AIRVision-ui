"""
AIRVision 应用基础测试模块。

用于验证应用基本功能和控件可见性。
"""
import pytest
from pages.base_page import BasePage


class TestAirVisionBasic:
    """AIRVision 应用基础冒烟测试。"""

    @pytest.fixture(autouse=True)
    def setup(self, app):
        """为每个测试初始化页面对象。"""
        self.page = BasePage(app)

    @pytest.mark.smoke
    def test_window_exists(self, app):
        """验证应用窗口存在且可见。"""
        window = app.top_window()
        assert window.exists(), "应用窗口应该存在"
        assert window.is_visible(), "应用窗口应该可见"

    @pytest.mark.smoke
    def test_main_window_auto_id(self, app):
        """验证主窗口 AutomationId 正确。"""
        window = app.top_window()
        auto_id = window.element_info.automation_id
        assert auto_id == "MainWindow", f"期望 auto_id 为 'MainWindow'，实际为 '{auto_id}'"


class TestControlInspection:
    """控件检查测试（用于开发调试）。"""

    @pytest.fixture(autouse=True)
    def setup(self, page):
        self.page = page

    @pytest.mark.skip(reason="仅用于开发调试，手动运行")
    def test_print_controls(self, app):
        """打印控件树，供开发参考。
        
        运行方式：pytest tests/test_sample.py::TestControlInspection::test_print_controls -s
        """
        window = app.top_window()
        print("\n" + "=" * 80)
        print("AIRVision 控件树 (深度=3)")
        print("=" * 80)
        window.print_control_identifiers(depth=3)
        print("=" * 80)

