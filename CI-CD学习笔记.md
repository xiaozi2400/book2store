# CI/CD 学习笔记

---

## 第一部分：Docker 基础

---

### 1.1 Dockerfile 核心语法

#### 基础结构

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "automation.main", "--help"]
```

#### 核心指令说明

| 指令 | 说明 |
|------|------|
| `FROM` | 基础镜像，`slim` 版本比完整版小 5-10 倍 |
| `RUN` | 执行命令，每条 RUN 产生一层镜像 |
| `COPY` | 复制文件到镜像 |
| `WORKDIR` | 设置工作目录 |
| `ENV` | 设置环境变量 |
| `CMD` | 容器启动命令 |
| `ENTRYPOINT` | 容器入口点 |
| `EXPOSE` | 声明端口 |
| `ARG` | 构建参数（不进入镜像） |

#### 常见优化写法

```dockerfile
# ❌ 多层 RUN（产生多余镜像层）
RUN apt-get update
RUN apt-get install -y wget
RUN apt-get clean

# ✅ 合并为一条（减少镜像层数）
RUN apt-get update && \
    apt-get install -y wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ❌ pip 缓存占用空间
RUN pip install -r requirements.txt

# ✅ 不缓存安装包
RUN pip install --no-cache-dir -r requirements.txt
```

---

### 1.2 .dockerignore

排除不需要打包进镜像的文件：

```
# .dockerignore
.git
.github
.gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
tests/
docs/
*.md
.env
.env.*
Dockerfile
docker-compose.yml
*.log
```

**注意**：`.dockerignore` 不会排除 `COPY . .` 中显式复制的文件。

---

### 1.3 镜像构建与运行

#### 基础命令

```bash
# 构建镜像
docker build -t book2store:latest .

# 构建并指定 Dockerfile
docker build -t book2store:latest -f Dockerfile.dev .

# 查看镜像大小
docker images book2store:latest

# 运行容器
docker run --rm book2store:latest

# 交互式运行
docker run -it --rm book2store:latest bash

# 后台运行
docker run -d --name book2store book2store:latest
```

#### 运行时挂载和环境变量

```bash
# 挂载数据目录
docker run --rm \
  -v D:/project/bookfile_bat/data:/app/data \
  book2store:latest \
  python -m automation.main auto

# 注入环境变量
docker run --rm \
  -e DEEPSEEK_API_KEY=sk-xxxx \
  -v D:/project/bookfile_bat/data:/app/data \
  book2store:latest \
  python -m automation.main auto

# Windows PowerShell
docker run --rm `
  -e DEEPSEEK_API_KEY=sk-xxxx `
  -v D:/project/bookfile_bat/data:/app/data `
  book2store:latest `
  python -m automation.main auto --skip-publish --skip-cache
```

#### 当前镜像大小

**约 2.96 GB**（主要来自 Playwright + Chromium）

---

### 1.4 国内镜像加速配置

#### 四级加速一览

| 层级 | 资源 | 加速地址 | 配置方式 |
|------|------|----------|----------|
| 1 | Docker 基础镜像 | `docker.m.daocloud.io/library/python:3.12-slim` | FROM 指令 |
| 2 | apt-get 包 | 中科大 USTC (`mirrors.ustc.edu.cn`) | sed 替换 debian 源 |
| 3 | pip 包 | 中科大 USTC (`pypi.mirrors.ustc.edu.cn`) | `pip config set global.index-url` |
| 4 | Playwright 浏览器 | 淘宝 npmmirror (`npmmirror.com/mirrors/playwright`) | `ENV PLAYWRIGHT_DOWNLOAD_HOST` |

#### 加速效果对比

| 操作 | 无加速 | 有加速 |
|------|--------|--------|
| 拉取 Python 基础镜像 | 5-10 分钟 | 几秒 |
| apt-get 安装系统包 | 2-5 分钟 | 几秒 |
| pip install (50+ 包) | 3-8 分钟 | 十几秒 |
| Playwright Chromium 下载 | 10-20 分钟 | 1-2 分钟 |
| **总计** | **20-40 分钟** | **2-5 分钟** |

#### Dockerfile 完整加速配置

```dockerfile
# 国内加速镜像
FROM docker.m.daocloud.io/library/python:3.12-slim

# apt 使用中科大镜像加速
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i 's|http://deb.debian.org|https://mirrors.ustc.edu.cn|g' /etc/apt/sources.list; \
    fi \
    && apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg curl fonts-noto-cjk calibre \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# pip 使用中科大镜像
RUN pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 浏览器下载加速
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
RUN pip install --no-cache-dir playwright && playwright install chromium --with-deps

# 禁用 Qt WebEngine 沙箱（Docker 以 root 运行需要）
ENV QTWEBENGINE_DISABLE_SANDBOX=1

COPY . .
CMD ["python", "-m", "automation.main", "--help"]
```

#### Docker Hub 系统级加速

在 `~/.docker/daemon.json` 配置：

```json
{
  "registry-mirrors": [
    "https://f5ce6d47.m.daocloud.io"
  ]
}
```

```bash
# 重启 Docker Desktop 使配置生效
docker info | grep -i mirror  # 验证
```

---

### 1.5 本地开发调试

#### 调试命令

```bash
# 进入运行中的容器
docker exec -it book2store bash

# 查看容器日志
docker logs -f book2store

# 查看容器内进程
docker top book2store

# 检查容器网络
docker port book2store

# 查看容器 IP
docker inspect book2store | grep IPAddress
```

#### Python 环境调试

```bash
# 在容器内调试
docker run -it --rm \
  -v $(pwd):/app \
  book2store:latest \
  bash

# 进入后可以直接运行 Python
python -c "import automation; print(automation.__file__)"
```

---

## 第二部分：Docker 进阶

---

### 2.1 Multi-stage Builds 原理

#### 问题：单阶段构建的痛点

单阶段构建的最终镜像包含所有构建工具和中间产物：

```dockerfile
FROM python:3.12-slim
# ... 安装 gcc、make、git ...
# ... pip install 所有依赖 ...
# ... playwright install chromium ...
# 镜像体积：2.96 GB
```

**包含的内容**：
- Python 源码 + 编译工具（gcc/make）
- Playwright 浏览器二进制（150MB+）
- Node.js 运行时
- 所有 `pip install` 的中间缓存

#### 解决方案：多阶段构建

```dockerfile
# ============ Stage 1: Builder（构建阶段）============
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc make
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ============ Stage 2: Runtime（运行阶段）============
FROM python:3.12-slim
WORKDIR /app
# 只复制 builder 阶段的产物，不复制构建工具
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local:$PATH
CMD ["python", "-m", "automation.main"]
```

#### 核心原理

| 概念 | 说明 |
|------|------|
| **阶段分离** | 每个 `FROM` 是独立阶段，有自己的文件系统 |
| `AS builder` | 给阶段起名，后续 `COPY --from=builder` 引用 |
| `COPY --from=builder` | 只复制指定阶段的产物，不复制整个镜像 |
| **基础镜像选择** | `slim` 比完整版小 5-10 倍 |

---

### 2.2 优化策略（5种）

#### 策略一：最小化运行时基础镜像

```dockerfile
# ❌ 大镜像
FROM python:3.12              # ~1GB

# ✅ 小镜像
FROM python:3.12-slim-bookworm  # ~150MB
FROM alpine:latest             # ~7MB（需注意兼容性）
FROM gcr.io/distroless/python3  # ~50MB（无 shell）
```

#### 策略二：只复制编译产物

```dockerfile
# ❌ 复制整个项目
COPY . .

# ✅ 只复制产出物
COPY --from=builder /app/dist /dist
COPY --from=builder /root/.local/lib/python3.12/site-packages /site-packages
```

#### 策略三：层缓存优化

```dockerfile
# ❌ 依赖放最后，改动代码导致全部重建
COPY . .
RUN pip install -r requirements.txt

# ✅ 依赖放前面，代码改动只触发最后 COPY
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

#### 策略四：合并 RUN 减少层数

```dockerfile
# ❌ 多层，每层都产生中间文件
RUN apt-get update
RUN apt-get install -y gcc
RUN apt-get install -y make
RUN apt-get install -y git
RUN apt-get clean

# ✅ 合并为一条
RUN apt-get update && \
    apt-get install -y gcc make git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
```

#### 策略五：.dockerignore 排除无关文件

```
# .dockerignore
__pycache__/
*.pyc
.git/
.venv/
tests/
docs/
*.md
```

---

### 2.3 镜像分析（docker history）

#### 查看镜像各层大小

```bash
# 查看完整镜像构建历史
docker history book2store:latest

# 只看大小，隐藏中间层
docker history book2store:latest --no-trunc

# 格式化输出
docker history book2store:latest --format "{{.Size}}\t{{.CreatedBy}}"
```

#### 输出示例

```
IMAGE          CREATED BY                                      SIZE
a1b2c3d4e5f6  CMD ["python","-m","automation.main"]          0B
e7f8g9h0i1j2  COPY . .                                        45MB
k3l4m5n6o7p8  RUN /bin/sh -c pip install --no-cache-dir...   320MB
q9r0s1t2u3v4  COPY requirements.txt .                          200B
w5x6y7z8a9b0  RUN /bin/sh -c pip config set global.index...  1.2MB
...
```

#### 找到最大贡献者

```bash
# 按大小排序，找出最大层
docker history book2store:latest | sort -k1 -h | tail -10
```

#### 镜像体积对比

| 项目类型 | 单阶段 | 多阶段优化后 |
|----------|--------|--------------|
| Python 应用 | 1-2 GB | 150-300 MB |
| Node.js 应用 | 500-800 MB | 100-200 MB |
| Go 应用 | 800 MB+ | 10-50 MB |
| **book2store** | **2.96 GB** | **~400 MB** |

---

### 2.4 实践：book2store 多阶段改造

#### 目标

```
2.96 GB → ~400 MB（缩减 87%）
```

#### 改造思路

**Stage 1 (builder)**：安装所有依赖和工具
- Python 包（pip install）
- Playwright 浏览器
- Calibre (ebook-convert)
- 中文字体

**Stage 2 (runtime)**：只复制运行时必需的文件
- Python site-packages
- Calibre 二进制
- 应用代码

#### 关键挑战

1. **Playwright 浏览器**：Chromium 约 150MB，需要在 builder 安装后在 runtime 复用
2. **Calibre**：体积大（约 200MB），需要完整安装
3. **字体**：fonts-noto-cjk（约 100MB）

---

## 第三部分：容器编排

---

### 3.1 docker-compose 核心概念

docker-compose 是 Docker 官方提供的**多容器编排工具**，通过 YAML 文件定义多个服务。

#### 核心概念

| 概念 | 说明 |
|------|------|
| **Service（服务）** | 一个容器定义 |
| **Volume（数据卷）** | 持久化存储 |
| **Network（网络）** | 容器间通信 |
| **depends_on** | 服务依赖顺序 |

#### 基本结构

```yaml
version: "3.8"

services:
  web:
    image: nginx
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html
    depends_on:
      - db

  db:
    image: mysql:8
    volumes:
      - db_data:/var/lib/mysql

volumes:
  db_data:
```

---

### 3.2 常用命令

```bash
# 启动所有服务（前台）
docker-compose up

# 启动所有服务（后台守护）
docker-compose up -d

# 重新构建镜像并启动
docker-compose up --build

# 停止并删除容器
docker-compose down

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f book2store

# 进入容器
docker-compose exec book2store bash

# 查看镜像
docker-compose images
```

#### docker-compose up 的完整流程

```
docker-compose up
│
├─ 1. 检查镜像是否存在 ── 不存在？→ 触发构建
│                              存在？→ 跳过构建
│
├─ 2. 创建容器（如果不存在）
│
└─ 3. 启动容器
```

---

### 3.3 开发 vs 生产使用场景

#### 开发环境（高频修改）

```bash
# 一条命令搞定构建+运行
docker-compose up --build

# 如果只改了小代码，不用 --build（直接复用旧镜像）
docker-compose up
```

#### 开发模式配置（代码热更新）

```yaml
services:
  book2store:
    build: .
    volumes:
      # 代码修改无需重建镜像
      - ./automation:/app/automation
      - ./ebook_translator:/app/ebook_translator
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
```

#### 生产环境（发布到仓库）

```bash
# 1. 构建镜像（打版本号 tag）
docker build -t book2store:1.0.0 .

# 2. 打 latest tag
docker tag book2store:1.0.0 book2store:latest

# 3. 推送到仓库
docker push book2store:1.0.0
docker push book2store:latest
```

| 场景 | 命令 | 原因 |
|------|------|------|
| **本地开发** | `docker-compose up --build` | 快速迭代，一条命令搞定 |
| **发布镜像** | `docker build -t book2store:1.0.0 .` | 需要版本控制，可追溯 |
| **推送仓库** | `docker push` | 让服务器能拉取 |

---

### 3.4 多容器扩展

#### book2store docker-compose 配置

```yaml
# docker-compose.yml
version: "3.8"

services:
  book2store:
    build:
      context: .
      dockerfile: Dockerfile
    image: book2store:latest
    container_name: book2store
    volumes:
      - ./data:/app/data
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    working_dir: /app
    command: python -m automation.main auto --skip-publish --skip-cache
    stdin_open: true
    tty: true
```

#### 添加 Redis 缓存

```yaml
services:
  book2store:
    build: .
    depends_on:
      - redis
    command: python -m automation.main auto

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

#### 环境变量文件 .env

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-7bb7d35add914702a912c2cd83903613
```

docker-compose 会自动读取 `.env` 文件。

---

## 第四部分：CI 持续集成

---

### 4.1 CI 核心概念

**CI = Continuous Integration（持续集成）**

```
代码提交 → 自动构建 → 自动测试 → 自动发布
    ↓           ↓           ↓           ↓
  开发者      GitHub      GitHub      ghcr.io
  推送代码    Actions     Actions     / Docker Hub
```

**传统方式（手动）**：
```bash
docker build -t book2store:1.0.0 .
docker push book2store:1.0.0
```

**CI 方式（自动）**：
```bash
git commit -m "feat: new feature"
git push
# → GitHub Actions 自动构建 → 自动推送
```

---

### 4.2 GitHub Actions 术语

| 术语 | 说明 |
|------|------|
| **Workflow（工作流）** | 整个自动化流程（.yml 文件） |
| **Job（任务）** | 一个 workflow 包含多个 job |
| **Step（步骤）** | 一个 job 包含多个 step |
| **Action（动作）** | 可复用的 step（社区或官方） |
| **Runner** | 执行 job 的服务器（GitHub 提供 ubuntu-latest） |

```
Workflow
  └─ Job: build
       ├─ Step 1: Checkout 代码
       ├─ Step 2: 设置 Python
       ├─ Step 3: 构建镜像
       └─ Step 4: 推送镜像
```

---

### 4.3 Workflow 文件结构

#### 完整示例

```yaml
# .github/workflows/docker.yml
name: Docker Build & Push

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
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: python -m pip install --quiet pytest ruff pytest-cov -r requirements.txt
      - name: Run unit tests
        run: python -m pytest tests/unit -v --tb=short --cov=automation --cov-report=xml --cov-report=html
      - name: Upload coverage XML
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml
          path: coverage.xml

  build:
    name: docker build & push
    runs-on: ubuntu-latest
    needs: [lint, test]
    if: github.event_name == 'push'
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to ghcr.io
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}/book2store
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}
      - name: Build and Push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

#### 关键字段

| 字段 | 说明 |
|------|------|
| `name` | Workflow 名称（显示在 GitHub Actions 页面） |
| `on` | 触发条件 |
| `jobs.<job_name>.runs-on` | Runner 系统 |
| `jobs.<job_name>.needs` | 依赖的 Job |
| `jobs.<job_name>.if` | 条件执行 |
| `steps.uses` | 使用 Action |
| `steps.run` | 执行命令 |
| `steps.with` | Action 参数 |

---

### 4.4 触发条件和 Job 依赖

#### 触发条件（on）

```yaml
on:
  # 仅在 main 分支 push 时触发
  push:
    branches: [main]

  # 仅在 PR 合到 main 时触发
  pull_request:
    branches: [main]

  # 手动触发（在 GitHub 网页点击按钮）
  workflow_dispatch:

  # 定时触发（每天凌晨）
  schedule:
    - cron: '0 2 * * *'
```

#### 触发事件表

| 事件 | lint | test | build |
|------|------|------|-------|
| push 到 main | ✅ | ✅ | ✅ |
| PR 到 main | ✅ | ✅ | ❌ |
| workflow_dispatch | ✅ | ✅ | ✅ |
| schedule | ✅ | ✅ | ✅ |

#### Job 依赖链

```yaml
build:
  needs: [lint, test]  # 等待 lint 和 test 完成
```

```
lint ──→ build
test ──┘
```

#### 条件执行

```yaml
# 仅在 push 时构建，PR 时跳过构建
build:
  if: github.event_name == 'push'
```

---

### 4.5 Secrets 和环境变量

#### 内置 Secrets

| Secret | 说明 |
|--------|------|
| `GITHUB_TOKEN` | 自动注入，无需手动配置 |
| `secrets.GITHUB_TOKEN` | 用于 Actions 内部认证 |

#### 自定义 Secrets

1. GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **"New repository secret"**
3. 填写 **Name** 和 **Secret**

```yaml
# 使用自定义 Secret
- name: Login to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}
```

#### 环境变量设置

```yaml
- name: Set up environment
  run: echo "BUILD_VERSION=1.0.0" >> $GITHUB_ENV

- name: Use environment variable
  run: echo $BUILD_VERSION
```

#### GITHUB_TOKEN 权限

```yaml
permissions:
  contents: read
  packages: write
```

---

### 4.6 构建缓存（BuildKit）

#### 什么是 BuildKit？

BuildKit 是 Docker 的新一代构建后端，比传统构建快 2-10 倍。

#### GitHub Actions 缓存配置

```yaml
- name: Build and Push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ghcr.io/${{ github.repository }}/book2store:latest
    cache-from: type=gha        # 读取缓存
    cache-to: type=gha,mode=max # 写入缓存
```

#### 缓存类型

| 类型 | 说明 |
|------|------|
| `type=gha` | GitHub Actions 缓存（免费，跨 branch 共享） |
| `type=local` | 本地缓存 |
| `type=registry` | 镜像内缓存（推送到仓库） |

#### 缓存原理

```
构建时：
  Layer 1 (Python)   ──→ [缓存]
  Layer 2 (pip)      ──→ [缓存]
  Layer 3 (COPY)     ──→ [缓存]

代码改动后：
  Layer 1 (Python)   ──→ [命中缓存]
  Layer 2 (pip)      ──→ [命中缓存]
  Layer 3 (COPY)     ──→ [重新构建]
  Layer 4 (RUN)      ──→ [重新构建]
```

---

### 4.7 多架构构建（Buildx）

#### 为什么要多架构？

不同服务器（Intel/AMD、ARM、M1 Mac）需要不同架构的镜像。

#### 配置

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and Push
  uses: docker/build-push-action@v5
  with:
    context: .
    platforms: linux/amd64,linux/arm64  # 多架构
    push: true
    tags: |
      ghcr.io/${{ github.repository }}/book2store:latest
      ghcr.io/${{ github.repository }}/book2store:${{ github.sha }}
```

#### 镜像标签

```
ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
ghcr.io/xiaozi2400/bookfile_bat/book2store:latest-linux-amd64
ghcr.io/xiaozi2400/bookfile_bat/book2store:latest-linux-arm64
```

---

### 4.8 Matrix 构建

#### 什么是 Matrix？

用一组参数并行运行多个 Job。

#### 示例：多 Python 版本测试

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/unit -v --tb=short
```

#### 多平台 + 多 Python 版本

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
    os: [ubuntu-latest, windows-latest]
    exclude:
      - python-version: "3.12"
        os: windows-latest  # 排除不兼容的组合
```

---

### 4.9 Artifact 管理

#### 上传 Artifact

```yaml
- name: Upload coverage XML
  uses: actions/upload-artifact@v4
  with:
    name: coverage-xml
    path: coverage.xml
    retention-days: 30  # 保留 30 天
```

#### 下载 Artifact

```yaml
- name: Download coverage
  uses: actions/download-artifact@v4
  with:
    name: coverage-xml
    path: ./coverage
```

#### 多 Artifact

```yaml
- name: Upload all coverage reports
  uses: actions/upload-artifact@v4
  with:
    name: coverage-reports
    path: |
      coverage.xml
      htmlcov/
      coverage.json
```

#### 下载并解压

```yaml
- name: Download and extract artifacts
  uses: actions/download-artifact@v4
  with:
    path: ./artifacts
    pattern: coverage-*
    merge-multiple: true
```

---

### 4.10 workflow_call 复用

#### 问题：ci.yml 和 docker.yml 内容重复

```yaml
# ci.yml 有 lint + test
# docker.yml 有 lint + test + build
# lint 和 test 重复
```

#### 解决方案：提取可复用 Workflow

```yaml
# .github/workflows/_lint-and-test.yml
name: Lint and Test

on:
  workflow_call:
    inputs:
      python-version:
        required: false
        default: "3.12"
        type: string

jobs:
  lint:
    name: ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ inputs.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - name: Install ruff
        run: pip install ruff
      - name: Run ruff
        run: ruff check .

  test:
    name: pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ inputs.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
      - name: Install dependencies
        run: pip install pytest ruff pytest-cov -r requirements.txt
      - name: Run tests
        run: pytest tests/unit -v --tb=short
```

#### 调用可复用 Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    uses: ./.github/workflows/_lint-and-test.yml
```

```yaml
# .github/workflows/docker.yml
name: Docker Build & Push

on:
  push:
    branches: [main]

jobs:
  lint-and-test:
    uses: ./.github/workflows/_lint-and-test.yml

  build:
    runs-on: ubuntu-latest
    needs: [lint-and-test]
    steps:
      - name: Build and Push
        run: docker build -t ghcr.io/${{ github.repository }}/book2store:latest .
```

---

### 4.11 GitHub Actions 完整流程图

```
┌─────────────────────────────────────────────────────────┐
│                     GitHub Repository                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  git push                                                │
│     │                                                    │
│     ▼                                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │              GitHub Actions Runner               │    │
│  ├─────────────────────────────────────────────────┤    │
│  │                                                  │    │
│  │  Job 1: lint    ──→ 通过？                      │    │
│  │    └─ ruff check                                │    │
│  │                        │                         │    │
│  │  Job 2: test    ──→ 通过？ ──┐                 │    │
│  │    └─ pytest                 │                  │    │
│  │                             ▼                   │    │
│  │  Job 3: build  ──→ Docker Buildx ──→ Push     │    │
│  │    └─ build-push-action    │                   │    │
│  │                             ▼                   │    │
│  │                    ┌──────────────┐            │    │
│  │                    │   ghcr.io    │            │    │
│  │                    │  /book2store │            │    │
│  │                    │  :latest     │            │    │
│  │                    │  :sha-xxx    │            │    │
│  │                    └──────────────┘            │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

### 4.12 镜像仓库选择

| 仓库 | 说明 |
|------|------|
| **Docker Hub** | 公共仓库，免费额度有限 |
| **GitHub Container Registry (ghcr.io)** | GitHub 官方，支持私有包 |
| **阿里云容器镜像服务** | 国内访问快 |
| **腾讯云容器镜像服务** | 国内访问快 |

#### ghcr.io 免费额度

| 账户类型 | 存储空间 | 带宽 |
|----------|----------|------|
| GitHub Free | 500 MB | 1 GB/月 |
| GitHub Pro | 2 GB | 10 GB/月 |

**注意**：当前镜像 2.96GB，**必须先做 Multi-stage Build 优化到 ~400MB** 才能使用 ghcr.io 免费额度。

#### 镜像地址格式

```
ghcr.io/用户名/仓库名/镜像名:tag
ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
ghcr.io/xiaozi2400/bookfile_bat/book2store:main-abc1234
```

---

## 第五部分：CD 持续部署

---

### 5.1 SSH 部署

#### 手动部署流程

```bash
# 1. 登录服务器
ssh root@server

# 2. 拉取最新镜像
docker pull ghcr.io/xiaozi2400/bookfile_bat/book2store:latest

# 3. 停止旧容器
docker stop book2store || true

# 4. 启动新容器
docker run -d --name book2store \
  -e DEEPSEEK_API_KEY=sk-xxxx \
  -v /opt/book2store/data:/app/data \
  ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
```

#### GitHub Actions 自动 SSH 部署

```yaml
- name: Deploy to Server
  uses: appleboy/ssh-action@v0.1.10
  with:
    host: ${{ secrets.SERVER_HOST }}
    username: root
    key: ${{ secrets.SERVER_SSH_KEY }}
    script: |
      docker pull ghcr.io/${{ github.repository }}/book2store:latest
      docker stop book2store || true
      docker run -d --name book2store \
        -e DEEPSEEK_API_KEY=${{ secrets.DEPLOY_API_KEY }} \
        -v /opt/book2store/data:/app/data \
        ghcr.io/${{ github.repository }}/book2store:latest
```

#### 配置 Secrets

| Secret | 说明 |
|--------|------|
| `SERVER_HOST` | 服务器 IP 或域名 |
| `SERVER_SSH_KEY` | SSH 私钥 |
| `DEPLOY_API_KEY` | 部署用的 API Key |

---

### 5.2 滚动更新

#### 什么是滚动更新？

零停机部署，新容器启动后再停止旧容器。

#### Docker Compose 滚动更新

```yaml
# docker-compose.yml
services:
  book2store:
    image: ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first  # 先启动新容器，再停止旧的
```

#### 手动滚动更新

```bash
# 1. 拉取新镜像
docker pull ghcr.io/xiaozi2400/bookfile_bat/book2store:latest

# 2. 创建新容器（不删除旧容器）
docker create --name book2store-new \
  -e DEEPSEEK_API_KEY=sk-xxxx \
  ghcr.io/xiaozi2400/bookfile_bat/book2store:latest

# 3. 启动新容器
docker start book2store-new

# 4. 验证新容器正常
curl http://localhost:8080/health

# 5. 停止并删除旧容器
docker stop book2store-old && docker rm book2store-old

# 6. 重命名新容器
docker rename book2store-new book2store
```

---

### 5.3 回滚机制

#### 手动回滚

```bash
# 1. 查看镜像历史
docker images book2store

# 2. 拉取旧版本镜像
docker pull ghcr.io/xiaozi2400/bookfile_bat/book2store:1.0.0

# 3. 停止当前容器
docker stop book2store

# 4. 用旧镜像启动
docker run -d --name book2store \
  ghcr.io/xiaozi2400/bookfile_bat/book2store:1.0.0
```

#### GitHub Actions 回滚

```yaml
- name: Rollback
  if: failure()
  run: |
    docker pull ghcr.io/${{ github.repository }}/book2store:${{ github.sha }}-previous
    docker stop book2store || true
    docker run -d --name book2store \
      ghcr.io/${{ github.repository }}/book2store:${{ github.sha }}-previous
```

#### 健康检查回滚

```bash
# 检查容器健康状态
docker inspect book2store | grep -A 10 "Health"

# 如果不健康，自动回滚
if [ "$(docker inspect --format='{{.State.Health.Status}}' book2store)" != "healthy" ]; then
  docker stop book2store
  docker run -d --name book2store book2store:previous
fi
```

---

## 第六部分：测试集成

---

### 6.1 测试报告集成

#### 为什么需要测试报告？

| 方式 | 特点 |
|------|------|
| 本地测试 | 控制台输出，看完就忘 |
| CI 测试 + 报告 | HTML 报告，可存档、可分享、可追踪 |

#### pytest-html

```bash
# 安装
pip install pytest-html

# 运行测试并生成报告
pytest tests/unit -v --html=report.html --self-contained-html
```

#### CI 配置

```yaml
- name: Run tests
  run: |
    pytest tests/unit -v \
      --html=report.html \
      --self-contained-html \
      --tb=short

- name: Upload test report
  uses: actions/upload-artifact@v4
  if: always()  # 无论成功失败都上传报告
  with:
    name: test-report-${{ github.run_number }}
    path: report.html
    retention-days: 30
```

---

### 6.2 Allure 报告

#### Allure vs pytest-html

| 特性 | pytest-html | Allure |
|------|-------------|--------|
| 图表 | 简单 | 丰富（趋势图、饼图）|
| 历史对比 | ❌ | ✅ |
| 失败截图 | 需手动 | ✅ 自动 |
| 集成难度 | 简单 | 中等 |

#### CI 配置

```yaml
- name: Install Allure
  run: npm install -g allure-commandline

- name: Run tests with Allure
  run: |
    pytest tests/ -v \
      --alluredir=allure-results

- name: Generate Allure report
  run: allure generate allure-results -o allure-report --clean

- name: Upload Allure report
  uses: actions/upload-artifact@v4
  with:
    name: allure-report
    path: allure-report

- name: Deploy to GitHub Pages
  uses: peaceiris/actions-gh-pages@v3
  if: github.ref == 'refs/heads/main'
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./allure-report
```

---

### 6.3 质量门禁（Quality Gates）

#### 什么是质量门禁？

```
代码合并前，必须满足的条件：
├── 测试通过率 100%
├── 覆盖率 >= 80%
├── 没有新的高危漏洞
└── 代码风格检查通过
```

#### 覆盖率门禁

```yaml
- name: Check coverage threshold
  run: |
    coverage report --fail-under=80
```

#### 完整质量门禁 Job

```yaml
jobs:
  quality-gate:
    runs-on: ubuntu-latest
    needs: [lint, test, build]
    if: github.event_name == 'push'
    steps:
      - name: Check all gates
        run: |
          echo "=== Quality Gates ==="
          echo "✓ Lint: PASSED"
          echo "✓ Test: PASSED"
          echo "✓ Build: PASSED"
          echo "✓ Coverage: >= 80%"
```

---

### 6.4 Docker 内运行测试

#### 在运行中的容器内测试

```bash
# 启动测试容器
docker run -d --name test-runner book2store:latest

# 进入容器
docker exec -it test-runner bash

# 运行测试
pytest tests/unit -v --tb=short

# 复制报告出来
docker cp test-runner:/app/report.html ./

# 清理
docker stop test-runner && docker rm test-runner
```

#### 直接用容器运行测试

```bash
# 不进入容器，直接运行测试
docker run --rm \
  -v $(pwd):/app \
  book2store:latest \
  pytest tests/unit -v --tb=short --cov=automation

# 挂载报告目录
docker run --rm \
  -v $(pwd)/reports:/app/reports \
  -v $(pwd):/app \
  book2store:latest \
  pytest tests/unit -v --html=/app/reports/report.html
```

#### docker-compose 测试环境

```yaml
# docker-compose.test.yml
version: "3.8"

services:
  test:
    build: .
    volumes:
      - ./tests:/app/tests
      - ./reports:/app/reports
    command: pytest tests/ -v --html=/app/reports/report.html
```

```bash
# 运行测试
docker-compose -f docker-compose.test.yml up

# 查看报告
open reports/report.html
```

---

### 6.5 E2E 测试在 CI

#### Playwright 在 CI 中运行

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: "18"

      - name: Install dependencies
        run: npm install

      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium

      - name: Run E2E tests
        run: npx playwright test

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

#### Playwright 配置（playwright.config.ts）

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
```

---

### 6.6 测试环境隔离

#### 环境分层

```
┌─────────────────────────────────────────┐
│            开发环境 (Local)               │
│   开发者自己电脑，代码改动即时生效          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│            测试环境 (CI/Staging)          │
│   每次 PR 触发，与生产环境尽可能一致        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│            生产环境 (Production)           │
│   真实数据，面向用户                       │
└─────────────────────────────────────────┘
```

#### 测试环境特点

| 特性 | 测试环境 | 生产环境 |
|------|----------|----------|
| 数据 | 模拟数据 | 真实数据 |
| API Key | 测试 Key | 生产 Key |
| 外部服务 | Mock 或沙箱 | 真实服务 |
| 日志级别 | DEBUG | INFO/WARNING |

#### CI 环境变量配置

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Set up test environment
        env:
          DEEPSEEK_API_KEY: ${{ secrets.TEST_DEEPSEEK_API_KEY }}
          TESTING_MODE: "true"
          LOG_LEVEL: "DEBUG"
        run: |
          echo "TESTING_MODE=$TESTING_MODE"
          pytest tests/ -v
```

---

### 6.7 镜像安全扫描（DevSecOps）

#### Trivy 漏洞扫描

```yaml
jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build image
        run: docker build -t book2store:test .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: book2store:test
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Fail on critical vulnerabilities
        if: failure()
        run: |
          echo "Critical vulnerabilities found!"
          exit 1
```

#### 本地扫描

```bash
# 安装 Trivy
brew install trivy

# 扫描镜像
trivy image book2store:latest

# 扫描文件系统
trivy fs --severity HIGH,CRITICAL .
```

---

### 6.8 测试数据准备

#### Fixture 数据

```python
# tests/fixtures/sample_book.py
import pytest

@pytest.fixture
def sample_book():
    return {
        "id": "test-book-001",
        "title": "小王子",
        "author": "安托万·德·圣-埃克苏佩里",
        "filename": "the-little-prince.epub"
    }
```

#### 测试数据库服务

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@postgres:5432/test_db
        run: pytest tests/ -v
```

---

### 6.9 完整测试集成 Workflow 示例

```yaml
# .github/workflows/test-integration.yml
name: Test Integration

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
        run: pip install ruff
      - name: Run ruff
        run: ruff check .

  unit-test:
    name: pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install pytest pytest-html pytest-cov ruff -r requirements.txt
      - name: Run unit tests
        run: |
          pytest tests/unit -v --tb=short \
            --cov=automation \
            --cov-report=xml \
            --cov-report=html \
            --html=unit-report.html \
            --self-contained-html
      - name: Check coverage
        run: coverage report --fail-under=80
      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov
      - name: Upload test report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: unit-test-report
          path: unit-report.html

  security-scan:
    name: trivy scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t book2store:test .
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: book2store:test
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
      - name: Upload scan results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

---

## 附录

---

### 常用命令速查

```bash
# Docker
docker build -t book2store:latest .           # 构建镜像
docker images book2store                      # 查看镜像大小
docker history book2store:latest              # 分析镜像层
docker run --rm book2store:latest            # 运行容器
docker logs -f book2store                    # 查看日志

# Docker Compose
docker-compose up --build                     # 构建并启动
docker-compose down                           # 停止并删除
docker-compose logs -f                        # 查看日志

# GitHub Actions 本地模拟
act -l                                        # 列出可用 workflow
act                                           # 运行 CI workflow

# 镜像推送
docker tag book2store:latest ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
docker push ghcr.io/xiaozi2400/bookfile_bat/book2store:latest
```

---

### 项目文件清单

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 镜像构建定义 |
| `.dockerignore` | 排除文件 |
| `docker-compose.yml` | 容器编排配置 |
| `.env.example` | 环境变量模板 |
| `.github/workflows/ci.yml` | CI 工作流（lint + test）|
| `.github/workflows/docker.yml` | Docker 构建推送 |
