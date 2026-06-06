@echo off
chcp 65001 >nul
cd /d "%~dp0"
set VER=V10.2.4
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

:: 试用必读（纯文本，微信也能看）
(
echo 【Temu 选品助手 %VER% — 同事试用】
echo.
echo ★ 推荐：打开网页（不用 Python）
echo    https://18ok.github.io/temu-PUD/
echo    → 数据导入 → 拖两份 Excel → 🏆 个人 PK
echo.
echo 1. 店铺利润统计 .xls + 店铺数据记录 .xlsx
echo 2. 团队云端（可选）：侧边栏 ⚙ OSS 填 Key → 📥 团队
echo    Key 找玉成私聊，勿发群
echo.
echo ── 备选：本压缩包本地 bat ──
echo 仅无网或管理员用：双击「启动本地看板.bat」
echo 不要直接双击 HTML 文件
echo.
echo ── 使用限制（必读）──
echo · 内部试用，勿把 Key 发给团队外的人
echo · PK 是个人对齐分，不是团队排名
echo · 协作版尚未开放
echo · 公司数据勿发群 / 勿发 AI
echo.
echo 详细说明：组员使用说明.html
) > "%OUT%\先看这里.txt"

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
