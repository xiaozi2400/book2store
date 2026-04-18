# 电子书自动化处理与闲鱼发布系统 - 产品需求文档 (PRD)

**版本**: v1.0  
**日期**: 2026-04-18  
**作者**: AI Assistant  

---

## 1. 产品概述

### 1.1 产品背景
基于现有电子书翻译系统，扩展完整的自动化处理流程，实现从原始 EPUB 到闲鱼商品发布的端到端自动化。

### 1.2 产品目标
- 自动化处理英文 EPUB 电子书，生成多版本 PDF 和营销素材
- 减少人工操作，提高电子书商品上架效率
- 标准化商品发布流程，确保一致性

### 1.3 目标用户
个人电子书卖家，主要在闲鱼平台销售英文电子书的中文翻译版本。

---

## 2. 业务流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    电子书处理与闲鱼发布自动化系统                         │
└─────────────────────────────────────────────────────────────────────────┘

  用户手动操作                      系统自动化处理
  ┌──────────────┐                ┌──────────────┐
  │ 1.下载电子书  │───────────────▶│ 2.扫描目录   │
  │ 放入指定目录  │                │ 检测新文件   │
  └──────────────┘                └──────┬───────┘
                                         │
                                         ▼
                                ┌──────────────┐
                                │ 3.EPUB处理   │
                                │ • 格式验证   │
                                │ • 翻译双语PDF│
                                │ • 中文PDF   │
                                └──────┬───────┘
                                       │
                                       ▼
                                ┌──────────────┐
                                │ 4.内容精简   │
                                │ • AI摘要    │
                                │ • 核心PDF   │
                                └──────┬───────┘
                                       │
                                       ▼
                                ┌──────────────┐
                                │ 5.图片提取   │
                                │ • 封面图    │
                                │ • 目录图    │
                                └──────┬───────┘
                                       │
                                       ▼
                                ┌──────────────┐
                                │ 6.AI文案生成 │
                                │ • 闲鱼标题  │
                                │ • 商品描述  │
                                │ • 种草笔记  │
                                └──────┬───────┘
                                       │
  用户手动操作                         │
  ┌──────────────┐                     │
  │ 7.上传网盘   │─────────────────────┤
  │ 获取分享链接  │                     │
  │ 提供Excel   │                     ▼
  └──────────────┘            ┌──────────────┐
                              │ 8.读取Excel  │
                              │ 匹配分享链接 │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ 9.闲管家发布 │
                              │ • 创建商品  │
                              │ • 配置SKU   │
                              │ • 发货链接  │
                              └──────────────┘
```

---

## 3. 功能模块

### 3.1 目录扫描器 (DirectoryScanner)

#### 功能描述
扫描指定输入目录，检测新的 EPUB 文件，验证文件完整性。

#### 输入
- 输入目录路径: `E:\ebooks\input\`

#### 输出
- 待处理书籍列表（包含文件名、文件大小、检测时间）

#### 处理逻辑
1. 扫描目录中的所有 `.epub` 文件
2. 验证 EPUB 文件格式完整性
3. 检测文件语言（确认是纯英文）
4. 检查是否已处理（避免重复处理）
5. 提取基础元数据（书名、作者，如有）

#### 验收标准
- [ ] 能正确识别所有 EPUB 文件
- [ ] 能检测文件是否已处理
- [ ] 能验证 EPUB 格式有效性
- [ ] 能提取基础元数据

---

### 3.2 翻译处理器 (TranslationProcessor)

#### 功能描述
基于现有翻译系统，将英文 EPUB 翻译为中文，生成双语和纯中文版本。

#### 输入
- 原始 EPUB 文件路径

#### 输出
- 中英双语 EPUB
- 纯中文 EPUB
- 中英双语 PDF
- 纯中文 PDF

#### 处理逻辑
1. 调用现有 EPUBParser 解析文件
2. 调用 DeepSeekTranslator 进行翻译
3. 生成双语 EPUB（段落对照）
4. 生成纯中文 EPUB
5. 调用 PDFConverter 转换为 PDF

#### 验收标准
- [ ] 翻译质量符合要求
- [ ] PDF 排版正确
- [ ] 保留原始排版结构
- [ ] 支持中断恢复

---

### 3.3 核心内容精简器 (ContentSummarizer) ⭐ 新增

#### 功能描述
使用 AI 生成书籍核心内容精简版 PDF，包含全书摘要、章节摘要和金句摘录。

#### 输入
- 原始 EPUB 文件路径

#### 输出
- 精简版 PDF 文件（原书 10-15% 篇幅）

#### 内容结构
1. **全书核心观点**（500字左右）
2. **各章节摘要**（每章 200字左右）
3. **金句摘录**（10-15 条）
4. **思维导图大纲**（层级结构）

#### 处理逻辑
1. 提取 EPUB 章节结构
2. 逐章调用 AI 生成摘要
3. 提取金句（基于 AI 分析）
4. 整合生成精简版 PDF

#### AI Prompt 模板
```
你是一位专业的书籍摘要专家。请为以下书籍内容生成精简摘要：

【书名】: {title}
【作者】: {author}

【要求】:
1. 核心观点：用 300-500 字概括全书核心思想
2. 章节摘要：为每个章节生成 150-200 字摘要
3. 金句摘录：提取 10-15 条最有价值的句子
4. 适用人群：说明这本书适合谁阅读

【内容】:
{content}

请以结构化格式输出。
```

#### 验收标准
- [ ] 摘要准确反映原书内容
- [ ] PDF 排版美观
- [ ] 生成时间合理（< 5分钟/本）

---

### 3.4 图片提取器 (ImageExtractor) ⭐ 新增

#### 功能描述
从 EPUB 中提取封面图片，从翻译后的 PDF 中截取目录预览图，用于商品展示。

#### 输入
- EPUB 文件路径
- 翻译后的 PDF 文件路径（用于目录预览）

#### 输出
- 封面图片 (cover.jpg/png)
- 目录预览图 (toc_preview.jpg/png)

#### 处理逻辑
1. **封面提取**:
   - 优先从 EPUB 元数据获取封面
   - 如元数据中没有，从第一个图片文件提取
   - 转换为 JPG/PNG 格式
   
2. **目录预览提取**:
   - 使用 PyMuPDF（fitz）打开翻译后的 PDF
   - 定位目录页（通过 PDF 目录结构或关键词搜索）
   - 将目录页渲染为图片
   - 优化图片尺寸

3. **图片优化**:
   - 调整尺寸（最大 1200x1600）
   - 压缩文件大小（< 500KB）

#### 技术实现
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
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pix.save(output_path)
            break
```

#### 验收标准
- [ ] 封面图片清晰完整
- [ ] 目录预览图可读
- [ ] 图片大小适中

---

### 3.5 AI 文案生成器 (AICopywriter) ⭐ 新增

#### 功能描述
使用 AI 生成闲鱼商品文案和小红书种草笔记。

#### 输入
- 书名、作者
- 书籍简介/摘要
- 封面图片

#### 输出
- 闲鱼商品信息（JSON 格式）
- 小红书笔记（Markdown 格式）

#### 闲鱼文案结构
```json
{
  "title": "商品标题（30字内）",
  "description": "商品描述（包含卖点、格式说明）",
  "tags": ["标签1", "标签2", "标签3"],
  "price_suggestions": {
    "english_only": 3.99,
    "full_package": 8.99
  }
}
```

#### AI Prompt 模板 - 闲鱼文案
```
你是一位闲鱼电商文案专家。请为以下书籍生成商品文案：

【书名】: {title}
【作者】: {author}
【简介】: {summary}

【SKU信息】:
- 纯英文原版 PDF: ¥3.99
- 完整套装(英文+中文+双语+精简版): ¥8.99

【要求】:
1. 标题：25-30字，吸引人，包含关键词
2. 描述：
   - 第一段：书籍价值和亮点
   - 第二段：包含内容说明（4个版本）
   - 第三段：购买须知和发货方式
3. 标签：5-8个相关标签
4. 语气：专业、友好、有说服力

请按 JSON 格式输出。
```

#### AI Prompt 模板 - 小红书笔记
```
你是一位小红书读书博主。请为以下书籍生成种草笔记：

【书名】: {title}
【作者】: {author}
【核心观点】: {key_points}

【要求】:
1. 标题：爆款风格，带 emoji，20字内
2. 正文：
   - 开头：痛点引入或金句
   - 中间：书籍介绍 + 核心价值
   - 结尾：推荐理由 + 获取方式
3. 使用 emoji 增加可读性
4. 添加相关话题标签（#读书 #好书推荐 等）
5. 语气：亲切、真实、像朋友推荐

请按 Markdown 格式输出。
```

#### 验收标准
- [ ] 文案吸引人，符合平台风格
- [ ] 包含所有必要信息
- [ ] 标签准确相关

---

### 3.6 Excel 链接读取器 (LinkImporter) ⭐ 新增

#### 功能描述
读取百度网盘导出的 Excel 文件，自动匹配文件名和分享链接。

#### 输入
- Excel 文件路径（百度网盘导出格式）
- 已处理书籍列表

#### 输出
- 匹配结果列表（书籍 ID + 分享链接）

#### Excel 格式预期
百度网盘导出的 Excel 通常包含：
- 文件名
- 分享链接
- 提取码（如有）

#### 处理逻辑
1. 读取 Excel 文件
2. 提取文件名和分享链接
3. 与系统中的书籍进行模糊匹配
4. 标记未匹配项，供人工确认
5. 保存匹配结果到数据库

#### 匹配算法
```python
def match_book_to_link(book_title: str, filename: str) -> float:
    """
    计算书名和文件名的匹配度
    返回 0-1 的相似度分数
    """
    # 1. 去除扩展名
    # 2. 统一大小写
    # 3. 计算编辑距离或相似度
    # 4. 返回匹配分数
```

#### 验收标准
- [ ] 能正确读取百度网盘 Excel
- [ ] 匹配准确率 > 90%
- [ ] 未匹配项清晰标记

---

### 3.7 闲管家发布器 (XianyuPublisher) ⭐ 新增

#### 功能描述
通过浏览器自动化，在闲管家网页版发布商品、配置 SKU 和自动发货链接。

#### 输入
- 书籍完整信息（含文案、图片、网盘链接）
- SKU 配置
- 登录凭证（扫码）

#### 输出
- 发布成功的商品链接
- 发布日志

#### SKU 配置
| SKU 名称 | 价格 | 包含内容 | 发货链接 |
|---------|------|---------|---------|
| 纯英文原版 | ¥3.99 | 英文 PDF | 网盘链接 |
| 完整套装 | ¥8.99 | 英文+中文+双语+精简 | 网盘链接 |

#### 处理流程
1. **登录**:
   - 打开闲管家网页版
   - 显示二维码
   - 用户扫码登录
   - 保存登录态

2. **创建商品**:
   - 点击"发布商品"
   - 填写标题
   - 填写描述
   - 上传图片（封面、目录、内容预览）
   - 设置价格（取 SKU 最低价）

3. **配置 SKU**:
   - 进入 SKU 配置页面
   - 添加两个 SKU 选项
   - 设置对应价格

4. **配置自动发货**:
   - 进入发货设置
   - 为每个 SKU 配置对应的网盘链接
   - 设置自动回复消息

5. **发布**:
   - 检查所有信息
   - 点击发布
   - 保存商品链接

#### 技术实现
使用 Playwright 进行浏览器自动化：
```python
from playwright.sync_api import sync_playwright

class XianyuPublisher:
    def __init__(self):
        self.browser = None
        self.page = None
    
    def login(self):
        # 打开闲管家，等待扫码
        pass
    
    def create_product(self, book_info):
        # 创建商品
        pass
    
    def configure_sku(self, skus):
        # 配置 SKU
        pass
    
    def setup_delivery(self, sku_links):
        # 配置自动发货
        pass
```

#### 验收标准
- [ ] 能成功登录闲管家
- [ ] 能正确发布商品
- [ ] SKU 配置正确
- [ ] 发货链接配置正确
- [ ] 支持批量发布

---

## 4. 数据模型

### 4.1 数据库表结构

```sql
-- 书籍基础信息表
CREATE TABLE books (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT,
    author TEXT,
    isbn TEXT,
    language TEXT,
    page_count INTEGER,
    file_size INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 书籍输出文件表
CREATE TABLE book_outputs (
    id TEXT PRIMARY KEY,
    book_id TEXT REFERENCES books(id),
    bilingual_epub TEXT,
    chinese_epub TEXT,
    bilingual_pdf TEXT,
    chinese_pdf TEXT,
    summary_pdf TEXT,
    cover_image TEXT,
    toc_image TEXT,
    xianyu_title TEXT,
    xianyu_description TEXT,
    xianyu_tags TEXT,
    xiaohongshu_note TEXT,
    pan_link TEXT,
    pan_code TEXT,
    xianyu_product_id TEXT,
    xianyu_listing_url TEXT,
    publish_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 处理日志表
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT REFERENCES books(id),
    stage TEXT,
    status TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 文件目录结构

```
workspace/
├── input/                          # 用户放入原始 EPUB
│   ├── book1.epub
│   ├── book2.epub
│   └── ...
├── output/                         # 系统生成文件
│   ├── book1/
│   │   ├── 中英双语-book1.epub
│   │   ├── 中文版本-book1.epub
│   │   ├── 中英双语-book1.pdf
│   │   ├── 中文版本-book1.pdf
│   │   ├── 核心精简-book1.pdf
│   │   ├── cover.jpg
│   │   ├── toc.jpg
│   │   ├── xianyu_listing.json
│   │   └── xiaohongshu_note.txt
│   └── book2/
│       └── ...
├── data/                           # 数据文件
│   ├── books.db                    # SQLite 数据库
│   ├── processing_log.json
│   └── share_links.xlsx            # 用户提供的网盘链接
├── config/                         # 配置文件
│   ├── settings.json
│   └── prompts/                    # AI Prompt 模板
│       ├── summary_prompt.txt
│       ├── xianyu_prompt.txt
│       └── xiaohongshu_prompt.txt
└── logs/                           # 运行日志
    └── app.log
```

---

## 5. 配置参数

### 5.1 系统配置

```json
{
  "paths": {
    "input_dir": "E:\\ebooks\\input\\",
    "output_dir": "./output",
    "data_dir": "./data"
  },
  "sku_config": {
    "options": [
      {
        "name": "纯英文原版",
        "price": 3.99,
        "includes": ["english_pdf"]
      },
      {
        "name": "完整套装",
        "price": 8.99,
        "includes": ["english_pdf", "chinese_pdf", "bilingual_pdf", "summary_pdf"]
      }
    ]
  },
  "ai_config": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "image_config": {
    "max_width": 1200,
    "max_height": 1600,
    "quality": 85,
    "format": "jpg"
  },
  "xianyu_config": {
    "login_method": "qr_code",
    "category": "书籍/杂志/报纸",
    "location": "全国"
  }
}
```

### 5.2 用户确认配置汇总

| 配置项 | 设置值 |
|--------|--------|
| **输入目录** | `E:\ebooks\input\` |
| **SKU 1** | 纯英文原版 PDF - ¥3.99 |
| **SKU 2** | 完整套装（英文+中文+双语+精简）- ¥8.99 |
| **登录方式** | 扫码登录 |
| **AI 模型** | DeepSeek |
| **定价策略** | 统一定价 |

---

## 6. 界面设计

### 6.1 命令行界面 (CLI)

```bash
# 扫描并处理新书籍
python main.py process

# 仅扫描
python main.py scan

# 导入网盘链接
python main.py import-links data/share_links.xlsx

# 预览待发布商品
python main.py preview

# 发布到闲鱼
python main.py publish

# 启动 Web 界面
python main.py web
```

### 6.2 Web 界面 (Streamlit)

**主页面功能**:
- 处理状态看板（待处理/处理中/已完成/已发布）
- 书籍列表（可筛选、搜索）
- 处理进度实时显示
- 一键发布功能

**书籍详情页**:
- 基础信息展示
- 生成的文件列表（可下载）
- AI 生成文案预览
- 发布状态管理

---

## 7. 非功能性需求

### 7.1 性能要求
- 单本书处理时间 < 30 分钟（取决于页数和 API 响应）
- 支持批量处理（队列机制）
- 系统资源占用合理（内存 < 4GB）

### 7.2 可靠性要求
- 支持中断恢复
- 错误重试机制（3次）
- 数据备份（SQLite 自动备份）

### 7.3 安全要求
- API 密钥不硬编码，使用环境变量
- 登录凭证加密存储
- 日志中不记录敏感信息

---

## 8. 验收标准

### 8.1 功能验收

| 模块 | 验收标准 | 优先级 |
|------|---------|--------|
| 目录扫描器 | 能正确识别 EPUB，提取元数据 | P0 |
| 翻译处理器 | 翻译质量合格，PDF 排版正确 | P0 |
| 内容精简器 | 摘要准确，PDF 生成成功 | P0 |
| 图片提取器 | 封面/目录图片清晰可用 | P0 |
| AI 文案生成器 | 文案符合平台风格 | P0 |
| Excel 链接读取器 | 匹配准确率 > 90% | P1 |
| 闲管家发布器 | 能成功发布商品 | P0 |

### 8.2 集成验收
- [ ] 端到端流程跑通（从 EPUB 到商品发布）
- [ ] 批量处理 10 本书无错误
- [ ] 异常处理机制有效

---

## 9. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| DeepSeek API 限流 | 处理中断 | 实现指数退避重试 |
| 闲鱼反爬机制 | 发布失败 | 控制操作频率，模拟人工 |
| EPUB 格式不兼容 | 解析失败 | 增加格式验证和错误报告 |
| 网盘链接失效 | 用户投诉 | 定期检查链接有效性 |

---

## 10. 附录

### 10.1 依赖清单

```
# 核心依赖
python >= 3.8
playwright >= 1.40.0
openpyxl >= 3.1.0
pillow >= 10.0.0
streamlit >= 1.28.0

# 现有依赖
ebooklib >= 0.18
requests >= 2.31.0
beautifulsoup4 >= 4.12.0
lxml >= 4.9.0
```

### 10.2 相关文档
- [现有翻译系统 README](ebook_translator/README.md)
- [DeepSeek API 文档](https://platform.deepseek.com/)
- [Playwright 文档](https://playwright.dev/python/)

---

**文档结束**
