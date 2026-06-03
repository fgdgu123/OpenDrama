@echo off
chcp 65001 >nul
title OpenDrama Studio

echo.
echo ╔══════════════════════════════════════════╗
echo ║     🎬 OpenDrama Studio v1.0             ║
echo ║     AI短剧全链路工厂                      ║
echo ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Step 1: Auto-launch ComfyUI
echo ── 启动 ComfyUI 远程服务 ──
python launcher.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ ComfyUI 启动失败，请检查网络和服务器状态
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════╗
echo ║  🎬 开始制作短剧                          ║
echo ╚══════════════════════════════════════════╝
echo.

:: Step 2: Run pipeline with default settings
python pipeline/generate.py ^
    --script templates/scripts/sample_office.md ^
    --style cyberpunk ^
    --ssh-host connect.westc.seetacloud.com ^
    --ssh-port 38342 ^
    --ssh-password bBXvSvISTNNB ^
    --width 576 ^
    --height 1024 ^
    --steps 20 ^
    --no-subtitle ^
    --output output/drama_output.mp4

echo.
echo ╔══════════════════════════════════════════╗
echo ║  ✅ 完成! 视频保存在 output/              ║
echo ╚══════════════════════════════════════════╝
echo.
pause
