"""测试 ContentSummarizer 在生成摘要后保存 summary_text"""
from unittest.mock import MagicMock, Mock
from automation.content_summarizer import ContentSummarizer
from automation.database import get_session
from automation.models import Book


class TestSummarySave:
    """测试摘要保存逻辑"""

    def test_summary_saved_when_generate_succeeds(self):
        """mock _generate_summary 返回摘要字典，验证 summary_text 被保存到DB"""
        session = get_session()
        book = Book(
            id="test-book-001",
            filename="test.epub",
            title="测试书籍",
            author="测试作者",
            status="pending"
        )
        session.add(book)
        session.commit()
        session.close()

        summarizer = ContentSummarizer()

        summarizer._check_suitability = MagicMock(return_value=Mock(
            passed=True, label="适合", score=85, recommendation="推荐", details={}
        ))
        summarizer._extract_chapters = MagicMock(return_value=[
            {"title": "第一章", "content": "这是第一章的内容..."},
            {"title": "第二章", "content": "这是第二章的内容..."},
        ])
        summarizer._generate_summary = MagicMock(return_value={
            'title': '测试书籍',
            'author': '测试作者',
            'book_type': '商业',
            'content': '## 核心观点\n这是核心观点\n\n## 章节摘要\n第一章内容摘要'
        })
        summarizer._extract_cover_from_epub = MagicMock(return_value=None)
        summarizer._create_pdf = MagicMock()

        result = summarizer.summarize("test-book-001", "test.epub")

        assert result is True
        session = get_session()
        book = session.query(Book).filter(Book.id == "test-book-001").first()
        assert book is not None
        assert book.summary_text is not None
        assert "核心观点" in book.summary_text
        assert "测试书籍" in book.summary_text
        session.close()

    def test_summary_not_saved_when_generate_returns_none(self):
        """mock _generate_summary 返回 None，验证摘要未保存"""
        session = get_session()
        book = Book(
            id="test-book-002",
            filename="test.epub",
            title="测试书籍",
            author="测试作者",
            status="pending"
        )
        session.add(book)
        session.commit()
        session.close()

        summarizer = ContentSummarizer()

        summarizer._check_suitability = MagicMock(return_value=Mock(
            passed=True, label="适合", score=85, recommendation="推荐", details={}
        ))
        summarizer._extract_chapters = MagicMock(return_value=[
            {"title": "第一章", "content": "这是第一章的内容..."},
        ])
        summarizer._generate_summary = MagicMock(return_value=None)
        summarizer._extract_cover_from_epub = MagicMock(return_value=None)
        summarizer._create_pdf = MagicMock()

        result = summarizer.summarize("test-book-002", "test.epub")

        assert result is False
        session = get_session()
        book = session.query(Book).filter(Book.id == "test-book-002").first()
        assert book is not None
        assert book.summary_text is None
        session.close()