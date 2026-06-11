"""画布右键 Filter 菜单：搜索 / 滚动 / 键盘选工具并放置节点。"""
import time

import pyautogui
from pywinauto import Application
from pywinauto.findwindows import find_elements

from pages.mixins.filter import (
    FilterToolDef,
    effective_filter_keyword,
    get_filter_tool,
    global_menu_line_index,
)
from pages.mixins.locators import (
    FILTER_MENU_ITEM_CLASS,
    FILTER_MENU_LINE_HEIGHT,
    FILTER_MENU_ROW_MAX_HEIGHT,
    FILTER_MENU_ROW_MIN_HEIGHT,
    FILTER_MENU_ROW_Y_PAD,
    FILTER_MENU_VIEWPORT_BOTTOM_MARGIN,
)
from pages.mixins.workflow_layout import NodePlacement
from pages.mixins.workflow_canvas import WorkflowCanvasMixin
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
        h_margin = 160

        while time.time() < end:
            try:
                for top_level_only in (True, False):
                    for info in find_elements(
                        backend="uia",
                        process=pid,
                        class_name="QMenu",
                        top_level_only=top_level_only,
                    ):
                        r = info.rectangle
                        if r.height() < 80:
                            continue
                        if r.bottom < canvas_rect.top - 60:
                            continue
                        if r.top > canvas_rect.bottom + 60:
                            continue
                        if (
                            r.right < canvas_rect.left - h_margin
                            or r.left > canvas_rect.right + h_margin
                        ):
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
        logger.info(f"搜索后 Invoke 搜索结果行「{defn.display_name}」({tx}, {ty})")
        pyautogui.click(tx, ty)
        time.sleep(0.45)
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
        if menu_rect is None:
            return False

        keyword = effective_filter_keyword(defn)
        global_line = global_menu_line_index(defn)

        if keyword:
            logger.info(f"选工具「{defn.display_name}」: Filter 搜索 {keyword!r}")
            if self._select_via_filter_search(
                canvas_rect, menu_win, menu_rect, defn, keyword
            ):
                return True

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

    def _click_canvas(self, x: int, y: int, *, duration: float = 0.25) -> None:
        """移动并点击画布（用于放置节点）。"""
        pyautogui.moveTo(x, y, duration=duration)
        time.sleep(0.12)
        pyautogui.click(x, y)
        time.sleep(0.35)

    def _canvas_empty_anchor(self, canvas_rect) -> tuple[int, int]:
        """画布右侧空白区（取消选中 / 获取焦点，避开左侧节点列）。"""
        return (
            canvas_rect.right - 55,
            canvas_rect.top + canvas_rect.height() // 2,
        )

    def _canvas_node_origin(self, canvas_rect) -> tuple[int, int]:
        """首节点列锚点（与实测左上角放置区域一致）。"""
        return (
            canvas_rect.left + 180,
            canvas_rect.top + 120,
        )

    def _canvas_menu_anchor(self, canvas_rect) -> tuple[int, int]:
        """Filter 菜单锚点：画布右侧空白区（避开左侧/中央节点列）。"""
        return (
            canvas_rect.right - 90,
            canvas_rect.top + 72,
        )

    def _filter_menu_anchor_candidates(
        self, canvas_rect, primary: tuple[int, int] | None = None
    ) -> list[tuple[int, int]]:
        """Filter 右键候选点：优先右侧，失败再试画布中心。"""
        anchors: list[tuple[int, int]] = []
        if primary is not None:
            anchors.append(primary)
        for pt in (
            self._canvas_menu_anchor(canvas_rect),
            (
                canvas_rect.left + canvas_rect.width() // 2,
                canvas_rect.top + canvas_rect.height() // 2,
            ),
            (
                canvas_rect.right - 60,
                canvas_rect.top + canvas_rect.height() // 2,
            ),
        ):
            if pt not in anchors:
                anchors.append(pt)
        return anchors

    def _reset_for_next_tool_add(self, canvas_rect) -> None:
        """退出放置/选中状态，为下一次右键 Filter 做准备。"""
        try:
            self.window.set_focus()
        except Exception:
            pass
        self.mouse_press_key("esc")
        time.sleep(0.12)
        self.mouse_press_key("esc")
        time.sleep(0.15)
        x, y = self._canvas_empty_anchor(canvas_rect)
        pyautogui.click(x, y)
        time.sleep(0.25)

    def _finish_tool_placement(self, canvas_rect) -> None:
        """放置完成后退出 ghost/选中，避免阻塞下一次 Filter。"""
        self.mouse_press_key("esc")
        time.sleep(0.12)
        x, y = self._canvas_empty_anchor(canvas_rect)
        pyautogui.click(x, y)
        time.sleep(0.3)

    def _ensure_canvas_ready(self, canvas_rect) -> None:
        """确保主窗口与画布获得焦点（点击空白区，不选中节点）。"""
        try:
            self.window.set_focus()
        except Exception:
            pass
        time.sleep(0.12)
        x, y = self._canvas_empty_anchor(canvas_rect)
        pyautogui.click(x, y)
        time.sleep(0.2)

    def _open_filter_menu_at(
        self,
        canvas_rect,
        menu_x: int,
        menu_y: int,
        *,
        timeout: float = 5.0,
    ):
        """在画布坐标打开 Filter 菜单（多锚点 + 先左键再右键）。"""
        try:
            self.window.set_focus()
        except Exception:
            pass
        time.sleep(0.15)

        anchors = self._filter_menu_anchor_candidates(
            canvas_rect, primary=(menu_x, menu_y)
        )
        per_anchor = max(1.5, timeout / len(anchors))

        for ax, ay in anchors:
            logger.debug(f"Filter 右键尝试 @ ({ax}, {ay})")
            pyautogui.moveTo(ax, ay, duration=0.12)
            pyautogui.click(ax, ay)
            time.sleep(0.2)
            pyautogui.click(ax, ay, button="right")
            time.sleep(1.0)
            menu_win, menu_rect = self._find_filter_qmenu(
                canvas_rect, timeout=per_anchor
            )
            if menu_rect is not None:
                return menu_win, menu_rect
            self._close_stray_menu()

        try:
            menu_win = self._get_popup_menu(timeout=2.0)
            rect = menu_win.rectangle()
            if rect.height() >= 80:
                logger.info(f"Filter 弹出菜单(fallback): rect={rect}")
                return menu_win, rect
        except TimeoutError:
            logger.debug("BasePage._get_popup_menu 未找到弹出菜单")
        return None, None

    def _close_stray_menu(self) -> None:
        pyautogui.press("esc")
        time.sleep(0.15)

    def _place_tool_on_canvas(
        self,
        x: int,
        y: int,
        canvas_rect,
        *,
        use_drag: bool = False,
        drag_from: tuple[int, int] | None = None,
    ) -> None:
        """在画布目标坐标放置已选中的工具。"""
        if use_drag and drag_from is not None:
            fx, fy = drag_from
            logger.info(f"拖拽放置: ({fx},{fy}) → ({x},{y})")
            pyautogui.moveTo(fx, fy, duration=0.2)
            time.sleep(0.1)
            pyautogui.mouseDown(button="left")
            pyautogui.moveTo(x, y, duration=0.35)
            pyautogui.mouseUp(button="left")
            time.sleep(0.5)
        elif use_drag:
            cx = canvas_rect.left + canvas_rect.width() // 2
            cy = canvas_rect.top + canvas_rect.height() // 2
            pyautogui.moveTo(cx, cy, duration=0.2)
            time.sleep(0.1)
            pyautogui.mouseDown(button="left")
            pyautogui.moveTo(x, y, duration=0.35)
            pyautogui.mouseUp(button="left")
            time.sleep(0.5)
        else:
            self._click_canvas(x, y)

    def add_workflow_tool(
        self,
        tool_key: str,
        timeout: int = 10,
        *,
        x: int | None = None,
        y: int | None = None,
        menu_anchor: tuple[int, int] | None = None,
        use_drag_place: bool = False,
        drag_from: tuple[int, int] | None = None,
    ) -> FilterToolDef:
        """选工具 → 仅在目标坐标单击一次完成放置。"""
        defn = get_filter_tool(tool_key)
        canvas, canvas_rect, cx, cy = self._canvas_center(timeout)
        try:
            self.window.set_focus()
            if hasattr(self.window, "restore"):
                self.window.restore()
        except Exception:
            pass
        time.sleep(0.25)
        px = x if x is not None else cx
        py = y if y is not None else cy
        if menu_anchor is not None:
            menu_x, menu_y = menu_anchor
        else:
            menu_x, menu_y = self._canvas_menu_anchor(canvas_rect)

        self._canvas_descendant_baseline = self._count_canvas_descendants(canvas)
        self._canvas_image_before_add = self._grab_canvas_image(canvas_rect)

        logger.info(
            f"添加工具「{defn.display_name}」({tool_key}) "
            f"放置=({px},{py}) 菜单@({menu_x},{menu_y})"
        )

        self._reset_for_next_tool_add(canvas_rect)
        self._ensure_canvas_ready(canvas_rect)
        selected = False
        for attempt in range(3):
            if attempt > 0:
                self._close_stray_menu()
            menu_win, menu_rect = self._open_filter_menu_at(
                canvas_rect, menu_x, menu_y
            )
            if menu_rect is None:
                logger.warning(
                    f"未找到 Filter QMenu (尝试 {attempt + 1}/3)，重试右键…"
                )
                continue
            if self._select_tool_in_menu(
                canvas_rect, menu_win, menu_rect, defn
            ):
                selected = True
                break
            logger.warning(
                f"菜单选工具「{defn.display_name}」失败 (尝试 {attempt + 1}/3)"
            )
            self._close_stray_menu()

        if not selected:
            logger.info("菜单选工具失败，键盘兜底")
            menu_win, menu_rect = self._open_filter_menu_at(
                canvas_rect, menu_x, menu_y, timeout=3.0
            )
            if menu_rect is not None:
                self._select_tool_by_keyboard(defn)
            else:
                raise RuntimeError(
                    f"无法打开 Filter 菜单以添加工具「{defn.display_name}」"
                )

        time.sleep(0.2)
        self._place_tool_on_canvas(
            px,
            py,
            canvas_rect,
            use_drag=use_drag_place,
            drag_from=drag_from,
        )
        time.sleep(0.5)
        self._finish_tool_placement(canvas_rect)
        self.register_node_position(tool_key, px, py)
        return defn

    def add_workflow_tool_from_placement(
        self,
        placement: NodePlacement,
        timeout: int = 10,
        *,
        use_drag_place: bool = False,
        drag_from: tuple[int, int] | None = None,
    ) -> FilterToolDef:
        """按 LayoutPlan 中的 NodePlacement 添加节点。"""
        _, canvas_rect, _, _ = self._canvas_center(timeout=2)
        return self.add_workflow_tool(
            placement.tool_key,
            timeout=timeout,
            x=placement.x,
            y=placement.y,
            menu_anchor=self._canvas_menu_anchor(canvas_rect),
            use_drag_place=use_drag_place,
            drag_from=drag_from,
        )
