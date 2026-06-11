"""工作流画布定位、布局、连线与节点放置断言（QtNodes::GraphicsView）。"""
import time
from typing import Dict, Tuple

import pyautogui
from PIL import ImageChops

from pages.mixins.filter import FilterToolDef, get_filter_tool
from pages.mixins.locators import (
    WORKFLOW_CANVAS_CLASS,
    WORKFLOW_CANVAS_CLASS_NAMES,
    WORKFLOW_CANVAS_MIN_HEIGHT,
    WORKFLOW_CANVAS_MIN_WIDTH,
)
from pages.mixins.workflow_layout import LayoutPlan, NodePlacement, WorkflowLayoutEngine
from utils.logger import logger


class WorkflowCanvasMixin:
    """画布查找、布局、连线、截图对比（Qt 自绘节点 UIA 常无文本）。"""

    def _init_workflow_canvas_state(self) -> None:
        if not hasattr(self, "_workflow_node_positions"):
            self._workflow_node_positions: Dict[str, Tuple[int, int]] = {}
        if not hasattr(self, "_canvas_zoom"):
            self._canvas_zoom: float = 1.0

    def get_canvas_zoom(self) -> float:
        self._init_workflow_canvas_state()
        return self._canvas_zoom

    def _focus_canvas(self) -> tuple[int, int, object]:
        """点击画布中心获取焦点，返回 (cx, cy, rect)。"""
        _, rect, cx, cy = self._canvas_center()
        pyautogui.click(cx, cy)
        time.sleep(0.15)
        return cx, cy, rect

    def _apply_canvas_zoom_steps(self, steps: int) -> None:
        """Ctrl+滚轮缩放画布（steps>0 放大，steps<0 缩小）。"""
        if steps == 0:
            return
        cx, cy, _ = self._focus_canvas()
        pyautogui.moveTo(cx, cy)
        for _ in range(abs(steps)):
            pyautogui.keyDown("ctrl")
            pyautogui.scroll(1 if steps > 0 else -1)
            pyautogui.keyUp("ctrl")
            time.sleep(0.07)

    def reset_canvas_zoom(self, baseline: float = 1.0) -> None:
        """将画布缩放重置到基准倍数。"""
        self._init_workflow_canvas_state()
        current = self._canvas_zoom
        if abs(current - baseline) < 0.04:
            self._canvas_zoom = baseline
            return
        steps = WorkflowLayoutEngine.zoom_steps_for_factor(baseline / current)
        logger.info(
            f"画布缩放 {current:.0%} → {baseline:.0%} "
            f"(Ctrl+滚轮 {'×' if steps else ''}{abs(steps) if steps else '无需'})"
        )
        self._apply_canvas_zoom_steps(steps)
        self._canvas_zoom = baseline
        time.sleep(0.25)

    def set_canvas_zoom(self, target_zoom: float) -> None:
        """设置画布缩放至目标倍数。"""
        self._init_workflow_canvas_state()
        target = max(
            WorkflowLayoutEngine.MIN_ZOOM,
            min(WorkflowLayoutEngine.MAX_ZOOM, target_zoom),
        )
        current = self._canvas_zoom
        if abs(current - target) < 0.04:
            self._canvas_zoom = target
            return
        steps = WorkflowLayoutEngine.zoom_steps_for_factor(target / current)
        logger.info(
            f"画布缩放 {current:.0%} → {target:.0%} "
            f"(Ctrl+滚轮 {'放大' if steps > 0 else '缩小'} {abs(steps)} 档)"
        )
        self._apply_canvas_zoom_steps(steps)
        self._canvas_zoom = target
        time.sleep(0.25)

    def prepare_canvas_for_tools(
        self,
        tool_keys: list[str] | tuple[str, ...],
    ) -> tuple[float, LayoutPlan]:
        """重置缩放并计算链式步长。"""
        keys = tuple(tool_keys)
        self.reset_canvas_zoom(1.0)
        _, rect = self.get_canvas_rect()

        target_zoom, plan = WorkflowLayoutEngine.plan_viewport_pipeline(
            rect.left,
            rect.top,
            rect.width(),
            rect.height(),
            keys,
        )
        logger.info(
            f"视口布局: 节点={len(keys)}, 画布={rect.width()}x{rect.height()}px, "
            f"目标缩放={target_zoom:.0%}, 链式步长≈{plan.v_gap}px"
        )
        if target_zoom < 0.98:
            self.set_canvas_zoom(target_zoom)
            _, rect = self.get_canvas_rect()
            plan = WorkflowLayoutEngine.compute_viewport_vertical_layout(
                rect.left,
                rect.top,
                rect.width(),
                rect.height(),
                keys,
                zoom_factor=target_zoom,
            )
        else:
            logger.info("视口足够，保持 100% 缩放")
        return target_zoom, plan

    def clear_workflow_node_positions(self) -> None:
        self._init_workflow_canvas_state()
        self._workflow_node_positions.clear()

    def get_workflow_node_position(self, tool_key: str) -> Tuple[int, int] | None:
        self._init_workflow_canvas_state()
        return self._workflow_node_positions.get(tool_key)

    def get_canvas_rect(self, timeout: int = 10):
        """返回画布 pywinauto 控件及其屏幕矩形。"""
        canvas = self.find_workflow_canvas(timeout=timeout)
        return canvas, canvas.rectangle()

    @staticmethod
    def _is_workflow_canvas_candidate(elem) -> bool:
        try:
            if not elem.is_visible():
                return False
            if "GraphicsView" not in (elem.class_name() or ""):
                return False
            rect = elem.rectangle()
            return (
                rect.width() >= WORKFLOW_CANVAS_MIN_WIDTH
                and rect.height() >= WORKFLOW_CANVAS_MIN_HEIGHT
            )
        except Exception:
            return False

    def _pick_largest_canvas(self, elements) -> tuple[object | None, int]:
        best, best_area = None, 0
        for elem in elements:
            if not self._is_workflow_canvas_candidate(elem):
                continue
            try:
                rect = elem.rectangle()
                area = rect.width() * rect.height()
                if area > best_area:
                    best_area, best = area, elem
            except Exception:
                continue
        return best, best_area

    def find_workflow_canvas(self, timeout: int = 10, *, log_result: bool = True):
        """定位 ``QtNodes::GraphicsView``（取面积最大者）。"""
        end = time.time() + timeout
        last_error = None

        while time.time() < end:
            candidates = []
            try:
                candidates.extend(
                    self.window.descendants(class_name=WORKFLOW_CANVAS_CLASS)
                )
            except Exception as e:
                last_error = e

            for class_name in WORKFLOW_CANVAS_CLASS_NAMES:
                if class_name == WORKFLOW_CANVAS_CLASS:
                    continue
                try:
                    candidates.extend(
                        self.window.descendants(class_name=class_name)
                    )
                except Exception as e:
                    last_error = e

            if not candidates:
                try:
                    for elem in self.window.descendants():
                        if "GraphicsView" in (elem.class_name() or ""):
                            candidates.append(elem)
                except Exception as e:
                    last_error = e

            best, best_area = self._pick_largest_canvas(candidates)
            if best is not None:
                msg = (
                    f"工作流画布: class={best.class_name()}, "
                    f"rect={best.rectangle()}, area={best_area}"
                )
                (logger.info if log_result else logger.debug)(msg)
                return best

            time.sleep(0.3)

        raise RuntimeError(
            f"未找到工作流画布 (QtNodes::GraphicsView, last_error={last_error})"
        )

    def log_layout_plan(self, plan: LayoutPlan) -> None:
        logger.info(
            f"布局计划: 节点={plan.node_count}, 缩放={plan.zoom_factor:.0%}, "
            f"画布={plan.canvas_width}x{plan.canvas_height}, "
            f"链式步长={plan.v_gap}px"
        )

    def connect_workflow_nodes(
        self,
        src_tool_key: str,
        dst_tool_key: str,
        *,
        drag_duration: float = 0.65,
        src_branch: str = "exec",
    ) -> None:
        """Exec 连线：源节点下方输出端口 → 目标节点上方输入端口（纵向）。"""
        self._init_workflow_canvas_state()
        src_pos = self._workflow_node_positions.get(src_tool_key)
        dst_pos = self._workflow_node_positions.get(dst_tool_key)
        if src_pos is None or dst_pos is None:
            raise RuntimeError(
                f"连线失败，缺少节点坐标: src={src_tool_key!r} dst={dst_tool_key!r}"
            )

        zoom = self.get_canvas_zoom()
        branch = src_branch
        if branch == "exec" and WorkflowLayoutEngine._is_result_condition(
            src_tool_key
        ):
            branch = "true"
        (sx, sy), (dx, dy) = WorkflowLayoutEngine.connection_endpoints(
            src_tool_key,
            dst_tool_key,
            src_pos,
            dst_pos,
            zoom_factor=zoom,
            src_branch=branch,  # type: ignore[arg-type]
        )
        logger.info(
            f"Exec 连线 {src_tool_key!r} → {dst_tool_key!r}: "
            f"({sx},{sy}) ↓ → ({dx},{dy}) zoom={zoom:.0%}"
        )

        self.mouse_press_key("esc")
        time.sleep(0.2)
        self._focus_canvas()
        time.sleep(0.15)

        pyautogui.moveTo(sx, sy, duration=0.25)
        time.sleep(0.2)
        pyautogui.mouseDown(button="left")
        time.sleep(0.12)
        pyautogui.moveTo(dx, dy, duration=drag_duration)
        time.sleep(0.12)
        pyautogui.mouseUp(button="left")
        time.sleep(0.5)

    def connect_workflow_pipeline(
        self, tool_keys: list[str] | tuple[str, ...]
    ) -> int:
        """按顺序连接流水线相邻节点，返回连线数量。"""
        keys = list(tool_keys)
        count = 0
        for i in range(len(keys) - 1):
            self.connect_workflow_nodes(keys[i], keys[i + 1])
            count += 1
        return count

    def register_node_position(
        self, tool_key: str, x: int, y: int, *, instance: int = 0
    ) -> None:
        """记录节点屏幕坐标（同 key 多次放置用 instance 区分）。"""
        self._init_workflow_canvas_state()
        key = tool_key if instance == 0 else f"{tool_key}#{instance}"
        self._workflow_node_positions[key] = (x, y)
        if instance == 0:
            self._workflow_node_positions[tool_key] = (x, y)

    def _canvas_center(self, timeout: int = 10):
        canvas = self.find_workflow_canvas(timeout=timeout)
        rect = canvas.rectangle()
        cx = rect.left + rect.width() // 2
        cy = rect.top + rect.height() // 2
        return canvas, rect, cx, cy

    @staticmethod
    def _grab_canvas_image(canvas_rect):
        return pyautogui.screenshot(
            region=(
                canvas_rect.left,
                canvas_rect.top,
                canvas_rect.width(),
                canvas_rect.height(),
            )
        )

    @staticmethod
    def _canvas_screenshot_changed(before, after, min_changed_pixels: int = 400) -> bool:
        if before is None or after is None:
            return False
        if before.size != after.size:
            after = after.resize(before.size)
        diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
        if diff.getbbox() is None:
            return False
        return (
            sum(1 for px in diff.getdata() if px != (0, 0, 0))
            >= min_changed_pixels
        )

    @staticmethod
    def _count_canvas_descendants(canvas) -> int:
        try:
            return sum(1 for _ in canvas.descendants())
        except Exception:
            return 0

    @staticmethod
    def _element_text_blob(elem) -> str:
        parts: list[str] = []
        try:
            parts.append(elem.window_text() or "")
        except Exception:
            pass
        try:
            parts.append(getattr(elem.element_info, "name", "") or "")
        except Exception:
            pass
        try:
            leg = elem.legacy_properties()
            for key in ("Name", "Value", "Description"):
                parts.append(leg.get(key) or "")
        except Exception:
            pass
        return " ".join(p for p in parts if p)

    @staticmethod
    def _text_matches_tool(blob: str, defn: FilterToolDef) -> bool:
        if not blob.strip():
            return False
        lower = blob.casefold()
        for marker in (defn.node_name_contains, defn.display_name):
            if marker and marker.casefold() in lower:
                return True
        if defn.node_name_contains and len(defn.node_name_contains) >= 6:
            if defn.node_name_contains[:6].casefold() in lower:
                return True
        return False

    def has_workflow_tool_node_for_key(self, tool_key: str, timeout: int = 10) -> bool:
        defn = get_filter_tool(tool_key)
        if not defn.node_name_contains and not defn.display_name:
            return False

        before_img = getattr(self, "_canvas_image_before_add", None)
        end = time.time() + timeout

        while time.time() < end:
            for elem in self.window.descendants():
                try:
                    if elem.is_visible() and self._text_matches_tool(
                        self._element_text_blob(elem), defn
                    ):
                        logger.info("UIA 找到节点文本")
                        return True
                except Exception:
                    continue

            if before_img is not None:
                try:
                    canvas = self.find_workflow_canvas(timeout=2, log_result=False)
                    after = self._grab_canvas_image(canvas.rectangle())
                    if self._canvas_screenshot_changed(before_img, after):
                        logger.info(
                            f"画布截图有变化，判定已放置: {defn.display_name!r}"
                        )
                        return True
                except RuntimeError:
                    pass

            baseline = getattr(self, "_canvas_descendant_baseline", 0)
            try:
                canvas = self.find_workflow_canvas(timeout=2, log_result=False)
                if self._count_canvas_descendants(canvas) > baseline + 1:
                    logger.info("画布 UIA 子控件增多，判定已放置")
                    return True
            except RuntimeError:
                pass

            time.sleep(0.35)
        return False
