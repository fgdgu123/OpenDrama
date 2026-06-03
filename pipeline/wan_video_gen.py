"""
Wan2.1 视频生成器 — SSH 桥接远程 ComfyUI

功能:
  - 静态图 → 动态视频 (I2V)
  - 批量处理分镜帧
  - 参数控制 (运动幅度、帧数、帧率)
"""
import json, os, time
from pathlib import Path


class WanVideoGen:
    """Wan2.1 I2V 视频生成"""
    
    def __init__(self, config):
        self.ssh_host = config["ssh_host"]
        self.ssh_port = config["ssh_port"]
        self.ssh_user = config.get("ssh_user", "root")
        self.ssh_password = config["ssh_password"]
        self.comfy_port = config.get("comfy_port", 8188)
        self.output_dir = Path(config["output_dir"])
        
        # Wan2.1 参数
        self.model_name = config.get("wan_model", "wan21_i2v_14b_480p")
        self.num_frames = config.get("wan_frames", 16)
        self.fps = config.get("wan_fps", 8)
        self.steps = config.get("wan_steps", 20)
        self.cfg = config.get("wan_cfg", 7.0)
        self.motion = config.get("wan_motion", 50)  # 运动幅度 0-100
        
        self.video_dir = self.output_dir / "videos"
        self.video_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_videos(self, scenes):
        """批量图生视频"""
        total = len(scenes)
        print(f"  🎥 Wan2.1 ({self.model_name}) | {total} 个片段 | {self.num_frames}帧 @ {self.fps}fps")
        
        import paramiko
        success = 0
        
        for i, scene in enumerate(scenes):
            sid = scene["id"]
            frame_path = scene.get("frame_path")
            
            if not frame_path or not os.path.exists(frame_path):
                print(f"  [{i+1}/{total}] {sid}: 无图片，跳过")
                continue
            
            print(f"  [{i+1}/{total}] {sid}: 生成视频...", end="", flush=True)
            
            t0 = time.time()
            result = self._generate_one(sid, frame_path)
            dt = time.time() - t0
            
            if result:
                scene["video_path"] = result
                success += 1
                print(f" ✅ {dt:.1f}s")
            else:
                print(f" ❌ {dt:.1f}s")
        
        print(f"  📊 {success}/{total} 成功")
        return scenes
    
    def _generate_one(self, scene_id, image_path):
        import paramiko
        
        # 1. Upload image to remote
        remote_img = f"OpenDrama/input_{scene_id}.png"
        remote_path = f"/root/autodl-tmp/ComfyUI/input/{remote_img}"
        
        try:
            t = paramiko.Transport((self.ssh_host, self.ssh_port))
            t.connect(username=self.ssh_user, password=self.ssh_password)
            sftp = paramiko.SFTPClient.from_transport(t)
            sftp.put(image_path, remote_path)
            sftp.close()
            t.close()
        except Exception as e:
            return None
        
        # 2. Build Wan2.1 workflow
        prefix = f"OpenDrama/video_{scene_id}"
        seed = hash(scene_id) % 9999999
        
        wf = {
            "1": {"class_type": "LoadImage", "inputs": {"image": remote_img}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "smooth camera motion, cinematic, high quality", "clip": ["4", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "static, jumpy, glitch, distortion, blurry", "clip": ["4", 1]}},
            "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5-v1_1-xxl/pytorch_model-00001-of-00002.bin", "type": "wan"}},
            "5": {
                "class_type": "WanImageToVideo",
                "inputs": {
                    "image": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "clip": ["4", 0],
                    "model_name": self.model_name,
                    "seed": seed,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "num_frames": self.num_frames,
                    "fps": self.fps,
                    "motion_bucket_id": self.motion,
                }
            },
            "6": {"class_type": "SaveVideo", "inputs": {"filename_prefix": prefix, "images": ["5", 0]}},
        }
        
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
        
        # Wait (video generation takes longer)
        try:
            for _ in range(120):  # Up to 4 minutes
                time.sleep(3)
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
        
        # Download video
        try:
            hist_data = json.loads(hist)
            outputs = hist_data.get(pid, {}).get("outputs", {})
            for _, node_out in outputs.items():
                gifs = node_out.get("gifs", [])
                if gifs:
                    vid = gifs[0]
                    sub = vid.get("subfolder", "")
                    fn = vid["filename"]
                    remote = f"/root/autodl-tmp/ComfyUI/output/{sub}/{fn}".replace("//", "/")
                    
                    local = str(self.video_dir / f"{scene_id}.mp4")
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


if __name__ == "__main__":
    config = {
        "ssh_host": "connect.westc.seetacloud.com",
        "ssh_port": 38342,
        "ssh_password": "bBXvSvISTNNB",
        "output_dir": "./output",
    }
    
    gen = WanVideoGen(config)
    
    # Test with existing frame
    test_scenes = [
        {"id": "test_video", "frame_path": "output/frames/scene_001.png", "title": "Test"}
    ]
    
    gen.generate_videos(test_scenes)
