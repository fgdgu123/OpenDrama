"""
OpenDrama Studio — 短剧全链路生成器 v1.0
==========================================
一条命令: 剧本 → 分镜 → 生图 → 配音 → 合成

用法:
  cd OpenDrama && python pipeline/generate.py --script templates/scripts/sample_office.md --dry-run
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path so imports work from OpenDrama root
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.script_engine import ScriptEngine
from pipeline.scene_gen import SceneGenerator
from pipeline.audio_engine import AudioEngine
from pipeline.composer import Composer

# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG = {
    "comfyui_url": os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"),
    "output_dir": os.environ.get("OPENDRAMA_OUTPUT", "./output"),
    
    # 图片生成
    "width": 576,
    "height": 1024,
    "steps": 30,
    "cfg": 8.0,
    "sampler": "dpmpp_2m",
    "scheduler": "karras",
    
    # IP-Adapter 锁脸
    "ipadapter_weight": 0.75,
    "ipadapter_end_at": 0.65,
    "ref_face": None,  # 角色参考图路径
    
    # 视频生成 (Wan2.1)
    "video_enabled": False,
    "video_model": "wan21_i2v_14b_480p",
    "video_frames": 16,
    "video_fps": 8,
    
    # TTS
    "tts_engine": "edge-tts",  # edge-tts | cosyvoice
    "tts_voice": "zh-CN-YunxiNeural",
    "tts_rate": "+10%",
    
    # BGM
    "bgm_path": None,
    "bgm_volume": 0.3,
    
    # 导出
    "video_codec": "libx264",
    "crf": 23,
    "fps": 24,
    "subtitle_enabled": True,
    
    # 风格预设
    "style": "cinematic",
    "negative_prompt": (
        "ugly, deformed, blurry, bad anatomy, distorted, disfigured, "
        "extra limbs, low quality, watermark, text, poorly drawn, "
        "cartoon, 3d render, mutated hands, bad fingers, fused fingers"
    ),
}

STYLE_PRESETS = {
    "cinematic": {
        "prefix": "cinematic lighting, photorealistic, 8k, high detail, professional photography",
    },
    "cyberpunk": {
        "prefix": "cyberpunk style, neon lights, dark futuristic city, high tech low life, Blade Runner aesthetic, vaporwave, synthwave",
    },
    "anime": {
        "prefix": "anime style, Studio Ghibli, Makoto Shinkai, vibrant colors, cel shaded, 2d animation",
    },
    "noir": {
        "prefix": "film noir style, black and white, high contrast, dramatic shadows, venetian blinds, 1940s detective, moody atmosphere",
    },
    "fantasy": {
        "prefix": "fantasy art, epic fantasy, magical realm, Dungeons and Dragons style, Greg Rutkowski, ArtStation trending",
    },
    "horror": {
        "prefix": "horror aesthetic, dark atmosphere, disturbing, creepy, psychological horror, David Lynch style",
    },
    "period_drama": {
        "prefix": "Chinese period drama, historical costume, wuxia aesthetic, ancient China, ink wash painting style",
    },
}


class OpenDrama:
    """短剧工厂主控"""
    
    def __init__(self, config=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        
        # 处理风格预设
        style = self.config.get("style", "cinematic")
        if style in STYLE_PRESETS:
            self.style_data = STYLE_PRESETS[style]
        else:
            self.style_data = STYLE_PRESETS["cinematic"]
        
        # 初始化模块
        self.script_engine = None
        self.scene_gen = None
        self.audio_engine = None
        self.composer = None
        
        # 创建输出目录
        os.makedirs(self.config["output_dir"], exist_ok=True)
    
    def run(self, script_path, output_path, skip_scenes=False, dry_run=False):
        """执行全链路"""
        
        print("=" * 60)
        print(f"🎬 OpenDrama Studio v1.0")
        print(f"📝 剧本: {script_path}")
        print(f"🎨 风格: {self.config['style']}")
        print(f"🎙️ 配音: {self.config['tts_engine']} | {self.config['tts_voice']}")
        print(f"📦 输出: {output_path}")
        print("=" * 60)
        
        # ===== 第1步: 剧本解析 =====
        print("\n[1/4] 📝 剧本解析...")
        self.script_engine = ScriptEngine(script_path)
        scenes = self.script_engine.parse()
        print(f"  ✅ 解析完成: {len(scenes)} 个分镜")
        
        if dry_run:
            print("\n📋 分镜预览:")
            for i, scene in enumerate(scenes):
                print(f"  [{i+1}] {scene['id']}: {scene.get('narration', '')[:60]}...")
            print(f"\n✅ 干跑完成，未生成实际内容")
            return scenes
        
        # ===== 第2步: 分镜生成 =====
        if not skip_scenes:
            print(f"\n[2/4] 🎬 分镜生成 (ComfyUI @ {self.config['comfyui_url']})...")
            self.scene_gen = SceneGenerator(self.config, self.style_data)
            scenes = self.scene_gen.generate(scenes)
        else:
            print(f"\n[2/4] ⏭️ 跳过图片生成")
        
        # ===== 第3步: 配音 =====
        print(f"\n[3/4] 🎙️ 配音合成...")
        self.audio_engine = AudioEngine(self.config)
        scenes = self.audio_engine.generate(scenes)
        
        # ===== 第4步: 合成 =====
        print(f"\n[4/4] 📦 视频合成...")
        self.composer = Composer(self.config)
        result = self.composer.compose(scenes, output_path)
        
        print(f"\n{'=' * 60}")
        print(f"🎉 完成! → {output_path}")
        print(f"{'=' * 60}")
        
        return result
    
    def generate_only(self, script_path, output_dir):
        """仅生成分镜图片，不配音不合片"""
        self.script_engine = ScriptEngine(script_path)
        scenes = self.script_engine.parse()
        self.scene_gen = SceneGenerator(self.config, self.style_data)
        return self.scene_gen.generate(scenes)
    
    def audio_only(self, script_path, output_path):
        """仅配音合成"""
        self.script_engine = ScriptEngine(script_path)
        scenes = self.script_engine.parse()
        self.audio_engine = AudioEngine(self.config)
        scenes = self.audio_engine.generate(scenes)
        self.composer = Composer(self.config)
        return self.composer.compose_audio_only(scenes, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="OpenDrama Studio - 开源 AI 短剧工厂",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate.py --script my_script.md --output drama.mp4
  python generate.py --script my_script.md --style cyberpunk --dry-run
  python generate.py --script my_script.md --output drama.mp4 --skip-scenes
  python generate.py --script my_script.md --generate-only --output-dir ./frames
        """
    )
    
    parser.add_argument("--script", required=True, help="剧本文件路径 (txt/md/json)")
    parser.add_argument("--output", default="output/drama.mp4", help="输出文件路径")
    parser.add_argument("--style", default="cinematic", 
                        choices=list(STYLE_PRESETS.keys()), help="风格预设")
    parser.add_argument("--characters", help="角色配置文件 (JSON)")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural", help="TTS 语音")
    parser.add_argument("--bgm", help="背景音乐文件路径")
    
    parser.add_argument("--comfyui-url", default=DEFAULT_CONFIG["comfyui_url"],
                        help="ComfyUI API 地址")
    parser.add_argument("--output-dir", default=DEFAULT_CONFIG["output_dir"],
                        help="中间文件输出目录")
    
    parser.add_argument("--skip-scenes", action="store_true", help="跳过图片生成")
    parser.add_argument("--generate-only", action="store_true", help="仅生成图片")
    parser.add_argument("--audio-only", action="store_true", help="仅配音合成")
    parser.add_argument("--no-video", action="store_true", help="不要视频生成")
    parser.add_argument("--no-subtitle", action="store_true", help="不要字幕")
    parser.add_argument("--dry-run", action="store_true", help="仅预览分镜")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    parser.add_argument("--width", type=int, default=576)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--ip-weight", type=float, default=0.75)
    parser.add_argument("--tts-engine", default="edge-tts", choices=["edge-tts", "cosyvoice"])
    parser.add_argument("--ssh-host", help="ComfyUI SSH host")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--ssh-user", default="root")
    parser.add_argument("--ssh-password", help="SSH password")
    parser.add_argument("--comfy-port", type=int, default=8188, help="Remote ComfyUI port")
    
    args = parser.parse_args()
    
    # 构建配置
    config = {
        "comfyui_url": args.comfyui_url,
        "output_dir": args.output_dir,
        "style": args.style,
        "tts_engine": args.tts_engine,
        "tts_voice": args.voice,
        "bgm_path": args.bgm,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "ipadapter_weight": args.ip_weight,
        "subtitle_enabled": not args.no_subtitle,
        "video_enabled": not args.no_video,
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "comfy_port": args.comfy_port,
    }
    
    # 加载角色配置
    if args.characters:
        with open(args.characters, "r", encoding="utf-8") as f:
            config["characters"] = json.load(f)
    
    drama = OpenDrama(config)
    
    if args.dry_run:
        drama.run(args.script, args.output, dry_run=True)
    elif args.generate_only:
        drama.generate_only(args.script, args.output_dir)
    elif args.audio_only:
        drama.audio_only(args.script, args.output)
    else:
        drama.run(args.script, args.output, skip_scenes=args.skip_scenes)


if __name__ == "__main__":
    main()
