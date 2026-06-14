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


def test_list_failed_command_shows_failed_books(monkeypatch):
    """list-failed 命令输出含失败书名 + 提示运行 republish-failed"""
    from typer.testing import CliRunner
    from automation.main import app

    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    session = get_session()
    try:
        session.add(Book(id="book-failed-1", filename="f1.epub", title="失败的书", status="completed"))
        session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时，请重试"))
        session.add(ProcessingLog(book_id="book-failed-1", stage="publishing", status="error", message="登录超时，请重试"))
        session.commit()
    finally:
        close_session(session)

    runner = CliRunner()
    result = runner.invoke(app, ["list-failed"])

    assert result.exit_code == 0
    assert "失败的书" in result.stdout
    assert "book-failed-1" in result.stdout
    assert "登录超时" in result.stdout
    assert "republish-failed" in result.stdout


def test_republish_failed_command_retries_all(monkeypatch):
    """republish-failed --all --auto 重新发布所有失败书籍"""
    from typer.testing import CliRunner
    from automation.main import app
    from automation.xianyu_publisher import XianyuPublisher

    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    session = get_session()
    try:
        session.add(Book(id="book-failed-1", filename="f1.epub", title="失败1", status="completed"))
        session.add(Book(id="book-failed-2", filename="f2.epub", title="失败2", status="completed"))
        session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
        session.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
        session.commit()
    finally:
        close_session(session)

    # Mock publish: 第 1 本仍失败，第 2 本成功
    def mock_publish(self, book_id):
        if book_id == "book-failed-1":
            self.db.update_book_output(book_id, publish_status="failed", publish_error="再次登录超时")
            return False
        else:
            self.db.update_book_output(book_id, publish_status="published", xianyu_listing_url="https://example.com/2")
            self.db.update_book_status(book_id, "published")
            return True
    monkeypatch.setattr(XianyuPublisher, "publish", mock_publish)

    runner = CliRunner()
    result = runner.invoke(app, ["republish-failed", "--all", "--auto"])

    assert result.exit_code == 0

    session = get_session()
    try:
        out1 = session.query(BookOutput).filter(BookOutput.book_id == "book-failed-1").first()
        out2 = session.query(BookOutput).filter(BookOutput.book_id == "book-failed-2").first()
        assert out1.publish_status == "failed"
        assert out2.publish_status == "published"
    finally:
        close_session(session)


def test_republish_failed_book_id_not_found_warns(monkeypatch):
    """republish-failed --book-id <not_found> 警告并跳过"""
    from typer.testing import CliRunner
    from automation.main import app

    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    runner = CliRunner()
    result = runner.invoke(app, ["republish-failed", "--book-id", "nonexistent-uuid-xxx", "--auto"])

    assert result.exit_code == 0
    assert ("未找到" in result.stdout) or ("跳过" in result.stdout)


def test_backfill_failed_publish_status_marks_pending_as_failed(monkeypatch):
    """backfill_failed_publish_status 把'日志中曾失败但 publish_status 仍 pending'的回填为 failed"""
    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    session = get_session()
    try:
        # 历史失败：应被回填
        session.add(Book(id="book-hist-1", filename="h1.epub", title="历史失败", status="completed"))
        session.add(BookOutput(book_id="book-hist-1", publish_status="pending"))
        session.add(ProcessingLog(book_id="book-hist-1", stage="publishing", status="error", message="历史登录超时"))
        # 已成功：不应被覆盖
        session.add(Book(id="book-pub-1", filename="p1.epub", title="已成功", status="published"))
        session.add(BookOutput(book_id="book-pub-1", publish_status="published"))
        session.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="error", message="早期错误但后来成功了"))
        session.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="success", message="成功发布"))
        # 干净：不应被回填
        session.add(Book(id="book-clean-1", filename="c1.epub", title="干净", status="completed"))
        session.add(BookOutput(book_id="book-clean-1", publish_status="pending"))
        session.commit()
    finally:
        close_session(session)

    db = DatabaseManager()
    count = db.backfill_failed_publish_status()

    assert count == 1

    session = get_session()
    try:
        out_hist = session.query(BookOutput).filter(BookOutput.book_id == "book-hist-1").first()
        out_pub = session.query(BookOutput).filter(BookOutput.book_id == "book-pub-1").first()
        out_clean = session.query(BookOutput).filter(BookOutput.book_id == "book-clean-1").first()
        assert out_hist.publish_status == "failed"
        assert out_hist.publish_error == "历史登录超时"
        assert out_pub.publish_status == "published"
        assert out_clean.publish_status == "pending"
    finally:
        close_session(session)


def test_backfill_is_idempotent(monkeypatch):
    """backfill 重复运行返回 0（幂等）"""
    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    session = get_session()
    try:
        session.add(Book(id="book-idem-1", filename="i1.epub", title="幂等测试", status="completed"))
        session.add(BookOutput(book_id="book-idem-1", publish_status="pending"))
        session.add(ProcessingLog(book_id="book-idem-1", stage="publishing", status="error", message="错误"))
        session.commit()
    finally:
        close_session(session)

    db = DatabaseManager()
    assert db.backfill_failed_publish_status() == 1
    assert db.backfill_failed_publish_status() == 0


def test_count_unbackfilled_failed(monkeypatch):
    """count_unbackfilled_failed 正确计数未回填的失败书"""
    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")

    session = get_session()
    try:
        session.add(Book(id="book-a", filename="a.epub", title="A", status="completed"))
        session.add(BookOutput(book_id="book-a", publish_status="pending"))
        session.add(ProcessingLog(book_id="book-a", stage="publishing", status="error", message="err"))
        session.add(Book(id="book-b", filename="b.epub", title="B", status="completed"))
        session.add(BookOutput(book_id="book-b", publish_status="failed"))  # 已回填
        session.add(ProcessingLog(book_id="book-b", stage="publishing", status="error", message="err"))
        session.commit()
    finally:
        close_session(session)

    db = DatabaseManager()
    assert db.count_unbackfilled_failed() == 1
