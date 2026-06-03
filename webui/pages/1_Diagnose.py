"""
OpenDrama 诊断页面
"""
import streamlit as st
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config("诊断", "🔍")
st.title("🔍 系统诊断")

from pipeline.diagnose import diagnose_all

with st.spinner("检测中..."):
    issues, fixes = diagnose_all()

if not issues:
    st.success("✅ 全系统正常")
else:
    st.warning(f"发现 {len(issues)} 个问题")
    for iss, fix in zip(issues, fixes):
        with st.expander(f"⚠️ {iss}", expanded=True):
            st.info(f"修复: `{fix}`")

# Frame stats
out = Path("output")
if out.exists():
    frames = list(out.rglob("frames/*.png"))
    videos = list(out.rglob("*.mp4"))
    st.metric("生成帧数", len(frames))
    st.metric("成品视频", len(videos))

if st.button("← 返回主页"):
    st.switch_page("app.py")
