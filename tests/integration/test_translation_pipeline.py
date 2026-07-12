"""tests/test_translation_pipeline.py — 翻译流水线集成测试"""
from unittest.mock import patch, MagicMock
import pytest


# ============================================================
# Test 1: translate_epub 空翻译检测
# ============================================================

@patch('ebook_translator.library.PDFConverter')
@patch('ebook_translator.library.EPUBGenerator')
@patch('ebook_translator.library.CacheManager')
@patch('ebook_translator.library.get_translator')
@patch('ebook_translator.library.EPUBParser')
def test_translate_epub_empty_translation_detection(
    mock_parser_cls, mock_get_translator, mock_cache_cls,
    mock_gen_cls, mock_pdf_cls
):
    """翻译 API 全部返回空时，translate_epub 返回 success=False"""
    from ebook_translator.library import translate_epub

    mock_parser = MagicMock()
    mock_parser.parse.return_value = True
    mock_parser.get_content_items.return_value = [MagicMock()]
    mock_parser.get_paragraphs.return_value = [
        {'id': 'p1', 'text': 'Hello world', 'html': '<p>Hello world</p>', 'tier': 'normal'},
        {'id': 'p2', 'text': 'This is a test', 'html': '<p>This is a test</p>', 'tier': 'normal'},
    ]
    mock_parser_cls.return_value = mock_parser

    mock_translator = MagicMock()
    mock_translator.translate_smart.return_value = [
        {'id': 'p1', 'original': 'Hello world', 'translated': '', 'is_duplicate': False},
        {'id': 'p2', 'original': 'This is a test', 'translated': '', 'is_duplicate': False},
    ]
    mock_get_translator.return_value = mock_translator

    result = translate_epub(
        epub_path="dummy.epub",
        skip_cache=True,
        test_mode=True
    )

    assert result["success"] is False
    assert "翻译 API 返回全部为空" in result["error"]
    assert result["total_paragraphs"] == 2


# ============================================================
# Test 2: translate_epub 成功时返回质量检查数据
# ============================================================

@patch('ebook_translator.library.shutil.copy2')
@patch('ebook_translator.library.PDFConverter')
@patch('ebook_translator.library.EPUBGenerator')
@patch('ebook_translator.library.CacheManager')
@patch('ebook_translator.library.get_translator')
@patch('ebook_translator.library.EPUBParser')
def test_translate_epub_success_returns_quality_data(
    mock_parser_cls, mock_get_translator, mock_cache_cls,
    mock_gen_cls, mock_pdf_cls, mock_copy2
):
    """翻译成功时，返回 source_paragraphs、translated_paragraphs、cache_data"""
    from ebook_translator.library import translate_epub

    mock_parser = MagicMock()
    mock_parser.parse.return_value = True
    mock_parser.get_content_items.return_value = [MagicMock()]
    mock_parser.get_paragraphs.return_value = [
        {'id': 'p1', 'text': 'Hello world', 'html': '<p>Hello world</p>', 'tier': 'normal'},
        {'id': 'p2', 'text': 'This is a test', 'html': '<p>This is a test</p>', 'tier': 'normal'},
    ]
    mock_parser_cls.return_value = mock_parser

    mock_translator = MagicMock()
    mock_translator.translate_smart.return_value = [
        {'id': 'p1', 'original': 'Hello world', 'translated': '你好世界', 'is_duplicate': False},
        {'id': 'p2', 'original': 'This is a test', 'translated': '这是一个测试', 'is_duplicate': False},
    ]
    mock_translator.get_stats.return_value = {}
    mock_get_translator.return_value = mock_translator

    result = translate_epub(
        epub_path="dummy.epub",
        skip_cache=True,
        test_mode=True
    )

    assert result["success"] is True

    assert "source_paragraphs" in result
    assert result["source_paragraphs"] == ["Hello world", "This is a test"]

    assert "translated_paragraphs" in result
    assert result["translated_paragraphs"] == ["你好世界", "这是一个测试"]

    assert "cache_data" in result
    assert result["cache_data"] == {
        "0": {"source": "Hello world", "translated": "你好世界"},
        "1": {"source": "This is a test", "translated": "这是一个测试"},
    }


# ============================================================
# Test 3: TranslationProcessor 处理失败场景
# ============================================================

@patch('automation.translation_processor.translate_epub')
@patch('automation.translation_processor.DatabaseManager')
def test_translation_processor_failed_translation(mock_db_cls, mock_translate):
    """translate_epub 返回 success=False 时，process 返回 False"""
    from automation.translation_processor import TranslationProcessor

    mock_translate.return_value = {"success": False}

    mock_db = MagicMock()
    mock_db_cls.return_value = mock_db

    processor = TranslationProcessor()
    result = processor.process(book_id="test-id", epub_path="dummy.epub")

    assert result is False
    mock_db.update_book_status.assert_any_call("test-id", "failed", "翻译失败")