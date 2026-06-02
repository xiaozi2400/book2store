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


# ============================================================
# CompletenessChecker 测试（维度 7：翻译完整性）
# ============================================================

from automation.quality_checker import CompletenessChecker


def test_completeness_all_translated():
    """所有段落都翻译完成"""
    cache_data = {
        "hash1": {"source": "Hello", "translated": "你好"},
        "hash2": {"source": "World", "translated": "世界"},
    }
    source_paragraphs = ["Hello", "World"]
    checker = CompletenessChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] == 100
    assert result["translated_paragraphs"] == 2
    assert result["missing_count"] == 0


def test_completeness_partial_missing():
    """部分段落缺失翻译"""
    cache_data = {
        "hash1": {"source": "Hello", "translated": "你好"},
    }
    source_paragraphs = ["Hello", "World", "Test"]
    checker = CompletenessChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["missing_count"] == 2
    assert result["translated_paragraphs"] == 1
    assert result["score"] < 100


def test_completeness_empty_translated():
    """译文为空字符串的情况"""
    cache_data = {
        "hash1": {"source": "Hello", "translated": ""},
    }
    source_paragraphs = ["Hello"]
    checker = CompletenessChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["empty_paragraphs"] == 1
    assert result["score"] < 100


def test_completeness_no_cache():
    """没有缓存数据"""
    cache_data = {}
    source_paragraphs = ["Hello"]
    checker = CompletenessChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] == 0
    assert result["missing_count"] == 1


def test_completeness_empty_source():
    """源文档没有段落"""
    cache_data = {}
    source_paragraphs = []
    checker = CompletenessChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] == 100
    assert result["missing_count"] == 0


# ============================================================
# PdfTocLinkChecker 测试（维度 8：PDF 目录链接检查）
# ============================================================

import os
from automation.quality_checker import PdfTocLinkChecker


def test_pdf_toc_checker_no_pdf():
    """PDF 文件不存在"""
    checker = PdfTocLinkChecker()
    result = checker.check("non_existent.pdf")
    assert result["score"] == 0
    assert "PDF 文件不存在" in str(result["issues"])


def test_pdf_toc_checker_not_pdf():
    """非 PDF 文件"""
    checker = PdfTocLinkChecker()
    result = checker.check(__file__)
    assert result["score"] == 0
    assert result["toc_entries"] == 0


def test_pdf_toc_checker_simple_pdf(tmp_path):
    """生成一个简单 PDF 并检查其目录链接"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf_path = os.path.join(tmp_path, "test_toc.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.drawString(100, 700, "Chapter 1")
    c.showPage()
    c.drawString(100, 700, "Chapter 2")
    c.showPage()
    c.drawString(100, 700, "Chapter 3")
    c.showPage()
    c.save()

    import fitz
    doc = fitz.open(pdf_path)
    toc = [
        [1, "Chapter 1", 1],
        [1, "Chapter 2", 2],
        [1, "Chapter 3", 3],
    ]
    doc.set_toc(toc)
    doc.save(pdf_path, incremental=True, encryption=0)
    doc.close()

    checker = PdfTocLinkChecker()
    result = checker.check(pdf_path)
    assert result["toc_entries"] == 3
    assert result["valid_links"] == 3
    assert result["broken_links"] == 0
    assert result["score"] == 100


def test_pdf_toc_checker_broken_links(tmp_path):
    """目录链接指向不存在的页码"""
    import fitz
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf_path = os.path.join(tmp_path, "test_broken_toc.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.drawString(100, 700, "Page 1")
    c.showPage()
    c.save()

    doc = fitz.open(pdf_path)
    toc = [
        [1, "Chapter 1", 1],
        [1, "Missing Chapter", -1],
    ]
    doc.set_toc(toc)
    doc.save(pdf_path, incremental=True, encryption=0)
    doc.close()

    checker = PdfTocLinkChecker()
    result = checker.check(pdf_path)
    assert result["toc_entries"] == 2
    assert result["valid_links"] == 1
    assert result["broken_links"] == 1
    assert result["score"] == 50