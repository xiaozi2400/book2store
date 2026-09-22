# book2store Docker Image
# Python CLI 工具，支持自动化电子书处理

# 国内加速镜像
FROM docker.m.daocloud.io/library/python:3.12-slim

# 安装系统依赖（精简版）
# apt 使用中科大镜像加速 https://mirrors.ustc.edu.cn
RUN sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    || sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list \
    ; apt-get update \
    ; apt-get install -y --no-install-recommends fonts-noto-cjk calibre \
    ; rm -rf /var/lib/apt/lists/* && apt-get clean

# 安装 uv（通过 pip，比拉取镜像快）
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple \
    && pip install --no-cache-dir uv

# 设置工作目录
WORKDIR /app

# 配置 uv 使用中科大镜像
ENV UV_INDEX_URL=https://pypi.mirrors.ustc.edu.cn/simple
ENV UV_LINK_MODE=copy
ENV UV_HTTP_TIMEOUT=300
ENV UV_HTTP_RETRIES=5

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用 uv，比 pip 快 10-100x）
RUN uv pip install --system --no-cache -r requirements.txt

# 安装 Playwright 和 Chromium
RUN uv pip install --system --no-cache playwright

# 设置 Playwright 浏览器下载镜像（淘宝源）
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright

# 安装 Chromium（带系统依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
        libatspi2.0-0 libcups2 libdrm2 libgbm1 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libxtst6 libpango-1.0-0 \
        libcairo2 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libgtk-3-0 \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# 禁用 Qt WebEngine 沙箱（Docker 以 root 运行需要）
ENV QTWEBENGINE_DISABLE_SANDBOX=1

# 复制应用代码
COPY . .

# 默认命令（CLI 入口）
CMD ["python", "-m", "automation.main", "--help"]