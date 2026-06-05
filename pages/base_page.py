"""基础页面对象基类。

提供所有页面对象共用的核心能力：
- 元素定位：find_element / find_elements / find_popup_element
- 鼠标操作：click / double_click / right_click / mouse_click / mouse_type
- 键盘操作：input_text / type_keys / _send_keys
- 状态查询：is_visible / is_enabled / get_text / wait_until_visible
- 弹出菜单：_get_popup_menu / click_popup_item
- 图像/坐标定位：click_by_image / click_by_position
- 窗口操作：maximize / minimize / restore / close

所有 Mixin 通过 MainPage 组合继承本类，统一使用这些方法操作 UI。
"""
import time

import pyautogui
from pywinauto import Application
from pywinauto.findwindows import find_elements

from pages.file_dialog import FileDialogMixin
from utils import ui_input
from utils.logger import logger

# Qt 顶部菜单（Projects / Workflows 等）与 Filter 相同，多为弹出窗而非 QMenu
_QT_POPUP_CLASS_MARKERS = (
    "Qt5QWindowPopup",
    "PopupDropShadow",
    "QMenu",
)


class BasePage(FileDialogMixin):
    """基础页面对象，用于 Windows 桌面应用自动化。

    所有交互均模拟真实用户操作：以鼠标点击为主，文本输入为先点击再键入。
    文件对话框相关操作由 FileDialogMixin 提供。
    """

    def __init__(self, app: Application, window_title: str = None):
        """
        Args:
            app: pywinauto Application 实例。
            window_title: 当前页面对应的窗口标题。
        """
        self.app = app
        if window_title:
            self.window = app.window(title=window_title)
        else:
            self.window = app.top_window()

    # ─── 元素定位 ──────────────────────────────────────────────────────

    def find_element(self, timeout: int = 10, **kwargs):
        """通过 pywinauto 条件查找单个元素。"""
        logger.debug(f"Finding element: {kwargs}")
        try:
            ctrl = self.window.child_window(**kwargs)
            ctrl.wait("exists visible", timeout=timeout)
            return ctrl
        except Exception as e:
            logger.error(f"Element not found: {kwargs}, error: {e}")
            raise

    def find_elements(self, **kwargs) -> list:
        """查找匹配条件的多个元素。"""
        logger.debug(f"Finding elements: {kwargs}")
        return self.window.children(**kwargs)

    # ─── 鼠标模拟操作 ─────────────────────────────────────────────────

    @staticmethod
    def _element_center(element) -> tuple[int, int]:
        """获取控件中心点屏幕坐标。"""
        return ui_input.element_center(element)

    def mouse_click(self, element, clicks: int = 1, button: str = "left"):
        """在控件中心模拟鼠标点击。"""
        ui_input.mouse_click(element, clicks=clicks, button=button)

    def mouse_double_click(self, element):
        """在控件中心模拟鼠标双击。"""
        ui_input.mouse_double_click(element)

    def mouse_right_click(self, element):
        """在控件中心模拟鼠标右键。"""
        ui_input.mouse_right_click(element)

    def mouse_type(self, element, text: str, clear: bool = True):
        """先鼠标点击控件聚焦，再模拟键盘输入。"""
        ui_input.mouse_type(element, text, clear=clear)

    def mouse_type_filename(self, edit, text: str):
        """文件对话框文件名框：鼠标点击 → 全选 → send_keys 键入。"""
        ui_input.mouse_type_filename(edit, text)

    def _activate_dialog(self, dlg):
        """将对话框置于前台并获取焦点。"""
        ui_input.activate_dialog(dlg)

    def mouse_press_key(self, key: str):
        """模拟按下单个键（如 enter、esc）。"""
        ui_input.press_key(key)

    # ─── 元素操作 ──────────────────────────────────────────────────────

    def click(self, timeout: int = 10, **kwargs):
        """鼠标点击元素。"""
        element = self.find_element(timeout=timeout, **kwargs)
        logger.info(f"鼠标点击元素: {kwargs}")
        self.mouse_click(element)

    def double_click(self, timeout: int = 10, **kwargs):
        """鼠标双击元素。"""
        element = self.find_element(timeout=timeout, **kwargs)
        logger.info(f"鼠标双击元素: {kwargs}")
        self.mouse_double_click(element)

    def right_click(self, timeout: int = 10, **kwargs):
        """鼠标右键点击元素。"""
        element = self.find_element(timeout=timeout, **kwargs)
        logger.info(f"鼠标右键点击元素: {kwargs}")
        self.mouse_right_click(element)

    def input_text(self, text: str, timeout: int = 10, **kwargs):
        """鼠标点击后输入文本。"""
        element = self.find_element(timeout=timeout, **kwargs)
        logger.info(f"鼠标点击并输入文本: {kwargs}")
        self.mouse_type(element, text)

    def type_keys(self, keys: str, timeout: int = 10, **kwargs):
        """鼠标点击元素后发送按键。"""
        element = self.find_element(timeout=timeout, **kwargs)
        logger.info(f"鼠标点击后按键 '{keys}': {kwargs}")
        self.mouse_click(element)
        time.sleep(0.1)
        self._send_keys(keys)

    def _send_keys(self, keys: str):
        """发送常用快捷键/按键。"""
        ui_input.send_key_sequence(keys)

    # ─── 元素状态 ──────────────────────────────────────────────────────

    def is_visible(self, **kwargs) -> bool:
        """检查元素是否可见。"""
        try:
            ctrl = self.window.child_window(**kwargs)
            return ctrl.is_visible()
        except Exception:
            return False

    def is_enabled(self, **kwargs) -> bool:
        """检查元素是否可用。"""
        try:
            ctrl = self.window.child_window(**kwargs)
            return ctrl.is_enabled()
        except Exception:
            return False

    def get_text(self, timeout: int = 10, **kwargs) -> str:
        """获取元素的文本内容。"""
        element = self.find_element(timeout=timeout, **kwargs)
        return element.window_text()

    # ─── 等待辅助 ──────────────────────────────────────────────────────

    def wait_until_visible(self, timeout: int = 10, **kwargs):
        """等待元素变为可见。"""
        logger.debug(f"Waiting for element to be visible: {kwargs}")
        ctrl = self.window.child_window(**kwargs)
        ctrl.wait("exists visible", timeout=timeout)
        return ctrl

    def wait_until_gone(self, timeout: int = 10, **kwargs):
        """等待元素消失。"""
        logger.debug(f"Waiting for element to disappear: {kwargs}")
        ctrl = self.window.child_window(**kwargs)
        ctrl.wait_not("exists", timeout=timeout)

    # ─── 弹出菜单操作 ──────────────────────────────────────────────────

    def _connect_popup_window(self, handle: int):
        popup_app = Application(backend="uia").connect(handle=handle)
        return popup_app.window(handle=handle)

    def _iter_popup_roots(self):
        """枚举可能承载菜单项的根：主窗口、QMenu、Qt5QWindowPopup 弹出窗。"""
        roots = [self.window]
        seen = {self.window.handle}
        pid = self.app.process

        try:
            menu = self.window.child_window(control_type="Menu")
            if menu.exists(timeout=0):
                roots.append(menu)
        except Exception:
            pass

        try:
            for info in find_elements(
                backend="uia", process=pid, top_level_only=True
            ):
                if info.handle in seen:
                    continue
                cls = (info.class_name or "").strip()
                if not any(m in cls for m in _QT_POPUP_CLASS_MARKERS):
                    continue
                seen.add(info.handle)
                try:
                    roots.append(self._connect_popup_window(info.handle))
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"枚举 Qt 弹出窗失败: {e}")

        for top_level_only in (True, False):
            try:
                popups = find_elements(
                    backend="uia",
                    process=pid,
                    class_name="QMenu",
                    top_level_only=top_level_only,
                )
                for popup in popups:
                    if popup.handle in seen:
                        continue
                    seen.add(popup.handle)
                    try:
                        roots.append(self._connect_popup_window(popup.handle))
                    except Exception:
                        continue
            except Exception:
                continue

        return roots

    def _get_popup_menu(self, timeout: int = 5):
        """获取当前进程的弹出菜单（QMenu 或 Qt5QWindowPopup）。"""
        pid = self.app.process
        end = time.time() + timeout
        last_error = None

        while time.time() < end:
            for root in self._iter_popup_roots():
                if root is self.window:
                    continue
                try:
                    for elem in root.descendants(control_type="MenuItem"):
                        if elem.is_visible():
                            logger.debug(
                                f"弹出菜单: handle={root.handle}, "
                                f"class={root.class_name()}"
                            )
                            return root
                except Exception as e:
                    last_error = e

            for root in self._iter_popup_roots():
                if root is not self.window:
                    logger.debug(
                        f"弹出窗(无 MenuItem 扫描): handle={root.handle}"
                    )
                    return root

            time.sleep(0.3)

        raise TimeoutError(f"弹出菜单未出现 (pid={pid}, last_error={last_error})")

    def _match_popup_element(self, elem, kwargs: dict) -> bool:
        """判断控件是否匹配 child_window 条件。"""
        title = kwargs.get("title")
        if title is not None:
            text = (elem.window_text() or "").strip()
            if text != title and title not in text:
                return False
        ctrl_type = kwargs.get("control_type")
        if ctrl_type is not None:
            try:
                if (elem.element_info.control_type or "") != ctrl_type:
                    return False
            except Exception:
                return False
        class_name = kwargs.get("class_name")
        if class_name is not None:
            try:
                if (elem.class_name() or "") != class_name:
                    return False
            except Exception:
                return False
        return True

    def find_popup_element(self, timeout: int = 5, **kwargs):
        """在弹出菜单中查找子元素（含 Qt 弹出窗内 MenuItem / QWidgetAction）。"""
        logger.debug(f"在弹出菜单中查找元素: {kwargs}")
        end = time.time() + timeout
        last_error = None

        while time.time() < end:
            for root in self._iter_popup_roots():
                try:
                    ctrl = root.child_window(**kwargs)
                    if ctrl.exists(timeout=0):
                        ctrl.wait("exists visible", timeout=1)
                        return ctrl
                except Exception as e:
                    last_error = e

                try:
                    for elem in root.descendants():
                        try:
                            if not elem.is_visible():
                                continue
                            if self._match_popup_element(elem, kwargs):
                                logger.debug(
                                    f"在弹出层扫描到菜单项: "
                                    f"{elem.window_text()!r}"
                                )
                                return elem
                        except Exception:
                            continue
                except Exception as e:
                    last_error = e

            time.sleep(0.3)

        raise TimeoutError(f"菜单项未出现: {kwargs}, last_error={last_error}")

    def click_popup_item(self, timeout: int = 5, **kwargs):
        """点击弹出菜单中的元素（优先 Invoke）。"""
        element = self.find_popup_element(timeout=timeout, **kwargs)
        logger.info(f"点击菜单项: {kwargs}")
        try:
            element.invoke()
            time.sleep(0.3)
            return
        except Exception as e:
            logger.debug(f"菜单项 Invoke 失败，改用鼠标: {e}")
        self.mouse_click(element)

    def is_popup_visible(self, **kwargs) -> bool:
        """检查弹出菜单中的元素是否可见。"""
        try:
            self.find_popup_element(timeout=2, **kwargs)
            return True
        except Exception:
            return False

    # ─── PyAutoGUI 辅助（图像/坐标定位）───────────────────────────────

    def click_by_image(self, image_path: str, confidence: float = 0.9, timeout: int = 10):
        """通过图像模板匹配点击屏幕位置。"""
        logger.info(f"Clicking by image: {image_path}")
        end_time = time.time() + timeout
        location = None

        while time.time() < end_time:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                break
            time.sleep(0.5)

        if location is None:
            raise TimeoutError(f"Image not found on screen: {image_path}")

        center = pyautogui.center(location)
        pyautogui.click(center)
        logger.info(f"Clicked at {center}")

    def click_by_position(self, x: int, y: int):
        """点击屏幕绝对坐标。"""
        logger.info(f"Clicking at position ({x}, {y})")
        pyautogui.click(x, y)

    # ─── 窗口操作 ──────────────────────────────────────────────────────

    def maximize_window(self):
        """最大化当前窗口。"""
        self.window.maximize()

    def minimize_window(self):
        """最小化当前窗口。"""
        self.window.minimize()

    def restore_window(self):
        """还原当前窗口。"""
        self.window.restore()

    def close_window(self):
        """关闭当前窗口。"""
        self.window.close()
