"""
OpenDrama Auto-Launcher — 全链路自动启动脚本

功能:
  1. SSH 连接远程 ComfyUI 服务器
  2. 检测 ComfyUI 是否运行，没运行就启动
  3. 检查模型文件完整性（UNET/CLIP/VAE）
  4. 模型缺失就自动从已有目录复制
  5. 验证生成能力（生成一张测试图）
  6. 返回可用状态

用法:
  python launcher.py                    # 使用默认配置
  python launcher.py --host 1.2.3.4     # 自定义服务器
  python launcher.py --check-only       # 仅检测，不修复
  python launcher.py --force-restart    # 强制重启 ComfyUI
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


# =====================================================
# 默认配置 — 修改这里适配你的环境
# =====================================================
DEFAULT_CONFIG = {
    "host": "connect.westc.seetacloud.com",
    "port": 38342,
    "user": "root",
    "password": "bBXvSvISTNNB",
    "comfy_port": 8188,
    "comfy_dir": "/root/autodl-tmp/ComfyUI",
    "models": {
        "unet": {"name": "dreamshaper8_unet.safetensors", "dir": "models/unet/", "source": "models/checkpoints/dreamshaper8/unet/diffusion_pytorch_model.fp16.safetensors", "size_mb": 1700},
        "clip": {"name": "dreamshaper8_clip.safetensors", "dir": "models/clip/", "source": "models/checkpoints/dreamshaper8/text_encoder/model.fp16.safetensors", "size_mb": 235},
        "vae":  {"name": "dreamshaper8_vae.safetensors",  "dir": "models/vae/",  "source": "models/checkpoints/dreamshaper8/vae/diffusion_pytorch_model.fp16.safetensors", "size_mb": 160},
    },
    "test_prompt": "a simple test image, blue sky, white clouds, green grass, photorealistic, 8k",
    "test_negative": "ugly, deformed, blurry, text, watermark",
}

STATUS_OK = "✅"
STATUS_ERR = "❌"
STATUS_WARN = "⚠️"


class ComfyLauncher:
    """ComfyUI 自动化启动器"""
    
    def __init__(self, config=None):
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}
        self._ssh = None
        self._paramiko = None
    
    def _import_paramiko(self):
        if self._paramiko is None:
            import paramiko
            self._paramiko = paramiko
    
    def _connect(self):
        """建立 SSH 连接"""
        self._import_paramiko()
        c = self._paramiko.SSHClient()
        c.set_missing_host_key_policy(self._paramiko.AutoAddPolicy())
        c.connect(
            self.cfg["host"], port=self.cfg["port"],
            username=self.cfg["user"], password=self.cfg["password"],
            timeout=10
        )
        return c
    
    def _exec(self, cmd, timeout=30):
        """执行远程命令，返回 stdout, stderr"""
        c = self._connect()
        i, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore").strip()
        err = e.read().decode("utf-8", "ignore").strip()
        c.close()
        return out, err
    
    def _sftp_put(self, local, remote):
        """上传文件"""
        self._import_paramiko()
        t = self._paramiko.Transport((self.cfg["host"], self.cfg["port"]))
        t.connect(username=self.cfg["user"], password=self.cfg["password"])
        sftp = self._paramiko.SFTPClient.from_transport(t)
        sftp.put(local, remote)
        sftp.close()
        t.close()
    
    # =================================================
    # 检测步骤
    # =================================================
    
    def step1_check_ssh(self):
        """1. 检查 SSH 连通性"""
        print("[1/6] SSH 连接...", end=" ", flush=True)
        try:
            c = self._connect()
            _, o, _ = c.exec_command("echo OK", timeout=5)
            result = o.read().decode("utf-8", "ignore").strip()
            c.close()
            if "OK" in result:
                print(f"{STATUS_OK} 已连接")
                return True
        except Exception as e:
            print(f"{STATUS_ERR} {str(e)[:80]}")
        return False
    
    def step2_check_gpu(self):
        """2. 检查 GPU 状态"""
        print("[2/6] GPU 状态...", end=" ", flush=True)
        try:
            out, _ = self._exec("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader", timeout=10)
            if out and "GeForce" in out:
                # NVIDIA GeForce RTX 4090, 1 MiB, 24564 MiB, 0 %
                parts = [p.strip() for p in out.split(",")]
                print(f"{STATUS_OK} {parts[0]} | 显存: {parts[1]}/{parts[2]} | 利用率: {parts[3]}")
                return True
            else:
                print(f"{STATUS_ERR} 无GPU或无nvidia-smi")
        except Exception as e:
            print(f"{STATUS_ERR} {e}")
        return False
    
    def step3_check_comfyui(self):
        """3. 检查 ComfyUI 是否运行"""
        print("[3/6] ComfyUI 服务...", end=" ", flush=True)
        h = self.cfg["comfy_port"]
        
        # Check process
        out, _ = self._exec(f"ps aux | grep 'python.*main.py' | grep -v grep | wc -l", timeout=5)
        procs = int(out.strip() or "0")
        
        # Check port
        out2, _ = self._exec(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{h}/system_stats 2>/dev/null", timeout=5)
        
        if procs > 0 and out2 == "200":
            print(f"{STATUS_OK} 运行中 (PID数:{procs})")
            return "running"
        elif procs > 0:
            print(f"{STATUS_WARN} 进程存在但无响应")
            return "stuck"
        else:
            print(f"{STATUS_WARN} 未运行")
            return "stopped"
    
    def step4_check_models(self):
        """4. 检查模型文件完整性"""
        print("[4/6] 模型文件...")
        base = self.cfg["comfy_dir"]
        all_ok = True
        
        for key, m in self.cfg["models"].items():
            target = f"{base}/{m['dir']}{m['name']}"
            source = f"{base}/{m['source']}"
            
            print(f"      [{key.upper():5s}] {m['name']:35s}", end=" ", flush=True)
            
            # Check target
            out, _ = self._exec(f"ls -l '{target}' 2>/dev/null | awk '{{print $5}}'", timeout=5)
            size = int(out.strip() or "0")
            expected = m["size_mb"] * 1024 * 1024
            
            if size > expected * 0.8:
                print(f"{STATUS_OK} {size/1024/1024:.0f}MB")
                continue
            
            # Missing or corrupted — try to copy from source
            out, _ = self._exec(f"ls -l '{source}' 2>/dev/null | awk '{{print $5}}'", timeout=5)
            src_size = int(out.strip() or "0")
            
            if src_size > 0:
                self._exec(f"mkdir -p '{base}/{m['dir']}' && cp '{source}' '{target}'", timeout=30)
                out2, _ = self._exec(f"ls -l '{target}' 2>/dev/null | awk '{{print $5}}'", timeout=5)
                new_size = int(out2.strip() or "0")
                if new_size > expected * 0.8:
                    print(f"{STATUS_OK} 已复制 {new_size/1024/1024:.0f}MB")
                    continue
            
            print(f"{STATUS_ERR} 缺失! (需要 {m['size_mb']}MB)")
            all_ok = False
        
        return all_ok
    
    def step5_start_comfyui(self, force=False):
        """5. 启动 ComfyUI"""
        print("[5/6] 启动 ComfyUI...", end=" ", flush=True)
        h = self.cfg["comfy_port"]
        
        if not force:
            status = self.step3_check_comfyui()
            if status == "running":
                return True
        
        # Kill existing
        self._exec("pkill -f 'python.*main.py' 2>/dev/null; sleep 2", timeout=10)
        
        # Start
        comfy_dir = self.cfg["comfy_dir"]
        self._exec(
            f"cd {comfy_dir} && nohup python3 main.py --listen 0.0.0.0 --port {h} "
            f"> /tmp/comfyui_autolaunch.log 2>&1 &",
            timeout=10
        )
        
        # Wait for startup
        for i in range(20):
            time.sleep(3)
            out, _ = self._exec(f"curl -s http://127.0.0.1:{h}/system_stats 2>/dev/null | head -c 50", timeout=5)
            if "system" in out:
                print(f"{STATUS_OK} {i+1}次等待后启动成功")
                return True
            if i % 5 == 4:
                print(f"\n      (等待中...)", end="", flush=True)
        
        print(f"{STATUS_ERR} 20次尝试后仍未启动")
        # Print last log
        out, _ = self._exec("tail -5 /tmp/comfyui_autolaunch.log 2>/dev/null", timeout=5)
        if out:
            print(f"      最后日志: {out[:200]}")
        return False
    
    def step6_verify_generation(self):
        """6. 验证图片生成能力"""
        print("[6/6] 生成测试...", end=" ", flush=True)
        h = self.cfg["comfy_port"]
        
        wf = {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": self.cfg["test_prompt"], "clip": ["2", 0]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.cfg["test_negative"], "clip": ["2", 0]}},
            "8": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 10, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
            "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "LAUNCHER_TEST", "images": ["9", 0]}},
        }
        
        payload = json.dumps({"prompt": wf})
        escaped = payload.replace("'", "'\\''")
        
        try:
            out, err = self._exec(
                f"curl -s -X POST http://127.0.0.1:{h}/prompt "
                f"-H 'Content-Type: application/json' -d '{escaped}'",
                timeout=15
            )
            
            if "prompt_id" not in out:
                print(f"{STATUS_ERR} 提交失败: {out[:100]}")
                return False
            
            pid = json.loads(out)["prompt_id"]
            
            # Wait
            for attempt in range(30):
                time.sleep(2)
                out, _ = self._exec(f"curl -s http://127.0.0.1:{h}/history/{pid}", timeout=10)
                
                if '"status_str": "success"' in out:
                    print(f"{STATUS_OK} 第{attempt+1}次轮询成功 (正常)")
                    return True
                if "exception_message" in out:
                    idx = out.find("exception_message")
                    err_msg = out[idx:idx+200] if idx > 0 else out[:200]
                    print(f"{STATUS_ERR} 生成失败: {err_msg}")
                    return False
            
            print(f"{STATUS_WARN} 生成超时(60秒)")
            return False
            
        except Exception as e:
            print(f"{STATUS_ERR} {e}")
            return False
    
    # =================================================
    # 主流程
    # =================================================
    
    def launch(self, force_restart=False, check_only=False):
        """完整启动流程"""
        print("=" * 55)
        print("  🚀 OpenDrama Auto-Launcher v1.0")
        print(f"  目标: {self.cfg['user']}@{self.cfg['host']}:{self.cfg['port']}")
        print("=" * 55)
        
        results = {}
        t_start = time.time()
        
        # Step 1: SSH
        if not self.step1_check_ssh():
            print(f"\n{STATUS_ERR} SSH 连接失败，终止。请检查主机网络。")
            return False
        
        # Step 2: GPU
        self.step2_check_gpu()
        
        # Step 3: ComfyUI status
        status = self.step3_check_comfyui()
        
        if check_only:
            print(f"\n{STATUS_OK} 检测完成 (仅检测模式)")
            return True
        
        # Step 4: Models
        models_ok = self.step4_check_models()
        if not models_ok:
            print(f"\n{STATUS_WARN} 部分模型缺失，可手动执行: pip install -r requirements.txt")
            print(f"  或者从 HuggingFace 下载 DreamShaper 8")
        
        # Step 5: Start ComfyUI if needed
        if force_restart or status != "running":
            if not self.step5_start_comfyui(force=force_restart):
                print(f"\n{STATUS_ERR} ComfyUI 启动失败")
                return False
        else:
            print("[5/6] ComfyUI 已在运行，跳过启动")
        
        # Step 6: Verify
        if not self.step6_verify_generation():
            print(f"\n{STATUS_ERR} 图片生成验证失败，请检查日志。")
            out, _ = self._exec("tail -10 /tmp/comfyui_autolaunch.log 2>/dev/null", timeout=5)
            if out:
                print(f"  ComfyUI 最后日志: {out[:300]}")
            return False
        
        elapsed = time.time() - t_start
        
        print(f"\n{'=' * 55}")
        print(f"  {STATUS_OK} 全链路就绪! (耗时 {elapsed:.1f}秒)")
        print(f"  ComfyUI API: http://{self.cfg['host']}:{self.cfg['comfy_port']}  (需SSH隧道)")
        print(f"  现在可以运行: python pipeline/generate.py --script xxx.md")
        print(f"{'=' * 55}")
        return True


def main():
    parser = argparse.ArgumentParser(description="OpenDrama ComfyUI Auto-Launcher")
    parser.add_argument("--host", default=DEFAULT_CONFIG["host"])
    parser.add_argument("--port", type=int, default=DEFAULT_CONFIG["port"])
    parser.add_argument("--user", default=DEFAULT_CONFIG["user"])
    parser.add_argument("--password", default=DEFAULT_CONFIG["password"])
    parser.add_argument("--comfy-port", type=int, default=DEFAULT_CONFIG["comfy_port"])
    parser.add_argument("--comfy-dir", default=DEFAULT_CONFIG["comfy_dir"])
    parser.add_argument("--force-restart", action="store_true", help="强制重启 ComfyUI")
    parser.add_argument("--check-only", action="store_true", help="仅检测状态，不修复/启动")
    parser.add_argument("--config", help="JSON 配置文件路径")
    
    args = parser.parse_args()
    
    # Load config file if specified
    config = vars(args).copy()
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            file_config = json.load(f)
            config = {**config, **file_config}
    
    # Remove parser-only args
    for k in ["config"]:
        config.pop(k, None)
    
    launcher = ComfyLauncher(config)
    success = launcher.launch(
        force_restart=args.force_restart,
        check_only=args.check_only
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
