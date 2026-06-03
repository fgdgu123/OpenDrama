"""
OpenDrama 监控面板 v3 — 按需刷新，不自动循环
"""
import streamlit as st
import paramiko, json
from pathlib import Path
from datetime import datetime

st.set_page_config("Monitor", "📊", layout="wide")

SSH = {"host":"connect.westc.seetacloud.com","port":38342,"user":"root","password":"bBXvSvISTNNB"}

def ssh(cmd):
    c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(**SSH,timeout=5)
        i,o,_=c.exec_command(cmd,timeout=8)
        out=o.read().decode("utf-8","ignore").strip()
        c.close()
        return out
    except:
        return ""

st.title("📊 实时监控")
if st.button("🔄 刷新", use_container_width=True):
    st.rerun()

# GPU
gpu_raw=ssh("nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu --format=csv,noheader")
if gpu_raw:
    p=[x.strip() for x in gpu_raw.split(",")]
    vram_used,vram_total,temp,util=int(p[0].split()[0]),int(p[1].split()[0]),int(p[2].split()[0]),int(p[3].split()[0])
    c1,c2,c3,c4=st.columns(4)
    c1.metric("显存",f"{vram_used/1024:.1f}/{vram_total/1024:.0f}GB")
    c2.metric("温度",f"{temp}°C")
    c3.metric("利用率",f"{util}%")
    c4.metric("可用",f"{(vram_total-vram_used)/1024:.1f}GB")

# Queue
q=ssh("curl -s http://127.0.0.1:8188/queue 2>/dev/null")
try:
    qd=json.loads(q)
    st.metric("排队","/".join([str(len(qd.get("queue_running",[]))),str(len(qd.get("queue_pending",[])))]))
except:
    st.metric("排队","?")

# ComfyUI status
comfy_status = "🟢 运行中" if ssh("curl -s -o /dev/null -w %{http_code} http://127.0.0.1:8188/system_stats")=="200" else "🔴 离线"
st.caption("ComfyUI: "+comfy_status)

# Output files
st.divider()
st.subheader("📦 输出")
out=Path("output")
files=sorted(out.rglob("*.mp4"),key=lambda x:x.stat().st_mtime,reverse=True)[:10]
if files:
    for f in files:
        c1,c2=st.columns([4,1])
        c1.text(str(f))
        c2.text(f"{f.stat().st_size//1024}KB")
else:
    st.info("无记录")

frames=sorted(Path("output/frames").glob("*.png"),key=lambda x:x.stat().st_mtime,reverse=True)[:6]
if frames:
    cols=st.columns(3)
    for i,fp in enumerate(frames):
        cols[i%3].image(str(fp),use_container_width=True)
