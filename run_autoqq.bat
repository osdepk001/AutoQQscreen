@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==================================================
echo   AutoQQ 筛选工具
echo ==================================================
echo.

echo 正在启动筛选工具...
start python qq_gui.py

echo.
echo 筛选工具已启动！
echo 如果 Bot 未运行，请先双击 run_rbt.bat 启动 Bot
echo.
timeout /t 3 /nobreak >nul
