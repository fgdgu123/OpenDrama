FROM python:3.10-slim

# 系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 项目代码
COPY . .

# Web UI 端口
EXPOSE 8501

# 默认启动 Web UI
CMD ["streamlit", "run", "webui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
