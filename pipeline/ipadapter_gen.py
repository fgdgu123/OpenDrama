"""
IP-Adapter 锁脸生成器 — 基于 SSH 桥接 ComfyUI
支持角色参考图 + 固定人脸 + 批量场景

技术栈: DreamShaper 8 UNET/CLIP/VAE + IP-Adapter PLUS + CLIP-ViT-H
"""
import json, os, time, base64
from pathlib import Path


class IPAdapterFaceLock:
    """IP-Adapter 人脸锁定 + 批量生图"""
    
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
        self.ip_noise = config.get("ipadapter_noise", 0.2)
        self.negative = config.get("negative_prompt", 
            "ugly, deformed, blurry, bad anatomy, text, watermark, low quality, cartoon, 3d render, different face")
        
        # 参考图配置
        self.ref_face_local = config.get("ref_face")  # 本地参考图路径
        self.ref_face_remote = None  # 上传后的远程路径
        
        self.frames_dir = self.output_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
    
    def upload_reference_face(self):
        """上传参考脸图到远程 ComfyUI"""
        if not self.ref_face_local or not os.path.exists(self.ref_face_local):
            print("  ⚠️ 无参考脸图")
            return False
        
        import paramiko
        
        remote_dir = "/root/autodl-tmp/ComfyUI/input"
        remote_path = f"{remote_dir}/opendrama_ref_face.png"
        
        try:
            t = paramiko.Transport((self.ssh_host, self.ssh_port))
            t.connect(username=self.ssh_user, password=self.ssh_password)
            sftp = paramiko.SFTPClient.from_transport(t)
            
            # 确保远程目录存在
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(self.ssh_host, port=self.ssh_port, username=self.ssh_user, 
                       password=self.ssh_password, timeout=10)
            c.exec_command(f"mkdir -p {remote_dir}")
            c.close()
            
            sftp.put(self.ref_face_local, remote_path)
            sftp.close()
            t.close()
            
            self.ref_face_remote = "opendrama_ref_face.png"
            print(f"  ✅ 参考脸已上传: {self.ref_face_remote}")
            return True
        except Exception as e:
            print(f"  ❌ 上传失败: {e}")
            return False
    
    def generate_with_face(self, scenes, face_image_path=None):
        """带 IP-Adapter 锁脸生成所有分镜"""
        if face_image_path:
            self.ref_face_local = face_image_path
        
        if self.ref_face_local:
            if not self.upload_reference_face():
                print("  ⚠️ 退回到无锁脸模式")
                self.ref_face_remote = None
        
        total = len(scenes)
        print(f"  👤 IP-Adapter 锁脸模式 | 权重: {self.ip_weight} | 参考图: {'✅' if self.ref_face_remote else '❌'}")
        print(f"  📸 生成 {total} 分镜...")
        
        import paramiko
        success = 0
        
        for i, scene in enumerate(scenes):
            sid = scene["id"]
            prompt = self._build_prompt(scene)
            
            print(f"  [{i+1}/{total}] {sid}: {scene.get('title','')[:30]}", end="", flush=True)
            
            t0 = time.time()
            result = self._generate_one_ip(sid, prompt)
            dt = time.time() - t0
            
            if result:
                scene["frame_path"] = result
                success += 1
                print(f" ✅ {dt:.1f}s")
            else:
                print(f" ❌")
        
        print(f"  📊 {success}/{total} 成功")
        return scenes
    
    def _build_prompt(self, scene):
        parts = []
        # 角色描述优先
        char = scene.get("character", "")
        if char:
            parts.append(f"portrait of {char}")
        if scene.get("prompt"):
            parts.append(scene["prompt"])
        elif scene.get("narration"):
            parts.append(f"scene: {scene['narration'][:300]}")
        parts.append("cinematic lighting, photorealistic, highly detailed, 8k, masterpiece")
        return ", ".join(parts)
    
    def _generate_one_ip(self, scene_id, prompt):
        """通过 SSH 提交 IP-Adapter 工作流"""
        import paramiko
        
        seed = hash(scene_id) % 9999999
        prefix = f"OpenDrama/ipa_{scene_id}"
        
        wf = self._build_ipadapter_workflow(prompt, seed, prefix)
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
        except Exception:
            return None
        
        # Wait
        try:
            for _ in range(60):
                time.sleep(2)
                i2, o2, _ = c.exec_command(
                    f"curl -s http://127.0.0.1:{self.comfy_port}/history/{pid}", timeout=10)
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
        
        # Download
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
        except Exception:
            pass
        
        c.close()
        return None
    
    def _build_ipadapter_workflow(self, prompt, seed, prefix):
        """构建 IP-Adapter PLUS 工作流"""
        if self.ref_face_remote:
            return {
                # DreamShaper 8 components
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
                
                # IPAdapterUnifiedLoader (combined model+clip+ipadapter)
                "11": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["1", 0], "preset": "PLUS (high strength)"}},
                
                # Reference image
                "12": {"class_type": "LoadImage", "inputs": {"image": self.ref_face_remote}},
                
                # IPAdapter node
                "13": {"class_type": "IPAdapter", "inputs": {
                    "model": ["11", 0],
                    "ipadapter": ["11", 1],
                    "image": ["12", 0],
                    "weight": self.ip_weight,
                    "start_at": 0.0,
                    "end_at": self.ip_end,
                    "weight_type": "standard",
                }},
                
                # Prompts
                "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.negative, "clip": ["2", 0]}},
                
                # KSampler (model from IPAdapter)
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
            # Fallback: no IP-Adapter
            return {
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "dreamshaper8_unet.safetensors", "weight_dtype": "default"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "dreamshaper8_clip.safetensors", "type": "stable_diffusion"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "dreamshaper8_vae.safetensors"}},
                "5": {"class_type": "EmptyLatentImage", "inputs": {"width": self.width, "height": self.height, "batch_size": 1}},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "7": {"class_type": "CLIPTextEncode", "inputs": {"text": self.negative, "clip": ["2", 0]}},
                "8": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": self.steps, "cfg": self.cfg, "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0, "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
                "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
                "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["9", 0]}},
            }


def create_reference_face(prompt="a professional portrait photo of a young Chinese person, front facing, neutral expression, clean background, studio lighting, sharp focus, 8k", output_path="reference_face.png", config=None):
    """生成参考脸图（用于后续 IP-Adapter 锁脸）"""
    if config is None:
        config = {
            "ssh_host": "connect.westc.seetacloud.com",
            "ssh_port": 38342,
            "ssh_user": "root",
            "ssh_password": "bBXvSvISTNNB",
            "output_dir": "./output",
            "width": 512,
            "height": 512,
            "steps": 20,
        }
    
    lock = IPAdapterFaceLock(config)
    
    # 无 IP-Adapter，直接生成参考图
    lock.ref_face_remote = None
    scene = {"id": "ref_face_gen", "title": "Reference Face", "prompt": prompt, "character": ""}
    
    results = lock.generate_with_face([scene])
    
    if results and results[0].get("frame_path"):
        src = results[0]["frame_path"]
        dest = os.path.join(os.path.dirname(src), output_path)
        import shutil
        shutil.copy(src, dest)
        print(f"✅ 参考脸已生成: {dest}")
        return dest
    else:
        print("❌ 参考脸生成失败")
        return None


if __name__ == "__main__":
    config = {
        "ssh_host": "connect.westc.seetacloud.com",
        "ssh_port": 38342,
        "ssh_password": "bBXvSvISTNNB",
        "output_dir": "./output",
        "width": 576,
        "height": 1024,
        "steps": 20,
        "ipadapter_weight": 0.8,
        "ref_face": "reference_face.png",  # 如果有的话
    }
    
    lock = IPAdapterFaceLock(config)
    
    scenes = [
        {"id": "ipa_test_01", "title": "Hero Face", "prompt": "young Chinese programmer, short black hair, sharp eyes, dark hoodie, cyberpunk, cinematic", "character": "Chinese male programmer, 28, short hair"},
        {"id": "ipa_test_02", "title": "Hero Profile", "prompt": "side profile of young Chinese programmer, neon lit, dramatic shadows, cyberpunk", "character": "Chinese male programmer, 28, short hair"},
        {"id": "ipa_test_03", "title": "Hero Action", "prompt": "young Chinese programmer typing on keyboard, blue screen glow, intense focus, cyberpunk", "character": "Chinese male programmer, 28, short hair"},
    ]
    
    lock.generate_with_face(scenes)
