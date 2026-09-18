# 架构评审报告

**项目**: 电子书自动化处理与闲鱼发布系统  
**评审日期**: 2026-09-18  
**评审人**: 架构评审团队

---

## 1. 项目整体架构

### 1.1 架构模式与设计原则

本项目采用**面向切面流水线（Pipeline）架构**，结合**模块化分层设计**：

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 入口层                              │
│                   (automation/main.py)                      │
│                      Typer + Rich                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Pipeline 编排层                          │
│                   (automation/pipeline.py)                   │
│              Stage 抽象 + Pipeline 编排器                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ TranslationStage │   │ SummaryStage  │   │ PublishStage  │
└───────────────┘   └───────────────┘   └───────────────┘
```

**核心设计原则**：
- **单一职责**: 每个 Stage 独立完成特定任务
- **可配置跳过**: 所有阶段支持 `--skip-*` 选项
- **上下文传递**: `PipelineContext` 作为数据传递载体
- **日志追踪**: 每个阶段记录 ProcessingLog

### 1.2 模块划分与依赖关系

```
automation/                      # 主项目（父模块）
├── main.py (30KB)              # CLI 入口，Typer 命令行
├── pipeline.py (9.7KB)         # Pipeline/Stage 架构
├── database.py (15KB)          # SQLite + SQLAlchemy ORM
├── models.py (5.7KB)           # 数据模型定义
├── config.py (7.9KB)           # 单例配置类
├── quality_checker.py (27KB)   # 8 维度质量检查（711 行）
├── progress.py (2.6KB)         # 阶段进度输出
│
├── translation/                # 翻译处理子模块
│   ├── translation_processor.py
│   └── translation_cache.py
│
├── summarizer/                 # 摘要生成子模块 (105KB)
│   ├── pdf_generator.py (42KB, 1263 行)  # 最大文件
│   ├── content_summarizer.py
│   ├── suitability_evaluator.py
│   └── ...
│
├── publishing/                 # 发布子模块
│   ├── xianyu_publisher.py (31KB, 762 行)
│   └── ai_copywriter.py
│
├── image/                      # 图片生成子模块
│   └── image_generator.py (34KB)
│
└── ebook_translator/           # 可独立运行的翻译子项目
    ├── library.py (10.5KB)     # 对外编程接口
    ├── translator/              # 核心翻译逻辑
    └── ...
```

**关键依赖关系**：
- `main.py` 依赖所有子模块，是业务组装层
- `pipeline.py` 定义 Stage 抽象，子模块实现具体逻辑
- `database.py` 被所有需要持久化的模块共享
- `ebook_translator/library.py` 是核心翻译引擎，被 `translation/` 调用

### 1.3 代码组织结构

| 目录/文件 | 大小 | 行数 | 职责 |
|-----------|------|------|------|
| `automation/main.py` | 30KB | 820 | CLI 命令入口 |
| `automation/pipeline.py` | 9.7KB | 307 | 流水线编排 |
| `automation/quality_checker.py` | 27KB | 711 | 质量检查 |
| `automation/summarizer/pdf_generator.py` | 42KB | 1263 | PDF 生成 |
| `automation/publishing/xianyu_publisher.py` | 31KB | 762 | 闲鱼发布 |
| `automation/image/image_generator.py` | 34KB | - | AI 主图 |
| `automation/database.py` | 15KB | 442 | 数据持久化 |

---

## 2. 核心模块分析

### 2.1 automation/ - 自动化处理核心

#### Pipeline 架构 (pipeline.py)

```python
class Stage(ABC):
    name: str
    def execute(self, ctx: PipelineContext) -> None
    def should_skip(self, ctx: PipelineContext) -> bool

class TranslationStage(Stage)
class SummaryStage(Stage)
class ImageGenerationStage(Stage)
class CopywritingStage(Stage)
class PublishStage(Stage)
```

**优点**：
- 清晰的 Stage 抽象，每个阶段职责单一
- 支持跳过机制，灵活性高
- PipelineContext 统一管理状态

**问题**：
- `ImageExtractionStage` 被标记为"已禁用"但仍存在于构建中
- Stage 之间耦合在 `build_pipeline()` 硬编码

#### 数据库层 (database.py + models.py)

**数据模型**：
```
Book (1) ──── (1) BookOutput
       │
       └────── (*) ProcessingLog
       │
       └────── (*) TokenUsage
       │
       └────── (*) ShareLink
       │
       └────── (*) TranslationCache
```

**优点**：
- SQLAlchemy ORM 抽象，类型安全
- 迁移机制 `_migrate_database()` 支持字段扩展
- Token 消耗统计完整

**问题**：
- 全局单例 `_db_engine` 管理不够清晰
- 每个方法都创建新 session，频繁开关
- `TranslationCache` 表已存在但 `translation_processor.py` 似乎未充分使用

#### 质量检查器 (quality_checker.py)

8 维度质检，纯规则实现，零 API 成本：
- `CompletenessChecker` - 翻译完整性
- `FidelityChecker` - 忠实度
- `FluencyChecker` - 流畅度
- `ConsistencyChecker` - 一致性
- `FormatChecker` - 格式规范
- `TerminologyChecker` - 术语一致性
- `Cultural适应性Checker`
- `PDFTOCLinksChecker` - PDF 目录链接

**优点**：无 API 调用成本，可离线运行

### 2.2 ebook_translator/ - 翻译模块（独立子项目）

```
ebook_translator/
├── library.py           # 对外 API (translate_epub)
├── translator/          # 核心翻译引擎
│   ├── epub_parser.py  # EPUB 解析
│   ├── translator.py   # 翻译逻辑
│   └── cache.py        # 缓存管理
├── epub_generator.py   # EPUB 生成
└── pdf_converter.py    # PDF 转换
```

**设计亮点**：
- 可独立运行：`python -m ebook_translator.main <input.epub>`
- `ebook_translator/config.py` 与 `automation/config.py` 分离
- PDF 生成依赖外部 Calibre 工具

### 2.3 各模块职责边界

| 模块 | 职责 | 边界清晰度 |
|------|------|----------|
| `directory_scanner` | 扫描输入目录 | 清晰 |
| `translation_processor` | 调用 ebook_translator | 清晰 |
| `content_summarizer` | 书籍摘要 + PDF | 较清晰（混合了封面提取）|
| `image_generator` | AI 主图生成 | 清晰 |
| `ai_copywriter` | 闲鱼/小红书文案 | 清晰 |
| `xianyu_publisher` | Playwright 自动化发布 | 复杂（31KB）|
| `quality_checker` | 8 维度质检 | 清晰 |

---

## 3. 技术栈评估

### 3.1 技术选型合理性

| 技术 | 选型 | 评估 |
|------|------|------|
| **CLI 框架** | Typer + Rich | ✅ 现代化，体验好 |
| **数据库** | SQLite + SQLAlchemy | ✅ 轻量适合本地，无运维成本 |
| **PDF 生成** | ReportLab + Calibre | ⚠️ 混合方案，Calibre 外部依赖 |
| **AI 调用** | DeepSeek API + MiniMax | ✅ 多 provider 支持 |
| **浏览器自动化** | Playwright | ✅ 现代方案 |
| **图片处理** | Pillow | ✅ 成熟稳定 |

### 3.2 依赖管理

**requirements-automation.txt** 结构清晰，但存在以下问题：
- 外部依赖：Calibre（`ebook-convert`）需手动安装
- `ebook_translator/requirements.txt` 与主 requirements 可能有重复
- 未使用 pip-tools 或 poetry 锁定版本

### 3.3 跨平台兼容性

**已知问题**（来自 CLAUDE.md）：
- Windows + Git Bash 环境
- Playwright/Chrome 路径处理需在 Windows 验证
- `Path(...).stem.strip()` 已防御 EPUB 文件名尾随空格

**进度输出**（progress.py）：
```python
sys.stdout.reconfigure(encoding='utf-8')  # Windows UTF-8 支持
```

---

## 4. 代码质量

### 4.1 关键文件大小与复杂度

| 文件 | 行数 | 复杂度 | 建议 |
|------|------|--------|------|
| `pdf_generator.py` | 1263 | 高 | 考虑拆分为多个模块 |
| `xianyu_publisher.py` | 762 | 高 | 考虑进一步封装 |
| `quality_checker.py` | 711 | 中 | 合理，但缺少集成测试 |
| `main.py` | 820 | 中 | 命令众多，考虑分组 |

### 4.2 异常处理

**现状**：
- 全局异常通过 `phase()` 上下文管理器捕获并输出
- `DatabaseManager` 方法中 `try/finally` 模式统一
- 特定错误类型定义在 `exceptions.py`

**问题**：
- 很多地方 bare `except Exception` 捕获过于宽泛
- 缺少统一的异常层次结构
- 错误信息有时过于简单（`raise Exception("翻译失败")`）

### 4.3 日志与监控

**现状**：
- 使用标准 `logging` 模块
- `progress.py` 提供用户友好的阶段输出
- `ProcessingLog` 表记录详细日志

**问题**：
- 日志级别使用混乱（DEBUG/INFO/WARNING 混用）
- 缺少结构化日志（JSON 格式）用于分析
- Token 消耗有记录但缺少监控告警

---

## 5. 数据流与架构

### 5.1 输入 → 处理 → 输出流程

```
EPUB 文件
    │
    ▼
┌─────────────────┐
│ directory_scanner │ → Book 记录 (status=pending)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ translation      │ → bilingual_epub, chinese_epub, pdf
│ (ebook_translator)│   + TokenUsage
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ content_summarizer │ → summary_pdf, summary_text
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ image_generator  │ → main_images, cover_image
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ai_copywriter    │ → xianyu_title, xianyu_description
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ xianyu_publisher │ → 发布到闲鱼
└─────────────────┘
    │
    ▼
BookOutput (publish_status=published)
```

### 5.2 数据库设计

**Book 状态机**：
```
pending → processing → completed → published
                      ↘ failed
```

**BookOutput 冗余设计**：
- 所有输出文件路径存在 `book_outputs` 表
- `quality_report` JSON 存储在 `Text` 字段
- 缺少输出文件存在性校验

### 5.3 缓存策略

**TranslationCache**：
- 基于段落 MD5 哈希查重
- 首次运行自动迁移旧 `translation_cache.json`
- **问题**：ebook_translator 内部缓存与 automation 层缓存可能不同步

---

## 6. 可改进点

### 6.1 架构层面优化建议

#### 1. 依赖注入改进
**现状**：`DatabaseManager` 在每个 Stage `__init__` 中创建
```python
class Stage(ABC):
    def __init__(self):
        self.db = DatabaseManager()  # 紧耦合
```

**建议**：通过构造函数注入共享数据库连接

#### 2. 配置管理统一
**现状**：
- `automation/config.py` - Config 单例
- `ebook_translator/config.py` - DEEPSEEK_API_KEY
- `config.yaml` - 主配置

**建议**：合并为统一的配置层，避免 API Key 两处配置

#### 3. Pipeline Stage 动态注册
**现状**：`build_pipeline()` 硬编码阶段顺序

**建议**：支持配置驱动的阶段编排

### 6.2 潜在风险

| 风险 | 级别 | 描述 |
|------|------|------|
| Calibre 外部依赖 | 中 | PDF 转换依赖 `ebook-convert`，需单独安装 |
| API Key 暴露 | 高 | config.yaml 中明文存储 API Key |
| 大文件处理 | 中 | 74KB 的 pdf_generator.py 可能内存压力大 |
| Session 频繁创建 | 低 | 每个 DB 方法都创建/关闭 session |

### 6.3 扩展性考虑

#### 短期可扩展性
- **多 AI Provider**：已支持 DeepSeek + MiniMax，易于扩展
- **多平台发布**：架构支持添加其他发布渠道
- **质量检查维度**：8 维度设计，可继续扩展

#### 长期扩展考虑
- **微服务拆分**：翻译、摘要、发布可拆分为独立服务
- **消息队列**：当前同步流水线，可引入 Celery/RQ
- **分布式缓存**：TranslationCache 可迁移到 Redis

### 6.4 测试覆盖

**现状**：
- `tests/unit/` - 单元测试
- `tests/integration/` - 集成测试
- `tests/e2e/` - E2E 测试（新增）

**覆盖率缺口**：
- `xianyu_publisher.py` 缺少自动化测试（依赖 Playwright）
- `pdf_generator.py` 缺少单元测试
- 缺少性能/压力测试

---

## 7. 总结评分

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| **架构设计** | 4 | Pipeline 模式清晰，Stage 抽象合理 |
| **代码组织** | 3.5 | 模块划分清晰，但部分文件过大 |
| **技术选型** | 4 | 现代化技术栈，适合场景 |
| **可维护性** | 3.5 | 缺少依赖注入，配置分散 |
| **可测试性** | 3 | 有测试但覆盖率不足 |
| **扩展性** | 4 | 多 AI Provider、多平台支持 |
| **健壮性** | 3.5 | 异常处理较粗糙，缺少统一错误类型 |
| **文档** | 4 | README/CLAUDE.md/PRD 齐全 |

**综合评分：3.8/5**

---

## 8. Pipeline 架构未被使用问题（新增）

### 8.1 问题描述

`pipeline.py` 定义了完整的 Pipeline + Stage 架构，但 `main.py` 的所有命令（包括核心的 `auto` 命令）都直接调用各模块函数，完全绕过了 Pipeline 架构。

**架构设计形同虚设**：
- `pipeline.py` 定义了 6 个 Stage：`TranslationStage`、`SummaryStage`、`ImageGenerationStage`、`ImageExtractionStage`（已禁用）、`CopywritingStage`、`PublishStage`
- `main.py` 的 `auto` 命令手动按顺序调用：`scan_input_directory` -> `translate_book` -> `generate_summary` -> `generate_main_image` -> `generate_copywriting` -> `publish_to_xianyu`
- `process` 命令同样直接调用各函数，不经过 Pipeline

### 8.2 根因分析

| 因素 | 分析 |
|------|------|
| **设计时序问题** | Pipeline 架构是后来引入的，但 main.py 已经稳定运行，未重构 |
| **功能不一致** | `TranslationStage.execute()` 调用 `translate_book()`，但参数签名与 Stage 设计不完全匹配 |
| **skip 参数处理** | Pipeline 用 `ctx.skip_*` 控制跳过，但 main.py 用 `if not skip_*` 条件判断 |
| **上下文传递** | Pipeline 用 `PipelineContext` 在 Stage 间共享数据，但 main.py 直接从 `DatabaseManager` 读取 |
| **Stage 内部耦合** | 每个 Stage 在 `__init__` 中创建 `DatabaseManager()` 单例，违反了依赖注入原则 |

### 8.3 具体差异对比

**Pipeline 架构设计的执行流程**：
```
run_pipeline(ctx)
  -> Pipeline.run(ctx)
    -> for stage in stages:
         -> stage.should_skip(ctx)  # 检查 ctx.skip_*
         -> stage.execute(ctx)       # 执行阶段
         -> stage.on_error(ctx, e)   # 错误处理
```

**main.py auto 命令的实际执行流程**：
```
for book in books:
  -> scan_input_directory()           # 不经过 Stage
  -> db.create_book()                 # 直接调用
  -> translate_book()                 # 阶段1，手动 with phase()
  -> generate_summary()               # 阶段2，手动 with phase()
  -> generate_main_image()            # 阶段3，手动 with phase()
  -> generate_copywriting()           # 阶段4，手动 with phase()
  -> publish_to_xianyu()              # 阶段5，手动 with phase()
```

**关键差异**：
1. Pipeline 用 `ctx.skip_*` 属性控制跳过，main.py 用 `if not skip_*` 条件判断
2. Pipeline 用 `PipelineContext` 传递数据，main.py 用 `DatabaseManager` 查询
3. Pipeline 用 `stage.on_error()` 统一错误处理，main.py 用 `try/except` 块
4. Pipeline 的 `TranslationStage` 接收 `skip_cache` 参数，但实际调用时参数传递不一致

### 8.4 ImageExtractionStage 问题

```python
# pipeline.py 第 160-169 行
class ImageExtractionStage(Stage):
    """图片提取阶段 - 已禁用（封面提取已移至 summarizer）"""

    name = "image_extraction"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return True  # 始终跳过

    def execute(self, ctx: PipelineContext) -> None:
        logger.info(f"[{self.name}] 图片提取已禁用，跳过: {ctx.book_id}")
```

**问题**：
- 已禁用的 Stage 仍然在 `build_pipeline()` 中被添加到 stages 列表
- 虽然 `should_skip()` 返回 True，但代码冗余
- Stage 注释说"封面提取已移至 summarizer"，但未从 pipeline 中移除

### 8.5 迁移路径建议

#### Phase 1: 清理 Pipeline 架构
1. 从 `build_pipeline()` 中移除 `ImageExtractionStage`
2. 统一样的 skip 逻辑：`should_skip()` 检查 `ctx.skip_*` 属性
3. 清理 `PipelineContext`，移除不再使用的字段

#### Phase 2: 重构 main.py 使用 Pipeline
```python
# main.py auto 命令重构后
from automation.pipeline import run_pipeline

@app.command()
def auto(
    skip_publish: bool = typer.Option(False, help="跳过发布步骤"),
    skip_translate: bool = typer.Option(False, help="跳过翻译步骤"),
    skip_summarize: bool = typer.Option(False, help="跳过生成精简版"),
    skip_images: bool = typer.Option(False, help="跳过图片提取"),
    skip_copywriting: bool = typer.Option(False, help="跳过文案生成"),
    skip_cache: bool = typer.Option(False, help="跳过翻译缓存，强制重新翻译"),
):
    books = scan_input_directory()
    for book in books:
        ctx = run_pipeline(
            book_id=book['id'],
            epub_path=str(Path(config.input_dir) / book['filename']),
            filename=book['filename'],
            title=book.get('title', ''),
            author=book.get('author', ''),
            skip_translate=skip_translate,
            skip_summarize=skip_summarize,
            skip_images=skip_images,
            skip_copywriting=skip_copywriting,
            skip_publish=skip_publish,
            skip_cache=skip_cache,
        )
        # 处理 ctx.status, ctx.error
```

#### Phase 3: 完善 Stage 实现
1. 所有 Stage 的数据读写都通过 `PipelineContext`，不再直接查询数据库
2. Stage 之间通过 context 传递中间结果
3. 统一的错误处理和日志记录

---

## 9. 模块耦合问题（新增）

### 9.1 DatabaseManager 单例滥用

```python
# pipeline.py 第 52-53 行
class Stage(ABC):
    def __init__(self):
        self.db = DatabaseManager()  # 每个 Stage 都创建新实例
```

**问题**：
- 每个 Stage 在 `__init__` 中创建 `DatabaseManager()`，虽然 DatabaseManager 是单例，但紧耦合
- Stage 无法独立单元测试（必须要有数据库）
- 数据库连接在每个 Stage 中独立管理，无法统一事务

### 9.2 main.py 直接导入问题

```python
# main.py 大量直接导入
from automation.database import DatabaseManager
from automation.directory_scanner import scan_input_directory
from automation.summarizer import generate_summary
from automation.publishing import generate_copywriting
from automation.translation import translate_book
from automation.publishing import publish_to_xianyu
from automation.image import generate_main_image
```

**问题**：
- `main.py` 是业务组装层，直接导入并调用各模块函数
- 各模块函数签名不一致，有的返回 bool，有的返回路径，有的返回字典
- 缺乏统一的接口抽象

### 9.3 ebook_translator 耦合问题

```
automation/              ebook_translator/
    │                         │
    ├── translation/          ├── library.py
    │   └── translation_processor.py
    │           │                   │
    └───────────┴───────────────────┘
                    │调用
```

**问题**：
- `automation/translation/translation_processor.py` 调用 `ebook_translator/library.py`
- 但 `ebook_translator/config.py` 独立配置 API Key
- 两处 config.py 维护两套 API Key 配置

---

## 10. 配置分散问题（新增）

### 10.1 双配置系统

| 配置位置 | 内容 | API Key |
|----------|------|---------|
| `automation/config.py` | Config 单例类，读取 config.yaml | `config.yaml` 中的 `ai.api_key` |
| `ebook_translator/config.py` | 模块级变量 DEEPSEEK_API_KEY | 环境变量 `DEEPSEEK_API_KEY` |

### 10.2 API Key 两处配置

**config.yaml**（主流程使用）：
```yaml
ai:
  provider: deepseek
  api_key: "your-api-key-here"  # 手动填入
```

**ebook_translator/config.py**（standalone 模式使用）：
```python
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
```

**问题**：
- 主流程通过 `automation/config.py` -> `config.yaml` 读取 api_key
- standalone 翻译器通过环境变量读取
- 容易造成 API Key 不一致的困惑

### 10.3 配置加载时机

```python
# automation/config.py
config = Config()  # 模块加载时立即实例化

# ebook_translator/config.py
PDF_CONFIG = load_pdf_config()  # 模块加载时执行
```

**问题**：
- 配置在模块导入时就加载，无法动态重载
- `ebook_translator/config.py` 加载时使用 `os.getcwd()`，依赖当前工作目录
- 测试时无法轻易 mock 配置

---

## 11. 异常处理不统一问题（新增）

### 11.1 异常处理模式混乱

```python
# main.py auto 命令
try:
    if not skip_translate:
        with phase("翻译并生成 PDF"):
            if not translate_book(...):
                raise Exception("翻译失败")  # 手动抛异常
except Exception as e:
    db.update_book_status(book_id, "failed", str(e))
    console.print(f"[bold red]✗ {title} 处理失败: {e}[/bold red]")
```

```python
# pipeline.py Stage.on_error()
def on_error(self, ctx: PipelineContext, exc: Exception) -> None:
    ctx.error = str(exc)
    ctx.status = "failed"
    logger.error(f"[{self.name}] 阶段失败: {exc}")
```

**问题**：
- main.py 用 `if not success: raise Exception()` 模式检查结果
- Pipeline 用异常传播机制
- 两种模式混用导致错误处理路径不一致

### 11.2 缺少统一异常类型

```python
# 大量 bare raise
raise Exception("翻译失败")
raise RuntimeError("发布失败")
```

**问题**：
- 没有定义项目专用的异常类层次结构
- 无法区分可重试错误和不可重试错误
- `exceptions.py` 存在但未被充分利用

### 11.3 phase() 上下文管理器的作用

```python
# progress.py
@contextmanager
def phase(name: str):
    print(f"{indent}⏳ 正在{name}...")
    try:
        yield
        print(f"{indent}✓ {name}完成 ({_format_duration(elapsed)})")
    except Exception as e:
        print(f"{indent}✗ {name}失败: {type(e).__name__}: {str(e)[:200]}")
        raise
```

**作用**：
- 为用户提供阶段执行的视觉反馈
- 捕获异常并输出友好错误信息
- 但不负责错误恢复或状态回滚

---

## 12. 架构问题优先级排序与解决方案

### 12.1 问题优先级矩阵

| 优先级 | 问题 | 影响 | 修复成本 |
|--------|------|------|----------|
| P0 | Pipeline 架构未被使用 | 架构设计形同虚设，技术债务 | 高 |
| P0 | API Key 两处配置 | 配置混乱，易出错 | 中 |
| P1 | DatabaseManager 单例滥用 | 测试困难，紧耦合 | 高 |
| P1 | 异常处理不统一 | 错误处理路径混乱 | 中 |
| P2 | ImageExtractionStage 残留 | 代码冗余 | 低 |
| P2 | Stage 间数据传递混乱 | PipelineContext 字段过多 | 中 |
| P3 | 配置加载时机固定 | 无法动态重载 | 低 |

### 12.2 解决方案详细说明

#### P0-1: 将 main.py 迁移到使用 Pipeline

**目标**：让 `auto` 和 `process` 命令通过 `run_pipeline()` 执行

**步骤**：
1. 清理 `ImageExtractionStage`，从 `build_pipeline()` 移除
2. 统一 skip 逻辑：所有 Stage 的 `should_skip()` 检查 `ctx.skip_*` 属性
3. 完善 `PipelineContext` 字段定义
4. 重构 `TranslationStage`、`SummaryStage` 等，使数据读写通过 context
5. 修改 `auto` 命令使用 `run_pipeline()`
6. 修改 `process` 命令使用 `run_pipeline()`

**验收标准**：
- `python -m automation.main auto --skip-publish` 能正常运行
- `python -m automation.main process <book_id>` 能正常运行

#### P0-2: 统一 API Key 配置

**目标**：消除 `ebook_translator/config.py` 的独立 API Key 配置

**步骤**：
1. 修改 `ebook_translator/config.py`，优先从环境变量读取，fallback 到 `automation/config.py` 读取
2. 或者：统一使用 `automation/config` 的 `ai.api_key`
3. 更新 `ebook_translator/library.py`，调用 `automation/config` 而非自己的配置

#### P1-1: 依赖注入改进

**目标**：让 Stage 可以独立测试

**步骤**：
1. 为 `Stage` 添加 `db: DatabaseManager` 构造函数参数
2. `Pipeline` 在构建时注入共享的 `DatabaseManager` 实例
3. 测试时传入 mock 的 DatabaseManager

**重构后**：
```python
class Stage(ABC):
    name: str = "base"

    def __init__(self, db: DatabaseManager):
        self.db = db

class TranslationStage(Stage):
    def __init__(self, db: DatabaseManager, skip_cache: bool = False):
        super().__init__(db)
        self.skip_cache = skip_cache
```

#### P1-2: 统一异常类型

**目标**：建立项目专用的异常层次结构

**步骤**：
1. 在 `automation/exceptions.py` 定义异常类
2. 用自定义异常替换 bare `raise Exception()`

**示例**：
```python
class PipelineError(Exception):
    """流水线执行错误"""
    pass

class TranslationError(PipelineError):
    """翻译阶段错误"""
    pass

class PublishError(PipelineError):
    """发布阶段错误"""
    pass
```

---

## 附录：关键文件路径

```
D:\project\bookfile_bat\
├── automation/
│   ├── main.py                    # CLI 入口 (820 行)
│   ├── pipeline.py               # Pipeline 架构 (307 行)
│   ├── database.py               # 数据库管理 (442 行)
│   ├── models.py                 # 数据模型 (165 行)
│   ├── config.py                 # 配置单例 (256 行)
│   ├── quality_checker.py        # 质量检查 (711 行)
│   ├── progress.py               # 进度输出 (98 行)
│   ├── translation/              # 翻译模块
│   ├── summarizer/               # 摘要模块
│   ├── publishing/               # 发布模块
│   └── image/                    # 图片模块
├── ebook_translator/
│   ├── library.py                # 翻译库接口 (300 行)
│   └── translator/               # 核心翻译引擎
├── config.yaml                   # 主配置文件
├── requirements-automation.txt   # 依赖清单
└── tests/                        # 测试目录
```
