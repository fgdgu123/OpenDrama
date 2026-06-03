"""
OpenDrama Studio v3.0 — 工业级生成器
====================================
支持工业级剧本的所有维度:
  剧本解析 → 智能prompt构建 → 多角色锁脸生图 → 配音 → SFX → 合成

用法:
  python pipeline/generate_v3.py --script templates/scripts/infinite_evolution/ep01_industrial.md
"""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.industrial_engine import IndustrialScriptEngine, GLOBAL_ASSETS
from pipeline.audio_engine import AudioEngine
from pipeline.composer import Composer


class IndustrialOpenDrama:
    """v3.0: 工业级短剧工厂"""
    
    def __init__(self, config=None):
        self.cfg = {
            "output_dir": "output",
            "width": 576, "height": 1024,
            "steps": 25, "cfg": 7.5,
            "tts_engine": "edge-tts",
            "subtitle_enabled": True,
            "fps": 24,
            **(config or {}),
        }
        os.makedirs(self.cfg["output_dir"], exist_ok=True)
    
    def run(self, script_path, output_path, dry_run=False):
        print("=" * 55)
        print("🎬 OpenDrama Studio v3.0 — 工业级")
        print(f"📝 剧本: {script_path}")
        print(f"📦 输出: {output_path}")
        print("=" * 55)
        
        # Step 1: Parse industrial script
        print("\n[1/6] 📝 工业剧本解析...")
        engine = IndustrialScriptEngine(script_path)
        scenes = engine.parse()
        print(f"  ✅ {len(scenes)} 个场景")
        
        if engine.metadata:
            print(f"  📋 标题: {engine.metadata.get('title','未知')}")
        
        if dry_run:
            for s in scenes:
                print(f"\n  [{s.id}] 类型:{s.scene_type} | 时长:{s.duration}s")
                if s.char_desc:
                    print(f"    角色: {s.char_desc[:60]}...")
                if s.scene_desc:
                    print(f"    场景: {s.scene_desc[:60]}...")
                if s.music:
                    print(f"    音乐: {s.music[:40]}...")
                if s.sfx:
                    print(f"    音效: {', '.join(s.sfx[:3])}")
            return scenes
        
        # Step 2: Build master prompts
        print("\n[2/6] 🎨 构建Master Prompt...")
        for s in scenes:
            s.master_prompt = engine.build_master_prompt(s)
            s.master_negative = engine.build_negative_prompt(s)
        print(f"  ✅ {len(scenes)} 个prompt已构建")
        
        # Step 3: Generate images
        print("\n[3/6] 🎬 分镜生成...")
        scenes = self._generate_images(scenes)
        
        # Step 4: Generate audio (per-character voice)
        print("\n[4/6] 🎙️ 智能配音...")
        scenes = self._generate_audio(scenes)
        
        # Step 5: Compose
        print("\n[5/6] 📦 合成...")
        result = self._compose(scenes, output_path)
        
        # Step 6: Summary
        print(f"\n[6/6] ✅ 完成")
        music_types = set(s.music for s in scenes if s.music)
        sfx_count = sum(len(s.sfx) for s in scenes if s.sfx)
        print(f"  音乐风格: {len(music_types)} 种")
        print(f"  音效点: {sfx_count} 个")
        print(f"  输出: {output_path}")
        
        return result
    
    def _generate_images(self, scenes):
        """SSH 桥接生图"""
        ssh_host = self.cfg.get("ssh_host", "connect.westc.seetacloud.com")
        ssh_port = self.cfg.get("ssh_port", 38342)
        ssh_user = self.cfg.get("ssh_user", "root")
        ssh_pass = self.cfg.get("ssh_password", "bBXvSvISTNNB")
        comfy_port = self.cfg.get("comfy_port", 8188)
        
        from pipeline.scene_gen import SceneGenerator
        
        gen_config = {
            "ssh_host": ssh_host,
            "ssh_port": ssh_port,
            "ssh_user": ssh_user,
            "ssh_password": ssh_pass,
            "comfy_port": comfy_port,
            "output_dir": self.cfg["output_dir"],
            "width": self.cfg["width"],
            "height": self.cfg["height"],
            "steps": self.cfg["steps"],
            "cfg": self.cfg["cfg"],
        }
        
        style_data = {"prefix": "3D anime, cinematic, high quality"}
        
        # Convert to legacy scene format for scene_gen
        legacy_scenes = []
        for s in scenes:
            legacy_scenes.append({
                "id": s.id,
                "title": f"场景{s.scene_number}",
                "prompt": s.master_prompt,
                "narration": s.narration or s.caption or "",
                "character": s.dialogue_char or "",
                "duration": s.duration,
            })
        
        gen = SceneGenerator(gen_config, style_data)
        legacy_scenes = gen.generate(legacy_scenes)
        
        # Map back paths
        for i, s in enumerate(scenes):
            if i < len(legacy_scenes):
                s.frame_path = legacy_scenes[i].get("frame_path")
        
        return scenes
    
    def _generate_audio(self, scenes):
        """按角色配音"""
        audio_config = {
            "output_dir": self.cfg["output_dir"],
            "tts_engine": self.cfg["tts_engine"],
            "tts_voice": self.cfg.get("tts_voice", "zh-CN-YunxiNeural"),
        }
        
        audio = AudioEngine(audio_config)
        
        # Build audio scenes
        audio_scenes = []
        for s in scenes:
            text = s.narration or ""
            if s.dialogue:
                text = text + " " + s.dialogue if text else s.dialogue
            
            # Per-character voice
            char_info = GLOBAL_ASSETS["characters"].get(s.dialogue_char, {})
            voice = char_info.get("voice", audio_config["tts_voice"]) if isinstance(char_info, dict) else audio_config["tts_voice"]
            
            audio_scenes.append({
                "id": s.id,
                "narration": text,
                "duration": s.duration,
                "_voice": voice,
                "audio_path": None,
            })
        
        audio_scenes = audio.generate(audio_scenes)
        
        # Map back
        for i, s in enumerate(scenes):
            if i < len(audio_scenes) and audio_scenes[i].get("audio_path"):
                s.audio_path = audio_scenes[i]["audio_path"]
        
        return scenes
    
    def _compose(self, scenes, output_path):
        """合成最终视频"""
        comp_config = {
            "output_dir": self.cfg["output_dir"],
            "width": self.cfg["width"],
            "height": self.cfg["height"],
            "fps": self.cfg["fps"],
            "subtitle_enabled": self.cfg.get("subtitle_enabled", True),
            "bgm_path": self.cfg.get("bgm_path"),
        }
        
        comp = Composer(comp_config)
        
        legacy = []
        for s in scenes:
            legacy.append({
                "id": s.id,
                "frame_path": getattr(s, "frame_path", None),
                "audio_path": getattr(s, "audio_path", None),
                "narration": s.narration or s.caption or "",
                "duration": s.duration,
            })
        
        return comp.compose(legacy, output_path)


def main():
    p = argparse.ArgumentParser(description="OpenDrama Studio v3.0")
    p.add_argument("--script", required=True, help="工业级剧本文件")
    p.add_argument("--output", default="output/drama_v3.mp4")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--ssh-host", default="connect.westc.seetacloud.com")
    p.add_argument("--ssh-port", type=int, default=38342)
    p.add_argument("--ssh-user", default="root")
    p.add_argument("--ssh-password", default="bBXvSvISTNNB")
    p.add_argument("--comfy-port", type=int, default=8188)
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--width", type=int, default=576)
    p.add_argument("--height", type=int, default=1024)
    
    args = p.parse_args()
    
    config = {
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "comfy_port": args.comfy_port,
        "output_dir": "output",
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
    }
    
    IndustrialOpenDrama(config).run(args.script, args.output, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
