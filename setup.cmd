@echo off
rem AI Werewolf - first-time setup (Windows)
rem Creates .venv, installs backend deps, installs frontend deps

cd /d "%~dp0"

echo ========================================
echo   AI Werewolf - First-Time Setup
echo ========================================

echo [1/3] Creating Python venv .venv ...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] Please install Python 3.11+ and add it to PATH.
    pause
    exit /b 1
)

echo [2/3] Installing backend dependencies ...
".venv\Scripts\python" -m pip install --upgrade pip
".venv\Scripts\python" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Backend dependency install failed.
    pause
    exit /b 1
)

echo [3/3] Installing frontend dependencies ...
cd frontend
call npm install
if errorlevel 1 (
    echo [ERROR] Frontend dependency install failed.
    pause
    exit /b 1
)
cd ..

echo.
echo Setup complete! Run start.cmd to launch the app.
pause
