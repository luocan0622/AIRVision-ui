"""页面对象层：BasePage + 对话框标题常量 + 文件对话框 Mixin。"""
from pages.base_page import BasePage
from pages.dialogs import DialogTitle
from pages.file_dialog import FileDialogMixin

__all__ = ["BasePage", "DialogTitle", "FileDialogMixin"]
