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


# ===== 维度 1：忠实度检查器 =====
from automation.quality_checker import FidelityChecker


def test_fidelity_all_translated():
    """所有段落完整翻译，译文长度合理"""
    cache_data = {
        "h1": {"source": "Hello World", "translated": "你好世界"},
        "h2": {"source": "Good Morning", "translated": "早上好"},
    }
    source_paragraphs = ["Hello World", "Good Morning"]
    checker = FidelityChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] >= 90
    assert result["missing_count"] == 0


def test_fidelity_partial_missing():
    """部分段落缺失翻译"""
    cache_data = {
        "h1": {"source": "Hello", "translated": "你好"},
    }
    source_paragraphs = ["Hello", "World", "Test"]
    checker = FidelityChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] < 100
    assert result["missing_count"] == 2


def test_fidelity_empty_translation():
    """译文为空字符串"""
    cache_data = {
        "h1": {"source": "Hello", "translated": ""},
    }
    source_paragraphs = ["Hello"]
    checker = FidelityChecker()
    result = checker.check(cache_data, source_paragraphs)
    assert result["score"] < 50
    assert result["empty_count"] == 1


# ===== 维度 2：流畅度检查器 =====
from automation.quality_checker import FluencyChecker


def test_fluency_good_chinese():
    """优质中文翻译"""
    text = "今天天气很好，适合出去散步。我们一起去公园吧！"
    checker = FluencyChecker()
    result = checker.check(text)
    assert result["score"] >= 90
    assert result["chinese_ratio"] > 0.9
    assert result["english_word_count"] == 0


def test_fluency_mixed_english():
    """包含遗留英文单词"""
    text = "这个功能需要 review 一下，然后 deploy 到 server"
    checker = FluencyChecker()
    result = checker.check(text)
    assert result["score"] < 100
    assert result["english_word_count"] > 0


def test_fluency_no_chinese():
    """完全没有中文"""
    text = "Hello world, this is English text."
    checker = FluencyChecker()
    result = checker.check(text)
    assert result["score"] == 0
    assert result["chinese_ratio"] == 0


def test_fluency_empty_text():
    """空文本"""
    checker = FluencyChecker()
    result = checker.check("")
    assert result["score"] == 100


# ===== 维度 3：一致性检查器 =====
from automation.quality_checker import ConsistencyChecker


def test_consistency_perfect():
    """同一英文术语始终翻译一致"""
    cache_data = {
        "h1": {"source": "Apple", "translated": "苹果"},
        "h2": {"source": "Apple", "translated": "苹果"},
        "h3": {"source": "Banana", "translated": "香蕉"},
    }
    checker = ConsistencyChecker()
    result = checker.check(cache_data)
    assert result["score"] == 100
    assert result["inconsistent_terms"] == 0


def test_consistency_inconsistent():
    """同一英文术语出现不一致翻译"""
    cache_data = {
        "h1": {"source": "Apple", "translated": "苹果"},
        "h2": {"source": "Apple", "translated": "苹果公司"},
        "h3": {"source": "Banana", "translated": "香蕉"},
    }
    checker = ConsistencyChecker()
    result = checker.check(cache_data)
    assert result["score"] < 100
    assert result["inconsistent_terms"] > 0


def test_consistency_empty_cache():
    """空缓存"""
    checker = ConsistencyChecker()
    result = checker.check({})
    assert result["score"] == 100


# ===== 维度 4：格式完整性检查器 =====
from automation.quality_checker import FormatIntegrityChecker


def test_format_paragraphs_preserved():
    """段落结构完整保留"""
    source = ["Heading 1", "This is a paragraph.", "Item 1", "Item 2"]
    translated = ["标题 1", "这是一个段落。", "项目 1", "项目 2"]
    checker = FormatIntegrityChecker()
    result = checker.check(source, translated)
    assert result["score"] == 100
    assert result["para_count_match"] is True


def test_format_paragraphs_mismatch():
    """段落数量不匹配"""
    source = ["P1", "P2", "P3"]
    translated = ["T1", "T2"]
    checker = FormatIntegrityChecker()
    result = checker.check(source, translated)
    assert result["score"] < 100
    assert result["para_count_match"] is False


def test_format_empty_lists():
    """空列表"""
    checker = FormatIntegrityChecker()
    result = checker.check([], [])
    assert result["score"] == 100


# ===== 维度 5：术语准确性检查器 =====
from automation.quality_checker import TerminologyChecker


def test_terminology_all_correct():
    """所有术语翻译正确"""
    cache_data = {
        "h1": {"source": "API", "translated": "API"},
        "h2": {"source": "database", "translated": "数据库"},
    }
    checker = TerminologyChecker()
    result = checker.check(cache_data)
    assert result["score"] >= 90
    assert result["matched_count"] > 0


def test_terminology_wrong():
    """术语翻译错误"""
    cache_data = {
        "h1": {"source": "API", "translated": "应用程序"},
        "h2": {"source": "database", "translated": "数据库"},
    }
    checker = TerminologyChecker()
    result = checker.check(cache_data)
    assert result["incorrect_count"] > 0


def test_terminology_empty_cache():
    """空缓存"""
    checker = TerminologyChecker()
    result = checker.check({})
    assert result["score"] == 100


# ===== 维度 6：文化适配检查器 =====
from automation.quality_checker import CulturalAdaptationChecker


def test_cultural_well_adapted():
    """日期格式已适配中文"""
    text = "2024年1月15日，我们在北京召开了会议。"
    checker = CulturalAdaptationChecker()
    result = checker.check(text)
    assert result["score"] >= 90
    assert result["western_date_count"] == 0


def test_cultural_western_dates():
    """存在英文日期格式"""
    text = "The event is on 01/15/2024, please join us."
    checker = CulturalAdaptationChecker()
    result = checker.check(text)
    assert result["western_date_count"] > 0
    assert result["score"] < 100


def test_cultural_measurement_units():
    """存在英制度量衡"""
    text = "The screen is 15 inches and weighs 2 pounds."
    checker = CulturalAdaptationChecker()
    result = checker.check(text)
    assert result["imperial_units"] > 0


def test_cultural_empty_text():
    """空文本"""
    checker = CulturalAdaptationChecker()
    result = checker.check("")
    assert result["score"] == 100


"""tests/test_quality_checker.py — QualityChecker main class tests"""
from automation.quality_checker import QualityChecker, QualityReport, DimensionResult
from unittest.mock import patch, MagicMock
import json


def test_grade_excellent():
    """90 分以上为优秀"""
    checker = QualityChecker()
    assert checker._determine_grade(95) == "优秀"
    assert checker._determine_grade(90) == "优秀"


def test_grade_good():
    """75-89 分为良好"""
    checker = QualityChecker()
    assert checker._determine_grade(85) == "良好"
    assert checker._determine_grade(75) == "良好"


def test_grade_pass():
    """60-74 分为合格"""
    checker = QualityChecker()
    assert checker._determine_grade(74) == "合格"
    assert checker._determine_grade(60) == "合格"


def test_grade_needs_improvement():
    """60 分以下为需改进"""
    checker = QualityChecker()
    assert checker._determine_grade(59) == "需改进"
    assert checker._determine_grade(0) == "需改进"


def test_overall_score_average():
    """综合评分为各维度评分的加权平均"""
    checker = QualityChecker()
    dimensions = {
        "fidelity": DimensionResult(score=100, issues=[]),
        "fluency": DimensionResult(score=80, issues=[]),
        "format": DimensionResult(score=60, issues=[]),
    }
    score = checker._calc_overall_score(dimensions)
    # (100 + 80 + 60) / 3 = 80.0
    assert score == 80.0


def test_report_to_json():
    """报告可正确序列化为 JSON"""
    dimensions = {
        "fidelity": DimensionResult(score=90, issues=[]),
        "completeness": DimensionResult(
            score=95,
            issues=[],
            details={"translated_paragraphs": 10, "missing_count": 0}
        )
    }
    report = QualityReport(
        book_title="Test Book",
        overall_score=92.5,
        overall_grade="优秀",
        dimensions=dimensions,
        summary="整体质量高",
        recommendation="可直接发布"
    )
    json_str = report.to_json()
    parsed = json.loads(json_str)
    assert parsed["book_title"] == "Test Book"
    assert parsed["overall_score"] == 92.5
    assert parsed["dimensions"]["fidelity"]["score"] == 90
    assert parsed["dimensions"]["completeness"]["details"]["translated_paragraphs"] == 10