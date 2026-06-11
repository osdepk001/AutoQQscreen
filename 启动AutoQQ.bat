@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==================================================
echo   AutoQQ 启动器
echo ==================================================
echo.
echo   正在启动图形化管理界面...
echo.
echo   启动后按以下步骤操作：
echo     1. 点击「启动 Bot 服务」按钮
echo     2. 等待服务就绪后，点击「打开筛选工具」
echo.
echo ==================================================

REM 优先使用打包好的 exe（无需 Python），否则用 Python 运行
if exist "%~dp0autoqq_launcher.exe" (
    start "" "%~dp0autoqq_launcher.exe"
) else (
    start python autoqq_launcher.py
)
