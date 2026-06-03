"""
角色参考脸管理器 — 一键生成+管理多个角色参考图
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.ipadapter_gen import IPAdapterFaceLock


class FaceManager:
    """角色脸谱管理"""
    
    def __init__(self, ssh_config=None):
        self.config = {
            "ssh_host": ssh_config.get("ssh_host","connect.westc.seetacloud.com") if ssh_config else "connect.westc.seetacloud.com",
            "ssh_port": ssh_config.get("ssh_port",38342) if ssh_config else 38342,
            "ssh_user": "root",
            "ssh_password": ssh_config.get("ssh_password","bBXvSvISTNNB") if ssh_config else "bBXvSvISTNNB",
            "output_dir": "output",
            "width": 512, "height": 512,
            "steps": 20,
        }
        self.faces_dir = Path("output/faces")
        self.faces_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_face(self, name, description, gender="male"):
        """生成角色参考脸"""
        if gender == "male":
            desc = f"professional portrait photo of a young Chinese man, {description}, front facing, neutral expression, plain white background, studio lighting, photorealistic, 8k"
        else:
            desc = f"professional portrait photo of a young Chinese woman, {description}, front facing, neutral expression, plain white background, studio lighting, photorealistic, 8k"
        
        print(f"  生成 {name}...", end=" ", flush=True)
        
        gen = IPAdapterFaceLock(self.config)
        gen.ref_face_remote = None
        scenes = [{"id": f"face_{name}", "title": name, "prompt": desc}]
        results = gen.generate_with_face(scenes)
        
        if results and results[0].get("frame_path"):
            src = results[0]["frame_path"]
            dest = str(self.faces_dir / f"{name}.png")
            import shutil
            shutil.copy(src, dest)
            print(f"✅ {dest}")
            return dest
        else:
            print("❌")
            return None
    
    def generate_default_hero(self):
        """生成默认男主参考脸"""
        path = self.faces_dir / "hero_ref_face.png"
        if path.exists():
            print(f"  ✅ hero_ref_face 已存在")
            return str(path)
        return self.generate_face("hero_ref_face", "28 years old, short neat black hair, sharp intense brown eyes, pale fair skin, slim athletic build, clean shaven")
    
    def generate_default_heroine(self):
        """生成默认女主参考脸"""
        path = self.faces_dir / "heroine_ref_face.png"
        if path.exists():
            return str(path)
        return self.generate_face("heroine_ref_face", "26 years old, short pixie cut black hair, sharp intelligent eyes, fair skin, slim build", "female")
    
    def list_faces(self):
        return sorted(self.faces_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    def get_face_path(self, name):
        p = self.faces_dir / f"{name}.png"
        return str(p) if p.exists() else None


# 预定义角色库
CHARACTER_PRESETS = {
    "hero_programmer": {
        "name": "hero_ref_face",
        "desc": "28 years old, short neat black hair, sharp intense brown eyes, pale fair skin, slim athletic build, clean shaven",
        "gender": "male"
    },
    "heroine_hacker": {
        "name": "heroine_ref_face", 
        "desc": "26 years old, short pixie cut black hair, sharp intelligent eyes, fair skin",
        "gender": "female"
    },
    "hero_cultivator": {
        "name": "cultivator_ref_face",
        "desc": "22 years old, medium black hair tied back, determined bright eyes, tan skin, athletic build, wuxia style",
        "gender": "male"
    },
    "hero_ceo": {
        "name": "ceo_ref_face",
        "desc": "32 years old, slick dark hair, cold dark eyes, angular face, sharp jawline, wearing dark suit, confident",
        "gender": "male"
    },
    "heroine_entrepreneur": {
        "name": "entrepreneur_ref_face",
        "desc": "28 years old, medium wavy black hair, warm intelligent eyes, professional yet approachable, business attire",
        "gender": "female"
    }
}


if __name__ == "__main__":
    SSH = {"host":"connect.westc.seetacloud.com","port":38342,"password":"bBXvSvISTNNB"}
    mgr = FaceManager(SSH)
    
    print("生成默认角色参考脸...")
    mgr.generate_default_hero()
    mgr.generate_default_heroine()
    
    print(f"\n已有脸谱: {len(mgr.list_faces())}")
    for f in mgr.list_faces():
        print(f"  {f.name} ({f.stat().st_size//1024}KB)")
