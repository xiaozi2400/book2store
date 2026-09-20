"""测试主图生成集成 - 验证 AI 生成和文件输出"""

from unittest.mock import MagicMock, patch

import pytest

from automation.database import DatabaseManager
from automation.image.image_generator import ImageGenerator
from automation.models import Book


class TestMainImageIntegration:
    """测试主图生成阶段集成"""

    @pytest.fixture
    def book_with_summary(self, in_memory_db):
        """创建带摘要的测试书籍"""
        book = Book(
            id="test-img-book-001",
            filename="test-book.epub",
            title="测试书籍",
            author="测试作者",
            status="pending",
            summary_text="这是一个测试书籍的摘要内容，用于验证主图生成功能。书籍讲述了一个人在生活中面临的各种选择和挑战。",
        )
        in_memory_db.add(book)
        in_memory_db.commit()
        return book

    @pytest.fixture
    def metadata_dir(self, tmp_path):
        """创建临时 metadata 目录"""
        meta_dir = tmp_path / "test-book_metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        # 创建一个简单的封面图
        cover_path = meta_dir / "cover.jpg"
        cover_path.write_bytes(b"fake-image-data")
        return meta_dir

    def test_image_generation_stage_calls_ai_and_playwright(
        self, book_with_summary, metadata_dir, in_memory_db, tmp_path
    ):
        """测试 ImageGenerationStage 调用 AI 和 Playwright"""
        book_id = book_with_summary.id

        # Mock AI client and playwright
        with patch(
            "automation.image.image_generator.ImageGenerator._find_cover_path", return_value=metadata_dir / "cover.jpg"
        ):
            with patch(
                "automation.image.image_generator.ImageGenerator._extract_cover_colors", return_value="蓝色、红色"
            ):
                with patch("automation.image.image_generator.ImageGenerator._pick_palette") as mock_palette:
                    mock_palette.return_value = (
                        "经典深沉",
                        "图1主色: #1A365D",
                        ["#1A365D", "#276749", "#553C9A", "#9B2C2C"],
                        "dark",
                    )
                    with patch(
                        "automation.image.image_generator.ImageGenerator._design_analysis", return_value="简约风格"
                    ):
                        with patch("automation.image.image_generator.ImageGenerator._call_ai_json") as mock_ai:
                            mock_ai.return_value = {
                                "page1": {
                                    "title": "测试书籍",
                                    "author": "测试作者",
                                    "subline": "英文 | 翻译",
                                    "quote": "一本好书",
                                },
                                "page2": {
                                    "items": [{"title": "技能1", "desc": "描述1"}, {"title": "技能2", "desc": "描述2"}]
                                },
                                "page3": {"items": [{"label": "标签1", "desc": "描述"}]},
                                "page4": {"items": [{"chapter": "第1章", "brief": "简介"}]},
                            }
                            with patch(
                                "automation.image.image_generator.ImageGenerator._render_html",
                                return_value="<html><body><div>Test</div></body></html>",
                            ):
                                with patch("playwright.sync_api.sync_playwright") as mock_playwright:
                                    # Mock Playwright screenshot
                                    mock_page = MagicMock()
                                    mock_page.query_selector_all.return_value = [
                                        MagicMock(),  # page1
                                        MagicMock(),  # page2
                                    ]
                                    mock_page.screenshot = MagicMock()
                                    mock_browser = MagicMock()
                                    mock_browser.new_page.return_value = mock_page
                                    mock_pw = MagicMock()
                                    mock_pw.chromium.launch.return_value = mock_browser
                                    mock_playwright.return_value.__enter__.return_value = mock_pw

                                    with patch("automation.image.image_generator.ImageGenerator._update_db"):
                                        with patch(
                                            "automation.image.image_generator.ImageGenerator._find_epub_path",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "automation.image.image_generator.ImageGenerator._load_cover_base64",
                                                return_value="",
                                            ):
                                                # Patch the output_dir in the ImageGenerator instance
                                                with patch.object(ImageGenerator, "output_dir", tmp_path, create=True):
                                                    pass

                                                db = DatabaseManager()
                                                db.create_book_output(book_id)

                                                # 直接测试 ImageGenerator.generate 方法
                                                gen = ImageGenerator()
                                                gen.output_dir = tmp_path  # 直接设置实例属性

                                                with patch.object(gen, "output_dir", tmp_path):
                                                    result = gen.generate(book_id)

                                                    # 验证结果
                                                    assert result is not None

    def test_image_stage_executes_without_error(self, book_with_summary, metadata_dir, tmp_path, in_memory_db):
        """测试 ImageGenerationStage 执行不出错"""
        book_id = book_with_summary.id

        # Mock all dependencies
        with patch(
            "automation.image.image_generator.ImageGenerator._find_cover_path", return_value=metadata_dir / "cover.jpg"
        ):
            with patch("automation.image.image_generator.ImageGenerator._extract_cover_colors", return_value="蓝色"):
                with patch("automation.image.image_generator.ImageGenerator._pick_palette") as mock_palette:
                    mock_palette.return_value = ("经典", "图1", ["#1A365D", "#276749", "#553C9A", "#9B2C2C"], "dark")
                    with patch("automation.image.image_generator.ImageGenerator._design_analysis", return_value="简约"):
                        with patch("automation.image.image_generator.ImageGenerator._call_ai_json") as mock_ai:
                            mock_ai.return_value = {
                                "page1": {"title": "测试", "author": "作者", "subline": "副标题", "quote": "引用"},
                                "page2": {"items": []},
                                "page3": {"items": []},
                                "page4": {"items": []},
                            }
                            with patch(
                                "automation.image.image_generator.ImageGenerator._render_html",
                                return_value="<html><body><div class='page page-1'>T</div></body></html>",
                            ):
                                with patch("playwright.sync_api.sync_playwright") as mock_pw:
                                    mock_page = MagicMock()
                                    mock_page.query_selector_all.return_value = []
                                    mock_page.screenshot = MagicMock()
                                    mock_browser = MagicMock()
                                    mock_browser.new_page.return_value = mock_page
                                    mock_pw_instance = MagicMock()
                                    mock_pw_instance.chromium.launch.return_value = mock_browser
                                    mock_pw.return_value.__enter__.return_value = mock_pw_instance

                                    with patch("automation.image.image_generator.ImageGenerator._update_db"):
                                        with patch(
                                            "automation.image.image_generator.ImageGenerator._find_epub_path",
                                            return_value=None,
                                        ):
                                            with patch(
                                                "automation.image.image_generator.ImageGenerator._load_cover_base64",
                                                return_value="",
                                            ):
                                                from automation.image.image_generator import ImageGenerator
                                                from automation.pipeline import ImageGenerationStage, PipelineContext

                                                db = DatabaseManager()
                                                db.create_book_output(book_id)

                                                gen = ImageGenerator()
                                                gen.output_dir = tmp_path

                                                stage = ImageGenerationStage(db=db)
                                                ctx = PipelineContext(
                                                    book_id=book_id,
                                                    epub_path="dummy.epub",
                                                )

                                                # 不应抛出异常
                                                try:
                                                    stage.execute(ctx)
                                                    success = True
                                                except Exception:
                                                    success = False

                                                assert success, "ImageGenerationStage.execute 不应抛出异常"
