@echo off
chcp 65001 >nul
cd /d "%~dp0"
set VER=V10.3.1
set OUT=Temu选品助手-%VER%-组员试用包

echo.
echo   ╔══════════════════════════════════════╗
echo   ║   Temu 选品助手 %VER% — 打包分发      ║
echo   ╚══════════════════════════════════════╝
echo.

if exist "%OUT%" rmdir /s /q "%OUT%"
if exist "%OUT%.zip" del "%OUT%.zip"

mkdir "%OUT%"

copy /y temu-dashboard.html "%OUT%\" >nul
copy /y local_server.py "%OUT%\" >nul
copy /y 启动本地看板.bat "%OUT%\" >nul
copy /y 组员使用说明.html "%OUT%\" >nul
copy /y OSS与协作版说明.html "%OUT%\" >nul
copy /y .env.example "%OUT%\" >nul
copy /y CHANGELOG.md "%OUT%\" >nul
copy /y 先看这里.txt "%OUT%\" >nul

powershell -NoProfile -Command "Compress-Archive -LiteralPath '%OUT%' -DestinationPath '%OUT%.zip' -Force"

if exist "%OUT%.zip" (
    echo   ✅ 已生成 %OUT%.zip
    echo   📁 位置：%CD%\%OUT%.zip
    echo.
    echo   📦 包内文件：看板 + 本地服务 + 说明（无 .env / 无 Key）
    echo   ⚠️  云端同步需玉成单独发 .env
) else (
    echo   ❌ 压缩失败，请检查文件夹 %OUT%
)
echo.
pause
