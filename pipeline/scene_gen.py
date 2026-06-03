"""
分镜生成器 — 调用 ComfyUI API 生成关键帧图片

支持:
  - DreamShaper 8 + IP-Adapter PLUS (锁脸)
  - 多个 IP-Adapter 参考图 (多角色)
  - 批量生成 + 进度追踪
  - 失败重试
"""
import json
import os
import time
import base64
import requests
from pathlib import Path


class SceneGenerator:
    """ComfyUI 分镜生成器"""
    
    def __init__(self, config, style_data=None):
        self.api_url = config["comfyui_url"].rstrip("/")
        self.output_dir = Path(config["output_dir"])
        self.width = config.get("width", 576)
        self.height = config.get("height", 1024)
        self.steps = config.get("steps", 30)
        self.cfg = config.get("cfg", 8.0)
        self.sampler = config.get("sampler", "dpmpp_2m")
        self.scheduler = config.get("scheduler", "karras")
        self.ip_weight = config.get("ipadapter_weight", 0.75)
        self.ip_end_at = config.get("ipadapter_end_at", 0.65)
        self.ref_face = config.get("ref_face")
        self.negative_prompt = config.get("negative_prompt", "")
        self.style_data = style_data or {}
        self.characters = config.get("characters", {})
        
        # 创建输出目录
        self.frames_dir = self.output_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, scenes):
        """批量生成分镜图片"""
        total = len(scenes)
        print(f"  📸 开始生成 {total} 个分镜...")
        
        results = []
        success = 0
        failed = 0
        
        for i, scene in enumerate(scenes):
            scene_id = scene["id"]
            prompt = self._build_prompt(scene)
            
            print(f"  [{i+1}/{total}] {scene_id}: {scene.get('title', '')[:40]}", end="", flush=True)
            
            start_time = time.time()
            result = self._generate_single(scene_id, prompt)
            elapsed = time.time() - start_time
            
            if result:
                scene["frame_path"] = result
                scene["frame_url"] = str(self.frames_dir / f"{scene_id}.png")
                success += 1
                print(f" ✅ {elapsed:.1f}s")
            else:
                failed += 1
                print(f" ❌ 失败")
            
            results.append(scene)
        
        print(f"  📊 完成: {success} 成功, {failed} 失败")
        return results
    
    def _build_prompt(self, scene):
        """构建完整 prompt"""
        parts = []
        
        # 风格前缀
        if self.style_data.get("prefix"):
            parts.append(self.style_data["prefix"])
        
        # 角色描述
        character = scene.get("character")
        if character and character in self.characters:
            char_info = self.characters[character]
            if isinstance(char_info, dict):
                parts.append(char_info.get("description", character))
        elif character:
            parts.append(character)
        
        # 场景 prompt
        if scene.get("prompt"):
            parts.append(scene["prompt"])
        elif scene.get("narration"):
            parts.append(scene["narration"][:500])
        
        # 画质后缀
        parts.append("masterpiece, best quality, highly detailed, sharp focus, 8k")
        
        return ", ".join(parts)
    
    def _generate_single(self, scene_id, prompt, max_retries=3):
        """调用 ComfyUI 生成单张图片"""
        seed = hash(scene_id) % 999999
        
        workflow = self._build_workflow(prompt, seed)
        
        for attempt in range(max_retries):
            try:
                # 提交工作流
                resp = requests.post(
                    f"{self.api_url}/prompt",
                    json={"prompt": workflow},
                    timeout=30
                )
                
                if resp.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
                
                prompt_id = resp.json().get("prompt_id")
                if not prompt_id:
                    return None
                
                # 等待完成（轮询）
                if not self._wait_for_completion(prompt_id, timeout=300):
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
                
                # 获取输出图片
                image_data = self._get_output(prompt_id)
                if image_data:
                    # 保存本地
                    output_path = self.frames_dir / f"{scene_id}.png"
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    return str(output_path)
                
            except requests.exceptions.RequestException:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return None
        
        return None
    
    def _build_workflow(self, prompt, seed):
        """构建 ComfyUI 工作流 JSON"""
        # 基础工作流: LoadCheckpoint → CLIPTextEncode → KSampler → VAEDecode → SaveImage
        # 如果配置了 IP-Adapter，则注入 IPAdapter 节点
        
        wf = {
            # 加载检查点
            "4": {
                "inputs": {"ckpt_name": "dreamshaper_8.safetensors"},
                "class_type": "CheckpointLoaderSimple"
            },
            
            # 正负 Prompt
            "6": {
                "inputs": {"text": prompt, "clip": ["4", 1]},
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {"text": self.negative_prompt, "clip": ["4", 1]},
                "class_type": "CLIPTextEncode"
            },
            
            # 空 latent
            "5": {
                "inputs": {"width": self.width, "height": self.height, "batch_size": 1},
                "class_type": "EmptyLatentImage"
            },
            
            # KSampler
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": self.steps,
                    "cfg": self.cfg,
                    "sampler_name": self.sampler,
                    "scheduler": self.scheduler,
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler"
            },
            
            # VAE Decode
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                "class_type": "VAEDecode"
            },
            
            # 保存图片
            "9": {
                "inputs": {"filename_prefix": "OpenDrama", "images": ["8", 0]},
                "class_type": "SaveImage"
            },
        }
        
        # 如果有参考脸图，注入 IP-Adapter
        if self.ref_face and os.path.exists(self.ref_face):
            wf = self._inject_ipadapter(wf, prompt, seed)
        
        return wf
    
    def _inject_ipadapter(self, wf, prompt, seed):
        """注入 IP-Adapter PLUS 锁脸节点"""
        try:
            # 上传参考图
            with open(self.ref_face, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            
            upload_resp = requests.post(
                f"{self.api_url}/upload/image",
                files={"image": open(self.ref_face, "rb")},
                data={"overwrite": "true"},
                timeout=30
            )
            
            if upload_resp.status_code != 200:
                return wf  # 保留原工作流
            
            ref_name = upload_resp.json().get("name", "")
            if not ref_name:
                return wf
            
            # 使用 IPAdapterApply + IPAdapterModelLoader + CLIPVisionLoader
            wf["10"] = {
                "inputs": {"image": ref_name, "upload": "image"},
                "class_type": "LoadImage"
            }
            
            wf["11"] = {
                "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"},
                "class_type": "CLIPVisionLoader"
            }
            
            wf["12"] = {
                "inputs": {"ipadapter_file": "ip-adapter-plus_sd15.safetensors"},
                "class_type": "IPAdapterModelLoader"
            }
            
            wf["13"] = {
                "inputs": {
                    "ipadapter": ["12", 0],
                    "clip_vision": ["11", 0],
                    "image": ["10", 0],
                    "model": ["4", 0],
                    "weight": self.ip_weight,
                    "noise": 0.2,
                    "weight_type": "original",
                    "start_at": 0.0,
                    "end_at": self.ip_end_at,
                },
                "class_type": "IPAdapterApply"
            }
            
            # 重定向 KSampler 的 model 输入到 IPAdapter
            wf["3"]["inputs"]["model"] = ["13", 0]
            
            return wf
            
        except Exception:
            return wf
    
    def _wait_for_completion(self, prompt_id, timeout=300):
        """轮询等待 ComfyUI 完成"""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                resp = requests.get(
                    f"{self.api_url}/history/{prompt_id}",
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if prompt_id in data:
                        return True
                
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(1)
        
        return False
    
    def _get_output(self, prompt_id):
        """获取生成的图片数据"""
        try:
            resp = requests.get(
                f"{self.api_url}/history/{prompt_id}",
                timeout=10
            )
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            outputs = data.get(prompt_id, {}).get("outputs", {})
            
            for node_id, node_output in outputs.items():
                images = node_output.get("images", [])
                if images:
                    filename = images[0]["filename"]
                    subfolder = images[0].get("subfolder", "")
                    
                    img_resp = requests.get(
                        f"{self.api_url}/view",
                        params={"filename": filename, "subfolder": subfolder, "type": "output"},
                        timeout=30
                    )
                    
                    if img_resp.status_code == 200:
                        return img_resp.content
            
            return None
            
        except Exception:
            return None


if __name__ == "__main__":
    # 测试
    config = {
        "comfyui_url": "http://127.0.0.1:8188",
        "output_dir": "./output",
        "width": 512,
        "height": 912,
    }
    
    gen = SceneGenerator(config)
    
    test_scenes = [
        {
            "id": "test_001",
            "title": "测试场景",
            "prompt": "a beautiful landscape with mountains and lake, cinematic",
            "character": None,
        }
    ]
    
    results = gen.generate(test_scenes)
    print(f"\n结果: {results}")
