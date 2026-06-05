"""主窗口工具栏（15 个 QToolButton）。

Inspect 中 Name 常为空，需用 AutomationId（Qt objectName）区分；
若 auto_id 失效，则按工具栏内从左到右的序号（index）或屏幕坐标排序定位。
"""
from dataclasses import dataclass

from tests.model.locators import TOOLBAR
from utils.logger import logger


@dataclass(frozen=True)
class ToolbarButtonDef:
    """单个工具栏按钮的元数据（与 Inspect 属性对应）。"""

    key: str
    """语义名，如 Save_Workflows。"""
    auto_id_suffix: str
    """``widgetToolBar`` 下 Qt objectName，完整 auto_id = ``{TOOLBAR}.{suffix}``。"""
    index: int
    """在工具栏中从左到右的序号（0~14）。"""
    tooltip_en: str = ""
    """悬停提示（英文，Inspect 中 HelpText / 工具提示）。"""
    legacy_name_zh: str = ""
    """LegacyIAccessible.Name 可能出现的中文描述（如「撤销按钮」）。"""


# 从左到右共 15 个按钮（与界面顺序一致）
TOOLBAR_BUTTONS: tuple[ToolbarButtonDef, ...] = (
    ToolbarButtonDef("Save_Workflows", "toolButtonSave", 0, "Save Workflow", "保存"),
    ToolbarButtonDef("open_workflows", "toolButtonOpen", 1, "Open Workflow", "打开"),
    ToolbarButtonDef("undo", "toolButtonUndo", 2, "Undo", "撤销按钮"),
    ToolbarButtonDef("redo", "toolButtonRedo", 3, "Redo", "重做按钮"),
    ToolbarButtonDef("Lock_view", "toolButtonLock", 4, "Lock View", "锁定视图"),
    ToolbarButtonDef("camara", "toolButtonCamera", 5, "Camera", "相机"),
    ToolbarButtonDef("contrllor", "toolButtonController", 6, "Controller", "控制器"),
    ToolbarButtonDef("Global_Variables", "toolButtonGlobalVar", 7, "Global Variables", "全局变量"),
    ToolbarButtonDef("Communication", "toolButtonComms", 8, "Communication", "通信"),
    ToolbarButtonDef("Start_Excution", "toolButtonStart", 9, "Start Execution", "开始执行"),
    ToolbarButtonDef("Stop_Excution", "toolButtonStop", 10, "Stop Execution", "停止执行"),
    ToolbarButtonDef("Global_Trigger", "toolButtonGlobalTrigger", 11, "Global Trigger", "全局触发"),
    ToolbarButtonDef("Script_Editor", "toolButtonScript", 12, "Script Editor", "脚本编辑器"),
    ToolbarButtonDef("Run", "toolButtonRun", 13, "Run", "运行"),
    ToolbarButtonDef("Loop_Run", "toolButtonLoopRun", 14, "Loop Run", "循环运行"),
)

TOOLBAR_BUTTON_BY_KEY = {b.key: b for b in TOOLBAR_BUTTONS}
TOOLBAR_BUTTON_COUNT = len(TOOLBAR_BUTTONS)


def _button_locator(defn: ToolbarButtonDef) -> dict:
    return {
        "auto_id": f"{TOOLBAR}.{defn.auto_id_suffix}",
        "control_type": "Button",
    }


class ToolbarMixin:
    """工具栏 15 个按钮的定位与点击。"""

    # ─── 按语义名暴露定位器（供 is_visible / click 使用）────────────────

    BTN_SAVE_WORKFLOWS = _button_locator(TOOLBAR_BUTTONS[0])
    BTN_OPEN_WORKFLOWS = _button_locator(TOOLBAR_BUTTONS[1])
    BTN_UNDO = _button_locator(TOOLBAR_BUTTONS[2])
    BTN_REDO = _button_locator(TOOLBAR_BUTTONS[3])
    BTN_LOCK_VIEW = _button_locator(TOOLBAR_BUTTONS[4])
    BTN_CAMARA = _button_locator(TOOLBAR_BUTTONS[5])
    BTN_CONTRLLOR = _button_locator(TOOLBAR_BUTTONS[6])
    BTN_GLOBAL_VARIABLES = _button_locator(TOOLBAR_BUTTONS[7])
    BTN_COMMUNICATION = _button_locator(TOOLBAR_BUTTONS[8])
    BTN_START_EXCUTION = _button_locator(TOOLBAR_BUTTONS[9])
    BTN_STOP_EXCUTION = _button_locator(TOOLBAR_BUTTONS[10])
    BTN_GLOBAL_TRIGGER = _button_locator(TOOLBAR_BUTTONS[11])
    BTN_SCRIPT_EDITOR = _button_locator(TOOLBAR_BUTTONS[12])
    BTN_RUN = _button_locator(TOOLBAR_BUTTONS[13])
    BTN_LOOP_RUN = _button_locator(TOOLBAR_BUTTONS[14])

    # 兼容旧命名
    BTN_SAVE = BTN_SAVE_WORKFLOWS
    BTN_OPEN = BTN_OPEN_WORKFLOWS
    BTN_LOCK = BTN_LOCK_VIEW
    BTN_CAMERA = BTN_CAMARA
    BTN_CONTROLLER = BTN_CONTRLLOR
    BTN_GLOBAL_VAR = BTN_GLOBAL_VARIABLES
    BTN_COMMS = BTN_COMMUNICATION
    BTN_START = BTN_START_EXCUTION
    BTN_STOP = BTN_STOP_EXCUTION
    BTN_SCRIPT = BTN_SCRIPT_EDITOR

    def get_toolbar_button_def(self, key: str) -> ToolbarButtonDef:
        """按语义名获取按钮定义。"""
        if key not in TOOLBAR_BUTTON_BY_KEY:
            raise KeyError(
                f"未知工具栏按钮: {key!r}，可选: {list(TOOLBAR_BUTTON_BY_KEY)}"
            )
        return TOOLBAR_BUTTON_BY_KEY[key]

    def _toolbar_locator(self, key: str) -> dict:
        return _button_locator(self.get_toolbar_button_def(key))

    def _list_toolbar_qtoolbuttons(self) -> list:
        """列出工具栏区域内可见的 QToolButton，按屏幕 left 坐标排序。"""
        toolbar = self.find_element(timeout=5, auto_id=TOOLBAR)
        buttons = []
        try:
            for elem in toolbar.descendants(class_name="QToolButton"):
                try:
                    if elem.is_visible():
                        buttons.append(elem)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"扫描 QToolButton 失败: {e}")
            return []

        buttons.sort(key=lambda b: b.rectangle().left)
        return buttons

    def find_toolbar_button(self, key: str, timeout: int = 10):
        """定位工具栏按钮：优先 AutomationId，失败则按 index 序号。"""
        defn = self.get_toolbar_button_def(key)

        try:
            ctrl = self.find_element(
                timeout=min(timeout, 3), **_button_locator(defn)
            )
            logger.debug(
                f"工具栏 [{defn.key}]: auto_id={TOOLBAR}.{defn.auto_id_suffix}"
            )
            return ctrl
        except Exception as e:
            logger.debug(f"工具栏 [{defn.key}] auto_id 定位失败: {e}")

        buttons = self._list_toolbar_qtoolbuttons()
        if defn.index < len(buttons):
            logger.info(
                f"工具栏 [{defn.key}]: 按序号 index={defn.index} 定位 "
                f"(共 {len(buttons)} 个 QToolButton)"
            )
            return buttons[defn.index]

        raise RuntimeError(
            f"未找到工具栏按钮 {defn.key!r}: "
            f"auto_id={defn.auto_id_suffix}, index={defn.index}, "
            f"可见按钮数={len(buttons)}"
        )

    def click_toolbar_button(self, key: str, timeout: int = 10):
        """点击指定语义名的工具栏按钮。"""
        defn = self.get_toolbar_button_def(key)
        logger.info(f"点击工具栏: {defn.key}")
        elem = self.find_toolbar_button(key, timeout=timeout)
        self.mouse_click(elem)

    def is_toolbar_button_visible(self, key: str) -> bool:
        """检查工具栏按钮是否可见。"""
        try:
            self.find_toolbar_button(key, timeout=2)
            return True
        except Exception:
            return False

    def are_all_toolbar_buttons_visible(self) -> bool:
        """15 个工具栏按钮是否均可见。"""
        return all(self.is_toolbar_button_visible(b.key) for b in TOOLBAR_BUTTONS)

    # ─── 便捷点击方法 ─────────────────────────────────────────────────

    def click_save_workflows(self):
        self.click_toolbar_button("Save_Workflows")

    def click_open_workflows(self):
        self.click_toolbar_button("open_workflows")

    def click_undo(self):
        self.click_toolbar_button("undo")

    def click_redo(self):
        self.click_toolbar_button("redo")

    def click_lock_view(self):
        self.click_toolbar_button("Lock_view")

    def click_camara(self):
        self.click_toolbar_button("camara")

    def click_contrllor(self):
        self.click_toolbar_button("contrllor")

    def click_global_variables(self):
        self.click_toolbar_button("Global_Variables")

    def click_communication(self):
        self.click_toolbar_button("Communication")

    def click_start_excution(self):
        self.click_toolbar_button("Start_Excution")

    def click_stop_excution(self):
        self.click_toolbar_button("Stop_Excution")

    def click_global_trigger(self):
        self.click_toolbar_button("Global_Trigger")

    def click_script_editor(self):
        self.click_toolbar_button("Script_Editor")

    def click_run(self):
        self.click_toolbar_button("Run")

    def click_loop_run(self):
        self.click_toolbar_button("Loop_Run")

    # 兼容旧方法名
    click_save = click_save_workflows
    click_open = click_open_workflows
    click_camera = click_camara
    click_start = click_start_excution
    click_stop = click_stop_excution
    click_script = click_script_editor

    def is_run_enabled(self) -> bool:
        try:
            ctrl = self.find_toolbar_button("Run", timeout=2)
            return ctrl.is_enabled()
        except Exception:
            return False

    def is_stop_enabled(self) -> bool:
        try:
            ctrl = self.find_toolbar_button("Stop_Excution", timeout=2)
            return ctrl.is_enabled()
        except Exception:
            return False
