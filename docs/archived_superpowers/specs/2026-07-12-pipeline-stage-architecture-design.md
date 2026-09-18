# Pipeline/Stage 架构重构设计方案

## 背景

当前 `main.py` 中的 `auto` 和 `process` 命令是 **135 行的巨型函数**，直接实例化所有模块并顺序调用，导致：
- 单元测试无法对单个阶段进行 mock
- 阶段间耦合紧密，难以独立运行或跳过
- 错误处理逻辑散落在主流程中

## 目标

引入 **Pipeline + Stage** 模式，将线性流程拆分为独立、可组合的阶段。

## 设计

### 1. PipelineContext

所有阶段共享的上下文对象，负责阶段间数据传递：

```python
class PipelineContext:
    book_id: str
    epub_path: str
    # 输入信息（由调用方填充）
    filename: str
    title: str
    author: str
    # 各阶段输出（由阶段填充）
    translation_result: dict = {}
    summary_text: str = ""
    summary_pdf: str = ""
    main_images: List[str] = []
    cover_image: str = ""
    toc_preview: str = ""
    xianyu_description: str = ""
    xiaohongshu_note: str = ""
    # 状态
    status: str = "pending"
    error: Optional[str] = None
```

### 2. Stage 抽象

```python
class Stage(ABC):
    name: str  # 阶段名称

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> None:
        """执行阶段逻辑"""
        pass

    def should_skip(self, ctx: PipelineContext) -> bool:
        """是否跳过此阶段（默认 False）"""
        return False

    def on_error(self, ctx: PipelineContext, exc: Exception) -> None:
        """阶段出错时的处理（可重写）"""
        ctx.error = str(exc)
```

### 3. 五个阶段实现

| 阶段 | 类名 | 跳过条件 |
|------|------|---------|
| 翻译 | `TranslationStage` | `skip_translate=True` |
| 精简版 | `SummaryStage` | `skip_summarize=True` |
| 主图 | `ImageGenerationStage` | `skip_images=True` |
| 提取图片 | `ImageExtractionStage` | `skip_images=True` |
| 文案 | `CopywritingStage` | `skip_copywriting=True` |
| 发布 | `PublishStage` | `skip_publish=True` |

### 4. Pipeline 编排器

```python
class Pipeline:
    def __init__(self, stages: List[Stage]):
        self.stages = stages

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """顺序执行所有阶段"""
        for stage in self.stages:
            if stage.should_skip(ctx):
                continue
            try:
                stage.execute(ctx)
            except Exception as e:
                stage.on_error(ctx, e)
                if ctx.status == "failed":
                    break
        return ctx
```

### 5. 单元测试优势

```python
# 之前（难以测试）
# main.py 直接调用 translate_book()，无法 mock 数据库

# 之后（易于测试）
def test_translation_stage():
    ctx = PipelineContext(book_id="123", epub_path="test.epub")
    stage = TranslationStage(skip_cache=False)
    stage.execute(ctx)
    assert ctx.translation_result["bilingual_epub"] is not None
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `automation/pipeline.py` | **新增** - PipelineContext + Pipeline + 所有 Stage 类 |
| `automation/main.py` | 重构 `auto` / `process` / `test` 命令使用 Pipeline |

## 实施步骤

1. 创建 `automation/pipeline.py`，实现 `PipelineContext` + `Pipeline` + 所有 `Stage`
2. 创建 `automation/stages/` 目录，将各阶段代码迁移到独立文件
3. 重构 `main.py` 的 `auto` / `process` / `test` 命令
4. 确保向后兼容：保留所有 CLI 参数（`--skip-*`）
5. 运行测试确保无回归

## 风险

- 阶段拆分可能破坏现有的隐式依赖
- 阶段间共享状态需要 `PipelineContext` 设计清晰
- 闲鱼发布（Playwright）阶段较为脆弱，拆分需谨慎