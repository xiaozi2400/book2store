# 电子书自动化处理与闲鱼发布系统

> 一款面向电子书卖家的端到端自动化处理工具，支持 EPUB 翻译、PDF 生成、精简版生成、文案创作及闲鱼商品发布。

---

## 功能概览

| 模块 | 功能描述 |
|------|----------|
| 📚 **EPUB翻译** | 将英文EPUB翻译为中英双语/纯中文/纯英文（EPUB+PDF三版本），支持SQLite缓存 |
| ✂️ **精简版生成** | AI分析书籍内容，生成约100页精简版（含AI适合度评估机制） |
| 🖼️ **图片处理** | 自动生成主图、提取封面图、目录预览图 |
| ✍️ **AI文案生成** | 自动生成闲鱼商品标题/描述、小红书种草笔记 |
| 🚀 **闲鱼发布** | 通过Playwright自动化发布到闲鱼（需闲管家账号） |

---

## 快速开始

### 环境要求

- Python 3.9+
- Windows 10/11
- Google Chrome（用于Playwright自动化和PDF生成）
- Calibre（可选，用于EPUB转PDF回退）

### 安装依赖

```bash
cd d:\project\bookfile_bat
pip install -r requirements-automation.txt
pip install -r ebook_translator/requirements.txt
```

### 基础配置

1. 复制并配置 `pdf_config.json`（PDF排版配置）
2. 在 `config.yaml` 中配置 API Key：
   ```yaml
   ai:
     api_key: "your-deepseek-api-key"
     base_url: "https://api.deepseek.com"
   ```

---

## 命令参考

### 查看帮助

```bash
# 查看所有可用命令
python -m automation.main --help

# 查看单个命令详情
python -m automation.main publish --help
python -m automation.main auto --help
python -m automation.main process --help
```

### 完整处理流程

#### 一键处理所有新书籍（推荐）

扫描 `input_dir` 目录，自动翻译、生成精简版、生成图片和文案、发布到闲鱼：

```bash
python -m automation.main auto
```

各步骤可通过 `--skip-*` 参数灵活控制：

```bash
# 跳过发布步骤（只完成翻译+精简版+图片+文案）
python -m automation.main auto --skip-publish

# 只翻译，跳过精简版/图片/文案/发布
python -m automation.main auto --skip-summarize --skip-images --skip-copywriting --skip-publish

# 跳过翻译，只用已有翻译结果重新生成后续内容
python -m automation.main auto --skip-translate

# 跳过翻译缓存，强制重新翻译所有内容
python -m automation.main auto --skip-cache
```

#### 处理指定书籍

```bash
# 完整处理：翻译 -> 精简版 -> 主图 -> 提取图片 -> 文案 -> 发布
python -m automation.main process <book_id>

# 处理指定书籍，跳过发布
python -m automation.main process <book_id> --skip-publish
```

`book_id` 支持前缀匹配，只需输入前几位即可。

#### 测试模式

从 `test_input_dir` 目录读取文件处理（自动跳过闲鱼发布）：

```bash
# 完整测试（翻译+精简版+图片+文案）
python -m automation.main test

# 跳过某些步骤
python -m automation.main test --skip-translate --skip-summarize
```

---

### 分步骤操作

#### 扫描与查询

```bash
# 扫描输入目录，检测新书籍
python -m automation.main scan

# 查看处理状态统计
python -m automation.main status

# 列出书籍（默认显示最近10本）
python -m automation.main list

# 按状态筛选（pending/completed/failed/published）
python -m automation.main list --status-filter failed

# 指定显示数量
python -m automation.main list --limit 20

# 初始化数据库（创建表结构）
python -m automation.main init
```

#### 发布相关

```bash
# 发布到闲鱼（有确认提示）
python -m automation.main publish <book_id>

# 自动发布（跳过手动确认）
python -m automation.main publish <book_id> --auto

# 重新发布失败书籍（metadata目录未删除时可直接重试）
python -m automation.main publish <book_id>

# 生成闲鱼发布清单（备用方案）
python -m automation.main generate_list <book_id>
```

#### 查看与重试发布失败

```bash
# 列出所有发布失败的书籍（完整 ID + 失败原因 + 失败时间）
python -m automation.main list-failed

# 重新发布所有失败的书籍（带确认提示）
python -m automation.main republish-failed --all

# 重新发布指定 ID（可多次）
python -m automation.main republish-failed --book-id <id1> --book-id <id2>

# 跳过确认提示
python -m automation.main republish-failed --all --auto

# 回填历史发布失败状态（幂等；启动时若有未回填会自动提示）
python -m automation.main backfill-publish-status
```

发布失败的书籍在数据库中由 `BookOutput.publish_status='failed'` 标识。`list-failed` 输出完整 UUID,`republish-failed` 接受完整 ID 作为参数。

#### 分享链接导入

```bash
# 从Excel导入分享链接（匹配数据库中的书籍）
python -m automation.main import_links <excel_path>

# 生成Excel导入模板
python -m automation.main generate_template
```

#### Token统计

```bash
# 查看指定书籍的Token消耗明细
python -m automation.main stats <book_id>
```

#### 重新生成主图

修改主图提示词后，复用已有摘要重新生成主图：

```bash
# 按书籍标题关键词匹配
python -m automation.main regenerate-images "书名关键词"

# 按书籍ID精确指定
python -m automation.main regenerate-images --book-id <book_id>
```

---

### standalone EPU B 翻译工具

独立翻译工具，不依赖自动化数据库：

```bash
# 基本用法
python -m ebook_translator.main <input.epub> -o <output_dir>

# 测试模式（只翻译前50个段落）
python -m ebook_translator.main <input.epub> -o <output_dir> --test-mode

# 跳过缓存，强制重新翻译
python -m ebook_translator.main <input.epub> -o <output_dir> --skip-cache

# 指定API Key
python -m ebook_translator.main <input.epub> -o <output_dir> -k <api_key>
```

---

### auto 命令完整参数一览

| 参数 | 说明 |
|------|------|
| `--skip-publish` | 跳过闲鱼发布 |
| `--skip-translate` | 跳过翻译步骤 |
| `--skip-summarize` | 跳过精简版生成 |
| `--skip-images` | 跳过图片生成与提取 |
| `--skip-copywriting` | 跳过文案生成 |
| `--skip-cache` | 跳过翻译缓存，强制重新翻译 |

`process` 命令支持 `--skip-publish`，`test` 命令支持除 `--skip-publish` 外的所有参数。

---

## 项目结构

```
bookfile_bat/
├── automation/                    # 自动化处理核心模块
│   ├── main.py                    # CLI入口（Typer）
│   ├── config.py                  # 配置加载
│   ├── database.py                # SQLite数据库管理
│   ├── models.py                  # ORM模型定义
│   ├── utils.py                   # 工具函数（日志、EPUB验证等）
│   ├── ai_client.py               # AI客户端（DeepSeek API封装）
│   ├── ai_copywriter.py           # 文案生成（闲鱼/小红书）
│   ├── content_summarizer.py      # 精简版生成（含PDF生成）
│   ├── suitability_evaluator.py   # 适合度评估（AI+规则）
│   ├── template_generator.py      # 动态模板生成
│   ├── translation_processor.py   # 翻译处理器（调用ebook_translator）
│   ├── translation_cache.py       # SQLite翻译缓存实现
│   ├── directory_scanner.py       # 输入目录扫描
│   ├── image_extractor.py         # EPUB图片提取
│   ├── image_generator.py         # AI主图生成
│   ├── metadata_writer.py         # metadata.json写入
│   ├── xianyu_publisher.py        # 闲鱼Playwright自动化发布
│   ├── link_importer.py           # Excel分享链接导入
│   ├── quality_checker.py         # 翻译质量检查
│   └── 精简版生成提示词.md         # AI精简版提示词
│
├── ebook_translator/              # EPUB翻译模块
│   ├── main.py                    # 独立翻译主程序
│   ├── library.py                 # 库函数接口（供automation调用）
│   ├── config.py                  # 翻译配置
│   ├── translator/
│   │   ├── epub_parser.py         # EPUB解析（提取段落）
│   │   ├── epub_generator.py      # EPUB生成（双语/中文）
│   │   ├── pdf_converter.py       # EPUB转PDF
│   │   ├── translator.py          # 翻译器（智能分层）
│   │   ├── deepseek_api.py        # DeepSeek API调用
│   │   ├── cache.py               # JSON缓存管理
│   │   └── cache_interface.py     # 缓存抽象接口
│   └── requirements.txt
│
├── config.yaml                    # 主配置文件
├── config_template.yaml           # 精简版模板配置
├── pdf_config.json                # PDF排版配置
├── requirements-automation.txt    # 自动化模块依赖
├── PRD.md                         # 产品需求文档
└── README.md                      # 本文件
```

---

## 配置说明

### config.yaml 主要配置项

```yaml
paths:
  input_dir: "./input"              # 输入目录（放EPUB文件）
  output_dir: "./output"            # 输出目录
  test_input_dir: "./test_input"    # 测试输入目录

ai:
  api_key: "your-api-key"           # DeepSeek API Key
  base_url: "https://api.deepseek.com"

suitability_eval:
  precheck:
    min_pages: 50                   # 最少页数
    max_pages: 2000                 # 最大页数

summarizer:
  core_insight_length: "300-500"
  chapter_summary_length: "150-200"

xianyu:
  cookie: "your-xianyu-cookie"
  inventory: 999
  location: "上海"
  shipping: "包邮"
```

### pdf_config.json 排版配置

```json
{
  "css": {
    "paragraph_text_indent": "2em",
    "paragraph_margin_bottom": "1.5em",
    "paragraph_line_height": "1.8",
    "heading_margin_top": "1.5em",
    "heading_margin_bottom": "1em",
    "list_item_margin_bottom": "0.8em",
    "blockquote_margin": "1.5em",
    "blockquote_padding_left": "1.5em",
    "blockquote_border_left": "3px solid #ccc"
  }
}
```

---

## 输出文件结构

每本书籍在 `output_dir` 下会生成以下目录结构：

```
output/<书名>/
├── 双语-<书名>/           # 中英对照版
│   ├── 双语-<书名>.epub
│   └── 双语-<书名>.pdf
├── 中文-<书名>/            # 纯中文版
│   ├── 中文-<书名>.epub
│   └── 中文-<书名>.pdf
├── 英文-<书名>/            # 英文原版（仅PDF）
│   └── 英文-<书名>.pdf
├── <书名>_metadata/       # 元数据（发布用）
│   ├── metadata.json      # 书籍元数据
│   ├── cover.*            # 封面图片
│   ├── xianyu_listing.txt # 闲鱼文案
│   └── *_metadata/        # 主图等资源
├── <书名>_精.pdf          # 精简版PDF
└── <书名>_metadata/       # 精简版元数据
```

---

## 核心功能详解

### 1. 翻译流程

- **智能分层翻译**：按段落复杂度（标题/正文/代码/引用）分层翻译，平衡速度和准确度
- **缓存机制**：使用 SQLite 数据库缓存翻译结果，下次处理自动跳过已翻译内容
- **原版保留**：保留英文原版 EPUB/PDF 不变

### 2. 适合度评估

系统在生成精简版前会自动使用 **AI 评估** 书籍是否适合：

- **AI 评估**（主）：使用 DeepSeek API 智能判断
- **规则评估**（备）：关键词匹配规则
- 返回详细的通过/不适合原因

### 3. 精简版生成

采用动态模板系统，根据书籍类型选择不同策略：

| 书籍类型 | 策略 | 模板 |
|----------|------|------|
| 技能型 | 强化操作步骤 | 步骤+练习+检查清单 |
| 概念型 | 精确定义概念 | 概念+关系+应用场景 |
| 案例型 | 保留核心案例 | 案例+规律+框架 |
| 理论型 | 保留理论框架 | 假设+命题+应用 |
| 叙事型 | 保留故事线 | 经历+洞见+原则 |
| 混合型 | 识别主导类型 | 综合策略 |

### 4. 闲鱼发布流程

通过 Playwright 自动化浏览器操作：

1. 打开闲鱼商家后台
2. 自动登录（支持Cookie持久化）
3. 上传商品图片（主图+目录预览图）
4. 填写商品描述（AI生成的文案）
5. 设置分类和SKU
6. 提交发布，记录商品链接
7. 发布成功后自动清理临时文件

---

## 常见问题

### Q: 翻译失败怎么办？
A: 检查 `config.yaml` 中的 API Key 是否正确，确保网络能访问 DeepSeek API。也可以加 `--skip-cache` 强制重新翻译。

### Q: 翻译到一半中断了怎么办？
A: 重新执行命令即可，已有缓存的部分会自动跳过。对未完成的部分继续翻译。

### Q: 适合度评估不通过怎么办？
A: 该书籍可能被判定为不适合生成精简版（如内容过于简单或复杂）。可以在 `config.yaml` 中调整评估规则。

### Q: 发布到闲鱼失败怎么办？
A: 运行 `python -m automation.main publish <book_id>` 重新发布。如果多次失败，检查 `logs/publish_error_*.png` 截图查看错误原因。

### Q: 如何跳过某些步骤？
A: `auto` 命令支持 `--skip-publish`、`--skip-translate`、`--skip-summarize`、`--skip-images`、`--skip-copywriting` 参数。

### Q: 如何查看Token消耗？
A: 运行 `python -m automation.main stats <book_id>` 查看各步骤的 Token 消耗明细和费用。

### Q: 如何查看详细日志？
A: 日志文件位于 `logs/automation_YYYYMMDD.log`

### Q: 修改了主图提示词后如何重新生成？
A: 运行 `python -m automation.main regenerate-images <书名关键词>` 或 `--book-id <book_id>`。

---

## 数据存储

系统使用 SQLite 数据库（`data/automation.db`）存储所有数据：

| 表 | 说明 |
|----|------|
| `books` | 书籍基本信息（文件名、标题、作者、状态） |
| `book_outputs` | 输出文件路径、发布链接、发布状态 |
| `processing_logs` | 处理日志记录 |
| `token_usage` | Token消耗统计 |
| `translation_cache` | 翻译缓存（替代旧JSON缓存文件） |

---

## 注意事项

1. **API配额**：DeepSeek API 有调用限制，翻译大量书籍时请注意配额
2. **缓存机制**：翻译结果会缓存到 SQLite 数据库中，重复翻译会使用缓存。旧 JSON 缓存文件（`translation_cache.json`）首次使用时自动迁移
3. **PDF转换**：推荐使用 Playwright + Chrome 生成PDF（默认），Calibre 作为回退方案
4. **闲鱼发布**：需要闲管家账号，首次登录需扫码
5. **文件名**：EPUB 文件名不应包含尾随空格，否则可能导致路径异常

---

## 技术栈

- **Python 3.9+** - 主语言
- **DeepSeek API** - AI能力（翻译、文案生成、精简版）
- **SQLite (SQLAlchemy)** - 本地数据存储
- **Playwright** - 浏览器自动化（PDF生成 + 闲鱼发布）
- **BeautifulSoup / lxml** - HTML/EPUB解析
- **Typer** - CLI框架
- **Rich** - 终端美化

---

## 后续规划

- [ ] 支持更多书籍类型识别
- [ ] 优化适合度评估规则
- [ ] 支持更多电商平台
- [ ] 添加Web管理界面
- [ ] 多账号发布支持