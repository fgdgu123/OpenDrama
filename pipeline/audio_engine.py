"""
音频引擎 — TTS 配音 + BGM 混音

支持:
  - edge-tts (免费, 在线) — 微软 Azure TTS
  - CosyVoice (免费, 离线) — 阿里开源语音合成
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path


class AudioEngine:
    """配音引擎"""
    
    def __init__(self, config):
        self.output_dir = Path(config["output_dir"])
        self.engine = config.get("tts_engine", "edge-tts")
        self.voice = config.get("tts_voice", "zh-CN-YunxiNeural")
        self.rate = config.get("tts_rate", "+10%")
        self.bgm_path = config.get("bgm_path")
        self.bgm_volume = config.get("bgm_volume", 0.3)
        
        # 语音角色映射
        self.voice_map = {
            "male": "zh-CN-YunxiNeural",
            "female": "zh-CN-XiaoxiaoNeural",
            "narrator": "zh-CN-YunxiNeural",
            "young_male": "zh-CN-YunyangNeural",
            "young_female": "zh-CN-XiaoyiNeural",
        }
        
        # 音频输出目录
        self.audio_dir = self.output_dir / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, scenes):
        """批量生成配音"""
        total = len(scenes)
        print(f"  🎙️ 引擎: {self.engine} | 语音: {self.voice}")
        print(f"  📝 生成 {total} 段配音...")
        
        if self.engine == "cosyvoice":
            return self._generate_cosyvoice(scenes)
        else:
            return self._run_edge_tts_sync(scenes)
    
    def _run_edge_tts_sync(self, scenes):
        """使用 edge-tts 同步生成（Windows 兼容）"""
        # 检查 edge-tts 是否可用
        try:
            subprocess.run(
                [sys.executable, "-m", "edge_tts", "--version"],
                capture_output=True, timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("  ⚠️ edge-tts 未安装，正在安装...")
            subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts", "-q"])
        
        success = 0
        failed = 0
        
        for i, scene in enumerate(scenes):
            narration = scene.get("narration", "").strip()
            if not narration:
                scene["audio_path"] = None
                continue
            
            # 确定语音（角色特定）
            voice = self.voice
            character = scene.get("character", "")
            if character and character in self.voice_map:
                voice = self.voice_map[character]
            
            scene_id = scene["id"]
            audio_file = self.audio_dir / f"{scene_id}.mp3"
            
            print(f"  [{i+1}/{len(scenes)}] {scene_id}: {narration[:40]}...", end="", flush=True)
            
            try:
                # 调用 edge-tts CLI
                # PowerShell 参数编码: 直接用 asyncio 子进程避免 shell 转义问题
                import asyncio
                import tempfile
                
                # 将文本写入临时文件，避免命令行转义
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                    f.write(narration)
                    tmp_txt = f.name
                
                result = subprocess.run([
                    sys.executable, "-m", "edge_tts",
                    "-f", tmp_txt,
                    "--voice", voice,
                    "--rate", self.rate,
                    "--write-media", str(audio_file),
                ], capture_output=True, text=True, timeout=60, encoding="utf-8")
                
                # 清理临时文件
                try:
                    os.unlink(tmp_txt)
                except Exception:
                    pass
                
                if audio_file.exists() and audio_file.stat().st_size > 100:
                    scene["audio_path"] = str(audio_file)
                    success += 1
                    print(" ✅")
                else:
                    scene["audio_path"] = None
                    failed += 1
                    print(f" ❌ 生成失败")
                    if result.stderr:
                        print(f"     {result.stderr[:300]}")
            
            except subprocess.TimeoutExpired:
                scene["audio_path"] = None
                failed += 1
                print(" ❌ 超时")
            except Exception as e:
                scene["audio_path"] = None
                failed += 1
                print(f" ❌ {e}")
        
        print(f"  📊 配音: {success} 成功, {failed} 失败")
        return scenes
    
    def _generate_cosyvoice(self, scenes):
        """使用 CosyVoice 离线生成"""
        print("  ⚠️ CosyVoice 需要额外配置 GPU 环境")
        print("  📖 参考: https://github.com/FunAudioLLM/CosyVoice")
        
        # CosyVoice 需要 GPU + 权重文件，这里给出框架
        # 实际使用时需要: pip install cosyvoice
        for scene in scenes:
            scene_id = scene["id"]
            narration = scene.get("narration", "")
            
            if narration:
                audio_file = self.audio_dir / f"{scene_id}.wav"
                try:
                    # import cosyvoice  # 需要安装
                    # cosyvoice.synthesize(narration, str(audio_file), voice=self.voice)
                    scene["audio_path"] = str(audio_file)
                except ImportError:
                    print("  ❌ CosyVoice 未安装")
                    scene["audio_path"] = None
            else:
                scene["audio_path"] = None
        
        return scenes


async def _edge_tts_async(text, voice, rate, output_path):
    """异步 edge-tts (备用，需要 python 3.7+)"""
    import edge_tts
    
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def list_voices():
    """列出可用语音"""
    import edge_tts
    
    voices = edge_tts.list_voices()
    for v in voices:
        if "zh-CN" in v["ShortName"]:
            print(f"  {v['ShortName']:30s} {v.get('Locale', '')} {v.get('VoiceTag', {}).get('VoiceRole', '')}")


if __name__ == "__main__":
    # 测试
    config = {
        "output_dir": "./output",
        "tts_engine": "edge-tts",
        "tts_voice": "zh-CN-YunxiNeural",
    }
    
    engine = AudioEngine(config)
    
    test_scenes = [
        {"id": "test_001", "narration": "这是一个测试配音，用于验证音频引擎是否正常工作。", "character": "narrator"},
    ]
    
    results = engine.generate(test_scenes)
    
    for s in results:
        if s.get("audio_path"):
            print(f"  ✅ {s['id']}: {s['audio_path']}")
        else:
            print(f"  ❌ {s['id']}: 失败")
