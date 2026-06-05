"""Projects 菜单与项目文件操作。"""
import os
import time

from pages.dialogs import DialogTitle
from tests.model.locators import (
    PROJECT_FILE_RE,
    TEST_PATHS,
    TEST_PROJECT_NAME_PATTERN,
    WORKFLOWS_SUBDIR,
)
from utils.logger import logger
from utils.naming import collect_numbers_from_filenames, next_test_name, parse_test_number


class ProjectMixin:
    """Projects 菜单：新建、打开、保存、模板图、路径解析。"""

    PROJECT_PATH = TEST_PATHS["project"]
    SAVE_AS_PROJECT_PATH = TEST_PATHS["save_as_project"]
    TEMPLATE_IMAGE_PATH = TEST_PATHS["template_images"]
    DEFAULT_TEMPLATE_IMAGE = TEST_PATHS["default_template_image"]
    DEFAULT_DEPTH_IMAGE = TEST_PATHS["default_depth_image"]
    DEFAULT_WORKFLOW_FILENAME = TEST_PATHS["default_workflow_filename"]

    MENU_NEW_PROJECT = {"title": "New Project", "control_type": "MenuItem"}
    MENU_OPEN_PROJECT = {"title": "Open Project", "control_type": "MenuItem"}
    MENU_SAVE_PROJECT = {"title": "Save Project", "control_type": "MenuItem"}
    MENU_SAVE_PROJECT_AS = {"title": "Save Project As...", "control_type": "MenuItem"}
    MENU_SET_DEFAULT_TEMPLATE = {
        "title": "Set Default Template Image...",
        "control_type": "MenuItem",
    }
    MENU_CLOSE_PROJECT = {"title": "Close Project", "control_type": "MenuItem"}

    BTN_BROWSE_TEMPLATE = {
        "auto_id": "MainWindow.TemplateImageDialog.groupBoxTemplate.pushButtonBrowseTemplate",
        "control_type": "Button",
    }
    BTN_BROWSE_DEPTH = {
        "auto_id": "MainWindow.TemplateImageDialog.groupBoxDepth.pushButtonBrowseDepth",
        "control_type": "Button",
    }
    BTN_TEMPLATE_DIALOG_OK = {"title": "OK", "control_type": "Button"}

    TEST_PROJECT_NAME_PATTERN = TEST_PROJECT_NAME_PATTERN
    PROJECT_FILE_RE = PROJECT_FILE_RE
    WORKFLOWS_SUBDIR = WORKFLOWS_SUBDIR

    def _read_project_path_label(self) -> str:
        """读取标题栏项目路径文本（可能被 UI 截断显示省略号）。"""
        elem = self.find_element(**self.LBL_PROJECT_PATH)
        for value in (
            elem.window_text(),
            getattr(elem.element_info, "name", "") or "",
        ):
            text = (value or "").strip().replace("/", os.sep)
            if text:
                return text
        return ""

    def _resolve_project_paths(self) -> tuple[str, str, str]:
        """解析项目路径，返回 (项目目录, 项目名, .airvision 完整路径)。"""
        label = self._read_project_path_label()
        if not label:
            raise RuntimeError("未打开项目，标题栏项目路径为空")

        truncated = ("…" in label) or ("..." in label)
        normalized = label.replace("…", "").replace("...", "")

        if not truncated and normalized.lower().endswith(".airvision"):
            if os.path.isfile(normalized):
                project_dir = os.path.dirname(normalized)
                stem = os.path.splitext(os.path.basename(normalized))[0]
                return project_dir, stem, normalized
            parent = os.path.dirname(normalized)
            if parent and os.path.isdir(parent):
                stem = os.path.splitext(os.path.basename(normalized))[0]
                return parent, stem, normalized

        match = self.PROJECT_FILE_RE.search(label)
        if not match:
            raise RuntimeError(f"无法从项目路径标签解析项目文件: {label!r}")

        airvision_name = match.group(1)
        stem = os.path.splitext(airvision_name)[0]
        project_dir = self.PROJECT_PATH
        full_path = os.path.join(project_dir, airvision_name)
        logger.info(
            f"项目路径由标签还原: label={label!r} -> dir={project_dir}, file={full_path}"
        )
        return project_dir, stem, full_path

    def get_project_file_path(self) -> str:
        """获取当前打开的项目文件完整路径（.airvision）。"""
        return self._resolve_project_paths()[2]

    def get_workflows_directory(self, project_file_path: str = None) -> str:
        """根据当前项目推导工作流保存目录。"""
        if project_file_path:
            project_dir = os.path.dirname(project_file_path)
            project_stem = os.path.splitext(os.path.basename(project_file_path))[0]
        else:
            project_dir, project_stem, _ = self._resolve_project_paths()

        workflows_dir = os.path.join(
            project_dir, f"{project_stem}_data", self.WORKFLOWS_SUBDIR
        )
        os.makedirs(workflows_dir, exist_ok=True)
        logger.info(f"工作流目录: {workflows_dir}")
        return workflows_dir

    def _collect_test_project_numbers(self, project_dir: str = None) -> list[int]:
        directory = project_dir or self.PROJECT_PATH
        return collect_numbers_from_filenames(
            directory,
            file_suffix=".airvision",
            data_dir_suffix="_data",
        )

    def next_test_project_name(self, project_dir: str = None) -> str:
        return next_test_name(self._collect_test_project_numbers(project_dir))

    def find_existing_project_file(self, project_dir: str = None) -> str:
        directory = project_dir or self.PROJECT_PATH
        if not os.path.isdir(directory):
            raise RuntimeError(f"项目目录不存在: {directory}")

        files = sorted(
            name
            for name in os.listdir(directory)
            if name.lower().endswith(".airvision")
            and os.path.isfile(os.path.join(directory, name))
        )
        if not files:
            raise RuntimeError(
                f"目录下无 .airvision 项目文件: {directory}，请先 new_project()"
            )

        test_files = [
            name
            for name in files
            if self.TEST_PROJECT_NAME_PATTERN.match(os.path.splitext(name)[0])
        ]
        if test_files:
            return max(
                test_files,
                key=lambda name: parse_test_number(os.path.splitext(name)[0]) or 0,
            )
        return files[-1]

    def _dismiss_project_created_success(self, timeout: int = 10):
        if not self.dismiss_project_created_success(timeout=timeout):
            raise RuntimeError("[Success] 未找到 Success 提示框或 OK 按钮")

    def new_project(
        self, path: str = None, filename: str = None, confirm: bool = True
    ) -> str:
        target_path = path or self.PROJECT_PATH
        target_name = (filename or self.next_test_project_name(target_path)).strip()
        if not self.TEST_PROJECT_NAME_PATTERN.match(target_name):
            raise ValueError(f"项目名须符合 test_数字 规则，实际: {target_name!r}")

        logger.info(f"新建项目: path={target_path}, project_name={target_name}")
        self.click_projects()
        self.click_popup_item(**self.MENU_NEW_PROJECT)
        time.sleep(1)
        self.handle_new_project_dialog(
            path=target_path,
            project_name=target_name,
            confirm=confirm,
        )
        self._last_project_name = target_name
        logger.info(f"已新建项目: {target_name!r}")
        return target_name

    def open_project(self, path: str = None, filename: str = None, confirm: bool = True):
        target_path = path or self.PROJECT_PATH
        if filename:
            target_name = filename
            if not target_name.lower().endswith(".airvision"):
                target_name = f"{target_name}.airvision"
        elif self._last_project_name:
            target_name = f"{self._last_project_name}.airvision"
        else:
            target_name = self.find_existing_project_file(target_path)

        logger.info(f"打开项目: path={target_path}, filename={target_name}")
        self.click_projects()
        self.click_popup_item(**self.MENU_OPEN_PROJECT)
        time.sleep(1)
        self.handle_open_project_dialog(
            path=target_path,
            filename=target_name,
            confirm=confirm,
        )
        self._after_task()
        stem = os.path.splitext(target_name)[0]
        self._last_project_name = stem

    def save_project(self):
        self.click_projects()
        self.click_popup_item(**self.MENU_SAVE_PROJECT)
        self._after_task()

    def save_project_as(self, path: str = None, filename: str = None, confirm: bool = True):
        target_path = path or self.SAVE_AS_PROJECT_PATH
        target_name = filename or self.next_test_project_name(target_path)
        logger.info(f"另存为项目: path={target_path}, filename={target_name}")

        self.click_projects()
        self.click_popup_item(**self.MENU_SAVE_PROJECT_AS)
        time.sleep(1)
        self.handle_file_dialog(
            dialog_title=DialogTitle.SAVE_PROJECT_AS,
            path=target_path,
            filename=target_name,
            confirm=confirm,
        )
        self._after_task()

    def set_default_template_image(
        self,
        path: str = None,
        template_image: str = None,
        depth_image: str = None,
        confirm: bool = True,
    ):
        target_path = path or self.TEMPLATE_IMAGE_PATH
        template_name = template_image or self.DEFAULT_TEMPLATE_IMAGE
        depth_name = depth_image or self.DEFAULT_DEPTH_IMAGE
        logger.info(
            f"设置默认模板: path={target_path}, "
            f"template={template_name}, depth={depth_name}"
        )

        self.click_projects()
        self.click_popup_item(**self.MENU_SET_DEFAULT_TEMPLATE)
        time.sleep(1)
        self.get_window_by_title(DialogTitle.SELECT_TEMPLATE_IMAGES, timeout=10)

        logger.info("选择 Template Image")
        self.click(**self.BTN_BROWSE_TEMPLATE)
        time.sleep(0.8)
        self.handle_image_file_dialog(
            DialogTitle.SELECT_TEMPLATE_IMAGE,
            path=target_path,
            filename=template_name,
        )
        time.sleep(0.8)

        logger.info("选择 Depth Image")
        self.click(**self.BTN_BROWSE_DEPTH)
        time.sleep(0.8)
        self.handle_image_file_dialog(
            DialogTitle.SELECT_DEPTH_IMAGE,
            path=target_path,
            filename=depth_name,
        )
        time.sleep(0.5)

        if confirm:
            self.click_in_dialog(
                DialogTitle.SELECT_TEMPLATE_IMAGES,
                timeout=10,
                **self.BTN_TEMPLATE_DIALOG_OK,
            )
        self._after_task()

    def close_project(self):
        self.click_projects()
        self.click_popup_item(**self.MENU_CLOSE_PROJECT)
        self._after_task()
