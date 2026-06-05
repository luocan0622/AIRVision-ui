"""AIRVision 窗口标题注册表。

通过窗口左上角标题定位并区分不同对话框，后续新增功能只需在此注册标题。
"""


class DialogTitle:
    """已知窗口标题常量。"""

    # ─── Projects ────────────────────────────────────────────────────
    CREATE_NEW_PROJECT = "Create New Project"
    NEW_PROJECT = "New Project"  # 与 CREATE_NEW_PROJECT 为同一对话框
    CREATE_NEW_PROJECT_TITLES = (CREATE_NEW_PROJECT, NEW_PROJECT)
    OPEN_PROJECT = "Open Project"
    SAVE_PROJECT_AS = "Save Project As"  # 另存为项目
    CONFIRM_SAVE_AS = "Confirm Save As"  # 新建/另存为时文件已存在确认
    PROJECT_CREATED_SUCCESS = "Success"  # 新建项目成功提示
    SELECT_TEMPLATE_IMAGES = "Select Template Images"  # 设置默认模板主对话框
    SELECT_TEMPLATE_IMAGE = "Select Template Image"    # 选择 Template 图片
    SELECT_DEPTH_IMAGE = "Select Depth Image"          # 选择 Depth 图片

    # ─── Workflows ───────────────────────────────────────────────────
    OPEN_WORKFLOW = "Open Workflow"
    SAVE_WORKFLOW = "Save Workflow"
    SAVE_WORKFLOW_AS = "Save Workflow As"
    RENAME_WORKFLOW = "Rename Workflow"
