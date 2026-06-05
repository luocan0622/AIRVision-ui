"""工作流画布定位与节点放置断言（QtNodes::GraphicsView）。"""
import time

import pyautogui
from PIL import ImageChops

from tests.model.filter import FilterToolDef, get_filter_tool
from tests.model.locators import (
    WORKFLOW_CANVAS_CLASS,
    WORKFLOW_CANVAS_CLASS_NAMES,
    WORKFLOW_CANVAS_MIN_HEIGHT,
    WORKFLOW_CANVAS_MIN_WIDTH,
)
from utils.logger import logger


class WorkflowCanvasMixin:
    """画布查找、截图对比（Qt 自绘节点 UIA 常无文本）。"""

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
