"""MainPage 公共定位器前缀与配置路径。"""
import re

from utils.config import get_test_paths
from utils.naming import TEST_NUMBER_PATTERN

HEADER = "MainWindow.wBody.centralwidget.widgetTitle.widgetMenuBar.header.LHeader"
TOOLBAR = "MainWindow.wBody.centralwidget.widgetTitle.widgetToolBar"

# 工作流编辑区画布（Inspect: ClassName=QtNodes::GraphicsView, ControlType=Group）
WORKFLOW_CANVAS_CLASS = "QtNodes::GraphicsView"
WORKFLOW_CANVAS_CLASS_NAMES = (
    WORKFLOW_CANVAS_CLASS,
    "QGraphicsView",
)
# 画布最小可见尺寸，避免误选缩略图内嵌视图
WORKFLOW_CANVAS_MIN_WIDTH = 200
WORKFLOW_CANVAS_MIN_HEIGHT = 200

# 画布右键 Filter 菜单（Inspect: 独立 QMenu 弹出窗，锚在右键点附近）
FILTER_MENU_ITEM_CLASS = "QWidgetAction"
FILTER_MENU_ROW_MIN_HEIGHT = 8
FILTER_MENU_ROW_MAX_HEIGHT = 120
FILTER_MENU_LINE_HEIGHT = 28
FILTER_MENU_ROW_Y_PAD = 14
FILTER_MENU_FIRST_TOOL_LINE = 2
# QMenu 视口内保留底部边距，避免点到最后一条被裁切
FILTER_MENU_VIEWPORT_BOTTOM_MARGIN = 2

TEST_PATHS = get_test_paths()

WORKFLOW_NAME_PATTERN = re.compile(r"^Untitled-\d+$", re.I)
TEST_WORKFLOW_NAME_PATTERN = TEST_NUMBER_PATTERN
TEST_PROJECT_NAME_PATTERN = TEST_NUMBER_PATTERN
PROJECT_FILE_RE = re.compile(r"([\w.-]+\.airvision)", re.I)
WORKFLOWS_SUBDIR = "workflows"
WORKFLOW_FILE_EXT = ".json"
