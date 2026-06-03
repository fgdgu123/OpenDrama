"""
分镜生成器 — ComfyUI SSH桥接 / HTTP 双模式
Remote ComfyUI via paramiko SSH + curl + SFTP
"""
import json, os, time
from pathlib import Path


class SceneGenerator:
    
    def __init__(self, config, style_data=None):
        self.output_dir = Path(config["output_dir"])
        self.width = config.get("width", 576)
        self.height = config.get("height", 1024)
        self.steps = config.get("steps", 25)
        self.cfg = config.get("cfg", 7.0)
        self.sampler = config.get("sampler", "dpmpp_2m")
        self.scheduler = config.get("scheduler", "karras")
        self.negative_prompt = config.get("negative_prompt", "ugly, deformed, blurry, bad anatomy, text, watermark")
        self.style_data = style_data or {}
        self.characters = config.get("characters", {})
        self.ssh_host = config.get("ssh_host")
        self.ssh_port = config.get("ssh_port", 22)
        self.ssh_user = config.get("ssh_user", "root")
        self.ssh_password = config.get("ssh_password")
        self.comfy_port = config.get("comfy_port", 8188)
        self.frames_dir = self.output_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        os.makedirs(self.output_dir / "audio", exist_ok=True)

    def generate(self, scenes):
        total = len(scenes)
        mode = "SSH桥接" if self.ssh_host else "HTTP"
        print(f"  📸 生成 {total} 分镜 (模式: {mode})")
        
        success = 0
        for i, scene in enumerate(scenes):
            sid = scene["id"]
            prompt = self._make_prompt(scene)
            print(f"  [{i+1}/{total}] {sid}: {scene.get('title','')[:30]}", end="", flush=True)
            
            t0 = time.time()
            result = self._gen_one(sid, prompt)
            dt = time.time() - t0
            
            if result:
                scene["frame_path"] = result
                success += 1
                print(f" ✅ {dt:.1f}s")
            else:
                print(f" ❌")
        
        print(f"  📊 {success}/{total} 成功")
        return scenes

    def _make_prompt(self, scene):
        parts = []
        if self.style_data.get("prefix"):
            parts.append(self.style_data["prefix"])
        if scene.get("prompt"):
            parts.append(scene["prompt"])
        elif scene.get("narration"):
            parts.append(f"scene description: {scene['narration'][:300]}")
        parts.append("masterpiece, best quality, cinematic, photorealistic, 8k")
        return ", ".join(parts)

    def _gen_one(self, scene_id, prompt, retries=3):
        for attempt in range(retries):
            try:
                result = self._ssh_generate(scene_id, prompt) if self.ssh_host else self._http_generate(scene_id, prompt)
                if result:
                    return result
                if attempt < retries - 1:
                    time.sleep(3)
            except Exception:
                if attempt < retries - 1:
                    time.sleep(3)
        return None

    def _ssh_generate(self, scene_id, prompt):
        import paramiko
        seed = hash(scene_id) % 9999999
        prefix = f"OpenDrama/{scene_id}"
        
        wf = self._workflow(prompt, seed, prefix)
        payload = json.dumps({"prompt": wf})
        escaped = payload.replace("'", "'\\''")
        cmd = f"curl -s -X POST http://127.0.0.1:{self.comfy_port}/prompt -H 'Content-Type: application/json' -d '{escaped}'"
        
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.ssh_host, port=self.ssh_port, username=self.ssh_user,
                      password=self.ssh_password, timeout=10)
            
            i, o, e = c.exec_command(cmd, timeout=30)
            out = o.read().decode("utf-8", "ignore").strip()
            err_out = e.read().decode("utf-8", "ignore").strip()
            
            if "prompt_id" not in out:
                print(f"\n    [SSH ERR: {err_out[:200]}]", end="")
                return None
            
            prompt_id = json.loads(out)["prompt_id"]
        except Exception as ex:
            print(f"\n    [SSH EX: {ex}]", end="")
            return None
        
        # Wait for completion
        hist = ""
        try:
            for _ in range(60):
                time.sleep(2)
                i2, o2, _ = c.exec_command(
                    f"curl -s http://127.0.0.1:{self.comfy_port}/history/{prompt_id}",
                    timeout=10
                )
                hist = o2.read().decode("utf-8", "ignore").strip()
                
                if '"status_str": "success"' in hist:
                    break
                if "exception_message" in hist:
                    c.close()
                    return None
            else:
                c.close()
                return None
        except Exception:
            c.close()
            return None
        
        # Parse history & download
        try:
            hist_data = json.loads(hist)
            outputs = hist_data.get(prompt_id, {}).get("outputs", {})
            for _, node_out in outputs.items():
                images = node_out.get("images", [])
                if images:
                    img = images[0]
                    sub = img.get("subfolder", "")
                    fn = img["filename"]
                    remote = f"/root/autodl-tmp/ComfyUI/output/{sub}/{fn}".replace("//", "/")
                    
                    local = str(self.frames_dir / f"{scene_id}.png")
                    t = paramiko.Transport((self.ssh_host, self.ssh_port))
                    t.connect(username=self.ssh_user, password=self.ssh_password)
                    sftp = paramiko.SFTPClient.from_transport(t)
                    sftp.get(remote, local)
                    sftp.close()
                    t.close()
                    c.close()
                    return local
        except Exception as ex:
            print(f"\n    [DL ERR: {ex}]", end="")
        
        c.close()
        return None

    def _http_generate(self, scene_id, prompt):
        import requests
        seed = hash(scene_id) % 9999999
        prefix = f"OpenDrama/{scene_id}"
        wf = self._workflow(prompt, seed, prefix)
        
        try:
            r = requests.post(f"{self.api_url}/prompt", json={"prompt": wf}, timeout=30)
            if r.status_code != 200:
                return None
            pid = r.json()["prompt_id"]
        except Exception:
            return None
        
        for _ in range(60):
            time.sleep(2)
            r2 = requests.get(f"{self.api_url}/history/{pid}", timeout=10)
            if r2.status_code != 200:
                continue
            data = r2.json()
            if pid not in data:
                continue
            for _, node_out in data[pid].get("outputs", {}).items():
                for img in node_out.get("images", []):
                    local = str(self.frames_dir / f"{scene_id}.png")
                    r3 = requests.get(f"{self.api_url}/view",
                        params={"filename": img["filename"], "subfolder": img.get("subfolder",""), "type": "output"},
                        timeout=30)
                    if r3.status_code == 200:
                        with open(local, "wb") as f:
                            f.write(r3.content)
                        return local
        return None

    def _workflow(self, prompt, seed, prefix):
        return {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.negative_prompt, "clip": ["2", 0]}},
            "8": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": self.steps, "cfg": self.cfg, "sampler_name": self.sampler, "scheduler": self.scheduler, "denoise": 1.0, "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
            "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
            "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["9", 0]}},
        }
