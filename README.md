# 🎬 OpenDrama Studio

> 开源 AI 短剧全链路工厂 — 从剧本到成片，一条命令。
> 全开源模型，零 API 费用，MIT 协议，商业友好。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

## 🎯 一句话

给短剧创作者的"一键流水线"——不是商业 SaaS，是**完全开源免费**的工具包。商业闭源平台收月费，我们靠生态赚钱。

## 🔥 为什么需要 OpenDrama？

| | 商业闭源 SaaS | 手工开源折腾 | **OpenDrama** |
|---|---|---|---|
| 费用 | 月费 199-999 元 | 免费 | **免费** |
| 技术门槛 | 零 | 极高 | **零** |
| 数据可控 | ❌ 锁在平台 | ✅ | ✅ |
| 可定制 | ❌ | ✅ | ✅ |
| 一键部署 | ✅ | ❌ | ✅ |
| 开源协议 | 闭源 | Apache/MIT | **MIT** |

## ⚡ 核心功能

```
📝 剧本引擎    → LLM 生成剧本 + 自动拆分分镜
🎬 分镜生成    → ComfyUI 工作流一键调用（StarLight / DreamShaper + IP-Adapter）
👤 人物锁脸    → IP-Adapter PLUS 固定角色形象，全剧统一
🎥 视频生成    → Wan2.1 图生视频批量生产
🎙️ 配音合成    → CosyVoice / edge-tts 多角色配音
🎵 BGM + 字幕  → 自动配乐 + 字幕合成
📦 成品导出    → FFmpeg 合片 + 红果/抖音/出海格式适配
```

## 🚀 3 分钟上手

### 前置条件

- **显卡**: 8GB+ 显存（推荐 16GB+）
- **Python**: 3.10+
- **ComfyUI**: 已安装并运行
- **FFmpeg**: 已安装

### 安装

```bash
git clone https://github.com/OpenDrama/OpenDrama.git
cd OpenDrama
pip install -r requirements.txt
```

### 方式一：Web UI（推荐）

```bash
python webui/app.py
# 浏览器打开 http://localhost:8501
```

### 方式二：命令行

```bash
# 三步出片
python pipeline/generate.py --script my_script.txt --output my_drama.mp4

# 进阶控制
python pipeline/generate.py \
  --script my_script.txt \
  --style cyberpunk \
  --characters characters.json \
  --voice male \
  --bgm suspense \
  --output my_drama.mp4
```

### 方式三：Docker 一键（含 ComfyUI）

```bash
docker-compose up -d
# 端口 8501: Web UI / 端口 8188: ComfyUI
```

## 📊 管线架构

```
剧本 (TXT/Markdown)
  │
  ├─→ LLM 解析 ─→ 分镜列表 (JSON)
  │
  ├─→ 角色管理 ─→ IP-Adapter 参考图
  │
  ├─→ ComfyUI ──→ 关键帧图片 (.png)
  │
  ├─→ Wan2.1 ───→ 动态视频片段 (.mp4)
  │
  ├─→ TTS ──────→ 配音音频 (.mp3)
  │
  ├─→ BGM ──────→ 背景音乐 (.mp3)
  │
  └─→ FFmpeg ───→ 最终成片 (.mp4)
```

## 🛠️ 技术栈

| 组件 | 技术 | 协议 |
|------|------|------|
| 剧本生成 | DeepSeek / Qwen / Llama3 | 开源免费 |
| 图片生成 | DreamShaper 8 + IP-Adapter PLUS | 开源/可商用 |
| 视频生成 | Wan2.1 I2V-14B | Apache 2.0 |
| 语音合成 | CosyVoice / edge-tts | 开源免费 |
| 编排引擎 | Python + ComfyUI API | - |
| Web UI | Streamlit | Apache 2.0 |

## 📦 项目结构

```
OpenDrama/
├── pipeline/          # 核心管线脚本
│   ├── generate.py    # 主入口
│   ├── script_engine.py   # 剧本引擎
│   ├── scene_gen.py       # 分镜生成
│   ├── video_gen.py       # 视频生成
│   ├── audio_engine.py    # 配音引擎
│   └── composer.py        # 合成导出
├── webui/             # Streamlit Web UI
│   └── app.py
├── templates/         # 分镜/角色/风格模板
│   ├── scripts/       # 剧本模板
│   ├── styles/        # 风格预设
│   └── characters/    # 角色预设
├── docker/            # Docker 部署
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/              # 文档
└── requirements.txt
```

## 🌍 赚钱模式（OpenDrama 作者视角）

| 层级 | 产品 | 目标 |
|------|------|------|
| 🆓 免费 | GitHub 开源 + 教程 | 占领搜索心智 |
| 💰 托管 | 云端 GPU 一键启动 | 主力收入 |
| 🎨 模板 | 精品模板市场 | 持续复购 |
| 🏢 企业 | 私有化部署 + 定制 | 高客单价 |
| 🌏 出海 | 海外版本地化 | 新蓝海 |

## 📄 协议

MIT License — 个人/商用均可，注明出处即可。

---

**别人在挖金子，我们在卖铲子。金矿会枯竭，铲子的需求只会越来越大。**
