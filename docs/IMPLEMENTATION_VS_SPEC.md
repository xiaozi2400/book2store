# 实现与规格文档一致性分析报告

**项目**: bookfile_bat - 电子书自动化处理与闲鱼发布系统
**分析日期**: 2026-09-18
**分析范围**: `docs/archived_superpowers/specs/` 目录下的规格文档 vs `automation/` 目录下的代码实现

---

## 一、核心规格文档概览

| 文档 | 日期 | 主要内容 |
|------|------|---------|
| `TECH_SPEC.md` | 2026-04-18 | 最终技术方案（系统架构、项目结构、模块设计） |
| `PRD.md` | 2026-04-18 | 产品需求文档（业务流程、功能模块、验收标准） |
| `2026-05-29-xianyu-auto-publish-design.md` | 2026-05-29 | 闲鱼自动发布功能设计 |
| `2026-05-30-main-image-generator-design.md` | 2026-05-30 | 闲鱼商品主图生成功能设计 |
| `2026-06-04-optimize-pipeline-design.md` | 2026-06-04 | 流水线优化（质量报告终端输出、文件名规范化、文件转移） |
| `2026-06-04-stage-progress-output-design.md` | 2026-06-04 | 阶段进度输出优化 |
| `2026-06-04-terminal-output-optimization.md` | 2026-06-04 | 终端输出优化 |
| `2026-06-14-republish-failed-books-design.md` | 2026-06-14 | 重新发布失败书籍功能 |
| `2026-06-15-epub-quality-checker-design.md` | 2026-06-15 | EPUB文件质量检查工具 |
| `2026-07-12-pipeline-stage-architecture-design.md` | 2026-07-12 | Pipeline/Stage架构重构 |
| `2026-07-12-content-summarizer-split-design.md` | 2026-07-12 | 内容精简器重构设计方案 |

---

## 二、模块对比分析

### 2.1 目录扫描器 (directory_scanner.py)

| 规格描述 (TECH_SPEC/PRD) | 实现状态 | 差异说明 |
|------------------------|---------|---------|
| 扫描 `.epub` 文件 | ✅ 已实现 | `scan_input_directory()` 函数 |
| 验证EPUB格式 | ✅ 已实现 | 调用 `is_valid_epub()` |
| 检查是否已处理 | ✅ 已实现 | 查询数据库 |
| 提取基础元数据（书名、作者） | ✅ 已实现 | 通过 `ebooklib` 提取 |

**差异**: 规格中提到"检查文件语言（确认是纯英文）"，实际代码未实现语言检测。

---

### 2.2 翻译处理器 (TranslationProcessor)

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 调用现有 EPUBParser 解析 | ✅ 已实现 | 复用 `ebook_translator` 库 |
| 调用 DeepSeekTranslator 翻译 | ✅ 已实现 | |
| 生成双语 EPUB | ✅ 已实现 | |
| 生成纯中文 EPUB | ✅ 已实现 | |
| 调用 PDFConverter 转换 PDF | ✅ 已实现 | |
| 支持中断恢复（翻译阶段） | ✅ 已实现 | 翻译缓存机制 |

**差异**: 无重大差异。

---

### 2.3 内容精简器 (ContentSummarizer)

| 规格描述 (PRD) | 实现状态 | 差异说明 |
|--------------|---------|---------|
| 全书核心观点（500字左右） | ✅ 已实现 | |
| 各章节摘要（每章200字左右） | ✅ 已实现 | |
| 金句摘录（10-15条） | ✅ 已实现 | 配置 `max_quotes: 10` |
| 适用人群说明 | ✅ 已实现 | |
| 思维导图大纲 | ❌ 未实现 | PRD中提到，但实现中无此功能 |
| PDF生成 | ✅ 已实现 | 使用ReportLab |

**重大差异**:
1. **未实现**: 思维导图大纲（PRD中明确列出但代码中无）
2. **架构变更**: 按照 `2026-07-12-content-summarizer-split-design.md`，内容精简器已重构为多文件模块结构

---

### 2.4 图片提取器 (ImageExtractor)

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 从EPUB提取封面 | ✅ 已实现（代码存在） | `_extract_cover()` 方法存在 |
| 从PDF提取目录预览 | ✅ 已实现 | `_extract_toc_preview()` 方法存在 |
| **封面提取已禁用** | ⚠️ 重大变更 | `extract()` 方法直接返回True，不执行实际提取 |

**重大差异**:
- **图片提取功能已被禁用**。`ImageExtractor.extract()` 方法体只有日志输出，没有任何实际提取逻辑
- 规格文档中完全没有提及此功能被禁用

---

### 2.5 AI文案生成器 (AICopywriter)

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 生成闲鱼文案（JSON格式） | ✅ 已实现 | 输出到 `xianyu_listing.txt` 而非JSON |
| 生成小红书笔记（Markdown） | ✅ 已实现 | |
| 调用DeepSeek API | ✅ 已实现 | |
| 解析JSON响应 | ✅ 已实现 | |

**差异**: 规格提到输出JSON格式，实际输出是 `.txt` 文件

---

### 2.6 Excel链接导入器 (LinkImporter)

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 读取百度网盘Excel | ✅ 已实现 | 使用OpenPyXL |
| 文件名模糊匹配 | ✅ 已实现 | |
| 标记未匹配项 | ✅ 已实现 | |

**差异**: 无重大差异

---

### 2.7 闲管家发布器 (XianyuPublisher)

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 使用Playwright浏览器自动化 | ✅ 已实现 | |
| 扫码登录 | ✅ 已实现 | Cookie持久化到 `xianyu_cookie.json` |
| 填写商品信息 | ✅ 已实现 | |
| 配置SKU | ✅ 已实现 | |
| 设置发货链接 | ✅ 已实现 | |
| 备用清单方案 | ✅ 已实现 | `generate_publish_list()` 方法 |

**差异**: 无重大差异，实现完整度较高

---

### 2.8 主图生成器 (ImageGenerator)

| 规格描述 (2026-05-30设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| 根据封面+摘要调用AI生成HTML主图 | ✅ 已实现 | |
| Playwright截图保存为JPG | ✅ 已实现 | |
| 图片存入元数据目录 | ✅ 已实现 | |
| 配置写在config.yaml | ✅ 已实现 | `image_generator` 配置节 |

**差异**: 无重大差异，已按照设计文档实现

---

### 2.9 Pipeline/Stage 架构

| 规格描述 (2026-07-12设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| PipelineContext 数据类 | ✅ 已实现 | `pipeline.py` 中定义 |
| Stage 抽象基类 | ✅ 已实现 | |
| TranslationStage | ✅ 已实现 | |
| SummaryStage | ✅ 已实现 | |
| ImageGenerationStage | ✅ 已实现 | |
| ImageExtractionStage | ✅ 已实现 | |
| CopywritingStage | ✅ 已实现 | |
| PublishStage | ✅ 已实现 | |
| Pipeline 编排器 | ✅ 已实现 | |

**差异**:
- `main.py` 中仍存在直接的流程代码，**Pipeline架构虽已实现但未被 `main.py` 的 `auto/process/test` 命令使用**
- 规格要求重构 `main.py` 使用Pipeline，但实际 `main.py` 仍直接调用各模块

---

### 2.10 质量报告终端统一输出

| 规格描述 (2026-06-04优化设计) | 实现状态 | 差异说明 |
|-----------------------------|---------|---------|
| 质量报告不再写入JSON文件 | ✅ 已实现 | 只写入数据库 |
| 终端展示Rich表格 | ✅ 已实现 | `auto()` 命令末尾展示 |

**差异**: 无重大差异

---

### 2.11 文件名规范化

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 含 `--` 取前面部分 | ✅ 已实现 | |
| 长度超过60字符截断 | ✅ 已实现 | |
| 尾随空格处理 | ✅ 已实现 | |

**差异**: 无重大差异

---

### 2.12 处理完成后转移文件

| 规格描述 | 实现状态 | 差异说明 |
|---------|---------|---------|
| 处理完成后移动到"已处理"目录 | ✅ 已实现 | `move_processed_epubs()` |

**差异**: 无重大差异

---

### 2.13 阶段进度输出 (progress.py)

| 规格描述 (2026-06-04设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| `phase()` 上下文管理器 | ✅ 已实现 | |
| `event()` 函数 | ✅ 已实现 | |
| `phase_decorator()` 装饰器 | ❌ 未实现 | 设计中有，但代码中未找到 |

**差异**: 装饰器形式未实现，但功能通过上下文管理器已覆盖

---

### 2.14 终端输出优化

| 规格描述 (2026-06-04设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| StreamHandler 只输出WARNING及以上 | ✅ 已实现 | `utils.py` 中 `setup_logging()` |

**差异**: 无重大差异

---

### 2.15 重新发布失败书籍功能

| 规格描述 (2026-06-14设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| `list-failed` 命令 | ✅ 已实现 | |
| `republish-failed` 命令 | ✅ 已实现 | |
| `backfill-publish-status` 命令 | ✅ 已实现 | |
| 发布失败时回写 `publish_status='failed'` | ✅ 已实现 | |
| Cookie持久化 | ✅ 已实现 | |

**差异**: 无重大差异，实现完整

---

### 2.16 EPUB质量检查器 (epub_checker.py)

| 规格描述 (2026-06-15设计) | 实现状态 | 差异说明 |
|--------------------------|---------|---------|
| 独立CLI工具 | ❌ 未实现 | 设计为单文件脚本 `epub_checker.py`，但文件不存在 |
| 调用外部epubcheck + 解析JSON | ❌ 未实现 | |
| Rich + JSON + Markdown报告 | ❌ 未实现 | |
| 退出码支持CI集成 | ❌ 未实现 | |

**重大差异**: 整个 `epub_checker.py` 工具**完全未实现**

---

## 三、汇总：差异分类

### 3.1 已实现但文档未提及

| 功能 | 说明 |
|------|------|
| `quality_checker.py` (翻译质量检查) | 27KB的质量检查工具，PRD/TECH_SPEC未提及 |
| MiniMax AI配置 | `config.yaml` 中有 `minimax` 配置，但文档未提及 |
| `SuitabilityEvaluator` (适合度评估) | 精简版生成前的书籍适合度评估，文档未提及 |
| Token消耗记录 (`TokenUsage` 表) | 详细的Token统计功能，文档未明确描述 |
| `main.py` 中的 `test` 命令 | 测试模式，文档未作为CLI命令描述 |

---

### 3.2 文档描述但未实现

| 功能 | 规格文档 | 严重程度 |
|------|---------|---------|
| **思维导图大纲** | PRD 3.3节 | 中 |
| **EPUB质量检查器** (`epub_checker.py`) | 2026-06-15设计 | 高 |
| **阶段进度装饰器** (`phase_decorator`) | 2026-06-04设计 | 低 |
| **Pipeline/Stage 架构被 main.py 使用** | 2026-07-12设计 | 高 |

---

### 3.3 实现与描述不符

| 功能 | 文档描述 | 实际实现 | 严重程度 |
|------|---------|---------|---------|
| **图片提取** | 正常提取封面和目录预览 | 功能已被禁用（`extract()` 方法为空） | **高** |
| **闲鱼文案格式** | 输出JSON (`xianyu_listing.json`) | 输出Text (`xianyu_listing.txt`) | 低 |
| **Pipeline使用** | `main.py` 应使用Pipeline架构 | `main.py` 仍为巨型函数，未使用Pipeline | 高 |

---

## 四、数据模型对比

### 4.1 数据库表结构

**Books表** - 规格与实现基本一致

**BookOutput表** - 实现比规格多字段

**额外表（实现中新增，文档未提及）**:
- `SystemConfig` - 系统配置表
- `ShareLink` - 网盘分享链接表
- `TokenUsage` - Token消耗记录表
- `TranslationCache` - 翻译缓存表

---

## 五、配置参数对比

### 5.1 config.yaml 实际配置 vs 规格

| 配置项 | 规格值 | 实际值 | 差异 |
|-------|-------|-------|------|
| `sku[0].name` | "纯英文原版" | "英文原版" | 命名略有不同 |
| `sku[0].price` | 3.99 | 1.99 | **价格不同** |
| `sku[1].name` | "完整套装" | "英文+双语+中译" | 命名不同 |
| `sku[1].price` | 8.99 | 5.99 | **价格不同** |

**重大差异**: SKU价格与规格文档中不一致

---

## 六、CLI命令对比

### 规格中的命令 (TECH_SPEC 8.1)

| 规格命令 | 实现命令 | 差异 |
|---------|---------|------|
| `python cli.py init` | `python -m automation.main init` | 入口不同 |
| `python cli.py scan` | `python -m automation.main scan` | ✅ 一致 |
| `python cli.py process <book_id>` | `python -m automation.main process <book_id>` | ✅ 一致 |
| `python cli.py batch-process` | `python -m automation.main auto` | 命令名不同 |
| `python cli.py import-links <excel_path>` | `python -m automation.main import-links <excel_path>` | ✅ 一致 |
| `python cli.py publish <book_id>` | `python -m automation.main publish <book_id>` | ✅ 一致 |
| `python cli.py batch-publish` | ❌ 无对应命令 | 未实现批量发布 |
| `python cli.py status` | `python -m automation.main status` | ✅ 一致 |
| `python cli.py logs` | ❌ 无对应命令 | 未实现 |
| `python cli.py web` | ❌ 无对应命令 | Web界面未实现 |

**未实现**:
- `batch-publish` - 批量发布命令
- `logs` - 查看日志命令
- `web` - Web界面（Streamlit）

---

## 七、关键发现总结

### 7.1 高优先级差异（需关注）

1. **图片提取功能被禁用** - `image_extractor.py` 的 `extract()` 方法已完全禁用，但文档未提及此变更
2. **Pipeline架构未被使用** - `pipeline.py` 已实现完整架构，但 `main.py` 仍使用巨型函数，未按设计重构
3. **EPUB质量检查器完全未实现** - 规格文档描述的工具不存在
4. **SKU价格与规格不符** - config.yaml 中价格与TECH_SPEC中定义不一致
5. **Web界面未实现** - 规格中的 `web_app.py` (Streamlit) 不存在

### 7.2 中优先级差异

1. **思维导图大纲未实现** - PRD中提到但代码中无
2. **批量发布命令未实现** - 只有单本 `publish` 命令
3. **日志查看命令未实现** - `logs` 命令不存在

### 7.3 已实现但未文档化

1. 翻译质量检查 (`quality_checker.py`)
2. 适合度评估 (`suitability_evaluator.py`)
3. Token消耗统计
4. MiniMax AI支持
5. `test` 测试模式命令

---

## 八、建议

1. **优先修复或文档化已变更的功能**：图片提取禁用状态应在文档中明确说明
2. **完成Pipeline重构**：按 `2026-07-12-pipeline-stage-architecture-design.md` 重构 `main.py` 使用Pipeline
3. **实现EPUB质量检查器**或从文档中移除该规格
4. **统一配置参数**：SKU价格应与规格一致或更新规格文档
5. **补充缺失文档**：将已实现但未文档化的功能（质量检查、适合度评估等）补充到文档
