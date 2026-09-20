"""测试 Translator stats 中的 prompt_tokens / completion_tokens 跟踪"""

import pytest


class MockResponse:
    """模拟 API 响应"""

    def __init__(self, prompt_tokens=100, completion_tokens=50):
        self.status_code = 200
        self._json = {
            "choices": [{"message": {"content": "测试翻译结果"}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


class TestTranslatorStats:
    """测试 Translator stats 中的 token 细分统计"""

    @pytest.fixture
    def translator(self, monkeypatch):
        """创建 Translator 实例并 mock API key"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setenv("DEEPSEEK_API_URL", "https://test.api.com/v1/chat/completions")
        # 需要重载配置模块
        import ebook_translator.config as config

        config.DEEPSEEK_API_KEY = "test-key"
        config.DEEPSEEK_API_URL = "https://test.api.com/v1/chat/completions"

        from ebook_translator.translator.translator import Translator

        t = Translator(provider="deepseek")
        return t

    def test_stats_has_prompt_and_completion_tokens(self, translator):
        """验证 stats 字典包含 prompt_tokens 和 completion_tokens 字段"""
        assert "prompt_tokens" in translator.stats
        assert "completion_tokens" in translator.stats
        assert translator.stats["prompt_tokens"] == 0
        assert translator.stats["completion_tokens"] == 0

    def test_translate_tracks_token_breakdown(self, translator, monkeypatch):
        """验证 translate() 方法分别跟踪 prompt_tokens, completion_tokens, total_tokens"""

        def mock_post(*args, **kwargs):
            return MockResponse(prompt_tokens=200, completion_tokens=80)

        monkeypatch.setattr(translator.session, "post", mock_post)

        result = translator.translate("Hello world")

        assert result == "测试翻译结果"
        assert translator.stats["prompt_tokens"] == 200
        assert translator.stats["completion_tokens"] == 80
        assert translator.stats["total_tokens"] == 280

    def test_chat_tracks_token_breakdown(self, translator, monkeypatch):
        """验证 chat() 方法分别跟踪 prompt_tokens, completion_tokens, total_tokens"""

        def mock_post(*args, **kwargs):
            return MockResponse(prompt_tokens=150, completion_tokens=60)

        monkeypatch.setattr(translator.session, "post", mock_post)

        result = translator.chat("Hello")

        assert result == "测试翻译结果"
        assert translator.stats["prompt_tokens"] == 150
        assert translator.stats["completion_tokens"] == 60
        assert translator.stats["total_tokens"] == 210

    def test_multiple_calls_accumulate_tokens(self, translator, monkeypatch):
        """验证多次 API 调用累计 token 计数"""
        call_count = [0]

        def mock_post(*args, **kwargs):
            call_count[0] += 1
            return MockResponse(prompt_tokens=100, completion_tokens=50)

        monkeypatch.setattr(translator.session, "post", mock_post)

        translator.translate("Hello")
        translator.translate("World")
        translator.chat("Test")

        assert translator.stats["prompt_tokens"] == 300  # 100 + 100 + 100
        assert translator.stats["completion_tokens"] == 150  # 50 + 50 + 50
        assert translator.stats["total_tokens"] == 450  # 150 + 150 + 150

    def test_empty_text_does_not_change_stats(self, translator):
        """验证空文本不影响 stats"""
        translator.translate("")
        translator.chat("")

        assert translator.stats["prompt_tokens"] == 0
        assert translator.stats["completion_tokens"] == 0
        assert translator.stats["total_tokens"] == 0
        assert translator.stats["api_calls"] == 0
