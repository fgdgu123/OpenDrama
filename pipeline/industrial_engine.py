"""
《无限进化》工业级剧本引擎 v3.0
===============================
支持完整的 12 维度场景描述，生成 ComfyUI 可用的精确 prompt

格式标准:
  ## 场景N
  ### 场景描述    ← 环境、氛围、光线、色调
  ### 人物描述    ← 角色定位、外貌、服饰、姿态
  ### 多人定位    ← 多人构图、站位、交互关系
  ### 动作描述    ← 动态、速度线、特效
  ### 镜头语言    ← 视角、景别、运镜
  ### 画面Prompt  ← ComfyUI/文生视频 直接使用的prompt
  ### 负面Prompt  ← 排除项
  ### 旁白        ← narrator VO
  ### 对话        ← 角色台词
  ### 配文        ← 屏幕文字/字幕特效
  ### 音乐        ← BGM风格/曲目
  ### 音效        ← SFX清单
  ### 时长        ← 秒
  ### 类型        ← 风格分类
  ### 参考图      ← 场景/角色参考图路径
  ### 衔接        ← 与前/后场景的过渡方式
"""

import json, re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SceneFrame:
    """单帧/场景的完整描述"""
    id: str = ""
    scene_number: int = 0
    
    # 视觉层
    scene_desc: str = ""        # 场景环境描述
    char_desc: str = ""         # 角色外貌描述
    multi_char_layout: str = "" # 多人构图
    action_desc: str = ""       # 动作描述
    camera: str = ""            # 镜头语言
    image_prompt: str = ""      # 生图prompt
    negative_prompt: str = ""   # 负面prompt
    ref_image: str = ""         # 参考图
    
    # 音频层
    narration: str = ""         # 旁白
    dialogue: str = ""          # 对白
    dialogue_char: str = ""     # 说话人
    caption: str = ""           # 屏幕文字
    music: str = ""             # BGM
    sfx: List[str] = field(default_factory=list)  # 音效
    
    # 元数据
    duration: float = 5.0
    scene_type: str = "日常"
    transition: str = ""        # 衔接方式
    realm: str = ""             # 所在位面
    mood: str = ""              # 情绪调性


class IndustrialScriptEngine:
    """工业级剧本解析+增强引擎"""
    
    def __init__(self, script_path):
        self.script_path = Path(script_path)
        self.raw = self.script_path.read_text(encoding="utf-8")
        self.scenes: List[SceneFrame] = []
        self.metadata: Dict = {}
    
    def parse(self) -> List[SceneFrame]:
        """解析工业级剧本"""
        scenes = []
        lines = self.raw.split("\n")
        
        current: Optional[SceneFrame] = None
        current_field = None
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                current_field = None
                continue
            
            # 集元数据
            if stripped.startswith("# ") and not stripped.startswith("## "):
                self.metadata["title"] = stripped[2:]
                continue
            
            # 新场景
            if stripped.startswith("## ") and not stripped.startswith("### "):
                if current:
                    scenes.append(current)
                current = SceneFrame(
                    id=f"scene_{len(scenes)+1:03d}",
                    scene_number=len(scenes)+1,
                )
                current_field = None
                continue
            
            if current is None:
                continue
            
            # 字段标记
            if stripped.startswith("### "):
                tag = stripped[4:].lower()
                val_part = ""
                
                for delim in ["场景描述", "场景环境", "人物描述", "人物定位", "多人定位", "多人构图",
                              "动作描述", "镜头语言", "画面prompt", "画面", "负面prompt", "负面",
                              "旁白", "对话", "配文", "音乐", "音效", "时长", "类型", "场景类型", "风格",
                              "参考图", "衔接", "过渡", "情绪", "氛围", "位面"]:
                    if tag.startswith(delim):
                        val_part = tag[len(delim):].strip()
                        normalized = delim
                        if delim in ("场景类型", "风格"):
                            normalized = "类型"
                        elif delim == "场景环境":
                            normalized = "场景描述"
                        elif delim == "人物定位":
                            normalized = "人物描述"
                        elif delim == "多人构图":
                            normalized = "多人定位"
                        elif delim == "画面":
                            normalized = "画面prompt"
                        elif delim == "负面":
                            normalized = "负面prompt"
                        elif delim in ("过渡",):
                            normalized = "衔接"
                        elif delim == "氛围":
                            normalized = "情绪"
                        else:
                            normalized = delim
                        tag = normalized
                        break
                
                current_field = tag
                
                if val_part:
                    self._set_field(current, tag, val_part)
                
                continue
            
            # 多行值
            if current_field:
                existing = self._get_field(current, current_field)
                if isinstance(existing, str) and existing:
                    stripped = existing + " " + stripped
                elif isinstance(existing, list) and existing:
                    # For list fields, append as new item
                    if stripped:
                        existing.append(stripped)
                    continue
                self._set_field(current, current_field, stripped)
        
        if current:
            scenes.append(current)
        
        self.scenes = [s for s in scenes if s.scene_desc or s.image_prompt]
        return self.scenes
    
    def _set_field(self, scene: SceneFrame, field: str, value: str):
        v = value.strip()
        field_map = {
            "场景描述": "scene_desc", "场景环境": "scene_desc",
            "人物描述": "char_desc", "人物定位": "char_desc",
            "多人定位": "multi_char_layout", "多人构图": "multi_char_layout",
            "动作描述": "action_desc",
            "镜头语言": "camera",
            "画面prompt": "image_prompt", "画面": "image_prompt",
            "负面prompt": "negative_prompt", "负面": "negative_prompt",
            "旁白": "narration",
            "对话": "dialogue",
            "配文": "caption",
            "音乐": "music",
            "音效": "sfx",
            "参考图": "ref_image",
            "衔接": "transition", "过渡": "transition",
            "情绪": "mood", "氛围": "mood",
            "位面": "realm",
            "类型": "scene_type", "场景类型": "scene_type", "风格": "scene_type",
        }
        
        attr = field_map.get(field)
        if not attr:
            return
        
        if isinstance(getattr(scene, attr), list):
            items = [x.strip() for x in v.split(",") if x.strip()]
            getattr(scene, attr).extend(items)
        elif attr in ("duration",):
            try:
                setattr(scene, attr, float(v))
            except ValueError:
                pass
        elif attr == "scene_type":
            setattr(scene, "scene_type", v)
        else:
            setattr(scene, attr, v)
    
    def _get_field(self, scene: SceneFrame, field: str):
        field_map = {
            "场景描述": "scene_desc", "场景环境": "scene_desc",
            "人物描述": "char_desc", "人物定位": "char_desc",
            "多人定位": "multi_char_layout", "多人构图": "multi_char_layout",
            "动作描述": "action_desc",
            "镜头语言": "camera",
            "画面prompt": "image_prompt", "画面": "image_prompt",
            "负面prompt": "negative_prompt", "负面": "negative_prompt",
            "旁白": "narration", "对话": "dialogue", "配文": "caption",
            "音乐": "music", "音效": "sfx", "参考图": "ref_image",
            "衔接": "transition", "过渡": "transition",
            "情绪": "mood", "氛围": "mood", "位面": "realm",
        }
        attr = field_map.get(field, field)
        return getattr(scene, attr, "")
    
    def to_legacy(self) -> List[Dict]:
        """转换为兼容旧管线的格式"""
        result = []
        for s in self.scenes:
            result.append({
                "id": s.id,
                "title": f"场景{s.scene_number}",
                "narration": s.narration or s.caption or "",
                "prompt": s.image_prompt or s.scene_desc or "",
                "character": s.dialogue_char or "",
                "duration": s.duration,
                "type": s.scene_type,
                "realm": s.realm,
                "mood": s.mood,
                "transition": s.transition,
                "music": s.music,
                "sfx": s.sfx,
            })
        return result
    
    def build_master_prompt(self, scene: SceneFrame) -> str:
        """
        构建 ComfyUI/视频模型的完整 prompt
        
        顺序: 质量标签 → 镜头语言 → 人物 → 场景 → 动作 → 光线氛围 → 风格
        """
        parts = []
        
        # 1. 质量基准 (总是最先)
        parts.append("masterpiece, best quality, 8k, highly detailed")
        
        # 2. 镜头语言
        if scene.camera:
            parts.append(scene.camera)
        
        # 3. 人物描述 (对于文生视频, 人物必须精确)
        if scene.char_desc:
            parts.append(scene.char_desc)
        if scene.multi_char_layout:
            parts.append(scene.multi_char_layout)
        
        # 4. 场景环境
        if scene.scene_desc:
            parts.append(scene.scene_desc)
        elif scene.image_prompt:
            parts.append(scene.image_prompt)
        
        # 5. 动作
        if scene.action_desc:
            parts.append(scene.action_desc)
        
        # 6. 风格 (根据scene_type)
        style_map = {
            "科幻": "cyberpunk aesthetic, neon lighting, volumetric fog, sci-fi atmosphere, futuristic technology, H.R. Giger inspired",
            "国风水墨": "traditional Chinese ink wash painting, sumi-e brushwork, flowing ink splashes, rice paper texture, zen aesthetic, minimalist color with accent red, gold accents",
            "穿越": "dimensional portal, space-time distortion, cosmic energy, ethereal light, kaleidoscopic colors, reality bending",
            "异世界": "fantasy landscape, magical atmosphere, Studio Ghibli inspired, bioluminescent flora, floating islands, mythical architecture, epic scale",
            "动作": "dynamic action, motion blur, impact frames, particle effects, speed lines, dramatic camera angle, cinematic fight choreography, energy aura",
            "日常": "slice of life, warm natural lighting, detailed environment, atmospheric, emotional, Makoto Shinkai lighting",
        }
        if scene.scene_type in style_map:
            parts.append(style_map[scene.scene_type])
        
        # 7. 情绪调性
        if scene.mood:
            parts.append(f"{scene.mood} atmosphere, emotional depth")
        
        # 8. 3D 动漫渲染标签
        parts.append("3D anime render, cel-shaded, Pixar-style textures, cinematic lighting, film grain, depth of field")
        
        return ", ".join(parts)
    
    def build_negative_prompt(self, scene: SceneFrame) -> str:
        """构建统一的负面prompt"""
        base = (
            "lowres, bad anatomy, bad hands, text, error, missing fingers, "
            "extra digit, fewer digits, cropped, worst quality, low quality, "
            "normal quality, jpeg artifacts, signature, watermark, username, "
            "blurry, ugly, deformed, mutated, disfigured, fused fingers, "
            "too many fingers, long neck, extra limbs"
        )
        if scene.negative_prompt:
            return f"{base}, {scene.negative_prompt}"
        return base


# ── 全局资产库 ──

GLOBAL_ASSETS = {
    "characters": {
        "林渊": {
            "full_name": "林渊",
            "age": 21,
            "role": "男主",
            "desc": "21岁中国男大学生, 身高182cm, 身材挺拔瘦削但不单薄, 黑色短发带隐约银色挑染, 剑眉星目, 瞳孔觉醒后变为淡金色带环形纹理, 右手背有金色龙剑交织的进化印记, 常穿黑色高领战术内衬配深灰机能外套, 气质冷峻但眼神有温度",
            "voice": "zh-CN-YunyangNeural",
            "ref_face": "assets/chars/linyuan_ref.png",
            "ref_fullbody": "assets/chars/linyuan_full.png",
        },
        "苏晚晴": {
            "full_name": "苏晚晴",
            "age": 20,
            "role": "女主",
            "desc": "20岁中国女大学生, 身高168cm, 及腰黑色长发尾端渐变青色, 杏眼含秋水, 皮肤白皙透着健康血色, 身穿改良旗袍式战斗服, 蓝青色为主调绣有青鸾纹样, 温婉外表下藏着坚韧, 觉醒后背后浮现青鸾虚影",
            "voice": "zh-CN-XiaoxiaoNeural",
            "ref_face": "assets/chars/suwanqing_ref.png",
            "ref_fullbody": "assets/chars/suwanqing_full.png",
        },
        "陈天策": {
            "full_name": "陈天策",
            "age": 42,
            "role": "反派/后期盟友",
            "desc": "42岁中年男人, 身高185cm, 轮廓硬朗, 两鬓斑白后梳背头, 眼神冷冽如刀, 身穿暗红色纳米装甲作战服, 肩部有能量纹路, 压迫感极强, 双手覆盖黑铁色进化手甲, 气场如铁血将军",
            "voice": "zh-CN-YunxiNeural",
            "ref_face": "assets/chars/chentiance_ref.png",
        },
    },
    "realms": {
        "现实世界": "2029年中国一线城市, 超高层玻璃幕墙建筑群, 全息广告牌悬浮在街道上空, 无人机物流网络, 进化者与普通人混居, 街道偶见位面裂缝残留的能量粒子, 色调偏冷蓝+霓虹橙",
        "试炼道场": "悬浮在无尽星空中的巨型中国古建筑群, 汉白玉地面反射星辉, 飞檐翘角挂青铜风铃, 四周环绕漂浮的水墨卷轴, 中央有太极图腾的演武场, 没有天空没有地面只有星海, 金色道纹在石板上流淌",
        "桃源乡": "中国水墨画中的理想乡, 桃花四季不落, 溪流中流淌的是淡墨而非清水, 远山以皴法渲染, 雾气是真实的水墨晕染, 建筑是榫卯木结构茶亭, 色调以黑白为主点缀桃红和石青",
        "赛博废土": "被机械AI统治的废墟都市, 酸雨不断, 生锈的巨大机甲残骸半埋在瓦砾中, 霓虹涂鸦覆盖断裂的高架桥, 全息幽灵(死于这里的人类意识残留)在街道游荡, 色调以暗紫+荧光绿+铁锈红为主",
        "昆仑墟": "神话中的万山之祖, 终年冰雪覆盖的锯齿状山峰, 悬浮的玉石桥梁连接各峰, 山顶有半透明的宫殿群, 山海经异兽的巨大剪影在云雾中若隐若现, 神光从九天之上垂落, 色调以冰蓝+玉白+金色圣光为主",
        "虚空走廊": "维度之间的通道, 没有上下左右, 碎镜般漂浮着各时代文明的残片, 能量流如极光般流动, 远处能看到不同时间线同时播放如同碎裂的胶片, 色调以极光色+深紫+星银为主",
    },
    "music_styles": {
        "科幻": "低频电子合成器 + 工业打击乐 + 数字glitch音效 + 深沉弦乐 sub-bass",
        "国风水墨": "古琴/箫/琵琶主旋律 + 留白电子氛围 + 水墨滴落音效 + 钟磬余韵",
        "穿越": "时间扭曲音效 + 倒放钢琴 + 宇宙低频嗡鸣 + 水晶音色琶音",
        "异世界": "交响管弦乐 + 凯尔特竖琴 + 史诗合唱团 + 风铃和鸣",
        "动作": "高速电子鼓 + 失真吉他 + 合成器琶音跑动 + 金属撞击 + 肾上腺素类BGM",
        "日常": "钢琴独奏 + 温暖弦乐拨奏 + 环境音场 + lofi beats subtle",
    },
    "sfx_library": {
        "能量爆发": "低频嗡鸣 crescendo → 金色高频炸裂 → 粒子消散 shimmer",
        "水墨龙吟": "低沉龙吟 + 墨汁飞溅的湿润质感 + 纸卷展开的沙沙声",
        "系统UI": "数字bleep序列 + 全息投影hover音 + 数据流swoosh",
        "位面裂缝": "空间撕裂的金属摩擦声 + 异界低频共鸣 + 能量泄漏的电流声",
        "拳击命中": "低音撞击 + 骨骼震动 + 气浪扩散的whoosh",
    },
}


def dump_global_assets():
    """导出全局资产为JSON (给ComfyUI等工具用)"""
    return json.dumps(GLOBAL_ASSETS, ensure_ascii=False, indent=2)
