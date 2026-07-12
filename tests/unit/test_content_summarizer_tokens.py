"""
测试 SummaryAIGenerator 的 token 记录功能
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestSummaryAIGeneratorTokenRecording:
    """验证 SummaryAIGenerator.generate 能正确解包 chat() tuple 并记录 token"""

    def test_generate_unpacks_chat_tuple(self):
        """generate 应解包 chat() 返回的 (text, usage) tuple"""
        from automation.summarizer.ai_generator import SummaryAIGenerator

        generator = SummaryAIGenerator()
        generator.ai = MagicMock()

        fake_text = '{"content": "这是一段摘要内容"}'
        fake_usage = {"prompt_tokens": 500, "completion_tokens": 300}
        generator.ai.chat.return_value = (fake_text, fake_usage)

        generator.db = MagicMock()
        generator.template_gen = MagicMock()
        generator.template_gen.detect_book_type.return_value = "general"
        generator.template_gen.detect_and_generate_prompt.return_value = MagicMock(
            prompt_for_ai="请总结以下内容：{content}"
        )

        book_info = {"title": "Test Book", "author": "Test Author"}
        chapters = [{"title": "第1章", "content": "这是第一章的内容。"}]

        result = generator.generate("test-book-id", book_info, chapters)

        assert result is not None
        assert result["title"] == "Test Book"
        assert "这是一段摘要内容" in result["content"]

    def test_generate_records_token_usage(self):
        """generate 应在 chat 成功后调用 record_token_usage"""
        from automation.summarizer.ai_generator import SummaryAIGenerator

        generator = SummaryAIGenerator()
        generator.ai = MagicMock()

        fake_text = '{"content": "摘要内容"}'
        fake_usage = {"prompt_tokens": 500, "completion_tokens": 300}
        generator.ai.chat.return_value = (fake_text, fake_usage)

        generator.db = MagicMock()
        generator.template_gen = MagicMock()
        generator.template_gen.detect_book_type.return_value = "general"
        generator.template_gen.detect_and_generate_prompt.return_value = MagicMock(
            prompt_for_ai="请总结：{content}"
        )

        book_info = {"title": "Test", "author": "Author"}
        chapters = [{"title": "第1章", "content": "内容。"}]

        generator.generate("test-book-id", book_info, chapters)

        generator.db.record_token_usage.assert_called_once_with(
            "test-book-id", "summarizing",
            input_tokens=500, output_tokens=300
        )

    def test_generate_handles_missing_usage(self):
        """generate 应在 usage 为空时跳过记录"""
        from automation.summarizer.ai_generator import SummaryAIGenerator

        generator = SummaryAIGenerator()
        generator.ai = MagicMock()

        fake_text = "纯文本内容"
        fake_usage = {}
        generator.ai.chat.return_value = (fake_text, fake_usage)

        generator.db = MagicMock()
        generator.template_gen = MagicMock()
        generator.template_gen.detect_book_type.return_value = "general"
        generator.template_gen.detect_and_generate_prompt.return_value = MagicMock(
            prompt_for_ai="请总结：{content}"
        )

        book_info = {"title": "Test", "author": "Author"}
        chapters = [{"title": "第1章", "content": "内容。"}]

        generator.generate("test-book-id", book_info, chapters)

        generator.db.record_token_usage.assert_not_called()
