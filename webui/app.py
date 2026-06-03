"""
OpenDrama Studio Web UI v3.0
极简智能 — 输入剧本 → 一键生成 → 预览下载
"""
import streamlit as st
import sys, os, json, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config("OpenDrama Studio", "🎬", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main-header{font-size:2.4rem;font-weight:900;background:linear-gradient(135deg,#ff6b35,#6b5ce7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:5px}
    .sub-header{text-align:center;color:#888;margin-bottom:20px;font-size:0.9rem}
    .card{border-radius:14px;border:1px solid #e8e8e8;padding:20px;margin:8px 0;transition:all .2s}
    .card:hover{border-color:#6b5ce7;box-shadow:0 2px 12px rgba(107,92,231,.12)}
    .status-ok{color:#2e7d32;font-weight:600}
    .status-warn{color:#f57c00;font-weight:600}
    .btn-primary{background:linear-gradient(135deg,#ff6b35,#6b5ce7)!important;color:white!important;border:none!important;border-radius:10px!important;padding:14px 28px!important;font-weight:700!important;font-size:1.1rem!important}
    .tag{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:2px}
    .tag-on{background:#e8f5e9;color:#2e7d32}
    .tag-off{background:#f5f5f5;color:#999}
    footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ── Init session state ──
if "scenes" not in st.session_state: st.session_state.scenes = []
if "generated" not in st.session_state: st.session_state.generated = False
if "video_path" not in st.session_state: st.session_state.video_path = None
if "server_ok" not in st.session_state: st.session_state.server_ok = None

CONFIG = Path("config.json")

def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except:
        return {
            "server": {"ssh_host":"connect.westc.seetacloud.com","ssh_port":38342,"ssh_user":"root","ssh_password":"bBXvSvISTNNB"},
            "image": {"width":576,"height":1024,"steps":25},
            "ipadapter": {"weight":0.8,"ref_face":"output/frames/hero_ref_face.png"},
            "style": "cyberpunk"
        }

cfg = load_config()
srv = cfg.get("server", {})

# ── Header ──
st.markdown('<p class="main-header">🎬 OpenDrama Studio</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">剧本 → AI生图(锁脸) → 配音 → 成片 | 全自动 零成本</p>', unsafe_allow_html=True)

# Quick status bar
col1, col2, col3, col4, col5 = st.columns(5)

if st.session_state.server_ok is None:
    try:
        from pipeline.scene_gen import SceneGenerator
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(srv["ssh_host"], port=srv["ssh_port"], username=srv["ssh_user"], password=srv["ssh_password"], timeout=5)
        i, o, _ = c.exec_command("curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8188/system_stats", timeout=5)
        st.session_state.server_ok = "200" in o.read().decode()
        c.close()
    except:
        st.session_state.server_ok = False

server_icon = "🟢" if st.session_state.server_ok else "🔴"
server_text = "服务器在线" if st.session_state.server_ok else "服务器离线"

with col1: st.markdown(f"**{server_icon} {server_text}**")
with col2: st.markdown("**🟢 4090 24GB**")
with col3: st.markdown("**🟢 IP-Adapter**")
with col4: st.markdown("**🟢 edge-tts**")
with col5: st.markdown("**🟢 FFmpeg**")

st.divider()

# ── Main 3-step wizard ──
step = st.radio("", ["1️⃣ 写剧本", "2️⃣ 调参数", "3️⃣ 生成"], horizontal=True, label_visibility="collapsed")

if "1️⃣" in step:
    st.markdown("### 📝 输入你的故事")
    
    col_input, col_preview = st.columns([5, 4])
    
    with col_input:
        mode = st.radio("", ["✏️ 自由创作", "🎯 示例剧本", "📄 上传文件"], horizontal=True, label_visibility="collapsed")
        
        script = ""
        script_path = None
        
        if "自由" in mode:
            script = st.text_area("Markdown 格式剧本", height=380, placeholder="## 场景1\n### 旁白\n深夜，他独自坐在办公室里...\n### 画面\ndark office, programmer at desk\n### 角色\n男主\n### 时长\n5\n\n## 场景2\n### 旁白\n突然，屏幕上出现了异常代码...\n### 画面\ncomputer screen, red error, dramatic\n### 角色\n男主\n### 时长\n4")
        elif "示例" in mode:
            script_path = "templates/scripts/sample_office.md"
            script = open(script_path, encoding="utf-8").read()
            st.success("已加载示例剧本")
        elif "上传" in mode:
            f = st.file_uploader("", ["md","txt","json"], label_visibility="collapsed")
            if f:
                script = f.read().decode("utf-8")
                script_path = "temp_script.md"
                Path(script_path).write_text(script, encoding="utf-8")
        
        if script:
            Path("temp_script.md").write_text(script, encoding="utf-8")
            script_path = script_path or "temp_script.md"
            st.session_state.script_path = script_path
    
    with col_preview:
        if script.strip():
            st.markdown("**📋 预览**")
            lines = script.strip().split("\n")
            scene_count = sum(1 for l in lines if l.startswith("## ") and not l.startswith("### "))
            st.metric("场景数", scene_count)
            
            with st.expander("展开剧本", expanded=True):
                st.code(script[:800] + ("..." if len(script) > 800 else ""), language="markdown")
        else:
            st.info("输入你的剧本后这里会显示预览")

elif "2️⃣" in step:
    st.markdown("### ⚙️ 调整参数")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("**🎨 风格**")
        style = st.selectbox("", ["cyberpunk","cinematic","noir","anime","fantasy","horror","period_drama"], label_visibility="collapsed")
        
        st.markdown("**👤 角色锁脸**")
        face_on = st.checkbox("启用 IP-Adapter", True)
        if face_on:
            ip_weight = st.slider("锁脸强度", 0.0, 1.0, 0.8, 0.05)
            ref_exists = Path("output/frames/hero_ref_face.png").exists()
            st.caption("参考图: " + ("✅ 已就绪" if ref_exists else "⚠️ 未生成"))
    
    with c2:
        st.markdown("**🎬 画面**")
        w = st.slider("宽度", 384, 1024, 576, 64)
        h = st.slider("高度", 512, 1280, 1024, 64)
        steps = st.slider("质量(步数)", 10, 40, 25, 5)
        
        st.markdown("**🎥 动画**")
        video_on = st.checkbox("图生视频", False)
    
    with c3:
        st.markdown("**🎙️ 配音**")
        voice = st.selectbox("", ["男声","女声","青年男","青年女"], label_visibility="collapsed")
        voice_map = {"男声":"zh-CN-YunxiNeural","女声":"zh-CN-XiaoxiaoNeural","青年男":"zh-CN-YunyangNeural","青年女":"zh-CN-XiaoyiNeural"}
        
        sub_on = st.checkbox("叠加字幕", True)
        
        st.markdown("**📦 输出**")
        out_name = st.text_input("", "my_drama", label_visibility="collapsed")
    
    # Save config
    cfg["image"]["width"] = w
    cfg["image"]["height"] = h
    cfg["image"]["steps"] = steps
    cfg["style"] = style
    cfg["ipadapter"]["weight"] = ip_weight if face_on else 0.0
    cfg["video"]["enabled"] = video_on
    cfg["audio"]["voice"] = voice_map[voice]
    cfg["output"]["subtitle"] = sub_on
    st.session_state.cfg = cfg
    st.session_state.out_name = out_name
    st.session_state.face_on = face_on

elif "3️⃣" in step:
    st.markdown("### 🚀 生成短剧")
    
    if not st.session_state.get("script_path"):
        st.warning("请先在「写剧本」步骤输入内容")
    else:
        c1, c2 = st.columns([2, 1])
        
        with c1:
            cfg = st.session_state.get("cfg", cfg)
            out_name = st.session_state.get("out_name", "my_drama")
            face_on = st.session_state.get("face_on", True)
            
            # Show summary
            tags = []
            tags.append(f"<span class='tag tag-on'>风格:{cfg.get('style','cyberpunk')}</span>")
            tags.append(f"<span class='tag tag-on'>锁脸</span>" if face_on else f"<span class='tag tag-off'>无锁脸</span>")
            tags.append(f"<span class='tag tag-on'>{cfg['image']['width']}x{cfg['image']['height']}</span>")
            tags.append(f"<span class='tag tag-on'>步数:{cfg['image']['steps']}</span>")
            tags.append(f"<span class='tag tag-on'>字幕</span>" if cfg.get("output",{}).get("subtitle",True) else "")
            
            st.markdown(" ".join(tags), unsafe_allow_html=True)
            
            if st.button("🎬 一键生成", use_container_width=True, type="primary"):
                script_path = st.session_state.script_path
                output_file = f"output/{out_name}.mp4"
                
                build_config = {
                    "output_dir": "output",
                    "style": cfg["style"],
                    "tts_engine": "edge-tts",
                    "tts_voice": cfg["audio"]["voice"],
                    "width": cfg["image"]["width"],
                    "height": cfg["image"]["height"],
                    "steps": cfg["image"]["steps"],
                    "ipadapter_weight": cfg["ipadapter"]["weight"],
                    "ref_face": "output/frames/hero_ref_face.png" if face_on else None,
                    "video_enabled": cfg.get("video",{}).get("enabled", False),
                    "subtitle_enabled": cfg.get("output",{}).get("subtitle", True),
                    "ssh_host": cfg["server"]["ssh_host"],
                    "ssh_port": cfg["server"]["ssh_port"],
                    "ssh_user": cfg["server"]["ssh_user"],
                    "ssh_password": cfg["server"]["ssh_password"],
                }
                
                # Progress
                prog = st.progress(0)
                status = st.empty()
                log_area = st.empty()
                
                logs = []
                def update_log(msg):
                    logs.append(msg)
                    log_area.code("\n".join(logs[-8:]), language=None)
                
                try:
                    from pipeline.script_engine import ScriptEngine
                    
                    status.text("📝 解析剧本...")
                    prog.progress(10)
                    engine = ScriptEngine(script_path)
                    scenes = engine.parse()
                    update_log(f"解析完成: {len(scenes)} 个分镜")
                    
                    status.text("🎬 生成分镜图...")
                    prog.progress(20)
                    
                    if face_on:
                        from pipeline.ipadapter_gen import IPAdapterFaceLock
                        gen = IPAdapterFaceLock(build_config)
                        scenes = gen.generate_with_face(scenes)
                    else:
                        from pipeline.scene_gen import SceneGenerator
                        gen = SceneGenerator(build_config, {"prefix":"cinematic"})
                        scenes = gen.generate(scenes)
                    
                    prog.progress(60)
                    ok = sum(1 for s in scenes if s.get("frame_path"))
                    update_log(f"分镜: {ok}/{len(scenes)}")
                    
                    status.text("🎙️ 合成配音...")
                    from pipeline.audio_engine import AudioEngine
                    scenes = AudioEngine(build_config).generate(scenes)
                    prog.progress(80)
                    
                    status.text("📦 合成视频...")
                    from pipeline.composer import Composer
                    result = Composer(build_config).compose(scenes, output_file)
                    prog.progress(100)
                    status.text("✅ 完成!")
                    
                    if result:
                        st.session_state.video_path = result
                        st.session_state.generated = True
                        st.session_state.scenes = scenes
                        update_log("生成完成: " + result)
                    else:
                        st.error("合成失败，请查看日志")
                        
                except Exception as e:
                    status.text("")
                    st.error(str(e))
                    update_log("ERROR: " + str(e)[:200])
        
        with c2:
            # Show previous result
            if st.session_state.generated and st.session_state.video_path:
                vp = st.session_state.video_path
                if os.path.exists(vp):
                    st.markdown("**✅ 最新成品**")
                    st.video(vp)
                    fs = os.path.getsize(vp)
                    st.caption(f"{vp} ({fs//1024}KB)")
                    
                    with open(vp, "rb") as f:
                        st.download_button("📥 下载视频", f, os.path.basename(vp), mime="video/mp4", use_container_width=True)
            
            # Frame gallery
            frames = sorted(Path("output/frames").glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:4]
            if frames:
                st.markdown("**🖼️ 最近分镜**")
                for fp in frames:
                    st.image(str(fp), use_container_width=True)

# ── Footer ──
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#ccc;font-size:0.8rem">'
    'OpenDrama Studio v3.0 · MIT · '
    '<a href="https://github.com/fgdgu123/OpenDrama" style="color:#6b5ce7">GitHub</a> · '
    '<a href="http://localhost:8502" style="color:#6b5ce7">监控面板</a>'
    '</div>',
    unsafe_allow_html=True
)
