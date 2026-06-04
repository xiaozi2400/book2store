"""测试质量报告：验证 JSON 文件不再写入，数据库仍保存报告"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_no_json_file_written():
    """
    验证 _run_quality_check 不再写入 JSON 文件到磁盘。
    通过 mock QualityChecker 返回一个报告，然后检查 output_dir 下没有 质量报告-*.json 文件。
    """
    from automation.translation_processor import TranslationProcessor

    # mock 所有外部依赖
    processor = TranslationProcessor()
    processor.db = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        base_name = "test-book"

        # mock QualityChecker
        report_mock = MagicMock()
        report_mock.to_json.return_value = json.dumps({
            "book_title": base_name,
            "overall_score": 85.0,
            "overall_grade": "良好",
            "summary": "测试摘要",
            "recommendation": "测试建议",
            "dimensions": {}
        })

        with patch.object(processor, '_run_quality_check', wraps=processor._run_quality_check) as wrapped, \
             patch('automation.quality_checker.QualityChecker') as MockChecker:

            mock_checker = MagicMock()
            mock_checker.enabled = True
            mock_checker.check.return_value = report_mock
            MockChecker.return_value = mock_checker

            translation_result = {
                "bilingual_pdf": "test.pdf",
                "chinese_pdf": "test-zh.pdf",
                "cache_data": {},
                "source_paragraphs": ["hello"],
                "translated_paragraphs": ["你好"]
            }

            processor._run_quality_check(
                book_id="test-book-id",
                base_name=base_name,
                translation_result=translation_result,
                output_root=tmp_path
            )

        # 断言：没有 JSON 文件被写入
        json_files = list(tmp_path.glob(f"质量报告-*.json"))
        assert len(json_files) == 0, f"期望没有质量报告 JSON 文件，但发现: {json_files}"


def test_db_update_called():
    """
    验证 _run_quality_check 仍调用 db.update_book_quality_report。
    """
    from automation.translation_processor import TranslationProcessor

    processor = TranslationProcessor()
    processor.db = MagicMock()

    report_json_str = json.dumps({
        "book_title": "test",
        "overall_score": 85.0,
        "overall_grade": "良好",
        "summary": "测试",
        "recommendation": "测试",
        "dimensions": {}
    })

    report_mock = MagicMock()
    report_mock.to_json.return_value = report_json_str

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        with patch('automation.quality_checker.QualityChecker') as MockChecker:
            mock_checker = MagicMock()
            mock_checker.enabled = True
            mock_checker.check.return_value = report_mock
            MockChecker.return_value = mock_checker

            processor._run_quality_check(
                book_id="test-book-id",
                base_name="test-book",
                translation_result={
                    "bilingual_pdf": "test.pdf",
                    "chinese_pdf": "test-zh.pdf",
                    "cache_data": {},
                    "source_paragraphs": ["hello"],
                    "translated_paragraphs": ["你好"]
                },
                output_root=tmp_path
            )

    # 断言：update_book_quality_report 被调用了一次
    processor.db.update_book_quality_report.assert_called_once_with(
        "test-book-id", report_json_str
    )


def test_get_book_quality_report():
    """验证 DatabaseManager.get_book_quality_report 方法正常工作"""
    from automation.database import DatabaseManager

    # mock session 和 query
    mock_session = MagicMock()
    mock_output = MagicMock()
    mock_output.quality_report = '{"overall_score": 90, "overall_grade": "优秀"}'
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = mock_output
    mock_session.query.return_value = mock_query

    with patch('automation.database.get_session', return_value=mock_session), \
         patch('automation.database.close_session'):
        mgr = DatabaseManager()
        result = mgr.get_book_quality_report("test-book-1")
        assert result == '{"overall_score": 90, "overall_grade": "优秀"}', f"期望报告数据，得到 {result}"

        # 无输出记录时返回 None
        mock_query.filter.return_value.first.return_value = None
        result2 = mgr.get_book_quality_report("no-output")
        assert result2 is None, f"期望 None, 得到 {result2}"