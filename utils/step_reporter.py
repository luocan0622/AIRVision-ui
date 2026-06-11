"""测试步骤记录器：收集每步截图、耗时与元数据，供 Airtest 风格报告生成。"""
from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from utils.logger import logger
from utils.screenshot import take_screenshot

T = TypeVar("T")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_ROOT = PROJECT_ROOT / "reports" / "airtest"


@dataclass
class StepRecord:
    """单条测试步骤记录。"""

    index: int
    title: str
    action: str
    status: str  # passed | failed | skipped
    timestamp: str
    duration_ms: int
    screenshot: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class StepReporter:
    """当前测试用例的步骤收集器。"""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.test_id: str = ""
        self.script_name: str = ""
        self.device: str = "Windows"
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.status: str = "running"
        self.steps: list[StepRecord] = []
        self._report_dir: Optional[Path] = None
        self._screenshot_dir: Optional[Path] = None

    def start_test(self, test_id: str, script_name: str, device: str = "Windows") -> None:
        self.reset()
        self.test_id = test_id
        self.script_name = script_name
        self.device = device
        self.start_time = datetime.now()
        self.status = "running"

        safe_name = _safe_filename(test_id)
        session_stamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self._report_dir = REPORT_ROOT / session_stamp / safe_name
        self._screenshot_dir = self._report_dir / "screenshots"
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Step reporter started: {self._report_dir}")

    def add_step(
        self,
        title: str,
        action: str,
        *,
        status: str = "passed",
        duration_ms: int = 0,
        screenshot_path: str = "",
        args: Optional[dict[str, Any]] = None,
        error: str = "",
    ) -> StepRecord:
        index = len(self.steps) + 1
        rel_screenshot = ""

        if screenshot_path and self._screenshot_dir is not None:
            src = Path(screenshot_path)
            if src.is_file():
                dest_name = f"step_{index:03d}_{_safe_filename(title)}.png"
                dest = self._screenshot_dir / dest_name
                try:
                    shutil.copy2(src, dest)
                    rel_screenshot = f"screenshots/{dest_name}"
                except OSError as exc:
                    logger.warning(f"Could not copy screenshot to report dir: {exc}")

        record = StepRecord(
            index=index,
            title=title,
            action=action,
            status=status,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_ms=duration_ms,
            screenshot=rel_screenshot,
            args=args or {},
            error=error,
        )
        self.steps.append(record)
        return record

    def finish_test(self, status: str) -> None:
        self.end_time = datetime.now()
        self.status = status
        if status == "failed" and self.steps and self.steps[-1].status == "passed":
            last = self.steps[-1]
            self.steps[-1] = StepRecord(
                index=last.index,
                title=last.title,
                action=last.action,
                status="failed",
                timestamp=last.timestamp,
                duration_ms=last.duration_ms,
                screenshot=last.screenshot,
                args=last.args,
                error=last.error,
            )

    @property
    def duration_ms(self) -> int:
        if not self.start_time:
            return 0
        end = self.end_time or datetime.now()
        return int((end - self.start_time).total_seconds() * 1000)

    @property
    def report_dir(self) -> Optional[Path]:
        return self._report_dir

    def to_dict(self) -> dict[str, Any]:
        start = self.start_time or datetime.now()
        end = self.end_time or datetime.now()
        status_label = {
            "passed": "运行成功",
            "failed": "运行失败",
            "skipped": "已跳过",
            "running": "运行中",
        }.get(self.status, self.status)

        return {
            "title": "AIRVision 自动化测试报告",
            "test_id": self.test_id,
            "status": self.status,
            "status_label": status_label,
            "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_ms": self.duration_ms,
            "step_count": len(self.steps),
            "author": "pytest",
            "script": self.script_name,
            "device": self.device,
            "steps": [
                {
                    "index": s.index,
                    "title": s.title,
                    "action": s.action,
                    "status": s.status,
                    "timestamp": s.timestamp,
                    "duration_ms": s.duration_ms,
                    "screenshot": s.screenshot,
                    "args": s.args,
                    "error": s.error,
                }
                for s in self.steps
            ],
        }


_reporter = StepReporter()


def get_reporter() -> StepReporter:
    return _reporter


def _safe_filename(name: str, max_len: int = 60) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", name)
    cleaned = cleaned.strip("._")
    return cleaned[:max_len] or "step"


def execute_step(
    title: str,
    action: str,
    func: Callable[[], T],
    *,
    args: Optional[dict[str, Any]] = None,
    pause: float = 0,
    screenshot: bool = True,
) -> T:
    """执行一步操作：计时、截图并写入步骤报告。"""
    start = time.perf_counter()
    status = "passed"
    error = ""
    result: Any = None

    try:
        result = func()
        return result
    except Exception as exc:
        status = "failed"
        error = str(exc)
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        if pause:
            time.sleep(pause)

        screenshot_path = ""
        if screenshot:
            shot_name = f"tmp_{get_reporter().test_id}_{len(get_reporter().steps) + 1}"
            screenshot_path = take_screenshot(name=_safe_filename(shot_name))

        get_reporter().add_step(
            title=title,
            action=action,
            status=status,
            duration_ms=duration_ms,
            screenshot_path=screenshot_path,
            args=args,
            error=error,
        )
