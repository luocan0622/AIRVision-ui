"""项目根 conftest：将项目根目录添加到 Python 路径，使 pytest 能正确导入项目模块。"""
import os
import sys

# 将项目根目录添加到 Python 路径，确保 tests/、pages/、utils/ 等子包可被 import
sys.path.insert(0, os.path.dirname(__file__))
