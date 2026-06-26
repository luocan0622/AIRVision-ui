"""MainPage 通用任务收尾与测试前置清理。"""
import time

from utils.logger import logger


class CommonMixin:
    """任务结束 OK 处理、全流程前置清理。"""

    def finish_task(self) -> None:
        """每个任务结束后：有 OK 就点 OK，没有则等待 1 秒。"""
        self.dismiss_ok_or_wait(wait_if_absent=1.0)

    def _after_task(self) -> None:
        """兼容旧调用，请改用 finish_task()。"""
        self.finish_task()

    def _is_project_open(self) -> bool:
        try:
            return bool(self._read_project_path_label().strip())
        except Exception:
            return False

    def _ensure_project_closed(self, timeout: float = 15) -> None:
        """全流程开始前确保无打开项目（含未保存提示）。"""
        if not self._is_project_open():
            return

        logger.info("检测到已打开项目，先关闭再开始")
        self.close_project(save_changes=False)
        end = time.time() + timeout
        while time.time() < end:
            if not self._is_project_open():
                return
            self.dismiss_unsaved_changes_if_present(timeout=1)
            self.dismiss_ok_or_wait(wait_if_absent=0.3)
            self.mouse_press_key("esc")
            time.sleep(0.5)

        raise RuntimeError(f"无法在 {timeout}s 内关闭已打开的项目")

    def prepare_clean_state(self):
        """全流程测试前置：关闭残留弹窗、取消未完成的保存确认、关闭已打开项目。"""
        self.mouse_press_key("esc")
        time.sleep(0.3)
        self.cancel_open_file_dialogs(timeout=1)
        self.cancel_template_images_dialog(timeout=1)
        self.cancel_overwrite_if_present(timeout=1)
        self.cancel_new_project_dialog(timeout=0.5)
        self.dismiss_unsaved_changes_if_present(timeout=1)
        self.dismiss_ok_or_wait(wait_if_absent=0.3)
        self._ensure_project_closed(timeout=15)
        self.mouse_press_key("esc")
        time.sleep(0.3)

    def ensure_project_open(self, create_if_missing: bool = True) -> str:
        """确保已有打开的项目；无项目且允许时则新建。"""
        self.mouse_press_key("esc")
        time.sleep(0.2)
        try:
            label = self._read_project_path_label()
            if label:
                logger.info(f"已有打开项目，跳过新建: {label!r}")
                return label
        except Exception:
            pass
        if not create_if_missing:
            raise RuntimeError("未打开项目且 create_if_missing=False")
        return self.new_project()

    def ensure_workflow_tab_open(self) -> str:
        """确保存在活动工作流标签；无则新建。"""
        try:
            return self.get_active_workflow_name()
        except RuntimeError:
            logger.info("无活动工作流，执行 new_workflow()")
            return self.new_workflow()
