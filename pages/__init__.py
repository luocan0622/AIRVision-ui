"""页面对象层：BasePage + 对话框 + MainPage 业务 Mixin。"""
from pages.base_page import BasePage
from pages.dialogs import DialogTitle
from pages.file_dialog import FileDialogMixin
from pages.main_page import MainPage

__all__ = ["BasePage", "DialogTitle", "FileDialogMixin", "MainPage"]
