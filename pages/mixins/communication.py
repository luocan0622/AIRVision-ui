"""Communication 设备管理窗口（工具栏 Communication 按钮打开）。"""
from __future__ import annotations

import time

from pywinauto import Application
from pywinauto.findwindows import find_elements

from pages.dialogs import DialogTitle
from utils.logger import logger
from utils.naming import next_numbered_label

# Add Device 对话框 Device Type 下拉可选项（与界面一致）
COMMUNICATION_DEVICE_TYPES: tuple[str, ...] = (
    "TCP Client",
    "TCP Server",
    "Serial Device",
    "Modbus TCP",
    "Modbus RTU",
    "PLC Link",
)

_DEFAULT_DEVICE_TYPE = COMMUNICATION_DEVICE_TYPES[0]


class CommunicationMixin:
    """Communication 管理：打开窗口、添加设备等。"""

    BTN_ADD_DEVICE = {"title": "Add device", "control_type": "Button"}
    BTN_OK = {"title": "OK", "control_type": "Button"}

    def is_communication_window_open(self, timeout: float = 1.0) -> bool:
        try:
            self._get_communication_window(timeout=timeout)
            return True
        except TimeoutError:
            return False

    def open_communication(self, timeout: int = 10):
        """点击工具栏 Communication 按钮并等待管理窗口出现。"""
        if self.is_communication_window_open(timeout=0.5):
            logger.info("Communication 窗口已打开，跳过点击工具栏")
        else:
            logger.info("打开 Communication 管理界面")
            self.click_communication()
            time.sleep(0.5)
        win = self._get_communication_window(timeout=timeout)
        self._activate_dialog(win)
        return win

    def list_communication_devices(self) -> list[str]:
        """读取 Device list 中已有设备名称。"""
        comm_win = self._get_communication_window(timeout=5)
        names: list[str] = []
        seen: set[str] = set()

        for elem in comm_win.descendants(control_type="ListItem"):
            text = (elem.window_text() or "").strip()
            if text and text not in seen:
                seen.add(text)
                names.append(text)

        if not names:
            for elem in comm_win.descendants(class_name="QListWidget"):
                try:
                    for child in elem.descendants():
                        text = (child.window_text() or "").strip()
                        if text and text not in seen:
                            seen.add(text)
                            names.append(text)
                except Exception:
                    continue

        logger.debug(f"Communication 设备列表: {names}")
        return names

    def add_communication_device(
        self,
        *,
        device_type: str = _DEFAULT_DEVICE_TYPE,
        device_name: str | None = None,
        timeout: int = 10,
    ) -> str:
        """添加通信设备：Add device → 设置类型与名称（类型+数字）→ OK。

        Args:
            device_type: Device Type 下拉选项，默认 ``TCP Client``。
            device_name: 显式设备名；默认按已有列表自动生成 ``{device_type} N``。

        Returns:
            最终写入的设备名称。
        """
        if device_type not in COMMUNICATION_DEVICE_TYPES:
            raise ValueError(
                f"未知设备类型: {device_type!r}，可选: {list(COMMUNICATION_DEVICE_TYPES)}"
            )

        comm_win = self.open_communication(timeout=timeout)
        existing = self.list_communication_devices()
        name = device_name or next_numbered_label(device_type, existing)

        logger.info(
            f"添加 Communication 设备: type={device_type!r}, name={name!r}"
        )
        self._click_communication_button(comm_win, "Add device")
        time.sleep(0.4)

        add_dlg = self._get_add_device_dialog(timeout=timeout)
        self._activate_dialog(add_dlg)
        self._select_communication_device_type(add_dlg, device_type)
        self._set_communication_device_name(add_dlg, name)
        self._click_communication_button(add_dlg, "OK")
        time.sleep(0.5)

        updated = self.list_communication_devices()
        assert any(
            n.strip().lower() == name.strip().lower() for n in updated
        ), f"设备列表中应出现 {name!r}，当前: {updated}"
        logger.info(f"Communication 设备已添加: {name!r}")
        return name

    def close_communication(self) -> None:
        """关闭 Communication 管理窗口。"""
        try:
            win = self._get_communication_window(timeout=1)
            win.close()
            time.sleep(0.3)
        except TimeoutError:
            logger.debug("Communication 窗口未打开，无需关闭")

    def _get_communication_window(self, timeout: float = 10):
        return self.get_window_by_title(
            DialogTitle.COMMUNICATION,
            timeout=int(timeout),
            alt_titles=DialogTitle.COMMUNICATION_TITLES,
        )

    def _get_add_device_dialog(self, timeout: int = 10):
        return self.get_window_by_title(
            DialogTitle.ADD_DEVICE,
            timeout=timeout,
            alt_titles=DialogTitle.ADD_DEVICE_TITLES,
        )

    def _click_communication_button(self, parent, title: str) -> None:
        target = title.strip().lower()
        for elem in parent.descendants(class_name="QPushButton"):
            try:
                if not elem.is_visible():
                    continue
                text = (elem.window_text() or "").strip().lower()
                if text == target:
                    logger.info(f"点击按钮: {title!r}")
                    self.mouse_click(elem)
                    return
            except Exception:
                continue

        btn = parent.child_window(title=title, control_type="Button")
        btn.wait("exists visible", timeout=3)
        logger.info(f"点击按钮(child_window): {title!r}")
        self.mouse_click(btn)

    def _set_communication_device_name(self, dlg, name: str) -> None:
        edit = self._find_device_name_edit(dlg)
        logger.info(f"设置 Device Name: {name!r}")
        self.mouse_type(edit, name)

    def _find_device_name_edit(self, dlg):
        edits = [
            e
            for e in dlg.descendants(class_name="QLineEdit")
            if e.is_visible()
        ]
        if edits:
            return edits[0]

        edit = dlg.child_window(auto_id="Device Name:", control_type="Edit")
        if edit.exists(timeout=0):
            return edit

        raise RuntimeError("Add Device 对话框中未找到 Device Name 输入框")

    def _select_communication_device_type(self, dlg, device_type: str) -> None:
        combos = [
            c
            for c in dlg.descendants(class_name="QComboBox")
            if c.is_visible()
        ]
        if not combos:
            raise RuntimeError("Add Device 对话框中未找到 Device Type 下拉框")

        combo = combos[0]
        current = (combo.window_text() or "").strip()
        if current.lower() == device_type.lower():
            logger.info(f"Device Type 已是 {device_type!r}，跳过选择")
            return

        logger.info(f"选择 Device Type: {device_type!r}")
        self.mouse_click(combo)
        time.sleep(0.35)
        if self._pick_combo_list_item(device_type):
            time.sleep(0.2)
            return

        # 键盘兜底：首项连按 Down 选中
        options = list(COMMUNICATION_DEVICE_TYPES)
        try:
            index = options.index(device_type)
        except ValueError:
            index = 0
        self.mouse_click(combo)
        time.sleep(0.2)
        for _ in range(index):
            self.mouse_press_key("down")
            time.sleep(0.08)
        self.mouse_press_key("enter")
        time.sleep(0.2)

    def _pick_combo_list_item(self, text: str) -> bool:
        target = text.strip().lower()
        pid = self.app.process

        for top_level_only in (True, False):
            try:
                for info in find_elements(
                    backend="uia",
                    process=pid,
                    top_level_only=top_level_only,
                ):
                    try:
                        app = Application(backend="uia").connect(handle=info.handle)
                        popup = app.window(handle=info.handle)
                        for elem in popup.descendants():
                            try:
                                if not elem.is_visible():
                                    continue
                                label = (elem.window_text() or "").strip()
                                if label.lower() != target:
                                    continue
                                cls = (elem.class_name() or "").lower()
                                if cls in (
                                    "qlistview",
                                    "qmenu",
                                ) or elem.element_info.control_type in (
                                    "ListItem",
                                    "MenuItem",
                                ):
                                    logger.info(f"下拉选中: {label!r}")
                                    self.mouse_click(elem)
                                    return True
                            except Exception:
                                continue
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"枚举下拉列表失败: {e}")

        return False

    def next_communication_device_name(
        self,
        device_type: str = _DEFAULT_DEVICE_TYPE,
    ) -> str:
        """根据当前设备列表生成下一个 ``{device_type} N`` 名称。"""
        existing = self.list_communication_devices() if self.is_communication_window_open() else []
        return next_numbered_label(device_type, existing)
