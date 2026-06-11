"""全局日志配置（基于 loguru）。

双通道输出：
- 控制台：INFO 级别，带颜色，格式为 时间 | 级别 | 位置 | 消息
- 文件：DEBUG 级别，按天轮转，保留 7 天，保存在 logs/ 目录
"""
import os
import sys
from loguru import logger

# 移除 loguru 默认处理器，避免重复输出
logger.remove()

# 创建日志目录（项目根目录下 logs/）
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 控制台输出：INFO 级别（用 stderr，避免与 pytest 捕获 stdout 冲突）
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
           "<level>{message}</level>",
)

# 文件输出：DEBUG 级别，按天轮转（rotation="1 day"），保留最近 7 天
logger.add(
    os.path.join(LOG_DIR, "test_{time:YYYY-MM-DD}.log"),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
           "{name}:{function}:{line} - {message}",
    rotation="1 day",
    retention="7 days",
    encoding="utf-8",
)
