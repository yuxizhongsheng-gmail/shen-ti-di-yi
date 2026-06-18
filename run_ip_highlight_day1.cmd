@echo off
chcp 65001 >nul 2>&1
setlocal

echo.
echo ╔══════════════════════════════════════════════╗
echo ║       IP 群高光 · Day 1 Bot                  ║
echo ╚══════════════════════════════════════════════╝
echo.

REM --- 检查参数 ---
if "%~1"=="" (
    echo 用法: run_ip_highlight_day1.cmd 2026-W25
    echo.
    echo 示例:
    echo   run_ip_highlight_day1.cmd 2026-W24
    echo   run_ip_highlight_day1.cmd 2026-W25
    echo.
    echo 运行前请确保:
    echo   1. 手机已用 USB 连接电脑
    echo   2. 手机开启了 USB 调试
    echo   3. 手机微信已打开到目标群的本周聊天位置
    echo.
    exit /b 1
)

set WEEK=%~1

echo 运行前请确保:
echo   1. 手机已用 USB 连接电脑，ADB 可用
echo   2. 手机开启了「开发者选项 - USB 调试」
echo   3. 手机微信已打开到「25IP训练营交流群」
echo   4. 已滚动到本周聊天记录起始位置附近
echo.

REM --- 切换到项目目录 ---
cd /d "%~dp0"

REM --- 运行 Day 1 全流程 ---
python -m src.ip_highlight_cli day1 --week %WEEK%

if errorlevel 1 (
    echo.
    echo ❌ 运行失败。请检查上方错误信息。
    echo.
    echo 常见问题:
    echo   - ADB 未找到: 把 adb.exe 放到 tools\platform-tools\ 下
    echo   - 手机未连接: 检查 USB 线和调试开关
    echo   - Tesseract 未安装: OCR 步骤会生成空模板，需手动填写
    echo   - Python 未安装: 需要 Python 3.9+
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ 完成！请查看 runs\%WEEK%\ 目录下的输出文件。
echo.
pause
