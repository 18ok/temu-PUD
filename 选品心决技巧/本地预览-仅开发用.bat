@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 选品心决 · 本地预览（仅开发者）

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [开发用] 未检测到 Python，无法启动本地 HTTP 预览。
    echo 读者请使用 GitHub Pages 链接，不要发此 bat 给任何人。
    pause
    exit /b 1
)

echo.
echo   [开发用] 选品心决本地预览
echo   http://localhost:8765/
echo.
echo   正式网址见 选品心决技巧.txt
echo   关闭此窗口即停止服务
echo.

start "" http://localhost:8765/
python -m http.server 8765
