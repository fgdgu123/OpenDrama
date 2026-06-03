"""
OpenDrama 实时监控仪表盘 v2.0
自动刷新 + GPU 实时曲线 + 任务队列 + 错误诊断
"""
import streamlit as st
import paramiko, json, time
from pathlib import Path
from datetime import datetime
from collections import deque

st.set_page_config("Monitor", "📊", layout="wide")
st.markdown("<style>.metric-big{font-size:2.4rem;font-weight:800;text-align:center}.metric-label{text-align:center;color:#888;font-size:0.8rem}.live-dot{animation:pulse 2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}</style>", unsafe_allow_html=True)

SSH = {"host":"connect.westc.seetacloud.com","port":38342,"user":"root","password":"bBXvSvISTNNB"}

def ssh(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(**SSH, timeout=5)
        i, o, _ = c.exec_command(cmd, timeout=8)
        out = o.read().decode("utf-8","ignore").strip()
        c.close()
        return out
    except:
        return ""

# Auto-refresh every 5s
if "tick" not in st.session_state:
    st.session_state.tick = 0
    st.session_state.vram_history = deque(maxlen=60)
    st.session_state.temp_history = deque(maxlen=60)

st.session_state.tick += 1

# Header
col1, col2 = st.columns([4,1])
col1.title("📊 实时监控")
col2.metric("刷新次数", st.session_state.tick)

# GPU real-time
gpu_raw = ssh("nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw --format=csv,noheader")
if gpu_raw:
    parts = [p.strip() for p in gpu_raw.split(",")]
    vram_used = int(parts[1].split()[0])
    vram_total = int(parts[2].split()[0])
    temp = int(parts[3].split()[0])
    util = int(parts[4].split()[0]) if parts[4].strip() else 0
    power = parts[5]
    
    st.session_state.vram_history.append(vram_used / 1024)
    st.session_state.temp_history.append(temp)
    
    cols = st.columns(5)
    cols[0].metric("GPU", parts[0].replace("NVIDIA GeForce ",""), "在线")
    cols[1].metric("显存", f"{vram_used/1024:.1f}GB", f"/{vram_total/1024:.0f}GB")
    cols[2].metric("温度", f"{temp}°C", delta_color="inverse" if temp > 75 else "normal")
    cols[3].metric("利用率", f"{util}%")
    cols[4].metric("功耗", power)

# Charts
c1, c2 = st.columns(2)
with c1:
    vram_data = list(st.session_state.vram_history)
    if len(vram_data) > 1:
        st.line_chart({"显存(GB)": vram_data}, height=200)
with c2:
    temp_data = list(st.session_state.temp_history)
    if len(temp_data) > 1:
        st.line_chart({"温度(°C)": temp_data}, height=200)

# ComfyUI
st.divider()
q_out = ssh("curl -s http://127.0.0.1:8188/queue 2>/dev/null")
running = pending = 0
try:
    q = json.loads(q_out)
    running = len(q.get("queue_running", []))
    pending = len(q.get("queue_pending", []))
except:
    pass

c1, c2, c3 = st.columns(3)
c1.metric("ComfyUI", "🟢 运行中" if running+pending > 0 or ssh("curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8188/system_stats")=="200" else "🔴")
c2.metric("进行中", running)
c3.metric("排队", pending)

# Recent output
st.divider()
st.subheader("📦 最新输出")
out = Path("output")
files = sorted(out.rglob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]
if files:
    for f in files:
        c1, c2, c3 = st.columns([3,1,1])
        c1.text(str(f))
        c2.text(f"{f.stat().st_size//1024}KB")
        c3.text(datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M"))
else:
    st.info("暂无生成记录")

# Auto-refresh
time.sleep(4)
st.rerun()
