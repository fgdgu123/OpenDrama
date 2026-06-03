"""
OpenDrama 监控仪表盘 — 实时状态面板
自动检测: GPU 显存、ComfyUI 健康、最近生成任务、错误日志
"""
import streamlit as st
import paramiko, json, time, os
from pathlib import Path
from datetime import datetime, timedelta

sys_path = str(Path(__file__).parent.parent)
if sys_path not in __import__('sys').path:
    __import__('sys').path.insert(0, sys_path)

st.set_page_config("OpenDrama Monitor", "📊", layout="wide")
st.markdown("<style>.metric-card{padding:16px;border-radius:12px;border:1px solid #ddd;text-align:center}.metric-card.green{border-color:#4caf50;background:#f1f8e9}.metric-card.red{border-color:#f44336;background:#fce4ec}.metric-value{font-size:2rem;font-weight:700}</style>", unsafe_allow_html=True)

# Config
SSH = {
    "host": "connect.westc.seetacloud.com",
    "port": 38342,
    "user": "root",
    "password": "bBXvSvISTNNB"
}

def ssh_cmd(cmd, timeout=10):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(**SSH, timeout=8)
        i, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "ignore").strip()
        err = e.read().decode("utf-8", "ignore").strip()
        c.close()
        return out, err
    except Exception as e:
        return "", str(e)

def get_gpu_stats():
    out, _ = ssh_cmd("nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu,utilization.gpu,power.draw --format=csv,noheader")
    if out:
        parts = [p.strip() for p in out.split(",")]
        return {
            "name": parts[0],
            "vram_used": int(parts[1].split()[0]),
            "vram_total": int(parts[2].split()[0]),
            "temp": int(parts[3].split()[0]),
            "util": int(parts[4].split()[0]) if parts[4].strip() else 0,
            "power": parts[5] if len(parts) > 5 else "0W"
        }
    return None

def get_comfy_queue():
    out, _ = ssh_cmd("curl -s http://127.0.0.1:8188/queue 2>/dev/null")
    try:
        data = json.loads(out)
        running = len(data.get("queue_running", []))
        pending = len(data.get("queue_pending", []))
        return running, pending
    except:
        return 0, 0

def get_recent_jobs():
    out_dir = Path("output")
    jobs = []
    if out_dir.exists():
        for f in sorted(out_dir.rglob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            jobs.append({
                "name": f.name,
                "size": f.stat().st_size,
                "time": datetime.fromtimestamp(f.stat().st_mtime),
                "path": str(f)
            })
    return jobs

# Header
col1, col2 = st.columns([3, 1])
col1.title("📊 OpenDrama 监控面板")
col2.markdown("")
col2.markdown("")
col2.button("🔄 刷新", use_container_width=True)

# GPU
st.subheader("🖥️ 服务器状态")
gpu = get_gpu_stats()

if gpu:
    cols = st.columns(5)
    vram_pct = gpu["vram_used"] / gpu["vram_total"] * 100
    color_vram = "red" if vram_pct > 80 else "green"
    
    cols[0].markdown(f"<div class='metric-card'><small>GPU</small><div class='metric-value' style='font-size:1.2rem'>{gpu['name']}</div></div>", unsafe_allow_html=True)
    cols[1].markdown(f"<div class='metric-card {color_vram}'><small>显存</small><div class='metric-value'>{gpu['vram_used']/1024:.1f}/{gpu['vram_total']/1024:.0f} GB</div></div>", unsafe_allow_html=True)
    cols[2].markdown(f"<div class='metric-card'><small>温度</small><div class='metric-value'>{gpu['temp']}°C</div></div>", unsafe_allow_html=True)
    cols[3].markdown(f"<div class='metric-card'><small>利用率</small><div class='metric-value'>{gpu['util']}%</div></div>", unsafe_allow_html=True)
    cols[4].markdown(f"<div class='metric-card'><small>功耗</small><div class='metric-value' style='font-size:1.2rem'>{gpu['power']}</div></div>", unsafe_allow_html=True)
else:
    st.error("无法连接 GPU 服务器")

# ComfyUI Queue
st.subheader("⚡ ComfyUI 队列")
running, pending = get_comfy_queue()
col1, col2, col3 = st.columns(3)
col1.metric("进行中", running)
col2.metric("排队中", pending)
col3.metric("总任务", running + pending)

# Recent Jobs
st.subheader("📦 最近生成")
jobs = get_recent_jobs()
if jobs:
    for j in jobs:
        col1, col2, col3, col4 = st.columns([3,1,1,1])
        col1.text(j["name"])
        col2.text(f"{j['size']//1024}KB")
        col3.text(j["time"].strftime("%H:%M:%S"))
        col4.button("📥", key=f"dl_{j['name']}", help=f"下载 {j['name']}")
else:
    st.info("暂无生成记录")

# 最近帧
st.subheader("🖼️ 最近分镜")
frames_dir = Path("output/frames")
if frames_dir.exists():
    imgs = sorted(frames_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:6]
    if imgs:
        cols = st.columns(3)
        for i, img_path in enumerate(imgs):
            cols[i % 3].image(str(img_path), caption=img_path.name[:30], use_container_width=True)

# 自动刷新
time.sleep(2)
st.rerun() if st.session_state.get("auto_refresh") else None
