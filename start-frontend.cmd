@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist frontend\node_modules (
  echo [错误] 未找到 node_modules，请先执行 setup.cmd 完成环境初始化
  pause
  exit /b 1
)
echo 启动前端 http://localhost:3000 ...
cd frontend
call npm run dev
pause
