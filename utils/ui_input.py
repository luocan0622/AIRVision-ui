"""UI 输入模拟底层工具。

提供所有鼠标点击、键盘输入、剪贴板操作、窗口激活的原子操作。
所有方法通过屏幕坐标驱动，是 BasePage 鼠标/键盘操作的最终实现层。

层级关系：BasePage → ui_input → pyautogui / pywinauto / win32gui
"""
import time

import pyautogui
import pyperclip
import win32con
import win32gui
from pywinauto.keyboard import SendKeys as send_keys

from utils.logger import logger

# 模拟用户操作时的全局鼠标/键盘间隔（秒），避免操作过快导致 UI 无响应
pyautogui.PAUSE = 0.05

_KEY_SHORTCUTS = {
    "%d": ("alt", "d"),
    "^a": ("ctrl", "a"),
    "{ENTER}": ("enter",),
    "{ESC}": ("esc",),
}


def element_center(element) -> tuple[int, int]:
    """获取控件中心点屏幕坐标。"""
    rect = element.rectangle()
    return (rect.left + rect.width() // 2, rect.top + rect.height() // 2)


def mouse_click(element, clicks: int = 1, button: str = "left"):
    """在控件中心模拟鼠标点击。"""
    x, y = element_center(element)
    logger.debug(f"鼠标点击 ({x}, {y}), button={button}, clicks={clicks}")
    pyautogui.click(x=x, y=y, clicks=clicks, button=button)
    time.sleep(0.1)


def mouse_double_click(element):
    """在控件中心模拟鼠标双击。"""
    mouse_click(element, clicks=2)


def mouse_right_click(element):
    """在控件中心模拟鼠标右键。"""
    mouse_click(element, button="right")


def mouse_type(element, text: str, clear: bool = True):
    """先鼠标点击控件聚焦，再模拟键盘输入。"""
    mouse_click(element)
    time.sleep(0.15)
    if clear:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
    pyautogui.write(text, interval=0.03)
    time.sleep(0.1)


def mouse_type_filename(edit, text: str):
    """文件对话框文件名框：鼠标点击 → 全选 → send_keys 键入。"""
    x, y = element_center(edit)
    logger.info(f"鼠标点击文件名框 ({x}, {y})，键入: {text!r}")
    pyautogui.click(x=x, y=y)
    time.sleep(0.3)
    pyautogui.click(x=x, y=y, clicks=3)
    time.sleep(0.15)
    send_keys("^a{BACKSPACE}", pause=0.03, with_spaces=True)
    send_keys(text, pause=0.04, with_spaces=True)
    time.sleep(0.3)


def read_edit_via_clipboard(edit) -> str:
    """鼠标聚焦编辑框后 Ctrl+C 读取当前文本。"""
    x, y = element_center(edit)
    pyautogui.click(x=x, y=y)
    time.sleep(0.15)
    pyautogui.click(x=x, y=y, clicks=3)
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.15)
    return (pyperclip.paste() or "").strip()


def activate_dialog(dlg):
    """将对话框置于前台并获取焦点。"""
    try:
        hwnd = dlg.handle
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        logger.debug(f"SetForegroundWindow 失败: {e}")
    try:
        dlg.set_focus()
    except Exception:
        pass
    time.sleep(0.25)


def press_key(key: str):
    """模拟按下单个键（如 enter、esc）。"""
    pyautogui.press(key)
    time.sleep(0.1)


def send_key_sequence(keys: str):
    """发送常用快捷键/按键。"""
    combo = _KEY_SHORTCUTS.get(keys)
    if combo:
        if len(combo) == 1:
            pyautogui.press(combo[0])
        else:
            pyautogui.hotkey(*combo)
    else:
        pyautogui.write(keys, interval=0.02)
    time.sleep(0.1)


def clear_edit_field():
    """全选并清空当前聚焦的编辑框（pyautogui，部分 Win32 对话框不可靠）。"""
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)
    pyautogui.press("backspace")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    time.sleep(0.1)


def focus_file_dialog_address_bar():
    """Alt+D 聚焦 Windows 文件对话框地址栏（标准快捷键，通常会全选路径）。"""
    send_keys("%d", pause=0.3, with_spaces=True)
    time.sleep(0.35)


def select_all_clear_and_type(text: str):
    """用 pywinauto SendKeys 全选、清空并键入（直接发给焦点窗口，比 pyautogui 可靠）。"""
    send_keys("^a", pause=0.08, with_spaces=True)
    send_keys("{BACKSPACE}", pause=0.08, with_spaces=True)
    send_keys(text, pause=0.04, with_spaces=True, turn_off_numlock=False)
    time.sleep(0.35)


def select_all_and_paste(text: str):
    """全选后通过剪贴板粘贴（适合含中文或特殊字符的路径）。"""
    pyperclip.copy(text)
    send_keys("^a", pause=0.08, with_spaces=True)
    send_keys("^v", pause=0.08, with_spaces=True)
    time.sleep(0.35)


def confirm_address_bar():
    """地址栏输入路径后按 Enter 确认跳转（必须用 SendKeys 发给对话框）。"""
    send_keys("{ENTER}", pause=0.15, with_spaces=True)
    time.sleep(0.5)


def paste_text(text: str):
    """向已聚焦的编辑框粘贴文本（优先 SendKeys，回退 pyautogui）。"""
    pyperclip.copy(text)
    send_keys("^v", pause=0.08, with_spaces=True)
    time.sleep(0.25)
