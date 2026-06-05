"""
控件检查工具 - 用于调试和开发时查看应用控件树

使用方法：
    python inspect_controls.py [--depth DEPTH]

参数：
    --depth: 控件树深度，默认为 3
"""
import argparse
import sys

from utils.app_manager import AppManager
from utils.config import load_config
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="AIRVision 控件检查工具")
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="控件树深度 (默认: 3)"
    )
    args = parser.parse_args()

    # 加载配置
    config = load_config()
    app_cfg = config["app"]

    # 连接或启动应用
    manager = AppManager(
        app_path=app_cfg["path"],
        backend=app_cfg["backend"],
        timeout=app_cfg["timeout"],
    )

    try:
        logger.info("正在连接到 AIRVision 应用...")
        manager.start_or_connect(window_title=app_cfg.get("title", "MainWindow"))
        
        logger.info(f"打印控件树 (深度={args.depth})...")
        print("\n" + "=" * 80)
        print("AIRVision 控件树")
        print("=" * 80 + "\n")
        
        window = manager.app.top_window()
        window.print_control_identifiers(depth=args.depth)
        
        print("\n" + "=" * 80)
        logger.info("控件树打印完成")
        
    except Exception as e:
        logger.error(f"检查控件失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()