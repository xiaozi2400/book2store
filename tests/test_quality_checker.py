"""tests/test_quality_checker.py"""
import pytest
from automation.models import BookOutput, Book, generate_uuid
from automation.database import init_database, get_session, close_session
from datetime import datetime


def test_quality_report_field_exists():
    """验证 BookOutput 表有 quality_report 字段"""
    init_database()
    session = get_session()
    try:
        book = Book(
            filename="test_quality.epub",
            title="Test Quality Book",
            status="completed"
        )
        session.add(book)
        session.flush()

        output = BookOutput(
            book_id=book.id,
            quality_report='{"overall_score": 85, "overall_grade": "良好"}'
        )
        session.add(output)
        session.commit()

        retrieved = session.query(BookOutput).filter(
            BookOutput.book_id == book.id
        ).first()
        assert retrieved is not None
        assert retrieved.quality_report is not None
        import json
        report = json.loads(retrieved.quality_report)
        assert report["overall_score"] == 85
        assert report["overall_grade"] == "良好"
    finally:
        close_session(session)


def test_quality_report_defaults_to_none():
    """新建 BookOutput 时 quality_report 默认为 None"""
    init_database()
    session = get_session()
    try:
        book = Book(
            filename="test_no_report.epub",
            title="No Report Book",
            status="completed"
        )
        session.add(book)
        session.flush()

        output = BookOutput(book_id=book.id)
        session.add(output)
        session.commit()

        retrieved = session.query(BookOutput).filter(
            BookOutput.book_id == book.id
        ).first()
        assert retrieved.quality_report is None
    finally:
        close_session(session)


def test_quality_check_default_config():
    """验证质量检查默认配置存在"""
    from automation.config import config
    qc_config = config.get("quality_check", {})
    assert isinstance(qc_config, dict)
    assert "enabled" in qc_config
    assert "thresholds" in qc_config
    assert "dimensions" in qc_config
    assert "model" not in qc_config  # 纯程序化检查，无模型配置


def test_quality_check_enabled_by_default():
    """验证质量检查默认开启"""
    from automation.config import config
    enabled = config.get_quality_check_enabled()
    assert enabled is True