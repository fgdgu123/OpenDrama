"""
ComfyUI SSH Bridge — 通过 SSH 隧道调用远程 ComfyUI API
免公网端口暴露，直接命令执行
"""
import paramiko
import json
import time
import base64
import os
from pathlib import Path


class ComfyUIBridge:
    """通过 SSH 连接远程 ComfyUI，用 curl 命令提交工作流"""
    
    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.comfy_port = 8188
        self.output_remote_dir = "/root/autodl-tmp/ComfyUI/output"
    
    def _exec(self, cmd, timeout=300):
        """执行 SSH 命令"""
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(self.host, port=self.port, username=self.username, 
                   password=self.password, timeout=10)
        i, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore")
        err = e.read().decode("utf-8", "ignore")
        c.close()
        return out.strip(), err.strip()
    
    def generate_image(self, prompt, negative_prompt, output_name, 
                       width=512, height=768, steps=25, cfg=7.5,
                       checkpoint="dreamshaper_8.safetensors"):
        """生成单张图片"""
        
        wf = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": hash(output_name) % 9999999,
                    "steps": steps, "cfg": cfg,
                    "sampler_name": "dpmpp_2m", "scheduler": "karras",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint}
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1}
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt + ", masterpiece, best quality", "clip": ["4", 1]}
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["4", 1]}
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]}
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": output_name, "images": ["8", 0]}
            }
        }
        
        payload = json.dumps({"prompt": wf})
        # Escape for shell
        escaped = payload.replace("'", "'\\''")
        
        cmd = f"curl -s -X POST http://127.0.0.1:{self.comfy_port}/prompt -H 'Content-Type: application/json' -d '{escaped}'"
        out, err = self._exec(cmd, timeout=10)
        
        try:
            result = json.loads(out)
            prompt_id = result.get("prompt_id")
        except:
            return None, f"Failed to submit: {out}"
        
        if not prompt_id:
            return None, f"No prompt_id: {out}"
        
        # Wait for completion
        for attempt in range(60):
            time.sleep(3)
            check = f"curl -s http://127.0.0.1:{self.comfy_port}/history/{prompt_id}"
            hist, _ = self._exec(check, timeout=10)
            
            if prompt_id in hist:
                # Parse history to get filename
                try:
                    hist_data = json.loads(hist)
                    outputs = hist_data.get(prompt_id, {}).get("outputs", {})
                    for node_id, node_out in outputs.items():
                        images = node_out.get("images", [])
                        if images:
                            img = images[0]
                            filename = img["filename"]
                            subfolder = img.get("subfolder", "")
                            if subfolder:
                                full_path = f"{self.output_remote_dir}/{subfolder}/{filename}"
                            else:
                                full_path = f"{self.output_remote_dir}/{filename}"
                            return full_path, None
                    return None, "No images in history"
                except Exception as e:
                    return None, f"Parse error: {e}"
        
        return None, "Timeout waiting for generation"
    
    def download_file(self, remote_path, local_path):
        """通过 SFTP 下载文件"""
        t = paramiko.Transport((self.host, self.port))
        t.connect(username=self.username, password=self.password)
        sftp = paramiko.SFTPClient.from_transport(t)
        sftp.get(remote_path, local_path)
        sftp.close()
        t.close()
        return True


# Test
if __name__ == "__main__":
    bridge = ComfyUIBridge(
        host="connect.westc.seetacloud.com",
        port=38342,
        username="root",
        password="bBXvSvISTNNB"
    )
    
    print("Testing image generation...")
    path, err = bridge.generate_image(
        prompt="Chinese cyberpunk city at night, neon lights, rainy street, Blade Runner aesthetic, cinematic",
        negative_prompt="ugly, deformed, blurry, bad anatomy, text, watermark, low quality",
        output_name="opendrama/test_cyberpunk",
        width=576,
        height=1024,
        steps=25
    )
    
    if path:
        print(f"✅ Generated: {path}")
        bridge.download_file(path, "C:/Users/Administrator/Desktop/test_gen.png")
        print("Downloaded to Desktop/test_gen.png")
    else:
        print(f"❌ Failed: {err}")
