@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ========================================
echo   Temu 看板本地服务（含 OSS 代理）
echo   目录: %CD%
echo ========================================
echo.
echo 浏览器打开:
echo   http://localhost:8080/temu-dashboard.html
echo.
echo 云端同步走本地代理，无需配置 OSS 跨域 CORS
echo 按 Ctrl+C 可停止服务
echo.
python local_server.py
