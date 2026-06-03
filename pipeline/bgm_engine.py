"""
BGM 引擎 — 生成/下载背景音乐

支持:
  - 内置无声 BGM (纯静音轨，静默场景)
  - 外部 BGM 文件混音
  - (未来) AI 音乐生成
"""
import os, subprocess
from pathlib import Path


def generate_silent_bgm(output_path, duration=60, sample_rate=44100):
    """生成静音 BGM 轨（占位，防止 FFmpeg 混音报错）"""
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r={sample_rate}:cl=stereo",
            "-t", str(duration),
            "-c:a", "aac", "-b:a", "32k",
            str(output_path)
        ], capture_output=True, timeout=30)
        return output_path.exists() and output_path.stat().st_size > 100
    except Exception:
        return False


def get_default_bgm_path(output_dir="output"):
    """获取或创建默认 BGM"""
    d = Path(output_dir)
    d.mkdir(parents=True, exist_ok=True)
    bgm = d / "default_bgm.aac"
    if not bgm.exists():
        generate_silent_bgm(str(bgm), duration=180)
    return str(bgm) if bgm.exists() else None


if __name__ == "__main__":
    p = get_default_bgm_path()
    if p:
        print(f"BGM ready: {p} ({os.path.getsize(p)} bytes)")
    else:
        print("BGM generation failed")
