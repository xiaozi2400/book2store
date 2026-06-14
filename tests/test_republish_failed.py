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


def test_publish_failure_writes_publish_status_failed(monkeypatch, tmp_path):
    """XianyuPublisher.publish() 失败时回写 BookOutput.publish_status='failed' 和 publish_error"""
    from automation.xianyu_publisher import XianyuPublisher
    from automation.config import config

    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    # 准备一个临时 output_dir，里面有 book-001 的 xianyu_listing.txt
    real_output_dir = tmp_path / "output"
    real_output_dir.mkdir()
    meta_dir = real_output_dir / "b1_metadata"
    meta_dir.mkdir()
    (meta_dir / "xianyu_listing.txt").write_text("一份闲鱼文案", encoding="utf-8")
    # 覆盖 _config 字典（output_dir 是 property，只能改 _config 字典）
    monkeypatch.setitem(config._config["paths"], "output_dir", str(real_output_dir))

    session = get_session()
    try:
        session.add(Book(id="book-001", filename="b1.epub", title="测试书", status="completed"))
        session.add(BookOutput(book_id="book-001", publish_status="pending"))
        session.commit()
    finally:
        close_session(session)

    # Mock _start_browser 抛异常
    def mock_start_browser(self):
        raise RuntimeError("浏览器启动失败：playwright 未安装")
    monkeypatch.setattr(XianyuPublisher, "_start_browser", mock_start_browser)

    publisher = XianyuPublisher()
    result = publisher.publish("book-001")

    assert result is False

    session = get_session()
    try:
        book = session.query(Book).filter(Book.id == "book-001").first()
        output = session.query(BookOutput).filter(BookOutput.book_id == "book-001").first()
        assert output.publish_status == "failed"
        assert "playwright 未安装" in output.publish_error
        assert len(output.publish_error) <= 1000
        assert book.status == "completed"  # 关键：Book.status 保持 completed
    finally:
        close_session(session)
