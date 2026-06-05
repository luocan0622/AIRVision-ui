@echo off
chcp 65001 >nul
echo ========================================
echo AIRVision 冒烟测试 - 快速启动
echo ========================================
echo.

REM 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM 运行冒烟测试
python run_smoke.py

pause