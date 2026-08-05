@echo off
rem AI Werewolf - one-click launcher (Windows)
rem Usage: double-click or run `start.cmd`
rem Prerequisite: run setup.cmd once first

cd /d "%~dp0"

echo ========================================
echo   AI Werewolf - Local Launcher
echo ========================================

rem 1. Create .env from template if missing
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [INFO] .env created from .env.example. Please edit APP_SECRET_KEY if needed.
)

rem 2. Start backend on port 8000
echo [1/2] Starting backend  http://127.0.0.1:8000 ...
start "AI-Werewolf-Backend" cmd /c "cd /d %~dp0backend && ..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 3 /nobreak >nul

rem 3. Start frontend on port 3000
echo [2/2] Starting frontend  http://localhost:3000 ...
cd frontend
start "AI-Werewolf-Frontend" cmd /c "npm run dev"

echo.
echo Done! Open http://localhost:3000 in your browser.
echo Admin account: see ADMIN_USERNAME in .env (default admin / admin123)
echo To stop: close both console windows.
pause
