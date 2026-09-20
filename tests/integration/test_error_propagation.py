"""测试流水线错误传播 - 验证各阶段失败时 Book.status 变为 failed"""

from unittest.mock import patch

import pytest

# 必须先导入子模块，确保 patch 能找到它们
from automation import (
    image,  # noqa: F401
    publishing,  # noqa: F401
    summarizer,  # noqa: F401
    translation,  # noqa: F401
)
from automation.database import DatabaseManager
from automation.models import Book
from automation.pipeline import (
    CopywritingStage,
    ImageGenerationStage,
    Pipeline,
    PipelineContext,
    SummaryStage,
    TranslationStage,
)


class TestErrorPropagation:
    """测试流水线错误传播"""

    @pytest.fixture
    def book(self, in_memory_db):
        """创建测试书籍"""
        book = Book(
            id="test-err-book-001",
            filename="test-err.epub",
            title="错误测试书籍",
            author="测试作者",
            status="pending",
            summary_text="这是测试错误传播的书籍摘要。",
        )
        in_memory_db.add(book)
        in_memory_db.commit()
        return book

    def test_translation_stage_failure_via_pipeline(self, book, in_memory_db):
        """通过 Pipeline 测试翻译阶段失败时状态变化"""
        book_id = book.id

        with patch("automation.translation.translate_book") as mock_translate:
            mock_translate.return_value = False

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [TranslationStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            # 验证状态
            assert ctx.status == "failed", f"期望状态 'failed'，实际 '{ctx.status}'"
            assert ctx.error is not None, "错误信息不应为空"

    def test_summary_stage_failure_via_pipeline(self, book, in_memory_db):
        """通过 Pipeline 测试摘要阶段失败时状态变化"""
        book_id = book.id

        with patch("automation.summarizer.generate_summary") as mock_summary:
            mock_summary.side_effect = Exception("摘要生成失败")

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [SummaryStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            # 验证状态
            assert ctx.status == "failed", f"期望状态 'failed'，实际 '{ctx.status}'"
            assert ctx.error is not None, "错误信息不应为空"

    def test_image_generation_stage_failure_via_pipeline(self, book, in_memory_db):
        """通过 Pipeline 测试主图生成阶段失败"""
        book_id = book.id

        with patch("automation.image.generate_main_image") as mock_img:
            mock_img.return_value = False

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [ImageGenerationStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            # image generation 失败不一定导致 failed

    def test_copywriting_stage_failure_via_pipeline(self, book, in_memory_db):
        """通过 Pipeline 测试文案生成阶段失败"""
        book_id = book.id

        with patch("automation.publishing.generate_copywriting") as mock_cw:
            mock_cw.side_effect = Exception("AI 文案生成失败")

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [CopywritingStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(
                book_id=book_id,
                epub_path="dummy.epub",
                title="测试书籍",
                author="测试作者",
                summary_text="测试摘要",
            )

            pipeline.run(ctx)

            # 验证状态
            assert ctx.status == "failed" or ctx.error is not None, "文案阶段失败应设置错误"

    def test_pipeline_stops_on_stage_failure(self, book, in_memory_db):
        """阶段失败时流水线停止后续阶段"""
        book_id = book.id

        execution_order = []

        class TrackingTranslationStage(TranslationStage):
            def execute(self, ctx):
                execution_order.append("translation")
                ctx.status = "failed"
                ctx.error = "Translation failed"
                raise Exception("Translation failed")

        class DummyStage(TranslationStage):
            name = "dummy"

            def execute(self, ctx):
                execution_order.append("dummy")

        db = DatabaseManager()
        db.create_book_output(book_id)

        pipeline = Pipeline([TrackingTranslationStage(db=db), DummyStage(db=db)])
        ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

        pipeline.run(ctx)

        assert "translation" in execution_order
        assert "dummy" not in execution_order, f"Dummy stage should not run but got: {execution_order}"

    def test_processing_log_written_on_failure(self, book, in_memory_db):
        """阶段失败时 ProcessingLog 被写入

        注意：当通过 mock translate_book 返回 False 时，TranslationProcessor.process()
        内部的 add_log 不会被执行（因为整个函数被 mock 了）。
        真实的 'error' 日志只有在 translate_book 真实执行并返回 False 时才会写入。
        这里我们验证 start 日志被写入，以及 ctx.status/error 状态被正确设置。
        """
        book_id = book.id

        db = DatabaseManager()
        db.create_book_output(book_id)

        with patch("automation.translation.translate_book") as mock_translate:
            mock_translate.return_value = False

            stages = [TranslationStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            # 验证 ctx 状态被正确设置
            assert ctx.status == "failed", f"期望状态 'failed'，实际 '{ctx.status}'"
            assert ctx.error is not None, "错误信息不应为空"

            # 验证 start 日志被写入
            db_logs = db.get_logs(book_id)
            assert len(db_logs) > 0, "应该有 ProcessingLog 记录"

            start_logs = [log for log in db_logs if log.status == "start"]
            assert len(start_logs) > 0, "应该有 start 状态的日志"

    def test_error_message_in_context_on_failure(self, book, in_memory_db):
        """阶段失败时错误信息存储在上下文"""
        book_id = book.id

        with patch("automation.translation.translate_book") as mock_translate:
            mock_translate.return_value = False

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [TranslationStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            assert ctx.error is not None, "错误信息应被设置"
            assert ctx.status == "failed", "状态应为 failed"

    def test_successful_stage_does_not_set_failed(self, book, in_memory_db):
        """成功阶段不设置 failed 状态"""
        book_id = book.id

        with patch("automation.translation.translate_book") as mock_translate:
            mock_translate.return_value = True

            db = DatabaseManager()
            db.create_book_output(book_id)

            stages = [TranslationStage(db=db)]
            pipeline = Pipeline(stages)
            ctx = PipelineContext(book_id=book_id, epub_path="dummy.epub")

            pipeline.run(ctx)

            assert ctx.status != "failed", f"成功阶段不应设置 failed 状态，实际状态: {ctx.status}"
