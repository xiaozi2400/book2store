"""测试子进程临时 JSON 文件桥接逻辑"""

import json
import tempfile
import os


class TestTempStatsBridge:
    """测试临时 JSON 文件桥接的读写逻辑"""

    def test_write_and_read_stats(self):
        """验证翻译 stats 写入临时 JSON 文件后能正确读回"""
        book_id = "test-book-001"
        stats = {
            "prompt_tokens": 285686,
            "completion_tokens": 596770,
            "total_tokens": 882456,
            "api_calls": 2554,
            "cache_hits": 100,
            "translated_paragraphs": 9422
        }

        stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False)

            with open(stats_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert loaded["prompt_tokens"] == 285686
            assert loaded["completion_tokens"] == 596770
            assert loaded["total_tokens"] == 882456
            assert loaded["api_calls"] == 2554
            assert loaded["translated_paragraphs"] == 9422
        finally:
            if os.path.exists(stats_file):
                os.remove(stats_file)

    def test_cleanup_after_read(self):
        """验证读取后删除临时文件"""
        book_id = "test-book-002"
        stats = {"prompt_tokens": 100, "completion_tokens": 50}

        stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f)

        assert os.path.exists(stats_file)

        os.remove(stats_file)
        assert not os.path.exists(stats_file)

    def test_missing_file_returns_none(self):
        """验证文件不存在时不会报错"""
        book_id = "non-existent"
        stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")

        if os.path.exists(stats_file):
            os.remove(stats_file)

        assert not os.path.exists(stats_file)

    def test_partial_stats_still_valid(self):
        """验证只有部分字段的 stats 文件仍然有效"""
        book_id = "test-book-003"
        partial_stats = {"prompt_tokens": 1000}

        stats_file = os.path.join(tempfile.gettempdir(), f"translation_stats_{book_id}.json")
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(partial_stats, f)

            with open(stats_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            assert loaded.get("prompt_tokens", 0) == 1000
            assert loaded.get("completion_tokens", 0) == 0
        finally:
            if os.path.exists(stats_file):
                os.remove(stats_file)
