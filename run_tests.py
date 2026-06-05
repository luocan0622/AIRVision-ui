"""
快速运行脚本 - 运行所有测试
"""
import subprocess
import sys

def main():
    """运行所有测试用例"""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
        "--html=reports/report.html",
        "--self-contained-html"
    ]
    
    print("=" * 60)
    print("运行 AIRVision 自动化测试")
    print("=" * 60)
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()