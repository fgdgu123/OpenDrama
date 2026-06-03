"""
合成器 v2.0 — FFmpeg 视频合成 + 字幕 + BGM
修复:
  - duration 优先使用音频实际长度
  - -framerate 确保静态图正常显示
  - 增强错误日志
"""
import os, subprocess, re
from pathlib import Path


class Composer:
    
    def __init__(self, config):
        self.output_dir = Path(config["output_dir"])
        self.width = config.get("width", 576)
        self.height = config.get("height", 1024)
        self.fps = config.get("fps", 24)
        self.codec = config.get("video_codec", "libx264")
        self.crf = config.get("crf", 23)
        self.bgm_path = config.get("bgm_path")
        self.bgm_volume = config.get("bgm_volume", 0.3)
        self.subtitle_enabled = config.get("subtitle_enabled", True)
        
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("  ⚠️ FFmpeg 未找到!")
    
    def compose(self, scenes, output_path):
        """合成最终视频"""
        print(f"  🎬 合成 {len(scenes)} 个分镜...")
        
        segments = []
        for i, scene in enumerate(scenes):
            frame = scene.get("frame_path")
            audio = scene.get("audio_path")
            duration = scene.get("duration", 5.0)
            
            if not frame or not os.path.exists(frame):
                print(f"  ⚠️ [{scene['id']}] 缺少图片: {frame}")
                frame = self._gen_placeholder(scene["id"], scene.get("narration", "")[:50])
                if not frame:
                    continue
            
            # 用音频实际长度覆盖 duration
            actual_duration = duration
            if audio and os.path.exists(audio):
                audio_len = self._get_audio_duration(audio)
                if audio_len and audio_len > 0.5:
                    actual_duration = max(duration, audio_len + 0.5)  # 留0.5秒缓冲
            
            seg_file = self.temp_dir / f"seg_{i:03d}.mp4"
            
            if self._image_to_video(frame, audio, actual_duration, seg_file):
                segments.append((seg_file, scene))
            else:
                print(f"  ⚠️ [{scene['id']}] 合成失败")
        
        if not segments:
            print("  ❌ 没有可用的视频片段")
            return None
        
        # 拼接所有片段
        concat_file = self.temp_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg_file, _ in segments:
                absolute = seg_file.resolve().as_posix()
                f.write(f"file '{absolute}'\n")
        
        concat_video = self.temp_dir / "concatenated.mp4"
        self._concat_videos(concat_file, concat_video)
        
        if not concat_video.exists() or concat_video.stat().st_size < 100:
            print("  ❌ 拼接失败")
            return None
        
        # 字幕
        current_video = concat_video
        if self.subtitle_enabled:
            subtitle_file = self._generate_subtitles(scenes)
            if subtitle_file:
                with_sub = self.temp_dir / "with_subtitles.mp4"
                if self._add_subtitles(concat_video, subtitle_file, with_sub):
                    current_video = with_sub
        
        # BGM
        final_path = Path(output_path)
        if self.bgm_path and os.path.exists(self.bgm_path):
            self._mix_bgm(current_video, self.bgm_path, str(final_path))
        else:
            import shutil
            shutil.copy(current_video, str(final_path))
        
        self._cleanup()
        
        size_mb = final_path.stat().st_size / 1024 / 1024 if final_path.exists() else 0
        print(f"  ✅ 合成完成 → {output_path} ({size_mb:.1f}MB)")
        return str(output_path)
    
    def _get_audio_duration(self, audio_path):
        """获取音频文件实际时长"""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception:
            return None
    
    def _image_to_video(self, image_path, audio_path, duration, output_path):
        """图片+音频 → 视频片段 — 单步合成"""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-framerate", str(self.fps),
            "-i", str(image_path),
        ]
        
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-i", str(audio_path)])
        
        cmd.extend([
            "-vf", (f"scale={self.width}:{self.height}"
                    ":force_original_aspect_ratio=decrease"
                    f",pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2"
                    ",setsar=1,format=yuv420p"),
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "medium",
            "-t", str(duration),
        ])
        
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
        
        cmd.append(str(output_path))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            ok = output_path.exists() and output_path.stat().st_size > 500
            if not ok:
                stderr = result.stderr[-300:] if result.stderr else ''
                print(f"\n      🐛 _img2vid failed: exists={output_path.exists()}, size={output_path.stat().st_size if output_path.exists() else 0}, rc={result.returncode}, err={stderr[:150]}")
            return ok
        except subprocess.TimeoutExpired:
            print(f"\n      ⏰ _img2vid timeout")
            return False
        except Exception as e:
            print(f"\n      💥 _img2vid exception: {e}")
            return False
    
    def _gen_placeholder(self, scene_id, text):
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (self.width, self.height), (20, 20, 40))
            draw = ImageDraw.Draw(img)
            lines = [scene_id]
            if text:
                for i in range(0, len(text), 30):
                    lines.append(text[i:i+30])
            y = self.height // 2 - len(lines) * 15
            for line in lines:
                try:
                    draw.text((self.width//2 - len(line)*4, y), line, fill=(200,200,255))
                except:
                    pass
                y += 30
            path = self.temp_dir / f"placeholder_{scene_id}.png"
            img.save(path)
            return str(path)
        except ImportError:
            return None
    
    def _concat_videos(self, concat_file, output_path):
        """拼接所有视频片段——必须转码，避免 codec 不兼容"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", self.codec, "-crf", str(self.crf),
            "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception:
            pass
    
    def _generate_subtitles(self, scenes):
        srt_path = self.temp_dir / "subtitles.srt"
        lines = []
        seq = 0
        current_time = 0.0
        
        for scene in scenes:
            narration = scene.get("narration", "")
            if not narration:
                continue
            duration = scene.get("duration", 5.0)
            seq += 1
            lines.append(str(seq))
            lines.append(f"{self._fmt_time(current_time)} --> {self._fmt_time(current_time + duration)}")
            lines.append(narration)
            lines.append("")
            current_time += duration
        
        if lines:
            srt_path.write_text("\n".join(lines), encoding="utf-8")
            return srt_path
        return None
    
    def _fmt_time(self, seconds):
        ms = int((seconds % 1) * 1000)
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def _add_subtitles(self, video_path, srt_path, output_path):
        if not srt_path.exists():
            return False
        
        try:
            # Use drawtext instead of subtitles filter (more reliable cross-platform)
            # Simple overlay: burn subtitles directly
            srt_abs = str(srt_path.resolve())
            # ffmpeg subtitles filter needs double-escaped colon on Windows
            escaped = srt_abs.replace('\\', '/').replace(':', '\\:')
            vf = f"subtitles='{escaped}':force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=2'"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", vf,
                "-c:v", self.codec, "-crf", str(self.crf),
                "-preset", "medium",
                "-c:a", "copy",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            ok = output_path.exists() and output_path.stat().st_size > 50000  # must be > 50KB
            if not ok:
                # subtitles failed — fall back to no-subtitle
                import shutil
                shutil.copy(video_path, output_path)
                print(f"\n  ⚠️ 字幕叠加失败，使用无字幕版本")
                return True  # Still return True, just without subs
            return True
        except Exception as e:
            print(f"  ⚠️ 字幕失败: {e}")
            import shutil
            shutil.copy(video_path, output_path)
            return True
    
    def _srt_to_ass(self, srt_path, ass_path):
        srt_text = srt_path.read_text(encoding="utf-8")
        blocks = re.split(r'\n\n+', srt_text.strip())
        
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.width}
PlayResY: {self.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,20,20,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        dialogs = []
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if not m:
                continue
            start = m.group(1).replace(',', '.')
            end = m.group(2).replace(',', '.')
            text = '\\N'.join(lines[2:])
            dialogs.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        
        ass_path.write_text(header + '\n'.join(dialogs), encoding="utf-8")
    
    def _mix_bgm(self, video_path, bgm_path, output_path):
        duration = self._get_audio_duration(video_path) or 60.0
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(bgm_path),
            "-filter_complex",
            f"[1:a]volume={self.bgm_volume},aloop=loop=-1:size=44100,atrim=0:{duration}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception:
            import shutil
            shutil.copy(video_path, output_path)
    
    def _cleanup(self):
        for f in self.temp_dir.glob("seg_*.mp4"):
            f.unlink(missing_ok=True)
        for f in self.temp_dir.glob("_tmp_*.mp4"):
            f.unlink(missing_ok=True)
        for f in self.temp_dir.glob("*.txt"):
            f.unlink(missing_ok=True)
        for f in self.temp_dir.glob("*.srt"):
            f.unlink(missing_ok=True)
        for f in self.temp_dir.glob("*.ass"):
            f.unlink(missing_ok=True)
