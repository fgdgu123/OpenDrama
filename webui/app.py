"""
OpenDrama Studio Web UI
=======================
Streamlit 界面 — 零代码操作 AI 短剧工厂

启动: streamlit run webui/app.py
"""
import streamlit as st
import sys
import os
from pathlib import Path

# 添加 pipeline 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from generate import OpenDrama, STYLE_PRESETS

st.set_page_config(
    page_title="OpenDrama Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CSS 样式
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        color: #888;
        font-size: 1rem;
        margin-top: -10px;
    }
    .step-card {
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 16px;
    }
    .step-card.done {
        border-color: #4caf50;
        background: #f1f8e9;
    }
    .step-card.active {
        border-color: #667eea;
        background: #f3f0ff;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 标题
# ============================================================
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<p class="main-header">🎬 OpenDrama Studio</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">开源 AI 短剧全链路工厂 — 从剧本到成片，一条命令</p>', unsafe_allow_html=True)
with col2:
    st.markdown("")
    st.markdown("")
    st.markdown("**[⭐ GitHub](https://github.com/OpenDrama/OpenDrama)**  |  **[📖 文档](https://opendrama.dev)**")

st.divider()

# ============================================================
# 侧边栏 — 配置
# ============================================================
with st.sidebar:
    st.header("⚙️ 配置")
    
    # ComfyUI 连接
    comfyui_url = st.text_input(
        "ComfyUI API",
        value=os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188"),
        help="ComfyUI 服务地址"
    )
    
    # 风格
    style = st.selectbox(
        "🎨 风格预设",
        options=list(STYLE_PRESETS.keys()),
        index=0,
        help="选择视觉风格模板"
    )
    
    # 配音
    st.subheader("🎙️ 配音设置")
    tts_engine = st.selectbox("引擎", ["edge-tts", "cosyvoice"], index=0)
    tts_voice = st.selectbox(
        "语音",
        ["zh-CN-YunxiNeural (男声)", "zh-CN-XiaoxiaoNeural (女声)", 
         "zh-CN-YunyangNeural (青年男)", "zh-CN-XiaoyiNeural (青年女)"],
        index=0
    )
    tts_voice = tts_voice.split(" ")[0]
    
    # 输出设置
    st.subheader("📦 输出")
    output_format = st.selectbox("格式", ["mp4", "mov", "webm"], index=0)
    add_subtitles = st.checkbox("添加字幕", value=True)
    add_bgm = st.checkbox("添加 BGM", value=False)
    
    if add_bgm:
        bgm_file = st.file_uploader("上传 BGM", type=["mp3", "wav"])
    else:
        bgm_file = None
    
    # 高级设置
    with st.expander("🔧 高级"):
        width = st.number_input("宽度", 256, 1920, 576, step=64)
        height = st.number_input("高度", 256, 1920, 1024, step=64)
        steps = st.slider("采样步数", 10, 50, 30)
        ip_weight = st.slider("IP-Adapter 权重", 0.0, 1.0, 0.75, 0.05, help="锁脸强度")

# ============================================================
# 主界面
# ============================================================

# 第1步: 剧本输入
st.markdown("### 📝 第1步: 输入剧本")

script_method = st.radio(
    "剧本来源",
    ["📄 上传文件", "✏️ 手动输入", "🤖 AI 生成"],
    horizontal=True,
    label_visibility="collapsed"
)

script_content = ""
script_path = None

if "📄" in script_method:
    uploaded_script = st.file_uploader("上传剧本文件", type=["txt", "md", "json"])
    if uploaded_script:
        script_content = uploaded_script.read().decode("utf-8")
        # 保存临时文件
        temp_script = Path("temp_script.md")
        temp_script.write_text(script_content, encoding="utf-8")
        script_path = str(temp_script.absolute())
        st.success(f"✅ 已加载: {uploaded_script.name}")
        
        with st.expander("📋 预览"):
            st.text(script_content[:1000])

elif "✏️" in script_method:
    script_content = st.text_area(
        "输入剧本（Markdown 格式）",
        height=300,
        placeholder="""## 场景1: 深夜办公室
### 旁白
深夜，林墨独自一人坐在办公室里，电脑屏幕是唯一的光源。
### 画面
dark office at night, single programmer at desk, multiple monitors glowing with code
### 时长
5

## 场景2: 收到邮件
### 旁白
一封神秘的加密邮件突然弹出，没有发件人。
### 画面
computer screen showing encrypted email, dramatic lighting, close-up
### 时长
4
""",
    )
    
    if script_content.strip():
        temp_script = Path("temp_script.md")
        temp_script.write_text(script_content, encoding="utf-8")
        script_path = str(temp_script.absolute())

elif "🤖" in script_method:
    st.info("AI 剧本生成功能开发中... 敬请期待!")
    st.markdown("""
    未来功能:
    - 输入剧情大纲，AI 自动生成完整剧本
    - 支持多集系列
    - 角色自动管理
    - 对话自动标注
    """)

# 第2步: 预览分镜
if script_path and script_content:
    st.markdown("---")
    st.markdown("### 🎬 第2步: 预览与调整")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🔍 解析分镜", type="primary"):
            with st.spinner("解析中..."):
                from script_engine import ScriptEngine
                engine = ScriptEngine(script_path)
                scenes = engine.parse()
                st.session_state["scenes"] = scenes
                
                st.success(f"✅ 解析完成: {len(scenes)} 个分镜")
                
                # 显示分镜列表
                for i, s in enumerate(scenes):
                    col_scene, col_info = st.columns([1, 5])
                    with col_scene:
                        st.markdown(f"### {i+1}")
                    with col_info:
                        st.markdown(f"**{s.get('title', f'分镜 {i+1}')}**")
                        if s.get("narration"):
                            st.text(f"旁白: {s['narration'][:100]}")
                        if s.get("character"):
                            st.caption(f"角色: {s['character']} | 时长: {s.get('duration', 5)}s")
                    st.divider()
    
    with col2:
        if st.button("🧹 清除", type="secondary"):
            st.session_state["scenes"] = []
            st.rerun()

# 第3步: 生成
if st.session_state.get("scenes"):
    st.markdown("---")
    st.markdown("### 🚀 第3步: 生成短剧")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        gen_frames = st.checkbox("生成分镜图", value=True)
        skip_scenes = not gen_frames
    
    with col2:
        gen_audio = st.checkbox("生成配音", value=True)
    
    with col3:
        gen_compose = st.checkbox("合成视频", value=True)
    
    output_name = st.text_input("输出文件名", "my_drama")
    output_path = f"output/{output_name}.{output_format}"
    
    if st.button("🎬 开始生成", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 构建配置
        config = {
            "comfyui_url": comfyui_url,
            "output_dir": "output",
            "style": style,
            "tts_engine": tts_engine,
            "tts_voice": tts_voice,
            "width": width,
            "height": height,
            "steps": steps,
            "ipadapter_weight": ip_weight,
            "subtitle_enabled": add_subtitles,
            "video_enabled": True,
        }
        
        dialogue = OpenDrama(config)
        
        try:
            # 剧本解析
            status_text.text("📝 解析剧本...")
            progress_bar.progress(10)
            
            # 分镜生成
            if gen_frames:
                status_text.text(f"🎨 生成分镜图 (ComfyUI)...")
                progress_bar.progress(20)
            
            # 配音
            if gen_audio:
                status_text.text("🎙️ 合成配音...")
                progress_bar.progress(60)
            
            # 合成
            if gen_compose:
                status_text.text("📦 合成视频...")
                progress_bar.progress(80)
            
            # 执行
            result = dialogue.run(
                script_path,
                output_path,
                skip_scenes=skip_scenes,
            )
            
            progress_bar.progress(100)
            status_text.text("✅ 完成!")
            
            if result:
                st.success(f"🎉 短剧已生成!")
                st.video(output_path)
                
                # 下载按钮
                with open(output_path, "rb") as f:
                    st.download_button(
                        "📥 下载视频",
                        f,
                        f"{output_name}.{output_format}",
                        mime=f"video/{output_format}",
                    )
        
        except Exception as e:
            st.error(f"❌ 生成失败: {e}")
            st.exception(e)

# ============================================================
# 底部
# ============================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #999;">
    <small>
        OpenDrama Studio v1.0 | 
        <a href="https://github.com/OpenDrama/OpenDrama">GitHub</a> | 
        <a href="https://opendrama.dev">文档</a> | 
        MIT License
    </small>
    <br>
    <small>别人在挖金子，我们在卖铲子 ⛏️</small>
</div>
""", unsafe_allow_html=True)
