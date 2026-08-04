@echo off
rem AI狼人杀 一键启动脚本（Windows）
rem 用法：双击运行，或命令行执行 start.cmd
rem 前置：已执行过 setup.cmd（创建 .venv 并安装依赖）

cd /d "%~dp0"

echo ========================================
echo   AI 狼人杀 - 本地启动
echo ========================================

rem 1. 检查 .env
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [提示] 已从 .env.example 生成 .env，请按需修改 APP_SECRET_KEY
)

rem 2. 后端（8000 端口）
echo [1/2] 启动后端 http://127.0.0.1:8000 ...
start "AI狼人杀-后端" cmd /c "cd /d %~dp0backend && ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

rem 3. 前端（3000 端口）
echo [2/2] 启动前端 http://localhost:3000 ...
cd frontend
start "AI狼人杀-前端" cmd /c "npm run dev"

echo.
echo 启动完成！浏览器打开 http://localhost:3000
echo 管理员账号：见 .env 中 ADMIN_USERNAME（默认 admin / admin123）
echo 关闭方式：关闭两个黑色窗口即可
pause
