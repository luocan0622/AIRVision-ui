"""Communication 设备管理测试。"""
import os
import time

import pytest

from pages.mixins.communication import COMMUNICATION_DEVICE_TYPES


TCP_CLIENT_HOST = os.getenv("AIRVISION_TCP_CLIENT_HOST", "127.0.0.1")
TCP_CLIENT_PORT = int(os.getenv("AIRVISION_TCP_CLIENT_PORT", "8081"))
TCP_CLIENT_PAYLOAD = os.getenv("AIRVISION_TCP_CLIENT_PAYLOAD", "AIRVISION_SIGNAL_001")


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

    @pytest.mark.regression
    def test_tcp_client_config_connect_test_send_receive(self):
        """TCP Client: configure IP/port, apply, connect, test, send, receive."""
        host = TCP_CLIENT_HOST
        port = TCP_CLIENT_PORT
        payload = TCP_CLIENT_PAYLOAD

        self.page.close_connection_failed_dialog()
        self.page.open_communication()
        name = self.page.add_communication_device(device_type="TCP Client")
        self.page.select_communication_device(name)
        self.page.configure_communication_device(
            ip_address=host,
            port=port,
        )
        self.page.connect_communication_device()
        self.page.open_communication_debug()
        self.page.send_communication_debug_data(payload)

        received = self.page.read_communication_receive_data()
        assert isinstance(received, str)

        self.page.close_communication_debug()
        self.page.close_communication()

    @pytest.mark.regression
    def test_configure_event_for_tcp_client_device(self):
        """Communication Event: name, source, device, delimiter, rule, value."""
        self.page.close_event_management_dialog()
        self.page.open_communication()
        self.page.open_communication_device_tab()
        device_name = self.page.add_communication_device(device_type="TCP Client")

        event_name = f"Auto Event {int(time.time())}"
        self.page.configure_communication_event(
            event_name=event_name,
            event_source="IO",
            device_name=device_name,
            delimiter=",",
            value_type="String",
            match_rule="Equal",
            condition_value="AIRVISION_SIGNAL_001",
        )

        self.page.close_communication()
