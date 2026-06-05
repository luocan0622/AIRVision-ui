"""pytest 配置：fixture 与会话级应用生命周期管理。

提供：
- ``config`` fixture：会话级配置加载（config.yaml）
- ``app_manager`` fixture：应用启动/连接/关闭
- ``app`` fixture：每个测试函数的 Application 实例
- ``pytest_runtest_makereport`` hook：失败自动截图
"""
import pytest

from utils.app_manager import AppManager
from utils.config import load_config
from utils.screenshot import take_screenshot
from utils.logger import logger


@pytest.fixture(scope="session")
def config():
    """提供会话级别的测试配置 fixture。"""
    return load_config()


@pytest.fixture(scope="session")
def app_manager(config):
    """测试会话级应用生命周期：启动前检测是否已打开，测试结束后保持窗口（可配置关闭）。"""
    app_cfg = config["app"]
    window_title = app_cfg.get("title", "MainWindow")
    close_on_finish = app_cfg.get("close_on_finish", False)
    manager = AppManager(
        app_path=app_cfg["path"],
        backend=app_cfg["backend"],
        timeout=app_cfg["timeout"],
    )
    manager.start_or_connect(window_title=window_title)
    yield manager
    if close_on_finish:
        manager.close()
    else:
        logger.info("测试结束，保持应用窗口打开（app.close_on_finish=false）")


@pytest.fixture(scope="function")
def app(app_manager):
    """为每个测试函数提供 pywinauto Application 实例。"""
    return app_manager.app


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """测试失败时自动截图。"""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        try:
            test_name = item.nodeid.replace("::", "_").replace("/", "_")
            screenshot_path = take_screenshot(name=f"FAIL_{test_name}")
            if screenshot_path:
                logger.error(f"Test failed - screenshot: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Could not take failure screenshot: {e}")
