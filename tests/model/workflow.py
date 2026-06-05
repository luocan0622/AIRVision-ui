"""Workflows 菜单与工作流文件操作。"""
import os
import time

from pages.dialogs import DialogTitle
from tests.model.filter_menu import FilterMenuMixin
from tests.model.locators import (
    TEST_WORKFLOW_NAME_PATTERN,
    WORKFLOW_FILE_EXT,
    WORKFLOW_NAME_PATTERN,
)
from utils.logger import logger
from utils.naming import collect_numbers_from_filenames, next_test_name, parse_test_number


class WorkflowMixin(FilterMenuMixin):
    """Workflows：新建 / 保存 / 打开 / 重命名；画布添加工具见 FilterMenuMixin。"""

    WORKFLOWS_NEW = {"title": "New", "control_type": "MenuItem"}
    WORKFLOWS_OPEN = {"title": "Open", "control_type": "MenuItem"}
    WORKFLOWS_SAVE = {"title": "Save", "control_type": "MenuItem"}
    WORKFLOWS_CLEAR = {"title": "Clear", "control_type": "MenuItem"}
    WORKFLOWS_CLOSE = {"title": "Close", "control_type": "MenuItem"}
    WORKFLOWS_RENAME = {"title": "Rename", "control_type": "MenuItem"}

    WORKFLOW_NAME_PATTERN = WORKFLOW_NAME_PATTERN
    TEST_WORKFLOW_NAME_PATTERN = TEST_WORKFLOW_NAME_PATTERN

    def get_active_workflow_name(self) -> str:
        try:
            for elem in self.window.descendants(class_name="QTabBar"):
                name = (elem.window_text() or "").strip()
                if name:
                    return name
        except Exception as e:
            logger.debug(f"读取 QTabBar 失败: {e}")

        try:
            for elem in self.window.descendants(control_type="TabItem"):
                try:
                    if elem.is_selected():
                        name = (elem.window_text() or "").strip()
                        if name:
                            return name
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"读取选中 TabItem 失败: {e}")

        patterns = (self.TEST_WORKFLOW_NAME_PATTERN, self.WORKFLOW_NAME_PATTERN)
        candidates = []
        try:
            for elem in self.window.descendants(control_type="TabItem"):
                try:
                    name = (elem.window_text() or "").strip()
                except Exception:
                    continue
                if any(p.match(name) for p in patterns):
                    candidates.append(name)
        except Exception as e:
            logger.debug(f"扫描工作流 TabItem 失败: {e}")

        if candidates:
            return candidates[-1]
        raise RuntimeError("未找到当前工作流名称")

    @staticmethod
    def _workflow_save_filename(workflow_name: str) -> str:
        name = workflow_name.strip()
        if not name.lower().endswith(".json"):
            name = f"{name}.json"
        return name

    def is_save_workflow_dialog_open(self, timeout: int = 2) -> bool:
        return self._is_save_workflow_dialog_visible(timeout)

    def get_workflow_json_path(
        self, workflow_name: str = None, workflows_dir: str = None
    ) -> str:
        directory = workflows_dir or self.get_workflows_directory()
        name = workflow_name or self.get_active_workflow_name()
        return os.path.join(directory, self._workflow_save_filename(name))

    def is_workflow_saved(self, workflow_name: str = None, workflows_dir: str = None) -> bool:
        return os.path.isfile(self.get_workflow_json_path(workflow_name, workflows_dir))

    def _is_save_workflow_dialog_visible(self, timeout: int = 2) -> bool:
        try:
            self.get_window_by_title(DialogTitle.SAVE_WORKFLOW, timeout=timeout)
            return True
        except TimeoutError:
            return False

    def new_workflow(self) -> str:
        logger.info("新建工作流")
        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_NEW)
        time.sleep(0.8)
        name = self.get_active_workflow_name()
        logger.info(f"已新建工作流: {name}")
        self._after_task()
        return name

    def save_workflow(self, workflow_name: str = None, confirm: bool = True):
        workflows_dir = self.get_workflows_directory()
        name = workflow_name or self.get_active_workflow_name()
        filename = self._workflow_save_filename(name)
        already_saved = self.is_workflow_saved(name, workflows_dir)

        logger.info(
            f"保存工作流: name={name}, file={filename}, "
            f"dir={workflows_dir}, already_saved={already_saved}"
        )

        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_SAVE)
        time.sleep(0.8)

        if already_saved:
            if self._is_save_workflow_dialog_visible(timeout=2):
                logger.warning("工作流已存在但仍弹出保存对话框，按首次保存处理")
                self.handle_file_dialog(
                    dialog_title=DialogTitle.SAVE_WORKFLOW,
                    path=workflows_dir,
                    filename=filename,
                    confirm=confirm,
                )
            else:
                logger.info(f"工作流 {name!r} 已保存，直接覆盖，未打开保存对话框")
            self._after_task()
            return

        self.handle_file_dialog(
            dialog_title=DialogTitle.SAVE_WORKFLOW,
            path=workflows_dir,
            filename=filename,
            confirm=confirm,
        )
        self._after_task()

    def open_workflow(
        self,
        path: str = None,
        filename: str = None,
        confirm: bool = True,
    ) -> str:
        workflows_dir = path or self.get_workflows_directory()
        target_file = filename or self.DEFAULT_WORKFLOW_FILENAME
        if not target_file.lower().endswith(".json"):
            target_file = f"{target_file}{WORKFLOW_FILE_EXT}"

        logger.info(f"打开工作流: path={workflows_dir}, filename={target_file}")
        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_OPEN)
        time.sleep(0.8)

        self.handle_image_file_dialog(
            dialog_title=DialogTitle.OPEN_WORKFLOW,
            path=workflows_dir,
            filename=target_file,
            confirm=confirm,
        )

        time.sleep(0.5)
        workflow_name = os.path.splitext(target_file)[0]
        logger.info(f"已打开工作流: {workflow_name!r}")
        self._after_task()
        return workflow_name

    def close_workflow(self):
        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_CLOSE)

    def clear_workflow(self):
        logger.info("清空工作流")
        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_CLEAR)
        time.sleep(0.5)

    def _collect_test_workflow_numbers(self) -> list[int]:
        numbers = collect_numbers_from_filenames(
            self.get_workflows_directory(),
            file_suffix=".json",
        )
        try:
            for elem in self.window.descendants(control_type="TabItem"):
                try:
                    name = (elem.window_text() or "").strip()
                except Exception:
                    continue
                num = parse_test_number(name)
                if num is not None:
                    numbers.append(num)
        except Exception as e:
            logger.debug(f"扫描 test_数字 工作流标签失败: {e}")
        return numbers

    def next_test_workflow_name(self) -> str:
        return next_test_name(self._collect_test_workflow_numbers())

    def _find_rename_display_name_edit(self, dlg):
        for kwargs in (
            {"class_name": "QLineEdit"},
            {"control_type": "Edit"},
        ):
            try:
                for edit in dlg.descendants(**kwargs):
                    if edit.is_visible():
                        return edit
            except Exception as e:
                logger.debug(f"查找 Rename 输入框失败: {e}")
        raise RuntimeError("[Rename Workflow] 未找到 Display name 输入框")

    def _type_rename_display_name(self, edit, new_name: str):
        self.mouse_click(edit)
        time.sleep(0.2)
        self._send_keys("^a")
        self._send_keys(new_name)
        time.sleep(0.15)

    def _handle_rename_workflow_dialog(
        self, new_name: str, confirm: bool = True, timeout: int = 10
    ):
        dialog_title = DialogTitle.RENAME_WORKFLOW
        dlg = self.get_window_by_title(dialog_title, timeout=timeout)
        edit = self._find_rename_display_name_edit(dlg)
        self._type_rename_display_name(edit, new_name)
        if confirm:
            btn = self._find_dialog_button(dlg, ("OK", "确定"))
            if btn is None:
                raise RuntimeError(f"[{dialog_title}] 未找到 OK 按钮")
            logger.info(f"[{dialog_title}] 鼠标点击确认按钮: {btn.window_text()!r}")
            self.mouse_click(btn)
            time.sleep(0.5)

    def rename_workflow(self, new_name: str = None, confirm: bool = True) -> str:
        name = (new_name or self.next_test_workflow_name()).strip()
        if not self.TEST_WORKFLOW_NAME_PATTERN.match(name):
            raise ValueError(f"工作流重命名须符合 test_数字 规则，实际: {name!r}")

        old_name = self.get_active_workflow_name()
        logger.info(f"重命名工作流: {old_name!r} -> {name!r}")

        self.click_workflows()
        self.click_popup_item(**self.WORKFLOWS_RENAME)
        time.sleep(0.5)
        self._handle_rename_workflow_dialog(name, confirm=confirm)
        time.sleep(0.5)

        active = self.get_active_workflow_name()
        if active != name:
            logger.warning(
                f"重命名后标签名与预期不一致: expected={name!r}, actual={active!r}"
            )
        logger.info(f"工作流已重命名为: {active!r}")
        self._after_task()
        return name
