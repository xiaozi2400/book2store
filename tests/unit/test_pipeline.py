"""
Pipeline/Stage 架构单元测试
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.pipeline import (
    PipelineContext, Pipeline, Stage,
    TranslationStage, SummaryStage, ImageGenerationStage,
    ImageExtractionStage, CopywritingStage, PublishStage,
    build_pipeline, run_pipeline
)


class TestPipelineContext:
    """PipelineContext 数据类测试"""

    def test_create_context(self):
        ctx = PipelineContext(
            book_id="test-123",
            epub_path="test.epub",
            filename="test.epub",
            title="Test Book",
            author="Test Author"
        )
        assert ctx.book_id == "test-123"
        assert ctx.epub_path == "test.epub"
        assert ctx.title == "Test Book"
        assert ctx.status == "pending"
        assert ctx.error is None

    def test_default_skip_flags(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub")
        assert ctx.skip_translate is False
        assert ctx.skip_summarize is False
        assert ctx.skip_images is False
        assert ctx.skip_copywriting is False
        assert ctx.skip_publish is False
        assert ctx.skip_cache is False

    def test_translation_result_dict(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub")
        assert ctx.translation_result == {}


class TestBuildPipeline:
    """流水线构建测试"""

    def test_build_pipeline_returns_pipeline(self):
        pipeline = build_pipeline()
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.stages) == 6

    def test_build_pipeline_with_skip_flags(self):
        pipeline = build_pipeline(
            skip_translate=True,
            skip_summarize=True,
            skip_images=True,
            skip_publish=True
        )
        assert isinstance(pipeline, Pipeline)
        # 所有阶段都应该存在，但运行时根据 ctx 决定是否跳过


class TestPipelineRun:
    """流水线执行测试"""

    def test_pipeline_runs_all_stages(self):
        """测试流水线按顺序执行所有阶段"""
        ctx = PipelineContext(
            book_id="test-123",
            epub_path="test.epub",
            skip_publish=True  # 跳过发布避免真实调用
        )

        # Mock 所有阶段
        with patch.multiple(
            'automation.pipeline',
            TranslationStage=MagicMock(),
            SummaryStage=MagicMock(),
            ImageGenerationStage=MagicMock(),
            ImageExtractionStage=MagicMock(),
            CopywritingStage=MagicMock(),
            PublishStage=MagicMock(),
        ) as mocks:
            # 设置 mock 实例
            for name, mock_cls in mocks.items():
                mock_cls.return_value.should_skip.return_value = True  # 跳过避免真实执行

            # 创建 pipeline（手动添加 mock 阶段）
            class MockStage(Stage):
                name = "mock"
                def __init__(self):
                    super().__init__()
                    self.executed = False
                def execute(self, ctx):
                    self.executed = True

            stage1 = MockStage()
            stage1.name = "stage1"
            stage2 = MockStage()
            stage2.name = "stage2"

            pipeline = Pipeline([stage1, stage2])
            pipeline.run(ctx)

            assert stage1.executed is True
            assert stage2.executed is True


class TestStageShouldSkip:
    """阶段跳过逻辑测试"""

    def test_translation_stage_skips_when_flag_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_translate=True)
        stage = TranslationStage()
        assert stage.should_skip(ctx) is True

    def test_translation_stage_runs_when_flag_not_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_translate=False)
        stage = TranslationStage()
        assert stage.should_skip(ctx) is False

    def test_summary_stage_skips_when_flag_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_summarize=True)
        stage = SummaryStage()
        assert stage.should_skip(ctx) is True

    def test_image_stages_skip_when_images_flag_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_images=True)
        gen_stage = ImageGenerationStage()
        extract_stage = ImageExtractionStage()
        assert gen_stage.should_skip(ctx) is True
        assert extract_stage.should_skip(ctx) is True

    def test_copywriting_stage_skips_when_flag_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_copywriting=True)
        stage = CopywritingStage()
        assert stage.should_skip(ctx) is True

    def test_publish_stage_skips_when_flag_set(self):
        ctx = PipelineContext(book_id="test", epub_path="test.epub", skip_publish=True)
        stage = PublishStage()
        assert stage.should_skip(ctx) is True


class TestStageExecution:
    """阶段执行逻辑测试"""

    def test_translation_stage_creates_context_result(self):
        """测试 TranslationStage 执行后填充 context"""
        ctx = PipelineContext(
            book_id="test-123",
            epub_path="test.epub",
            skip_summarize=True,
            skip_images=True,
            skip_copywriting=True,
            skip_publish=True,
        )

        # Mock 数据库和 translate_book（在 translation_processor 模块中）
        mock_output = MagicMock()
        mock_output.bilingual_epub = "/path/to/bilingual.epub"
        mock_output.chinese_epub = "/path/to/chinese.epub"
        mock_output.bilingual_pdf = "/path/to/bilingual.pdf"
        mock_output.chinese_pdf = "/path/to/chinese.pdf"
        mock_output.english_pdf = "/path/to/english.pdf"

        with patch('automation.pipeline.DatabaseManager') as MockDB:
            mock_db = MockDB.return_value
            mock_db.get_book_output.return_value = mock_output
            mock_db.update_book_status.return_value = None
            mock_db.add_log.return_value = None

            with patch('automation.translation_processor.translate_book') as mock_translate:
                mock_translate.return_value = True

                stage = TranslationStage()
                stage.db = mock_db
                stage.execute(ctx)

                mock_translate.assert_called_once()
                assert ctx.translation_result["bilingual_epub"] == "/path/to/bilingual.epub"


class TestPipelineErrorHandling:
    """流水线错误处理测试"""

    def test_stage_error_sets_context_status(self):
        """测试阶段出错时设置 context 状态"""
        ctx = PipelineContext(book_id="test", epub_path="test.epub")

        class FailingStage(Stage):
            name = "failing"
            def execute(self, ctx):
                raise RuntimeError("Test error")

        pipeline = Pipeline([FailingStage()])
        pipeline.run(ctx)

        assert ctx.status == "failed"
        assert ctx.error == "Test error"


class TestRunPipelineFunction:
    """run_pipeline 便捷函数测试"""

    def test_run_pipeline_creates_correct_context(self):
        """测试 run_pipeline 创建正确的上下文"""
        with patch('automation.pipeline.Pipeline') as MockPipeline:
            mock_pipeline = MockPipeline.return_value
            mock_pipeline.run.return_value = PipelineContext(
                book_id="test-123",
                epub_path="test.epub"
            )

            ctx = run_pipeline(
                book_id="test-123",
                epub_path="test.epub",
                filename="test.epub",
                title="Test",
                author="Author",
                skip_publish=True
            )

            MockPipeline.assert_called_once()
            mock_pipeline.run.assert_called_once()
