"""
OpenDrama Studio v4.0 — 一页搞定
"""
import streamlit as st
import sys, os, json, time, threading
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config("OpenDrama", "🎬", layout="wide", initial_sidebar_state="collapsed")

# ── CSS ──
st.markdown("""
<style>
.main-title{font-size:2.6rem;font-weight:900;background:linear-gradient(135deg,#ff6b35,#6b5ce7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{color:#999;font-size:0.85rem;margin-top:-10px;margin-bottom:16px}
.pill{display:inline-block;padding:4px 14px;border-radius:20px;font-size:0.8rem;font-weight:600;margin:3px;border:1px solid #ddd}
.pill-on{background:#e8f5e9;color:#2e7d32;border-color:#a5d6a7}
.pill-off{background:#fafafa;color:#ccc;border-color:#eee}
.output-card{border-radius:14px;border:2px solid #6b5ce7;padding:20px;background:linear-gradient(135deg,#fafafe,#f3f0ff);margin:12px 0}
.log-line{font-family:monospace;font-size:0.8rem;color:#666;padding:2px 0}
footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ── Config ──
CFG = json.loads(Path("config.json").read_text(encoding="utf-8")) if Path("config.json").exists() else {}
SRV = CFG.get("server", {})

# ── Session ──
for key, default in [("generating",False),("video_path",None),("logs",[]),("progress",0),("status","")]:
    if key not in st.session_state: st.session_state[key] = default

# ── Background runner ──
def run_pipeline(script_path, output_path, face_on, style, voice):
    from pipeline.generate import OpenDrama
    config = {
        "output_dir": "output", "style": style,
        "tts_engine": "edge-tts", "tts_voice": voice,
        "width": 576, "height": 1024, "steps": 25,
        "ipadapter_weight": 0.8 if face_on else 0,
        "ref_face": "output/frames/hero_ref_face.png" if face_on else None,
        "video_enabled": False, "subtitle_enabled": True,
        "ssh_host": SRV.get("ssh_host"), "ssh_port": SRV.get("ssh_port"),
        "ssh_user": SRV.get("ssh_user"), "ssh_password": SRV.get("ssh_password"),
    }
    try:
        st.session_state.status = "📝 解析剧本..."
        st.session_state.progress = 10
        
        from pipeline.script_engine import ScriptEngine
        scenes = ScriptEngine(script_path).parse()
        st.session_state.logs.append(f"✓ 解析: {len(scenes)} 个分镜")
        
        st.session_state.status = "🎬 生成分镜图..."
        st.session_state.progress = 20
        
        if face_on:
            from pipeline.ipadapter_gen import IPAdapterFaceLock
            gen = IPAdapterFaceLock(config)
            scenes = gen.generate_with_face(scenes)
        else:
            from pipeline.scene_gen import SceneGenerator
            gen = SceneGenerator(config)
            scenes = gen.generate(scenes)
        
        ok = sum(1 for s in scenes if s.get("frame_path"))
        st.session_state.logs.append(f"✓ 生图: {ok}/{len(scenes)}")
        st.session_state.progress = 55
        
        st.session_state.status = "🎙️ 配音..."
        from pipeline.audio_engine import AudioEngine
        scenes = AudioEngine(config).generate(scenes)
        st.session_state.progress = 75
        
        st.session_state.status = "📦 合成..."
        from pipeline.composer import Composer
        result = Composer(config).compose(scenes, output_path)
        st.session_state.progress = 100
        st.session_state.status = "✅ 完成!"
        st.session_state.logs.append(f"✓ 输出: {output_path}")
        st.session_state.video_path = result
    except Exception as e:
        st.session_state.status = "❌ 失败"
        st.session_state.logs.append(f"✗ {str(e)[:200]}")
    finally:
        st.session_state.generating = False

# ── Header ──
col_h, col_btn = st.columns([5, 1])
with col_h:
    st.markdown('<p class="main-title">🎬 OpenDrama Studio</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI 短剧工厂 —— 剧本→锁脸生图→配音→成片 | 全自动 零成本</p>', unsafe_allow_html=True)
with col_btn:
    if st.button("🔍 诊断", use_container_width=True): st.switch_page("pages/1_Diagnose.py")

# ── Mode selector ──
mode = st.radio("", ["📝 自由创作", "📚 模板生成", "📄 上传剧本"], horizontal=True, label_visibility="collapsed")

script_content = ""
script_path = None

if "📚" in mode:
    templates = {
        "🔒 悬疑科技": "templates/scripts/sample_office.md",
        "🏥 医疗惊悚": "templates/scripts/thriller_medical.md",
        "⚡ 灵气复苏": "templates/scripts/fantasy_awakening.md",
        "💼 商战爱情": "templates/scripts/romance_business.md",
        "🤖 科幻克隆": "templates/scripts/scifi_clone.md",
    }
    sel = st.selectbox("", list(templates.keys()), label_visibility="collapsed")
    script_path = templates[sel]
    script_content = open(script_path, encoding="utf-8").read()

elif "📄" in mode:
    f = st.file_uploader("", ["md","txt","json"], label_visibility="collapsed")
    if f:
        script_content = f.read().decode("utf-8")
        script_path = "temp_script.md"
        Path(script_path).write_text(script_content, encoding="utf-8")

elif "📝" in mode:
    script_content = st.text_area("", height=240, placeholder="## 场景1\n### 旁白\n深夜，林墨独自坐在办公室里...\n### 画面\ndark office, programmer at desk, monitors glowing\n### 角色\n男主\n### 时长\n5\n\n## 场景2\n### 旁白\n突然，一封加密邮件弹出...\n### 画面\ncomputer screen, red error, dramatic lighting\n### 角色\n男主\n### 时长\n4", label_visibility="collapsed")
    if script_content.strip():
        script_path = "temp_script.md"
        Path(script_path).write_text(script_content, encoding="utf-8")

# ── Controls bar ──
st.divider()
c1, c2, c3, c4, c5 = st.columns([2, 2, 1, 1, 2])

with c1:
    style = st.selectbox("🎨 风格", ["cyberpunk","cinematic","noir","anime","fantasy","horror"], label_visibility="collapsed")
with c2:
    voice = st.selectbox("🎙️ 配音", ["男声","女声","青年男","青年女"], index=0, label_visibility="collapsed")
with c3:
    face_on = st.checkbox("👤 锁脸", True)
with c4:
    sub_on = st.checkbox("📝 字幕", True)

VOICE_MAP = {"男声":"zh-CN-YunxiNeural","女声":"zh-CN-XiaoxiaoNeural","青年男":"zh-CN-YunyangNeural","青年女":"zh-CN-XiaoyiNeural"}

with c5:
    can_generate = bool(script_content.strip()) and not st.session_state.generating
    btn_text = "🎬 生成" if can_generate else ("⏳ 生成中..." if st.session_state.generating else "🛑 请先输入剧本")
    btn_disabled = not can_generate
    if st.button(btn_text, use_container_width=True, type="primary", disabled=btn_disabled):
        out_name = f"drama_{datetime.now().strftime('%H%M%S')}"
        output_path = f"output/{out_name}.mp4"
        st.session_state.generating = True
        st.session_state.video_path = None
        st.session_state.logs = []
        st.session_state.progress = 0
        st.session_state.status = "启动中..."
        threading.Thread(target=run_pipeline, args=(script_path, output_path, face_on, style, VOICE_MAP[voice])).start()
        st.rerun()

# ── Script preview ──
if script_content.strip():
    with st.expander("📋 剧本预览 (" + str(len([l for l in script_content.split('\n') if l.startswith('## ') and not l.startswith('### ')])) + " 场景)", expanded=False):
        st.code(script_content[:600] + ("..." if len(script_content)>600 else ""), language="markdown")

# ── Progress bar ──
if st.session_state.generating or st.session_state.progress > 0:
    st.progress(st.session_state.progress / 100)
    st.caption(st.session_state.status)
    
    if st.session_state.logs:
        st.markdown("\n".join(f'<p class="log-line">{l}</p>' for l in st.session_state.logs[-5:]), unsafe_allow_html=True)

# ── Result ──
if st.session_state.video_path and os.path.exists(st.session_state.video_path):
    vp = st.session_state.video_path
    st.markdown('<div class="output-card">', unsafe_allow_html=True)
    
    col_v, col_info = st.columns([3, 1])
    with col_v:
        st.video(vp)
    with col_info:
        fsize = os.path.getsize(vp)
        st.metric("文件大小", f"{fsize//1024}KB")
        with open(vp, "rb") as f:
            st.download_button("📥 下载", f, os.path.basename(vp), mime="video/mp4", use_container_width=True)
        st.caption(datetime.fromtimestamp(os.path.getmtime(vp)).strftime("%Y-%m-%d %H:%M"))
    
    st.markdown('</div>', unsafe_allow_html=True)

# ── Frame gallery ──
frames = sorted(Path("output/frames").glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:6]
if frames and not st.session_state.generating:
    st.markdown("**🖼️ 最新分镜**")
    cols = st.columns(3)
    for i, fp in enumerate(frames):
        cols[i%3].image(str(fp), use_container_width=True)

# ── Footer ──
st.divider()
col_f1, col_f2 = st.columns([4, 1])
col_f1.caption("OpenDrama Studio v4.0 · MIT · github.com/fgdgu123/OpenDrama")
if col_f2.button("🔄 刷新", use_container_width=True):
    st.rerun()

# ── Auto-refresh while generating ──
if st.session_state.generating:
    time.sleep(2)
    st.rerun()
