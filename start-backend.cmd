@echo off
rem AI Werewolf - backend only (port 8000)

cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo [ERROR] .venv not found. Please run setup.cmd first.
    pause
    exit /b 1
)
if not exist .env (
    copy .env.example .env >nul
    echo [INFO] .env created from .env.example. Please edit APP_SECRET_KEY if needed.
)
echo Starting backend  http://127.0.0.1:8000 ...
cd backend
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
