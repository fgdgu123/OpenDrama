"""
剧本引擎 — 解析剧本文件，提取分镜和角色信息

支持格式:
  1. Markdown 格式（推荐）
  2. 纯文本（自动按段落拆分为分镜）
  3. JSON 格式（精确控制）
"""
import json
import re
from pathlib import Path


class ScriptEngine:
    """剧本解析器"""
    
    def __init__(self, script_path):
        self.script_path = Path(script_path)
        self.raw_text = ""
        
        if not self.script_path.exists():
            raise FileNotFoundError(f"剧本文件不存在: {script_path}")
        
        with open(self.script_path, "r", encoding="utf-8") as f:
            self.raw_text = f.read()
    
    def parse(self):
        """解析剧本，返回分镜列表"""
        if self.script_path.suffix == ".json":
            return self._parse_json()
        elif self.script_path.suffix in (".md", ".markdown"):
            return self._parse_markdown()
        else:
            return self._parse_text()
    
    def _parse_json(self):
        """JSON 格式: { "scenes": [...], "characters": {...} }"""
        data = json.loads(self.raw_text)
        
        if isinstance(data, list):
            return data
        
        scenes = data.get("scenes", [])
        if not scenes and "episodes" in data:
            for ep in data["episodes"]:
                scenes.extend(ep.get("scenes", []))
        
        return scenes
    
    def _parse_markdown(self):
        """Markdown 格式 - 每个 ## 标题是一个分镜
        
        支持两种格式:
          ### 旁白 旁白文本     (同行)
          ### 旁白
          旁白文本               (下一行)
        """
        scenes = []
        lines = self.raw_text.split("\n")
        
        current_scene = None
        current_field = None  # 跟踪当前编辑字段
        scene_id = 0
        
        for line in lines:
            stripped = line.strip()
            
            # 空行 = 结束当前字段编辑
            if not stripped:
                current_field = None
                continue
            
            # ## 标记新分镜
            if stripped.startswith("## ") and not stripped.startswith("### "):
                if current_scene:
                    scenes.append(current_scene)
                
                scene_id += 1
                title = stripped[3:].strip()
                current_scene = {
                    "id": f"scene_{scene_id:03d}",
                    "title": title,
                    "narration": "",
                    "prompt": "",
                    "duration": 5.0,
                    "character": None,
                }
                current_field = None
                continue
            
            if current_scene is None:
                continue
            
            # ### 字段标记
            if stripped.startswith("### "):
                tag = stripped[4:]
                current_field = None
                
                # 角色
                if tag.startswith("角色") or tag.startswith("人物"):
                    val = tag.split("角色", 1)[-1].split("人物", 1)[-1].strip()
                    if val:
                        current_scene["character"] = val
                    else:
                        current_field = "character"
                
                # 旁白 / 对白
                elif tag.startswith("旁白") or tag.startswith("对白"):
                    val = tag.split("旁白", 1)[-1].split("对白", 1)[-1].strip()
                    if val:
                        current_scene["narration"] = val
                    else:
                        current_field = "narration"
                
                # 画面 / Prompt
                elif tag.startswith("画面") or tag.startswith("Prompt"):
                    val = tag.split("画面", 1)[-1].split("Prompt", 1)[-1].strip()
                    if val:
                        current_scene["prompt"] = val
                    else:
                        current_field = "prompt"
                
                # 时长
                elif tag.startswith("时长") or tag.startswith("Duration") or tag.startswith("时间"):
                    val = tag.split("时长", 1)[-1].split("Duration", 1)[-1].split("时间", 1)[-1].strip()
                    if val:
                        try:
                            current_scene["duration"] = float(val)
                        except ValueError:
                            pass
                    else:
                        current_field = "duration"
            
            else:
                # 非标记行 = 当前字段的值
                if current_field == "narration":
                    current_scene["narration"] = stripped
                    current_field = None
                elif current_field == "prompt":
                    current_scene["prompt"] = stripped
                    current_field = None
                elif current_field == "character":
                    current_scene["character"] = stripped
                    current_field = None
                elif current_field == "duration":
                    try:
                        current_scene["duration"] = float(stripped)
                    except ValueError:
                        pass
                    current_field = None
        
        # 最后一个分镜
        if current_scene:
            scenes.append(current_scene)
        
        return scenes
    
    def _parse_text(self):
        """纯文本 — 按空行分割，每段一个分镜"""
        scenes = []
        paragraphs = [p.strip() for p in self.raw_text.split("\n\n") if p.strip()]
        
        for i, para in enumerate(paragraphs):
            scenes.append({
                "id": f"scene_{i+1:03d}",
                "title": f"分镜 {i+1}",
                "narration": para[:200],
                "prompt": para[:500],
                "duration": max(3.0, min(8.0, len(para) / 8)),  # 估算时长
                "character": None,
            })
        
        return scenes


def build_prompt(scene, style_data, character_data=None):
    """根据分镜数据构建 Stable Diffusion prompt"""
    parts = []
    
    # 风格前缀
    if style_data and "prefix" in style_data:
        parts.append(style_data["prefix"])
    
    # 角色描述
    if scene.get("character") and character_data:
        char_info = character_data.get(scene["character"], scene["character"])
        if isinstance(char_info, dict):
            parts.append(char_info.get("description", scene["character"]))
        else:
            parts.append(str(char_info))
    elif scene.get("character"):
        parts.append(scene["character"])
    
    # 场景 prompt
    if scene.get("prompt"):
        parts.append(scene["prompt"])
    elif scene.get("narration"):
        parts.append(scene["narration"][:500])
    
    # 画质后缀
    parts.append("high quality, detailed, sharp focus")
    
    prompt = ", ".join(parts)
    return prompt


if __name__ == "__main__":
    # 自测
    import sys
    
    if len(sys.argv) > 1:
        engine = ScriptEngine(sys.argv[1])
    else:
        # 创建示例剧本
        sample_script = Path(__file__).parent.parent / "templates" / "scripts" / "sample.md"
        if sample_script.exists():
            engine = ScriptEngine(str(sample_script))
        else:
            print("用法: python script_engine.py <剧本文件>")
            print("示例剧本: templates/scripts/sample.md")
            sys.exit(1)
    
    scenes = engine.parse()
    print(f"\n解析完成: {len(scenes)} 个分镜\n")
    
    for s in scenes:
        print(f"[{s['id']}] {s.get('title', '')}")
        print(f"  旁白: {s.get('narration', '')[:80]}...")
        print(f"  时长: {s.get('duration', 5)}s")
        if s.get('character'):
            print(f"  角色: {s['character']}")
        print()
