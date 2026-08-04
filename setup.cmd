@echo off
rem AI狼人杀 首次安装脚本（Windows）
rem 创建 .venv、安装后端依赖、安装前端依赖

cd /d "%~dp0"

echo ========================================
echo   AI 狼人杀 - 首次安装
echo ========================================

echo [1/3] 创建 Python 虚拟环境 .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [错误] 请先安装 Python 3.11+ 并加入 PATH
    pause
    exit /b 1
)

echo [2/3] 安装后端依赖 ...
".venv\Scripts\python" -m pip install --upgrade pip
".venv\Scripts\python" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo [3/3] 安装前端依赖 ...
cd frontend
call npm install
if errorlevel 1 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)
cd ..

echo.
echo 安装完成！运行 start.cmd 启动应用。
pause
