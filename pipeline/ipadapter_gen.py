"""
IP-Adapter 多角色锁脸生成器 v2.0
===============================
支持:
  - 多角色参考图映射 (男主/女主/配角各一张脸)
  - 角色→参考图自动匹配
  - 回退到无锁脸模式
"""
import json, os, time
from pathlib import Path


class MultiCharIPAdapter:
    """多角色 IP-Adapter 锁脸"""
    
    def __init__(self, config):
        self.ssh_host = config["ssh_host"]
        self.ssh_port = config["ssh_port"]
        self.ssh_user = config.get("ssh_user", "root")
        self.ssh_password = config["ssh_password"]
        self.comfy_port = config.get("comfy_port", 8188)
        self.output_dir = Path(config["output_dir"])
        self.width = config.get("width", 576)
        self.height = config.get("height", 1024)
        self.steps = config.get("steps", 25)
        self.cfg = config.get("cfg", 7.0)
        self.ip_weight = config.get("ipadapter_weight", 0.8)
        self.ip_end = config.get("ipadapter_end_at", 0.65)
        self.negative = config.get("negative_prompt",
            "ugly, deformed, blurry, bad anatomy, text, watermark, "
            "low quality, cartoon, 3d render, different face, extra limbs, "
            "distorted, disfigured, mutated hands, fused fingers")
        
        # 角色→参考图映射
        self.face_map = config.get("face_map", {})
        self.default_ref = config.get("ref_face")  # 默认参考图
        
        self.frames_dir = self.output_dir / "frames"
        self.faces_dir = self.output_dir / "faces"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.faces_dir.mkdir(parents=True, exist_ok=True)
        
        self._uploaded = {}  # 已经上传的参考图 → 远程路径缓存
    
    def generate_with_face(self, scenes):
        """批量生成，每个场景匹配对应角色"""
        total = len(scenes)
        using_ip = bool(self.face_map or self.default_ref)
        
        if using_ip:
            print(f"  👤 IP-Adapter 多角色锁脸 | 权重: {self.ip_weight} | 角色映射: {len(self.face_map)} 个")
        else:
            print(f"  🎨 无锁脸模式 (quality first)")
        
        print(f"  📸 生成 {total} 分镜...")
        
        import paramiko
        success = 0
        
        for i, scene in enumerate(scenes):
            sid = scene["id"]
            char = scene.get("character", "")
            title = scene.get("title", "")[:30]
            
            # 匹配角色参考图
            ref_face = self._match_face(char)
            prompt = self._build_prompt(scene)
            
            print(f"  [{i+1}/{total}] {sid}: {title}", end="", flush=True)
            
            t0 = time.time()
            result = self._generate_one(sid, prompt, ref_face)
            dt = time.time() - t0
            
            if result:
                scene["frame_path"] = result
                success += 1
                print(f" ✅ {dt:.1f}s {'👤' if ref_face else ''}")
            else:
                print(f" ❌ {dt:.1f}s")
        
        print(f"  📊 {success}/{total} 成功")
        return scenes
    
    def _match_face(self, character):
        """根据角色名匹配参考图"""
        if not character or character == "narrator":
            return None  # 旁白不需要锁脸
        
        char_lower = character.lower()
        
        # 精确匹配
        for key, path in self.face_map.items():
            if key in char_lower or char_lower in key:
                full = str(self.faces_dir / path) if not os.path.isabs(path) else path
                if os.path.exists(full):
                    return full
        
        # 回退到默认参考图
        if self.default_ref and os.path.exists(self.default_ref):
            return self.default_ref
        
        return None
    
    def _build_prompt(self, scene):
        """构建分镜提示词，包含角色描述"""
        parts = []
        
        char = scene.get("character", "")
        if char:
            parts.append(f"portrait of {char}")
        
        if scene.get("prompt"):
            parts.append(scene["prompt"])
        elif scene.get("narration"):
            # 提取narration关键词
            narration = scene["narration"][:200]
            parts.append(f"scene: {narration}")
        
        parts.append("cinematic lighting, photorealistic, highly detailed, 8k, masterpiece")
        return ", ".join(parts)
    
    def _upload_ref(self, local_path):
        """上传参考脸图到远程 ComfyUI"""
        if local_path in self._uploaded:
            return self._uploaded[local_path]
        
        import paramiko
        
        # 生成唯一远程文件名
        name = os.path.basename(local_path)
        base, ext = os.path.splitext(name)
        remote_name = f"opendrama_ref_{base}{ext}"
        remote_dir = "/root/autodl-tmp/ComfyUI/input"
        remote_path = f"{remote_dir}/{remote_name}"
        
        try:
            # Ensure remote dir
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.ssh_host, port=self.ssh_port, username=self.ssh_user,
                       password=self.ssh_password, timeout=10)
            c.exec_command(f"mkdir -p {remote_dir}")
            c.close()
            
            # Upload
            t = paramiko.Transport((self.ssh_host, self.ssh_port))
            t.connect(username=self.ssh_user, password=self.ssh_password)
            sftp = paramiko.SFTPClient.from_transport(t)
            sftp.put(local_path, remote_path)
            sftp.close()
            t.close()
            
            self._uploaded[local_path] = remote_name
            return remote_name
        except Exception as e:
            print(f"\n      ⚠️ 上传参考图失败: {e}")
            return None
    
    def _generate_one(self, scene_id, prompt, ref_face=None):
        """生成一张分镜图"""
        import paramiko
        
        seed = hash(f"{scene_id}_{prompt}") % 9999999
        prefix = f"OpenDrama/ipa_{scene_id}"
        
        wf = self._build_workflow(prompt, seed, prefix, ref_face)
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
            
            if "prompt_id" not in out:
                c.close()
                return None
            
            pid = json.loads(out)["prompt_id"]
        except Exception as e:
            return None
        
        # Wait for completion
        try:
            for attempt in range(90):
                time.sleep(2)
                i2, o2, _ = c.exec_command(
                    f"curl -s http://127.0.0.1:{self.comfy_port}/history/{pid}", timeout=10)
                hist = o2.read().decode("utf-8", "ignore").strip()
                
                if '"status_str": "success"' in hist:
                    break
                if "exception_message" in hist:
                    # Print error for debugging
                    err_start = hist.find("exception_message")
                    err = hist[err_start:err_start+200] if err_start > 0 else "unknown"
                    print(f"\n      ⚠️ ComfyUI error: {err}")
                    c.close()
                    return None
            else:
                print(f"\n      ⚠️ Timeout after 180s")
                c.close()
                return None
        except Exception:
            c.close()
            return None
        
        # Download result
        try:
            hist_data = json.loads(hist)
            outputs = hist_data.get(pid, {}).get("outputs", {})
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
        except Exception as e:
            pass
        
        c.close()
        return None
    
    def _build_workflow(self, prompt, seed, prefix, ref_face=None):
        """构建 ComfyUI workflow"""
        if ref_face:
            remote_ref = self._upload_ref(ref_face)
            if not remote_ref:
                # 上传失败，退回到无锁脸
                ref_face = None
        
        if ref_face and remote_ref:
            return {
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
                "11": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["1", 0], "preset": "PLUS (high strength)"}},
                "12": {"class_type": "LoadImage", "inputs": {"image": remote_ref}},
                "13": {"class_type": "IPAdapter", "inputs": {
                    "model": ["11", 0], "ipadapter": ["11", 1], "image": ["12", 0],
                    "weight": self.ip_weight, "start_at": 0.0, "end_at": self.ip_end,
                    "weight_type": "standard",
                }},
                "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.negative, "clip": ["2", 0]}},
                "8": {"class_type": "KSampler", "inputs": {
                    "seed": seed, "steps": self.steps, "cfg": self.cfg,
                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                    "model": ["13", 0], "positive": ["6", 0], "negative": ["7", 0],
                    "latent_image": ["5", 0]
                }},
                "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
                "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["9", 0]}},
            }
        else:
            return {
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
                "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.negative, "clip": ["2", 0]}},
                "8": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": self.steps, "cfg": self.cfg,
                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                    "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0],
                    "latent_image": ["5", 0]}},
                "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
                "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["9", 0]}},
            }
