"""
配置验证工具 - 检查测试环境配置是否正确

检查项：
1. Python 版本
2. 依赖包安装
3. 配置文件有效性
4. 应用路径存在性
5. 必要目录创建
"""
import os
import sys

from utils.config import CONFIG_PATH, load_config, PROJECT_ROOT


def check_python_version():
    """检查 Python 版本"""
    print("检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python 版本过低: {version.major}.{version.minor}.{version.micro}")
        print(f"    需要 Python 3.8 或更高版本")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n检查依赖包...")
    required_packages = [
        ("pytest", "pytest"),
        ("pytest-html", "pytest_html"),
        ("pywinauto", "pywinauto"),
        ("pyautogui", "pyautogui"),
        ("pyperclip", "pyperclip"),
        ("pywin32", "win32api"),
        ("PyYAML", "yaml"),
        ("loguru", "loguru"),
        ("Pillow", "PIL"),
    ]
    
    all_installed = True
    for display_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"  ✓ {display_name}")
        except ImportError:
            print(f"  ✗ {display_name} 未安装")
            all_installed = False
    
    if not all_installed:
        print("\n  提示: 运行 'pip install -r requirements.txt' 安装依赖")
    
    return all_installed


def check_config_file():
    """检查配置文件"""
    print("\n检查配置文件...")

    if not os.path.exists(CONFIG_PATH):
        print(f"  ✗ 配置文件不存在: {CONFIG_PATH}")
        return False, None

    try:
        config = load_config()
        print(f"  ✓ 配置文件有效")
        return True, config
    except Exception as e:
        print(f"  ✗ 配置文件解析失败: {e}")
        return False, None


def check_app_path(config):
    """检查应用路径"""
    print("\n检查应用路径...")
    if not config or "app" not in config:
        print("  ✗ 配置中缺少 'app' 部分")
        return False
    
    app_path = config["app"].get("path", "")
    if not app_path:
        print("  ✗ 未配置应用路径")
        return False
    
    if os.path.exists(app_path):
        print(f"  ✓ 应用存在: {app_path}")
        return True
    else:
        print(f"  ✗ 应用不存在: {app_path}")
        print(f"    请在 config/config.yaml 中配置正确的应用路径")
        return False


def check_directories():
    """检查并创建必要目录"""
    print("\n检查必要目录...")
    directories = ["logs", "screenshots", "reports"]

    all_ok = True
    for dir_name in directories:
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        if os.path.exists(dir_path):
            print(f"  ✓ {dir_name}/")
        else:
            try:
                os.makedirs(dir_path)
                print(f"  ✓ {dir_name}/ (已创建)")
            except Exception as e:
                print(f"  ✗ {dir_name}/ 创建失败: {e}")
                all_ok = False
    
    return all_ok


def main():
    print("=" * 60)
    print("AIRVision 测试环境配置检查")
    print("=" * 60)
    print()
    
    results = []
    
    # 检查 Python 版本
    results.append(("Python 版本", check_python_version()))
    
    # 检查依赖包
    results.append(("依赖包", check_dependencies()))
    
    # 检查配置文件
    config_ok, config = check_config_file()
    results.append(("配置文件", config_ok))
    
    # 检查应用路径
    if config_ok:
        results.append(("应用路径", check_app_path(config)))
    
    # 检查目录
    results.append(("必要目录", check_directories()))
    
    # 总结
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name:.<30} {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ 所有检查通过，环境配置正确！")
        print("  可以运行测试: python run_tests.py")
        return 0
    else:
        print("\n✗ 部分检查失败，请根据上述提示修复问题")
        return 1


if __name__ == "__main__":
    sys.exit(main())