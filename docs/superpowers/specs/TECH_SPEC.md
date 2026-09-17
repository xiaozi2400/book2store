# 电子书自动化处理系统 - 最终技术方案

**版本**: v1.0 (Final)  
**日期**: 2026-04-18  
**状态**: 已确认，待开发  

---

## 一、方案概述

### 1.1 设计原则
- **简单可靠优先**：避免过度设计，选择稳定可靠的实现方案
- **渐进式开发**：先打通全流程，再逐步优化
- **容错性强**：详细错误处理，关键错误暂停等待人工

### 1.2 核心决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 图片处理 | EPUB现有图片 | 简单可靠，无需渲染 |
| 闲管家发布 | 全自动 + 备用清单 | 优先自动，失败时手动 |
| 断点续传 | 仅翻译阶段 | 复用现有缓存机制 |
| 错误处理 | 详细分类处理 | 不同错误不同处理策略 |
| 数据库 | SQLite | 单文件，简单易用 |
| 用户界面 | CLI + Web | 满足不同场景需求 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         系统架构图                                       │
└─────────────────────────────────────────────────────────────────────────┘

  用户界面层
  ┌─────────────────┐  ┌─────────────────┐
  │   CLI (Typer)   │  │ Streamlit Web   │
  │   命令行工具     │  │   管理界面       │
  └────────┬────────┘  └────────┬────────┘
           │                    │
           └──────────┬─────────┘
                      │
                      ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                      工作流编排层 (Workflow)                         │
  │  • 状态管理  • 错误处理  • 进度跟踪  • 断点续传                      │
  └─────────────────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ 核心模块  │  │ 现有系统  │  │ 外部服务  │
  │ (新增)   │  │ (复用)   │  │          │
  ├──────────┤  ├──────────┤  ├──────────┤
  │Directory │  │  EPUB    │  │ DeepSeek │
  │ Scanner  │  │  Parser  │  │   API    │
  ├──────────┤  ├──────────┤  ├──────────┤
  │ Content  │  │ DeepSeek │  │ 闲管家    │
  │Summarizer│  │Translator│  │ (Playwright)
  ├──────────┤  ├──────────┤  └──────────┘
  │  Image   │  │  EPUB    │
  │ Extractor│  │ Generator│
  ├──────────┤  ├──────────┤
  │   AI     │  │  PDF     │
  │Copywriter│  │ Converter│
  ├──────────┤  └──────────┘
  │  Link    │
  │ Importer │
  ├──────────┤
  │  Xianyu  │
  │ Publisher│
  └──────────┘
        │
        ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                      数据存储层                                       │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
  │  │  SQLite  │  │  File    │  │  JSON    │                          │
  │  │  Database│  │  System  │  │  Cache   │                          │
  │  └──────────┘  └──────────┘  └──────────┘                          │
  └─────────────────────────────────────────────────────────────────────┘
```

---

## 三、项目结构

```
bookfile_bat/
├── ebook_translator/              # 【现有】翻译系统
│   ├── translator/
│   │   ├── cache.py
│   │   ├── deepseek_api.py
│   │   ├── epub_generator.py
│   │   ├── epub_parser.py
│   │   └── pdf_converter.py
│   ├── config.py
│   ├── main.py
│   └── requirements.txt
│
├── automation/                    # 【新增】自动化模块
│   ├── __init__.py
│   ├── models.py                  # 数据库模型
│   ├── database.py                # 数据库连接管理
│   ├── config.py                  # 配置管理
│   ├── ai_client.py               # AI客户端封装
│   ├── utils.py                   # 工具函数
│   ├── directory_scanner.py       # 目录扫描器
│   ├── content_summarizer.py      # 内容精简器
│   ├── image_extractor.py         # 图片提取器
│   ├── ai_copywriter.py           # AI文案生成器
│   ├── link_importer.py           # Excel链接导入器
│   └── xianyu_publisher.py        # 闲管家发布器
│
├── workflow.py                    # 工作流编排
├── cli.py                         # CLI入口
├── web_app.py                     # Web界面入口
├── config.yaml                    # 配置文件
├── requirements-automation.txt    # 自动化依赖
└── TECH_SPEC.md                   # 本技术方案文档
```

---

## 四、模块详细设计

### 4.1 目录扫描器 (directory_scanner.py)

**功能**：扫描输入目录，检测新EPUB文件

**输入**：`E:\ebooks\input\`

**输出**：待处理书籍列表

**实现要点**：
- 扫描 `.epub` 文件
- 验证EPUB格式（尝试读取）
- 检查是否已处理（查数据库）
- 提取基础元数据（书名、作者）

**错误处理**：
- 文件损坏 → 记录错误，跳过
- 无法提取元数据 → 使用文件名作为标题

---

### 4.2 内容精简器 (content_summarizer.py)

**功能**：生成书籍核心内容精简版PDF

**输入**：EPUB文件路径

**输出**：精简版PDF

**内容结构**：
1. 全书核心观点（300-500字）
2. 各章节摘要（每章150-200字）
3. 金句摘录（10-15条）
4. 适用人群说明

**实现要点**：
- 复用 `EPUBParser` 提取章节
- 调用DeepSeek API生成摘要
- 使用ReportLab生成PDF

**错误处理**：
- API调用失败 → 重试3次，仍失败则使用简化模板
- PDF生成失败 → 记录错误，跳过此步骤

---

### 4.3 图片提取器 (image_extractor.py)

**功能**：提取EPUB封面 + 从PDF截取目录预览图

**输入**：EPUB文件路径、翻译后的PDF路径

**输出**：封面图片、目录预览图

**实现要点**：
- 从EPUB元数据提取封面
- 如无封面，取第一个图片文件
- 压缩优化封面（最大1200x1600，<500KB）
- 从翻译后的PDF中提取目录页（定位"目录"或"Contents"页面）
- 使用PyMuPDF（fitz）将目录页渲染为图片

**PDF目录截图实现**：
```python
import fitz  # PyMuPDF

def extract_toc_preview(pdf_path: str, output_path: str):
    """从PDF中提取目录页并截图"""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()  # 获取PDF目录结构
    
    # 查找目录页码
    for page_num, (level, title, page) in enumerate(toc):
        if "目录" in title.lower() or "contents" in title.lower():
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x缩放
            pix.save(output_path)
            break
```

**错误处理**：
- 无图片 → 使用默认占位图
- PDF目录页找不到 → 跳过目录截图，仅使用封面
- 图片处理失败 → 记录错误，继续

---

### 4.4 AI文案生成器 (ai_copywriter.py)

**功能**：生成闲鱼文案和小红书笔记

**输入**：书名、作者、摘要

**输出**：
- 闲鱼文案（JSON格式）
- 小红书笔记（Markdown格式）

**实现要点**：
- 调用DeepSeek API
- 使用结构化Prompt
- 解析JSON响应

**错误处理**：
- API失败 → 重试3次，仍失败则使用默认模板
- JSON解析失败 → 使用正则提取关键信息

---

### 4.5 Excel链接导入器 (link_importer.py)

**功能**：读取百度网盘分享链接Excel

**输入**：Excel文件路径

**输出**：匹配的书籍-链接映射

**实现要点**：
- 使用OpenPyXL读取Excel
- 文件名模糊匹配
- 支持手动确认未匹配项

**错误处理**：
- Excel格式错误 → 提示用户检查格式
- 匹配失败 → 标记为待人工处理

---

### 4.6 闲管家发布器 (xianyu_publisher.py)

**功能**：自动发布商品到闲鱼

**输入**：书籍完整信息、网盘链接

**输出**：发布结果

**实现要点**：
- 使用Playwright浏览器自动化
- 扫码登录
- 填写商品信息
- 配置SKU
- 设置发货链接

**错误处理策略**：
| 错误类型 | 处理方式 |
|---------|---------|
| 登录失败 | 暂停，等待人工扫码 |
| 页面元素找不到 | 生成备用清单，转手动发布 |
| SKU配置失败 | 记录错误，继续发布基础商品 |
| 发货链接设置失败 | 发布成功后，人工补充 |

**备用方案**：
自动生成发布清单：
```
【闲鱼发布清单】
标题: xxx
描述: xxx
价格: ¥3.99 / ¥8.99
图片: xxx
SKU1链接: xxx
SKU2链接: xxx
```

---

## 五、工作流编排

### 5.1 处理流程

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  PENDING │───▶│ SCANNING│───▶│ PARSING │───▶│TRANSLATE│
│ (待处理) │    │ (扫描中) │    │ (解析中) │    │ (翻译中) │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                   │
┌─────────┐    ┌─────────┐    ┌─────────┐         │
│COMPLETED│◀───│COPYWRITE│◀───│ EXTRACT │◀────────┘
│(已完成) │    │(文案生成)│    │(提取图片)│
└────┬────┘    └─────────┘    └─────────┘
     │
     │  用户上传网盘
     ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│  LINKED │───▶│PUBLISHING│───▶│PUBLISHED│
│(已关联) │    │ (发布中) │    │ (已发布) │
└─────────┘    └─────────┘    └─────────┘
```

### 5.2 错误处理流程

```
┌─────────┐
│  开始   │
└────┬────┘
     │
     ▼
┌─────────┐    失败    ┌─────────┐
│  执行   │───────────▶│ 错误分类 │
│  任务   │            └────┬────┘
└────┬────┘                 │
     │成功                   │
     ▼                      ▼
┌─────────┐    可重试   ┌─────────┐
│  完成   │◀───────────│ 重试3次 │
└─────────┘            └────┬────┘
                            │ 仍失败
                            ▼
                     ┌─────────┐
           关键错误  │ 暂停等待 │
           一般错误  │ 记录跳过 │
                     └─────────┘
```

---

## 六、数据模型

### 6.1 数据库表结构

```python
# books 表 - 书籍基础信息
{
    "id": "UUID",
    "filename": "string",      # 原始文件名
    "title": "string",         # 书名
    "author": "string",        # 作者
    "language": "string",      # 语言
    "status": "string",        # 处理状态
    "error_message": "string", # 错误信息
    "created_at": "datetime",
    "updated_at": "datetime"
}

# book_outputs 表 - 处理输出
{
    "id": "UUID",
    "book_id": "UUID",         # 关联books
    "bilingual_epub": "path",
    "chinese_epub": "path",
    "bilingual_pdf": "path",
    "chinese_pdf": "path",
    "summary_pdf": "path",     # 精简版
    "cover_image": "path",     # 封面
    "other_images": "json",    # 其他图片列表
    "xianyu_title": "string",
    "xianyu_description": "text",
    "xianyu_tags": "string",
    "xiaohongshu_note": "text",
    "pan_link_sku1": "string", # 纯英文链接
    "pan_link_sku2": "string", # 套装链接
    "pan_code": "string",      # 提取码
    "xianyu_product_id": "string",
    "xianyu_listing_url": "string",
    "publish_status": "string",
    "publish_error": "string"
}

# processing_logs 表 - 处理日志
{
    "id": "integer",
    "book_id": "UUID",
    "stage": "string",         # 处理阶段
    "status": "string",        # 状态
    "message": "string",       # 详细信息
    "created_at": "datetime"
}
```

---

## 七、配置参数

### 7.1 config.yaml

```yaml
# 路径配置
paths:
  input_dir: "E:\\ebooks\\input"
  output_dir: "./output"
  data_dir: "./data"
  log_dir: "./logs"

# SKU配置
sku:
  - name: "纯英文原版"
    price: 3.99
    includes: ["english_pdf"]
  - name: "完整套装"
    price: 8.99
    includes: ["english_pdf", "chinese_pdf", "bilingual_pdf", "summary_pdf"]

# AI配置
ai:
  provider: "deepseek"
  model: "deepseek-chat"
  max_tokens: 4096
  temperature: 0.7
  retry_times: 3
  retry_delay: 5  # 秒

# 图片配置
image:
  max_width: 1200
  max_height: 1600
  quality: 85
  format: "jpg"

# 闲管家配置
xianyu:
  login_method: "qr_code"
  base_url: "https://www.xianyu.com"
  timeout: 30  # 扫码等待时间(秒)
  auto_retry: true

# 错误处理配置
error_handling:
  api_error: "retry"        # API错误：重试
  file_error: "skip"        # 文件错误：跳过
  parse_error: "skip"       # 解析错误：跳过
  publish_error: "manual"   # 发布错误：转手动
```

---

## 八、用户界面

### 8.1 CLI命令

```bash
# 初始化
python cli.py init

# 扫描新书籍
python cli.py scan

# 处理单本书
python cli.py process <book_id>

# 批量处理
python cli.py batch-process

# 导入网盘链接
python cli.py import-links <excel_path>

# 发布到闲鱼
python cli.py publish <book_id>

# 批量发布
python cli.py batch-publish

# 查看状态
python cli.py status

# 查看日志
python cli.py logs

# 启动Web界面
python cli.py web
```

### 8.2 Web界面功能

- **仪表盘**：处理统计、待处理数量、已发布数量
- **书籍列表**：查看所有书籍及状态
- **处理监控**：实时显示处理进度
- **发布管理**：查看发布状态、重新发布
- **配置管理**：修改配置参数

---

## 九、开发计划

### Phase 1: 基础设施 (2-3小时)
- [ ] 创建项目结构
- [ ] 数据库模型
- [ ] 配置系统
- [ ] 工具函数

### Phase 2: 核心模块 (4-5小时)
- [ ] 目录扫描器
- [ ] 内容精简器
- [ ] 图片提取器
- [ ] AI文案生成器
- [ ] Excel导入器
- [ ] 闲管家发布器

### Phase 3: 集成优化 (2-3小时)
- [ ] 工作流编排
- [ ] CLI界面
- [ ] Web界面
- [ ] 集成测试
- [ ] Bug修复

**总计：8-11小时（AI开发模式，2-3天）**

---

## 十、风险与应对

| 风险 | 可能性 | 影响 | 应对策略 |
|------|--------|------|---------|
| DeepSeek API限流 | 中 | 高 | 实现指数退避重试 |
| 闲鱼页面改版 | 中 | 高 | 备用清单方案 |
| EPUB格式不兼容 | 低 | 中 | 格式验证，错误跳过 |
| Playwright安装问题 | 低 | 中 | 提供安装脚本 |
| 网盘链接失效 | 低 | 低 | 定期检查提醒 |

---

## 十一、验收标准

### 功能验收
- [ ] 能正确扫描EPUB文件
- [ ] 能生成双语/中文PDF
- [ ] 能生成精简版PDF
- [ ] 能提取封面图片
- [ ] 能从PDF截取目录预览图
- [ ] 能生成闲鱼文案
- [ ] 能生成小红书笔记
- [ ] 能读取Excel链接
- [ ] 能发布到闲鱼（或生成清单）

### 性能验收
- [ ] 单本书处理时间 < 30分钟
- [ ] 支持批量处理
- [ ] 内存占用 < 4GB

### 可靠性验收
- [ ] API失败能重试
- [ ] 错误能正确记录
- [ ] 支持中断恢复（翻译阶段）

---

## 十二、确认签字

**本技术方案已确认，可以开始开发。**

| 确认项 | 状态 |
|--------|------|
| 图片处理方案 | ✅ 确认 |
| 闲管家发布方案 | ✅ 确认 |
| 断点续传方案 | ✅ 确认 |
| 错误处理方案 | ✅ 确认 |
| 数据库选择 | ✅ 确认 |
| 用户界面方案 | ✅ 确认 |
| 开发计划 | ✅ 确认 |

**下一步行动**：开始Phase 1开发

---

**文档结束**
