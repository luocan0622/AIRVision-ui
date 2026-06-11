"""
控件检查工具 - 用于调试和开发时查看应用控件树

使用方法：
    python inspect_controls.py [--depth DEPTH]
    python inspect_controls.py --filter-menu [--depth DEPTH]
    python inspect_controls.py --list-qmenus [--wait SECONDS]

参数：
    --depth: 控件树深度，默认为 3
    --filter-menu: 打开工作流画布右键 Filter 菜单并打印其控件树
    --list-qmenus: 列出当前进程中所有顶层 QMenu（菜单已手动打开时用）
    --wait: 配合 --list-qmenus，等待指定秒数后再扫描（默认 0）
"""
import argparse
import sys
import time

import pyautogui
from pywinauto import Application
from pywinauto.findwindows import find_elements

from pages.main_page import MainPage
from pages.mixins.filter import FILTER_TOOLS, MENU_LINE_BY_KEY, global_menu_line_index
from pages.mixins.locators import FILTER_MENU_ITEM_CLASS
from utils.app_manager import AppManager
from utils.config import load_config
from utils.logger import logger


def _connect_manager():
    config = load_config()
    app_cfg = config["app"]
    manager = AppManager(
        app_path=app_cfg["path"],
        backend=app_cfg["backend"],
        timeout=app_cfg["timeout"],
    )
    manager.start_or_connect(window_title=app_cfg.get("title", "MainWindow"))
    return manager


def list_qmenus(app, *, wait: float = 0.0) -> list:
    if wait > 0:
        logger.info(f"等待 {wait}s，请保持 Filter 菜单打开…")
        time.sleep(wait)
    pid = app.process
    return list(
        find_elements(
            backend="uia", process=pid, class_name="QMenu", top_level_only=True
        )
    )


def print_qmenu_tree(menu_info, depth: int = 6) -> None:
    app = Application(backend="uia").connect(handle=menu_info.handle)
    win = app.window(handle=menu_info.handle)
    rect = menu_info.rectangle
    print(
        f"\nQMenu handle={menu_info.handle} "
        f"rect={rect} size={rect.width()}x{rect.height()}"
    )
    print("-" * 80)
    win.print_control_identifiers(depth=depth)


def dump_qmenu_action_rows(menu_info) -> list[tuple[int, str, str, int]]:
    """列出 QMenu 内 QWidgetAction 行（按 top 坐标排序）。"""
    app = Application(backend="uia").connect(handle=menu_info.handle)
    win = app.window(handle=menu_info.handle)
    rows: list[tuple[int, str, str, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for elem in win.descendants(class_name=FILTER_MENU_ITEM_CLASS):
        try:
            if not elem.is_visible():
                continue
            r = elem.rectangle()
            key = (r.left, r.top, r.width(), r.height())
            if key in seen:
                continue
            seen.add(key)
            texts = []
            try:
                t = elem.window_text()
                if t:
                    texts.append(t)
            except Exception:
                pass
            try:
                name = getattr(elem.element_info, "name", "") or ""
                if name:
                    texts.append(name)
            except Exception:
                pass
            label = " | ".join(dict.fromkeys(texts)) or "(无文本)"
            rows.append((r.top, label, elem.class_name(), r.height()))
        except Exception:
            continue
    rows.sort(key=lambda x: x[0])
    return rows


def open_filter_menu_via_canvas(page: MainPage) -> None:
    """在画布中心右键打开 Filter 菜单（已有项目/工作流时跳过新建）。"""
    page.mouse_press_key("esc")
    time.sleep(0.3)
    try:
        canvas = page.find_workflow_canvas(timeout=4, log_result=False)
        logger.info("检测到已有工作流画布，跳过新建项目")
    except RuntimeError:
        logger.info("未检测到画布，尝试 ensure_project_open + new_workflow")
        page.ensure_project_open()
        time.sleep(0.5)
        page.ensure_workflow_tab_open()
        time.sleep(0.5)
        canvas = page.find_workflow_canvas(timeout=10)
    rect = canvas.rectangle()
    cx = rect.left + rect.width() // 2
    cy = rect.top + rect.height() // 2
    logger.info(f"画布右键 @ ({cx}, {cy}), rect={rect}")
    pyautogui.click(cx, cy)
    time.sleep(0.2)
    pyautogui.click(cx, cy, button="right")
    time.sleep(1.0)


def compare_filter_py_with_menu(rows: list[tuple[int, str, str, int]]) -> None:
    print("\n" + "=" * 80)
    print("Filter 菜单可见行（QWidgetAction，按 Y 排序）")
    print("=" * 80)
    for i, (top, label, cls, h) in enumerate(rows):
        print(f"  UI行 {i:2d}  y={top:4d}  h={h:2d}  [{cls}]  {label!r}")

    print("\n" + "=" * 80)
    print("filter.py 预期行号（global_menu_line_index，0=Filter 搜索框）")
    print("=" * 80)
    print("  行 0  (搜索框)  — 通常为 QLineEdit，非 QWidgetAction")
    line = 0
    current_cat = "__init__"
    for tool in FILTER_TOOLS:
        if tool.category != current_cat:
            current_cat = tool.category
            if tool.category:
                line += 1
                print(f"  行 {line:2d}  (分类)   {tool.category!r}")
        line += 1
        print(f"  行 {line:2d}  (工具)   {tool.display_name!r}  [{tool.key}]")

    print("\n" + "=" * 80)
    print("3D 算法 分类下 17 项（与截图对照）")
    print("=" * 80)
    cat_tools = [t for t in FILTER_TOOLS if t.category == "3D 算法"]
    for i, t in enumerate(cat_tools):
        print(f"  {i+1:2d}. {t.display_name!r}  menu_line={MENU_LINE_BY_KEY[t.key]}")


def inspect_filter_menu(app, depth: int, *, auto_open: bool) -> None:
    if auto_open:
        page = MainPage(app)
        open_filter_menu_via_canvas(page)

    menus = list_qmenus(app)
    if not menus:
        logger.error("未找到顶层 QMenu。请先打开 Filter 菜单或使用 --filter-menu")
        sys.exit(1)

    best = max(menus, key=lambda m: m.rectangle.width() * m.rectangle.height())
    print("\n" + "=" * 80)
    print(f"找到 {len(menus)} 个 QMenu，分析最大者")
    print("=" * 80)

    print_qmenu_tree(best, depth=max(depth, 6))
    rows = dump_qmenu_action_rows(best)
    compare_filter_py_with_menu(rows)
    logger.info("Filter 菜单检查完成")


def main():
    parser = argparse.ArgumentParser(description="AIRVision 控件检查工具")
    parser.add_argument("--depth", type=int, default=3, help="控件树深度 (默认: 3)")
    parser.add_argument(
        "--filter-menu",
        action="store_true",
        help="自动打开画布 Filter 菜单并打印控件树",
    )
    parser.add_argument(
        "--list-qmenus",
        action="store_true",
        help="列出进程中所有顶层 QMenu",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="扫描 QMenu 前等待秒数",
    )
    args = parser.parse_args()

    try:
        manager = _connect_manager()
        app = manager.app

        if args.list_qmenus or args.filter_menu:
            if args.wait > 0 and not args.filter_menu:
                time.sleep(args.wait)
            inspect_filter_menu(
                app,
                args.depth,
                auto_open=args.filter_menu,
            )
            return

        logger.info("正在连接到 AIRVision 应用...")
        logger.info(f"打印主窗口控件树 (深度={args.depth})...")
        print("\n" + "=" * 80)
        print("AIRVision 主窗口控件树")
        print("=" * 80 + "\n")

        window = app.top_window()
        window.print_control_identifiers(depth=args.depth)

        print("\n" + "=" * 80)
        logger.info("控件树打印完成")
        print("提示: Filter 菜单为独立 QMenu 弹出窗，请使用:")
        print("  python inspect_controls.py --filter-menu --depth 8")
        print("  python inspect_controls.py --list-qmenus --wait 5")

    except Exception as e:
        logger.error(f"检查控件失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
