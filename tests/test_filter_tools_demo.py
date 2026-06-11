"""Filter 菜单添加工具 Demo 测试。

覆盖多种选取路径：菜单靠前直点、Filter 搜索、滚轮滚动、远分类等。
"""
import os
import random
import time

import pytest

from pages.mixins.filter import FILTER_TOOLS, get_filter_tool
from tests import flow_steps as fs
from utils.logger import logger

# 固定种子便于复现；环境变量 FILTER_DEMO_SEED=0 则每次随机不同
DEMO_SEED = int(os.environ.get("FILTER_DEMO_SEED", "42"))
DEMO_RANDOM_COUNT = int(os.environ.get("FILTER_DEMO_COUNT", "5"))

# 各策略代表工具（覆盖不同 Filter 交互路径）
DEMO_STRATEGY_TOOLS = [
    pytest.param("d3_circle_detection", id="front_3d_circle"),
    pytest.param("d3_plane_fitting", id="search_3d_plane"),
    pytest.param("mold_cup_path_detection", id="search_mold_cup"),
    pytest.param("communication_send", id="far_comm_send"),
    pytest.param("debug_tool", id="airvision_debug"),
]


class TestFilterToolsDemo:
    """Demo：逐个 / 随机添加 Filter 工具并断言画布节点。"""

    @pytest.fixture(autouse=True)
    def setup(self, page_esc):
        self.page = page_esc

    def _add_and_assert(self, tool_key: str) -> None:
        defn = get_filter_tool(tool_key)
        logger.info(f"Demo 添加工具: {tool_key!r} ({defn.display_name!r})")
        tool = self.page.add_workflow_tool(tool_key)
        assert tool.key == tool_key
        assert self.page.has_workflow_tool_node_for_key(
            tool_key, timeout=20
        ), f"画布上应出现 {defn.display_name!r} 节点"
        time.sleep(0.8)

    @pytest.mark.demo
    @pytest.mark.slow
    @pytest.mark.regression
    @pytest.mark.parametrize("tool_key", DEMO_STRATEGY_TOOLS)
    def test_add_tool_by_strategy(self, tool_key: str):
        """按策略选取的工具：各测例独立准备画布并添加 1 个工具。"""
        fs.prepare_workflow_canvas(self.page)
        self._add_and_assert(tool_key)

    @pytest.mark.demo
    @pytest.mark.slow
    @pytest.mark.regression
    def test_add_random_tools_batch(self):
        """同一工作流内随机添加 N 个工具（默认 5，可 FILTER_DEMO_COUNT 调整）。"""
        rng = random.Random(DEMO_SEED)
        pool = list(FILTER_TOOLS)
        count = min(DEMO_RANDOM_COUNT, len(pool))
        picked = rng.sample(pool, count)
        keys = [t.key for t in picked]

        logger.info(
            f"随机工具 Demo: seed={DEMO_SEED}, count={count}, keys={keys}"
        )
        fs.prepare_workflow_canvas(self.page)

        for key in keys:
            self.page.mouse_press_key("esc")
            time.sleep(0.3)
            self._add_and_assert(key)

        logger.info(f"随机 Demo 完成，成功添加 {count} 个工具")
