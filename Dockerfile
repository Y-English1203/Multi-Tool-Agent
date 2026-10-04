FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV HF_ENDPOINT=https://hf-mirror.com
ENV HF_HUB_OFFLINE=1

COPY requirements.txt .

# 关键：先安装 CPU 版 torch，跳过几G的 NVIDIA 包
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# 再安装其他依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]