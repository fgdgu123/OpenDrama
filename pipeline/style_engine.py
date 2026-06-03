"""
《无限进化》5合1风格引擎
========================
根据场景类型自动选择最佳风格prompt组合
"""
import random

STYLE_PRESETS = {
    "穿越": {
        "prefix": "dimensional portal, space-time rift, energy vortex, cosmic tunnel, transition between worlds",
        "negative_extra": "static, normal lighting, mundane",
        "model": "dreamshaper",  # 写实基底 + 强化风格
        "steps": 25, "cfg": 7.5,
    },
    "异世界": {
        "prefix": "fantasy landscape, magical atmosphere, floating islands, ancient ruins, mystical forest, otherworldly, bioluminescent, epic scale",
        "negative_extra": "modern, urban, technology",
        "model": "animagine",  # 动漫模型
        "steps": 20, "cfg": 7.0,
    },
    "科幻": {
        "prefix": "cyberpunk 2077 style, neon cityscape, holographic UI, futuristic technology, chrome and glass, volumetric lighting, rain-slicked streets",
        "negative_extra": "medieval, ancient, rustic",
        "model": "dreamshaper",
        "steps": 25, "cfg": 7.5,
    },
    "国风水墨": {
        "prefix": "traditional Chinese ink wash painting style, sumi-e, brush strokes, flowing ink, calligraphy aesthetic, misty mountains, zen atmosphere, negative space, minimal color palette with accent red",
        "negative_extra": "photorealistic, 3D render, western art style, oil painting",
        "model": "animagine",
        "steps": 20, "cfg": 7.0,
    },
    "动作": {
        "prefix": "dynamic action scene, motion blur, dramatic camera angle, impact frames, particle effects, battle aura, speed lines, cinematic lighting, intense expression",
        "negative_extra": "static pose, boring, standing still",
        "model": "dreamshaper",
        "steps": 25, "cfg": 8.0,
    },
    "日常": {
        "prefix": "slice of life anime style, warm lighting, detailed background, emotional atmosphere, character focus",
        "negative_extra": "horror, dark, gore",
        "model": "animagine",
        "steps": 20, "cfg": 7.0,
    },
    "战斗": {
        "prefix": "epic battle scene, anime action, energy clash, impact effects, dramatic composition, cinematic fight choreography, sparks and particles, aura burst",
        "negative_extra": "peaceful, calm, static",
        "model": "dreamshaper",
        "steps": 30, "cfg": 8.0,
    },
}

CHARACTER_PROFILES = {
    "林渊": {
        "prompt": "tall young Chinese man, 21 years old, short black hair with subtle silver streaks, sharp eyes with golden irises after evolution, athletic build, wearing modern combat outfit with Chinese elements, dragon-scale patterns on arms",
        "ref_face": "faces/hero_linyuan.png",
    },
    "苏晚晴": {
        "prompt": "beautiful young Chinese woman, 20 years old, long flowing black hair with cyan tips, gentle blue eyes, slender figure, wearing elegant qipao-inspired combat dress with phoenix motifs",
        "ref_face": "faces/heroine_suwanqing.png",
    },
    "陈天策": {
        "prompt": "middle-aged Chinese man, 40s, cold expression, sharp features, slicked back hair with gray temples, wearing high-tech armor with red energy lines, imposing presence",
        "ref_face": "faces/villain_chentiance.png",
    },
}

# 每个位面的视觉指南
REALM_VISUALS = {
    "现实世界": "modern Chinese city, skyscrapers, neon signs, 2029 aesthetic, holographic advertisements",
    "试炼道场": "floating ancient dojo in space, Chinese temple architecture, starry void, jade platforms, ink scroll banners",
    "桃源乡": "Chinese ink painting landscape, peach blossom forest, misty mountains, ancient watermill, bamboo groves, golden sunset",
    "赛博废土": "post-apocalyptic cyberpunk city, rusted mechs, neon graffiti, holographic ghosts, acid rain, decaying infrastructure",
    "昆仑墟": "mythical Chinese mountain range, jade palaces, floating bridges, mythical beast silhouettes, ice and snow peaks, divine light",
    "虚空走廊": "abstract dimension, fractal geometry, flowing energy streams, shattered mirror fragments, aurora colors, weightless",
}

ANIMAGINE_WORKFLOW = {
    "checkpoint": "animagine-xl-3.1.safetensors",
    "vae": "sdxl_vae.safetensors",
    "clip": "dreamshaper8_clip.safetensors",
    "default_size": (896, 1152),  # SDXL native
    "negative_global": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, ugly, deformed",
}


def get_style_for_scene(scene_type="日常", intensity="normal"):
    """根据场景类型返回最佳风格参数"""
    if scene_type not in STYLE_PRESETS:
        scene_type = "日常"
    
    preset = STYLE_PRESETS[scene_type].copy()
    
    # 强度调整
    if intensity == "high":
        preset["steps"] = min(preset["steps"] + 5, 40)
        preset["cfg"] = min(preset["cfg"] + 0.5, 9.0)
    elif intensity == "low":
        preset["steps"] = max(preset["steps"] - 5, 15)
    
    return preset


def build_character_prompt(character, scene_visual, action=""):
    """构建角色+场景+动作的完整prompt"""
    char_info = CHARACTER_PROFILES.get(character, {"prompt": character})
    parts = [char_info["prompt"]]
    
    if scene_visual:
        parts.append(scene_visual)
    
    if action:
        parts.append(action)
    
    parts.append("anime style, cel-shaded, high quality, detailed, 8k, 3D anime render, Pixar-style lighting, cinematic composition")
    return ", ".join(parts)
