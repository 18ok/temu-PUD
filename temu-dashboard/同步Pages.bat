@echo off
chcp 65001 >nul
cd /d "%~dp0"
copy /Y "temu-dashboard.html" "docs\index.html"
copy /Y "temu-dashboard-editorial.html" "docs\editorial.html"
if %errorlevel% equ 0 (
    echo OK: docs\index.html 已与 temu-dashboard.html 同步
    echo OK: docs\editorial.html 已与 temu-dashboard-editorial.html 同步
) else (
    echo 同步失败，请检查路径
    pause
)
