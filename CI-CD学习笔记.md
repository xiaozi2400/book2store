# CI/CD 学习笔记

## Stage 1：Docker 容器化

### 1.1 核心文件

#### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl fonts-noto-cjk fonts-arphic-uming \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir playwright && playwright install chromium --with-deps

COPY . .

CMD ["python", "-m", "automation.main", "--help"]
```

**要点**：
- `python:3.12-slim` 基础镜像（约 150MB）
- `--no-install-recommends` 减少包体积
- `rm -rf /var/lib/apt/lists/*` 清理 apt 缓存
- `--no-cache-dir` pip 不缓存安装包
- `COPY . .` 复制所有代码

#### .dockerignore

排除不需要打包进镜像的文件：
- `.git`、`.github`、`.pytest_cache`
- `__pycache__`、`.venv`
- `*.md`、`.env`、`.gitignore`
- `Dockerfile` 本身（不需要）

#### requirements.txt

确保包含所有依赖：
- `playwright`（主图生成）
- `python-dotenv`（配置读取）
- `SQLAlchemy`（数据库）
- `PyYAML`（配置解析）
- `reportlab`、`fitz(pymupdf)`（PDF 生成）

### 1.2 镜像构建与运行

```bash
# 构建镜像
docker build -t book2store:latest .

# 查看镜像大小
docker images book2store:latest

# 运行（查看 CLI 帮助）
docker run --rm book2store:latest

# 本地文件映射运行
docker run --rm -v D:/ebooks/input:/app/data/input book2store:latest python -m automation.main auto
```

**当前镜像大小**：约 2.96GB（主要来自 Playwright + Chromium）

### 1.3 Docker Hub 加速配置

国内拉取 Docker Hub 镜像速度慢，配置 DaoCloud 镜像加速：

**配置文件**：`~/.docker/daemon.json`

```json
{
  "registry-mirrors": [
    "https://f5ce6d47.m.daocloud.io"
  ]
}
```

```bash
# 重启 Docker Desktop 使配置生效
# 验证加速是否生效
docker info | grep -i mirror
```

### 1.4 镜像内路径与挂载

**config.yaml 路径**：相对于工作目录 `/app`

```yaml
paths:
  input_dir: "./data/input"   # 容器内: /app/data/input
  output_dir: "./data/output"  # 容器内: /app/data/output
```

**运行命令**：挂载到容器内对应的相对路径

```bash
docker run --rm \
  -e DEEPSEEK_API_KEY=sk-xxxx \
  -v D:/project/bookfile_bat/data/input:/app/data/input \
  -v D:/project/bookfile_bat/data/output:/app/data/output \
  book2store:latest \
  python -m automation.main auto
```

### 1.5 环境变量注入

敏感信息（API Key）通过 `-e` 注入，不写在 config.yaml 中：

```bash
-e DEEPSEEK_API_KEY=sk-xxxx
```

config.yaml 中 `api_key` 留空，生产环境由环境变量覆盖。

### 1.6 系统依赖：Calibre

Dockerfile 中需要安装 Calibre（提供 `ebook-convert` 工具）：

```dockerfile
# 使用国内 apt 镜像
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories && \
    apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl fonts-noto-cjk fonts-arphic-uming \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# Calibre 安装（无国内镜像，下载较慢）
RUN wget -q -O /tmp/calibre-installer.sh https://download.calibre-ebook.com/linux-installer.py && \
    python /tmp/calibre-installer.sh --no-system-packages && \
    rm /tmp/calibre-installer.sh
```

### 1.7 国内镜像加速配置（重点）

当前项目 Dockerfile 使用了**四级加速**，构建速度大幅提升：

#### 镜像加速一览

| 层级 | 资源 | 加速地址 | 配置方式 |
|------|------|----------|----------|
| 1 | Docker 基础镜像 | `docker.m.daocloud.io/library/python:3.12-slim` | FROM 指令 |
| 2 | apt-get 包 | 中科大 USTC (`mirrors.ustc.edu.cn`) | sed 替换 debian 源 |
| 3 | pip 包 | 中科大 USTC (`pypi.mirrors.ustc.edu.cn`) | `pip config set global.index-url` |
| 4 | Playwright 浏览器 | 淘宝 npmmirror (`npmmirror.com/mirrors/playwright`) | `ENV PLAYWRIGHT_DOWNLOAD_HOST` |

#### 当前 Dockerfile 完整配置

```dockerfile
# book2store Docker Image
# Python CLI 工具，支持自动化电子书处理

# 国内加速镜像
FROM docker.m.daocloud.io/library/python:3.12-slim

# 安装系统依赖（Playwright + 中文字体 + Calibre）
# apt 使用中科大镜像加速 https://mirrors.ustc.edu.cn
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        curl \
        fonts-noto-cjk \
        calibre \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 全局配置 pip 使用中科大镜像
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple

# 复制依赖文件
COPY requirements.txt ./

# 安装 Python 依赖（此时自动走上面配置的镜像）
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright 和 Chromium
RUN pip install --no-cache-dir playwright

# 设置 Playwright 浏览器下载镜像（淘宝源）
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright

# 安装 Chromium
RUN playwright install chromium --with-deps

# 禁用 Qt WebEngine 沙箱（Docker 以 root 运行需要）
ENV QTWEBENGINE_DISABLE_SANDBOX=1

# 复制应用代码
COPY . .

# 默认命令（CLI 入口）
CMD ["python", "-m", "automation.main", "--help"]
```

#### 各加速配置详解

**1. Docker 基础镜像加速**
```dockerfile
FROM docker.m.daocloud.io/library/python:3.12-slim
```
直接使用 DaoCloud 托管的 Python 官方镜像，无需配置 daemon.json。

**2. apt-get 镜像加速**
```bash
sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources
```
替换 Debian APT 源为中科大源，支持 Debian 12 (bookworm) 和 Debian 11 (bullseye) 两种配置方式。

**3. pip 镜像加速**
```dockerfile
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple
```
永久配置 pip 使用中科大 PyPI 镜像，安装 Python 包速度提升显著。

**4. Playwright 浏览器下载加速**
```dockerfile
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
```
淘宝 npm 镜像托管的 Playwright 浏览器二进制（约 2GB），加速效果明显。

#### Docker Hub 系统级加速（补充）

如果需要拉取其他官方镜像，可在 `~/.docker/daemon.json` 配置：

```json
{
  "registry-mirrors": [
    "https://f5ce6d47.m.daocloud.io"
  ]
}
```

重启 Docker Desktop 后生效，可用 `docker info | grep -i mirror` 验证。

#### 加速效果对比

| 操作 | 无加速 | 有加速 |
|------|--------|--------|
| 拉取 Python 基础镜像 | 5-10 分钟 | 几秒 |
| apt-get 安装系统包 | 2-5 分钟 | 几秒 |
| pip install (50+ 包) | 3-8 分钟 | 十几秒 |
| Playwright Chromium 下载 | 10-20 分钟 | 1-2 分钟 |
| **总计** | **20-40 分钟** | **2-5 分钟** |

### 1.7 API Key 获取链路与优先级

项目中 `DEEPSEEK_API_KEY` 有两处读取逻辑：

```
ebook_translator/config.py
│
├── 1. 优先读取环境变量 DEEPSEEK_API_KEY  ← 最高优先级
│
└── 2. Fallback 读取 automation.config.ai_config["api_key"]
```

`translation_processor.py` 会将 config.yaml 的 api_key 同步到环境变量：

```python
_ai_key = config.ai_config.get("api_key", "") or config.get("ai.api_key", "")
if _ai_key:
    os.environ.setdefault("DEEPSEEK_API_KEY", _ai_key)
```

**优先级**：环境变量 `DEEPSEEK_API_KEY` > config.yaml `ai.api_key`

**模块加载顺序问题**：`ebook_translator/config.py` 在模块导入时就读取环境变量，而 `translation_processor.py` 的 `os.environ.setdefault` 在导入之后才执行。**生产环境直接用 `-e` 注入环境变量即可绕过此问题。**

```cmd
docker run --rm ^
    -e DEEPSEEK_API_KEY=sk-7bb7d35add914702a912c2cd83903613 ^
    -v D:/project/bookfile_bat/data/input:/app/data/input ^
    -v D:/project/bookfile_bat/data/output:/app/data/output ^
    book2store:latest ^
    python -m automation.main auto --skip-publish --skip-cache
```

```powershell
docker run --rm `
    -e DEEPSEEK_API_KEY=sk-7bb7d35add914702a912c2cd83903613 `
    -v D:/project/bookfile_bat/data:/app/data `
    -v D:/project/bookfile_bat/data:/app/data `
    book2store:latest `
    python -m automation.main auto --skip-publish --skip-cache
```

### 1.8 GitHub Actions CI 流程

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install ruff
        run: python -m pip install --quiet ruff
      - name: Run ruff
        run: ruff check .

  test:
    name: pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: python -m pip install --quiet pytest ruff pytest-cov -r requirements.txt
      - name: Run unit tests
        run: python -m pytest tests/unit -v --tb=short --cov=automation --cov-report=xml --cov-report=html
      - name: Run integration tests
        run: python -m pytest tests/integration -v --tb=short
      - name: Upload coverage XML
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml
          path: coverage.xml
      - name: Upload coverage HTML
        uses: actions/upload-artifact@v4
        with:
          name: coverage-html
          path: htmlcov
```

**流程说明**：
- `lint` job：代码风格检查（ruff）
- `test` job：运行单元测试 + 集成测试
- 生成覆盖率报告并上传为 Artifact


### 1.10 关键命令速查

```bash
# Docker
docker build -t book2store:latest .          # 构建镜像
docker images book2store:latest              # 查看镜像大小
docker run --rm book2store:latest           # 运行并查看帮助
docker run --rm -v /path:/app/data book2store:latest python -m automation.main auto

# Docker Hub 加速
docker info | grep -i mirror                # 验证加速配置

# 本地测试 Python 环境
pip install -r requirements.txt
playwright install chromium
python -m automation.main --help

# GitHub Actions 本地模拟（可选）
act -l                                    # 列出可用 workflow
act                                        # 运行 CI workflow
```

---

## 下一步：Stage 2

- [ ] Multi-stage builds 优化（2.96GB → ~400MB）
- [ ] 分离构建阶段和运行阶段
- [ ] 使用 `playwright install --with-deps` 优化字体安装

## 已完成补充（Stage 1 扩展）

- [x] Calibre 安装（ebook-convert 工具）
- [x] 环境变量注入 API Key（DEEPSEEK_API_KEY）
- [x] 镜像内路径与宿主机挂载的对应关系
