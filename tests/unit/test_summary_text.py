"""测试 Book.summary_text 字段与 update_book_summary 方法"""

from automation.database import DatabaseManager, close_session, get_session
from automation.models import Book


class TestSummaryTextField:
    def test_book_has_summary_text_field(self, in_memory_db, sample_book):
        """验证 Book 模型有 summary_text 字段，初始值为 None"""
        book = in_memory_db.query(Book).filter(Book.id == "test-book-001").first()
        assert hasattr(book, "summary_text")
        assert book.summary_text is None

    def test_update_book_summary_updates_field(self):
        """验证 update_book_summary 能正确更新 summary_text 字段"""
        db = DatabaseManager()
        book = db.create_book(filename="test_update.epub", title="更新测试")
        summary = "这是一本关于Python编程的书籍摘要"
        db.update_book_summary(book.id, summary)

        session = get_session()
        try:
            updated = session.query(Book).filter(Book.id == book.id).first()
            assert updated.summary_text == summary
        finally:
            close_session(session)

    def test_update_book_summary_returns_book(self):
        """验证 update_book_summary 返回更新后的 Book 对象"""
        db = DatabaseManager()
        book = db.create_book(filename="test_return.epub", title="返回测试")
        summary = "另一段摘要内容"
        result = db.update_book_summary(book.id, summary)

        assert isinstance(result, Book)
        assert result.id == book.id
        assert result.summary_text == summary
