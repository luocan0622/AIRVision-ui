"""画布右键 Filter 菜单：搜索 / 滚动 / 键盘选工具并放置节点。"""
import time

import pyautogui
from pywinauto import Application
from pywinauto.findwindows import find_elements

from tests.model.filter import (
    FilterToolDef,
    effective_filter_keyword,
    get_filter_tool,
    global_menu_line_index,
)
from tests.model.locators import (
    FILTER_MENU_ITEM_CLASS,
    FILTER_MENU_LINE_HEIGHT,
    FILTER_MENU_ROW_MAX_HEIGHT,
    FILTER_MENU_ROW_MIN_HEIGHT,
    FILTER_MENU_ROW_Y_PAD,
    FILTER_MENU_VIEWPORT_BOTTOM_MARGIN,
)
from tests.model.workflow_canvas import WorkflowCanvasMixin
from utils import ui_input
from utils.logger import logger


class FilterMenuMixin(WorkflowCanvasMixin):
    """右键画布 → QMenu 选工具 → 点画布放置。"""

    @staticmethod
    def _visible_line_count(menu_rect) -> int:
        inner = menu_rect.height() - FILTER_MENU_ROW_Y_PAD * 2
        return max(4, inner // FILTER_MENU_LINE_HEIGHT)

    def _wheel_scroll_menu(self, menu_rect, lines_down: int) -> None:
        if lines_down <= 0:
            return
        x = menu_rect.left + menu_rect.width() // 2
        y = menu_rect.top + menu_rect.height() // 2
        pyautogui.moveTo(x, y)
        for _ in range(max(1, lines_down // 2)):
            pyautogui.scroll(-4)
            time.sleep(0.06)

    def _scroll_menu_to_global_line(self, menu_rect, global_line: int) -> int:
        visible = self._visible_line_count(menu_rect)
        max_row = visible - FILTER_MENU_VIEWPORT_BOTTOM_MARGIN - 1
        if global_line <= max_row:
            return global_line
        scroll_by = global_line - max_row
        logger.info(f"QMenu 向下滚动约 {scroll_by} 行 (目标行 {global_line})")
        self._wheel_scroll_menu(menu_rect, scroll_by)
        time.sleep(0.2)
        return max_row

    def _find_filter_qmenu(self, canvas_rect, timeout: float = 3.0):
        pid = self.app.process
        end = time.time() + timeout
        best, best_area = None, 0

        while time.time() < end:
            try:
                for info in find_elements(
                    backend="uia",
                    process=pid,
                    class_name="QMenu",
                    top_level_only=True,
                ):
                    r = info.rectangle
                    if r.height() < 120:
                        continue
                    if r.right < canvas_rect.left or r.left > canvas_rect.right + 80:
                        continue
                    if r.bottom < canvas_rect.top - 40:
                        continue
                    area = r.width() * r.height()
                    if area > best_area:
                        best_area, best = area, info
            except Exception as e:
                logger.debug(f"枚举 QMenu 失败: {e}")

            if best is not None:
                app = Application(backend="uia").connect(handle=best.handle)
                win = app.window(handle=best.handle)
                logger.info(f"Filter QMenu: rect={best.rectangle}")
                return win, best.rectangle

            time.sleep(0.25)
        return None, None

    def _qmenu_line_xy(self, menu_rect, line: int) -> tuple[int, int]:
        x = menu_rect.left + menu_rect.width() // 2
        y = menu_rect.top + FILTER_MENU_ROW_Y_PAD + line * FILTER_MENU_LINE_HEIGHT
        return int(x), int(y)

    def _filter_row_cutoff_y(self, menu_rect) -> int:
        return menu_rect.top + FILTER_MENU_ROW_Y_PAD + FILTER_MENU_LINE_HEIGHT - 4

    def _list_qmenu_actions(self, menu_win, *, min_top: int | None = None) -> list:
        rows: list[tuple[int, object]] = []
        seen: set[tuple[int, int, int, int]] = set()
        try:
            for elem in menu_win.descendants(class_name=FILTER_MENU_ITEM_CLASS):
                if not elem.is_visible():
                    continue
                r = elem.rectangle()
                h = r.height()
                if h < FILTER_MENU_ROW_MIN_HEIGHT or h > FILTER_MENU_ROW_MAX_HEIGHT:
                    continue
                if min_top is not None and r.top < min_top:
                    continue
                key = (r.left, r.top, r.width(), h)
                if key in seen:
                    continue
                seen.add(key)
                rows.append((r.top, elem))
        except Exception:
            pass
        rows.sort(key=lambda item: item[0])
        return [elem for _, elem in rows]

    def _invoke_qmenu_element(self, elem, label: str = "") -> bool:
        if label:
            logger.info(label)
        try:
            elem.invoke()
            time.sleep(0.4)
            return True
        except Exception as e:
            logger.debug(f"Invoke 失败: {e}")
        try:
            self.mouse_click(elem)
            time.sleep(0.4)
            return True
        except Exception as e:
            logger.warning(f"点击菜单项失败: {e}")
            return False

    def _invoke_menu_row(self, menu_win, index: int) -> bool:
        rows = self._list_qmenu_actions(menu_win)
        if index >= len(rows):
            logger.debug(f"QMenu 行不足: 需要 {index}, 共 {len(rows)}")
            return False
        return self._invoke_qmenu_element(
            rows[index], f"UIA 选中 QMenu 第 {index} 行 (共 {len(rows)} 行)"
        )

    def _invoke_first_result_below_filter(self, menu_win, menu_rect) -> bool:
        cutoff = self._filter_row_cutoff_y(menu_rect)
        rows = self._list_qmenu_actions(menu_win, min_top=cutoff)
        if not rows:
            return False
        return self._invoke_qmenu_element(
            rows[0], f"Invoke 搜索结果 @ top={rows[0].rectangle().top}"
        )

    def _select_tool_by_keyboard(self, defn: FilterToolDef) -> None:
        downs = defn.menu_down_count
        if downs < 0:
            downs = global_menu_line_index(defn)
        logger.info(f"键盘选工具「{defn.display_name}」: Down×{downs}")
        for _ in range(downs):
            pyautogui.press("down")
            time.sleep(0.08)
        pyautogui.press("enter")
        time.sleep(0.4)

    def _type_filter_search(self, menu_rect, keyword: str) -> None:
        fx, fy = self._qmenu_line_xy(menu_rect, 0)
        logger.info(f"Filter 搜索: {keyword!r} @ ({fx}, {fy})")
        pyautogui.click(fx, fy)
        time.sleep(0.25)
        ui_input.paste_text(keyword)
        time.sleep(0.7)

    def _click_qmenu_line(self, menu_rect, line: int, *, double: bool = False) -> None:
        tx, ty = self._qmenu_line_xy(menu_rect, line)
        pyautogui.click(tx, ty)
        time.sleep(0.15)
        if double:
            pyautogui.click(tx, ty)
        time.sleep(0.35)

    def _select_via_filter_search(
        self, canvas_rect, menu_win, menu_rect, defn: FilterToolDef, keyword: str
    ) -> bool:
        self._type_filter_search(menu_rect, keyword)

        menu_win2, menu_rect2 = self._find_filter_qmenu(canvas_rect, timeout=1.5)
        if menu_rect2 is not None:
            menu_rect, menu_win = menu_rect2, menu_win2
            logger.info(f"搜索后 QMenu: rect={menu_rect}")

        if menu_win and self._invoke_first_result_below_filter(menu_win, menu_rect):
            return True

        ty = (
            menu_rect.top
            + FILTER_MENU_ROW_Y_PAD
            + FILTER_MENU_LINE_HEIGHT
            + FILTER_MENU_LINE_HEIGHT // 2
        )
        tx = menu_rect.left + menu_rect.width() // 2
        logger.info(f"搜索后双击「{defn.display_name}」({tx}, {ty})")
        pyautogui.click(tx, ty)
        time.sleep(0.15)
        pyautogui.click(tx, ty)
        time.sleep(0.35)

        pyautogui.press("down")
        time.sleep(0.12)
        pyautogui.press("enter")
        time.sleep(0.4)
        return True

    def _select_via_scroll_and_click(
        self, menu_win, menu_rect, defn: FilterToolDef, global_line: int
    ) -> bool:
        viewport_line = self._scroll_menu_to_global_line(menu_rect, global_line)
        if menu_win and self._invoke_menu_row(menu_win, viewport_line):
            return True
        logger.info(
            f"滚动后点击「{defn.display_name}」行 {viewport_line} "
            f"(全局 {global_line})"
        )
        self._click_qmenu_line(menu_rect, viewport_line)
        return True

    def _select_tool_in_menu(
        self, canvas_rect, menu_win, menu_rect, defn: FilterToolDef
    ) -> bool:
        keyword = effective_filter_keyword(defn)
        global_line = global_menu_line_index(defn)

        if keyword:
            logger.info(f"选工具「{defn.display_name}」: Filter 搜索 {keyword!r}")
            if self._select_via_filter_search(
                canvas_rect, menu_win, menu_rect, defn, keyword
            ):
                return True

        if menu_rect is None:
            return False

        visible = self._visible_line_count(menu_rect)
        if global_line < visible:
            if menu_win and self._invoke_menu_row(menu_win, global_line):
                return True
            logger.info(f"视口内点击「{defn.display_name}」行 {global_line}")
            self._click_qmenu_line(menu_rect, global_line)
            return True

        return self._select_via_scroll_and_click(
            menu_win, menu_rect, defn, global_line
        )

    def add_workflow_tool(self, tool_key: str, timeout: int = 10) -> FilterToolDef:
        defn = get_filter_tool(tool_key)
        canvas, canvas_rect, cx, cy = self._canvas_center(timeout)

        self._canvas_descendant_baseline = self._count_canvas_descendants(canvas)
        self._canvas_image_before_add = self._grab_canvas_image(canvas_rect)

        logger.info(
            f"添加工具「{defn.display_name}」({tool_key}), "
            f"菜单行≈{global_menu_line_index(defn)}"
        )
        pyautogui.click(cx, cy)
        time.sleep(0.2)
        pyautogui.click(cx, cy, button="right")
        time.sleep(1.0)

        menu_win, menu_rect = self._find_filter_qmenu(canvas_rect)
        if menu_rect is None or not self._select_tool_in_menu(
            canvas_rect, menu_win, menu_rect, defn
        ):
            logger.info("菜单选工具失败，键盘兜底")
            self._select_tool_by_keyboard(defn)

        pyautogui.click(cx, cy)
        time.sleep(0.8)
        return defn
