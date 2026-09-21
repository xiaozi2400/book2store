# book2store Docker Image
# Python CLI 工具，支持自动化电子书处理

FROM python:3.12-slim

# 安装系统依赖（Playwright + 中文字体）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    fonts-noto-cjk \
    fonts-arphic-uming \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 和 Chromium
RUN pip install --no-cache-dir playwright && \
    playwright install chromium --with-deps

# 复制应用代码
COPY . .

# 默认命令（CLI 入口）
CMD ["python", "-m", "automation.main", "--help"]
