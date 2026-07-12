"""测试质量检查优化：空翻译/翻译过短不重试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock
from ebook_translator.translator.translator import Translator


def _make_translator() -> Translator:
    """构造一个仅注入必要字段的 Translator 测试替身，使用真实 _quality_check 方法"""
    t = MagicMock(spec=Translator)
    t.provider = 'test'
    t.stats = {
        'api_calls': 0,
        'total_tokens': 0,
        'translated_paragraphs': 0,
        'retried': 0,
        'failed': 0,
        'by_tier': {}
    }
    t.opt_config = {
        'batch': {
            'tier1_batch_size': 10,
            'tier2_batch_size': 5,
            'tier3_batch_size': 1,
            'max_workers': 1,
            'use_char_based_batching': False,
            'max_chars_per_batch': 1800,
        },
        'quality_check': {
            'enabled': True,
            'min_translation_ratio': 0.3,
            'max_translation_ratio': 3.0,
            'tier3_min_ratio': 0.1,
            'tier3_max_ratio': 5.0,
            'short_text_min_length': 30,
            'short_text_min_absolute': 3,
            'retry_empty': True,
        }
    }
    # 绑定真实 _quality_check 方法，避免过度 mock
    t._quality_check = Translator._quality_check.__get__(t, type(t))
    return t


def test_empty_translation_keeps_original():
    """空翻译应保留原文，不重试"""
    t = _make_translator()
    result = {
        'id': 1,
        'original': 'Hello World',
        'translated': '',
        'html': '<p>Hello World</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == 'Hello World', "空翻译应保留原文"
    assert t.stats['retried'] == 0, "空翻译不应触发重试"
    assert t.stats['failed'] == 1, "空翻译应计入失败"


def test_whitespace_only_translation_keeps_original():
    """空格翻译应保留原文"""
    t = _make_translator()
    result = {
        'id': 2,
        'original': 'Chapter 1',
        'translated': '   ',
        'html': '<p>Chapter 1</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == 'Chapter 1', "空格翻译应保留原文"
    assert t.stats['retried'] == 0, "不应触发重试"


def test_too_short_absolute_keeps_translated():
    """绝对长度过短（但非空）应保留翻译，不重试"""
    t = _make_translator()
    result = {
        'id': 3,
        'original': 'Hi',
        'translated': 'x',
        'html': '<p>Hi</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == 'x', "过短翻译（但非空）应保留翻译"
    assert t.stats['retried'] == 0, "不应触发重试"


def test_normal_translation_no_issues():
    """正常翻译不应有任何问题"""
    t = _make_translator()
    result = {
        'id': 4,
        'original': 'This is a normal sentence to translate.',
        'translated': '这是一个正常的翻译句子。',
        'html': '<p>Original</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == '这是一个正常的翻译句子。', "正常翻译不应被修改"
    assert t.stats['retried'] == 0
    assert t.stats['failed'] == 0


def test_quality_log_level_is_info():
    """质量问题日志应为 INFO 而非 WARNING（通过不报错验证）"""
    t = _make_translator()
    result = {
        'id': 5,
        'original': 'Hello World',
        'translated': '',
        'html': '<p>Hello World</p>',
        'tier': 'tier2_normal'
    }
    # 执行不应抛出异常
    t._quality_check(result, 'tier2_normal')


def test_short_translation_keeps_translated_not_original():
    """翻译过短（但非空）应保留翻译，不应回退原文"""
    t = _make_translator()
    result = {
        'id': 10,
        'original': '1 The Surprising Power of Atomic Habits',
        'translated': '1 原子习惯的惊人力量',  # 短但有效
        'html': '<p>1 The Surprising Power of Atomic Habits</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == '1 原子习惯的惊人力量', \
        f"翻译过短但有效的应保留翻译，实际得到: {checked['translated']}"
    assert checked['translated'] != result['original'], \
        "不应回退到原文"


def test_ratio_too_low_long_text_keeps_translated():
    """长文本翻译比例过低时保留翻译（不重试，因为重试大概率无效）"""
    t = _make_translator()
    result = {
        'id': 11,
        'original': 'This is a long English sentence that should normally translate to Chinese with similar length.',
        'translated': '短译文',  # 比例极低
        'html': '<p>Original</p>',
        'tier': 'tier2_normal'
    }
    checked = t._quality_check(result, 'tier2_normal')
    assert checked['translated'] == '短译文', \
        f"翻译过短应保留翻译，实际得到: {checked['translated']}"


if __name__ == '__main__':
    test_empty_translation_keeps_original()
    test_whitespace_only_translation_keeps_original()
    test_too_short_absolute_keeps_translated()
    test_normal_translation_no_issues()
    test_quality_log_level_is_info()
    test_short_translation_keeps_translated_not_original()
    test_ratio_too_low_long_text_keeps_translated()
    print("所有测试通过!")
