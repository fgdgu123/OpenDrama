"""
智能引擎 — 根据剧本内容自动优化参数
"""
import re


class SmartEngine:
    """剧本智能分析 + 参数自动调优"""
    
    def analyze(self, script_text):
        """分析剧本，返回最优参数"""
        scenes = len(re.findall(r'^##\s', script_text, re.MULTILINE))
        chars = list(set(re.findall(r'###\s*(?:角色|人物)\s*\n?\s*(.+)', script_text)))
        words = len(script_text)
        
        # 场景数 → 调步数（超10场景降步数加速）
        if scenes <= 3:   steps = 30
        elif scenes <= 6: steps = 25
        elif scenes <= 10: steps = 20
        else:             steps = 15
        
        # 字数多 → 可能需要更长时长
        avg_words_per_scene = max(3, words // max(scenes, 1))
        duration = min(8, max(3, avg_words_per_scene // 15))
        
        # 画面描述长度 → 调分辨率（长描述需要更大分辨率）
        prompts = re.findall(r'###\s*画面\s*\n?\s*(.+)', script_text)
        if prompts:
            avg_prompt_len = sum(len(p) for p in prompts) / len(prompts)
            if avg_prompt_len > 100:
                width, height = 768, 1152
            elif avg_prompt_len > 60:
                width, height = 576, 1024
            else:
                width, height = 512, 768
        else:
            width, height = 576, 1024
        
        # 角色多 → 需要锁脸
        need_face_lock = len(chars) > 0 and len(chars) <= 3
        
        # 风格推断
        keywords = {
            "cyberpunk": ["cyberpunk","霓虹","赛博","科幻","克隆","AI","代码"],
            "noir": ["悬疑","惊悚","杀人","死亡","恐怖","阴谋"],
            "fantasy": ["修仙","灵气","魔法","剑","异能"],
            "cinematic": ["职场","办公室","城市","公司"],
        }
        detected_style = "cinematic"
        for style, kws in keywords.items():
            if any(kw in script_text for kw in kws):
                detected_style = style
                break
        
        return {
            "scenes": scenes,
            "characters": chars,
            "words": words,
            "params": {
                "steps": steps,
                "width": width,
                "height": height,
                "duration": duration,
                "face_lock": need_face_lock,
            },
            "detected_style": detected_style,
        }
    
    def build_config(self, analysis, style=None, face_on=None):
        """从分析结果构建生成配置"""
        p = analysis["params"]
        s = style or analysis["detected_style"]
        f = face_on if face_on is not None else p["face_lock"]
        
        return {
            "width": p["width"],
            "height": p["height"],
            "steps": p["steps"],
            "style": s,
            "face_lock": f,
            "duration_per_scene": p["duration"],
        }


if __name__ == "__main__":
    se = SmartEngine()
    
    samples = [
        ("5场景悬疑", open("templates/scripts/sample_office.md",encoding="utf-8").read()),
        ("5场景科幻", open("templates/scripts/scifi_clone.md",encoding="utf-8").read()),
    ]
    
    for name, text in samples:
        r = se.analyze(text)
        print(f"{name}: {r['scenes']}场景 {r['words']}字 | 风格:{r['detected_style']} | 步数:{r['params']['steps']} | {r['params']['width']}x{r['params']['height']} | 锁脸:{r['params']['face_lock']}")
