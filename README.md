# 🎬 OpenDrama Studio

> 开源 AI 短剧全链路工厂 — 从剧本到成片，一条命令。
> 全开源模型，零 API 费用，MIT 协议，商业友好。

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

## 🎯 一句话

给短剧创作者的"一键流水线"——不是商业 SaaS，是**完全开源免费**的工具包。

## ⚡ 一键启动

```bash
# 1. 自动连通远程 ComfyUI（检测+启动+修复模型）
python launcher.py

# 2. 生成短剧（剧本→AI生图→配音→合成视频）
python pipeline/generate.py \
  --script templates/scripts/sample_office.md \
  --style cyberpunk \
  --ssh-host <服务器IP> --ssh-password <密码> \
  --output output/my_drama.mp4

# Windows 用户：直接双击 start.bat
```

## ✅ 已验证

| 步骤 | 状态 | 耗时 |
|------|------|------|
| 剧本解析 (Markdown→分镜) | ✅ | <1s |
| SSH桥接远程4090生图 | ✅ | ~6秒/张 |
| 配音合成 (edge-tts) | ✅ | ~2秒/段 |
| 视频合成 (FFmpeg) | ✅ | ~3秒 |
| 全链路端到端 (5场景) | ✅ | ~65秒 |

## 🔧 启动器功能

`launcher.py` 自动完成 6 项检测：
1. SSH 连通性
2. GPU 状态（型号/显存/利用率）
3. ComfyUI 服务状态
4. 模型文件完整性（自动修复缺失）
5. ComfyUI 自动启动
6. 图片生成能力验证

```bash
python launcher.py                    # 全自动
python launcher.py --check-only       # 仅检查
python launcher.py --force-restart    # 强制重启
python launcher.py --config my.json   # 自定义配置
```

## ⚡ 核心功能

- 📝 剧本引擎 → Markdown/JSON 自动解析分镜
- 🎬 分镜生成 → 远程 ComfyUI SSH 桥接，4090 GPU
- 🎙️ 配音合成 → edge-tts 中文多角色
- 📦 视频合成 → FFmpeg 拼图+配音+字幕
- 🌐 Web UI → Streamlit (开发中)
- 🐳 Docker → docker-compose 一键部署

## 🚀 安装

```bash
git clone https://github.com/OpenDrama/OpenDrama.git
cd OpenDrama
pip install -r requirements.txt
```

需要: Python 3.10+, FFmpeg, 远程 ComfyUI + GPU

## 🛠️ 技术栈

| 组件 | 技术 | 协议 |
|------|------|------|
| 图片生成 | DreamShaper 8 (UNET+CLIP+VAE) | 开源可商用 |
| 视频生成 | Wan2.1 I2V-14B | Apache 2.0 |
| 语音合成 | edge-tts / CosyVoice | 免费 |
| 编排引擎 | Python + SSH Bridge | - |
| 合成 | FFmpeg | GPL |

## 📦 项目结构

```
OpenDrama/
├── launcher.py        # 一键启动器
├── start.bat          # Windows 批处理
├── pipeline/          # 核心引擎
│   ├── generate.py    # 主入口
│   ├── script_engine.py
│   ├── scene_gen.py   # SSH桥接生图
│   ├── audio_engine.py
│   └── composer.py
├── webui/app.py       # Streamlit Web UI
├── templates/         # 剧本/角色模板
└── docker/            # Docker 部署
```

## 💰 商业模式（开源免费 + 增值服务）

| 层级 | 产品 | 目标 |
|------|------|------|
| 🆓 免费 | GitHub 开源 + 教程 | 占领搜索 |
| 💰 托管 | 云端 GPU 一键启动 | 主力收入 |
| 🎨 模板 | 精品模板市场 | 持续复购 |
| 🏢 企业 | 私有化部署 | 高客单 |

## 📄 协议

MIT License — 个人/商用均可。

---

**别人在挖金子，我们在卖铲子。**
