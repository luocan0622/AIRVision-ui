"""Windows 文件对话框通用操作 Mixin。"""
import os
import time

import pyautogui
from pywinauto import Application
from pywinauto.keyboard import SendKeys as send_keys

from pages.dialogs import DialogTitle
from utils import ui_input
from utils.logger import logger


class FileDialogMixin:
    """文件/项目对话框处理：地址栏导航、文件名输入、确认与覆盖提示。

    依赖宿主类提供 ``self.app``（pywinauto Application 实例）。
    """

    # 文件名输入框 auto_id：Create New Project=1001，Open Project=1148
    _NEW_PROJECT_FILENAME_AUTO_ID = "1001"
    _OPEN_PROJECT_FILENAME_AUTO_ID = "1148"
    _FILENAME_EDIT_AUTO_IDS = (_NEW_PROJECT_FILENAME_AUTO_ID, _OPEN_PROJECT_FILENAME_AUTO_ID)
    _CONFIRM_BUTTON_TITLES = ("打开(O)", "打开", "保存(S)", "保存", "OK", "确定")
    _OVERWRITE_YES_TITLES = ("是(Y)", "是", "Yes", "&Yes", "Yes(Y)")
    _OVERWRITE_NO_TITLES = ("否(N)", "否", "No", "&No", "No(N)")
    _OVERWRITE_DIALOG_TITLES = ("Confirm Save As", "确认另存为")

    def get_window_by_title(
        self, title: str, timeout: int = 5, alt_titles: tuple = ()
    ):
        """通过窗口左上角标题等待并返回窗口。"""
        import win32gui

        titles = {title, *alt_titles}
        end = time.time() + timeout
        while time.time() < end:
            try:
                hwnds = []

                def _enum(hwnd, _lp):
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            text = win32gui.GetWindowText(hwnd)
                            if text in titles:
                                hwnds.append(hwnd)
                    except Exception:
                        pass
                    return True

                win32gui.EnumWindows(_enum, None)
                if hwnds:
                    target_hwnd = hwnds[0]
                    win_title = win32gui.GetWindowText(target_hwnd)
                    logger.info(
                        f"定位窗口: title={win_title!r}, "
                        f"class={win32gui.GetClassName(target_hwnd)!r}, handle={target_hwnd}"
                    )
                    dlg_app = Application(backend="uia").connect(handle=target_hwnd)
                    return dlg_app.window(handle=target_hwnd)
            except Exception:
                pass
            time.sleep(0.3)
        raise TimeoutError(f"未找到标题为 {titles!r} 的窗口")

    def get_new_project_dialog(self, timeout: int = 10):
        """定位 Create New Project / New Project 对话框。"""
        return self.get_window_by_title(
            DialogTitle.CREATE_NEW_PROJECT,
            timeout=timeout,
            alt_titles=DialogTitle.CREATE_NEW_PROJECT_TITLES[1:],
        )

    def get_file_dialog(self, timeout: int = 5, dialog_title: str = None):
        """兼容旧接口，请优先使用 get_window_by_title。"""
        if not dialog_title:
            raise ValueError("必须指定 dialog_title，参见 pages.dialogs.DialogTitle")
        return self.get_window_by_title(dialog_title, timeout=timeout)

    def _find_dialog_address_bar(self, dlg):
        """查找文件对话框地址栏（名称「地址」，auto_id 41477）。"""
        locators = (
            {"title": "地址", "control_type": "Edit", "auto_id": "41477"},
            {"title": "Address", "control_type": "Edit", "auto_id": "41477"},
            {"title": "地址", "control_type": "Edit"},
            {"title": "Address", "control_type": "Edit"},
            {"auto_id": "41477", "control_type": "Edit"},
            {"auto_id": "41477", "class_name": "Edit"},
        )
        for loc in locators:
            try:
                ctrl = dlg.child_window(**loc)
                if ctrl.exists(timeout=0):
                    logger.info(
                        f"地址栏(auto_id=41477): UIA loc={loc}, "
                        f"rect={ctrl.rectangle()}"
                    )
                    return ctrl
            except Exception:
                continue

        try:
            for elem in dlg.descendants():
                try:
                    if (elem.element_info.automation_id or "") != "41477":
                        continue
                    if getattr(elem.element_info, "control_type", "") != "Edit":
                        continue
                    if elem.is_visible():
                        logger.info(
                            f"地址栏(auto_id=41477): UIA scan, "
                            f"rect={elem.rectangle()}"
                        )
                        return elem
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"UIA 扫描地址栏 auto_id=41477 失败: {e}")

        try:
            hwnd = dlg.handle
            win32_dlg = Application(backend="win32").connect(
                handle=hwnd
            ).window(handle=hwnd)
            for loc in locators:
                try:
                    ctrl = win32_dlg.child_window(**loc)
                    if ctrl.exists(timeout=0):
                        logger.info(
                            f"地址栏(auto_id=41477): win32 loc={loc}, "
                            f"rect={ctrl.rectangle()}"
                        )
                        return ctrl
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"win32 查找地址栏 auto_id=41477 失败: {e}")

        logger.error("未找到地址栏(auto_id=41477, 名称=地址)")
        return None

    def _read_address_bar_value(self, address, *, allow_clipboard: bool = False) -> str:
        """读取地址栏当前路径（默认仅用 UIA，避免 Enter 后反复鼠标点击）。"""
        readers = [
            lambda: address.get_value(),
            lambda: address.window_text(),
        ]
        if allow_clipboard:
            readers.append(lambda: ui_input.read_edit_via_clipboard(address))

        for reader in readers:
            try:
                value = reader()
                if value and str(value).strip():
                    return str(value).strip()
            except Exception:
                continue
        return ""

    def _type_into_address_bar(self, dlg, address, path: str) -> bool:
        """地址栏：Alt+D 输入 → Enter 跳转（不再用鼠标点击地址栏）。"""
        normalized = os.path.normpath(path)
        before = self._read_address_bar_value(address) if address else ""
        logger.info(
            f"地址栏 Alt+D 输入: 当前={before!r}, 目标={normalized!r}"
        )

        ui_input.activate_dialog(dlg)
        self._address_via_alt_d_paste(normalized)
        logger.info("地址栏已输入，按 Enter 确认跳转")
        ui_input.confirm_address_bar()
        time.sleep(1.5)

        # Enter 后地址栏通常处于面包屑模式，UIA 读不到完整路径属正常；
        # 不再为校验而反复点击/Alt+D，避免干扰后续文件名输入。
        if address:
            after = self._read_address_bar_value(address)
            if after:
                logger.info(f"地址栏跳转后读数: {after!r}")

        logger.info(f"地址栏跳转完成: {normalized!r}")
        return True

    def _address_via_alt_d_paste(self, path: str):
        """Alt+D 聚焦地址栏 → 全选 → 粘贴路径（Windows 标准操作，无需鼠标）。"""
        ui_input.focus_file_dialog_address_bar()
        ui_input.select_all_and_paste(path)

    def _clear_and_type_address_path(self, dlg, path: str) -> bool:
        """Alt+D 聚焦地址栏 → 粘贴路径 → Enter 跳转。"""
        normalized = os.path.normpath(path)
        logger.info(f"Alt+D 聚焦地址栏，粘贴并 Enter 跳转: {normalized!r}")
        ui_input.activate_dialog(dlg)
        self._address_via_alt_d_paste(normalized)
        ui_input.confirm_address_bar()
        time.sleep(1.5)
        return True

    def dismiss_ok_or_wait(self, wait_if_absent: float = 1.0) -> bool:
        """任务结束后：若有 OK/确定 按钮则点击，否则等待后继续。"""
        ok_titles = ("OK", "确定")

        try:
            dlg = self.get_window_by_title(
                DialogTitle.PROJECT_CREATED_SUCCESS, timeout=0.5
            )
            btn = self._find_dialog_button(dlg, ok_titles)
            if btn is not None:
                logger.info("[Success] 点击 OK")
                ui_input.activate_dialog(dlg)
                ui_input.mouse_click(btn)
                time.sleep(0.3)
                return True
        except (TimeoutError, Exception):
            pass

        try:
            for w in self.app.windows():
                try:
                    if not w.is_visible():
                        continue
                    btn = self._find_dialog_button(w, ok_titles)
                    if btn is None or not btn.is_visible():
                        continue
                    title = w.window_text()
                    logger.info(f"[{title}] 点击 OK")
                    ui_input.activate_dialog(w)
                    ui_input.mouse_click(btn)
                    time.sleep(0.3)
                    return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"扫描 OK 按钮失败: {e}")

        logger.debug(f"未发现 OK 按钮，等待 {wait_if_absent}s 后继续")
        time.sleep(wait_if_absent)
        return False

    def _navigate_file_dialog_to_path(self, dlg, dialog_title: str, path: str):
        """在地址栏先清空再输入路径，回车跳转。"""
        normalized = os.path.normpath(path)
        logger.info(f"[{dialog_title}] 步骤1: 地址栏导航 -> {normalized}")
        ui_input.activate_dialog(dlg)

        address = self._find_dialog_address_bar(dlg)
        if not address:
            time.sleep(0.5)
            address = self._find_dialog_address_bar(dlg)

        ok = False
        if address:
            logger.info(f"[{dialog_title}] 定位地址栏: auto_id=41477, 名称=地址")
            ok = self._type_into_address_bar(dlg, address, normalized)
        else:
            logger.warning(
                f"[{dialog_title}] 未找到地址栏(auto_id=41477)，回退 Alt+D"
            )
            ok = self._clear_and_type_address_path(dlg, normalized)

        if not ok:
            raise RuntimeError(
                f"[{dialog_title}] 地址栏跳转失败: {normalized!r}"
            )

        logger.info(f"[{dialog_title}] 步骤1 完成: 已跳转到 {normalized}")

    def navigate_file_dialog(self, path: str, dialog_title: str, timeout: int = 5):
        """在文件对话框地址栏输入路径并跳转。"""
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        self._navigate_file_dialog_to_path(dlg, dialog_title, path)

    def handle_file_dialog(
        self,
        dialog_title: str,
        path: str = None,
        filename: str = None,
        confirm: bool = True,
        timeout: int = 5,
    ):
        """统一处理文件对话框：定位 → 导航目录 → 填文件名 → 确认。"""
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)

        if path:
            self._navigate_file_dialog_to_path(dlg, dialog_title, path)

        if filename:
            self._set_filename_in_dialog(dlg, dialog_title, filename)

        if confirm:
            self._confirm_dialog(dlg, dialog_title)

    def _find_filename_edit_by_auto_id(self, dlg, auto_id: str):
        """定位文件名 Edit（auto_id 1001/1148）。"""
        edits = []
        combos = []

        try:
            for elem in dlg.descendants():
                try:
                    if (elem.element_info.automation_id or "") != auto_id:
                        continue
                    control_type = getattr(elem.element_info, "control_type", "")
                    if control_type == "Edit":
                        edits.append(elem)
                    elif control_type == "ComboBox":
                        combos.append(elem)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"扫描 auto_id={auto_id} 失败: {e}")

        for edit in edits:
            try:
                if edit.is_visible():
                    logger.debug(
                        f"定位文件名 Edit: auto_id={auto_id}, "
                        f"rect={edit.rectangle()}"
                    )
                    return edit
            except Exception:
                continue

        if edits:
            return edits[0]

        for combo in combos:
            try:
                for inner in combo.descendants(class_name="Edit"):
                    try:
                        if inner.is_visible():
                            return inner
                    except Exception:
                        continue
            except Exception:
                pass
            return combo

        raise RuntimeError(f"未找到 auto_id={auto_id} 的文件名 Edit 控件")

    def _read_filename_edit_value(self, ctrl) -> str:
        """读取文件名/项目名输入框当前文本。"""
        label_names = {"文件名:", "文件名(N):", "File name:", "File name"}

        def _accept(value: str) -> str:
            text = (value or "").strip()
            if text and text not in label_names:
                return text
            return ""

        try:
            value = _accept(ctrl.iface_value.CurrentValue)
            if value:
                return value
        except Exception:
            pass

        try:
            props = ctrl.legacy_properties()
            value = _accept(props.get("Value") or "")
            if value:
                return value
        except Exception:
            pass

        try:
            value = _accept(ctrl.get_value())
            if value:
                return value
        except Exception:
            pass

        try:
            for text in ctrl.texts():
                value = _accept(text)
                if value:
                    return value
        except Exception:
            pass

        try:
            value = _accept(ctrl.window_text())
            if value:
                return value
        except Exception:
            pass

        return ""

    @staticmethod
    def _filename_edit_matches(actual: str, expected: str) -> bool:
        """比较文件名框内容（新建项目时可忽略 .airvision 后缀）。"""
        if not actual:
            return False
        actual_stem = os.path.splitext(actual)[0]
        expected_stem = os.path.splitext(expected)[0]
        return actual_stem == expected_stem or actual == expected

    def _type_into_filename_field(self, dlg, filename: str):
        """Alt+N 聚焦文件名框后，再次鼠标点击并键入。"""
        ui_input.activate_dialog(dlg)
        pyautogui.hotkey("alt", "n")
        time.sleep(0.3)
        edit = self._find_filename_edit_by_auto_id(
            dlg, self._NEW_PROJECT_FILENAME_AUTO_ID
        )
        ui_input.mouse_type_filename(edit, filename)

    def _enter_new_project_name(self, dlg, dialog_title: str, project_name: str):
        """在文件名框输入 test_数字（不含 .airvision）。"""
        logger.info(f"[{dialog_title}] 步骤2: 文件名框输入 -> {project_name!r}")
        ui_input.activate_dialog(dlg)

        send_keys("%n", pause=0.3, with_spaces=True)
        time.sleep(0.3)

        edit = self._find_filename_edit_by_auto_id(
            dlg, self._NEW_PROJECT_FILENAME_AUTO_ID
        )

        for attempt in range(3):
            ui_input.mouse_type_filename(edit, project_name)
            actual = self._read_filename_edit_value(edit)
            if not actual:
                actual = ui_input.read_edit_via_clipboard(edit)
            logger.info(
                f"[{dialog_title}] 项目名校验: expected={project_name!r}, actual={actual!r}"
            )
            if self._filename_edit_matches(actual, project_name):
                logger.info(f"[{dialog_title}] 步骤2 完成: 项目名已输入")
                return

            logger.warning(
                f"[{dialog_title}] 第 {attempt + 1} 次输入不符，重试"
            )
            send_keys("%n", pause=0.2, with_spaces=True)
            time.sleep(0.2)
            edit = self._find_filename_edit_by_auto_id(
                dlg, self._NEW_PROJECT_FILENAME_AUTO_ID
            )
            time.sleep(0.3)

        actual = self._read_filename_edit_value(edit)
        if not actual:
            actual = ui_input.read_edit_via_clipboard(edit)
        raise RuntimeError(
            f"[{dialog_title}] 无法写入项目名: "
            f"expected={project_name!r}, actual={actual!r}"
        )

    def _set_dialog_filename_by_auto_id(
        self, dlg, dialog_title: str, filename: str, auto_id: str, strict: bool = False
    ):
        """向指定 auto_id 的文件名/项目名输入框写入文本。"""
        logger.info(f"[{dialog_title}] 输入(auto_id={auto_id}): {filename!r}")
        edit = self._find_filename_edit_by_auto_id(dlg, auto_id)

        for attempt in range(3):
            ui_input.mouse_type_filename(edit, filename)
            actual = self._read_filename_edit_value(edit)
            if self._filename_edit_matches(actual, filename):
                logger.info(
                    f"[{dialog_title}] 文件名框已写入: {filename!r} "
                    f"(actual={actual!r})"
                )
                return
            logger.warning(
                f"[{dialog_title}] 文件名框第 {attempt + 1} 次写入不符: "
                f"expected={filename!r}, actual={actual!r}，Alt+N 后重试"
            )
            try:
                dlg.set_focus()
            except Exception:
                pass
            self._type_into_filename_field(dlg, filename)

        if strict:
            actual = self._read_filename_edit_value(edit)
            if not actual:
                logger.warning(
                    f"[{dialog_title}] 无法读取文件名框，已键入 {filename!r}，继续"
                )
                return
            raise RuntimeError(
                f"[{dialog_title}] 无法写入文件名框: "
                f"expected={filename!r}, actual={actual!r}"
            )

    def handle_new_project_dialog(
        self,
        path: str,
        project_name: str,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """Create New Project 完整用户操作流程。"""
        dialog_title = DialogTitle.CREATE_NEW_PROJECT
        target_dir = os.path.normpath(path)

        dlg = self.get_new_project_dialog(timeout=timeout)
        ui_input.activate_dialog(dlg)

        self._navigate_file_dialog_to_path(dlg, dialog_title, target_dir)

        dlg = self.get_new_project_dialog(timeout=timeout)
        self._enter_new_project_name(dlg, dialog_title, project_name)

        if not confirm:
            return

        logger.info(f"[{dialog_title}] 步骤3: 鼠标点击保存")
        dlg = self.get_new_project_dialog(timeout=timeout)
        ui_input.activate_dialog(dlg)
        self._confirm_dialog(dlg, dialog_title)
        time.sleep(0.5)

        logger.info(f"[{dialog_title}] 步骤4: 处理覆盖确认（若有）")
        self.confirm_overwrite_if_present(timeout=8)

        logger.info(f"[{dialog_title}] 步骤5: 等待 Success 提示框并点击 OK")
        if not self.dismiss_project_created_success(timeout=10):
            logger.warning(f"[{dialog_title}] 未检测到 Success 框，回退通用 OK 扫描")
            self.dismiss_ok_or_wait(wait_if_absent=1.0)

    def dismiss_project_created_success(self, timeout: int = 10) -> bool:
        """新建项目成功后，等待并鼠标点击 Success 提示框 OK。"""
        ok_titles = ("OK", "确定")
        end = time.time() + timeout
        while time.time() < end:
            try:
                dlg = self.get_window_by_title(
                    DialogTitle.PROJECT_CREATED_SUCCESS, timeout=0.5
                )
                btn = self._find_dialog_button(dlg, ok_titles)
                if btn is not None:
                    logger.info(f"[Success] 鼠标点击 OK: {btn.window_text()!r}")
                    ui_input.activate_dialog(dlg)
                    ui_input.mouse_click(btn)
                    time.sleep(0.3)
                    return True
            except (TimeoutError, Exception):
                pass
            time.sleep(0.3)
        return False

    def cancel_new_project_dialog(self, timeout: int = 2):
        """取消 New Project / Create New Project 对话框。"""
        try:
            dlg = self.get_new_project_dialog(timeout=timeout)
            for btn_title in ("取消", "Cancel"):
                btn = self._find_dialog_button(dlg, (btn_title,))
                if btn is not None:
                    logger.info(f"取消新建项目对话框: {btn_title!r}")
                    ui_input.mouse_click(btn)
                    return True
        except Exception:
            pass
        return False

    def handle_open_project_dialog(
        self,
        path: str,
        filename: str,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """Open Project：导航目录 → 文件名框输入 .airvision → 打开。"""
        dialog_title = DialogTitle.OPEN_PROJECT
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        self._navigate_file_dialog_to_path(dlg, dialog_title, path)
        time.sleep(0.5)
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)

        target = filename.strip()
        if not target.lower().endswith(".airvision"):
            target = f"{target}.airvision"

        logger.info(f"[{dialog_title}] 文件名框输入: {target!r}")
        self._set_dialog_filename_by_auto_id(
            dlg,
            dialog_title,
            target,
            self._OPEN_PROJECT_FILENAME_AUTO_ID,
        )

        if confirm:
            dlg = self.get_window_by_title(dialog_title, timeout=timeout)
            self._confirm_dialog(dlg, dialog_title)

    def confirm_overwrite_if_present(self, timeout: int = 5) -> bool:
        """若弹出覆盖确认框，鼠标点击是/Yes。"""
        end = time.time() + timeout
        while time.time() < end:
            for title in self._OVERWRITE_DIALOG_TITLES:
                try:
                    dlg = self.get_window_by_title(title, timeout=0.5)
                except TimeoutError:
                    continue
                ui_input.activate_dialog(dlg)
                btn = self._find_dialog_button(dlg, self._OVERWRITE_YES_TITLES)
                if btn is not None:
                    logger.info(
                        f"[{title}] 鼠标点击替换确认: {btn.window_text()!r}"
                    )
                    ui_input.mouse_click(btn)
                    time.sleep(0.5)
                    return True
            time.sleep(0.3)
        logger.debug("未出现文件覆盖确认框，跳过")
        return False

    def cancel_overwrite_if_present(self, timeout: int = 2) -> bool:
        """若存在覆盖确认框，点击否/No 取消。"""
        end = time.time() + timeout
        while time.time() < end:
            for title in self._OVERWRITE_DIALOG_TITLES:
                try:
                    dlg = self.get_window_by_title(title, timeout=0.5)
                except TimeoutError:
                    continue
                btn = self._find_dialog_button(dlg, self._OVERWRITE_NO_TITLES)
                if btn is not None:
                    logger.info(f"[{title}] 取消覆盖确认: {btn.window_text()!r}")
                    ui_input.mouse_click(btn)
                    time.sleep(0.5)
                    return True
            time.sleep(0.3)
        return False

    def _select_file_by_list_item(self, dlg, dialog_title: str, filename: str) -> bool:
        """鼠标单击文件列表项选中文件（模拟用户在资源管理器中点击）。"""
        target = filename.strip()
        if not target.lower().endswith(".airvision"):
            target = f"{target}.airvision"
        target_lower = target.lower()

        try:
            for item in dlg.descendants(control_type="ListItem"):
                name = (item.window_text() or "").strip()
                if not name:
                    continue
                if name == target or name.lower() == target_lower:
                    logger.info(f"[{dialog_title}] 鼠标单击列表项: {name!r}")
                    ui_input.mouse_click(item)
                    time.sleep(0.3)
                    return True
        except Exception as e:
            logger.debug(f"[{dialog_title}] ListItem 查找失败: {e}")
        return False

    def handle_image_file_dialog(
        self,
        dialog_title: str,
        path: str = None,
        filename: str = None,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """选择图片文件：导航目录 → 单击列表项选中 → 打开。"""
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)

        if path:
            self._navigate_file_dialog_to_path(dlg, dialog_title, path)
            time.sleep(0.5)
            dlg = self.get_window_by_title(dialog_title, timeout=timeout)

        if filename:
            if not self._select_file_by_list_item(dlg, dialog_title, filename):
                self._set_filename_in_dialog(dlg, dialog_title, filename)

        if confirm:
            dlg = self.get_window_by_title(dialog_title, timeout=timeout)
            self._confirm_dialog(dlg, dialog_title)

    def click_in_dialog(self, dialog_title: str, timeout: int = 5, **kwargs):
        """在指定标题的对话框内鼠标点击控件。"""
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        ctrl = dlg.child_window(**kwargs)
        ctrl.wait("exists visible", timeout=timeout)
        logger.info(f"[{dialog_title}] 鼠标点击: {kwargs}")
        ui_input.mouse_click(ctrl)

    def _set_filename_in_dialog(self, dlg, dialog_title: str, filename: str):
        """向对话框文件名输入框写入文本。"""
        logger.info(f"[{dialog_title}] 输入文件名: {filename}")

        try:
            edit_wrappers = dlg.descendants(control_type="Edit")
            logger.debug(
                f"[{dialog_title}] Edit 控件: "
                + ", ".join(
                    f"name={e.window_text()!r}, auto_id={e.element_info.automation_id!r}"
                    for e in edit_wrappers
                )
            )
        except Exception as e:
            logger.debug(f"descendants 查找 Edit 失败: {e}")
            edit_wrappers = []

        for auto_id in self._FILENAME_EDIT_AUTO_IDS:
            for wrapper in edit_wrappers:
                if wrapper.element_info.automation_id == auto_id:
                    ui_input.mouse_type_filename(wrapper, filename)
                    logger.info(f"[{dialog_title}] 已向文件名框(auto_id={auto_id})写入: {filename!r}")
                    return

        for auto_id in self._FILENAME_EDIT_AUTO_IDS:
            try:
                ctrl = dlg.child_window(auto_id=auto_id)
                if not ctrl.exists():
                    continue
                if getattr(ctrl.element_info, "control_type", "") == "ComboBox":
                    inner = ctrl.child_window(class_name="Edit")
                    if inner.exists():
                        ctrl = inner
                ui_input.mouse_type_filename(ctrl, filename)
                logger.info(f"[{dialog_title}] 已向文件名框(auto_id={auto_id})写入: {filename!r}")
                return
            except Exception:
                continue

        raise RuntimeError(
            f"[{dialog_title}] 未找到文件名输入框(auto_id={'/'.join(self._FILENAME_EDIT_AUTO_IDS)})"
        )

    def _find_dialog_button(self, dlg, titles: tuple, control_types=("Button", "SplitButton")):
        """在对话框中查找确认/取消按钮。"""
        for btn_title in titles:
            for ctrl_type in control_types:
                try:
                    btn = dlg.child_window(title=btn_title, control_type=ctrl_type)
                    if btn.exists(timeout=0):
                        return btn
                except Exception:
                    continue
            try:
                btn = dlg.child_window(title=btn_title)
                if btn.exists(timeout=0):
                    return btn
            except Exception:
                continue

        try:
            for elem in dlg.descendants():
                name = elem.window_text()
                if name in titles:
                    return elem
        except Exception:
            pass
        return None

    def _confirm_dialog(self, dlg, dialog_title: str):
        """鼠标点击对话框确认按钮。"""
        btn = self._find_dialog_button(dlg, self._CONFIRM_BUTTON_TITLES)
        if btn is not None:
            logger.info(f"[{dialog_title}] 鼠标点击确认按钮: {btn.window_text()!r}")
            ui_input.mouse_click(btn)
            time.sleep(0.5)
            return
        raise RuntimeError(f"[{dialog_title}] 未找到可点击的确认按钮")

    def cancel_file_dialog(self, dialog_title: str, timeout: int = 5):
        """鼠标点击取消按钮关闭文件对话框。"""
        logger.info(f"[{dialog_title}] 取消对话框")
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        for btn_title in ("取消", "Cancel"):
            btn = self._find_dialog_button(dlg, (btn_title,))
            if btn is not None:
                ui_input.mouse_click(btn)
                return
        ui_input.mouse_click(dlg)
        pyautogui.press("esc")
