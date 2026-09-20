"""测试文案生成集成 - 验证 xianyu_listing.txt 和 xiaohongshu_note.txt 文件输出"""

from unittest.mock import patch

import pytest

from automation.database import DatabaseManager
from automation.models import Book


class TestMainSummaryFlow:
    """测试文案生成流程集成"""

    @pytest.fixture
    def book_with_summary(self, in_memory_db):
        """创建带摘要的测试书籍"""
        book = Book(
            id="test-copy-book-001",
            filename="test-copy.epub",
            title="测试文案书籍",
            author="测试作者",
            status="pending",
            summary_text="这是一个用于测试文案生成的书籍摘要。书籍内容涉及人生哲学和自我成长。",
        )
        in_memory_db.add(book)
        in_memory_db.commit()
        return book

    @pytest.fixture
    def metadata_dir(self, tmp_path):
        """创建临时 metadata 目录"""
        meta_dir = tmp_path / "test-copy_metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        return meta_dir

    def test_copywriting_stage_writes_xianyu_and_xiaohongshu_files(
        self, book_with_summary, metadata_dir, tmp_path, in_memory_db
    ):
        """测试 CopywritingStage 生成 xianyu_listing.txt 和 xiaohongshu_note.txt"""
        book_id = book_with_summary.id

        # Mock AI copywriter to return specific content
        mock_xianyu_content = "【闲鱼文案】这本书是《测试文案书籍》，作者测试作者。非常值得一读！"
        mock_xiaohongshu_content = "📚 《测试文案书籍》读后感 | 这本书真的超赞！"

        with patch("automation.publishing.ai_copywriter.AIClient.generate_xianyu_listing") as mock_xianyu:
            mock_xianyu.return_value = (mock_xianyu_content, {"prompt_tokens": 100, "completion_tokens": 50})

            with patch("automation.publishing.ai_copywriter.AIClient.generate_xiaohongshu_note") as mock_xhs:
                mock_xhs.return_value = (mock_xiaohongshu_content, {"prompt_tokens": 80, "completion_tokens": 40})

                # Mock MetadataWriter to write to our temp directory
                with patch("automation.metadata_writer.MetadataWriter.write_copywriting") as mock_write:
                    # Call the actual write method but redirect to temp dir
                    def side_effect(book_id, xianyu_text, xhs_text):
                        xianyu_path = metadata_dir / "xianyu_listing.txt"
                        xhs_path = metadata_dir / "xiaohongshu_note.txt"
                        xianyu_path.write_text(xianyu_text, encoding="utf-8")
                        xhs_path.write_text(xhs_text, encoding="utf-8")
                        return True

                    mock_write.side_effect = side_effect

                    from automation.pipeline import CopywritingStage, PipelineContext

                    db = DatabaseManager()
                    db.create_book_output(book_id)

                    stage = CopywritingStage(db=db)
                    ctx = PipelineContext(
                        book_id=book_id,
                        epub_path="dummy.epub",
                        title="测试文案书籍",
                        author="测试作者",
                        summary_text=book_with_summary.summary_text,
                    )

                    stage.execute(ctx)

                    # 验证执行成功
                    assert ctx.status != "failed", f"阶段失败: {ctx.error}"

                    # 验证文件存在
                    xianyu_path = metadata_dir / "xianyu_listing.txt"
                    xhs_path = metadata_dir / "xiaohongshu_note.txt"

                    assert xianyu_path.exists(), f"闲鱼文案文件不存在: {xianyu_path}"
                    assert xhs_path.exists(), f"小红书文案文件不存在: {xhs_path}"

                    # 验证文件非空
                    xianyu_content = xianyu_path.read_text(encoding="utf-8")
                    xhs_content = xhs_path.read_text(encoding="utf-8")

                    assert len(xianyu_content) > 0, "闲鱼文案文件为空"
                    assert len(xhs_content) > 0, "小红书文案文件为空"

                    # 验证内容包含预期文本
                    assert "测试文案书籍" in xianyu_content, f"闲鱼文案缺少书名: {xianyu_content}"
                    assert "测试文案书籍" in xhs_content, f"小红书文案缺少书名: {xhs_content}"

    def test_copywriting_files_contain_expected_fields(self, book_with_summary, metadata_dir, tmp_path, in_memory_db):
        """验证文案文件包含必要字段"""
        book_id = book_with_summary.id

        mock_xianyu = "【闲鱼】《测试文案书籍》作者：测试作者\n\n非常好的一本书！"
        mock_xhs = "📖 《测试文案书籍》\n\n作者: 测试作者\n\n强烈推荐！"

        with patch("automation.publishing.ai_copywriter.AIClient.generate_xianyu_listing") as mock_xy:
            mock_xy.return_value = (mock_xianyu, {"prompt_tokens": 100, "completion_tokens": 50})

            with patch("automation.publishing.ai_copywriter.AIClient.generate_xiaohongshu_note") as mock_xhs_fn:
                mock_xhs_fn.return_value = (mock_xhs, {"prompt_tokens": 80, "completion_tokens": 40})

                with patch("automation.metadata_writer.MetadataWriter.write_copywriting") as mock_write:

                    def side_effect(book_id, xianyu_text, xhs_text):
                        xianyu_path = metadata_dir / "xianyu_listing.txt"
                        xhs_path = metadata_dir / "xiaohongshu_note.txt"
                        xianyu_path.write_text(xianyu_text, encoding="utf-8")
                        xhs_path.write_text(xhs_text, encoding="utf-8")
                        return True

                    mock_write.side_effect = side_effect

                    from automation.pipeline import CopywritingStage, PipelineContext

                    db = DatabaseManager()
                    db.create_book_output(book_id)

                    stage = CopywritingStage(db=db)
                    ctx = PipelineContext(
                        book_id=book_id,
                        epub_path="dummy.epub",
                        title="测试文案书籍",
                        author="测试作者",
                        summary_text=book_with_summary.summary_text,
                    )

                    stage.execute(ctx)

                    # 验证闲鱼文案包含书名和作者
                    xianyu_path = metadata_dir / "xianyu_listing.txt"
                    xianyu_content = xianyu_path.read_text(encoding="utf-8")

                    # 验证至少包含书名
                    assert "测试文案书籍" in xianyu_content, f"闲鱼文案缺少书名: {xianyu_content}"
                    # 验证闲鱼文案长度合理
                    assert len(xianyu_content) > 10, f"闲鱼文案过短: {xianyu_content}"

                    # 验证小红书文案
                    xhs_path = metadata_dir / "xiaohongshu_note.txt"
                    xhs_content = xhs_path.read_text(encoding="utf-8")

                    assert "测试文案书籍" in xhs_content, f"小红书文案缺少书名: {xhs_content}"
                    assert len(xhs_content) > 10, f"小红书文案过短: {xhs_content}"
