@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 迁移 OSS Key 到 .env

echo.
echo   ╔══════════════════════════════════════════════╗
echo   ║  一键迁移 AccessKey → 本地 .env              ║
echo   ╚══════════════════════════════════════════════╝
echo.
echo   前提：「启动本地看板.bat」已在运行，且浏览器里曾保存过 OSS Key
echo.
echo   [1] 若 bat 窗口是旧版，请先关掉再双击「启动本地看板.bat」
echo   [2] 即将打开看板并自动迁移（或点 ⚙ OSS → 一键迁移）
echo.

start "" http://localhost:8080/temu-dashboard.html

echo   浏览器打开后请按 Ctrl+F5 强刷一次
echo   成功时会 toast：Key 已写入 .env
echo   然后请重启「启动本地看板.bat」使 .env 在下次启动时加载
echo.
pause
