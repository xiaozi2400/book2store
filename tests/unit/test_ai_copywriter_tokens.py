"""
测试 AICopywriter 的 token 记录功能
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestAICopywriterTokenRecording:
    """验证 AICopywriter.generate 解包 tuple 并记录 token"""

    def test_generate_unpacks_xianyu_tuple(self):
        """应解包 generate_xianyu_listing 的 tuple 并传 text 给 write_copywriting"""
        with (
            patch("automation.publishing.ai_copywriter.AIClient") as MockAIClient,
            patch("automation.publishing.ai_copywriter.DatabaseManager") as MockDB,
            patch("automation.metadata_writer.MetadataWriter") as MockMW,
        ):
            ai_instance = MagicMock()
            ai_instance.generate_xianyu_listing.return_value = (
                "【书名】Test Book\n【价格】¥20\n【介绍】好书",
                {"prompt_tokens": 300, "completion_tokens": 150},
            )
            ai_instance.generate_xiaohongshu_note.return_value = (
                "📚 推荐一本好书《Test》",
                {"prompt_tokens": 400, "completion_tokens": 200},
            )
            MockAIClient.return_value = ai_instance

            db_instance = MagicMock()
            MockDB.return_value = db_instance

            mw_instance = MagicMock()
            MockMW.return_value = mw_instance

            from automation.publishing.ai_copywriter import AICopywriter

            copywriter = AICopywriter()

            copywriter.generate("test-book-id", {"title": "Test", "author": "Author"})

            called_xianyu = mw_instance.write_copywriting.call_args[0][1]
            called_xiaohongshu = mw_instance.write_copywriting.call_args[0][2]

            assert isinstance(called_xianyu, str), "xianyu_result 应是字符串"
            assert isinstance(called_xiaohongshu, str), "xiaohongshu_result 应是字符串"
            assert "Test Book" in called_xianyu
            assert "推荐一本好书" in called_xiaohongshu

    def test_generate_records_xianyu_token_usage(self):
        """应记录闲鱼文案的 token 使用"""
        with (
            patch("automation.publishing.ai_copywriter.AIClient") as MockAIClient,
            patch("automation.publishing.ai_copywriter.DatabaseManager") as MockDB,
            patch("automation.metadata_writer.MetadataWriter"),
        ):
            ai_instance = MagicMock()
            ai_instance.generate_xianyu_listing.return_value = (
                "闲鱼文案",
                {"prompt_tokens": 300, "completion_tokens": 150},
            )
            ai_instance.generate_xiaohongshu_note.return_value = (
                "小红书笔记",
                {"prompt_tokens": 400, "completion_tokens": 200},
            )
            MockAIClient.return_value = ai_instance

            db_instance = MagicMock()
            MockDB.return_value = db_instance

            from automation.publishing.ai_copywriter import AICopywriter

            copywriter = AICopywriter()

            copywriter.generate("test-book-id", {"title": "Test"})

            db_instance.record_token_usage.assert_any_call(
                "test-book-id", "copywriting_xianyu", input_tokens=300, output_tokens=150
            )

    def test_generate_records_xiaohongshu_token_usage(self):
        """应记录小红书文案的 token 使用"""
        with (
            patch("automation.publishing.ai_copywriter.AIClient") as MockAIClient,
            patch("automation.publishing.ai_copywriter.DatabaseManager") as MockDB,
            patch("automation.metadata_writer.MetadataWriter"),
        ):
            ai_instance = MagicMock()
            ai_instance.generate_xianyu_listing.return_value = (
                "闲鱼文案",
                {"prompt_tokens": 300, "completion_tokens": 150},
            )
            ai_instance.generate_xiaohongshu_note.return_value = (
                "小红书笔记",
                {"prompt_tokens": 400, "completion_tokens": 200},
            )
            MockAIClient.return_value = ai_instance

            db_instance = MagicMock()
            MockDB.return_value = db_instance

            from automation.publishing.ai_copywriter import AICopywriter

            copywriter = AICopywriter()

            copywriter.generate("test-book-id", {"title": "Test"})

            db_instance.record_token_usage.assert_any_call(
                "test-book-id", "copywriting_xiaohongshu", input_tokens=400, output_tokens=200
            )

    def test_generate_records_both_token_usages(self):
        """应记录闲鱼和小红书两者的 token 使用"""
        with (
            patch("automation.publishing.ai_copywriter.AIClient") as MockAIClient,
            patch("automation.publishing.ai_copywriter.DatabaseManager") as MockDB,
            patch("automation.metadata_writer.MetadataWriter"),
        ):
            ai_instance = MagicMock()
            ai_instance.generate_xianyu_listing.return_value = (
                "闲鱼文案",
                {"prompt_tokens": 100, "completion_tokens": 50},
            )
            ai_instance.generate_xiaohongshu_note.return_value = (
                "小红书笔记",
                {"prompt_tokens": 200, "completion_tokens": 100},
            )
            MockAIClient.return_value = ai_instance

            db_instance = MagicMock()
            MockDB.return_value = db_instance

            from automation.publishing.ai_copywriter import AICopywriter

            copywriter = AICopywriter()

            copywriter.generate("test-book-id", {"title": "Test"})

            assert db_instance.record_token_usage.call_count == 2

    def test_generate_handles_missing_usage(self):
        """usage 为空时应跳过记录"""
        with (
            patch("automation.publishing.ai_copywriter.AIClient") as MockAIClient,
            patch("automation.publishing.ai_copywriter.DatabaseManager") as MockDB,
            patch("automation.metadata_writer.MetadataWriter"),
        ):
            ai_instance = MagicMock()
            ai_instance.generate_xianyu_listing.return_value = ("闲鱼文案", {})
            ai_instance.generate_xiaohongshu_note.return_value = ("小红书笔记", {})
            MockAIClient.return_value = ai_instance

            db_instance = MagicMock()
            MockDB.return_value = db_instance

            from automation.publishing.ai_copywriter import AICopywriter

            copywriter = AICopywriter()

            copywriter.generate("test-book-id", {"title": "Test"})

            db_instance.record_token_usage.assert_not_called()
