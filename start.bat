@echo off
chcp 65001 >nul
title OpenDrama Studio v2.0
cd /d "%~dp0"

:menu
cls
echo.
echo ╔══════════════════════════════════════════╗
echo ║     🎬 OpenDrama Studio v2.0             ║
echo ║     AI 短剧全链路工厂                      ║
echo ╚══════════════════════════════════════════╝
echo.
echo   [1] 检测全链路状态
echo   [2] 自动启动 ComfyUI
echo   [3] 生成短剧 (示例剧本)
echo   [4] 生成短剧 (自定义剧本)
echo   [5] 启动 Web UI
echo   [6] 启动监控面板
echo   [7] 批量生成
echo   [0] 退出
echo.
set /p choice="请选择 [0-7]: "

if "%choice%"=="1" (
    python check_all.py
    pause
    goto menu
)
if "%choice%"=="2" (
    python launcher.py
    pause
    goto menu
)
if "%choice%"=="3" (
    echo.
    echo 正在生成示例短剧...
    python pipeline/generate.py --script templates/scripts/sample_office.md --style cyberpunk --ssh-host connect.westc.seetacloud.com --ssh-port 38342 --ssh-password bBXvSvISTNNB --no-video --no-subtitle --output output/demo.mp4
    echo.
    echo 完成! 视频: output\demo.mp4
    pause
    goto menu
)
if "%choice%"=="4" (
    echo.
    set /p script="请输入剧本文件路径: "
    set /p style="请输入风格 (cinematic/cyberpunk/noir/anime): "
    if "%style%"=="" set style=cyberpunk
    python pipeline/generate.py --script "%script%" --style %style% --ssh-host connect.westc.seetacloud.com --ssh-port 38342 --ssh-password bBXvSvISTNNB --no-video --no-subtitle --output output/custom.mp4
    pause
    goto menu
)
if "%choice%"=="5" (
    start "" cmd /c "streamlit run webui/app.py --server.port 8501"
    echo Web UI 已启动: http://localhost:8501
    pause
    goto menu
)
if "%choice%"=="6" (
    start "" cmd /c "streamlit run webui/monitor.py --server.port 8502"
    echo 监控面板已启动: http://localhost:8502
    pause
    goto menu
)
if "%choice%"=="7" (
    echo.
    echo 批量处理 my_scripts/ 目录下所有剧本...
    python pipeline/batch_generate.py --scripts-dir my_scripts
    pause
    goto menu
)
if "%choice%"=="0" exit

goto menu
