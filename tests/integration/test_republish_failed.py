"""发布失败书籍重新发布功能测试"""
import pytest
from automation.database import DatabaseManager, get_session, close_session
from automation.models import Book, BookOutput, ProcessingLog


@pytest.fixture
def db_session(monkeypatch):
    """提供与 DatabaseManager 共享的内存数据库会话，测试结束后自动清理"""
    monkeypatch.setattr("automation.database.get_database_url", lambda: "sqlite:///:memory:")
    session = get_session()
    yield session
    close_session(session)


def test_get_books_by_publish_status_returns_only_failed(db_session):
    """get_books_by_publish_status('failed') 只返回 publish_status='failed' 的书"""
    db_session.add(Book(id="book-failed-1", filename="f1.epub", title="失败书1", status="completed"))
    db_session.add(Book(id="book-failed-2", filename="f2.epub", title="失败书2", status="completed"))
    db_session.add(Book(id="book-published-1", filename="p1.epub", title="已发布书", status="published"))
    db_session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
    db_session.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
    db_session.add(BookOutput(book_id="book-published-1", publish_status="published", xianyu_listing_url="https://example.com/1"))
    db_session.commit()

    db = DatabaseManager()
    result = db.get_books_by_publish_status("failed")

    assert len(result) == 2
    titles = {b.title for b in result}
    assert titles == {"失败书1", "失败书2"}


def test_publish_failure_writes_publish_status_failed(db_session, monkeypatch, tmp_path):
    """XianyuPublisher.publish() 失败时回写 BookOutput.publish_status='failed' 和 publish_error"""
    from automation.publishing.xianyu_publisher import XianyuPublisher
    from automation.config import config

    real_output_dir = tmp_path / "output"
    real_output_dir.mkdir()
    meta_dir = real_output_dir / "b1_metadata"
    meta_dir.mkdir()
    (meta_dir / "xianyu_listing.txt").write_text("一份闲鱼文案", encoding="utf-8")
    monkeypatch.setitem(config._config["paths"], "output_dir", str(real_output_dir))

    db_session.add(Book(id="book-001", filename="b1.epub", title="测试书", status="completed"))
    db_session.add(BookOutput(book_id="book-001", publish_status="pending"))
    db_session.commit()

    def mock_start_browser(self):
        raise RuntimeError("浏览器启动失败：playwright 未安装")
    monkeypatch.setattr(XianyuPublisher, "_start_browser", mock_start_browser)

    publisher = XianyuPublisher()
    result = publisher.publish("book-001")

    assert result is False

    db_session.expire_all()
    book = db_session.query(Book).filter(Book.id == "book-001").first()
    output = db_session.query(BookOutput).filter(BookOutput.book_id == "book-001").first()
    assert output.publish_status == "failed"
    assert "playwright 未安装" in output.publish_error
    assert len(output.publish_error) <= 1000
    assert book.status == "completed"


def test_list_failed_command_shows_failed_books(db_session, monkeypatch):
    """list-failed 命令输出含失败书名 + 提示运行 republish-failed"""
    from typer.testing import CliRunner
    from automation.main import app

    db_session.add(Book(id="book-failed-1", filename="f1.epub", title="失败的书", status="completed"))
    db_session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时，请重试"))
    db_session.add(ProcessingLog(book_id="book-failed-1", stage="publishing", status="error", message="登录超时，请重试"))
    db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["list-failed"])

    assert result.exit_code == 0
    assert "失败的书" in result.stdout
    assert "book-failed-1" in result.stdout
    assert "登录超时" in result.stdout
    assert "republish-failed" in result.stdout


def test_republish_failed_command_retries_all(db_session, monkeypatch):
    """republish-failed --all --auto 重新发布所有失败书籍"""
    from typer.testing import CliRunner
    from automation.main import app
    from automation.publishing.xianyu_publisher import XianyuPublisher

    db_session.add(Book(id="book-failed-1", filename="f1.epub", title="失败1", status="completed"))
    db_session.add(Book(id="book-failed-2", filename="f2.epub", title="失败2", status="completed"))
    db_session.add(BookOutput(book_id="book-failed-1", publish_status="failed", publish_error="登录超时"))
    db_session.add(BookOutput(book_id="book-failed-2", publish_status="failed", publish_error="扫码失败"))
    db_session.commit()

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

    db_session.expire_all()
    out1 = db_session.query(BookOutput).filter(BookOutput.book_id == "book-failed-1").first()
    out2 = db_session.query(BookOutput).filter(BookOutput.book_id == "book-failed-2").first()
    assert out1.publish_status == "failed"
    assert out2.publish_status == "published"


def test_republish_failed_book_id_not_found_warns(db_session, monkeypatch):
    """republish-failed --book-id <not_found> 警告并跳过"""
    from typer.testing import CliRunner
    from automation.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["republish-failed", "--book-id", "nonexistent-uuid-xxx", "--auto"])

    assert result.exit_code == 0
    assert ("未找到" in result.stdout) or ("跳过" in result.stdout)


def test_backfill_failed_publish_status_marks_pending_as_failed(db_session):
    """backfill_failed_publish_status 把'日志中曾失败但 publish_status 仍 pending'的回填为 failed"""
    db_session.add(Book(id="book-hist-1", filename="h1.epub", title="历史失败", status="completed"))
    db_session.add(BookOutput(book_id="book-hist-1", publish_status="pending"))
    db_session.add(ProcessingLog(book_id="book-hist-1", stage="publishing", status="error", message="历史登录超时"))
    db_session.add(Book(id="book-pub-1", filename="p1.epub", title="已成功", status="published"))
    db_session.add(BookOutput(book_id="book-pub-1", publish_status="published"))
    db_session.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="error", message="早期错误但后来成功了"))
    db_session.add(ProcessingLog(book_id="book-pub-1", stage="publishing", status="success", message="成功发布"))
    db_session.add(Book(id="book-clean-1", filename="c1.epub", title="干净", status="completed"))
    db_session.add(BookOutput(book_id="book-clean-1", publish_status="pending"))
    db_session.commit()

    db = DatabaseManager()
    count = db.backfill_failed_publish_status()

    assert count == 1

    db_session.expire_all()
    out_hist = db_session.query(BookOutput).filter(BookOutput.book_id == "book-hist-1").first()
    out_pub = db_session.query(BookOutput).filter(BookOutput.book_id == "book-pub-1").first()
    out_clean = db_session.query(BookOutput).filter(BookOutput.book_id == "book-clean-1").first()
    assert out_hist.publish_status == "failed"
    assert out_hist.publish_error == "历史登录超时"
    assert out_pub.publish_status == "published"
    assert out_clean.publish_status == "pending"


def test_backfill_is_idempotent(db_session):
    """backfill 重复运行返回 0（幂等）"""
    db_session.add(Book(id="book-idem-1", filename="i1.epub", title="幂等测试", status="completed"))
    db_session.add(BookOutput(book_id="book-idem-1", publish_status="pending"))
    db_session.add(ProcessingLog(book_id="book-idem-1", stage="publishing", status="error", message="错误"))
    db_session.commit()

    db = DatabaseManager()
    assert db.backfill_failed_publish_status() == 1
    assert db.backfill_failed_publish_status() == 0


def test_count_unbackfilled_failed(db_session):
    """count_unbackfilled_failed 正确计数未回填的失败书"""
    db_session.add(Book(id="book-a", filename="a.epub", title="A", status="completed"))
    db_session.add(BookOutput(book_id="book-a", publish_status="pending"))
    db_session.add(ProcessingLog(book_id="book-a", stage="publishing", status="error", message="err"))
    db_session.add(Book(id="book-b", filename="b.epub", title="B", status="completed"))
    db_session.add(BookOutput(book_id="book-b", publish_status="failed"))
    db_session.add(ProcessingLog(book_id="book-b", stage="publishing", status="error", message="err"))
    db_session.commit()

    db = DatabaseManager()
    assert db.count_unbackfilled_failed() == 1


def test_backfill_publish_status_command_runs(db_session):
    """backfill-publish-status 命令回填并打印数量"""
    from typer.testing import CliRunner
    from automation.main import app

    db_session.add(Book(id="book-bf-1", filename="b1.epub", title="BF1", status="completed"))
    db_session.add(BookOutput(book_id="book-bf-1", publish_status="pending"))
    db_session.add(ProcessingLog(book_id="book-bf-1", stage="publishing", status="error", message="历史失败"))
    db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["backfill-publish-status"])

    assert result.exit_code == 0
    assert "1" in result.stdout


def test_check_unbackfilled_prints_warning(db_session, capsys):
    """check_unbackfilled_failed_books 检测到未回填时打印黄色提示"""
    from automation.utils import check_unbackfilled_failed_books

    db_session.add(Book(id="book-warn-1", filename="w1.epub", title="W1", status="completed"))
    db_session.add(BookOutput(book_id="book-warn-1", publish_status="pending"))
    db_session.add(ProcessingLog(book_id="book-warn-1", stage="publishing", status="error", message="err"))
    db_session.commit()

    check_unbackfilled_failed_books()

    captured = capsys.readouterr()
    assert "1" in captured.out
    assert "backfill-publish-status" in captured.out
