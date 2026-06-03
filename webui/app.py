"""
OpenDrama Studio v5.0 — 极简单页，生成即预览
"""
import streamlit as st
import sys, os, json, time, threading
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
st.set_page_config("OpenDrama", "🎬", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.title{font-size:2rem;font-weight:900;background:linear-gradient(135deg,#ff6b35,#6b5ce7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center}
.sub{text-align:center;color:#999;margin-top:-8px;margin-bottom:16px;font-size:0.85rem}
.bar{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin:10px 0}
.bar-item{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:20px;border:1px solid #e0e0e0;font-size:0.85rem}
.log{font-family:monospace;font-size:0.78rem;color:#666;padding:1px 8px}
footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ── Init ──
for k,v in [("gen",False),("vid",None),("logs",[]),("pct",0),("msg","")]:
    if k not in st.session_state: st.session_state[k]=v

CFG = json.loads(open("config.json",encoding="utf-8").read()) if Path("config.json").exists() else {}
SRV = CFG.get("server",{})

VOICES = {"男声":"zh-CN-YunxiNeural","女声":"zh-CN-XiaoxiaoNeural","青年男":"zh-CN-YunyangNeural","青年女":"zh-CN-XiaoyiNeural"}
TEMPLATES = {
    "🔒 悬疑科技":"templates/scripts/sample_office.md",
    "🏥 医疗惊悚":"templates/scripts/thriller_medical.md",
    "⚡ 灵气复苏":"templates/scripts/fantasy_awakening.md",
    "💼 商战爱情":"templates/scripts/romance_business.md",
    "🤖 科幻克隆":"templates/scripts/scifi_clone.md",
}

def run(script_path, out_path, face, style, voice):
    from pipeline.generate import OpenDrama
    from pipeline.smart_engine import SmartEngine
    
    # Smart analysis for auto-tuning
    script_text = open(script_path,encoding="utf-8").read()
    analysis = SmartEngine().analyze(script_text)
    auto_params = analysis["params"]
    auto_style = analysis["detected_style"]
    
    c = {
        "output_dir":"output",
        "style":auto_style if style=="auto" else style,
        "tts_engine":"edge-tts","tts_voice":voice,
        "width":auto_params["width"],"height":auto_params["height"],
        "steps":auto_params["steps"],"ipadapter_weight":0.8,
        "ref_face":"output/faces/hero_ref_face.png" if face else None,
        "video_enabled":False,"subtitle_enabled":True,
        "ssh_host":SRV.get("ssh_host"),"ssh_port":SRV.get("ssh_port"),
        "ssh_user":SRV.get("ssh_user"),"ssh_password":SRV.get("ssh_password"),
    }
    try:
        st.session_state.msg="📝 解析..."; st.session_state.pct=10
        from pipeline.script_engine import ScriptEngine
        scenes = ScriptEngine(script_path).parse()
        st.session_state.logs=[f"✓ {len(scenes)} 场景"]

        st.session_state.msg="🎬 生图..."; st.session_state.pct=25
        if face:
            from pipeline.ipadapter_gen import MultiCharIPAdapter
            gen = MultiCharIPAdapter(c)
        else:
            from pipeline.scene_gen import SceneGenerator
            gen = SceneGenerator(c)
        scenes = gen.generate_with_face(scenes) if face else gen.generate(scenes)
        ok=sum(1 for s in scenes if s.get("frame_path"))
        st.session_state.logs.append(f"✓ 生图 {ok}/{len(scenes)}"); st.session_state.pct=55

        st.session_state.msg="🎙️ 配音..."; st.session_state.pct=70
        from pipeline.audio_engine import AudioEngine
        # Smart voice mapping: different characters get different voices
        ae = AudioEngine(c)
        for s in scenes:
            ch = s.get("character","").lower()
            if "女主" in ch or "女" in ch or "heroine" in ch:
                s["_voice"] = "zh-CN-XiaoxiaoNeural"
            elif "男主" in ch or "男" in ch or "hero" in ch:
                s["_voice"] = "zh-CN-YunxiNeural"
        scenes = ae.generate(scenes)
        st.session_state.pct=85

        st.session_state.msg="📦 合成..."; st.session_state.pct=95
        from pipeline.composer import Composer
        r = Composer(c).compose(scenes, out_path)
        st.session_state.vid=r; st.session_state.pct=100; st.session_state.msg="✅ 完成"
        if r:
            from pipeline.history import HistoryManager
            HistoryManager().add(out_path,{"style":style})
    except Exception as e:
        st.session_state.msg=f"❌ {e}"; st.session_state.logs.append(f"✗ {str(e)[:150]}")
    finally:
        st.session_state.gen=False

# ── UI ──
st.markdown('<p class="title">🎬 OpenDrama Studio</p>',unsafe_allow_html=True)
st.markdown('<p class="sub">剧本 → 锁脸生图 → 配音 → 成片 | 全自动零成本</p>',unsafe_allow_html=True)

# Mode
m=st.radio("",["📚 模板","✏️ 创作","📄 上传"],horizontal=True,label_visibility="collapsed")
script_path=None; script=""

if "📚" in m:
    sel=st.selectbox("",list(TEMPLATES.keys()),label_visibility="collapsed")
    script_path=TEMPLATES[sel]; script=open(script_path,encoding="utf-8").read()
elif "📄" in m:
    f=st.file_uploader("",["md","txt","json"],label_visibility="collapsed")
    if f: script=f.read().decode("utf-8"); script_path="temp_script.md"; Path(script_path).write_text(script,encoding="utf-8")
else:
    script=st.text_area("",height=200,placeholder="## 场景1\n### 旁白\n深夜，他独自坐在办公室里...\n### 画面\ndark office, programmer at desk\n### 角色\n男主\n### 时长\n5",label_visibility="collapsed")
    if script.strip(): script_path="temp_script.md"; Path(script_path).write_text(script,encoding="utf-8")

# Controls
st.markdown('<div class="bar">',unsafe_allow_html=True)
c1,c2,c3,c4,c5=st.columns([1.5,1,1,1,2])
with c1: quick=st.checkbox("⚡智能模式",True,help="自动匹配最优参数")
with c2: style=st.selectbox("🎨",["auto","cyberpunk","cinematic","noir","anime"],label_visibility="collapsed")
with c3: voice=st.selectbox("🎙️",list(VOICES.keys()),label_visibility="collapsed") if not quick else st.empty()
with c4: face=st.checkbox("👤",True) if not quick else st.empty()
with c5:
    go=bool(script.strip()) and not st.session_state.gen
    btn_label = "🚀 一键出片" if quick and go else ("🎬 生成" if go else ("⏳..." if st.session_state.gen else "🛑"))
    if st.button(btn_label,use_container_width=True,type="primary",disabled=not go):
        st.session_state.gen=True; st.session_state.vid=None; st.session_state.logs=[]; st.session_state.pct=0
        out=f"output/drama_{datetime.now().strftime('%H%M%S')}.mp4"
        final_style = "auto" if quick else style
        final_voice = VOICES.get(voice,"zh-CN-YunxiNeural") if not quick else "zh-CN-YunxiNeural"
        threading.Thread(target=run,args=(script_path,out,face,final_style,final_voice)).start()
        st.rerun()
st.markdown('</div>',unsafe_allow_html=True)

# Progress
if st.session_state.pct>0:
    st.progress(st.session_state.pct/100,st.session_state.msg)
if st.session_state.logs:
    st.markdown("\n".join(f'<p class="log">{l}</p>' for l in st.session_state.logs[-3:]),unsafe_allow_html=True)

# Result
if st.session_state.vid and os.path.exists(st.session_state.vid):
    vp=st.session_state.vid
    st.video(vp)
    cols=st.columns([3,1])
    cols[0].caption(vp)
    cols[1].download_button("📥",open(vp,"rb"),os.path.basename(vp),mime="video/mp4",use_container_width=True)

# Frames
frames=sorted(Path("output/frames").glob("*.png"),key=lambda x:x.stat().st_mtime,reverse=True)[:6]
if frames and not st.session_state.gen:
    st.markdown("#### 🖼️ 最新分镜")
    for i in range(0,len(frames),3):
        for j,c in enumerate(st.columns(3)):
            if i+j<len(frames): c.image(str(frames[i+j]),use_container_width=True)

# Refresh while generating
if st.session_state.gen: time.sleep(2); st.rerun()
