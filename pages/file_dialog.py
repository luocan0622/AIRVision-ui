"""Windows 文件对话框通用操作 Mixin。"""
import os
import time

from pywinauto import Application
from pywinauto.keyboard import SendKeys as send_keys

from pages.dialogs import DialogTitle
from utils import ui_input
from utils.logger import logger


class FileDialogMixin:
    """文件/项目对话框处理：地址栏导航、文件名输入、确认与覆盖提示。

    依赖宿主类提供 ``self.app``（pywinauto Application 实例）。
    """

    # Windows 标准 #32770 对话框控件 ID（固定，不随启动变化）：
    # 地址栏 41477；文件名多为 1148（ComboBoxEx32 内 Edit），旧版可能是 1001
    _NEW_PROJECT_FILENAME_AUTO_ID = "1001"
    _OPEN_PROJECT_FILENAME_AUTO_ID = "1148"
    _ADDRESS_BAR_AUTO_ID = "41477"
    _FILENAME_EDIT_AUTO_IDS = (_NEW_PROJECT_FILENAME_AUTO_ID, _OPEN_PROJECT_FILENAME_AUTO_ID)
    _FILENAME_CTRL_IDS = (1148, 1001)
    _CONFIRM_BUTTON_TITLES = (
        "打开(O)", "打开", "Open(O)", "Open", "&Open",
        "保存(S)", "保存", "Save(S)", "Save", "&Save",
        "OK", "确定",
    )
    _SAVE_BUTTON_TITLES = ("保存(S)", "保存", "Save(S)", "Save", "&Save")
    _OVERWRITE_YES_TITLES = ("是(Y)", "是", "Yes", "&Yes", "Yes(Y)")
    _OVERWRITE_NO_TITLES = ("否(N)", "否", "No", "&No", "No(N)")
    _OVERWRITE_DIALOG_TITLES = ("Confirm Save As", "确认另存为")
    _WIN32_DIALOG_CLASS = "#32770"

    @staticmethod
    def _connect_dialog_by_hwnd(hwnd: int):
        """标准文件对话框用 win32（快且稳），Qt 窗口用 uia。"""
        import win32gui

        cls = win32gui.GetClassName(hwnd)
        backend = "win32" if cls == FileDialogMixin._WIN32_DIALOG_CLASS else "uia"
        app = Application(backend=backend).connect(handle=hwnd)
        return app.window(handle=hwnd), backend

    def _ensure_dialog_backend(self, dlg):
        """#32770 对话框统一切换到 win32，避免 UIA descendants 卡死。"""
        import win32gui

        hwnd = dlg.handle
        if win32gui.GetClassName(hwnd) == self._WIN32_DIALOG_CLASS:
            return self._connect_dialog_by_hwnd(hwnd)[0]
        return dlg

    def get_window_by_title(
        self,
        title: str,
        timeout: int = 5,
        alt_titles: tuple = (),
        *,
        substring_match: bool = False,
    ):
        """通过窗口标题等待并返回窗口（支持子串匹配）。"""
        import win32gui

        titles = tuple(t for t in (title, *alt_titles) if t)
        title_set = set(titles)
        end = time.time() + timeout
        last_hint = 0.0

        def _title_matches(text: str) -> bool:
            if not text:
                return False
            if text in title_set:
                return True
            if not substring_match:
                return False
            return any(part in text or text in part for part in titles if part)

        while time.time() < end:
            try:
                hwnds = []

                def _enum(hwnd, _lp):
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            text = win32gui.GetWindowText(hwnd)
                            if _title_matches(text):
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
                    return self._connect_dialog_by_hwnd(target_hwnd)[0]
            except Exception:
                pass

            if time.time() - last_hint >= 3.0:
                logger.info(f"等待窗口出现: {titles!r} ...")
                last_hint = time.time()
            time.sleep(0.3)

        self._log_visible_windows_for_debug(titles)
        raise TimeoutError(f"未找到标题匹配 {titles!r} 的窗口 (timeout={timeout}s)")

    @staticmethod
    def _log_visible_windows_for_debug(expected_titles: tuple):
        """超时后打印当前可见顶层窗口，便于排查标题不匹配。"""
        import win32gui

        samples = []

        def _enum(hwnd, _lp):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    text = win32gui.GetWindowText(hwnd)
                    if text:
                        samples.append(
                            f"{text!r} ({win32gui.GetClassName(hwnd)!r})"
                        )
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(_enum, None)
            if samples:
                logger.warning(
                    "可见窗口(节选): " + "; ".join(samples[:12])
                )
        except Exception as e:
            logger.debug(f"枚举可见窗口失败: {e}")

    def _find_file_dialog_by_filename_auto_id(
        self, auto_id: str, timeout: int = 5
    ):
        """按文件名 Edit 的 auto_id 定位标准文件对话框（仅 #32770，避免扫 Qt 主窗）。"""
        import win32gui

        pid = self.app.process
        end = time.time() + timeout

        while time.time() < end:
            for hwnd in self._enum_app_top_windows(pid):
                try:
                    if win32gui.GetClassName(hwnd) != self._WIN32_DIALOG_CLASS:
                        continue
                    dlg = self._connect_dialog_by_hwnd(hwnd)[0]
                    for loc in (
                        {"auto_id": auto_id, "class_name": "Edit"},
                        {"auto_id": auto_id},
                    ):
                        edit = dlg.child_window(**loc)
                        if edit.exists(timeout=0):
                            title = win32gui.GetWindowText(hwnd)
                            logger.info(
                                f"按 auto_id={auto_id} 定位对话框: "
                                f"title={title!r}, handle={hwnd}"
                            )
                            return dlg
                except Exception:
                    continue
            time.sleep(0.3)

        raise TimeoutError(
            f"未找到含文件名框 auto_id={auto_id!r} 的对话框 (timeout={timeout}s)"
        )

    @staticmethod
    def _enum_app_top_windows(pid: int) -> list[int]:
        import win32gui
        import win32process

        dialog_classes = {"#32770", "Qt5QWindowIcon", "Qt5152QWindowIcon"}
        hwnds: list[int] = []

        def _enum(hwnd, _lp):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                if found_pid != pid:
                    return True
                if win32gui.GetClassName(hwnd) in dialog_classes:
                    hwnds.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_enum, None)
        return hwnds

    def get_new_project_dialog(self, timeout: int = 10):
        """定位 Create New Project / 新建项目 对话框。"""
        try:
            return self.get_window_by_title(
                DialogTitle.CREATE_NEW_PROJECT,
                timeout=min(timeout, 6),
                alt_titles=DialogTitle.CREATE_NEW_PROJECT_TITLES[1:],
                substring_match=True,
            )
        except TimeoutError:
            logger.info("标题未匹配，尝试按文件名框 auto_id=1001 定位新建项目对话框")
            return self._find_file_dialog_by_filename_auto_id(
                self._NEW_PROJECT_FILENAME_AUTO_ID,
                timeout=max(4, timeout - 6),
            )

    def _find_dialog_address_bar(self, dlg):
        """查找文件对话框地址栏（auto_id 41477）；优先 win32，避免 UIA 全树扫描。"""
        dlg = self._ensure_dialog_backend(dlg)
        locators = (
            {"auto_id": "41477", "class_name": "Edit"},
            {"auto_id": "41477"},
            {"title": "地址", "class_name": "Edit"},
            {"title": "Address", "class_name": "Edit"},
        )
        for loc in locators:
            try:
                ctrl = dlg.child_window(**loc)
                if ctrl.exists(timeout=0):
                    logger.info(f"地址栏(auto_id=41477): loc={loc}")
                    return ctrl
            except Exception:
                continue
        logger.debug("未找到地址栏控件，将使用 Alt+D 键盘路径")
        return None

    def _address_via_alt_d_paste(self, path: str):
        """Alt+D 聚焦地址栏 → 全选 → 粘贴路径（Windows 标准操作，无需鼠标）。"""
        ui_input.focus_file_dialog_address_bar()
        ui_input.select_all_and_paste(path)

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
            import win32gui

            pid = self.app.process
            skip_titles = (
                DialogTitle.SELECT_TEMPLATE_IMAGES,
                DialogTitle.SELECT_TEMPLATE_IMAGE,
                DialogTitle.SELECT_DEPTH_IMAGE,
            )
            for hwnd in self._enum_app_top_windows(pid):
                try:
                    title = win32gui.GetWindowText(hwnd)
                    if title in skip_titles:
                        continue
                    dlg, _ = self._connect_dialog_by_hwnd(hwnd)
                    btn = self._find_dialog_button(dlg, ok_titles)
                    if btn is None:
                        continue
                    logger.info(f"[{title}] 点击 OK")
                    ui_input.activate_dialog(dlg)
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

    _UNSAVED_SAVE_TITLES = ("Save", "保存(S)", "保存", "Save(S)", "&Save")
    _UNSAVED_DISCARD_TITLES = (
        "Discard",
        "放弃",
        "Don't Save",
        "不保存",
        "不保存(N)",
        "否(N)",
        "否",
        "No",
        "No(N)",
    )

    def _is_unsaved_changes_dialog(self, title: str, dlg) -> bool:
        if any(marker in title for marker in DialogTitle.UNSAVED_CHANGES_TITLES):
            return True
        has_save = self._find_dialog_button(dlg, self._UNSAVED_SAVE_TITLES) is not None
        has_discard = self._find_dialog_button(dlg, self._UNSAVED_DISCARD_TITLES) is not None
        return has_save and has_discard

    def handle_unsaved_changes_if_present(
        self, save: bool = True, timeout: int = 3
    ) -> bool:
        """处理「Unsaved Changes」对话框。

        save=True 时点击 Save 保存更改；save=False 时点击 Discard/不保存。
        """
        button_titles = (
            self._UNSAVED_SAVE_TITLES if save else self._UNSAVED_DISCARD_TITLES
        )
        action_label = "保存" if save else "不保存/放弃"

        end = time.time() + timeout
        while time.time() < end:
            try:
                import win32gui

                pid = self.app.process
                for hwnd in self._enum_app_top_windows(pid):
                    try:
                        title = win32gui.GetWindowText(hwnd)
                        dlg, _ = self._connect_dialog_by_hwnd(hwnd)
                        if not self._is_unsaved_changes_dialog(title, dlg):
                            continue
                        btn = self._find_dialog_button(dlg, button_titles)
                        if btn is None:
                            continue
                        logger.info(
                            f"[{title}] 未保存更改，点击{action_label}: "
                            f"{btn.window_text()!r}"
                        )
                        ui_input.activate_dialog(dlg)
                        ui_input.mouse_click(btn)
                        time.sleep(0.5)
                        return True
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def dismiss_unsaved_changes_if_present(self, timeout: int = 3) -> bool:
        """清理场景：未保存提示时点「不保存/放弃」。"""
        return self.handle_unsaved_changes_if_present(save=False, timeout=timeout)

    def _handle_close_confirm_dialogs(
        self, save_changes: bool = True, timeout: float = 5.0
    ) -> None:
        """关闭项目/工作流后的弹窗：有未保存更改则保存或放弃，否则点 OK。"""
        end = time.time() + timeout
        while time.time() < end:
            if self.handle_unsaved_changes_if_present(save=save_changes, timeout=0.8):
                if save_changes:
                    time.sleep(0.5)
                    self.dismiss_ok_or_wait(wait_if_absent=0.5)
                continue
            if self.dismiss_ok_or_wait(wait_if_absent=0.3):
                continue
            time.sleep(0.3)
            break

    @staticmethod
    def _enum_file_dialog_edits(parent_hwnd: int) -> list[tuple[int, int]]:
        """枚举文件对话框内 Edit（含 ComboBoxEx32 内嵌），返回 (hwnd, ctrl_id)。"""
        import win32gui

        results: list[tuple[int, int]] = []

        def _cb(child, _):
            cls = win32gui.GetClassName(child)
            if cls == "Edit":
                results.append((child, win32gui.GetDlgCtrlID(child)))
            elif cls in ("ComboBoxEx32", "ComboBox"):
                win32gui.EnumChildWindows(child, _cb, None)
            return True

        win32gui.EnumChildWindows(parent_hwnd, _cb, None)
        return results

    def _find_filename_edit_by_auto_id(self, dlg, auto_id: str):
        """定位文件名 Edit（auto_id 1001/1148）；优先 win32 child_window。"""
        dlg = self._ensure_dialog_backend(dlg)
        for loc in (
            {"auto_id": auto_id, "class_name": "Edit"},
            {"auto_id": auto_id, "class_name": "ComboBoxEx32"},
            {"auto_id": auto_id, "control_type": "Edit"},
            {"auto_id": auto_id},
        ):
            try:
                ctrl = dlg.child_window(**loc)
                if not ctrl.exists(timeout=0):
                    continue
                if ctrl.class_name() in ("ComboBoxEx32", "ComboBox"):
                    inner = ctrl.child_window(class_name="Edit")
                    if inner.exists(timeout=0):
                        logger.debug(
                            f"定位文件名 Edit: ComboBoxEx32 auto_id={auto_id}"
                        )
                        return inner
                else:
                    logger.debug(f"定位文件名 Edit: auto_id={auto_id}, loc={loc}")
                    return ctrl
            except Exception:
                continue
        raise RuntimeError(f"未找到 auto_id={auto_id} 的文件名 Edit 控件")

    def _find_file_dialog_filename_edit(self, dlg):
        """定位文件对话框文件名输入框（1001/1148/EnumChild 回退）。"""
        dlg = self._ensure_dialog_backend(dlg)

        for auto_id in self._FILENAME_EDIT_AUTO_IDS:
            try:
                return self._find_filename_edit_by_auto_id(dlg, auto_id)
            except RuntimeError:
                continue

        address_id = int(self._ADDRESS_BAR_AUTO_ID)
        for hwnd, ctrl_id in self._enum_file_dialog_edits(dlg.handle):
            if ctrl_id in self._FILENAME_CTRL_IDS:
                logger.info(f"定位文件名框: Edit ctrl_id={ctrl_id}")
                return dlg.child_window(handle=hwnd, class_name="Edit")

        for hwnd, ctrl_id in reversed(self._enum_file_dialog_edits(dlg.handle)):
            if ctrl_id != address_id:
                logger.info(f"定位文件名框: Edit ctrl_id={ctrl_id} (fallback)")
                return dlg.child_window(handle=hwnd, class_name="Edit")

        return None

    def _reconnect_file_dialog(self, dlg, fallback_getter=None, timeout: int = 3):
        """按 hwnd 重连对话框，避免标题搜索；失败时回退 getter。"""
        import win32gui

        hwnd = getattr(dlg, "handle", None)
        if hwnd and win32gui.IsWindow(hwnd):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    return self._ensure_dialog_backend(
                        self._connect_dialog_by_hwnd(hwnd)[0]
                    )
            except Exception:
                pass
        if fallback_getter is not None:
            return self._ensure_dialog_backend(fallback_getter(timeout=timeout))
        return self._ensure_dialog_backend(dlg)

    def _navigate_file_dialog_address(self, dlg, dialog_title: str, path: str):
        """地址导航栏输入路径并回车跳转（鼠标点地址栏 + 粘贴，回退 Alt+D）。"""
        normalized = os.path.normpath(path)
        logger.info(f"[{dialog_title}] 地址栏导航 -> {normalized!r}")
        dlg = self._ensure_dialog_backend(dlg)
        ui_input.activate_dialog(dlg)
        time.sleep(0.3)

        address = self._find_dialog_address_bar(dlg)
        if address is not None:
            ui_input.mouse_click(address)
            time.sleep(0.15)
            ui_input.select_all_and_paste(normalized)
        else:
            self._address_via_alt_d_paste(normalized)

        ui_input.confirm_address_bar()
        time.sleep(1.0)
        logger.info(f"[{dialog_title}] 地址栏跳转完成: {normalized!r}")

    def _type_filename_in_dialog(self, dlg, dialog_title: str, filename: str):
        """向文件对话框文件名框写入文本（1001/1148 + Alt+N 回退）。"""
        logger.info(f"[{dialog_title}] 文件名框输入: {filename!r}")
        dlg = self._ensure_dialog_backend(dlg)
        ui_input.activate_dialog(dlg)
        time.sleep(0.5)

        edit = self._find_file_dialog_filename_edit(dlg)
        if edit is not None:
            ui_input.mouse_type_filename(edit, filename)
        else:
            logger.warning(f"[{dialog_title}] 未定位文件名框，回退 Alt+N 粘贴")
            send_keys("%n", pause=0.3, with_spaces=True)
            time.sleep(0.2)
            ui_input.select_all_and_paste(filename)
        time.sleep(0.3)

    def _select_file_by_list_item(self, dlg, dialog_title: str, filename: str) -> bool:
        """在文件列表中选中指定文件（win32 SysListView32，精确匹配文件名）。"""
        target = filename.strip()
        target_lower = target.lower()
        dlg = self._ensure_dialog_backend(dlg)

        for loc in (
            {"class_name": "SysListView32", "control_id": 1},
            {"class_name": "SysListView32"},
        ):
            try:
                listview = dlg.child_window(**loc)
                if not listview.exists(timeout=0):
                    continue
                for index, name in enumerate(listview.item_texts()):
                    text = (name or "").strip()
                    if not text:
                        continue
                    if text == target or text.lower() == target_lower:
                        logger.info(
                            f"[{dialog_title}] 选中列表项: {text!r} (index={index})"
                        )
                        listview.select(index)
                        time.sleep(0.3)
                        return True
            except Exception as e:
                logger.debug(f"[{dialog_title}] SysListView32 查找失败: {e}")

        return False

    def _fill_file_dialog_filename(
        self,
        dlg,
        dialog_title: str,
        filename: str,
        *,
        try_list_select: bool = True,
    ):
        """列表选中或文件名框键入。"""
        if try_list_select and self._select_file_by_list_item(
            dlg, dialog_title, filename
        ):
            return
        self._type_filename_in_dialog(dlg, dialog_title, filename)

    def handle_file_dialog(
        self,
        dialog_title: str,
        path: str = None,
        filename: str = None,
        confirm: bool = True,
        timeout: int = 10,
        alt_titles: tuple = (),
        substring_match: bool = False,
        try_list_select: bool = True,
    ):
        """统一处理 #32770 文件对话框：定位 → 地址栏 → 文件名/列表 → 确认。"""
        def _get_dialog(t=timeout):
            return self.get_window_by_title(
                dialog_title,
                timeout=t,
                alt_titles=alt_titles,
                substring_match=substring_match,
            )

        dlg = self._ensure_dialog_backend(_get_dialog())

        if path:
            self._navigate_file_dialog_address(
                dlg, dialog_title, os.path.normpath(path)
            )
            dlg = self._reconnect_file_dialog(
                dlg, fallback_getter=_get_dialog, timeout=3
            )

        if filename:
            self._fill_file_dialog_filename(
                dlg,
                dialog_title,
                filename,
                try_list_select=try_list_select,
            )

        if confirm:
            dlg = self._reconnect_file_dialog(
                dlg, fallback_getter=_get_dialog, timeout=2
            )
            self._confirm_dialog(dlg, dialog_title)

    def _set_new_project_filename(self, dlg, dialog_title: str, project_name: str):
        """新建项目：文件名框输入项目名（不含 .airvision）。"""
        logger.info(f"[{dialog_title}] 文件名框 -> {project_name!r}")
        self._type_filename_in_dialog(dlg, dialog_title, project_name)

    def _click_new_project_save(self, dlg, dialog_title: str):
        """步骤3：鼠标点击保存按钮（失败时回退 Alt+S）。"""
        logger.info(f"[{dialog_title}] 步骤3: 点击保存")
        dlg = self._ensure_dialog_backend(dlg)
        ui_input.activate_dialog(dlg)
        btn = self._find_dialog_button(dlg, self._SAVE_BUTTON_TITLES)
        if btn is not None:
            logger.info(f"[{dialog_title}] 鼠标点击保存: {btn.window_text()!r}")
            ui_input.mouse_click(btn)
            time.sleep(0.5)
            return
        logger.warning(f"[{dialog_title}] 未找到保存按钮，回退 Alt+S")
        send_keys("%s", pause=0.2, with_spaces=True)
        time.sleep(0.6)

    def handle_new_project_dialog(
        self,
        path: str,
        project_name: str,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """Create New Project：地址栏路径 → 文件名项目名 → 保存 → Success OK。"""
        dialog_title = DialogTitle.CREATE_NEW_PROJECT
        target_dir = os.path.normpath(path)

        dlg = self._ensure_dialog_backend(
            self.get_new_project_dialog(timeout=timeout)
        )
        logger.info(f"[{dialog_title}] 对话框已就绪, handle={dlg.handle}")

        self._navigate_file_dialog_address(dlg, dialog_title, target_dir)
        dlg = self._reconnect_file_dialog(
            dlg, fallback_getter=self.get_new_project_dialog, timeout=3
        )

        self._set_new_project_filename(dlg, dialog_title, project_name)

        if not confirm:
            return

        dlg = self._reconnect_file_dialog(
            dlg, fallback_getter=self.get_new_project_dialog, timeout=2
        )
        self._click_new_project_save(dlg, dialog_title)

        logger.info(f"[{dialog_title}] 步骤4: 处理覆盖确认（若有）")
        self.confirm_overwrite_if_present(timeout=8)

        logger.info(f"[{dialog_title}] 步骤5: Success 提示框点击 OK")
        if not self.dismiss_project_created_success(timeout=10):
            logger.warning(f"[{dialog_title}] 未检测到 Success 框，回退 OK 扫描")
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

    def cancel_template_images_dialog(self, timeout: int = 2) -> bool:
        """取消 Select Template Images 主对话框。"""
        try:
            dlg = self.get_window_by_title(
                DialogTitle.SELECT_TEMPLATE_IMAGES, timeout=timeout
            )
            for btn_title in ("Cancel", "取消"):
                btn = self._find_dialog_button(dlg, (btn_title,))
                if btn is not None:
                    logger.info(f"取消模板图片主对话框: {btn_title!r}")
                    ui_input.activate_dialog(dlg)
                    ui_input.mouse_click(btn)
                    time.sleep(0.3)
                    return True
        except Exception:
            pass
        return False

    def cancel_open_file_dialogs(self, timeout: int = 1) -> bool:
        """取消应用内残留的标准打开文件对话框（#32770）。"""
        import win32gui

        end = time.time() + timeout
        while time.time() < end:
            pid = self.app.process
            for hwnd in self._enum_app_top_windows(pid):
                try:
                    if win32gui.GetClassName(hwnd) != self._WIN32_DIALOG_CLASS:
                        continue
                    title = win32gui.GetWindowText(hwnd)
                    dlg, _ = self._connect_dialog_by_hwnd(hwnd)
                    for btn_title in ("取消", "Cancel"):
                        btn = self._find_dialog_button(dlg, (btn_title,))
                        if btn is None:
                            continue
                        logger.info(f"取消文件对话框: {title!r}")
                        ui_input.activate_dialog(dlg)
                        ui_input.mouse_click(btn)
                        time.sleep(0.3)
                        return True
                except Exception:
                    continue
            time.sleep(0.2)
        return False

    def handle_open_project_dialog(
        self,
        path: str,
        filename: str,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """Open Project：导航目录 → 文件名框输入 .airvision → 打开。"""
        target = filename.strip()
        if not target.lower().endswith(".airvision"):
            target = f"{target}.airvision"

        self.handle_file_dialog(
            DialogTitle.OPEN_PROJECT,
            path=path,
            filename=target,
            confirm=confirm,
            timeout=timeout,
            alt_titles=DialogTitle.OPEN_PROJECT_TITLES[1:],
            substring_match=True,
        )

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

    def handle_image_file_dialog(
        self,
        dialog_title: str,
        path: str = None,
        filename: str = None,
        confirm: bool = True,
        timeout: int = 10,
    ):
        """选择图片/工作流文件：委托统一 handle_file_dialog。"""
        self.handle_file_dialog(
            dialog_title,
            path=path,
            filename=filename,
            confirm=confirm,
            timeout=timeout,
        )

    def click_in_dialog(self, dialog_title: str, timeout: int = 5, **kwargs):
        """在指定标题的对话框内鼠标点击控件。"""
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        ctrl = dlg.child_window(**kwargs)
        ctrl.wait("exists visible", timeout=timeout)
        logger.info(f"[{dialog_title}] 鼠标点击: {kwargs}")
        ui_input.mouse_click(ctrl)

    def _find_dialog_button(self, dlg, titles: tuple, control_types=("Button", "SplitButton")):
        """在对话框中查找确认/取消按钮（win32 child_window，不扫全树）。"""
        dlg = self._ensure_dialog_backend(dlg)
        for btn_title in titles:
            for loc in (
                {"title": btn_title, "class_name": "Button"},
                {"title": btn_title, "control_type": "Button"},
                {"title": btn_title},
            ):
                try:
                    btn = dlg.child_window(**loc)
                    if btn.exists(timeout=0):
                        return btn
                except Exception:
                    continue
        return None

    def _confirm_dialog(self, dlg, dialog_title: str):
        """鼠标点击对话框确认/打开/保存按钮。"""
        dlg = self._ensure_dialog_backend(dlg)
        ui_input.activate_dialog(dlg)

        btn = self._find_dialog_button(dlg, self._CONFIRM_BUTTON_TITLES)
        if btn is not None:
            logger.info(f"[{dialog_title}] 鼠标点击确认按钮: {btn.window_text()!r}")
            ui_input.mouse_click(btn)
            time.sleep(0.5)
            return

        for loc in (
            {"control_id": 1, "class_name": "Button"},
            {"auto_id": "1", "class_name": "Button"},
        ):
            try:
                btn = dlg.child_window(**loc)
                if btn.exists(timeout=0):
                    logger.info(
                        f"[{dialog_title}] 鼠标点击默认按钮: {btn.window_text()!r}"
                    )
                    ui_input.mouse_click(btn)
                    time.sleep(0.5)
                    return
            except Exception:
                continue

        logger.warning(f"[{dialog_title}] 未找到确认按钮，回退 Alt+O")
        send_keys("%o", pause=0.2, with_spaces=True)
        time.sleep(0.5)
