"""Communication 设备管理测试。"""
import time

import pytest

from pages.mixins.communication import COMMUNICATION_DEVICE_TYPES


class TestCommunication:
    """工具栏 Communication → 添加设备。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    @pytest.mark.regression
    def test_open_communication_window(self):
        """点击工具栏 Communication 按钮，管理窗口应出现。"""
        assert self.page.is_toolbar_button_visible("Communication")
        self.page.open_communication()
        assert self.page.is_communication_window_open()
        self.page.close_communication()

    @pytest.mark.regression
    def test_add_device_with_type_and_number_name(self):
        """Add device：设备名 = Device Type + 数字（如 TCP Client 2）。"""
        self.page.open_communication()
        device_type = "TCP Client"
        expected_name = self.page.next_communication_device_name(device_type)

        name = self.page.add_communication_device(device_type=device_type)
        assert name == expected_name
        assert name.lower().startswith(device_type.lower())
        assert name.split()[-1].isdigit()

        devices = self.page.list_communication_devices()
        assert any(d.strip().lower() == name.lower() for d in devices)
        self.page.close_communication()
        time.sleep(0.3)

    @pytest.mark.regression
    @pytest.mark.parametrize("device_type", COMMUNICATION_DEVICE_TYPES[:3])
    def test_add_device_by_type(self, device_type: str):
        """各 Device Type 均可添加，名称遵循「类型 + 序号」。"""
        self.page.open_communication()
        name = self.page.add_communication_device(device_type=device_type)
        assert device_type.lower() in name.lower()
        self.page.close_communication()
