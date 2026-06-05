@echo off
chcp 65001 >nul
echo ========================================
echo AIRVision 自动化测试 - 快速启动
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv\" (
    echo [提示] 未找到虚拟环境，正在创建...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境创建完成
    echo.
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖
echo [检查] 正在检查依赖包...
pip show pytest >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
    echo [成功] 依赖安装完成
    echo.
)

REM 运行测试
echo ========================================
echo 开始运行测试
echo ========================================
echo.
python run_tests.py

pause