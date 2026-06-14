"""发布失败书籍重新发布功能测试"""
import pytest
from automation.database import DatabaseManager, get_session, close_session
from automation.models import Book, BookOutput, ProcessingLog


def test_get_books_by_publish_status_returns_only_failed(monkeypatch):
    """get_books_by_publish_status('failed') 只返回 publish_status='failed' 的书"""
    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    # 写入测试数据（使用共享引擎）
    session = get_session()
    try:
        session.add(Book(id="book-failed-1", filename="f1.epub", title="失败书1", status="completed"))
        session.add(Book(id="book-failed-2", filename="f2.epub", title="失败书2", status="completed"))
        session.add(Book(id="book-published-1", filename="p1.epub", title="已发布书", status="published"))
        session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
        session.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
        session.add(BookOutput(book_id="book-published-1", publish_status="published", xianyu_listing_url="https://example.com/1"))
        session.commit()
    finally:
        close_session(session)

    db = DatabaseManager()
    result = db.get_books_by_publish_status("failed")

    assert len(result) == 2
    titles = {b.title for b in result}
    assert titles == {"失败书1", "失败书2"}
