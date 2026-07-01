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
   # "Modbus TCP",
    #"Modbus RTU",
    #"PLC Link",
)

_DEFAULT_DEVICE_TYPE = COMMUNICATION_DEVICE_TYPES[0]


def _normalize_communication_text(text: str) -> str:
    return "".join(text.split()).lower()


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
        expected_name = _normalize_communication_text(name)
        assert any(
            _normalize_communication_text(n) == expected_name for n in updated
        ), f"设备列表中应出现 {name!r}，当前: {updated}"
        logger.info(f"Communication 设备已添加: {name!r}")
        return name

    def select_communication_device(self, device_name: str) -> None:
        comm_win = self.open_communication()
        target = _normalize_communication_text(device_name)

        for elem in comm_win.descendants():
            try:
                if not elem.is_visible():
                    continue
                text = (elem.window_text() or "").strip()
                if _normalize_communication_text(text) == target:
                    logger.info(f"Select Communication device: {device_name!r}")
                    self.mouse_click(elem)
                    time.sleep(0.3)
                    return
            except Exception:
                continue

        raise RuntimeError(f"Communication device not found: {device_name!r}")

    def open_communication_event_tab(self):
        comm_win = self.open_communication()
        self._click_communication_tab(comm_win, "Event")
        return comm_win

    def open_communication_device_tab(self):
        comm_win = self.open_communication()
        self._click_communication_tab(comm_win, "Device")
        self.close_event_management_dialog()
        if not self._has_visible_text(comm_win, "Add device"):
            self._click_communication_tab(comm_win, "Device")
            self.close_event_management_dialog()
        return comm_win

    def configure_communication_event(
        self,
        *,
        event_name: str,
        event_source: str = "IO",
        device_name: str | None = None,
        delimiter: str = ",",
        value_type: str = "String",
        match_rule: str = "Equal",
        condition_value: str = "AIRVISION_SIGNAL_001",
        save: bool = True,
    ) -> None:
        """Configure Communication Event tab."""
        comm_win = self.open_communication_event_tab()
        self._click_communication_button(comm_win, "New")

        self._set_labeled_edit(comm_win, "Event name", event_name)
        self._select_labeled_combo(comm_win, "Event source", event_source)

        if device_name:
            self._select_labeled_combo(comm_win, "Device", device_name, normalize=True)

        self._set_labeled_edit(comm_win, "Delimiter", delimiter)
        self._select_condition_combo(comm_win, 0, value_type)
        self._select_condition_combo(comm_win, 1, match_rule)
        self._set_condition_value(comm_win, condition_value)

        if save:
            self._click_communication_button(comm_win, "Save")
            time.sleep(0.5)

    def close_communication(self) -> None:
        """关闭 Communication 管理窗口。"""
        try:
            win = self._get_communication_window(timeout=1)
            win.close()
            time.sleep(0.3)
        except TimeoutError:
            logger.debug("Communication 窗口未打开，无需关闭")

    def close_event_management_dialog(self) -> None:
        try:
            dlg = self.get_window_by_title("Event management", timeout=1)
        except TimeoutError:
            return

        try:
            self._click_communication_button(dlg, "OK")
        except Exception:
            dlg.close()
        time.sleep(0.3)

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

    def _click_communication_tab(self, parent, title: str) -> None:
        target = title.strip().lower()
        for elem in parent.descendants():
            try:
                if not elem.is_visible():
                    continue
                text = (elem.window_text() or "").strip().lower()
                if text != target:
                    continue
                ctrl_type = elem.element_info.control_type or ""
                if ctrl_type == "TabItem":
                    logger.info(f"Click Communication tab: {title!r}")
                    self.mouse_click(elem)
                    time.sleep(0.3)
                    return
            except Exception:
                continue

        tab = parent.child_window(title=title, control_type="TabItem")
        tab.wait("exists visible", timeout=3)
        self.mouse_click(tab)
        time.sleep(0.3)

    def _has_visible_text(self, parent, text: str) -> bool:
        try:
            self._find_visible_text(parent, text)
            return True
        except RuntimeError:
            return False

    def _find_visible_text(self, parent, text: str):
        target = text.strip().lower()
        for elem in parent.descendants():
            try:
                if not elem.is_visible():
                    continue
                label = (elem.window_text() or "").strip().lower()
                if label == target:
                    return elem
            except Exception:
                continue
        raise RuntimeError(f"Visible text not found: {text!r}")

    def _find_labeled_controls(self, parent, label: str, class_name: str) -> list:
        label_elem = self._find_visible_text(parent, label)
        label_rect = label_elem.rectangle()
        label_y = label_rect.top + label_rect.height() // 2
        controls = []

        for elem in parent.descendants(class_name=class_name):
            try:
                if not elem.is_visible():
                    continue
                rect = elem.rectangle()
                elem_y = rect.top + rect.height() // 2
                if rect.left < label_rect.right - 10:
                    continue
                if abs(elem_y - label_y) > 28:
                    continue
                controls.append((abs(elem_y - label_y), rect.left, elem))
            except Exception:
                continue

        controls.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in controls]

    def _find_labeled_control(self, parent, label: str, class_name: str):
        controls = self._find_labeled_controls(parent, label, class_name)
        if controls:
            return controls[0]
        raise RuntimeError(f"{class_name} for label {label!r} not found")

    def _set_labeled_edit(self, parent, label: str, value: str) -> None:
        edit = self._find_labeled_control(parent, label, "QLineEdit")
        logger.info(f"Set {label}: {value!r}")
        self.mouse_type(edit, value)

    def _select_labeled_combo(
        self,
        parent,
        label: str,
        value: str,
        *,
        normalize: bool = False,
    ) -> None:
        combo = self._find_labeled_control(parent, label, "QComboBox")
        self._select_combo_value(combo, value, normalize=normalize)

    def _select_combo_value(self, combo, value: str, *, normalize: bool = False) -> None:
        current = (combo.window_text() or "").strip()
        if self._combo_text_matches(current, value, normalize):
            return

        logger.info(f"Select combo value: {value!r}")
        self.mouse_click(combo)
        time.sleep(0.25)
        if self._pick_combo_list_item(value, normalize=normalize):
            time.sleep(0.2)
            return
        raise RuntimeError(f"Combo option not found: {value!r}")

    def _combo_text_matches(self, actual: str, expected: str, normalize: bool) -> bool:
        if normalize:
            return _normalize_communication_text(actual) == _normalize_communication_text(expected)
        return actual.strip().lower() == expected.strip().lower()

    def _condition_row_controls(self, parent, class_name: str) -> list:
        controls = []
        for elem in parent.descendants(class_name=class_name):
            try:
                if not elem.is_visible():
                    continue
                rect = elem.rectangle()
                controls.append((rect.top, rect.left, elem))
            except Exception:
                continue
        controls.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in controls]

    def _select_condition_combo(self, parent, index: int, value: str) -> None:
        combos = self._condition_row_controls(parent, "QComboBox")
        if len(combos) <= index:
            raise RuntimeError(f"Condition combo index {index} not found")
        self._select_combo_value(combos[index], value)

    def _set_condition_value(self, parent, value: str) -> None:
        edits = self._condition_row_controls(parent, "QLineEdit")
        editable = []
        for edit in edits:
            text = (edit.window_text() or "").strip()
            if text in {"", "Condition value"}:
                editable.append(edit)
        if not editable:
            raise RuntimeError("Condition value edit not found")
        logger.info(f"Set condition value: {value!r}")
        self.mouse_type(editable[-1], value)

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

    def _pick_combo_list_item(self, text: str, *, normalize: bool = False) -> bool:
        target = (
            _normalize_communication_text(text)
            if normalize
            else text.strip().lower()
        )
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
                                candidate = (
                                    _normalize_communication_text(label)
                                    if normalize
                                    else label.lower()
                                )
                                if candidate != target:
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
