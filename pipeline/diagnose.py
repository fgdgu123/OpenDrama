"""
OpenDrama 诊断修复工具 — 一键检测并自动修复常见问题
"""
import sys, os, subprocess, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def diagnose_all():
    """全系统诊断报告"""
    issues = []
    fixes = []
    
    # 1. ComfyUI 进程
    import paramiko
    SSH = {"host":"connect.westc.seetacloud.com","port":38342,"user":"root","password":"bBXvSvISTNNB"}
    
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(SSH["host"], port=SSH["port"], username=SSH["user"], password=SSH["password"], timeout=8)
        
        # Check ComfyUI
        i, o, _ = c.exec_command("ps aux | grep 'python.*main.py' | grep -v grep | wc -l")
        procs = int(o.read().decode().strip() or "0")
        
        if procs == 0:
            issues.append("ComfyUI 未运行")
            fixes.append("运行: python launcher.py")
        else:
            # Check GPU
            i, o, _ = c.exec_command("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")
            gpu = o.read().decode().strip()
            if gpu:
                used, total = [int(x.split()[0]) for x in gpu.split(",")]
                if used > total * 0.9:
                    issues.append(f"GPU 显存不足 ({used/1024:.0f}/{total/1024:.0f}GB)")
                    fixes.append("运行: python launcher.py --force-restart")
            
            # Check model files
            models = {
                "UNET": "/root/autodl-tmp/ComfyUI/models/unet/dreamshaper8_unet.safetensors",
                "CLIP": "/root/autodl-tmp/ComfyUI/models/clip/dreamshaper8_clip.safetensors",
                "VAE": "/root/autodl-tmp/ComfyUI/models/vae/dreamshaper8_vae.safetensors",
            }
            for name, path in models.items():
                i, o, _ = c.exec_command(f"ls -l '{path}' 2>/dev/null | awk '{{print $5}}'")
                size = o.read().decode().strip()
                if not size or int(size) < 10000:
                    issues.append(f"模型文件缺失: {name}")
                    fixes.append("运行: python launcher.py (自动修复)")
        
        # Check Wan2.1 model
        i, o, _ = c.exec_command("ls /root/autodl-tmp/ComfyUI/models/diffusion_models/wan21_i2v_14b_480p/ 2>/dev/null | wc -l")
        wan_count = int(o.read().decode().strip() or "0")
        if wan_count == 0:
            issues.append("Wan2.1 视频模型缺失 (视频生成不可用)")
        
        c.close()
    except Exception as e:
        issues.append(f"SSH 连接失败: {str(e)[:80]}")
        fixes.append("检查服务器网络和端口")
    
    # 2. Local
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
    except:
        issues.append("FFmpeg 未安装")
        fixes.append("下载: https://ffmpeg.org/download.html")
    
    for pkg in ["requests", "paramiko", "edge_tts"]:
        try:
            __import__(pkg)
        except ImportError:
            issues.append(f"Python 包缺失: {pkg}")
            fixes.append(f"pip install {pkg}")
    
    # 3. GitHub
    try:
        r = subprocess.run(["git", "rev-list", "--count", "origin/master..HEAD"], 
                          capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        ahead = int(r.stdout.strip() or "0")
        if ahead > 0:
            issues.append(f"GitHub 有 {ahead} 个 commit 未推送")
            fixes.append("git push origin master")
    except:
        pass
    
    return issues, fixes


def print_report(issues, fixes):
    """打印诊断报告"""
    if not issues:
        print("✅ 一切正常，无需修复")
        return
    
    print(f"\n诊断发现 {len(issues)} 个问题：\n")
    for i, (iss, fix) in enumerate(zip(issues, fixes)):
        print(f"  [{i+1}] {iss}")
        print(f"      → {fix}\n")
    
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"💡 运行 python launcher.py 可自动修复大部分问题")


if __name__ == "__main__":
    print("🔍 OpenDrama 系统诊断")
    print("=" * 45)
    issues, fixes = diagnose_all()
    print_report(issues, fixes)
