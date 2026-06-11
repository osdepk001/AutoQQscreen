@echo off
chcp 65001 >nul
cd /d "%~dp0rbt\bin"

echo ==================================================
echo   AutoQQ Bot 启动 (后台运行)
echo ==================================================
echo.

:: 杀掉旧进程
echo [1/3] 清理旧进程...
taskkill /f /im pmhq-win-x64.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im QQ.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: 启动 PMHQ
echo [2/3] 启动 PMHQ (QQ 将自动重启)...
cd /d "%~dp0rbt\bin\pmhq"
start "PMHQ" /MIN pmhq-win-x64.exe
timeout /t 3 /nobreak >nul

:: 启动 LLBot
echo [3/3] 启动 Bot 服务...
cd /d "%~dp0rbt\bin\llbot"
start "AutoQQ-Bot" /MIN node --enable-source-maps llbot.js -- --pmhq-port=13000

echo.
echo ==================================================
echo   Bot 启动完成！
echo.
echo   API 地址: http://127.0.0.1:8099
echo.
echo   等待 5 秒后检测 API 是否就绪...
echo ==================================================
timeout /t 5 /nobreak >nul

:: 检测 API
powershell -Command "try {$r=Invoke-RestMethod 'http://127.0.0.1:8099/get_login_info' -Method Post -Body '{}' -ContentType 'application/json' -TimeoutSec 5; Write-Host 'API 就绪! 账号:' $r.data.nickname; exit 0} catch {Write-Host 'API 暂未响应，请稍等后刷新'; exit 0}"

echo.
echo 关闭此窗口不会停止 Bot (后台运行)
echo 现在可以双击 run_autoqq.bat 打开筛选工具
echo.
pause
