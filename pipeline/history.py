"""
生成历史管理器 — 列出、预览、删除、对比所有成品
"""
import sys, os, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class HistoryManager:
    
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.history_file = self.output_dir / "history.json"
        self._ensure_history()
    
    def _ensure_history(self):
        if not self.history_file.exists():
            self.history_file.write_text("[]", encoding="utf-8")
    
    def _load(self):
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except:
            return []
    
    def _save(self, data):
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def add(self, video_path, metadata=None):
        """记录一次生成"""
        entry = {
            "path": str(video_path),
            "time": datetime.now().isoformat(),
            "size": os.path.getsize(video_path) if os.path.exists(video_path) else 0,
            "metadata": metadata or {},
        }
        data = self._load()
        data.append(entry)
        # Keep last 50
        self._save(data[-50:])
    
    def list(self, limit=20):
        """列出最近生成"""
        data = self._load()
        return sorted(data, key=lambda x: x["time"], reverse=True)[:limit]
    
    def get_frames_for(self, video_name):
        """获取某视频对应的分镜帧"""
        prefix = Path(video_name).stem.split("_")[0] if "_" in Path(video_name).stem else Path(video_name).stem[:8]
        frames_dir = self.output_dir / "frames"
        if frames_dir.exists():
            return sorted(frames_dir.glob(f"*{prefix}*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
        return []
    
    def delete(self, video_path):
        """删除视频和关联帧"""
        vp = Path(video_path)
        if vp.exists():
            vp.unlink()
        
        # Remove from history
        data = self._load()
        data = [d for d in data if d["path"] != str(video_path)]
        self._save(data)
    
    def stats(self):
        """统计"""
        frames = list(self.output_dir.rglob("frames/*.png")) if self.output_dir.exists() else []
        videos = list(self.output_dir.glob("*.mp4")) if self.output_dir.exists() else []
        total_size = sum(f.stat().st_size for f in videos)
        return {
            "total_videos": len(videos),
            "total_frames": len(frames),
            "total_size_mb": round(total_size / 1024 / 1024, 1),
        }
    
    def clear_all(self):
        """清空所有生成文件"""
        for pattern in ["*.mp4", "audio/*", "temp/*", "frames/*"]:
            for f in self.output_dir.glob(pattern):
                try: f.unlink()
                except: pass
        self._save([])


if __name__ == "__main__":
    h = HistoryManager()
    stats = h.stats()
    print(f"  Videos: {stats['total_videos']} | Frames: {stats['total_frames']} | Size: {stats['total_size_mb']}MB")
    
    recent = h.list(5)
    if recent:
        print(f"\n  最近生成:")
        for r in recent:
            dt = datetime.fromisoformat(r["time"]).strftime("%m-%d %H:%M")
            print(f"  [{dt}] {Path(r['path']).name} ({r['size']//1024}KB)")
    else:
        print("  暂无记录")
