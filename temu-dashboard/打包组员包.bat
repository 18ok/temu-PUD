@echo off
chcp 65001 >nul
cd /d "%~dp0"
set OUT=Temu看板-V10-组员包

echo.
echo   ╔══════════════════════════════════════╗
echo   ║      V10 看板 — 一键打包分发          ║
echo   ╚══════════════════════════════════════╝
echo.

if exist "%OUT%" rmdir /s /q "%OUT%"
if exist "%OUT%.zip" del "%OUT%.zip"

mkdir "%OUT%"

copy /y temu-dashboard.html "%OUT%\" >nul
copy /y local_server.py "%OUT%\" >nul
copy /y 启动本地看板.bat "%OUT%\" >nul
copy /y 组员使用说明.html "%OUT%\" >nul

echo 【Temu 看板 V10 — 3 步上手】> "%OUT%\先看这里.txt"
echo.>> "%OUT%\先看这里.txt"
echo 1. 安装 Python 3（若还没有）：https://www.python.org/downloads/>> "%OUT%\先看这里.txt"
echo    ⚠️ 安装时勾选 "Add Python to PATH">> "%OUT%\先看这里.txt"
echo.>> "%OUT%\先看这里.txt"
echo 2. 双击「启动本地看板.bat」>> "%OUT%\先看这里.txt"
echo    浏览器自动打开 http://localhost:8080/temu-dashboard.html>> "%OUT%\先看这里.txt"
echo.>> "%OUT%\先看这里.txt"
echo 3. OSS 配置找玉成私聊（Key 全组共用，归属人每人不同）>> "%OUT%\先看这里.txt"
echo.>> "%OUT%\先看这里.txt"
echo 详细说明：双击「组员使用说明.html」>> "%OUT%\先看这里.txt"

powershell Compress-Archive -Path "%OUT%" -DestinationPath "%OUT%.zip" -Force

echo   ✅ 已生成 %OUT%.zip
echo   📁 位置：%CD%\%OUT%.zip
echo.
echo   ⚠️ zip 里没有 AccessKey — Key 需玉成私聊发给组员。
echo.
pause
