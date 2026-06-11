"""pytest 配置：fixture 与会话级应用生命周期管理。

提供：
- ``config`` fixture：会话级配置加载（config.yaml）
- ``app_manager`` fixture：应用启动/连接/关闭
- ``app`` fixture：每个测试函数的 Application 实例
- ``page`` / ``page_esc`` / ``clean_page``：MainPage 及常用前置/收尾
- Airtest 风格步骤报告：每步自动截图，生成 ``reports/airtest/`` 下 HTML 报告
- ``pytest_runtest_makereport`` hook：失败自动截图并嵌入 pytest-html 报告
"""
import time
from pathlib import Path

import pytest
from pywinauto.keyboard import SendKeys

from pages.main_page import MainPage
from utils.airtest_report import generate_report, generate_session_index
from utils.app_manager import AppManager
from utils.config import load_config
from utils.screenshot import take_screenshot
from utils.logger import logger
from utils.step_reporter import get_reporter


_session_reports: list[dict] = []


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


@pytest.fixture(scope="function")
def page(app):
    """为每个测试函数提供 MainPage 页面对象。"""
    return MainPage(app)


@pytest.fixture(scope="function")
def page_esc(page):
    """MainPage；测试结束后按 ESC 关闭残留弹层/菜单。"""
    yield page
    SendKeys("{ESC}")
    time.sleep(0.3)


@pytest.fixture(scope="function")
def clean_page(page):
    """MainPage + prepare_clean_state（关闭残留项目/弹窗）。"""
    page.prepare_clean_state()
    return page


@pytest.fixture(scope="function")
def clean_page_esc(clean_page):
    """clean_page + 测试结束后按 ESC 关闭残留弹层/菜单。"""
    yield clean_page
    SendKeys("{ESC}")
    time.sleep(0.3)


@pytest.fixture(autouse=True)
def _step_reporter_context(request):
    """每个测试开始前初始化步骤记录器。"""
    reporter = get_reporter()
    script_name = Path(request.node.fspath).name
    reporter.start_test(test_id=request.node.nodeid, script_name=script_name)
    yield reporter


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """测试失败时截图；生成 Airtest 风格 HTML 报告；附加失败截图到 pytest-html。"""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    reporter = get_reporter()

    if report.passed:
        reporter.finish_test("passed")
    elif report.skipped:
        reporter.finish_test("skipped")
    else:
        reporter.finish_test("failed")
        try:
            test_name = item.nodeid.replace("::", "_").replace("/", "_")
            screenshot_path = take_screenshot(name=f"FAIL_{test_name}")
            if screenshot_path:
                logger.error(f"Test failed - screenshot: {screenshot_path}")
                shot = Path(screenshot_path)
                reporter.add_step(
                    title="测试失败",
                    action="test_failure",
                    status="failed",
                    screenshot_path=screenshot_path,
                    error=str(report.longrepr) if report.longrepr else "",
                )

                html_plugin = item.config.pluginmanager.getplugin("html")
                if html_plugin is not None:
                    from pytest_html import extras

                    report.extras = getattr(report, "extras", [])
                    report.extras.append(extras.image(str(shot)))
                    report.extras.append(
                        extras.html(
                            f'<p><b>失败截图：</b>'
                            f'<a href="../screenshots/{shot.name}">{shot.name}</a></p>'
                        )
                    )
        except Exception as e:
            logger.warning(f"Could not attach failure screenshot to report: {e}")

    report_path = generate_report(reporter)
    if report_path is not None:
        data = reporter.to_dict()
        data["report_path"] = str(report_path)
        _session_reports.append(data)


def pytest_sessionfinish(session, exitstatus):
    """会话结束时生成汇总索引页。"""
    if _session_reports:
        index_path = generate_session_index(_session_reports)
        if index_path:
            logger.info(f"Airtest session index: {index_path}")
