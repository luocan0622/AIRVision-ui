"""主窗口顶部菜单栏。"""
import time

from tests.model.locators import HEADER
from utils.logger import logger


class MenuBarMixin:
    """菜单栏按钮定位与点击。"""

    BTN_PROJECTS = {"auto_id": f"{HEADER}.pushButtonProject", "control_type": "Button"}
    BTN_WORKFLOWS = {"auto_id": f"{HEADER}.pushButtonFile", "control_type": "Button"}
    BTN_SETTINGS = {"auto_id": f"{HEADER}.pushButtonSettings", "control_type": "Button"}
    BTN_TOOLS = {"auto_id": f"{HEADER}.pushButtonTools", "control_type": "Button"}
    BTN_HELP = {"auto_id": f"{HEADER}.pushButtonHelp", "control_type": "Button"}
    BTN_LANG = {"auto_id": f"{HEADER}.pushButtonLang", "control_type": "Button"}
    BTN_MINIMIZE = {"auto_id": f"{HEADER}.pushButtonMinimum", "control_type": "Button"}
    BTN_MAXIMIZE = {"auto_id": f"{HEADER}.pushButtonMaximum", "control_type": "Button"}
    BTN_CLOSE = {"auto_id": f"{HEADER}.pushButtonClose", "control_type": "Button"}
    LBL_TITLE = {"auto_id": f"{HEADER}.lableTitle", "control_type": "Text"}
    LBL_PROJECT_PATH = {"auto_id": f"{HEADER}.labelProjectPath", "control_type": "Text"}

    # ─── 语言弹出菜单项 ────────────────────────────────────────────────
    MENU_LANG_EN = {"title": "English", "control_type": "MenuItem"}
    MENU_LANG_CN = {"title": "中文", "control_type": "MenuItem"}

    @staticmethod
    def _normalize_lang(lang: str) -> str:
        """将用户输入规范化为 'EN' 或 'CN'。"""
        upper = lang.strip().upper()
        if upper in ("EN", "ENGLISH", "ENG"):
            return "EN"
        if upper in ("CN", "ZH", "CHINESE", "中文", "简体中文", "CHS"):
            return "CN"
        raise ValueError(
            f"不支持的语言: {lang!r}，可选: EN/English, CN/ZH/中文"
        )

    # ─── 菜单栏按钮点击 ────────────────────────────────────────────────

    def click_projects(self):
        """点击 Projects 按钮，展开项目菜单。"""
        logger.info("点击 Projects 按钮")
        self.click(**self.BTN_PROJECTS)
        time.sleep(0.5)

    def click_workflows(self):
        """点击 Workflows 按钮。"""
        logger.info("点击 Workflows 按钮")
        self.click(**self.BTN_WORKFLOWS)
        time.sleep(0.5)

    def click_settings(self):
        """点击 Settings 按钮。"""
        logger.info("点击 Settings 按钮")
        self.click(**self.BTN_SETTINGS)

    def click_tools(self):
        """点击 Tools 按钮。"""
        logger.info("点击 Tools 按钮")
        self.click(**self.BTN_TOOLS)

    def click_help(self):
        """点击 Help 按钮。"""
        logger.info("点击 Help 按钮")
        self.click(**self.BTN_HELP)

    def click_language(self):
        """点击语言切换按钮（EN/CN），展开语言选择菜单。"""
        logger.info("点击语言切换按钮")
        self.click(**self.BTN_LANG)
        time.sleep(0.3)

    # ─── 语言切换 ──────────────────────────────────────────────────────

    def switch_language(self, lang: str):
        """模拟用户点击切换语言。

        点击语言按钮展开下拉菜单，再点击目标语言菜单项完成切换。

        Args:
            lang: 目标语言，支持 'EN'/'English' 或 'CN'/'ZH'/'中文'。
        """
        target = self._normalize_lang(lang)
        logger.info(f"切换语言为: {target}")
        self.click_language()
        if target == "EN":
            self.click_popup_item(**self.MENU_LANG_EN)
        else:
            self.click_popup_item(**self.MENU_LANG_CN)
        logger.info(f"已切换语言为: {target}")

    def toggle_language(self):
        """在 EN 与 CN 之间来回切换语言。

        不要求事先知道当前语言，依次尝试点击 EN / 中文菜单项。
        """
        logger.info("切换语言（EN ↔ CN）")
        self.click_language()
        try:
            self.click_popup_item(**self.MENU_LANG_EN)
            logger.info("已切换为 English")
        except TimeoutError:
            self.click_popup_item(**self.MENU_LANG_CN)
            logger.info("已切换为 中文")

    # ─── 标题栏信息 ────────────────────────────────────────────────────

    def get_title_text(self) -> str:
        """获取标题栏文字（如 'AIRVision'）。"""
        return self.get_text(**self.LBL_TITLE)

    def get_project_path(self) -> str:
        """获取当前项目路径。"""
        return self.get_text(**self.LBL_PROJECT_PATH)

    def is_projects_visible(self) -> bool:
        """检查 Projects 按钮是否可见。"""
        return self.is_visible(**self.BTN_PROJECTS)
