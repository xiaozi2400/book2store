# 电子书自动化处理与闲鱼发布系统

> 一款面向电子书卖家的端到端自动化处理工具，支持 EPUB 翻译、PDF 生成、精简版生成、文案创作及闲鱼商品发布。

---

## 功能概览

| 模块 | 功能描述 |
|------|----------|
| 📚 **EPUB翻译** | 将英文EPUB翻译为中英双语/纯中文PDF，支持缓存 |
| ✂️ **精简版生成** | AI分析书籍内容，生成100分精简版（含评估机制） |
| 🖼️ **图片提取** | 自动提取封面图、目录预览图 |
| ✍️ **AI文案生成** | 自动生成闲鱼商品标题/描述、小红书种草笔记 |
| 🚀 **闲鱼发布** | 自动创建商品并发布（需配置闲管家） |

---

## 快速开始

### 环境要求

- Python 3.9+
- Windows 10/11
- Calibre (用于EPUB转PDF)

### 安装依赖

```bash
cd d:\project\bookfile_bat
pip install -r requirements-automation.txt
pip install -r ebook_translator/requirements.txt
```

### 基础配置

1. 复制并配置 `pdf_config.json`（PDF排版配置）
2. 在 `config.yaml` 中配置 API Key、闲鱼账号等

### 使用命令

```bash
# 查看所有命令
python -m automation.main --help

# 一键处理：扫描输入目录，自动处理所有新书籍（推荐）
python -m automation.main auto

# 一键处理，跳过发布步骤
python -m automation.main auto --skip-publish

# 扫描输入目录，发现新书籍
python -m automation.main scan

# 查看处理状态统计
python -m automation.main status

# 查看书籍列表
python -m automation.main list

# 处理指定书籍
python -m automation.main process <book_id>

# 处理指定书籍，跳过发布
python -m automation.main process <book_id> --skip-publish

# 导入分享链接（从Excel）
python -m automation.main import_links <excel_path>

# 发布到闲鱼
python -m automation.main publish <book_id>

# 生成商品清单
python -m automation.main generate_list
```

---

## 项目结构

```
bookfile_bat/
├── automation/                 # 自动化处理核心模块
│   ├── main.py                 # CLI入口
│   ├── config.py               # 配置加载
│   ├── database.py             # SQLite数据库管理
│   ├── ai_client.py            # AI客户端（DeepSeek）
│   ├── ai_copywriter.py        # 文案生成
│   ├── content_summarizer.py   # 精简版生成
│   ├── suitability_evaluator.py # 适合度评估
│   ├── template_generator.py   # 动态模板生成
│   ├── translation_processor.py # 翻译处理器
│   ├── image_extractor.py       # 图片提取
│   ├── xianyu_publisher.py     # 闲鱼发布
│   └── 精简版生成提示词.md      # AI精简版提示词
│
├── ebook_translator/           # EPUB翻译模块
│   ├── main.py                 # 翻译主程序
│   ├── translator/
│   │   ├── deepseek_api.py     # DeepSeek API调用
│   │   ├── epub_parser.py      # EPUB解析
│   │   ├── epub_generator.py   # EPUB生成
│   │   └── pdf_converter.py    # PDF转换
│   └── config.py               # 翻译配置
│
├── config.yaml                 # 主配置文件
├── config_template.yaml        # 精简版模板配置
├── pdf_config.json             # PDF排版配置
├── PRD.md                      # 产品需求文档
└── README.md                   # 本文件
```

---

## 配置说明

### config.yaml 主要配置项

```yaml
paths:
  input_dir: "./input"          # 输入目录
  output_dir: "./output"        # 输出目录

ai:
  api_key: "your-api-key"       # DeepSeek API Key
  base_url: "https://api.deepseek.com"

suitability_eval:
  # 精简版适合度评估规则
  precheck:
    min_pages: 50
    max_pages: 2000

summarizer:
  # 精简版生成配置
  core_insight_length: "300-500"
  chapter_summary_length: "150-200"

xianyu:
  # 闲鱼发布配置
  cookie: "your-xianyu-cookie"
```

### config_template.yaml 精简版模板

```yaml
templates:
  skill:
    name: "技能型"
    template: "..."            # 技能型书籍模板
  concept:
    name: "概念型"
    template: "..."            # 概念型书籍模板
  # ...
```

---

## 核心功能详解

### 1. 适合度评估

系统在生成精简版前会自动使用 **AI 评估** 书籍是否适合：

```python
# 评估逻辑
suitability_result = evaluator.evaluate(book_info, page_count)
if suitability_result.passed:
    # 生成精简版
else:
    # 跳过，记录原因
```

评估方式：
- **AI 评估**（主）：使用 DeepSeek API 智能判断
- **规则评估**（备）：关键词匹配规则

AI 评估优势：
- 理解语义上下文，不依赖关键词精确匹配
- 自动识别任何书籍类型
- 返回具体的通过/不适合原因

### 2. 精简版生成

采用动态模板系统，根据书籍类型选择不同策略：

| 书籍类型 | 策略 | 模板 |
|----------|------|------|
| 技能型 | 强化操作步骤 | 步骤+练习+检查清单 |
| 概念型 | 精确定义概念 | 概念+关系+应用场景 |
| 案例型 | 保留核心案例 | 案例+规律+框架 |
| 理论型 | 保留理论框架 | 假设+命题+应用 |
| 叙事型 | 保留故事线 | 经历+洞见+原则 |
| 混合型 | 识别主导类型 | 综合策略 |

### 3. AI提示词系统

精简版生成使用 `精简版生成提示词.md` 作为系统提示词，包含：
- 角色定义：[书籍领域]专家 + 书籍精简专家
- 核心使命：让读者"做到"而非"知道"
- 六阶段工作流程
- 质量检验标准

---

## 常见问题

### Q: 翻译失败怎么办？
A: 检查 `config.yaml` 中的 API Key 是否正确，确保网络能访问 DeepSeek API。

### Q: 适合度评估不通过怎么办？
A: 该书籍可能被判定为不适合生成精简版（如内容过于简单或复杂）。可以在 `config.yaml` 中调整评估规则。

### Q: 如何跳过某些步骤？
A: 使用 `--skip-publish` 参数可以跳过发布步骤，其他步骤暂不支持跳过。

### Q: 如何查看详细日志？
A: 日志文件位于 `logs/automation_YYYYMMDD.log`

---

## 注意事项

1. **API配额**：DeepSeek API 有调用限制，翻译大量书籍时请注意配额
2. **缓存机制**：翻译结果会被缓存到 `translation_cache.json`，重复翻译会使用缓存
3. **PDF转换**：需要安装 Calibre 并配置 `ebook-convert` 路径
4. **闲鱼发布**：需要配置Cookie，且账号需要满足发布条件

---

## 技术栈

- **Python 3.9+** - 主语言
- **DeepSeek API** - AI能力（翻译、文案生成、精简版）
- **SQLite** - 本地数据存储
- **Calibre** - EPUB转PDF
- **Typer** - CLI框架
- **Rich** - 终端美化

---

## 后续规划

- [ ] 支持更多书籍类型识别
- [ ] 优化适合度评估规则
- [ ] 添加批量处理模式
- [ ] 支持更多电商平台
- [ ] 添加Web管理界面
