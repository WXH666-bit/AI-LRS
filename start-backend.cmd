@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo [错误] 未找到 .venv，请先执行 setup.cmd 完成环境初始化
  pause
  exit /b 1
)
if not exist .env (
  copy .env.example .env >nul
  echo [提示] 已从 .env.example 生成 .env，请修改 APP_SECRET_KEY
)
echo 启动后端 http://127.0.0.1:8000  ...
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
