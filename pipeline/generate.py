"""
OpenDrama Studio — 短剧全链路生成器 v2.0
==========================================
一条脚本: 剧本 → 锁脸生图 → 图生视频 → 配音 → 合成

用法:
  python pipeline/generate.py --script templates/scripts/sample_office.md --style cyberpunk --ssh-host ... --ssh-password ... --output drama.mp4
"""
import argparse, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.script_engine import ScriptEngine
from pipeline.audio_engine import AudioEngine
from pipeline.composer import Composer

DEFAULT_CONFIG = {
    "comfyui_url": os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"),
    "output_dir": os.environ.get("OPENDRAMA_OUTPUT", "./output"),
    "width": 576, "height": 1024, "steps": 25, "cfg": 7.0,
    "sampler": "dpmpp_2m", "scheduler": "karras",
    "ipadapter_weight": 0.8, "ipadapter_end_at": 0.65,
    "ref_face": None,
    "video_enabled": False, "video_model": "wan21_i2v_14b_480p",
    "video_frames": 16, "video_fps": 8,
    "tts_engine": "edge-tts", "tts_voice": "zh-CN-YunxiNeural",
    "bgm_path": None, "bgm_volume": 0.3,
    "video_codec": "libx264", "crf": 23, "fps": 24,
    "subtitle_enabled": True,
    "style": "cinematic",
    "negative_prompt": "ugly, deformed, blurry, bad anatomy, distorted, disfigured, extra limbs, low quality, watermark, text, poorly drawn, cartoon, 3d render, mutated hands",
}

STYLE_PRESETS = {
    "cinematic": {"prefix": "cinematic lighting, photorealistic, 8k, high detail"},
    "cyberpunk": {"prefix": "cyberpunk style, neon lights, dark futuristic city, Blade Runner aesthetic"},
    "anime": {"prefix": "anime style, Studio Ghibli, Makoto Shinkai, vibrant colors"},
    "noir": {"prefix": "film noir, black and white, high contrast, dramatic shadows"},
    "fantasy": {"prefix": "fantasy art, epic, magical, Greg Rutkowski style"},
    "horror": {"prefix": "horror aesthetic, dark atmosphere, creepy, psychological horror"},
    "period_drama": {"prefix": "Chinese period drama, historical costume, wuxia aesthetic, ancient China"},
}


class OpenDrama:
    
    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        style = self.config.get("style", "cinematic")
        self.style_data = STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic"])
        os.makedirs(self.config["output_dir"], exist_ok=True)
    
    def run(self, script_path, output_path, skip_scenes=False, skip_audio=False, dry_run=False):
        print("=" * 55)
        print(f"🎬 OpenDrama Studio v2.0")
        print(f"📝 剧本: {script_path}")
        print(f"🎨 风格: {self.config['style']}")
        print(f"👤 锁脸: {'✅ IP-Adapter' if self.config.get('ref_face') else '❌ 关闭'}")
        print(f"🎥 视频: {'✅ Wan2.1' if self.config.get('video_enabled') else '❌ 关闭'}")
        print(f"🎙️ 配音: {self.config['tts_engine']} | {self.config['tts_voice']}")
        print(f"📦 输出: {output_path}")
        print("=" * 55)
        
        # Step 1: Script
        print("\n[1/5] 📝 剧本解析...")
        engine = ScriptEngine(script_path)
        scenes = engine.parse()
        print(f"  ✅ {len(scenes)} 个分镜")
        
        if dry_run:
            for i, s in enumerate(scenes):
                print(f"  [{i+1}] {s['id']}: {s.get('narration','')[:60]}...")
            return scenes
        
        # Step 2: Image generation (with optional IP-Adapter)
        if not skip_scenes:
            print(f"\n[2/5] 🎬 分镜生成...")
            if self.config.get("ref_face"):
                from pipeline.ipadapter_gen import IPAdapterFaceLock
                gen = IPAdapterFaceLock(self.config)
                scenes = gen.generate_with_face(scenes)
            else:
                from pipeline.scene_gen import SceneGenerator
                gen = SceneGenerator(self.config, self.style_data)
                scenes = gen.generate(scenes)
        else:
            print(f"\n[2/5] ⏭️ 跳过生图")
        
        # Step 3: Video generation (optional)
        if self.config.get("video_enabled") and not skip_scenes:
            print(f"\n[3/5] 🎥 图生视频 (Wan2.1)...")
            from pipeline.wan_video_gen import WanVideoGen
            vgen = WanVideoGen(self.config)
            scenes = vgen.generate_videos(scenes)
        else:
            print(f"\n[3/5] ⏭️ 跳过视频")
        
        # Step 4: Audio
        if not skip_audio:
            print(f"\n[4/5] 🎙️ 配音...")
            audio = AudioEngine(self.config)
            scenes = audio.generate(scenes)
        else:
            print(f"\n[4/5] ⏭️ 跳过配音")
        
        # Step 5: Compose
        print(f"\n[5/5] 📦 合成...")
        comp = Composer(self.config)
        result = comp.compose(scenes, output_path)
        
        print(f"\n{'=' * 55}")
        print(f"🎉 完成 → {output_path}")
        print(f"{'=' * 55}")
        return result


def main():
    p = argparse.ArgumentParser(description="OpenDrama Studio v2.0")
    p.add_argument("--script", required=True, help="剧本文件")
    p.add_argument("--output", default="output/drama.mp4", help="输出路径")
    p.add_argument("--style", default="cinematic", choices=list(STYLE_PRESETS.keys()))
    p.add_argument("--ref-face", help="IP-Adapter 参考脸图路径")
    p.add_argument("--ip-weight", type=float, default=0.8)
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--no-subtitle", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-scenes", action="store_true")
    p.add_argument("--skip-audio", action="store_true")
    
    # SSH
    p.add_argument("--ssh-host")
    p.add_argument("--ssh-port", type=int, default=22)
    p.add_argument("--ssh-user", default="root")
    p.add_argument("--ssh-password")
    p.add_argument("--comfy-port", type=int, default=8188)
    
    # Image
    p.add_argument("--width", type=int, default=576)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--steps", type=int, default=25)
    
    # TTS
    p.add_argument("--tts-engine", default="edge-tts")
    p.add_argument("--voice", default="zh-CN-YunxiNeural")
    p.add_argument("--bgm")
    
    args = p.parse_args()
    
    config = {
        "output_dir": "output",
        "style": args.style,
        "tts_engine": args.tts_engine,
        "tts_voice": args.voice,
        "bgm_path": args.bgm,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "ipadapter_weight": args.ip_weight,
        "ref_face": args.ref_face,
        "video_enabled": not args.no_video,
        "subtitle_enabled": not args.no_subtitle,
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "comfy_port": args.comfy_port,
    }
    
    OpenDrama(config).run(args.script, args.output,
        skip_scenes=args.skip_scenes,
        skip_audio=args.skip_audio,
        dry_run=args.dry_run)


if __name__ == "__main__":
    main()
