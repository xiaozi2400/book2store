"""
Pipeline/Stage 架构 - 将线性流程拆分为独立、可测试的阶段
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

from automation.config import config
from automation.database import DatabaseManager
from automation.utils import logger


@dataclass
class PipelineContext:
    """流水线上下文 - 所有阶段共享的数据容器"""
    book_id: str
    epub_path: str
    filename: str = ""
    title: str = ""
    author: str = ""
    summary_text: str = ""

    # 各阶段输出（由阶段填充）
    translation_result: Dict[str, Any] = field(default_factory=dict)
    summary_pdf: str = ""
    main_images: List[str] = field(default_factory=list)
    main_image_count: int = 0
    cover_image: str = ""
    toc_preview: str = ""
    xianyu_description: str = ""
    xiaohongshu_note: str = ""

    # 状态
    status: str = "pending"
    error: Optional[str] = None

    # 跳过选项
    skip_translate: bool = False
    skip_summarize: bool = False
    skip_images: bool = False
    skip_copywriting: bool = False
    skip_publish: bool = False
    skip_cache: bool = False


class Stage(ABC):
    """阶段抽象基类"""

    name: str = "base"

    def __init__(self):
        self.db = DatabaseManager()

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> None:
        """执行阶段逻辑"""
        pass

    def should_skip(self, ctx: PipelineContext) -> bool:
        """是否跳过此阶段"""
        return False

    def on_error(self, ctx: PipelineContext, exc: Exception) -> None:
        """阶段出错时的处理"""
        ctx.error = str(exc)
        ctx.status = "failed"
        logger.error(f"[{self.name}] 阶段失败: {exc}")


class TranslationStage(Stage):
    """翻译阶段 - 调用 ebook_translator 翻译 EPUB 并生成 PDF"""

    name = "translation"

    def __init__(self, skip_cache: bool = False):
        super().__init__()
        self.skip_cache = skip_cache

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_translate

    def execute(self, ctx: PipelineContext) -> None:
        from automation.translation import translate_book

        logger.info(f"[{self.name}] 开始翻译: {ctx.book_id}")
        self.db.update_book_status(ctx.book_id, "translating")
        self.db.add_log(ctx.book_id, "translating", "start", "开始翻译")

        success = translate_book(ctx.book_id, ctx.epub_path, skip_cache=self.skip_cache or ctx.skip_cache)

        if not success:
            raise RuntimeError("翻译失败")

        # 获取翻译结果
        output = self.db.get_book_output(ctx.book_id)
        if output:
            ctx.translation_result = {
                "bilingual_epub": output.bilingual_epub,
                "chinese_epub": output.chinese_epub,
                "bilingual_pdf": output.bilingual_pdf,
                "chinese_pdf": output.chinese_pdf,
                "english_pdf": output.english_pdf,
            }

        self.db.add_log(ctx.book_id, "translating", "success", "翻译完成")
        logger.info(f"[{self.name}] 翻译完成: {ctx.book_id}")


class SummaryStage(Stage):
    """精简版生成阶段 - 生成书籍摘要和精简版 PDF"""

    name = "summarize"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_summarize

    def execute(self, ctx: PipelineContext) -> None:
        from automation.content_summarizer import generate_summary

        logger.info(f"[{self.name}] 开始生成精简版: {ctx.book_id}")
        self.db.update_book_status(ctx.book_id, "summarizing")
        self.db.add_log(ctx.book_id, "summarizing", "start", "开始生成精简版")

        summary_pdf = generate_summary(ctx.book_id, ctx.epub_path)

        if summary_pdf:
            ctx.summary_pdf = summary_pdf
            # 更新数据库中的 summary_text
            book = self.db.get_book_by_id(ctx.book_id)
            if book and book.summary_text:
                ctx.summary_text = book.summary_text

        self.db.add_log(ctx.book_id, "summarizing", "success", "精简版生成完成")
        logger.info(f"[{self.name}] 精简版生成完成: {ctx.book_id}")


class ImageGenerationStage(Stage):
    """主图生成阶段 - AI 生成商品主图"""

    name = "image_generation"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_images

    def execute(self, ctx: PipelineContext) -> None:
        from automation.image_generator import generate_main_image

        logger.info(f"[{self.name}] 开始生成主图: {ctx.book_id}")
        self.db.update_book_status(ctx.book_id, "generating_images")
        self.db.add_log(ctx.book_id, "generating_images", "start", "开始生成主图")

        image_count = generate_main_image(ctx.book_id)
        ctx.main_image_count = image_count or 0

        self.db.add_log(ctx.book_id, "generating_images", "success", f"生成 {ctx.main_image_count} 张主图")
        logger.info(f"[{self.name}] 主图生成完成: {ctx.book_id}, 数量: {ctx.main_image_count}")


class ImageExtractionStage(Stage):
    """图片提取阶段 - 从 EPUB 提取封面和目录预览图"""

    name = "image_extraction"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_images

    def execute(self, ctx: PipelineContext) -> None:
        from automation.image_extractor import extract_images

        logger.info(f"[{self.name}] 开始提取图片: {ctx.book_id}")
        self.db.add_log(ctx.book_id, "extracting", "start", "开始提取图片")

        # 构建 PDF 路径
        base_name = Path(ctx.epub_path).stem.strip()
        pdf_path = Path(config.output_dir) / base_name / "PDF" / f"中英双语-{base_name}.pdf"
        pdf_path_str = str(pdf_path) if pdf_path.exists() else None

        extract_images(ctx.book_id, ctx.epub_path, pdf_path_str)

        # 获取结果
        output = self.db.get_book_output(ctx.book_id)
        if output:
            ctx.cover_image = output.cover_image or ""
            ctx.toc_preview = output.toc_preview_image or ""

        self.db.add_log(ctx.book_id, "extracting", "success", "图片提取完成")
        logger.info(f"[{self.name}] 图片提取完成: {ctx.book_id}")


class CopywritingStage(Stage):
    """文案生成阶段 - 生成闲鱼文案和小红书笔记"""

    name = "copywriting"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_copywriting

    def execute(self, ctx: PipelineContext) -> None:
        from automation.ai_copywriter import generate_copywriting

        logger.info(f"[{self.name}] 开始生成文案: {ctx.book_id}")
        self.db.update_book_status(ctx.book_id, "copywriting")
        self.db.add_log(ctx.book_id, "copywriting", "start", "开始生成文案")

        generate_copywriting(ctx.book_id, {
            'title': ctx.title,
            'author': ctx.author,
            'summary': ctx.summary_text or ''
        })

        self.db.add_log(ctx.book_id, "copywriting", "success", "文案生成完成")
        logger.info(f"[{self.name}] 文案生成完成: {ctx.book_id}")


class PublishStage(Stage):
    """发布阶段 - 发布到闲鱼"""

    name = "publish"

    def should_skip(self, ctx: PipelineContext) -> bool:
        return ctx.skip_publish

    def execute(self, ctx: PipelineContext) -> None:
        from automation.xianyu_publisher import publish_to_xianyu

        logger.info(f"[{self.name}] 开始发布: {ctx.book_id}")
        self.db.update_book_status(ctx.book_id, "publishing")
        self.db.add_log(ctx.book_id, "publishing", "start", "开始发布到闲鱼")

        success = publish_to_xianyu(ctx.book_id)

        if not success:
            raise RuntimeError("发布失败")

        self.db.update_book_status(ctx.book_id, "published")
        self.db.add_log(ctx.book_id, "publishing", "success", "发布成功")
        logger.info(f"[{self.name}] 发布成功: {ctx.book_id}")


class Pipeline:
    """流水线编排器"""

    def __init__(self, stages: List[Stage]):
        self.stages = stages

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """顺序执行所有阶段，返回最终的上下文"""
        for stage in self.stages:
            if stage.should_skip(ctx):
                logger.info(f"[{stage.name}] 跳过")
                continue

            try:
                stage.execute(ctx)
            except Exception as e:
                stage.on_error(ctx, e)
                # 如果是严重错误，可以选择停止
                if ctx.status == "failed":
                    break

        return ctx


def build_pipeline(
    skip_translate: bool = False,
    skip_summarize: bool = False,
    skip_images: bool = False,
    skip_copywriting: bool = False,
    skip_publish: bool = False,
    skip_cache: bool = False,
) -> Pipeline:
    """构建流水线实例"""
    stages = [
        TranslationStage(skip_cache=skip_cache),
        SummaryStage(),
        ImageGenerationStage(),
        ImageExtractionStage(),
        CopywritingStage(),
        PublishStage(),
    ]

    # 注意：实际的跳过逻辑在 Stage.should_skip() 中通过 ctx 参数判断
    # 这里传入的 skip_* 参数会设置到 ctx 中
    return Pipeline(stages)


def run_pipeline(
    book_id: str,
    epub_path: str,
    filename: str = "",
    title: str = "",
    author: str = "",
    skip_translate: bool = False,
    skip_summarize: bool = False,
    skip_images: bool = False,
    skip_copywriting: bool = False,
    skip_publish: bool = False,
    skip_cache: bool = False,
) -> PipelineContext:
    """便捷函数：创建上下文并运行流水线"""
    ctx = PipelineContext(
        book_id=book_id,
        epub_path=epub_path,
        filename=filename,
        title=title,
        author=author,
        skip_translate=skip_translate,
        skip_summarize=skip_summarize,
        skip_images=skip_images,
        skip_copywriting=skip_copywriting,
        skip_publish=skip_publish,
        skip_cache=skip_cache,
    )

    pipeline = build_pipeline(
        skip_translate=skip_translate,
        skip_summarize=skip_summarize,
        skip_images=skip_images,
        skip_copywriting=skip_copywriting,
        skip_publish=skip_publish,
        skip_cache=skip_cache,
    )

    return pipeline.run(ctx)
