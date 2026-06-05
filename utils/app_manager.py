"""应用生命周期管理器。

负责被测应用的启动、连接、进程发现和优雅/强制关闭。
支持先检测是否已运行再决定启动还是连接，避免重复启动。
"""
import os
import time
import subprocess

from pywinauto import Application
from pywinauto.findwindows import find_elements
from pywinauto.timings import wait_until_passes
from utils.logger import logger


class AppManager:
    """应用生命周期管理：启动、连接、关闭。"""

    def __init__(
        self,
        app_path: str,
        backend: str = "uia",
        timeout: int = 10,
        window_wait: int = 60,
    ):
        """
        Args:
            app_path: 被测应用可执行文件的完整路径。
            backend: 'uia' 适用于现代应用，'win32' 适用于老式应用。
            timeout: pywinauto 操作的默认超时时间（秒）。
            window_wait: 进程启动后等待 GUI 窗口出现的最大秒数
                         （部分应用启动较慢）。
        """
        self.app_path = app_path
        self.backend = backend
        self.timeout = timeout
        self.window_wait = window_wait
        self.exe_name = os.path.basename(app_path)
        self.app: Application = None

    # ─── 进程发现 ──────────────────────────────────────────────────────

    def _find_running_pids(self) -> list:
        """返回与 exe 名称匹配的正在运行的进程 PID 列表。"""
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {self.exe_name}", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
            ).decode("gbk", errors="ignore")
            matching = []
            for line in out.strip().splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[0].lower() == self.exe_name.lower():
                    try:
                        matching.append(int(parts[1].strip('"')))
                    except ValueError:
                        pass
            return matching
        except Exception as e:
            logger.debug(f"tasklist failed: {e}")
            return []

    def is_running(self, window_title: str = "MainWindow") -> bool:
        """判断应用是否已启动且主窗口可见。

        Args:
            window_title: 主窗口标题或类名（config 中 app.title，默认 MainWindow）。

        Returns:
            True 表示进程在运行且能找到对应主窗口。
        """
        for pid in self._find_running_pids():
            try:
                for elem in find_elements(
                    backend=self.backend, process=pid, top_level_only=True
                ):
                    name = (elem.name or "").strip()
                    class_name = (elem.class_name or "").strip()
                    if name == window_title or class_name == window_title:
                        logger.info(
                            f"应用已运行: window={name!r}, class={class_name!r}, pid={pid}"
                        )
                        return True
            except Exception as e:
                logger.debug(f"检查窗口失败 pid={pid}: {e}")
        return False

    def _wait_for_window(self, pid: int, window_title: str = "MainWindow") -> bool:
        """轮询等待指定 pid 的顶层可见主窗口出现。"""
        end = time.time() + self.window_wait
        while time.time() < end:
            try:
                for elem in find_elements(backend=self.backend, process=pid, top_level_only=True):
                    name = (elem.name or "").strip()
                    class_name = (elem.class_name or "").strip()
                    if name == window_title or class_name == window_title:
                        logger.info(
                            f"Window detected: title={name!r}, class={class_name!r}, pid={pid}"
                        )
                        return True
            except Exception as e:
                logger.debug(f"Waiting for window: {e}")
            time.sleep(1)
        return False

    # ─── 生命周期 ──────────────────────────────────────────────────────

    def start(self, wait_for_idle: bool = False, window_title: str = "MainWindow", **kwargs) -> Application:
        """启动应用并等待主窗口出现。

        Args:
            wait_for_idle: 是否等待进程进入空闲状态。
            window_title: 主窗口标题或类名。
            **kwargs: 传递给 Application.start() 的额外参数。

        Returns:
            pywinauto Application 实例。
        """
        logger.info(f"Starting application: {self.app_path}")
        try:
            self.app = Application(backend=self.backend).start(
                self.app_path,
                timeout=self.timeout,
                wait_for_idle=wait_for_idle,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise

        pid = self.app.process
        logger.info(f"Process started (pid={pid}), waiting for GUI window...")
        if not self._wait_for_window(pid, window_title):
            raise TimeoutError(
                f"Application window {window_title!r} did not appear within "
                f"{self.window_wait}s (pid={pid}, exe={self.exe_name})"
            )
        logger.info("Application started successfully")
        return self.app

    def connect(self, **kwargs) -> Application:
        """连接到已运行的应用。

        Args:
            **kwargs: 传递给 Application.connect() 的参数，
                      例如 title="窗口标题"、process=1234。

        Returns:
            pywinauto Application 实例。
        """
        logger.info(f"Connecting to application with params: {kwargs}")
        try:
            self.app = Application(backend=self.backend).connect(**kwargs)
            logger.info("Connected to application successfully")
        except Exception as e:
            logger.error(f"Failed to connect to application: {e}")
            raise
        return self.app

    def start_or_connect(self, window_title: str = "MainWindow") -> Application:
        """若应用已打开则连接，否则启动应用。

        Args:
            window_title: 主窗口标题或类名，用于判断应用是否已就绪。

        Returns:
            pywinauto Application 实例。
        """
        if self.is_running(window_title):
            pids = self._find_running_pids()
            pid = pids[0]
            logger.info(f"应用已打开 (pid={pid})，跳过启动，直接连接...")
            self.connect(process=pid)
            time.sleep(1)
            return self.app

        logger.info("应用未打开，正在启动...")
        return self.start(window_title=window_title)

    def close(self, force: bool = False):
        """关闭应用；测试会话结束时调用。

        Args:
            force: 若为 True，跳过优雅关闭直接终止进程。
        """
        pids = self._find_running_pids()

        if self.app is None and not pids:
            logger.info("应用未运行，无需关闭")
            return

        logger.info("正在关闭应用...")
        try:
            if self.app and not force:
                top = self.app.top_window()
                top.close()
                time.sleep(2)
        except Exception as e:
            logger.debug(f"优雅关闭失败: {e}")

        still_running = self._find_running_pids()
        if still_running:
            logger.warning("应用未正常退出，强制结束进程...")
            if self.app:
                try:
                    self.app.kill()
                except Exception as e:
                    logger.error(f"kill 失败: {e}")
            for pid in still_running:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/F"],
                        check=False,
                        capture_output=True,
                    )
                except Exception as e:
                    logger.error(f"taskkill pid={pid} 失败: {e}")

        self.app = None
        logger.info("应用已关闭")

    def get_window(self, title: str = None, **kwargs):
        """获取主窗口或指定标题的窗口。

        Args:
            title: 窗口标题或标题正则。
            **kwargs: 窗口匹配的其他条件。

        Returns:
            WindowSpecification 对象。
        """
        if self.app is None:
            raise RuntimeError("Application is not started or connected")

        if title:
            return self.app.window(title=title, **kwargs)
        return self.app.top_window()
