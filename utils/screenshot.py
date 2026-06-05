"""截图工具：全屏截图并保存到 screenshots/ 目录。"""
import os
import time
from datetime import datetime

import pyautogui
from utils.logger import logger


SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def take_screenshot(name: str = None) -> str:
    """截取屏幕并保存到 screenshots 目录。

    Args:
        name: 可选的截图文件名。

    Returns:
        保存的截图完整路径。
    """
    if name is None:
        name = datetime.now().strftime("%Y%m%d_%H%M%S")
    else:
        # 清理文件名中的特殊字符
        name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")

    filename = f"{name}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        logger.info(f"Screenshot saved: {filepath}")
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        filepath = ""

    return filepath
