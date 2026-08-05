@echo off
rem AI Werewolf - frontend only (port 3000)

cd /d "%~dp0"
if not exist frontend\node_modules (
    echo [ERROR] node_modules not found. Please run setup.cmd first.
    pause
    exit /b 1
)
echo Starting frontend  http://localhost:3000 ...
cd frontend
call npm run dev
pause
