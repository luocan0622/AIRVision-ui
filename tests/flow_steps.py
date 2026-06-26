"""共享测试流程步骤：日志、断言与常用业务串联。"""
import os
import re
import time
from typing import Any, Callable, Optional, Tuple, TypeVar

from pages.main_page import MainPage
from utils.logger import logger
from utils.step_reporter import execute_step

T = TypeVar("T")


def log_step(step: int, total: int, message: str) -> None:
    logger.info(f"步骤 {step}/{total}: {message}")


def _log_step_message(
    message: str,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
) -> None:
    if step is not None and total is not None:
        log_step(step, total, message)
    else:
        logger.info(f"步骤: {message}")


def run_step(
    title: str,
    action: str,
    func: Callable[[], T],
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    args: Optional[dict[str, Any]] = None,
    pause: float = 0,
) -> T:
    """执行单步并记录日志、截图与报告元数据。"""
    _log_step_message(title, step=step, total=total)
    return execute_step(title, action, func, args=args, pause=pause)


def assert_app_ready(page: MainPage) -> None:
    window = page.app.top_window()
    assert window.exists(), "应用窗口应存在"
    assert window.is_visible(), "应用窗口应可见"
    logger.info("AIRVision 已就绪")


def prepare_workflow_canvas(page: MainPage) -> None:
    """确保已打开项目与工作流标签（画布工具测试前置）。"""

    def _do() -> None:
        page.mouse_press_key("esc")
        time.sleep(0.3)
        try:
            page.find_workflow_canvas(timeout=4, log_result=False)
            logger.info("已有工作流画布，跳过新建项目/工作流")
            return
        except RuntimeError:
            pass
        page.ensure_project_open()
        time.sleep(0.5)
        page.ensure_workflow_tab_open()
        time.sleep(0.5)

    run_step("准备工作流画布", "prepare_workflow_canvas", _do)


def step_new_project(
    page: MainPage,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> Tuple[str, str]:
    def _do() -> Tuple[str, str]:
        project_name = page.new_project()
        assert re.match(r"^test_\d+$", project_name, re.I)
        project_file = os.path.join(page.PROJECT_PATH, f"{project_name}.airvision")
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"
        return project_name, project_file

    return run_step("新建项目", "new_project", _do, step=step, total=total, pause=pause)


def step_set_default_template(
    page: MainPage,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 1.0,
) -> None:
    run_step(
        "设置默认模板图片",
        "set_default_template_image",
        lambda: page.set_default_template_image(),
        step=step,
        total=total,
        pause=pause,
    )


def step_save_project(
    page: MainPage,
    project_file: str,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> None:
    def _do() -> None:
        page.save_project()
        assert os.path.isfile(project_file), f"项目文件应存在: {project_file}"

    run_step(
        "保存项目",
        "save_project",
        _do,
        step=step,
        total=total,
        args={"project_file": project_file},
        pause=pause,
    )


def step_close_project(
    page: MainPage,
    *,
    save_changes: bool = True,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 1.0,
) -> None:
    run_step(
        "关闭项目",
        "close_project",
        lambda: page.close_project(save_changes=save_changes),
        step=step,
        total=total,
        args={"save_changes": save_changes},
        pause=pause,
    )


def step_open_project(
    page: MainPage,
    filename: str,
    *,
    path: str = None,
    title: str = None,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 1.0,
) -> None:
    display = title or "打开项目"
    kwargs = {"filename": filename}
    if path is not None:
        kwargs["path"] = path

    def _do() -> None:
        page.open_project(**kwargs)

    run_step(
        display,
        "open_project",
        _do,
        step=step,
        total=total,
        args=kwargs,
        pause=pause,
    )


def step_new_workflow(
    page: MainPage,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> str:
    def _do() -> str:
        initial_name = page.new_workflow()
        assert re.match(r"^Untitled-\d+$", initial_name, re.I)
        return initial_name

    return run_step(
        "新建 workflow", "new_workflow", _do, step=step, total=total, pause=pause
    )


def step_rename_workflow(
    page: MainPage,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
) -> str:
    def _do() -> str:
        workflow_name = page.rename_workflow()
        assert re.match(r"^test_\d+$", workflow_name, re.I)
        assert page.get_active_workflow_name() == workflow_name
        return workflow_name

    return run_step(
        "重命名 workflow", "rename_workflow", _do, step=step, total=total
    )


def step_add_filter_tool(
    page: MainPage,
    tool_key: str,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    timeout: int = 15,
    pause: float = 0.5,
):
    def _do():
        tool = page.add_workflow_tool(tool_key)
        assert tool.key == tool_key
        assert page.has_workflow_tool_node_for_key(
            tool_key, timeout=timeout
        ), f"画布上应出现 {tool_key} 工具节点"
        return tool

    return run_step(
        f"Filter 添加工具 ({tool_key})",
        "add_filter_tool",
        _do,
        step=step,
        total=total,
        args={"tool_key": tool_key},
        pause=pause,
    )


def step_save_workflow(
    page: MainPage,
    workflow_name: str,
    *,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> str:
    def _do() -> str:
        page.save_workflow(workflow_name)
        json_path = page.get_workflow_json_path(workflow_name)
        assert os.path.isfile(json_path), f"工作流文件应存在: {json_path}"
        return json_path

    return run_step(
        "保存 workflow",
        "save_workflow",
        _do,
        step=step,
        total=total,
        args={"workflow_name": workflow_name},
        pause=pause,
    )


def step_close_workflow(
    page: MainPage,
    *,
    workflow_name: str = None,
    save_changes: bool = True,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
    after_task: bool = False,
) -> None:
    title = (
        f"关闭 workflow ({workflow_name})"
        if workflow_name
        else "关闭 workflow"
    )

    def _do() -> None:
        page.close_workflow(
            workflow_name=workflow_name, save_changes=save_changes
        )
        if after_task:
            page.finish_task()

    run_step(
        title,
        "close_workflow",
        _do,
        step=step,
        total=total,
        args={
            "workflow_name": workflow_name,
            "save_changes": save_changes,
            "after_task": after_task,
        },
        pause=pause,
    )


def step_save_project_as(
    page: MainPage,
    *,
    path: str = None,
    filename: str = None,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> Tuple[str, str]:
    target_path = path or page.SAVE_AS_PROJECT_PATH

    def _do() -> Tuple[str, str]:
        save_as_name = filename or page.next_test_project_name(target_path)
        page.save_project_as(path=target_path, filename=save_as_name)
        save_as_file = os.path.join(target_path, f"{save_as_name}.airvision")
        assert os.path.isfile(save_as_file), f"另存为项目文件应存在: {save_as_file}"
        return save_as_name, save_as_file

    return run_step(
        "另存为项目 (Save Project As)",
        "save_project_as",
        _do,
        step=step,
        total=total,
        args={"path": target_path},
        pause=pause,
    )


def step_build_circle_workpiece_pipeline(page: MainPage, *, verify: bool = True):
    """搭建圆形工件检测流水线（布局 + 放置，不含连线）。"""

    def _do():
        return page.build_circle_workpiece_detection(
            connect=False, verify_nodes=verify
        )

    return run_step(
        "搭建圆形工件检测流程",
        "build_circle_workpiece_detection",
        _do,
        args={"verify": verify},
        pause=0.5,
    )


def step_build_workflow_pipeline(
    page: MainPage,
    tool_keys: list[str],
    *,
    connect: bool = True,
    verify: bool = True,
):
    def _do():
        return page.build_workflow_pipeline(
            tool_keys, connect=connect, verify_nodes=verify
        )

    return run_step(
        "搭建流水线",
        "build_workflow_pipeline",
        _do,
        args={"tool_keys": tool_keys, "connect": connect, "verify": verify},
    )


def step_open_workflow(
    page: MainPage,
    filename: str,
    *,
    path: str = None,
    expected_name: str = None,
    title: str = None,
    step: Optional[int] = None,
    total: Optional[int] = None,
    pause: float = 0.5,
) -> str:
    display = title or f"打开 workflow ({filename})"
    kwargs = {"filename": filename}
    if path is not None:
        kwargs["path"] = path

    def _do() -> str:
        opened_name = page.open_workflow(**kwargs)
        if expected_name is not None:
            assert opened_name == expected_name
            assert page.get_active_workflow_name() == expected_name
        return opened_name

    return run_step(
        display,
        "open_workflow",
        _do,
        step=step,
        total=total,
        args={**kwargs, "expected_name": expected_name},
        pause=pause,
    )
