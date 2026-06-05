"""
清理工具 - 清理测试生成的临时文件和目录

清理内容：
- logs/ 目录中的日志文件
- screenshots/ 目录中的截图
- reports/ 目录中的报告
- __pycache__ 缓存目录
- .pytest_cache 目录
"""
import os
import shutil
import sys


def remove_directory(path):
    """删除目录及其内容"""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            print(f"✓ 已删除: {path}")
            return True
        except Exception as e:
            print(f"✗ 删除失败 {path}: {e}")
            return False
    return False


def remove_files_in_directory(path, pattern="*"):
    """删除目录中的文件但保留目录"""
    if os.path.exists(path):
        try:
            count = 0
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    count += 1
            if count > 0:
                print(f"✓ 已清理 {count} 个文件: {path}")
            return True
        except Exception as e:
            print(f"✗ 清理失败 {path}: {e}")
            return False
    return False


def main():
    print("=" * 60)
    print("AIRVision 测试清理工具")
    print("=" * 60)
    print()

    project_root = os.path.dirname(__file__)
    
    # 清理日志
    logs_dir = os.path.join(project_root, "logs")
    remove_files_in_directory(logs_dir)
    
    # 清理截图
    screenshots_dir = os.path.join(project_root, "screenshots")
    remove_files_in_directory(screenshots_dir)
    
    # 清理报告
    reports_dir = os.path.join(project_root, "reports")
    remove_files_in_directory(reports_dir)
    
    # 清理缓存
    cache_dirs = [
        os.path.join(project_root, "__pycache__"),
        os.path.join(project_root, ".pytest_cache"),
        os.path.join(project_root, "pages", "__pycache__"),
        os.path.join(project_root, "tests", "__pycache__"),
        os.path.join(project_root, "utils", "__pycache__"),
    ]
    
    for cache_dir in cache_dirs:
        remove_directory(cache_dir)
    
    print()
    print("=" * 60)
    print("清理完成")
    print("=" * 60)


if __name__ == "__main__":
    main()