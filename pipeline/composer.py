"""
合成器 — FFmpeg 视频合成 + 字幕 + BGM

功能:
  - 图片→视频（配旁白音频）
  - 多段拼接
  - 字幕叠加
  - BGM 混音
  - 红果/抖音/出海格式导出
"""
import os
import subprocess
import json
from pathlib import Path


class Composer:
    """视频合成器"""
    
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
        
        # 临时文件目录
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查 ffmpeg
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查 FFmpeg 是否可用"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("  ⚠️ FFmpeg 未找到!")
            print("  安装: https://ffmpeg.org/download.html")
            print("  Windows: choco install ffmpeg 或手动下载")
    
    def compose(self, scenes, output_path):
        """合成最终视频"""
        print(f"  🎬 合成 {len(scenes)} 个分镜...")
        
        # 第1步: 每个分镜生成独立视频片段
        segments = []
        for i, scene in enumerate(scenes):
            frame = scene.get("frame_path")
            audio = scene.get("audio_path")
            duration = scene.get("duration", 5.0)
            
            if not frame or not os.path.exists(frame):
                # Auto-generate a placeholder frame with text
                frame = self._gen_placeholder(scene["id"], scene.get("narration", "")[:50])
                if not frame:
                    print(f"  ⚠️ [{scene['id']}] 缺少图片，跳过")
                    continue
            
            seg_file = self.temp_dir / f"seg_{i:03d}.mp4"
            
            if self._image_to_video(frame, audio, duration, seg_file):
                segments.append((seg_file, scene))
            else:
                print(f"  ⚠️ [{scene['id']}] 合成失败")
        
        if not segments:
            print("  ❌ 没有可用的视频片段")
            return None
        
        # 第2步: 拼接所有片段
        concat_file = self.temp_dir / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg_file, _ in segments:
                f.write(f"file '{seg_file.absolute().as_posix()}'\n")
        
        concat_video = self.temp_dir / "concatenated.mp4"
        self._concat_videos(concat_file, concat_video)
        
        # 第3步: 叠加字幕
        if self.subtitle_enabled:
            subtitle_file = self._generate_subtitles(scenes)
            with_sub = self.temp_dir / "with_subtitles.mp4"
            success = self._add_subtitles(concat_video, subtitle_file, with_sub)
            if success and with_sub.exists():
                current_video = with_sub
            else:
                current_video = concat_video
        else:
            current_video = concat_video
        
        # 第4步: 混入 BGM
        if self.bgm_path and os.path.exists(self.bgm_path):
            final = Path(output_path)
            self._mix_bgm(current_video, self.bgm_path, str(final))
        else:
            # 直接复制
            import shutil
            shutil.copy(current_video, output_path)
        
        # 清理临时文件
        self._cleanup()
        
        print(f"  ✅ 合成完成 → {output_path}")
        return output_path
    
    def _image_to_video(self, image_path, audio_path, duration, output_path):
        """将图片+音频合成为视频片段"""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
        ]
        
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-i", str(audio_path)])
        
        # 滤镜: 缩放 + 居中裁剪
        scale_filter = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1"
        )
        
        cmd.extend([
            "-vf", scale_filter,
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
        ])
        
        if audio_path and os.path.exists(audio_path):
            cmd.extend(["-c:a", "aac", "-b:a", "128k", "-shortest"])
        
        cmd.append(str(output_path))
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return output_path.exists() and output_path.stat().st_size > 1000
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
    
    def _gen_placeholder(self, scene_id, text):
        """Generate a blank placeholder frame with scene text"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (self.width, self.height), (20, 20, 40))
            draw = ImageDraw.Draw(img)
            # Center text
            lines = [scene_id]
            if text:
                for i in range(0, len(text), 30):
                    lines.append(text[i:i+30])
            y = self.height // 2 - len(lines) * 15
            for line in lines:
                draw.text((self.width//2 - len(line)*4, y), line, fill=(200,200,255))
                y += 30
            path = self.temp_dir / f"placeholder_{scene_id}.png"
            img.save(path)
            return str(path)
        except ImportError:
            return None
    
    def _concat_videos(self, concat_file, output_path):
        """拼接所有视频片段"""
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            pass
    
    def _generate_subtitles(self, scenes):
        """生成 SRT 字幕文件"""
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
            
            start = self._format_srt_time(current_time)
            end = self._format_srt_time(current_time + duration)
            
            lines.append(str(seq))
            lines.append(f"{start} --> {end}")
            lines.append(narration)
            lines.append("")  # 空行
            
            current_time += duration
        
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return srt_path
    
    def _format_srt_time(self, seconds):
        """格式化为 SRT 时间戳"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def _add_subtitles(self, video_path, srt_path, output_path):
        """给视频添加字幕 - Windows 用 drawtext filter 替代 subtitles filter"""
        import platform
        
        if not srt_path.exists():
            return False
        
        try:
            # Windows 上 subtitles filter 路径处理有坑，用 drawtext 逐行渲染
            if platform.system() == "Windows":
                return self._add_subtitles_drawtext(video_path, srt_path, output_path)
            
            # Linux/macOS: 直接使用 subtitles filter
            srt_escaped = str(srt_path.absolute()).replace("\\", "/").replace(":", "\\:")
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"subtitles={srt_escaped}:force_style='FontSize=28,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=50'",
                "-c:v", self.codec,
                "-crf", str(self.crf),
                "-preset", "medium",
                "-c:a", "copy",
                str(output_path),
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return output_path.exists() and output_path.stat().st_size > 1000
        except Exception as e:
            print(f"  ⚠️ 字幕添加失败: {e}")
            return False
    
    def _add_subtitles_drawtext(self, video_path, srt_path, output_path):
        """Windows 兼容字幕: 用 drawtext 把字幕烧进每一个分镜"""
        # 解析 SRT 获得文字列表
        import re
        srt_text = srt_path.read_text(encoding="utf-8")
        entries = re.findall(r'\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\r?\n(.+)', srt_text)
        
        if not entries:
            return False
        
        # 构建 drawtext filter chain
        # 格式: drawtext=text='...':fontsize=28:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-th-80:enable='between(t,start,end)'
        filters = []
        current_time = 0.0
        
        for idx, (start, end, text) in enumerate(entries):
            text = text.strip().replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")
            
            # 解析时间戳
            def ts_to_sec(ts):
                parts = ts.replace(',', ':').split(':')
                return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2]) + int(parts[3])/1000
            
            t_start = ts_to_sec(start)
            t_end = ts_to_sec(end)
            
            draw = (
                f"drawtext=text='{text}':fontsize=28:fontcolor=white@0.95:"
                f"borderw=3:bordercolor=black@0.6:line_spacing=8:"
                f"x=(w-text_w)/2:y=h-text_h-80:"
                f"enable='between(t,{t_start},{t_end})'"
            )
            filters.append(draw)
        
        filter_chain = ",".join(filters)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", filter_chain,
            "-c:v", self.codec,
            "-crf", str(self.crf),
            "-preset", "medium",
            "-c:a", "copy",
            str(output_path),
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"  ⚠️ drawtext 失败: {result.stderr[:200]}")
                return False
            return output_path.exists() and output_path.stat().st_size > 1000
        except Exception as e:
            print(f"  ⚠️ 字幕: {e}")
            return False
    
    def _mix_bgm(self, video_path, bgm_path, output_path):
        """混入背景音乐"""
        # 先获取视频时长
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        
        try:
            result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip())
        except Exception:
            duration = 60.0
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(bgm_path),
            "-filter_complex",
            f"[1:a]volume={self.bgm_volume},aloop=loop=-1:size=44100,atrim=0:{duration}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception as e:
            print(f"  ⚠️ BGM 混音失败: {e}")
            import shutil
            shutil.copy(video_path, output_path)
    
    def compose_audio_only(self, scenes, output_path):
        """仅合成音频（无视频）"""
        # 这个功能用于测试配音效果
        print("  🎵 仅合成音频...")
        return None
    
    def _cleanup(self):
        """清理临时文件"""
        import shutil
        try:
            for f in self.temp_dir.glob("seg_*.mp4"):
                f.unlink()
            concat = self.temp_dir / "concat.txt"
            if concat.exists():
                concat.unlink()
            srt = self.temp_dir / "subtitles.srt"
            if srt.exists():
                srt.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    config = {
        "output_dir": "./output",
        "width": 576,
        "height": 1024,
    }
    
    composer = Composer(config)
    
    # 测试: 用现有图片和音频
    test_scenes = [
        {
            "id": "test_001",
            "frame_path": None,  # 需要实际图片
            "audio_path": None,  # 需要实际音频
            "narration": "测试字幕",
            "duration": 5.0,
        }
    ]
    
    # composer.compose(test_scenes, "test_output.mp4")
    print("Composer ready. Use compose() with valid scenes to generate video.")
    print(f"FFmpeg: {'✅' if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode == 0 else '❌'}")
