"""右键菜单中的 40 个工具定义。

添加任意工具::

    page.add_workflow_tool("d3_plane_fitting")      # 3D 算法靠后 → 自动 Filter 搜索 / 滚动

    page.add_workflow_tool("communication_send")    # 其它分类同理

菜单行号（含 Filter 行 0、分类行、工具行）由 ``global_menu_line_index`` 计算；
超出视口时 ``filter_menu`` 会在 QMenu 内滚轮滚动或走 Filter 搜索框。
"""
from dataclasses import dataclass

FILTER_TOOL_COUNT = 40


@dataclass(frozen=True)
class FilterToolDef:
    """Filter 菜单中的单个工具。"""

    key: str
    """语义键（英文 snake_case），供测试与 ``add_workflow_tool`` 使用。"""
    display_name: str
    """界面显示名称（中文或英文，与 Inspect / 菜单文本一致）。"""
    category: str
    """所属分类；空字符串表示顶层项（无分类前缀）。"""
    index_in_category: int = 0
    """在该分类展开列表中的大致顺序（0 起），用于文档与兜底。"""
    tooltip_en: str = ""
    """悬停英文提示（若有）。"""
    node_name_contains: str = ""
    """画布节点标题片段（如 Circle3DDetector）。"""
    filter_keyword: str = ""
    """菜单 Filter 框输入的关键字；空则用 display_name 简写。"""
    menu_down_count: int = -1
    """右键后方向键 Down 次数；-1 则 2+index_in_category。"""


# ─── 3D 算法（17）────────────────────────────────────────────────────────
_CAT_3D_ALGO = "3D 算法"

# ─── 其余分类 ───────────────────────────────────────────────────────────
_CAT_AI = "AI 工具"
_CAT_AIRVISION = "AIRVision Tools"
_CAT_VIZ = "可视化"
_CAT_DATA = "数据源"
_CAT_ROBOT = "机器人"
_CAT_CAMERA = "相机"
_CAT_CUSTOM = "自定义算法"
_CAT_COMM = "通讯"

FILTER_TOOLS: tuple[FilterToolDef, ...] = (
    # 3D 算法
    FilterToolDef(
        "d3_circle_detection",
        "3D 圆检测",
        _CAT_3D_ALGO,
        0,
        tooltip_en="3D circle detection",
        node_name_contains="Circle3DDetector",
        filter_keyword="圆检测",
        menu_down_count=2,
    ),
    FilterToolDef("d3_point_cloud_coarse_registration", "3D 点云粗配准", _CAT_3D_ALGO, 1),
    FilterToolDef("d3_depth_bitmap", "3D 深度位图", _CAT_3D_ALGO, 2, "3D depth bitmap"),
    FilterToolDef("d3_edge_detection", "3D 边缘检测", _CAT_3D_ALGO, 3),
    FilterToolDef("d3_ellipse_detection", "3D 椭圆检测", _CAT_3D_ALGO, 4),
    FilterToolDef("d3_target_search", "3D 目标查找", _CAT_3D_ALGO, 5),
    FilterToolDef("d3_point_cloud_fine_registration", "3D 点云精配准", _CAT_3D_ALGO, 6),
    FilterToolDef("d3_flatness_detection", "3D 平面度检测", _CAT_3D_ALGO, 7),
    FilterToolDef("d3_height_detection", "3D 高度检测", _CAT_3D_ALGO, 8, filter_keyword="高度检测"),
    FilterToolDef("d3_line_detection", "3D 直线检测", _CAT_3D_ALGO, 9),
    FilterToolDef("d3_normal_estimation", "3D 法向估计", _CAT_3D_ALGO, 10),
    FilterToolDef("d3_plane_fitting", "3D 平面拟合", _CAT_3D_ALGO, 11, filter_keyword="平面拟合"),
    FilterToolDef("d3_plane_segmentation", "3D 平面分割", _CAT_3D_ALGO, 12),
    FilterToolDef("d3_point_cloud_transform", "3D 点云变换", _CAT_3D_ALGO, 13),
    FilterToolDef("d3_point_plane_distance", "3D 点面距离", _CAT_3D_ALGO, 14),
    FilterToolDef("d3_roi_crop_point_cloud", "3D ROI 裁剪点云", _CAT_3D_ALGO, 15, filter_keyword="ROI 裁剪"),
    FilterToolDef("d3_roi_transform", "3D ROI 变换", _CAT_3D_ALGO, 16),
    # 顶层
    FilterToolDef("d3_point_cloud_registration", "3D 点云配准", "", 0),
    # AI 工具
    FilterToolDef("ai_2d_detection", "2D AI-检测", _CAT_AI, 0),
    FilterToolDef("ai_2d_detection_segmentation", "2D AI-检测+分割", _CAT_AI, 1),
    FilterToolDef("ai_2d_segmentation", "2D AI-分割", _CAT_AI, 2),
    # AIRVision Tools
    FilterToolDef("debug_tool", "DebugTool", _CAT_AIRVISION, 0),
    FilterToolDef("plane_segmentation_tool", "PlaneSegmentationTool", _CAT_AIRVISION, 1),
    FilterToolDef("registration_tool", "RegistrationTool", _CAT_AIRVISION, 2),
    FilterToolDef(
        "result_condition_tool",
        "ResultConditionTool",
        _CAT_AIRVISION,
        3,
        filter_keyword="ResultCondition",
        node_name_contains="ResultCondition",
    ),
    FilterToolDef("template_matching_tool", "TemplateMatchingTool", _CAT_AIRVISION, 4),
    # 可视化
    FilterToolDef(
        "d3_point_cloud_visualization",
        "3D 点云可视化",
        _CAT_VIZ,
        0,
        filter_keyword="点云可视化",
    ),
    FilterToolDef("robot_waypoint_display", "机器人路点显示", _CAT_VIZ, 1),
    # 数据源
    FilterToolDef("d3_data_center", "3D 数据中心", _CAT_DATA, 0),
    FilterToolDef("d2_data_source", "2D 数据源", _CAT_DATA, 1),
    FilterToolDef("d3_data_source", "3D 数据源", _CAT_DATA, 2),
    FilterToolDef("d2_data_source_depth", "2D 数据源-深度图", _CAT_DATA, 3),
    FilterToolDef("d2_data_source_grayscale", "2D 数据源-灰度图", _CAT_DATA, 4),
    FilterToolDef("d3_pose_data_source", "3D 位姿数据源", _CAT_DATA, 5),
    FilterToolDef("d3_roi_data_source", "3D ROI数据源", _CAT_DATA, 6),
    # 机器人
    FilterToolDef("robot_pose_transform", "机器人位姿变换", _CAT_ROBOT, 0),
    # 相机
    FilterToolDef(
        "camera_data_source",
        "相机数据源",
        _CAT_CAMERA,
        0,
        filter_keyword="相机数据源",
        node_name_contains="CameraDataSource",
    ),
    FilterToolDef("camera_trigger", "相机触发", _CAT_CAMERA, 1),
    # 自定义算法
    FilterToolDef(
        "mold_cup_path_detection",
        "模杯路径检测",
        _CAT_CUSTOM,
        0,
        filter_keyword="模杯",
        node_name_contains="MoldCup",
    ),
    # 通讯
    FilterToolDef("communication_send", "通讯发送", _CAT_COMM, 0, filter_keyword="通讯发送"),
)

assert len(FILTER_TOOLS) == FILTER_TOOL_COUNT

FILTER_TOOL_BY_KEY = {t.key: t for t in FILTER_TOOLS}

FILTER_CATEGORIES: tuple[str, ...] = (
    _CAT_3D_ALGO,
    _CAT_AI,
    _CAT_AIRVISION,
    _CAT_VIZ,
    _CAT_DATA,
    _CAT_ROBOT,
    _CAT_CAMERA,
    _CAT_CUSTOM,

    _CAT_COMM,
)

TOOLS_BY_CATEGORY: dict[str, tuple[FilterToolDef, ...]] = {}
for _cat in FILTER_CATEGORIES:
    TOOLS_BY_CATEGORY[_cat] = tuple(t for t in FILTER_TOOLS if t.category == _cat)

TOP_LEVEL_FILTER_TOOLS: tuple[FilterToolDef, ...] = tuple(
    t for t in FILTER_TOOLS if not t.category
)


def get_filter_tool(key: str) -> FilterToolDef:
    """按语义键获取工具定义。"""
    if key not in FILTER_TOOL_BY_KEY:
        raise KeyError(
            f"未知 Filter 工具: {key!r}，可选: {list(FILTER_TOOL_BY_KEY)}"
        )
    return FILTER_TOOL_BY_KEY[key]


def _build_menu_line_by_key() -> dict[str, int]:
    """按 ``FILTER_TOOLS`` 在界面中的顺序生成行号（0=Filter 搜索框）。"""
    line = 0
    mapping: dict[str, int] = {}
    current_cat: str | None = "__init__"
    for tool in FILTER_TOOLS:
        if tool.category != current_cat:
            current_cat = tool.category
            if tool.category:
                line += 1
        line += 1
        mapping[tool.key] = line
    return mapping


MENU_LINE_BY_KEY: dict[str, int] = _build_menu_line_by_key()


def global_menu_line_index(defn: FilterToolDef) -> int:
    """工具在完整 Filter 列表中的行号（0=搜索框）。"""
    try:
        return MENU_LINE_BY_KEY[defn.key]
    except KeyError as e:
        raise KeyError(f"未在菜单树中找到工具: {defn.key!r}") from e


def infer_filter_keyword(display_name: str) -> str:
    """从显示名推断 Filter 搜索关键字（列表很长时优先用搜索）。"""
    s = display_name.strip()
    for prefix in ("3D ", "2D "):
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
    if "-" in s:
        tail = s.split("-", 1)[-1].strip()
        if tail:
            s = tail
    if len(s) <= 6:
        return s
    if any("\u4e00" <= c <= "\u9fff" for c in s):
        return s[-4:]
    return s[:10]


def effective_filter_keyword(defn: FilterToolDef) -> str:
    """显式 ``filter_keyword`` 优先，否则自动推断。"""
    return (defn.filter_keyword or infer_filter_keyword(defn.display_name)).strip()
