"""
批量短剧生产线 — 30集全自动生成
===============================
从剧本大纲自动创建完整剧本 → 分镜 → 生图 → 配音 → 合成

用法:
  python pipeline/batch_studio.py --count 30 --start 1
  python pipeline/batch_studio.py --episodes 1-5 --quality cinema
"""
import argparse, json, os, sys, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.script_engine import ScriptEngine
from pipeline.audio_engine import AudioEngine
from pipeline.composer import Composer
from pipeline.style_engine import STYLE_PRESETS, get_style_for_scene, build_character_prompt


class BatchStudio:
    """批量短剧工厂"""
    
    def __init__(self, config):
        self.cfg = config
        self.output_dir = Path(config.get("output_dir", "output"))
        self.episodes_dir = self.output_dir / "infinite_evolution"
        self.episodes_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计
        self.stats = {
            "total_episodes": 0,
            "total_scenes": 0,
            "total_images": 0,
            "total_time": 0,
            "failed": [],
        }
    
    def produce_episode(self, episode_num, script_path, style="异世界", quality="standard"):
        """
        生产单集短剧
        
        Args:
            episode_num: 集数
            script_path: 剧本文件路径
            style: 主导风格 (异世界/科幻/国风水墨/动作/穿越)
            quality: 质量预设 (quick/standard/quality/cinema)
        """
        import paramiko
        
        ep_id = f"ep{episode_num:02d}"
        print(f"\n{'='*55}")
        print(f"  📽️ 第{episode_num}集 | 风格: {style} | 质量: {quality}")
        print(f"{'='*55}")
        
        t_start = time.time()
        
        # 1. 解析剧本
        engine = ScriptEngine(script_path)
        scenes = engine.parse()
        
        # 智能增强: 给每个场景注入风格prompt
        style_data = get_style_for_scene(style)
        for scene in scenes:
            scene_type = scene.get("type", style)
            s = get_style_for_scene(scene_type)
            
            # 构建增强prompt
            enhanced = scene.get("prompt", "")
            if s["prefix"]:
                enhanced = f"{s['prefix']}, {enhanced}"
            
            # 添加角色描述
            char = scene.get("character", "")
            if char in ["林渊", "苏晚晴", "陈天策"]:
                from pipeline.style_engine import build_character_prompt
                realm = scene.get("realm", "")
                action = scene.get("action", "")
                enhanced = build_character_prompt(char, realm, action)
            
            scene["prompt"] = enhanced
            scene["_style_cfg"] = s["cfg"]
            scene["_style_steps"] = s["steps"]
        
        print(f"  📝 {len(scenes)} 个分镜")
        
        # 2. 生图 (SSH桥接)
        from pipeline.ipadapter_gen import MultiCharIPAdapter
        gen_config = {
            "ssh_host": self.cfg["ssh_host"],
            "ssh_port": self.cfg["ssh_port"],
            "ssh_user": self.cfg.get("ssh_user", "root"),
            "ssh_password": self.cfg["ssh_password"],
            "comfy_port": self.cfg.get("comfy_port", 8188),
            "output_dir": str(self.episodes_dir / ep_id),
            "width": self.cfg.get("width", 576),
            "height": self.cfg.get("height", 1024),
            "steps": self.cfg.get("steps", 25),
            "cfg": self.cfg.get("cfg", 7.0),
            "ipadapter_weight": 0.8,
            "ipadapter_end_at": 0.65,
            "ref_face": self.cfg.get("ref_face"),
            "face_map": self.cfg.get("face_map", {}),
            "negative_prompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, blurry, ugly, deformed, watermark, signature, low quality",
        }
        
        if self.cfg.get("use_ipadapter"):
            gen = MultiCharIPAdapter(gen_config)
            scenes = gen.generate_with_face(scenes)
        else:
            from pipeline.scene_gen import SceneGenerator
            gen = SceneGenerator(gen_config, style_data)
            scenes = gen.generate(scenes)
        
        # 3. 配音
        audio = AudioEngine({
            "output_dir": str(self.episodes_dir / ep_id),
            "tts_engine": "edge-tts",
            "tts_voice": self.cfg.get("voice", "zh-CN-YunxiNeural"),
        })
        scenes = audio.generate(scenes)
        
        # 4. 合成
        comp = Composer({
            "output_dir": str(self.episodes_dir / ep_id),
            "width": self.cfg.get("width", 576),
            "height": self.cfg.get("height", 1024),
            "fps": 24,
            "subtitle_enabled": self.cfg.get("subtitle", True),
            "bgm_path": self.cfg.get("bgm_path"),
            "bgm_volume": 0.3,
        })
        
        ep_output = str(self.episodes_dir / f"{ep_id}.mp4")
        result = comp.compose(scenes, ep_output)
        
        dt = time.time() - t_start
        self.stats["total_episodes"] += 1
        self.stats["total_scenes"] += len(scenes)
        self.stats["total_time"] += dt
        
        if result:
            size_mb = os.path.getsize(result) / 1024 / 1024
            print(f"\n  ✅ 第{episode_num}集完成 → {result} ({size_mb:.1f}MB, {dt:.1f}s)")
        else:
            print(f"\n  ❌ 第{episode_num}集失败")
            self.stats["failed"].append(episode_num)
        
        return result
    
    def batch_produce(self, episode_range, script_dir, **kwargs):
        """
        批量生产多集
        
        Args:
            episode_range: (start, end) 或 list
            script_dir: 剧本文件目录
        """
        if isinstance(episode_range, tuple):
            episodes = list(range(episode_range[0], episode_range[1] + 1))
        else:
            episodes = episode_range
        
        total = len(episodes)
        print(f"\n{'='*55}")
        print(f"  🏭 批量生产 {total} 集短剧")
        print(f"  📂 剧本目录: {script_dir}")
        print(f"  📦 输出目录: {self.episodes_dir}")
        print(f"{'='*55}")
        
        results = {}
        for i, ep in enumerate(episodes):
            script_file = os.path.join(script_dir, f"ep{ep:02d}.md")
            if not os.path.exists(script_file):
                print(f"\n  ⚠️ 第{ep}集剧本不存在: {script_file}")
                continue
            
            print(f"\n[{i+1}/{total}] ", end="")
            result = self.produce_episode(ep, script_file, **kwargs)
            results[ep] = result
        
        # 打印总结
        print(f"\n{'='*55}")
        print(f"  📊 批量生产完成")
        print(f"  成功: {len([r for r in results.values() if r])}/{total} 集")
        print(f"  总耗时: {self.stats['total_time']/60:.1f} 分钟")
        if self.stats["failed"]:
            print(f"  失败: 第{self.stats['failed']}集")
        print(f"{'='*55}")
        
        return results


def main():
    p = argparse.ArgumentParser(description="批量短剧生产线")
    p.add_argument("--episodes", default="1-5", help="集数范围 (如 1-5 或 1,3,5)")
    p.add_argument("--script-dir", default="templates/scripts/infinite_evolution")
    p.add_argument("--style", default="异世界", choices=list(STYLE_PRESETS.keys()))
    p.add_argument("--quality", default="standard", choices=["quick", "standard", "quality"])
    p.add_argument("--no-ipadapter", action="store_true")
    p.add_argument("--no-subtitle", action="store_true")
    p.add_argument("--voice", default="zh-CN-YunxiNeural")
    p.add_argument("--bgm")
    
    # SSH
    p.add_argument("--ssh-host", default="connect.westc.seetacloud.com")
    p.add_argument("--ssh-port", type=int, default=38342)
    p.add_argument("--ssh-user", default="root")
    p.add_argument("--ssh-password", default="bBXvSvISTNNB")
    p.add_argument("--comfy-port", type=int, default=8188)
    
    args = p.parse_args()
    
    # 解析集数范围
    if "-" in args.episodes:
        start, end = args.episodes.split("-")
        episode_range = (int(start), int(end))
    elif "," in args.episodes:
        episode_range = [int(x.strip()) for x in args.episodes.split(",")]
    else:
        episode_range = [int(args.episodes)]
    
    config = {
        "ssh_host": args.ssh_host,
        "ssh_port": args.ssh_port,
        "ssh_user": args.ssh_user,
        "ssh_password": args.ssh_password,
        "comfy_port": args.comfy_port,
        "output_dir": "output",
        "width": 576, "height": 1024,
        "steps": 25, "cfg": 7.5,
        "use_ipadapter": not args.no_ipadapter,
        "subtitle": not args.no_subtitle,
        "voice": args.voice,
        "bgm_path": args.bgm,
        "face_map": {
            "林渊": "faces/hero_linyuan.png",
            "苏晚晴": "faces/heroine_suwanqing.png",
            "陈天策": "faces/villain_chentiance.png",
        },
    }
    
    studio = BatchStudio(config)
    studio.batch_produce(episode_range, args.script_dir, style=args.style)


if __name__ == "__main__":
    main()
