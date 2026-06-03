"""
OpenDrama 全链路连通性检测脚本
检测：SSH、GPU、ComfyUI、模型、生成能力、TTS、FFmpeg、GitHub
"""
import sys, os, json, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test(label, fn):
    """运行测试并打印结果"""
    print(f"  [{label:30s}]", end=" ", flush=True)
    try:
        ok, msg = fn()
        icon = "✅" if ok else "❌"
        print(f"{icon} {msg}")
        return ok
    except Exception as e:
        print(f"❌ {str(e)[:80]}")
        return False


def main():
    print("=" * 60)
    print("  🔍 OpenDrama 全链路连通性检测")
    print("  " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    results = {}
    
    # ── 1. 本地环境 ──
    print("\n── 本地环境 ──")
    
    def check_python():
        v = sys.version_info
        return True, f"Python {v.major}.{v.minor}.{v.micro}"
    results["python"] = test("Python", check_python)
    
    def check_ffmpeg():
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            line = r.stdout.split("\n")[0]
            return True, line[:60]
        except FileNotFoundError:
            return False, "未安装 — https://ffmpeg.org"
        except subprocess.TimeoutExpired:
            return False, "超时"
    results["ffmpeg"] = test("FFmpeg", check_ffmpeg)
    
    def check_pip_pkgs():
        pkgs = {"requests": "HTTP", "paramiko": "SSH", "edge_tts": "TTS"}
        missing = []
        for pkg, name in pkgs.items():
            try:
                __import__(pkg)
            except ImportError:
                missing.append(name)
        if missing:
            return False, f"缺少: {', '.join(missing)}"
        return True, "requests + paramiko + edge-tts"
    results["pip"] = test("Python依赖", check_pip_pkgs)
    
    def check_git():
        try:
            r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            return True, r.stdout.strip()
        except FileNotFoundError:
            return False, "未安装"
    results["git"] = test("Git", check_git)
    
    # ── 2. SSH 连接 ──
    print("\n── 远程服务器 ──")
    
    import paramiko
    ssh_configs = [
        ("矩池云 4090", "connect.westc.seetacloud.com", 38342, "root", "bBXvSvISTNNB"),
        ("阿里云", "47.102.115.11", 22, "root", "aabb8899@"),
    ]
    
    for name, host, port, user, pwd in ssh_configs:
        def make_ssh_check(h, p, u, pw):
            def check():
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(h, port=p, username=u, password=pw, timeout=8)
                i, o, _ = c.exec_command("echo OK && uname -r", timeout=5)
                out = o.read().decode("utf-8", "ignore").strip()
                c.close()
                kernel = out.split("\n")[-1].strip() if "\n" in out else out
                return True, f"kernel {kernel}" if "OK" in out else out
            return check
        
        ok = test(f"SSH → {name}", make_ssh_check(host, port, user, pwd))
        if ok and "4090" in name:
            # Check GPU
            def gpu_check():
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(host, port=port, username=user, password=pwd, timeout=8)
                i, o, _ = c.exec_command("nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader", timeout=5)
                out = o.read().decode("utf-8","ignore").strip()
                c.close()
                if out:
                    parts = [p.strip() for p in out.split(",")]
                    return True, f"{parts[0]} 显存{parts[1]}/{parts[2]}"
                return False, "nvidia-smi 异常"
            test("GPU", gpu_check)
            
            # Check ComfyUI
            def comfy_check():
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(host, port=port, username=user, password=pwd, timeout=8)
                i, o, _ = c.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8188/system_stats 2>/dev/null", timeout=8)
                code = o.read().decode("utf-8","ignore").strip()
                c.close()
                if code == "200":
                    return True, "运行中 :8188"
                return False, f"状态码={code or '超时'}"
            test("ComfyUI", comfy_check)
            
            # Check models
            def models_check():
                c = paramiko.SSHClient()
                c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                c.connect(host, port=port, username=user, password=pwd, timeout=8)
                models = {
                    "UNET": "ls -lh /root/autodl-tmp/ComfyUI/models/unet/dreamshaper8_unet.safetensors 2>/dev/null | awk '{print $5}'",
                    "CLIP": "ls -lh /root/autodl-tmp/ComfyUI/models/clip/dreamshaper8_clip.safetensors 2>/dev/null | awk '{print $5}'",
                    "VAE": "ls -lh /root/autodl-tmp/ComfyUI/models/vae/dreamshaper8_vae.safetensors 2>/dev/null | awk '{print $5}'",
                    "IP-Adapter": "ls -lh /root/autodl-tmp/ComfyUI/models/ipadapter/ip-adapter-plus_sd15.safetensors 2>/dev/null | awk '{print $5}'",
                }
                details = []
                ok_all = True
                for name, cmd in models.items():
                    i2, o2, _ = c.exec_command(cmd, timeout=5)
                    size = o2.read().decode("utf-8","ignore").strip()
                    if size:
                        details.append(f"{name}:{size}")
                    else:
                        details.append(f"{name}:缺失")
                        ok_all = False
                c.close()
                return ok_all, " | ".join(details)
            test("模型文件", models_check)
    
    # ── 3. ComfyUI 生成验证 ──
    print("\n── 生成验证 ──")
    
    def test_generation():
        import paramiko, json
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect("connect.westc.seetacloud.com", port=38342, username="root", password="bBXvSvISTNNB", timeout=8)
        
        wf = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a red apple on white table, photorealistic, 8k", "clip": ["2", 0]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly, deformed, blurry, text, watermark", "clip": ["2", 0]}},
            "8": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 8, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
            "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "CHECK_TEST", "images": ["9", 0]}},
        }
        
        payload = json.dumps({"prompt": wf})
        escaped = payload.replace("'", "'\\''")
        
        i, o, _ = c.exec_command(f"curl -s -X POST http://127.0.0.1:8188/prompt -H 'Content-Type: application/json' -d '{escaped}'", timeout=15)
        out = o.read().decode("utf-8","ignore").strip()
        
        if "prompt_id" not in out:
            c.close()
            return False, f"提交失败: {out[:100]}"
        
        pid = json.loads(out)["prompt_id"]
        t0 = time.time()
        
        for _ in range(20):
            time.sleep(1)
            i2, o2, _ = c.exec_command(f"curl -s http://127.0.0.1:8188/history/{pid}", timeout=8)
            hist = o2.read().decode("utf-8","ignore").strip()
            if '"status_str": "success"' in hist:
                elapsed = time.time() - t0
                c.close()
                return True, f"成功 {elapsed:.1f}s"
            if "exception_message" in hist:
                idx = hist.find("exception_message")
                err = hist[idx+20:idx+120] if idx>0 else hist[:100]
                c.close()
                return False, err
        
        c.close()
        return False, "生成超时"
    
    results["generation"] = test("图片生成", test_generation)
    
    # ── 4. TTS ──
    print("\n── 配音检测 ──")
    
    def test_tts():
        import tempfile
        tmp = tempfile.mktemp(suffix=".mp3")
        r = subprocess.run([
            sys.executable, "-m", "edge_tts",
            "-f", "-",
            "--voice", "zh-CN-YunxiNeural",
            "--write-media", tmp,
        ], input="测试", capture_output=True, text=True, timeout=15, encoding="utf-8")
        ok = os.path.exists(tmp) and os.path.getsize(tmp) > 100
        if os.path.exists(tmp):
            os.unlink(tmp)
        if ok:
            return True, "edge-tts 就绪"
        return False, r.stderr[:60] if r.stderr else "失败"
    results["tts"] = test("Edge-TTS", test_tts)
    
    # ── 5. GitHub ──
    print("\n── 代码仓库 ──")
    
    def test_github():
        import requests
        try:
            r = requests.get("https://api.github.com/repos/fgdgu123/OpenDrama", timeout=8)
            if r.status_code == 200:
                data = r.json()
                return True, f"github.com/fgdgu123/OpenDrama ({data.get('pushed_at','')[:10]})"
            return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)[:60]
    results["github"] = test("GitHub仓库", test_github)
    
    def test_git_push():
        try:
            r = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, cwd=Path(__file__).parent)
            commit = r.stdout.strip()
            r2 = subprocess.run(["git", "branch", "-r"], capture_output=True, text=True, cwd=Path(__file__).parent)
            has_remote = "origin/master" in r2.stdout
            if has_remote:
                r3 = subprocess.run(["git", "rev-list", "--count", "origin/master..HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent)
                ahead = int(r3.stdout.strip() or "0")
                if ahead > 0:
                    return True, "Git: " + commit + " +" + str(ahead) + " pending"
                return True, "Git: " + commit + " (synced)"
            return False, "no remote"
        except Exception as e:
            return False, str(e)[:60]
    test("本地Git状态", test_git_push)

    def test_webui():
        import requests
        try:
            r = requests.get("http://localhost:8501", timeout=3)
            return r.status_code == 200, "localhost:8501"
        except:
            return False, "not running"
    test("Web UI", test_webui)
    
    # ── 6. 汇总 ──
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    if passed == total:
        print(f"  🎉 全链路就绪! ({passed}/{total})")
        print(f"  现在可以运行: python pipeline/generate.py --script xxx.md ...")
    else:
        print(f"  ⚠️ {passed}/{total} 通过, 请检查上面 ❌ 标记项")
    
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
