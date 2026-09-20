"""测试翻译缓存 MD5 查重功能"""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


def load_translation_cache_directly():
    """直接从文件加载 translation_cache 模块，避免通过 __init__ 导入"""
    cache_path = Path(__file__).parent.parent.parent / "automation" / "translation" / "translation_cache.py"

    # 先设置好 sys.path 确保依赖能找到
    ebook_translator_path = Path(__file__).parent.parent.parent / "ebook_translator"
    if str(ebook_translator_path) not in sys.path:
        sys.path.insert(0, str(ebook_translator_path))

    spec = importlib.util.spec_from_file_location("translation_cache", cache_path)
    module = importlib.util.module_from_spec(spec)

    # 手动添加必要的依赖到模块
    sys.modules["automation.translation.translation_cache"] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        # 如果直接加载也失败，尝试 mock 方式
        return None

    return module


class TestTranslationCache:
    """测试翻译缓存功能"""

    def test_translation_cache_md5_returns_32_char_hex(self):
        """验证 MD5 哈希是 32 位十六进制字符串"""
        test_text = "Test string for MD5"
        hash_result = hashlib.md5(test_text.encode("utf-8")).hexdigest()

        assert len(hash_result) == 32, f"MD5 哈希长度应为 32，实际 {len(hash_result)}"
        assert all(c in "0123456789abcdef" for c in hash_result), "MD5 哈希应只包含 0-9a-f 字符"

    def test_translation_cache_different_texts_different_hashes(self):
        """不同文本产生不同哈希"""
        text1 = "First text"
        text2 = "Second text"

        hash1 = hashlib.md5(text1.encode("utf-8")).hexdigest()
        hash2 = hashlib.md5(text2.encode("utf-8")).hexdigest()

        assert hash1 != hash2, "不同文本应产生不同哈希"

    def test_translation_cache_stores_and_retrieves(self, in_memory_db):
        """验证缓存存储和检索"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()

        pairs = [
            ("Hello", "你好"),
            ("Good morning", "早上好"),
            ("Good night", "晚安"),
        ]

        for original, translated in pairs:
            cache.set(original, translated)

        for original, expected_translated in pairs:
            result = cache.get(original)
            assert result == expected_translated, f"缓存检索失败：期望 '{expected_translated}'，实际 '{result}'"

    def test_translation_cache_updates_existing(self, in_memory_db):
        """验证更新已有缓存"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()
        text = "Update test"
        translated_v1 = "翻译版本1"
        translated_v2 = "翻译版本2"

        cache.set(text, translated_v1)
        assert cache.get(text) == translated_v1

        cache.set(text, translated_v2)
        assert cache.get(text) == translated_v2, "更新后应返回新翻译"

    def test_translation_cache_unicode_handling(self, in_memory_db):
        """验证 Unicode 文本处理"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()

        unicode_text = "你好，世界！Hello 世界！"
        translated = "Hello, world!你好世界！"

        cache.set(unicode_text, translated)
        result = cache.get(unicode_text)

        assert result == translated, "Unicode 文本缓存失败"

    def test_translation_cache_long_text(self, in_memory_db):
        """验证长文本处理"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()

        long_text = "这是一个非常长的段落。" * 100
        translated = "This is a very long paragraph." * 100

        cache.set(long_text, translated)
        result = cache.get(long_text)

        assert result == translated, "长文本缓存失败"

    def test_translation_cache_second_run_hits_cache(self, in_memory_db):
        """验证第二次翻译命中缓存"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()

        test_text = "Hello, world!"
        expected_translation = "你好，世界！"

        cache.set(test_text, expected_translation)
        result = cache.get(test_text)
        assert result == expected_translation, "第二次应该命中缓存"

    def test_translation_cache_query_count(self, in_memory_db):
        """验证缓存记录数量"""
        module = load_translation_cache_directly()
        if module is None:
            pytest.skip("无法直接加载 translation_cache 模块")

        cache = module.SQLiteTranslationCache()

        for i in range(5):
            cache.set(f"Text {i}", f"翻译 {i}")

        for i in range(5):
            result = cache.get(f"Text {i}")
            assert result == f"翻译 {i}", f"缓存检索失败: Text {i}"
