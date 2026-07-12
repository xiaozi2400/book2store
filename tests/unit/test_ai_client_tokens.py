"""测试 AIClient.chat() 返回 (text, usage) tuple"""

import pytest


class TestAIClientChatReturnsTuple:
    """测试 AIClient 的 chat 方法返回 (text, usage) tuple"""

    @pytest.fixture
    def mock_translator(self, monkeypatch):
        """Mock Translator.chat_raw 返回模拟的 API 响应"""
        import automation.ai_client as ai_client_module

        class MockTranslator:
            def __init__(self, *args, **kwargs):
                pass

            def chat_raw(self, prompt, **kwargs):
                return {
                    "choices": [{"message": {"content": "模拟回复"}}],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150
                    }
                }

        monkeypatch.setattr(ai_client_module, "Translator", MockTranslator)

    def test_chat_returns_tuple(self, mock_translator):
        """验证 chat() 返回 (text, usage) 元组"""
        from automation.ai_client import AIClient

        client = AIClient(provider="deepseek")
        result = client.chat("测试 prompt")

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, usage = result
        assert text == "模拟回复"
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_generate_summary_returns_parsed_dict(self, mock_translator):
        """验证 generate_summary 仍然返回解析后的 dict"""
        from automation.ai_client import AIClient

        client = AIClient(provider="deepseek")
        book_info = {"title": "测试书", "author": "测试作者"}
        result = client.generate_summary(book_info, "测试内容")

        assert isinstance(result, dict)
        # 因为 mock 返回不是 JSON 格式，所以会走 error 路径
        assert "error" in result

    def test_generate_xianyu_listing_returns_tuple(self, mock_translator):
        """验证 generate_xianyu_listing 返回 (text, usage) 元组"""
        from automation.ai_client import AIClient

        client = AIClient(provider="deepseek")
        book_info = {"title": "测试书", "author": "测试作者"}
        result = client.generate_xianyu_listing(book_info)

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, usage = result
        assert text == "模拟回复"
        assert usage["prompt_tokens"] == 100

    def test_generate_xiaohongshu_note_returns_tuple(self, mock_translator):
        """验证 generate_xiaohongshu_note 返回 (text, usage) 元组"""
        from automation.ai_client import AIClient

        client = AIClient(provider="deepseek")
        book_info = {"title": "测试书", "author": "测试作者"}
        result = client.generate_xiaohongshu_note(book_info)

        assert isinstance(result, tuple)
        assert len(result) == 2
        text, usage = result
        assert text == "模拟回复"
        assert usage["prompt_tokens"] == 100
