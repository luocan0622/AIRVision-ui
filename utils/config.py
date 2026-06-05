"""项目配置加载与路径常量。"""
import os

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "config.yaml")

_DEFAULT_TEST_PATHS = {
    "project": r"C:\Users\luoca\Desktop\test\new_project",
    "save_as_project": r"C:\Users\luoca\Desktop\test\Save_AS_Project",
    "template_images": r"C:\Users\luoca\Desktop\test\模型\重命名",
    "default_template_image": "moban1.png",
    "default_depth_image": "moban2.png",
    "default_workflow_filename": "Untitled-1.json",
}


def load_config() -> dict:
    """从 config/config.yaml 加载配置。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_test_paths(config: dict = None) -> dict:
    """获取测试用文件/目录路径（config.test_paths，缺失时使用默认值）。"""
    if config is None:
        config = load_config()
    paths = config.get("test_paths") or {}
    return {key: paths.get(key, default) for key, default in _DEFAULT_TEST_PATHS.items()}
