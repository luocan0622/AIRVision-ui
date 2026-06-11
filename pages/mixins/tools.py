"""Tools 下拉菜单。"""


class ToolsMixin:
    MENU_TOOLBOX = {"title": "Toolbox", "control_type": "MenuItem"}
    MENU_PLUGIN_MANAGER = {"title": "Plugin Manager", "control_type": "MenuItem"}
    MENU_SCRIPT_EDITOR = {"title": "Script Editor", "control_type": "MenuItem"}
    MENU_DEBUG_CONSOLE = {"title": "Debug Console", "control_type": "MenuItem"}
    MENU_CUSTOMIZE = {"title": "Customize", "control_type": "MenuItem"}

    def open_toolbox(self):
        self.click_tools()
        self.click_popup_item(**self.MENU_TOOLBOX)

    def open_plugin_manager(self):
        self.click_tools()
        self.click_popup_item(**self.MENU_PLUGIN_MANAGER)

    def open_script_editor(self):
        self.click_tools()
        self.click_popup_item(**self.MENU_SCRIPT_EDITOR)

    def open_debug_console(self):
        self.click_tools()
        self.click_popup_item(**self.MENU_DEBUG_CONSOLE)

    def open_customize(self):
        self.click_tools()
        self.click_popup_item(**self.MENU_CUSTOMIZE)
