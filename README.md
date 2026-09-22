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
| 🚀 **闲鱼发布** | 通过Playwright自动化发布到闲鱼（需登录闲鱼卖家工作台） |

---

## 快速开始

### 环境要求

- Python 3.9+
- Windows 10/11
- Google Chrome（用于Playwright自动化和PDF生成）
- Calibre（可选，用于EPUB转PDF回退）

### 安装依赖

```bash
cd D:\project\bookfile_bat
pip install -r requirements.txt
pip install -r ebook_translator/requirements.txt
playwright install chromium
```

### 基础配置

1. 复制并配置 `pdf_config.json`（PDF排版配置）
2. 在 `config.yaml` 中配置 API Key（留空则通过环境变量 `DEEPSEEK_API_KEY` 注入）：
   ```yaml
   ai:
     provider: "deepseek"
     api_key: ""
   ```

---

## 常见使用场景

### 场景一：首次使用全自动处理

```bash
# 扫描 input_dir，自动处理所有新书（翻译→精简版→图片→文案→发布）
python -m automation.main auto
```

### 场景二：调试/开发（跳过发布）

```bash
# 处理到发布前各步骤，方便调试
python -m automation.main auto --skip-publish

# 只翻译，跳过后续所有步骤
python -m automation.main auto --skip-summarize --skip-images --skip-copywriting --skip-publish

# 强制重新翻译（跳过缓存）
python -m automation.main auto --skip-cache
```

### 场景三：处理指定书籍

```bash
# 完整处理指定书籍
python -m automation.main process <book_id>

# 处理指定书籍，跳过发布
python -m automation.main process <book_id> --skip-publish
```

`book_id` 支持前缀匹配，只需输入前几位即可。

### 场景四：发布失败重试

```bash
# 查看所有发布失败的书籍
python -m automation.main list-failed

# 重新发布所有失败的书籍
python -m automation.main republish-failed --all --auto
```

### 场景五：测试模式

从 `test_input_dir` 目录读取文件（自动跳过闲鱼发布）：

```bash
python -m automation.main test
```

---

## 命令速查

| 用途 | 命令 |
|------|------|
| **一键处理新书** | `python -m automation.main auto` |
| **处理指定书籍** | `python -m automation.main process <book_id>` |
| **测试模式** | `python -m automation.main test` |
| **发布到闲鱼** | `python -m automation.main publish <book_id> --auto` |
| **重试发布失败** | `python -m automation.main republish-failed --all --auto` |
| **查看处理状态** | `python -m automation.main list --status-filter failed` |
| **查看Token消耗** | `python -m automation.main stats <book_id>` |
| **初始化数据库** | `python -m automation.main init` |

---

## 完整命令参考

### auto 命令

核心一键处理命令，扫描 `input_dir` 自动处理所有新书籍。

```bash
python -m automation.main auto [选项]
```

| 参数 | 说明 |
|------|------|
| `--skip-publish` | 跳过闲鱼发布 |
| `--skip-translate` | 跳过翻译步骤 |
| `--skip-summarize` | 跳过精简版生成 |
| `--skip-images` | 跳过图片生成与提取 |
| `--skip-copywriting` | 跳过文案生成 |
| `--skip-cache` | 跳过翻译缓存，强制重新翻译 |

### process 命令

处理指定书籍，支持前缀匹配。

```bash
python -m automation.main process <book_id> [选项]
```

支持 `--skip-publish` 参数。

### test 命令

从 `test_input_dir` 读取文件，自动跳过发布。

```bash
python -m automation.main test [选项]
```

支持除 `--skip-publish` 外的所有参数。

### publish 命令

```bash
# 发布到闲鱼（有确认提示）
python -m automation.main publish <book_id>

# 自动发布（跳过确认）
python -m automation.main publish <book_id> --auto
```

### 辅助命令

```bash
# 扫描输入目录，检测新书籍
python -m automation.main scan

# 查看处理状态统计
python -m automation.main status

# 列出书籍（默认最近10本）
python -m automation.main list

# 按状态筛选
python -m automation.main list --status-filter failed

# 重新生成主图
python -m automation.main regenerate-images --book-id <book_id>

# 从Excel导入分享链接
python -m automation.main import_links <excel_path>

# 生成Excel导入模板
python -m automation.main generate_template
```

### standalone EPUB 翻译工具

独立翻译工具，不依赖自动化数据库：

```bash
# 方式一：在项目根目录
python -m ebook_translator.main <input.epub> -o <output_dir>

# 方式二：进入子目录直接运行
cd ebook_translator && python main.py <input.epub> -o <output_dir>

# 测试模式（只翻译前50个段落）
python -m ebook_translator.main <input.epub> -o <output_dir> --test-mode

# 指定API Key
python -m ebook_translator.main <input.epub> -o <output_dir> -k <api_key>
```

---

## 配置说明

### config.yaml 主要配置项

```yaml
# 路径配置
paths:
  input_dir: "./data/input"          # 输入目录（放EPUB文件）
  output_dir: "./data/output"        # 输出目录
  log_dir: "./logs"                  # 日志目录

# SKU配置
sku:
  - name: "英文原版"
    price: 1.99
  - name: "英文+双语+中译"
    price: 5.99

# AI配置
# 注意：api_key 留空，生产环境通过环境变量 DEEPSEEK_API_KEY 注入
ai:
  provider: "deepseek"              # AI provider
  api_key: ""                        # DeepSeek API Key（生产环境用环境变量）
  retry_times: 3                     # API 重试次数

# 文案生成配置
copywriting:
  xianyu_listing_prompt: |           # 闲鱼文案生成 prompt
    ...
  xiaohongshu_note_prompt: |         # 小红书笔记生成 prompt
    ...

# 闲管家配置
xianyu:
  base_url: "https://seller.goofish.com"
  timeout: 30
  inventory: 100
  shipping: "包邮"
  cookie_path: "data/xianyu_cookie.json"
  max_retries: 3
  retry_interval: 2
  headless: true

# 精简版生成配置
summarizer:
  core_insight_length: "300-500"    # 核心观点字数
  chapter_summary_length: "150-200"  # 章节摘要字数
  max_quotes: 10                     # 金句数量
  prompt: |                          # 摘要生成 prompt
    ...

# 质量检查配置
quality_check:
  enabled: true
  thresholds:
    excellent: 90
    good: 75
    pass: 60

# 图片生成器配置
image_generator:
  enabled: true
  width: 800
  height: 800
  device_scale_factor: 2
  screenshot_quality: 92
  color_theme: light
  palettes:                          # 配色方案（深色系+浅色系）
    ...
  design_prompt: |                    # 主图设计 prompt
    ...
  html_prompt: |                     # 主图HTML生成 prompt
    ...
```

### pdf_config.json 排版配置

```json
{
  "css": {
    "paragraph_text_indent": "2em",
    "paragraph_margin_bottom": "1.5em",
    "paragraph_line_height": "1.8"
  }
}
```

---

## 输出文件结构

每本书籍在 `data/output` 下会生成以下目录结构：

```
data/output/<书名>/
├── 双语-<书名>/           # 中英对照版
│   ├── 双语-<书名>.epub
│   └── 双语-<书名>.pdf
├── 中文-<书名>/            # 纯中文版
│   ├── 中文-<书名>.epub
│   └── 中文-<书名>.pdf
├── 英文-<书名>/            # 英文原版（仅PDF）
│   └── 英文-<书名>.pdf
├── <书名>_metadata/       # 元数据（发布用）
│   ├── cover.*            # 封面图片
│   └── xianyu_listing.txt # 闲鱼文案
├── <书名>_精.pdf          # 精简版PDF
└── <书名>_metadata/       # 精简版元数据
```

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

### Q: 精简版生成如何工作？
A: 系统会根据书籍类型（技能型/概念型/案例型/理论型/叙事型）自动选择最优模板，确保精简版保留核心内容。

### Q: 如何查看详细日志？
A: 日志文件位于 `logs/automation_YYYYMMDD.log`

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

## CI/CD

### GitHub Actions

| Job | 说明 |
|-----|------|
| `ruff` | 代码风格检查 (ruff lint + format) |
| `pytest` | 测试 (unit + integration)，覆盖率阈值 35% |
| `pip-audit` | Python 依赖安全漏洞扫描 |
| `trivy` | 文件系统安全扫描 (SARIF 格式) |

### pre-commit 钩子

```bash
pip install pre-commit
pre-commit install
```

### Dependabot

- **Python 依赖**: 每周一 09:00 (Asia/Shanghai) 自动创建 PR
- **GitHub Actions**: 每周一 09:00 (Asia/Shanghai) 自动创建 PR

---

## 技术栈

- **Python 3.9+** - 主语言
- **DeepSeek API** - AI能力（翻译、文案生成、精简版）
- **SQLite (SQLAlchemy)** - 本地数据存储
- **Playwright** - 浏览器自动化（PDF生成 + 闲鱼发布）
- **BeautifulSoup / lxml** - HTML/EPUB解析
- **Typer** - CLI框架
- **Rich** - 终端美化
- **Ruff** - 代码风格检查（lint + format）

---

