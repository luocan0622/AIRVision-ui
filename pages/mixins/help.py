"""Help 下拉菜单。"""


class HelpMixin:
    MENU_DOCUMENTATION = {"title": "Documentation", "control_type": "MenuItem"}
    MENU_TUTORIAL = {"title": "Tutorial", "control_type": "MenuItem"}
    MENU_KEYBOARD_SHORTCUTS = {"title": "Keyboard Shortcuts", "control_type": "MenuItem"}
    MENU_CHECK_UPDATES = {"title": "Check for Updates", "control_type": "MenuItem"}
    MENU_REPORT_BUG = {"title": "Report Bug", "control_type": "MenuItem"}
    MENU_ABOUT = {"title": "About AIRVision", "control_type": "MenuItem"}

    def open_documentation(self):
        self.click_help()
        self.click_popup_item(**self.MENU_DOCUMENTATION)

    def open_tutorial(self):
        self.click_help()
        self.click_popup_item(**self.MENU_TUTORIAL)

    def open_keyboard_shortcuts(self):
        self.click_help()
        self.click_popup_item(**self.MENU_KEYBOARD_SHORTCUTS)

    def check_for_updates(self):
        self.click_help()
        self.click_popup_item(**self.MENU_CHECK_UPDATES)

    def report_bug(self):
        self.click_help()
        self.click_popup_item(**self.MENU_REPORT_BUG)

    def open_about(self):
        self.click_help()
        self.click_popup_item(**self.MENU_ABOUT)
