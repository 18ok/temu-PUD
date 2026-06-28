@echo off
pushd "%~dp0"
copy /Y "temu-dashboard.html" "docs\index.html"
copy /Y "temu-dashboard-editorial.html" "docs\editorial.html"
python -c "import shutil; from pathlib import Path; names=['\u7ec4\u5458\u4f7f\u7528\u8bf4\u660e.html','OSS\u4e0e\u534f\u4f5c\u7248\u8bf4\u660e.html','\u5148\u770b\u8fd9\u91cc.txt']; [shutil.copy2(n, Path('docs') / n) for n in names]"
if %errorlevel% equ 0 (
    echo OK: docs\index.html synced from temu-dashboard.html
    echo OK: docs\editorial.html synced from temu-dashboard-editorial.html
    echo OK: docs guide files synced
) else (
    echo Sync failed. Check paths.
    pause
)
popd
