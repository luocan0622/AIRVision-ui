"""
快速运行脚本 - 仅运行冒烟测试
"""
import subprocess
import sys

def main():
    """运行冒烟测试用例"""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "-m",
        "smoke",
        "--tb=short"
    ]
    
    print("=" * 60)
    print("运行冒烟测试 (Smoke Tests)")
    print("=" * 60)
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()