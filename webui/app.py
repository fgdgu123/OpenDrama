"""
OpenDrama Studio Web UI v2.0
Streamlit — 零代码 AI 短剧工厂
"""
import streamlit as st
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="OpenDrama Studio", page_icon="🎬", layout="wide")
st.markdown("<style>.main-header{font-size:2.2rem;font-weight:800;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}</style>", unsafe_allow_html=True)

st.markdown('<p class="main-header">🎬 OpenDrama Studio v2.0</p>', unsafe_allow_html=True)
st.caption("开源 AI 短剧工厂 — 从剧本到成片，带 IP-Adapter 角色锁脸")

# ═══════ Sidebar ═══════
with st.sidebar:
    st.header("⚙️ 服务器")
    use_ssh = st.checkbox("远程 ComfyUI (SSH)", value=True)
    
    if use_ssh:
        ssh_host = st.text_input("主机", "connect.westc.seetacloud.com")
        ssh_port = st.number_input("端口", 1, 65535, 38342)
        ssh_user = st.text_input("用户", "root")
        ssh_pwd = st.text_input("密码", "bBXvSvISTNNB", type="password")
    
    st.header("🎨 风格")
    style = st.selectbox("视觉风格", ["cinematic","cyberpunk","noir","fantasy","anime","horror","period_drama"])
    
    st.header("👤 锁脸")
    enable_face = st.checkbox("IP-Adapter 锁脸", value=True)
    ip_weight = st.slider("权重", 0.0, 1.0, 0.8, 0.05) if enable_face else 0.0
    
    st.header("📐 画面")
    col1, col2 = st.columns(2)
    with col1: width = st.number_input("宽", 256, 1920, 576, 64)
    with col2: height = st.number_input("高", 256, 1920, 1024, 64)
    steps = st.slider("步数", 10, 50, 25)
    
    st.header("🎙️ 配音")
    voice = st.selectbox("语音", [
        "zh-CN-YunxiNeural (男)", "zh-CN-XiaoxiaoNeural (女)",
        "zh-CN-YunyangNeural (青年男)", "zh-CN-XiaoyiNeural (青年女)"
    ])
    voice = voice.split("(")[0].strip()
    add_sub = st.checkbox("字幕", True)

# ═══════ Main ═══════
tab1, tab2, tab3 = st.tabs(["📝 剧本", "🎬 生成", "📊 历史"])

with tab1:
    st.markdown("### 剧本输入")
    
    script_method = st.radio("来源", ["✏️ 手动输入", "📄 上传文件", "🎯 示例剧本"], horizontal=True, label_visibility="collapsed")
    
    script_path = None
    
    if "✏️" in script_method:
        script = st.text_area("Markdown 格式", height=250, placeholder="""## 场景1: 深夜办公室
### 旁白
深夜，林墨独自坐在办公室里。
### 画面
dark office, programmer at desk, monitors glowing
### 角色
narrator
### 时长
5""")
        if script.strip():
            Path("temp_script.md").write_text(script, encoding="utf-8")
            script_path = "temp_script.md"
    
    elif "📄" in script_method:
        uploaded = st.file_uploader("上传 .md/.txt/.json", type=["md","txt","json"])
        if uploaded:
            content = uploaded.read().decode("utf-8")
            Path("temp_script.md").write_text(content, encoding="utf-8")
            script_path = "temp_script.md"
            st.success(f"已加载: {uploaded.name}")
            with st.expander("预览"): st.code(content[:500])
    
    elif "🎯" in script_method:
        sample = Path(__file__).parent.parent / "templates/scripts/sample_office.md"
        script_path = str(sample)
        st.success("已加载示例剧本")
        st.code(open(sample, encoding="utf-8").read()[:500])
    
    if script_path:
        if st.button("🔍 解析预览", type="secondary"):
            from pipeline.script_engine import ScriptEngine
            scenes = ScriptEngine(script_path).parse()
            st.session_state.scenes = scenes
            st.success(f"{len(scenes)} 个分镜")
            for i, s in enumerate(scenes):
                with st.container():
                    cols = st.columns([1,6])
                    cols[0].markdown(f"### {i+1}")
                    cols[1].markdown(f"**{s.get('title','')}**")
                    if s.get("narration"): cols[1].text(s["narration"][:120])
                    cols[1].caption(f"角色:{s.get('character','?')} | {s.get('duration',5)}s")

with tab2:
    st.markdown("### 🚀 生成短剧")
    
    if not script_path:
        st.warning("请先在「剧本」选项卡输入剧本")
    else:
        out_name = st.text_input("输出文件名", "my_drama")
        
        if st.button("🎬 开始生成", type="primary", use_container_width=True):
            config = {
                "output_dir": "output",
                "style": style,
                "tts_engine": "edge-tts",
                "tts_voice": voice,
                "width": width, "height": height, "steps": steps,
                "ipadapter_weight": ip_weight,
                "ref_face": "output/frames/hero_ref_face.png" if enable_face else None,
                "video_enabled": False,
                "subtitle_enabled": add_sub,
                "ssh_host": ssh_host if use_ssh else None,
                "ssh_port": ssh_port, "ssh_user": ssh_user,
                "ssh_password": ssh_pwd,
            }
            
            from pipeline.generate import OpenDrama
            drama = OpenDrama(config)
            
            progress = st.progress(0)
            status = st.empty()
            
            output_file = f"output/{out_name}.mp4"
            
            try:
                status.text("📝 解析剧本..."); progress.progress(10)
                status.text("🎬 生成分镜..."); progress.progress(30)
                status.text("🎙️ 合成配音..."); progress.progress(60)
                status.text("📦 合成视频..."); progress.progress(85)
                
                result = drama.run(script_path, output_file)
                
                progress.progress(100)
                status.text("✅ 完成!")
                
                if result and os.path.exists(result):
                    st.success("🎉 短剧已生成!")
                    st.video(result)
                    with open(result, "rb") as f:
                        st.download_button("📥 下载", f, f"{out_name}.mp4", mime="video/mp4")
                else:
                    st.warning("生成完成但文件不可用，请查看日志")
                    
            except Exception as e:
                st.error(f"失败: {e}")

with tab3:
    st.markdown("### 📊 输出文件")
    out_dir = Path("output")
    if out_dir.exists():
        files = list(out_dir.rglob("*.mp4"))[-5:] + list(out_dir.rglob("*.png"))[-10:]
        for f in sorted(files, reverse=True):
            col1, col2 = st.columns([4,1])
            col1.text(str(f))
            col2.text(f"{f.stat().st_size//1024}KB")
    else:
        st.info("暂无输出")

st.markdown("---")
st.caption("OpenDrama Studio v2.0 | MIT License | github.com/fgdgu123/OpenDrama")
